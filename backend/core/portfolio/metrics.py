from __future__ import annotations

from math import sqrt
from typing import Any

import pandas as pd


def compute_backtest_metrics(
    daily_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    *,
    max_positions: int,
    blocked_by_trend_count: int = 0,
    total_buy_signals: int = 0,
    candidates_df: pd.DataFrame | None = None,
    enable_strength_rank: bool = False,
    strength_ma: int = 120,
) -> dict[str, Any]:
    if daily_df.empty:
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "vol_annual": 0.0,
            "max_daily_drawdown": 0.0,
            "trades": 0,
            "avg_positions": 0.0,
            "turnover_avg": 0.0,
            "max_positions": int(max_positions),
            "blocked_by_trend_count": int(blocked_by_trend_count),
            "trend_filter_block_rate": 0.0,
            "not_in_topk_reject_count": 0,
            "avg_candidates_per_day": 0.0,
            "avg_selected_per_day": 0.0,
            "avg_buys_per_day": 0.0,
            "avg_buy_slots_per_day": 0.0,
            "trigger_when_slots_small_rate": 0.0,
            "mean_order_value_scale": 0.0,
            "weak_trend_buy_rate": 0.0,
            "strong_trend_buy_rate": 0.0,
            "trend_break_exit_rate": 0.0,
            "trend_break_exit_count": 0,
            "mean_break_streak_at_exit": 0.0,
            "days_held_median": 0.0,
            "rank_trigger_days": 0,
            "rank_trigger_rate": 0.0,
            "mf_rank_trigger_days": 0,
            "mf_rank_trigger_rate": 0.0,
            "mf_rank_applied_days": 0,
            "mf_rank_applied_rate": 0.0,
            "mf_avg_candidates_when_triggered": 0.0,
            "mf_topk_reject_count": 0,
            "mf_concentrated_buy_rate": 0.0,
            "mf_gate_on_days": 0,
            "mf_gate_on_rate": 0.0,
            "strong_risk_on_days": 0,
            "strong_risk_on_rate": 0.0,
            "mf_rank_suppressed_by_strong_gate_days": 0,
            "trend_slope_block_count": 0,
            "trend_continuity_block_count": 0,
            "avg_trend_on_rate": 0.0,
            "avg_quality_trend_on_rate": 0.0,
            "strength_rank_enabled": bool(enable_strength_rank),
            "strength_ma": int(strength_ma),
        }
    nav0 = float(daily_df["nav"].iloc[0])
    nav1 = float(daily_df["nav"].iloc[-1])
    total_return = (nav1 / nav0 - 1.0) if nav0 > 0 else 0.0
    n = int(len(daily_df))
    years = max(n / 252.0, 1e-9)
    cagr = (nav1 / nav0) ** (1.0 / years) - 1.0 if nav0 > 0 and nav1 > 0 else 0.0
    max_drawdown = float(daily_df["drawdown"].min())
    daily_ret = pd.to_numeric(daily_df["daily_return"], errors="coerce").fillna(0.0)
    vol_annual = float(daily_ret.std(ddof=0) * sqrt(252.0))
    sharpe = float((daily_ret.mean() / daily_ret.std(ddof=0)) * sqrt(252.0)) if float(daily_ret.std(ddof=0)) > 0 else 0.0
    calmar = float(cagr / abs(max_drawdown)) if max_drawdown != 0 else 0.0
    max_daily_drawdown = float(daily_ret.min())
    avg_positions = float(pd.to_numeric(daily_df["positions_count"], errors="coerce").fillna(0.0).mean())
    turnover_avg = float(pd.to_numeric(daily_df["turnover_pct"], errors="coerce").fillna(0.0).mean())
    not_in_topk_reject_count = 0
    rank_trigger_days = 0
    if candidates_df is not None and not candidates_df.empty and "reject_reason" in candidates_df.columns:
        rr = candidates_df["reject_reason"].astype(str)
        not_in_topk_reject_count = int(rr.eq("NOT_IN_TOPK").sum())
    if "candidates_count" in daily_df.columns and "buy_slots_before_buy" in daily_df.columns:
        cc = pd.to_numeric(daily_df["candidates_count"], errors="coerce").fillna(0.0)
        bs = pd.to_numeric(daily_df["buy_slots_before_buy"], errors="coerce").fillna(0.0)
        rank_trigger_days = int((cc > bs).sum())
    def _num_series_any(*names: str) -> pd.Series:
        for name in names:
            if name in daily_df.columns:
                return pd.to_numeric(daily_df[name], errors="coerce").fillna(0.0)
        return pd.Series(0.0, index=daily_df.index, dtype=float)

    mtr = _num_series_any("final_score_rank_triggered", "mf_rank_triggered")
    mfc = _num_series_any("final_score_candidates_when_triggered", "mf_candidates_when_triggered")
    mra = _num_series_any("final_score_rank_applied", "mf_rank_applied")
    mtk = _num_series_any("final_score_topk_reject_count", "mf_topk_reject_count")
    mfc_sel = _num_series_any("final_score_concentrated_selected_count", "mf_concentrated_selected_count")
    mg = _num_series_any("final_score_rank_gate_on", "mf_gate_on")
    mf_rank_trigger_days = int((mtr > 0).sum())
    mf_avg_candidates_when_triggered = 0.0
    picked = mfc[mtr > 0]
    if len(picked) > 0:
        mf_avg_candidates_when_triggered = float(picked.mean())
    mf_rank_applied_days = int((mra > 0).sum())
    mf_rank_applied_rate = float((mra > 0).mean()) if len(mra) > 0 else 0.0
    mf_topk_reject_count = int(mtk.sum())
    msel = float(pd.to_numeric(daily_df["selected_count"], errors="coerce").fillna(0.0).sum()) if "selected_count" in daily_df.columns else 0.0
    mf_concentrated_buy_rate = (float(mfc_sel.sum()) / msel) if msel > 0 else 0.0
    mf_gate_on_days = int((mg > 0).sum())
    mf_gate_on_rate = float((mg > 0).mean()) if len(mg) > 0 else 0.0
    strong_risk_on_days = 0
    strong_risk_on_rate = 0.0
    if "strong_risk_on" in daily_df.columns:
        sro = pd.to_numeric(daily_df["strong_risk_on"], errors="coerce").fillna(0.0)
        strong_risk_on_days = int((sro > 0).sum())
        strong_risk_on_rate = float((sro > 0).mean()) if len(sro) > 0 else 0.0
    mssg = _num_series_any("final_score_rank_suppressed_by_strong_gate", "mf_rank_suppressed_by_strong_gate")
    mf_rank_suppressed_by_strong_gate_days = int((mssg > 0).sum())
    trend_slope_block_count = int(pd.to_numeric(daily_df.get("trend_slope_block_count"), errors="coerce").fillna(0.0).sum()) if "trend_slope_block_count" in daily_df.columns else 0
    trend_continuity_block_count = int(pd.to_numeric(daily_df.get("trend_continuity_block_count"), errors="coerce").fillna(0.0).sum()) if "trend_continuity_block_count" in daily_df.columns else 0
    avg_trend_on_rate = float(pd.to_numeric(daily_df.get("base_trend_on_rate"), errors="coerce").fillna(0.0).mean()) if "base_trend_on_rate" in daily_df.columns else 0.0
    avg_quality_trend_on_rate = float(pd.to_numeric(daily_df.get("quality_trend_on_rate"), errors="coerce").fillna(0.0).mean()) if "quality_trend_on_rate" in daily_df.columns else 0.0
    avg_candidates_per_day = float(pd.to_numeric(daily_df.get("candidates_count"), errors="coerce").fillna(0.0).mean()) if "candidates_count" in daily_df.columns else 0.0
    avg_selected_per_day = float(pd.to_numeric(daily_df.get("selected_count"), errors="coerce").fillna(0.0).mean()) if "selected_count" in daily_df.columns else 0.0
    avg_buys_per_day = float(avg_selected_per_day)
    buy_slots_series = pd.to_numeric(daily_df.get("buy_slots_before_buy"), errors="coerce").fillna(0.0) if "buy_slots_before_buy" in daily_df.columns else pd.Series([0.0] * len(daily_df))
    avg_buy_slots_per_day = float(buy_slots_series.mean()) if len(buy_slots_series) > 0 else 0.0
    trigger_when_slots_small_rate = float((buy_slots_series <= 1).mean()) if len(buy_slots_series) > 0 else 0.0
    mean_order_value_scale = float(pd.to_numeric(daily_df.get("mean_order_value_scale"), errors="coerce").fillna(0.0).mean()) if "mean_order_value_scale" in daily_df.columns else 0.0
    weak_trend_buy_rate = float(pd.to_numeric(daily_df.get("weak_trend_buy_rate"), errors="coerce").fillna(0.0).mean()) if "weak_trend_buy_rate" in daily_df.columns else 0.0
    strong_trend_buy_rate = float(pd.to_numeric(daily_df.get("strong_trend_buy_rate"), errors="coerce").fillna(0.0).mean()) if "strong_trend_buy_rate" in daily_df.columns else 0.0
    trend_break_exit_rate = 0.0
    trend_break_exit_count = 0
    mean_break_streak_at_exit = 0.0
    days_held_median = 0.0
    if not trades_df.empty and "side" in trades_df.columns and "reason_code" in trades_df.columns:
        sell_part = trades_df[trades_df["side"].astype(str).str.upper() == "SELL"].copy()
        if not sell_part.empty:
            rc = sell_part["reason_code"].astype(str).str.upper()
            trend_break_exit_count = int((rc == "TREND_BREAK_EXIT").sum())
            trend_break_exit_rate = float(trend_break_exit_count / len(sell_part))
            if "break_streak" in sell_part.columns:
                bsv = pd.to_numeric(sell_part.loc[rc == "TREND_BREAK_EXIT", "break_streak"], errors="coerce").dropna()
                if len(bsv) > 0:
                    mean_break_streak_at_exit = float(bsv.mean())
            if "hold_days" in sell_part.columns:
                hd = pd.to_numeric(sell_part["hold_days"], errors="coerce").dropna()
                if len(hd) > 0:
                    days_held_median = float(hd.median())
    trading_days = int(len(daily_df))
    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "calmar": calmar,
        "vol_annual": vol_annual,
        "max_daily_drawdown": max_daily_drawdown,
        "trades": int(len(trades_df)),
        "avg_positions": avg_positions,
        "turnover_avg": turnover_avg,
        "max_positions": int(max_positions),
        "blocked_by_trend_count": int(blocked_by_trend_count),
        "trend_filter_block_rate": (float(blocked_by_trend_count) / float(total_buy_signals)) if total_buy_signals > 0 else 0.0,
        "not_in_topk_reject_count": int(not_in_topk_reject_count),
        "avg_candidates_per_day": float(avg_candidates_per_day),
        "avg_selected_per_day": float(avg_selected_per_day),
        "avg_buys_per_day": float(avg_buys_per_day),
        "avg_buy_slots_per_day": float(avg_buy_slots_per_day),
        "trigger_when_slots_small_rate": float(trigger_when_slots_small_rate),
        "mean_order_value_scale": float(mean_order_value_scale),
        "WEAK_TREND_BUY_RATE": float(weak_trend_buy_rate),
        "STRONG_TREND_BUY_RATE": float(strong_trend_buy_rate),
        "TREND_BREAK_EXIT_RATE": float(trend_break_exit_rate),
        "TREND_BREAK_EXIT_COUNT": int(trend_break_exit_count),
        "mean_break_streak_at_exit": float(mean_break_streak_at_exit),
        "days_held_median": float(days_held_median),
        "rank_trigger_days": int(rank_trigger_days),
        "rank_trigger_rate": (float(rank_trigger_days) / float(trading_days)) if trading_days > 0 else 0.0,
        "final_score_rank_trigger_days": int(mf_rank_trigger_days),
        "final_score_rank_trigger_rate": (float(mf_rank_trigger_days) / float(trading_days)) if trading_days > 0 else 0.0,
        "final_score_rank_applied_days": int(mf_rank_applied_days),
        "final_score_rank_applied_rate": float(mf_rank_applied_rate),
        "final_score_avg_candidates_when_triggered": float(mf_avg_candidates_when_triggered),
        "final_score_topk_reject_count": int(mf_topk_reject_count),
        "final_score_concentrated_buy_rate": float(mf_concentrated_buy_rate),
        "final_score_rank_gate_on_days": int(mf_gate_on_days),
        "final_score_rank_gate_on_rate": float(mf_gate_on_rate),
        "final_score_rank_suppressed_by_strong_gate_days": int(mf_rank_suppressed_by_strong_gate_days),
        "mf_rank_trigger_days": int(mf_rank_trigger_days),
        "mf_rank_trigger_rate": (float(mf_rank_trigger_days) / float(trading_days)) if trading_days > 0 else 0.0,
        "mf_rank_applied_days": int(mf_rank_applied_days),
        "mf_rank_applied_rate": float(mf_rank_applied_rate),
        "mf_avg_candidates_when_triggered": float(mf_avg_candidates_when_triggered),
        "mf_topk_reject_count": int(mf_topk_reject_count),
        "mf_concentrated_buy_rate": float(mf_concentrated_buy_rate),
        "mf_gate_on_days": int(mf_gate_on_days),
        "mf_gate_on_rate": float(mf_gate_on_rate),
        "strong_risk_on_days": int(strong_risk_on_days),
        "strong_risk_on_rate": float(strong_risk_on_rate),
        "mf_rank_suppressed_by_strong_gate_days": int(mf_rank_suppressed_by_strong_gate_days),
        "trend_slope_block_count": int(trend_slope_block_count),
        "trend_continuity_block_count": int(trend_continuity_block_count),
        "avg_trend_on_rate": float(avg_trend_on_rate),
        "avg_quality_trend_on_rate": float(avg_quality_trend_on_rate),
        "trend_filter_block_rate": (
            (float(int(blocked_by_trend_count) + trend_slope_block_count + trend_continuity_block_count) / float(total_buy_signals))
            if total_buy_signals > 0
            else 0.0
        ),
        "strength_rank_enabled": bool(enable_strength_rank),
        "strength_ma": int(strength_ma),
        "total_buy_signals": int(total_buy_signals),
        "blocked_signals": int(blocked_by_trend_count),
    }
