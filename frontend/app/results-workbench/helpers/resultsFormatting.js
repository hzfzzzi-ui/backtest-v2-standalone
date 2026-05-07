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
  if (value === Infinity) return 'INF';
  if (value === -Infinity) return '-INF';
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

function joinList(values) {
  const arr = Array.isArray(values)
    ? values.map((value) => String(value || '').trim()).filter(Boolean)
    : [];
  return arr.length ? arr.join(', ') : '-';
}

function summarizeManualOverride(overridePayload) {
  const payload = overridePayload && typeof overridePayload === 'object' ? overridePayload : {};
  if (!payload.active) return '无';
  const parts = [
    String(payload.scope || 'override').trim(),
    String(payload.target_state_5 || '').trim(),
    String(payload.reason || '').trim(),
  ].filter(Boolean);
  return parts.length ? parts.join(' | ') : '已启用';
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

function deriveNavComponentTotalReturn(rows, key) {
  const series = (Array.isArray(rows) ? rows : [])
    .map((row) => ({
      date: String(row?.date || '').trim(),
      value: Number(row?.[key]),
    }))
    .filter((row) => row.date && Number.isFinite(row.value) && row.value > 0);
  if (!series.length) return null;
  const firstValue = Number(series[0]?.value);
  const lastValue = Number(series[series.length - 1]?.value);
  if (!Number.isFinite(firstValue) || !Number.isFinite(lastValue) || firstValue <= 0) return null;
  return (lastValue / firstValue) - 1;
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

function extractExecutionContract(snapshot) {
  const workbenchConfig = extractWorkbenchConfig(snapshot);
  return workbenchConfig?.unified_runtime?.execution_contract
    || snapshot?.artifacts?.run_meta?.execution_contract
    || null;
}

function extractProvenanceComponentSourceContract(snapshot) {
  const runMeta = snapshot?.artifacts?.run_meta || {};
  const provenance = runMeta.provenance && typeof runMeta.provenance === 'object'
    ? runMeta.provenance
    : {};
  const provenanceContract = provenance.component_source_contract && typeof provenance.component_source_contract === 'object'
    ? provenance.component_source_contract
    : {};
  return Object.keys(provenanceContract).length ? provenanceContract : {};
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

function comboRuntimeFlags(meta) {
  const runMeta = meta && typeof meta === 'object' ? meta : {};
  const data = runMeta.data && typeof runMeta.data === 'object' ? runMeta.data : {};
  const comboRuntime = runMeta.combo_runtime && typeof runMeta.combo_runtime === 'object' ? runMeta.combo_runtime : {};
  const comboResult = runMeta.combo_result && typeof runMeta.combo_result === 'object' ? runMeta.combo_result : {};
  const researchCombo = runMeta.research_combo && typeof runMeta.research_combo === 'object' ? runMeta.research_combo : {};
  const executionContractRef = runMeta.execution_contract_ref && typeof runMeta.execution_contract_ref === 'object'
    ? runMeta.execution_contract_ref
    : {};
  const executionContract = runMeta.execution_contract && typeof runMeta.execution_contract === 'object'
    ? runMeta.execution_contract
    : {};
  const componentSourceContract = comboComponentSourceContract(runMeta);
  const assetRole = String(data.asset_role || '').trim().toLowerCase();
  const comboSourceMode = (
    Object.keys(executionContractRef).length || Object.keys(executionContract).length
      ? 'execution_contract'
      : (Object.keys(componentSourceContract).length ? 'provenance' : '')
  );
  const researchComboOnly = Boolean(
    comboResult.research_combo_only
    || researchCombo.research_combo_only
    || comboRuntime.research_combo_only
  );
  const isUnifiedCombo = assetRole === 'unified_multi_sleeve_combo'
    || String(comboResult.type || '').trim().toLowerCase() === 'unified_runtime_combo';
  const isResearchCombo = assetRole === 'research_combo'
    || researchComboOnly
    || (!assetRole && !!researchCombo.mode);
  return {
    isUnifiedCombo,
    isResearchCombo,
    isComboResult: isUnifiedCombo || isResearchCombo,
    researchComboOnly,
    comboSourceMode,
  };
}

function comboComponentSourceContract(meta) {
  const runMeta = meta && typeof meta === 'object' ? meta : {};
  const provenance = runMeta.provenance && typeof runMeta.provenance === 'object'
    ? runMeta.provenance
    : {};
  const provenanceContract = provenance.component_source_contract && typeof provenance.component_source_contract === 'object'
    ? provenance.component_source_contract
    : {};
  return Object.keys(provenanceContract).length ? provenanceContract : {};
}

function comboExecutionContract(meta) {
  const runMeta = meta && typeof meta === 'object' ? meta : {};
  const topLevel = runMeta.execution_contract && typeof runMeta.execution_contract === 'object'
    ? runMeta.execution_contract
    : {};
  if (Object.keys(topLevel).length) return topLevel;
  const comboRuntime = runMeta.combo_runtime && typeof runMeta.combo_runtime === 'object' ? runMeta.combo_runtime : {};
  if (comboRuntime.execution_contract && typeof comboRuntime.execution_contract === 'object') {
    return comboRuntime.execution_contract;
  }
  const comboContext = runMeta.combo_context && typeof runMeta.combo_context === 'object' ? runMeta.combo_context : {};
  return comboContext.execution_contract && typeof comboContext.execution_contract === 'object'
    ? comboContext.execution_contract
    : {};
}

function resolvedComboComponents(meta) {
  const runMeta = meta && typeof meta === 'object' ? meta : {};
  const contract = comboComponentSourceContract(runMeta);
  const executionContract = comboExecutionContract(runMeta);
  const contractComponents = contract.components && typeof contract.components === 'object' ? contract.components : {};
  const executionComponents = executionContract.components && typeof executionContract.components === 'object'
    ? executionContract.components
    : {};
  const keys = Array.from(new Set([
    ...Object.keys(contractComponents),
    ...Object.keys(executionComponents),
  ]));
  return keys.reduce((acc, key) => {
    const contractEntry = contractComponents[key] && typeof contractComponents[key] === 'object' ? contractComponents[key] : {};
    const executionEntry = executionComponents[key] && typeof executionComponents[key] === 'object' ? executionComponents[key] : {};
    acc[key] = {
      ...contractEntry,
      ...executionEntry,
      source: contractEntry.source && typeof contractEntry.source === 'object' ? contractEntry.source : executionEntry.source,
      compile_input: contractEntry.compile_input && typeof contractEntry.compile_input === 'object' ? contractEntry.compile_input : executionEntry.compile_input,
    };
    return acc;
  }, {});
}

function comboComponentSourceText(component) {
  const payload = component && typeof component === 'object' ? component : {};
  const source = payload.source && typeof payload.source === 'object' ? payload.source : {};
  const kind = String(source.source_kind || '').trim().toLowerCase();
  if (kind === 'baseline_anchor') {
    return String(source.baseline_id || payload.sleeve_id || '-').trim() || '-';
  }
  if (kind === 'study_anchor') {
    const studyId = String(source.study_id || payload.sleeve_id || '-').trim() || '-';
    const variant = String(source.variant_name || '').trim();
    return variant ? `${studyId}::${variant}` : studyId;
  }
  return String(payload.sleeve_id || source.source_kind || '-').trim() || '-';
}

function comboStrategyFields(snapshot, meta) {
  const runMeta = meta && typeof meta === 'object' ? meta : {};
  const comboRuntime = runMeta.combo_runtime && typeof runMeta.combo_runtime === 'object' ? runMeta.combo_runtime : {};
  const comboResult = runMeta.combo_result && typeof runMeta.combo_result === 'object' ? runMeta.combo_result : {};
  const researchCombo = runMeta.research_combo && typeof runMeta.research_combo === 'object' ? runMeta.research_combo : {};
  const comboComponents = resolvedComboComponents(runMeta);
  const flags = comboRuntimeFlags(runMeta);
  const stockSource = comboComponentSourceText(comboComponents.stock_component);
  const etfSource = comboComponentSourceText(comboComponents.etf_component);
  return {
    strategy: flags.isResearchCombo ? 'RESEARCH_COMBO' : 'UNIFIED_COMBO',
    strategyCore: `Stock ${stockSource} + ETF ${etfSource}`,
    portfolioMode: firstDefined(comboRuntime.mode, researchCombo.mode, comboResult.mode, '-') || '-',
    strategySummary: [
      firstDefined(comboResult.assumption, researchCombo.assumption, '-'),
      flags.comboSourceMode || '-',
    ].filter(Boolean).join(' | '),
  };
}

function strategyFields(snapshot) {
  const result = snapshot?.result || {};
  const artifacts = snapshot?.artifacts || {};
  const meta = artifacts.run_meta || {};
  const comboFlags = comboRuntimeFlags(meta);
  if (comboFlags.isComboResult) {
    return comboStrategyFields(snapshot, meta);
  }
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
  const navRows = Array.isArray(artifacts.nav) ? artifacts.nav : [];
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
  const executionContract = extractExecutionContract(snapshot);
  const provenanceComponentSourceContract = extractProvenanceComponentSourceContract(snapshot);
  const navCapitalRows = navSeries.length ? navSeries : navRows;
  const navStartValue = firstDefined(
    navCapitalRows[0]?.value,
    navCapitalRows[0]?.nav,
  );
  const navEndValue = firstDefined(
    navCapitalRows[navCapitalRows.length - 1]?.value,
    navCapitalRows[navCapitalRows.length - 1]?.nav,
  );
  const initialCapitalValue = firstDefined(
    perf.initial_capital,
    result.initial_capital,
    workbenchConfig?.initial_capital,
    artifacts?.config?.overrides?.initial_capital,
    artifacts?.config?.base_config?.initial_capital,
    executionContract?.runtime_config?.initial_capital,
    executionContract?.components?.stock_component?.runtime_config?.initial_capital,
    executionContract?.components?.etf_component?.runtime_config?.initial_capital,
    provenanceComponentSourceContract?.components?.stock_component?.compile_input?.semantic_config?.initial_capital,
    provenanceComponentSourceContract?.components?.etf_component?.compile_input?.semantic_config?.initial_capital,
    navStartValue,
  );
  const initialCapitalNumber = toFiniteNumber(initialCapitalValue);
  const totalReturnNumber = toFiniteNumber(totalReturnValue);
  const navStartNumber = toFiniteNumber(navStartValue);
  const navEndNumber = toFiniteNumber(navEndValue);
  const finalCapitalValue = firstDefined(
    perf.final_capital,
    result.final_capital,
    initialCapitalNumber != null && navStartNumber != null && navEndNumber != null && navStartNumber > 0
      ? initialCapitalNumber * (navEndNumber / navStartNumber)
      : null,
    initialCapitalNumber != null && totalReturnNumber != null
      ? initialCapitalNumber * (1 + totalReturnNumber)
      : null,
    navEndValue,
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
  const assetRole = String(firstDefined(meta.data?.asset_role, result.asset_role, '') || '').trim().toLowerCase();
  const comboResult = meta.combo_result && typeof meta.combo_result === 'object' ? meta.combo_result : {};
  const comboFlags = comboRuntimeFlags(meta);
  const isUnifiedCombo = comboFlags.isUnifiedCombo;
  const isResearchCombo = comboFlags.isResearchCombo;
  const isComboResult = comboFlags.isComboResult;
  const researchComboOnly = comboFlags.researchComboOnly;
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
  const governedSnapshot = meta.governed_snapshot && typeof meta.governed_snapshot === 'object'
    ? meta.governed_snapshot
    : {};
  const latestRegime = meta.regime?.latest_state && typeof meta.regime.latest_state === 'object'
    ? meta.regime.latest_state
    : {};
  const governedManualOverride = latestRegime.manual_override && typeof latestRegime.manual_override === 'object'
    ? latestRegime.manual_override
    : {};
  const hasGovernedSnapshot = Boolean(
    firstDefined(
      governedSnapshot.effective_state,
      latestRegime.effective_state,
      governedSnapshot.base_state,
      latestRegime.base_state,
    ),
  );
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
  const comboMetrics = meta.combo_metrics && typeof meta.combo_metrics === 'object' ? meta.combo_metrics : {};
  const researchCombo = meta.research_combo && typeof meta.research_combo === 'object' ? meta.research_combo : {};
  const comboMeta = researchComboOnly ? researchCombo : (isUnifiedCombo ? comboResult : researchCombo);
  const comboComponents = resolvedComboComponents(meta);
  const comboStockExpId = firstDefined(comboComponents.stock_component?.exp_id, '-') || '-';
  const comboEtfExpId = firstDefined(comboComponents.etf_component?.exp_id, '-') || '-';
  const comboStockReturn = deriveNavComponentTotalReturn(navRows, firstDefined(comboMeta.stock_nav_column, 'stock_nav'));
  const comboEtfReturn = deriveNavComponentTotalReturn(navRows, firstDefined(comboMeta.etf_nav_column, 'etf_nav'));
  const comboWindowStart = firstDefined(comboMetrics.start, meta.data?.coverage_start);
  const comboWindowEnd = firstDefined(comboMetrics.end, meta.data?.coverage_end);
  const comboWindow = comboWindowStart && comboWindowEnd ? `${comboWindowStart} ~ ${comboWindowEnd}` : '-';
  const comboComponentCount = Object.values(comboComponents).filter((component) => component && typeof component === 'object').length;
  const comboTradeCount = firstDefined(
    perf.trades,
    result.trades,
    meta.counters?.closed_trades,
    meta.counters?.orders,
  );
  const comboBenchmark = firstDefined(meta.data?.benchmark, 'CN_STOCK_ETF_50_50', '-') || '-';

  return {
    assetScope,
    assetRole,
    isResearchCombo,
    isUnifiedCombo,
    isComboResult,
    researchComboOnly,
    universeSectionTitle: isComboResult
      ? (isResearchCombo ? '组合研究口径' : '组合结果口径')
      : (isCnEtf ? 'ETF研究口径' : '股票池口径'),
    universeModeLabel: isComboResult ? '组合模式' : (isCnEtf ? 'ETF名单' : '股票池'),
    universeCountLabel: isComboResult ? '组件数' : (isCnEtf ? 'ETF数量' : '标的数'),
    etfBatch: firstDefined(meta.data?.etf_batch, meta.data_bundle?.etf_batch, '-') || '-',
    etfSymbols: etfSymbols.length ? etfSymbols.join(', ') : '-',
    coverageWindow,
    priceSeriesSemantics,
    expId: result.exp_id || '-',
    status: result.status || 'WAITING',
    effectiveExecutionStartDate: effectiveExecutionStartDate || '-',
    universeRange: isComboResult
      ? comboWindow
      : `${firstDefined(meta.data?.start, '-') || '-'} ~ ${firstDefined(meta.data?.end, '-') || '-'}`,
    benchmark: isComboResult ? comboBenchmark : (firstDefined(meta.data?.benchmark, etfSymbols[0], '-') || '-'),
    universeMode: isComboResult
      ? (firstDefined(comboMeta.mode, meta.data?.asset_role, '-') || '-')
      : (firstDefined(meta.universe?.universe_mode, meta.data?.universe_mode, '-') || '-'),
    universeCount: isComboResult ? fmtInt(comboComponentCount || 0) : universeCount,
    hasGovernedSnapshot,
    governedBaseState: firstDefined(governedSnapshot.base_state, latestRegime.base_state, '-') || '-',
    governedEffectiveState: firstDefined(governedSnapshot.effective_state, latestRegime.effective_state, '-') || '-',
    governedCoarseState: firstDefined(governedSnapshot.coarse_state, latestRegime.coarse_state, '-') || '-',
    governedEffectiveCoarseState: firstDefined(
      governedSnapshot.effective_coarse_state,
      latestRegime.effective_coarse_state,
      '-',
    ) || '-',
    governedRiskBudgetMultiplier: fmtRatio(
      firstDefined(governedSnapshot.risk_budget_multiplier, latestRegime.risk_budget_multiplier),
      2,
    ),
    governedTotalRiskBudget: fmtPct(governedSnapshot.total_risk_budget),
    governedTotalExposureCap: fmtPct(governedSnapshot.total_exposure_cap),
    governedDefenseBias: fmtPct(firstDefined(governedSnapshot.defense_bias, latestRegime.defense_bias)),
    governedReasonCodes: joinList(latestRegime.reason_codes),
    governedBudgetReasonCodes: joinList(governedSnapshot.budget_reason_codes),
    governedManualOverride: summarizeManualOverride(governedManualOverride),
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
    trades: fmtInt(isComboResult ? comboTradeCount : firstDefined(perf.trades, result.trades)),
    turnover: fmtPct(firstDefined(perf.turnover, result.turnover)),
    top10ProfitConcentration: fmtPct(top10ProfitConcentrationValue),
    top10AvgReturn: fmtPct(top10AvgReturn),
    tier: firstDefined(perf.tier, result.tier, meta.tier) || '-',
    comboMode: firstDefined(comboMeta.mode, '-') || '-',
    comboAssumption: firstDefined(comboMeta.assumption, '-') || '-',
    comboWindow,
    comboStockExpId,
    comboEtfExpId,
    comboStockTotalReturn: fmtPct(comboStockReturn),
    comboEtfTotalReturn: fmtPct(comboEtfReturn),
    comboReadOnlyNote: isResearchCombo
      ? '当前结果是研究组合锚点，只读展示，不代表 unified runtime 正式实验。'
      : (isUnifiedCombo ? '当前结果来自 unified runtime 组合实验，组合层与 sleeve 层产物已统一收口。' : '-'),
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

function mapObjectEntries(payload, valueFormatter = null) {
  const source = payload && typeof payload === 'object' ? payload : {};
  return Object.entries(source)
    .map(([name, value]) => {
      const formatted = typeof valueFormatter === 'function' ? valueFormatter(value, name) : value;
      return {
        name,
        value: formatted == null || formatted === '' ? '-' : String(formatted),
      };
    })
    .filter((entry) => entry.value !== '-');
}

function extractComboTruthPayload(snapshot) {
  const payload = snapshot?.artifacts?.comboTruth;
  return payload && typeof payload === 'object' ? payload : {};
}

function extractComboTruthDisplay(snapshot) {
  const comboTruth = extractComboTruthPayload(snapshot);
  if (comboTruth.display && typeof comboTruth.display === 'object') {
    return comboTruth.display;
  }
  return {};
}

function extractComboTruthComponents(snapshot) {
  const comboTruth = extractComboTruthPayload(snapshot);
  if (comboTruth.components && typeof comboTruth.components === 'object') {
    return comboTruth.components;
  }
  return {};
}

function extractComboTruthComponentRunMeta(snapshot, componentKey) {
  const components = extractComboTruthComponents(snapshot);
  const payload = components?.[componentKey];
  if (!payload || typeof payload !== 'object') return {};
  const snapshotPayload = payload.snapshot && typeof payload.snapshot === 'object' ? payload.snapshot : null;
  const snapshotArtifacts = snapshotPayload?.artifacts && typeof snapshotPayload.artifacts === 'object'
    ? snapshotPayload.artifacts
    : null;
  if (snapshotArtifacts?.run_meta && typeof snapshotArtifacts.run_meta === 'object') {
    return snapshotArtifacts.run_meta;
  }
  const componentRunMeta = payload.run_meta;
  return componentRunMeta && typeof componentRunMeta === 'object' ? componentRunMeta : {};
}

export function buildRegimePanelModel(snapshot) {
  const meta = snapshot?.artifacts?.run_meta || {};
  const comboTruthDisplay = extractComboTruthDisplay(snapshot);
  const latestState = meta.regime?.latest_state && typeof meta.regime.latest_state === 'object'
    ? meta.regime.latest_state
    : {};
  const governedSnapshot = meta.governed_snapshot && typeof meta.governed_snapshot === 'object'
    ? meta.governed_snapshot
    : {};
  const stockRunMeta = extractComboTruthComponentRunMeta(snapshot, 'stock');
  const etfRunMeta = extractComboTruthComponentRunMeta(snapshot, 'etf');
  const stockLatestState = stockRunMeta?.regime?.latest_state
    && typeof stockRunMeta.regime.latest_state === 'object'
      ? stockRunMeta.regime.latest_state
      : {};
  const etfLatestState = etfRunMeta?.regime?.latest_state
    && typeof etfRunMeta.regime.latest_state === 'object'
      ? etfRunMeta.regime.latest_state
      : {};
  const manualOverride = latestState.manual_override && typeof latestState.manual_override === 'object'
    ? latestState.manual_override
    : {};
  const confidence = toFiniteNumber(latestState.confidence);

  if (!firstDefined(latestState.effective_state, latestState.base_state, governedSnapshot.regime_effective_state) && comboTruthDisplay?.regime?.available) {
    return {
      available: true,
      baseState: String(comboTruthDisplay.regime.base_state || '-'),
      effectiveState: String(comboTruthDisplay.regime.effective_state || '-'),
      coarseState: String(comboTruthDisplay.regime.coarse_state || '-'),
      effectiveCoarseState: String(comboTruthDisplay.regime.coarse_state || '-'),
      confidence: '-',
      riskBudgetMultiplier: String(comboTruthDisplay.regime.risk_budget_multiplier_text || '-'),
      defenseBias: '-',
      durationBars: '-',
      transitionReason: String(comboTruthDisplay.regime.reason_text || '-'),
      reasonCodes: [
        stockLatestState.effective_state ? `个股 ${stockLatestState.effective_state}` : '',
        etfLatestState.effective_state ? `ETF ${etfLatestState.effective_state}` : '',
      ].filter(Boolean),
      manualOverrideSummary: String(comboTruthDisplay.regime.manual_override_text || '无'),
      manualOverride: {},
      subscores: [
        stockLatestState.effective_state ? { name: '个股状态', value: String(stockLatestState.effective_state) } : null,
        etfLatestState.effective_state ? { name: 'ETF状态', value: String(etfLatestState.effective_state) } : null,
      ].filter(Boolean),
      blockScores: [],
      stability: [],
      featureAvailability: [],
    };
  }

  return {
    available: Boolean(firstDefined(latestState.effective_state, latestState.base_state, governedSnapshot.regime_effective_state)),
    baseState: firstDefined(latestState.base_state, governedSnapshot.regime_source_state, '-') || '-',
    effectiveState: firstDefined(latestState.effective_state, governedSnapshot.regime_effective_state, '-') || '-',
    coarseState: firstDefined(latestState.coarse_state, governedSnapshot.coarse_state, '-') || '-',
    effectiveCoarseState: firstDefined(latestState.effective_coarse_state, governedSnapshot.effective_coarse_state, '-') || '-',
    confidence: confidence != null ? fmtRatio(confidence, 2) : '-',
    riskBudgetMultiplier: fmtRatio(firstDefined(latestState.risk_budget_multiplier, governedSnapshot.risk_budget_multiplier), 2),
    defenseBias: fmtPct(firstDefined(latestState.defense_bias, governedSnapshot.defense_bias)),
    durationBars: fmtInt(firstDefined(latestState.regime_duration_bars, latestState.duration_bars)),
    transitionReason: firstDefined(latestState.regime_transition_reason, latestState.transition_reason, '-') || '-',
    reasonCodes: Array.isArray(latestState.reason_codes) ? latestState.reason_codes : [],
    manualOverrideSummary: summarizeManualOverride(manualOverride),
    manualOverride,
    subscores: mapObjectEntries(latestState.subscores, (value) => (typeof value === 'number' ? fmtRatio(value, 2) : JSON.stringify(value))),
    blockScores: mapObjectEntries(latestState.block_scores, (value) => (typeof value === 'number' ? fmtRatio(value, 2) : JSON.stringify(value))),
    stability: mapObjectEntries(latestState.state_stability_metrics, (value) => {
      if (typeof value === 'boolean') return value ? '是' : '否';
      if (typeof value === 'number') return fmtRatio(value, 2);
      return JSON.stringify(value);
    }),
    featureAvailability: mapObjectEntries(latestState.feature_availability, (value) => {
      if (typeof value === 'boolean') return value ? '可用' : '缺失';
      return JSON.stringify(value);
    }),
  };
}

export function buildGovernorPanelModel(snapshot) {
  const meta = snapshot?.artifacts?.run_meta || {};
  const comboTruthDisplay = extractComboTruthDisplay(snapshot);
  const governedSnapshot = meta.governed_snapshot && typeof meta.governed_snapshot === 'object'
    ? meta.governed_snapshot
    : {};
  const accountAllocatorRuntime = meta.account_allocator_runtime && typeof meta.account_allocator_runtime === 'object'
    ? meta.account_allocator_runtime
    : {};
  const accountBudgetRoles = accountAllocatorRuntime.budget_roles && typeof accountAllocatorRuntime.budget_roles === 'object'
    ? accountAllocatorRuntime.budget_roles
    : {};
  const accountTarget = accountBudgetRoles.target && typeof accountBudgetRoles.target === 'object'
    ? accountBudgetRoles.target
    : {};
  const accountActual = accountBudgetRoles.actual && typeof accountBudgetRoles.actual === 'object'
    ? accountBudgetRoles.actual
    : {};
  const accountDeviation = accountBudgetRoles.deviation && typeof accountBudgetRoles.deviation === 'object'
    ? accountBudgetRoles.deviation
    : {};
  const accountStateSource = String(accountAllocatorRuntime.state_source || '').trim();
  const accountStateResolution = accountAllocatorRuntime.state_resolution && typeof accountAllocatorRuntime.state_resolution === 'object'
    ? accountAllocatorRuntime.state_resolution
    : {};
  const accountStateTransitionPolicy = accountAllocatorRuntime.state_transition_policy && typeof accountAllocatorRuntime.state_transition_policy === 'object'
    ? accountAllocatorRuntime.state_transition_policy
    : {};
  const accountStateTransitionRuntime = accountAllocatorRuntime.state_transition_runtime && typeof accountAllocatorRuntime.state_transition_runtime === 'object'
    ? accountAllocatorRuntime.state_transition_runtime
    : {};
  const transitionActionHandoff = accountAllocatorRuntime.transition_action_handoff
    && typeof accountAllocatorRuntime.transition_action_handoff === 'object'
      ? accountAllocatorRuntime.transition_action_handoff
      : {};
  const riskoffLeftSideAccumulationBudget = accountAllocatorRuntime.riskoff_left_side_accumulation_budget
    && typeof accountAllocatorRuntime.riskoff_left_side_accumulation_budget === 'object'
      ? accountAllocatorRuntime.riskoff_left_side_accumulation_budget
      : {};
  const stockRunMeta = extractComboTruthComponentRunMeta(snapshot, 'stock');
  const etfRunMeta = extractComboTruthComponentRunMeta(snapshot, 'etf');
  const stockGovernor = stockRunMeta?.governed_snapshot
    && typeof stockRunMeta.governed_snapshot === 'object'
      ? stockRunMeta.governed_snapshot
      : {};
  const etfGovernor = etfRunMeta?.governed_snapshot
    && typeof etfRunMeta.governed_snapshot === 'object'
      ? etfRunMeta.governed_snapshot
      : {};
  const etfFormalView = etfRunMeta?.etf_beta?.formal_view
    && typeof etfRunMeta.etf_beta.formal_view === 'object'
      ? etfRunMeta.etf_beta.formal_view
      : {};
  const transitionExecution = accountAllocatorRuntime.transition_execution
    && typeof accountAllocatorRuntime.transition_execution === 'object'
      ? accountAllocatorRuntime.transition_execution
      : {};
  const sleeveBudgets = governedSnapshot.sleeve_budgets && typeof governedSnapshot.sleeve_budgets === 'object'
    ? governedSnapshot.sleeve_budgets
    : {};

  if (String(accountAllocatorRuntime.runtime_truth_source || '').trim() === 'account_allocator') {
    const riskoffLeftSideActive = Boolean(riskoffLeftSideAccumulationBudget.active);
    const defenseAssets = Array.isArray(riskoffLeftSideAccumulationBudget.defense_assets)
      ? riskoffLeftSideAccumulationBudget.defense_assets.filter(Boolean).join(', ')
      : '';
    const coreBetaAssets = Array.isArray(riskoffLeftSideAccumulationBudget.core_beta_assets)
      ? riskoffLeftSideAccumulationBudget.core_beta_assets.filter(Boolean).join(', ')
      : '';
    const transitionKind = String(accountStateTransitionRuntime.transition_kind || '').trim();
    const transitionFrom = String(accountStateTransitionRuntime.previous_state_5 || '').trim();
    const transitionTo = String(accountStateTransitionRuntime.effective_state_5 || '').trim();
    const transitionCarryMode = String(accountStateTransitionRuntime.carry_rules?.mode || '').trim();
    const transitionDeRiskMode = String(accountStateTransitionRuntime.de_risk_rules?.mode || '').trim();
    const transitionCashMode = String(accountStateTransitionRuntime.cash_release_rules?.mode || '').trim();
    const transitionHandoffMode = String(accountStateTransitionRuntime.budget_handoff_rules?.mode || '').trim();
    const transitionActionMode = String(transitionActionHandoff.consumption_mode || '').trim();
    const transitionExecutionOwner = String(transitionExecution.owner || '').trim();
    const transitionExecutionStatus = String(transitionExecution.status || '').trim();
    const transitionExecutionReason = String(transitionExecution.reason_code || '').trim();
    const transitionRejectReason = String(transitionExecution.reject_reason || '').trim();
    const roleBudgetRows = ['defense', 'core_beta', 'alpha'].map((roleKey) => ({
      sleeveId: roleKey,
      systemRole: `${roleKey}_budget`,
      slotCap: '-',
      availableSlots: '-',
      selectedCount: '-',
      candidateCount: '-',
      budgetShare: fmtPct(accountTarget[roleKey]),
      actualBudgetShare: fmtPct(accountActual[roleKey]),
      budgetGap: fmtPct(accountDeviation[`${roleKey}_gap`]),
    }));
    return {
      available: true,
      assetScope: firstDefined(meta.data?.asset_scope, 'cn_a_equity'),
      budgetOwner: String(accountAllocatorRuntime.budget_owner || 'account_allocator'),
      consumerSleeveId: 'defense / core_beta / alpha',
      consumerRole: 'account_allocator_runtime',
      totalRiskBudget: String(accountAllocatorRuntime.budget_basis || '-'),
      totalExposureCap: [
        '账户层主叙事',
        firstDefined(accountAllocatorRuntime.effective_state_5, '-'),
        firstDefined(transitionKind, '-'),
        transitionExecutionOwner ? `owner ${transitionExecutionOwner}` : '',
        transitionExecutionStatus ? `status ${transitionExecutionStatus}` : '',
        transitionExecutionReason ? `reason ${transitionExecutionReason}` : '',
        transitionRejectReason ? `reject ${transitionRejectReason}` : '',
      ].filter(Boolean).join(' | '),
      hardMaxPositions: '-',
      effectiveMaxPositions: '-',
      drawdown: fmtPct(governedSnapshot.drawdown),
      drawdownState: firstDefined(governedSnapshot.drawdown_state, '-'),
      recoveryState: firstDefined(governedSnapshot.recovery_state, '-'),
      cooldownState: firstDefined(governedSnapshot.cooldown_state, '-'),
      defenseFloor: fmtPct(governedSnapshot.defense_floor),
      defenseFloorState: firstDefined(governedSnapshot.defense_floor_state, '-'),
      defenseBias: fmtPct(governedSnapshot.defense_bias),
      budgetReasonCodes: Array.isArray(accountBudgetRoles.reason_codes) ? accountBudgetRoles.reason_codes : [],
      localBudgetControls: [
        `runtime_truth_source=${String(accountAllocatorRuntime.runtime_truth_source || 'account_allocator')}`,
        `source_mode=${String(accountAllocatorRuntime.source_mode || '-')}`,
        `state_source=${firstDefined(accountStateSource, '-')}`,
        `transition_kind=${firstDefined(transitionKind, '-')}`,
        transitionFrom && transitionTo ? `transition_path=${transitionFrom}->${transitionTo}` : '',
        transitionCarryMode ? `carry_mode=${transitionCarryMode}` : '',
        transitionDeRiskMode ? `de_risk_mode=${transitionDeRiskMode}` : '',
        transitionCashMode ? `cash_release_mode=${transitionCashMode}` : '',
        transitionHandoffMode ? `budget_handoff=${transitionHandoffMode}` : '',
        transitionActionMode ? `transition_action=${transitionActionMode}` : '',
        transitionExecutionOwner ? `transition_owner=${transitionExecutionOwner}` : '',
        transitionExecutionStatus ? `transition_status=${transitionExecutionStatus}` : '',
        transitionExecutionReason ? `transition_reason=${transitionExecutionReason}` : '',
        transitionRejectReason ? `transition_reject=${transitionRejectReason}` : '',
        accountStateResolution.resolution_mode ? `resolution_mode=${accountStateResolution.resolution_mode}` : '',
        accountStateTransitionPolicy.contract_version ? `transition_contract=${accountStateTransitionPolicy.contract_version}` : '',
        riskoffLeftSideActive ? 'riskoff_left_side=active' : '',
        riskoffLeftSideActive && defenseAssets ? `defense_assets=${defenseAssets}` : '',
        riskoffLeftSideActive && coreBetaAssets ? `core_beta_assets=${coreBetaAssets}` : '',
        riskoffLeftSideActive ? `target_mix=${fmtPct(riskoffLeftSideAccumulationBudget.defense_weight)} / ${fmtPct(riskoffLeftSideAccumulationBudget.core_beta_weight)}` : '',
      ],
      sleeveBudgets: roleBudgetRows,
    };
  }

  if (!firstDefined(governedSnapshot.budget_owner, governedSnapshot.budget_consumer_sleeve_id) && comboTruthDisplay?.governor?.available) {
    return {
      available: true,
      assetScope: 'research_combo',
      budgetOwner: 'research_combo_anchor',
      consumerSleeveId: String(comboTruthDisplay.governor.budget_consumer_text || '-'),
      consumerRole: 'stock_alpha_sleeve + market_beta_sleeve',
      totalRiskBudget: String(comboTruthDisplay.governor.total_risk_budget_text || '-'),
      totalExposureCap: String(comboTruthDisplay.governor.total_exposure_cap_text || '-'),
      hardMaxPositions: '-',
      effectiveMaxPositions: '-',
      drawdown: '-',
      drawdownState: '-',
      recoveryState: '-',
      cooldownState: '-',
      defenseFloor: '-',
      defenseFloorState: '-',
      defenseBias: '-',
      budgetReasonCodes: [
        stockGovernor.budget_reason_codes?.length ? `个股 ${stockGovernor.budget_reason_codes.join(', ')}` : '',
        etfGovernor.budget_reason_codes?.length ? `ETF ${etfGovernor.budget_reason_codes.join(', ')}` : '',
      ].filter(Boolean),
      localBudgetControls: [],
      sleeveBudgets: [
        stockGovernor.budget_consumer_sleeve_id ? {
          sleeveId: String(stockGovernor.budget_consumer_sleeve_id),
          systemRole: String(stockGovernor.budget_consumer_system_role || '-'),
          slotCap: fmtInt(stockGovernor.effective_max_positions),
          availableSlots: '-',
          selectedCount: '-',
          candidateCount: '-',
          budgetShare: String(stockGovernor.total_risk_budget != null ? fmtPct(stockGovernor.total_risk_budget) : '-'),
        } : null,
        etfGovernor.budget_consumer_sleeve_id ? {
          sleeveId: String(etfGovernor.budget_consumer_sleeve_id),
          systemRole: String(etfGovernor.budget_consumer_system_role || '-'),
          slotCap: fmtInt(etfGovernor.effective_max_positions),
          availableSlots: '-',
          selectedCount: '-',
          candidateCount: '-',
          budgetShare: String(etfGovernor.total_risk_budget != null ? fmtPct(etfGovernor.total_risk_budget) : '-'),
        } : null,
      ].filter(Boolean),
    };
  }

  return {
    available: Boolean(firstDefined(governedSnapshot.budget_owner, governedSnapshot.budget_consumer_sleeve_id)),
    assetScope: firstDefined(governedSnapshot.asset_scope, meta.data?.asset_scope, '-') || '-',
    budgetOwner: firstDefined(governedSnapshot.budget_owner, '-') || '-',
    consumerSleeveId: firstDefined(governedSnapshot.budget_consumer_sleeve_id, '-') || '-',
    consumerRole: firstDefined(governedSnapshot.budget_consumer_system_role, '-') || '-',
    totalRiskBudget: fmtPct(governedSnapshot.total_risk_budget),
    totalExposureCap: fmtPct(governedSnapshot.total_exposure_cap),
    hardMaxPositions: fmtInt(governedSnapshot.hard_max_positions),
    effectiveMaxPositions: fmtInt(governedSnapshot.effective_max_positions),
    drawdown: fmtPct(governedSnapshot.drawdown),
    drawdownState: firstDefined(governedSnapshot.drawdown_state, '-') || '-',
    recoveryState: firstDefined(governedSnapshot.recovery_state, '-') || '-',
    cooldownState: firstDefined(governedSnapshot.cooldown_state, '-') || '-',
    defenseFloor: fmtPct(governedSnapshot.defense_floor),
    defenseFloorState: firstDefined(governedSnapshot.defense_floor_state, '-') || '-',
    defenseBias: fmtPct(governedSnapshot.defense_bias),
    budgetReasonCodes: Array.isArray(governedSnapshot.budget_reason_codes) ? governedSnapshot.budget_reason_codes : [],
    localBudgetControls: Array.isArray(governedSnapshot.local_budget_controls) ? governedSnapshot.local_budget_controls : [],
    sleeveBudgets: Object.entries(sleeveBudgets).map(([sleeveId, payload]) => ({
      sleeveId,
      systemRole: firstDefined(payload?.system_role, '-') || '-',
      slotCap: fmtInt(payload?.slot_cap),
      availableSlots: fmtInt(payload?.available_slots),
      selectedCount: fmtInt(payload?.selected_count),
      candidateCount: fmtInt(payload?.candidate_count),
      budgetShare: fmtPct(payload?.budget_share),
    })),
  };
}

export function buildAttributionPanelModel(snapshot) {
  const meta = snapshot?.artifacts?.run_meta || {};
  const attribution = meta.attribution && typeof meta.attribution === 'object'
    ? meta.attribution
    : {};
  const summary = attribution.summary && typeof attribution.summary === 'object'
    ? attribution.summary
    : {};
  const reasonCodeSummary = attribution.reason_code_summary && typeof attribution.reason_code_summary === 'object'
    ? attribution.reason_code_summary
    : {};

  return {
    available: Boolean(Object.keys(summary).length || Object.keys(reasonCodeSummary).length),
    summaryCards: [
      { label: '状态日志', value: fmtInt(summary.state_log_count) },
      { label: '预算日志', value: fmtInt(summary.budget_log_count) },
      { label: 'Sleeve 日志', value: fmtInt(summary.sleeve_log_count) },
      { label: '人工覆盖日志', value: fmtInt(summary.manual_override_log_count) },
      { label: '状态切换次数', value: fmtInt(summary.state_transition_count) },
      { label: '预算变化次数', value: fmtInt(summary.budget_change_count) },
      { label: '原因码家族数', value: fmtInt(summary.reason_code_family_count) },
    ],
    latestStateDate: firstDefined(summary.latest_state_date, '-') || '-',
    latestBudgetDate: firstDefined(summary.latest_budget_date, '-') || '-',
    latestManualOverrideDate: firstDefined(summary.latest_manual_override_date, '-') || '-',
    sleeves: Array.isArray(summary.sleeves) ? summary.sleeves : [],
    stateReasonCodes: mapObjectEntries(reasonCodeSummary.state_reason_codes),
    budgetReasonCodes: mapObjectEntries(reasonCodeSummary.budget_reason_codes, (value) => fmtInt(value)),
    sleeveReasonCodes: mapObjectEntries(reasonCodeSummary.sleeve_reason_codes, (value) => fmtInt(value)),
    manualOverrideReasons: mapObjectEntries(reasonCodeSummary.manual_override_reasons, (value) => fmtInt(value)),
    refs: attribution.refs && typeof attribution.refs === 'object'
      ? Object.entries(attribution.refs).map(([name, value]) => ({ name, value: String(value || '-') }))
      : [],
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

