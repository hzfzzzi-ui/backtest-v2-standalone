from __future__ import annotations

from fastapi import HTTPException

from backend.api.backtest_v2.semantic_config_compiler import (
    SEMANTIC_CONFIG_SCHEMA_VERSION,
    compile_semantic_config_json,
    validate_semantic_config_json,
)


def _valid_config() -> dict:
    return {
        "mode": "experiment",
        "initial_capital": 1000000,
        "strategy_pack": "BREAKOUT_TREND",
        "universe_mode": "HS300_ZZ500",
        "industries": [],
        "universe": {
            "start": "2016-03-01",
            "end": "2026-03-01",
            "benchmark": "000300.SH",
            "symbols": [],
            "limit": 0,
            "price_adj": "hfq",
            "filters": {
                "exclude_st": True,
                "exclude_suspended": True,
                "min_list_days": 120,
                "min_avg_turnover_20d": 100000000,
                "price_min": 5,
                "price_max": 99999,
                "atr_pct_range": "0,100",
                "limit_rule": "ignore",
            },
        },
        "signal_generation": {
            "enabled": True,
            "strategy": "BREAKOUT_TREND",
            "breakout": {
                "breakout_window": 55,
                "enable_dual_breakout": False,
            },
        },
        "exit_rules": {
            "enabled": True,
            "atr_stop": {"enabled": True, "k": 1.2},
            "trailing": {"enabled": True, "k": 3.0},
            "time_exit": {"enabled": False, "n_days": 20},
        },
        "position_risk": {
            "enabled": True,
            "max_positions": 10,
            "single_stock_cap": 0.1,
            "industry_cap": 0.3,
            "lot": 100,
            "cash_shortage_policy": "skip",
        },
    }


def _valid_multi_alpha_config() -> dict:
    return {
        "mode": "experiment",
        "initial_capital": 1000000,
        "universe_mode": "HS300_ZZ500",
        "industries": [],
        "universe": {
            "start": "2016-03-01",
            "end": "2026-03-01",
            "benchmark": "000300.SH",
            "symbols": [],
            "limit": 0,
            "price_adj": "hfq",
            "filters": {
                "exclude_st": True,
                "exclude_suspended": True,
                "min_list_days": 120,
                "min_avg_turnover_20d": 100000000,
                "price_min": 5,
                "price_max": 99999,
                "atr_pct_range": "0,100",
                "limit_rule": "ignore",
            },
        },
        "signal_generation": {
            "enabled": True,
            "modules": [
                {"name": "breakout_55", "alpha_id": "breakout_55", "family": "trend"},
                {"name": "rsi_reversal", "alpha_id": "rsi_rev_6_20_80", "family": "mean_revert"},
            ],
        },
        "signal_composition": {
            "enabled": True,
            "compose_mode": "REGIME_ROUTE",
            "same_symbol_policy": "PREFER_HIGHER_SCORE",
            "holding_ownership": "SOURCE_ONLY",
            "modules": [
                {"name": "breakout_55", "role": "trend", "priority": 100},
                {"name": "rsi_reversal", "role": "mean_revert", "priority": 80},
            ],
            "regime_matrix": {
                "TREND_UP": ["breakout_55"],
                "RANGE": ["breakout_55", "rsi_reversal"],
            },
        },
        "position_risk": {
            "enabled": True,
            "max_positions": 10,
            "single_stock_cap": 0.1,
            "industry_cap": 0.3,
            "lot": 100,
            "cash_shortage_policy": "skip",
        },
    }


def test_validate_semantic_config_json_accepts_known_fields() -> None:
    out = validate_semantic_config_json(_valid_config())
    assert out["strategy_pack"] == "BREAKOUT_TREND"
    assert out["universe"]["filters"]["price_min"] == 5.0


def test_validate_semantic_config_json_accepts_turnover_rate_filter_fields() -> None:
    payload = _valid_config()
    payload["universe"]["filters"]["min_avg_turnover_rate_20d"] = 1.25
    payload["universe"]["filters"]["turnover_rate_field"] = "turnover_rate_f"

    out = validate_semantic_config_json(payload)

    assert out["universe"]["filters"]["min_avg_turnover_rate_20d"] == 1.25
    assert out["universe"]["filters"]["turnover_rate_field"] == "turnover_rate_f"


def test_validate_semantic_config_json_accepts_membership_mode() -> None:
    payload = _valid_config()
    payload["universe"]["membership_mode"] = "PIT_DYNAMIC"
    out = validate_semantic_config_json(payload)
    assert out["universe"]["membership_mode"] == "PIT_DYNAMIC"


def test_validate_semantic_config_json_accepts_sizing_fields() -> None:
    payload = _valid_config()
    payload["universe"]["membership_mode"] = "PIT_DYNAMIC"
    payload["sizing"] = {
        "weight_mode": "mf_rank_tilt",
        "min_positions": 10,
        "tilt_strength": 0.15,
        "tilt_top_n": 3,
        "tilt_bottom_n": 2,
    }
    out = validate_semantic_config_json(payload)
    assert out["universe"]["membership_mode"] == "PIT_DYNAMIC"
    assert out["sizing"]["weight_mode"] == "mf_rank_tilt"
    assert out["sizing"]["min_positions"] == 10
    assert out["sizing"]["tilt_strength"] == 0.15
    assert out["sizing"]["tilt_top_n"] == 3
    assert out["sizing"]["tilt_bottom_n"] == 2


def test_validate_semantic_config_json_accepts_score_weighted_sizing_fields() -> None:
    payload = _valid_config()
    payload["universe"]["membership_mode"] = "PIT_DYNAMIC"
    payload["sizing"] = {
        "weight_mode": "score_weighted",
        "min_positions": 10,
        "score_weight_min_scale": 0.75,
        "score_weight_max_scale": 1.25,
    }
    out = validate_semantic_config_json(payload)
    assert out["sizing"]["weight_mode"] == "score_weighted"
    assert out["sizing"]["min_positions"] == 10
    assert out["sizing"]["score_weight_min_scale"] == 0.75
    assert out["sizing"]["score_weight_max_scale"] == 1.25


def test_validate_semantic_config_json_accepts_cash_aware_candidate_planner_fields() -> None:
    payload = _valid_config()
    payload["universe"]["membership_mode"] = "PIT_DYNAMIC"
    payload["sizing"] = {
        "candidate_plan_mode": "cash_aware",
        "cash_aware_search_top_n": 12,
    }
    out = validate_semantic_config_json(payload)
    assert out["sizing"]["candidate_plan_mode"] == "cash_aware"
    assert out["sizing"]["cash_aware_search_top_n"] == 12


def test_validate_semantic_config_json_accepts_segmented_market_filter_fields() -> None:
    payload = _valid_config()
    payload["position_risk"]["market_filter"] = {
        "enabled": True,
        "bull_multiplier": 1.5,
        "light_multiplier": 0.6,
        "trans_down_multiplier": 0.3,
        "trans_up_multiplier": 0.8,
        "bear_multiplier": 0.0,
        "ema_light_fast": 5,
        "ema_light_slow": 20,
    }
    out = validate_semantic_config_json(payload)
    market_filter = out["position_risk"]["market_filter"]
    assert market_filter["trans_down_multiplier"] == 0.3
    assert market_filter["trans_up_multiplier"] == 0.8
    assert market_filter["bear_multiplier"] == 0.0


def test_validate_semantic_config_json_accepts_breadth_fields() -> None:
    payload = _valid_config()
    payload["position_risk"]["breadth"] = {
        "enabled": True,
        "mode": "dynamic_maxpos",
        "score_type": "combo",
        "mapping_mode": "smooth",
        "min_positions": 6,
        "max_positions": 10,
        "gate_threshold": 0.45,
        "gate_quantile_window": 252,
        "gate_quantile_pct": 0.2,
    }
    out = validate_semantic_config_json(payload)
    breadth = out["position_risk"]["breadth"]
    assert breadth["enabled"] is True
    assert breadth["mode"] == "dynamic_maxpos"
    assert breadth["score_type"] == "combo"
    assert breadth["mapping_mode"] == "smooth"
    assert breadth["min_positions"] == 6
    assert breadth["max_positions"] == 10
    assert breadth["gate_threshold"] == 0.45


def test_validate_semantic_config_json_accepts_source_aware_residual_mode() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "source_aware_residual_mode": "PULLBACK_ONLY",
    }
    out = validate_semantic_config_json(payload)
    assert out["signal_generation"]["ranking"]["score_source_mode"] == "residual_only"
    assert out["signal_generation"]["ranking"]["source_aware_residual_mode"] == "PULLBACK_ONLY"


def test_validate_semantic_config_json_accepts_quality_then_residual_fields() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "QUALITY_THEN_RESIDUAL",
        "residual_window": 40,
        "breakout_quality_gate_min_score": 0.55,
        "breakout_quality_margin_cap_pct": 0.08,
        "breakout_quality_fade_cap_pct": 0.035,
        "breakout_quality_open_gap_cap_pct": 0.04,
    }

    out = validate_semantic_config_json(payload)

    ranking = out["signal_generation"]["ranking"]
    assert ranking["score_source_mode"] == "QUALITY_THEN_RESIDUAL"
    assert ranking["breakout_quality_gate_min_score"] == 0.55
    assert ranking["breakout_quality_margin_cap_pct"] == 0.08
    assert ranking["breakout_quality_fade_cap_pct"] == 0.035
    assert ranking["breakout_quality_open_gap_cap_pct"] == 0.04


def test_validate_semantic_config_json_accepts_leadership_then_residual_fields() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "LEADERSHIP_THEN_RESIDUAL",
        "residual_window": 40,
        "leadership_route_bucket_count": 3,
    }

    out = validate_semantic_config_json(payload)

    ranking = out["signal_generation"]["ranking"]
    assert ranking["score_source_mode"] == "LEADERSHIP_THEN_RESIDUAL"
    assert ranking["leadership_route_bucket_count"] == 3


def test_validate_semantic_config_json_accepts_risk_off_exit_field() -> None:
    payload = _valid_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "bear_only",
        "partial_pct": 0.5,
        "partial_mode": "FIRST_TRANS_DOWN_THEN_FULL",
        "partial_only_if_profitable": True,
    }
    out = validate_semantic_config_json(payload)
    assert out["exit_rules"]["risk_off_exit"]["enabled"] is True
    assert out["exit_rules"]["risk_off_exit"]["mode"] == "bear_only"
    assert out["exit_rules"]["risk_off_exit"]["partial_pct"] == 0.5
    assert out["exit_rules"]["risk_off_exit"]["partial_mode"] == "FIRST_TRANS_DOWN_THEN_FULL"
    assert out["exit_rules"]["risk_off_exit"]["partial_only_if_profitable"] is True


def test_validate_semantic_config_json_accepts_pre_profit_breakout_failure_fields() -> None:
    payload = _valid_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.15,
        "pre_profit_breakout_failure_enabled": True,
        "pre_profit_breakout_failure_max_bars": 10,
        "pre_profit_breakout_failure_atr_buffer_k": 0.5,
    }
    out = validate_semantic_config_json(payload)
    trailing = out["exit_rules"]["trailing"]
    assert trailing["pre_profit_breakout_failure_enabled"] is True
    assert trailing["pre_profit_breakout_failure_max_bars"] == 10
    assert trailing["pre_profit_breakout_failure_atr_buffer_k"] == 0.5


def test_validate_semantic_config_json_accepts_profit_decay_exit_fields() -> None:
    payload = _valid_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.15,
        "profit_decay_exit_enabled": True,
        "profit_decay_exit_profit_pct": 0.12,
        "profit_decay_exit_min_hold_bars": 8,
        "profit_decay_exit_residual_score_threshold": 0.35,
    }
    out = validate_semantic_config_json(payload)
    trailing = out["exit_rules"]["trailing"]
    assert trailing["profit_decay_exit_enabled"] is True
    assert trailing["profit_decay_exit_profit_pct"] == 0.12
    assert trailing["profit_decay_exit_min_hold_bars"] == 8
    assert trailing["profit_decay_exit_residual_score_threshold"] == 0.35


def test_validate_semantic_config_json_accepts_entry_gap_guard_fields() -> None:
    payload = _valid_config()
    payload["signal_generation"]["breakout"]["entry_gap_guard_enabled"] = True
    payload["signal_generation"]["breakout"]["entry_gap_guard_pct"] = 0.04
    out = validate_semantic_config_json(payload)
    breakout = out["signal_generation"]["breakout"]
    assert breakout["entry_gap_guard_enabled"] is True
    assert breakout["entry_gap_guard_pct"] == 0.04


def test_validate_semantic_config_json_accepts_trans_down_freeze_bear_exit_mode() -> None:
    payload = _valid_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "TRANS_DOWN_FREEZE_BEAR_EXIT",
    }
    out = validate_semantic_config_json(payload)
    assert out["exit_rules"]["risk_off_exit"]["mode"] == "TRANS_DOWN_FREEZE_BEAR_EXIT"


def test_validate_semantic_config_json_accepts_trans_down_topk_bear_exit_mode() -> None:
    payload = _valid_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "TRANS_DOWN_TOPK_BEAR_EXIT",
        "trans_down_max_positions": 4,
    }
    out = validate_semantic_config_json(payload)
    assert out["exit_rules"]["risk_off_exit"]["mode"] == "TRANS_DOWN_TOPK_BEAR_EXIT"
    assert out["exit_rules"]["risk_off_exit"]["trans_down_max_positions"] == 4


def test_validate_semantic_config_json_accepts_trans_down_residual_floor_bear_exit_mode() -> None:
    payload = _valid_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "TRANS_DOWN_RESIDUAL_FLOOR_BEAR_EXIT",
        "trans_down_min_residual_score": 0.85,
    }
    out = validate_semantic_config_json(payload)
    assert out["exit_rules"]["risk_off_exit"]["mode"] == "TRANS_DOWN_RESIDUAL_FLOOR_BEAR_EXIT"
    assert out["exit_rules"]["risk_off_exit"]["trans_down_min_residual_score"] == 0.85


def test_validate_semantic_config_json_accepts_trans_down_residual_profit_floor_bear_exit_mode() -> None:
    payload = _valid_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "TRANS_DOWN_RESIDUAL_PROFIT_FLOOR_BEAR_EXIT",
        "trans_down_min_residual_score": 0.85,
    }
    out = validate_semantic_config_json(payload)
    assert out["exit_rules"]["risk_off_exit"]["mode"] == "TRANS_DOWN_RESIDUAL_PROFIT_FLOOR_BEAR_EXIT"
    assert out["exit_rules"]["risk_off_exit"]["trans_down_min_residual_score"] == 0.85


def test_validate_semantic_config_json_accepts_trans_down_residual_ma20_floor_bear_exit_mode() -> None:
    payload = _valid_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "TRANS_DOWN_RESIDUAL_MA20_FLOOR_BEAR_EXIT",
        "trans_down_min_residual_score": 0.85,
    }
    out = validate_semantic_config_json(payload)
    assert out["exit_rules"]["risk_off_exit"]["mode"] == "TRANS_DOWN_RESIDUAL_MA20_FLOOR_BEAR_EXIT"
    assert out["exit_rules"]["risk_off_exit"]["trans_down_min_residual_score"] == 0.85


def test_validate_semantic_config_json_accepts_chandelier_segmented_trailing_mode() -> None:
    payload = _valid_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.15,
        "segmented_trend_exit_mode": "CHANDELIER",
        "segmented_mid_profit_pct": 0.15,
        "segmented_high_profit_pct": 0.25,
        "segmented_high_trail_k": 2.0,
    }
    out = validate_semantic_config_json(payload)
    assert out["exit_rules"]["trailing"]["segmented_trend_exit_mode"] == "CHANDELIER"
    assert out["exit_rules"]["trailing"]["segmented_mid_profit_pct"] == 0.15
    assert out["exit_rules"]["trailing"]["segmented_high_profit_pct"] == 0.25
    assert out["exit_rules"]["trailing"]["segmented_high_trail_k"] == 2.0


def test_validate_semantic_config_json_accepts_trailing_activate_profit_pct() -> None:
    payload = _valid_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.08,
    }
    out = validate_semantic_config_json(payload)
    assert out["exit_rules"]["trailing"]["enabled"] is True
    assert out["exit_rules"]["trailing"]["k"] == 3.0
    assert out["exit_rules"]["trailing"]["activate_profit_pct"] == 0.08


def test_validate_semantic_config_json_accepts_segmented_trend_exit_fields() -> None:
    payload = _valid_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.15,
        "segmented_trend_exit_mode": "ma20",
        "segmented_mid_profit_pct": 0.08,
        "segmented_high_profit_pct": 0.15,
        "segmented_high_trail_k": 2.5,
    }
    out = validate_semantic_config_json(payload)
    trailing = out["exit_rules"]["trailing"]
    assert trailing["segmented_trend_exit_mode"] == "ma20"
    assert trailing["segmented_mid_profit_pct"] == 0.08
    assert trailing["segmented_high_profit_pct"] == 0.15
    assert trailing["segmented_high_trail_k"] == 2.5


def test_validate_semantic_config_json_accepts_multi_alpha_fields() -> None:
    out = validate_semantic_config_json(_valid_multi_alpha_config())
    assert [item["name"] for item in out["signal_generation"]["modules"]] == ["breakout_55", "rsi_reversal"]
    assert out["signal_composition"]["compose_mode"] == "REGIME_ROUTE"


def test_validate_semantic_config_json_accepts_ranking_fields() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {
        "momentum_top_pct": 0.1,
        "score_source_mode": "residual_quality",
        "residual_window": 40,
        "residual_benchmark_weight": 0.7,
        "residual_industry_weight": 0.3,
        "industry_relative_mode": "INDUSTRY_RANK_PCT",
        "industry_relative_regime_mode": "STRONG_RISK_ON",
        "residual_weight_regime_mode": "STRONG_RISK_ON",
        "residual_benchmark_weight_fallback": 0.5,
        "residual_industry_weight_fallback": 0.5,
        "residual_window_regime_mode": "STRONG_RISK_ON",
        "residual_window_fallback": 60,
        "residual_window_regime_fast_ma": 20,
        "residual_window_regime_slow_ma": 60,
        "residual_refine_mode": "BREAKOUT_MARGIN",
        "residual_refine_weight": 0.15,
        "residual_weight": 0.8,
        "sector_weight": 0.0,
        "quality_weight": 0.2,
        "enable_strength_rank": True,
        "strength_ma": 120,
        "strength_top_k_mode": "FILL_TO_MAX",
        "enable_multifactor_rank": True,
        "mf_topk": 10,
        "mf_concentrate_scale": 1.25,
        "mf_rank_gate_mode": "TRANS_UP_OR_BULL",
    }
    out = validate_semantic_config_json(payload)
    ranking = out["signal_generation"]["ranking"]
    assert ranking["score_source_mode"] == "residual_quality"
    assert ranking["residual_window"] == 40
    assert ranking["residual_benchmark_weight"] == 0.7
    assert ranking["residual_industry_weight"] == 0.3
    assert ranking["industry_relative_mode"] == "INDUSTRY_RANK_PCT"
    assert ranking["industry_relative_regime_mode"] == "STRONG_RISK_ON"
    assert ranking["residual_weight_regime_mode"] == "STRONG_RISK_ON"
    assert ranking["residual_benchmark_weight_fallback"] == 0.5
    assert ranking["residual_industry_weight_fallback"] == 0.5
    assert ranking["residual_window_regime_mode"] == "STRONG_RISK_ON"
    assert ranking["residual_window_fallback"] == 60
    assert ranking["residual_window_regime_fast_ma"] == 20
    assert ranking["residual_window_regime_slow_ma"] == 60
    assert ranking["residual_refine_mode"] == "BREAKOUT_MARGIN"
    assert ranking["residual_refine_weight"] == 0.15
    assert ranking["residual_weight"] == 0.8
    assert ranking["sector_weight"] == 0.0
    assert ranking["quality_weight"] == 0.2
    assert ranking["enable_strength_rank"] is True
    assert ranking["strength_ma"] == 120
    assert ranking["strength_top_k_mode"] == "FILL_TO_MAX"
    assert ranking["enable_multifactor_rank"] is True
    assert ranking["mf_topk"] == 10
    assert ranking["mf_concentrate_scale"] == 1.25
    assert ranking["mf_rank_gate_mode"] == "TRANS_UP_OR_BULL"
    assert ranking["momentum_top_pct"] == 0.1


def test_validate_semantic_config_json_accepts_conditional_tiebreak_refine_mode() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "residual_refine_mode": "CONDITIONAL_TIEBREAK",
        "residual_refine_weight": 0.2,
    }
    out = validate_semantic_config_json(payload)
    ranking = out["signal_generation"]["ranking"]
    assert ranking["score_source_mode"] == "residual_only"
    assert ranking["residual_refine_mode"] == "CONDITIONAL_TIEBREAK"
    assert ranking["residual_refine_weight"] == 0.2


def test_validate_semantic_config_json_accepts_industry_second_stage_refine_mode() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "residual_refine_mode": "INDUSTRY_SECOND_STAGE",
        "residual_refine_weight": 0.15,
        "industry_second_stage_min_industry_score": 0.85,
    }
    out = validate_semantic_config_json(payload)
    ranking = out["signal_generation"]["ranking"]
    assert ranking["residual_refine_mode"] == "INDUSTRY_SECOND_STAGE"
    assert ranking["residual_refine_weight"] == 0.15
    assert ranking["industry_second_stage_min_industry_score"] == 0.85


def test_validate_semantic_config_json_accepts_industry_second_stage_tiebreak_mode() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "residual_refine_mode": "INDUSTRY_SECOND_STAGE_TIEBREAK",
        "industry_second_stage_min_industry_score": 0.9,
    }
    out = validate_semantic_config_json(payload)
    ranking = out["signal_generation"]["ranking"]
    assert ranking["residual_refine_mode"] == "INDUSTRY_SECOND_STAGE_TIEBREAK"
    assert ranking["industry_second_stage_min_industry_score"] == 0.9


def test_validate_semantic_config_json_rejects_negative_ranking_weight() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_quality",
        "quality_weight": -0.1,
    }
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.quality_weight" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for negative ranking weight")


def test_validate_semantic_config_json_rejects_zero_residual_split_weights() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "residual_benchmark_weight": 0.0,
        "residual_industry_weight": 0.0,
    }
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.residual_benchmark_weight" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for zero residual split weights")


def test_validate_semantic_config_json_rejects_unpaired_residual_weight_fallbacks() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "residual_weight_regime_mode": "STRONG_RISK_ON",
        "residual_benchmark_weight_fallback": 0.5,
    }
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.residual_benchmark_weight_fallback" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for unpaired residual weight fallbacks")


def test_validate_semantic_config_json_rejects_zero_residual_weight_fallbacks() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "residual_weight_regime_mode": "STRONG_RISK_ON",
        "residual_benchmark_weight_fallback": 0.0,
        "residual_industry_weight_fallback": 0.0,
    }
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.residual_benchmark_weight_fallback" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for zero residual fallback weights")


def test_validate_semantic_config_json_rejects_invalid_residual_window() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {"residual_window": 1}
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.residual_window" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for invalid residual_window")


def test_validate_semantic_config_json_rejects_invalid_residual_window_fallback() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {"residual_window_fallback": 1}
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.residual_window_fallback" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for invalid residual_window_fallback")


def test_validate_semantic_config_json_rejects_invalid_residual_window_regime_fast_ma() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {"residual_window_regime_fast_ma": 1}
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.residual_window_regime_fast_ma" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for invalid residual_window_regime_fast_ma")


def test_validate_semantic_config_json_rejects_invalid_residual_window_regime_ma_order() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {
        "residual_window_regime_fast_ma": 60,
        "residual_window_regime_slow_ma": 20,
    }
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.residual_window_regime_fast_ma" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for invalid residual_window_regime_fast_ma order")


def test_validate_semantic_config_json_rejects_unsupported_residual_window_regime_mode() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {"residual_window_regime_mode": "BULL_ONLY"}
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.residual_window_regime_mode" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for unsupported residual_window_regime_mode")


def test_validate_semantic_config_json_rejects_unsupported_residual_weight_regime_mode() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {"residual_weight_regime_mode": "BULL_ONLY"}
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.residual_weight_regime_mode" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for unsupported residual_weight_regime_mode")


def test_validate_semantic_config_json_rejects_unsupported_industry_relative_mode() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {"industry_relative_mode": "INDUSTRY_MAGIC"}
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.industry_relative_mode" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for unsupported industry_relative_mode")


def test_validate_semantic_config_json_accepts_industry_excess_median_mode() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {"industry_relative_mode": "INDUSTRY_EXCESS_MEDIAN"}
    validated = validate_semantic_config_json(payload)
    assert validated["signal_generation"]["ranking"]["industry_relative_mode"] == "INDUSTRY_EXCESS_MEDIAN"


def test_validate_semantic_config_json_rejects_unsupported_industry_relative_regime_mode() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {"industry_relative_regime_mode": "BULL_ONLY"}
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.industry_relative_regime_mode" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for unsupported industry_relative_regime_mode")


def test_validate_semantic_config_json_rejects_unsupported_residual_refine_mode() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {"residual_refine_mode": "alpha_magic"}
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.residual_refine_mode" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for unsupported residual_refine_mode")


def test_validate_semantic_config_json_rejects_unsupported_ranking_score_source_mode() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {"score_source_mode": "alpha_magic"}
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.score_source_mode" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for unsupported ranking score_source_mode")


def test_validate_semantic_config_json_rejects_small_leadership_route_bucket_count() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "LEADERSHIP_THEN_RESIDUAL",
        "leadership_route_bucket_count": 1,
    }
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.leadership_route_bucket_count" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for invalid leadership_route_bucket_count")


def test_validate_semantic_config_json_rejects_unsupported_ranking_gate_mode() -> None:
    payload = _valid_config()
    payload["signal_generation"]["ranking"] = {"mf_rank_gate_mode": "BEAR_ONLY"}
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.ranking.mf_rank_gate_mode" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for unsupported ranking mf_rank_gate_mode")


def test_validate_semantic_config_json_rejects_unknown_top_level_field() -> None:
    payload = _valid_config()
    payload["unexpected_flag"] = True
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "unexpected_flag" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for unknown top-level field")


def test_validate_semantic_config_json_rejects_unknown_nested_field() -> None:
    payload = _valid_config()
    payload["universe"]["filters"]["mystery_field"] = 123
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "mystery_field" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for unknown nested field")


def test_validate_semantic_config_json_rejects_missing_strategy_block() -> None:
    payload = _valid_config()
    payload["signal_generation"].pop("breakout", None)
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.breakout" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for missing breakout block")


def test_validate_semantic_config_json_rejects_unsupported_multi_alpha_module() -> None:
    payload = _valid_multi_alpha_config()
    payload["signal_generation"]["modules"][0]["name"] = "momentum_roc"
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.modules[0].name" in str(exc.detail)
        assert "momentum_roc" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for unsupported multi-alpha module")


def test_compile_semantic_config_json_emits_provenance_and_compiled_plan() -> None:
    compiled = compile_semantic_config_json(
        _valid_config(),
        compiled_plan_payload={"runtime_config": {"strategy": {"name": "breakout_trend"}}},
        config_source="config_json",
    )
    assert compiled["schema_version"] == SEMANTIC_CONFIG_SCHEMA_VERSION
    assert compiled["resolved_config"]["schema_version"] == SEMANTIC_CONFIG_SCHEMA_VERSION
    assert compiled["resolved_config"]["config_source"] == "config_json"
    assert compiled["compiled_plan"]["runtime_config"]["strategy"]["name"] == "breakout_trend"

