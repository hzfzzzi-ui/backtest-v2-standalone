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

const DEFAULT_PORTFOLIO_BENCHMARK_SYMBOL = '000001.SH';

const singleChartRef = ref(null);
const portfolioTopChartRef = ref(null);
const portfolioBottomChartRef = ref(null);
const symbolSeriesCache = ref({});
const portfolioBenchmarkCache = ref({});

const artifacts = computed(() => props.snapshot?.artifacts || {});
const view = computed(() => props.snapshot?.view || {});
const navRows = computed(() => Array.isArray(artifacts.value.navSeries) ? artifacts.value.navSeries : []);
const symbolRows = computed(() => Array.isArray(artifacts.value.symbolPerformanceRows) ? artifacts.value.symbolPerformanceRows : []);
const tradeMarkers = computed(() => {
  const rows = Array.isArray(artifacts.value.tradesRows) ? artifacts.value.tradesRows : [];
  if (typeof window.tradeMarkers === 'function') return window.tradeMarkers(rows, { navRows: navRows.value }) || [];
  return rows
    .map((row, index) => ({ row, index }))
    .filter(({ row }) => String(row?.date || '').trim())
    .map(({ row, index }) => {
      const side = String(row?.side || '').trim().toUpperCase();
      const isBuy = side === 'BUY';
      const isSell = side === 'SELL';
      if (!isBuy && !isSell) return null;
      let meta = {};
      try {
        meta = typeof row?.meta_json === 'string' && row.meta_json.trim() ? JSON.parse(row.meta_json) : {};
      } catch (_) {
        meta = {};
      }
      const candidates = [
        Number(meta?.target_weight),
        Number(meta?.final_target_weight),
        Number(meta?.requested_target_weight),
      ].filter((value) => Number.isFinite(value) && value >= 0);
      const weight = candidates.length ? candidates[0] : null;
      const symbol = String(row?.symbol || '').trim().toUpperCase();
      return {
        time: String(row.date).slice(0, 10),
        position: isBuy ? 'belowBar' : 'aboveBar',
        color: isBuy ? '#22c55e' : '#ef4444',
        shape: isBuy ? 'arrowUp' : 'arrowDown',
        text: Number.isFinite(weight) ? `${(weight * 100).toFixed(1).replace(/\.0$/, '')}%` : '',
        id: `${symbol || 'ALL'}_${String(row.date)}_${side}_${index}`,
        symbol: String(row?.symbol || '').trim().toLowerCase(),
        side,
      };
    })
    .filter(Boolean);
});
const tradeMarkerPreview = computed(() => tradeMarkers.value.slice(-8));
const isResearchCombo = computed(() => {
  const runMeta = artifacts.value.run_meta && typeof artifacts.value.run_meta === 'object'
    ? artifacts.value.run_meta
    : {};
  const assetRole = String(runMeta?.data?.asset_role || '').trim().toLowerCase();
  return assetRole === 'research_combo' || !!(runMeta.research_combo && typeof runMeta.research_combo === 'object');
});
const effectiveChartMode = computed(() => (isResearchCombo.value ? 'portfolio' : String(view.value.chartMode || 'portfolio')));

const selectedSymbol = computed(() => {
  const explicit = String(view.value.selectedSymbol || '').trim().toLowerCase();
  if (explicit) return explicit;
  return String(symbolRows.value[0]?.symbol || '').trim().toLowerCase();
});

const isSymbolMode = computed(() => effectiveChartMode.value === 'symbol' && !!selectedSymbol.value);
const portfolioBenchmarkSymbol = computed(() => {
  const metaData = artifacts.value.run_meta?.data || {};
  const etfSymbols = Array.isArray(metaData.etf_symbols) ? metaData.etf_symbols : [];
  return String(metaData.benchmark || etfSymbols[0] || DEFAULT_PORTFOLIO_BENCHMARK_SYMBOL).trim() || DEFAULT_PORTFOLIO_BENCHMARK_SYMBOL;
});
const benchmarkToggleLabel = computed(() => (isSymbolMode.value ? '对比基准' : `对比 ${portfolioBenchmarkSymbol.value}`));
const showPortfolioBenchmark = computed(() => !isSymbolMode.value && !isResearchCombo.value && (view.value.showBenchmark !== false));
const showBenchmarkToggle = computed(() => !isResearchCombo.value);

const REGIME_MODE_LABELS = {
  BULL: '牛市 / 主趋势',
  BULL_MAIN: '牛市 / 主趋势',
  TRANS_UP: '转强',
  TURN_STRONG: '转强',
  TREND_LIGHT: '轻仓趋势',
  TRANS_DOWN: '转弱',
  TURN_WEAK: '转弱',
  BEAR: '熊市',
  DEFENSIVE: '空仓防守',
  NO_TRADE: '空仓防守',
  TREND_MAIN: '主趋势',
  NO_TRADE_TRANS: '过渡空仓',
};

const REGIME_MODE_SWATCH = {
  BULL: 'rgba(239, 68, 68, 0.18)',
  BULL_MAIN: 'rgba(239, 68, 68, 0.18)',
  TRANS_UP: 'rgba(249, 115, 22, 0.18)',
  TURN_STRONG: 'rgba(249, 115, 22, 0.18)',
  TREND_LIGHT: 'rgba(251, 191, 36, 0.18)',
  TRANS_DOWN: 'rgba(59, 130, 246, 0.18)',
  TURN_WEAK: 'rgba(59, 130, 246, 0.18)',
  BEAR: 'rgba(34, 197, 94, 0.18)',
  DEFENSIVE: 'rgba(148, 163, 184, 0.18)',
  NO_TRADE: 'rgba(148, 163, 184, 0.18)',
  TREND_MAIN: 'rgba(239, 68, 68, 0.18)',
  NO_TRADE_TRANS: 'rgba(100, 116, 139, 0.18)',
};

const portfolioRegimeMeta = computed(() => {
  const states = Array.isArray(artifacts.value.marketStates) ? artifacts.value.marketStates : [];
  const latest = states[states.length - 1] || {};
  const runMeta = artifacts.value.run_meta && typeof artifacts.value.run_meta === 'object'
    ? artifacts.value.run_meta
    : {};
  const regime = runMeta.regime && typeof runMeta.regime === 'object' ? runMeta.regime : {};
  const engine = String(
    latest.regime_engine
    || regime.engine
    || runMeta?.report_consistency?.regime_engine
    || 'ma200_legacy',
  ).trim().toLowerCase() || 'ma200_legacy';
  const semantics = String(
    latest.regime_semantics
    || regime.regime_semantics
    || runMeta?.report_consistency?.regime_semantics
    || (engine === 'market_regime_framework'
      ? 'formal_framework'
      : (engine === 'weekly_five_state' ? 'weekly_five_state_regime' : 'legacy_price_filter')),
  ).trim().toLowerCase() || 'legacy_price_filter';
  const confidence = Number.isFinite(Number(latest.regime_confidence)) ? Number(latest.regime_confidence) : null;
  const duration = Number.isFinite(Number(latest.regime_duration_bars)) ? Number(latest.regime_duration_bars) : null;
  const reason = String(latest.regime_transition_reason || '').trim();
  return {
    engine,
    semantics,
    confidence,
    duration,
    reason: reason || null,
  };
});

const portfolioRegimeLegend = computed(() => {
  if (isResearchCombo.value) return [];
  const states = Array.isArray(artifacts.value.marketStates) ? artifacts.value.marketStates : [];
  const seen = new Set();
  states.forEach((row) => {
    const mode = String(row?.mode || '').trim().toUpperCase();
    if (mode) seen.add(mode);
  });
  return ['BULL_MAIN', 'TURN_STRONG', 'LIGHT_TREND', 'TURN_WEAK', 'DEFENSIVE', 'BULL', 'TRANS_UP', 'TREND_LIGHT', 'TRANS_DOWN', 'BEAR', 'NO_TRADE', 'NO_TRADE_TRANS']
    .filter((mode) => seen.has(mode))
    .map((mode) => ({
      mode,
      label: REGIME_MODE_LABELS[mode] || mode,
      color: REGIME_MODE_SWATCH[mode] || 'rgba(148, 163, 184, 0.18)',
    }));
});

const portfolioRegimeSummary = computed(() => {
  if (isResearchCombo.value) {
    return '研究组合锚点：当前只展示组合 NAV，不绘制市场基准绝对价格。';
  }
  const meta = portfolioRegimeMeta.value;
  const engineLabel = meta.engine === 'market_regime_framework'
    ? '正式 Regime Framework'
    : (meta.engine === 'weekly_five_state' ? '周度五态状态机' : 'Legacy MA200 状态机');
  const semanticsLabel = meta.semantics === 'formal_framework'
    ? '正式框架语义'
    : (meta.semantics === 'weekly_five_state_regime' ? '周度五态语义' : 'legacy 价格过滤语义');
  const parts = [engineLabel, semanticsLabel];
  if (meta.confidence != null) parts.push(`置信度 ${fmtNum(meta.confidence, 2)}`);
  if (meta.duration != null) parts.push(`已持续 ${fmtNum(meta.duration, 0)} bars`);
  if (meta.reason) parts.push(`最近切换: ${meta.reason}`);
  return parts.join(' | ');
});

function aggregateMarketStates(rows, period) {
  const input = Array.isArray(rows) ? rows : [];
  if (!input.length || !period || period === 'D') return input;
  const buckets = new Map();
  for (const row of input) {
    const d = String(row?.time || '').trim();
    const mode = String(row?.mode || '').trim();
    if (!d || !mode) continue;
    let key = d;
    if (period === 'W') {
      const dt = new Date(`${d}T00:00:00`);
      const day = dt.getDay();
      const mon = new Date(dt);
      mon.setDate(dt.getDate() - ((day + 6) % 7));
      key = mon.toISOString().slice(0, 10);
    } else if (period === 'M') {
      key = `${d.slice(0, 7)}-01`;
    } else if (period === 'Y') {
      key = `${d.slice(0, 4)}-01-01`;
    }
    buckets.set(key, { ...row, time: key, mode });
  }
  return [...buckets.values()];
}

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

const ensurePortfolioBenchmarkSeries = async () => {
  if (isSymbolMode.value) return null;
  const navSeries = Array.isArray(artifacts.value.navSeries) ? artifacts.value.navSeries : [];
  const start = String(navSeries[0]?.date || '').trim();
  const end = String(navSeries[navSeries.length - 1]?.date || '').trim();
  const symbol = portfolioBenchmarkSymbol.value;
  const cacheKey = `${symbol}:${start}:${end}`;
  if (portfolioBenchmarkCache.value[cacheKey]) return portfolioBenchmarkCache.value[cacheKey];
  if (typeof window.loadBenchmarkSeries !== 'function') return null;
  const loaded = await window.loadBenchmarkSeries(navSeries, { symbol, absolute: true });
  portfolioBenchmarkCache.value = {
    ...portfolioBenchmarkCache.value,
    [cacheKey]: loaded || { points: [], ohlc: [], symbol },
  };
  return portfolioBenchmarkCache.value[cacheKey];
};

const chartFooter = computed(() => {
  if (isSymbolMode.value) {
    const cache = symbolSeriesCache.value[selectedSymbol.value] || {};
    const ohlc = Array.isArray(cache.ohlc) ? cache.ohlc : [];
    const firstClose = Number(ohlc[0]?.close);
    const lastClose = Number(ohlc[ohlc.length - 1]?.close);
    const benchmarkOhlc = Array.isArray(artifacts.value.benchmarkOhlc) ? artifacts.value.benchmarkOhlc : [];
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
  return `净值 ${String(navSeries.length || 0)} 点 | 上图 NAV + 基准归一化 | 下图 ${portfolioBenchmarkSymbol.value} 绝对价格`;
});

const groupLoadStatus = computed(() => {
  const missing = Array.isArray(artifacts.value.missing) ? artifacts.value.missing : [];
  return missing.length ? `缺少 ${missing.length} 个产物，请查看状态中心` : '产物已加载';
});

function tradeMarkerPreviewLabel(marker) {
  const arrow = marker?.position === 'belowBar' ? '↑' : '↓';
  const text = String(marker?.text || '').trim();
  return text ? `${arrow} ${text}` : arrow;
}

function destroyInactiveCharts(forSymbolMode) {
  if (forSymbolMode) {
    if (typeof window.destroyPortfolioDualChartLW === 'function') {
      try { window.destroyPortfolioDualChartLW(); } catch (_) {}
    }
    return;
  }
  if (typeof window.destroyNavChartState === 'function') {
    try { window.destroyNavChartState(); } catch (_) {}
  }
}

async function redrawChart() {
  if (isSymbolMode.value) {
    destroyInactiveCharts(true);
    if (!singleChartRef.value || typeof window.renderNavChartLW !== 'function') return;
    await ensureSymbolSeries();
    await nextTick();

    const benchmarkOhlc = Array.isArray(artifacts.value.benchmarkOhlc) ? artifacts.value.benchmarkOhlc : [];
    const chartRange = String(view.value.chartRange || 'D');
    const aggregateNav = typeof window.aggregateNav === 'function' ? window.aggregateNav : ((rows) => rows || []);
    const aggregateOhlc = typeof window.aggregateOhlc === 'function' ? window.aggregateOhlc : ((rows) => rows || []);
    const cache = symbolSeriesCache.value[selectedSymbol.value] || {};
    const rawSeries = Array.isArray(cache.ohlc) ? cache.ohlc.map((item) => ({ date: item.time, value: Number(item.close) })) : [];
    const ohlc = Array.isArray(cache.ohlc) ? cache.ohlc : [];
    const lastClose = Number(ohlc[ohlc.length - 1]?.close);
    const markers = typeof window.symbolTradeMarkers === 'function'
      ? window.symbolTradeMarkers(selectedSymbol.value, artifacts.value.tradesRows || [], { navRows: navRows.value })
      : [];
    const suspensionRanges = Array.isArray(cache.suspensionRanges) ? cache.suspensionRanges : [];

    window.renderNavChartLW(
      singleChartRef.value.id,
      aggregateOhlc(benchmarkOhlc, chartRange),
      aggregateNav(rawSeries, chartRange),
      !!view.value.showBenchmark,
      {
        mode: 'symbol',
        markers,
        marketStates: [],
        suspensionRanges,
        symbolLastClose: lastClose,
      },
    );
    return;
  }

  destroyInactiveCharts(false);
  if (!portfolioTopChartRef.value) return;
  const portfolioBenchmark = await ensurePortfolioBenchmarkSeries();
  await nextTick();
  if (typeof window.renderPortfolioDualChartLW !== 'function') return;

  const chartRange = String(view.value.chartRange || 'D');
  const benchmarkOhlc = Array.isArray(portfolioBenchmark?.ohlc) ? portfolioBenchmark.ohlc : [];
  const navSeries = Array.isArray(artifacts.value.navSeries) ? artifacts.value.navSeries : [];
  const marketStates = aggregateMarketStates(
    Array.isArray(artifacts.value.marketStates) ? artifacts.value.marketStates : [],
    chartRange,
  );
  const aggregateNav = typeof window.aggregateNav === 'function' ? window.aggregateNav : ((rows) => rows || []);
  const aggregateOhlc = typeof window.aggregateOhlc === 'function' ? window.aggregateOhlc : ((rows) => rows || []);
  const markers = typeof window.tradeMarkers === 'function'
    ? window.tradeMarkers(artifacts.value.tradesRows || [], { navRows: navRows.value })
    : tradeMarkers.value;

  window.renderPortfolioDualChartLW(
    portfolioTopChartRef.value.id,
    portfolioBottomChartRef.value?.id || '',
    aggregateOhlc(benchmarkOhlc, chartRange),
    aggregateNav(navSeries, chartRange),
    {
      showBenchmark: showPortfolioBenchmark.value,
      benchmarkSymbol: portfolioBenchmarkSymbol.value,
      marketStates,
      markers,
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

function jumpToTradeSymbol(symbol) {
  const normalized = String(symbol || '').trim().toLowerCase();
  if (!normalized) return;
  props.patchViewState({
    chartMode: 'symbol',
    selectedSymbol: normalized,
  });
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
          {{ benchmarkToggleLabel }}
        </label>
        <select :value="view.chartRange || 'D'" class="formInput wb-input-sm" @change="onChartRangeChange">
          <option value="D">日K</option>
          <option value="W">周K</option>
          <option value="M">月K</option>
          <option value="Y">年K</option>
        </select>
      </div>
    </div>

    <div v-if="tradeMarkerPreview.length" class="wb-inline" style="gap:6px 8px;flex-wrap:wrap;margin:0 0 10px;">
      <span class="wb-mini">买卖点</span>
      <button
        v-for="marker in tradeMarkerPreview"
        :key="marker.id"
        type="button"
        class="pill wb-cmd-btn"
        @click="jumpToTradeSymbol(marker.symbol)"
      >
        {{ tradeMarkerPreviewLabel(marker) }} · {{ marker.time }}
      </button>
    </div>

    <div
      v-if="!isSymbolMode"
      class="wb-mini"
      style="display:flex;flex-wrap:wrap;gap:8px 12px;margin-bottom:10px;align-items:center;"
    >
      <span>{{ portfolioRegimeSummary }}</span>
      <span
        v-for="item in portfolioRegimeLegend"
        :key="item.mode"
        style="display:inline-flex;align-items:center;gap:6px;"
      >
        <span
          :style="{
            width: '12px',
            height: '12px',
            borderRadius: '3px',
            background: item.color,
            border: '1px solid rgba(148,163,184,0.35)',
          }"
        ></span>
        <span>{{ item.label }}</span>
      </span>
    </div>

    <template v-if="isSymbolMode">
      <div id="wbResultsWorkbenchChart" ref="singleChartRef" class="wb-chart wb-chart-main">
        <div class="wb-empty">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
          <span>运行实验后，在这里查看个股净值与基准走势。</span>
        </div>
      </div>
    </template>

    <template v-else>
      <div
        class="wb-chart-stack"
        :style="{
          display: 'grid',
          gridTemplateRows: showPortfolioBenchmark ? '344px 244px' : '520px',
          gap: showPortfolioBenchmark ? '12px' : '0',
          height: 'auto',
          minHeight: '0',
        }"
      >
        <div class="wb-chart-stack-panel" :style="{ minHeight: showPortfolioBenchmark ? '344px' : '520px' }">
          <div class="wb-mini" style="margin-bottom: 6px;">上图：NAV + 基准归一化收益曲线</div>
          <div id="wbResultsWorkbenchChartTop" ref="portfolioTopChartRef" class="wb-chart wb-chart-main" :style="{ height: showPortfolioBenchmark ? '320px' : '496px' }">
            <div class="wb-empty">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
              <span>运行实验后，在这里查看 NAV 与基准归一化收益曲线。</span>
            </div>
          </div>
        </div>
        <div v-show="showPortfolioBenchmark" class="wb-chart-stack-panel" style="min-height: 244px;">
          <div class="wb-mini" style="margin-bottom: 6px;">下图：基准绝对价格</div>
          <div id="wbResultsWorkbenchChartBottom" ref="portfolioBottomChartRef" class="wb-chart wb-chart-main" style="height: 220px;">
            <div class="wb-empty">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
              <span>运行实验后，在这里查看基准 K 线。</span>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div class="wb-canvas-footer">
      <div class="wb-mini">{{ chartFooter }}</div>
    </div>
  </section>
</template>
