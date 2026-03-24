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
                }
            ]
        )
    )

    row = projected.iloc[0].to_dict()
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
    assert json.loads(row["diagnostics_input_json"])["raw_after_slot_filter_count"] == 2
    assert row["regime_engine"] == "market_regime_framework"
    assert row["regime_confidence"] == 0.82
    assert row["regime_duration_bars"] == 12
    assert row["regime_transition_reason"] == "TREND_BLOCK_CONFIRMED"
    assert json.loads(row["feature_availability_json"])["risk_block"] is True
    assert json.loads(row["governor_budget_json"])["contract_version"] == "cn_a_governor_budget@1"
