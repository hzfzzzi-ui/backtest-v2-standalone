/* artifacts.js: canonical experiment surface consumer and bridge publisher only. */
/* Visible DOM under #wbResultsWorkbenchMount belongs to the Vue results workbench. */
/* Globals used: state, byId, esc, num, pct, fmtInt, setTextById, setHtmlById,
   apiRequestJson, setStatusItems, addLog, renderLoadingSkeleton,
   applyConfigToUI, refreshConfigPanels, publishResultsWorkbenchSnapshot */

async function readExperimentSurface(expId) {
  const normalizedExpId = String(expId || '').trim();
  if (!normalizedExpId) return null;
  if (typeof window.ensureDesktopExperimentSurface === 'function') {
    return window.ensureDesktopExperimentSurface(state, normalizedExpId);
  }
  return apiRequestJson(
    `experiment_surface_${normalizedExpId}`,
    `/api/backtest_v2/experiments/${encodeURIComponent(normalizedExpId)}/surface`,
  );
}

async function readExperimentSurfaceSection(expId, section) {
  const normalizedExpId = String(expId || '').trim();
  const normalizedSection = String(section || '').trim().toLowerCase();
  if (!normalizedExpId || !normalizedSection) return null;
  if (typeof window.ensureDesktopExperimentSurfaceSection === 'function') {
    return window.ensureDesktopExperimentSurfaceSection(state, normalizedExpId, normalizedSection);
  }
  return apiRequestJson(
    `experiment_surface_${normalizedExpId}_${normalizedSection}`,
    `/api/backtest_v2/experiments/${encodeURIComponent(normalizedExpId)}/surface/${encodeURIComponent(normalizedSection)}`,
  );
}

function isSurfaceSectionAvailable(surface, section) {
  return !!surface?.lazy_sections?.[section]?.available;
}

function normalizeRunMetaCounters(metaObj) {
  const meta = metaObj && typeof metaObj === 'object' ? { ...metaObj } : {};
  const counters = meta.counters && typeof meta.counters === 'object' ? { ...meta.counters } : {};
  meta.counters = counters;
  return meta;
}

function normalizeNavRows(rows) {
  const out = [];
  (rows || []).forEach((row) => {
    const date = String(row?.date ?? row?.datetime ?? row?.trade_date ?? '').trim();
    const nav = Number(row?.nav ?? row?.strategy_nav ?? row?.equity ?? row?.portfolio_value ?? row?.value);
    if (!date || !Number.isFinite(nav) || nav <= 0) return;
    out.push({ date, nav });
  });
  out.sort((a, b) => (a.date < b.date ? -1 : 1));
  return out;
}

function _parseJsonObject(value) {
  if (value == null || value === '') return null;
  if (typeof value === 'object') return value;
  try {
    const parsed = JSON.parse(String(value));
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch (_) {
    return null;
  }
}

function _parseFiniteNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function _parseMarketStates(dailyRows, runMeta) {
  const out = [];
  const runRegime = runMeta && typeof runMeta === 'object' ? (runMeta.regime || {}) : {};
  const weeklyModes = new Set(['BULL_MAIN', 'TURN_STRONG', 'LIGHT_TREND', 'TURN_WEAK', 'DEFENSIVE']);
  const defaultEngine = String(
    runRegime.engine
    || runMeta?.report_consistency?.regime_engine
    || 'ma200_legacy',
  ).trim().toLowerCase() || 'ma200_legacy';
  const defaultSemantics = String(
    runRegime.regime_semantics
    || runMeta?.report_consistency?.regime_semantics
    || (defaultEngine === 'market_regime_framework'
      ? 'formal_framework'
      : (defaultEngine === 'weekly_five_state' ? 'weekly_five_state_regime' : 'legacy_price_filter')),
  ).trim().toLowerCase() || 'legacy_price_filter';
  for (const row of dailyRows || []) {
    const date = String(row?.date ?? '').trim();
    const rawState = String(row?.market_state_raw ?? row?.market_state ?? '').trim().toUpperCase();
    const smoothedState = String(row?.market_state_smoothed ?? row?.market_state_5 ?? row?.market_state ?? '').trim().toUpperCase();
    const marketState = String(row?.market_state_5 ?? smoothedState ?? row?.market_state ?? '').trim().toUpperCase();
    const tradeMode = String(row?.trade_mode ?? '').trim().toUpperCase();
    if (!date || !marketState) continue;
    let mode = marketState || tradeMode || 'NO_TRADE_TRANS';
    if (weeklyModes.has(marketState)) {
      mode = marketState;
    } else if (tradeMode === 'TREND_MAIN') {
      mode = marketState === 'BULL' ? 'BULL' : 'TREND_MAIN';
    } else if (tradeMode === 'TREND_LIGHT') {
      if (marketState === 'TRANS_DOWN') mode = 'TRANS_DOWN';
      else if (marketState === 'TRANS_UP') mode = 'TRANS_UP';
      else mode = 'TREND_LIGHT';
    } else if (tradeMode === 'NO_TRADE') {
      mode = marketState === 'BEAR' ? 'BEAR' : 'NO_TRADE';
    }
    const engine = String(row?.regime_engine ?? defaultEngine).trim().toLowerCase() || defaultEngine;
    const semantics = String(row?.regime_semantics ?? defaultSemantics).trim().toLowerCase() || defaultSemantics;
    out.push({
      time: date,
      mode,
      market_state: marketState,
      market_state_raw: rawState || null,
      market_state_smoothed: smoothedState || null,
      trade_mode: tradeMode || null,
      regime_engine: engine,
      regime_semantics: semantics,
      regime_confidence: _parseFiniteNumber(row?.regime_confidence),
      regime_duration_bars: _parseFiniteNumber(row?.regime_duration_bars),
      regime_transition_reason: String(row?.regime_transition_reason ?? '').trim() || null,
      feature_availability: _parseJsonObject(row?.feature_availability_json ?? row?.feature_availability),
    });
  }
  return out;
}

function normalizeSymbolPerformanceRows(rows) {
  const toBool = (value) => {
    const text = String(value ?? '').trim().toLowerCase();
    return ['1', 'true', 'yes', 'y'].includes(text);
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
  return (rows || []).reduce((acc, row) => {
    const symbol = String(row?.symbol ?? '').trim().toLowerCase();
    if (!symbol) return acc;
    const returnPct = Number(deriveReturnPct(row));
    const maxDrawdown = Number(row?.max_drawdown);
    const trades = Number(row?.trades);
    const netPnl = Number(row?.net_pnl);
    const realizedPnl = Number(row?.realized_pnl);
    const buyNotional = Number(row?.buy_notional);
    acc.push({
      symbol,
      return_pct: Number.isFinite(returnPct) ? returnPct : 0,
      max_drawdown: Number.isFinite(maxDrawdown) ? maxDrawdown : 0,
      trades: Number.isFinite(trades) ? trades : 0,
      net_pnl: Number.isFinite(netPnl) ? netPnl : 0,
      realized_pnl: Number.isFinite(realizedPnl) ? realizedPnl : 0,
      buy_notional: Number.isFinite(buyNotional) ? buyNotional : 0,
      unrealized_approx_pnl: Number.isFinite(Number(row?.unrealized_approx_pnl)) ? Number(row.unrealized_approx_pnl) : 0,
      valuation_fallback_used: toBool(row?.valuation_fallback_used),
    });
    return acc;
  }, []);
}

function stockZh(symbol) {
  const names = (state.active_artifacts || {}).stockNames || {};
  return names?.[symbol] ? String(names[symbol]) : String(symbol ?? '');
}

async function loadBenchmarkSeries(navPoints, options = {}) {
  const requestedSymbol = String(options?.symbol || state.config_draft?.universe?.benchmark || '000300.SH').trim();
  const symbol = requestedSymbol || '000300.SH';
  const absolute = !!options?.absolute;
  const start = navPoints?.[0]?.date || state.config_draft?.universe?.start;
  const end = navPoints?.[navPoints.length - 1]?.date || state.config_draft?.universe?.end;
  const url = `/api/backtest_v2/series/benchmark?symbol=${encodeURIComponent(symbol)}&start=${encodeURIComponent(start || '')}&end=${encodeURIComponent(end || '')}&absolute=${absolute ? 'true' : 'false'}`;
  const cacheKey = `series_benchmark_${symbol}_${start || ''}_${end || ''}_${absolute ? 'abs' : 'norm'}`;
  try {
    const payload = await apiRequestJson(cacheKey, url, {
      retryCount: 0,
      suppressStatusOnError: true,
    });
    const raw = Array.isArray(payload?.points) ? payload.points : [];
    const points = normalizeNavRows(raw.map((item) => ({ date: item.date, nav: item.nav })));
    const ohlc = raw.map((item) => ({
      time: item.date,
      open: item.open ?? item.nav,
      high: item.high ?? item.nav,
      low: item.low ?? item.nav,
      close: item.close ?? item.nav,
    }));
    return { points, ohlc, source: 'api', symbol, normalized: payload?.normalized !== false };
  } catch (error) {
    return {
      points: [],
      ohlc: [],
      source: 'api_failed',
      symbol,
      error: String(error?.message || error),
      normalized: !absolute,
    };
  }
}

async function loadSymbolSeries(symbol, navPoints) {
  const normalizedSymbol = String(symbol || '').trim().toLowerCase();
  if (!normalizedSymbol) return { points: [], ohlc: [], source: 'empty', symbol: '' };
  const start = navPoints?.[0]?.date || state.config_draft?.universe?.start;
  const end = navPoints?.[navPoints.length - 1]?.date || state.config_draft?.universe?.end;
  const url = `/api/backtest_v2/series/symbol?symbol=${encodeURIComponent(normalizedSymbol)}&start=${encodeURIComponent(start || '')}&end=${encodeURIComponent(end || '')}`;
  try {
    const payload = await apiRequestJson('series_symbol', url, {
      retryCount: 0,
      suppressStatusOnError: true,
    });
    const raw = Array.isArray(payload?.points) ? payload.points : [];
    const points = normalizeNavRows(raw.map((item) => ({ date: item.date, nav: item.nav })));
    const ohlc = raw.map((item) => ({
      time: item.date,
      open: item.open ?? item.nav,
      high: item.high ?? item.nav,
      low: item.low ?? item.nav,
      close: item.close ?? item.nav,
      suspended: !!item.suspended,
    }));
    const suspensionRanges = [];
    let rangeStart = null;
    let prevDate = null;
    for (const item of raw) {
      if (item.suspended && !rangeStart) rangeStart = item.date;
      if (!item.suspended && rangeStart) {
        suspensionRanges.push({ start: rangeStart, end: prevDate || rangeStart });
        rangeStart = null;
      }
      prevDate = item.date;
    }
    if (rangeStart) suspensionRanges.push({ start: rangeStart, end: prevDate || rangeStart });
    return {
      points,
      ohlc,
      suspensionRanges,
      source: payload?.source || 'api',
      symbol: String(payload?.symbol || normalizedSymbol).toLowerCase(),
    };
  } catch (error) {
    return {
      points: [],
      ohlc: [],
      source: 'api_failed',
      symbol: normalizedSymbol,
      error: String(error?.message || error),
    };
  }
}

function symbolTradeMarkers(symbol, tradesRows) {
  const normalizedSymbol = String(symbol || '').trim().toLowerCase();
  if (!normalizedSymbol) return [];
  const rows = Array.isArray(tradesRows) ? tradesRows : [];
  return rows
    .map((row, index) => ({ row, index }))
    .filter(({ row }) => String(row?.symbol || '').trim().toLowerCase() === normalizedSymbol)
    .filter(({ row }) => String(row?.date || '').trim())
    .map(({ row, index }) => {
      const side = String(row?.side || '').trim().toUpperCase();
      const isBuy = side === 'BUY';
      const isSell = side === 'SELL';
      if (!isBuy && !isSell) return null;
      const qty = _toFiniteNumber(row?.qty);
      const price = _toFiniteNumber(row?.fill_price) ?? _toFiniteNumber(row?.price);
      const labelParts = [isBuy ? 'B' : 'S'];
      if (qty !== null) labelParts.push(String(Math.round(qty)));
      if (price !== null) labelParts.push(num(price, 2));
      return {
        time: String(row.date).slice(0, 10),
        position: isBuy ? 'belowBar' : 'aboveBar',
        color: isBuy ? '#22c55e' : '#ef4444',
        shape: isBuy ? 'arrowUp' : 'arrowDown',
        text: labelParts.join(' '),
        id: `${normalizedSymbol}_${String(row.date)}_${side}_${index}`,
      };
    })
    .filter(Boolean)
    .sort((left, right) => {
      const leftTime = String(left.time || '');
      const rightTime = String(right.time || '');
      if (leftTime !== rightTime) return leftTime < rightTime ? -1 : 1;
      const leftIsBuy = left.position === 'belowBar';
      const rightIsBuy = right.position === 'belowBar';
      if (leftIsBuy !== rightIsBuy) return leftIsBuy ? -1 : 1;
      return String(left.id || '').localeCompare(String(right.id || ''));
    });
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
  (rows || []).forEach((row) => {
    const code = codeOf(row);
    if (code.startsWith('BLOCKED_') || code.startsWith('BLOCK_')) out.blocked.push(row);
    else if (code.startsWith('SKIPPED_') || code.startsWith('SKIP_')) out.skipped.push(row);
    else if (code.includes('EXIT') || code.includes('ATR_') || exitSingles.has(code)) out.exit.push(row);
    else out.other.push(row);
  });
  Object.values(out).forEach((group) => group.sort((a, b) => Number(b.count || 0) - Number(a.count || 0)));
  return out;
}

function _toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function _sumDailyInt(dailyRows, key) {
  return (dailyRows || []).reduce((sum, row) => {
    const value = _toFiniteNumber(row?.[key]);
    return sum + (value === null ? 0 : value);
  }, 0);
}

function buildStageRows(artifacts, counters) {
  const buyStageRows = Array.isArray(artifacts?.funnelRows) && artifacts.funnelRows.length
    ? artifacts.funnelRows
    : (Array.isArray(counters?.buy_stage_funnel) ? counters.buy_stage_funnel : []);
  const dailyRows = Array.isArray(artifacts?.dailyRows) ? artifacts.dailyRows : [];
  const rawSignals = _sumDailyInt(dailyRows, 'raw_buy_signal_count');
  const buyCandidates = _sumDailyInt(dailyRows, 'buy_candidate_count');
  const buyOrders = _toFiniteNumber(counters?.buy_orders_count) ?? 0;
  const minHoldBlockCount = _toFiniteNumber(counters?.min_hold_block_count) ?? 0;
  const cooldownBlockCount = _toFiniteNumber(counters?.cooldown_block_count) ?? 0;
  const heldDupBlockCount = Math.max(rawSignals - buyCandidates - minHoldBlockCount - cooldownBlockCount, 0);
  const mfRankAppliedDays = _toFiniteNumber(counters?.mf_rank_applied_days) ?? 0;
  const mfTopkRejectCount = _toFiniteNumber(counters?.mf_topk_reject_count) ?? 0;
  const rankActuallyApplied = mfRankAppliedDays > 0 || mfTopkRejectCount > 0;

  return buyStageRows.map((row) => {
    const stageKey = String(row?.stage_key || '').toLowerCase();
    const inputCount = _toFiniteNumber(row?.input_count);
    const outputCount = _toFiniteNumber(row?.output_count);
    const filteredCount = _toFiniteNumber(row?.filtered_count);
    if (stageKey === 's4') {
      const noRawSignalCount = inputCount === null ? null : Math.max(inputCount - rawSignals, 0);
      return {
        ...row,
        input_count: inputCount,
        output_count: outputCount,
        filtered_count: filteredCount,
        note: row?.note || `Tradable stock-day events compressed into raw buy signals; no raw trigger ${fmtInt(noRawSignalCount)}, held/cooldown blocks ${fmtInt(heldDupBlockCount + minHoldBlockCount + cooldownBlockCount)}`,
      };
    }
    if (stageKey === 's5') {
      return {
        ...row,
        input_count: inputCount,
        output_count: outputCount,
        filtered_count: filteredCount,
        note: row?.note || (rankActuallyApplied
          ? `Ranking actually applied; top-k truncation ${fmtInt(mfTopkRejectCount)}`
          : 'No independent rank truncation was applied on this baseline.'),
      };
    }
    return {
      ...row,
      input_count: inputCount,
      output_count: outputCount,
      filtered_count: filteredCount,
    };
  });
}

async function loadActiveArtifacts() {
  const expId = state.active_exp?.exp_id || state.active_result?.exp_id || null;
  const result = state.active_result;
  if (!expId || !result) return;

  state.active_artifacts = null;
  state.symbol_series_cache = {};
  state.symbol_series_loading = false;
  renderLoadingSkeleton();

  const surface = await readExperimentSurface(expId);
  if (!surface || typeof surface !== 'object') {
    throw new Error(`experiment surface unavailable: ${expId}`);
  }
  result.surface = surface;
  state.active_manifest = cloneJson(result.manifest || state.active_manifest || { exp_id: expId }) || { exp_id: expId };
  state.active_surface_summary = surface?.summary && typeof surface.summary === 'object'
    ? cloneJson(surface.summary) || null
    : null;
  state.active_asset_context = typeof assetContextFromPayload === 'function'
    ? assetContextFromPayload(surface?.asset_context || surface?.summary || state.active_manifest || {}, 'cn_a_equity')
    : { asset_scope: String(surface?.asset_scope || state.active_manifest?.asset_scope || 'cn_a_equity').trim() || 'cn_a_equity' };
  if (typeof rememberRuntimeSource === 'function') {
    rememberRuntimeSource('experiment', expId, state.active_manifest, state.active_asset_context);
  }

  const requiredSections = ['nav', 'run_meta', 'config'];
  const optionalSections = [];
  const sectionData = {};
  const missing = [];
  const errors = [];
  const statusItems = [];

  const loadSection = async (section, required = false) => {
    if (!isSurfaceSectionAvailable(surface, section)) {
      if (required) {
        missing.push(section);
        statusItems.push({
          title: '结果区缺少 section',
          message: `${section} 不可用`,
          file: section,
          detail: 'surface.lazy_sections reported unavailable',
        });
      }
      return;
    }
    try {
      const payload = await readExperimentSurfaceSection(expId, section);
      sectionData[section] = payload?.data ?? null;
    } catch (error) {
      const detail = String(error?.message || error || '');
      if (required) {
        missing.push(section);
        statusItems.push({
          title: '结果区 section 加载失败',
          message: `${section} 不可用`,
          file: section,
          detail,
        });
      } else {
        errors.push(`${section}: ${detail}`);
      }
    }
  };

  await Promise.all([
    ...requiredSections.map((section) => loadSection(section, true)),
    ...optionalSections.map((section) => loadSection(section, false)),
  ]);

  setStatusItems(statusItems);

  const navRows = normalizeNavRows(Array.isArray(sectionData.nav) ? sectionData.nav : []);
  const benchmark = await loadBenchmarkSeries(navRows);
  const benchmarkPoints = Array.isArray(benchmark?.points) ? benchmark.points : [];
  const dailyRows = Array.isArray(sectionData.daily) ? sectionData.daily : [];
  const symbolStats = Array.isArray(sectionData.symbol_stats) ? sectionData.symbol_stats : [];
  const normalizedRunMeta = normalizeRunMetaCounters(sectionData.run_meta || {});
  const stockNames = sectionData.stock_names && typeof sectionData.stock_names === 'object'
    ? cloneJson(sectionData.stock_names) || {}
    : {};

  state.active_artifacts = {
    perf: surface?.perf && typeof surface.perf === 'object' ? cloneJson(surface.perf) || {} : {},
    audit: surface?.audit && typeof surface.audit === 'object' ? cloneJson(surface.audit) || {} : {},
    nav: navRows,
    navSeries: navRows.map((row) => ({ date: row.date, value: row.nav })),
    benchmarkSeries: benchmarkPoints.map((row) => ({ date: row.date, value: row.nav })),
    benchmarkOhlc: Array.isArray(benchmark?.ohlc) ? benchmark.ohlc : [],
    benchmarkSource: String(benchmark?.source || ''),
    benchmarkError: String(benchmark?.error || ''),
    drawdownSeries: Array.isArray(sectionData.drawdown) ? cloneJson(sectionData.drawdown) || [] : [],
    run_meta: normalizedRunMeta,
    funnelRows: Array.isArray(sectionData.stage_funnel) ? sectionData.stage_funnel : [],
    reasonRows: Array.isArray(sectionData.reason_codes) ? sectionData.reason_codes : [],
    config: sectionData.config && typeof sectionData.config === 'object' ? cloneJson(sectionData.config) : null,
    tradesRows: Array.isArray(sectionData.trades) ? sectionData.trades : [],
    dailyRows,
    marketStates: _parseMarketStates(dailyRows, normalizedRunMeta),
    symbolPerformanceRows: normalizeSymbolPerformanceRows(symbolStats),
    stockNames,
    surfaceSummary: surface?.summary && typeof surface.summary === 'object' ? cloneJson(surface.summary) || {} : {},
    surfaceLazySections: cloneJson(surface?.lazy_sections) || {},
    machineOutputs: cloneJson(surface?.machine_outputs) || {},
    humanOutputs: cloneJson(surface?.human_outputs) || {},
    missing,
    errors,
  };

  const loadedConfig = state.active_artifacts?.config;
  const originalWorkbenchConfig = loadedConfig?.overrides?.original_workbench_config;
  if (originalWorkbenchConfig && typeof originalWorkbenchConfig === 'object') {
    try {
      applyConfigToUI(originalWorkbenchConfig);
    } catch (_) {
      // Ignore incompatible historical payloads in the UI bridge.
    }
  }

  const hasSelectedSymbol = state.selected_symbol
    && state.active_artifacts.symbolPerformanceRows.some((row) => row.symbol === state.selected_symbol);
  if (!hasSelectedSymbol) {
    state.selected_symbol = state.active_artifacts.symbolPerformanceRows[0]?.symbol || '';
  }

  if (typeof syncLoadedSourceUI === 'function') syncLoadedSourceUI();
  if (typeof syncLoadHint === 'function') syncLoadHint(expId);
  refreshConfigPanels();
}

function renderSymbolPerformancePanel() {
}

function renderExecutionPanel() {
  const preview = state.execution_preview;
  const execStatus = state.api_status?.execution_preview || null;
  if (!state.execution_api_enabled) {
    setTextById('wbExecDateNote', '后端未启用 execution preview');
    setTextById('wbExecCandidates', '候选标的: -');
    setTextById('wbExecTargets', '目标持仓: -');
    return;
  }
  if (!preview) {
    if (execStatus?.status === 'failed') {
      setTextById('wbExecDateNote', `执行接口失败: ${String(execStatus.error || '未知错误')}`);
    } else if (execStatus?.status === 'loading') {
      setTextById('wbExecDateNote', '执行接口请求中...');
    } else {
      setTextById('wbExecDateNote', '未生成执行清单（可点击“生成今日执行清单”）');
    }
    setTextById('wbExecCandidates', '候选标的: -');
    setTextById('wbExecTargets', '目标持仓: -');
    return;
  }
  setTextById('wbExecDateNote', `基准日期=${String(preview.as_of_date_used || '-')} (来源=${String(preview.source || '未知')})`);
  setHtmlById(
    'wbExecCandidates',
    `候选标的 TopN: ${(preview.candidates || []).map((item) => `${item.rank}.${item.symbol}(${num(item.score, 6)})`).join(' | ')}`,
  );
  setHtmlById(
    'wbExecTargets',
    `目标持仓: ${(preview.target_positions || []).map((item) => `${item.symbol}:${pct(item.target_weight)}`).join(' | ')}`,
  );
}

function renderPerfPanel() {
}

function renderTradesList() {
}

function renderExplainPanel() {
}
