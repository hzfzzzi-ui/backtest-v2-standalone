from __future__ import annotations

import json
import pandas as pd

from backend.core.tools.experiment_runner import _project_daily_csv_schema


def test_project_daily_csv_schema_preserves_sorting_diagnostics() -> None:
    projected = _project_daily_csv_schema(
        pd.DataFrame(
            [
                {
                    "date": "2026-03-02",
                    "nav": 1.0,
                    "cash": 1.0,
                    "positions_count": 1,
                    "positions_count_end_of_day": 1,
                    "daily_return": 0.01,
                    "drawdown": -0.02,
                    "gross_exposure": 0.9,
                    "turnover_pct": 0.1,
                    "top5_positions_json": "[]",
                    "candidates_count": 3,
                    "selected_count": 2,
                    "top5_selected_strength_json": "[]",
                    "top5_rejected_strength_json": "[]",
                    "buy_slots_before_buy": 2,
                    "buy_slots_after_sell": 2,
                    "raw_buy_signal_count": 3,
                    "raw_alpha_signal_count": 3,
                    "composed_buy_signal_count": 2,
                    "composed_sell_signal_count": 1,
                    "buy_candidate_count": 3,
                    "after_held_filter_count": 3,
                    "after_slot_filter_count": 2,
                    "after_cash_lot_count": 2,
                    "diagnostics_input_json": json.dumps(
                        {
                            "route_id": "strict_inline_runtime",
                            "candidates_count": 3,
                            "selected_count": 2,
                            "raw_buy_signal_count": 3,
                            "raw_buy_candidate_count": 3,
                            "raw_after_held_filter_count": 3,
                            "raw_after_slot_filter_count": 2,
                            "raw_after_cash_lot_count": 2,
                            "diagnostics": {
                                "etf_beta_formal_view": {
                                    "target_exposure": 0.2,
                                    "min_deployable_exposure": 0.1,
                                    "target_exposure_source": "fixed",
                                    "min_deployable_exposure_source": "fixed",
                                    "target_selected_count": 1,
                                },
                                "etf_beta_research_view": {
                                    "strategic_floor_cap": 0.12,
                                    "tactical_overlay_cap": 0.06,
                                    "limited_defense_cap": 0.02,
                                    "deployment_pace": 0.03,
                                    "bull_partial_overlay_pace_ratio": 0.5,
                                    "bull_pace_mode": "partial_overlay_v1",
                                    "pace_policy_gap": 0.17,
                                    "pace_policy_reason_code": "ETF_BETA_DEPLOYMENT_PACE_FLOOR_ONLY",
                                    "rebalance_timing_gap": 0.03,
                                    "rebalance_timing_reason_code": "ETF_BETA_AWAIT_MONTHLY_REBALANCE",
                                    "execution_residual_gap": 0.0,
                                    "gap_primary_owner": "pace_policy",
                                    "hard_block_flags": [],
                                    "deployability_gap": 0.04,
                                    "execution_path": "trans_up_state_change_redeploy",
                                    "trans_up_contract_mode": "single_seat_core_recovery",
                                    "trans_up_single_seat_core_recovery": True,
                                    "trans_up_redeploy_active": True,
                                    "trans_up_redeploy_reason_code": "ETF_BETA_TRANS_UP_REDEPLOY_ACTIVE",
                                    "trans_up_redeploy_reject_reason": "",
                                    "trans_up_redeploy_floor_gap": 0.0527,
                                    "trans_up_redeploy_edge_from_state": "RISK_OFF",
                                },
                            },
                        },
                        ensure_ascii=False,
                    ),
                    "positions_before_sell": 1,
                    "sells_executed_count": 0,
                    "positions_after_sell": 1,
                    "buy_slots_calculated": 2,
                    "candidates_after_held_filter_count": 3,
                    "sorting_triggered": True,
                    "mean_order_value_scale": 1.2,
                    "weak_trend_buy_rate": 0.0,
                    "strong_trend_buy_rate": 1.0,
                    "mf_rank_triggered": 1,
                    "mf_rank_applied": 1,
                    "mf_candidates_when_triggered": 3,
                    "mf_topk_reject_count": 1,
                    "mf_concentrated_selected_count": 1,
                    "mf_gate_on": 1,
                    "strong_risk_on": 1,
                    "mf_rank_suppressed_by_strong_gate": 0,
                    "same_symbol_conflict_count": 0,
                    "sleeve_budget_reject_count": 0,
                    "source_only_exit_count": 0,
                    "global_risk_override_count": 0,
                    "trend_slope_block_count": 0,
                    "trend_continuity_block_count": 0,
                    "base_trend_on_rate": 1.0,
                    "quality_trend_on_rate": 1.0,
                    "effective_max_positions": 10,
                    "dd_state": "NORMAL",
                    "market_state": "BULL",
                    "trade_mode": "MAIN",
                    "benchmark_regime_on": True,
                    "regime_engine": "market_regime_framework",
                    "regime_confidence": 0.82,
                    "regime_duration_bars": 12,
                    "regime_transition_reason": "TREND_BLOCK_CONFIRMED",
                    "feature_availability_json": json.dumps(
                        {
                            "trend_block": True,
                            "risk_block": True,
                            "breadth_block": True,
                            "participation_block": True,
                        },
                        ensure_ascii=False,
                    ),
                    "governor_budget_json": json.dumps(
                        {
                            "contract_version": "cn_a_governor_budget@1",
                            "total_risk_budget": 0.82,
                            "total_exposure_cap": 1.0,
                        },
                        ensure_ascii=False,
                    ),
                    "etf_target_exposure": 0.2,
                    "etf_min_deployable_exposure": 0.1,
                    "etf_target_exposure_source": "fixed",
                    "etf_min_deployable_exposure_source": "fixed",
                    "etf_actual_exposure": 0.16,
                    "etf_actual_risk_exposure": 0.15,
                    "etf_actual_fallback_exposure": 0.01,
                    "etf_actual_other_exposure": 0.0,
                    "etf_actual_core_exposure": 0.1,
                    "etf_actual_satellite_exposure": 0.04,
                    "etf_actual_defense_exposure": 0.02,
                }
            ]
        )
    )

    row = projected.iloc[0].to_dict()
    diagnostics_input = json.loads(row["diagnostics_input_json"])
    formal_view = diagnostics_input["diagnostics"]["etf_beta_formal_view"]
    research_view = diagnostics_input["diagnostics"]["etf_beta_research_view"]
    assert row["sorting_triggered"] is True
    assert row["mf_rank_triggered"] == 1
    assert row["mf_rank_applied"] == 1
    assert row["mf_candidates_when_triggered"] == 3
    assert row["mf_topk_reject_count"] == 1
    assert row["mf_concentrated_selected_count"] == 1
    assert row["mf_gate_on"] == 1
    assert row["strong_risk_on"] == 1
    assert row["mf_rank_suppressed_by_strong_gate"] == 0
    assert row["after_slot_filter_count"] == 2
    assert row["after_cash_lot_count"] == 2
    assert row["candidates_after_held_filter_count"] == 3
    assert diagnostics_input["raw_after_slot_filter_count"] == 2
    assert row["regime_engine"] == "market_regime_framework"
    assert row["regime_confidence"] == 0.82
    assert row["regime_duration_bars"] == 12
    assert row["regime_transition_reason"] == "TREND_BLOCK_CONFIRMED"
    assert json.loads(row["feature_availability_json"])["risk_block"] is True
    assert json.loads(row["governor_budget_json"])["contract_version"] == "cn_a_governor_budget@1"
    assert row["etf_target_exposure"] == 0.2
    assert row["etf_target_exposure_source"] == "fixed"
    assert row["etf_actual_risk_exposure"] == 0.15
    assert row["etf_actual_core_exposure"] == 0.1
    assert row["etf_actual_satellite_exposure"] == 0.04
    assert row["etf_actual_defense_exposure"] == 0.02
    assert "etf_strategic_floor_target" not in row
    assert "etf_deployment_pace" not in row
    assert "etf_execution_path" not in row
    assert formal_view["target_exposure"] == 0.2
    assert formal_view["min_deployable_exposure"] == 0.1
    assert research_view["strategic_floor_cap"] == 0.12
    assert research_view["tactical_overlay_cap"] == 0.06
    assert research_view["limited_defense_cap"] == 0.02
    assert research_view["deployment_pace"] == 0.03
    assert research_view["bull_partial_overlay_pace_ratio"] == 0.5
    assert research_view["bull_pace_mode"] == "partial_overlay_v1"
    assert research_view["pace_policy_gap"] == 0.17
    assert research_view["pace_policy_reason_code"] == "ETF_BETA_DEPLOYMENT_PACE_FLOOR_ONLY"
    assert research_view["rebalance_timing_gap"] == 0.03
    assert research_view["rebalance_timing_reason_code"] == "ETF_BETA_AWAIT_MONTHLY_REBALANCE"
    assert research_view["execution_residual_gap"] == 0.0
    assert research_view["gap_primary_owner"] == "pace_policy"
    assert research_view["hard_block_flags"] == []
    assert research_view["deployability_gap"] == 0.04
    assert research_view["execution_path"] == "trans_up_state_change_redeploy"
    assert research_view["trans_up_contract_mode"] == "single_seat_core_recovery"
    assert research_view["trans_up_single_seat_core_recovery"] is True
    assert research_view["trans_up_redeploy_active"] is True
    assert research_view["trans_up_redeploy_reason_code"] == "ETF_BETA_TRANS_UP_REDEPLOY_ACTIVE"
    assert research_view["trans_up_redeploy_reject_reason"] == ""
    assert research_view["trans_up_redeploy_floor_gap"] == 0.0527
    assert research_view["trans_up_redeploy_edge_from_state"] == "RISK_OFF"
