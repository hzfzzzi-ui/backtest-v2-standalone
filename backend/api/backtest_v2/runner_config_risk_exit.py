"""Risk, exit, and sizing-domain runtime config compilation helpers."""

from __future__ import annotations

from typing import Any

from backend.api.backtest_v2.execution_overrides import to_int_or_default as _to_int_or_default


def apply_risk_exit_runtime_cfg(
    cfg: dict[str, Any],
    wb_cfg: dict[str, Any],
    *,
    signal_context: dict[str, Any],
) -> None:
    sig = signal_context.get("signal_generation") if isinstance(signal_context.get("signal_generation"), dict) else {}
    multi_alpha_payload = signal_context.get("multi_alpha_payload")
    pos_risk_cfg = signal_context.get("position_risk") if isinstance(signal_context.get("position_risk"), dict) else {}

    strategy = cfg.setdefault("strategy", {})
    if multi_alpha_payload is not None:
        strategy["params"] = {
            **dict(strategy.get("params") or {}),
            "multi_alpha": multi_alpha_payload,
            "portfolio_mode": str(pos_risk_cfg.get("portfolio_mode", "hard_sleeve_budget") or "hard_sleeve_budget"),
        }

    exit_rules = wb_cfg.get("exit_rules") if isinstance(wb_cfg.get("exit_rules"), dict) else {}
    atr_stop = exit_rules.get("atr_stop") if isinstance(exit_rules.get("atr_stop"), dict) else {}
    if atr_stop:
        strategy.setdefault("params", {})["enable_atr_stop"] = bool(atr_stop.get("enabled", False))
        strategy["params"]["atr_stop_k"] = float(atr_stop.get("k", 2.0))
    trailing = exit_rules.get("trailing") if isinstance(exit_rules.get("trailing"), dict) else {}
    if trailing:
        strategy.setdefault("params", {})["enable_atr_trail"] = bool(trailing.get("enabled", False))
        strategy["params"]["atr_trail_k"] = float(trailing.get("k", 3.0))
        if trailing.get("activate_profit_pct") is not None:
            strategy["params"]["trailing_activate_profit_pct"] = float(trailing.get("activate_profit_pct"))
        if trailing.get("segmented_trend_exit_mode") is not None:
            strategy["params"]["segmented_trend_exit_mode"] = str(trailing.get("segmented_trend_exit_mode") or "off").strip().lower()
        if trailing.get("segmented_mid_profit_pct") is not None:
            strategy["params"]["segmented_mid_profit_pct"] = float(trailing.get("segmented_mid_profit_pct"))
        if trailing.get("segmented_high_profit_pct") is not None:
            strategy["params"]["segmented_high_profit_pct"] = float(trailing.get("segmented_high_profit_pct"))
        if trailing.get("segmented_high_trail_k") is not None:
            strategy["params"]["segmented_high_trail_k"] = float(trailing.get("segmented_high_trail_k"))
        if trailing.get("pre_profit_breakout_failure_enabled") is not None:
            strategy["params"]["enable_pre_profit_breakout_failure_exit"] = bool(trailing.get("pre_profit_breakout_failure_enabled"))
        if trailing.get("pre_profit_breakout_failure_max_bars") is not None:
            strategy["params"]["pre_profit_breakout_failure_max_bars"] = int(trailing.get("pre_profit_breakout_failure_max_bars"))
        if trailing.get("pre_profit_breakout_failure_atr_buffer_k") is not None:
            strategy["params"]["pre_profit_breakout_failure_atr_buffer_k"] = float(trailing.get("pre_profit_breakout_failure_atr_buffer_k"))
        if trailing.get("profit_decay_exit_enabled") is not None:
            strategy["params"]["enable_profit_decay_exit"] = bool(trailing.get("profit_decay_exit_enabled"))
        if trailing.get("profit_decay_exit_profit_pct") is not None:
            strategy["params"]["profit_decay_exit_profit_pct"] = float(trailing.get("profit_decay_exit_profit_pct"))
        if trailing.get("profit_decay_exit_min_hold_bars") is not None:
            strategy["params"]["profit_decay_exit_min_hold_bars"] = int(trailing.get("profit_decay_exit_min_hold_bars"))
        if trailing.get("profit_decay_exit_residual_score_threshold") is not None:
            strategy["params"]["profit_decay_exit_residual_score_threshold"] = float(trailing.get("profit_decay_exit_residual_score_threshold"))
    time_exit = exit_rules.get("time_exit") if isinstance(exit_rules.get("time_exit"), dict) else {}
    if time_exit:
        strategy["params"]["max_hold_days"] = int(time_exit.get("n_days", 0)) if bool(time_exit.get("enabled", False)) else 0
    hold_constraint = exit_rules.get("hold_constraint") if isinstance(exit_rules.get("hold_constraint"), dict) else {}
    if hold_constraint:
        strategy["params"]["min_hold_days"] = int(hold_constraint.get("min_hold_days", 0))
        strategy["params"]["cooldown_days"] = int(hold_constraint.get("cooldown_days", 0))

    take_profit = exit_rules.get("take_profit") if isinstance(exit_rules.get("take_profit"), dict) else {}
    fixed_stop = exit_rules.get("fixed_stop") if isinstance(exit_rules.get("fixed_stop"), dict) else {}
    if take_profit:
        strategy.setdefault("params", {})["enable_take_profit"] = bool(take_profit.get("enabled", False))
        strategy["params"]["take_profit_mode"] = str(take_profit.get("mode", "pct"))
        strategy["params"]["take_profit_pct"] = float(take_profit.get("pct", 0.10))
        strategy["params"]["take_profit_atr_k"] = float(take_profit.get("atr_k", 3.0))
    if fixed_stop:
        strategy.setdefault("params", {})["enable_fixed_stop_loss"] = bool(fixed_stop.get("enabled", False))
        strategy["params"]["fixed_stop_loss_pct"] = float(fixed_stop.get("pct", 0.05))

    exit_cfg = cfg.setdefault("exit", {})
    if take_profit:
        exit_cfg["enable_take_profit"] = bool(take_profit.get("enabled", False))
        exit_cfg["take_profit_mode"] = str(take_profit.get("mode", "pct"))
        exit_cfg["take_profit_pct"] = float(take_profit.get("pct", 0.10))
        exit_cfg["take_profit_atr_k"] = float(take_profit.get("atr_k", 3.0))
    if fixed_stop:
        exit_cfg["enable_fixed_stop_loss"] = bool(fixed_stop.get("enabled", False))
        exit_cfg["fixed_stop_loss_pct"] = float(fixed_stop.get("pct", 0.05))
    if atr_stop:
        exit_cfg["enable_atr_stop"] = bool(atr_stop.get("enabled", False))
        exit_cfg["atr_stop_k"] = float(atr_stop.get("k", 2.0))
    if trailing:
        exit_cfg["enable_atr_trail"] = bool(trailing.get("enabled", False))
        exit_cfg["atr_trail_k"] = float(trailing.get("k", 3.0))
        if trailing.get("activate_profit_pct") is not None:
            exit_cfg["trailing_activate_profit_pct"] = float(trailing.get("activate_profit_pct"))
        if trailing.get("segmented_trend_exit_mode") is not None:
            exit_cfg["segmented_trend_exit_mode"] = str(trailing.get("segmented_trend_exit_mode") or "off").strip().lower()
        if trailing.get("segmented_mid_profit_pct") is not None:
            exit_cfg["segmented_mid_profit_pct"] = float(trailing.get("segmented_mid_profit_pct"))
        if trailing.get("segmented_high_profit_pct") is not None:
            exit_cfg["segmented_high_profit_pct"] = float(trailing.get("segmented_high_profit_pct"))
        if trailing.get("segmented_high_trail_k") is not None:
            exit_cfg["segmented_high_trail_k"] = float(trailing.get("segmented_high_trail_k"))
        if trailing.get("pre_profit_breakout_failure_enabled") is not None:
            exit_cfg["enable_pre_profit_breakout_failure_exit"] = bool(trailing.get("pre_profit_breakout_failure_enabled"))
        if trailing.get("pre_profit_breakout_failure_max_bars") is not None:
            exit_cfg["pre_profit_breakout_failure_max_bars"] = int(trailing.get("pre_profit_breakout_failure_max_bars"))
        if trailing.get("pre_profit_breakout_failure_atr_buffer_k") is not None:
            exit_cfg["pre_profit_breakout_failure_atr_buffer_k"] = float(trailing.get("pre_profit_breakout_failure_atr_buffer_k"))
        if trailing.get("profit_decay_exit_enabled") is not None:
            exit_cfg["enable_profit_decay_exit"] = bool(trailing.get("profit_decay_exit_enabled"))
        if trailing.get("profit_decay_exit_profit_pct") is not None:
            exit_cfg["profit_decay_exit_profit_pct"] = float(trailing.get("profit_decay_exit_profit_pct"))
        if trailing.get("profit_decay_exit_min_hold_bars") is not None:
            exit_cfg["profit_decay_exit_min_hold_bars"] = int(trailing.get("profit_decay_exit_min_hold_bars"))
        if trailing.get("profit_decay_exit_residual_score_threshold") is not None:
            exit_cfg["profit_decay_exit_residual_score_threshold"] = float(trailing.get("profit_decay_exit_residual_score_threshold"))

    ma20_exit = exit_rules.get("ma20_exit") if isinstance(exit_rules.get("ma20_exit"), dict) else {}
    low10_exit = exit_rules.get("low10_exit") if isinstance(exit_rules.get("low10_exit"), dict) else {}
    risk_off_exit = exit_rules.get("risk_off_exit") if isinstance(exit_rules.get("risk_off_exit"), dict) else {}
    if ma20_exit:
        strategy.setdefault("params", {})["enable_ma20_exit"] = bool(ma20_exit.get("enabled", False))
        exit_cfg["enable_ma20_exit"] = bool(ma20_exit.get("enabled", False))
    if low10_exit:
        strategy.setdefault("params", {})["enable_low10_exit"] = bool(low10_exit.get("enabled", False))
        exit_cfg["enable_low10_exit"] = bool(low10_exit.get("enabled", False))
    if risk_off_exit:
        strategy.setdefault("params", {})["enable_risk_off_exit"] = bool(risk_off_exit.get("enabled", False))
        if risk_off_exit.get("mode") is not None:
            strategy.setdefault("params", {})["risk_off_exit_mode"] = str(risk_off_exit.get("mode") or "").strip().lower()
        if risk_off_exit.get("partial_pct") is not None:
            strategy.setdefault("params", {})["risk_off_exit_partial_pct"] = float(risk_off_exit.get("partial_pct"))
        if risk_off_exit.get("partial_mode") is not None:
            strategy.setdefault("params", {})["risk_off_exit_partial_mode"] = str(risk_off_exit.get("partial_mode") or "").strip().lower()
        if risk_off_exit.get("partial_only_if_profitable") is not None:
            strategy.setdefault("params", {})["risk_off_exit_partial_only_if_profitable"] = bool(risk_off_exit.get("partial_only_if_profitable"))
        if risk_off_exit.get("trans_down_max_positions") is not None:
            strategy.setdefault("params", {})["risk_off_exit_trans_down_max_positions"] = int(risk_off_exit.get("trans_down_max_positions"))
        if risk_off_exit.get("trans_down_min_residual_score") is not None:
            strategy.setdefault("params", {})["risk_off_exit_trans_down_min_residual_score"] = float(risk_off_exit.get("trans_down_min_residual_score"))

    universe_filter = wb_cfg.get("universe_filter") if isinstance(wb_cfg.get("universe_filter"), dict) else {}
    if universe_filter:
        strategy.setdefault("params", {})["min_price"] = float(universe_filter.get("min_price", 5.0))

    regime_detection = sig.get("regime_detection") if isinstance(sig.get("regime_detection"), dict) else {}
    strategy.setdefault("params", {}).setdefault("regime_ma", _to_int_or_default(regime_detection.get("regime_ma"), 60))

    _apply_ranking_cfg(strategy, sig)

    stock_trend = wb_cfg.get("stock_trend_filter") if isinstance(wb_cfg.get("stock_trend_filter"), dict) else {}
    if stock_trend:
        strategy.setdefault("params", {})["enable_v2_trend_filter"] = bool(stock_trend.get("enabled", False))
        strategy["params"]["v2_trend_short_ma"] = int(stock_trend.get("short_ma", 20))
        strategy["params"]["v2_trend_long_ma"] = int(stock_trend.get("long_ma", 60))

    sector_gate = wb_cfg.get("sector_gate") if isinstance(wb_cfg.get("sector_gate"), dict) else {}
    if sector_gate:
        strategy.setdefault("params", {})["enable_sector_gate"] = bool(sector_gate.get("enabled", False))
        strategy["params"]["sector_rank_window"] = int(sector_gate.get("rank_window", 60))
        strategy["params"]["sector_top_pct"] = float(sector_gate.get("top_pct", 0.30))

    pos_risk = wb_cfg.get("position_risk") if isinstance(wb_cfg.get("position_risk"), dict) else {}
    _apply_risk_budget_cfg(cfg, pos_risk, atr_stop)
    _apply_market_filter_cfg(cfg, pos_risk)
    _apply_benchmark_regime_cfg(cfg, wb_cfg, sig)
    _apply_breadth_cfg(cfg, pos_risk)
    _apply_sizing_cfg(cfg, wb_cfg)
    _apply_cost_cfg(cfg, wb_cfg)


def _apply_ranking_cfg(strategy: dict[str, Any], sig: dict[str, Any]) -> None:
    ranking = sig.get("ranking") if isinstance(sig.get("ranking"), dict) else {}
    if not ranking:
        return
    ranking_mode = str(ranking.get("score_source_mode") or "none").strip().lower()
    default_weights = {
        "residual_only": (0.5, 0.3, 0.2),
        "residual_quality": (0.8, 0.0, 0.2),
        "sector_quality": (0.5, 0.3, 0.2),
        "provider_final": (0.5, 0.3, 0.2),
        "quality_then_residual": (1.0, 0.0, 0.0),
        "leadership_then_residual": (1.0, 0.0, 0.0),
    }
    default_residual_weight, default_sector_weight, default_quality_weight = default_weights.get(
        ranking_mode,
        (0.5, 0.3, 0.2),
    )
    strategy.setdefault("params", {})["momentum_top_pct"] = float(ranking.get("momentum_top_pct", 0.0))
    strategy["params"]["ranking_mode"] = ranking_mode
    strategy["params"]["enable_residual_ranking"] = bool(
        ranking_mode in {"residual_only", "residual_quality", "provider_final", "quality_then_residual", "leadership_then_residual"}
    )
    strategy["params"]["enable_sector_quality_ranking"] = bool(
        ranking_mode in {"residual_quality", "sector_quality", "provider_final"}
    )
    strategy["params"]["source_aware_residual_mode"] = str(
        ranking.get("source_aware_residual_mode", "off") or "off"
    )
    strategy["params"]["residual_window"] = int(ranking.get("residual_window", 60) or 60)
    strategy["params"]["residual_benchmark_weight"] = float(ranking.get("residual_benchmark_weight", 0.5) or 0.0)
    strategy["params"]["residual_industry_weight"] = float(ranking.get("residual_industry_weight", 0.5) or 0.0)
    strategy["params"]["industry_relative_mode"] = str(
        ranking.get("industry_relative_mode", "sector_proxy") or "sector_proxy"
    )
    strategy["params"]["industry_relative_regime_mode"] = str(
        ranking.get("industry_relative_regime_mode", "off") or "off"
    )
    strategy["params"]["residual_weight_regime_mode"] = str(
        ranking.get("residual_weight_regime_mode", "off") or "off"
    )
    strategy["params"]["residual_benchmark_weight_fallback"] = float(
        ranking.get(
            "residual_benchmark_weight_fallback",
            strategy["params"]["residual_benchmark_weight"],
        )
        or 0.0
    )
    strategy["params"]["residual_industry_weight_fallback"] = float(
        ranking.get(
            "residual_industry_weight_fallback",
            strategy["params"]["residual_industry_weight"],
        )
        or 0.0
    )
    strategy["params"]["breakout_quality_gate_min_score"] = float(
        ranking.get("breakout_quality_gate_min_score", 0.55) or 0.55
    )
    strategy["params"]["breakout_quality_margin_cap_pct"] = float(
        ranking.get("breakout_quality_margin_cap_pct", 0.08) or 0.08
    )
    strategy["params"]["breakout_quality_fade_cap_pct"] = float(
        ranking.get("breakout_quality_fade_cap_pct", 0.035) or 0.035
    )
    strategy["params"]["breakout_quality_open_gap_cap_pct"] = float(
        ranking.get("breakout_quality_open_gap_cap_pct", 0.04) or 0.04
    )
    strategy["params"]["bull_breakout_quality_veto_enabled"] = bool(
        ranking.get("bull_breakout_quality_veto_enabled", False)
    )
    strategy["params"]["bull_breakout_quality_veto_min_residual_strength_score"] = float(
        ranking.get("bull_breakout_quality_veto_min_residual_strength_score", 0.0) or 0.0
    )
    strategy["params"]["bull_breakout_quality_veto_min_breakout_margin_score"] = float(
        ranking.get("bull_breakout_quality_veto_min_breakout_margin_score", 0.0) or 0.0
    )
    strategy["params"]["leadership_route_bucket_count"] = int(
        ranking.get("leadership_route_bucket_count", 3) or 3
    )
    strategy["params"]["residual_window_regime_mode"] = str(
        ranking.get("residual_window_regime_mode", "off") or "off"
    )
    strategy["params"]["residual_window_fallback"] = int(
        ranking.get("residual_window_fallback", strategy["params"]["residual_window"])
        or strategy["params"]["residual_window"]
    )
    strategy["params"]["residual_window_regime_fast_ma"] = int(
        ranking.get("residual_window_regime_fast_ma", 120) or 120
    )
    strategy["params"]["residual_window_regime_slow_ma"] = int(
        ranking.get("residual_window_regime_slow_ma", 200) or 200
    )
    strategy["params"]["residual_refine_mode"] = str(
        ranking.get("residual_refine_mode", "off") or "off"
    )
    strategy["params"]["residual_refine_weight"] = float(ranking.get("residual_refine_weight", 0.0) or 0.0)
    if ranking.get("industry_second_stage_min_industry_score") is not None:
        strategy["params"]["industry_second_stage_min_industry_score"] = float(
            ranking.get("industry_second_stage_min_industry_score") or 0.0
        )
    strategy["params"]["residual_weight"] = float(ranking.get("residual_weight", default_residual_weight))
    strategy["params"]["sector_weight"] = float(ranking.get("sector_weight", default_sector_weight))
    strategy["params"]["quality_weight"] = float(ranking.get("quality_weight", default_quality_weight))


def _apply_risk_budget_cfg(cfg: dict[str, Any], pos_risk: dict[str, Any], atr_stop: dict[str, Any]) -> None:
    rb_cfg = pos_risk.get("risk_budget") if isinstance(pos_risk.get("risk_budget"), dict) else {}
    if not rb_cfg:
        return
    risk_budget = cfg.setdefault("risk_budget", {})
    risk_budget["enabled"] = bool(rb_cfg.get("enabled", False))
    risk_budget["dd_reduce_pct"] = float(rb_cfg.get("dd_reduce_pct", 0.10))
    risk_budget["dd_reduce_scale"] = float(rb_cfg.get("dd_reduce_scale", 0.5))
    rb_atr_k = rb_cfg.get("atr_stop_k")
    if rb_atr_k is not None:
        risk_budget["atr_stop_k"] = float(rb_atr_k)
    elif atr_stop:
        risk_budget["atr_stop_k"] = float(atr_stop.get("k", 2.0))


def _apply_market_filter_cfg(cfg: dict[str, Any], pos_risk: dict[str, Any]) -> None:
    mf_cfg = pos_risk.get("market_filter") if isinstance(pos_risk.get("market_filter"), dict) else {}
    if not mf_cfg:
        return
    market_filter = cfg.setdefault("market_filter", {})
    market_filter["enabled"] = bool(mf_cfg.get("enabled", False))
    market_filter["long_ma_window"] = int(mf_cfg.get("long_ma_window", 200))
    market_filter["slope_window"] = int(mf_cfg.get("slope_window", 10))
    market_filter["slope_ma_period"] = int(mf_cfg.get("slope_ma_period", 50))
    market_filter["bull_multiplier"] = float(mf_cfg.get("bull_multiplier", 1.5))
    market_filter["light_multiplier"] = float(mf_cfg.get("light_multiplier", 0.6))
    if mf_cfg.get("trans_down_multiplier") is not None:
        market_filter["trans_down_multiplier"] = float(mf_cfg.get("trans_down_multiplier"))
    if mf_cfg.get("trans_up_multiplier") is not None:
        market_filter["trans_up_multiplier"] = float(mf_cfg.get("trans_up_multiplier"))
    if mf_cfg.get("bear_multiplier") is not None:
        market_filter["bear_multiplier"] = float(mf_cfg.get("bear_multiplier"))
    market_filter["freeze_trans_up_entries"] = bool(mf_cfg.get("freeze_trans_up_entries", False))
    market_filter["allow_trans_up_recovery_entries_when_benchmark_off"] = bool(
        mf_cfg.get("allow_trans_up_recovery_entries_when_benchmark_off", True)
    )
    market_filter["trans_up_recovery_entry_scale_when_benchmark_off"] = float(
        mf_cfg.get("trans_up_recovery_entry_scale_when_benchmark_off", 1.0) or 1.0
    )
    market_filter["trans_up_recovery_confirmed_top_up_scale_when_benchmark_on"] = float(
        mf_cfg.get("trans_up_recovery_confirmed_top_up_scale_when_benchmark_on", 0.0) or 0.0
    )
    market_filter["ema_light_fast"] = int(mf_cfg.get("ema_light_fast", 5))
    market_filter["ema_light_slow"] = int(mf_cfg.get("ema_light_slow", 20))


def _apply_benchmark_regime_cfg(cfg: dict[str, Any], wb_cfg: dict[str, Any], sig: dict[str, Any]) -> None:
    br_cfg = wb_cfg.get("benchmark_regime") if isinstance(wb_cfg.get("benchmark_regime"), dict) else {}
    if not br_cfg:
        regime_detection = sig.get("regime_detection") if isinstance(sig.get("regime_detection"), dict) else {}
        if regime_detection:
            regime_ma = int(regime_detection.get("regime_ma", 60))
            br_cfg = {
                "enabled": bool(regime_detection.get("enabled", False)),
                "fast_period": max(5, min(regime_ma, 120)),
                "slow_period": max(60, regime_ma),
                "slope_window": 5,
            }
    if not br_cfg:
        return
    benchmark_regime = cfg.setdefault("benchmark_regime", {})
    benchmark_regime["enabled"] = bool(br_cfg.get("enabled", False))
    benchmark_regime["fast_period"] = int(br_cfg.get("fast_period", 20))
    benchmark_regime["slow_period"] = int(br_cfg.get("slow_period", 60))
    benchmark_regime["slope_window"] = int(br_cfg.get("slope_window", 5))


def _apply_breadth_cfg(cfg: dict[str, Any], pos_risk: dict[str, Any]) -> None:
    breadth_cfg = pos_risk.get("breadth") if isinstance(pos_risk.get("breadth"), dict) else {}
    if not breadth_cfg:
        return
    breadth = cfg.setdefault("breadth", {})
    breadth["enabled"] = bool(breadth_cfg.get("enabled", False))
    breadth["score_type"] = str(breadth_cfg.get("score_type", "B"))
    breadth["mapping_mode"] = str(breadth_cfg.get("mapping_mode", "smooth"))
    breadth["min_positions"] = int(breadth_cfg.get("min_positions", 3))
    breadth["max_positions"] = int(breadth_cfg.get("max_positions", 15))
    breadth["step_high"] = float(breadth_cfg.get("step_high", 0.60))
    breadth["step_mid"] = float(breadth_cfg.get("step_mid", 0.45))
    breadth["smooth_lo"] = float(breadth_cfg.get("smooth_lo", 0.40))
    breadth["smooth_range"] = float(breadth_cfg.get("smooth_range", 0.20))
    breadth["ema_fast"] = int(breadth_cfg.get("ema_fast", 8))
    breadth["ema_slow"] = int(breadth_cfg.get("ema_slow", 25))
    breadth["mode"] = str(breadth_cfg.get("mode", "dynamic_maxpos"))
    breadth["gate_threshold"] = float(breadth_cfg.get("gate_threshold", 0.45))
    breadth["gate_quantile_window"] = int(breadth_cfg.get("gate_quantile_window", 252))
    breadth["gate_quantile_pct"] = float(breadth_cfg.get("gate_quantile_pct", 0.20))
    breadth["gate_persist_days"] = int(breadth_cfg.get("gate_persist_days", 3))
    breadth["size_scale_floor"] = float(breadth_cfg.get("size_scale_floor", 0.3))


def _apply_sizing_cfg(cfg: dict[str, Any], wb_cfg: dict[str, Any]) -> None:
    sizing_wb = wb_cfg.get("sizing") if isinstance(wb_cfg.get("sizing"), dict) else {}
    if not sizing_wb:
        return
    sizing = cfg.setdefault("sizing", {})
    weight_mode = str(sizing_wb.get("weight_mode", "equal"))
    sizing["weight_mode"] = weight_mode
    sizing["min_positions"] = int(sizing_wb.get("min_positions", 10))
    candidate_plan_mode = str(sizing_wb.get("candidate_plan_mode", "ranked"))
    sizing["candidate_plan_mode"] = candidate_plan_mode
    if candidate_plan_mode.strip().lower() == "cash_aware":
        sizing["cash_aware_search_top_n"] = int(sizing_wb.get("cash_aware_search_top_n", 12))
    elif sizing_wb.get("cash_aware_search_top_n") is not None:
        sizing["cash_aware_search_top_n"] = int(sizing_wb.get("cash_aware_search_top_n"))
    if weight_mode.strip().lower() == "mf_rank_tilt":
        sizing["tilt_strength"] = float(sizing_wb.get("tilt_strength", 0.15))
        sizing["tilt_top_n"] = int(sizing_wb.get("tilt_top_n", 3))
        sizing["tilt_bottom_n"] = int(sizing_wb.get("tilt_bottom_n", 2))
    elif weight_mode.strip().lower() == "score_weighted":
        sizing["score_weight_min_scale"] = float(sizing_wb.get("score_weight_min_scale", 0.75))
        sizing["score_weight_max_scale"] = float(sizing_wb.get("score_weight_max_scale", 1.25))
    else:
        if sizing_wb.get("tilt_strength") is not None:
            sizing["tilt_strength"] = float(sizing_wb.get("tilt_strength"))
        if sizing_wb.get("tilt_top_n") is not None:
            sizing["tilt_top_n"] = int(sizing_wb.get("tilt_top_n"))
        if sizing_wb.get("tilt_bottom_n") is not None:
            sizing["tilt_bottom_n"] = int(sizing_wb.get("tilt_bottom_n"))
        if sizing_wb.get("score_weight_min_scale") is not None:
            sizing["score_weight_min_scale"] = float(sizing_wb.get("score_weight_min_scale"))
        if sizing_wb.get("score_weight_max_scale") is not None:
            sizing["score_weight_max_scale"] = float(sizing_wb.get("score_weight_max_scale"))
    if sizing_wb.get("rotation_replace_enabled") is not None:
        sizing["rotation_replace_enabled"] = bool(sizing_wb.get("rotation_replace_enabled"))
    if sizing_wb.get("rotation_replace_only_strong_risk_on") is not None:
        sizing["rotation_replace_only_strong_risk_on"] = bool(sizing_wb.get("rotation_replace_only_strong_risk_on"))
    if sizing_wb.get("rotation_replace_max_swaps_per_day") is not None:
        sizing["rotation_replace_max_swaps_per_day"] = int(sizing_wb.get("rotation_replace_max_swaps_per_day"))
    if sizing_wb.get("rotation_replace_candidate_top_n") is not None:
        sizing["rotation_replace_candidate_top_n"] = int(sizing_wb.get("rotation_replace_candidate_top_n"))
    if sizing_wb.get("rotation_replace_min_score_gap") is not None:
        sizing["rotation_replace_min_score_gap"] = float(sizing_wb.get("rotation_replace_min_score_gap"))


def _apply_cost_cfg(cfg: dict[str, Any], wb_cfg: dict[str, Any]) -> None:
    cost_cfg = wb_cfg.get("costs") if isinstance(wb_cfg.get("costs"), dict) else {}
    if not cost_cfg:
        return
    costs = cfg.setdefault("costs", {})
    for key in ("commission_rate", "commission_min", "stamp_tax_rate", "slippage_bps"):
        if key in cost_cfg:
            costs[key] = float(cost_cfg[key])
    if "slippage_mode" in cost_cfg:
        costs["slippage_mode"] = str(cost_cfg["slippage_mode"])
