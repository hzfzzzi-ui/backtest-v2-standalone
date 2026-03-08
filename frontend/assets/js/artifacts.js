/* ── artifacts.js ── Artifact loading, normalization, and rendering ── */
/* Globals used: state, byId, esc, num, pct, fmtInt, fmtMoney, setTextById, setHtmlById,
   reasonZh,
   apiRequestJson, setStatusItems, addLog,
   renderLoadingSkeleton, renderNavChartLW, renderDdChartLW,
   aggregateOhlc, aggregateNav, aggregateDrawdown,
   applyConfigToUI, refreshConfigPanels,
   populateExitStats, populateConstraintStats (from other modules) */

async function readArtifactWithStatus(resultsDir, relPath, keyName) {
  if (!relPath) return { ok: false, key: keyName, missing: true, error: `${keyName} 缺失` };
  let reqResultsDir = resultsDir;
  let reqRelPath = relPath;
  const relText = String(relPath);
  const isAbsPosix = relText.startsWith('/');
  const isAbsWin = /^[A-Za-z]:[\\/]/.test(relText);
  if (isAbsPosix || isAbsWin) {
    const normalized = relText.replaceAll('\\', '/');
    const idx = normalized.lastIndexOf('/');
    if (idx > 0) {
      reqResultsDir = normalized.slice(0, idx);
      reqRelPath = normalized.slice(idx + 1);
    }
  }
  try {
    const payload = await apiRequestJson(
      `artifact_read_${keyName}`,
      '/api/backtest_v2/artifacts/read',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ results_dir: reqResultsDir, rel_path: reqRelPath }),
      },
    );
    return { ok: true, key: keyName, relPath: reqRelPath, payload };
  } catch (e) {
    return { ok: false, key: keyName, missing: true, error: String(e?.message || e), relPath: reqRelPath };
  }
}

function normalizeRunMetaCounters(metaObj) {
  const meta = metaObj && typeof metaObj === 'object' ? { ...metaObj } : {};
  const counters = meta.counters && typeof meta.counters === 'object' ? { ...meta.counters } : {};
  meta.counters = counters;
  return meta;
}

async function readArtifactWithFallback(resultsDir, relPath, keyName, fallbacks = []) {
  const primaryRel = relPath || `${keyName}.csv`;
  const first = await readArtifactWithStatus(resultsDir, primaryRel, keyName);
  if (first.ok) return { ...first, usedLegacyFallback: false };
  for (const altRel of (fallbacks || [])) {
    const fb = await readArtifactWithStatus(resultsDir, altRel, keyName);
    if (fb.ok) return { ...fb, usedLegacyFallback: true };
  }
  return first;
}

function normalizeNavRows(rows) {
  const out = [];
  (rows || []).forEach((r) => {
    const date = String(r.date ?? r.datetime ?? r.trade_date ?? '').trim();
    const nav = Number(r.nav ?? r.strategy_nav ?? r.equity ?? r.portfolio_value ?? r.value);
    if (!date || !Number.isFinite(nav) || nav <= 0) return;
    out.push({ date, nav });
  });
  out.sort((a, b) => (a.date < b.date ? -1 : 1));
  return out;
}

function computeDrawdownSeries(navRows) {
  let peak = null;
  const out = [];
  (navRows || []).forEach((r) => {
    const nav = Number(r.nav);
    if (!Number.isFinite(nav) || nav <= 0) return;
    peak = peak == null ? nav : Math.max(peak, nav);
    const dd = peak > 0 ? (nav - peak) / peak : 0;
    out.push({ date: r.date, value: dd });
  });
  return out;
}

function _parseMarketStates(dailyRows) {
  // 从 portfolio_daily.csv 行解析 market_state + trade_mode → [{time, mode}]
  // mode: TREND_MAIN / TREND_LIGHT / BEAR / NO_TRADE_TRANS (transparent)
  const out = [];
  for (const r of dailyRows || []) {
    // market_state 列不存在时 r.market_state 为 undefined，跳过
    if (r.market_state == null || r.market_state === '') continue;
    const date = String(r.date ?? '').trim();
    const ms = String(r.market_state).trim().toUpperCase();
    const tm = String(r.trade_mode ?? '').trim().toUpperCase();
    if (!date || !ms) continue;
    let mode;
    if (tm === 'TREND_MAIN') mode = 'TREND_MAIN';
    else if (tm === 'TREND_LIGHT') mode = 'TREND_LIGHT';
    else if (ms === 'BEAR') mode = 'BEAR';
    else mode = 'NO_TRADE_TRANS'; // transition without signal → transparent
    out.push({ time: date, mode });
  }
  return out;
}

function normalizeSymbolPerformanceRows(rows) {
  const out = [];
  const toBool = (v) => {
    const t = String(v ?? '').trim().toLowerCase();
    if (!t) return false;
    return ['1', 'true', 'yes', 'y'].includes(t);
  };
  (rows || []).forEach((r) => {
    const symbol = String(r.symbol ?? '').trim().toLowerCase();
    if (!symbol) return;
    const returnPct = Number(r.return_pct);
    const maxDrawdown = Number(r.max_drawdown);
    const trades = Number(r.trades);
    out.push({
      symbol,
      return_pct: Number.isFinite(returnPct) ? returnPct : 0,
      max_drawdown: Number.isFinite(maxDrawdown) ? maxDrawdown : 0,
      trades: Number.isFinite(trades) ? trades : 0,
      unrealized_approx_pnl: Number.isFinite(Number(r.unrealized_approx_pnl)) ? Number(r.unrealized_approx_pnl) : 0,
      valuation_fallback_used: toBool(r.valuation_fallback_used),
    });
  });
  return out;
}

function getFilteredSortedSymbolRows() {
  const rows = (state.active_artifacts || {}).symbolPerformanceRows || [];
  const keyword = String(state.symbol_filter || '').trim().toLowerCase();
  const filtered = keyword
    ? rows.filter((r) => {
      const symbol = String(r.symbol || '').toLowerCase();
      const name = String(stockZh(r.symbol) || '').toLowerCase();
      return symbol.includes(keyword) || name.includes(keyword);
    })
    : rows.slice();
  const sorter = String(state.symbol_sort || 'return_desc');
  if (sorter === 'drawdown_asc') {
    filtered.sort((a, b) => Number(a.max_drawdown || 0) - Number(b.max_drawdown || 0));
  } else if (sorter === 'trades_desc') {
    filtered.sort((a, b) => Number(b.trades || 0) - Number(a.trades || 0));
  } else {
    filtered.sort((a, b) => Number(b.return_pct || 0) - Number(a.return_pct || 0));
  }
  return filtered;
}

function symbolTradeMarkers(symbol, rows) {
  if (!symbol) return [];
  return (rows || [])
    .filter((r) => String(r.symbol || '').toLowerCase() === String(symbol).toLowerCase())
    .map((r) => {
      const isBuy = String(r.side || '').toUpperCase() === 'BUY';
      return {
        time: String(r.date || ''),
        position: isBuy ? 'belowBar' : 'aboveBar',
        color: isBuy ? '#22c55e' : '#ef4444',
        shape: isBuy ? 'arrowUp' : 'arrowDown',
        text: isBuy ? 'B' : 'S',
      };
    })
    .filter((m) => m.time);
}

async function loadBenchmarkSeries(navPoints) {
  // 总是走 API 获取真实数据库行情，不使用 artifact 预计算数据
  const symbol = state.config_draft?.universe?.benchmark || '000300.SH';
  const start = navPoints?.[0]?.date || state.config_draft?.universe?.start;
  const end = navPoints?.[navPoints.length - 1]?.date || state.config_draft?.universe?.end;
  const url = `/api/backtest_v2/series/benchmark?symbol=${encodeURIComponent(symbol)}&start=${encodeURIComponent(start || '')}&end=${encodeURIComponent(end || '')}`;
  try {
    const j = await apiRequestJson('series_benchmark', url);
    const raw = j?.points || [];
    const points = normalizeNavRows(raw.map((x) => ({ date: x.date, nav: x.nav })));
    // 保留 OHLC 数据供蜡烛图渲染
    const ohlc = raw.map((x) => ({
      time: x.date,
      open: x.open ?? x.nav,
      high: x.high ?? x.nav,
      low: x.low ?? x.nav,
      close: x.close ?? x.nav,
    }));
    return { points, ohlc, source: 'api' };
  } catch (e) {
    return { points: [], ohlc: [], source: 'api_failed', error: String(e?.message || e) };
  }
}

async function loadSymbolSeries(symbol, navPoints) {
  const target = String(symbol || '').trim().toLowerCase();
  if (!target) return { points: [], ohlc: [], source: 'empty', symbol: '' };
  const start = navPoints?.[0]?.date || state.config_draft?.universe?.start;
  const end = navPoints?.[navPoints.length - 1]?.date || state.config_draft?.universe?.end;
  const url = `/api/backtest_v2/series/symbol?symbol=${encodeURIComponent(target)}&start=${encodeURIComponent(start || '')}&end=${encodeURIComponent(end || '')}`;
  try {
    const j = await apiRequestJson('series_symbol', url);
    const raw = j?.points || [];
    const points = normalizeNavRows(raw.map((x) => ({ date: x.date, nav: x.nav })));
    const ohlc = raw.map((x) => ({
      time: x.date,
      open: x.open ?? x.nav,
      high: x.high ?? x.nav,
      low: x.low ?? x.nav,
      close: x.close ?? x.nav,
      suspended: !!x.suspended,
    }));
    // 收集停牌区间列表 [{start, end}]
    const suspensionRanges = [];
    let rangeStart = null;
    let prevDate = null;
    for (const x of raw) {
      if (x.suspended && !rangeStart) rangeStart = x.date;
      if (!x.suspended && rangeStart) {
        suspensionRanges.push({ start: rangeStart, end: prevDate || rangeStart });
        rangeStart = null;
      }
      prevDate = x.date;
    }
    if (rangeStart) suspensionRanges.push({ start: rangeStart, end: prevDate || rangeStart });
    return { points, ohlc, suspensionRanges, source: j?.source || 'api', symbol: String(j?.symbol || target).toLowerCase() };
  } catch (e) {
    return { points: [], ohlc: [], source: 'api_failed', symbol: target, error: String(e?.message || e) };
  }
}

async function loadActiveArtifacts() {
  const resultsDir = state.active_exp?.results_dir;
  const result = state.active_result;
  if (!resultsDir || !result) return;
  state.active_artifacts = null;
  renderLoadingSkeleton();
  const gf = result.artifacts || {};
  const [perfR, navR, funnelR, reasonR, runMetaR, configR, tradesR, dailyR, symbolPerfR] = await Promise.all([
    readArtifactWithStatus(resultsDir, gf.perf, 'perf'),
    readArtifactWithStatus(resultsDir, gf.nav, 'nav'),
    readArtifactWithStatus(resultsDir, gf.funnel, 'funnel'),
    readArtifactWithStatus(resultsDir, gf.reason_codes || 'reason_codes.csv', 'reason_codes'),
    readArtifactWithStatus(resultsDir, gf.run_meta, 'run_meta'),
    readArtifactWithStatus(resultsDir, gf.config, 'config'),
    gf.trades ? readArtifactWithStatus(resultsDir, gf.trades, 'trades') : Promise.resolve({ ok: false, key: 'trades', missing: true }),
    gf.daily ? readArtifactWithStatus(resultsDir, gf.daily, 'daily') : Promise.resolve({ ok: false, key: 'daily', missing: true }),
    readArtifactWithFallback(resultsDir, gf.symbol_performance || 'symbol_performance.csv', 'symbol_performance', ['symbol_performance.json']),
  ]);
  const allR = [perfR, navR, funnelR, reasonR, runMetaR, configR, tradesR, dailyR, symbolPerfR];
  const optionalKeys = new Set(['trades', 'daily', 'symbol_performance']);
  const missing = allR.filter((x) => !x.ok && !optionalKeys.has(String(x.key || ''))).map((x) => x.key);
  const errors = allR
    .filter((x) => !x.ok && x.error && !optionalKeys.has(String(x.key || '')))
    .map((x) => `${x.key}: ${x.error}`);
  const statusItems = [perfR, navR, funnelR, reasonR, runMetaR, configR]
    .filter((x) => !x.ok)
    .map((x) => ({
      title: '产物缺失',
      message: `${x.key} 不可用`,
      file: String(x.relPath || x.key || ''),
      detail: String(x.error || ''),
    }));
  setStatusItems(statusItems);

  const normalizedRunMeta = runMetaR.ok ? normalizeRunMetaCounters(runMetaR.payload?.data || {}) : {};

  const navResolved = normalizeNavRows(navR.ok ? navR.payload?.rows || [] : []);
  const strategySeries = navResolved.map((x) => ({ date: x.date, value: x.nav }));
  const drawdownSeries = computeDrawdownSeries(navResolved);
  const benchmark = await loadBenchmarkSeries(navResolved);
  const benchmarkSeries = (benchmark.points || []).map((x) => ({ date: x.date, value: x.nav }));
  const benchmarkDd = computeDrawdownSeries((benchmark.points || []).map((x) => ({ date: x.date, nav: x.nav })));

  const tradesRows = tradesR.ok ? tradesR.payload?.rows || [] : [];
  const symbolPerfRowsRaw = symbolPerfR.ok
    ? (symbolPerfR.payload?.rows || symbolPerfR.payload?.data?.rows || [])
    : [];
  const symbolPerfRows = normalizeSymbolPerformanceRows(symbolPerfRowsRaw);
  state.active_artifacts = {
    perf: perfR.ok ? perfR.payload?.data || {} : {},
    nav: navResolved,
    navSeries: strategySeries,
    drawdownSeries,
    benchmarkSeries,
    benchmarkOhlc: benchmark.ohlc || [],
    benchmarkDrawdownSeries: benchmarkDd,
    benchmarkSource: benchmark.source,
    benchmarkError: benchmark.error || '',
    run_meta: normalizedRunMeta,
    funnelRows: funnelR.ok ? funnelR.payload?.rows || [] : [],
    reasonRows: reasonR.ok ? reasonR.payload?.rows || [] : [],
    config: configR.ok ? configR.payload?.data || null : null,
    tradesRows,
    symbolPerformanceRows: symbolPerfRows,
    dailyRows: dailyR.ok ? dailyR.payload?.rows || [] : [],
    marketStates: _parseMarketStates(dailyR.ok ? dailyR.payload?.rows || [] : []),
    stockNames: {},
    missing,
    errors,
  };
  if (typeof syncConfigSourceUI === 'function') syncConfigSourceUI();
  state.symbol_series_cache = {};
  state.symbol_series_loading = false;
  const hasSelected = state.selected_symbol && symbolPerfRows.some((x) => x.symbol === state.selected_symbol);
  if (!hasSelected) state.selected_symbol = symbolPerfRows[0]?.symbol || '';

  // Fetch Chinese stock names for trade symbols
  if (tradesRows.length) {
    const symbols = [...new Set(tradesRows.map((r) => String(r.symbol || '')).filter(Boolean))];
    if (symbols.length) {
      try {
        const resp = await fetch('/api/backtest_v2/stock_names', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ symbols }),
        });
        if (resp.ok) {
          const data = await resp.json();
          state.active_artifacts.stockNames = data.names || {};
        }
      } catch (_) { /* stock names are optional */ }
    }
  }

  // Sync config_draft with loaded experiment config (use original frontend format)
  const loadedConfig = state.active_artifacts?.config;
  const originalWb = loadedConfig?.overrides?.original_workbench_config;
  if (originalWb && typeof originalWb === 'object') {
    try { applyConfigToUI(originalWb); } catch (_) { /* config format mismatch */ }
  }

  refreshConfigPanels();
}

function reasonByPrefix(rows) {
  const out = { blocked: [], skipped: [], exit: [], other: [] };
  const exitSingles = new Set([
    'TAKE_PROFIT',
    'FIXED_STOP_LOSS',
    'STOP_LOSS',
    'SIGNAL_REVERSE',
    'TREND_REVERSE',
    'RISK_OFF_EXIT',
  ]);
  const codeOf = (row) => String(row?.code || row?.reason_code || '').toUpperCase();
  (rows || []).forEach((r) => {
    const code = codeOf(r);
    if (code.startsWith('BLOCKED_') || code.startsWith('BLOCK_')) out.blocked.push(r);
    else if (code.startsWith('SKIPPED_') || code.startsWith('SKIP_')) out.skipped.push(r);
    else if (code.includes('EXIT') || code.includes('ATR_') || exitSingles.has(code)) out.exit.push(r);
    else out.other.push(r);
  });
  Object.values(out).forEach((arr) => arr.sort((a, b) => Number(b.count || 0) - Number(a.count || 0)));
  return out;
}

function renderSymbolPerformancePanel() {
  const body = byId('wbSymbolPerfBody');
  const hint = byId('wbSymbolPerfHint');
  if (!body) return;
  const allRows = (state.active_artifacts || {}).symbolPerformanceRows || [];
  if (hint) {
    const fb = allRows.filter((r) => r.valuation_fallback_used).length;
    hint.textContent = fb > 0
      ? `未平仓收益按区间末日收盘价近似估值（${fb} 个标的使用回溯收盘价）。`
      : '未平仓收益按区间末日收盘价近似估值。';
  }
  const rows = getFilteredSortedSymbolRows();
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="4" class="wb-symbol-empty">无个股绩效数据</td></tr>';
    return;
  }
  body.innerHTML = rows.map((r) => {
    const active = String(state.selected_symbol || '') === String(r.symbol);
    const displayName = stockZh(r.symbol);
    const symbolCell = displayName !== r.symbol
      ? `${esc(displayName)}<span class="wb-mini" style="margin-left:6px">${esc(r.symbol)}</span>`
      : esc(r.symbol);
    return `<tr class="wb-symbol-row${active ? ' active' : ''}" data-symbol="${esc(r.symbol)}">
      <td>${symbolCell}</td>
      <td class="num">${pct(r.return_pct)}</td>
      <td class="num">${pct(r.max_drawdown)}</td>
      <td class="num">${fmtInt(r.trades)}</td>
    </tr>`;
  }).join('');
  body.querySelectorAll('tr[data-symbol]').forEach((tr) => {
    tr.addEventListener('click', () => {
      const sym = String(tr.getAttribute('data-symbol') || '').toLowerCase();
      if (!sym) return;
      state.selected_symbol = sym;
      state.chart_mode = 'symbol';
      if (byId('wbChartMode')) byId('wbChartMode').value = 'symbol';
      renderPerfPanel();
    });
  });
}

function firstValidValue(...values) {
  for (const value of values) {
    if (value == null) continue;
    if (typeof value === 'string' && !String(value).trim()) continue;
    if (typeof value === 'number' && Number.isNaN(value)) continue;
    return value;
  }
  return null;
}

function setKpiValue(id, text) {
  setTextById(id, text == null || text === '' ? '-' : String(text));
}

function renderBuyFunnelRows(rows, counters) {
  if (!Array.isArray(rows) || !rows.length) {
    return '<div class="wb-mini">当前结果未提供买入 stage counters，无法安全生成逐 stage 买入漏斗。</div>';
  }
  const maxValue = Math.max(1, ...rows.map((row) => Number(row.input_count ?? row.output_count ?? row.filtered_count ?? 0) || 0));
  const body = rows.map((row) => {
    const available = row.available !== false;
    const inputCount = Number(row.input_count);
    const outputCount = Number(row.output_count);
    const filteredCount = Number(row.filtered_count);
    const inputText = Number.isFinite(inputCount) ? fmtInt(inputCount) : '-';
    const outputText = Number.isFinite(outputCount) ? fmtInt(outputCount) : '-';
    const filteredText = Number.isFinite(filteredCount) ? fmtInt(filteredCount) : '-';
    const width = Number.isFinite(outputCount) ? Math.max(6, (outputCount / maxValue) * 100) : 0;
    return `<div class="wb-funnel-row${available ? '' : ' wb-funnel-unavailable'}">
      <div class="wb-funnel-row-head">
        <div class="wb-funnel-row-title">${esc(row.stage_label || row.title || row.stage_key || '阶段')}</div>
        <div class="wb-funnel-row-note">${esc(row.note || (available ? '已接入后端计数' : '当前策略未启用或未单独计数'))}</div>
      </div>
      <div class="wb-bar"><span style="width:${width}%"></span></div>
      <div class="wb-funnel-row-meta">
        <div><span>输入</span><strong>${inputText}</strong></div>
        <div><span>保留</span><strong>${outputText}</strong></div>
        <div><span>过滤</span><strong>${filteredText}</strong></div>
      </div>
    </div>`;
  }).join('');
  const reasonCounts = counters?.buy_block_reason_counts || {};
  const topReasons = Object.entries(reasonCounts)
    .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0))
    .slice(0, 8)
    .map(([code, count]) => `${reasonZh(code)} ${fmtInt(count)}`)
    .join(' | ');
  const footer = topReasons ? `<div class="wb-mini wb-gap-top">主要过滤原因：${esc(topReasons)}</div>` : '';
  return `<div class="wb-funnel-stack">${body}</div>${footer}`;
}

function renderSellFunnelRows(reasonRows) {
  const rows = Array.isArray(reasonRows) ? reasonRows : [];
  if (!rows.length) {
    return '<div class="wb-mini">当前结果没有可展示的卖出原因频次。</div>';
  }
  const maxCount = Math.max(1, ...rows.map((row) => Number(row.count || 0)));
  return `<div class="wb-sell-funnel-list">${rows.map((row) => {
    const count = Number(row.count || 0);
    return `<div class="wb-sell-funnel-item">
      <div class="wb-sell-funnel-label">${esc(reasonZh(row.code))}</div>
      <div class="wb-bar"><span style="width:${Math.max(6, (count / maxCount) * 100)}%"></span></div>
      <div class="wb-sell-funnel-count">${fmtInt(count)}</div>
    </div>`;
  }).join('')}</div>`;
}

async function ensureSelectedSymbolSeries(navSeries) {
  const symbol = String(state.selected_symbol || '').toLowerCase();
  if (!symbol) return;
  if (state.symbol_series_cache[symbol]) return;
  if (state.symbol_series_loading) return;
  state.symbol_series_loading = true;
  try {
    const series = await loadSymbolSeries(symbol, navSeries);
    state.symbol_series_cache[symbol] = series;
  } finally {
    state.symbol_series_loading = false;
  }
  renderPerfPanel();
}

function renderPerfPanel() {
  const row = state.active_result || {};
  const art = state.active_artifacts || {};
  const p = art.perf || {};
  renderSymbolPerformancePanel();
  const kpis = byId('wbPerfKpis');
  if (kpis) {
    const items = [
      ['年化收益', p.cagr ?? row.cagr, pct],
      ['最大回撤', p.max_drawdown ?? row.max_drawdown, pct],
      ['夏普比率', p.sharpe ?? row.sharpe, (v) => num(v, 2)],
      ['卡尔马比率', p.calmar ?? row.calmar, (v) => num(v, 2)],
      ['交易次数', p.trades ?? row.trades, fmtInt],
      ['换手率', p.turnover ?? row.turnover, pct],
      ['Top10集中度', p.top10_profit_concentration ?? row.top10_profit_concentration, pct],
      ['评级', p.tier ?? row.tier, null],
    ];
    kpis.innerHTML = items.map(([k, v, fmt]) => `<div class="wb-kpi"><div class="wb-mini">${esc(k)}</div><div class="wb-code">${fmt && typeof v === 'number' ? fmt(v) : esc(String(v ?? '-'))}</div></div>`).join('');
  }

  const missingMsg = art?.missing?.length ? `缺失 ${art.missing.length} 个产物，详情见状态中心` : '产物已加载';
  setTextById('wbGroupLoadStatus', missingMsg);

  const period = state.chart_range; // D / W / M / Y

  const isSymbolMode = state.chart_mode === 'symbol' && !!state.selected_symbol;
  const symbolCache = isSymbolMode ? state.symbol_series_cache[state.selected_symbol] : null;
  if (isSymbolMode && !symbolCache) ensureSelectedSymbolSeries(art.navSeries || []);
  const rawMainSeries = (isSymbolMode && symbolCache)
    ? (symbolCache.points || []).map((x) => ({ date: x.date, value: x.nav }))
    : (art.navSeries || []);
  const rawMainDd = computeDrawdownSeries(rawMainSeries.map((x) => ({ date: x.date, nav: x.value })));

  // 按周期聚合 OHLC 和 NAV
  const benchOhlc = aggregateOhlc(art.benchmarkOhlc || [], period);
  const navSeries = aggregateNav(rawMainSeries, period);
  const ddSeries = aggregateDrawdown(rawMainDd, period);
  const benchDdSeries = aggregateDrawdown(art.benchmarkDrawdownSeries || [], period);
  const tradeMarkers = isSymbolMode ? symbolTradeMarkers(state.selected_symbol, art.tradesRows || []) : [];

  // 市场状态色带数据（仅组合模式有效）
  const marketStates = !isSymbolMode ? (art.marketStates || []) : [];
  // 停牌区间（仅个股模式有效）
  const suspensionRanges = (isSymbolMode && symbolCache) ? (symbolCache.suspensionRanges || []) : [];

  // 主图：基准K + 主序列（组合净值或个股）
  renderNavChartLW(
    'wbNavChart',
    state.chart_show_benchmark ? benchOhlc : [],
    navSeries,
    state.chart_show_benchmark,
    { mode: isSymbolMode ? 'symbol' : 'portfolio', markers: tradeMarkers, marketStates, suspensionRanges },
  );

  // 回撤图：LightweightCharts AreaSeries（与主图时间轴同步）
  renderDdChartLW('wbDdChart', ddSeries, benchDdSeries, state.chart_show_benchmark, { marketStates });

  const navInfo = navSeries.length
    ? `${isSymbolMode ? `个股 ${state.selected_symbol}` : '净值'}=${navSeries.length}点`
    : `${isSymbolMode ? '个股序列缺失' : '净值缺失'}(${art.errors?.find((x) => String(x).startsWith('nav:')) || '未提供'})`;
  const bmInfo = art.benchmarkError ? `基准异常=${art.benchmarkError}` : `基准来源=${art.benchmarkSource || '无'}`;
  setHtmlById('wbPerfSeries', `${navInfo} | 回撤=${ddSeries.length}点 | ${bmInfo} ${state.chart_show_benchmark ? '' : '| 基准=关'}`);
  renderTradesList();
}

function renderFunnelBars(funnel) {
  const keys = [
    ['原始信号', Number(funnel.raw_signal || 0)],
    ['被拦截', Number(funnel.blocked || 0)],
    ['下单', Number(funnel.orders || 0)],
    ['跳过', Number(funnel.skipped || 0)],
    ['已平仓', Number(funnel.closed_trades || 0)],
  ];
  const maxV = Math.max(...keys.map((x) => x[1]), 1);
  return keys.map(([k, v]) => `<div style="display:grid;grid-template-columns:110px 1fr 70px;gap:6px;align-items:center;margin-bottom:4px"><span>${k}</span><div class="wb-bar"><span style="width:${(v / maxV) * 100}%"></span></div><span class="wb-code">${num(v, 0)}</span></div>`).join('');
}

function renderExplainPanel() {
  const row = state.active_result || {};
  const art = state.active_artifacts || {};
  if (!row.exp_id && !Object.keys(art || {}).length) {
    setHtmlById('wbFunnel', '<div class="wb-mini">运行后显示信号漏斗</div>');
    setHtmlById('wbTriggers', '<div class="wb-mini">运行后显示触发统计</div>');
    setHtmlById('wbReasons', '<div class="wb-mini">运行后显示原因码分布</div>');
    setTextById('wbBaselineDiff', '结果: - | 状态=-');
    return;
  }
  const counters = art?.run_meta?.counters || row || {};
  const funnel = (art.funnelRows || [])[0] || {};
  setHtmlById('wbFunnel', `<div class="wb-mini" style="margin-bottom:6px">信号漏斗</div>${renderFunnelBars({
    raw_signal: funnel.raw_signal ?? row.raw_signal ?? 0,
    blocked: funnel.blocked ?? row.blocked ?? 0,
    orders: funnel.orders ?? row.orders ?? 0,
    skipped: funnel.skipped ?? row.skipped ?? 0,
    closed_trades: funnel.closed_trades ?? row.closed_trades ?? 0,
  })}`);

  const tRows = [
    ['信号反转退出', counters.reversal_exit_count ?? 0, false],
    ['时间退出', counters.time_exit_count ?? 0, false],
    ['ATR止损平仓', counters.atr_stop_exit_count ?? row.atr_stop_exit_count ?? 0, false],
    ['ATR追踪平仓', counters.atr_trail_exit_count ?? row.atr_trail_exit_count ?? 0, false],
    ['ATR追踪更新', counters.atr_trail_update_count ?? row.atr_trail_update_count ?? 0, false],
    ['资金流排名应用率', counters.mf_rank_applied_rate ?? row.mf_rank_applied_rate ?? 0, true],
    ['门控触发率', counters.gate_on_rate ?? row.gate_on_rate ?? 0, true],
    ['趋势斜率拦截', counters.trend_slope_block_count ?? row.trend_slope_block_count ?? 0, false],
    ['入场过滤(close>slow_ma)', counters.entry_above_slow_ma_block_count ?? 0, false],
    ['入场过滤(slow_ma斜率)', counters.entry_slope_block_count ?? 0, false],
    ['最短持有拦截', counters.min_hold_block_count ?? 0, false],
    ['冷却期拦截', counters.cooldown_block_count ?? 0, false],
    ['止盈平仓', counters.take_profit_exit_count ?? 0, false],
    ['固定止损平仓', counters.fixed_stop_loss_exit_count ?? 0, false],
    ['DD缩仓0.8x', counters.dd_scale_08_count ?? 0, false],
    ['DD缩仓0.6x', counters.dd_scale_06_count ?? 0, false],
    ['DD固定3%', counters.dd_fixed_03_count ?? 0, false],
    ['DD停买', counters.dd_stop_count ?? 0, false],
    ['DD停买拦截', counters.dd_stop_block_count ?? 0, false],
    ['DD恢复重置', counters.dd_stop_reset_count ?? 0, false],
  ];

  // regime router 计数器（仅在有数据时显示）
  const regimeTrend = Number(counters.regime_trend_days ?? 0);
  const regimeMr = Number(counters.regime_mr_days ?? 0);
  if (regimeTrend + regimeMr > 0) {
    const total = regimeTrend + regimeMr;
    tRows.push(
      ['趋势天数', regimeTrend, false],
      ['震荡天数', regimeMr, false],
      ['趋势天占比', total ? regimeTrend / total : 0, true],
      ['MR RSI买入', counters.mr_rsi_oversold_buy_count ?? 0, false],
      ['MR RSI卖出', counters.mr_rsi_overbought_sell_count ?? 0, false],
      ['MR 止损', counters.mr_stop_loss_count ?? 0, false],
      ['MR 时间退出', counters.mr_time_exit_count ?? 0, false],
    );
  }
  const rfDiag = counters.regime_filter_diagnostics;
  if (rfDiag && typeof rfDiag === 'object' && Object.keys(rfDiag).length > 0) {
    tRows.push(
      ['RF Market Gate均值', Number(rfDiag.gate_m_mean ?? 0), true],
      ['RF Sector覆盖率', Number(rfDiag.gate_sec_coverage ?? 0), true],
      ['RF 信号均值', Number(rfDiag.regime_signal_mean ?? 0), true],
      ['RF 超阈值占比', Number(rfDiag.regime_signal_above_threshold_pct ?? 0), true],
    );
  }

  setHtmlById('wbTriggers', `<table class="wb-table"><thead><tr><th>计数器</th><th>值</th></tr></thead><tbody>${tRows.map(([k, v, isRate]) => `<tr><td>${esc(k)}</td><td>${isRate ? pct(v) : num(v, 0)}</td></tr>`).join('')}</tbody></table>`);

  const reasonBuckets = reasonByPrefix(art.reasonRows || []);
  const top = (arr) => arr.slice(0, 20).map((x) => `${reasonZh(x.code)}:${x.count}`).join(', ') || '无';
  const errPart = art.errors?.length ? `<br>异常: ${esc(art.errors.join(' | '))}` : '';
  setHtmlById('wbReasons', `拦截: ${esc(top(reasonBuckets.blocked))}<br>跳过: ${esc(top(reasonBuckets.skipped))}<br>退出: ${esc(top(reasonBuckets.exit))}${errPart}`);
  setTextById('wbBaselineDiff', `结果: ${row.exp_id || '-'} | 状态=${row.status || '-'}`);

  // Populate Drawer stats panels
  populateExitStats(counters);
  populateConstraintStats(counters, state.config_draft);
  populateMarketStateStats(counters);
}

function renderExecutionPanel() {
  const p = state.execution_preview;
  const execStatus = state.api_status?.execution_preview || null;
  if (!state.execution_api_enabled) {
    setTextById('wbExecDateNote', '后端未启用 execution preview');
    setTextById('wbExecCandidates', '候选标的: -');
    setTextById('wbExecTargets', '目标持仓: -');
  } else if (!p) {
    if (execStatus?.status === 'failed') {
      setTextById('wbExecDateNote', `执行接口失败: ${execStatus.error || '未知错误'}`);
    } else if (execStatus?.status === 'loading') {
      setTextById('wbExecDateNote', '执行接口请求中...');
    } else {
      setTextById('wbExecDateNote', '未生成执行清单（可点击"生成今日执行清单"）');
    }
    setTextById('wbExecCandidates', '候选标的: -');
    setTextById('wbExecTargets', '目标持仓: -');
  } else {
    setTextById('wbExecDateNote', `基准日期=${p.as_of_date_used} (来源=${p.source || '未知'})`);
    setHtmlById('wbExecCandidates', `候选标的 TopN: ${(p.candidates || []).map((x) => `${x.rank}.${x.symbol}(${num(x.score, 6)})`).join(' | ')}`);
    setHtmlById('wbExecTargets', `目标持仓: ${(p.target_positions || []).map((x) => `${x.symbol}:${pct(x.target_weight)}`).join(' | ')}`);
  }
  // 渲染交易明细表
  renderTradesList();
}

function stockZh(symbol) {
  const names = (state.active_artifacts || {}).stockNames || {};
  const name = names[symbol];
  return name ? `${name}` : String(symbol ?? '');
}

function visibleTradesRows() {
  const rows = (state.active_artifacts || {}).tradesRows || [];
  const symbolMode = state.chart_mode === 'symbol' && state.selected_symbol;
  if (!symbolMode) return rows;
  const symbol = String(state.selected_symbol || '').toLowerCase();
  return rows.filter((r) => String(r.symbol || '').toLowerCase() === symbol);
}

function tradesTableHtml(rows, totalRows) {
  const symbolMode = state.chart_mode === 'symbol' && state.selected_symbol;
  const title = symbolMode
    ? `交易明细 (${fmtInt(rows.length)} 条 / ${esc(String(state.selected_symbol || '').toUpperCase())})`
    : `交易明细 (${fmtInt(rows.length)} 条)`;
  if (!rows.length) {
    const emptyText = totalRows
      ? '当前个股视图下没有交易明细'
      : '运行后显示交易明细';
    return `<div class="wb-mini">${emptyText}</div>`;
  }
  const labels = ['日期', '标的', '方向', '成交价', '数量', '金额', '佣金', '印花税', '净额', '原因'];
  const aligns = ['', '', '', 'num', 'num', 'num', 'num', 'num', 'num', ''];
  const header = `<tr>${labels.map((l, i) => `<th${aligns[i] ? ' class="num"' : ''}>${esc(l)}</th>`).join('')}</tr>`;
  const body = rows.map((r) => {
    const isBuy = String(r.side || '').toUpperCase() === 'BUY';
    const sideBadge = isBuy
      ? '<span class="wb-badge-buy">买入</span>'
      : '<span class="wb-badge-sell">卖出</span>';
    const sym = String(r.symbol ?? '');
    const displayName = stockZh(sym);
    const symbolCell = displayName !== sym ? `<span title="${esc(sym)}">${esc(displayName)}</span>` : esc(sym);
    const fp = r.fill_price != null ? num(r.fill_price, 3) : num(r.price, 3);
    const comm = r.commission != null ? fmtMoney(r.commission) : '-';
    const stax = r.stamp_tax != null ? fmtMoney(r.stamp_tax) : '-';
    const netAmt = r.net_amount != null ? fmtMoney(r.net_amount) : fmtMoney(r.value);
    return `<tr><td>${esc(String(r.date ?? ''))}</td><td>${symbolCell}</td><td>${sideBadge}</td><td class="num">${fp}</td><td class="num">${fmtInt(r.qty)}</td><td class="num">${fmtMoney(r.value)}</td><td class="num">${comm}</td><td class="num">${stax}</td><td class="num">${netAmt}</td><td>${esc(reasonZh(r.reason_code))}</td></tr>`;
  }).join('');
  return `<div class="wb-mini" style="margin-bottom:4px">${title}</div><table class="wb-table"><thead>${header}</thead><tbody>${body}</tbody></table>`;
}

function renderTradesList() {
  const allRows = (state.active_artifacts || {}).tradesRows || [];
  const rows = visibleTradesRows();
  const html = tradesTableHtml(rows, allRows.length);
  const el = byId('wbTradesList');
  if (el) el.innerHTML = html;
}

function _reasonCodeOf(row) {
  return String(row?.code || row?.reason_code || '').toUpperCase();
}

renderBuyFunnelRows = function renderBuyFunnelRowsV2(rows, counters) {
  if (!Array.isArray(rows) || !rows.length) {
    return '<div class="wb-mini">当前结果尚未提供买入 stage counters，无法安全生成买入漏斗。</div>';
  }
  const maxValue = Math.max(1, ...rows.map((row) => Number(row.input_count ?? row.output_count ?? row.filtered_count ?? 0) || 0));
  const body = rows.map((row) => {
    const available = row.available !== false;
    const inputCount = Number(row.input_count);
    const outputCount = Number(row.output_count);
    const filteredCount = Number(row.filtered_count);
    const inputText = Number.isFinite(inputCount) ? fmtInt(inputCount) : '-';
    const outputText = Number.isFinite(outputCount) ? fmtInt(outputCount) : '-';
    const filteredText = Number.isFinite(filteredCount) ? fmtInt(filteredCount) : '-';
    const width = Number.isFinite(outputCount) ? Math.max(6, (outputCount / maxValue) * 100) : 0;
    return `<div class="wb-funnel-row${available ? '' : ' wb-funnel-unavailable'}">
      <div class="wb-funnel-row-head">
        <div class="wb-funnel-row-title">${esc(row.stage_label || row.title || row.stage_key || '阶段')}</div>
        <div class="wb-funnel-row-note">${esc(row.note || (available ? '已接入后端真实计数' : '当前策略未启用或未单独计数'))}</div>
      </div>
      <div class="wb-bar"><span style="width:${width}%"></span></div>
      <div class="wb-funnel-row-meta">
        <div><span>输入</span><strong>${inputText}</strong></div>
        <div><span>保留</span><strong>${outputText}</strong></div>
        <div><span>过滤</span><strong>${filteredText}</strong></div>
      </div>
    </div>`;
  }).join('');
  const reasonCounts = counters?.buy_block_reason_counts || {};
  const topReasons = Object.entries(reasonCounts)
    .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0))
    .slice(0, 8)
    .map(([code, count]) => `${reasonZh(code)} ${fmtInt(count)}`)
    .join(' | ');
  const footer = topReasons ? `<div class="wb-mini wb-gap-top">主要过滤原因：${esc(topReasons)}</div>` : '';
  return `<div class="wb-funnel-stack">${body}</div>${footer}`;
};

renderSellFunnelRows = function renderSellFunnelRowsV2(reasonRows) {
  const rows = Array.isArray(reasonRows) ? reasonRows : [];
  if (!rows.length) {
    return '<div class="wb-mini">当前结果没有可展示的卖出原因频次。</div>';
  }
  const maxCount = Math.max(1, ...rows.map((row) => Number(row.count || 0)));
  return `<div class="wb-sell-funnel-list">${rows.map((row) => {
    const count = Number(row.count || 0);
    const code = _reasonCodeOf(row);
    return `<div class="wb-sell-funnel-item">
      <div class="wb-sell-funnel-label">${esc(reasonZh(code))}</div>
      <div class="wb-bar"><span style="width:${Math.max(6, (count / maxCount) * 100)}%"></span></div>
      <div class="wb-sell-funnel-count">${fmtInt(count)}</div>
    </div>`;
  }).join('')}</div>`;
};

renderPerfPanel = function renderPerfPanelV2() {
  const row = state.active_result || {};
  const art = state.active_artifacts || {};
  const p = art.perf || {};
  const cagr = firstValidValue(p.cagr, row.cagr);
  const totalReturn = firstValidValue(p.total_return, row.total_return);
  const maxDrawdown = firstValidValue(p.max_drawdown, row.max_drawdown);
  const sharpe = firstValidValue(p.sharpe, row.sharpe);
  const calmar = firstValidValue(p.calmar, row.calmar);
  const trades = firstValidValue(p.trades, row.trades);
  const turnover = firstValidValue(p.turnover, row.turnover);
  const top10 = firstValidValue(p.top10_profit_concentration, row.top10_profit_concentration);
  const tier = firstValidValue(p.tier, row.tier, art.run_meta?.tier);
  renderSymbolPerformancePanel();

  const navBase = Array.isArray(art.navSeries) ? art.navSeries : [];
  const navStart = Number(navBase[0]?.value);
  const navEnd = Number(navBase[navBase.length - 1]?.value);
  setKpiValue('wbKpiInitialCapital', Number.isFinite(navStart) ? fmtMoney(navStart) : '-');
  setKpiValue('wbKpiFinalCapital', Number.isFinite(navEnd) ? fmtMoney(navEnd) : '-');
  setKpiValue('wbKpiCagr', cagr == null ? '-' : pct(cagr));
  setKpiValue('wbKpiTotalReturn', totalReturn == null ? '-' : pct(totalReturn));
  setKpiValue('wbKpiMaxDrawdown', maxDrawdown == null ? '-' : pct(maxDrawdown));
  setKpiValue('wbKpiSharpe', sharpe == null ? '-' : num(sharpe, 2));
  setKpiValue('wbKpiCalmar', calmar == null ? '-' : num(calmar, 2));
  setKpiValue('wbKpiTrades', trades == null ? '-' : fmtInt(trades));
  setKpiValue('wbKpiTurnover', turnover == null ? '-' : pct(turnover));
  setKpiValue('wbKpiTop10Concentration', top10 == null ? '-' : pct(top10));
  setKpiValue('wbKpiTier', tier == null ? '-' : tier);

  const missingMsg = art?.missing?.length ? `缺失 ${art.missing.length} 个产物，详情见状态中心` : '产物已加载';
  setTextById('wbGroupLoadStatus', missingMsg);

  const period = state.chart_range;
  const isSymbolMode = state.chart_mode === 'symbol' && !!state.selected_symbol;
  const symbolCache = isSymbolMode ? state.symbol_series_cache[state.selected_symbol] : null;
  if (isSymbolMode && !symbolCache) ensureSelectedSymbolSeries(art.navSeries || []);
  const rawMainSeries = (isSymbolMode && symbolCache)
    ? (symbolCache.points || []).map((x) => ({ date: x.date, value: x.nav }))
    : (art.navSeries || []);

  const benchOhlc = aggregateOhlc(art.benchmarkOhlc || [], period);
  const navSeries = aggregateNav(rawMainSeries, period);
  const tradeMarkers = isSymbolMode ? symbolTradeMarkers(state.selected_symbol, art.tradesRows || []) : [];
  const marketStates = !isSymbolMode ? (art.marketStates || []) : [];
  const suspensionRanges = (isSymbolMode && symbolCache) ? (symbolCache.suspensionRanges || []) : [];

  renderNavChartLW(
    'wbNavChart',
    state.chart_show_benchmark ? benchOhlc : [],
    navSeries,
    state.chart_show_benchmark,
    { mode: isSymbolMode ? 'symbol' : 'portfolio', markers: tradeMarkers, marketStates, suspensionRanges },
  );

  const navInfo = navSeries.length
    ? `${isSymbolMode ? `个股 ${state.selected_symbol}` : '净值'}=${navSeries.length}点`
    : `${isSymbolMode ? '个股序列缺失' : '净值缺失'}(${art.errors?.find((x) => String(x).startsWith('nav:')) || '未提供'})`;
  const bmInfo = art.benchmarkError ? `基准异常=${art.benchmarkError}` : `基准来源=${art.benchmarkSource || '未知'}`;
  setHtmlById('wbPerfSeries', `${navInfo} | ${bmInfo}${state.chart_show_benchmark ? '' : ' | 基准=关闭'}`);
  renderTradesList();
};

renderExplainPanel = function renderExplainPanelV2() {
  const row = state.active_result || {};
  const art = state.active_artifacts || {};
  if (!row.exp_id && !Object.keys(art || {}).length) {
    setHtmlById('wbBuyFunnel', '<div class="wb-mini">运行后显示买入漏斗。</div>');
    setHtmlById('wbSellFunnel', '<div class="wb-mini">运行后显示卖出漏斗。</div>');
    setTextById('wbAccBuyFunnelMeta', '等待结果');
    setTextById('wbAccSellFunnelMeta', '等待结果');
    setTextById('wbAccLogsMeta', '状态输出');
    return;
  }
  const counters = art?.run_meta?.counters || row || {};
  const buyStageRows = Array.isArray(counters.buy_stage_funnel) ? counters.buy_stage_funnel : [];
  const reasonBuckets = reasonByPrefix(art.reasonRows || []);
  const exitRows = reasonBuckets.exit || [];
  const exitCount = exitRows.reduce((sum, item) => sum + Number(item.count || 0), 0);
  const buyOrders = Number(counters.buy_orders_count ?? 0);

  setHtmlById('wbBuyFunnel', renderBuyFunnelRows(buyStageRows, counters));
  setHtmlById('wbSellFunnel', renderSellFunnelRows(exitRows));
  setTextById('wbAccBuyFunnelMeta', buyStageRows.length ? `最终买入 ${fmtInt(buyOrders)} 笔` : '等待后端 stage counters');
  setTextById('wbAccSellFunnelMeta', exitRows.length ? `卖出原因 ${fmtInt(exitCount)} 次` : '无退出数据');
  setTextById('wbAccLogsMeta', row.exp_id ? `${row.exp_id} | ${row.status || '-'}` : '状态输出');
};

renderTradesList = function renderTradesListV2() {
  const allRows = (state.active_artifacts || {}).tradesRows || [];
  const rows = visibleTradesRows();
  const html = tradesTableHtml(rows, allRows.length);
  const el = byId('wbTradesList');
  if (el) el.innerHTML = html;
  const symbolMode = state.chart_mode === 'symbol' && state.selected_symbol;
  const meta = symbolMode
    ? `${String(state.selected_symbol || '').toUpperCase()} | ${fmtInt(rows.length)} 条`
    : `全部交易 ${fmtInt(rows.length)} 条`;
  setTextById('wbAccTradesMeta', meta);
};

renderExecutionPanel = function renderExecutionPanelV2() {
  if (!byId('wbExecDateNote') && !byId('wbExecCandidates') && !byId('wbExecTargets')) return;
};
