from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import numpy as np

from backend.core.config.models import ExitConfig, StrategyConfig
from backend.core.engine_vector.breakout_provider_day_signals import evaluate_peak_giveback_ma20_exits
from backend.core.engine_vector.signal_provider import evaluate_engine_exits as _evaluate_engine_exits
from backend.core.strategies.registry import build_strategy


def evaluate_engine_exits(*args, **kwargs):
    exits, exit_syms, counts, _fragility_diag = _evaluate_engine_exits(*args, **kwargs)
    return exits, exit_syms, counts


def test_build_strategy_preserves_bear_only_risk_off_exit_mode() -> None:
    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "enable_risk_off_exit": True,
                "risk_off_exit_mode": "bear_only",
                "risk_off_exit_partial_pct": 0.5,
                "risk_off_exit_partial_mode": "trans_down_only",
                "risk_off_exit_partial_only_if_profitable": True,
            },
        )
    )

    assert getattr(strategy, "enable_risk_off_exit", False) is True
    assert getattr(strategy, "risk_off_exit_mode", "") == "bear_only"
    assert getattr(strategy, "risk_off_exit_partial_pct", 1.0) == 0.5
    assert getattr(strategy, "risk_off_exit_partial_mode", "") == "trans_down_only"
    assert getattr(strategy, "risk_off_exit_partial_only_if_profitable", False) is True


def test_build_strategy_preserves_pre_profit_breakout_failure_fields() -> None:
    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "enable_pre_profit_breakout_failure_exit": True,
                "pre_profit_breakout_failure_max_bars": 10,
                "pre_profit_breakout_failure_atr_buffer_k": 0.5,
            },
        )
    )

    assert getattr(strategy, "enable_pre_profit_breakout_failure_exit", False) is True
    assert getattr(strategy, "pre_profit_breakout_failure_max_bars", 0) == 10
    assert getattr(strategy, "pre_profit_breakout_failure_atr_buffer_k", 0.0) == 0.5


def test_build_strategy_preserves_profit_decay_exit_fields() -> None:
    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "enable_profit_decay_exit": True,
                "profit_decay_exit_profit_pct": 0.12,
                "profit_decay_exit_min_hold_bars": 8,
                "profit_decay_exit_residual_score_threshold": 0.35,
            },
        )
    )

    assert getattr(strategy, "enable_profit_decay_exit", False) is True
    assert getattr(strategy, "profit_decay_exit_profit_pct", 0.0) == 0.12
    assert getattr(strategy, "profit_decay_exit_min_hold_bars", 0) == 8
    assert getattr(strategy, "profit_decay_exit_residual_score_threshold", 0.0) == 0.35


def test_build_strategy_preserves_peak_giveback_ma20_exit_fields() -> None:
    default_strategy = build_strategy(StrategyConfig(name="breakout_trend", params={}))
    assert getattr(default_strategy, "enable_peak_giveback_ma20_exit", True) is False

    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "enable_peak_giveback_ma20_exit": True,
                "peak_giveback_ma20_min_peak_profit_pct": 0.22,
                "peak_giveback_ma20_min_giveback_pct": 0.28,
                "peak_giveback_ma20_min_hold_bars": 12,
                "peak_giveback_ma20_exit_pct": 0.5,
            },
        )
    )

    assert getattr(strategy, "enable_peak_giveback_ma20_exit", False) is True
    assert getattr(strategy, "peak_giveback_ma20_min_peak_profit_pct", 0.0) == 0.22
    assert getattr(strategy, "peak_giveback_ma20_min_giveback_pct", 0.0) == 0.28
    assert getattr(strategy, "peak_giveback_ma20_min_hold_bars", 0) == 12
    assert getattr(strategy, "peak_giveback_ma20_exit_pct", 0.0) == 0.5


def test_build_strategy_preserves_mfe_mae_confirmation_exit_fields() -> None:
    default_strategy = build_strategy(StrategyConfig(name="breakout_trend", params={}))
    assert getattr(default_strategy, "enable_mfe_mae_confirmation_exit", True) is False
    assert getattr(default_strategy, "enable_mfe_mae_restore_candidate", True) is False

    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "enable_mfe_mae_confirmation_exit": True,
                "mfe_mae_confirmation_lookahead_bars": 3,
                "mfe_mae_confirmation_min_mfe_pct": 0.02,
                "mfe_mae_confirmation_max_mae_pct": -0.05,
                "mfe_mae_confirmation_exit_pct": 0.5,
                "mfe_mae_confirmation_scope": "high_chase",
                "mfe_mae_confirmation_action": "watch_day10",
                "mfe_mae_high_chase_min_core_flags": 2,
                "mfe_mae_high_chase_ret5_pct": 0.20,
                "mfe_mae_watch_review_bars": 10,
                "enable_mfe_mae_restore_candidate": True,
                "mfe_mae_restore_candidate_scope": "high_chase",
                "mfe_mae_restore_candidate_max_bars": 40,
                "mfe_mae_restore_candidate_target_basis": "original_target",
                "mfe_mae_restore_candidate_clear_on_fill": True,
            },
        )
    )

    assert getattr(strategy, "enable_mfe_mae_confirmation_exit", False) is True
    assert getattr(strategy, "mfe_mae_confirmation_lookahead_bars", 0) == 3
    assert getattr(strategy, "mfe_mae_confirmation_min_mfe_pct", 0.0) == 0.02
    assert getattr(strategy, "mfe_mae_confirmation_max_mae_pct", 0.0) == -0.05
    assert getattr(strategy, "mfe_mae_confirmation_exit_pct", 0.0) == 0.5
    assert getattr(strategy, "mfe_mae_confirmation_scope", "") == "high_chase"
    assert getattr(strategy, "mfe_mae_confirmation_action", "") == "watch_day10"
    assert getattr(strategy, "mfe_mae_high_chase_min_core_flags", 0) == 2
    assert getattr(strategy, "mfe_mae_high_chase_ret5_pct", 0.0) == 0.20
    assert getattr(strategy, "mfe_mae_watch_review_bars", 0) == 10
    assert getattr(strategy, "enable_mfe_mae_restore_candidate", False) is True
    assert getattr(strategy, "mfe_mae_restore_candidate_scope", "") == "high_chase"
    assert getattr(strategy, "mfe_mae_restore_candidate_max_bars", 0) == 40
    assert getattr(strategy, "mfe_mae_restore_candidate_target_basis", "") == "original_target"
    assert getattr(strategy, "mfe_mae_restore_candidate_clear_on_fill", False) is True


def test_peak_giveback_ma20_exit_emits_partial_sell_after_profit_giveback() -> None:
    provider = SimpleNamespace(
        _enable_peak_giveback_ma20_exit=True,
        _peak_giveback_ma20_min_peak_profit_pct=0.20,
        _peak_giveback_ma20_min_giveback_pct=0.25,
        _peak_giveback_ma20_min_hold_bars=10,
        _peak_giveback_ma20_exit_pct=0.5,
        _sym_to_col={"sh600000": 0},
        _peak_close_state={"sh600000": 13.0},
        entry_bar_index={"sh600000": 0},
        _mx=SimpleNamespace(close=np.array([[9.5]] * 13, dtype=float)),
        _feats=SimpleNamespace(sma20=np.array([[10.0]] * 13, dtype=float)),
    )

    exit_syms: set[str] = set()
    exits = evaluate_peak_giveback_ma20_exits(
        provider,
        day=date(2026, 3, 2),
        day_idx=12,
        positions={"sh600000": 1000},
        position_avg_cost={"sh600000": 10.0},
        close_idx={(date(2026, 3, 2), "sh600000"): 9.5},
        exit_syms=exit_syms,
    )

    assert len(exits) == 1
    assert exits[0].reason_code == "PEAK_GIVEBACK_MA20_EXIT"
    assert exits[0].qty == 500
    assert exits[0].meta["partial_exit"] is True
    assert "sh600000" in exit_syms


def test_peak_giveback_ma20_exit_waits_for_ma20_break() -> None:
    provider = SimpleNamespace(
        _enable_peak_giveback_ma20_exit=True,
        _peak_giveback_ma20_min_peak_profit_pct=0.20,
        _peak_giveback_ma20_min_giveback_pct=0.25,
        _peak_giveback_ma20_min_hold_bars=10,
        _peak_giveback_ma20_exit_pct=0.5,
        _sym_to_col={"sh600000": 0},
        _peak_close_state={"sh600000": 13.0},
        entry_bar_index={"sh600000": 0},
        _mx=SimpleNamespace(close=np.array([[10.5]] * 13, dtype=float)),
        _feats=SimpleNamespace(sma20=np.array([[10.0]] * 13, dtype=float)),
    )

    exits = evaluate_peak_giveback_ma20_exits(
        provider,
        day=date(2026, 3, 2),
        day_idx=12,
        positions={"sh600000": 1000},
        position_avg_cost={"sh600000": 10.0},
        close_idx={(date(2026, 3, 2), "sh600000"): 9.5},
        exit_syms=set(),
    )

    assert exits == []


def test_build_strategy_preserves_entry_gap_guard_fields() -> None:
    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "enable_entry_gap_guard": True,
                "entry_gap_guard_pct": 0.04,
            },
        )
    )

    assert getattr(strategy, "enable_entry_gap_guard", False) is True
    assert getattr(strategy, "entry_gap_guard_pct", 0.0) == 0.04


def test_build_strategy_preserves_bad_breakout_quality_veto_fields() -> None:
    default_strategy = build_strategy(StrategyConfig(name="breakout_trend", params={}))
    assert getattr(default_strategy, "bad_breakout_quality_veto_enabled", True) is False

    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "bad_breakout_quality_veto_enabled": True,
                "bad_breakout_quality_ret5_rank_min": 0.75,
                "bad_breakout_quality_r2_60_rank_max": 0.25,
            },
        )
    )

    assert getattr(strategy, "bad_breakout_quality_veto_enabled", False) is True
    assert getattr(strategy, "bad_breakout_quality_ret5_rank_min", 0.0) == 0.75
    assert getattr(strategy, "bad_breakout_quality_r2_60_rank_max", 0.0) == 0.25


def test_build_strategy_preserves_trend_quality_soft_score_fields() -> None:
    default_strategy = build_strategy(StrategyConfig(name="breakout_trend", params={}))
    assert getattr(default_strategy, "trend_quality_soft_score_enabled", True) is False

    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "trend_quality_soft_score_enabled": True,
                "trend_quality_soft_score_weight": 0.4,
                "trend_quality_r2_60_weight": 0.5,
                "trend_quality_slope60_weight": 0.2,
                "trend_quality_ret60_vol_adj_weight": 0.2,
                "trend_quality_ret60_dd_adj_weight": 0.1,
            },
        )
    )

    assert getattr(strategy, "trend_quality_soft_score_enabled", False) is True
    assert getattr(strategy, "trend_quality_soft_score_weight", 0.0) == 0.4
    assert getattr(strategy, "trend_quality_r2_60_weight", 0.0) == 0.5
    assert getattr(strategy, "trend_quality_slope60_weight", 0.0) == 0.2
    assert getattr(strategy, "trend_quality_ret60_vol_adj_weight", 0.0) == 0.2
    assert getattr(strategy, "trend_quality_ret60_dd_adj_weight", 0.0) == 0.1


def test_build_strategy_preserves_risk_archetype_soft_deprioritize_fields() -> None:
    default_strategy = build_strategy(StrategyConfig(name="breakout_trend", params={}))
    assert getattr(default_strategy, "risk_archetype_soft_deprioritize_enabled", True) is False

    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "risk_archetype_soft_deprioritize_enabled": True,
                "risk_archetype_soft_deprioritize_quantile": 0.82,
                "risk_archetype_hot_crowded_penalty": 0.18,
                "risk_archetype_high_volatility_penalty": 0.12,
            },
        )
    )

    assert getattr(strategy, "risk_archetype_soft_deprioritize_enabled", False) is True
    assert getattr(strategy, "risk_archetype_soft_deprioritize_quantile", 0.0) == 0.82
    assert getattr(strategy, "risk_archetype_hot_crowded_penalty", 0.0) == 0.18
    assert getattr(strategy, "risk_archetype_high_volatility_penalty", 0.0) == 0.12


def test_build_strategy_preserves_entry_risk_position_sizing_fields() -> None:
    default_strategy = build_strategy(StrategyConfig(name="breakout_trend", params={}))
    assert getattr(default_strategy, "entry_risk_position_sizing_enabled", True) is False

    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "entry_risk_position_sizing_enabled": True,
                "entry_risk_position_watch_scale": 0.75,
                "entry_risk_position_high_scale": 0.45,
                "entry_risk_position_extreme_scale": 0.25,
            },
        )
    )

    assert getattr(strategy, "entry_risk_position_sizing_enabled", False) is True
    assert getattr(strategy, "entry_risk_position_watch_scale", 0.0) == 0.75
    assert getattr(strategy, "entry_risk_position_high_scale", 0.0) == 0.45
    assert getattr(strategy, "entry_risk_position_extreme_scale", 0.0) == 0.25


def test_evaluate_engine_exits_bear_only_waits_for_bear_state() -> None:
    common_kwargs = {
        "positions": {"sh600000": 100},
        "day": date(2026, 3, 2),
        "close_idx": {(date(2026, 3, 2), "sh600000"): 10.0},
        "position_avg_cost": {"sh600000": 9.0},
        "peak_state": {},
        "entry_day": {},
        "exit_cfg": ExitConfig(),
        "get_atr": lambda _sym, _day: None,
        "enable_risk_off_exit": True,
        "risk_off_exit_mode": "bear_only",
    }

    exits_trans_down, _, _ = evaluate_engine_exits(
        risk_on=False,
        market_state="TRANS_DOWN",
        **common_kwargs,
    )
    exits_bear, _, _ = evaluate_engine_exits(
        risk_on=False,
        market_state="BEAR",
        **common_kwargs,
    )

    assert exits_trans_down == []
    assert len(exits_bear) == 1
    assert exits_bear[0].reason_code == "RISK_OFF_EXIT"


def test_evaluate_engine_exits_trans_down_or_bear_triggers_in_transition() -> None:
    exits_trans_down, _, _ = evaluate_engine_exits(
        positions={"sh600000": 100},
        day=date(2026, 3, 2),
        close_idx={(date(2026, 3, 2), "sh600000"): 10.0},
        position_avg_cost={"sh600000": 9.0},
        peak_state={},
        entry_day={},
        exit_cfg=ExitConfig(),
        get_atr=lambda _sym, _day: None,
        risk_on=True,
        enable_risk_off_exit=True,
        risk_off_exit_mode="trans_down_or_bear",
        market_state="TRANS_DOWN",
    )

    assert len(exits_trans_down) == 1
    assert exits_trans_down[0].reason_code == "RISK_OFF_EXIT"


def test_evaluate_engine_exits_trans_down_freeze_bear_exit_waits_for_bear_state() -> None:
    common_kwargs = {
        "positions": {"sh600000": 100},
        "day": date(2026, 3, 2),
        "close_idx": {(date(2026, 3, 2), "sh600000"): 10.0},
        "position_avg_cost": {"sh600000": 9.0},
        "peak_state": {},
        "entry_day": {},
        "exit_cfg": ExitConfig(),
        "get_atr": lambda _sym, _day: None,
        "risk_on": True,
        "enable_risk_off_exit": True,
        "risk_off_exit_mode": "trans_down_freeze_bear_exit",
    }

    exits_trans_down, _, _ = evaluate_engine_exits(
        market_state="TRANS_DOWN",
        **common_kwargs,
    )
    exits_bear, _, _ = evaluate_engine_exits(
        market_state="BEAR",
        **common_kwargs,
    )

    assert exits_trans_down == []
    assert len(exits_bear) == 1
    assert exits_bear[0].reason_code == "RISK_OFF_EXIT"


def test_evaluate_engine_exits_trans_down_topk_bear_exit_waits_for_bear_state() -> None:
    common_kwargs = {
        "positions": {"sh600000": 100},
        "day": date(2026, 3, 2),
        "close_idx": {(date(2026, 3, 2), "sh600000"): 10.0},
        "position_avg_cost": {"sh600000": 9.0},
        "peak_state": {},
        "entry_day": {},
        "exit_cfg": ExitConfig(),
        "get_atr": lambda _sym, _day: None,
        "risk_on": True,
        "enable_risk_off_exit": True,
        "risk_off_exit_mode": "trans_down_topk_bear_exit",
    }

    exits_trans_down, _, _ = evaluate_engine_exits(
        market_state="TRANS_DOWN",
        **common_kwargs,
    )
    exits_bear, _, _ = evaluate_engine_exits(
        market_state="BEAR",
        **common_kwargs,
    )

    assert exits_trans_down == []
    assert len(exits_bear) == 1
    assert exits_bear[0].reason_code == "RISK_OFF_EXIT"


def test_evaluate_engine_exits_trans_down_residual_floor_bear_exit_waits_for_bear_state() -> None:
    common_kwargs = {
        "positions": {"sh600000": 100},
        "day": date(2026, 3, 2),
        "close_idx": {(date(2026, 3, 2), "sh600000"): 10.0},
        "position_avg_cost": {"sh600000": 9.0},
        "peak_state": {},
        "entry_day": {},
        "exit_cfg": ExitConfig(),
        "get_atr": lambda _sym, _day: None,
        "risk_on": True,
        "enable_risk_off_exit": True,
        "risk_off_exit_mode": "trans_down_residual_floor_bear_exit",
    }

    exits_trans_down, _, _ = evaluate_engine_exits(
        market_state="TRANS_DOWN",
        **common_kwargs,
    )
    exits_bear, _, _ = evaluate_engine_exits(
        market_state="BEAR",
        **common_kwargs,
    )

    assert exits_trans_down == []
    assert len(exits_bear) == 1
    assert exits_bear[0].reason_code == "RISK_OFF_EXIT"


def test_evaluate_engine_exits_trans_down_residual_profit_floor_bear_exit_waits_for_bear_state() -> None:
    common_kwargs = {
        "positions": {"sh600000": 100},
        "day": date(2026, 3, 2),
        "close_idx": {(date(2026, 3, 2), "sh600000"): 10.0},
        "position_avg_cost": {"sh600000": 9.0},
        "peak_state": {},
        "entry_day": {},
        "exit_cfg": ExitConfig(),
        "get_atr": lambda _sym, _day: None,
        "risk_on": True,
        "enable_risk_off_exit": True,
        "risk_off_exit_mode": "trans_down_residual_profit_floor_bear_exit",
    }

    exits_trans_down, _, _ = evaluate_engine_exits(
        market_state="TRANS_DOWN",
        **common_kwargs,
    )
    exits_bear, _, _ = evaluate_engine_exits(
        market_state="BEAR",
        **common_kwargs,
    )

    assert exits_trans_down == []
    assert len(exits_bear) == 1
    assert exits_bear[0].reason_code == "RISK_OFF_EXIT"


def test_evaluate_engine_exits_trans_down_residual_ma20_floor_bear_exit_waits_for_bear_state() -> None:
    common_kwargs = {
        "positions": {"sh600000": 100},
        "day": date(2026, 3, 2),
        "close_idx": {(date(2026, 3, 2), "sh600000"): 10.0},
        "position_avg_cost": {"sh600000": 9.0},
        "peak_state": {},
        "entry_day": {},
        "exit_cfg": ExitConfig(),
        "get_atr": lambda _sym, _day: None,
        "risk_on": True,
        "enable_risk_off_exit": True,
        "risk_off_exit_mode": "trans_down_residual_ma20_floor_bear_exit",
    }

    exits_trans_down, _, _ = evaluate_engine_exits(
        market_state="TRANS_DOWN",
        **common_kwargs,
    )
    exits_bear, _, _ = evaluate_engine_exits(
        market_state="BEAR",
        **common_kwargs,
    )

    assert exits_trans_down == []
    assert len(exits_bear) == 1
    assert exits_bear[0].reason_code == "RISK_OFF_EXIT"


def test_evaluate_engine_exits_pre_profit_breakout_failure_triggers_before_atr_stop() -> None:
    exits, _, _ = evaluate_engine_exits(
        positions={"sh600000": 100},
        day=date(2026, 3, 12),
        close_idx={(date(2026, 3, 12), "sh600000"): 9.85},
        position_avg_cost={"sh600000": 10.1},
        peak_state={},
        entry_day={"sh600000": date(2026, 3, 10)},
        entry_bar_index={"sh600000": 10},
        current_bar_index=12,
        entry_breakout_floor={"sh600000": 9.9},
        exit_cfg=ExitConfig(
            enable_pre_profit_breakout_failure_exit=True,
            pre_profit_breakout_failure_max_bars=5,
            trailing_activate_profit_pct=0.15,
            enable_atr_stop=True,
            atr_stop_k=3.0,
        ),
        get_atr=lambda _sym, _day: 1.0,
        risk_on=True,
        enable_risk_off_exit=False,
        risk_off_exit_mode="trans_down_or_bear",
        market_state="BULL",
    )

    assert len(exits) == 1
    assert exits[0].reason_code == "PRE_PROFIT_BREAKOUT_FAILURE_EXIT"
    assert exits[0].meta["entry_breakout_floor"] == 9.9
    assert exits[0].meta["bars_since_entry"] == 2


def test_evaluate_engine_exits_pre_profit_breakout_failure_skips_after_profit_activation() -> None:
    exits, _, _ = evaluate_engine_exits(
        positions={"sh600000": 100},
        day=date(2026, 3, 12),
        close_idx={(date(2026, 3, 12), "sh600000"): 11.8},
        position_avg_cost={"sh600000": 10.0},
        peak_state={},
        entry_day={"sh600000": date(2026, 3, 10)},
        entry_bar_index={"sh600000": 10},
        current_bar_index=12,
        entry_breakout_floor={"sh600000": 11.9},
        exit_cfg=ExitConfig(
            enable_pre_profit_breakout_failure_exit=True,
            pre_profit_breakout_failure_max_bars=5,
            trailing_activate_profit_pct=0.15,
        ),
        get_atr=lambda _sym, _day: None,
        risk_on=True,
        enable_risk_off_exit=False,
        risk_off_exit_mode="trans_down_or_bear",
        market_state="BULL",
    )

    assert exits == []


def test_evaluate_engine_exits_pre_profit_breakout_failure_respects_atr_buffer() -> None:
    exits, _, _ = evaluate_engine_exits(
        positions={"sh600000": 100},
        day=date(2026, 3, 12),
        close_idx={(date(2026, 3, 12), "sh600000"): 9.2},
        position_avg_cost={"sh600000": 10.0},
        peak_state={},
        entry_day={"sh600000": date(2026, 3, 10)},
        entry_bar_index={"sh600000": 10},
        current_bar_index=12,
        entry_breakout_floor={"sh600000": 10.0},
        exit_cfg=ExitConfig(
            enable_pre_profit_breakout_failure_exit=True,
            pre_profit_breakout_failure_max_bars=5,
            pre_profit_breakout_failure_atr_buffer_k=0.5,
            trailing_activate_profit_pct=0.15,
            enable_atr_stop=True,
            atr_stop_k=3.0,
        ),
        get_atr=lambda _sym, _day: 2.0,
        risk_on=True,
        enable_risk_off_exit=False,
        risk_off_exit_mode="trans_down_or_bear",
        market_state="BULL",
    )

    assert exits == []


def test_evaluate_engine_exits_partial_risk_off_exit_is_lot_aware() -> None:
    exits, _, _ = evaluate_engine_exits(
        positions={"sh600000": 1000},
        day=date(2026, 3, 2),
        close_idx={(date(2026, 3, 2), "sh600000"): 10.0},
        position_avg_cost={"sh600000": 9.0},
        peak_state={},
        entry_day={},
        exit_cfg=ExitConfig(),
        get_atr=lambda _sym, _day: None,
        risk_on=True,
        enable_risk_off_exit=True,
        risk_off_exit_mode="trans_down_or_bear",
        risk_off_exit_partial_pct=0.5,
        market_state="TRANS_DOWN",
    )

    assert len(exits) == 1
    assert exits[0].reason_code == "RISK_OFF_EXIT"
    assert exits[0].qty == 500
    assert exits[0].meta["partial_exit"] is True
    assert exits[0].meta["risk_off_exit_partial_pct"] == 0.5


def test_evaluate_engine_exits_trans_down_only_partial_keeps_bear_full_exit() -> None:
    common_kwargs = {
        "positions": {"sh600000": 1000},
        "day": date(2026, 3, 2),
        "close_idx": {(date(2026, 3, 2), "sh600000"): 10.0},
        "position_avg_cost": {"sh600000": 9.0},
        "peak_state": {},
        "entry_day": {},
        "exit_cfg": ExitConfig(),
        "get_atr": lambda _sym, _day: None,
        "risk_on": True,
        "enable_risk_off_exit": True,
        "risk_off_exit_mode": "trans_down_or_bear",
        "risk_off_exit_partial_pct": 0.5,
        "risk_off_exit_partial_mode": "trans_down_only",
    }

    exits_trans_down, _, _ = evaluate_engine_exits(
        market_state="TRANS_DOWN",
        **common_kwargs,
    )
    exits_bear, _, _ = evaluate_engine_exits(
        market_state="BEAR",
        **common_kwargs,
    )

    assert exits_trans_down[0].qty == 500
    assert exits_trans_down[0].meta["partial_exit"] is True
    assert exits_trans_down[0].meta["risk_off_exit_partial_mode"] == "trans_down_only"
    assert exits_bear[0].qty == 1000
    assert exits_bear[0].meta["partial_exit"] is False


def test_evaluate_engine_exits_first_trans_down_then_full_uses_stateful_partial() -> None:
    common_kwargs = {
        "positions": {"sh600000": 1000},
        "day": date(2026, 3, 2),
        "close_idx": {(date(2026, 3, 2), "sh600000"): 10.0},
        "position_avg_cost": {"sh600000": 9.0},
        "peak_state": {},
        "entry_day": {},
        "exit_cfg": ExitConfig(),
        "get_atr": lambda _sym, _day: None,
        "risk_on": True,
        "enable_risk_off_exit": True,
        "risk_off_exit_mode": "trans_down_or_bear",
        "risk_off_exit_partial_pct": 0.5,
        "risk_off_exit_partial_mode": "first_trans_down_then_full",
    }

    exits_first, _, _ = evaluate_engine_exits(
        market_state="TRANS_DOWN",
        risk_off_partial_state={},
        **common_kwargs,
    )
    exits_second, _, _ = evaluate_engine_exits(
        market_state="TRANS_DOWN",
        risk_off_partial_state={"sh600000": True},
        **common_kwargs,
    )
    exits_bear, _, _ = evaluate_engine_exits(
        market_state="BEAR",
        risk_off_partial_state={"sh600000": True},
        **common_kwargs,
    )

    assert exits_first[0].qty == 500
    assert exits_first[0].meta["partial_exit"] is True
    assert exits_first[0].meta["risk_off_partial_mark_on_fill"] is True
    assert exits_first[0].meta["risk_off_partial_state_seen"] is False
    assert exits_second[0].qty == 1000
    assert exits_second[0].meta["partial_exit"] is False
    assert exits_second[0].meta["risk_off_partial_state_seen"] is True
    assert exits_bear[0].qty == 1000
    assert exits_bear[0].meta["partial_exit"] is False


def test_evaluate_engine_exits_partial_profit_gate_blocks_losing_position() -> None:
    exits, _, _ = evaluate_engine_exits(
        positions={"sh600000": 1000},
        day=date(2026, 3, 2),
        close_idx={(date(2026, 3, 2), "sh600000"): 9.5},
        position_avg_cost={"sh600000": 10.0},
        peak_state={},
        entry_day={},
        exit_cfg=ExitConfig(),
        get_atr=lambda _sym, _day: None,
        risk_on=True,
        enable_risk_off_exit=True,
        risk_off_exit_mode="trans_down_or_bear",
        risk_off_exit_partial_pct=0.3,
        risk_off_exit_partial_mode="first_trans_down_then_full",
        risk_off_exit_partial_only_if_profitable=True,
        risk_off_partial_state={},
        market_state="TRANS_DOWN",
    )

    assert len(exits) == 1
    assert exits[0].qty == 1000
    assert exits[0].meta["partial_exit"] is False
    assert exits[0].meta["risk_off_exit_partial_only_if_profitable"] is True
    assert exits[0].meta["risk_off_partial_profit_gate_passed"] is False


def test_evaluate_engine_exits_partial_profit_gate_keeps_partial_for_winner() -> None:
    exits, _, _ = evaluate_engine_exits(
        positions={"sh600000": 1000},
        day=date(2026, 3, 2),
        close_idx={(date(2026, 3, 2), "sh600000"): 10.5},
        position_avg_cost={"sh600000": 10.0},
        peak_state={},
        entry_day={},
        exit_cfg=ExitConfig(),
        get_atr=lambda _sym, _day: None,
        risk_on=True,
        enable_risk_off_exit=True,
        risk_off_exit_mode="trans_down_or_bear",
        risk_off_exit_partial_pct=0.3,
        risk_off_exit_partial_mode="first_trans_down_then_full",
        risk_off_exit_partial_only_if_profitable=True,
        risk_off_partial_state={},
        market_state="TRANS_DOWN",
    )

    assert len(exits) == 1
    assert exits[0].qty == 300
    assert exits[0].meta["partial_exit"] is True
    assert exits[0].meta["risk_off_exit_partial_only_if_profitable"] is True
    assert exits[0].meta["risk_off_partial_profit_gate_passed"] is True


def test_evaluate_engine_exits_atr_trail_waits_until_profit_threshold_is_met() -> None:
    common_kwargs = {
        "positions": {"sh600000": 100},
        "day": date(2026, 3, 2),
        "close_idx": {(date(2026, 3, 2), "sh600000"): 10.7},
        "peak_state": {"sh600000": 12.0},
        "entry_day": {},
        "get_atr": lambda _sym, _day: 0.4,
        "risk_on": True,
        "enable_risk_off_exit": False,
        "market_state": "BULL",
    }

    exits_blocked, _, _ = evaluate_engine_exits(
        position_avg_cost={"sh600000": 10.0},
        exit_cfg=ExitConfig(enable_atr_trail=True, atr_trail_k=3.0, trailing_activate_profit_pct=0.08),
        **common_kwargs,
    )
    exits_allowed, _, _ = evaluate_engine_exits(
        position_avg_cost={"sh600000": 9.0},
        exit_cfg=ExitConfig(enable_atr_trail=True, atr_trail_k=3.0, trailing_activate_profit_pct=0.08),
        **common_kwargs,
    )

    assert exits_blocked == []
    assert len(exits_allowed) == 1
    assert exits_allowed[0].reason_code == "ATR_TRAIL_EXIT"
    assert exits_allowed[0].meta["trailing_activate_profit_pct"] == 0.08


def test_evaluate_engine_exits_segmented_ma20_exit_activates_at_mid_profit() -> None:
    exits, _, counts = evaluate_engine_exits(
        positions={"sh600000": 100},
        day=date(2026, 3, 2),
        close_idx={(date(2026, 3, 2), "sh600000"): 10.9},
        position_avg_cost={"sh600000": 10.0},
        peak_state={"sh600000": 11.5},
        entry_day={},
        exit_cfg=ExitConfig(
            enable_atr_stop=True,
            atr_stop_k=2.0,
            enable_atr_trail=True,
            atr_trail_k=3.0,
            trailing_activate_profit_pct=0.15,
            enable_ma20_exit=False,
            enable_low10_exit=True,
            segmented_trend_exit_mode="ma20",
            segmented_mid_profit_pct=0.08,
            segmented_high_profit_pct=0.15,
            segmented_high_trail_k=2.5,
        ),
        get_atr=lambda _sym, _day: 0.4,
        risk_on=True,
        enable_risk_off_exit=False,
        market_state="BULL",
        check_ma20_exit=lambda _sym: True,
        check_low10_exit=lambda _sym: True,
    )

    assert len(exits) == 1
    assert exits[0].reason_code == "TREND_EXIT_MA20"
    assert exits[0].meta["trend_exit_stage"] == "mid_profit"
    assert exits[0].meta["segmented_trend_exit_mode"] == "ma20"
    assert counts.ma20_exit == 1
    assert counts.low10_exit == 0


def test_evaluate_engine_exits_segmented_low10_exit_activates_at_mid_profit() -> None:
    exits, _, counts = evaluate_engine_exits(
        positions={"sh600000": 100},
        day=date(2026, 3, 2),
        close_idx={(date(2026, 3, 2), "sh600000"): 10.9},
        position_avg_cost={"sh600000": 10.0},
        peak_state={"sh600000": 11.5},
        entry_day={},
        exit_cfg=ExitConfig(
            enable_atr_stop=True,
            atr_stop_k=2.0,
            enable_atr_trail=True,
            atr_trail_k=3.0,
            trailing_activate_profit_pct=0.15,
            enable_ma20_exit=False,
            enable_low10_exit=True,
            segmented_trend_exit_mode="low10",
            segmented_mid_profit_pct=0.08,
            segmented_high_profit_pct=0.15,
            segmented_high_trail_k=2.5,
        ),
        get_atr=lambda _sym, _day: 0.4,
        risk_on=True,
        enable_risk_off_exit=False,
        market_state="BULL",
        check_ma20_exit=lambda _sym: True,
        check_low10_exit=lambda _sym: True,
    )

    assert len(exits) == 1
    assert exits[0].reason_code == "TREND_EXIT_LOW10"
    assert exits[0].meta["trend_exit_stage"] == "mid_profit"
    assert exits[0].meta["segmented_trend_exit_mode"] == "low10"
    assert counts.ma20_exit == 0
    assert counts.low10_exit == 1


def test_evaluate_engine_exits_segmented_high_profit_uses_tighter_trailing() -> None:
    exits, _, counts = evaluate_engine_exits(
        positions={"sh600000": 100},
        day=date(2026, 3, 2),
        close_idx={(date(2026, 3, 2), "sh600000"): 10.6},
        position_avg_cost={"sh600000": 9.0},
        peak_state={"sh600000": 11.8},
        entry_day={},
        exit_cfg=ExitConfig(
            enable_atr_trail=True,
            atr_trail_k=3.0,
            trailing_activate_profit_pct=0.15,
            segmented_trend_exit_mode="ma20",
            segmented_mid_profit_pct=0.08,
            segmented_high_profit_pct=0.15,
            segmented_high_trail_k=2.5,
        ),
        get_atr=lambda _sym, _day: 0.4,
        risk_on=True,
        enable_risk_off_exit=False,
        market_state="BULL",
        check_ma20_exit=lambda _sym: False,
        check_low10_exit=lambda _sym: False,
    )

    assert len(exits) == 1
    assert exits[0].reason_code == "ATR_TRAIL_EXIT"
    assert exits[0].meta["trend_exit_stage"] == "high_profit"
    assert exits[0].meta["effective_atr_trail_k"] == 2.5
    assert counts.atr_trail == 1


def test_evaluate_engine_exits_segmented_chandelier_activates_trailing_at_mid_profit() -> None:
    exits, _, counts = evaluate_engine_exits(
        positions={"sh600000": 100},
        day=date(2026, 3, 2),
        close_idx={(date(2026, 3, 2), "sh600000"): 10.7},
        position_avg_cost={"sh600000": 9.0},
        peak_state={"sh600000": 12.0},
        entry_day={},
        exit_cfg=ExitConfig(
            enable_atr_trail=True,
            atr_trail_k=3.0,
            segmented_trend_exit_mode="chandelier",
            segmented_mid_profit_pct=0.15,
            segmented_high_profit_pct=0.25,
            segmented_high_trail_k=2.0,
        ),
        get_atr=lambda _sym, _day: 0.4,
        risk_on=True,
        enable_risk_off_exit=False,
        market_state="BULL",
    )

    assert len(exits) == 1
    assert exits[0].reason_code == "ATR_TRAIL_EXIT"
    assert exits[0].meta["segmented_trend_exit_mode"] == "chandelier"
    assert exits[0].meta["trend_exit_stage"] == "mid_profit"
    assert exits[0].meta["effective_atr_trail_k"] == 3.0
    assert exits[0].meta["trailing_activate_profit_pct"] == 0.15
    assert counts.atr_trail == 1


def test_evaluate_engine_exits_segmented_chandelier_uses_tighter_trailing_at_high_profit() -> None:
    exits, _, counts = evaluate_engine_exits(
        positions={"sh600000": 100},
        day=date(2026, 3, 2),
        close_idx={(date(2026, 3, 2), "sh600000"): 10.6},
        position_avg_cost={"sh600000": 8.0},
        peak_state={"sh600000": 11.8},
        entry_day={},
        exit_cfg=ExitConfig(
            enable_atr_trail=True,
            atr_trail_k=3.0,
            segmented_trend_exit_mode="chandelier",
            segmented_mid_profit_pct=0.15,
            segmented_high_profit_pct=0.25,
            segmented_high_trail_k=2.0,
        ),
        get_atr=lambda _sym, _day: 0.4,
        risk_on=True,
        enable_risk_off_exit=False,
        market_state="BULL",
    )

    assert len(exits) == 1
    assert exits[0].reason_code == "ATR_TRAIL_EXIT"
    assert exits[0].meta["segmented_trend_exit_mode"] == "chandelier"
    assert exits[0].meta["trend_exit_stage"] == "high_profit"
    assert exits[0].meta["effective_atr_trail_k"] == 2.0
    assert exits[0].meta["trailing_activate_profit_pct"] == 0.25
    assert counts.atr_trail == 1
