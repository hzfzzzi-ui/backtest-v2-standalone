<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

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

const comboChartRef = ref(null);
const stockTopChartRef = ref(null);
const stockBottomChartRef = ref(null);
const etfTopChartRef = ref(null);
const etfBottomChartRef = ref(null);

const benchmarkCache = ref({});
const chartDisposers = [];

const COMBO_VISIBLE_BARS = 96;

const artifacts = computed(() => props.snapshot?.artifacts || {});
const view = computed(() => props.snapshot?.view || {});
const comboNavRows = computed(() => (Array.isArray(artifacts.value.nav) ? artifacts.value.nav : []));
const comboTruth = computed(() => {
  const payload = artifacts.value.comboTruth;
  return payload && typeof payload === 'object' ? payload : {};
});
const comboComponents = computed(() => {
  const payload = comboTruth.value.components;
  if (payload && typeof payload === 'object') return payload;
  const legacyPayload = artifacts.value.researchComboComponents;
  return legacyPayload && typeof legacyPayload === 'object' ? legacyPayload : {};
});

function normalizeComboComponent(componentPayload, fallbackBenchmarkSymbol) {
  const payload = componentPayload && typeof componentPayload === 'object' ? componentPayload : null;
  if (!payload) return null;
  const snapshot = payload.snapshot && typeof payload.snapshot === 'object' ? payload.snapshot : null;
  const snapshotArtifacts = snapshot?.artifacts && typeof snapshot.artifacts === 'object'
    ? snapshot.artifacts
    : null;
  if (snapshotArtifacts) {
    const runMeta = snapshotArtifacts.run_meta && typeof snapshotArtifacts.run_meta === 'object'
      ? snapshotArtifacts.run_meta
      : {};
    const navRows = Array.isArray(snapshotArtifacts.nav)
      ? snapshotArtifacts.nav
      : [];
    return {
      expId: String(payload.exp_id || snapshot?.result?.exp_id || '').trim(),
      runMeta,
      benchmarkSymbol: String(runMeta?.data?.benchmark || fallbackBenchmarkSymbol).trim() || fallbackBenchmarkSymbol,
      navRows,
      navSeries: Array.isArray(snapshotArtifacts.navSeries)
        ? snapshotArtifacts.navSeries
        : navRows.map((row) => ({ date: row.date, value: row.nav })),
      snapshot,
    };
  }
  return payload && typeof payload === 'object' ? payload : {};
}
const stockComponent = computed(() => {
  const payload = comboComponents.value.stock;
  return normalizeComboComponent(payload, '000300.SH');
});
const etfComponent = computed(() => {
  const payload = comboComponents.value.etf;
  return normalizeComboComponent(payload, '510050.SH');
});
const stockNavRows = computed(() => (Array.isArray(stockComponent.value?.navRows) ? stockComponent.value.navRows : []));
const etfNavRows = computed(() => (Array.isArray(etfComponent.value?.navRows) ? etfComponent.value.navRows : []));
const stockBenchmarkSymbol = computed(() => String(stockComponent.value?.benchmarkSymbol || '000300.SH').trim() || '000300.SH');
const etfBenchmarkSymbol = computed(() => String(etfComponent.value?.benchmarkSymbol || '510050.SH').trim() || '510050.SH');
const stockBenchmarkRows = ref([]);
const etfBenchmarkRows = ref([]);

const comboReturn = computed(() => buildReturnText(comboNavRows.value, 'nav'));
const stockReturn = computed(() => buildReturnText(stockNavRows.value, 'nav'));
const etfReturn = computed(() => buildReturnText(etfNavRows.value, 'nav'));

function buildReturnText(rows, key = 'nav') {
  const series = buildLineRows(rows, key, false);
  if (!series.length) return '-';
  const firstValue = Number(series[0]?.value);
  const lastValue = Number(series[series.length - 1]?.value);
  if (!Number.isFinite(firstValue) || !Number.isFinite(lastValue) || firstValue <= 0) return '-';
  return `${(((lastValue / firstValue) - 1) * 100).toFixed(2)}%`;
}

function buildLineRows(rows, key = 'nav', normalize = false) {
  const source = Array.isArray(rows) ? rows : [];
  const valid = source
    .map((row) => ({
      date: String(row?.date || '').trim(),
      value: Number(row?.[key]),
    }))
    .filter((row) => row.date && Number.isFinite(row.value) && row.value > 0);
  if (!valid.length) return [];
  if (!normalize) return valid;
  const base = Number(valid[0]?.value);
  if (!Number.isFinite(base) || base <= 0) return valid;
  return valid.map((row) => ({
    date: row.date,
    value: row.value / base,
  }));
}

function aggregateLineRows(rows, chartRange) {
  const aggregateNav = typeof window.aggregateNav === 'function' ? window.aggregateNav : ((value) => value || []);
  return aggregateNav(rows, String(chartRange || 'D'));
}

function createBaseChart(container, height, showTimeScale = true) {
  const LWC = window.LightweightCharts;
  if (!container || !LWC || typeof LWC.createChart !== 'function') return null;
  container.innerHTML = '';
  const chart = LWC.createChart(container, {
    width: container.clientWidth || 640,
    height,
    layout: {
      background: { type: LWC.ColorType ? LWC.ColorType.Solid : 'solid', color: 'transparent' },
      textColor: '#94a3b8',
      fontSize: 11,
    },
    grid: {
      vertLines: { color: 'rgba(51,65,85,0.4)' },
      horzLines: { color: 'rgba(51,65,85,0.4)' },
    },
    crosshair: { mode: LWC.CrosshairMode ? LWC.CrosshairMode.Normal : 0 },
    leftPriceScale: { visible: false, borderColor: '#334155', autoScale: true },
    rightPriceScale: { visible: true, borderColor: '#334155', autoScale: true },
    timeScale: {
      borderColor: '#334155',
      timeVisible: false,
      secondsVisible: false,
      barSpacing: 6,
      minBarSpacing: 2,
      rightOffset: 5,
      visible: showTimeScale,
      lockVisibleTimeRangeOnResize: true,
      rightBarStaysOnScroll: true,
    },
    handleScale: {
      mouseWheel: true,
      pinch: true,
      axisPressedMouseMove: { time: true, price: true },
      axisDoubleClickReset: { time: true, price: true },
    },
    handleScroll: {
      mouseWheel: true,
      pressedMouseMove: true,
      horzTouchDrag: true,
      vertTouchDrag: false,
    },
  });
  return chart;
}

function addLineSeries(chart, options) {
  if (!chart) return null;
  if (typeof chart.addLineSeries === 'function') return chart.addLineSeries(options);
  return chart.addSeries(window.LightweightCharts.LineSeries, options);
}

function setVisibleRange(chart, totalBars) {
  if (!chart || !(totalBars > 0)) return;
  try {
    chart.timeScale().setVisibleLogicalRange({
      from: Math.max(0, totalBars - COMBO_VISIBLE_BARS) - 0.5,
      to: totalBars - 1 + 2.5,
    });
  } catch (_) {
    try { chart.timeScale().fitContent(); } catch (_) {}
  }
}

function registerChart(chart, container) {
  if (!chart || !container || typeof ResizeObserver !== 'function') return;
  const observer = new ResizeObserver(() => {
    try {
      chart.applyOptions({
        width: container.clientWidth || 640,
        height: container.clientHeight || 240,
      });
    } catch (_) {}
  });
  observer.observe(container);
  chartDisposers.push(() => {
    try { observer.disconnect(); } catch (_) {}
    try { chart.remove(); } catch (_) {}
  });
}

function disposeCharts() {
  while (chartDisposers.length) {
    const dispose = chartDisposers.pop();
    try { dispose?.(); } catch (_) {}
  }
}

function renderMultiLineChart(container, rowsBySeries, options = {}) {
  if (!container) return;
  const seriesEntries = Array.isArray(rowsBySeries) ? rowsBySeries.filter((item) => Array.isArray(item?.rows) && item.rows.length) : [];
  if (!seriesEntries.length) return;
  const chart = createBaseChart(container, Number(options.height || 360), options.showTimeScale !== false);
  if (!chart) return;
  seriesEntries.forEach((entry) => {
    const series = addLineSeries(chart, {
      color: String(entry.color || '#f59e0b'),
      lineWidth: Number(entry.lineWidth || 2),
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
    });
    series?.setData(entry.rows.map((row) => ({ time: row.date, value: Number(row.value) })));
  });
  const totalBars = Math.max(...seriesEntries.map((entry) => entry.rows.length));
  setVisibleRange(chart, totalBars);
  registerChart(chart, container);
}

async function ensureBenchmarkRows(symbol, navRows) {
  const normalizedSymbol = String(symbol || '').trim();
  const rows = Array.isArray(navRows) ? navRows : [];
  if (!normalizedSymbol || !rows.length || typeof window.loadBenchmarkSeries !== 'function') return [];
  const start = String(rows[0]?.date || '').trim();
  const end = String(rows[rows.length - 1]?.date || '').trim();
  const cacheKey = `${normalizedSymbol}:${start}:${end}`;
  if (Array.isArray(benchmarkCache.value[cacheKey])) return benchmarkCache.value[cacheKey];
  try {
    const payload = await window.loadBenchmarkSeries(rows.map((row) => ({ date: row.date, nav: row.nav })), {
      symbol: normalizedSymbol,
      absolute: true,
    });
    const points = Array.isArray(payload?.points)
      ? payload.points
        .map((row) => ({ date: String(row?.date || '').trim(), nav: Number(row?.nav) }))
        .filter((row) => row.date && Number.isFinite(row.nav) && row.nav > 0)
      : [];
    benchmarkCache.value = {
      ...benchmarkCache.value,
      [cacheKey]: points,
    };
    return points;
  } catch (_) {
    benchmarkCache.value = {
      ...benchmarkCache.value,
      [cacheKey]: [],
    };
    return [];
  }
}

async function loadBenchmarks() {
  const [stockRows, etfRows] = await Promise.all([
    ensureBenchmarkRows(stockBenchmarkSymbol.value, stockNavRows.value),
    ensureBenchmarkRows(etfBenchmarkSymbol.value, etfNavRows.value),
  ]);
  stockBenchmarkRows.value = stockRows;
  etfBenchmarkRows.value = etfRows;
}

function renderComponentCharts() {
  const chartRange = String(view.value.chartRange || 'D');
  const comboSeries = aggregateLineRows(buildLineRows(comboNavRows.value, 'nav', false), chartRange);
  const stockSeries = aggregateLineRows(buildLineRows(stockNavRows.value, 'nav', false), chartRange);
  const etfSeries = aggregateLineRows(buildLineRows(etfNavRows.value, 'nav', false), chartRange);

  renderMultiLineChart(comboChartRef.value, [
    { rows: comboSeries, color: '#f59e0b', lineWidth: 3 },
    { rows: stockSeries, color: '#60a5fa', lineWidth: 2 },
    { rows: etfSeries, color: '#34d399', lineWidth: 2 },
  ], { height: 420, showTimeScale: true });

  const stockBenchmarkNormalized = aggregateLineRows(
    buildLineRows(stockBenchmarkRows.value, 'nav', true),
    chartRange,
  );
  const stockBenchmarkAbsolute = aggregateLineRows(
    buildLineRows(stockBenchmarkRows.value, 'nav', false),
    chartRange,
  );
  renderMultiLineChart(stockTopChartRef.value, [
    { rows: stockSeries, color: '#f59e0b', lineWidth: 3 },
    { rows: stockBenchmarkNormalized, color: '#60a5fa', lineWidth: 2 },
  ], { height: 260, showTimeScale: false });
  renderMultiLineChart(stockBottomChartRef.value, [
    { rows: stockBenchmarkAbsolute, color: '#60a5fa', lineWidth: 2 },
  ], { height: 180, showTimeScale: true });

  const etfBenchmarkNormalized = aggregateLineRows(
    buildLineRows(etfBenchmarkRows.value, 'nav', true),
    chartRange,
  );
  const etfBenchmarkAbsolute = aggregateLineRows(
    buildLineRows(etfBenchmarkRows.value, 'nav', false),
    chartRange,
  );
  renderMultiLineChart(etfTopChartRef.value, [
    { rows: etfSeries, color: '#34d399', lineWidth: 3 },
    { rows: etfBenchmarkNormalized, color: '#a78bfa', lineWidth: 2 },
  ], { height: 260, showTimeScale: false });
  renderMultiLineChart(etfBottomChartRef.value, [
    { rows: etfBenchmarkAbsolute, color: '#a78bfa', lineWidth: 2 },
  ], { height: 180, showTimeScale: true });
}

async function redrawCharts() {
  disposeCharts();
  if (!comboNavRows.value.length) return;
  await loadBenchmarks();
  await nextTick();
  renderComponentCharts();
}

function onChartRangeChange(event) {
  props.patchViewState({ chartRange: String(event?.target?.value || 'D') });
}

onMounted(async () => {
  await redrawCharts();
});

onBeforeUnmount(() => {
  disposeCharts();
});

watch(
  () => [
    props.snapshot?.updatedAt,
    view.value.chartRange,
    comboNavRows.value.length,
    stockNavRows.value.length,
    etfNavRows.value.length,
    stockBenchmarkSymbol.value,
    etfBenchmarkSymbol.value,
  ],
  async () => {
    await redrawCharts();
  },
);
</script>

<template>
  <section class="wb-canvas">
    <div class="wb-canvas-head">
      <div class="wb-canvas-info">
        <span class="wb-canvas-kicker">组合研究图</span>
        <span class="wb-mini">只读 Research Combo</span>
      </div>
      <div class="wb-inline wb-canvas-tools">
        <select :value="view.chartRange || 'D'" class="formInput wb-input-sm" @change="onChartRangeChange">
          <option value="D">日</option>
          <option value="W">周</option>
          <option value="M">月</option>
          <option value="Y">年</option>
        </select>
      </div>
    </div>

    <div class="wb-mini" style="display:flex;flex-wrap:wrap;gap:8px 12px;margin-bottom:10px;align-items:center;">
      <span>组合 NAV: {{ comboReturn }}</span>
      <span>个股 Sleeve: {{ stockReturn }}</span>
      <span>ETF Sleeve: {{ etfReturn }}</span>
    </div>

    <div class="wb-mini" style="margin-bottom: 6px;">上图：组合 NAV + 个股 NAV + ETF NAV</div>
    <div id="wbResearchComboChart" ref="comboChartRef" class="wb-chart wb-chart-main" style="height: 420px;">
      <div class="wb-empty">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
        <span>加载组合结果后，这里展示组合、个股和 ETF 三条净值线。</span>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:16px;">
      <section style="padding:16px;border:1px solid rgba(51,65,85,0.65);border-radius:20px;background:rgba(15,23,42,0.38);">
        <div class="wb-mini" style="margin-bottom: 8px;">A股个股：NAV 与大盘归一化走势（{{ stockBenchmarkSymbol }}）</div>
        <div id="wbResearchComboStockChartTop" ref="stockTopChartRef" class="wb-chart wb-chart-main" style="height: 260px;">
          <div class="wb-empty">
            <span>加载个股组件实验后，这里展示个股 NAV 与大盘走势。</span>
          </div>
        </div>
        <div class="wb-mini" style="margin: 10px 0 6px;">A股个股下图：大盘绝对价格</div>
        <div id="wbResearchComboStockChartBottom" ref="stockBottomChartRef" class="wb-chart wb-chart-main" style="height: 180px;">
          <div class="wb-empty">
            <span>这里展示个股组件使用的大盘绝对价格。</span>
          </div>
        </div>
      </section>

      <section style="padding:16px;border:1px solid rgba(51,65,85,0.65);border-radius:20px;background:rgba(15,23,42,0.38);">
        <div class="wb-mini" style="margin-bottom: 8px;">ETF：NAV 与基准归一化走势（{{ etfBenchmarkSymbol }}）</div>
        <div id="wbResearchComboEtfChartTop" ref="etfTopChartRef" class="wb-chart wb-chart-main" style="height: 260px;">
          <div class="wb-empty">
            <span>加载 ETF 组件实验后，这里展示 ETF NAV 与基准走势。</span>
          </div>
        </div>
        <div class="wb-mini" style="margin: 10px 0 6px;">ETF 下图：基准绝对价格</div>
        <div id="wbResearchComboEtfChartBottom" ref="etfBottomChartRef" class="wb-chart wb-chart-main" style="height: 180px;">
          <div class="wb-empty">
            <span>这里展示 ETF 组件使用的基准绝对价格。</span>
          </div>
        </div>
      </section>
    </div>

    <div class="wb-canvas-footer">
      <div class="wb-mini">当前结果是只读 research combo。上图展示组合总线；下方分开展示 A股个股与 ETF 的净值和各自基准走势。</div>
    </div>
  </section>
</template>
