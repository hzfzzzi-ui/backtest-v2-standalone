"""Signal-domain runtime config compilation helpers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from backend.api.backtest_v2.execution_overrides import (
    compile_multi_alpha_runtime_payload as _compile_multi_alpha_runtime_payload,
    to_int_or_default as _to_int_or_default,
)


def compile_signal_runtime(cfg: dict[str, Any], wb_cfg: dict[str, Any]) -> dict[str, Any]:
    sig = wb_cfg.get("signal_generation") if isinstance(wb_cfg.get("signal_generation"), dict) else {}
    multi_alpha_payload = _compile_multi_alpha_runtime_payload(wb_cfg)
    raw_strategy_pack = str(sig.get("strategy") or wb_cfg.get("strategy_pack") or "").strip().upper()
    strategy_pack = raw_strategy_pack or ("COMPOSITE" if multi_alpha_payload is not None else "SMA_CROSS")
    if strategy_pack == "ADAPTIVE_REGIME":
        raise HTTPException(status_code=400, detail="strategy_pack ADAPTIVE_REGIME has been removed; use REGIME_ROUTER")
    strategy_name_map = {
        "COMPOSITE": "composite",
        "SMA_CROSS": "sma_cross",
        "EMA_CROSS": "ema_cross",
        "REGIME_ROUTER": "regime_router",
        "BREAKOUT_TREND": "breakout_trend",
    }
    strategy_name = strategy_name_map.get(strategy_pack)
    pos_risk_cfg = wb_cfg.get("position_risk") if isinstance(wb_cfg.get("position_risk"), dict) else {}

    if strategy_name is None:
        if multi_alpha_payload is not None:
            strategy = cfg.setdefault("strategy", {})
            strategy["name"] = str(strategy.get("name") or "composite")
            strategy["params"] = {
                **dict(strategy.get("params") or {}),
                "multi_alpha": multi_alpha_payload,
                "portfolio_mode": str(pos_risk_cfg.get("portfolio_mode", "hard_sleeve_budget") or "hard_sleeve_budget"),
            }
        return {
            "signal_generation": sig,
            "multi_alpha_payload": multi_alpha_payload,
            "position_risk": pos_risk_cfg,
            "strategy_name": strategy_name,
            "strategy_pack": strategy_pack,
        }

    if strategy_name == "regime_router":
        _compile_regime_router_strategy(cfg, sig)
    elif strategy_name == "breakout_trend":
        _compile_breakout_strategy(cfg, sig, pos_risk_cfg)
    else:
        _compile_ma_cross_strategy(cfg, sig, strategy_name, strategy_pack)

    return {
        "signal_generation": sig,
        "multi_alpha_payload": multi_alpha_payload,
        "position_risk": pos_risk_cfg,
        "strategy_name": strategy_name,
        "strategy_pack": strategy_pack,
    }


def _compile_regime_router_strategy(cfg: dict[str, Any], sig: dict[str, Any]) -> None:
    rd = sig.get("regime_detection") if isinstance(sig.get("regime_detection"), dict) else {}
    trend_cfg = sig.get("trend") if isinstance(sig.get("trend"), dict) else {}
    mr_cfg = sig.get("mr") if isinstance(sig.get("mr"), dict) else {}

    trend_name = str(trend_cfg.get("strategy", "SMA_CROSS")).strip().lower()
    trend_name_map = {"sma_cross": "sma_cross", "ema_cross": "ema_cross"}
    resolved_trend = trend_name_map.get(trend_name, "sma_cross")

    order_size = _to_int_or_default(cfg.get("strategy", {}).get("order_size"), 1000)
    strategy = cfg.setdefault("strategy", {})
    strategy["name"] = "regime_router"
    strategy["fast"] = _to_int_or_default(trend_cfg.get("fast_ma"), 5)
    strategy["slow"] = _to_int_or_default(trend_cfg.get("slow_ma"), 20)
    strategy["order_size"] = order_size
    strategy["params"] = {
        "regime_ma": _to_int_or_default(rd.get("regime_ma"), 60),
        "trend_strategy": resolved_trend,
        "trend_params": {
            "fast": strategy["fast"],
            "slow": strategy["slow"],
            "order_size": order_size,
        },
        "mr_strategy": "rsi_reversal",
        "mr_params": {
            "rsi_period": _to_int_or_default(mr_cfg.get("rsi_period"), 6),
            "rsi_buy_threshold": float(mr_cfg.get("rsi_buy_threshold", 20.0)),
            "rsi_sell_threshold": float(mr_cfg.get("rsi_sell_threshold", 80.0)),
            "mr_max_hold_days": _to_int_or_default(mr_cfg.get("mr_max_hold_days"), 5),
            "mr_stop_loss_pct": float(mr_cfg.get("mr_stop_loss_pct", 0.03)),
            "order_size": order_size,
        },
        "order_size": order_size,
    }
    rf_raw = rd.get("regime_filter") if isinstance(rd.get("regime_filter"), dict) else {}
    if rf_raw.get("enabled"):
        strategy["params"]["regime_filter"] = {
            "enabled": True,
            "regime_threshold": float(rf_raw.get("regime_threshold", 0.3)),
            "alpha_m": float(rf_raw.get("alpha_m", 2.0)),
            "alpha_sec": float(rf_raw.get("alpha_sec", 2.0)),
            "alpha_i": float(rf_raw.get("alpha_i", 2.0)),
        }


def _compile_breakout_strategy(cfg: dict[str, Any], sig: dict[str, Any], pos_risk_cfg: dict[str, Any]) -> None:
    bo_cfg = sig.get("breakout") if isinstance(sig.get("breakout"), dict) else {}
    entry_filter = sig.get("entry_filter") if isinstance(sig.get("entry_filter"), dict) else {}
    strategy = cfg.setdefault("strategy", {})
    order_size = _to_int_or_default(strategy.get("order_size"), 1000)
    strategy["name"] = "breakout_trend"
    strategy["order_size"] = order_size
    strategy["params"] = {
        **dict(strategy.get("params") or {}),
        "breakout_window": _to_int_or_default(bo_cfg.get("breakout_window"), 20),
        "enable_dual_breakout": bool(bo_cfg.get("enable_dual_breakout", False)),
        "breakout_window_short": _to_int_or_default(bo_cfg.get("breakout_window_short"), 20),
        "breakout_window_long": _to_int_or_default(bo_cfg.get("breakout_window_long"), 55),
        "dual_breakout_mode": str(bo_cfg.get("dual_breakout_mode", "or") or "or"),
        "dual_breakout_gate_ma_window": _to_int_or_default(bo_cfg.get("dual_breakout_gate_ma_window"), 120),
        "dual_breakout_gate_slope_lookback": _to_int_or_default(bo_cfg.get("dual_breakout_gate_slope_lookback"), 10),
        "breakout_entry_buffer_pct": float(bo_cfg.get("breakout_entry_buffer_pct", 0.0)),
        "entry_confirm_mode": str(bo_cfg.get("entry_confirm_mode", "none")),
        "entry_delay_mode": str(bo_cfg.get("entry_delay_mode", "none")),
        "enable_entry_gap_guard": bool(bo_cfg.get("entry_gap_guard_enabled", False)),
        "entry_gap_guard_pct": float(bo_cfg.get("entry_gap_guard_pct", 0.04)),
        "enable_pullback_candidates": bool(bo_cfg.get("enable_pullback_candidates", False)),
        "pullback_variant_mode": str(bo_cfg.get("pullback_variant_mode", "pb_reclaim_ma20") or "pb_reclaim_ma20"),
        "pullback_touch_lookback": _to_int_or_default(bo_cfg.get("pullback_touch_lookback"), 12),
        "pullback_reclaim_window": _to_int_or_default(bo_cfg.get("pullback_reclaim_window"), 3),
        "pullback_ma20_touch_band_pct": float(bo_cfg.get("pullback_ma20_touch_band_pct", 0.01)),
        "pullback_low_lookback": _to_int_or_default(bo_cfg.get("pullback_low_lookback"), 10),
        "pullback_low_band_pct": float(bo_cfg.get("pullback_low_band_pct", 0.02)),
        "pullback_box_window": _to_int_or_default(bo_cfg.get("pullback_box_window"), 5),
        "pullback_box_range_pct_max": float(bo_cfg.get("pullback_box_range_pct_max", 0.08)),
        "enable_entry_above_slow_ma": bool(entry_filter.get("enable_entry_above_slow_ma", False)),
        "enable_entry_slow_ma_slope": bool(entry_filter.get("enable_entry_slow_ma_slope", False)),
        "entry_slope_lookback": int(entry_filter.get("entry_slope_lookback", 5)),
        "portfolio_mode": str(pos_risk_cfg.get("portfolio_mode", "equal_10")),
        "order_size": order_size,
        "enable_v2_trend_filter": True,
    }


def _compile_ma_cross_strategy(
    cfg: dict[str, Any],
    sig: dict[str, Any],
    strategy_name: str,
    strategy_pack: str,
) -> None:
    ma_key = "ema" if strategy_pack == "EMA_CROSS" else "sma"
    ma_cfg = sig.get(ma_key) if isinstance(sig.get(ma_key), dict) else {}

    strategy = cfg.setdefault("strategy", {})
    fast = _to_int_or_default(ma_cfg.get("fast_ma"), strategy.get("fast", 5))
    slow = _to_int_or_default(ma_cfg.get("slow_ma"), strategy.get("slow", 20))
    order_size = _to_int_or_default(strategy.get("order_size"), 1000)

    strategy["name"] = strategy_name
    strategy["fast"] = fast
    strategy["slow"] = slow
    strategy["order_size"] = order_size
    entry_filter = sig.get("entry_filter") if isinstance(sig.get("entry_filter"), dict) else {}
    strategy["params"] = {
        **dict(strategy.get("params") or {}),
        "fast": fast,
        "slow": slow,
        "order_size": order_size,
        "signal_class": "TREND",
        "trend_signal_family": "MA_CROSS",
        "ma_type": "EMA" if strategy_name == "ema_cross" else "SMA",
        "enable_entry_above_slow_ma": bool(entry_filter.get("enable_entry_above_slow_ma", False)),
        "enable_entry_slow_ma_slope": bool(entry_filter.get("enable_entry_slow_ma_slope", False)),
        "entry_slope_lookback": int(entry_filter.get("entry_slope_lookback", 5)),
    }
