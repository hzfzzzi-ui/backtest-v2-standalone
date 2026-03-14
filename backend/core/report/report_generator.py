"""Generate a self-contained HTML backtest report from experiment artifacts."""
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
    "EMA_CROSS_UP": "EMA金叉",
    "EMA_CROSS_DOWN": "EMA死叉",
    "SIGNAL_REVERSE": "信号反转",
    "ATR_STOP_LOSS": "ATR止损",
    "ATR_TRAIL_STOP": "ATR跟踪止损",
    "ATR_TRAIL_EXIT": "ATR跟踪止盈",
    "PROFIT_DECAY_EXIT": "利润衰减退出",
    "TIME_EXIT": "到期平仓",
    "TREND_REVERSE": "趋势反转",
    "TREND_BREAK_EXIT": "趋势破位平仓",
    "RISK_OFF_EXIT": "风控平仓",
    "MANUAL_CLOSE": "手动平仓",
    "MAX_HOLD_DAYS": "持仓到期",
    "TAKE_PROFIT": "止盈",
    "STOP_LOSS": "止损",
    "LOW10_EXIT": "LOW10退出",
    "MA20_EXIT": "MA20退出",
}


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


def _render_enabled_k(enabled: Any, k: Any) -> str:
    if enabled is True:
        return f"启用 (k={_n2(k)})" if k is not None else "启用"
    if enabled is False:
        return "禁用"
    return "-"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _load_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path)
        if df.empty:
            return []
        return df.where(df.notna(), None).to_dict("records")
    except Exception:
        return []


def _pick_first(candidates: list[tuple[Any, str]]) -> tuple[Any, str, bool]:
    for value, source in candidates:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value, source, source != candidates[0][1]
    return None, "missing", True


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
      <tr><td>卡尔玛比率</td><td>{_n2(perf.get('calmar'))}</td></tr>
    </table>"""


def _build_trade_analysis(trades: list[dict], funnel: dict, counters: dict, funnel_source: str) -> str:
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

    f_raw = int(funnel.get("raw_signal") if funnel else 0)
    f_blocked = int(funnel.get("blocked") if funnel else 0)
    f_orders = int(funnel.get("orders") if funnel else 0)
    f_skipped = int(funnel.get("skipped") if funnel else 0)
    f_closed = int(funnel.get("closed_trades") if funnel else 0)

    if not funnel:
        f_raw = int(counters.get("raw_signal") or 0)
        f_blocked = int(counters.get("blocked") or 0)
        f_orders = int(counters.get("orders") or 0)
        f_skipped = int(counters.get("skipped") or 0)
        f_closed = int(counters.get("closed_trades") or 0)

    if f_raw or f_orders or f_closed:
        html += f"""<h4>信号漏斗</h4><p style="color:#666;font-size:12px">数据源: {_e(funnel_source)}；当前表格展示的是引擎事件级聚合计数，字段名未进一步区分 symbol-level 或 portfolio-level 口径。</p><table>
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
      <tr><td>个股上限触发</td><td style="color:#999">未实现</td></tr>
      <tr><td>行业上限触发</td><td style="color:#999">未实现</td></tr>
      <tr><td>资金不足跳过</td><td>{_inum(counters.get('cash_skip_count', 0))}</td></tr>
      <tr><td>最小手数跳过</td><td>{_inum(counters.get('lot_skip_count', 0))}</td></tr>
    </table>"""


def _build_config_summary(config: dict, run_config: dict, resolved_symbol_count: int) -> str:
    bc = config.get("base_config") or config or {}
    overrides = config.get("overrides") or {}
    wc = overrides.get("original_workbench_config") or overrides.get("workbench_config") or {}
    rc = run_config if isinstance(run_config, dict) else {}
    rc_exit = rc.get("exit") if isinstance(rc.get("exit"), dict) else {}
    rc_risk_budget = rc.get("risk_budget") if isinstance(rc.get("risk_budget"), dict) else {}
    rc_sizing = rc.get("sizing") if isinstance(rc.get("sizing"), dict) else {}

    sig_w = wc.get("signal_generation") if isinstance(wc.get("signal_generation"), dict) else {}
    bo_w = sig_w.get("breakout") if isinstance(sig_w.get("breakout"), dict) else {}
    pr_w = wc.get("position_risk") if isinstance(wc.get("position_risk"), dict) else {}
    ex_w = wc.get("exit_rules") if isinstance(wc.get("exit_rules"), dict) else {}
    u_w = wc.get("universe") if isinstance(wc.get("universe"), dict) else {}
    sizing_w = wc.get("sizing") if isinstance(wc.get("sizing"), dict) else {}
    benchmark_regime_w = wc.get("benchmark_regime") if isinstance(wc.get("benchmark_regime"), dict) else {}
    stock_trend_w = wc.get("stock_trend_filter") if isinstance(wc.get("stock_trend_filter"), dict) else {}
    sector_gate_w = wc.get("sector_gate") if isinstance(wc.get("sector_gate"), dict) else {}
    filters = u_w.get("filters") if isinstance(u_w.get("filters"), dict) else {}

    strategy = (sig_w.get("strategy") or _dig(rc, "strategy.name") or "UNKNOWN").upper()
    params = _dig(rc, "strategy.params") or {}
    regime_det = sig_w.get("regime_detection") if isinstance(sig_w.get("regime_detection"), dict) else {}
    regime_filter = regime_det.get("regime_filter") if isinstance(regime_det.get("regime_filter"), dict) else {}
    ranking_w = sig_w.get("ranking") if isinstance(sig_w.get("ranking"), dict) else {}
    risk_budget_w = pr_w.get("risk_budget") if isinstance(pr_w.get("risk_budget"), dict) else {}
    market_filter_w = pr_w.get("market_filter") if isinstance(pr_w.get("market_filter"), dict) else {}
    breadth_w = pr_w.get("breadth") if isinstance(pr_w.get("breadth"), dict) else {}

    html = ""

    if strategy == "BREAKOUT_TREND" or str(_dig(rc, "strategy.name") or "").lower() == "breakout_trend":
        bw = bo_w.get("breakout_window")
        if bw is None:
            bw = params.get("breakout_window")
        confirm_mode = bo_w.get("entry_confirm_mode")
        if confirm_mode is None:
            confirm_mode = params.get("entry_confirm_mode")
        delay_mode = bo_w.get("entry_delay_mode")
        if delay_mode is None:
            delay_mode = params.get("entry_delay_mode")
        portfolio_mode = pr_w.get("portfolio_mode")
        if portfolio_mode is None:
            portfolio_mode = params.get("portfolio_mode")
        html += f"""<h3>信号策略</h3><table>
      <tr><td>策略名称</td><td>{_e(strategy)}</td></tr>
      <tr><td>突破窗口</td><td>{_e(bw if bw is not None else '-')}</td></tr>
      <tr><td>入场确认模式</td><td>{_e(confirm_mode if confirm_mode is not None else '-')}</td></tr>
      <tr><td>延迟入场模式</td><td>{_e(delay_mode if delay_mode is not None else '-')}</td></tr>
      <tr><td>组合模式</td><td>{_e(portfolio_mode if portfolio_mode is not None else '-')}</td></tr>
    </table>"""
    else:
        fast_ma = sig_w.get("ema", {}).get("fast_ma") or sig_w.get("sma", {}).get("fast_ma") or _dig(rc, "strategy.fast")
        slow_ma = sig_w.get("ema", {}).get("slow_ma") or sig_w.get("sma", {}).get("slow_ma") or _dig(rc, "strategy.slow")
        entry_buf = sig_w.get("ema", {}).get("entry_buffer_pct") or sig_w.get("sma", {}).get("entry_buffer_pct")
        html += f"""<h3>信号策略</h3><table>
      <tr><td>策略名称</td><td>{_e(strategy)}</td></tr>
      <tr><td>快线周期</td><td>{_e(fast_ma if fast_ma is not None else '-')}</td></tr>
      <tr><td>慢线周期</td><td>{_e(slow_ma if slow_ma is not None else '-')}</td></tr>
      <tr><td>入场缓冲</td><td>{_n2(entry_buf) + '%' if entry_buf is not None else '-'}</td></tr>
    </table>"""

    regime_enabled = regime_det.get("enabled")
    if regime_enabled is None:
        regime_enabled = strategy == "REGIME_ROUTER"
    benchmark_regime_enabled = benchmark_regime_w.get("enabled")
    if benchmark_regime_enabled is None:
        benchmark_regime_enabled = _dig(rc, "benchmark_regime.enabled")
    stock_trend_enabled = stock_trend_w.get("enabled")
    if stock_trend_enabled is None:
        stock_trend_enabled = params.get("enable_v2_trend_filter")
    sector_gate_enabled = sector_gate_w.get("enabled")
    if sector_gate_enabled is None:
        sector_gate_enabled = params.get("enable_sector_gate")
    html += f"""<h3>Stage 2-5 过滤</h3><table>
      <tr><td>Regime Router</td><td>{_enabled_txt(regime_enabled)}</td></tr>
      <tr><td>regime_ma</td><td>{_e(regime_det.get('regime_ma', params.get('regime_ma', '-')))}</td></tr>
      <tr><td>Regime Filter</td><td>{_enabled_txt(regime_filter.get('enabled'))}</td></tr>
      <tr><td>regime_threshold</td><td>{_e(regime_filter.get('regime_threshold', '-'))}</td></tr>
      <tr><td>Benchmark Regime</td><td>{_enabled_txt(benchmark_regime_enabled)}</td></tr>
      <tr><td>BR fast / slow / slope</td><td>{_e(benchmark_regime_w.get('fast_period', _dig(rc, 'benchmark_regime.fast_period') if _dig(rc, 'benchmark_regime.fast_period') is not None else '-'))} / {_e(benchmark_regime_w.get('slow_period', _dig(rc, 'benchmark_regime.slow_period') if _dig(rc, 'benchmark_regime.slow_period') is not None else '-'))} / {_e(benchmark_regime_w.get('slope_window', _dig(rc, 'benchmark_regime.slope_window') if _dig(rc, 'benchmark_regime.slope_window') is not None else '-'))}</td></tr>
      <tr><td>个股趋势过滤</td><td>{_enabled_txt(stock_trend_enabled)}</td></tr>
      <tr><td>STF short / long</td><td>{_e(stock_trend_w.get('short_ma', params.get('v2_trend_short_ma', '-')))} / {_e(stock_trend_w.get('long_ma', params.get('v2_trend_long_ma', '-')))}</td></tr>
      <tr><td>行业趋势门控</td><td>{_enabled_txt(sector_gate_enabled)}</td></tr>
      <tr><td>Sector rank / top_pct</td><td>{_e(sector_gate_w.get('rank_window', params.get('sector_rank_window', '-')))} / {_e(sector_gate_w.get('top_pct', params.get('sector_top_pct', '-')))}</td></tr>
      <tr><td>momentum_top_pct</td><td>{_e(ranking_w.get('momentum_top_pct', params.get('momentum_top_pct', '-')))}</td></tr>
    </table>"""

    atr_stop = ex_w.get("atr_stop") if isinstance(ex_w.get("atr_stop"), dict) else {}
    trailing = ex_w.get("trailing") if isinstance(ex_w.get("trailing"), dict) else {}
    low10_exit = ex_w.get("low10_exit") if isinstance(ex_w.get("low10_exit"), dict) else {}
    ma20_exit = ex_w.get("ma20_exit") if isinstance(ex_w.get("ma20_exit"), dict) else {}
    strategy_atr_stop_enabled = params.get("enable_atr_stop")
    strategy_atr_stop_k = params.get("atr_stop_k")
    strategy_atr_trail_enabled = params.get("enable_atr_trail")
    strategy_atr_trail_k = params.get("atr_trail_k")
    exit_atr_stop_enabled = atr_stop.get("enabled")
    if exit_atr_stop_enabled is None:
        exit_atr_stop_enabled = rc_exit.get("enable_atr_stop")
    exit_atr_stop_k = atr_stop.get("k")
    if exit_atr_stop_k is None:
        exit_atr_stop_k = rc_exit.get("atr_stop_k")
    exit_atr_trail_enabled = trailing.get("enabled")
    if exit_atr_trail_enabled is None:
        exit_atr_trail_enabled = rc_exit.get("enable_atr_trail")
    exit_atr_trail_k = trailing.get("k")
    if exit_atr_trail_k is None:
        exit_atr_trail_k = rc_exit.get("atr_trail_k")
    low10_enabled = low10_exit.get("enabled")
    if low10_enabled is None:
        low10_enabled = rc_exit.get("enable_low10_exit", params.get("enable_low10_exit"))
    ma20_enabled = ma20_exit.get("enabled")
    if ma20_enabled is None:
        ma20_enabled = rc_exit.get("enable_ma20_exit", params.get("enable_ma20_exit"))
    min_hold_days = _dig(ex_w, "hold_constraint.min_hold_days")
    if min_hold_days is None:
        min_hold_days = params.get("min_hold_days")
    cooldown_days = _dig(ex_w, "hold_constraint.cooldown_days")
    if cooldown_days is None:
        cooldown_days = params.get("cooldown_days")
    html += f"""<h3>退出规则</h3><table>
      <tr><td>反转退出</td><td>{_enabled_txt(ex_w.get('signal_reverse'))}</td></tr>
      <tr><td>策略层 ATR 止损</td><td>{_render_enabled_k(strategy_atr_stop_enabled, strategy_atr_stop_k)}</td></tr>
      <tr><td>策略层 ATR 跟踪</td><td>{_render_enabled_k(strategy_atr_trail_enabled, strategy_atr_trail_k)}</td></tr>
      <tr><td>Exit 层 ATR 止损</td><td>{_render_enabled_k(exit_atr_stop_enabled, exit_atr_stop_k)}</td></tr>
      <tr><td>Exit 层 ATR 跟踪</td><td>{_render_enabled_k(exit_atr_trail_enabled, exit_atr_trail_k)}</td></tr>
      <tr><td>MA20 退出</td><td>{_enabled_txt(ma20_enabled)}</td></tr>
      <tr><td>LOW10 退出</td><td>{_enabled_txt(low10_enabled)}</td></tr>
      <tr><td>最短持有天数</td><td>{_e(min_hold_days if min_hold_days is not None else '-')}</td></tr>
      <tr><td>冷却天数</td><td>{_e(cooldown_days if cooldown_days is not None else '-')}</td></tr>
      <tr><td>参数来源</td><td>runtime config 优先，workbench draft 仅回退</td></tr>
    </table>"""

    single_cap = pr_w.get("single_stock_cap")
    ind_cap = pr_w.get("industry_cap")
    html += f"""<h3>仓位与风险</h3><table>
      <tr><td>最大持仓数</td><td>{_e(pr_w.get('max_positions', '-'))}</td></tr>
      <tr><td>单票上限</td><td>{f'{float(single_cap) * 100:.0f}%' if single_cap is not None else '-'}</td></tr>
      <tr><td>行业上限</td><td>{f'{float(ind_cap) * 100:.0f}%' if ind_cap is not None else '-'}</td></tr>
      <tr><td>现金不足策略</td><td>{_e(pr_w.get('cash_shortage_policy', '-'))}</td></tr>
      <tr><td>组合模式</td><td>{_e(pr_w.get('portfolio_mode', params.get('portfolio_mode', '-')))}</td></tr>
      <tr><td>weight_mode</td><td>{_e(sizing_w.get('weight_mode', rc_sizing.get('weight_mode', 'equal')))}</td></tr>
      <tr><td>min_positions</td><td>{_e(sizing_w.get('min_positions', rc_sizing.get('min_positions', '-')))}</td></tr>
    </table>"""

    html += f"""<h3>风控扩展</h3><table>
      <tr><td>Risk Budget</td><td>{_enabled_txt(risk_budget_w.get('enabled', rc_risk_budget.get('enabled')))}</td></tr>
      <tr><td>RB atr_stop_k</td><td>{_e(risk_budget_w.get('atr_stop_k', rc_risk_budget.get('atr_stop_k', '-')))}</td></tr>
      <tr><td>RB base_portfolio_risk</td><td>{_e(risk_budget_w.get('base_portfolio_risk', '-'))}</td></tr>
      <tr><td>RB legacy dd_reduce_pct</td><td>{_e(risk_budget_w.get('dd_reduce_pct', rc_risk_budget.get('dd_reduce_pct', '-')))}</td></tr>
      <tr><td>RB legacy dd_reduce_scale</td><td>{_e(risk_budget_w.get('dd_reduce_scale', rc_risk_budget.get('dd_reduce_scale', '-')))}</td></tr>
      <tr><td>Market Filter</td><td>{_enabled_txt(market_filter_w.get('enabled', _dig(rc, 'market_filter.enabled')))}</td></tr>
      <tr><td>MF slope_ma / slope_window</td><td>{_e(market_filter_w.get('slope_ma_period', _dig(rc, 'market_filter.slope_ma_period') if _dig(rc, 'market_filter.slope_ma_period') is not None else '-'))} / {_e(market_filter_w.get('slope_window', _dig(rc, 'market_filter.slope_window') if _dig(rc, 'market_filter.slope_window') is not None else '-'))}</td></tr>
      <tr><td>Breadth</td><td>{_enabled_txt(breadth_w.get('enabled', _dig(rc, 'breadth.enabled')))}</td></tr>
      <tr><td>Breadth mode</td><td>{_e(breadth_w.get('mode', _dig(rc, 'breadth.mode') if _dig(rc, 'breadth.mode') is not None else '-'))}</td></tr>
      <tr><td>Breadth min/max positions</td><td>{_e(breadth_w.get('min_positions', _dig(rc, 'breadth.min_positions') if _dig(rc, 'breadth.min_positions') is not None else '-'))} / {_e(breadth_w.get('max_positions', _dig(rc, 'breadth.max_positions') if _dig(rc, 'breadth.max_positions') is not None else '-'))}</td></tr>
      <tr><td>风险参数来源</td><td>runtime config 优先，workbench draft 仅回退</td></tr>
    </table>"""

    turnover_20d = filters.get("min_avg_turnover_20d")
    tn = _safe_float(turnover_20d)
    turnover_display = f"{int(tn / 10000):,} 万" if tn is not None else "-"
    turnover_rate_20d = _safe_float(filters.get("min_avg_turnover_rate_20d"))
    turnover_rate_display = f"{turnover_rate_20d:.2f}%" if turnover_rate_20d is not None and turnover_rate_20d > 0 else "-"
    turnover_rate_field = filters.get("turnover_rate_field") or "-"
    price_min = filters.get("price_min", "-")
    price_max = filters.get("price_max", "-")
    price_range = f"{price_min} ~ {price_max}" if (price_min != "-" or price_max != "-") else "-"
    adj_val = u_w.get("price_adj") or overrides.get("price_adj") or _dig(rc, "universe.price_adj") or "-"

    html += f"""<h3>选股范围</h3><table>
      <tr><td>选股模式</td><td>{_e(wc.get('universe_mode') or overrides.get('universe_mode') or '-')}</td></tr>
      <tr><td>标的数量</td><td>{_inum(resolved_symbol_count)}</td></tr>
      <tr><td>排除 ST</td><td>{_yes_no(filters.get('exclude_st'))}</td></tr>
      <tr><td>排除停牌</td><td>{_yes_no(filters.get('exclude_suspended'))}</td></tr>
      <tr><td>最小上市天数</td><td>{_inum(filters.get('min_list_days')) if filters.get('min_list_days') is not None else '-'}</td></tr>
      <tr><td>日均成交额下限</td><td>{turnover_display}</td></tr>
      <tr><td>20日均换手率下限</td><td>{_e(turnover_rate_display)}</td></tr>
      <tr><td>换手率字段</td><td>{_e(turnover_rate_field)}</td></tr>
      <tr><td>价格区间</td><td>{_e(price_range)}</td></tr>
      <tr><td>涨跌停规则</td><td>{_e(filters.get('limit_rule') or '-')}</td></tr>
      <tr><td>价格口径</td><td>{_e(_price_adj_label(adj_val))} ({_e(adj_val)})</td></tr>
    </table>"""

    costs = bc.get("costs") or {}
    execution = bc.get("execution") or {}
    comm_rate = _safe_float(costs.get("commission_rate"))
    stamp_rate = _safe_float(costs.get("stamp_tax_rate"))
    comm_rate_str = f"{comm_rate * 10000:.0f}‱" if comm_rate is not None else "-"
    stamp_rate_str = f"{stamp_rate * 1000:.0f}‰" if stamp_rate is not None else "-"

    html += f"""<h3>执行假设</h3><table>
      <tr><td>佣金率</td><td>{comm_rate_str}</td></tr>
      <tr><td>最低佣金</td><td>{_n2(costs.get('commission_min')) if costs.get('commission_min') is not None else '-'}</td></tr>
      <tr><td>印花税率</td><td>{stamp_rate_str}</td></tr>
      <tr><td>滑点</td><td>{_n2(costs.get('slippage_bps')) + ' bps' if costs.get('slippage_bps') is not None else '-'}</td></tr>
      <tr><td>手数</td><td>{_inum(execution.get('lot_size')) if execution.get('lot_size') is not None else '-'}</td></tr>
      <tr><td>T+1</td><td>{_yes_no(execution.get('t_plus_one'))}</td></tr>
      <tr><td>初始资金</td><td>{f"{int(bc.get('initial_capital')):,}" if bc.get('initial_capital') is not None else '-'}</td></tr>
    </table>"""

    return html


def _build_trade_appendix(
    trades: list[dict],
    stock_names: dict[str, str],
    trade_st_flags: dict[str, str] | None = None,
) -> str:
    if not trades:
        return "<p>无交易记录</p>"

    flags = dict(trade_st_flags or {})
    html = '<table><thead><tr><th>日期</th><th>标的</th><th>方向</th><th style="text-align:right">成交价</th><th style="text-align:right">数量</th><th style="text-align:right">金额</th><th style="text-align:right">佣金</th><th style="text-align:right">印花税</th><th style="text-align:right">净额</th><th>原因</th><th>ST判定</th></tr></thead><tbody>'
    for t in trades:
        is_buy = str(t.get("side") or "").upper() == "BUY"
        side = '<span style="color:#2e7d32;font-weight:600">买入</span>' if is_buy else '<span style="color:#c62828;font-weight:600">卖出</span>'

        sym = str(t.get("symbol") or "")
        display_name = stock_names.get(sym, sym)
        symbol_cell = f'<span title="{_e(sym)}">{_e(display_name)}</span>' if display_name != sym else _e(sym)

        fp_raw = t.get("fill_price")
        fp = f"{float(fp_raw):.3f}" if fp_raw is not None else f"{float(t.get('price') or 0):.3f}"
        comm = _mnum(t.get("commission")) if t.get("commission") is not None else "-"
        stax = _mnum(t.get("stamp_tax")) if t.get("stamp_tax") is not None else "-"
        net_amt = _mnum(t.get("net_amount")) if t.get("net_amount") is not None else _mnum(t.get("value"))
        date_str = str(t.get("date", ""))
        st_flag = flags.get(f"{date_str}|{sym.lower()}", "-")

        html += f'<tr><td>{_e(date_str)}</td><td>{symbol_cell}</td><td>{side}</td><td style="text-align:right">{fp}</td><td style="text-align:right">{_inum(t.get("qty"))}</td><td style="text-align:right">{_mnum(t.get("value"))}</td><td style="text-align:right">{comm}</td><td style="text-align:right">{stax}</td><td style="text-align:right">{net_amt}</td><td>{_e(_rzh(t.get("reason_code")))}</td><td>{_e(st_flag)}</td></tr>'
    html += "</tbody></table>"
    return html


def generate_report(results_dir: str) -> str:
    rd = Path(results_dir)

    perf = _load_json(rd / "perf.json")
    run_meta = _load_json(rd / "run_meta.json")
    config = _load_json(rd / "config.json")
    run_config = _load_json(rd / "run_config.json")
    stock_names = _load_json(rd / "stock_names.json")
    trade_st_flags = _load_json(rd / "trade_st_flags.json")

    counters = run_meta.get("counters") or {}
    tier = run_meta.get("tier") or "-"
    daily = _load_csv_rows(rd / "portfolio_daily.csv")
    trades = _load_csv_rows(rd / "portfolio_trades.csv")
    funnel_rows = _load_csv_rows(rd / "funnel.csv")
    funnel = funnel_rows[0] if funnel_rows else {}

    data = run_meta.get("data") if isinstance(run_meta.get("data"), dict) else {}
    universe_meta = run_meta.get("universe") if isinstance(run_meta.get("universe"), dict) else {}
    overrides = config.get("overrides") if isinstance(config.get("overrides"), dict) else {}
    wc = overrides.get("original_workbench_config") if isinstance(overrides.get("original_workbench_config"), dict) else {}
    wc_u = wc.get("universe") if isinstance(wc.get("universe"), dict) else {}
    rc_u = run_config.get("universe") if isinstance(run_config.get("universe"), dict) else {}

    start, start_src, start_fallback = _pick_first([
        (rc_u.get("start"), "run_config.universe.start"),
        (wc_u.get("start"), "original_workbench_config.universe.start"),
        (data.get("start"), "run_meta.data.start"),
    ])
    end, end_src, end_fallback = _pick_first([
        (rc_u.get("end"), "run_config.universe.end"),
        (wc_u.get("end"), "original_workbench_config.universe.end"),
        (data.get("end"), "run_meta.data.end"),
    ])
    benchmark, benchmark_src, benchmark_fallback = _pick_first([
        (rc_u.get("benchmark"), "run_config.universe.benchmark"),
        (wc_u.get("benchmark"), "original_workbench_config.universe.benchmark"),
        (data.get("benchmark"), "run_meta.data.benchmark"),
    ])

    symbol_count_val, symbol_count_src, symbol_count_fallback = _pick_first([
        (universe_meta.get("raw_count"), "run_meta.universe.raw_count"),
        (universe_meta.get("after_filters_symbols"), "run_meta.universe.after_filters_symbols"),
        (len(wc_u.get("symbols") or []), "original_workbench_config.universe.symbols"),
    ])
    resolved_symbol_count = int(symbol_count_val or 0)
    report_consistency = dict(run_meta.get("report_consistency") or {})
    resolved_config_mode = str(report_consistency.get("resolved_config_mode") or "-")
    resolved_config_id = str(report_consistency.get("resolved_config_id") or "-")
    resolved_config_hash = str(report_consistency.get("resolved_config_hash") or "-")
    resolved_config_meta = dict(report_consistency.get("resolved_config_meta") or {})
    resolved_universe_mode = str(
        resolved_config_meta.get("universe_mode")
        or data.get("universe_mode")
        or universe_meta.get("universe_mode")
        or "-"
    )

    funnel_source = "funnel.csv" if funnel else "run_meta.counters"

    exp_id = run_meta.get("exp_id") or rd.name
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    kpi_items = [
        ("年化收益", _pct(perf.get("cagr"))),
        ("最大回撤", _pct(perf.get("max_drawdown"))),
        ("夏普比率", _n2(perf.get("sharpe"))),
        ("卡尔玛比率", _n2(perf.get("calmar"))),
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

    source_diag = [
        ("区间开始", f"{_e(start_src)}{' (fallback)' if start_fallback else ''}"),
        ("区间结束", f"{_e(end_src)}{' (fallback)' if end_fallback else ''}"),
        ("基准", f"{_e(benchmark_src)}{' (fallback)' if benchmark_fallback else ''}"),
        ("标的数量", f"{_e(symbol_count_src)}{' (fallback)' if symbol_count_fallback else ''}"),
        ("漏斗", funnel_source),
        ("配置冲突策略", _e(report_consistency.get("config_conflict_policy") or overrides.get("config_conflict_policy") or "-")),
        ("解析配置模式", _e(resolved_config_mode)),
        ("解析配置ID", _e(resolved_config_id)),
        ("解析配置Hash", _e(resolved_config_hash)),
        ("解析配置股票池", _e(resolved_universe_mode)),
    ]

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
  <tr><td>回测区间</td><td>{_e(start or '-')} ~ {_e(end or '-')}</td></tr>
  <tr><td>基准指数</td><td>{_e(benchmark or '-')}</td></tr>
  <tr><td>对照指数</td><td>{_e(data.get('compare_symbol', '-'))}</td></tr>
  <tr><td>股票池模式</td><td>{_e(resolved_universe_mode)}</td></tr>
  <tr><td>股票池数量</td><td>{_inum(resolved_symbol_count)}</td></tr>
  <tr><td>解析配置</td><td>{_e(f"{resolved_config_mode} | {resolved_config_id}")}</td></tr>
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
{_build_trade_analysis(trades, funnel, counters, funnel_source)}

<h2>§5 持仓分析</h2>
{_build_position_analysis(counters)}

<h2>§6 策略参数</h2>
{_build_config_summary(config, run_config, resolved_symbol_count)}

<h2>§7 附录：全部交易明细</h2>
<p style="color:#666;font-size:12px;margin-bottom:8px">共 {_inum(len(trades))} 条交易记录</p>
{_build_trade_appendix(trades, stock_names, trade_st_flags)}

<h2>§8 口径诊断</h2>
<table>
  <thead><tr><th>字段</th><th>来源</th></tr></thead>
  <tbody>
    {''.join(f'<tr><td>{_e(k)}</td><td>{_e(v)}</td></tr>' for k, v in source_diag)}
  </tbody>
</table>

</body>
</html>"""

    report_path = rd / "report.html"
    report_path.write_text(html, encoding="utf-8")
    logger.info("Report generated: %s", report_path)
    return str(report_path)
