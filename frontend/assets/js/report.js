/* ── report.js ── HTML report generation ── */
/* Globals used: state, REASON_MAP, addLog (from backtest_v2.js) */

async function generateReport() {
  const art = state.active_artifacts;
  const result = state.active_result;
  if (!art || !result || !result.exp_id) {
    addLog('请先运行回测');
    return;
  }
  // Try backend report first
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
  const funnel = (art.funnelRows || [])[0] || {};

  if (!perf.total_return && perf.total_return !== 0 && !trades.length && !daily.length) {
    addLog('本地数据不足，无法生成报告。请检查回测产物是否完整。');
    return;
  }

  const e = (v) => String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const p = (v) => { const n = Number(v); return Number.isFinite(n) ? `${(n * 100).toFixed(2)}%` : '-'; };
  const n2 = (v) => { const n = Number(v); return Number.isFinite(n) ? n.toFixed(2) : '-'; };
  const iNum = (v) => { const n = Number(v); return Number.isFinite(n) ? Math.round(n).toLocaleString('en-US') : '-'; };
  const mNum = (v) => { const n = Number(v); return Number.isFinite(n) ? n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-'; };
  const rZh = (code) => REASON_MAP[code] || String(code ?? '');

  // §2 月度/年度收益
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
    for (let m = 1; m <= 12; m++) html += `<th>${m}月</th>`;
    html += '<th>年度</th></tr></thead><tbody>';
    years.forEach((y) => {
      html += `<tr><td><b>${e(y)}</b></td>`;
      let yearReturn = 1;
      for (let m = 1; m <= 12; m++) {
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

  // §3 最大回撤分析
  function buildDrawdownAnalysis() {
    if (!daily.length) return '<p>日级数据不可用</p>';
    let maxDd = 0, ddStart = '', ddBottom = '';
    let peak = 0, peakDate = '';
    daily.forEach((d) => {
      const nav = Number(d.nav || 0);
      if (nav > peak) { peak = nav; peakDate = String(d.date || ''); }
      if (peak > 0) {
        const dd = (nav - peak) / peak;
        if (dd < maxDd) { maxDd = dd; ddStart = peakDate; ddBottom = String(d.date || ''); }
      }
    });
    return `<table>
      <tr><td>最大回撤幅度</td><td><b>${p(maxDd)}</b></td></tr>
      <tr><td>回撤起始日</td><td>${e(ddStart)}</td></tr>
      <tr><td>回撤最低点日</td><td>${e(ddBottom)}</td></tr>
      <tr><td>夏普比率</td><td>${n2(perf.sharpe)}</td></tr>
      <tr><td>卡尔马比率</td><td>${n2(perf.calmar)}</td></tr>
    </table>`;
  }

  // §4 交易分析
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

    const fRaw = Number(funnel.raw_signal || counters.raw_signal || 0);
    const fBlocked = Number(funnel.blocked || counters.blocked || 0);
    const fOrders = Number(funnel.orders || counters.orders || 0);
    const fSkipped = Number(funnel.skipped || counters.skipped || 0);
    const fClosed = Number(funnel.closed_trades || counters.closed_trades || 0);
    if (fRaw || fOrders || fClosed) {
      html += `<h4>信号漏斗</h4><table>
        <tr><td>原始信号</td><td>${iNum(fRaw)}</td></tr>
        <tr><td>被拦截</td><td>${iNum(fBlocked)}</td></tr>
        <tr><td>下单</td><td>${iNum(fOrders)}</td></tr>
        <tr><td>跳过</td><td>${iNum(fSkipped)}</td></tr>
        <tr><td>已平仓</td><td>${iNum(fClosed)}</td></tr>
      </table>`;
    }
    return html;
  }

  // §4b 市况判断
  function buildRegimeSummary() {
    const trendDays = Number(counters.regime_trend_days || 0);
    const mrDays = Number(counters.regime_mr_days || 0);
    const totalDays = trendDays + mrDays;
    if (!totalDays) return '';

    const rfDiag = counters.regime_filter_diagnostics || {};
    const hasRf = Object.keys(rfDiag).length > 0;

    let html = `<h4>市况路由统计</h4><table>
      <tr><td>趋势天数</td><td>${iNum(trendDays)}</td><td>${p(totalDays ? trendDays / totalDays : 0)}</td></tr>
      <tr><td>震荡天数</td><td>${iNum(mrDays)}</td><td>${p(totalDays ? mrDays / totalDays : 0)}</td></tr>
      <tr><td>总交易天数</td><td>${iNum(totalDays)}</td><td></td></tr>
    </table>`;

    const mrBuys = Number(counters.mr_rsi_oversold_buy_count || 0);
    const mrOverboughtSells = Number(counters.mr_rsi_overbought_sell_count || 0);
    const mrStopLoss = Number(counters.mr_stop_loss_count || 0);
    const mrTimeExit = Number(counters.mr_time_exit_count || 0);
    if (mrBuys || mrOverboughtSells || mrStopLoss || mrTimeExit) {
      html += `<h4>MR 信号统计</h4><table>
        <tr><td>RSI 超卖买入</td><td>${iNum(mrBuys)}</td></tr>
        <tr><td>RSI 超买卖出</td><td>${iNum(mrOverboughtSells)}</td></tr>
        <tr><td>MR 止损</td><td>${iNum(mrStopLoss)}</td></tr>
        <tr><td>MR 时间退出</td><td>${iNum(mrTimeExit)}</td></tr>
      </table>`;
    }

    if (hasRf) {
      const gm = Number(rfDiag.gate_m_mean || 0);
      const secCov = Number(rfDiag.gate_sec_coverage || 0);
      const rsMean = Number(rfDiag.regime_signal_mean || 0);
      const abovePct = Number(rfDiag.regime_signal_above_threshold_pct || 0);
      const rfSec = Number(rfDiag.precompute_seconds || 0);
      html += `<h4>三层趋势过滤诊断</h4><table>
        <tr><td>Market Gate 均值</td><td>${n2(gm)}</td></tr>
        <tr><td>Sector 覆盖率</td><td>${p(secCov)}</td></tr>
        <tr><td>Regime Signal 均值</td><td>${n2(rsMean)}</td></tr>
        <tr><td>超阈值占比</td><td>${p(abovePct)}</td></tr>
        <tr><td>预计算耗时</td><td>${n2(rfSec)}s</td></tr>
      </table>`;
    }

    return html;
  }

  // §5 持仓分析
  function buildPositionAnalysis() {
    const maxPos = Number(counters.max_positions || 10);
    const avgPos = Number(counters.avg_positions || 0);
    const slotsLeft = counters.slots_left != null ? Number(counters.slots_left) : (maxPos - avgPos);
    const utilization = maxPos > 0 ? avgPos / maxPos : 0;
    return `<table>
      <tr><td>平均持仓数</td><td>${n2(avgPos)}</td></tr>
      <tr><td>最大持仓数</td><td>${iNum(maxPos)}</td></tr>
      <tr><td>空余仓位</td><td>${n2(slotsLeft)}</td></tr>
      <tr><td>仓位利用率</td><td>${p(utilization)}</td></tr>
    </table>
    <h4>约束触发统计</h4>
    <table>
      <tr><td>个股上限触发</td><td style="color:#999">未实现</td></tr>
      <tr><td>行业上限触发</td><td style="color:#999">未实现</td></tr>
      <tr><td>资金不足跳过</td><td>${iNum(counters.cash_skip_count || 0)}</td></tr>
      <tr><td>最小手数跳过</td><td>${iNum(counters.lot_skip_count || 0)}</td></tr>
    </table>`;
  }

  // §6 策略参数摘要
  function buildConfigSummary() {
    const bc = config.base_config || config || {};
    const wc = (config.overrides || {}).original_workbench_config || (config.overrides || {}).workbench_config || null;

    // 链式读取：wc[wcPath] → bc[bcPath] → "-"
    const _dig = (obj, path) => {
      if (!obj || !path) return undefined;
      return path.split('.').reduce((o, k) => (o != null ? o[k] : undefined), obj);
    };
    const wcVal = (wcPath, bcPath) => {
      const v = _dig(wc, wcPath);
      if (v != null && v !== '') return v;
      const fb = _dig(bc, bcPath);
      if (fb != null && fb !== '') return fb;
      return '-';
    };
    const yesNo = (v) => (v === true ? '是' : v === false ? '否' : '-');
    const enabledTxt = (v) => (v === true ? '启用' : v === false ? '禁用' : '-');
    const pctAdj = (label) => { const adj = {'hfq':'后复权','qfq':'前复权','none':'不复权'}; return adj[label] || label || '-'; };

    let html = '';

    // ── 子表 1：信号策略 ──
    const stratName = wcVal('signal_generation.strategy', 'strategy.name');
    const maKey = String(stratName).toUpperCase().includes('EMA') ? 'ema' : 'sma';
    const fastMa = wcVal(`signal_generation.${maKey}.fast_ma`, 'strategy.fast');
    const slowMa = wcVal(`signal_generation.${maKey}.slow_ma`, 'strategy.slow');
    const entryBuf = wcVal(`signal_generation.${maKey}.entry_buffer_pct`, null);
    const trendMa = wcVal(null, 'strategy.params.trend_ma');
    html += `<h3>信号策略</h3><table>
      <tr><td>策略名称</td><td>${e(stratName)}</td></tr>
      <tr><td>快线周期</td><td>${e(fastMa)}</td></tr>
      <tr><td>慢线周期</td><td>${e(slowMa)}</td></tr>
      <tr><td>入场缓冲</td><td>${entryBuf !== '-' ? n2(entryBuf) + '%' : '-'}</td></tr>
      <tr><td>趋势过滤 MA</td><td>${e(trendMa)}</td></tr>
    </table>`;

    // ── 子表 2：退出规则 ──
    const exitRules = wc ? (wc.exit_rules || {}) : {};
    const sigReverse = exitRules.signal_reverse;
    const atrStop = exitRules.atr_stop || {};
    const trailing = exitRules.trailing || {};
    const timeExit = exitRules.time_exit || {};
    const exitPri = wc ? (wc.exit_priority || []) : [];
    html += `<h3>退出规则</h3><table>
      <tr><td>反转退出</td><td>${enabledTxt(sigReverse)}</td></tr>
      <tr><td>ATR 止损</td><td>${atrStop.enabled === true ? '启用 (k=' + n2(atrStop.k) + ')' : atrStop.enabled === false ? '禁用' : '-'}</td></tr>
      <tr><td>追踪止损</td><td>${trailing.enabled === true ? '启用 (k=' + n2(trailing.k) + ')' : trailing.enabled === false ? '禁用' : '-'}</td></tr>
      <tr><td>时间退出</td><td>${timeExit.enabled === true ? '启用 (' + (timeExit.n_days || '-') + ' 天)' : timeExit.enabled === false ? '禁用' : '-'}</td></tr>
      <tr><td>退出优先级</td><td>${exitPri.length ? e(exitPri.join(' → ')) : '-'}</td></tr>
    </table>`;

    // ── 子表 3：仓位与风控 ──
    const posRisk = wc ? (wc.position_risk || {}) : {};
    const riskGate = wc ? (wc.risk_gate || {}) : {};
    const maxPos = wcVal('position_risk.max_positions', null);
    const singleCap = _dig(wc, 'position_risk.single_stock_cap');
    const indCap = _dig(wc, 'position_risk.industry_cap');
    const lot = wcVal('position_risk.lot', 'execution.lot_size');
    const cashPolicy = wcVal('position_risk.cash_shortage_policy', null);
    let riskGateTxt = '-';
    if (riskGate.enabled === true) {
      const dd = riskGate.drawdown_threshold;
      const ddPct = (dd != null && Number.isFinite(Number(dd))) ? Math.abs(Number(dd) * 100).toFixed(0) + '%' : '-';
      riskGateTxt = `启用 — 回撤阈值 ${ddPct}, 动作 ${e(riskGate.action || '-')}, 冷却 ${riskGate.cooldown_days ?? '-'} 天`;
    } else if (riskGate.enabled === false) {
      riskGateTxt = '禁用';
    }
    html += `<h3>仓位与风控</h3><table>
      <tr><td>最大持仓数</td><td>${e(maxPos)}</td></tr>
      <tr><td>单票仓位上限</td><td>${singleCap != null ? (Number(singleCap) * 100).toFixed(0) + '%' : '-'}</td></tr>
      <tr><td>行业仓位上限</td><td>${indCap != null ? (Number(indCap) * 100).toFixed(0) + '%' : '-'}</td></tr>
      <tr><td>手数</td><td>${e(lot)}</td></tr>
      <tr><td>现金不足策略</td><td>${e(cashPolicy)}</td></tr>
      <tr><td>风险门</td><td>${riskGateTxt}</td></tr>
    </table>`;

    // ── 子表 4：选股范围 ──
    const uniMode = wcVal(null, null);  // 先单独处理
    const uniModeVal = _dig(wc, 'universe_mode') || _dig(config.overrides, 'universe_mode') || '-';
    const uniSymbols = (_dig(wc, 'universe.symbols') || bc.universe?.symbols || []);
    const rmUniverse = (meta || {}).universe;
    const resolvedSymbolCount = (rmUniverse && rmUniverse.raw_count != null) ? rmUniverse.raw_count : uniSymbols.length;
    const filters = wc ? (_dig(wc, 'universe.filters') || {}) : {};
    const turnover20d = filters.min_avg_turnover_20d;
    const turnoverDisplay = (turnover20d != null && Number.isFinite(Number(turnover20d)))
      ? (Number(turnover20d) / 10000).toLocaleString('en-US', {maximumFractionDigits: 0}) + ' 万'
      : '-';
    const priceMin = filters.price_min ?? '-';
    const priceMax = filters.price_max ?? '-';
    const priceRange = (priceMin !== '-' || priceMax !== '-') ? `${priceMin} ~ ${priceMax}` : '-';
    const adjVal = _dig(wc, 'universe.price_adj') || _dig(config.overrides, 'price_adj') || '-';
    html += `<h3>选股范围</h3><table>
      <tr><td>选股模式</td><td>${e(uniModeVal)}</td></tr>
      <tr><td>标的数量</td><td>${iNum(resolvedSymbolCount)}</td></tr>
      <tr><td>排除 ST</td><td>${yesNo(filters.exclude_st)}</td></tr>
      <tr><td>排除停牌</td><td>${yesNo(filters.exclude_suspended)}</td></tr>
      <tr><td>最小上市天数</td><td>${filters.min_list_days != null ? iNum(filters.min_list_days) : '-'}</td></tr>
      <tr><td>日均成交额下限</td><td>${turnoverDisplay}</td></tr>
      <tr><td>价格区间</td><td>${e(priceRange)}</td></tr>
      <tr><td>ATR 波动区间</td><td>${e(filters.atr_pct_range || '-')}</td></tr>
      <tr><td>涨跌停规则</td><td>${e(filters.limit_rule || '-')}</td></tr>
      <tr><td>价格口径</td><td>${e(pctAdj(adjVal) + ' (' + adjVal + ')')}</td></tr>
    </table>`;

    // ── 子表 5：执行假设 ──
    const costs = bc.costs || {};
    const exec = bc.execution || {};
    const commRate = Number(costs.commission_rate);
    const stampRate = Number(costs.stamp_tax_rate);
    html += `<h3>执行假设</h3><table>
      <tr><td>佣金率</td><td>${Number.isFinite(commRate) ? (commRate * 10000).toFixed(0) + '‱' : '-'}</td></tr>
      <tr><td>最低佣金</td><td>${costs.commission_min != null ? n2(costs.commission_min) : '-'}</td></tr>
      <tr><td>印花税率</td><td>${Number.isFinite(stampRate) ? (stampRate * 1000).toFixed(0) + '‰' : '-'}</td></tr>
      <tr><td>滑点</td><td>${costs.slippage_bps != null ? n2(costs.slippage_bps) + ' bps' : '-'}</td></tr>
      <tr><td>手数</td><td>${exec.lot_size != null ? iNum(exec.lot_size) : '-'}</td></tr>
      <tr><td>T+1</td><td>${yesNo(exec.t_plus_one)}</td></tr>
      <tr><td>初始资金</td><td>${bc.initial_capital != null ? Number(bc.initial_capital).toLocaleString('en-US') : '-'}</td></tr>
    </table>`;

    // ── 可选：复合信号子表 ──
    const sigComp = wc ? (wc.signal_composition || {}) : {};
    if (sigComp.enabled === true && Array.isArray(sigComp.modules) && sigComp.modules.length > 0) {
      html += `<h3>复合信号 (${e(sigComp.compose_mode || '-')}) <span style="color:#999;font-size:13px">(未实现)</span></h3>`;
      html += '<table><thead><tr><th>模块名</th><th>角色</th><th>权重</th><th>优先级</th></tr></thead><tbody>';
      sigComp.modules.forEach((m) => {
        html += `<tr><td>${e(m.name || '-')}</td><td>${e(m.role || '-')}</td><td>${n2(m.weight)}</td><td>${e(m.priority ?? '-')}</td></tr>`;
      });
      html += '</tbody></table>';
    }

    return html;
  }

  // §7 交易明细附录
  function buildTradeAppendix() {
    if (!trades.length) return '<p>无交易记录</p>';
    const names = (art.stockNames || {});
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
  @media print { body { padding: 20px; } h2 { page-break-before: auto; } table { page-break-inside: auto; } }
</style>
</head>
<body>
<h1>量化回测分析报告</h1>
<div class="subtitle">实验 ${e(result.exp_id || '-')} | 生成于 ${e(now)}</div>

<h2>§1 概览</h2>
<table>
  <tr><td>回测区间</td><td>${e(meta.data?.start || '-')} ~ ${e(meta.data?.end || '-')}</td></tr>
  <tr><td>基准指数</td><td>${e(meta.data?.benchmark || '-')}</td></tr>
  <tr><td>对照指数</td><td>${e(meta.data?.compare_symbol || '-')}</td></tr>
  <tr><td>股票池数量</td><td>${iNum(meta.data?.universe_limit || '-')}</td></tr>
</table>
<div class="kpi-grid">
  ${[
    ['年化收益', p(perf.cagr)],
    ['最大回撤', p(perf.max_drawdown)],
    ['夏普比率', n2(perf.sharpe)],
    ['卡尔马比率', n2(perf.calmar)],
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

<h2>§3 风险分析</h2>
${buildDrawdownAnalysis()}

<h2>§4 交易分析</h2>
${buildTradeAnalysis()}
${buildRegimeSummary() ? `<h2>§4b 市况判断</h2>${buildRegimeSummary()}` : ''}

<h2>§5 持仓分析</h2>
${buildPositionAnalysis()}

<h2>§6 策略参数</h2>
${buildConfigSummary()}

<h2>§7 附录：全部交易明细</h2>
<p style="color:#666;font-size:12px;margin-bottom:8px">共 ${iNum(trades.length)} 条交易记录</p>
${buildTradeAppendix()}

</body>
</html>`;

  const win = window.open('', '_blank');
  if (win) {
    win.document.write(html);
    win.document.close();
  } else {
    addLog('浏览器阻止了弹出窗口，请允许弹出窗口后重试');
  }
}
