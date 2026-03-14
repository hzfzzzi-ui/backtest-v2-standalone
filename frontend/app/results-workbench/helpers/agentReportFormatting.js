import { buildStageRows, reasonByPrefix, reasonZh } from './stageFunnelFormatting.js';

function fmtNum(value, digits = 2) {
  const num = Number(value);
  return Number.isFinite(num) ? num.toFixed(digits) : '-';
}

function fmtPct(value) {
  const num = Number(value);
  return Number.isFinite(num) ? `${(num * 100).toFixed(2)}%` : '-';
}

function fmtInt(value) {
  const num = Number(value);
  return Number.isFinite(num) ? Math.round(num).toLocaleString('en-US') : '-';
}

function fmtMoney(value) {
  const num = Number(value);
  return Number.isFinite(num)
    ? num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : '-';
}

function reportValue(value) {
  if (value == null) return '-';
  const text = String(value).trim();
  return text || '-';
}

function reportCell(value) {
  return reportValue(value).replace(/\|/g, '\\|').replace(/\r?\n/g, ' ');
}

function reportTable(headers, rows) {
  const head = `| ${headers.map(reportCell).join(' | ')} |`;
  const sep = `| ${headers.map(() => '---').join(' | ')} |`;
  const body = (rows || []).map((row) => `| ${row.map(reportCell).join(' | ')} |`);
  return [head, sep, ...body].join('\n');
}

function firstDefined(...values) {
  for (const value of values) {
    if (value == null) continue;
    if (typeof value === 'string' && !value.trim()) continue;
    return value;
  }
  return null;
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

function reportScalarCounters(counters) {
  return Object.entries(counters || {})
    .filter(([key, value]) => key !== 'buy_stage_funnel' && value != null && (typeof value === 'number' || typeof value === 'string' || typeof value === 'boolean'))
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
    .map(([key, value]) => [String(key), typeof value === 'number' ? fmtNum(value, Number.isInteger(value) ? 0 : 6) : String(value)]);
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

function formatCounts(counts) {
  const obj = counts && typeof counts === 'object' ? counts : {};
  const items = Object.entries(obj)
    .filter(([, value]) => value != null)
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])));
  if (!items.length) return '-';
  return items.map(([key, value]) => `${moduleLabel(key)}:${fmtInt(value)}`).join(', ');
}

function moduleList(modules) {
  return (Array.isArray(modules) ? modules : [])
    .map((module) => moduleLabel(module?.name || module))
    .filter(Boolean)
    .join(' + ');
}

function formatRegimeMatrix(regimeMatrix) {
  const matrix = regimeMatrix && typeof regimeMatrix === 'object' ? regimeMatrix : {};
  const regimes = ['TREND_UP', 'RANGE', 'WEAK_DOWN'];
  return regimes.map((regime) => {
    const values = Array.isArray(matrix[regime]) ? matrix[regime] : [];
    return `${regime}=${values.map((name) => moduleLabel(name)).join(' + ') || '-'}`;
  }).join(' | ');
}

function extractCompositeConfig(config) {
  const originalWorkbench = config?.overrides?.original_workbench_config || {};
  const signalGeneration = originalWorkbench?.signal_generation || {};
  const modules = Array.isArray(signalGeneration.modules) ? signalGeneration.modules : [];
  if (!modules.length) return null;
  return {
    modules,
    composition: originalWorkbench?.signal_composition || {},
    portfolioMode: originalWorkbench?.position_risk?.portfolio_mode || '-',
  };
}

export function buildAgentMarkdownFromSnapshot(snapshot) {
  const artifacts = snapshot?.artifacts || {};
  const result = snapshot?.result || {};
  if (!result.exp_id) {
    return '# AI Analysis Report\n\nNo experiment is loaded.';
  }

  const perf = artifacts.perf || {};
  const meta = artifacts.run_meta || {};
  const counters = meta.counters || {};
  const config = artifacts.config || {};
  const audit = artifacts.audit || {};
  const auditSummary = audit.summary || {};
  const reportConsistency = meta.report_consistency || {};
  const resolvedMeta = reportConsistency.resolved_config_meta || {};
  const symbolRows = (artifacts.symbolPerformanceRows || []).slice().sort((a, b) => Number(b?.return_pct || 0) - Number(a?.return_pct || 0));
  const exitRows = (reasonByPrefix(artifacts.reasonRows || []).exit || [])
    .map((row) => ({
      code: String(row?.code || row?.reason_code || '').toUpperCase(),
      count: Number(row?.count || 0),
    }))
    .filter((row) => row.code && row.count > 0)
    .sort((a, b) => b.count - a.count);
  const stageRows = buildStageRows(artifacts, counters);
  const navSeries = Array.isArray(artifacts.navSeries) ? artifacts.navSeries : [];
  const top10AvgReturn = firstDefined(deriveTop10AverageReturn(symbolRows), perf.top10_avg_return_pct, result.top10_avg_return_pct);
  const navStart = Number(navSeries[0]?.value);
  const navEnd = Number(navSeries[navSeries.length - 1]?.value);
  const topExit = exitRows[0] || null;
  const totalExitCount = exitRows.reduce((sum, row) => sum + Number(row.count || 0), 0);
  const missingStages = stageRows.filter((row) => row?.available === false).map((row) => String(row?.stage_key || '').toUpperCase()).filter(Boolean);
  const scalarCounters = reportScalarCounters(counters);
  const originalWorkbench = config?.overrides?.original_workbench_config || {};
  const compositeConfig = extractCompositeConfig(config);

  const lines = [
    '# Backtest Analysis Report',
    '',
    '## 1. Basic Info',
    reportTable(
      ['Field', 'Value'],
      [
        ['exp_id', result.exp_id],
        ['status', result.status || meta.status || '-'],
        ['tier', firstDefined(meta.tier, result.tier)],
        ['start', firstDefined(meta.data?.start, originalWorkbench?.universe?.start)],
        ['end', firstDefined(meta.data?.end, originalWorkbench?.universe?.end)],
        ['benchmark', firstDefined(meta.data?.benchmark, originalWorkbench?.universe?.benchmark)],
        ['universe_mode', firstDefined(meta.universe?.universe_mode, meta.data?.universe_mode, resolvedMeta.universe_mode, originalWorkbench?.universe_mode)],
        ['symbols_raw_to_tradable', `${fmtInt(meta.universe?.raw_count)} -> ${fmtInt(meta.universe?.after_filters_symbols)}`],
        ['config_source', reportConsistency.config_source || config.config_source || '-'],
        ['resolved_config_mode', reportConsistency.resolved_config_mode || '-'],
        ['resolved_config_id', reportConsistency.resolved_config_id || '-'],
        ['resolved_config_hash', reportConsistency.resolved_config_hash || '-'],
      ],
    ),
    '',
    '## 2. Core Metrics',
    reportTable(
      ['Metric', 'Value'],
      [
        ['initial_capital', Number.isFinite(navStart) ? fmtMoney(navStart) : '-'],
        ['final_capital', Number.isFinite(navEnd) ? fmtMoney(navEnd) : '-'],
        ['cagr', fmtPct(firstDefined(perf.cagr, result.cagr))],
        ['total_return', fmtPct(firstDefined(perf.total_return, result.total_return))],
        ['max_drawdown', fmtPct(firstDefined(perf.max_drawdown, result.max_drawdown))],
        ['sharpe', fmtNum(firstDefined(perf.sharpe, result.sharpe), 2)],
        ['calmar', fmtNum(firstDefined(perf.calmar, result.calmar), 2)],
        ['trades', fmtInt(firstDefined(perf.trades, result.trades))],
        ['turnover', fmtPct(firstDefined(perf.turnover, result.turnover))],
        ['top10_avg_return', fmtPct(top10AvgReturn)],
      ],
    ),
    '',
    '## 3. AI Summary',
    `- top_exit_reason: ${topExit ? `${reasonZh(topExit.code)} (${topExit.code})` : '-'}`,
    `- top_exit_count: ${topExit ? fmtInt(topExit.count) : '-'}`,
    `- top_exit_ratio: ${topExit && totalExitCount > 0 ? fmtPct(topExit.count / totalExitCount) : '-'}`,
    `- buy_orders: ${fmtInt(counters.buy_orders_count)}`,
    `- sell_orders: ${fmtInt(counters.sell_orders_count)}`,
    `- missing_stage_counters: ${missingStages.length ? missingStages.join(', ') : 'none'}`,
    '',
    '## 4. 9-Stage Funnel',
    reportTable(
      ['stage', 'label', 'input_cnt', 'keep_cnt', 'filtered_cnt', 'available', 'note'],
      stageRows.map((row) => [
        String(row?.stage_key || '').toUpperCase(),
        row?.stage_label || '-',
        fmtInt(row?.input_count),
        fmtInt(row?.output_count),
        fmtInt(row?.filtered_count),
        row?.available === false ? 'false' : 'true',
        row?.note || '-',
      ]),
    ),
    '',
    '## 5. Exit Analysis',
    reportTable(
      ['reason_zh', 'reason_code', 'count', 'ratio'],
      exitRows.length
        ? exitRows.map((row) => [reasonZh(row.code), row.code, fmtInt(row.count), fmtPct(totalExitCount > 0 ? row.count / totalExitCount : 0)])
        : [['-', '-', '-', '-']],
    ),
    '',
    '## 6. Multi-Alpha Audit',
    reportTable(
      ['field', 'value'],
      [
        ['contract_version', audit.contract_version || '-'],
        ['raw_signal_counts_by_alpha', formatCounts(auditSummary.raw_signal_counts_by_alpha)],
        ['composed_signal_counts_by_alpha', formatCounts(auditSummary.composed_signal_counts_by_alpha)],
        ['blocked_signal_counts_by_reason', formatCounts(auditSummary.blocked_signal_counts_by_reason)],
        ['conflict_resolution_counts', formatCounts(auditSummary.conflict_resolution_counts)],
        ['source_only_exit_count', fmtInt(auditSummary.source_only_exit_count)],
        ['global_risk_override_count', fmtInt(auditSummary.global_risk_override_count)],
      ],
    ),
    '',
    '## 7. Strategy Config',
    reportTable(
      ['field', 'value'],
      compositeConfig
        ? [
            ['strategy', 'COMPOSITE'],
            ['modules', moduleList(compositeConfig.modules)],
            ['compose_mode', compositeConfig.composition?.compose_mode || '-'],
            ['same_symbol_policy', compositeConfig.composition?.same_symbol_policy || '-'],
            ['holding_ownership', compositeConfig.composition?.holding_ownership || '-'],
            ['portfolio_mode', compositeConfig.portfolioMode],
            ['regime_matrix', formatRegimeMatrix(compositeConfig.composition?.regime_matrix)],
          ]
        : [
            ['strategy', originalWorkbench?.signal_generation?.strategy || '-'],
            ['portfolio_mode', originalWorkbench?.position_risk?.portfolio_mode || '-'],
            ['price_adj', originalWorkbench?.universe?.price_adj || meta.price_adj_mode || '-'],
          ],
    ),
    '',
    '## 8. Top Symbols',
    reportTable(
      ['rank', 'symbol', 'return', 'max_drawdown', 'trades'],
      symbolRows.slice(0, 10).map((row, index) => [
        String(index + 1),
        row?.symbol || '-',
        fmtPct(row?.return_pct),
        fmtPct(row?.max_drawdown),
        fmtInt(row?.trades),
      ]),
    ),
    '',
    '## 9. Raw Counters',
    reportTable(
      ['counter_key', 'value'],
      scalarCounters.length ? scalarCounters : [['-', '-']],
    ),
    '',
    '## 10. Notes',
    '- This markdown is optimized for GPT/agent review and keeps audit fields explicit.',
    '- Multi-alpha summary is sourced from original_workbench_config and audit.json when available.',
    `- Generated at: ${new Date().toLocaleString('zh-CN')}`,
    '',
  ];

  return lines.join('\n');
}