from __future__ import annotations

import pandas as pd

from backend.api.backtest_v2 import runner_impl
from backend.api.endpoints._paths import _bt_root
from backend.core.tools.experiment_runner import _project_trade_csv_schema


def _multi_alpha_config() -> dict:
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
            "portfolio_mode": "hard_sleeve_budget",
        },
    }


def _breakout_config() -> dict:
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
                "breakout_window": 45,
                "enable_dual_breakout": False,
                "breakout_entry_buffer_pct": 0.0,
                "entry_confirm_mode": "none",
                "entry_delay_mode": "none",
            },
            "entry_filter": {
                "enable_entry_above_slow_ma": True,
                "enable_entry_slow_ma_slope": True,
                "entry_slope_lookback": 7,
            },
        },
        "exit_rules": {
            "enabled": True,
            "atr_stop": {"enabled": True, "k": 1.2},
            "trailing": {"enabled": True, "k": 3.0},
        },
        "position_risk": {
            "enabled": True,
            "max_positions": 12,
            "portfolio_mode": "profit_release",
        },
    }


def test_compile_semantic_bundle_preserves_multi_alpha_runtime_payload() -> None:
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=_multi_alpha_config(),
        config_source="config_json",
        use_body_universe_fields=False,
    )
    runtime_cfg = compiled["runtime_config"]
    multi_alpha = runtime_cfg["strategy"]["params"]["multi_alpha"]
    assert runtime_cfg["strategy"]["name"] == "composite"
    assert runtime_cfg["strategy"]["params"]["portfolio_mode"] == "hard_sleeve_budget"
    assert [item["name"] for item in multi_alpha["signal_generation"]["modules"]] == ["breakout_55", "rsi_reversal"]
    assert multi_alpha["signal_composition"]["compose_mode"] == "REGIME_ROUTE"
    assert multi_alpha["signal_composition"]["same_symbol_policy"] == "PREFER_HIGHER_SCORE"


def test_compile_semantic_bundle_injects_breakout_entry_filters() -> None:
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=_breakout_config(),
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert compiled["runtime_config"]["strategy"]["name"] == "breakout_trend"
    assert params["enable_entry_above_slow_ma"] is True
    assert params["enable_entry_slow_ma_slope"] is True
    assert params["entry_slope_lookback"] == 7
    assert params["portfolio_mode"] == "profit_release"


def test_compile_semantic_bundle_preserves_turnover_rate_filter_fields() -> None:
    payload = _breakout_config()
    payload["universe"]["filters"]["min_avg_turnover_rate_20d"] = 1.1
    payload["universe"]["filters"]["turnover_rate_field"] = "turnover_rate_f"
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    runtime_filters = compiled["runtime_config"]["universe"]["filters"]
    assert runtime_filters["min_avg_turnover_rate_20d"] == 1.1
    assert runtime_filters["turnover_rate_field"] == "turnover_rate_f"


def test_compile_semantic_bundle_emits_ranking_execution_overrides() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "momentum_top_pct": 0.1,
        "enable_strength_rank": True,
        "strength_ma": 120,
        "strength_top_k_mode": "FILL_TO_MAX",
        "enable_multifactor_rank": True,
        "mf_topk": 10,
        "mf_concentrate_scale": 1.25,
        "mf_rank_gate_mode": "BULL_ONLY",
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert params["momentum_top_pct"] == 0.1
    assert execution_overrides["enable_strength_rank"] is True
    assert execution_overrides["strength_ma"] == 120
    assert execution_overrides["strength_top_k_mode"] == "FILL_TO_MAX"
    assert execution_overrides["enable_multifactor_rank"] is True
    assert execution_overrides["mf_topk"] == 10
    assert execution_overrides["mf_concentrate_scale"] == 1.25
    assert execution_overrides["mf_rank_gate_mode"] == "BULL_ONLY"
    assert execution_overrides["momentum_top_pct"] == 0.1


def test_compile_semantic_bundle_maps_provider_final_score_source_mode() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "provider_final",
        "momentum_top_pct": 0.1,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert params["momentum_top_pct"] == 0.1
    assert params["enable_residual_ranking"] is True
    assert params["enable_sector_quality_ranking"] is True
    assert params["source_aware_residual_mode"] == "off"
    assert params["residual_weight"] == 0.5
    assert params["sector_weight"] == 0.3
    assert params["quality_weight"] == 0.2
    assert execution_overrides["enable_multifactor_rank"] is True
    assert "enable_strength_rank" not in execution_overrides


def test_compile_semantic_bundle_injects_conditional_tiebreak_refine_mode() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "residual_refine_mode": "conditional_tiebreak",
        "residual_refine_weight": 0.2,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_residual_ranking"] is True
    assert params["residual_refine_mode"] == "conditional_tiebreak"
    assert params["residual_refine_weight"] == 0.2


def test_compile_semantic_bundle_injects_industry_second_stage_refine_mode() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "residual_refine_mode": "industry_second_stage",
        "residual_refine_weight": 0.15,
        "industry_second_stage_min_industry_score": 0.85,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_residual_ranking"] is True
    assert params["residual_refine_mode"] == "industry_second_stage"
    assert params["residual_refine_weight"] == 0.15
    assert params["industry_second_stage_min_industry_score"] == 0.85


def test_compile_semantic_bundle_injects_leadership_then_residual_mode() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "leadership_then_residual",
        "residual_window": 40,
        "leadership_route_bucket_count": 3,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert params["ranking_mode"] == "leadership_then_residual"
    assert params["enable_residual_ranking"] is True
    assert params["leadership_route_bucket_count"] == 3
    assert execution_overrides["leadership_route_bucket_count"] == 3


def test_compile_semantic_bundle_injects_source_aware_residual_mode() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "source_aware_residual_mode": "pullback_only",
    }
    payload["signal_generation"]["breakout"]["enable_pullback_candidates"] = True
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_residual_ranking"] is True
    assert params["enable_pullback_candidates"] is True
    assert params["source_aware_residual_mode"] == "pullback_only"


def test_compile_semantic_bundle_injects_residual_split_weights() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "residual_window": 40,
        "residual_benchmark_weight": 0.7,
        "residual_industry_weight": 0.3,
        "industry_relative_mode": "industry_rank_pct",
        "industry_relative_regime_mode": "strong_risk_on",
        "residual_weight_regime_mode": "STRONG_RISK_ON",
        "residual_benchmark_weight_fallback": 0.5,
        "residual_industry_weight_fallback": 0.5,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert params["enable_residual_ranking"] is True
    assert params["residual_window"] == 40
    assert params["residual_benchmark_weight"] == 0.7
    assert params["residual_industry_weight"] == 0.3
    assert params["industry_relative_mode"] == "industry_rank_pct"
    assert params["industry_relative_regime_mode"] == "strong_risk_on"
    assert params["residual_weight_regime_mode"] == "STRONG_RISK_ON"
    assert params["residual_benchmark_weight_fallback"] == 0.5
    assert params["residual_industry_weight_fallback"] == 0.5
    assert execution_overrides["residual_benchmark_weight"] == 0.7
    assert execution_overrides["residual_industry_weight"] == 0.3
    assert execution_overrides["industry_relative_mode"] == "industry_rank_pct"
    assert execution_overrides["industry_relative_regime_mode"] == "strong_risk_on"
    assert execution_overrides["residual_weight_regime_mode"] == "STRONG_RISK_ON"
    assert execution_overrides["residual_benchmark_weight_fallback"] == 0.5
    assert execution_overrides["residual_industry_weight_fallback"] == 0.5


def test_compile_semantic_bundle_maps_residual_quality_score_source_mode() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_quality",
        "residual_weight": 0.8,
        "sector_weight": 0.0,
        "quality_weight": 0.2,
        "momentum_top_pct": 0.1,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert params["momentum_top_pct"] == 0.1
    assert params["enable_residual_ranking"] is True
    assert params["enable_sector_quality_ranking"] is True
    assert params["source_aware_residual_mode"] == "off"
    assert params["residual_weight"] == 0.8
    assert params["sector_weight"] == 0.0
    assert params["quality_weight"] == 0.2
    assert execution_overrides["enable_multifactor_rank"] is True
    assert execution_overrides["residual_weight"] == 0.8
    assert execution_overrides["sector_weight"] == 0.0
    assert execution_overrides["quality_weight"] == 0.2
    assert "enable_strength_rank" not in execution_overrides


def test_compile_semantic_bundle_injects_gated_dual_breakout_fields() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["breakout"].update(
        {
            "enable_dual_breakout": True,
            "breakout_window_short": 10,
            "breakout_window_long": 55,
            "dual_breakout_mode": "slow_gate_fast_trigger",
            "dual_breakout_gate_ma_window": 120,
            "dual_breakout_gate_slope_lookback": 10,
        }
    )
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_dual_breakout"] is True
    assert params["breakout_window_short"] == 10
    assert params["breakout_window_long"] == 55
    assert params["dual_breakout_mode"] == "slow_gate_fast_trigger"
    assert params["dual_breakout_gate_ma_window"] == 120
    assert params["dual_breakout_gate_slope_lookback"] == 10


def test_compile_semantic_bundle_injects_pullback_candidate_fields() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["breakout"].update(
        {
            "enable_pullback_candidates": True,
            "pullback_variant_mode": "pb_reclaim_ma20",
            "pullback_touch_lookback": 15,
            "pullback_reclaim_window": 4,
            "pullback_ma20_touch_band_pct": 0.02,
            "pullback_low_lookback": 11,
            "pullback_low_band_pct": 0.03,
            "pullback_box_window": 6,
            "pullback_box_range_pct_max": 0.07,
        }
    )
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_pullback_candidates"] is True
    assert params["pullback_variant_mode"] == "pb_reclaim_ma20"
    assert params["pullback_touch_lookback"] == 15
    assert params["pullback_reclaim_window"] == 4
    assert params["pullback_ma20_touch_band_pct"] == 0.02
    assert params["pullback_low_lookback"] == 11
    assert params["pullback_low_band_pct"] == 0.03
    assert params["pullback_box_window"] == 6
    assert params["pullback_box_range_pct_max"] == 0.07


def test_compile_semantic_bundle_injects_segmented_market_filter_fields() -> None:
    payload = _breakout_config()
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
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    market_filter = compiled["runtime_config"]["market_filter"]
    assert market_filter["trans_down_multiplier"] == 0.3
    assert market_filter["trans_up_multiplier"] == 0.8
    assert market_filter["bear_multiplier"] == 0.0


def test_compile_semantic_bundle_injects_breadth_fields() -> None:
    payload = _breakout_config()
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
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    breadth = compiled["runtime_config"]["breadth"]
    assert breadth["enabled"] is True
    assert breadth["mode"] == "dynamic_maxpos"
    assert breadth["score_type"] == "combo"
    assert breadth["mapping_mode"] == "smooth"
    assert breadth["min_positions"] == 6
    assert breadth["max_positions"] == 10
    assert breadth["gate_threshold"] == 0.45
    assert breadth["gate_quantile_window"] == 252
    assert breadth["gate_quantile_pct"] == 0.2


def test_compile_semantic_bundle_injects_mf_rank_tilt_sizing_fields() -> None:
    payload = _breakout_config()
    payload["sizing"] = {
        "weight_mode": "mf_rank_tilt",
        "min_positions": 10,
        "tilt_strength": 0.15,
        "tilt_top_n": 3,
        "tilt_bottom_n": 2,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    sizing = compiled["runtime_config"]["sizing"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert sizing["weight_mode"] == "mf_rank_tilt"
    assert sizing["min_positions"] == 10
    assert sizing["tilt_strength"] == 0.15
    assert sizing["tilt_top_n"] == 3
    assert sizing["tilt_bottom_n"] == 2
    assert execution_overrides["weight_mode"] == "mf_rank_tilt"
    assert execution_overrides["tilt_strength"] == 0.15
    assert execution_overrides["tilt_top_n"] == 3
    assert execution_overrides["tilt_bottom_n"] == 2


def test_compile_semantic_bundle_injects_score_weighted_sizing_fields() -> None:
    payload = _breakout_config()
    payload["sizing"] = {
        "weight_mode": "score_weighted",
        "min_positions": 10,
        "score_weight_min_scale": 0.75,
        "score_weight_max_scale": 1.25,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    sizing = compiled["runtime_config"]["sizing"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert sizing["weight_mode"] == "score_weighted"
    assert sizing["min_positions"] == 10
    assert sizing["score_weight_min_scale"] == 0.75
    assert sizing["score_weight_max_scale"] == 1.25
    assert execution_overrides["weight_mode"] == "score_weighted"
    assert execution_overrides["score_weight_min_scale"] == 0.75
    assert execution_overrides["score_weight_max_scale"] == 1.25


def test_compile_semantic_bundle_injects_cash_aware_candidate_planner_fields() -> None:
    payload = _breakout_config()
    payload["sizing"] = {
        "candidate_plan_mode": "cash_aware",
        "cash_aware_search_top_n": 12,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    sizing = compiled["runtime_config"]["sizing"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert sizing["candidate_plan_mode"] == "cash_aware"
    assert sizing["cash_aware_search_top_n"] == 12
    assert execution_overrides["candidate_plan_mode"] == "cash_aware"
    assert execution_overrides["cash_aware_search_top_n"] == 12


def test_compile_semantic_bundle_injects_risk_off_exit_flag() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "bear_only",
        "partial_pct": 0.5,
        "partial_mode": "first_trans_down_then_full",
        "partial_only_if_profitable": True,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_risk_off_exit"] is True
    assert params["risk_off_exit_mode"] == "bear_only"
    assert params["risk_off_exit_partial_pct"] == 0.5
    assert params["risk_off_exit_partial_mode"] == "first_trans_down_then_full"
    assert params["risk_off_exit_partial_only_if_profitable"] is True


def test_compile_semantic_bundle_injects_chandelier_segmented_trailing_fields() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.15,
        "segmented_trend_exit_mode": "chandelier",
        "segmented_mid_profit_pct": 0.15,
        "segmented_high_profit_pct": 0.25,
        "segmented_high_trail_k": 2.0,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    exit_cfg = compiled["runtime_config"]["exit"]
    assert params["segmented_trend_exit_mode"] == "chandelier"
    assert params["segmented_mid_profit_pct"] == 0.15
    assert params["segmented_high_profit_pct"] == 0.25
    assert params["segmented_high_trail_k"] == 2.0
    assert exit_cfg["segmented_trend_exit_mode"] == "chandelier"
    assert exit_cfg["segmented_mid_profit_pct"] == 0.15
    assert exit_cfg["segmented_high_profit_pct"] == 0.25
    assert exit_cfg["segmented_high_trail_k"] == 2.0


def test_compile_semantic_bundle_injects_trans_down_freeze_bear_exit_mode() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "trans_down_freeze_bear_exit",
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_risk_off_exit"] is True
    assert params["risk_off_exit_mode"] == "trans_down_freeze_bear_exit"


def test_compile_semantic_bundle_injects_trans_down_topk_bear_exit_mode() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "trans_down_topk_bear_exit",
        "trans_down_max_positions": 4,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_risk_off_exit"] is True
    assert params["risk_off_exit_mode"] == "trans_down_topk_bear_exit"
    assert params["risk_off_exit_trans_down_max_positions"] == 4


def test_compile_semantic_bundle_injects_trans_down_residual_floor_bear_exit_mode() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "trans_down_residual_floor_bear_exit",
        "trans_down_min_residual_score": 0.85,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_risk_off_exit"] is True
    assert params["risk_off_exit_mode"] == "trans_down_residual_floor_bear_exit"
    assert params["risk_off_exit_trans_down_min_residual_score"] == 0.85


def test_compile_semantic_bundle_injects_trans_down_residual_profit_floor_bear_exit_mode() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "trans_down_residual_profit_floor_bear_exit",
        "trans_down_min_residual_score": 0.85,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_risk_off_exit"] is True
    assert params["risk_off_exit_mode"] == "trans_down_residual_profit_floor_bear_exit"
    assert params["risk_off_exit_trans_down_min_residual_score"] == 0.85


def test_compile_semantic_bundle_injects_trans_down_residual_ma20_floor_bear_exit_mode() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "trans_down_residual_ma20_floor_bear_exit",
        "trans_down_min_residual_score": 0.85,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_risk_off_exit"] is True
    assert params["risk_off_exit_mode"] == "trans_down_residual_ma20_floor_bear_exit"
    assert params["risk_off_exit_trans_down_min_residual_score"] == 0.85


def test_compile_semantic_bundle_injects_trailing_activate_profit_pct() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.08,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_atr_trail"] is True
    assert params["atr_trail_k"] == 3.0
    assert params["trailing_activate_profit_pct"] == 0.08
    assert compiled["runtime_config"]["exit"]["trailing_activate_profit_pct"] == 0.08


def test_compile_semantic_bundle_injects_pre_profit_breakout_failure_fields() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.15,
        "pre_profit_breakout_failure_enabled": True,
        "pre_profit_breakout_failure_max_bars": 10,
        "pre_profit_breakout_failure_atr_buffer_k": 0.5,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    exit_cfg = compiled["runtime_config"]["exit"]
    assert params["enable_pre_profit_breakout_failure_exit"] is True
    assert params["pre_profit_breakout_failure_max_bars"] == 10
    assert params["pre_profit_breakout_failure_atr_buffer_k"] == 0.5
    assert exit_cfg["enable_pre_profit_breakout_failure_exit"] is True
    assert exit_cfg["pre_profit_breakout_failure_max_bars"] == 10
    assert exit_cfg["pre_profit_breakout_failure_atr_buffer_k"] == 0.5


def test_compile_semantic_bundle_injects_profit_decay_exit_fields() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.15,
        "profit_decay_exit_enabled": True,
        "profit_decay_exit_profit_pct": 0.12,
        "profit_decay_exit_min_hold_bars": 8,
        "profit_decay_exit_residual_score_threshold": 0.35,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    exit_cfg = compiled["runtime_config"]["exit"]
    assert params["enable_profit_decay_exit"] is True
    assert params["profit_decay_exit_profit_pct"] == 0.12
    assert params["profit_decay_exit_min_hold_bars"] == 8
    assert params["profit_decay_exit_residual_score_threshold"] == 0.35
    assert exit_cfg["enable_profit_decay_exit"] is True
    assert exit_cfg["profit_decay_exit_profit_pct"] == 0.12
    assert exit_cfg["profit_decay_exit_min_hold_bars"] == 8
    assert exit_cfg["profit_decay_exit_residual_score_threshold"] == 0.35


def test_compile_semantic_bundle_injects_entry_gap_guard_fields() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["breakout"]["entry_gap_guard_enabled"] = True
    payload["signal_generation"]["breakout"]["entry_gap_guard_pct"] = 0.04
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_entry_gap_guard"] is True
    assert params["entry_gap_guard_pct"] == 0.04


def test_compile_semantic_bundle_injects_segmented_trend_exit_fields() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.15,
        "segmented_trend_exit_mode": "low10",
        "segmented_mid_profit_pct": 0.08,
        "segmented_high_profit_pct": 0.15,
        "segmented_high_trail_k": 2.5,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    exit_cfg = compiled["runtime_config"]["exit"]
    assert params["segmented_trend_exit_mode"] == "low10"
    assert params["segmented_mid_profit_pct"] == 0.08
    assert params["segmented_high_profit_pct"] == 0.15
    assert params["segmented_high_trail_k"] == 2.5
    assert exit_cfg["segmented_trend_exit_mode"] == "low10"
    assert exit_cfg["segmented_mid_profit_pct"] == 0.08
    assert exit_cfg["segmented_high_profit_pct"] == 0.15
    assert exit_cfg["segmented_high_trail_k"] == 2.5


def test_compile_semantic_bundle_merges_request_level_blocks() -> None:
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(_bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(
            signal_generation={"modules": [{"name": "breakout_55", "alpha_id": "breakout_55"}]},
            signal_composition={"compose_mode": "REGIME_ROUTE"},
        ),
        semantic_cfg={
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
            },
        },
        config_source="saved_config",
        use_body_universe_fields=False,
    )
    multi_alpha = compiled["runtime_config"]["strategy"]["params"]["multi_alpha"]
    assert [item["name"] for item in multi_alpha["signal_generation"]["modules"]] == ["breakout_55"]
    assert multi_alpha["signal_composition"]["compose_mode"] == "REGIME_ROUTE"


def test_project_trade_csv_schema_keeps_source_and_exit_fields() -> None:
    projected = _project_trade_csv_schema(
        pd.DataFrame(
            [
                {
                    "date": "2026-03-02",
                    "symbol": "sh600000",
                    "side": "SELL",
                    "price": 10.0,
                    "qty": 100,
                    "reason_code": "EXIT",
                    "exit_owner": "global_risk_override",
                    "entry_alpha_id": "breakout_55",
                    "entry_sleeve_id": "trend",
                    "entry_reason_code": "BREAKOUT_HIGH",
                    "entry_date": "2026-02-20",
                }
            ]
        )
    )

    assert "exit_owner" in projected.columns
    assert "entry_alpha_id" in projected.columns
    assert "entry_sleeve_id" in projected.columns
    assert projected.loc[0, "exit_owner"] == "global_risk_override"
    assert projected.loc[0, "entry_alpha_id"] == "breakout_55"

