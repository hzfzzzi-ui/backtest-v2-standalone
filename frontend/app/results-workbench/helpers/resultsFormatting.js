import { buildAgentMarkdownFromSnapshot } from './agentReportFormatting.js';
import { buildUnifiedStageFunnelFromSnapshot } from './stageFunnelFormatting.js';

function toFiniteNumber(value) {
  if (value == null) return null;
  if (typeof value === 'string' && !value.trim()) return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

export function fmtNum(value, digits = 2) {
  const num = toFiniteNumber(value);
  return num != null ? num.toFixed(digits) : '-';
}

export function fmtPct(value, digits = 2) {
  const num = toFiniteNumber(value);
  return num != null ? `${(num * 100).toFixed(digits)}%` : '-';
}

export function fmtInt(value) {
  const num = toFiniteNumber(value);
  return num != null ? Math.round(num).toLocaleString('en-US') : '-';
}

export function fmtMoney(value) {
  const num = toFiniteNumber(value);
  return num != null
    ? num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : '-';
}

export function fmtRatio(value, digits = 2) {
  if (value === Infinity) return '∞';
  if (value === -Infinity) return '-∞';
  const num = toFiniteNumber(value);
  return num != null ? num.toFixed(digits) : '-';
}

export function firstDefined(...values) {
  for (const value of values) {
    if (value == null) continue;
    if (typeof value === 'string' && !value.trim()) continue;
    if (typeof value === 'number' && Number.isNaN(value)) continue;
    return value;
  }
  return null;
}

function parseJsonObject(value) {
  if (!value || typeof value !== 'string') return {};
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (_) {
    return {};
  }
}

function buildDatedReturns(series) {
  const rows = Array.isArray(series) ? series : [];
  const out = [];
  for (let idx = 1; idx < rows.length; idx += 1) {
    const prev = Number(rows[idx - 1]?.value ?? rows[idx - 1]?.nav);
    const curr = Number(rows[idx]?.value ?? rows[idx]?.nav);
    const date = String(rows[idx]?.date || rows[idx]?.time || '').trim();
    if (!date || !Number.isFinite(prev) || !Number.isFinite(curr) || prev <= 0 || curr <= 0) continue;
    out.push({ date, value: (curr / prev) - 1 });
  }
  return out;
}

function mean(values) {
  const arr = (Array.isArray(values) ? values : []).filter((value) => Number.isFinite(value));
  if (!arr.length) return null;
  return arr.reduce((sum, value) => sum + value, 0) / arr.length;
}

function standardDeviation(values) {
  const avg = mean(values);
  const arr = (Array.isArray(values) ? values : []).filter((value) => Number.isFinite(value));
  if (!arr.length || avg == null) return null;
  const variance = arr.reduce((sum, value) => sum + ((value - avg) ** 2), 0) / arr.length;
  return variance >= 0 ? Math.sqrt(variance) : null;
}

function annualizedSharpeFromReturns(values) {
  const arr = (Array.isArray(values) ? values : []).filter((value) => Number.isFinite(value));
  if (arr.length < 2) return null;
  const avg = mean(arr);
  const std = standardDeviation(arr);
  if (avg == null || std == null || std <= 0) return null;
  return (avg / std) * Math.sqrt(252);
}

function annualizedSortinoFromReturns(values) {
  const arr = (Array.isArray(values) ? values : []).filter((value) => Number.isFinite(value));
  if (arr.length < 2) return null;
  const avg = mean(arr);
  const downside = arr.map((value) => (value < 0 ? value : 0));
  const downsideDeviation = Math.sqrt(
    downside.reduce((sum, value) => sum + (value ** 2), 0) / downside.length,
  );
  if (avg == null || downsideDeviation <= 0) return null;
  return (avg / downsideDeviation) * Math.sqrt(252);
}

function maxDrawdownDurationDays(series) {
  const rows = Array.isArray(series) ? series : [];
  let peak = null;
  let peakIndex = 0;
  let maxDuration = 0;
  for (let idx = 0; idx < rows.length; idx += 1) {
    const value = Number(rows[idx]?.value ?? rows[idx]?.nav);
    if (!Number.isFinite(value) || value <= 0) continue;
    if (peak == null || value >= peak) {
      peak = value;
      peakIndex = idx;
      continue;
    }
    maxDuration = Math.max(maxDuration, idx - peakIndex);
  }
  return maxDuration || null;
}

function latestRollingSharpe(series, windowSize = 126) {
  const returns = buildDatedReturns(series).map((item) => item.value);
  if (!returns.length) return null;
  const sample = returns.slice(-Math.min(windowSize, returns.length));
  return annualizedSharpeFromReturns(sample);
}

function alphaBeta(series, benchmarkSeries) {
  const strategyReturns = buildDatedReturns(series);
  const benchmarkReturns = buildDatedReturns(benchmarkSeries);
  if (!strategyReturns.length || !benchmarkReturns.length) return { alpha: null, beta: null };

  const benchmarkMap = new Map(benchmarkReturns.map((item) => [item.date, item.value]));
  const aligned = strategyReturns
    .map((item) => {
      const benchmarkValue = benchmarkMap.get(item.date);
      if (!Number.isFinite(benchmarkValue)) return null;
      return { strategy: item.value, benchmark: benchmarkValue };
    })
    .filter(Boolean);

  if (aligned.length < 2) return { alpha: null, beta: null };
  const strategyValues = aligned.map((item) => item.strategy);
  const benchmarkValues = aligned.map((item) => item.benchmark);
  const strategyMean = mean(strategyValues);
  const benchmarkMean = mean(benchmarkValues);
  if (strategyMean == null || benchmarkMean == null) return { alpha: null, beta: null };

  const benchmarkVariance = benchmarkValues.reduce(
    (sum, value) => sum + ((value - benchmarkMean) ** 2),
    0,
  ) / benchmarkValues.length;
  if (!(benchmarkVariance > 0)) return { alpha: null, beta: null };

  const covariance = aligned.reduce(
    (sum, item) => sum + ((item.strategy - strategyMean) * (item.benchmark - benchmarkMean)),
    0,
  ) / aligned.length;
  const beta = covariance / benchmarkVariance;
  const strategyStart = Number(series?.[0]?.value ?? series?.[0]?.nav);
  const strategyEnd = Number(series?.[series.length - 1]?.value ?? series?.[series.length - 1]?.nav);
  const benchmarkStart = Number(benchmarkSeries?.[0]?.value ?? benchmarkSeries?.[0]?.nav);
  const benchmarkEnd = Number(
    benchmarkSeries?.[benchmarkSeries.length - 1]?.value
      ?? benchmarkSeries?.[benchmarkSeries.length - 1]?.nav,
  );
  const strategyReturn = (
    Number.isFinite(strategyStart)
    && Number.isFinite(strategyEnd)
    && strategyStart > 0
  ) ? ((strategyEnd / strategyStart) - 1) : null;
  const benchmarkReturn = (
    Number.isFinite(benchmarkStart)
    && Number.isFinite(benchmarkEnd)
    && benchmarkStart > 0
  ) ? ((benchmarkEnd / benchmarkStart) - 1) : null;
  const alpha = (
    Number.isFinite(strategyReturn)
    && Number.isFinite(benchmarkReturn)
  ) ? (strategyReturn - (beta * benchmarkReturn)) : null;
  return { alpha, beta };
}

function realizedPnlStats(rows) {
  const trades = Array.isArray(rows) ? rows : [];
  const books = new Map();
  const realizedPnls = [];
  const sorted = trades
    .map((row, index) => ({ row, index }))
    .sort((left, right) => {
      const ld = String(left.row?.date || '');
      const rd = String(right.row?.date || '');
      if (ld !== rd) return ld < rd ? -1 : 1;
      return left.index - right.index;
    });

  sorted.forEach(({ row }) => {
    const side = String(row?.side || '').toUpperCase();
    const symbol = String(row?.symbol || '').trim().toLowerCase();
    const qty = Number(row?.qty);
    if (!symbol || !Number.isFinite(qty) || qty <= 0) return;
    const meta = parseJsonObject(row?.meta_json);
    const book = books.get(symbol) || { qty: 0, cost: 0 };

    if (side === 'BUY') {
      const grossCost = Number(row?.net_amount);
      const cost = Number.isFinite(grossCost) ? grossCost : (Number(row?.fill_price) * qty);
      if (Number.isFinite(cost) && cost > 0) {
        book.qty += qty;
        book.cost += cost;
        books.set(symbol, book);
      }
      return;
    }

    if (side !== 'SELL') return;
    const matchedQty = Math.min(qty, book.qty > 0 ? book.qty : qty);
    if (!(matchedQty > 0)) return;

    let avgCost = book.qty > 0 ? (book.cost / book.qty) : null;
    if (!(Number.isFinite(avgCost) && avgCost > 0)) {
      avgCost = Number(meta?.avg_cost);
    }
    const proceeds = Number(row?.net_amount);
    if (!(Number.isFinite(avgCost) && avgCost > 0) || !Number.isFinite(proceeds)) return;

    const costBasis = avgCost * matchedQty;
    realizedPnls.push(proceeds - costBasis);

    if (book.qty > 0) {
      book.qty -= matchedQty;
      book.cost -= avgCost * matchedQty;
      if (book.qty <= 1e-8 || book.cost <= 1e-8) {
        books.delete(symbol);
      } else {
        books.set(symbol, book);
      }
    }
  });

  const wins = realizedPnls.filter((value) => value > 0);
  const losses = realizedPnls.filter((value) => value < 0);
  const grossProfit = wins.reduce((sum, value) => sum + value, 0);
  const grossLoss = losses.reduce((sum, value) => sum + Math.abs(value), 0);
  return {
    closedTrades: realizedPnls.length,
    winRate: realizedPnls.length ? (wins.length / realizedPnls.length) : null,
    profitFactor: grossLoss > 0 ? (grossProfit / grossLoss) : (grossProfit > 0 ? Infinity : null),
    expectancy: realizedPnls.length ? mean(realizedPnls) : null,
  };
}

export function deriveTop10AverageReturn(rows) {
  const values = (Array.isArray(rows) ? rows : [])
    .map((row) => Number(normalizeSymbolRow(row)?.return_pct))
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => b - a)
    .slice(0, 10);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function deriveSymbolReturnPct(row) {
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

function normalizeSymbolRow(row) {
  const symbol = String(row?.symbol || '').trim().toLowerCase();
  if (!symbol) return null;
  const maxDrawdown = Number(row?.max_drawdown);
  const trades = Number(row?.trades);
  const netPnl = Number(row?.net_pnl);
  const realizedPnl = Number(row?.realized_pnl);
  const buyNotional = Number(row?.buy_notional);
  const unrealizedApproxPnl = Number(row?.unrealized_approx_pnl);
  return {
    ...row,
    symbol,
    return_pct: Number.isFinite(deriveSymbolReturnPct(row)) ? deriveSymbolReturnPct(row) : 0,
    max_drawdown: Number.isFinite(maxDrawdown) ? maxDrawdown : 0,
    trades: Number.isFinite(trades) ? trades : 0,
    net_pnl: Number.isFinite(netPnl) ? netPnl : 0,
    realized_pnl: Number.isFinite(realizedPnl) ? realizedPnl : 0,
    buy_notional: Number.isFinite(buyNotional) ? buyNotional : 0,
    unrealized_approx_pnl: Number.isFinite(unrealizedApproxPnl) ? unrealizedApproxPnl : 0,
  };
}

function deriveTop10ProfitConcentration(rows) {
  const positivePnls = (Array.isArray(rows) ? rows : [])
    .map((row) => Number(row?.net_pnl))
    .filter((value) => Number.isFinite(value) && value > 0)
    .sort((a, b) => b - a);
  if (!positivePnls.length) return null;
  const totalPositive = positivePnls.reduce((sum, value) => sum + value, 0);
  if (!(totalPositive > 0)) return null;
  const top10Positive = positivePnls.slice(0, 10).reduce((sum, value) => sum + value, 0);
  return top10Positive / totalPositive;
}

export function stockZh(symbol, stockNames = null) {
  const normalized = String(symbol ?? '');
  const lookup = stockNames && typeof stockNames === 'object' ? stockNames : null;
  const mapped = lookup
    ? (lookup[normalized] || lookup[normalized.toLowerCase()] || lookup[normalized.toUpperCase()])
    : null;
  return mapped ? String(mapped) : (normalized || '-');
}

function normalizeName(value) {
  return String(value || '').trim().toLowerCase();
}

function moduleLabel(name) {
  const normalized = normalizeName(name);
  if (normalized === 'breakout_55') return 'Breakout 55';
  if (normalized === 'rsi_reversal') return 'RSI Reversal';
  return String(name || '-');
}

function joinCounts(counts) {
  const obj = counts && typeof counts === 'object' ? counts : {};
  const items = Object.entries(obj)
    .filter(([, value]) => value != null)
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])));
  if (!items.length) return '-';
  return items.map(([key, value]) => `${moduleLabel(key)}:${fmtInt(value)}`).join(', ');
}

function joinRegimes(regimeMatrix) {
  const matrix = regimeMatrix && typeof regimeMatrix === 'object' ? regimeMatrix : {};
  const regimes = ['TREND_UP', 'RANGE', 'WEAK_DOWN'];
  return regimes.map((regime) => {
    const values = Array.isArray(matrix[regime]) ? matrix[regime] : [];
    return `${regime}=${values.map((name) => moduleLabel(name)).join(' + ') || '-'}`;
  }).join(' | ');
}

function moduleListText(modules) {
  return (Array.isArray(modules) ? modules : [])
    .map((module) => moduleLabel(module?.name || module))
    .filter(Boolean)
    .join(' + ');
}

function extractWorkbenchConfig(snapshot) {
  const config = snapshot?.artifacts?.config || {};
  return config?.overrides?.original_workbench_config
    || config?.overrides?.workbench_config
    || config?.workbench_config
    || null;
}

function extractCompositePayload(snapshot) {
  const config = extractWorkbenchConfig(snapshot);
  const signalGeneration = config?.signal_generation || {};
  const signalComposition = config?.signal_composition || {};
  const modules = Array.isArray(signalGeneration?.modules) ? signalGeneration.modules : [];
  if (modules.length) {
    return {
      modules,
      composition: signalComposition,
      portfolioMode: config?.position_risk?.portfolio_mode || '-',
    };
  }
  const runtimeConfig = snapshot?.artifacts?.config?.base_config || {};
  const runtimeMultiAlpha = runtimeConfig?.strategy?.params?.multi_alpha || {};
  const runtimeModules = Array.isArray(runtimeMultiAlpha?.signal_generation?.modules)
    ? runtimeMultiAlpha.signal_generation.modules
    : [];
  if (!runtimeModules.length) return null;
  return {
    modules: runtimeModules,
    composition: runtimeMultiAlpha?.signal_composition || {},
    portfolioMode:
      runtimeConfig?.strategy?.params?.portfolio_mode
      || runtimeConfig?.position_risk?.portfolio_mode
      || '-',
  };
}

function strategyFields(snapshot) {
  const result = snapshot?.result || {};
  const artifacts = snapshot?.artifacts || {};
  const meta = artifacts.run_meta || {};
  const composite = extractCompositePayload(snapshot);
  const workbenchConfig = extractWorkbenchConfig(snapshot);
  const runtimeConfig = snapshot?.artifacts?.config?.base_config || {};
  if (composite) {
    const composition = composite.composition || {};
    return {
      strategy: 'COMPOSITE',
      strategyCore: moduleListText(composite.modules) || '-',
      portfolioMode: composite.portfolioMode || '-',
      strategySummary: [
        String(composition.compose_mode || '-'),
        String(composition.same_symbol_policy || '-'),
        String(composition.holding_ownership || '-'),
        joinRegimes(composition.regime_matrix),
      ].join(' | '),
    };
  }
  if (workbenchConfig) {
    const signalGeneration = workbenchConfig?.signal_generation || {};
    const breakout = signalGeneration?.breakout || {};
    const ranking = signalGeneration?.ranking || {};
    const exitRules = workbenchConfig?.exit_rules || {};
    const trailing = exitRules?.trailing || {};
    const atrStop = exitRules?.atr_stop || {};
    const benchmarkRegime = workbenchConfig?.benchmark_regime || {};
    const riskOffExit = exitRules?.risk_off_exit || {};
    const strategyName = String(
      workbenchConfig?.strategy_pack
        || signalGeneration?.strategy
        || result.strategy_name
        || 'STRATEGY',
    ).toUpperCase();
    const breakoutWindow = breakout?.breakout_window ?? 55;
    const scoreSourceMode = ranking?.score_source_mode || 'none';
    const trailActivatePct = Number(trailing?.activate_profit_pct);
    const trailActivateText = Number.isFinite(trailActivatePct)
      ? `Trail@${(trailActivatePct * 100).toFixed(0)}%`
      : 'Trail@OFF';
    const regimeText = benchmarkRegime?.enabled
      ? `BR ${benchmarkRegime?.fast_period ?? 20}/${benchmarkRegime?.slow_period ?? 120}/${benchmarkRegime?.slope_window ?? 5}`
      : 'BR OFF';
    const riskOffText = riskOffExit?.enabled
      ? `RiskOff ${riskOffExit?.mode || 'on'}`
      : 'RiskOff OFF';
    return {
      strategy: strategyName || '-',
      strategyCore: strategyName === 'BREAKOUT_TREND'
        ? `Breakout ${breakoutWindow} | ${scoreSourceMode}`
        : strategyName,
      portfolioMode: firstDefined(
        workbenchConfig?.position_risk?.portfolio_mode,
        result.portfolio_mode,
        '-',
      ) || '-',
      strategySummary: [
        `ATR ${atrStop?.k ?? '-'} / Trail ${trailing?.k ?? '-'}`,
        trailActivateText,
        regimeText,
        riskOffText,
      ].join(' | '),
    };
  }
  return {
    strategy: firstDefined(
      meta.strategy?.name,
      runtimeConfig?.strategy?.name,
      result.strategy_name,
      '-',
    ) || '-',
    strategyCore: firstDefined(meta.strategy?.core, result.strategy_core, '-') || '-',
    portfolioMode: firstDefined(meta.strategy?.portfolio_mode, result.portfolio_mode, '-') || '-',
    strategySummary: firstDefined(meta.strategy?.summary, result.strategy_summary, '-') || '-',
  };
}

export function summarizeSnapshot(snapshot) {
  const result = snapshot?.result || {};
  const artifacts = snapshot?.artifacts || {};
  const perf = artifacts.perf || {};
  const meta = artifacts.run_meta || {};
  const navSeries = Array.isArray(artifacts.navSeries) ? artifacts.navSeries : [];
  const benchmarkSeries = Array.isArray(artifacts.benchmarkSeries) ? artifacts.benchmarkSeries : [];
  const tradesRows = Array.isArray(artifacts.tradesRows) ? artifacts.tradesRows : [];
  const symbolRows = Array.isArray(artifacts.symbolPerformanceRows) ? artifacts.symbolPerformanceRows : [];
  const workbenchConfig = extractWorkbenchConfig(snapshot);
  const top10AvgReturn = firstDefined(
    deriveTop10AverageReturn(symbolRows),
    perf.top10_avg_return_pct,
    result.top10_avg_return_pct,
  );
  const top10ProfitConcentrationValue = firstDefined(
    perf.top10_profit_concentration,
    perf.profit_concentration,
    deriveTop10ProfitConcentration(symbolRows),
    result.top10_profit_concentration,
    result.profit_concentration,
  );
  const totalReturnValue = firstDefined(perf.total_return, result.total_return);
  const initialCapitalValue = firstDefined(
    perf.initial_capital,
    workbenchConfig?.initial_capital,
    artifacts?.config?.overrides?.initial_capital,
    artifacts?.config?.base_config?.initial_capital,
  );
  const initialCapitalNumber = toFiniteNumber(initialCapitalValue);
  const totalReturnNumber = toFiniteNumber(totalReturnValue);
  const finalCapitalValue = firstDefined(
    perf.final_capital,
    initialCapitalNumber != null && totalReturnNumber != null
      ? initialCapitalNumber * (1 + totalReturnNumber)
      : null,
  );
  const rawCount = firstDefined(
    meta.universe?.raw_count,
    meta.universe?.union_symbol_count,
    meta.data_bundle?.symbols_count,
  );
  const filteredCount = firstDefined(
    meta.universe?.after_filters_symbols,
    meta.universe?.tradable_symbols,
    meta.data_bundle?.symbols_count,
  );
  const rawCountNum = toFiniteNumber(rawCount);
  const filteredCountNum = toFiniteNumber(filteredCount);
  const universeCount = rawCountNum != null
    ? (
      filteredCountNum != null && filteredCountNum !== rawCountNum
        ? `${fmtInt(rawCountNum)} -> ${fmtInt(filteredCountNum)}`
        : fmtInt(firstDefined(filteredCountNum, rawCountNum))
    )
    : (filteredCountNum != null ? fmtInt(filteredCountNum) : '-');
  const assetScope = String(
    firstDefined(
      meta.data?.asset_scope,
      snapshot?.assetContext?.asset_scope,
      result.asset_scope,
      'cn_a_equity',
    ) || 'cn_a_equity',
  ).trim().toLowerCase();
  const isCnEtf = assetScope === 'cn_etf';
  const etfSymbols = Array.isArray(meta.data?.etf_symbols)
    ? meta.data.etf_symbols.map((item) => String(item || '').trim()).filter(Boolean)
    : [];
  const coverageStart = firstDefined(meta.data?.coverage_start, meta.data_bundle?.coverage_start);
  const coverageEnd = firstDefined(meta.data?.coverage_end, meta.data_bundle?.coverage_end);
  const coverageWindow = coverageStart && coverageEnd ? `${coverageStart} ~ ${coverageEnd}` : '-';
  const priceSeriesSemantics = firstDefined(
    meta.data?.price_series_semantics,
    meta.data_bundle?.price_series_semantics,
    '-',
  ) || '-';
  const strategy = strategyFields(snapshot);
  const auditSummary = artifacts.audit?.summary || {};
  const dailyReturns = buildDatedReturns(navSeries).map((item) => item.value);
  const sortino = annualizedSortinoFromReturns(dailyReturns);
  const rollingSharpe = latestRollingSharpe(navSeries);
  const drawdownDurationDays = maxDrawdownDurationDays(navSeries);
  const { alpha, beta } = alphaBeta(navSeries, benchmarkSeries);
  const realizedPnl = realizedPnlStats(tradesRows);
  const effectiveExecutionStartDate = firstDefined(
    perf.effective_execution_start_date,
    meta.warmup?.effective_execution_start_date,
    perf.candidate_ready_date,
  );

  return {
    assetScope,
    universeSectionTitle: isCnEtf ? 'ETF研究口径' : '股票池口径',
    universeModeLabel: isCnEtf ? 'ETF名单' : '股票池',
    universeCountLabel: isCnEtf ? 'ETF数量' : '标的数',
    etfBatch: firstDefined(meta.data?.etf_batch, meta.data_bundle?.etf_batch, '-') || '-',
    etfSymbols: etfSymbols.length ? etfSymbols.join(', ') : '-',
    coverageWindow,
    priceSeriesSemantics,
    expId: result.exp_id || '-',
    status: result.status || 'WAITING',
    effectiveExecutionStartDate: effectiveExecutionStartDate || '-',
    universeRange: `${firstDefined(meta.data?.start, '-') || '-'} ~ ${firstDefined(meta.data?.end, '-') || '-'}`,
    benchmark: firstDefined(meta.data?.benchmark, etfSymbols[0], '-') || '-',
    universeMode: firstDefined(meta.universe?.universe_mode, meta.data?.universe_mode, '-') || '-',
    universeCount,
    strategy: strategy.strategy,
    strategyCore: strategy.strategyCore,
    portfolioMode: strategy.portfolioMode,
    strategySummary: strategy.strategySummary,
    initialCapital: initialCapitalNumber != null ? fmtMoney(initialCapitalNumber) : '-',
    finalCapital: toFiniteNumber(finalCapitalValue) != null ? fmtMoney(finalCapitalValue) : '-',
    cagr: fmtPct(firstDefined(perf.cagr, result.cagr)),
    totalReturn: fmtPct(totalReturnValue),
    maxDrawdown: fmtPct(firstDefined(perf.max_drawdown, result.max_drawdown)),
    maxDrawdownDuration: toFiniteNumber(drawdownDurationDays) != null
      ? `${fmtInt(drawdownDurationDays)}天`
      : '-',
    sharpe: fmtNum(firstDefined(perf.sharpe, result.sharpe), 2),
    calmar: fmtNum(firstDefined(perf.calmar, result.calmar), 2),
    rollingSharpe: fmtRatio(rollingSharpe, 2),
    expectancyPerTrade: toFiniteNumber(firstDefined(perf.expectancy_per_trade, realizedPnl.expectancy)) != null
      ? fmtMoney(firstDefined(perf.expectancy_per_trade, realizedPnl.expectancy))
      : '-',
    sortino: fmtRatio(sortino, 2),
    profitFactor: fmtRatio(firstDefined(perf.profit_factor, realizedPnl.profitFactor), 2),
    winRate: fmtPct(firstDefined(perf.win_rate, realizedPnl.winRate)),
    alpha: fmtPct(alpha),
    beta: fmtRatio(beta, 2),
    trades: fmtInt(firstDefined(perf.trades, result.trades)),
    turnover: fmtPct(firstDefined(perf.turnover, result.turnover)),
    top10ProfitConcentration: fmtPct(top10ProfitConcentrationValue),
    top10AvgReturn: fmtPct(top10AvgReturn),
    tier: firstDefined(perf.tier, result.tier, meta.tier) || '-',
    groupLoadStatus: artifacts?.missing?.length
      ? `缺少 ${String(artifacts.missing.length)} 个产物`
      : '产物已加载',
    auditSummary: {
      rawSignals: joinCounts(auditSummary.raw_signal_counts_by_alpha),
      composedSignals: joinCounts(auditSummary.composed_signal_counts_by_alpha),
      blockedSignals: joinCounts(auditSummary.blocked_signal_counts_by_reason),
      conflicts: joinCounts(auditSummary.conflict_resolution_counts),
      sourceOnlyExitCount: fmtInt(auditSummary.source_only_exit_count),
      globalRiskOverrideCount: fmtInt(auditSummary.global_risk_override_count),
    },
  };
}

export function buildUnifiedStageFunnelHtml(snapshot) {
  return buildUnifiedStageFunnelFromSnapshot(snapshot);
}

export function buildAgentMarkdown(snapshot) {
  return buildAgentMarkdownFromSnapshot(snapshot);
}

export function normalizeTradesRows(snapshot) {
  const rows = Array.isArray(snapshot?.artifacts?.tradesRows) ? snapshot.artifacts.tradesRows : [];
  return rows.map((row) => ({
    ...row,
    entry_alpha_id: row?.entry_alpha_id || '-',
    entry_sleeve_id: row?.entry_sleeve_id || '-',
    entry_reason_code: row?.entry_reason_code || '-',
    exit_owner: row?.exit_owner || '-',
  }));
}

export function normalizeSymbolRows(snapshot) {
  return Array.isArray(snapshot?.artifacts?.symbolPerformanceRows)
    ? snapshot.artifacts.symbolPerformanceRows
      .map((row) => normalizeSymbolRow(row))
      .filter(Boolean)
    : [];
}

