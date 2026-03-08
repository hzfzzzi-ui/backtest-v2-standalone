export function fmtNum(value, digits = 2) {
  const num = Number(value);
  return Number.isFinite(num) ? num.toFixed(digits) : '-';
}

export function fmtPct(value, digits = 2) {
  const num = Number(value);
  return Number.isFinite(num) ? `${(num * 100).toFixed(digits)}%` : '-';
}

export function fmtInt(value) {
  const num = Number(value);
  return Number.isFinite(num) ? Math.round(num).toLocaleString('en-US') : '-';
}

export function fmtMoney(value) {
  const num = Number(value);
  return Number.isFinite(num)
    ? num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : '-';
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

export function deriveTop10AverageReturn(rows) {
  const values = (Array.isArray(rows) ? rows : [])
    .map((row) => Number(row?.return_pct))
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => b - a)
    .slice(0, 10);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function stockZh(symbol) {
  try {
    if (typeof window.stockZh === 'function') return window.stockZh(symbol);
  } catch (_) {
    return symbol;
  }
  return symbol;
}

export function summarizeSnapshot(snapshot) {
  const result = snapshot?.result || {};
  const artifacts = snapshot?.artifacts || {};
  const perf = artifacts.perf || {};
  const meta = artifacts.run_meta || {};
  const navSeries = Array.isArray(artifacts.navSeries) ? artifacts.navSeries : [];
  const symbolRows = Array.isArray(artifacts.symbolPerformanceRows) ? artifacts.symbolPerformanceRows : [];
  const top10AvgReturn = firstDefined(
    deriveTop10AverageReturn(symbolRows),
    perf.top10_avg_return_pct,
    result.top10_avg_return_pct,
  );
  const navStart = Number(navSeries[0]?.value);
  const navEnd = Number(navSeries[navSeries.length - 1]?.value);
  const rawCount = meta.universe?.raw_count;
  const filteredCount = firstDefined(meta.universe?.after_filters_symbols, meta.universe?.tradable_symbols);
  const universeCount = Number.isFinite(Number(rawCount))
    ? (Number.isFinite(Number(filteredCount)) ? `${fmtInt(rawCount)} -> ${fmtInt(filteredCount)}` : fmtInt(rawCount))
    : '-';

  return {
    expId: result.exp_id || '-',
    status: result.status || '等待运行',
    configSource: firstDefined(meta.report_consistency?.config_source, result.config_source, '草稿'),
    universeRange: `${firstDefined(meta.data?.start, '-') || '-'} ~ ${firstDefined(meta.data?.end, '-') || '-'}`,
    benchmark: firstDefined(meta.data?.benchmark, '-') || '-',
    universeMode: firstDefined(meta.universe?.universe_mode, meta.data?.universe_mode, '-') || '-',
    universeCount,
    strategy: firstDefined(meta.strategy?.name, result.strategy_name, '-') || '-',
    strategyCore: firstDefined(meta.strategy?.core, result.strategy_core, '-') || '-',
    portfolioMode: firstDefined(meta.strategy?.portfolio_mode, result.portfolio_mode, '-') || '-',
    strategySummary: firstDefined(meta.strategy?.summary, result.strategy_summary, '-') || '-',
    initialCapital: Number.isFinite(navStart) ? fmtMoney(navStart) : '-',
    finalCapital: Number.isFinite(navEnd) ? fmtMoney(navEnd) : '-',
    cagr: fmtPct(firstDefined(perf.cagr, result.cagr)),
    totalReturn: fmtPct(firstDefined(perf.total_return, result.total_return)),
    maxDrawdown: fmtPct(firstDefined(perf.max_drawdown, result.max_drawdown)),
    sharpe: fmtNum(firstDefined(perf.sharpe, result.sharpe), 2),
    calmar: fmtNum(firstDefined(perf.calmar, result.calmar), 2),
    trades: fmtInt(firstDefined(perf.trades, result.trades)),
    turnover: fmtPct(firstDefined(perf.turnover, result.turnover)),
    top10AvgReturn: fmtPct(top10AvgReturn),
    tier: firstDefined(perf.tier, result.tier, meta.tier) || '-',
    groupLoadStatus: artifacts?.missing?.length
      ? `缺少 ${String(artifacts.missing.length)} 个产物，请查看状态中心`
      : '产物已加载',
  };
}

export function buildUnifiedStageFunnelHtml(snapshot) {
  const artifacts = snapshot?.artifacts || {};
  const counters = artifacts?.run_meta?.counters || {};
  const buildRows = typeof window._finalBuildStageRows === 'function' ? window._finalBuildStageRows : null;
  const render = typeof window.renderUnifiedStageFunnel === 'function' ? window.renderUnifiedStageFunnel : null;
  const reasonByPrefix = typeof window.reasonByPrefix === 'function' ? window.reasonByPrefix : null;
  if (!buildRows || !render || !reasonByPrefix) {
    return {
      html: '<div class="wb-mini">结果工作台尚未接入统一漏斗 helper。</div>',
      meta: '等待结果',
    };
  }
  const stageRows = buildRows(artifacts, counters);
  const exitRows = reasonByPrefix(artifacts.reasonRows || []).exit || [];
  return {
    html: render(stageRows, counters, exitRows),
    meta: `买入 ${fmtInt(counters?.buy_orders_count ?? 0)} 笔 | 卖出 ${fmtInt(counters?.sell_orders_count ?? 0)} 笔 | stage=${fmtInt(stageRows.length)}`,
  };
}

export function buildAgentMarkdown(snapshot) {
  try {
    if (typeof window.buildAgentMarkdownReport === 'function') return window.buildAgentMarkdownReport(snapshot);
  } catch (_) {
    return '# AI分析报告（Markdown）\n\n当前报告生成器不可用。';
  }
  return '# AI分析报告（Markdown）\n\n当前报告生成器不可用。';
}

export function normalizeTradesRows(snapshot) {
  return Array.isArray(snapshot?.artifacts?.tradesRows) ? snapshot.artifacts.tradesRows : [];
}

export function normalizeSymbolRows(snapshot) {
  return Array.isArray(snapshot?.artifacts?.symbolPerformanceRows) ? snapshot.artifacts.symbolPerformanceRows.slice() : [];
}
