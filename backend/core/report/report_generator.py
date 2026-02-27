"""Generate a self-contained HTML backtest report from experiment artifacts.

Equivalent to the frontend generateReport() in backtest_v2.js, but runs
server-side so the report can be persisted and served via API.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from html import escape as _html_escape
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

REASON_MAP = {
    "SMA_CROSS_UP": "均线金叉",
    "SMA_CROSS_DOWN": "均线死叉",
    "SIGNAL_REVERSE": "信号反转",
    "ATR_STOP_LOSS": "ATR止损",
    "ATR_TRAIL_STOP": "ATR追踪止损",
    "TIME_EXIT": "到期平仓",
    "TREND_REVERSE": "趋势反转",
    "TREND_BREAK_EXIT": "趋势破位平仓",
    "RISK_OFF_EXIT": "风控平仓",
    "MANUAL_CLOSE": "手动平仓",
    "MAX_HOLD_DAYS": "持仓到期",
    "TAKE_PROFIT": "止盈",
    "STOP_LOSS": "止损",
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _e(v: Any) -> str:
    return _html_escape(str(v if v is not None else ""))


def _safe_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        n = float(v)
    except (ValueError, TypeError):
        return None
    if math.isnan(n) or math.isinf(n):
        return None
    return n


def _pct(v: Any) -> str:
    n = _safe_float(v)
    return f"{n * 100:.2f}%" if n is not None else "-"


def _n2(v: Any) -> str:
    n = _safe_float(v)
    return f"{n:.2f}" if n is not None else "-"


def _inum(v: Any) -> str:
    n = _safe_float(v)
    return f"{int(round(n)):,}" if n is not None else "-"


def _mnum(v: Any) -> str:
    n = _safe_float(v)
    return f"{n:,.2f}" if n is not None else "-"


def _rzh(code: Any) -> str:
    return REASON_MAP.get(str(code or ""), str(code or ""))


def _dig(obj: dict | None, path: str | None) -> Any:
    if not obj or not path:
        return None
    cur: Any = obj
    for key in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def _wc_val(wc: dict | None, bc: dict | None, wc_path: str | None, bc_path: str | None) -> Any:
    v = _dig(wc, wc_path)
    if v is not None and v != "":
        return v
    fb = _dig(bc, bc_path)
    if fb is not None and fb != "":
        return fb
    return "-"


def _yes_no(v: Any) -> str:
    if v is True:
        return "是"
    if v is False:
        return "否"
    return "-"


def _enabled_txt(v: Any) -> str:
    if v is True:
        return "启用"
    if v is False:
        return "禁用"
    return "-"


def _price_adj_label(label: Any) -> str:
    mapping = {"hfq": "后复权", "qfq": "前复权", "none": "不复权"}
    s = str(label or "")
    return mapping.get(s, s) or "-"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_monthly_returns(daily: list[dict]) -> str:
    if not daily:
        return "<p>日级数据不可用</p>"

    by_ym: dict[str, dict[int, list[float]]] = {}
    for d in daily:
        dt = str(d.get("date") or "")
        if len(dt) < 7:
            continue
        y = dt[:4]
        m = int(dt[5:7])
        by_ym.setdefault(y, {}).setdefault(m, []).append(float(d.get("daily_return") or 0))

    years = sorted(by_ym.keys())
    html = "<table><thead><tr><th>年份</th>"
    for m in range(1, 13):
        html += f"<th>{m}月</th>"
    html += "<th>年度</th></tr></thead><tbody>"

    for y in years:
        html += f"<tr><td><b>{_e(y)}</b></td>"
        year_ret = 1.0
        for m in range(1, 13):
            rets = by_ym[y].get(m, [])
            if rets:
                month_ret = 1.0
                for r in rets:
                    month_ret *= (1 + r)
                month_ret -= 1
                year_ret *= (1 + month_ret)
                color = "#2e7d32" if month_ret > 0 else ("#c62828" if month_ret < 0 else "#888")
                html += f'<td style="color:{color}">{_pct(month_ret)}</td>'
            else:
                html += "<td>-</td>"
        year_ret -= 1
        y_color = "#2e7d32" if year_ret > 0 else ("#c62828" if year_ret < 0 else "#888")
        html += f'<td style="color:{y_color};font-weight:600">{_pct(year_ret)}</td></tr>'
    html += "</tbody></table>"
    return html


def _build_drawdown_analysis(daily: list[dict], perf: dict) -> str:
    if not daily:
        return "<p>日级数据不可用</p>"
    max_dd = 0.0
    dd_start = ""
    dd_bottom = ""
    peak = 0.0
    peak_date = ""
    for d in daily:
        nav = float(d.get("nav") or 0)
        if nav > peak:
            peak = nav
            peak_date = str(d.get("date") or "")
        if peak > 0:
            dd = (nav - peak) / peak
            if dd < max_dd:
                max_dd = dd
                dd_start = peak_date
                dd_bottom = str(d.get("date") or "")

    return f"""<table>
      <tr><td>最大回撤幅度</td><td><b>{_pct(max_dd)}</b></td></tr>
      <tr><td>回撤起始日</td><td>{_e(dd_start)}</td></tr>
      <tr><td>回撤最低点日</td><td>{_e(dd_bottom)}</td></tr>
      <tr><td>夏普比率</td><td>{_n2(perf.get('sharpe'))}</td></tr>
      <tr><td>卡尔马比率</td><td>{_n2(perf.get('calmar'))}</td></tr>
    </table>"""


def _build_trade_analysis(trades: list[dict], funnel: dict, counters: dict) -> str:
    buys = [t for t in trades if str(t.get("side") or "").upper() == "BUY"]
    sells = [t for t in trades if str(t.get("side") or "").upper() == "SELL"]

    reason_counts: dict[str, int] = {}
    for t in sells:
        rc = str(t.get("reason_code") or "未知")
        reason_counts[rc] = reason_counts.get(rc, 0) + 1
    sorted_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)

    html = f"""<table>
      <tr><td>总交易次数</td><td><b>{_inum(len(trades))}</b></td></tr>
      <tr><td>买入次数</td><td>{_inum(len(buys))}</td></tr>
      <tr><td>卖出次数</td><td>{_inum(len(sells))}</td></tr>
    </table>"""

    if sorted_reasons:
        html += '<h4>平仓原因分布</h4><table><thead><tr><th>原因</th><th>次数</th><th>占比</th></tr></thead><tbody>'
        for code, cnt in sorted_reasons:
            ratio = cnt / len(sells) if sells else 0
            html += f"<tr><td>{_e(_rzh(code))}</td><td>{_inum(cnt)}</td><td>{_pct(ratio)}</td></tr>"
        html += "</tbody></table>"

    f_raw = int(funnel.get("raw_signal") or counters.get("raw_signal") or 0)
    f_blocked = int(funnel.get("blocked") or counters.get("blocked") or 0)
    f_orders = int(funnel.get("orders") or counters.get("orders") or 0)
    f_skipped = int(funnel.get("skipped") or counters.get("skipped") or 0)
    f_closed = int(funnel.get("closed_trades") or counters.get("closed_trades") or 0)
    if f_raw or f_orders or f_closed:
        html += f"""<h4>信号漏斗</h4><table>
        <tr><td>原始信号</td><td>{_inum(f_raw)}</td></tr>
        <tr><td>被拦截</td><td>{_inum(f_blocked)}</td></tr>
        <tr><td>下单</td><td>{_inum(f_orders)}</td></tr>
        <tr><td>跳过</td><td>{_inum(f_skipped)}</td></tr>
        <tr><td>已平仓</td><td>{_inum(f_closed)}</td></tr>
      </table>"""
    return html


def _build_position_analysis(counters: dict) -> str:
    max_pos = float(counters.get("max_positions") or 10)
    avg_pos = float(counters.get("avg_positions") or 0)
    slots_left = counters.get("slots_left")
    if slots_left is None:
        slots_left = max_pos - avg_pos
    utilization = avg_pos / max_pos if max_pos > 0 else 0

    return f"""<table>
      <tr><td>平均持仓数</td><td>{_n2(avg_pos)}</td></tr>
      <tr><td>最大持仓数</td><td>{_inum(max_pos)}</td></tr>
      <tr><td>空余仓位</td><td>{_n2(slots_left)}</td></tr>
      <tr><td>仓位利用率</td><td>{_pct(utilization)}</td></tr>
    </table>
    <h4>约束触发统计</h4>
    <table>
      <tr><td>个股上限触发</td><td>{_inum(counters.get('cap_hit_single', 0))}</td></tr>
      <tr><td>行业上限触发</td><td>{_inum(counters.get('cap_hit_industry', 0))}</td></tr>
      <tr><td>资金不足跳过</td><td>{_inum(counters.get('cash_skip_count', 0))}</td></tr>
      <tr><td>最小手数跳过</td><td>{_inum(counters.get('lot_skip_count', 0))}</td></tr>
    </table>"""


def _build_config_summary(config: dict) -> str:
    bc = config.get("base_config") or config or {}
    wc = (config.get("overrides") or {}).get("workbench_config")

    def wv(wc_path, bc_path):
        return _wc_val(wc, bc, wc_path, bc_path)

    html = ""

    # Sub-table 1: Signal strategy
    strat_name = wv("signal_generation.strategy", "strategy.name")
    fast_ma = wv("signal_generation.sma.fast_ma", "strategy.fast")
    slow_ma = wv("signal_generation.sma.slow_ma", "strategy.slow")
    entry_buf = wv("signal_generation.sma.entry_buffer_pct", None)
    atr_n = wv(None, "strategy.params.atr_n")
    atr_k = wv("exit_rules.atr_stop.k", "strategy.params.atr_k")
    trend_ma = wv(None, "strategy.params.trend_ma")
    entry_buf_str = f"{_n2(entry_buf)}%" if entry_buf != "-" else "-"
    atr_k_str = _n2(atr_k) if atr_k != "-" else "-"
    html += f"""<h3>信号策略</h3><table>
      <tr><td>策略名称</td><td>{_e(strat_name)}</td></tr>
      <tr><td>快线周期</td><td>{_e(fast_ma)}</td></tr>
      <tr><td>慢线周期</td><td>{_e(slow_ma)}</td></tr>
      <tr><td>入场缓冲</td><td>{entry_buf_str}</td></tr>
      <tr><td>ATR 窗口</td><td>{_e(atr_n)}</td></tr>
      <tr><td>ATR 倍数</td><td>{atr_k_str}</td></tr>
      <tr><td>趋势过滤 MA</td><td>{_e(trend_ma)}</td></tr>
    </table>"""

    # Sub-table 2: Exit rules
    exit_rules = (wc or {}).get("exit_rules") or {}
    sig_reverse = exit_rules.get("signal_reverse")
    atr_stop = exit_rules.get("atr_stop") or {}
    trailing = exit_rules.get("trailing") or {}
    time_exit = exit_rules.get("time_exit") or {}
    exit_pri = (wc or {}).get("exit_priority") or []

    atr_stop_txt = "-"
    if atr_stop.get("enabled") is True:
        atr_stop_txt = f"启用 (k={_n2(atr_stop.get('k'))})"
    elif atr_stop.get("enabled") is False:
        atr_stop_txt = "禁用"

    trailing_txt = "-"
    if trailing.get("enabled") is True:
        trailing_txt = f"启用 (k={_n2(trailing.get('k'))})"
    elif trailing.get("enabled") is False:
        trailing_txt = "禁用"

    time_exit_txt = "-"
    if time_exit.get("enabled") is True:
        time_exit_txt = f"启用 ({time_exit.get('n_days', '-')} 天)"
    elif time_exit.get("enabled") is False:
        time_exit_txt = "禁用"

    exit_pri_str = _e(" → ".join(exit_pri)) if exit_pri else "-"
    html += f"""<h3>退出规则</h3><table>
      <tr><td>反转退出</td><td>{_enabled_txt(sig_reverse)}</td></tr>
      <tr><td>ATR 止损</td><td>{atr_stop_txt}</td></tr>
      <tr><td>追踪止损</td><td>{trailing_txt}</td></tr>
      <tr><td>时间退出</td><td>{time_exit_txt}</td></tr>
      <tr><td>退出优先级</td><td>{exit_pri_str}</td></tr>
    </table>"""

    # Sub-table 3: Position & risk
    risk_gate = (wc or {}).get("risk_gate") or {}
    max_pos_v = wv("position_risk.max_positions", None)
    single_cap = _dig(wc, "position_risk.single_stock_cap")
    ind_cap = _dig(wc, "position_risk.industry_cap")
    lot_v = wv("position_risk.lot", "execution.lot_size")
    cash_policy = wv("position_risk.cash_shortage_policy", None)

    risk_gate_txt = "-"
    if risk_gate.get("enabled") is True:
        dd = risk_gate.get("drawdown_threshold")
        dd_n = _safe_float(dd)
        dd_pct = f"{abs(dd_n * 100):.0f}%" if dd_n is not None else "-"
        action = _e(risk_gate.get("action") or "-")
        cooldown = risk_gate.get("cooldown_days", "-")
        risk_gate_txt = f"启用 — 回撤阈值 {dd_pct}, 动作 {action}, 冷却 {cooldown} 天"
    elif risk_gate.get("enabled") is False:
        risk_gate_txt = "禁用"

    single_cap_str = f"{float(single_cap) * 100:.0f}%" if single_cap is not None else "-"
    ind_cap_str = f"{float(ind_cap) * 100:.0f}%" if ind_cap is not None else "-"
    html += f"""<h3>仓位与风控</h3><table>
      <tr><td>最大持仓数</td><td>{_e(max_pos_v)}</td></tr>
      <tr><td>单票仓位上限</td><td>{single_cap_str}</td></tr>
      <tr><td>行业仓位上限</td><td>{ind_cap_str}</td></tr>
      <tr><td>手数</td><td>{_e(lot_v)}</td></tr>
      <tr><td>现金不足策略</td><td>{_e(cash_policy)}</td></tr>
      <tr><td>风险门</td><td>{risk_gate_txt}</td></tr>
    </table>"""

    # Sub-table 4: Universe & filters
    overrides = config.get("overrides") or {}
    uni_mode_val = _dig(wc, "universe_mode") or overrides.get("universe_mode") or "-"
    uni_symbols = _dig(wc, "universe.symbols") or (bc.get("universe") or {}).get("symbols") or []
    filters = (_dig(wc, "universe.filters") or {}) if wc else {}

    turnover_20d = filters.get("min_avg_turnover_20d")
    if turnover_20d is not None:
        tn = _safe_float(turnover_20d)
        turnover_display = f"{int(tn / 10000):,} 万" if tn is not None else "-"
    else:
        turnover_display = "-"

    price_min = filters.get("price_min", "-")
    price_max = filters.get("price_max", "-")
    price_range = f"{price_min} ~ {price_max}" if (price_min != "-" or price_max != "-") else "-"
    adj_val = _dig(wc, "universe.price_adj") or overrides.get("price_adj") or "-"
    adj_display = f"{_price_adj_label(adj_val)} ({adj_val})"

    html += f"""<h3>选股范围</h3><table>
      <tr><td>选股模式</td><td>{_e(uni_mode_val)}</td></tr>
      <tr><td>标的数量</td><td>{_inum(len(uni_symbols))}</td></tr>
      <tr><td>排除 ST</td><td>{_yes_no(filters.get('exclude_st'))}</td></tr>
      <tr><td>排除停牌</td><td>{_yes_no(filters.get('exclude_suspended'))}</td></tr>
      <tr><td>最小上市天数</td><td>{_inum(filters.get('min_list_days')) if filters.get('min_list_days') is not None else '-'}</td></tr>
      <tr><td>日均成交额下限</td><td>{turnover_display}</td></tr>
      <tr><td>价格区间</td><td>{_e(price_range)}</td></tr>
      <tr><td>ATR 波动区间</td><td>{_e(filters.get('atr_pct_range') or '-')}</td></tr>
      <tr><td>涨跌停规则</td><td>{_e(filters.get('limit_rule') or '-')}</td></tr>
      <tr><td>价格口径</td><td>{_e(adj_display)}</td></tr>
    </table>"""

    # Sub-table 5: Execution assumptions
    costs = bc.get("costs") or {}
    execution = bc.get("execution") or {}
    comm_rate = _safe_float(costs.get("commission_rate"))
    stamp_rate = _safe_float(costs.get("stamp_tax_rate"))
    comm_rate_str = f"{comm_rate * 10000:.0f}‱" if comm_rate is not None else "-"
    stamp_rate_str = f"{stamp_rate * 1000:.0f}‰" if stamp_rate is not None else "-"
    comm_min = costs.get("commission_min")
    slip_bps = costs.get("slippage_bps")
    lot_size = execution.get("lot_size")
    t_plus_one = execution.get("t_plus_one")
    init_cap = bc.get("initial_capital")

    html += f"""<h3>执行假设</h3><table>
      <tr><td>佣金率</td><td>{comm_rate_str}</td></tr>
      <tr><td>最低佣金</td><td>{_n2(comm_min) if comm_min is not None else '-'}</td></tr>
      <tr><td>印花税率</td><td>{stamp_rate_str}</td></tr>
      <tr><td>滑点</td><td>{_n2(slip_bps) + ' bps' if slip_bps is not None else '-'}</td></tr>
      <tr><td>手数</td><td>{_inum(lot_size) if lot_size is not None else '-'}</td></tr>
      <tr><td>T+1</td><td>{_yes_no(t_plus_one)}</td></tr>
      <tr><td>初始资金</td><td>{f'{int(init_cap):,}' if init_cap is not None else '-'}</td></tr>
    </table>"""

    # Optional: Composite signal
    sig_comp = (wc or {}).get("signal_composition") or {}
    modules = sig_comp.get("modules") or []
    if sig_comp.get("enabled") is True and modules:
        compose_mode = _e(sig_comp.get("compose_mode") or "-")
        html += f'<h3>复合信号 ({compose_mode})</h3>'
        html += "<table><thead><tr><th>模块名</th><th>角色</th><th>权重</th><th>优先级</th></tr></thead><tbody>"
        for m in modules:
            html += f"<tr><td>{_e(m.get('name', '-'))}</td><td>{_e(m.get('role', '-'))}</td><td>{_n2(m.get('weight'))}</td><td>{_e(m.get('priority', '-'))}</td></tr>"
        html += "</tbody></table>"

    return html


def _build_trade_appendix(trades: list[dict], stock_names: dict[str, str]) -> str:
    if not trades:
        return "<p>无交易记录</p>"

    html = '<table><thead><tr><th>日期</th><th>标的</th><th>方向</th><th style="text-align:right">成交价</th><th style="text-align:right">数量</th><th style="text-align:right">金额</th><th style="text-align:right">佣金</th><th style="text-align:right">印花税</th><th style="text-align:right">净额</th><th>原因</th></tr></thead><tbody>'
    for t in trades:
        is_buy = str(t.get("side") or "").upper() == "BUY"
        if is_buy:
            side = '<span style="color:#2e7d32;font-weight:600">买入</span>'
        else:
            side = '<span style="color:#c62828;font-weight:600">卖出</span>'

        sym = str(t.get("symbol") or "")
        display_name = stock_names.get(sym, sym)
        if display_name != sym:
            symbol_cell = f'<span title="{_e(sym)}">{_e(display_name)}</span>'
        else:
            symbol_cell = _e(sym)

        fp_raw = t.get("fill_price")
        fp = f"{float(fp_raw):.3f}" if fp_raw is not None else f"{float(t.get('price') or 0):.3f}"
        comm = _mnum(t.get("commission")) if t.get("commission") is not None else "-"
        stax = _mnum(t.get("stamp_tax")) if t.get("stamp_tax") is not None else "-"
        net_amt = _mnum(t.get("net_amount")) if t.get("net_amount") is not None else _mnum(t.get("value"))

        html += f'<tr><td>{_e(t.get("date", ""))}</td><td>{symbol_cell}</td><td>{side}</td><td style="text-align:right">{fp}</td><td style="text-align:right">{_inum(t.get("qty"))}</td><td style="text-align:right">{_mnum(t.get("value"))}</td><td style="text-align:right">{comm}</td><td style="text-align:right">{stax}</td><td style="text-align:right">{net_amt}</td><td>{_e(_rzh(t.get("reason_code")))}</td></tr>'
    html += "</tbody></table>"
    return html


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_report(results_dir: str) -> str:
    """Read experiment artifacts from *results_dir* and return self-contained HTML."""
    rd = Path(results_dir)

    # Load artifacts
    perf = _load_json(rd / "perf.json")
    run_meta = _load_json(rd / "run_meta.json")
    config = _load_json(rd / "config.json")
    stock_names = _load_json(rd / "stock_names.json")
    counters = run_meta.get("counters") or {}
    tier = run_meta.get("tier") or "-"

    daily = _load_csv_rows(rd / "portfolio_daily.csv")
    trades = _load_csv_rows(rd / "portfolio_trades.csv")
    funnel_rows = _load_csv_rows(rd / "funnel.csv")
    funnel = funnel_rows[0] if funnel_rows else {}

    exp_id = run_meta.get("exp_id") or rd.name
    data = run_meta.get("data") or {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build KPI cards
    kpi_items = [
        ("年化收益", _pct(perf.get("cagr"))),
        ("最大回撤", _pct(perf.get("max_drawdown"))),
        ("夏普比率", _n2(perf.get("sharpe"))),
        ("卡尔马比率", _n2(perf.get("calmar"))),
        ("交易次数", _inum(perf.get("trades"))),
        ("换手率", _pct(perf.get("turnover"))),
        ("累计收益", _pct(perf.get("total_return"))),
        ("评级", _e(tier)),
    ]
    kpi_html = ""
    for label, val in kpi_items:
        val_str = str(val)
        cls = "negative" if val_str.startswith("-") and val_str != "-" else ("positive" if val_str and val_str[0].isdigit() else "")
        kpi_html += f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value {cls}">{val}</div></div>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>回测报告 - {_e(exp_id)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, 'Microsoft YaHei', sans-serif; color: #1a1a1a; padding: 40px 60px; max-width: 1000px; margin: 0 auto; line-height: 1.6; }}
  h1 {{ font-size: 24px; border-bottom: 2px solid #1a1a1a; padding-bottom: 8px; margin-bottom: 6px; }}
  .subtitle {{ color: #666; font-size: 13px; margin-bottom: 30px; }}
  h2 {{ font-size: 18px; color: #1a1a1a; margin: 30px 0 12px; padding-bottom: 4px; border-bottom: 1px solid #ddd; }}
  h3 {{ font-size: 15px; margin: 20px 0 8px; }}
  h4 {{ font-size: 14px; margin: 16px 0 6px; color: #444; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0 16px; font-size: 13px; }}
  th {{ background: #f5f5f5; font-weight: 600; text-align: left; padding: 6px 10px; border: 1px solid #ddd; white-space: nowrap; }}
  td {{ padding: 5px 10px; border: 1px solid #eee; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0; }}
  .kpi-card {{ border: 1px solid #e0e0e0; border-radius: 6px; padding: 12px; text-align: center; }}
  .kpi-label {{ font-size: 12px; color: #888; margin-bottom: 4px; }}
  .kpi-value {{ font-size: 20px; font-weight: 700; font-family: ui-monospace, monospace; }}
  .kpi-value.positive {{ color: #2e7d32; }}
  .kpi-value.negative {{ color: #c62828; }}
  @media print {{ body {{ padding: 20px; }} h2 {{ page-break-before: auto; }} table {{ page-break-inside: auto; }} }}
</style>
</head>
<body>
<h1>量化回测分析报告</h1>
<div class="subtitle">实验 {_e(exp_id)} | 生成于 {_e(now)}</div>

<h2>§1 概览</h2>
<table>
  <tr><td>回测区间</td><td>{_e(data.get('start', '-'))} ~ {_e(data.get('end', '-'))}</td></tr>
  <tr><td>基准指数</td><td>{_e(data.get('benchmark', '-'))}</td></tr>
  <tr><td>对照指数</td><td>{_e(data.get('compare_symbol', '-'))}</td></tr>
  <tr><td>股票池数量</td><td>{_inum(data.get('universe_limit', '-'))}</td></tr>
</table>
<div class="kpi-grid">
  {kpi_html}
</div>

<h2>§2 收益分析</h2>
<h3>月度收益率</h3>
{_build_monthly_returns(daily)}

<h2>§3 风险分析</h2>
{_build_drawdown_analysis(daily, perf)}

<h2>§4 交易分析</h2>
{_build_trade_analysis(trades, funnel, counters)}

<h2>§5 持仓分析</h2>
{_build_position_analysis(counters)}

<h2>§6 策略参数</h2>
{_build_config_summary(config)}

<h2>§7 附录：全部交易明细</h2>
<p style="color:#666;font-size:12px;margin-bottom:8px">共 {_inum(len(trades))} 条交易记录</p>
{_build_trade_appendix(trades, stock_names)}

</body>
</html>"""

    # Write to file
    report_path = rd / "report.html"
    report_path.write_text(html, encoding="utf-8")
    logger.info("Report generated: %s", report_path)
    return str(report_path)


# ---------------------------------------------------------------------------
# File loaders
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path)
        if df.empty:
            return []
        # Convert NaN to None for clean JSON handling
        return df.where(df.notna(), None).to_dict("records")
    except Exception:
        return []
