/* 鈹€鈹€ artifacts.js 鈹€鈹€ Artifact loading, normalization, and rendering 鈹€鈹€ */
/* Globals used: state, byId, esc, num, pct, fmtInt, fmtMoney, setTextById, setHtmlById,
   reasonZh,
   apiRequestJson, setStatusItems, addLog,
   renderLoadingSkeleton, renderNavChartLW, renderDdChartLW,
   aggregateOhlc, aggregateNav, aggregateDrawdown,
   applyConfigToUI, refreshConfigPanels,
   populateExitStats, populateConstraintStats (from other modules) */

async function readArtifactWithStatus(resultsDir, relPath, keyName, expId = null) {
  if (!relPath) return { ok: false, key: keyName, missing: true, error: `${keyName} 缺失` };
  let reqRelPath = relPath;
  const relText = String(relPath);
  const isAbsPosix = relText.startsWith('/');
  const isAbsWin = /^[A-Za-z]:[\\/]/.test(relText);
  if (isAbsPosix || isAbsWin) {
    const normalized = relText.replaceAll('\\', '/');
    const idx = normalized.lastIndexOf('/');
    if (idx > 0) {
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
        body: JSON.stringify({ exp_id: expId, rel_path: reqRelPath }),
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

async function readArtifactWithFallback(resultsDir, relPath, keyName, fallbacks = [], expId = null) {
  const primaryRel = relPath || `${keyName}.csv`;
  const first = await readArtifactWithStatus(resultsDir, primaryRel, keyName, expId);
  if (first.ok) return { ...first, usedLegacyFallback: false };
  for (const altRel of (fallbacks || [])) {
    const fb = await readArtifactWithStatus(resultsDir, altRel, keyName, expId);
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
  // 浠?portfolio_daily.csv 琛岃В鏋?market_state + trade_mode 鈫?[{time, mode}]
  // mode: TREND_MAIN / TREND_LIGHT / BEAR / NO_TRADE_TRANS (transparent)
  const out = [];
  for (const r of dailyRows || []) {
    // market_state 鍒椾笉瀛樺湪鏃?r.market_state 涓?undefined锛岃烦杩?    if (r.market_state == null || r.market_state === '') continue;
    const date = String(r.date ?? '').trim();
    const ms = String(r.market_state).trim().toUpperCase();
    const tm = String(r.trade_mode ?? '').trim().toUpperCase();
    if (!date || !ms) continue;
    let mode;
    if (tm === 'TREND_MAIN') mode = 'TREND_MAIN';
    else if (tm === 'TREND_LIGHT') mode = 'TREND_LIGHT';
    else if (ms === 'BEAR') mode = 'BEAR';
    else mode = 'NO_TRADE_TRANS'; // transition without signal 鈫?transparent
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
  const deriveReturnPct = (row) => {
    const buyNotional = Number(row?.buy_notional);
    const rawReturnPct = Number(row?.return_pct);
    const netPnl = Number(row?.net_pnl);
    const realizedPnl = Number(row?.realized_pnl);
    const unrealizedApproxPnl = Number(row?.unrealized_approx_pnl);
    const derivedPnl = Number.isFinite(netPnl)
      ? netPnl
      : ((Number.isFinite(realizedPnl) ? realizedPnl : 0) + (Number.isFinite(unrealizedApproxPnl) ? unrealizedApproxPnl : 0));
    if (Number.isFinite(buyNotional) && buyNotional > 0 && Number.isFinite(derivedPnl)) {
      return derivedPnl / buyNotional;
    }
    return rawReturnPct;
  };
  (rows || []).forEach((r) => {
    const symbol = String(r.symbol ?? '').trim().toLowerCase();
    if (!symbol) return;
    const returnPct = Number(deriveReturnPct(r));
    const maxDrawdown = Number(r.max_drawdown);
    const trades = Number(r.trades);
    const netPnl = Number(r.net_pnl);
    const realizedPnl = Number(r.realized_pnl);
    const buyNotional = Number(r.buy_notional);
    out.push({
      symbol,
      return_pct: Number.isFinite(returnPct) ? returnPct : 0,
      max_drawdown: Number.isFinite(maxDrawdown) ? maxDrawdown : 0,
      trades: Number.isFinite(trades) ? trades : 0,
      net_pnl: Number.isFinite(netPnl) ? netPnl : 0,
      realized_pnl: Number.isFinite(realizedPnl) ? realizedPnl : 0,
      buy_notional: Number.isFinite(buyNotional) ? buyNotional : 0,
      unrealized_approx_pnl: Number.isFinite(Number(r.unrealized_approx_pnl)) ? Number(r.unrealized_approx_pnl) : 0,
      valuation_fallback_used: toBool(r.valuation_fallback_used),
    });
  });
  return out;
}

function deriveLegacySymbolReturnPct(row) {
  const buyNotional = Number(row?.buy_notional);
  const rawReturnPct = Number(row?.return_pct);
  const netPnl = Number(row?.net_pnl);
  const realizedPnl = Number(row?.realized_pnl);
  const unrealizedApproxPnl = Number(row?.unrealized_approx_pnl);
  const derivedPnl = Number.isFinite(netPnl)
    ? netPnl
    : ((Number.isFinite(realizedPnl) ? realizedPnl : 0) + (Number.isFinite(unrealizedApproxPnl) ? unrealizedApproxPnl : 0));
  if (Number.isFinite(buyNotional) && buyNotional > 0 && Number.isFinite(derivedPnl)) {
    return derivedPnl / buyNotional;
  }
  return rawReturnPct;
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
    filtered.sort((a, b) => Number(deriveLegacySymbolReturnPct(b) || 0) - Number(deriveLegacySymbolReturnPct(a) || 0));
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
  // 始终通过 API 获取真实数据库行情，不使用 artifact 预估计算数据。
  const symbol = state.config_draft?.universe?.benchmark || '000300.SH';
  const start = navPoints?.[0]?.date || state.config_draft?.universe?.start;
  const end = navPoints?.[navPoints.length - 1]?.date || state.config_draft?.universe?.end;
  const url = `/api/backtest_v2/series/benchmark?symbol=${encodeURIComponent(symbol)}&start=${encodeURIComponent(start || '')}&end=${encodeURIComponent(end || '')}`;
  try {
    const j = await apiRequestJson('series_benchmark', url);
    const raw = j?.points || [];
    const points = normalizeNavRows(raw.map((x) => ({ date: x.date, nav: x.nav })));
    // 淇濈暀 OHLC 鏁版嵁渚涜湣鐑涘浘娓叉煋
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
    // 鏀堕泦鍋滅墝鍖洪棿鍒楄〃 [{start, end}]
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

async function ensureManifestForActiveResult(result) {
  if (!result || typeof result !== 'object') return null;
  const existingManifest = result.manifest;
  if (existingManifest && typeof existingManifest === 'object') {
    if (!result.artifacts && existingManifest.artifacts) result.artifacts = existingManifest.artifacts;
    return existingManifest;
  }
  const existingArtifacts = result.artifacts;
  if (existingArtifacts && Object.keys(existingArtifacts).length) return null;
  const expId = result.exp_id || result.experiment_id || null;
  if (!expId) return null;
  try {
    const manifest = await apiRequestJson(
      `experiment_manifest_${expId}`,
      `/api/backtest_v2/experiments/${encodeURIComponent(expId)}/manifest`,
    );
    if (manifest && typeof manifest === 'object') {
      result.manifest = manifest;
      result.artifacts = manifest.artifacts || {};
      return manifest;
    }
  } catch (e) {
    addLog(`manifest 鍔犺浇澶辫触: ${e?.message || e}`);
  }
  return null;
}

async function loadActiveArtifacts() {
  const expId = state.active_exp?.exp_id || state.active_result?.exp_id || null;
  const result = state.active_result;
  if (!expId || !result) return;
  const resultsDir = '';
  state.active_artifacts = null;
  renderLoadingSkeleton();
  await ensureManifestForActiveResult(result);
  const gf = result.artifacts || {};
  const [perfR, navR, funnelR, reasonR, runMetaR, configR, auditR, tradesR, dailyR, symbolPerfR, stockNamesR] = await Promise.all([
    readArtifactWithStatus(resultsDir, gf.perf, 'perf', expId),
    readArtifactWithStatus(resultsDir, gf.nav, 'nav', expId),
    readArtifactWithStatus(resultsDir, gf.funnel, 'funnel', expId),
    readArtifactWithStatus(resultsDir, gf.reason_codes || 'reason_codes.csv', 'reason_codes', expId),
    readArtifactWithStatus(resultsDir, gf.run_meta, 'run_meta', expId),
    readArtifactWithStatus(resultsDir, gf.config, 'config', expId),
    gf.audit ? readArtifactWithStatus(resultsDir, gf.audit, 'audit', expId) : Promise.resolve({ ok: false, key: 'audit', missing: true }),
    gf.trades ? readArtifactWithStatus(resultsDir, gf.trades, 'trades', expId) : Promise.resolve({ ok: false, key: 'trades', missing: true }),
    gf.daily ? readArtifactWithStatus(resultsDir, gf.daily, 'daily', expId) : Promise.resolve({ ok: false, key: 'daily', missing: true }),
    readArtifactWithFallback(resultsDir, gf.symbol_performance || 'symbol_performance.csv', 'symbol_performance', ['symbol_performance.json'], expId),
    readArtifactWithStatus(resultsDir, gf.stock_names || 'stock_names.json', 'stock_names', expId),
  ]);
  const allR = [perfR, navR, funnelR, reasonR, runMetaR, configR, tradesR, dailyR, symbolPerfR, auditR, stockNamesR];
  const optionalKeys = new Set(['trades', 'daily', 'symbol_performance', 'audit', 'stock_names']);
  const missing = allR.filter((x) => !x.ok && !optionalKeys.has(String(x.key || ''))).map((x) => x.key);
  const errors = allR
    .filter((x) => !x.ok && x.error && !optionalKeys.has(String(x.key || '')))
    .map((x) => `${x.key}: ${x.error}`);
  const statusItems = [perfR, navR, funnelR, reasonR, runMetaR, configR]
    .filter((x) => !x.ok)
    .map((x) => ({
      title: '产物缺失',
      message: String(x.key || '') + ' 不可用',
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
    audit: auditR.ok ? auditR.payload?.data || {} : {},
    tradesRows,
    symbolPerformanceRows: symbolPerfRows,
    dailyRows: dailyR.ok ? dailyR.payload?.rows || [] : [],
    marketStates: _parseMarketStates(dailyR.ok ? dailyR.payload?.rows || [] : []),
    stockNames: stockNamesR.ok ? stockNamesR.payload?.data || {} : {},
    missing,
    errors,
  };
  if (typeof syncConfigSourceUI === 'function') syncConfigSourceUI();
  state.symbol_series_cache = {};
  state.symbol_series_loading = false;
  const hasSelected = state.selected_symbol && symbolPerfRows.some((x) => x.symbol === state.selected_symbol);
  if (!hasSelected) state.selected_symbol = symbolPerfRows[0]?.symbol || '';

  // Sync config_draft with loaded experiment config (use original frontend format)
  const loadedConfig = state.active_artifacts?.config;
  const originalWb = loadedConfig?.overrides?.original_workbench_config;
  if (originalWb && typeof originalWb === 'object') {
    try { applyConfigToUI(originalWb); } catch (_) { /* config format mismatch */ }
  }

  refreshConfigPanels();
  if (typeof publishResultsWorkbenchSnapshot === 'function') publishResultsWorkbenchSnapshot();
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
  if (window.resultsWorkbenchBridge?.isMounted?.()) {
    if (typeof publishResultsWorkbenchSnapshot === 'function') publishResultsWorkbenchSnapshot();
    return;
  }
  // Legacy fallback only: symbol ranking is rendered by the Vue workbench when mounted.
  const wrap = byId('wbSymbolPerfWrap');
  const hint = byId('wbSymbolPerfHint');
  const meta = byId('wbAccSymbolPanelMeta');
  if (!wrap) return;
  const allRows = (state.active_artifacts || {}).symbolPerformanceRows || [];
  if (hint) {
    const fb = allRows.filter((r) => r.valuation_fallback_used).length;
    hint.textContent = fb > 0
      ? ('未平仓收益按区间末日收盘价近似估值 (' + String(fb) + ' 个标的使用回溯收盘价)。')
      : '未平仓收益按区间末日收盘价近似估值。';
  }
  const rows = getFilteredSortedSymbolRows();
  if (meta) {
    if (!allRows.length) meta.textContent = '默认收起';
    else if (state.chart_mode === 'symbol' && state.selected_symbol) meta.textContent = '默认收起 | ' + String(state.selected_symbol).toUpperCase() + ' | ' + fmtInt(rows.length) + ' 只';
    else meta.textContent = '默认收起 | ' + fmtInt(rows.length) + ' 只';
  }
  const rowsHtml = !rows.length
    ? '<div class="wb-symbol-grid-empty">暂无个股绩效数据</div>'
    : rows.map((r) => {
    const active = String(state.selected_symbol || '') === String(r.symbol);
    const displayName = stockZh(r.symbol);
    const returnPct = deriveLegacySymbolReturnPct(r);
    const symbolCell = displayName !== r.symbol
      ? (esc(displayName) + '<span class="wb-mini" style="margin-left:6px">' + esc(r.symbol) + '</span>')
      : esc(r.symbol);
    return '<div class="wb-symbol-grid-row' + (active ? ' active' : '') + '" data-symbol="' + esc(r.symbol) + '">' +
      '<div class="wb-symbol-grid-symbol">' + symbolCell + '</div>' +
      '<div class="num">' + pct(returnPct) + '</div>' +
      '<div class="num">' + pct(r.max_drawdown) + '</div>' +
      '<div class="num">' + fmtInt(r.trades) + '</div>' +
      '</div>';
  }).join('');
  wrap.innerHTML = ''
    + '<div class="wb-symbol-grid">'
    + '<div class="wb-symbol-grid-head">'
    + '<div>标的</div>'
    + '<div class="num">收益</div>'
    + '<div class="num">回撤</div>'
    + '<div class="num">交易数</div>'
    + '</div>'
    + rowsHtml
    + '</div>';
  wrap.querySelectorAll('[data-symbol]').forEach((tr) => {
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

function deriveTop10AverageReturn(rows) {
  const values = (Array.isArray(rows) ? rows : [])
    .map((row) => Number(row?.return_pct))
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => b - a)
    .slice(0, 10);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
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

function renderExecutionPanel() {
  const p = state.execution_preview;
  const execStatus = state.api_status?.execution_preview || null;
  if (!state.execution_api_enabled) {
    setTextById('wbExecDateNote', '后端未启用 execution preview');
    setTextById('wbExecCandidates', '候选标的: -');
    setTextById('wbExecTargets', '目标持仓: -');
  } else if (!p) {
    if (execStatus?.status === 'failed') {
      setTextById('wbExecDateNote', '执行接口失败: ' + String(execStatus.error || '未知错误'));
    } else if (execStatus?.status === 'loading') {
      setTextById('wbExecDateNote', '执行接口请求中...');
    } else {
      setTextById('wbExecDateNote', '未生成执行清单（可点击“生成今日执行清单”）');
    }
    setTextById('wbExecCandidates', '候选标的: -');
    setTextById('wbExecTargets', '目标持仓: -');
  } else {
    setTextById('wbExecDateNote', '基准日期=' + String(p.as_of_date_used || '-') + ' (来源=' + String(p.source || '未知') + ')');
    setHtmlById('wbExecCandidates', '候选标的 TopN: ' + (p.candidates || []).map((x) => String(x.rank) + '.' + String(x.symbol) + '(' + num(x.score, 6) + ')').join(' | '));
    setHtmlById('wbExecTargets', '目标持仓: ' + (p.target_positions || []).map((x) => String(x.symbol) + ':' + pct(x.target_weight)).join(' | '));
  }
  // 渲染交易明细表
  renderTradesList();
}

function stockZh(symbol) {
  const names = (state.active_artifacts || {}).stockNames || {};
  const name = names[symbol];
  return name ? String(name) : String(symbol ?? '');
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
    ? ('???? (' + fmtInt(rows.length) + ' ? / ' + esc(String(state.selected_symbol || '').toUpperCase()) + ')')
    : ('???? (' + fmtInt(rows.length) + ' ?)');
  if (!rows.length) {
    const emptyText = totalRows
      ? '?????????????'
      : '?????????';
    return '<div class="wb-mini">' + emptyText + '</div>';
  }
  const labels = ['??', '??', '??', '???', '??', '??', '??', '???', '??', '??', 'Entry Alpha', 'Sleeve', 'Entry Reason', 'Exit Owner'];
  const aligns = ['', '', '', 'num', 'num', 'num', 'num', 'num', 'num', '', '', '', '', ''];
  const header = '<tr>' + labels.map((label, idx) => {
    return '<th' + (aligns[idx] ? ' class="num"' : '') + '>' + esc(label) + '</th>';
  }).join('') + '</tr>';
  const body = rows.map((r) => {
    const isBuy = String(r.side || '').toUpperCase() === 'BUY';
    const sideBadge = isBuy
      ? '<span class="wb-badge-buy">??</span>'
      : '<span class="wb-badge-sell">??</span>';
    const sym = String(r.symbol ?? '');
    const displayName = stockZh(sym);
    const symbolCell = displayName !== sym ? ('<span title="' + esc(sym) + '">' + esc(displayName) + '</span>') : esc(sym);
    const fp = r.fill_price != null ? num(r.fill_price, 3) : num(r.price, 3);
    const comm = r.commission != null ? fmtMoney(r.commission) : '-';
    const stax = r.stamp_tax != null ? fmtMoney(r.stamp_tax) : '-';
    const netAmt = r.net_amount != null ? fmtMoney(r.net_amount) : fmtMoney(r.value);
    return '<tr>'
      + '<td>' + esc(String(r.date ?? '')) + '</td>'
      + '<td>' + symbolCell + '</td>'
      + '<td>' + sideBadge + '</td>'
      + '<td class="num">' + fp + '</td>'
      + '<td class="num">' + fmtInt(r.qty) + '</td>'
      + '<td class="num">' + fmtMoney(r.value) + '</td>'
      + '<td class="num">' + comm + '</td>'
      + '<td class="num">' + stax + '</td>'
      + '<td class="num">' + netAmt + '</td>'
      + '<td>' + esc(reasonZh(r.reason_code)) + '</td>'
      + '<td>' + esc(String(r.entry_alpha_id || '-')) + '</td>'
      + '<td>' + esc(String(r.entry_sleeve_id || '-')) + '</td>'
      + '<td>' + esc(String(r.entry_reason_code || '-')) + '</td>'
      + '<td>' + esc(String(r.exit_owner || '-')) + '</td>'
      + '</tr>';
  }).join('');
  return '<div class="wb-mini" style="margin-bottom:4px">' + title + '</div>'
    + '<div class="wb-table-wrap wb-trades-table-wrap wb-scrollbox"><table class="wb-table"><thead>'
    + header
    + '</thead><tbody>'
    + body
    + '</tbody></table></div>';
}

function _reasonCodeOf(row) {
  return String(row?.code || row?.reason_code || '').toUpperCase();
}

renderPerfPanel = function renderPerfPanelV2() {
  if (window.resultsWorkbenchBridge?.isMounted?.()) {
    if (typeof publishResultsWorkbenchSnapshot === 'function') publishResultsWorkbenchSnapshot();
    return;
  }
  // Legacy fallback only: KPI/chart/report updates are owned by the Vue workbench when mounted.
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
  const top10 = firstValidValue(deriveTop10AverageReturn(art.symbolPerformanceRows || []), p.top10_avg_return_pct, row.top10_avg_return_pct);
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

  const missingMsg = art?.missing?.length ? ('缺失 ' + String(art.missing.length) + ' 个产物，详情见状态中心') : '产物已加载';
  setTextById('wbGroupLoadStatus', missingMsg);

  const period = state.chart_range;
  const isSymbolMode = state.chart_mode === 'symbol' && !!state.selected_symbol;
  const symbolCache = isSymbolMode ? state.symbol_series_cache[state.selected_symbol] : null;
  const symbolOhlc = (isSymbolMode && symbolCache) ? (symbolCache.ohlc || []) : [];
  const symbolLastClose = Number(symbolOhlc[symbolOhlc.length - 1]?.close);
  if (isSymbolMode && !symbolCache) ensureSelectedSymbolSeries(art.navSeries || []);
  const rawMainSeries = (isSymbolMode && symbolCache)
    ? symbolOhlc.map((x) => ({ date: x.time, value: Number(x.close) }))
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
    { mode: isSymbolMode ? 'symbol' : 'portfolio', markers: tradeMarkers, marketStates, suspensionRanges, symbolLastClose },
  );

  const navInfo = navSeries.length
    ? ((isSymbolMode ? ('个股 ' + String(state.selected_symbol || '').toUpperCase()) : '净值') + '=' + String(navSeries.length) + '点')
    : ((isSymbolMode ? '个股序列缺失' : '净值缺失') + '(' + String(art.errors?.find((x) => String(x).startsWith('nav:')) || '未提供') + ')');
  const bmInfo = art.benchmarkError ? ('基准异常=' + String(art.benchmarkError)) : ('基准来源=' + String(art.benchmarkSource || '未知'));
  setHtmlById('wbPerfSeries', navInfo + ' | ' + bmInfo + (state.chart_show_benchmark ? '' : ' | 基准=关闭'));
  if (isSymbolMode) {
    const lastCloseValue = Number(navSeries[navSeries.length - 1]?.value);
    const firstCloseValue = Number(navSeries[0]?.value);
    const lastBenchClose = Number(benchOhlc[benchOhlc.length - 1]?.close);
    const firstBenchClose = Number(benchOhlc[0]?.close);
    const symbolRel = Number.isFinite(lastCloseValue) && Number.isFinite(firstCloseValue) && firstCloseValue > 0
      ? (lastCloseValue / firstCloseValue)
      : Number.NaN;
    const benchRel = state.chart_show_benchmark && Number.isFinite(lastBenchClose) && Number.isFinite(firstBenchClose) && firstBenchClose > 0
      ? (lastBenchClose / firstBenchClose)
      : Number.NaN;
    const symbolInfo = [
      '个股收盘价=' + (Number.isFinite(lastCloseValue) ? (num(lastCloseValue, 2) + '元') : '-'),
      '标的=' + String(state.selected_symbol || '').toUpperCase(),
      Number.isFinite(symbolRel) ? ('个股相对起点=' + num(symbolRel, 2) + 'x') : null,
      Number.isFinite(benchRel) ? ('基准相对起点=' + num(benchRel, 2) + 'x') : null,
    ].filter(Boolean).join(' | ');
    setHtmlById('wbPerfSeries', symbolInfo);
  }
  renderTradesList();
  if (typeof renderAgentMarkdownReport === 'function') renderAgentMarkdownReport();
};

renderTradesList = function renderTradesListV2() {
  if (window.resultsWorkbenchBridge?.isMounted?.()) {
    if (typeof publishResultsWorkbenchSnapshot === 'function') publishResultsWorkbenchSnapshot();
    return;
  }
  // Legacy fallback only: trades panel is rendered by the Vue workbench when mounted.
  const allRows = (state.active_artifacts || {}).tradesRows || [];
  const rows = visibleTradesRows();
  const html = tradesTableHtml(rows, allRows.length);
  const el = byId('wbTradesList');
  if (el) el.innerHTML = html;
  const symbolMode = state.chart_mode === 'symbol' && state.selected_symbol;
  const meta = symbolMode
    ? (String(state.selected_symbol || '').toUpperCase() + ' | ' + fmtInt(rows.length) + ' 条')
    : ('全部交易 ' + fmtInt(rows.length) + ' 条');
  setTextById('wbAccTradesMeta', meta);
};

renderExecutionPanel = function renderExecutionPanelV2() {
  if (window.resultsWorkbenchBridge?.isMounted?.()) {
    if (typeof publishResultsWorkbenchSnapshot === 'function') publishResultsWorkbenchSnapshot();
    return;
  }
  // Legacy fallback only: execution preview stays outside the migrated workbench surface.
  if (!byId('wbExecDateNote') && !byId('wbExecCandidates') && !byId('wbExecTargets')) return;
};

function _finalStageCountPills(items, emptyText = '鏆傛棤鐙珛鍘熷cnt') {
  const normalized = (items || []).filter((item) => {
    const label = String(item?.label || '').trim();
    const value = Number(item?.value);
    return !!label && Number.isFinite(value);
  });
  if (!normalized.length) {
    return '<div class="wb-funnel-row-stats"><span>' + esc(emptyText) + '</span></div>';
  }
  return '<div class="wb-funnel-row-stats">'
    + normalized.map((item) => '<span>' + esc(String(item.label)) + '=' + fmtInt(item.value) + '</span>').join('')
    + '</div>';
}

function _finalStageTrackCard(title, items, emptyText) {
  return '<div class="wb-stage-track-card">'
    + '<div class="wb-stage-track-title">' + esc(title) + '</div>'
    + _finalStageCountPills(items, emptyText)
    + '</div>';
}

function _finalStageClass(stageKey) {
  const key = String(stageKey || '').toLowerCase();
  if (key === 's1') return 'wb-funnel-stage-pool';
  if (key === 's8') return 'wb-funnel-stage-s8';
  if (key === 's9') return 'wb-funnel-stage-exit';
  return 'wb-funnel-stage-buy';
}

function _finalSumDailyInt(dailyRows, key) {
  return (dailyRows || []).reduce((sum, item) => {
    const value = Number(item?.[key]);
    return sum + (Number.isFinite(value) ? value : 0);
  }, 0);
}

function _finalBuildStageRows(art, counters) {
  const buyStageRows = Array.isArray(counters?.buy_stage_funnel) ? counters.buy_stage_funnel : [];
  const dailyRows = Array.isArray(art?.dailyRows) ? art.dailyRows : [];
  const rawSignals = _finalSumDailyInt(dailyRows, 'raw_buy_signal_count');
  const buyCandidates = _finalSumDailyInt(dailyRows, 'buy_candidate_count');
  const buyOrders = Number(counters?.buy_orders_count ?? 0);
  const minHoldBlockCount = Number(counters?.min_hold_block_count ?? 0);
  const cooldownBlockCount = Number(counters?.cooldown_block_count ?? 0);
  const heldDupBlockCount = Math.max(rawSignals - buyCandidates - minHoldBlockCount - cooldownBlockCount, 0);
  const mfRankAppliedDays = Number(counters?.mf_rank_applied_days ?? 0);
  const mfTopkRejectCount = Number(counters?.mf_topk_reject_count ?? 0);
  const rankActuallyApplied = mfRankAppliedDays > 0 || mfTopkRejectCount > 0;

  return buyStageRows.map((rowDef) => {
    const key = String(rowDef?.stage_key || '').toLowerCase();
    if (key === 's4') {
      const inputCount = Number(rowDef?.input_count ?? 0);
      const outputCount = buyCandidates > 0 ? buyCandidates : Number(rowDef?.output_count ?? 0);
      const noRawSignalCount = Math.max(inputCount - rawSignals, 0);
      return {
        ...rowDef,
        input_count: inputCount,
        output_count: outputCount,
        filtered_count: Math.max(inputCount - outputCount, 0),
        note: '可交易股票-日期事件收缩到候选买入；未触发原始买点=' + fmtInt(noRawSignalCount) + '，预筛去重=' + fmtInt(heldDupBlockCount + minHoldBlockCount + cooldownBlockCount),
        raw_items: [
          { label: 'INPUT_CNT', value: inputCount },
          { label: 'KEEP_CNT', value: outputCount },
          { label: 'FILTERED_CNT', value: Math.max(inputCount - outputCount, 0) },
          { label: 'RAW_SIGNAL_CNT', value: rawSignals },
          { label: 'NO_RAW_SIGNAL', value: noRawSignalCount },
          { label: 'HELD_DUP_BLOCK', value: heldDupBlockCount },
          { label: 'MIN_HOLD_BLOCK', value: minHoldBlockCount },
          { label: 'COOLDOWN_BLOCK', value: cooldownBlockCount },
        ],
      };
    }
    if (key === 's5') {
      const inputCount = buyCandidates > 0 ? buyCandidates : Number(rowDef?.input_count ?? 0);
      const outputCount = rankActuallyApplied ? Math.max(inputCount - mfTopkRejectCount, 0) : inputCount;
      return {
        ...rowDef,
        input_count: inputCount,
        output_count: outputCount,
        filtered_count: Math.max(inputCount - outputCount, 0),
        note: rankActuallyApplied
          ? ('排序层实际生效；TopK/多因子排序过滤=' + fmtInt(mfTopkRejectCount))
          : '当前基线未启用独立排序截断，排序层按实际显示为 0 过滤。',
        raw_items: [
          { label: 'INPUT_CNT', value: inputCount },
          { label: 'KEEP_CNT', value: outputCount },
          { label: 'FILTERED_CNT', value: Math.max(inputCount - outputCount, 0) },
          { label: 'MF_RANK_APPLIED_DAYS', value: mfRankAppliedDays },
          { label: 'MF_TOPK_REJECT_CNT', value: mfTopkRejectCount },
        ],
      };
    }
    if (key === 's6') {
      const inputCount = rankActuallyApplied
        ? Math.max((buyCandidates > 0 ? buyCandidates : Number(rowDef?.input_count ?? 0)) - mfTopkRejectCount, 0)
        : (buyCandidates > 0 ? buyCandidates : Number(rowDef?.input_count ?? 0));
      return {
        ...rowDef,
        input_count: inputCount,
        output_count: buyOrders,
        filtered_count: Math.max(inputCount - buyOrders, 0),
        note: '55日突破等入场事件在本层收口为最终实际开仓次数。',
        raw_items: [
          { label: 'INPUT_CNT', value: inputCount },
          { label: 'KEEP_CNT', value: buyOrders },
          { label: 'FILTERED_CNT', value: Math.max(inputCount - buyOrders, 0) },
          { label: 'BUY_ORDER_CNT', value: buyOrders },
          { label: 'ABOVE_SLOW_MA_BLOCK', value: Number(counters?.entry_above_slow_ma_block_count ?? 0) },
          { label: 'SLOPE_BLOCK', value: Number(counters?.entry_slope_block_count ?? 0) },
        ],
      };
    }
    if (key === 's7') {
      return {
        ...rowDef,
        stage_label: 'S7 仓位控制',
        input_count: buyOrders,
        output_count: buyOrders,
        filtered_count: 0,
        note: '仓位控制层；当前基线未稳定输出独立 slot 收缩计数，沿用最终开仓数展示。',
        raw_items: [
          { label: 'INPUT_CNT', value: buyOrders },
          { label: 'KEEP_CNT', value: buyOrders },
          { label: 'FILTERED_CNT', value: 0 },
          { label: 'BUY_ORDER_CNT', value: buyOrders },
          { label: 'AVG_POSITIONS', value: Number(counters?.avg_positions ?? 0) },
          { label: 'MAX_POSITIONS', value: Number(counters?.max_positions ?? 0) },
        ],
      };
    }
    return {
      ...rowDef,
      raw_items: [
        { label: 'INPUT_CNT', value: Number(rowDef?.input_count ?? 0) },
        { label: 'KEEP_CNT', value: Number(rowDef?.output_count ?? 0) },
        { label: 'FILTERED_CNT', value: Number(rowDef?.filtered_count ?? 0) },
      ],
    };
  });
}

function renderUnifiedStageFunnel(stageRows, counters, exitRows) {
  const rows = Array.isArray(stageRows) ? stageRows.map((row) => ({ ...row })) : [];
  if (!rows.length) {
    return '<div class="wb-mini">当前结果尚未提供 stage counters，无法生成统一 9-stage 漏斗。</div>';
  }
  const maxValue = Math.max(1, ...rows.map((row) => Number(row.output_count ?? row.input_count ?? row.filtered_count ?? 0) || 0));
  const pctText = (nume, deno) => {
    const n = Number(nume);
    const d = Number(deno);
    return Number.isFinite(n) && Number.isFinite(d) && d > 0 ? pct(n / d) : '-';
  };

  const body = rows.map((row) => {
    const key = String(row.stage_key || '').toLowerCase();
    const title = String(row.stage_label || row.title || row.stage_key || '阶段');
    let available = row.available !== false;
    let note = String(row.note || (available ? '已接入后端真实计数。' : '当前无独立计数。'));
    let inputCount = Number(row.input_count);
    let outputCount = Number(row.output_count);
    let filteredCount = Number(row.filtered_count);
    let extraHtml = '';
    let rawItems = Array.isArray(row.raw_items) ? row.raw_items : [];

    if (key === 's8') {
      available = true;
      note = '唯一同时涉及买入与卖出的阶段；左侧看建仓约束，右侧看风险侧卖出统计。';
      inputCount = Number.NaN;
      outputCount = Number.NaN;
      filteredCount = Number.NaN;
      rawItems = [];
      extraHtml = '<div class="wb-stage-track-grid">'
        + _finalStageTrackCard('S8 买入侧', [
          { label: 'CASH_SKIP', value: Number(counters?.cash_skip_count ?? 0) },
          { label: 'LOT_SKIP', value: Number(counters?.lot_skip_count ?? 0) },
          { label: 'SINGLE_CAP', value: Number(counters?.cap_hit_single ?? 0) },
          { label: 'INDUSTRY_CAP', value: Number(counters?.cap_hit_industry ?? 0) },
        ], '当前无独立买入约束 cnt')
        + _finalStageTrackCard('S8 卖出侧', [
          { label: 'DD_REDUCED', value: Number(counters?.dd_reduced_count ?? 0) },
          { label: 'DD_SCALE_08', value: Number(counters?.dd_scale_08_count ?? 0) },
          { label: 'DD_SCALE_06', value: Number(counters?.dd_scale_06_count ?? 0) },
          { label: 'DD_FIXED_03', value: Number(counters?.dd_fixed_03_count ?? 0) },
          { label: 'DD_STOP', value: Number(counters?.dd_stop_count ?? 0) },
        ], '当前无独立卖出风险 cnt')
        + '</div>';
    } else if (key === 's9') {
      available = true;
      note = '退出阶段只看卖出链路；按退出原因展示原始 cnt 与占比。';
      inputCount = Number.NaN;
      outputCount = Number.NaN;
      filteredCount = Number.NaN;
      rawItems = [
        { label: 'SELL_ORDER_CNT', value: Number(counters?.sell_orders_count ?? 0) },
        { label: 'CLOSED_TRADE_CNT', value: Number(counters?.closed_trades ?? 0) },
      ];
      const exitReasonItems = (Array.isArray(exitRows) ? exitRows : [])
        .map((item) => ({
          code: _reasonCodeOf(item),
          zh: reasonZh(_reasonCodeOf(item)),
          value: Number(item?.count ?? 0),
        }))
        .filter((item) => item.code && item.value > 0)
        .sort((a, b) => Number(b.value || 0) - Number(a.value || 0));
      const exitTotal = exitReasonItems.reduce((sum, item) => sum + Number(item.value || 0), 0);
      extraHtml = exitReasonItems.length
        ? '<div class="wb-stage-exit-stack"><div class="wb-stage-exit-head">S9 退出原因分布 | 总退出=' + fmtInt(exitTotal) + '</div>'
          + exitReasonItems.map((item) => {
            const ratio = exitTotal > 0 ? item.value / exitTotal : 0;
            return '<div class="wb-stage-exit-row">'
              + '<div class="wb-stage-exit-meta">'
              + '<span class="wb-stage-exit-name">' + esc(item.zh) + ' <span class="wb-stage-exit-code">' + esc(item.code) + '</span></span>'
              + '<span class="wb-stage-exit-count">' + fmtInt(item.value) + ' | ' + pct(ratio) + '</span>'
              + '</div>'
              + '<div class="wb-stage-exit-bar"><span style="width:' + Math.max(6, ratio * 100) + '%"></span></div>'
              + '</div>';
          }).join('')
          + '</div>'
        : '';
    }

    const inputText = Number.isFinite(inputCount) ? fmtInt(inputCount) : '-';
    const outputText = Number.isFinite(outputCount) ? fmtInt(outputCount) : '-';
    const filteredText = Number.isFinite(filteredCount) ? fmtInt(filteredCount) : '-';
    const width = Number.isFinite(outputCount) ? Math.max(6, (outputCount / maxValue) * 100) : 0;

    return '<div class="wb-funnel-row ' + _finalStageClass(key) + (available ? '' : ' wb-funnel-unavailable') + '">'
      + '<div class="wb-funnel-row-head">'
      + '<div class="wb-funnel-row-title">' + esc(title) + '</div>'
      + '<div class="wb-funnel-row-note">' + esc(note) + '</div>'
      + '</div>'
      + '<div class="wb-bar"><span style="width:' + width + '%"></span></div>'
      + '<div class="wb-funnel-row-meta">'
      + '<div><span>输入</span><strong>' + inputText + '</strong></div>'
      + '<div><span>保留</span><strong>' + outputText + '</strong></div>'
      + '<div><span>过滤</span><strong>' + filteredText + '</strong></div>'
      + '</div>'
      + _finalStageCountPills(rawItems, available ? '暂无额外原始 cnt' : '当前无独立原始 cnt')
      + (Number.isFinite(inputCount) ? ('<div class="wb-funnel-row-stats"><span>保留率=' + pctText(outputCount, inputCount) + '</span><span>过滤率=' + pctText(filteredCount, inputCount) + '</span></div>') : '')
      + extraHtml
      + '</div>';
  }).join('');

  const totals = rows.reduce((acc, row) => {
    acc.input += Number(row.input_count || 0);
    acc.output += Number(row.output_count || 0);
    acc.filtered += Number(row.filtered_count || 0);
    return acc;
  }, { input: 0, output: 0, filtered: 0 });

  return '<div class="wb-funnel-scroll wb-scrollbox">'
    + '<div class="wb-funnel-stack">' + body + '</div>'
    + '<div class="wb-funnel-summary">'
    + '<span>stage_cnt=' + fmtInt(rows.length) + '</span>'
    + '<span>input_sum=' + fmtInt(totals.input) + '</span>'
    + '<span>keep_sum=' + fmtInt(totals.output) + '</span>'
    + '<span>filtered_sum=' + fmtInt(totals.filtered) + '</span>'
    + '<span>buy_order_cnt=' + fmtInt(counters?.buy_orders_count ?? 0) + '</span>'
    + '<span>sell_order_cnt=' + fmtInt(counters?.sell_orders_count ?? 0) + '</span>'
    + '</div>'
    + '</div>';
}

renderExplainPanel = function renderExplainPanelFinal() {
  if (window.resultsWorkbenchBridge?.isMounted?.()) {
    if (typeof publishResultsWorkbenchSnapshot === 'function') publishResultsWorkbenchSnapshot();
    return;
  }
  // Legacy fallback only: unified stage funnel is rendered by the Vue workbench when mounted.
  const row = state.active_result || {};
  const art = state.active_artifacts || {};
  if (!row.exp_id && !Object.keys(art || {}).length) {
    setHtmlById('wbBuyFunnel', '<div class="wb-mini">运行实验后显示统一 9-stage 漏斗。</div>');
    setTextById('wbAccBuyFunnelMeta', '等待结果');
    setTextById('wbAccLogsMeta', '状态输出');
    return;
  }
  const counters = art?.run_meta?.counters || row || {};
  const buyStageRows = _finalBuildStageRows(art, counters);
  const buyOrders = Number(counters?.buy_orders_count ?? 0);
  const sellOrders = Number(counters?.sell_orders_count ?? 0);
  const reasonBuckets = reasonByPrefix(art.reasonRows || []);
  const exitRows = reasonBuckets.exit || [];
  setHtmlById('wbBuyFunnel', renderUnifiedStageFunnel(buyStageRows, counters, exitRows));
  setTextById('wbAccBuyFunnelMeta', buyStageRows.length
    ? ('买入 ' + fmtInt(buyOrders) + ' 笔 | 卖出 ' + fmtInt(sellOrders) + ' 笔 | stage=' + fmtInt(buyStageRows.length))
    : '等待后端 stage counters');
  setTextById('wbAccLogsMeta', row.exp_id ? (String(row.exp_id) + ' | ' + String(row.status || '-')) : '状态输出');
};



