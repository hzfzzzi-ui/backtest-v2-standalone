<script setup>
import { computed } from 'vue';
import { useResultsWorkbenchBridge } from './composables/useResultsWorkbenchBridge.js';
import { summarizeSnapshot } from './helpers/resultsFormatting.js';
import ResultsOverview from './components/ResultsOverview.vue';
import ResultsChart from './components/ResultsChart.vue';
import SymbolRankingPanel from './components/SymbolRankingPanel.vue';
import StageFunnelPanel from './components/StageFunnelPanel.vue';
import TradesPanel from './components/TradesPanel.vue';
import AgentReportPanel from './components/AgentReportPanel.vue';

const { snapshot, patchViewState } = useResultsWorkbenchBridge();
const hasResult = computed(() => !!snapshot.value?.result?.exp_id);
const summary = computed(() => summarizeSnapshot(snapshot.value));
</script>

<template>
  <div class="wb-results-workbench-shell">
    <template v-if="hasResult">
      <ResultsOverview :summary="summary" />
      <ResultsChart :snapshot="snapshot" :patch-view-state="patchViewState" />
      <SymbolRankingPanel :snapshot="snapshot" :patch-view-state="patchViewState" />
      <section class="wb-results-sections">
        <StageFunnelPanel :snapshot="snapshot" :patch-view-state="patchViewState" />
        <TradesPanel :snapshot="snapshot" :patch-view-state="patchViewState" />
      </section>
      <AgentReportPanel :snapshot="snapshot" />
    </template>
    <section v-else class="wb-empty" style="min-height: 220px;">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
      <span>运行或加载实验后，在这里查看结果工作台。</span>
    </section>
  </div>
</template>
