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
import ResearchComboPanel from './components/ResearchComboPanel.vue';
import SymbolRankingPanel from './components/SymbolRankingPanel.vue';
import StageFunnelPanel from './components/StageFunnelPanel.vue';
import TradesPanel from './components/TradesPanel.vue';
import AgentReportPanel from './components/AgentReportPanel.vue';

const { snapshot, patchViewState } = useResultsWorkbenchBridge();
const hasResult = computed(() => !!snapshot.value?.result?.exp_id);
const summary = computed(() => summarizeSnapshot(snapshot.value));
const regimeModel = computed(() => buildRegimePanelModel(snapshot.value));
const governorModel = computed(() => buildGovernorPanelModel(snapshot.value));
const attributionModel = computed(() => buildAttributionPanelModel(snapshot.value));
const isResearchCombo = computed(() => !!summary.value?.isResearchCombo);
const comboTruth = computed(() => {
  const artifacts = snapshot.value?.artifacts;
  return artifacts && typeof artifacts === 'object' ? artifacts.comboTruth || null : null;
});
const researchComboComponents = computed(() => {
  const components = comboTruth.value?.components;
  return components && typeof components === 'object'
    ? components
    : (snapshot.value?.artifacts?.researchComboComponents || null);
});

function resolveComboComponentSnapshot(componentKey, assetScope) {
  if (!isResearchCombo.value) return null;
  const component = researchComboComponents.value && typeof researchComboComponents.value === 'object'
    ? researchComboComponents.value[componentKey]
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
const activeTab = ref('performance');

watch(hasResult, (next) => {
  if (!next) activeTab.value = 'performance';
});
</script>

<template>
  <div class="wb-results-workbench-shell">
    <template v-if="hasResult">
      <nav class="wb-results-tabs" aria-label="结果面板">
        <button class="wb-results-tab" :class="{ active: activeTab === 'performance' }" @click="activeTab = 'performance'">Performance</button>
        <button class="wb-results-tab" :class="{ active: activeTab === 'regime' }" @click="activeTab = 'regime'">Regime</button>
        <button class="wb-results-tab" :class="{ active: activeTab === 'governor' }" @click="activeTab = 'governor'">Governor</button>
        <button class="wb-results-tab" :class="{ active: activeTab === 'attribution' }" @click="activeTab = 'attribution'">Attribution</button>
      </nav>

      <section v-if="activeTab === 'performance'" class="wb-workbench-panel">
        <ResultsOverview :summary="summary" />
        <ResearchComboChart v-if="isResearchCombo" :snapshot="snapshot" :patch-view-state="patchViewState" />
        <ResultsChart v-else :snapshot="snapshot" :patch-view-state="patchViewState" />
        <ResearchComboPanel v-if="isResearchCombo" :summary="summary" />
        <template v-if="isResearchCombo">
          <SymbolRankingPanel
            v-if="comboStockSnapshot"
            :snapshot="comboStockSnapshot"
            :patch-view-state="patchViewState"
            panel-id="comboStockSymbolPanel"
          />
          <SymbolRankingPanel
            v-if="comboEtfSnapshot"
            :snapshot="comboEtfSnapshot"
            :patch-view-state="patchViewState"
            panel-id="comboEtfSymbolPanel"
          />
          <section v-if="comboStockSnapshot" class="wb-results-sections">
            <StageFunnelPanel :snapshot="comboStockSnapshot" :patch-view-state="patchViewState" />
            <TradesPanel :snapshot="comboStockSnapshot" :patch-view-state="patchViewState" />
          </section>
        </template>
        <template v-else>
          <SymbolRankingPanel :snapshot="snapshot" :patch-view-state="patchViewState" />
          <section class="wb-results-sections">
            <StageFunnelPanel :snapshot="snapshot" :patch-view-state="patchViewState" />
            <TradesPanel :snapshot="snapshot" :patch-view-state="patchViewState" />
          </section>
        </template>
        <AgentReportPanel :snapshot="snapshot" />
      </section>

      <RegimePanel v-else-if="activeTab === 'regime'" :model="regimeModel" />
      <GovernorPanel v-else-if="activeTab === 'governor'" :model="governorModel" />
      <AttributionPanel v-else :model="attributionModel" />
    </template>
    <section v-else class="wb-empty" style="min-height: 220px;">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
      <span>运行或加载实验后，在这里查看结果工作台。</span>
    </section>
  </div>
</template>
