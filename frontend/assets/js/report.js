/* report.js - HTML report generation */
/* Globals used: state, REASON_MAP, addLog */

async function generateReport() {
  const art = state.active_artifacts;
  const result = state.active_result;
  if (!art || !result || !result.exp_id) {
    addLog('请先运行回测');
    return;
  }

  try {
    const reportUrl = `/api/backtest_v2/experiments/${encodeURIComponent(result.exp_id)}/report`;
    const resp = await fetch(reportUrl);
    if (resp.ok) {
      window.open(reportUrl, '_blank');
      return;
    }
  } catch (err) {
    addLog(`后端报告请求失败: ${err?.message || err}`);
  }

  addLog('后端报告不可用，使用本地生成');

  const perf = art.perf || {};
  const meta = art.run_meta || {};
  const counters = meta.counters || {};
  const trades = art.tradesRows || [];
  const daily = art.dailyRows || [];
  const config = art.config || {};
  const funnelRows = art.funnelRows || [];
  const funnel = funnelRows[0] || null;

  const e = (v) => String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const p = (v) => { const n = Number(v); return Number.isFinite(n) ? `${(n * 100).toFixed(2)}%` : '-'; };
  const n2 = (v) => { const n = Number(v); return Number.isFinite(n) ? n.toFixed(2) : '-'; };
  const iNum = (v) => { const n = Number(v); return Number.isFinite(n) ? Math.round(n).toLocaleString('en-US') : '-'; };
  const mNum = (v) => { const n = Number(v); return Number.isFinite(n) ? n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-'; };
  const rZh = (code) => REASON_MAP[code] || String(code ?? '');

  const cfg = config || {};
  const overrides = cfg.overrides || {};
  const runtimeCfg = overrides.workbench_config || {};
  const originalWb = overrides.original_workbench_config || {};
  const runUni = runtimeCfg.universe || {};
  const wbUni = originalWb.universe || {};
  const metaData = meta.data || {};
  const metaUni = meta.universe || {};
  const reportConsistency = meta.report_consistency || {};
  const resolvedConfigMeta = reportConsistency.resolved_config_meta || {};
  const resolvedConfigMode = reportConsistency.resolved_config_mode || '-';
  const resolvedConfigId = reportConsistency.resolved_config_id || '-';
  const resolvedConfigHash = reportConsistency.resolved_config_hash || '-';
  const resolvedUniverseMode = resolvedConfigMeta.universe_mode || metaData.universe_mode || metaUni.universe_mode || '-';

  const pickFirst = (arr) => {
    const primary = arr[0]?.[1] || 'missing';
    for (const [val, src] of arr) {
      if (val == null) continue;
      if (typeof val === 'string' && !val.trim()) continue;
      return { value: val, source: src, fallback: src !== primary };
    }
    return { value: null, source: 'missing', fallback: true };
  };

  const startInfo = pickFirst([
    [runUni.start, 'runtime.workbench_config.universe.start'],
    [wbUni.start, 'original_workbench_config.universe.start'],
    [metaData.start, 'run_meta.data.start'],
  ]);
  const endInfo = pickFirst([
    [runUni.end, 'runtime.workbench_config.universe.end'],
    [wbUni.end, 'original_workbench_config.universe.end'],
    [metaData.end, 'run_meta.data.end'],
  ]);
  const benchmarkInfo = pickFirst([
    [runUni.benchmark, 'runtime.workbench_config.universe.benchmark'],
    [wbUni.benchmark, 'original_workbench_config.universe.benchmark'],
    [metaData.benchmark, 'run_meta.data.benchmark'],
  ]);
  const symbolCountInfo = pickFirst([
    [metaUni.raw_count, 'run_meta.universe.raw_count'],
    [metaUni.after_filters_symbols, 'run_meta.universe.after_filters_symbols'],
    [Array.isArray(wbUni.symbols) ? wbUni.symbols.length : null, 'original_workbench_config.universe.symbols'],
  ]);

  const funnelSource = funnel ? 'funnelRows' : 'run_meta.counters';

  function buildMonthlyReturns() {
    if (!daily.length) return '<p>日级数据不可用</p>';
    const byYM = {};
    daily.forEach((d) => {
      const dt = String(d.date || '');
      if (dt.length < 7) return;
      const y = dt.slice(0, 4);
      const m = parseInt(dt.slice(5, 7), 10);
      if (!byYM[y]) byYM[y] = {};
      if (!byYM[y][m]) byYM[y][m] = [];
      byYM[y][m].push(Number(d.daily_return || 0));
    });
    const years = Object.keys(byYM).sort();
    let html = '<table><thead><tr><th>年份</th>';
    for (let m = 1; m <= 12; m += 1) html += `<th>${m}月</th>`;
    html += '<th>年度</th></tr></thead><tbody>';
    years.forEach((y) => {
      html += `<tr><td><b>${e(y)}</b></td>`;
      let yearReturn = 1;
      for (let m = 1; m <= 12; m += 1) {
        const rets = byYM[y][m] || [];
        const monthReturn = rets.reduce((acc, r) => acc * (1 + r), 1) - 1;
        yearReturn *= (1 + monthReturn);
        const color = monthReturn > 0 ? '#2e7d32' : monthReturn < 0 ? '#c62828' : '#888';
        html += `<td style="color:${color}">${rets.length ? p(monthReturn) : '-'}</td>`;
      }
      yearReturn -= 1;
      const yColor = yearReturn > 0 ? '#2e7d32' : yearReturn < 0 ? '#c62828' : '#888';
      html += `<td style="color:${yColor};font-weight:600">${p(yearReturn)}</td></tr>`;
    });
    html += '</tbody></table>';
    return html;
  }

  function buildTradeAnalysis() {
    const buys = trades.filter((t) => String(t.side || '').toUpperCase() === 'BUY');
    const sells = trades.filter((t) => String(t.side || '').toUpperCase() === 'SELL');
    const reasonCounts = {};
    sells.forEach((t) => {
      const rc = String(t.reason_code || '未知');
      reasonCounts[rc] = (reasonCounts[rc] || 0) + 1;
    });
    const sortedReasons = Object.entries(reasonCounts).sort((a, b) => b[1] - a[1]);

    let html = `<table>
      <tr><td>总交易次数</td><td><b>${iNum(trades.length)}</b></td></tr>
      <tr><td>买入次数</td><td>${iNum(buys.length)}</td></tr>
      <tr><td>卖出次数</td><td>${iNum(sells.length)}</td></tr>
    </table>`;

    if (sortedReasons.length) {
      html += '<h4>平仓原因分布</h4><table><thead><tr><th>原因</th><th>次数</th><th>占比</th></tr></thead><tbody>';
      sortedReasons.forEach(([code, cnt]) => {
        html += `<tr><td>${e(rZh(code))}</td><td>${iNum(cnt)}</td><td>${p(sells.length ? cnt / sells.length : 0)}</td></tr>`;
      });
      html += '</tbody></table>';
    }

    const src = funnel || {};
    const fRaw = Number(src.raw_signal ?? counters.raw_signal ?? 0);
    const fBlocked = Number(src.blocked ?? counters.blocked ?? 0);
    const fOrders = Number(src.orders ?? counters.orders ?? 0);
    const fSkipped = Number(src.skipped ?? counters.skipped ?? 0);
    const fClosed = Number(src.closed_trades ?? counters.closed_trades ?? 0);

    if (fRaw || fOrders || fClosed) {
      html += `<h4>信号漏斗</h4><p style="color:#666;font-size:12px">数据源: ${e(funnelSource)}</p><table>
        <tr><td>原始信号</td><td>${iNum(fRaw)}</td></tr>
        <tr><td>被拦截</td><td>${iNum(fBlocked)}</td></tr>
        <tr><td>下单</td><td>${iNum(fOrders)}</td></tr>
        <tr><td>跳过</td><td>${iNum(fSkipped)}</td></tr>
        <tr><td>已平仓</td><td>${iNum(fClosed)}</td></tr>
      </table>`;
    }
    return html;
  }

  function buildTradeAppendix() {
    if (!trades.length) return '<p>无交易记录</p>';
    const names = art.stockNames || {};
    let html = '<table><thead><tr><th>日期</th><th>标的</th><th>方向</th><th style="text-align:right">成交价</th><th style="text-align:right">数量</th><th style="text-align:right">金额</th><th style="text-align:right">佣金</th><th style="text-align:right">印花税</th><th style="text-align:right">净额</th><th>原因</th></tr></thead><tbody>';
    trades.forEach((t) => {
      const isBuy = String(t.side || '').toUpperCase() === 'BUY';
      const side = isBuy ? '<span style="color:#2e7d32;font-weight:600">买入</span>' : '<span style="color:#c62828;font-weight:600">卖出</span>';
      const sym = String(t.symbol || '');
      const displayName = names[sym] || sym;
      const symbolCell = displayName !== sym ? `<span title="${e(sym)}">${e(displayName)}</span>` : e(sym);
      const fp = t.fill_price != null ? Number(t.fill_price).toFixed(3) : Number(t.price || 0).toFixed(3);
      const comm = t.commission != null ? mNum(t.commission) : '-';
      const stax = t.stamp_tax != null ? mNum(t.stamp_tax) : '-';
      const netAmt = t.net_amount != null ? mNum(t.net_amount) : mNum(t.value);
      html += `<tr><td>${e(t.date || '')}</td><td>${symbolCell}</td><td>${side}</td><td style="text-align:right">${fp}</td><td style="text-align:right">${iNum(t.qty)}</td><td style="text-align:right">${mNum(t.value)}</td><td style="text-align:right">${comm}</td><td style="text-align:right">${stax}</td><td style="text-align:right">${netAmt}</td><td>${e(rZh(t.reason_code))}</td></tr>`;
    });
    html += '</tbody></table>';
    return html;
  }

  const now = new Date().toLocaleString('zh-CN');
  const sourceDiag = [
    ['区间开始', `${startInfo.source}${startInfo.fallback ? ' (fallback)' : ''}`],
    ['区间结束', `${endInfo.source}${endInfo.fallback ? ' (fallback)' : ''}`],
    ['基准', `${benchmarkInfo.source}${benchmarkInfo.fallback ? ' (fallback)' : ''}`],
    ['标的数量', `${symbolCountInfo.source}${symbolCountInfo.fallback ? ' (fallback)' : ''}`],
    ['漏斗', funnelSource],
    ['配置冲突策略', reportConsistency.config_conflict_policy || '-'],
    ['解析配置模式', resolvedConfigMode],
    ['解析配置ID', resolvedConfigId],
    ['解析配置Hash', resolvedConfigHash],
    ['解析配置股票池', resolvedUniverseMode],
  ];

  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>回测报告 - ${e(result.exp_id || '')}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, 'Microsoft YaHei', sans-serif; color: #1a1a1a; padding: 40px 60px; max-width: 1000px; margin: 0 auto; line-height: 1.6; }
  h1 { font-size: 24px; border-bottom: 2px solid #1a1a1a; padding-bottom: 8px; margin-bottom: 6px; }
  .subtitle { color: #666; font-size: 13px; margin-bottom: 30px; }
  h2 { font-size: 18px; color: #1a1a1a; margin: 30px 0 12px; padding-bottom: 4px; border-bottom: 1px solid #ddd; }
  h3 { font-size: 15px; margin: 20px 0 8px; }
  h4 { font-size: 14px; margin: 16px 0 6px; color: #444; }
  table { width: 100%; border-collapse: collapse; margin: 8px 0 16px; font-size: 13px; }
  th { background: #f5f5f5; font-weight: 600; text-align: left; padding: 6px 10px; border: 1px solid #ddd; white-space: nowrap; }
  td { padding: 5px 10px; border: 1px solid #eee; }
  .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0; }
  .kpi-card { border: 1px solid #e0e0e0; border-radius: 6px; padding: 12px; text-align: center; }
  .kpi-label { font-size: 12px; color: #888; margin-bottom: 4px; }
  .kpi-value { font-size: 20px; font-weight: 700; font-family: ui-monospace, monospace; }
  .kpi-value.positive { color: #2e7d32; }
  .kpi-value.negative { color: #c62828; }
</style>
</head>
<body>
<h1>量化回测分析报告</h1>
<div class="subtitle">实验 ${e(result.exp_id || '-')} | 生成于 ${e(now)}</div>

<h2>§1 概览</h2>
<table>
  <tr><td>回测区间</td><td>${e(startInfo.value || '-')} ~ ${e(endInfo.value || '-')}</td></tr>
  <tr><td>基准指数</td><td>${e(benchmarkInfo.value || '-')}</td></tr>
  <tr><td>对照指数</td><td>${e(metaData.compare_symbol || '-')}</td></tr>
  <tr><td>股票池模式</td><td>${e(resolvedUniverseMode)}</td></tr>
  <tr><td>股票池数量</td><td>${iNum(symbolCountInfo.value || 0)}</td></tr>
  <tr><td>解析配置</td><td>${e(`${resolvedConfigMode} | ${resolvedConfigId}`)}</td></tr>
</table>
<div class="kpi-grid">
  ${[
    ['年化收益', p(perf.cagr)],
    ['最大回撤', p(perf.max_drawdown)],
    ['夏普比率', n2(perf.sharpe)],
    ['卡尔玛比率', n2(perf.calmar)],
    ['交易次数', iNum(perf.trades)],
    ['换手率', p(perf.turnover)],
    ['累计收益', p(perf.total_return)],
    ['评级', e(String(result.tier || '-'))],
  ].map(([label, val]) => {
    const cls = String(val).startsWith('-') ? 'negative' : (String(val).match(/^[0-9]/) ? 'positive' : '');
    return `<div class="kpi-card"><div class="kpi-label">${label}</div><div class="kpi-value ${cls}">${val}</div></div>`;
  }).join('')}
</div>

<h2>§2 收益分析</h2>
<h3>月度收益率</h3>
${buildMonthlyReturns()}

<h2>§3 交易分析</h2>
${buildTradeAnalysis()}

<h2>§4 策略参数（简版）</h2>
<table>
  <tr><td>策略</td><td>${e((originalWb.signal_generation || {}).strategy || '-')}</td></tr>
  <tr><td>组合模式</td><td>${e((originalWb.position_risk || {}).portfolio_mode || '-')}</td></tr>
</table>

<h2>§5 附录：全部交易明细</h2>
<p style="color:#666;font-size:12px;margin-bottom:8px">共 ${iNum(trades.length)} 条交易记录</p>
${buildTradeAppendix()}

<h2>§6 口径诊断</h2>
<table><thead><tr><th>字段</th><th>来源</th></tr></thead><tbody>
${sourceDiag.map(([k, v]) => `<tr><td>${e(k)}</td><td>${e(v)}</td></tr>`).join('')}
</tbody></table>

</body>
</html>`;

  const win = window.open('', '_blank');
  if (win) {
    win.document.write(html);
    win.document.close();
  } else {
    addLog('浏览器阻止了弹窗，请允许弹窗后重试');
  }
}
