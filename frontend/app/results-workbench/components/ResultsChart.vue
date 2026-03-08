<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { fmtNum } from '../helpers/resultsFormatting.js';

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

const chartRef = ref(null);
const symbolSeriesCache = ref({});

const artifacts = computed(() => props.snapshot?.artifacts || {});
const view = computed(() => props.snapshot?.view || {});
const symbolRows = computed(() => Array.isArray(artifacts.value.symbolPerformanceRows) ? artifacts.value.symbolPerformanceRows : []);

const selectedSymbol = computed(() => {
  const explicit = String(view.value.selectedSymbol || '').trim().toLowerCase();
  if (explicit) return explicit;
  return String(symbolRows.value[0]?.symbol || '').trim().toLowerCase();
});

const isSymbolMode = computed(() => view.value.chartMode === 'symbol' && !!selectedSymbol.value);

const ensureSymbolSeries = async () => {
  if (!isSymbolMode.value) return null;
  if (symbolSeriesCache.value[selectedSymbol.value]) return symbolSeriesCache.value[selectedSymbol.value];
  if (typeof window.loadSymbolSeries !== 'function') return null;
  const loaded = await window.loadSymbolSeries(selectedSymbol.value, artifacts.value.navSeries || []);
  symbolSeriesCache.value = {
    ...symbolSeriesCache.value,
    [selectedSymbol.value]: loaded || { points: [], ohlc: [], suspensionRanges: [] },
  };
  return symbolSeriesCache.value[selectedSymbol.value];
};

const chartFooter = computed(() => {
  const benchmarkOhlc = Array.isArray(artifacts.value.benchmarkOhlc) ? artifacts.value.benchmarkOhlc : [];
  if (isSymbolMode.value) {
    const cache = symbolSeriesCache.value[selectedSymbol.value] || {};
    const ohlc = Array.isArray(cache.ohlc) ? cache.ohlc : [];
    const firstClose = Number(ohlc[0]?.close);
    const lastClose = Number(ohlc[ohlc.length - 1]?.close);
    const firstBench = Number(benchmarkOhlc[0]?.close);
    const lastBench = Number(benchmarkOhlc[benchmarkOhlc.length - 1]?.close);
    const symbolRel = Number.isFinite(firstClose) && firstClose > 0 && Number.isFinite(lastClose) ? lastClose / firstClose : Number.NaN;
    const benchRel = Number.isFinite(firstBench) && firstBench > 0 && Number.isFinite(lastBench) ? lastBench / firstBench : Number.NaN;
    return [
      `个股收盘价 ${Number.isFinite(lastClose) ? `${fmtNum(lastClose, 2)}元` : '-'}`,
      `标的 ${String(selectedSymbol.value || '').toUpperCase()}`,
      Number.isFinite(symbolRel) ? `个股相对起点 ${fmtNum(symbolRel, 2)}x` : null,
      Number.isFinite(benchRel) && view.value.showBenchmark ? `基准相对起点 ${fmtNum(benchRel, 2)}x` : null,
    ].filter(Boolean).join(' | ');
  }
  const navSeries = Array.isArray(artifacts.value.navSeries) ? artifacts.value.navSeries : [];
  const benchmarkSource = artifacts.value.benchmarkSource || 'api';
  return `净值 ${String(navSeries.length || 0)} 点 | 基准来源 ${benchmarkSource}`;
});

const groupLoadStatus = computed(() => {
  const missing = Array.isArray(artifacts.value.missing) ? artifacts.value.missing : [];
  return missing.length ? `缺少 ${missing.length} 个产物，请查看状态中心` : '产物已加载';
});

async function redrawChart() {
  if (!chartRef.value || typeof window.renderNavChartLW !== 'function') return;
  if (isSymbolMode.value) await ensureSymbolSeries();
  await nextTick();
  const benchmarkOhlc = Array.isArray(artifacts.value.benchmarkOhlc) ? artifacts.value.benchmarkOhlc : [];
  const navSeries = Array.isArray(artifacts.value.navSeries) ? artifacts.value.navSeries : [];
  const chartRange = String(view.value.chartRange || 'D');
  const aggregateNav = typeof window.aggregateNav === 'function' ? window.aggregateNav : ((rows) => rows || []);
  const aggregateOhlc = typeof window.aggregateOhlc === 'function' ? window.aggregateOhlc : ((rows) => rows || []);
  const cache = symbolSeriesCache.value[selectedSymbol.value] || {};
  const rawSeries = isSymbolMode.value
    ? (Array.isArray(cache.ohlc) ? cache.ohlc.map((item) => ({ date: item.time, value: Number(item.close) })) : [])
    : navSeries;
  const ohlc = isSymbolMode.value ? (cache.ohlc || []) : [];
  const lastClose = Number(ohlc[ohlc.length - 1]?.close);
  const markers = isSymbolMode.value && typeof window.symbolTradeMarkers === 'function'
    ? window.symbolTradeMarkers(selectedSymbol.value, artifacts.value.tradesRows || [])
    : [];
  const marketStates = !isSymbolMode.value ? (artifacts.value.marketStates || []) : [];
  const suspensionRanges = isSymbolMode.value ? (cache.suspensionRanges || []) : [];

  window.renderNavChartLW(
    chartRef.value.id,
    aggregateOhlc(benchmarkOhlc, chartRange),
    aggregateNav(rawSeries, chartRange),
    !!view.value.showBenchmark,
    {
      mode: isSymbolMode.value ? 'symbol' : 'portfolio',
      markers,
      marketStates,
      suspensionRanges,
      symbolLastClose: lastClose,
    },
  );
}

function onChartModeChange(event) {
  props.patchViewState({ chartMode: String(event.target.value || 'portfolio') });
}

function onChartRangeChange(event) {
  props.patchViewState({ chartRange: String(event.target.value || 'D') });
}

function onShowBenchmarkChange(event) {
  props.patchViewState({ showBenchmark: !!event.target.checked });
}

onMounted(async () => {
  if (!view.value.selectedSymbol && symbolRows.value[0]?.symbol) {
    props.patchViewState({ selectedSymbol: String(symbolRows.value[0].symbol || '').toLowerCase() });
  }
  await redrawChart();
});

watch(
  () => [props.snapshot?.updatedAt, view.value.chartMode, view.value.chartRange, view.value.showBenchmark, selectedSymbol.value],
  async () => {
    await redrawChart();
  },
);
</script>

<template>
  <section class="wb-canvas">
    <div class="wb-canvas-head">
      <div class="wb-canvas-info">
        <span class="wb-canvas-kicker">结果主图</span>
        <span class="wb-mini">{{ groupLoadStatus }}</span>
      </div>
      <div class="wb-inline wb-canvas-tools">
        <select :value="view.chartMode || 'portfolio'" class="formInput wb-input-sm" @change="onChartModeChange">
          <option value="portfolio">组合</option>
          <option value="symbol">个股</option>
        </select>
        <label class="wb-check-label">
          <input :checked="!!view.showBenchmark" type="checkbox" @change="onShowBenchmarkChange" />
          对比基准
        </label>
        <select :value="view.chartRange || 'D'" class="formInput wb-input-sm" @change="onChartRangeChange">
          <option value="D">日K</option>
          <option value="W">周K</option>
          <option value="M">月K</option>
          <option value="Y">年K</option>
        </select>
      </div>
    </div>

    <div id="wbResultsWorkbenchChart" ref="chartRef" class="wb-chart wb-chart-main">
      <div class="wb-empty">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
        <span>运行实验后，在这里查看净值和基准走势。</span>
      </div>
    </div>

    <div class="wb-canvas-footer">
      <div class="wb-mini">{{ chartFooter }}</div>
    </div>
  </section>
</template>
