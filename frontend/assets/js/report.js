/* report.js - AI-friendly Markdown report generation */
/* Globals used: state, byId, addLog, reasonZh */

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

function _reportExitRows(reasonRows) {
  const rows = Array.isArray(reasonRows) ? reasonRows : [];
  return rows
    .map((row) => ({
      code: String(row?.code || row?.reason_code || '').toUpperCase(),
      count: Number(row?.count || 0),
    }))
    .filter((row) => row.code && row.count > 0 && (row.code.includes('EXIT') || row.code.includes('ATR_') || ['TAKE_PROFIT', 'FIXED_STOP_LOSS', 'STOP_LOSS', 'SIGNAL_REVERSE', 'TREND_REVERSE', 'RISK_OFF_EXIT'].includes(row.code)))
    .sort((a, b) => b.count - a.count);
}

function _reportSumDailyInt(rows, key) {
  return (Array.isArray(rows) ? rows : []).reduce((sum, row) => {
    const value = Number(row?.[key]);
    return sum + (Number.isFinite(value) ? value : 0);
  }, 0);
}

function _reportScalarCounters(counters) {
  return Object.entries(counters || {})
    .filter(([key, value]) => key !== 'buy_stage_funnel' && value != null && (typeof value === 'number' || typeof value === 'string' || typeof value === 'boolean'))
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
    .map(([key, value]) => [String(key), typeof value === 'number' ? _reportNum(value, Number.isInteger(value) ? 0 : 6) : String(value)]);
}

function _reportNormalizedStageRows(art, counters) {
  const buyStageRows = Array.isArray(counters?.buy_stage_funnel) ? counters.buy_stage_funnel : [];
  const dailyRows = Array.isArray(art?.dailyRows) ? art.dailyRows : [];
  const buyCandidates = _reportSumDailyInt(dailyRows, 'buy_candidate_count');
  const rawSignals = _reportSumDailyInt(dailyRows, 'raw_buy_signal_count');
  const buyOrders = Number(counters?.buy_orders_count ?? 0);
  const minHoldBlockCount = Number(counters?.min_hold_block_count ?? 0);
  const cooldownBlockCount = Number(counters?.cooldown_block_count ?? 0);
  const heldDupBlockCount = Math.max(rawSignals - buyCandidates - minHoldBlockCount - cooldownBlockCount, 0);
  const mfRankAppliedDays = Number(counters?.mf_rank_applied_days ?? 0);
  const mfTopkRejectCount = Number(counters?.mf_topk_reject_count ?? 0);
  const rankActuallyApplied = mfRankAppliedDays > 0 || mfTopkRejectCount > 0;
  return buyStageRows.map((row) => {
    const key = String(row?.stage_key || '').toLowerCase();
    if (key === 's4') {
      const inputCount = Number(row?.input_count);
      const outputCount = buyCandidates > 0 ? buyCandidates : Number(row?.output_count);
      return {
        ...row,
        output_count: outputCount,
        filtered_count: Number.isFinite(inputCount) && Number.isFinite(outputCount) ? Math.max(inputCount - outputCount, 0) : row?.filtered_count,
        note: `原始买点=${_reportInt(rawSignals)}；已持仓/再入场约束去重=${_reportInt(heldDupBlockCount + minHoldBlockCount + cooldownBlockCount)}`,
      };
    }
    if (key === 's5') {
      const inputCount = buyCandidates > 0 ? buyCandidates : Number(row?.input_count);
      const outputCount = rankActuallyApplied ? Math.max(inputCount - mfTopkRejectCount, 0) : inputCount;
      return {
        ...row,
        input_count: inputCount,
        output_count: outputCount,
        filtered_count: Math.max(inputCount - outputCount, 0),
        note: rankActuallyApplied
          ? `排序层实际过滤=${_reportInt(mfTopkRejectCount)}`
          : '当前基线未启用独立排序截断，排序层按实际显示为 0 过滤',
      };
    }
    if (key === 's6') {
      const inputCount = rankActuallyApplied
        ? Math.max((buyCandidates > 0 ? buyCandidates : Number(row?.input_count)) - mfTopkRejectCount, 0)
        : (buyCandidates > 0 ? buyCandidates : Number(row?.input_count));
      return {
        ...row,
        input_count: inputCount,
        output_count: buyOrders,
        filtered_count: Number.isFinite(inputCount) ? Math.max(inputCount - buyOrders, 0) : row?.filtered_count,
        note: '55日突破等入场事件在本层收口为最终实际开仓次数',
      };
    }
    if (key === 's7') {
      return {
        ...row,
        stage_label: 'S7 仓位控制',
        input_count: buyOrders,
        output_count: buyOrders,
        filtered_count: 0,
        note: '当前基线未稳定输出独立 slot stage 计数，沿用最终开仓数量展示仓位控制层',
      };
    }
    return row;
  });
}

function buildAgentMarkdownReport() {
  const art = state.active_artifacts || {};
  const result = state.active_result || {};
  if (!result.exp_id) {
    return '# AI分析报告（Markdown）\n\n当前没有已加载的实验结果。';
  }

  const perf = art.perf || {};
  const meta = art.run_meta || {};
  const counters = meta.counters || {};
  const config = art.config || {};
  const reportConsistency = meta.report_consistency || {};
  const resolvedMeta = reportConsistency.resolved_config_meta || {};
  const symbolRows = (art.symbolPerformanceRows || []).slice().sort((a, b) => Number(b?.return_pct || 0) - Number(a?.return_pct || 0));
  const exitRows = _reportExitRows(art.reasonRows || []);
  const buyStageRows = _reportNormalizedStageRows(art, counters);
  const navSeries = Array.isArray(art.navSeries) ? art.navSeries : [];
  const top10AvgReturn = _reportFirst(_deriveTop10AverageReturn(symbolRows), perf.top10_avg_return_pct, result.top10_avg_return_pct);
  const navStart = Number(navSeries[0]?.value);
  const navEnd = Number(navSeries[navSeries.length - 1]?.value);
  const topExit = exitRows[0] || null;
  const totalExitCount = exitRows.reduce((sum, row) => sum + Number(row.count || 0), 0);
  const missingStages = buyStageRows.filter((row) => row?.available === false).map((row) => String(row?.stage_key || '').toUpperCase()).filter(Boolean);
  const scalarCounters = _reportScalarCounters(counters);
  const overrides = config.overrides || {};
  const originalWb = overrides.original_workbench_config || {};
  const signalCfg = originalWb.signal_generation || {};
  const exitCfg = originalWb.exit_rules || {};
  const positionCfg = originalWb.position_risk || {};
  const universeCfg = originalWb.universe || {};

  const lines = [
    '# 回测分析报告',
    '',
    '## 1. 基本信息',
    _reportTable(
      ['字段', '值'],
      [
        ['exp_id', result.exp_id],
        ['status', result.status || meta.status || '-'],
        ['tier', _reportFirst(meta.tier, result.tier)],
        ['start', _reportFirst(meta.data?.start, universeCfg.start)],
        ['end', _reportFirst(meta.data?.end, universeCfg.end)],
        ['benchmark', _reportFirst(meta.data?.benchmark, universeCfg.benchmark)],
        ['universe_mode', _reportFirst(meta.universe?.universe_mode, meta.data?.universe_mode, resolvedMeta.universe_mode, universeCfg.mode)],
        ['symbols_raw_to_tradable', `${_reportInt(meta.universe?.raw_count)} -> ${_reportInt(meta.universe?.after_filters_symbols)}`],
        ['config_source', reportConsistency.config_source || config.config_source || '-'],
        ['resolved_config_mode', reportConsistency.resolved_config_mode || '-'],
        ['resolved_config_id', reportConsistency.resolved_config_id || '-'],
        ['resolved_config_hash', reportConsistency.resolved_config_hash || '-'],
      ],
    ),
    '',
    '## 2. 核心指标',
    _reportTable(
      ['指标', '值'],
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
    '## 3. AI摘要',
    `- 主退出原因: ${topExit ? `${reasonZh(topExit.code)} (${topExit.code})` : '-'}`,
    `- 主退出次数: ${topExit ? _reportInt(topExit.count) : '-'}`,
    `- 主退出占比: ${topExit && totalExitCount > 0 ? _reportPct(topExit.count / totalExitCount) : '-'}`,
    `- 买单数: ${_reportInt(counters.buy_orders_count)}`,
    `- 卖单数: ${_reportInt(counters.sell_orders_count)}`,
    `- 缺独立计数阶段: ${missingStages.length ? missingStages.join(', ') : '无'}`,
    '',
    '## 4. 9阶段漏斗',
    _reportTable(
      ['stage', 'label', 'input_cnt', 'keep_cnt', 'filtered_cnt', 'available', 'note'],
      buyStageRows.map((row) => [
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
    '## 5. S9退出分析',
    _reportTable(
      ['reason_zh', 'reason_code', 'count', 'ratio'],
      exitRows.length
        ? exitRows.map((row) => [reasonZh(row.code), row.code, _reportInt(row.count), _reportPct(totalExitCount > 0 ? row.count / totalExitCount : 0)])
        : [['-', '-', '-', '-']],
    ),
    '',
    '## 6. 个股TOP10',
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
    '## 7. 配置摘要',
    _reportTable(
      ['字段', '值'],
      [
        ['strategy', signalCfg.strategy || '-'],
        ['breakout_window', signalCfg.breakout_window],
        ['confirm_mode', signalCfg.confirm || '-'],
        ['portfolio_mode', positionCfg.portfolio_mode || '-'],
        ['max_positions', positionCfg.max_positions],
        ['max_holding_count', positionCfg.max_holding_count],
        ['exit_mode', exitCfg.mode || '-'],
        ['atr_stop_loss_pct', exitCfg.stop_loss_pct],
        ['enable_low10_exit', exitCfg.enable_low10_exit],
        ['price_adj', originalWb.price_adjustment || meta.price_adj_mode || '-'],
      ],
    ),
    '',
    '## 8. 研究备注',
    '- 该 Markdown 面向 GPT/Agent 二次分析，优先保留结构化表格与原始计数。',
    '- 如果需要做稳健性判断，应继续结合年度分解、收益集中度、参数扰动结果，而不是只看 CAGR。',
    `- 生成时间: ${new Date().toLocaleString('zh-CN')}`,
    '',
  ];
  lines.splice(
    Math.max(0, lines.length - 5),
    0,
    '## 原始计数器总表',
    _reportTable(
      ['counter_key', 'value'],
      scalarCounters.length ? scalarCounters : [['-', '-']],
    ),
    '',
  );
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
    renderAgentMarkdownReport();
    addLog('Markdown 报告已复制');
  } catch (err) {
    addLog(`复制 Markdown 失败: ${err?.message || err}`);
  }
}

async function generateReport() {
  const art = state.active_artifacts;
  const result = state.active_result;
  if (!art || !result || !result.exp_id) {
    addLog('请先运行或加载实验');
    return;
  }
  const text = buildAgentMarkdownReport();
  renderAgentMarkdownReport();
  _downloadAgentMarkdown(text);
  addLog('Markdown 报告已导出');
}
