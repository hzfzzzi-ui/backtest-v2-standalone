<script setup>
import { computed } from 'vue';
import { buildReadableStageFunnelModel } from '../helpers/stageFunnelFormatting.js';

const props = defineProps({
  snapshot: {
    type: Object,
    required: true,
  },
  patchViewState: {
    type: Function,
    required: true,
  },
});

const view = computed(() => props.snapshot?.view || {});
const open = computed(() => !!view.value.openPanels?.funnelPanel);
const funnel = computed(() => buildReadableStageFunnelModel(props.snapshot));

function togglePanel() {
  props.patchViewState({ openPanels: { funnelPanel: !open.value } });
}

function toneClass(tone) {
  if (tone === 'ok') return 'wb-funnel-v2-status-ok';
  if (tone === 'derived') return 'wb-funnel-v2-status-derived';
  return 'wb-funnel-v2-status-missing';
}
</script>

<template>
  <section class="wb-result-acc" data-result-panel="funnelPanel" :class="{ 'wb-open': open }">
    <button type="button" class="wb-result-acc-toggle" :aria-expanded="String(open)" @click="togglePanel">
      <span class="wb-acc-summary-main">
        <span class="wb-acc-summary-title">交易漏斗</span>
      </span>
      <span class="wb-mini wb-acc-summary-meta">{{ funnel.meta }}</span>
    </button>
    <div class="wb-result-acc-body" :hidden="!open">
      <div class="wb-funnel-v2">
        <div class="wb-funnel-v2-summary">
          <article v-for="card in funnel.summaryCards" :key="card.label" class="wb-funnel-v2-summary-card">
            <span class="wb-mini">{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
          </article>
        </div>

        <section class="wb-funnel-v2-section">
          <div class="wb-funnel-v2-section-head">
            <div>
              <div class="wb-symbol-title">买入主链</div>
              <div class="wb-mini">把 S1-S7 单独展开，避免执行和退出统计混进同一条链路。</div>
            </div>
          </div>
          <div class="wb-funnel-v2-chain">
            <article v-for="stage in funnel.chainStages" :key="stage.key" class="wb-funnel-v2-stage">
              <div class="wb-funnel-v2-stage-top">
                <div>
                  <div class="wb-funnel-v2-stage-code">{{ stage.key.toUpperCase() }}</div>
                  <div class="wb-funnel-v2-stage-title">{{ stage.title }}</div>
                </div>
                <span class="wb-funnel-v2-stage-status" :class="toneClass(stage.status.tone)">{{ stage.status.label }}</span>
              </div>
              <div class="wb-mini wb-funnel-v2-stage-note">{{ stage.note || '当前没有额外说明。' }}</div>
              <div class="wb-funnel-v2-metrics">
                <div v-for="metric in stage.metrics" :key="metric.label" class="wb-funnel-v2-metric">
                  <span>{{ metric.label }}</span>
                  <strong>{{ metric.text }}</strong>
                </div>
              </div>
              <div v-if="stage.pills.length" class="wb-funnel-v2-pills">
                <span v-for="pill in stage.pills" :key="`${stage.key}-${pill.label}`" class="wb-funnel-v2-pill">
                  {{ pill.label }} {{ pill.text }}
                </span>
              </div>
            </article>
          </div>
        </section>

        <div class="wb-funnel-v2-side-grid">
          <section class="wb-funnel-v2-section">
            <div class="wb-funnel-v2-section-head">
              <div>
                <div class="wb-symbol-title">S8 执行与约束</div>
                <div class="wb-mini">把买入约束和卖出风险控制拆成两个桶，不再混成一行三列数字。</div>
              </div>
            </div>
            <div class="wb-funnel-v2-execution-grid">
              <article class="wb-funnel-v2-stage">
                <div class="wb-funnel-v2-stage-top">
                  <div>
                    <div class="wb-funnel-v2-stage-code">BUY</div>
                    <div class="wb-funnel-v2-stage-title">买入阻塞</div>
                  </div>
                </div>
                <div class="wb-funnel-v2-metrics">
                  <div v-for="metric in funnel.execution.buySide" :key="metric.label" class="wb-funnel-v2-metric">
                    <span>{{ metric.label }}</span>
                    <strong>{{ metric.text }}</strong>
                  </div>
                </div>
              </article>
              <article class="wb-funnel-v2-stage">
                <div class="wb-funnel-v2-stage-top">
                  <div>
                    <div class="wb-funnel-v2-stage-code">SELL</div>
                    <div class="wb-funnel-v2-stage-title">风险缩放</div>
                  </div>
                </div>
                <div class="wb-funnel-v2-metrics">
                  <div v-for="metric in funnel.execution.sellSide" :key="metric.label" class="wb-funnel-v2-metric">
                    <span>{{ metric.label }}</span>
                    <strong>{{ metric.text }}</strong>
                  </div>
                </div>
              </article>
            </div>
          </section>

          <section class="wb-funnel-v2-section">
            <div class="wb-funnel-v2-section-head">
              <div>
                <div class="wb-symbol-title">S9 退出分布</div>
                <div class="wb-mini">退出不再强行塞进买入漏斗，单独展示原因、次数和占比。</div>
              </div>
            </div>
            <div v-if="funnel.exitReasons.length" class="wb-funnel-v2-exit-list">
              <div v-for="reason in funnel.exitReasons" :key="reason.code" class="wb-funnel-v2-exit-row">
                <div class="wb-funnel-v2-exit-meta">
                  <span>{{ reason.label }}</span>
                  <span class="wb-mini">{{ reason.code }}</span>
                </div>
                <div class="wb-funnel-v2-exit-stat">
                  <strong>{{ reason.text }}</strong>
                  <span class="wb-mini">{{ reason.ratioText }}</span>
                </div>
                <div class="wb-funnel-v2-exit-bar">
                  <span :style="{ width: `${Math.max(6, reason.ratio * 100)}%` }"></span>
                </div>
              </div>
            </div>
            <div v-else class="wb-mini">当前没有退出原因数据。</div>
          </section>
        </div>

        <section class="wb-funnel-v2-section">
          <div class="wb-funnel-v2-section-head">
            <div>
              <div class="wb-symbol-title">口径说明</div>
              <div class="wb-mini">明确告诉你哪些阶段是后端真实计数，哪些只是汇总或暂时没有独立计数。</div>
            </div>
          </div>
          <ul class="wb-funnel-v2-notes">
            <li v-for="note in funnel.completenessNotes" :key="note" class="wb-funnel-v2-note">{{ note }}</li>
          </ul>
        </section>
      </div>
    </div>
  </section>
</template>
