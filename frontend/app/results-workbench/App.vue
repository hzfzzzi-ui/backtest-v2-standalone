<script setup>
import { computed, ref, watch } from 'vue';
import { useResultsWorkbenchBridge } from './composables/useResultsWorkbenchBridge.js';
import {
  summarizeSnapshot,
  buildRegimePanelModel,
  buildGovernorPanelModel,
  buildAttributionPanelModel,
} from './helpers/resultsFormatting.js';
import ResultsOverview from './components/ResultsOverview.vue';
import ResultsChart from './components/ResultsChart.vue';
import ResearchComboChart from './components/ResearchComboChart.vue';
import RegimePanel from './components/RegimePanel.vue';
import GovernorPanel from './components/GovernorPanel.vue';
import AttributionPanel from './components/AttributionPanel.vue';
import SymbolRankingPanel from './components/SymbolRankingPanel.vue';
import StageFunnelPanel from './components/StageFunnelPanel.vue';
import TradesPanel from './components/TradesPanel.vue';

const DEFAULT_SECTION_OPEN = Object.freeze({
  core: true,
  analysis: true,
  execution: false,
  audit: false,
});

const { snapshot, patchViewState } = useResultsWorkbenchBridge();
const hasResult = computed(() => !!snapshot.value?.result?.exp_id);
const summary = computed(() => summarizeSnapshot(snapshot.value));
const regimeModel = computed(() => buildRegimePanelModel(snapshot.value));
const governorModel = computed(() => buildGovernorPanelModel(snapshot.value));
const attributionModel = computed(() => buildAttributionPanelModel(snapshot.value));
const isComboResult = computed(() => !!summary.value?.isComboResult);
const comboTruth = computed(() => {
  const artifacts = snapshot.value?.artifacts;
  return artifacts && typeof artifacts === 'object' ? artifacts.comboTruth || null : null;
});
const sectionOpen = ref({ ...DEFAULT_SECTION_OPEN });

function present(value) {
  const text = String(value ?? '').trim();
  return text && text !== '-';
}

function fact(label, value) {
  return present(value) ? { label, value: String(value).trim() } : null;
}

function compactFacts(items) {
  return (Array.isArray(items) ? items : []).filter(Boolean);
}

function compactNotes(items) {
  return (Array.isArray(items) ? items : [])
    .map((item) => String(item ?? '').trim())
    .filter((item) => item && item !== '-');
}

function summarizeMeta(items, limit = 4) {
  const rows = compactFacts(items).slice(0, limit);
  if (!rows.length) return '点击展开查看详情';
  return rows.map((item) => `${item.label} ${item.value}`).join(' · ');
}

function resetSectionOpen() {
  sectionOpen.value = { ...DEFAULT_SECTION_OPEN };
}

function setAllSections(open) {
  const next = !!open;
  sectionOpen.value = {
    core: next,
    analysis: next,
    execution: next,
    audit: next,
  };
}

function onSectionToggle(sectionKey, event) {
  sectionOpen.value = {
    ...sectionOpen.value,
    [sectionKey]: !!event?.target?.open,
  };
}

function resolveComboComponentSnapshot(componentKey, assetScope) {
  if (!isComboResult.value) return null;
  const component = comboTruth.value?.components && typeof comboTruth.value.components === 'object'
    ? comboTruth.value.components[componentKey]
    : null;
  const baseSnapshot = component?.snapshot && typeof component.snapshot === 'object' ? component.snapshot : null;
  if (!baseSnapshot) return null;
  const componentArtifacts = baseSnapshot.artifacts && typeof baseSnapshot.artifacts === 'object'
    ? baseSnapshot.artifacts
    : {};
  const componentRunMeta = componentArtifacts.run_meta && typeof componentArtifacts.run_meta === 'object'
    ? componentArtifacts.run_meta
    : {};
  const componentData = componentRunMeta.data && typeof componentRunMeta.data === 'object'
    ? componentRunMeta.data
    : {};
  return {
    ...baseSnapshot,
    assetContext: {
      ...(baseSnapshot.assetContext || {}),
      asset_scope: assetScope,
    },
    artifacts: {
      ...componentArtifacts,
      run_meta: {
        ...componentRunMeta,
        data: {
          ...componentData,
          asset_scope: assetScope,
        },
      },
    },
    view: snapshot.value?.view || baseSnapshot.view || {},
  };
}

const comboStockSnapshot = computed(() => resolveComboComponentSnapshot('stock', 'cn_a_equity'));
const comboEtfSnapshot = computed(() => resolveComboComponentSnapshot('etf', 'cn_etf'));
const assetScopeLabel = computed(() => {
  if (isComboResult.value) return 'A股组合';
  return summary.value?.assetScope === 'cn_etf' ? 'A股ETF' : 'A股个股';
});
const workspaceBadge = computed(() => `${assetScopeLabel.value}工作台`);
const toolbarTitle = computed(() => (isComboResult.value ? '组合结果总览' : '结果总览'));
const toolbarNote = computed(() => (
  isComboResult.value
    ? '四个结果区已合并到同一页。先看组合主图，再按需展开执行与审计。'
    : '四个结果区已合并到同一页。先看核心结果和图表，再按需展开执行与审计。'
));

const coreFacts = computed(() => compactFacts([
  fact('实验', summary.value.expId),
  fact('状态', summary.value.status),
  fact('范围', assetScopeLabel.value),
  fact('有效起点', summary.value.effectiveExecutionStartDate),
  fact('区间', summary.value.universeRange),
  fact('基准', summary.value.benchmark),
  fact('加载状态', summary.value.groupLoadStatus),
]));

const coreTags = computed(() => compactNotes([
  assetScopeLabel.value,
  summary.value.strategy,
  summary.value.portfolioMode,
  isComboResult.value ? summary.value.comboMode : null,
]));

const analysisMetrics = computed(() => compactFacts([
  fact('CAGR', summary.value.cagr),
  fact('MaxDD', summary.value.maxDrawdown),
  fact('Sharpe', summary.value.sharpe),
  fact('Calmar', summary.value.calmar),
  fact('胜率', summary.value.winRate),
  fact('交易数', summary.value.trades),
]));

const analysisFacts = computed(() => compactFacts([
  fact('实验', summary.value.expId),
  fact('模式', isComboResult.value ? summary.value.comboMode : summary.value.portfolioMode),
  fact('区间', summary.value.universeRange),
  fact('基准', summary.value.benchmark),
  fact('个股腿', isComboResult.value ? summary.value.comboStockExpId : null),
  fact('ETF腿', isComboResult.value ? summary.value.comboEtfExpId : null),
]));

const analysisNotes = computed(() => compactNotes([
  summary.value.strategySummary,
  isComboResult.value && present(summary.value.comboStockTotalReturn)
    ? `个股腿累计收益 ${summary.value.comboStockTotalReturn}`
    : null,
  isComboResult.value && present(summary.value.comboEtfTotalReturn)
    ? `ETF腿累计收益 ${summary.value.comboEtfTotalReturn}`
    : null,
  summary.value.comboReadOnlyNote,
]));

const executionMetrics = computed(() => compactFacts([
  fact('胜率', summary.value.winRate),
  fact('交易数', summary.value.trades),
  fact('换手', summary.value.turnover),
  fact('Profit Factor', summary.value.profitFactor),
  fact('Top10集中度', summary.value.top10ProfitConcentration),
  fact('Top10平均收益', summary.value.top10AvgReturn),
]));

const executionFacts = computed(() => compactFacts([
  fact('池模式', summary.value.universeMode),
  fact('标的数', summary.value.universeCount),
  fact('组合模式', isComboResult.value ? summary.value.comboMode : summary.value.portfolioMode),
  fact('假设', isComboResult.value ? summary.value.comboAssumption : null),
]));

const executionNotes = computed(() => compactNotes([
  isComboResult.value
    ? '组合执行区按腿拆开，默认先展开组合拆解和主腿执行。'
    : '执行区把排名、漏斗和成交拆开放，避免首屏直接堆满表格。',
  present(summary.value.expectancyPerTrade) ? `单笔期望 ${summary.value.expectancyPerTrade}` : null,
  present(summary.value.rollingSharpe) ? `滚动夏普 ${summary.value.rollingSharpe}` : null,
]));

const auditMetrics = computed(() => compactFacts([
  fact('有效状态', summary.value.governedEffectiveState),
  fact('Base State', summary.value.governedBaseState),
  fact('风险预算', summary.value.governedTotalRiskBudget),
  fact('暴露上限', summary.value.governedTotalExposureCap),
  fact('风险倍数', summary.value.governedRiskBudgetMultiplier),
  fact('防守偏置', summary.value.governedDefenseBias),
]));

const auditNotes = computed(() => compactNotes([
  present(summary.value.governedManualOverride) ? `手工覆盖 ${summary.value.governedManualOverride}` : null,
  present(summary.value.governedReasonCodes) ? `状态原因 ${summary.value.governedReasonCodes}` : null,
  present(summary.value.governedBudgetReasonCodes) ? `预算原因 ${summary.value.governedBudgetReasonCodes}` : null,
]));

const coreFoldMeta = computed(() => summarizeMeta([
  fact('实验', summary.value.expId),
  fact('CAGR', summary.value.cagr),
  fact('MaxDD', summary.value.maxDrawdown),
  fact('Sharpe', summary.value.sharpe),
], 4));

const analysisFoldMeta = computed(() => summarizeMeta([
  fact('CAGR', summary.value.cagr),
  fact('总收益', summary.value.totalReturn),
  isComboResult.value ? fact('个股腿', summary.value.comboStockTotalReturn) : fact('胜率', summary.value.winRate),
  isComboResult.value ? fact('ETF腿', summary.value.comboEtfTotalReturn) : fact('交易数', summary.value.trades),
], 4));

const executionFoldMeta = computed(() => summarizeMeta([
  fact('胜率', summary.value.winRate),
  fact('交易数', summary.value.trades),
  fact('换手', summary.value.turnover),
  fact('标的数', summary.value.universeCount),
], 4));

const auditFoldMeta = computed(() => summarizeMeta([
  fact('有效状态', summary.value.governedEffectiveState),
  fact('风险预算', summary.value.governedTotalRiskBudget),
  fact('暴露上限', summary.value.governedTotalExposureCap),
  fact('防守偏置', summary.value.governedDefenseBias),
], 4));

watch(hasResult, (next) => {
  if (!next) resetSectionOpen();
});
</script>

<template>
  <div class="wb-results-workbench-shell">
    <template v-if="hasResult">
      <header class="wb-results-toolbar">
        <div class="wb-results-toolbar-main">
          <h2 class="wb-results-toolbar-title">{{ toolbarTitle }}</h2>
          <p class="wb-results-toolbar-note">{{ toolbarNote }}</p>
        </div>
        <div class="wb-results-toolbar-actions">
          <button type="button" class="wb-results-toolbar-action" @click="setAllSections(true)">展开全部</button>
          <button type="button" class="wb-results-toolbar-action" @click="setAllSections(false)">收起全部</button>
          <span class="wb-results-toolbar-badge">{{ workspaceBadge }}</span>
        </div>
      </header>

      <section class="wb-results-stack">
        <details class="wb-acc wb-results-fold" :open="sectionOpen.core" @toggle="onSectionToggle('core', $event)">
          <summary>
            <span class="wb-results-fold-summary-main">
              <span class="wb-results-fold-title">核心结果</span>
              <span class="wb-results-fold-note">运行摘要、当前锚点和策略口径。</span>
            </span>
            <span class="wb-results-fold-meta">{{ coreFoldMeta }}</span>
          </summary>
          <div class="wb-acc-body wb-results-fold-body">
            <section class="wb-results-stage wb-results-stage-solo">
              <div class="wb-results-stage-main">
                <ResultsOverview :summary="summary" mode="headline" />
              </div>
              <aside class="wb-results-stage-rail">
                <article class="wb-workbench-rail-card wb-workbench-rail-card-strong">
                  <span class="wb-workbench-rail-kicker">Workspace</span>
                  <h3 class="wb-workbench-rail-title">当前锚点</h3>
                  <dl class="wb-workbench-rail-list">
                    <div v-for="item in coreFacts" :key="item.label">
                      <dt>{{ item.label }}</dt>
                      <dd>{{ item.value }}</dd>
                    </div>
                  </dl>
                </article>

                <article class="wb-workbench-rail-card">
                  <span class="wb-workbench-rail-kicker">Context</span>
                  <h3 class="wb-workbench-rail-title">策略口径</h3>
                  <p class="wb-workbench-rail-note">{{ summary.strategySummary }}</p>
                  <div v-if="coreTags.length" class="wb-workbench-rail-pills">
                    <span v-for="tag in coreTags" :key="tag" class="wb-workbench-rail-pill">{{ tag }}</span>
                  </div>
                </article>
              </aside>
            </section>
          </div>
        </details>

        <details class="wb-acc wb-results-fold" :open="sectionOpen.analysis" @toggle="onSectionToggle('analysis', $event)">
          <summary>
            <span class="wb-results-fold-summary-main">
              <span class="wb-results-fold-title">图表分析</span>
              <span class="wb-results-fold-note">主图区优先，右侧只保留关键指标和当前口径。</span>
            </span>
            <span class="wb-results-fold-meta">{{ analysisFoldMeta }}</span>
          </summary>
          <div class="wb-acc-body wb-results-fold-body">
            <section class="wb-results-stage wb-results-stage-solo">
              <div class="wb-results-stage-main">
                <template v-if="isComboResult">
                  <ResearchComboChart
                    :snapshot="snapshot"
                    :patch-view-state="patchViewState"
                    section-mode="overview"
                  />
                </template>
                <template v-else>
                  <ResultsChart :snapshot="snapshot" :patch-view-state="patchViewState" />
                </template>
              </div>

              <aside class="wb-results-stage-rail wb-results-stage-rail-sticky">
                <article class="wb-workbench-rail-card wb-workbench-rail-card-strong">
                  <span class="wb-workbench-rail-kicker">Chart Desk</span>
                  <h3 class="wb-workbench-rail-title">主图区上下文</h3>
                  <div class="wb-workbench-rail-metrics">
                    <div v-for="item in analysisMetrics" :key="item.label" class="wb-workbench-rail-metric">
                      <span>{{ item.label }}</span>
                      <strong>{{ item.value }}</strong>
                    </div>
                  </div>
                </article>

                <article class="wb-workbench-rail-card">
                  <span class="wb-workbench-rail-kicker">Scope</span>
                  <h3 class="wb-workbench-rail-title">当前口径</h3>
                  <dl class="wb-workbench-rail-list">
                    <div v-for="item in analysisFacts" :key="item.label">
                      <dt>{{ item.label }}</dt>
                      <dd>{{ item.value }}</dd>
                    </div>
                  </dl>
                </article>

                <article v-if="analysisNotes.length" class="wb-workbench-rail-card">
                  <span class="wb-workbench-rail-kicker">Notes</span>
                  <h3 class="wb-workbench-rail-title">阅读提示</h3>
                  <ul class="wb-workbench-rail-notes">
                    <li v-for="note in analysisNotes" :key="note">{{ note }}</li>
                  </ul>
                </article>
              </aside>
            </section>
          </div>
        </details>

        <details class="wb-acc wb-results-fold" :open="sectionOpen.execution" @toggle="onSectionToggle('execution', $event)">
          <summary>
            <span class="wb-results-fold-summary-main">
              <span class="wb-results-fold-title">交易与信号</span>
              <span class="wb-results-fold-note">排名、漏斗和成交拆成纵向工作流，按需展开。</span>
            </span>
            <span class="wb-results-fold-meta">{{ executionFoldMeta }}</span>
          </summary>
          <div class="wb-acc-body wb-results-fold-body">
            <section class="wb-results-stage wb-results-stage-execution">
              <div class="wb-results-stage-main">
                <section class="wb-results-inline-grid">
                  <article class="wb-workbench-rail-card wb-workbench-rail-card-strong">
                    <span class="wb-workbench-rail-kicker">Execution</span>
                    <h3 class="wb-workbench-rail-title">执行概览</h3>
                    <div class="wb-workbench-rail-metrics">
                      <div v-for="item in executionMetrics" :key="item.label" class="wb-workbench-rail-metric">
                        <span>{{ item.label }}</span>
                        <strong>{{ item.value }}</strong>
                      </div>
                    </div>
                  </article>

                  <article class="wb-workbench-rail-card">
                    <span class="wb-workbench-rail-kicker">Universe</span>
                    <h3 class="wb-workbench-rail-title">当前执行口径</h3>
                    <dl class="wb-workbench-rail-list">
                      <div v-for="item in executionFacts" :key="item.label">
                        <dt>{{ item.label }}</dt>
                        <dd>{{ item.value }}</dd>
                      </div>
                    </dl>
                  </article>

                  <article v-if="executionNotes.length" class="wb-workbench-rail-card">
                    <span class="wb-workbench-rail-kicker">Notes</span>
                    <h3 class="wb-workbench-rail-title">使用提示</h3>
                    <ul class="wb-workbench-rail-notes">
                      <li v-for="note in executionNotes" :key="note">{{ note }}</li>
                    </ul>
                  </article>
                </section>

                <section v-if="isComboResult" class="wb-results-subtab-shell">
                  <details class="wb-acc wb-workbench-acc" open>
                    <summary>双腿拆解</summary>
                    <div class="wb-acc-body wb-workbench-acc-body">
                      <ResearchComboChart
                        :snapshot="snapshot"
                        :patch-view-state="patchViewState"
                        section-mode="sleeves"
                      />
                    </div>
                  </details>

                  <details v-if="comboStockSnapshot" class="wb-acc wb-workbench-acc" open>
                    <summary>个股腿执行</summary>
                    <div class="wb-acc-body wb-workbench-acc-body">
                      <div class="wb-section-head">
                        <div>
                          <h3 class="wb-section-title">个股腿执行</h3>
                          <p class="wb-section-note">把排名、漏斗和成交拆开放，避免首屏同时压满表格。</p>
                        </div>
                      </div>
                      <SymbolRankingPanel
                        :snapshot="comboStockSnapshot"
                        :patch-view-state="patchViewState"
                        panel-id="comboStockSymbolPanel"
                      />
                      <section class="wb-results-sections">
                        <StageFunnelPanel :snapshot="comboStockSnapshot" :patch-view-state="patchViewState" />
                        <TradesPanel :snapshot="comboStockSnapshot" :patch-view-state="patchViewState" />
                      </section>
                    </div>
                  </details>

                  <details v-if="comboEtfSnapshot" class="wb-acc wb-workbench-acc">
                    <summary>ETF 腿执行</summary>
                    <div class="wb-acc-body wb-workbench-acc-body">
                      <div class="wb-section-head">
                        <div>
                          <h3 class="wb-section-title">ETF 腿执行</h3>
                          <p class="wb-section-note">默认收住次级信息，需要时再展开，不和主图区抢注意力。</p>
                        </div>
                      </div>
                      <SymbolRankingPanel
                        :snapshot="comboEtfSnapshot"
                        :patch-view-state="patchViewState"
                        panel-id="comboEtfSymbolPanel"
                      />
                      <section class="wb-results-sections">
                        <StageFunnelPanel :snapshot="comboEtfSnapshot" :patch-view-state="patchViewState" />
                        <TradesPanel :snapshot="comboEtfSnapshot" :patch-view-state="patchViewState" />
                      </section>
                    </div>
                  </details>
                </section>

                <section v-else class="wb-results-subtab-shell wb-results-execution-grid">
                  <div class="wb-results-execution-primary">
                    <SymbolRankingPanel :snapshot="snapshot" :patch-view-state="patchViewState" />
                  </div>
                  <div class="wb-results-execution-dock">
                    <StageFunnelPanel :snapshot="snapshot" :patch-view-state="patchViewState" />
                    <TradesPanel :snapshot="snapshot" :patch-view-state="patchViewState" />
                  </div>
                </section>
              </div>

              <aside class="wb-results-stage-rail">
                <article class="wb-workbench-rail-card wb-workbench-rail-card-strong">
                  <span class="wb-workbench-rail-kicker">Execution</span>
                  <h3 class="wb-workbench-rail-title">执行概览</h3>
                  <div class="wb-workbench-rail-metrics">
                    <div v-for="item in executionMetrics" :key="item.label" class="wb-workbench-rail-metric">
                      <span>{{ item.label }}</span>
                      <strong>{{ item.value }}</strong>
                    </div>
                  </div>
                </article>

                <article class="wb-workbench-rail-card">
                  <span class="wb-workbench-rail-kicker">Universe</span>
                  <h3 class="wb-workbench-rail-title">当前执行口径</h3>
                  <dl class="wb-workbench-rail-list">
                    <div v-for="item in executionFacts" :key="item.label">
                      <dt>{{ item.label }}</dt>
                      <dd>{{ item.value }}</dd>
                    </div>
                  </dl>
                </article>

                <article v-if="executionNotes.length" class="wb-workbench-rail-card">
                  <span class="wb-workbench-rail-kicker">Notes</span>
                  <h3 class="wb-workbench-rail-title">使用提示</h3>
                  <ul class="wb-workbench-rail-notes">
                    <li v-for="note in executionNotes" :key="note">{{ note }}</li>
                  </ul>
                </article>
              </aside>
            </section>
          </div>
        </details>

        <details class="wb-acc wb-results-fold" :open="sectionOpen.audit" @toggle="onSectionToggle('audit', $event)">
          <summary>
            <span class="wb-results-fold-summary-main">
              <span class="wb-results-fold-title">深层审计</span>
              <span class="wb-results-fold-note">环境、预算和归因拆成独立审计区，默认收起。</span>
            </span>
            <span class="wb-results-fold-meta">{{ auditFoldMeta }}</span>
          </summary>
          <div class="wb-acc-body wb-results-fold-body">
            <section class="wb-results-stage wb-results-stage-solo">
              <div class="wb-results-stage-main">
                <div class="wb-results-audit-grid">
                  <RegimePanel :model="regimeModel" />
                  <GovernorPanel :model="governorModel" />
                  <AttributionPanel :model="attributionModel" />
                </div>
              </div>

              <aside class="wb-results-stage-rail">
                <article class="wb-workbench-rail-card wb-workbench-rail-card-strong">
                  <span class="wb-workbench-rail-kicker">Audit</span>
                  <h3 class="wb-workbench-rail-title">治理快照</h3>
                  <div class="wb-workbench-rail-metrics">
                    <div v-for="item in auditMetrics" :key="item.label" class="wb-workbench-rail-metric">
                      <span>{{ item.label }}</span>
                      <strong>{{ item.value }}</strong>
                    </div>
                  </div>
                </article>

                <article v-if="auditNotes.length" class="wb-workbench-rail-card">
                  <span class="wb-workbench-rail-kicker">Audit Trail</span>
                  <h3 class="wb-workbench-rail-title">审计提示</h3>
                  <ul class="wb-workbench-rail-notes">
                    <li v-for="note in auditNotes" :key="note">{{ note }}</li>
                  </ul>
                </article>
              </aside>
            </section>
          </div>
        </details>
      </section>
    </template>

    <section v-else class="wb-empty" style="min-height: 220px;">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
      <span>运行或加载实验后，在这里查看结果工作台。</span>
    </section>
  </div>
</template>
