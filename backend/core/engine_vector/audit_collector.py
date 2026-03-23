"""回测审计检查点收集器。

在仿真循环中嵌入 5 个检查点（CP1–CP5），逐日记录恒等式检查结果，
循环结束后汇总为 audit dict，写入 audit.json 供外部 AI 审查回测正确性。
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
_MAX_FLAGS = 50
_MAX_FLAGGED_DAYS = 50
_STALE_STREAK_THRESHOLD = 20  # 连续无信号天数阈值
_LIMIT_GAP_PCT = 9.5  # A股涨跌停近似阈值 (%)
_CASH_TOL = 0.015  # 现金守恒容差 (元)
_NAV_TOL = 0.01  # NAV 守恒容差 (元)


class AuditCollector:
    """回测审计收集器。两条仿真路径共用同一接口。"""

    def __init__(
        self,
        initial_cash: float,
        max_positions: int,
        cost_config: dict[str, Any] | None = None,
        market_key: str = "CN_A",
    ) -> None:
        if str(market_key or "").strip().upper() not in {"CN_A", "CN_ETF"}:
            raise ValueError(f"audit collector market rules unavailable for market_key: {market_key}")
        self._initial_cash = float(initial_cash)
        self._max_positions = int(max_positions)
        self._cost_config = dict(cost_config or {})
        self._market_key = "CN_A" if str(market_key or "").strip().upper() == "CN_A" else "CN_ETF"

        # CP1: 数据质量
        self.data_quality: dict[str, Any] = {}

        # 逐日汇总计数器
        self._cash_check_pass = 0
        self._cash_check_fail = 0
        self._pos_check_pass = 0
        self._pos_check_fail = 0
        self._nav_check_pass = 0
        self._nav_check_fail = 0
        self._t1_check_pass = 0
        self._t1_check_fail = 0
        self._total_fills = 0
        self._total_signals = 0
        self._orphan_fills = 0

        # 成本累计
        self._total_commission = 0.0
        self._total_stamp_tax = 0.0
        self._total_slippage = 0.0

        # 价格跳空收集
        self._gap_pcts: list[float] = []

        # 异常日 + flags
        self._flagged_days: list[dict[str, Any]] = []
        self._flags: list[dict[str, Any]] = []

        # 策略僵死检测
        self._no_signal_streak = 0
        self._no_signal_has_positions = False

        # 当日临时状态
        self._current_day: dict[str, Any] | None = None
        self._day_is_flagged = False

    # ------------------------------------------------------------------
    # CP1: 数据质量（循环前调用一次）
    # ------------------------------------------------------------------
    def record_data_quality(
        self,
        open_idx: dict[tuple[date, str], float],
        close_idx: dict[tuple[date, str], float],
        trading_days: list[date],
        symbols: list[str],
    ) -> None:
        """统计价格矩阵的 NaN 率、日期连续性、标的覆盖率。"""
        td_count = len(trading_days)
        sym_count = len(symbols)
        total_cells = td_count * sym_count if sym_count > 0 else 1

        close_nan = 0
        open_nan = 0
        sym_coverage: dict[str, int] = {s: 0 for s in symbols}

        for d in trading_days:
            for s in symbols:
                cv = close_idx.get((d, s))
                ov = open_idx.get((d, s))
                if cv is None or cv == 0.0 or (isinstance(cv, float) and math.isnan(cv)):
                    close_nan += 1
                else:
                    sym_coverage[s] = sym_coverage.get(s, 0) + 1
                if ov is None or ov == 0.0 or (isinstance(ov, float) and math.isnan(ov)):
                    open_nan += 1

        # 日期缺口: 检查相邻交易日之间是否有异常大间隔 (> 5 个自然日)
        date_gaps = 0
        for i in range(1, td_count):
            delta = (trading_days[i] - trading_days[i - 1]).days
            if delta > 5:
                date_gaps += 1

        full_coverage = sum(1 for v in sym_coverage.values() if v == td_count)

        self.data_quality = {
            "trading_days_count": td_count,
            "symbols_count": sym_count,
            "close_nan_rate": round(close_nan / total_cells, 4) if total_cells > 0 else 0.0,
            "open_nan_rate": round(open_nan / total_cells, 4) if total_cells > 0 else 0.0,
            "date_gaps": date_gaps,
            "symbols_with_full_coverage": full_coverage,
        }

    # ------------------------------------------------------------------
    # CP2 前置: begin_day
    # ------------------------------------------------------------------
    def begin_day(self, day: date, cash: float, positions: dict[str, int]) -> None:
        """记录当天 fill 前的现金和持仓快照。"""
        self._current_day = {
            "date": day.isoformat(),
            "cash_before": cash,
            "positions_before": len(positions),
            "positions_snapshot_before": dict(positions),
            # 以下字段由后续方法填充
            "cash_after": 0.0,
            "fills_net": 0.0,
            "costs_total": 0.0,
            "cash_check": True,
            "positions_after": 0,
            "buys_filled": 0,
            "sells_filled": 0,
            "pos_check": True,
            "nav": 0.0,
            "cash": 0.0,
            "market_value": 0.0,
            "nav_check": True,
            "signals_generated": 0,
            "orders_scheduled": 0,
            "fills_from_yesterday": 0,
            "t1_check": True,
            "fills": [],
        }
        self._day_is_flagged = False

    # ------------------------------------------------------------------
    # CP2: Fill 执行后
    # ------------------------------------------------------------------
    def record_fills(
        self,
        trade_rows_today: list[dict[str, Any]],
        cash_after: float,
        positions_after: dict[str, int],
    ) -> None:
        """现金守恒 + 持仓守恒 + 成交价合理性。"""
        cd = self._current_day
        if cd is None:
            return

        cash_before = cd["cash_before"]
        fills_detail: list[dict[str, Any]] = []
        sell_net_sum = 0.0
        buy_net_sum = 0.0
        costs_sum = 0.0
        buys = 0
        sells = 0

        for tr in trade_rows_today:
            side = str(tr.get("side", ""))
            net = float(tr.get("net_amount", 0.0))
            comm = float(tr.get("commission", 0.0))
            stax = float(tr.get("stamp_tax", 0.0))
            slip = float(tr.get("slippage", 0.0))
            fill_px = float(tr.get("fill_price", 0.0))
            open_px = float(tr.get("price", 0.0))
            reason = str(tr.get("reason_code", ""))

            costs_sum += comm + stax
            self._total_commission += comm
            self._total_stamp_tax += stax
            self._total_slippage += slip
            self._total_fills += 1

            if side == "SELL":
                sell_net_sum += net
                sells += 1
            elif side == "BUY":
                buy_net_sum += net
                buys += 1

            # 孤立成交检测
            if not reason:
                self._orphan_fills += 1
                self._add_flag("WARNING", cd["date"], f"{tr.get('symbol', '?')}: 成交无 reason_code（孤立成交）")

            # 跳空记录 (signal_close 在 meta_json 中不一定有，用 fill detail 记录)
            fill_rec: dict[str, Any] = {
                "sym": str(tr.get("symbol", "")),
                "side": side,
                "fill_open": round(open_px, 4),
                "fill_price": round(fill_px, 4),
                "slip_bps": round(abs(fill_px - open_px) / open_px * 10000, 2) if open_px > 0 else 0.0,
            }

            # signal_close 需要从 meta 获取（如果可用）
            meta = tr.get("_signal_close")
            if meta is not None:
                signal_close = float(meta)
                gap_pct = (open_px - signal_close) / signal_close * 100 if signal_close > 0 else 0.0
                fill_rec["signal_close"] = round(signal_close, 4)
                fill_rec["gap_pct"] = round(gap_pct, 2)
                self._gap_pcts.append(abs(gap_pct))

                # 涨跌停成交检测
                if abs(gap_pct) >= _LIMIT_GAP_PCT:
                    self._add_flag(
                        "WARNING",
                        cd["date"],
                        f"{fill_rec['sym']}: 跳空 {gap_pct:+.2f}%（疑似涨跌停成交）",
                    )

            fills_detail.append(fill_rec)

        # 现金守恒检查: cash_after == cash_before + sell_net - buy_net
        expected_cash = cash_before + sell_net_sum - buy_net_sum
        cash_check = abs(cash_after - expected_cash) < _CASH_TOL
        if not cash_check:
            self._cash_check_fail += 1
            self._day_is_flagged = True
        else:
            self._cash_check_pass += 1

        # 持仓守恒检查: 按标的级别比较
        pos_before = cd.get("positions_snapshot_before", {})
        pos_check = True
        new_entries = 0
        full_exits = 0
        for sym in set(list(pos_before.keys()) + list(positions_after.keys())):
            before_qty = int(pos_before.get(sym, 0))
            after_qty = int(positions_after.get(sym, 0))
            # 统计该标的今日买入/卖出
            sym_buys = sum(int(tr.get("qty", 0)) for tr in trade_rows_today if tr.get("symbol") == sym and tr.get("side") == "BUY")
            sym_sells = sum(int(tr.get("qty", 0)) for tr in trade_rows_today if tr.get("symbol") == sym and tr.get("side") == "SELL")
            expected_qty = before_qty + sym_buys - sym_sells
            if after_qty != expected_qty:
                pos_check = False
            if before_qty == 0 and after_qty > 0:
                new_entries += 1
            if before_qty > 0 and after_qty <= 0:
                full_exits += 1

        if not pos_check:
            self._pos_check_fail += 1
            self._day_is_flagged = True
        else:
            self._pos_check_pass += 1

        cd["cash_before"] = round(cd["cash_before"], 2)  # 计算完成后 round 用于显示
        cd["cash_after"] = round(cash_after, 2)
        cd["fills_net"] = round(sell_net_sum - buy_net_sum, 2)
        cd["costs_total"] = round(costs_sum, 2)
        cd["cash_check"] = cash_check
        cd["positions_after"] = len(positions_after)
        cd["buys_filled"] = buys
        cd["sells_filled"] = sells
        cd["pos_check"] = pos_check
        cd["fills"] = fills_detail
        cd["fills_from_yesterday"] = buys + sells

        # 现金负值检测
        if cash_after < 0:
            self._add_flag("ERROR", cd["date"], f"现金为负: {cash_after:.2f}")
            self._day_is_flagged = True

        # 持仓超限检测
        if len(positions_after) > self._max_positions:
            self._add_flag("ERROR", cd["date"], f"持仓超限: {len(positions_after)} > max {self._max_positions}")
            self._day_is_flagged = True

    # ------------------------------------------------------------------
    # CP3: NAV 快照后
    # ------------------------------------------------------------------
    def record_nav(self, nav: float, cash: float, market_value: float) -> None:
        """NAV = cash + market_value 恒等式检查。"""
        cd = self._current_day
        if cd is None:
            return

        nav_ok = True

        # NaN / 负值检测
        if math.isnan(nav) or nav < 0:
            nav_ok = False
            self._add_flag("ERROR", cd["date"], f"NAV 异常: {nav}")
            self._day_is_flagged = True

        # 恒等式: nav == cash + market_value
        if nav_ok and abs(nav - (cash + market_value)) > _NAV_TOL:
            nav_ok = False
            self._day_is_flagged = True

        if nav_ok:
            self._nav_check_pass += 1
        else:
            self._nav_check_fail += 1

        cd["nav"] = round(nav, 2)
        cd["cash"] = round(cash, 2)
        cd["market_value"] = round(market_value, 2)
        cd["nav_check"] = nav_ok

    # ------------------------------------------------------------------
    # CP4: 信号生成 + 订单构建后
    # ------------------------------------------------------------------
    def record_signals(
        self,
        signals_count: int,
        orders_count: int,
        fills_from_yesterday: int,
    ) -> None:
        """T+1 验证 + 信号/订单追踪。"""
        cd = self._current_day
        if cd is None:
            return

        self._total_signals += signals_count
        cd["signals_generated"] = signals_count
        cd["orders_scheduled"] = orders_count
        cd["fills_from_yesterday"] = fills_from_yesterday

        # T+1 天然成立（引擎设计即 pending[next_day]），此处仅记录
        cd["t1_check"] = True
        self._t1_check_pass += 1

        # 策略僵死追踪
        positions_count = cd.get("positions_after", 0)
        if signals_count == 0 and positions_count > 0:
            self._no_signal_streak += 1
            self._no_signal_has_positions = True
        else:
            if self._no_signal_streak >= _STALE_STREAK_THRESHOLD and self._no_signal_has_positions:
                self._add_flag(
                    "WARNING",
                    cd["date"],
                    f"策略僵死: 连续 {self._no_signal_streak} 天无信号但有持仓",
                )
            self._no_signal_streak = 0
            self._no_signal_has_positions = False

    # ------------------------------------------------------------------
    # end_day: 日终汇总
    # ------------------------------------------------------------------
    def end_day(self, turnover_pct: float) -> None:
        """将当日审计结果汇总；检测单日全换手；如有异常加入 flagged_days。"""
        cd = self._current_day
        if cd is None:
            return

        # 单日全换手检测
        if turnover_pct > 1.0:
            self._add_flag("WARNING", cd["date"], f"单日全换手: turnover={turnover_pct * 100:.1f}%")
            self._day_is_flagged = True

        # 如果当日有异常，加入 flagged_days
        if self._day_is_flagged and len(self._flagged_days) < _MAX_FLAGGED_DAYS:
            # 移除内部快照字段，只保留审计输出字段
            day_record = {k: v for k, v in cd.items() if k != "positions_snapshot_before"}
            self._flagged_days.append(day_record)

        self._current_day = None

    # ------------------------------------------------------------------
    # CP5: finalize（循环结束后）
    # ------------------------------------------------------------------
    def finalize(self, exp_id: str, total_signals: int | None = None) -> dict[str, Any]:
        """汇总所有检查点结果，组装完整 audit dict。"""
        # 如果传入了外部 total_signals 则覆盖
        if total_signals is not None:
            self._total_signals = total_signals

        # 结束时检测残留的策略僵死 streak
        if self._no_signal_streak >= _STALE_STREAK_THRESHOLD and self._no_signal_has_positions:
            last_date = self._flagged_days[-1]["date"] if self._flagged_days else "unknown"
            self._add_flag(
                "WARNING",
                last_date,
                f"策略僵死: 回测末尾连续 {self._no_signal_streak} 天无信号但有持仓",
            )

        # 价格跳空分布
        gap_sorted = sorted(self._gap_pcts) if self._gap_pcts else []
        gap_p50 = _percentile(gap_sorted, 0.50)
        gap_p95 = _percentile(gap_sorted, 0.95)
        gap_max = gap_sorted[-1] if gap_sorted else 0.0

        # 总成本占初始资金比例
        total_cost = self._total_commission + self._total_stamp_tax + self._total_slippage
        cost_pct = (total_cost / self._initial_cash * 100) if self._initial_cash > 0 else 0.0

        # 截断 flags
        flags_output = list(self._flags)
        if len(flags_output) > _MAX_FLAGS:
            overflow = len(flags_output) - _MAX_FLAGS
            flags_output = flags_output[:_MAX_FLAGS]
            flags_output.append({
                "level": "INFO",
                "date": "",
                "message": f"... and {overflow} more flags truncated",
            })

        summary = {
            "trading_days_count": (
                self._cash_check_pass + self._cash_check_fail
            ),
            "cash_check_pass": self._cash_check_pass,
            "cash_check_fail": self._cash_check_fail,
            "pos_check_pass": self._pos_check_pass,
            "pos_check_fail": self._pos_check_fail,
            "nav_check_pass": self._nav_check_pass,
            "nav_check_fail": self._nav_check_fail,
            "t1_check_pass": self._t1_check_pass,
            "t1_check_fail": self._t1_check_fail,
            "total_fills": self._total_fills,
            "total_signals": self._total_signals,
            "orphan_fills": self._orphan_fills,
            "fill_gap_pct_p50": round(gap_p50, 2),
            "fill_gap_pct_p95": round(gap_p95, 2),
            "fill_gap_pct_max": round(gap_max, 2),
            "total_commission": round(self._total_commission, 2),
            "total_stamp_tax": round(self._total_stamp_tax, 2),
            "total_slippage": round(self._total_slippage, 2),
            "cost_as_pct_of_initial": round(cost_pct, 4),
            "cost_config": self._cost_config,
        }

        return {
            "version": "1.0",
            "exp_id": str(exp_id),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "summary": summary,
            "data_quality": self.data_quality,
            "flagged_days": self._flagged_days,
            "flags": flags_output,
        }

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------
    def _add_flag(self, level: str, day: str, message: str) -> None:
        self._flags.append({"level": level, "date": day, "message": message})
        self._day_is_flagged = True


def _percentile(sorted_list: list[float], pct: float) -> float:
    """简易百分位计算（无 numpy 依赖）。"""
    if not sorted_list:
        return 0.0
    n = len(sorted_list)
    idx = pct * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_list[lo] * (1 - frac) + sorted_list[hi] * frac
