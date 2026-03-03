/* ── charts.js ── Chart rendering (SVG fallback + LightweightCharts) ── */
/* Globals used: state, byId, esc, num, setHtmlById (from backtest_v2.js) */

function filterSeriesByRange(points, range) {
  const arr = Array.isArray(points) ? points : [];
  if (!arr.length || !range || range === 'ALL' || range === 'D') return arr;
  const n = range === '1M' ? 22 : (range === '3M' ? 66 : (range === '1Y' ? 252 : arr.length));
  return arr.slice(Math.max(0, arr.length - n));
}

// 将日线 OHLC 聚合为周线/月线/年线
function aggregateOhlc(dailyOhlc, period) {
  if (!dailyOhlc?.length || !period || period === 'D') return dailyOhlc;
  const buckets = new Map();
  for (const bar of dailyOhlc) {
    const d = bar.time; // 'YYYY-MM-DD'
    let key;
    if (period === 'W') {
      // 按周聚合：算出周一的日期作为 key
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
      b.close = bar.close; // 最后一天的 close
    }
  }
  return [...buckets.values()];
}

// 将日线 NAV 聚合为周线/月线/年线（取每个周期最后一个值）
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
    buckets.set(key, { date: key, value: pt.value }); // 覆盖为最后一天的值
  }
  return [...buckets.values()];
}

// 回撤序列周期聚合：取周期内最小值（最大回撤深度），而非末日值
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

// ── MarketStateOverlay — LWC v4 Series Primitive for market state color bands ──
// A 股惯例: 红=涨/牛, 绿=跌/熊
const MARKET_STATE_COLORS = {
  TREND_MAIN:  'rgba(220, 38, 38, 0.08)',
  TREND_LIGHT: 'rgba(220, 38, 38, 0.05)',
  BEAR:        'rgba(22, 163, 74, 0.08)',
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
  constructor() { this._data = []; this._chart = null; this._paneView = new MarketStatePaneView(this); }
  setData(data) { this._data = data || []; }
  attached(p) { this._chart = p.chart || (p.series?.chart ? p.series.chart() : null); p.requestUpdate(); }
  detached() { this._chart = null; }
  paneViews() { return [this._paneView]; }
}

// lightweight-charts 实例管理
let _lwChartNav = null;  // 收益图
let _lwChartDd = null;   // 回撤图
let _syncLock = false;   // 防止时间轴同步递归

function renderLoadingSkeleton() {
  setHtmlById('wbGroupLoadStatus', '<span class="wb-mini">加载组产物中...</span>');
  // 清理 lightweight-charts 实例后再替换 innerHTML
  if (_lwChartNav) { _lwChartNav.remove(); _lwChartNav = null; }
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

function renderNavChartLW(containerId, benchOhlc, navSeries, showBenchmark, opts = {}) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const hasNav = Array.isArray(navSeries) && navSeries.length > 0;
  const hasBench = Array.isArray(benchOhlc) && benchOhlc.length > 0;
  const mode = String(opts.mode || 'portfolio');
  const markers = Array.isArray(opts.markers) ? opts.markers : [];


  // 无任何数据时显示空状态
  if (!hasNav && !hasBench) {
    if (_lwChartNav) { _lwChartNav.remove(); _lwChartNav = null; }
    container.innerHTML = '<div class="wb-empty"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg><span>运行实验后显示净值曲线</span></div>';
    return;
  }

  // 清理旧实例
  if (_lwChartNav) { _lwChartNav.remove(); _lwChartNav = null; }
  container.innerHTML = '';

  const LWC = window.LightweightCharts;
  if (!LWC) {
    container.innerHTML = '<div class="wb-empty"><span>lightweight-charts 加载失败</span></div>';
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
    rightPriceScale: { borderColor: '#334155' },
    timeScale: {
      borderColor: '#334155',
      timeVisible: false,
      barSpacing: 6,       // 默认蜡烛间距（像素），参考东方财富/同花顺
      minBarSpacing: 2,    // 缩放下限
      rightOffset: 5,      // 右侧留白
    },
  });
  _lwChartNav = chart;

  // Benchmark 蜡烛图（兼容 v4.0+ 和 v4.2+ API）
  if (showBenchmark && hasBench) {
    const candleSeries = typeof chart.addCandlestickSeries === 'function'
      ? chart.addCandlestickSeries({
          upColor: '#26a69a', downColor: '#ef5350',
          borderDownColor: '#ef5350', borderUpColor: '#26a69a',
          wickDownColor: '#ef5350', wickUpColor: '#26a69a',
        })
      : chart.addSeries(LWC.CandlestickSeries, {
          upColor: '#26a69a', downColor: '#ef5350',
          borderDownColor: '#ef5350', borderUpColor: '#26a69a',
          wickDownColor: '#ef5350', wickUpColor: '#26a69a',
        });
    candleSeries.setData(benchOhlc);
  }

  // Strategy NAV 折线（归一化后与 Benchmark 同量级）
  if (hasNav) {
    // NAV 可能是原始组合价值（如 100000），需要归一化为从 1.0 开始
    const firstVal = navSeries[0]?.value || 1;
    const lineData = navSeries.map((p) => ({ time: p.date, value: p.value / firstVal }));

    // 停牌区间分段：个股模式下用灰色停牌段 + 橙色正常段
    const suspRanges = Array.isArray(opts.suspensionRanges) ? opts.suspensionRanges : [];
    const hasSuspension = mode === 'symbol' && suspRanges.length > 0;

    const _addLine = (color) => typeof chart.addLineSeries === 'function'
      ? chart.addLineSeries({ color, lineWidth: 2, crosshairMarkerVisible: !hasSuspension, priceLineVisible: false, lastValueVisible: !hasSuspension })
      : chart.addSeries(LWC.LineSeries, { color, lineWidth: 2, crosshairMarkerVisible: !hasSuspension, priceLineVisible: false, lastValueVisible: !hasSuspension });

    let primaryLine;
    if (hasSuspension) {
      // 构建停牌日期集合
      const suspSet = new Set();
      for (const r of suspRanges) {
        for (const p of lineData) {
          if (p.time >= r.start && p.time <= r.end) suspSet.add(p.time);
        }
      }
      // 正常段（橙色）：停牌点设为 NaN 断开，但保留边界点使线段连接
      const normalData = [];
      const suspData = [];
      for (let i = 0; i < lineData.length; i++) {
        const p = lineData[i];
        const isSusp = suspSet.has(p.time);
        const prevSusp = i > 0 && suspSet.has(lineData[i - 1].time);
        const nextSusp = i < lineData.length - 1 && suspSet.has(lineData[i + 1].time);
        if (isSusp) {
          suspData.push(p);
          // 停牌段首尾加到正常段做连接点
          if (!prevSusp || !nextSusp) normalData.push(p);
        } else {
          normalData.push(p);
          // 正常段首尾加到停牌段做连接点
          if (nextSusp) suspData.push(p);
          if (prevSusp) suspData.push(p);
        }
      }
      // 去重并排序
      const dedup = (arr) => {
        const m = new Map();
        for (const p of arr) m.set(p.time, p);
        return Array.from(m.values()).sort((a, b) => (a.time < b.time ? -1 : 1));
      };
      const suspLine = _addLine('#999');
      suspLine.setData(dedup(suspData));
      primaryLine = _addLine('#f59e0b');
      primaryLine.setData(dedup(normalData));
    } else {
      primaryLine = _addLine(mode === 'symbol' ? '#f59e0b' : '#58a6ff');
      primaryLine.setData(lineData);
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
    // MarketStateOverlay — 挂载到主折线系列
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
  }

  // 数据量大时只显示最近一段，保证蜡烛清晰可见；数据少时全部显示
  const totalBars = Math.max(benchOhlc?.length || 0, navSeries?.length || 0);
  const chartWidth = container.clientWidth || 600;
  const maxVisibleBars = Math.floor(chartWidth / 6); // 6px 间距
  if (totalBars > maxVisibleBars) {
    chart.timeScale().scrollToPosition(5, false);
  } else {
    chart.timeScale().fitContent();
  }

  // 响应容器大小变化
  const ro = new ResizeObserver(() => {
    if (_lwChartNav === chart) {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight || 420 });
    }
  });
  ro.observe(container);
}

// 回撤图 — LightweightCharts AreaSeries 渲染
function renderDdChartLW(containerId, ddSeries, benchDdSeries, showBenchmark, opts = {}) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const hasDd = Array.isArray(ddSeries) && ddSeries.length > 0;
  const hasBenchDd = Array.isArray(benchDdSeries) && benchDdSeries.length > 0;

  if (!hasDd && !hasBenchDd) {
    if (_lwChartDd) { _lwChartDd.remove(); _lwChartDd = null; }
    container.innerHTML = '<div class="wb-empty"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg><span>回撤曲线</span></div>';
    return;
  }

  if (_lwChartDd) { _lwChartDd.remove(); _lwChartDd = null; }
  container.innerHTML = '';

  const LWC = window.LightweightCharts;
  if (!LWC) {
    container.innerHTML = '<div class="wb-empty"><span>lightweight-charts 加载失败</span></div>';
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

  // 策略回撤 — BaselineSeries 以 0 为基线，向下填充红色
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
    // MarketStateOverlay — 挂载到回撤 BaselineSeries
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

  // 基准回撤 — 橙色线
  if (showBenchmark && hasBenchDd) {
    const lineOpts = { color: '#f97316', lineWidth: 1, priceLineVisible: false, crosshairMarkerVisible: false };
    const benchLine = typeof chart.addLineSeries === 'function'
      ? chart.addLineSeries(lineOpts)
      : chart.addSeries(LWC.LineSeries, lineOpts);
    benchLine.setData(benchDdSeries.map((p) => ({ time: p.date, value: p.value })));
  }

  chart.timeScale().fitContent();

  // 响应容器大小变化
  const ro = new ResizeObserver(() => {
    if (_lwChartDd === chart) {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight || 160 });
    }
  });
  ro.observe(container);

  // --- 时间轴同步 + crosshair 联动 ---
  setupChartSync();
}

// 双图时间轴同步 + crosshair 联动
function setupChartSync() {
  if (!_lwChartNav || !_lwChartDd) return;

  // 时间轴缩放/平移同步
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

  // crosshair 联动
  _lwChartNav.subscribeCrosshairMove((param) => {
    if (!param || !param.time) {
      _lwChartDd.clearCrosshairPosition();
      return;
    }
    // 用 setCrosshairPosition 同步到回撤图（需要 price + time）
    // 传 NaN 作为 price 让 LWC 自动定位到数据点
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
