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
  sectionMode: {
    type: String,
    default: 'full',
  },
});

const comboChartRef = ref(null);
const comboBenchmarkChartRef = ref(null);
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
const comboTradeMarkers = computed(() => {
  const rows = Array.isArray(artifacts.value.tradesRows) ? artifacts.value.tradesRows : [];
  if (typeof window.tradeMarkers === 'function') return window.tradeMarkers(rows, { combo: true, navRows: comboNavRows.value }) || [];
  return [];
});
const runMeta = computed(() => {
  const payload = artifacts.value.run_meta;
  return payload && typeof payload === 'object' ? payload : {};
});
const comboTruth = computed(() => {
  const payload = artifacts.value.comboTruth;
  return payload && typeof payload === 'object' ? payload : {};
});
const comboComponents = computed(() => {
  const payload = comboTruth.value.components;
  return payload && typeof payload === 'object' ? payload : {};
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
const comboBenchmarkSymbol = computed(() => stockBenchmarkSymbol.value);
const stockBenchmarkRows = ref([]);
const etfBenchmarkRows = ref([]);
const stockBenchmarkOhlc = ref([]);
const etfBenchmarkOhlc = ref([]);
const stockTradeMarkers = computed(() => {
  const rows = Array.isArray(stockComponent.value?.snapshot?.artifacts?.tradesRows)
    ? stockComponent.value.snapshot.artifacts.tradesRows
    : [];
  return typeof window.tradeMarkers === 'function'
    ? (window.tradeMarkers(rows, { navRows: stockNavRows.value }) || [])
    : [];
});
const etfTradeMarkers = computed(() => {
  const rows = Array.isArray(etfComponent.value?.snapshot?.artifacts?.tradesRows)
    ? etfComponent.value.snapshot.artifacts.tradesRows
    : [];
  return typeof window.tradeMarkers === 'function'
    ? (window.tradeMarkers(rows, { navRows: etfNavRows.value }) || [])
    : [];
});

const isResearchLikeCombo = computed(() => {
  const comboRuntime = runMeta.value.combo_runtime && typeof runMeta.value.combo_runtime === 'object'
    ? runMeta.value.combo_runtime
    : {};
  const comboResult = runMeta.value.combo_result && typeof runMeta.value.combo_result === 'object'
    ? runMeta.value.combo_result
    : {};
  const researchCombo = runMeta.value.research_combo && typeof runMeta.value.research_combo === 'object'
    ? runMeta.value.research_combo
    : {};
  const assetRole = String(runMeta.value?.data?.asset_role || '').trim().toLowerCase();
  return assetRole === 'research_combo'
    || comboResult.research_combo_only
    || researchCombo.research_combo_only
    || comboRuntime.research_combo_only;
});

const comboReturn = computed(() => buildReturnText(comboNavRows.value, 'nav'));
const stockReturn = computed(() => (
  stockNavRows.value.length
    ? buildReturnText(stockNavRows.value, 'nav')
    : buildReturnText(comboNavRows.value, 'stock_nav')
));
const etfReturn = computed(() => (
  etfNavRows.value.length
    ? buildReturnText(etfNavRows.value, 'nav')
    : buildReturnText(comboNavRows.value, 'etf_nav')
));
const showMainChart = computed(() => props.sectionMode === 'full' || props.sectionMode === 'overview');
const showSleeveCharts = computed(() => props.sectionMode === 'full' || props.sectionMode === 'sleeves');
const showSleeveBenchmarks = computed(() => props.sectionMode === 'full');
const compactSleeveChrome = computed(() => props.sectionMode === 'sleeves');
const comboLegendItems = computed(() => [
  { key: 'combo', label: '组合净值', color: '#f59e0b' },
  { key: 'stock', label: '股票腿净值', color: '#60a5fa' },
  { key: 'etf', label: 'ETF 腿净值', color: '#34d399' },
]);
const stockSleeveLegendItems = computed(() => [
  { key: 'stock-nav', label: '股票腿净值', color: '#f59e0b' },
  { key: 'stock-benchmark', label: '股票腿基准', color: '#60a5fa' },
]);
const etfSleeveLegendItems = computed(() => [
  { key: 'etf-nav', label: 'ETF 腿净值', color: '#34d399' },
  { key: 'etf-benchmark', label: 'ETF 腿基准', color: '#a78bfa' },
]);
const canvasTitle = computed(() => {
  if (props.sectionMode === 'overview') return '组合主图';
  if (props.sectionMode === 'sleeves') return '双腿拆解';
  return '研究组合';
});
const canvasDescription = computed(() => {
  if (props.sectionMode === 'overview') {
    return '主图聚焦组合净值，并在下方补充股票腿对应的大盘 K 线。';
  }
  if (props.sectionMode === 'sleeves') {
    return '双腿图表聚焦各组件相对自身基准的表现。';
  }
  return '上方展示组合线，下方补充大盘 K 线，并拆开展示股票腿与 ETF 腿。';
});

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

function aggregateCandleRows(rows, chartRange) {
  const aggregateOhlc = typeof window.aggregateOhlc === 'function' ? window.aggregateOhlc : ((value) => value || []);
  return aggregateOhlc(rows, String(chartRange || 'D'));
}

function createBaseChart(container, height, showTimeScale = true, scaleOptions = {}) {
  const LWC = window.LightweightCharts;
  if (!container || !LWC || typeof LWC.createChart !== 'function') return null;
  container.innerHTML = '';
  const leftPriceScaleVisible = !!scaleOptions.leftPriceScaleVisible;
  const rightPriceScaleVisible = scaleOptions.rightPriceScaleVisible !== false;
  const interactive = scaleOptions.interactive !== false;
  return LWC.createChart(container, {
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
    leftPriceScale: { visible: leftPriceScaleVisible, borderColor: '#334155', autoScale: true },
    rightPriceScale: { visible: rightPriceScaleVisible, borderColor: '#334155', autoScale: true },
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
      mouseWheel: interactive,
      pinch: interactive,
      axisPressedMouseMove: { time: interactive, price: interactive },
      axisDoubleClickReset: { time: interactive, price: interactive },
    },
    handleScroll: {
      mouseWheel: interactive,
      pressedMouseMove: interactive,
      horzTouchDrag: interactive,
      vertTouchDrag: false,
    },
  });
}

function addLineSeries(chart, options) {
  if (!chart) return null;
  if (typeof chart.addLineSeries === 'function') return chart.addLineSeries(options);
  return chart.addSeries(window.LightweightCharts.LineSeries, options);
}

function addCandlestickSeries(chart, options) {
  if (!chart) return null;
  if (typeof chart.addCandlestickSeries === 'function') return chart.addCandlestickSeries(options);
  return chart.addSeries(window.LightweightCharts.CandlestickSeries, options);
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
    if (entry === seriesEntries[0] && Array.isArray(options.markers) && options.markers.length) {
      try {
        if (typeof series?.setMarkers === 'function') {
          series.setMarkers(options.markers);
        } else if (typeof window.LightweightCharts?.createSeriesMarkers === 'function') {
          window.LightweightCharts.createSeriesMarkers(series, options.markers);
        }
      } catch (_) {}
    }
  });
  const totalBars = Math.max(...seriesEntries.map((entry) => entry.rows.length));
  setVisibleRange(chart, totalBars);
  registerChart(chart, container);
}

function renderCandlestickChart(container, rows, options = {}) {
  if (!container) return;
  const candleRows = Array.isArray(rows)
    ? rows
      .map((row) => ({
        time: String(row?.time || '').trim(),
        open: Number(row?.open),
        high: Number(row?.high),
        low: Number(row?.low),
        close: Number(row?.close),
      }))
      .filter((row) => row.time && Number.isFinite(row.open) && Number.isFinite(row.high) && Number.isFinite(row.low) && Number.isFinite(row.close))
    : [];
  if (!candleRows.length) return;
  const chart = createBaseChart(
    container,
    Number(options.height || 220),
    options.showTimeScale !== false,
    {
      leftPriceScaleVisible: options.leftPriceScaleVisible !== false,
      rightPriceScaleVisible: !!options.rightPriceScaleVisible,
      interactive: options.interactive !== false,
    },
  );
  if (!chart) return;
  const series = addCandlestickSeries(chart, {
    upColor: '#ef4444',
    downColor: '#22c55e',
    borderDownColor: '#22c55e',
    borderUpColor: '#ef4444',
    wickDownColor: '#22c55e',
    wickUpColor: '#ef4444',
    priceScaleId: options.priceScaleId || 'left',
    priceLineVisible: false,
    lastValueVisible: options.lastValueVisible !== false,
  });
  series?.setData(candleRows);
  setVisibleRange(chart, candleRows.length);
  registerChart(chart, container);
}

async function ensureBenchmarkPayload(symbol, navRows) {
  const normalizedSymbol = String(symbol || '').trim();
  const rows = Array.isArray(navRows) ? navRows : [];
  if (!normalizedSymbol || !rows.length || typeof window.loadBenchmarkSeries !== 'function') {
    return { points: [], ohlc: [] };
  }
  const start = String(rows[0]?.date || '').trim();
  const end = String(rows[rows.length - 1]?.date || '').trim();
  const cacheKey = `${normalizedSymbol}:${start}:${end}`;
  const cached = benchmarkCache.value[cacheKey];
  if (cached && typeof cached === 'object') return cached;
  try {
    const payload = await window.loadBenchmarkSeries(rows.map((row) => ({ date: row.date, nav: row.nav })), {
      symbol: normalizedSymbol,
      absolute: true,
    });
    const resolved = {
      points: Array.isArray(payload?.points)
      ? payload.points
        .map((row) => ({ date: String(row?.date || '').trim(), nav: Number(row?.nav) }))
        .filter((row) => row.date && Number.isFinite(row.nav) && row.nav > 0)
      : [],
      ohlc: Array.isArray(payload?.ohlc)
        ? payload.ohlc
          .map((row) => ({
            time: String(row?.time || row?.date || '').trim(),
            open: Number(row?.open),
            high: Number(row?.high),
            low: Number(row?.low),
            close: Number(row?.close),
          }))
          .filter((row) => row.time && Number.isFinite(row.open) && Number.isFinite(row.high) && Number.isFinite(row.low) && Number.isFinite(row.close))
        : [],
    };
    benchmarkCache.value = {
      ...benchmarkCache.value,
      [cacheKey]: resolved,
    };
    return resolved;
  } catch (_) {
    benchmarkCache.value = {
      ...benchmarkCache.value,
      [cacheKey]: { points: [], ohlc: [] },
    };
    return { points: [], ohlc: [] };
  }
}

async function loadBenchmarks() {
  const [stockPayload, etfPayload] = await Promise.all([
    ensureBenchmarkPayload(stockBenchmarkSymbol.value, stockNavRows.value),
    ensureBenchmarkPayload(etfBenchmarkSymbol.value, etfNavRows.value),
  ]);
  stockBenchmarkRows.value = Array.isArray(stockPayload?.points) ? stockPayload.points : [];
  etfBenchmarkRows.value = Array.isArray(etfPayload?.points) ? etfPayload.points : [];
  stockBenchmarkOhlc.value = Array.isArray(stockPayload?.ohlc) ? stockPayload.ohlc : [];
  etfBenchmarkOhlc.value = Array.isArray(etfPayload?.ohlc) ? etfPayload.ohlc : [];
}

function renderComponentCharts() {
  const chartRange = String(view.value.chartRange || 'D');
  const comboSeries = aggregateLineRows(buildLineRows(comboNavRows.value, 'nav', false), chartRange);
  const stockSeries = aggregateLineRows(buildLineRows(stockNavRows.value, 'nav', false), chartRange);
  const etfSeries = aggregateLineRows(buildLineRows(etfNavRows.value, 'nav', false), chartRange);
  const comboBenchmarkSeries = aggregateCandleRows(stockBenchmarkOhlc.value, chartRange);

  renderMultiLineChart(comboChartRef.value, [
    { rows: comboSeries, color: '#f59e0b', lineWidth: 3 },
    { rows: stockSeries, color: '#60a5fa', lineWidth: 2 },
    { rows: etfSeries, color: '#34d399', lineWidth: 2 },
  ], { height: 420, showTimeScale: true, markers: comboTradeMarkers.value });
  renderCandlestickChart(comboBenchmarkChartRef.value, comboBenchmarkSeries, {
    height: 220,
    showTimeScale: true,
    leftPriceScaleVisible: true,
    rightPriceScaleVisible: false,
    interactive: true,
  });

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
  ], { height: 260, showTimeScale: false, markers: stockTradeMarkers.value });
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
  ], { height: 260, showTimeScale: false, markers: etfTradeMarkers.value });
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
    props.sectionMode,
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
  <section class="wb-canvas" :class="{ 'wb-canvas-compact': compactSleeveChrome }">
    <div class="wb-canvas-head">
      <div v-if="!compactSleeveChrome" class="wb-canvas-info">
        <span class="wb-canvas-kicker">{{ canvasTitle }}</span>
        <span class="wb-mini">{{ isResearchLikeCombo ? '研究组合' : '统一运行' }}</span>
      </div>
      <div class="wb-inline wb-canvas-tools">
        <select :value="view.chartRange || 'D'" class="formInput wb-input-sm" @change="onChartRangeChange">
          <option value="D">D</option>
          <option value="W">W</option>
          <option value="M">M</option>
          <option value="Y">Y</option>
        </select>
      </div>
    </div>

    <div v-if="!compactSleeveChrome" class="wb-mini" style="display:flex;flex-wrap:wrap;gap:8px 12px;margin-bottom:10px;align-items:center;">
      <span>组合净值：{{ comboReturn }}</span>
      <span>股票腿：{{ stockReturn }}</span>
      <span>ETF 腿：{{ etfReturn }}</span>
    </div>

    <template v-if="showMainChart">
      <div
        class="wb-chart-stack"
        style="display:grid;grid-template-rows:344px 244px;gap:12px;height:auto;min-height:0;"
      >
        <div class="wb-chart-stack-panel" style="min-height:344px;">
          <div class="wb-mini" style="margin-bottom: 6px;">叠加：组合净值 + 股票腿净值 + ETF 腿净值</div>
          <div class="wb-chart-legend" style="margin-bottom: 8px;">
            <span
              v-for="item in comboLegendItems"
              :key="item.key"
              class="wb-chart-legend-item"
            >
              <span class="wb-chart-legend-swatch" :style="{ background: item.color }"></span>
              <span>{{ item.label }}</span>
            </span>
          </div>
          <div id="wbResearchComboChart" ref="comboChartRef" class="wb-chart wb-chart-main" style="height: 320px;">
            <div class="wb-empty">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
              <span>加载组合结果后，这里会渲染组合、股票腿和 ETF 腿净值线。</span>
            </div>
          </div>
        </div>
        <div class="wb-chart-stack-panel" style="min-height:244px;">
          <div class="wb-mini" style="margin-bottom: 6px;">下图：股票腿大盘 K 线（{{ comboBenchmarkSymbol }}）</div>
          <div id="wbResearchComboBenchmarkChart" ref="comboBenchmarkChartRef" class="wb-chart wb-chart-main" style="height: 220px;">
            <div class="wb-empty">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
              <span>这里展示股票腿基准的大盘 K 线。</span>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template v-if="showSleeveCharts">
      <div class="wb-combo-sleeve-grid">
        <section class="wb-combo-sleeve-card">
          <div class="wb-mini" style="margin-bottom: 8px;">股票腿：净值 vs 归一化基准（{{ stockBenchmarkSymbol }}）</div>
          <div class="wb-chart-legend" style="margin-bottom: 8px;">
            <span
              v-for="item in stockSleeveLegendItems"
              :key="item.key"
              class="wb-chart-legend-item"
            >
              <span class="wb-chart-legend-swatch" :style="{ background: item.color }"></span>
              <span>{{ item.label }}</span>
            </span>
          </div>
          <div id="wbResearchComboStockChartTop" ref="stockTopChartRef" class="wb-chart wb-chart-main" style="height: 260px;">
            <div class="wb-empty">
              <span>加载股票腿组件结果后，这里会渲染股票腿图表。</span>
            </div>
          </div>
          <details v-if="!showSleeveBenchmarks" class="wb-combo-benchmark-details">
            <summary class="wb-mini wb-combo-benchmark-summary">基准上下文</summary>
            <div class="wb-mini" style="margin: 10px 0 6px;">股票基准绝对价格</div>
            <div id="wbResearchComboStockChartBottom" ref="stockBottomChartRef" class="wb-chart wb-chart-main" style="height: 180px;">
              <div class="wb-empty">
                <span>股票腿基准上下文显示在这里。</span>
              </div>
            </div>
          </details>
          <template v-else>
            <div class="wb-mini" style="margin: 10px 0 6px;">股票基准绝对价格</div>
            <div id="wbResearchComboStockChartBottom" ref="stockBottomChartRef" class="wb-chart wb-chart-main" style="height: 180px;">
              <div class="wb-empty">
                <span>股票腿基准上下文显示在这里。</span>
              </div>
            </div>
          </template>
        </section>

        <section class="wb-combo-sleeve-card">
          <div class="wb-mini" style="margin-bottom: 8px;">ETF 腿：净值 vs 归一化基准（{{ etfBenchmarkSymbol }}）</div>
          <div class="wb-chart-legend" style="margin-bottom: 8px;">
            <span
              v-for="item in etfSleeveLegendItems"
              :key="item.key"
              class="wb-chart-legend-item"
            >
              <span class="wb-chart-legend-swatch" :style="{ background: item.color }"></span>
              <span>{{ item.label }}</span>
            </span>
          </div>
          <div id="wbResearchComboEtfChartTop" ref="etfTopChartRef" class="wb-chart wb-chart-main" style="height: 260px;">
            <div class="wb-empty">
              <span>加载 ETF 腿组件结果后，这里会渲染 ETF 腿图表。</span>
            </div>
          </div>
          <details v-if="!showSleeveBenchmarks" class="wb-combo-benchmark-details">
            <summary class="wb-mini wb-combo-benchmark-summary">基准上下文</summary>
            <div class="wb-mini" style="margin: 10px 0 6px;">ETF 基准绝对价格</div>
            <div id="wbResearchComboEtfChartBottom" ref="etfBottomChartRef" class="wb-chart wb-chart-main" style="height: 180px;">
              <div class="wb-empty">
                <span>ETF 腿基准上下文显示在这里。</span>
              </div>
            </div>
          </details>
          <template v-else>
            <div class="wb-mini" style="margin: 10px 0 6px;">ETF 基准绝对价格</div>
            <div id="wbResearchComboEtfChartBottom" ref="etfBottomChartRef" class="wb-chart wb-chart-main" style="height: 180px;">
              <div class="wb-empty">
                <span>ETF 腿基准上下文显示在这里。</span>
              </div>
            </div>
          </template>
        </section>
      </div>
    </template>

    <div v-if="!compactSleeveChrome" class="wb-canvas-footer">
      <div class="wb-mini">{{ isResearchLikeCombo ? `当前结果是只读研究组合。${canvasDescription}` : `当前结果来自统一运行时。${canvasDescription}` }}</div>
    </div>
  </section>
</template>
