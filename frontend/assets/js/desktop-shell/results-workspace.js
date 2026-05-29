/* desktop-shell/results-workspace.js: desktop shell owner for results snapshot store, canonical surface hydration, and Vue workbench handoff. */
/* Standalone legacy bridge and artifact scripts have exited the main load chain; desktop shell now owns this bridge contract. */
(function initResultsWorkbenchBridge(globalScope) {
  const listeners = new Set();

  function shallowClone(value) {
    if (Array.isArray(value)) return value.slice();
    if (value && typeof value === 'object') return { ...value };
    return value;
  }

  function createEmptySnapshot() {
    return {
      active: false,
      source: {
        kind: '',
        id: '',
      },
      result: null,
      artifacts: null,
      view: {
        chartMode: 'portfolio',
        chartRange: 'D',
        showBenchmark: true,
        symbolFilter: '',
        symbolSort: 'return_desc',
        selectedSymbol: '',
        openPanels: {},
      },
      updatedAt: null,
    };
  }

  const bridge = {
    snapshot: createEmptySnapshot(),
    mounted: false,
    subscribe(listener) {
      if (typeof listener !== 'function') return function noop() {};
      listeners.add(listener);
      try {
        listener(bridge.snapshot);
      } catch (_) {
        // subscriber failure should not break bridge setup
      }
      return function unsubscribe() {
        listeners.delete(listener);
      };
    },
    getSnapshot() {
      return bridge.snapshot;
    },
    setSnapshot(nextSnapshot) {
      const base = createEmptySnapshot();
      bridge.snapshot = {
        ...base,
        ...(nextSnapshot || {}),
        source: {
          ...base.source,
          ...(shallowClone(nextSnapshot?.source || {}) || {}),
        },
        view: {
          ...base.view,
          ...(shallowClone(nextSnapshot?.view || {}) || {}),
          openPanels: {
            ...base.view.openPanels,
            ...(shallowClone(nextSnapshot?.view?.openPanels || {}) || {}),
          },
        },
        updatedAt: new Date().toISOString(),
      };
      bridge.emit();
    },
    patchViewState(patch) {
      bridge.snapshot = {
        ...bridge.snapshot,
        view: {
          ...bridge.snapshot.view,
          ...(shallowClone(patch || {}) || {}),
          openPanels: {
            ...(bridge.snapshot.view?.openPanels || {}),
            ...(shallowClone(patch?.openPanels || {}) || {}),
          },
        },
        updatedAt: new Date().toISOString(),
      };
      bridge.emit();
    },
    clear() {
      bridge.snapshot = createEmptySnapshot();
      bridge.snapshot.updatedAt = new Date().toISOString();
      bridge.emit();
    },
    setMounted(value) {
      bridge.mounted = !!value;
      bridge.emit();
    },
    isMounted() {
      return !!bridge.mounted;
    },
    emit() {
      const payload = bridge.snapshot;
      listeners.forEach((listener) => {
        try {
          listener(payload, { mounted: !!bridge.mounted });
        } catch (_) {
          // listener failures are isolated
        }
      });
    },
  };

  globalScope.resultsWorkbenchBridge = bridge;
})(window);

/* Canonical experiment surface consumer and workbench snapshot hydrator. */
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

function cloneJson(value) {
  if (Array.isArray(value)) return value.slice();
  if (value && typeof value === 'object') return { ...value };
  return value;
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
    const stockNav = _toFiniteNumber(row?.stock_nav);
    const etfNav = _toFiniteNumber(row?.etf_nav);
    out.push({
      date,
      nav,
      ...(stockNav !== null ? { stock_nav: stockNav } : {}),
      ...(etfNav !== null ? { etf_nav: etfNav } : {}),
    });
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
      volume: Number.isFinite(Number(item.volume)) ? Number(item.volume) : (Number.isFinite(Number(item.amount)) ? Number(item.amount) : null),
      amount: Number.isFinite(Number(item.amount)) ? Number(item.amount) : null,
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

function tradeMarkers(rows, options = {}) {
  const normalizedSymbol = String(options?.symbol || '').trim().toLowerCase();
  const comboMode = !!options?.combo;
  const navRows = Array.isArray(options?.navRows) ? options.navRows : [];
  const navRowByDate = new Map();
  navRows.forEach((row) => {
    const date = String(row?.date || row?.time || '').trim().slice(0, 10);
    if (date) navRowByDate.set(date, row);
  });
  const parseTradeMeta = (row) => _parseJsonObject(row?.meta_json) || {};
  const resolveMetaWeight = (meta) => {
    const candidates = [
      _toFiniteNumber(meta?.target_weight),
      _toFiniteNumber(meta?.final_target_weight),
      _toFiniteNumber(meta?.requested_target_weight),
    ];
    return candidates.find((value) => value !== null && value >= 0) ?? null;
  };
  const resolveComboSleeveWeight = (row, navRow) => {
    const sleeveId = String(row?.sleeve_id || row?.entry_sleeve_id || '').trim().toLowerCase();
    if (!navRow || !sleeveId) return null;
    if (sleeveId.includes('stock')) return _toFiniteNumber(navRow?.stock_weight);
    if (sleeveId.includes('etf')) return _toFiniteNumber(navRow?.etf_weight);
    return null;
  };
  const formatWeightText = (value) => {
    if (!Number.isFinite(value) || value < 0) return '';
    if (value >= 0.9995) return '100%';
    return `${(value * 100).toFixed(1).replace(/\.0$/, '')}%`;
  };
  const mergeMarkersByDay = (markers) => {
    const grouped = new Map();
    (Array.isArray(markers) ? markers : []).forEach((marker) => {
      const time = String(marker?.time || '').trim();
      const side = String(marker?.side || '').trim().toUpperCase();
      if (!time || !side) return;
      const key = `${time}|${side}`;
      if (!grouped.has(key)) {
        grouped.set(key, {
          time,
          side,
          position: marker.position,
          color: marker.color,
          shape: marker.shape,
          symbolSet: new Set(),
          totalWeight: 0,
          weightCount: 0,
          count: 0,
        });
      }
      const bucket = grouped.get(key);
      bucket.count += 1;
      const symbol = String(marker?.symbol || '').trim().toLowerCase();
      if (symbol) bucket.symbolSet.add(symbol);
      if (Number.isFinite(marker?.weight) && marker.weight >= 0) {
        bucket.totalWeight += marker.weight;
        bucket.weightCount += 1;
      }
    });
    return Array.from(grouped.values())
      .map((bucket) => {
        const symbol = bucket.symbolSet.size === 1 ? Array.from(bucket.symbolSet)[0] : '';
        const mergedWeight = bucket.weightCount ? bucket.totalWeight : null;
        return {
          time: bucket.time,
          position: bucket.position,
          color: bucket.color,
          shape: bucket.shape,
          text: formatWeightText(mergedWeight),
          id: `${symbol || 'ALL'}_${bucket.time}_${bucket.side}_${bucket.count}`,
          side: bucket.side,
          symbol,
          count: bucket.count,
        };
      })
      .sort((left, right) => {
        const leftTime = String(left.time || '');
        const rightTime = String(right.time || '');
        if (leftTime !== rightTime) return leftTime < rightTime ? -1 : 1;
        const leftIsBuy = left.position === 'belowBar';
        const rightIsBuy = right.position === 'belowBar';
        if (leftIsBuy !== rightIsBuy) return leftIsBuy ? -1 : 1;
        return String(left.id || '').localeCompare(String(right.id || ''));
      });
  };
  const inputRows = Array.isArray(rows) ? rows : [];
  return mergeMarkersByDay(inputRows
    .map((row, index) => ({ row, index }))
    .filter(({ row }) => !normalizedSymbol || String(row?.symbol || '').trim().toLowerCase() === normalizedSymbol)
    .filter(({ row }) => String(row?.date || '').trim())
    .map(({ row, index }) => {
      const side = String(row?.side || '').trim().toUpperCase();
      const isBuy = side === 'BUY';
      const isSell = side === 'SELL';
      if (!isBuy && !isSell) return null;
      const date = String(row.date).slice(0, 10);
      const meta = parseTradeMeta(row);
      const metaWeight = resolveMetaWeight(meta);
      const navRow = navRowByDate.get(date) || null;
      const sleeveWeight = comboMode ? resolveComboSleeveWeight(row, navRow) : null;
      const displayWeight = (comboMode && metaWeight !== null && sleeveWeight !== null)
        ? (metaWeight * sleeveWeight)
        : metaWeight;
      return {
        time: date,
        position: isBuy ? 'belowBar' : 'aboveBar',
        color: isBuy ? '#22c55e' : '#ef4444',
        shape: isBuy ? 'arrowUp' : 'arrowDown',
        text: formatWeightText(displayWeight),
        weight: Number.isFinite(displayWeight) && displayWeight >= 0 ? displayWeight : null,
        id: `${normalizedSymbol || 'ALL'}_${String(row.date)}_${side}_${index}`,
        side,
        symbol: String(row?.symbol || '').trim().toLowerCase(),
      };
    })
    .filter(Boolean));
}

function symbolTradeMarkers(symbol, tradesRows, options = {}) {
  return tradeMarkers(tradesRows, { ...options, symbol });
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
    ? assetContextFromPayload(
      surface?.asset_context || surface?.summary || state.active_manifest || {},
      resolvePreferredAssetScope(surface?.asset_scope || state.active_manifest?.asset_scope),
    )
    : { asset_scope: resolvePreferredAssetScope(surface?.asset_scope || state.active_manifest?.asset_scope) };
  if (typeof syncAssetAwareShell === 'function') syncAssetAwareShell(state.active_asset_context);
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
          title: '结果分区缺失',
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
          title: '结果分区加载失败',
          message: `${section} 加载失败`,
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

  const normalizedRunMeta = normalizeRunMetaCounters(sectionData.run_meta || {});
  const assetRole = String(normalizedRunMeta?.data?.asset_role || '').trim().toLowerCase();
  const executionShell = String(surface?.summary?.execution_shell || '').trim().toLowerCase();
  const warmupSections = ['drawdown', 'stage_funnel', 'trades', 'daily', 'reason_codes', 'stock_names', 'symbol_stats'];
  if (
    assetRole === 'research_combo'
    || assetRole === 'unified_multi_sleeve_combo'
    || executionShell === 'read_only_combo'
    || executionShell === 'unified_combo_phase1'
  ) {
    warmupSections.push('combo_truth');
  }

  setStatusItems(statusItems);

  const dailyRows = Array.isArray(sectionData.daily) ? sectionData.daily : [];
  const symbolStats = Array.isArray(sectionData.symbol_stats) ? sectionData.symbol_stats : [];
  const navRows = normalizeNavRows(Array.isArray(sectionData.nav) ? sectionData.nav : []);
  const isResearchCombo = String(normalizedRunMeta?.data?.asset_role || '').trim().toLowerCase() === 'research_combo';
  const comboTruth = sectionData.combo_truth && typeof sectionData.combo_truth === 'object'
    ? cloneJson(sectionData.combo_truth) || null
    : null;
  const benchmark = isResearchCombo ? { points: [], ohlc: [], source: 'skipped_research_combo', symbol: '' } : { points: [], ohlc: [], source: 'loading', symbol: '' };
  const benchmarkPoints = Array.isArray(benchmark?.points) ? benchmark.points : [];
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
    comboTruth,
  };

  const activeExperimentMatches = () => String(state.active_result?.exp_id || state.active_exp?.exp_id || '').trim() === String(expId || '').trim();
  const refreshWarmArtifacts = () => {
    if (!activeExperimentMatches()) return;
    if (typeof renderRightInspector === 'function') renderRightInspector();
  };

  void (async () => {
    await Promise.all(warmupSections.map((section) => loadSection(section, false)));
    if (!activeExperimentMatches() || !state.active_artifacts) return;
    const warmedDailyRows = Array.isArray(sectionData.daily) ? sectionData.daily : [];
    const warmedSymbolStats = Array.isArray(sectionData.symbol_stats) ? sectionData.symbol_stats : [];
    const warmedComboTruth = sectionData.combo_truth && typeof sectionData.combo_truth === 'object'
      ? cloneJson(sectionData.combo_truth) || null
      : null;
    state.active_artifacts.drawdownSeries = Array.isArray(sectionData.drawdown) ? cloneJson(sectionData.drawdown) || [] : [];
    state.active_artifacts.funnelRows = Array.isArray(sectionData.stage_funnel) ? sectionData.stage_funnel : [];
    state.active_artifacts.reasonRows = Array.isArray(sectionData.reason_codes) ? sectionData.reason_codes : [];
    state.active_artifacts.tradesRows = Array.isArray(sectionData.trades) ? sectionData.trades : [];
    state.active_artifacts.dailyRows = warmedDailyRows;
    state.active_artifacts.marketStates = _parseMarketStates(warmedDailyRows, normalizedRunMeta);
    state.active_artifacts.symbolPerformanceRows = normalizeSymbolPerformanceRows(warmedSymbolStats);
    state.active_artifacts.stockNames = sectionData.stock_names && typeof sectionData.stock_names === 'object'
      ? cloneJson(sectionData.stock_names) || {}
      : {};
    state.active_artifacts.comboTruth = warmedComboTruth;
    const hasSelectedSymbol = state.selected_symbol
      && state.active_artifacts.symbolPerformanceRows.some((row) => row.symbol === state.selected_symbol);
    if (!hasSelectedSymbol) {
      state.selected_symbol = state.active_artifacts.symbolPerformanceRows[0]?.symbol || '';
    }
    refreshWarmArtifacts();
  })();

  if (!isResearchCombo && navRows.length) {
    void (async () => {
      const warmedBenchmark = await loadBenchmarkSeries(navRows);
      if (!activeExperimentMatches() || !state.active_artifacts) return;
      const warmedBenchmarkPoints = Array.isArray(warmedBenchmark?.points) ? warmedBenchmark.points : [];
      state.active_artifacts.benchmarkSeries = warmedBenchmarkPoints.map((row) => ({ date: row.date, value: row.nav }));
      state.active_artifacts.benchmarkOhlc = Array.isArray(warmedBenchmark?.ohlc) ? warmedBenchmark.ohlc : [];
      state.active_artifacts.benchmarkSource = String(warmedBenchmark?.source || '');
      state.active_artifacts.benchmarkError = String(warmedBenchmark?.error || '');
      refreshWarmArtifacts();
    })();
  }


  const loadedConfig = state.active_artifacts?.config;
  const comboAwareWorkbenchConfig = loadedConfig?.overrides?.workbench_config;
  const originalWorkbenchConfig = loadedConfig?.overrides?.original_workbench_config;
  const configIsComboRuntime = Boolean(
    comboAwareWorkbenchConfig?.unified_runtime?.enabled
    || String(normalizedRunMeta?.data?.asset_role || '').trim().toLowerCase() === 'research_combo'
    || String(normalizedRunMeta?.data?.asset_role || '').trim().toLowerCase() === 'unified_multi_sleeve_combo',
  );
  const workbenchConfigToApply = configIsComboRuntime
    ? (state.loaded_source_config || comboAwareWorkbenchConfig || null)
    : (comboAwareWorkbenchConfig || originalWorkbenchConfig || null);
  if (workbenchConfigToApply && typeof workbenchConfigToApply === 'object') {
    try {
      applyConfigToUI(workbenchConfigToApply);
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
  if (typeof syncAssetAwareShell === 'function') syncAssetAwareShell();
}

function renderSymbolPerformancePanel() {
}

function renderExecutionPanel() {
  const preview = state.execution_preview;
  const execStatus = state.api_status?.execution_preview || null;
  if (!state.execution_api_enabled) {
    setTextById('wbExecDateNote', '鍚庣鏈惎鐢?execution preview');
    setTextById('wbExecCandidates', '鍊欓€夋爣鐨? -');
    setTextById('wbExecTargets', '鐩爣鎸佷粨: -');
    return;
  }
  if (!preview) {
    if (execStatus?.status === 'failed') {
      setTextById('wbExecDateNote', `鎵ц鎺ュ彛澶辫触: ${String(execStatus.error || '鏈煡閿欒')}`);
    } else if (execStatus?.status === 'loading') {
      setTextById('wbExecDateNote', '鎵ц鎺ュ彛璇锋眰涓?..');
    } else {
      setTextById('wbExecDateNote', '鏈敓鎴愭墽琛屾竻鍗曪紙鍙偣鍑烩€滅敓鎴愪粖鏃ユ墽琛屾竻鍗曗€濓級');
    }
    setTextById('wbExecCandidates', '鍊欓€夋爣鐨? -');
    setTextById('wbExecTargets', '鐩爣鎸佷粨: -');
    return;
  }
  setTextById('wbExecDateNote', `鍩哄噯鏃ユ湡=${String(preview.as_of_date_used || '-')} (鏉ユ簮=${String(preview.source || '鏈煡')})`);
  setHtmlById(
    'wbExecCandidates',
    `鍊欓€夋爣鐨?TopN: ${(preview.candidates || []).map((item) => `${item.rank}.${item.symbol}(${num(item.score, 6)})`).join(' | ')}`,
  );
  setHtmlById(
    'wbExecTargets',
    `鐩爣鎸佷粨: ${(preview.target_positions || []).map((item) => `${item.symbol}:${pct(item.target_weight)}`).join(' | ')}`,
  );
}

function renderPerfPanel() {
}

function renderTradesList() {
}

function renderExplainPanel() {
}

/* Canonical experiment surface fetch and snapshot merge owner. */
(function initDesktopResultsSurfaceOwner(globalScope) {
  const ALLOWED_LAZY_SECTIONS = [
    'nav',
    'drawdown',
    'symbol_stats',
    'stage_funnel',
    'run_meta',
    'config',
    'trades',
    'daily',
    'reason_codes',
    'stock_names',
    'combo_truth',
  ];
  let publishRevision = 0;

  function bridgeCloneJson(value) {
    if (Array.isArray(value)) return value.slice();
    if (value && typeof value === 'object') return { ...value };
    return value;
  }

  function getDesktopResultsWorkbenchBridge() {
    const bridge = globalScope.resultsWorkbenchBridge;
    return bridge && typeof bridge === 'object' ? bridge : null;
  }

  function currentExperimentId(state) {
    return String(state?.active_result?.exp_id || state?.active_exp?.exp_id || '').trim();
  }

  function ensureDesktopSurfaceRuntime(state) {
    if (!state || typeof state !== 'object') {
      return { main: { expId: '', payload: null, promise: null }, sections: {} };
    }
    if (!state.__desktopSurfaceRuntime || typeof state.__desktopSurfaceRuntime !== 'object') {
      state.__desktopSurfaceRuntime = {};
    }
    const holder = state.__desktopSurfaceRuntime;
    if (!holder.main || typeof holder.main !== 'object') {
      holder.main = { expId: '', payload: null, promise: null };
    }
    if (!holder.sections || typeof holder.sections !== 'object') {
      holder.sections = {};
    }
    const activeExpId = currentExperimentId(state);
    if (holder.main.expId && activeExpId && holder.main.expId !== activeExpId) {
      holder.main = { expId: activeExpId, payload: null, promise: null };
      holder.sections = {};
    } else if (!holder.main.expId) {
      holder.main.expId = activeExpId;
    }
    return holder;
  }

  function clearDesktopResultsWorkbenchState(state) {
    if (!state || typeof state !== 'object') return;
    state.__desktopSurfaceRuntime = null;
  }

  async function fetchJson(tag, url) {
    if (typeof globalScope.desktopApiAdapter?.requestJson === 'function') {
      return globalScope.desktopApiAdapter.requestJson(tag, url);
    }
    if (typeof globalScope.sharedApiRequestJson === 'function') {
      return globalScope.sharedApiRequestJson(tag, url);
    }
    if (typeof globalScope.apiRequestJson === 'function') {
      return globalScope.apiRequestJson(tag, url);
    }
    throw new Error('shared api adapter is unavailable');
  }

  function normalizeLazySections(sections) {
    const requested = Array.isArray(sections) ? sections : [];
    const unique = [];
    requested.forEach((section) => {
      const normalized = String(section || '').trim().toLowerCase();
      if (!ALLOWED_LAZY_SECTIONS.includes(normalized) || unique.includes(normalized)) return;
      unique.push(normalized);
      if (normalized === 'nav' && !unique.includes('drawdown')) unique.push('drawdown');
    });
    return unique;
  }

  function pushLazySection(sections, name) {
    const normalized = String(name || '').trim().toLowerCase();
    if (!ALLOWED_LAZY_SECTIONS.includes(normalized) || sections.includes(normalized)) return;
    sections.push(normalized);
    if (normalized === 'nav' && !sections.includes('drawdown')) sections.push('drawdown');
  }

  function resolveLazySectionsForSnapshot(snapshot, sections) {
    const resolved = normalizeLazySections(sections);
    const view = snapshot?.view && typeof snapshot.view === 'object' ? snapshot.view : {};
    const openPanels = view?.openPanels && typeof view.openPanels === 'object' ? view.openPanels : {};
    if (snapshot?.active) {
      pushLazySection(resolved, 'nav');
      pushLazySection(resolved, 'config');
      pushLazySection(resolved, 'daily');
    }
    if (String(view.chartMode || '').trim().toLowerCase() === 'symbol') {
      pushLazySection(resolved, 'symbol_stats');
      pushLazySection(resolved, 'stock_names');
      pushLazySection(resolved, 'trades');
    }
    if (openPanels.symbolPanel) {
      pushLazySection(resolved, 'symbol_stats');
      pushLazySection(resolved, 'stock_names');
    }
    if (openPanels.funnelPanel) {
      pushLazySection(resolved, 'stage_funnel');
      pushLazySection(resolved, 'run_meta');
      pushLazySection(resolved, 'reason_codes');
      pushLazySection(resolved, 'daily');
    }
    if (openPanels.tradesPanel) {
      pushLazySection(resolved, 'trades');
      pushLazySection(resolved, 'stock_names');
    }
    return resolved;
  }

  async function ensureDesktopExperimentSurface(state, expId) {
    const normalizedExpId = String(expId || '').trim();
    if (!normalizedExpId) return null;
    const runtime = ensureDesktopSurfaceRuntime(state);
    if (runtime.main.expId === normalizedExpId && runtime.main.payload) {
      return bridgeCloneJson(runtime.main.payload);
    }
    if (runtime.main.expId === normalizedExpId && runtime.main.promise) {
      const payload = await runtime.main.promise;
      return bridgeCloneJson(payload);
    }
    runtime.main.expId = normalizedExpId;
    runtime.main.payload = null;
    runtime.sections = {};
    runtime.main.promise = (async () => {
      try {
        const payload = await fetchJson(
          `experiment_surface_${normalizedExpId}`,
          `/api/backtest_v2/experiments/${encodeURIComponent(normalizedExpId)}/surface`,
        );
        runtime.main.payload = payload && typeof payload === 'object' ? payload : null;
        return runtime.main.payload;
      } finally {
        runtime.main.promise = null;
      }
    })();
    const payload = await runtime.main.promise;
    return bridgeCloneJson(payload);
  }

  async function ensureDesktopExperimentSurfaceSection(state, expId, section) {
    const normalizedExpId = String(expId || '').trim();
    const normalizedSection = String(section || '').trim().toLowerCase();
    if (!normalizedExpId || !ALLOWED_LAZY_SECTIONS.includes(normalizedSection)) return null;
    const runtime = ensureDesktopSurfaceRuntime(state);
    if (runtime.main.expId !== normalizedExpId) {
      runtime.main = { expId: normalizedExpId, payload: null, promise: null };
      runtime.sections = {};
    }
    if (!runtime.sections[normalizedSection] || typeof runtime.sections[normalizedSection] !== 'object') {
      runtime.sections[normalizedSection] = { payload: null, promise: null };
    }
    const cache = runtime.sections[normalizedSection];
    if (cache.payload) return bridgeCloneJson(cache.payload);
    if (cache.promise) {
      const payload = await cache.promise;
      return bridgeCloneJson(payload);
    }
    cache.promise = (async () => {
      try {
        const payload = await fetchJson(
          `experiment_surface_${normalizedExpId}_${normalizedSection}`,
          `/api/backtest_v2/experiments/${encodeURIComponent(normalizedExpId)}/surface/${encodeURIComponent(normalizedSection)}`,
        );
        cache.payload = payload && typeof payload === 'object' ? payload : null;
        return cache.payload;
      } finally {
        cache.promise = null;
      }
    })();
    const payload = await cache.promise;
    return bridgeCloneJson(payload);
  }

  function normalizeNavSectionData(rows) {
    return (Array.isArray(rows) ? rows : [])
      .map((row) => ({
        date: String(row?.date || '').trim().slice(0, 10),
        nav: Number(row?.nav),
        stock_nav: Number(row?.stock_nav),
        etf_nav: Number(row?.etf_nav),
      }))
      .filter((row) => row.date && Number.isFinite(row.nav) && row.nav > 0)
      .map((row) => ({
        date: row.date,
        nav: row.nav,
        ...(Number.isFinite(row.stock_nav) && row.stock_nav > 0 ? { stock_nav: row.stock_nav } : {}),
        ...(Number.isFinite(row.etf_nav) && row.etf_nav > 0 ? { etf_nav: row.etf_nav } : {}),
      }));
  }

  function normalizeDrawdownSectionData(rows) {
    return (Array.isArray(rows) ? rows : [])
      .map((row) => ({
        date: String(row?.date || '').trim().slice(0, 10),
        value: Number(row?.drawdown),
      }))
      .filter((row) => row.date && Number.isFinite(row.value));
  }

  function normalizeSymbolStatsSectionData(rows) {
    const rawRows = Array.isArray(rows) ? rows : [];
    if (typeof globalScope.normalizeSymbolPerformanceRows === 'function') {
      return bridgeCloneJson(globalScope.normalizeSymbolPerformanceRows(rawRows)) || [];
    }
    return bridgeCloneJson(rawRows) || [];
  }

  function mergeDesktopSurfaceIntoSnapshot(snapshot, surface) {
    const nextSnapshot = bridgeCloneJson(snapshot) || {};
    const summary = surface && typeof surface.summary === 'object' ? bridgeCloneJson(surface.summary) : {};
    const assetContext = bridgeCloneJson(surface?.asset_context || summary?.asset_context || nextSnapshot.assetContext || {}) || {};
    const artifacts = nextSnapshot.artifacts && typeof nextSnapshot.artifacts === 'object'
      ? { ...nextSnapshot.artifacts }
      : {};
    artifacts.perf = {
      ...(artifacts.perf || {}),
      ...((surface && typeof surface.perf === 'object') ? bridgeCloneJson(surface.perf) : {}),
    };
    artifacts.audit = {
      ...(artifacts.audit || {}),
      ...((surface && typeof surface.audit === 'object') ? bridgeCloneJson(surface.audit) : {}),
    };
    artifacts.surfaceSummary = summary;
    artifacts.assetContext = assetContext;
    artifacts.machineOutputs = bridgeCloneJson(surface?.machine_outputs) || {};
    artifacts.humanOutputs = bridgeCloneJson(surface?.human_outputs) || {};
    artifacts.surfaceLazySections = bridgeCloneJson(surface?.lazy_sections) || {};
    nextSnapshot.surface = bridgeCloneJson(surface) || null;
    nextSnapshot.assetContext = assetContext;
    nextSnapshot.result = {
      ...(nextSnapshot.result || {}),
      ...(summary.exp_id ? { exp_id: summary.exp_id } : {}),
      ...(summary.status ? { status: summary.status } : {}),
      surface_summary: summary,
    };
    nextSnapshot.artifacts = artifacts;
    return nextSnapshot;
  }

  async function mergeDesktopSurfaceSectionIntoSnapshot(snapshot, state, expId, sectionPayload, options = {}) {
    const section = String(sectionPayload?.section || '').trim().toLowerCase();
    if (!ALLOWED_LAZY_SECTIONS.includes(section)) return bridgeCloneJson(snapshot) || {};
    const nextSnapshot = bridgeCloneJson(snapshot) || {};
    const artifacts = nextSnapshot.artifacts && typeof nextSnapshot.artifacts === 'object'
      ? { ...nextSnapshot.artifacts }
      : {};
    const sections = artifacts.surfaceSections && typeof artifacts.surfaceSections === 'object'
      ? { ...artifacts.surfaceSections }
      : {};
    const data = bridgeCloneJson(sectionPayload?.data);
    sections[section] = data;
    artifacts.surfaceSections = sections;

    if (!nextSnapshot.surface || typeof nextSnapshot.surface !== 'object') {
      nextSnapshot.surface = { lazy_sections: {} };
    }
    if (!nextSnapshot.surface.lazy_sections || typeof nextSnapshot.surface.lazy_sections !== 'object') {
      nextSnapshot.surface.lazy_sections = {};
    }
    nextSnapshot.surface.lazy_sections[section] = {
      ...(bridgeCloneJson(nextSnapshot.surface.lazy_sections[section]) || {}),
      section,
      available: true,
      inline: true,
      data: data == null ? null : data,
    };

    if (section === 'nav') {
      const navRows = normalizeNavSectionData(Array.isArray(data) ? data : []);
      artifacts.nav = navRows;
      artifacts.navSeries = navRows.map((row) => ({ date: row.date, value: row.nav }));
      if (!Array.isArray(artifacts.drawdownSeries) || !artifacts.drawdownSeries.length) {
        // Display-only fallback; canonical drawdown should come from the backend drawdown section.
        artifacts.drawdownSeries = navRows.reduce((acc, row) => {
          const peak = acc.length ? Math.max(acc[acc.length - 1].__peak || row.nav, row.nav) : row.nav;
          const value = peak > 0 ? ((row.nav - peak) / peak) : 0;
          acc.push({ date: row.date, value, __peak: peak });
          return acc;
        }, []).map((row) => ({ date: row.date, value: row.value }));
      }
      const benchmarkSeriesExists = Array.isArray(artifacts.benchmarkSeries) && artifacts.benchmarkSeries.length;
      const benchmarkOhlcExists = Array.isArray(artifacts.benchmarkOhlc) && artifacts.benchmarkOhlc.length;
      const isResearchCombo = String(artifacts.run_meta?.data?.asset_role || '').trim().toLowerCase() === 'research_combo';
      if (!isResearchCombo && (!benchmarkSeriesExists || !benchmarkOhlcExists || !options.reuseExistingBenchmark) && typeof globalScope.loadBenchmarkSeries === 'function') {
        try {
          const benchmark = await globalScope.loadBenchmarkSeries(navRows);
          const benchmarkPoints = Array.isArray(benchmark?.points) ? benchmark.points : [];
          artifacts.benchmarkSeries = benchmarkPoints.map((row) => ({ date: row.date, value: row.nav }));
          artifacts.benchmarkOhlc = Array.isArray(benchmark?.ohlc) ? benchmark.ohlc : [];
          artifacts.benchmarkDrawdownSeries = benchmarkPoints.reduce((acc, row) => {
            const nav = Number(row?.nav);
            if (!Number.isFinite(nav) || nav <= 0) return acc;
            const peak = acc.length ? Math.max(acc[acc.length - 1].__peak || nav, nav) : nav;
            acc.push({ date: row.date, value: peak > 0 ? ((nav - peak) / peak) : 0, __peak: peak });
            return acc;
          }, []).map((row) => ({ date: row.date, value: row.value }));
          artifacts.benchmarkSource = String(benchmark?.source || '');
          artifacts.benchmarkError = String(benchmark?.error || '');
        } catch (error) {
          artifacts.benchmarkError = String(error?.message || error || '');
        }
      } else if (isResearchCombo) {
        artifacts.benchmarkSeries = [];
        artifacts.benchmarkOhlc = [];
        artifacts.benchmarkDrawdownSeries = [];
        artifacts.benchmarkSource = 'research_combo_not_applicable';
        artifacts.benchmarkError = '';
      }
    } else if (section === 'drawdown') {
      artifacts.drawdownSeries = normalizeDrawdownSectionData(Array.isArray(data) ? data : []);
    } else if (section === 'symbol_stats') {
      artifacts.symbolPerformanceRows = normalizeSymbolStatsSectionData(Array.isArray(data) ? data : []);
      const selectedSymbol = String(state?.selected_symbol || '').trim().toLowerCase();
      if (!selectedSymbol || !artifacts.symbolPerformanceRows.some((row) => row.symbol === selectedSymbol)) {
        state.selected_symbol = artifacts.symbolPerformanceRows[0]?.symbol || '';
      }
    } else if (section === 'stage_funnel') {
      artifacts.funnelRows = Array.isArray(data) ? bridgeCloneJson(data) || [] : [];
    } else if (section === 'run_meta') {
      artifacts.run_meta = normalizeRunMetaCounters(data && typeof data === 'object' ? data : {});
    } else if (section === 'config') {
      artifacts.config = data && typeof data === 'object' ? bridgeCloneJson(data) || {} : {};
    } else if (section === 'trades') {
      artifacts.tradesRows = Array.isArray(data) ? bridgeCloneJson(data) || [] : [];
    } else if (section === 'daily') {
      artifacts.dailyRows = Array.isArray(data) ? bridgeCloneJson(data) || [] : [];
      artifacts.marketStates = _parseMarketStates(artifacts.dailyRows, artifacts.run_meta);
    } else if (section === 'reason_codes') {
      artifacts.reasonRows = Array.isArray(data) ? bridgeCloneJson(data) || [] : [];
    } else if (section === 'stock_names') {
      artifacts.stockNames = data && typeof data === 'object' ? bridgeCloneJson(data) || {} : {};
    } else if (section === 'combo_truth') {
      artifacts.comboTruth = data && typeof data === 'object' ? bridgeCloneJson(data) || null : null;
    }

    nextSnapshot.artifacts = artifacts;
    return nextSnapshot;
  }

  function buildDesktopResultsWorkbenchSnapshot(args) {
    const state = args && args.state ? args.state : {};
    const currentSnapshot = args && args.currentSnapshot ? args.currentSnapshot : {};
    const currentView = currentSnapshot && currentSnapshot.view ? currentSnapshot.view : {};
    const viewPatch = args && args.viewPatch && typeof args.viewPatch === 'object' ? args.viewPatch : {};
    const openPanels = args && args.openPanels ? args.openPanels : (currentView.openPanels || {});
    const runtimeSourceKind = String(state.runtime_source_kind || '').trim()
      || (state.active_manifest && state.active_manifest.exp_id ? 'experiment' : '');
    const runtimeSourceId = String(state.runtime_source_id || '').trim()
      || String((state.active_manifest && state.active_manifest.exp_id) || '');
    const sourceKind = String((args && args.sourceKind) || runtimeSourceKind || state.loaded_source_kind || '').trim()
      || (state.active_result && state.active_result.exp_id ? 'experiment' : '');
    const sourceId = String((args && args.sourceId) || runtimeSourceId || state.loaded_source_id || '').trim()
      || String((state.active_result && state.active_result.exp_id) || '');
    const currentArtifacts = currentSnapshot && currentSnapshot.artifacts ? bridgeCloneJson(currentSnapshot.artifacts) : {};
    const assetContext = bridgeCloneJson(
      state.active_asset_context
      || state.loaded_source_asset_context
      || currentSnapshot?.assetContext
      || currentArtifacts?.assetContext
      || {},
    ) || {};
    return {
      active: !!((state.active_result && state.active_result.exp_id) || state.active_artifacts),
      source: { kind: sourceKind, id: sourceId },
      assetContext,
      result: bridgeCloneJson(state.active_result) || null,
      manifest: bridgeCloneJson(state.active_manifest) || null,
      artifacts: { ...(currentArtifacts || {}), ...(bridgeCloneJson(state.active_artifacts) || {}) },
      surface: bridgeCloneJson(currentSnapshot.surface) || null,
      view: {
        chartMode: String(viewPatch.chartMode || state.chart_mode || currentView.chartMode || 'portfolio'),
        chartRange: String(viewPatch.chartRange || state.chart_range || currentView.chartRange || 'D'),
        showBenchmark: typeof viewPatch.showBenchmark === 'boolean'
          ? !!viewPatch.showBenchmark
          : (typeof state.chart_show_benchmark === 'boolean' ? state.chart_show_benchmark : !!currentView.showBenchmark),
        symbolFilter: String(viewPatch.symbolFilter || state.symbol_filter || currentView.symbolFilter || ''),
        symbolSort: String(viewPatch.symbolSort || state.symbol_sort || currentView.symbolSort || 'return_desc'),
        selectedSymbol: String(viewPatch.selectedSymbol || state.selected_symbol || currentView.selectedSymbol || '').toLowerCase(),
        openPanels: { ...(currentView.openPanels || {}), ...(openPanels || {}) },
      },
    };
  }

  async function publishDesktopResultsWorkbenchSnapshot(args) {
    const state = args && args.state ? args.state : {};
    const bridge = getDesktopResultsWorkbenchBridge();
    if (!bridge || typeof bridge.setSnapshot !== 'function') return false;
    const publishRevisionId = ++publishRevision;
    const currentSnapshot = typeof bridge.getSnapshot === 'function' ? (bridge.getSnapshot() || {}) : {};
    const openPanels = args && args.openPanels ? args.openPanels : (currentSnapshot?.view?.openPanels || {});
    const expId = currentExperimentId(state);
    let snapshot = buildDesktopResultsWorkbenchSnapshot({
      state,
      currentSnapshot,
      viewPatch: args?.viewPatch,
      openPanels,
      sourceKind: args?.sourceKind,
      sourceId: args?.sourceId,
    });

    const lazySections = resolveLazySectionsForSnapshot(snapshot, args?.lazySections || []);
    bridge.setSnapshot(snapshot);

    if (expId) {
      try {
        const surface = await ensureDesktopExperimentSurface(state, expId);
        if (publishRevisionId !== publishRevision || currentExperimentId(state) !== expId) return true;
        if (surface) {
          snapshot = mergeDesktopSurfaceIntoSnapshot(snapshot, surface);
          bridge.setSnapshot(snapshot);
        }
      } catch (_) {
      }
    }

    if (expId && currentExperimentId(state) === expId && lazySections.length) {
      const payloads = await Promise.all(lazySections.map(async (section) => {
        try {
          return await ensureDesktopExperimentSurfaceSection(state, expId, section);
        } catch (_) {
          return null;
        }
      }));
      if (publishRevisionId !== publishRevision || currentExperimentId(state) !== expId) return true;
      for (const payload of payloads) {
        if (!payload || currentExperimentId(state) !== expId) continue;
        snapshot = await mergeDesktopSurfaceSectionIntoSnapshot(snapshot, state, expId, payload, {
          reuseExistingBenchmark: true,
        });
        if (publishRevisionId !== publishRevision || currentExperimentId(state) !== expId) return true;
      }
    }

    if (publishRevisionId === publishRevision && (!expId || currentExperimentId(state) === expId)) {
      bridge.setSnapshot(snapshot);
    }
    return true;
  }

  globalScope.getDesktopResultsWorkbenchBridge = getDesktopResultsWorkbenchBridge;
  globalScope.ensureDesktopExperimentSurface = ensureDesktopExperimentSurface;
  globalScope.ensureDesktopExperimentSurfaceSection = ensureDesktopExperimentSurfaceSection;
  globalScope.buildDesktopResultsWorkbenchSnapshot = buildDesktopResultsWorkbenchSnapshot;
  globalScope.publishDesktopResultsWorkbenchSnapshot = publishDesktopResultsWorkbenchSnapshot;
  globalScope.clearDesktopResultsWorkbenchState = clearDesktopResultsWorkbenchState;
  globalScope.renderSymbolPerformancePanel = renderSymbolPerformancePanel;
  globalScope.renderExecutionPanel = renderExecutionPanel;
  globalScope.renderPerfPanel = renderPerfPanel;
  globalScope.renderTradesList = renderTradesList;
  globalScope.renderExplainPanel = renderExplainPanel;
})(window);

