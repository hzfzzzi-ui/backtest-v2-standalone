/* report.js - AI-friendly Markdown report generation */
/* Globals used: state, byId, addLog, reasonZh, reasonByPrefix, buildStageRows */

function _reportNum(v, digits = 2) {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(digits) : '-';
}

function _reportPct(v) {
  const n = Number(v);
  return Number.isFinite(n) ? `${(n * 100).toFixed(2)}%` : '-';
}

function _reportInt(v) {
  const n = Number(v);
  return Number.isFinite(n) ? Math.round(n).toLocaleString('en-US') : '-';
}

function _reportMoney(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-';
}

function _reportVal(v) {
  if (v == null) return '-';
  const text = String(v).trim();
  return text || '-';
}

function _reportCell(v) {
  return _reportVal(v).replace(/\|/g, '\\|').replace(/\r?\n/g, ' ');
}

function _reportTable(headers, rows) {
  const head = `| ${headers.map(_reportCell).join(' | ')} |`;
  const sep = `| ${headers.map(() => '---').join(' | ')} |`;
  const body = (rows || []).map((row) => `| ${row.map(_reportCell).join(' | ')} |`);
  return [head, sep, ...body].join('\n');
}

function _reportFirst(...values) {
  for (const value of values) {
    if (value == null) continue;
    if (typeof value === 'string' && !value.trim()) continue;
    return value;
  }
  return null;
}

function _deriveTop10AverageReturn(rows) {
  const values = (Array.isArray(rows) ? rows : [])
    .map((row) => Number(row?.return_pct))
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => b - a)
    .slice(0, 10);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function _reportScalarCounters(counters) {
  return Object.entries(counters || {})
    .filter(([key, value]) => key !== 'buy_stage_funnel' && value != null && (typeof value === 'number' || typeof value === 'string' || typeof value === 'boolean'))
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
    .map(([key, value]) => [String(key), typeof value === 'number' ? _reportNum(value, Number.isInteger(value) ? 0 : 6) : String(value)]);
}

function _normalizeName(value) {
  return String(value || '').trim().toLowerCase();
}

function _moduleLabel(name) {
  const normalized = _normalizeName(name);
  if (normalized === 'breakout_55') return 'Breakout 55';
  if (normalized === 'rsi_reversal') return 'RSI Reversal';
  return String(name || '-');
}

function _formatCounts(counts) {
  const obj = counts && typeof counts === 'object' ? counts : {};
  const items = Object.entries(obj)
    .filter(([, value]) => value != null)
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])));
  if (!items.length) return '-';
  return items.map(([key, value]) => `${_moduleLabel(key)}:${_reportInt(value)}`).join(', ');
}

function _formatRegimeMatrix(regimeMatrix) {
  const matrix = regimeMatrix && typeof regimeMatrix === 'object' ? regimeMatrix : {};
  const regimes = ['TREND_UP', 'RANGE', 'WEAK_DOWN'];
  return regimes.map((regime) => {
    const values = Array.isArray(matrix[regime]) ? matrix[regime] : [];
    return `${regime}=${values.map((name) => _moduleLabel(name)).join(' + ') || '-'}`;
  }).join(' | ');
}

function _moduleList(modules) {
  return (Array.isArray(modules) ? modules : [])
    .map((module) => _moduleLabel(module?.name || module))
    .filter(Boolean)
    .join(' + ');
}

function _extractCompositeConfig(config) {
  const originalWb = config?.overrides?.original_workbench_config || {};
  const modules = Array.isArray(originalWb?.signal_generation?.modules) ? originalWb.signal_generation.modules : [];
  if (!modules.length) return null;
  return {
    modules,
    composition: originalWb?.signal_composition || {},
    portfolioMode: originalWb?.position_risk?.portfolio_mode || '-',
  };
}

function _fallbackStageRows(art) {
  return Array.isArray(art?.funnelRows) ? art.funnelRows : [];
}

function buildAgentMarkdownReport() {
  const art = state.active_artifacts || {};
  const result = state.active_result || {};
  if (!result.exp_id) {
    return '# AI Analysis Report\n\nNo experiment is loaded.';
  }

  const perf = art.perf || {};
  const meta = art.run_meta || {};
  const counters = meta.counters || {};
  const config = art.config || {};
  const audit = art.audit || {};
  const auditSummary = audit.summary || {};
  const reportConsistency = meta.report_consistency || {};
  const resolvedMeta = reportConsistency.resolved_config_meta || {};
  const symbolRows = (art.symbolPerformanceRows || []).slice().sort((a, b) => Number(b?.return_pct || 0) - Number(a?.return_pct || 0));
  const exitRows = ((typeof reasonByPrefix === 'function' ? reasonByPrefix(art.reasonRows || []).exit : []) || [])
    .map((row) => ({
      code: String(row?.code || row?.reason_code || '').toUpperCase(),
      count: Number(row?.count || 0),
    }))
    .filter((row) => row.code && row.count > 0)
    .sort((a, b) => b.count - a.count);
  const stageRows = typeof buildStageRows === 'function' ? buildStageRows(art, counters) : _fallbackStageRows(art);
  const navSeries = Array.isArray(art.navSeries) ? art.navSeries : [];
  const top10AvgReturn = _reportFirst(_deriveTop10AverageReturn(symbolRows), perf.top10_avg_return_pct, result.top10_avg_return_pct);
  const navStart = Number(navSeries[0]?.value);
  const navEnd = Number(navSeries[navSeries.length - 1]?.value);
  const topExit = exitRows[0] || null;
  const totalExitCount = exitRows.reduce((sum, row) => sum + Number(row.count || 0), 0);
  const missingStages = stageRows.filter((row) => row?.available === false).map((row) => String(row?.stage_key || '').toUpperCase()).filter(Boolean);
  const scalarCounters = _reportScalarCounters(counters);
  const originalWb = config?.overrides?.original_workbench_config || {};
  const compositeConfig = _extractCompositeConfig(config);

  const lines = [
    '# Backtest Analysis Report',
    '',
    '## 1. Basic Info',
    _reportTable(
      ['Field', 'Value'],
      [
        ['exp_id', result.exp_id],
        ['status', result.status || meta.status || '-'],
        ['tier', _reportFirst(meta.tier, result.tier)],
        ['start', _reportFirst(meta.data?.start, originalWb?.universe?.start)],
        ['end', _reportFirst(meta.data?.end, originalWb?.universe?.end)],
        ['benchmark', _reportFirst(meta.data?.benchmark, originalWb?.universe?.benchmark)],
        ['universe_mode', _reportFirst(meta.universe?.universe_mode, meta.data?.universe_mode, resolvedMeta.universe_mode, originalWb?.universe_mode)],
        ['symbols_raw_to_tradable', `${_reportInt(meta.universe?.raw_count)} -> ${_reportInt(meta.universe?.after_filters_symbols)}`],
        ['config_source', reportConsistency.config_source || config.config_source || '-'],
        ['resolved_config_mode', reportConsistency.resolved_config_mode || '-'],
        ['resolved_config_id', reportConsistency.resolved_config_id || '-'],
        ['resolved_config_hash', reportConsistency.resolved_config_hash || '-'],
      ],
    ),
    '',
    '## 2. Core Metrics',
    _reportTable(
      ['Metric', 'Value'],
      [
        ['initial_capital', Number.isFinite(navStart) ? _reportMoney(navStart) : '-'],
        ['final_capital', Number.isFinite(navEnd) ? _reportMoney(navEnd) : '-'],
        ['cagr', _reportPct(_reportFirst(perf.cagr, result.cagr))],
        ['total_return', _reportPct(_reportFirst(perf.total_return, result.total_return))],
        ['max_drawdown', _reportPct(_reportFirst(perf.max_drawdown, result.max_drawdown))],
        ['sharpe', _reportNum(_reportFirst(perf.sharpe, result.sharpe), 2)],
        ['calmar', _reportNum(_reportFirst(perf.calmar, result.calmar), 2)],
        ['trades', _reportInt(_reportFirst(perf.trades, result.trades))],
        ['turnover', _reportPct(_reportFirst(perf.turnover, result.turnover))],
        ['top10_avg_return', _reportPct(top10AvgReturn)],
      ],
    ),
    '',
    '## 3. AI Summary',
    `- top_exit_reason: ${topExit ? `${reasonZh(topExit.code)} (${topExit.code})` : '-'}`,
    `- top_exit_count: ${topExit ? _reportInt(topExit.count) : '-'}`,
    `- top_exit_ratio: ${topExit && totalExitCount > 0 ? _reportPct(topExit.count / totalExitCount) : '-'}`,
    `- buy_orders: ${_reportInt(counters.buy_orders_count)}`,
    `- sell_orders: ${_reportInt(counters.sell_orders_count)}`,
    `- missing_stage_counters: ${missingStages.length ? missingStages.join(', ') : 'none'}`,
    '',
    '## 4. 9-Stage Funnel',
    _reportTable(
      ['stage', 'label', 'input_cnt', 'keep_cnt', 'filtered_cnt', 'available', 'note'],
      stageRows.map((row) => [
        String(row?.stage_key || '').toUpperCase(),
        row?.stage_label || '-',
        _reportInt(row?.input_count),
        _reportInt(row?.output_count),
        _reportInt(row?.filtered_count),
        row?.available === false ? 'false' : 'true',
        row?.note || '-',
      ]),
    ),
    '',
    '## 5. Exit Analysis',
    _reportTable(
      ['reason_zh', 'reason_code', 'count', 'ratio'],
      exitRows.length
        ? exitRows.map((row) => [reasonZh(row.code), row.code, _reportInt(row.count), _reportPct(totalExitCount > 0 ? row.count / totalExitCount : 0)])
        : [['-', '-', '-', '-']],
    ),
    '',
    '## 6. Multi-Alpha Audit',
    _reportTable(
      ['field', 'value'],
      [
        ['contract_version', audit.contract_version || '-'],
        ['raw_signal_counts_by_alpha', _formatCounts(auditSummary.raw_signal_counts_by_alpha)],
        ['composed_signal_counts_by_alpha', _formatCounts(auditSummary.composed_signal_counts_by_alpha)],
        ['blocked_signal_counts_by_reason', _formatCounts(auditSummary.blocked_signal_counts_by_reason)],
        ['conflict_resolution_counts', _formatCounts(auditSummary.conflict_resolution_counts)],
        ['source_only_exit_count', _reportInt(auditSummary.source_only_exit_count)],
        ['global_risk_override_count', _reportInt(auditSummary.global_risk_override_count)],
      ],
    ),
    '',
    '## 7. Strategy Config',
    _reportTable(
      ['field', 'value'],
      compositeConfig
        ? [
            ['strategy', 'COMPOSITE'],
            ['modules', _moduleList(compositeConfig.modules)],
            ['compose_mode', compositeConfig.composition?.compose_mode || '-'],
            ['same_symbol_policy', compositeConfig.composition?.same_symbol_policy || '-'],
            ['holding_ownership', compositeConfig.composition?.holding_ownership || '-'],
            ['portfolio_mode', compositeConfig.portfolioMode],
            ['regime_matrix', _formatRegimeMatrix(compositeConfig.composition?.regime_matrix)],
          ]
        : [
            ['strategy', originalWb?.signal_generation?.strategy || '-'],
            ['portfolio_mode', originalWb?.position_risk?.portfolio_mode || '-'],
            ['price_adj', originalWb?.universe?.price_adj || meta.price_adj_mode || '-'],
          ],
    ),
    '',
    '## 8. Top Symbols',
    _reportTable(
      ['rank', 'symbol', 'return', 'max_drawdown', 'trades'],
      symbolRows.slice(0, 10).map((row, idx) => [
        String(idx + 1),
        row?.symbol || '-',
        _reportPct(row?.return_pct),
        _reportPct(row?.max_drawdown),
        _reportInt(row?.trades),
      ]),
    ),
    '',
    '## 9. Raw Counters',
    _reportTable(
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

function renderAgentMarkdownReport() {
  const box = byId('wbAgentReportMd');
  const meta = byId('wbAgentReportMeta');
  if (!box) return;
  const text = buildAgentMarkdownReport();
  box.value = text;
  const expId = state.active_result?.exp_id || '-';
  const symbolCount = (state.active_artifacts?.symbolPerformanceRows || []).length;
  if (meta) meta.textContent = `exp_id=${expId} | top_symbols=${symbolCount} | markdown_ready`;
}

function _downloadAgentMarkdown(text) {
  const expId = state.active_result?.exp_id || 'report';
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${expId}_agent_report.md`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function copyAgentMarkdownReport() {
  const text = buildAgentMarkdownReport();
  try {
    await navigator.clipboard.writeText(text);
    addLog('Markdown report copied');
  } catch (error) {
    addLog(`Copy failed: ${error?.message || error}`);
  }
}

function bindReportTools() {
  byId('wbCopyReportMd')?.addEventListener('click', () => {
    copyAgentMarkdownReport().catch((error) => addLog(`Copy failed: ${error?.message || error}`));
  });
  byId('wbExportReport')?.addEventListener('click', () => {
    _downloadAgentMarkdown(buildAgentMarkdownReport());
  });
}