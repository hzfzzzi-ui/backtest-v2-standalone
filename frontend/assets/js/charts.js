/* 鈹€鈹€ charts.js 鈹€鈹€ Chart rendering (SVG fallback + LightweightCharts) 鈹€鈹€ */
/* Globals used: state, byId, esc, num, setHtmlById (from desktop-shell/runtime-surface.js) */

function filterSeriesByRange(points, range) {
  const arr = Array.isArray(points) ? points : [];
  if (!arr.length || !range || range === 'ALL' || range === 'D') return arr;
  const n = range === '1M' ? 22 : (range === '3M' ? 66 : (range === '1Y' ? 252 : arr.length));
  return arr.slice(Math.max(0, arr.length - n));
}

// 灏嗘棩绾?OHLC 鑱氬悎涓哄懆绾?鏈堢嚎/骞寸嚎
function aggregateOhlc(dailyOhlc, period) {
  if (!dailyOhlc?.length || !period || period === 'D') return dailyOhlc;
  const buckets = new Map();
  for (const bar of dailyOhlc) {
    const d = bar.time; // 'YYYY-MM-DD'
    let key;
    if (period === 'W') {
      // 鎸夊懆鑱氬悎锛氱畻鍑哄懆涓€鐨勬棩鏈熶綔涓?key
      const dt = new Date(d + 'T00:00:00');
      const day = dt.getDay();
      const mon = new Date(dt);
      mon.setDate(dt.getDate() - ((day + 6) % 7));
      key = mon.toISOString().slice(0, 10);
    } else if (period === 'M') {
      key = d.slice(0, 7) + '-01'; // YYYY-MM-01
    } else if (period === 'Y') {
      key = d.slice(0, 4) + '-01-01'; // YYYY-01-01
    } else {
      return dailyOhlc;
    }
    if (!buckets.has(key)) {
      buckets.set(key, { time: key, open: bar.open, high: bar.high, low: bar.low, close: bar.close });
    } else {
      const b = buckets.get(key);
      if (bar.high > b.high) b.high = bar.high;
      if (bar.low < b.low) b.low = bar.low;
      b.close = bar.close; // 鏈€鍚庝竴澶╃殑 close
    }
  }
  return [...buckets.values()];
}

// Aggregate daily NAV into weekly / monthly / yearly rows using the last value in each period.
function aggregateNav(dailyNav, period) {
  if (!dailyNav?.length || !period || period === 'D') return dailyNav;
  const buckets = new Map();
  for (const pt of dailyNav) {
    const d = pt.date || pt.time;
    let key;
    if (period === 'W') {
      const dt = new Date(d + 'T00:00:00');
      const day = dt.getDay();
      const mon = new Date(dt);
      mon.setDate(dt.getDate() - ((day + 6) % 7));
      key = mon.toISOString().slice(0, 10);
    } else if (period === 'M') {
      key = d.slice(0, 7) + '-01';
    } else if (period === 'Y') {
      key = d.slice(0, 4) + '-01-01';
    } else {
      return dailyNav;
    }
    buckets.set(key, { date: key, value: pt.value });
  }
  return [...buckets.values()];
}

// Aggregate drawdown by period using the minimum value in each period.
function aggregateDrawdown(dailyDd, period) {
  if (!dailyDd?.length || !period || period === 'D') return dailyDd;
  const buckets = new Map();
  for (const pt of dailyDd) {
    const d = pt.date || pt.time;
    let key;
    if (period === 'W') {
      const dt = new Date(d + 'T00:00:00');
      const day = dt.getDay();
      const mon = new Date(dt);
      mon.setDate(dt.getDate() - ((day + 6) % 7));
      key = mon.toISOString().slice(0, 10);
    } else if (period === 'M') {
      key = d.slice(0, 7) + '-01';
    } else if (period === 'Y') {
      key = d.slice(0, 4) + '-01-01';
    } else {
      return dailyDd;
    }
    const existing = buckets.get(key);
    if (!existing || pt.value < existing.value) {
      buckets.set(key, { date: key, value: pt.value });
    }
  }
  return [...buckets.values()];
}

// MarketStateOverlay: LWC v4 series primitive for market-state background bands.
const MARKET_STATE_COLORS = {
  BULL:        'rgba(220, 38, 38, 0.08)',
  BULL_MAIN:   'rgba(220, 38, 38, 0.08)',
  TREND_MAIN:  'rgba(220, 38, 38, 0.08)',
  TRANS_UP:    'rgba(245, 158, 11, 0.08)',
  TURN_STRONG: 'rgba(245, 158, 11, 0.08)',
  TREND_LIGHT: 'rgba(245, 158, 11, 0.06)',
  TRANS_DOWN:  'rgba(59, 130, 246, 0.08)',
  TURN_WEAK:   'rgba(59, 130, 246, 0.08)',
  BEAR:        'rgba(22, 163, 74, 0.08)',
  DEFENSIVE:   'rgba(148, 163, 184, 0.08)',
  NO_TRADE:    'rgba(148, 163, 184, 0.08)',
  NO_TRADE_TRANS: 'rgba(148, 163, 184, 0.08)',
};

class MarketStatePaneRenderer {
  constructor(bands) { this._bands = bands; }
  draw(target) {
    // LWC v4: use useMediaCoordinateSpace for CSS-pixel drawing
    const scope = typeof target.useMediaCoordinateSpace === 'function'
      ? null  // will draw in callback below
      : target; // fallback: direct context (older API)
    if (typeof target.useMediaCoordinateSpace === 'function') {
      target.useMediaCoordinateSpace((s) => {
        const ctx = s.context;
        for (const band of this._bands) {
          if (!band.color) continue;
          ctx.fillStyle = band.color;
          ctx.fillRect(band.x, 0, Math.max(band.w, 1), s.mediaSize.height);
        }
      });
    } else if (target.context) {
      const ctx = target.context;
      for (const band of this._bands) {
        if (!band.color) continue;
        ctx.fillStyle = band.color;
        ctx.fillRect(band.x, 0, Math.max(band.w, 1), target.bitmapSize?.height || 400);
      }
    }
  }
}

class MarketStatePaneView {
  constructor(source) { this._source = source; }
  zOrder() { return 'bottom'; }
  renderer() {
    try {
      const data = this._source._data;
      const chart = this._source._chart;
      if (!data?.length || !chart) return null;
      const ts = chart.timeScale();
      const bands = [];
      let i = 0;
      while (i < data.length) {
        const mode = data[i].mode;
        const color = MARKET_STATE_COLORS[mode] || null;
        let j = i + 1;
        while (j < data.length && data[j].mode === mode) j++;
        if (color) {
          const x1 = ts.timeToCoordinate(data[i].time);
          const x2 = ts.timeToCoordinate(data[j - 1].time);
          if (x1 != null && x2 != null) {
            const barW = Math.max((x2 - x1) / Math.max(j - i - 1, 1), 2);
            bands.push({ x: Math.round(x1 - barW / 2), w: Math.round(x2 - x1 + barW), color });
          }
        }
        i = j;
      }
      return bands.length ? new MarketStatePaneRenderer(bands) : null;
    } catch (_) { return null; }
  }
}

class MarketStateOverlay {
  constructor() {
    this._data = [];
    this._chart = null;
    this._paneView = new MarketStatePaneView(this);
    this._requestUpdate = null;
  }
  setData(data) {
    this._data = data || [];
    if (typeof this._requestUpdate === 'function') {
      try { this._requestUpdate(); } catch (_) {}
    }
  }
  attached(p) {
    this._chart = p.chart || (p.series?.chart ? p.series.chart() : null);
    this._requestUpdate = typeof p.requestUpdate === 'function' ? (() => p.requestUpdate()) : null;
    if (typeof this._requestUpdate === 'function') this._requestUpdate();
  }
  detached() {
    this._chart = null;
    this._requestUpdate = null;
  }
  paneViews() { return [this._paneView]; }
}

// lightweight-charts instance state
let _lwChartNav = null;
let _lwChartDd = null;
let _syncLock = false;

let _lwNavState = null;

function destroyNavChartState() {
  const state = _lwNavState;
  if (!state) {
    if (_lwChartNav) {
      try { _lwChartNav.remove(); } catch (_) {}
      _lwChartNav = null;
    }
    return;
  }
  const container = state.container;
  const timeScaleApi = typeof state.chart?.timeScale === 'function' ? state.chart.timeScale() : null;
  if (timeScaleApi && state.visibleLogicalRangeHandler && typeof timeScaleApi.unsubscribeVisibleLogicalRangeChange === 'function') {
    try { timeScaleApi.unsubscribeVisibleLogicalRangeChange(state.visibleLogicalRangeHandler); } catch (_) {}
  }
  if (timeScaleApi && state.visibleTimeRangeHandler && typeof timeScaleApi.unsubscribeVisibleTimeRangeChange === 'function') {
    try { timeScaleApi.unsubscribeVisibleTimeRangeChange(state.visibleTimeRangeHandler); } catch (_) {}
  }
  if (container && state.wheelHandler) {
    try { container.removeEventListener('wheel', state.wheelHandler); } catch (_) {}
    if (container.__wbPriceScaleWheelHandler === state.wheelHandler) {
      container.__wbPriceScaleWheelHandler = null;
    }
  }
  if (state.resizeObserver) {
    try { state.resizeObserver.disconnect(); } catch (_) {}
  }
  if (state.chart) {
    try { state.chart.remove(); } catch (_) {}
  }
  _lwNavState = null;
  _lwChartNav = null;
}

function addNavLineSeries(chart, LWC, opts) {
  return typeof chart.addLineSeries === 'function'
    ? chart.addLineSeries(opts)
    : chart.addSeries(LWC.LineSeries, opts);
}

function addNavCandlestickSeries(chart, LWC, opts) {
  return typeof chart.addCandlestickSeries === 'function'
    ? chart.addCandlestickSeries(opts)
    : chart.addSeries(LWC.CandlestickSeries, opts);
}

function createNavChartState(container, LWC) {
  if (!container) return null;
  container.innerHTML = '';
  const chart = LWC.createChart(container, {
    width: container.clientWidth,
    height: container.clientHeight || 420,
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
    handleScale: {
      mouseWheel: true,
      pinch: true,
      axisPressedMouseMove: {
        time: true,
        price: true,
      },
      axisDoubleClickReset: {
        time: true,
        price: true,
      },
    },
    timeScale: {
      borderColor: '#334155',
      timeVisible: false,
      barSpacing: 6,
      minBarSpacing: 2,
      rightOffset: 5,
    },
  });
  const state = {
    container,
    chart,
    shapeKey: '',
    visibleKey: '',
    showLeftBenchmarkScale: false,
    symbolBadgeUpdater: null,
    benchmarkSeries: null,
    primarySeries: null,
    suspensionSeries: null,
    marketOverlay: null,
    refreshVisiblePriceScales: () => {},
    wheelHandler: null,
    visibleLogicalRangeHandler: null,
    visibleTimeRangeHandler: null,
    resizeObserver: null,
  };
  state.refreshVisiblePriceScales = () => {
    try { state.chart.priceScale('right').applyOptions({ autoScale: true }); } catch (_) {}
    if (state.showLeftBenchmarkScale) {
      try { state.chart.priceScale('left').applyOptions({ autoScale: true }); } catch (_) {}
    }
    if (typeof state.symbolBadgeUpdater === 'function') {
      requestAnimationFrame(state.symbolBadgeUpdater);
    }
  };
  state.wheelHandler = () => {
    requestAnimationFrame(state.refreshVisiblePriceScales);
  };
  container.__wbPriceScaleWheelHandler = state.wheelHandler;
  container.addEventListener('wheel', state.wheelHandler, { passive: true });
  const timeScaleApi = chart.timeScale();
  state.visibleLogicalRangeHandler = () => {
    requestAnimationFrame(state.refreshVisiblePriceScales);
  };
  state.visibleTimeRangeHandler = () => {
    requestAnimationFrame(state.refreshVisiblePriceScales);
  };
  if (typeof timeScaleApi?.subscribeVisibleLogicalRangeChange === 'function') {
    timeScaleApi.subscribeVisibleLogicalRangeChange(state.visibleLogicalRangeHandler);
  } else if (typeof timeScaleApi?.subscribeVisibleTimeRangeChange === 'function') {
    timeScaleApi.subscribeVisibleTimeRangeChange(state.visibleTimeRangeHandler);
  }
  state.resizeObserver = new ResizeObserver(() => {
    if (_lwNavState !== state) return;
    try {
      state.chart.applyOptions({ width: container.clientWidth, height: container.clientHeight || 420 });
    } catch (_) {}
    if (typeof state.symbolBadgeUpdater === 'function') {
      requestAnimationFrame(state.symbolBadgeUpdater);
    }
  });
  state.resizeObserver.observe(container);
  _lwChartNav = chart;
  _lwNavState = state;
  return state;
}

function resetNavChartSeries(state, LWC, shape) {
  if (!state?.chart) return state;
  if (typeof state.chart.removeSeries !== 'function') {
    destroyNavChartState();
    return createNavChartState(state?.container, LWC);
  }
  for (const series of [state.benchmarkSeries, state.primarySeries, state.suspensionSeries]) {
    if (!series) continue;
    try { state.chart.removeSeries(series); } catch (_) {}
  }
  state.benchmarkSeries = null;
  state.primarySeries = null;
  state.suspensionSeries = null;
  state.marketOverlay = null;

  if (shape.benchmarkKind === 'candlestick-right') {
    state.benchmarkSeries = addNavCandlestickSeries(state.chart, LWC, {
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderDownColor: '#ef5350',
      borderUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      wickUpColor: '#26a69a',
      priceScaleId: 'right',
      priceLineVisible: false,
      lastValueVisible: false,
    });
  } else if (shape.benchmarkKind === 'line-left') {
    state.benchmarkSeries = addNavLineSeries(state.chart, LWC, {
      color: '#58a6ff',
      lineWidth: 2,
      lineStyle: LWC.LineStyle ? LWC.LineStyle.Solid : 0,
      priceScaleId: 'left',
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });
  }

  if (shape.hasNav) {
    const buildPrimarySeries = (color) => addNavLineSeries(state.chart, LWC, {
      color,
      lineWidth: 2,
      crosshairMarkerVisible: !shape.hasSuspension,
      priceLineVisible: false,
      lastValueVisible: !shape.hasSuspension && shape.mode !== 'symbol',
    });
    if (shape.hasSuspension) {
      state.suspensionSeries = buildPrimarySeries('#999');
      state.primarySeries = buildPrimarySeries('#f59e0b');
    } else {
      state.primarySeries = buildPrimarySeries(shape.mode === 'symbol' ? '#f59e0b' : '#58a6ff');
    }
    state.marketOverlay = new MarketStateOverlay();
    if (state.primarySeries && typeof state.primarySeries.attachPrimitive === 'function') {
      try { state.primarySeries.attachPrimitive(state.marketOverlay); } catch (_) {}
    }
  }
  state.shapeKey = shape.key;
  return state;
}

function renderLoadingSkeleton() {
  setHtmlById('wbGroupLoadStatus', '<span class="wb-mini">鍔犺浇缁勪骇鐗╀腑...</span>');
  // 娓呯悊 lightweight-charts 瀹炰緥鍚庡啀鏇挎崲 innerHTML
  destroyNavChartState();
  if (_lwChartDd) { _lwChartDd.remove(); _lwChartDd = null; }
  setHtmlById('wbNavChart', '<div class="wb-skeleton" style="height:100%"></div>');
  setHtmlById('wbDdChart', '<div class="wb-skeleton" style="height:100%"></div>');
}

function linePath(points, width, height, minY, maxY, pad) {
  if (!points.length) return '';
  const w = width - pad * 2;
  const h = height - pad * 2;
  const span = Math.max(maxY - minY, 1e-9);
  return points.map((p, i) => {
    const x = pad + (points.length <= 1 ? 0 : (i / (points.length - 1)) * w);
    const y = pad + (1 - (p.value - minY) / span) * h;
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(' ');
}

function renderLineChart(containerId, series, yFmt = (v) => num(v, 4)) {
  const container = byId(containerId);
  if (!container) return;
  const cleanSeries = (series || []).filter((s) => Array.isArray(s.points) && s.points.length);
  if (!cleanSeries.length) {
    const isMain = containerId === 'wbNavChart';
    const svgSize = isMain ? 48 : 32;
    container.innerHTML = `<div class="wb-empty"><svg width="${svgSize}" height="${svgSize}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg><span>${isMain ? '运行实验后显示净值曲线' : '回撤曲线'}</span></div>`;
    return;
  }
  const width = container.clientWidth || 600;
  const height = container.clientHeight || 280;
  const pad = 28;
  const values = cleanSeries.flatMap((s) => s.points.map((p) => Number(p.value)));
  const minY = Math.min(...values);
  const maxY = Math.max(...values);
  const y0 = Number.isFinite(minY) ? minY : 0;
  const y1 = Number.isFinite(maxY) ? maxY : 1;
  const legend = cleanSeries.map((s) => `<span style="display:inline-flex;align-items:center;gap:4px;margin-right:12px"><span style="display:inline-block;width:10px;height:2px;background:${s.color}"></span>${esc(s.name)}</span>`).join('');
  const paths = cleanSeries.map((s) => {
    const pts = s.points.map((p) => ({ value: Number(p.value) })).filter((p) => Number.isFinite(p.value));
    const d = linePath(pts, width, height, y0, y1, pad);
    return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2"/>`;
  }).join('');
  container.innerHTML = `
    <div class="wb-mini" style="margin-bottom:6px">${legend}</div>
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      <rect x="0" y="0" width="${width}" height="${height}" fill="transparent"/>
      <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="#334155" stroke-width="1"/>
      <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="#334155" stroke-width="1"/>
      ${paths}
      <text x="4" y="${pad}" fill="#94a3b8" font-size="11">${esc(yFmt(y1))}</text>
      <text x="4" y="${height - pad}" fill="#94a3b8" font-size="11">${esc(yFmt(y0))}</text>
    </svg>
  `;
}

function clearChartValueBadge(container) {
  if (!container) return;
  container.querySelectorAll('.wb-chart-value-badge').forEach((node) => node.remove());
}

function renderChartValueBadge(container, seriesApi, value, label) {
  if (!container || !Number.isFinite(Number(value)) || !label) return;
  clearChartValueBadge(container);
  const badge = document.createElement('div');
  badge.className = 'wb-chart-value-badge';
  badge.textContent = label;
  container.appendChild(badge);
  const applyPosition = () => {
    let top = 12;
    try {
      const y = typeof seriesApi?.priceToCoordinate === 'function' ? seriesApi.priceToCoordinate(Number(value)) : null;
      if (Number.isFinite(y)) top = Math.max(10, Math.min((container.clientHeight || 520) - 34, y - 12));
    } catch (_) {
      // badge position fallback
    }
    badge.style.top = `${top}px`;
  };
  requestAnimationFrame(applyPosition);
}

function renderNavChartLW(containerId, benchOhlc, navSeries, showBenchmark, opts = {}) {
  const container = document.getElementById(containerId);
  if (!container) return;
  clearChartValueBadge(container);

  const hasNav = Array.isArray(navSeries) && navSeries.length > 0;
  const hasBench = Array.isArray(benchOhlc) && benchOhlc.length > 0;
  const mode = String(opts.mode || 'portfolio');
  const markers = Array.isArray(opts.markers) ? opts.markers : [];
  const useUnifiedRightScale = mode === 'portfolio';
  const showLeftBenchmarkScale = !!showBenchmark && hasBench && !useUnifiedRightScale;
  const useRelativeBenchLine = !!showBenchmark && hasBench;
  const benchFirstClose = Number(benchOhlc[0]?.close) || 1;
  const normalizedBenchLineData = useRelativeBenchLine
    ? benchOhlc.map((p) => ({ time: p.time, value: Number(p.close) / benchFirstClose }))
    : [];
  const normalizedBenchOhlc = useRelativeBenchLine
    ? benchOhlc.map((p) => ({
        time: p.time,
        open: Number(p.open) / benchFirstClose,
        high: Number(p.high) / benchFirstClose,
        low: Number(p.low) / benchFirstClose,
        close: Number(p.close) / benchFirstClose,
      }))
    : [];


  // Empty-state rendering.
  if (!hasNav && !hasBench) {
    if (_lwChartNav) { _lwChartNav.remove(); _lwChartNav = null; }
    container.innerHTML = '<div class="wb-empty"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg><span>杩愯瀹為獙鍚庢樉绀哄噣鍊兼洸绾?/span></div>';
    return;
  }

  // Reset previous chart instance.
  if (_lwChartNav) { _lwChartNav.remove(); _lwChartNav = null; }
  container.innerHTML = '';

  const LWC = window.LightweightCharts;
  if (!LWC) {
    container.innerHTML = '<div class="wb-empty"><span>lightweight-charts 鍔犺浇澶辫触</span></div>';
    return;
  }

  const chart = LWC.createChart(container, {
    width: container.clientWidth,
    height: container.clientHeight || 420,
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
    leftPriceScale: { visible: showLeftBenchmarkScale, borderColor: '#334155', autoScale: true },
    rightPriceScale: { visible: true, borderColor: '#334155', autoScale: true },
    handleScale: {
      mouseWheel: true,
      pinch: true,
      axisPressedMouseMove: {
        time: true,
        price: true,
      },
      axisDoubleClickReset: {
        time: true,
        price: true,
      },
    },
    timeScale: {
      borderColor: '#334155',
      timeVisible: false,
      barSpacing: 6,       // 榛樿铚＄儧闂磋窛锛堝儚绱狅級锛屽弬鑰冧笢鏂硅储瀵?鍚岃姳椤?      minBarSpacing: 2,    // 缂╂斁涓嬮檺
      rightOffset: 5,      // 鍙充晶鐣欑櫧
    },
  });
  _lwChartNav = chart;
  let symbolBadgeUpdater = null;
  let refreshVisiblePriceScales = () => {};

  // Benchmark series, compatible with multiple LWC APIs.
  if (showBenchmark && hasBench) {
    if (useUnifiedRightScale) {
      // In portfolio mode normalize benchmark candles onto the right scale.
      const candleSeries = typeof chart.addCandlestickSeries === 'function'
        ? chart.addCandlestickSeries({
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderDownColor: '#ef5350',
            borderUpColor: '#26a69a',
            wickDownColor: '#ef5350',
            wickUpColor: '#26a69a',
            priceScaleId: 'right',
            priceLineVisible: false,
            lastValueVisible: false,
          })
        : chart.addSeries(LWC.CandlestickSeries, {
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderDownColor: '#ef5350',
            borderUpColor: '#26a69a',
            wickDownColor: '#ef5350',
            wickUpColor: '#26a69a',
            priceScaleId: 'right',
            priceLineVisible: false,
            lastValueVisible: false,
          });
      candleSeries.setData(normalizedBenchOhlc);
    } else if (useRelativeBenchLine) {
      const benchLine = typeof chart.addLineSeries === 'function'
        ? chart.addLineSeries({
            color: '#58a6ff',
            lineWidth: 2,
            lineStyle: LWC.LineStyle ? LWC.LineStyle.Solid : 0,
            priceScaleId: 'left',
            crosshairMarkerVisible: false,
            priceLineVisible: false,
            lastValueVisible: false,
          })
        : chart.addSeries(LWC.LineSeries, {
            color: '#58a6ff',
            lineWidth: 2,
            lineStyle: LWC.LineStyle ? LWC.LineStyle.Solid : 0,
            priceScaleId: 'left',
            crosshairMarkerVisible: false,
            priceLineVisible: false,
            lastValueVisible: false,
          });
      benchLine.setData(normalizedBenchLineData);
    } else {
      const candleSeries = typeof chart.addCandlestickSeries === 'function'
        ? chart.addCandlestickSeries({
            upColor: '#26a69a', downColor: '#ef5350',
            borderDownColor: '#ef5350', borderUpColor: '#26a69a',
            wickDownColor: '#ef5350', wickUpColor: '#26a69a',
            priceScaleId: 'left',
          })
        : chart.addSeries(LWC.CandlestickSeries, {
            upColor: '#26a69a', downColor: '#ef5350',
            borderDownColor: '#ef5350', borderUpColor: '#26a69a',
            wickDownColor: '#ef5350', wickUpColor: '#26a69a',
            priceScaleId: 'left',
          });
      candleSeries.setData(benchOhlc);
    }
  }

  // Strategy NAV 鎶樼嚎锛堝綊涓€鍖栧悗涓?Benchmark 鍚岄噺绾э級
  if (hasNav) {
    // Portfolio NAV is normalized to start near 1.0 in non-symbol mode.
    const firstVal = navSeries[0]?.value || 1;
    const lineData = navSeries.map((p) => ({
      time: p.date,
      value: mode === 'symbol' ? Number(p.value) : (Number(p.value) / firstVal),
    }));
    const rightValues = lineData
      .map((p) => Number(p.value))
      .filter((v) => Number.isFinite(v));
    if (useUnifiedRightScale && normalizedBenchOhlc.length) {
      rightValues.push(
        ...normalizedBenchOhlc
          .flatMap((p) => [Number(p.open), Number(p.high), Number(p.low), Number(p.close)])
          .filter((v) => Number.isFinite(v)),
      );
    }
    const fixedRightAutoscaleProvider = rightValues.length
      ? (() => {
          const minValue = Math.min(...rightValues);
          const maxValue = Math.max(...rightValues);
          const span = Math.max(maxValue - minValue, Math.max(Math.abs(maxValue), 1) * 0.02, 1e-6);
          const pad = span * 0.08;
          return () => ({
            priceRange: {
              minValue: minValue - pad,
              maxValue: maxValue + pad,
            },
          });
        })()
      : null;

    // Symbol mode splits suspended ranges into a secondary grey series.
    const suspRanges = Array.isArray(opts.suspensionRanges) ? opts.suspensionRanges : [];
    const hasSuspension = mode === 'symbol' && suspRanges.length > 0;

    const _addLine = (color) => typeof chart.addLineSeries === 'function'
      ? chart.addLineSeries({ color, lineWidth: 2, crosshairMarkerVisible: !hasSuspension, priceLineVisible: false, lastValueVisible: !hasSuspension && mode !== 'symbol' })
      : chart.addSeries(LWC.LineSeries, { color, lineWidth: 2, crosshairMarkerVisible: !hasSuspension, priceLineVisible: false, lastValueVisible: !hasSuspension && mode !== 'symbol' });

    let primaryLine;
    if (hasSuspension) {
      // 鏋勫缓鍋滅墝鏃ユ湡闆嗗悎
      const suspSet = new Set();
      for (const r of suspRanges) {
        for (const p of lineData) {
          if (p.time >= r.start && p.time <= r.end) suspSet.add(p.time);
        }
      }
      // 姝ｅ父娈碉紙姗欒壊锛夛細鍋滅墝鐐硅涓?NaN 鏂紑锛屼絾淇濈暀杈圭晫鐐逛娇绾挎杩炴帴
      const normalData = [];
      const suspData = [];
      for (let i = 0; i < lineData.length; i++) {
        const p = lineData[i];
        const isSusp = suspSet.has(p.time);
        const prevSusp = i > 0 && suspSet.has(lineData[i - 1].time);
        const nextSusp = i < lineData.length - 1 && suspSet.has(lineData[i + 1].time);
        if (isSusp) {
          suspData.push(p);
          // 鍋滅墝娈甸灏惧姞鍒版甯告鍋氳繛鎺ョ偣
          if (!prevSusp || !nextSusp) normalData.push(p);
        } else {
          normalData.push(p);
          // 姝ｅ父娈甸灏惧姞鍒板仠鐗屾鍋氳繛鎺ョ偣
          if (nextSusp) suspData.push(p);
          if (prevSusp) suspData.push(p);
        }
      }
      // Deduplicate by time while preserving final value for each bar.
      const dedup = (arr) => {
        const m = new Map();
        for (const p of arr) m.set(p.time, p);
        return Array.from(m.values()).sort((a, b) => (a.time < b.time ? -1 : 1));
      };
      const suspLine = _addLine('#999');
      if (fixedRightAutoscaleProvider) {
        try { suspLine.applyOptions({ autoscaleInfoProvider: fixedRightAutoscaleProvider }); } catch (_) {}
      }
      suspLine.setData(dedup(suspData));
      primaryLine = _addLine('#f59e0b');
      if (fixedRightAutoscaleProvider) {
        try { primaryLine.applyOptions({ autoscaleInfoProvider: fixedRightAutoscaleProvider }); } catch (_) {}
      }
      primaryLine.setData(dedup(normalData));
      if (mode === 'symbol') {
        const lastValue = Number(lineData[lineData.length - 1]?.value);
        symbolBadgeUpdater = () => renderChartValueBadge(container, primaryLine, lastValue, `涓偂鍑€鍊?${num(lastValue, 2)}x`);
      }
    } else {
      primaryLine = _addLine(mode === 'symbol' ? '#f59e0b' : '#58a6ff');
      if (fixedRightAutoscaleProvider) {
        try { primaryLine.applyOptions({ autoscaleInfoProvider: fixedRightAutoscaleProvider }); } catch (_) {}
      }
      primaryLine.setData(lineData);
      if (mode === 'symbol') {
        const lastValue = Number(lineData[lineData.length - 1]?.value);
        symbolBadgeUpdater = () => renderChartValueBadge(container, primaryLine, lastValue, `涓偂鍑€鍊?${num(lastValue, 2)}x`);
      }
    }

    if (markers.length) {
      try {
        if (typeof primaryLine.setMarkers === 'function') {
          primaryLine.setMarkers(markers);
        } else if (typeof LWC.createSeriesMarkers === 'function') {
          LWC.createSeriesMarkers(primaryLine, markers);
        }
      } catch (_) {
        // marker rendering is optional
      }
    }
    // MarketStateOverlay 鈥?鎸傝浇鍒颁富鎶樼嚎绯诲垪
    const marketStates = Array.isArray(opts.marketStates) ? opts.marketStates : [];
    if (marketStates.length) {
      try {
        const overlay = new MarketStateOverlay();
        overlay.setData(marketStates);
        if (typeof primaryLine.attachPrimitive === 'function') {
          primaryLine.attachPrimitive(overlay);
        }
      } catch (_) { /* primitive API optional */ }
    }
    if (mode === 'symbol' && primaryLine && lineData.length) {
      const lastValue = Number(lineData[lineData.length - 1]?.value);
      const lastClose = Number(opts?.symbolLastClose);
      const label = Number.isFinite(lastClose)
        ? `涓偂鏀剁洏浠?${num(lastClose, 2)}`
        : `涓偂鍑€鍊?${num(lastValue, 2)}x`;
      symbolBadgeUpdater = () => renderChartValueBadge(container, primaryLine, lastValue, label);
    }
    if (typeof symbolBadgeUpdater === 'function') requestAnimationFrame(symbolBadgeUpdater);
  }

  // Large series default to the most recent visible window.
  const totalBars = Math.max(benchOhlc?.length || 0, navSeries?.length || 0);
  const chartWidth = container.clientWidth || 600;
  const maxVisibleBars = Math.floor(chartWidth / 6); // 6px 闂磋窛
  if (totalBars > maxVisibleBars) {
    chart.timeScale().scrollToPosition(5, false);
  } else {
    chart.timeScale().fitContent();
  }
  if (typeof symbolBadgeUpdater === 'function') requestAnimationFrame(symbolBadgeUpdater);

  refreshVisiblePriceScales = () => {
    try { chart.priceScale('right').applyOptions({ autoScale: true }); } catch (_) {}
    if (showLeftBenchmarkScale) {
      try { chart.priceScale('left').applyOptions({ autoScale: true }); } catch (_) {}
    }
    if (typeof symbolBadgeUpdater === 'function') requestAnimationFrame(symbolBadgeUpdater);
  };
  if (typeof container.__wbPriceScaleWheelHandler === 'function') {
    container.removeEventListener('wheel', container.__wbPriceScaleWheelHandler);
  }
  container.__wbPriceScaleWheelHandler = () => {
    requestAnimationFrame(refreshVisiblePriceScales);
  };
  container.addEventListener('wheel', container.__wbPriceScaleWheelHandler, { passive: true });
  const timeScaleApi = chart.timeScale();
  if (typeof timeScaleApi?.subscribeVisibleLogicalRangeChange === 'function') {
    timeScaleApi.subscribeVisibleLogicalRangeChange(() => {
      requestAnimationFrame(refreshVisiblePriceScales);
    });
  } else if (typeof timeScaleApi?.subscribeVisibleTimeRangeChange === 'function') {
    timeScaleApi.subscribeVisibleTimeRangeChange(() => {
      requestAnimationFrame(refreshVisiblePriceScales);
    });
  }

  // 鍝嶅簲瀹瑰櫒澶у皬鍙樺寲
  const ro = new ResizeObserver(() => {
    if (_lwChartNav === chart) {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight || 420 });
      if (typeof symbolBadgeUpdater === 'function') requestAnimationFrame(symbolBadgeUpdater);
    }
  });
  ro.observe(container);
}

// 鍥炴挙鍥?鈥?LightweightCharts AreaSeries 娓叉煋
function renderNavChartLW(containerId, benchOhlc, navSeries, showBenchmark, opts = {}) {
  const container = document.getElementById(containerId);
  if (!container) return;
  clearChartValueBadge(container);

  const hasNav = Array.isArray(navSeries) && navSeries.length > 0;
  const hasBench = Array.isArray(benchOhlc) && benchOhlc.length > 0;
  const mode = String(opts.mode || 'portfolio');
  const markers = Array.isArray(opts.markers) ? opts.markers : [];
  const useUnifiedRightScale = mode === 'portfolio';
  const showLeftBenchmarkScale = !!showBenchmark && hasBench && !useUnifiedRightScale;
  const useRelativeBenchLine = !!showBenchmark && hasBench;
  const benchFirstClose = Number(benchOhlc[0]?.close) || 1;
  const normalizedBenchLineData = useRelativeBenchLine
    ? benchOhlc.map((p) => ({ time: p.time, value: Number(p.close) / benchFirstClose }))
    : [];
  const normalizedBenchOhlc = useRelativeBenchLine
    ? benchOhlc.map((p) => ({
        time: p.time,
        open: Number(p.open) / benchFirstClose,
        high: Number(p.high) / benchFirstClose,
        low: Number(p.low) / benchFirstClose,
        close: Number(p.close) / benchFirstClose,
      }))
    : [];
  const suspensionRanges = Array.isArray(opts.suspensionRanges) ? opts.suspensionRanges : [];
  const hasSuspension = mode === 'symbol' && suspensionRanges.length > 0;

  if (!hasNav && !hasBench) {
    destroyNavChartState();
    container.innerHTML = '<div class="wb-empty"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg><span>鏉╂劘顢戠€圭偤鐛欓崥搴㈡▔缁€鍝勫櫍閸婂吋娲哥痪?/span></div>';
    return;
  }

  const LWC = window.LightweightCharts;
  if (!LWC) {
    destroyNavChartState();
    container.innerHTML = '<div class="wb-empty"><span>lightweight-charts 閸旂姾娴囨径杈Е</span></div>';
    return;
  }

  const shape = {
    key: [
      mode,
      hasNav ? 'nav' : 'no-nav',
      showBenchmark && hasBench ? (useUnifiedRightScale ? 'bench-candle-right' : 'bench-line-left') : 'bench-none',
      hasSuspension ? 'susp' : 'plain',
    ].join('|'),
    mode,
    hasNav,
    hasSuspension,
    benchmarkKind: showBenchmark && hasBench ? (useUnifiedRightScale ? 'candlestick-right' : 'line-left') : 'none',
  };

  let navState = _lwNavState;
  if (!navState || navState.container !== container) {
    destroyNavChartState();
    navState = createNavChartState(container, LWC);
  }
  if (!navState) return;
  if (navState.shapeKey !== shape.key) {
    navState = resetNavChartSeries(navState, LWC, shape);
  }
  if (!navState?.chart) return;

  const chart = navState.chart;
  navState.showLeftBenchmarkScale = showLeftBenchmarkScale;
  navState.symbolBadgeUpdater = null;

  try {
    chart.applyOptions({
      leftPriceScale: { visible: showLeftBenchmarkScale, borderColor: '#334155', autoScale: true },
      rightPriceScale: { visible: true, borderColor: '#334155', autoScale: true },
    });
  } catch (_) {}

  if (navState.benchmarkSeries) {
    if (shape.benchmarkKind === 'candlestick-right') {
      navState.benchmarkSeries.setData(normalizedBenchOhlc);
    } else if (shape.benchmarkKind === 'line-left') {
      navState.benchmarkSeries.setData(normalizedBenchLineData);
    }
  }

  if (hasNav && navState.primarySeries) {
    const firstVal = navSeries[0]?.value || 1;
    const lineData = navSeries.map((p) => ({
      time: p.date,
      value: mode === 'symbol' ? Number(p.value) : (Number(p.value) / firstVal),
    }));
    const rightValues = lineData
      .map((p) => Number(p.value))
      .filter((v) => Number.isFinite(v));
    if (useUnifiedRightScale && normalizedBenchOhlc.length) {
      rightValues.push(
        ...normalizedBenchOhlc
          .flatMap((p) => [Number(p.open), Number(p.high), Number(p.low), Number(p.close)])
          .filter((v) => Number.isFinite(v)),
      );
    }
    const fixedRightAutoscaleProvider = rightValues.length
      ? (() => {
          const minValue = Math.min(...rightValues);
          const maxValue = Math.max(...rightValues);
          const span = Math.max(maxValue - minValue, Math.max(Math.abs(maxValue), 1) * 0.02, 1e-6);
          const pad = span * 0.08;
          return () => ({
            priceRange: {
              minValue: minValue - pad,
              maxValue: maxValue + pad,
            },
          });
        })()
      : null;

    if (fixedRightAutoscaleProvider) {
      try { navState.primarySeries.applyOptions({ autoscaleInfoProvider: fixedRightAutoscaleProvider }); } catch (_) {}
      try { navState.suspensionSeries?.applyOptions({ autoscaleInfoProvider: fixedRightAutoscaleProvider }); } catch (_) {}
    }

    if (hasSuspension && navState.suspensionSeries) {
      const suspSet = new Set();
      for (const range of suspensionRanges) {
        for (const point of lineData) {
          if (point.time >= range.start && point.time <= range.end) suspSet.add(point.time);
        }
      }
      const normalData = [];
      const suspData = [];
      for (let i = 0; i < lineData.length; i++) {
        const point = lineData[i];
        const isSusp = suspSet.has(point.time);
        const prevSusp = i > 0 && suspSet.has(lineData[i - 1].time);
        const nextSusp = i < lineData.length - 1 && suspSet.has(lineData[i + 1].time);
        if (isSusp) {
          suspData.push(point);
          if (!prevSusp || !nextSusp) normalData.push(point);
        } else {
          normalData.push(point);
          if (nextSusp) suspData.push(point);
          if (prevSusp) suspData.push(point);
        }
      }
      const dedup = (arr) => {
        const byTime = new Map();
        for (const point of arr) byTime.set(point.time, point);
        return Array.from(byTime.values()).sort((a, b) => (a.time < b.time ? -1 : 1));
      };
      navState.suspensionSeries.setData(dedup(suspData));
      navState.primarySeries.setData(dedup(normalData));
    } else {
      navState.primarySeries.setData(lineData);
    }

    if (typeof navState.primarySeries.setMarkers === 'function') {
      try { navState.primarySeries.setMarkers(markers); } catch (_) {}
    } else if (markers.length && typeof LWC.createSeriesMarkers === 'function') {
      try { LWC.createSeriesMarkers(navState.primarySeries, markers); } catch (_) {}
    }

    if (navState.marketOverlay) {
      navState.marketOverlay.setData(Array.isArray(opts.marketStates) ? opts.marketStates : []);
    }

    if (mode === 'symbol' && lineData.length) {
      const lastValue = Number(lineData[lineData.length - 1]?.value);
      const lastClose = Number(opts?.symbolLastClose);
      const label = Number.isFinite(lastClose)
        ? `娑擃亣鍋傞弨鍓佹磸娴?${num(lastClose, 2)}`
        : `娑擃亣鍋傞崙鈧崐?${num(lastValue, 2)}x`;
      navState.symbolBadgeUpdater = () => renderChartValueBadge(container, navState.primarySeries, lastValue, label);
    }
  }

  const totalBars = Math.max(benchOhlc?.length || 0, navSeries?.length || 0);
  const chartWidth = container.clientWidth || 600;
  const maxVisibleBars = Math.floor(chartWidth / 6);
  const visibleKey = [
    totalBars,
    normalizedBenchOhlc[0]?.time || normalizedBenchLineData[0]?.time || '',
    normalizedBenchOhlc[normalizedBenchOhlc.length - 1]?.time || normalizedBenchLineData[normalizedBenchLineData.length - 1]?.time || '',
    navSeries?.[0]?.date || '',
    navSeries?.[navSeries.length - 1]?.date || '',
    mode,
    showBenchmark ? 'bench' : 'no-bench',
  ].join('|');
  if (navState.visibleKey !== visibleKey) {
    if (totalBars > maxVisibleBars) {
      chart.timeScale().scrollToPosition(5, false);
    } else {
      chart.timeScale().fitContent();
    }
    navState.visibleKey = visibleKey;
  }

  if (typeof navState.symbolBadgeUpdater === 'function') {
    requestAnimationFrame(navState.symbolBadgeUpdater);
  }
}

function renderDdChartLW(containerId, ddSeries, benchDdSeries, showBenchmark, opts = {}) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const hasDd = Array.isArray(ddSeries) && ddSeries.length > 0;
  const hasBenchDd = Array.isArray(benchDdSeries) && benchDdSeries.length > 0;

  if (!hasDd && !hasBenchDd) {
    if (_lwChartDd) { _lwChartDd.remove(); _lwChartDd = null; }
    container.innerHTML = '<div class="wb-empty"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg><span>鍥炴挙鏇茬嚎</span></div>';
    return;
  }

  if (_lwChartDd) { _lwChartDd.remove(); _lwChartDd = null; }
  container.innerHTML = '';

  const LWC = window.LightweightCharts;
  if (!LWC) {
    container.innerHTML = '<div class="wb-empty"><span>lightweight-charts 鍔犺浇澶辫触</span></div>';
    return;
  }

  const chart = LWC.createChart(container, {
    width: container.clientWidth,
    height: container.clientHeight || 160,
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
    rightPriceScale: {
      borderColor: '#334155',
    },
    localization: {
      priceFormatter: (v) => (v * 100).toFixed(1) + '%',
    },
    timeScale: {
      borderColor: '#334155',
      timeVisible: false,
      barSpacing: 6,
      minBarSpacing: 2,
      rightOffset: 5,
    },
  });
  _lwChartDd = chart;

  // 绛栫暐鍥炴挙 鈥?BaselineSeries 浠?0 涓哄熀绾匡紝鍚戜笅濉厖绾㈣壊
  if (hasDd) {
    const baseOpts = {
      baseValue: { type: 'price', price: 0 },
      topLineColor: 'transparent',
      topFillColor1: 'transparent',
      topFillColor2: 'transparent',
      bottomLineColor: '#ef4444',
      bottomFillColor1: 'rgba(239, 68, 68, 0.35)',
      bottomFillColor2: 'rgba(239, 68, 68, 0.05)',
      lineWidth: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: true,
    };
    const baselineSeries = typeof chart.addBaselineSeries === 'function'
      ? chart.addBaselineSeries(baseOpts)
      : chart.addSeries(LWC.BaselineSeries, baseOpts);
    baselineSeries.setData(ddSeries.map((p) => ({ time: p.date, value: p.value })));
    // MarketStateOverlay 鈥?鎸傝浇鍒板洖鎾?BaselineSeries
    const marketStates = Array.isArray(opts.marketStates) ? opts.marketStates : [];
    if (marketStates.length) {
      try {
        const overlay = new MarketStateOverlay();
        overlay.setData(marketStates);
        if (typeof baselineSeries.attachPrimitive === 'function') {
          baselineSeries.attachPrimitive(overlay);
        }
      } catch (_) { /* primitive API optional */ }
    }
  }

  // Benchmark drawdown line.
  if (showBenchmark && hasBenchDd) {
    const lineOpts = { color: '#f97316', lineWidth: 1, priceLineVisible: false, crosshairMarkerVisible: false };
    const benchLine = typeof chart.addLineSeries === 'function'
      ? chart.addLineSeries(lineOpts)
      : chart.addSeries(LWC.LineSeries, lineOpts);
    benchLine.setData(benchDdSeries.map((p) => ({ time: p.date, value: p.value })));
  }

  chart.timeScale().fitContent();

  // 鍝嶅簲瀹瑰櫒澶у皬鍙樺寲
  const ro = new ResizeObserver(() => {
    if (_lwChartDd === chart) {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight || 160 });
    }
  });
  ro.observe(container);

  // --- 鏃堕棿杞村悓姝?+ crosshair 鑱斿姩 ---
  setupChartSync();
}

// 鍙屽浘鏃堕棿杞村悓姝?+ crosshair 鑱斿姩
function setupChartSync() {
  if (!_lwChartNav || !_lwChartDd) return;

  // 鏃堕棿杞寸缉鏀?骞崇Щ鍚屾
  _lwChartNav.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (_syncLock || !range) return;
    _syncLock = true;
    try { _lwChartDd.timeScale().setVisibleLogicalRange(range); } catch (_) {}
    _syncLock = false;
  });
  _lwChartDd.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (_syncLock || !range) return;
    _syncLock = true;
    try { _lwChartNav.timeScale().setVisibleLogicalRange(range); } catch (_) {}
    _syncLock = false;
  });

  // crosshair 鑱斿姩
  _lwChartNav.subscribeCrosshairMove((param) => {
    if (!param || !param.time) {
      _lwChartDd.clearCrosshairPosition();
      return;
    }
    // 鐢?setCrosshairPosition 鍚屾鍒板洖鎾ゅ浘锛堥渶瑕?price + time锛?    // 浼?NaN 浣滀负 price 璁?LWC 鑷姩瀹氫綅鍒版暟鎹偣
    try { _lwChartDd.setCrosshairPosition(NaN, param.time, _lwChartDd.getSeries?.() || undefined); } catch (_) {}
  });
  _lwChartDd.subscribeCrosshairMove((param) => {
    if (!param || !param.time) {
      _lwChartNav.clearCrosshairPosition();
      return;
    }
    try { _lwChartNav.setCrosshairPosition(NaN, param.time, _lwChartNav.getSeries?.() || undefined); } catch (_) {}
  });
}


/* merged legacy results-chart-nav-override.js into charts.js on 2026-04-26 */
(function setupResultsNavChartOverride() {
  const PORTFOLIO_VISIBLE_BARS = 60;

  function buildFixedPriceRangeProvider(minValue, maxValue) {
    if (!Number.isFinite(minValue) || !Number.isFinite(maxValue) || maxValue <= minValue) return null;
    return () => ({
      priceRange: {
        minValue,
        maxValue,
      },
    });
  }

  function deriveExpandedBenchRange(benchWindow) {
    const rows = Array.isArray(benchWindow) ? benchWindow : [];
    const lows = rows
      .map((row) => (Number.isFinite(Number(row?.low)) ? Number(row.low) : Number(row?.close)))
      .filter((value) => Number.isFinite(value));
    const highs = rows
      .map((row) => (Number.isFinite(Number(row?.high)) ? Number(row.high) : Number(row?.close)))
      .filter((value) => Number.isFinite(value));
    if (!lows.length || !highs.length) return null;
    const rawMin = Math.min(...lows);
    const rawMax = Math.max(...highs);
    const rawSpan = Math.max(rawMax - rawMin, Math.max(Math.abs(rawMax), 1) * 0.02, 1e-6);
    const expandedSpan = rawSpan / 0.9;
    const mid = (rawMax + rawMin) / 2;
    return {
      min: mid - (expandedSpan / 2),
      max: mid + (expandedSpan / 2),
    };
  }

  function sliceRowsByVisibleRange(rows, chart) {
    const arr = Array.isArray(rows) ? rows : [];
    if (!arr.length) return [];
    const logicalRange = chart?.timeScale?.()?.getVisibleLogicalRange?.();
    if (!logicalRange || !Number.isFinite(logicalRange.from) || !Number.isFinite(logicalRange.to)) {
      return arr.slice(-Math.min(PORTFOLIO_VISIBLE_BARS, arr.length));
    }
    const from = Math.max(0, Math.floor(logicalRange.from));
    const to = Math.min(arr.length - 1, Math.ceil(logicalRange.to));
    if (to < from) return arr.slice(-Math.min(PORTFOLIO_VISIBLE_BARS, arr.length));
    return arr.slice(from, to + 1);
  }

  function derivePortfolioOverlayConfig(benchOhlc, navLineData, chart) {
    const benchRows = Array.isArray(benchOhlc) ? benchOhlc : [];
    const navRows = Array.isArray(navLineData) ? navLineData : [];
    if (!benchRows.length || !navRows.length) return null;
    const benchWindow = sliceRowsByVisibleRange(benchRows, chart);
    const navWindow = sliceRowsByVisibleRange(navRows, chart);
    const windowBars = Math.max(1, Math.max(benchWindow.length, navWindow.length));
    const leftRange = deriveExpandedBenchRange(benchWindow);
    const benchLast = Number(benchWindow[benchWindow.length - 1]?.close);
    const navLast = Number(navWindow[navWindow.length - 1]?.value);
    if (!leftRange || !Number.isFinite(benchLast) || benchLast <= 0 || !Number.isFinite(navLast) || navLast <= 0) {
      return { leftRange, rightRange: null, scaleFactor: null, windowBars };
    }
    const scaleFactor = benchLast / navLast;
    if (!Number.isFinite(scaleFactor) || scaleFactor <= 0) {
      return { leftRange, rightRange: null, scaleFactor: null, windowBars };
    }
    return {
      leftRange,
      rightRange: {
        min: leftRange.min / scaleFactor,
        max: leftRange.max / scaleFactor,
      },
      scaleFactor,
      windowBars,
    };
  }

  function ensurePortfolioBenchmarkCandles(navState, chart, LWC) {
    if (navState._portfolioBenchmarkKind === 'candlestick-left' && navState.benchmarkSeries) return;
    if (navState.benchmarkSeries && typeof chart.removeSeries === 'function') {
      try { chart.removeSeries(navState.benchmarkSeries); } catch (_) {}
    }
    navState.benchmarkSeries = typeof chart.addCandlestickSeries === 'function'
      ? chart.addCandlestickSeries({
          upColor: '#ef4444',
          downColor: '#22c55e',
          borderDownColor: '#22c55e',
          borderUpColor: '#ef4444',
          wickDownColor: '#22c55e',
          wickUpColor: '#ef4444',
          priceScaleId: 'left',
          priceLineVisible: false,
          lastValueVisible: true,
        })
      : chart.addSeries(LWC.CandlestickSeries, {
          upColor: '#ef4444',
          downColor: '#22c55e',
          borderDownColor: '#22c55e',
          borderUpColor: '#ef4444',
          wickDownColor: '#22c55e',
          wickUpColor: '#ef4444',
          priceScaleId: 'left',
          priceLineVisible: false,
          lastValueVisible: true,
        });
    navState._portfolioBenchmarkKind = 'candlestick-left';
  }

  function applyMarkers(series, markers) {
    const LWC = window.LightweightCharts;
    if (!series || !Array.isArray(markers) || !markers.length) return;
    if (typeof series.setMarkers === 'function') {
      try { series.setMarkers(markers); } catch (_) {}
      return;
    }
    if (typeof LWC?.createSeriesMarkers === 'function') {
      try { LWC.createSeriesMarkers(series, markers); } catch (_) {}
    }
  }

  function renderPortfolioChart(navState, container, chart, benchOhlc, navSeries, showBenchmark, opts) {
    const hasBench = Array.isArray(benchOhlc) && benchOhlc.length > 0;
    const lineData = (Array.isArray(navSeries) ? navSeries : [])
      .map((point) => ({ time: point.date, value: Number(point.value) }))
      .filter((point) => Number.isFinite(point.value));
    const dynamicOverlayConfig = () => derivePortfolioOverlayConfig(benchOhlc, lineData, chart);
    const leftRangeProvider = showBenchmark
      ? (() => {
          const overlay = dynamicOverlayConfig();
          return overlay?.leftRange
            ? { priceRange: { minValue: overlay.leftRange.min, maxValue: overlay.leftRange.max } }
            : null;
        })
      : null;
    const rightRangeProvider = showBenchmark
      ? (() => {
          const overlay = dynamicOverlayConfig();
          return overlay?.rightRange
            ? { priceRange: { minValue: overlay.rightRange.min, maxValue: overlay.rightRange.max } }
            : null;
        })
      : null;

    try {
      chart.applyOptions({
        leftPriceScale: {
          visible: !!showBenchmark && hasBench,
          borderColor: '#334155',
          autoScale: true,
        },
        rightPriceScale: {
          visible: true,
          borderColor: '#334155',
          autoScale: true,
        },
      });
    } catch (_) {}

    if (navState.benchmarkSeries) {
      ensurePortfolioBenchmarkCandles(navState, chart, window.LightweightCharts);
    } else if (showBenchmark && hasBench) {
      ensurePortfolioBenchmarkCandles(navState, chart, window.LightweightCharts);
    }

    if (navState.benchmarkSeries) {
      try {
        navState.benchmarkSeries.applyOptions({
          priceScaleId: 'left',
          priceLineVisible: false,
          lastValueVisible: true,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
          autoscaleInfoProvider: leftRangeProvider || undefined,
        });
      } catch (_) {}
      navState.benchmarkSeries.setData(Array.isArray(benchOhlc) ? benchOhlc : []);
    }

    if (navState.primarySeries) {
      try {
        navState.primarySeries.applyOptions({
          priceScaleId: 'right',
          color: '#f59e0b',
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: true,
          crosshairMarkerVisible: true,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
          autoscaleInfoProvider: rightRangeProvider || undefined,
        });
      } catch (_) {}
      navState.primarySeries.setData(lineData);
      applyMarkers(navState.primarySeries, []);

      if (navState.marketOverlay) {
        navState.marketOverlay.setData(Array.isArray(opts.marketStates) ? opts.marketStates : []);
      }

      if (lineData.length) {
        const lastValue = Number(lineData[lineData.length - 1]?.value);
        navState.symbolBadgeUpdater = () => renderChartValueBadge(
          container,
          navState.primarySeries,
          lastValue,
          `NAV ${num(lastValue, 2)}`,
        );
      }
    }

    const totalBars = Math.max(Array.isArray(benchOhlc) ? benchOhlc.length : 0, lineData.length);
    const visibleBars = Math.max(1, Math.min(PORTFOLIO_VISIBLE_BARS, totalBars || 1));
    const visibleKey = [
      totalBars,
      benchOhlc[0]?.time || '',
      benchOhlc[benchOhlc.length - 1]?.time || '',
      lineData[0]?.time || '',
      lineData[lineData.length - 1]?.time || '',
      showBenchmark ? 'bench' : 'no-bench',
      `portfolio:${visibleBars}`,
    ].join('|');

    if (navState.visibleKey !== visibleKey) {
      if (totalBars > 0 && typeof chart.timeScale()?.setVisibleLogicalRange === 'function') {
        chart.timeScale().setVisibleLogicalRange({
          from: Math.max(0, totalBars - visibleBars) - 0.5,
          to: totalBars - 1 + 2.5,
        });
      } else {
        chart.timeScale().fitContent();
      }
      navState.visibleKey = visibleKey;
    }
  }

  function renderSymbolChart(navState, container, chart, benchOhlc, navSeries, showBenchmark, opts) {
    const LWC = window.LightweightCharts;
    const hasBench = Array.isArray(benchOhlc) && benchOhlc.length > 0;
    const benchFirstClose = Number(benchOhlc[0]?.close) || 1;
    const benchmarkLineData = hasBench
      ? benchOhlc.map((point) => ({ time: point.time, value: Number(point.close) / benchFirstClose }))
      : [];
    const lineData = (Array.isArray(navSeries) ? navSeries : [])
      .map((point) => ({ time: point.date, value: Number(point.value) }))
      .filter((point) => Number.isFinite(point.value));
    const suspensionRanges = Array.isArray(opts.suspensionRanges) ? opts.suspensionRanges : [];
    const hasSuspension = suspensionRanges.length > 0 && !!navState.suspensionSeries;

    try {
      chart.applyOptions({
        leftPriceScale: {
          visible: !!showBenchmark && hasBench,
          borderColor: '#334155',
          autoScale: true,
        },
        rightPriceScale: {
          visible: true,
          borderColor: '#334155',
          autoScale: true,
        },
      });
    } catch (_) {}

    if (navState.benchmarkSeries) {
      try {
        navState.benchmarkSeries.applyOptions({
          priceScaleId: 'left',
          color: '#58a6ff',
          lineWidth: 2,
          crosshairMarkerVisible: false,
          priceLineVisible: false,
          lastValueVisible: false,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
        });
      } catch (_) {}
      navState.benchmarkSeries.setData(benchmarkLineData);
    }

    if (navState.primarySeries) {
      try {
        navState.primarySeries.applyOptions({
          priceScaleId: 'right',
          color: '#f59e0b',
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: !hasSuspension,
          crosshairMarkerVisible: !hasSuspension,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
        });
        navState.suspensionSeries?.applyOptions({
          priceScaleId: 'right',
          color: '#999',
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
        });
      } catch (_) {}

      if (hasSuspension) {
        const suspSet = new Set();
        for (const range of suspensionRanges) {
          for (const point of lineData) {
            if (point.time >= range.start && point.time <= range.end) suspSet.add(point.time);
          }
        }
        const normalData = [];
        const suspensionData = [];
        for (let i = 0; i < lineData.length; i += 1) {
          const point = lineData[i];
          const isSusp = suspSet.has(point.time);
          const prevSusp = i > 0 && suspSet.has(lineData[i - 1].time);
          const nextSusp = i < lineData.length - 1 && suspSet.has(lineData[i + 1].time);
          if (isSusp) {
            suspensionData.push(point);
            if (!prevSusp || !nextSusp) normalData.push(point);
          } else {
            normalData.push(point);
            if (prevSusp || nextSusp) suspensionData.push(point);
          }
        }
        const dedup = (rows) => {
          const byTime = new Map();
          for (const point of rows) byTime.set(point.time, point);
          return Array.from(byTime.values()).sort((left, right) => (left.time < right.time ? -1 : 1));
        };
        navState.suspensionSeries.setData(dedup(suspensionData));
        navState.primarySeries.setData(dedup(normalData));
      } else {
        navState.primarySeries.setData(lineData);
      }

      applyMarkers(navState.primarySeries, Array.isArray(opts.markers) ? opts.markers : []);
      if (navState.marketOverlay) {
        navState.marketOverlay.setData([]);
      }

      if (lineData.length) {
        const lastValue = Number(lineData[lineData.length - 1]?.value);
        const lastClose = Number(opts?.symbolLastClose);
        const label = Number.isFinite(lastClose)
          ? `涓偂鏀剁洏浠?${num(lastClose, 2)}`
          : `涓偂鍑€鍊?${num(lastValue, 2)}x`;
        navState.symbolBadgeUpdater = () => renderChartValueBadge(container, navState.primarySeries, lastValue, label);
      }
    }

    const totalBars = Math.max(benchmarkLineData.length, lineData.length);
    const maxVisibleBars = Math.floor((container.clientWidth || 600) / 6);
    const visibleKey = [
      totalBars,
      benchmarkLineData[0]?.time || '',
      benchmarkLineData[benchmarkLineData.length - 1]?.time || '',
      lineData[0]?.time || '',
      lineData[lineData.length - 1]?.time || '',
      showBenchmark ? 'bench' : 'no-bench',
      'symbol:auto',
    ].join('|');
    if (navState.visibleKey !== visibleKey) {
      if (totalBars > maxVisibleBars) chart.timeScale().scrollToPosition(5, false);
      else chart.timeScale().fitContent();
      navState.visibleKey = visibleKey;
    }
  }

  const renderNavChartLWOverride = function renderNavChartLWOverride(containerId, benchOhlc, navSeries, showBenchmark, opts = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;
    clearChartValueBadge(container);

    const hasNav = Array.isArray(navSeries) && navSeries.length > 0;
    const hasBench = Array.isArray(benchOhlc) && benchOhlc.length > 0;
    const mode = String(opts.mode || 'portfolio');
    const isPortfolioMode = mode === 'portfolio';
    const hasSuspension = mode === 'symbol' && Array.isArray(opts.suspensionRanges) && opts.suspensionRanges.length > 0;

    if (!hasNav && !hasBench) {
      destroyNavChartState();
      container.innerHTML = '<div class="wb-empty"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg><span>杩愯瀹為獙鍚庯紝杩欓噷鏄剧ず鍑€鍊间笌鍙傝€冩寚鏁拌蛋鍔裤€?/span></div>';
      return;
    }

    const LWC = window.LightweightCharts;
    if (!LWC) {
      destroyNavChartState();
      container.innerHTML = '<div class="wb-empty"><span>lightweight-charts 鍔犺浇澶辫触</span></div>';
      return;
    }

    const shape = {
      key: [
        mode,
        hasNav ? 'nav' : 'no-nav',
        showBenchmark && hasBench ? 'bench-line-left' : 'bench-none',
        hasSuspension ? 'susp' : 'plain',
      ].join('|'),
      mode,
      hasNav,
      hasSuspension,
      benchmarkKind: showBenchmark && hasBench ? 'line-left' : 'none',
    };

    let navState = _lwNavState;
    if (!navState || navState.container !== container) {
      destroyNavChartState();
      navState = createNavChartState(container, LWC);
    }
    if (!navState) return;
    if (navState.shapeKey !== shape.key) {
      navState = resetNavChartSeries(navState, LWC, shape);
    }
    if (!navState?.chart) return;

    const chart = navState.chart;
    navState.showLeftBenchmarkScale = !!showBenchmark && hasBench;
    navState.symbolBadgeUpdater = null;

    if (isPortfolioMode) {
      renderPortfolioChart(navState, container, chart, benchOhlc, navSeries, showBenchmark, opts);
    } else {
      renderSymbolChart(navState, container, chart, benchOhlc, navSeries, showBenchmark, opts);
    }

    if (typeof navState.symbolBadgeUpdater === 'function') {
      requestAnimationFrame(navState.symbolBadgeUpdater);
    }
  };

  window.renderNavChartLW = renderNavChartLWOverride;
  try { renderNavChartLW = renderNavChartLWOverride; } catch (_) {}
})();

(function setupPortfolioDualChartOverride() {
  const PORTFOLIO_VISIBLE_BARS = 60;
  let dualState = null;

  function destroyChart(chart) {
    if (!chart) return;
    try { chart.remove(); } catch (_) {}
  }

  function disconnectObserver(observer) {
    if (!observer) return;
    try { observer.disconnect(); } catch (_) {}
  }

  function unsubscribeLogical(chart, handler) {
    if (!chart || !handler) return;
    const timeScale = typeof chart.timeScale === 'function' ? chart.timeScale() : null;
    if (!timeScale || typeof timeScale.unsubscribeVisibleLogicalRangeChange !== 'function') return;
    try { timeScale.unsubscribeVisibleLogicalRangeChange(handler); } catch (_) {}
  }

  function logicalRangeEqual(left, right) {
    if (!left || !right) return false;
    const fromEqual = Math.abs(Number(left.from) - Number(right.from)) < 1e-3;
    const toEqual = Math.abs(Number(left.to) - Number(right.to)) < 1e-3;
    return fromEqual && toEqual;
  }

  function destroyPortfolioDualChartLW() {
    if (!dualState) return;
    unsubscribeLogical(dualState.topChart, dualState.topLogicalHandler);
    unsubscribeLogical(dualState.bottomChart, dualState.bottomLogicalHandler);
    disconnectObserver(dualState.topResizeObserver);
    disconnectObserver(dualState.bottomResizeObserver);
    destroyChart(dualState.topChart);
    destroyChart(dualState.bottomChart);
    if (dualState.topContainer) clearChartValueBadge(dualState.topContainer);
    if (dualState.bottomContainer) clearChartValueBadge(dualState.bottomContainer);
    dualState = null;
  }

  function createBaseChart(
    container,
    LWC,
    { leftScaleVisible = false, rightScaleVisible = true, showTimeScale = true, interactive = true } = {},
  ) {
    container.innerHTML = '';
    return LWC.createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight || 260,
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
      leftPriceScale: { visible: leftScaleVisible, borderColor: '#334155', autoScale: true },
      rightPriceScale: { visible: rightScaleVisible, borderColor: '#334155', autoScale: true },
      handleScale: {
        mouseWheel: interactive,
        pinch: interactive,
        axisPressedMouseMove: {
          time: interactive,
          price: interactive,
        },
        axisDoubleClickReset: {
          time: interactive,
          price: interactive,
        },
      },
      handleScroll: {
        mouseWheel: interactive,
        pressedMouseMove: interactive,
        horzTouchDrag: interactive,
        vertTouchDrag: false,
      },
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
    });
  }

  function addLineSeriesCompat(chart, LWC, options) {
    return typeof chart.addLineSeries === 'function'
      ? chart.addLineSeries(options)
      : chart.addSeries(LWC.LineSeries, options);
  }

  function addCandlestickSeriesCompat(chart, LWC, options) {
    return typeof chart.addCandlestickSeries === 'function'
      ? chart.addCandlestickSeries(options)
      : chart.addSeries(LWC.CandlestickSeries, options);
  }

  function addHistogramSeriesCompat(chart, LWC, options) {
    return typeof chart.addHistogramSeries === 'function'
      ? chart.addHistogramSeries(options)
      : chart.addSeries(LWC.HistogramSeries, options);
  }

  function buildMarketMaskData(rows) {
    const input = Array.isArray(rows) ? rows : [];
    const colorMap = typeof MARKET_STATE_COLORS === 'object' && MARKET_STATE_COLORS ? MARKET_STATE_COLORS : {};
    return input
      .map((row) => {
        const time = String(row?.time || '').trim();
        const mode = String(row?.mode || '').trim().toUpperCase();
        const color = colorMap[mode] || null;
        if (!time || !color) return null;
        return { time, value: 1, color };
      })
      .filter(Boolean);
  }

  function ensureMarketMaskLayer(container, key) {
    if (!container) return null;
    if (!container.style.position) container.style.position = 'relative';
    let layer = container.querySelector(`.wb-market-mask-layer[data-mask-key="${key}"]`);
    if (!layer) {
      layer = document.createElement('div');
      layer.className = 'wb-market-mask-layer';
      layer.dataset.maskKey = key;
      layer.style.position = 'absolute';
      layer.style.left = '0';
      layer.style.right = '0';
      layer.style.top = '0';
      layer.style.bottom = '0';
      layer.style.pointerEvents = 'none';
      layer.style.zIndex = '1';
      layer.style.overflow = 'hidden';
      container.appendChild(layer);
    }
    return layer;
  }

  function clearMarketMaskLayer(container, key) {
    const layer = container?.querySelector?.(`.wb-market-mask-layer[data-mask-key="${key}"]`);
    if (layer) layer.innerHTML = '';
  }

  function estimateBarWidth(chart, rows) {
    const timeScale = chart?.timeScale?.();
    if (!timeScale || typeof timeScale.timeToCoordinate !== 'function') return 6;
    const coords = (Array.isArray(rows) ? rows : [])
      .map((row) => timeScale.timeToCoordinate(row.time))
      .filter((value) => Number.isFinite(value));
    if (coords.length < 2) return 6;
    let total = 0;
    let count = 0;
    for (let i = 1; i < coords.length; i += 1) {
      const diff = Math.abs(coords[i] - coords[i - 1]);
      if (diff > 0) {
        total += diff;
        count += 1;
      }
    }
    return count > 0 ? Math.max(2, total / count) : 6;
  }

  function renderMarketMaskLayer(container, chart, rows, key) {
    const layer = ensureMarketMaskLayer(container, key);
    if (!layer) return;
    const input = Array.isArray(rows) ? rows : [];
    const timeScale = chart?.timeScale?.();
    if (!input.length || !timeScale || typeof timeScale.timeToCoordinate !== 'function') {
      layer.innerHTML = '';
      return;
    }
    const barWidth = estimateBarWidth(chart, input);
    const bands = [];
    let i = 0;
    while (i < input.length) {
      const current = input[i];
      const mode = String(current?.mode || '').trim().toUpperCase();
      const color = (typeof MARKET_STATE_COLORS === 'object' && MARKET_STATE_COLORS ? MARKET_STATE_COLORS[mode] : null) || null;
      let j = i + 1;
      while (j < input.length && String(input[j]?.mode || '').trim().toUpperCase() === mode) j += 1;
      if (color) {
        const x1 = timeScale.timeToCoordinate(current.time);
        const x2 = timeScale.timeToCoordinate(input[j - 1].time);
        if (Number.isFinite(x1) && Number.isFinite(x2)) {
          const left = Math.round(Math.min(x1, x2) - (barWidth / 2));
          const width = Math.max(1, Math.round(Math.abs(x2 - x1) + barWidth));
          bands.push({ left, width, color });
        }
      }
      i = j;
    }
    layer.innerHTML = bands.map((band) => (
      `<div style="position:absolute;top:0;bottom:0;left:${band.left}px;width:${band.width}px;background:${band.color};"></div>`
    )).join('');
  }

  function renderDualMarketMasks(state) {
    if (!state) return;
    renderMarketMaskLayer(state.topContainer, state.topChart, state.marketStates, 'top');
    if (state.bottomContainer && state.bottomChart) {
      renderMarketMaskLayer(state.bottomContainer, state.bottomChart, state.marketStates, 'bottom');
    } else if (state.bottomContainer) {
      clearMarketMaskLayer(state.bottomContainer, 'bottom');
    }
  }

  function ensureDualState(topContainer, bottomContainer, LWC) {
    const needsReset = !dualState
      || dualState.topContainer !== topContainer
      || dualState.bottomContainer !== bottomContainer;
    if (!needsReset) return dualState;

    destroyPortfolioDualChartLW();

    const topChart = createBaseChart(topContainer, LWC, {
      leftScaleVisible: false,
      rightScaleVisible: true,
      showTimeScale: false,
      interactive: true,
    });

    const topMaskSeries = addHistogramSeriesCompat(topChart, LWC, {
      priceScaleId: 'overlay-mask-top',
      base: 0,
      color: 'rgba(0,0,0,0)',
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      autoscaleInfoProvider: () => ({
        priceRange: { minValue: 0, maxValue: 1 },
      }),
    });
    try {
      topChart.priceScale('overlay-mask-top').applyOptions({
        visible: false,
        autoScale: false,
        scaleMargins: { top: 0, bottom: 0 },
      });
    } catch (_) {}

    const topNavSeries = addLineSeriesCompat(topChart, LWC, {
      priceScaleId: 'right',
      color: '#f59e0b',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    });

    const topBenchmarkSeries = addLineSeriesCompat(topChart, LWC, {
      priceScaleId: 'right',
      color: '#60a5fa',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: false,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    });

    let bottomChart = null;
    let bottomBenchmarkSeries = null;
    let bottomVolumeSeries = null;
    let bottomMaskSeries = null;
    if (bottomContainer) {
      bottomChart = createBaseChart(bottomContainer, LWC, {
        leftScaleVisible: true,
        rightScaleVisible: false,
        showTimeScale: true,
        interactive: false,
      });
      bottomMaskSeries = addHistogramSeriesCompat(bottomChart, LWC, {
        priceScaleId: 'overlay-mask-bottom',
        base: 0,
        color: 'rgba(0,0,0,0)',
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        autoscaleInfoProvider: () => ({
          priceRange: { minValue: 0, maxValue: 1 },
        }),
      });
      try {
        bottomChart.priceScale('overlay-mask-bottom').applyOptions({
          visible: false,
          autoScale: false,
          scaleMargins: { top: 0, bottom: 0 },
        });
      } catch (_) {}
      bottomVolumeSeries = addHistogramSeriesCompat(bottomChart, LWC, {
        priceScaleId: 'volume-overlay',
        color: 'rgba(148, 163, 184, 0.35)',
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      try {
        bottomChart.priceScale('volume-overlay').applyOptions({
          visible: false,
          autoScale: true,
          scaleMargins: { top: 0.74, bottom: 0.05 },
        });
      } catch (_) {}
      bottomBenchmarkSeries = addCandlestickSeriesCompat(bottomChart, LWC, {
        upColor: '#ef4444',
        downColor: '#22c55e',
        borderDownColor: '#22c55e',
        borderUpColor: '#ef4444',
        wickDownColor: '#22c55e',
        wickUpColor: '#ef4444',
        priceScaleId: 'left',
        priceLineVisible: false,
        lastValueVisible: true,
      });
    }

    dualState = {
      topContainer,
      bottomContainer,
      topChart,
      bottomChart,
      topMaskSeries,
      topNavSeries,
      topBenchmarkSeries,
      bottomBenchmarkSeries,
      bottomVolumeSeries,
      bottomMaskSeries,
      topResizeObserver: null,
      bottomResizeObserver: null,
      topLogicalHandler: null,
      syncLock: false,
      bottomBenchRows: [],
      marketStates: [],
      visibleKey: '',
      initialized: false,
    };

    dualState.topResizeObserver = null;
    dualState.bottomResizeObserver = null;

    const syncFromTop = (range) => {
      if (!dualState || dualState.syncLock || !dualState.bottomChart || !range) return;
      const bottomRange = dualState.bottomChart.timeScale()?.getVisibleLogicalRange?.();
      if (logicalRangeEqual(range, bottomRange)) {
        renderDualMarketMasks(dualState);
        return;
      }
      dualState.syncLock = true;
      try {
        dualState.bottomChart.timeScale().setVisibleLogicalRange(range);
      } catch (_) {
      } finally {
        dualState.syncLock = false;
      }
      renderDualMarketMasks(dualState);
    };
    dualState.topLogicalHandler = syncFromTop;

    if (typeof dualState.topChart.timeScale()?.subscribeVisibleLogicalRangeChange === 'function') {
      dualState.topChart.timeScale().subscribeVisibleLogicalRangeChange(syncFromTop);
    }

    return dualState;
  }

  function normalizeBenchmarkLine(benchOhlc) {
    const rows = Array.isArray(benchOhlc) ? benchOhlc : [];
    if (!rows.length) return [];
    const firstClose = Number(rows[0]?.close);
    if (!Number.isFinite(firstClose) || firstClose <= 0) return [];
    return rows
      .map((row) => {
        const close = Number(row?.close);
        if (!Number.isFinite(close)) return null;
        return { time: row.time, value: close / firstClose };
      })
      .filter(Boolean);
  }

  function sliceVisibleRows(rows, chart) {
    const arr = Array.isArray(rows) ? rows : [];
    if (!arr.length || !chart) return [];
    const logicalRange = chart.timeScale()?.getVisibleLogicalRange?.();
    if (!logicalRange || !Number.isFinite(logicalRange.from) || !Number.isFinite(logicalRange.to)) {
      return arr.slice(-Math.min(PORTFOLIO_VISIBLE_BARS, arr.length));
    }
    const from = Math.max(0, Math.floor(logicalRange.from));
    const to = Math.min(arr.length - 1, Math.ceil(logicalRange.to));
    return to >= from ? arr.slice(from, to + 1) : arr.slice(-Math.min(PORTFOLIO_VISIBLE_BARS, arr.length));
  }

  function buildExpandedPriceRange(rows) {
    const arr = Array.isArray(rows) ? rows : [];
    if (!arr.length) return null;
    const lows = arr.map((row) => Number.isFinite(Number(row?.low)) ? Number(row.low) : Number(row?.close)).filter(Number.isFinite);
    const highs = arr.map((row) => Number.isFinite(Number(row?.high)) ? Number(row.high) : Number(row?.close)).filter(Number.isFinite);
    if (!lows.length || !highs.length) return null;
    const min = Math.min(...lows);
    const max = Math.max(...highs);
    const span = Math.max(max - min, Math.max(Math.abs(max), 1) * 0.02, 1e-6);
    const expanded = span / 0.9;
    const mid = (min + max) / 2;
    return {
      min: mid - expanded / 2,
      max: mid + expanded / 2,
    };
  }

  function setInitialVisibleRange(state, totalBars) {
    if (!state?.topChart || totalBars <= 0) return;
    const visibleBars = Math.max(1, Math.min(PORTFOLIO_VISIBLE_BARS, totalBars));
    const range = {
      from: Math.max(0, totalBars - visibleBars) - 0.5,
      to: totalBars - 1 + 2.5,
    };
    try { state.topChart.timeScale().setVisibleLogicalRange(range); } catch (_) {}
  }

  function updateTopBadge(state, navLineData, benchmarkLineData) {
    if (!state?.topContainer || !Array.isArray(navLineData) || !navLineData.length) return;
    const navLast = Number(navLineData[navLineData.length - 1]?.value);
    const benchLast = Number(benchmarkLineData[benchmarkLineData.length - 1]?.value);
    const label = Number.isFinite(benchLast)
      ? `NAV ${num(navLast, 2)} | 涓婅瘉 ${num(benchLast, 2)}x`
      : `NAV ${num(navLast, 2)}`;
    renderChartValueBadge(state.topContainer, state.topNavSeries, navLast, label);
  }

  function updateBottomBadge(state, benchOhlc, benchmarkSymbol) {
    if (!state?.bottomContainer || !state.bottomBenchmarkSeries || !Array.isArray(benchOhlc) || !benchOhlc.length) return;
    const lastClose = Number(benchOhlc[benchOhlc.length - 1]?.close);
    if (!Number.isFinite(lastClose)) return;
    renderChartValueBadge(state.bottomContainer, state.bottomBenchmarkSeries, lastClose, `${benchmarkSymbol || '涓婅瘉'} ${num(lastClose, 2)}`);
  }

  function renderPortfolioDualChartLW(topContainerId, bottomContainerId, benchOhlc, navSeries, opts = {}) {
    const topContainer = document.getElementById(topContainerId);
    const bottomContainer = bottomContainerId ? document.getElementById(bottomContainerId) : null;
    if (!topContainer) return;
    clearChartValueBadge(topContainer);
    if (bottomContainer) clearChartValueBadge(bottomContainer);

    const LWC = window.LightweightCharts;
    if (!LWC) {
      destroyPortfolioDualChartLW();
      topContainer.innerHTML = '<div class="wb-empty"><span>lightweight-charts 鍔犺浇澶辫触</span></div>';
      if (bottomContainer) bottomContainer.innerHTML = '<div class="wb-empty"><span>lightweight-charts 鍔犺浇澶辫触</span></div>';
      return;
    }

    const hasBench = Array.isArray(benchOhlc) && benchOhlc.length > 0;
    const showBenchmark = !!opts.showBenchmark && hasBench;
    const state = ensureDualState(topContainer, showBenchmark ? bottomContainer : null, LWC);
    if (!state) return;

    const navLineData = (Array.isArray(navSeries) ? navSeries : [])
      .map((point) => ({ time: point.date, value: Number(point.value) }))
      .filter((point) => Number.isFinite(point.value));
    const benchmarkLineData = showBenchmark ? normalizeBenchmarkLine(benchOhlc) : [];
    const benchmarkVolumeData = showBenchmark
      ? (Array.isArray(benchOhlc) ? benchOhlc : [])
        .map((row) => {
          const volume = Number(row?.volume ?? row?.amount);
          if (!Number.isFinite(volume) || volume <= 0) return null;
          return {
            time: String(row?.time || '').trim(),
            value: volume,
            color: Number(row?.close) >= Number(row?.open) ? 'rgba(239, 68, 68, 0.42)' : 'rgba(34, 197, 94, 0.42)',
          };
        })
        .filter((row) => row && row.time)
      : [];
    const marketStates = Array.isArray(opts.marketStates) ? opts.marketStates : [];
    const marketMaskData = buildMarketMaskData(marketStates);
    state.marketStates = marketStates;

    state.topMaskSeries?.setData(marketMaskData);
    state.topNavSeries.setData(navLineData);
    state.topBenchmarkSeries.setData(benchmarkLineData);
    applyMarkers(state.topNavSeries, Array.isArray(opts.markers) ? opts.markers : []);
    try {
      state.topBenchmarkSeries.applyOptions({
        visible: showBenchmark,
        lastValueVisible: showBenchmark,
      });
      state.topChart.applyOptions({
        rightPriceScale: { visible: true, borderColor: '#334155', autoScale: true },
      });
    } catch (_) {}

    if (showBenchmark && state.bottomChart && state.bottomBenchmarkSeries) {
      state.bottomBenchRows = Array.isArray(benchOhlc) ? benchOhlc : [];
      state.bottomMaskSeries?.setData(marketMaskData);
      state.bottomVolumeSeries?.setData(benchmarkVolumeData);
      try {
        state.bottomBenchmarkSeries.applyOptions({
          priceScaleId: 'left',
          priceLineVisible: false,
          lastValueVisible: true,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
          autoscaleInfoProvider: () => {
            const visibleRows = sliceVisibleRows(state.bottomBenchRows, state.bottomChart);
            const range = buildExpandedPriceRange(visibleRows);
            return range ? { priceRange: { minValue: range.min, maxValue: range.max } } : null;
          },
        });
      } catch (_) {}
      state.bottomBenchmarkSeries.setData(benchOhlc);
      updateBottomBadge(state, benchOhlc, opts.benchmarkSymbol);
    } else if (state.bottomContainer) {
      state.bottomMaskSeries?.setData([]);
      state.bottomVolumeSeries?.setData([]);
      clearChartValueBadge(state.bottomContainer);
    }

    updateTopBadge(state, navLineData, benchmarkLineData);

    const totalBars = Math.max(navLineData.length, showBenchmark ? benchOhlc.length : 0);
    const visibleKey = [
      totalBars,
      navLineData[0]?.time || '',
      navLineData[navLineData.length - 1]?.time || '',
      showBenchmark ? (benchOhlc[0]?.time || '') : '',
      showBenchmark ? (benchOhlc[benchOhlc.length - 1]?.time || '') : '',
      showBenchmark ? 'with-bench' : 'nav-only',
    ].join('|');

    if (state.visibleKey !== visibleKey) {
      if (!state.initialized) {
        setInitialVisibleRange(state, totalBars);
        state.initialized = true;
      }
      state.visibleKey = visibleKey;
    }
    renderDualMarketMasks(state);
  }

  window.renderPortfolioDualChartLW = renderPortfolioDualChartLW;
  window.destroyPortfolioDualChartLW = destroyPortfolioDualChartLW;
})();

