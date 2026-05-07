from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from backend.core.engine_vector.breakout_signal_provider import BreakoutTrendProvider
from backend.core.engine_vector.cn_etf_beta_signal_provider import CNETFBetaSignalProvider
from backend.core.engine_vector.etf_beta.selection import (
    _compress_research_mainline_live_targets,
    _resolve_standalone_live_seat_symbols,
)
from backend.core.engine_vector.signal_provider import DayContext


def _extract_etf_views(day_signals):
    diagnostics = day_signals.diagnostics
    return diagnostics["etf_beta_formal_view"], diagnostics["etf_beta_research_view"]


def _build_formal_trans_up_redeploy_provider(
    *,
    previous_state: str = "RISK_OFF",
    current_state: str = "TRANS_UP",
    rebalance_day: bool = False,
    hard_blocked: bool = False,
) -> tuple[CNETFBetaSignalProvider, list[date]]:
    trading_days = [date(2026, 3, 19), date(2026, 3, 20)]
    provider = CNETFBetaSignalProvider()
    provider._mx = SimpleNamespace(
        dates=trading_days,
        symbols=["510300.sh", "512100.sh", "512890.sh"],
        close=np.array(
            [
                [4.0, 3.0, 2.0],
                [4.1, 3.1, 2.05],
            ],
            dtype=float,
        ),
    )
    provider._feats = SimpleNamespace(
        trend_fast_ma=np.array(
            [
                [3.9, 2.9, 1.98],
                [4.0, 3.0, 2.0],
            ],
            dtype=float,
        )
    )
    provider._sym_to_col = {
        "sh510300": 0,
        "sh512100": 1,
        "sh512890": 2,
    }
    provider._effective_state_5_arr = np.array([previous_state, current_state], dtype=object)
    provider._trade_mode_name_arr = np.array(["TREND_LIGHT", "TREND_LIGHT"], dtype=object)
    provider._etf_beta_slot_cap_arr = np.array([1, 1], dtype=np.int32)
    provider._etf_beta_rebalance_flag_arr = np.array([False, rebalance_day], dtype=bool)
    provider._etf_beta_formal_scope_symbols = ["510300.SH", "512100.SH", "511010.SH"]
    provider._etf_beta_eligible_symbols_arr = np.array(
        [
            ["510300.SH", "512100.SH", "511010.SH"],
            ["510300.SH", "512100.SH", "511010.SH"],
        ],
        dtype=object,
    )
    provider._etf_beta_selected_symbols_arr = np.array(
        [
            ["510300.SH"],
            ["510300.SH"],
        ],
        dtype=object,
    )
    provider._etf_beta_selection_reason_codes_arr = np.array(
        [
            {"510300.SH": ["PHASE1_FORMAL_SCOPE", "STATE::TRANS_UP"]},
            {"510300.SH": ["PHASE1_FORMAL_SCOPE", "STATE::TRANS_UP"]},
        ],
        dtype=object,
    )
    runtime_reason_codes = [
        "ETF_BETA_STRATEGIC_BETA_STABILIZER_ACTIVE",
        "ETF_BETA_BOUNDARY_POLICY::FORMAL_PHASE1_DOCUMENT_ALIGNED_V1",
        "ETF_BETA_LOCAL_BOUNDARY_STATE::ACTIVE",
    ]
    if not rebalance_day:
        runtime_reason_codes.append("ETF_BETA_AWAIT_MONTHLY_REBALANCE")
    if hard_blocked:
        runtime_reason_codes.append("ETF_BETA_PHASE1_GOVERNOR_HARD_BLOCK")
    provider._etf_beta_runtime_reason_codes_arr = np.array([list(runtime_reason_codes), list(runtime_reason_codes)], dtype=object)
    provider._etf_beta_vol_target_info_arr = np.array([{}, {}], dtype=object)
    provider._etf_beta_target_exposure_arr = np.array([0.1, 0.1], dtype=float)
    provider._etf_beta_target_exposure_source_arr = np.array(["governor_sleeve_budget", "governor_sleeve_budget"], dtype=object)
    provider._etf_beta_min_deployable_exposure_arr = np.array([0.0, 0.0], dtype=float)
    provider._etf_beta_min_deployable_exposure_source_arr = np.array(["phase1_allocation_engine", "phase1_allocation_engine"], dtype=object)
    provider._etf_beta_target_selected_count_arr = np.array([1, 1], dtype=np.int32)
    provider._etf_beta_target_exposure_per_symbol_arr = np.array([0.0527, 0.0527], dtype=float)
    provider._etf_beta_target_actual_exposure_arr = np.array([0.1, 0.1], dtype=float)
    provider._etf_beta_target_deployability_gap_arr = np.array([0.0, 0.0], dtype=float)
    provider._etf_beta_fallback_allowed_arr = np.array([False, False], dtype=bool)
    provider._etf_beta_exposure_policy_family_arr = np.array(["phase1_governed_allocation_v1", "phase1_governed_allocation_v1"], dtype=object)
    provider._etf_beta_policy_scope_arr = np.array(["broad_based_only", "broad_based_only"], dtype=object)
    provider._etf_beta_broad_based_only_arr = np.array([True, True], dtype=bool)
    provider._etf_beta_layering_policy_arr = np.array(["none", "none"], dtype=object)
    provider._etf_beta_layering_band_arr = np.array(["", ""], dtype=object)
    provider._etf_beta_layering_active_arr = np.array([False, False], dtype=bool)
    provider._etf_beta_layering_reason_codes_arr = np.array([[], []], dtype=object)
    provider._etf_beta_target_selected_count_source_arr = np.array(["input", "input"], dtype=object)
    provider._etf_beta_fallback_allowed_source_arr = np.array(["", ""], dtype=object)
    provider._etf_beta_core_slot_selected_symbol_arr = np.array(["", ""], dtype=object)
    provider._etf_beta_growth_slot_selected_symbol_arr = np.array(["", ""], dtype=object)
    provider._etf_beta_slot_selection_reason_codes_arr = np.array([{}, {}], dtype=object)
    provider._etf_beta_slot_under_deploy_reason_codes_arr = np.array([{}, {}], dtype=object)
    provider._etf_beta_core_slot_target_exposure_arr = np.array([np.nan, np.nan], dtype=float)
    provider._etf_beta_growth_slot_target_exposure_arr = np.array([np.nan, np.nan], dtype=float)
    provider._etf_beta_core_slot_target_actual_exposure_arr = np.array([np.nan, np.nan], dtype=float)
    provider._etf_beta_growth_slot_target_actual_exposure_arr = np.array([np.nan, np.nan], dtype=float)
    provider._etf_beta_absolute_filter_reject_count_arr = np.array([0, 0], dtype=np.int32)
    provider._etf_beta_absolute_filter_reject_reason_counts_arr = np.array([{}, {}], dtype=object)
    provider._etf_beta_selection_chain_winner_counts_arr = np.array([{}, {}], dtype=object)
    provider._etf_beta_selection_chain_reject_reason_counts_arr = np.array([{}, {}], dtype=object)
    provider._etf_beta_targets_arr = np.array(
        [
            {"510300.SH": 0.0527},
            {"510300.SH": 0.0527},
        ],
        dtype=object,
    )
    provider._etf_beta_requested_budget_arr = np.array([0.1, 0.1], dtype=float)
    provider._etf_beta_applied_budget_arr = np.array([0.1, 0.1], dtype=float)
    provider._etf_beta_cash_weight_arr = np.array([0.0, 0.0], dtype=float)
    provider._etf_beta_defense_weight_arr = np.array([0.005, 0.005], dtype=float)
    provider._etf_beta_equity_core_bucket_arr = np.array([0.85, 0.85], dtype=float)
    provider._etf_beta_defense_tilt_bucket_arr = np.array([0.05, 0.05], dtype=float)
    provider._etf_beta_cash_buffer_bucket_arr = np.array([0.10, 0.10], dtype=float)
    provider._etf_beta_strategic_floor_cap_arr = np.array([0.0135, 0.0527], dtype=float)
    provider._etf_beta_tactical_overlay_cap_arr = np.array([0.0, 0.0323], dtype=float)
    provider._etf_beta_limited_defense_cap_arr = np.array([0.015, 0.005], dtype=float)
    provider._etf_beta_deployment_pace_arr = np.array([0.0, 0.0527], dtype=float)
    provider._etf_beta_pace_policy_gap_arr = np.array([0.1, 0.0473], dtype=float)
    provider._etf_beta_pace_policy_reason_code_arr = np.array(["ETF_BETA_DEPLOYMENT_PACE_FLOOR_ONLY", "ETF_BETA_DEPLOYMENT_PACE_FLOOR_ONLY"], dtype=object)
    provider._etf_beta_pace_policy_mode_arr = np.array(["floor_only_between_rebalances", "floor_only_between_rebalances"], dtype=object)
    provider._etf_beta_bull_partial_overlay_pace_ratio_arr = np.array([np.nan, np.nan], dtype=float)
    provider._etf_beta_bull_pace_mode_arr = np.array(["", ""], dtype=object)
    provider._etf_beta_hard_block_flags_arr = np.array([[], ["GOVERNOR_ALLOW_NEW_RISK_FALSE"] if hard_blocked else []], dtype=object)
    provider._etf_beta_core_accumulator_symbols_arr = np.array([["510300.SH"], ["510300.SH"]], dtype=object)
    provider._etf_beta_tactical_satellite_symbols_arr = np.array([["512100.SH"], ["512100.SH"]], dtype=object)
    provider._etf_beta_limited_defense_symbols_arr = np.array([["511010.SH"], ["511010.SH"]], dtype=object)
    provider._etf_beta_symbol_role_map_arr = np.array(
        [
            {"510300.SH": "core_accumulator", "512100.SH": "tactical_satellite", "511010.SH": "limited_defense"},
            {"510300.SH": "core_accumulator", "512100.SH": "tactical_satellite", "511010.SH": "limited_defense"},
        ],
        dtype=object,
    )
    provider._etf_beta_allocation_reason_codes_arr = np.array(
        [
            ["PHASE1_ALLOCATION_ENGINE::THREE_BUCKET"],
            ["PHASE1_ALLOCATION_ENGINE::THREE_BUCKET"],
        ],
        dtype=object,
    )
    provider._etf_beta_strategy_role = "strategic_beta_stabilizer"
    provider._etf_beta_local_policy_mode = "phase1_bucket_allocation"
    provider._etf_beta_boundary_policy_mode = "formal_phase1_document_aligned_v1"
    provider._etf_beta_governor_boundary_mode = "consume_governor_sleeve_budget"
    provider._etf_beta_rule_family = "phase1_allocation_engine_v1"
    provider._etf_beta_rebalance_frequency = "monthly"
    provider._etf_beta_bull_partial_overlay_pace_ratio = 0.5
    provider._etf_beta_candidate_pool_symbols = ["510300.SH", "512100.SH", "511010.SH"]
    provider._etf_beta_candidate_pool_coverage_summary = {}
    provider._etf_beta_candidate_pool_reject_reason_counts = {}
    return provider, trading_days


def _build_standalone_inter_rebalance_provider(
    *,
    previous_state: str,
    current_state: str,
    deployment_pace: float,
    target_exposure: float,
    min_deployable_exposure: float,
    selected_symbols: list[str],
    targets: dict[str, float],
    fallback_mode: str = "none",
    fallback_symbol: str | None = None,
) -> tuple[CNETFBetaSignalProvider, list[date]]:
    trading_days = [date(2026, 3, 19), date(2026, 3, 20)]
    provider = CNETFBetaSignalProvider()
    provider._mx = SimpleNamespace(
        dates=trading_days,
        symbols=["510300.sh", "588000.sh", "511010.sh"],
        close=np.array(
            [
                [4.0, 2.5, 3.1],
                [4.1, 2.6, 3.1],
            ],
            dtype=float,
        ),
    )
    provider._feats = SimpleNamespace(
        trend_fast_ma=np.array(
            [
                [3.9, 2.4, 3.0],
                [4.0, 2.5, 3.0],
            ],
            dtype=float,
        )
    )
    provider._sym_to_col = {
        "sh510300": 0,
        "sh588000": 1,
        "sh511010": 2,
    }
    provider._effective_state_5_arr = np.array([previous_state, current_state], dtype=object)
    provider._trade_mode_name_arr = np.array(["TREND_LIGHT", "TREND_LIGHT"], dtype=object)
    provider._etf_beta_slot_cap_arr = np.array([max(1, len(selected_symbols)), max(1, len(selected_symbols))], dtype=np.int32)
    provider._etf_beta_rebalance_flag_arr = np.array([False, False], dtype=bool)
    provider._etf_beta_formal_scope_symbols = ["510300.SH", "588000.SH", "511010.SH"]
    provider._etf_beta_eligible_symbols_arr = np.array([selected_symbols, selected_symbols], dtype=object)
    provider._etf_beta_selected_symbols_arr = np.array([selected_symbols, selected_symbols], dtype=object)
    provider._etf_beta_selection_reason_codes_arr = np.array(
        [
            {symbol: [f"STATE::{current_state}", "SELECTION_PROFILE::CORE_GROWTH_SLOT"] for symbol in selected_symbols},
            {symbol: [f"STATE::{current_state}", "SELECTION_PROFILE::CORE_GROWTH_SLOT"] for symbol in selected_symbols},
        ],
        dtype=object,
    )
    provider._etf_beta_runtime_reason_codes_arr = np.array(
        [
            ["ETF_BETA_STANDALONE_MAINLINE_ACTIVE", "ETF_BETA_AWAIT_BIWEEKLY_REBALANCE"],
            ["ETF_BETA_STANDALONE_MAINLINE_ACTIVE", "ETF_BETA_AWAIT_BIWEEKLY_REBALANCE"],
        ],
        dtype=object,
    )
    provider._etf_beta_vol_target_info_arr = np.array([{}, {}], dtype=object)
    provider._etf_beta_target_exposure_arr = np.array([target_exposure, target_exposure], dtype=float)
    provider._etf_beta_target_exposure_source_arr = np.array(["state_map", "state_map"], dtype=object)
    provider._etf_beta_min_deployable_exposure_arr = np.array([min_deployable_exposure, min_deployable_exposure], dtype=float)
    provider._etf_beta_min_deployable_exposure_source_arr = np.array(["state_map", "state_map"], dtype=object)
    provider._etf_beta_target_selected_count_arr = np.array([len(selected_symbols), len(selected_symbols)], dtype=np.int32)
    provider._etf_beta_target_exposure_per_symbol_arr = np.array(
        [
            target_exposure / max(len(selected_symbols), 1),
            target_exposure / max(len(selected_symbols), 1),
        ],
        dtype=float,
    )
    provider._etf_beta_target_actual_exposure_arr = np.array([target_exposure, target_exposure], dtype=float)
    provider._etf_beta_target_deployability_gap_arr = np.array([0.0, 0.0], dtype=float)
    provider._etf_beta_fallback_allowed_arr = np.array([True, True], dtype=bool)
    provider._etf_beta_exposure_policy_family_arr = np.array(
        ["broad_based_standalone_mainline_v1", "broad_based_standalone_mainline_v1"],
        dtype=object,
    )
    provider._etf_beta_policy_scope_arr = np.array(["general", "general"], dtype=object)
    provider._etf_beta_broad_based_only_arr = np.array([False, False], dtype=bool)
    provider._etf_beta_layering_policy_arr = np.array(["light_trans_down_accumulate", "light_trans_down_accumulate"], dtype=object)
    provider._etf_beta_layering_band_arr = np.array(["", ""], dtype=object)
    provider._etf_beta_layering_active_arr = np.array([False, False], dtype=bool)
    provider._etf_beta_layering_reason_codes_arr = np.array([[], []], dtype=object)
    provider._etf_beta_target_selected_count_source_arr = np.array(["state_map", "state_map"], dtype=object)
    provider._etf_beta_fallback_allowed_source_arr = np.array(["state_map", "state_map"], dtype=object)
    provider._etf_beta_core_slot_selected_symbol_arr = np.array(["510300.SH", "510300.SH"], dtype=object)
    provider._etf_beta_growth_slot_selected_symbol_arr = np.array(["588000.SH", "588000.SH"], dtype=object)
    provider._etf_beta_slot_selection_reason_codes_arr = np.array([{}, {}], dtype=object)
    provider._etf_beta_slot_under_deploy_reason_codes_arr = np.array([{}, {}], dtype=object)
    provider._etf_beta_core_slot_target_exposure_arr = np.array([target_exposure / 2.0, target_exposure / 2.0], dtype=float)
    provider._etf_beta_growth_slot_target_exposure_arr = np.array([target_exposure / 2.0, target_exposure / 2.0], dtype=float)
    provider._etf_beta_core_slot_target_actual_exposure_arr = np.array([target_exposure / 2.0, target_exposure / 2.0], dtype=float)
    provider._etf_beta_growth_slot_target_actual_exposure_arr = np.array([target_exposure / 2.0, target_exposure / 2.0], dtype=float)
    provider._etf_beta_absolute_filter_reject_count_arr = np.array([0, 0], dtype=np.int32)
    provider._etf_beta_absolute_filter_reject_reason_counts_arr = np.array([{}, {}], dtype=object)
    provider._etf_beta_selection_chain_winner_counts_arr = np.array([{}, {}], dtype=object)
    provider._etf_beta_selection_chain_reject_reason_counts_arr = np.array([{}, {}], dtype=object)
    provider._etf_beta_targets_arr = np.array([targets, targets], dtype=object)
    provider._etf_beta_requested_budget_arr = np.array([target_exposure, target_exposure], dtype=float)
    provider._etf_beta_applied_budget_arr = np.array([target_exposure, target_exposure], dtype=float)
    provider._etf_beta_cash_weight_arr = np.array([0.0, 0.0], dtype=float)
    provider._etf_beta_defense_weight_arr = np.array([0.0, 0.0], dtype=float)
    provider._etf_beta_equity_core_bucket_arr = np.array([1.0, 1.0], dtype=float)
    provider._etf_beta_defense_tilt_bucket_arr = np.array([0.0, 0.0], dtype=float)
    provider._etf_beta_cash_buffer_bucket_arr = np.array([0.0, 0.0], dtype=float)
    provider._etf_beta_strategic_floor_cap_arr = np.array([deployment_pace, deployment_pace], dtype=float)
    provider._etf_beta_tactical_overlay_cap_arr = np.array([0.0, 0.0], dtype=float)
    provider._etf_beta_limited_defense_cap_arr = np.array([0.0, 0.0], dtype=float)
    provider._etf_beta_deployment_pace_arr = np.array([deployment_pace, deployment_pace], dtype=float)
    provider._etf_beta_pace_policy_gap_arr = np.array(
        [max(target_exposure - deployment_pace, 0.0), max(target_exposure - deployment_pace, 0.0)],
        dtype=float,
    )
    provider._etf_beta_pace_policy_reason_code_arr = np.array(["", ""], dtype=object)
    provider._etf_beta_pace_policy_mode_arr = np.array(["", ""], dtype=object)
    provider._etf_beta_bull_partial_overlay_pace_ratio_arr = np.array([np.nan, np.nan], dtype=float)
    provider._etf_beta_bull_pace_mode_arr = np.array(["", ""], dtype=object)
    provider._etf_beta_hard_block_flags_arr = np.array([[], []], dtype=object)
    provider._etf_beta_core_accumulator_symbols_arr = np.array([["510300.SH"], ["510300.SH"]], dtype=object)
    provider._etf_beta_tactical_satellite_symbols_arr = np.array([["588000.SH"], ["588000.SH"]], dtype=object)
    provider._etf_beta_limited_defense_symbols_arr = np.array([["511010.SH"], ["511010.SH"]], dtype=object)
    provider._etf_beta_symbol_role_map_arr = np.array(
        [
            {"510300.SH": "core_accumulator", "588000.SH": "tactical_satellite", "511010.SH": "limited_defense"},
            {"510300.SH": "core_accumulator", "588000.SH": "tactical_satellite", "511010.SH": "limited_defense"},
        ],
        dtype=object,
    )
    provider._etf_beta_allocation_reason_codes_arr = np.array([[], []], dtype=object)
    provider._etf_beta_strategy_role = "governed_broad_based_standalone_mainline"
    provider._etf_beta_local_policy_mode = "broad_based_rotation_mainline"
    provider._etf_beta_boundary_policy_mode = "legacy_state_slot_caps_v1"
    provider._etf_beta_governor_boundary_mode = "consume_governor_state_and_budget"
    provider._etf_beta_rule_family = "broad_based_rotation_template_a"
    provider._etf_beta_rebalance_frequency = "biweekly"
    provider._etf_beta_bull_partial_overlay_pace_ratio = 0.0
    provider._etf_beta_fallback_mode = fallback_mode
    provider._etf_beta_fallback_symbol = (
        f"sh{str(fallback_symbol).strip()[:6]}" if fallback_symbol and str(fallback_symbol).strip().upper().endswith(".SH")
        else f"sz{str(fallback_symbol).strip()[:6]}" if fallback_symbol and str(fallback_symbol).strip().upper().endswith(".SZ")
        else ""
    )
    provider._etf_beta_candidate_pool_symbols = ["510300.SH", "588000.SH", "511010.SH"]
    provider._etf_beta_candidate_pool_coverage_summary = {}
    provider._etf_beta_candidate_pool_reject_reason_counts = {}
    return provider, trading_days


def test_cn_etf_beta_day_signals_rebalance_into_runtime_selection() -> None:
    trading_day = date(2026, 3, 20)
    provider = CNETFBetaSignalProvider()
    provider._mx = SimpleNamespace(
        symbols=["sh510300", "sh510500"],
        close=np.array([[4.0, 6.0]], dtype=float),
        dates=[trading_day],
    )
    provider._feats = SimpleNamespace(
        trend_fast_ma=np.array([[3.5, 5.5]], dtype=float),
    )
    provider._sym_to_col = {"sh510300": 0, "sh510500": 1}
    provider._effective_state_5_arr = np.array(["BULL"], dtype=object)
    provider._trade_mode_name_arr = np.array(["TREND_MAIN"], dtype=object)
    provider._etf_beta_slot_cap_arr = np.array([1], dtype=np.int32)
    provider._etf_beta_rebalance_flag_arr = np.array([True], dtype=bool)
    provider._etf_beta_formal_scope_symbols = ["510300.SH", "510500.SH"]
    provider._etf_beta_eligible_symbols_arr = np.array([["510300.SH", "510500.SH"]], dtype=object)
    provider._etf_beta_selected_symbols_arr = np.array([["510300.SH"]], dtype=object)
    provider._etf_beta_selection_reason_codes_arr = np.array(
        [{"510300.SH": ["ETF_BETA_CORE_SCOPE", "ABSOLUTE_TREND_PASS"]}],
        dtype=object,
    )
    provider._etf_beta_runtime_reason_codes_arr = np.array([["ETF_BETA_WEEKLY_SELECTION_ACTIVE"]], dtype=object)
    provider._etf_beta_target_exposure_arr = np.array([0.2], dtype=float)
    provider._etf_beta_target_exposure_source_arr = np.array(["fixed"], dtype=object)
    provider._etf_beta_min_deployable_exposure_arr = np.array([0.1], dtype=float)
    provider._etf_beta_min_deployable_exposure_source_arr = np.array(["fixed"], dtype=object)
    provider._etf_beta_target_selected_count_arr = np.array([1], dtype=np.int32)
    provider._etf_beta_target_exposure_per_symbol_arr = np.array([0.2], dtype=float)
    provider._etf_beta_target_actual_exposure_arr = np.array([0.2], dtype=float)
    provider._etf_beta_target_deployability_gap_arr = np.array([0.0], dtype=float)
    provider._etf_beta_fallback_allowed_arr = np.array([False], dtype=bool)
    provider._etf_beta_strategy_role = "auxiliary_beta_sleeve"
    provider._etf_beta_local_policy_mode = "legacy_beta_selection"
    provider._etf_beta_rebalance_frequency = "weekly"

    ctx = DayContext(
        positions={"sh510500": 100},
        position_avg_cost={"sh510500": 5.0},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=1,
        close_idx={(trading_day, "sh510500"): 6.0},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )

    day_signals = provider.day_signals(trading_day, 0, ctx)

    assert [signal.symbol for signal in day_signals.sell_signals] == ["sh510500"]
    assert [signal.reason_code for signal in day_signals.sell_signals] == ["ETF_BETA_REBALANCE_EXIT"]
    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh510300"]
    assert [signal.reason_code for signal in day_signals.buy_signals] == ["ETF_BETA_WEEKLY_RS"]
    assert day_signals.diagnostics["etf_beta_selected_symbols"] == ["510300.SH"]
    assert day_signals.diagnostics["etf_beta_eligible_symbols"] == ["510300.SH", "510500.SH"]
    assert day_signals.diagnostics["etf_beta_runtime_reason_codes"] == ["ETF_BETA_WEEKLY_SELECTION_ACTIVE"]
    formal_view, research_view = _extract_etf_views(day_signals)
    assert formal_view["target_exposure"] == 0.2
    assert formal_view["min_deployable_exposure"] == 0.1
    assert formal_view["target_selected_count"] == 1
    assert research_view["deployability_gap"] == 0.0
    assert day_signals.buy_signals[0].meta["sleeve_id"] == "cn_etf_beta"
    assert day_signals.buy_signals[0].meta["target_exposure"] == 0.2
    assert day_signals.buy_signals[0].meta["min_deployable_exposure"] == 0.1
    assert day_signals.buy_signals[0].meta["target_weight"] == pytest.approx(0.2)


def test_cn_etf_beta_precompute_derives_legacy_regime_when_super_arrays_blank(monkeypatch) -> None:
    trading_days = [date(2026, 1, 5 + idx) for idx in range(10)]
    benchmark = pd.DataFrame(
        {
            "date": pd.to_datetime(trading_days),
            "close": [100.0 + float(idx) for idx in range(10)],
        }
    )

    def _fake_super_precompute(self, **_kwargs) -> None:
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh"],
            close=np.full((10, 1), 5.0, dtype=float),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.full((10, 1), 4.0, dtype=float),
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array([], dtype=object)
        self._effective_state_5_arr = np.array([], dtype=object)
        self._regime_risk_budget_multiplier_arr = np.array([], dtype=float)
        self._risk_budget_multiplier_arr = np.array([], dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=benchmark,
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        governed_a_share={
            "etf_beta": {
                "research_rule_family": "etf_beta_v1_control",
                "strategy_role": "auxiliary_beta_sleeve",
                "source_entry_type": "cn_etf_research_entry",
                "local_policy_mode": "legacy_beta_selection",
                "exposure_policy_family": "default",
                "core_beta_symbols": ["510300.SH"],
                "max_selected_symbols": 2,
            }
        },
        market_filter_cfg={
            "enabled": True,
            "long_ma_window": 5,
            "slope_window": 1,
            "slope_ma_period": 3,
            "bull_multiplier": 1.0,
            "light_multiplier": 0.5,
            "trans_down_multiplier": 0.25,
            "trans_up_multiplier": 0.75,
            "bear_multiplier": 0.0,
        },
    )

    assert len(provider._effective_state_5_arr) == 10
    assert provider._effective_state_5_arr[-1] == "BULL"
    assert provider._trade_mode_name_arr[-1] == "TREND_MAIN"
    assert provider._regime_risk_budget_multiplier_arr[-1] == 1.0
    assert provider._etf_beta_slot_cap_arr[-1] == 2


def test_cn_etf_beta_precompute_respects_dual_momentum_basic_config(monkeypatch) -> None:
    trading_days = [date(2025, 1, 1) + pd.Timedelta(days=idx) for idx in range(270)]
    trading_days = [pd.Timestamp(day).date() for day in trading_days]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 8.0, 270, dtype=float)
        close_510050 = np.linspace(8.0, 4.0, 270, dtype=float)
        close_511010 = np.linspace(3.0, 3.2, 270, dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510050.sh", "511010.sh"],
            close=np.column_stack([close_510300, close_510050, close_511010]),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.2,
                    close_510050 - 0.2,
                    close_511010 - 0.05,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array([], dtype=object)
        self._effective_state_5_arr = np.array([], dtype=object)
        self._regime_risk_budget_multiplier_arr = np.array([], dtype=float)
        self._risk_budget_multiplier_arr = np.array([], dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 130.0, 270, dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        market_filter_cfg={
            "enabled": True,
            "long_ma_window": 5,
            "slope_window": 1,
            "slope_ma_period": 3,
            "bull_multiplier": 1.0,
            "light_multiplier": 0.5,
            "trans_down_multiplier": 0.25,
            "trans_up_multiplier": 0.75,
            "bear_multiplier": 0.0,
        },
        governed_a_share={
            "etf_beta": {
                "research_rule_family": "dual_momentum_basic",
                "strategy_role": "auxiliary_beta_sleeve",
                "source_entry_type": "cn_etf_research_entry",
                "local_policy_mode": "legacy_beta_selection",
                "exposure_policy_family": "default",
                "core_beta_symbols": ["510300.SH", "510050.SH"],
                "rebalance_frequency": "weekly",
                "absolute_filter_mode": "positive_12m",
                "fallback_mode": "single_symbol",
                "fallback_symbol": "511010.SH",
                "relative_strength_fast_window": 60,
                "relative_strength_slow_window": 120,
                "relative_strength_fast_weight": 0.4,
                "relative_strength_slow_weight": 0.6,
                "max_selected_symbols": 1,
            }
        },
    )

    assert provider._etf_beta_rule_family == "dual_momentum_basic"
    assert provider._etf_beta_formal_scope_symbols == ["510300.SH", "510050.SH"]
    assert provider._etf_beta_selected_symbols_arr[-1] == ["510300.SH"]
    assert "ETF_BETA_WEEKLY_SELECTION_ACTIVE" in provider._etf_beta_runtime_reason_codes_arr[-1]


def test_cn_etf_beta_phase1_precompute_consumes_upstream_budget_before_governor_snapshot(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2024-01-02", periods=260)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 8.0, len(trading_days), dtype=float)
        close_510500 = np.linspace(3.2, 6.4, len(trading_days), dtype=float)
        close_510050 = np.linspace(3.8, 6.0, len(trading_days), dtype=float)
        close_512100 = np.linspace(2.8, 4.8, len(trading_days), dtype=float)
        close_512890 = np.linspace(1.8, 2.4, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510500.sh", "510050.sh", "512100.sh", "512890.sh"],
            close=np.column_stack([close_510300, close_510500, close_510050, close_512100, close_512890]),
        )
        self._sym_to_col = {
            "sh510300": 0,
            "sh510500": 1,
            "sh510050": 2,
            "sh512100": 3,
            "sh512890": 4,
        }
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.12,
                    close_510500 - 0.10,
                    close_510050 - 0.11,
                    close_512100 - 0.08,
                    close_512890 - 0.03,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array(["BULL"] * len(trading_days), dtype=object)
        self._effective_state_5_arr = np.array(["BULL"] * len(trading_days), dtype=object)
        self._regime_risk_budget_multiplier_arr = np.full(len(trading_days), 1.0, dtype=float)
        self._risk_budget_multiplier_arr = np.full(len(trading_days), 1.0, dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame(
            {
                "date": pd.to_datetime(trading_days),
                "close": np.linspace(100.0, 130.0, len(trading_days), dtype=float),
            }
        ),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        governed_a_share={
            "etf_beta": {
                "enabled": True,
                "research_rule_family": "phase1_allocation_engine_v1",
                "strategy_role": "phase1_allocation_engine",
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "governor_boundary_mode": "consume_governor_sleeve_budget",
                "local_policy_mode": "phase1_bucket_allocation",
                "exposure_policy_family": "phase1_governed_allocation_v1",
                "policy_scope": "broad_based_only",
                "broad_based_only": True,
                "rebalance_frequency": "monthly",
                "absolute_filter_mode": "none",
                "fallback_mode": "none",
                "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "max_selected_symbols": 3,
            }
        },
    )

    assert provider._etf_beta_slot_cap_arr[-1] == 2
    assert provider._etf_beta_target_selected_count_arr[-1] == 2
    assert provider._etf_beta_target_selected_count_source_arr[-1] == "input"
    assert len(provider._etf_beta_selected_symbols_arr[-1]) == 2
    assert provider._trade_mode_name_arr[-1] == "TREND_MAIN"
    assert "ETF_BETA_PHASE1_PROVISIONAL_SLOT_CAP_FALLBACK" not in provider._etf_beta_runtime_reason_codes_arr[-1]
    assert "ETF_BETA_BOUNDARY_POLICY::FORMAL_PHASE1_DOCUMENT_ALIGNED_V1" in provider._etf_beta_runtime_reason_codes_arr[-1]

    provider._etf_beta_rebalance_flag_arr[-1] = True
    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=10,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )

    day_signals = provider.day_signals(trading_days[-1], len(trading_days) - 1, ctx)

    assert len(day_signals.buy_signals) == 2
    assert day_signals.diagnostics["etf_beta_selected_cap"] == 2
    assert day_signals.diagnostics["etf_beta_target_selected_count_source"] == "input"
    assert day_signals.diagnostics["etf_beta_boundary_policy_mode"] == "formal_phase1_document_aligned_v1"
    assert day_signals.diagnostics["etf_beta_governor_hard_blocked"] is False
    assert day_signals.diagnostics["etf_beta_local_boundary_state"] == "ACTIVE"
    assert "ETF_BETA_PHASE1_PROVISIONAL_SLOT_CAP_FALLBACK" not in day_signals.diagnostics["etf_beta_runtime_reason_codes"]
    assert "ETF_BETA_SLOT_CAP_ZERO" not in day_signals.diagnostics["etf_beta_runtime_reason_codes"]


def test_cn_etf_beta_phase1_formal_boundary_uses_upstream_light_trade_mode_for_trans_down(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2024-01-02", periods=260)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 8.0, len(trading_days), dtype=float)
        close_510500 = np.linspace(3.2, 5.6, len(trading_days), dtype=float)
        close_510050 = np.linspace(3.8, 6.2, len(trading_days), dtype=float)
        close_512100 = np.linspace(2.8, 4.0, len(trading_days), dtype=float)
        close_512890 = np.linspace(1.8, 2.2, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510500.sh", "510050.sh", "512100.sh", "512890.sh"],
            close=np.column_stack([close_510300, close_510500, close_510050, close_512100, close_512890]),
        )
        self._sym_to_col = {
            "sh510300": 0,
            "sh510500": 1,
            "sh510050": 2,
            "sh512100": 3,
            "sh512890": 4,
        }
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.12,
                    close_510500 - 0.10,
                    close_510050 - 0.11,
                    close_512100 - 0.08,
                    close_512890 - 0.03,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array(["TREND_LIGHT"] * len(trading_days), dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array(["TRANS_DOWN"] * len(trading_days), dtype=object)
        self._effective_state_5_arr = np.array(["TRANS_DOWN"] * len(trading_days), dtype=object)
        self._regime_risk_budget_multiplier_arr = np.full(len(trading_days), 0.25, dtype=float)
        self._risk_budget_multiplier_arr = np.full(len(trading_days), 0.25, dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 115.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        governed_a_share={
            "etf_beta": {
                "enabled": True,
                "research_rule_family": "phase1_allocation_engine_v1",
                "strategy_role": "phase1_allocation_engine",
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "governor_boundary_mode": "consume_governor_sleeve_budget",
                "local_policy_mode": "phase1_bucket_allocation",
                "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                "exposure_policy_family": "phase1_governed_allocation_v1",
                "policy_scope": "broad_based_only",
                "broad_based_only": True,
                "rebalance_frequency": "monthly",
                "absolute_filter_mode": "none",
                "fallback_mode": "none",
                "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "max_selected_symbols": 3,
            }
        },
    )

    assert provider._trade_mode_name_arr[-1] == "TREND_LIGHT"
    assert provider._etf_beta_slot_cap_arr[-1] == 1
    assert provider._etf_beta_target_selected_count_arr[-1] == 1
    assert len(provider._etf_beta_selected_symbols_arr[-1]) == 1
    assert "ETF_BETA_LOCAL_BOUNDARY_STATE::REDUCED_ALLOCATION" in provider._etf_beta_runtime_reason_codes_arr[-1]
    assert provider._etf_beta_controlled_accumulation_mode == "none"


def test_cn_etf_beta_phase1_formal_boundary_does_not_treat_legacy_no_trade_as_explicit_block(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2024-01-02", periods=260)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 8.0, len(trading_days), dtype=float)
        close_510500 = np.linspace(3.2, 5.6, len(trading_days), dtype=float)
        close_510050 = np.linspace(3.8, 6.2, len(trading_days), dtype=float)
        close_512100 = np.linspace(2.8, 4.0, len(trading_days), dtype=float)
        close_512890 = np.linspace(1.8, 2.2, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510500.sh", "510050.sh", "512100.sh", "512890.sh"],
            close=np.column_stack([close_510300, close_510500, close_510050, close_512100, close_512890]),
        )
        self._sym_to_col = {
            "sh510300": 0,
            "sh510500": 1,
            "sh510050": 2,
            "sh512100": 3,
            "sh512890": 4,
        }
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.12,
                    close_510500 - 0.10,
                    close_510050 - 0.11,
                    close_512100 - 0.08,
                    close_512890 - 0.03,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array(["NO_TRADE"] * len(trading_days), dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array(["RISK_OFF"] * len(trading_days), dtype=object)
        self._effective_state_5_arr = np.array(["RISK_OFF"] * len(trading_days), dtype=object)
        self._regime_risk_budget_multiplier_arr = np.zeros(len(trading_days), dtype=float)
        self._risk_budget_multiplier_arr = np.zeros(len(trading_days), dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 105.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        governed_a_share={
            "etf_beta": {
                "enabled": True,
                "research_rule_family": "phase1_allocation_engine_v1",
                "strategy_role": "phase1_allocation_engine",
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "governor_boundary_mode": "consume_governor_sleeve_budget",
                "local_policy_mode": "phase1_bucket_allocation",
                "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                "exposure_policy_family": "phase1_governed_allocation_v1",
                "policy_scope": "broad_based_only",
                "broad_based_only": True,
                "rebalance_frequency": "monthly",
                "absolute_filter_mode": "none",
                "fallback_mode": "none",
                "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "max_selected_symbols": 3,
            }
        },
    )

    assert provider._trade_mode_name_arr[-1] == "TREND_LIGHT"
    assert provider._etf_beta_slot_cap_arr[-1] == 1
    assert len(provider._etf_beta_selected_symbols_arr[-1]) == 1
    assert "ETF_BETA_LOCAL_BOUNDARY_STATE::REDUCED_ALLOCATION" in provider._etf_beta_runtime_reason_codes_arr[-1]
    assert "ETF_BETA_PHASE1_GOVERNOR_HARD_BLOCK" not in provider._etf_beta_runtime_reason_codes_arr[-1]
    assert provider._formal_phase1_runtime_boundary_active is True


def test_cn_etf_beta_phase1_formal_boundary_treats_upstream_multiplier_as_explanatory_only(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2024-01-02", periods=260)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 8.0, len(trading_days), dtype=float)
        close_510500 = np.linspace(3.2, 5.6, len(trading_days), dtype=float)
        close_510050 = np.linspace(3.8, 6.2, len(trading_days), dtype=float)
        close_512100 = np.linspace(2.8, 4.0, len(trading_days), dtype=float)
        close_512890 = np.linspace(1.8, 2.2, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510500.sh", "510050.sh", "512100.sh", "512890.sh"],
            close=np.column_stack([close_510300, close_510500, close_510050, close_512100, close_512890]),
        )
        self._sym_to_col = {
            "sh510300": 0,
            "sh510500": 1,
            "sh510050": 2,
            "sh512100": 3,
            "sh512890": 4,
        }
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.12,
                    close_510500 - 0.10,
                    close_510050 - 0.11,
                    close_512100 - 0.08,
                    close_512890 - 0.03,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array(["TREND_MAIN"] * len(trading_days), dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array(["BULL"] * len(trading_days), dtype=object)
        self._effective_state_5_arr = np.array(["BULL"] * len(trading_days), dtype=object)
        self._regime_risk_budget_multiplier_arr = np.full(len(trading_days), 1.8, dtype=float)
        self._risk_budget_multiplier_arr = np.full(len(trading_days), 1.8, dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 120.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        governed_a_share={
            "etf_beta": {
                "enabled": True,
                "research_rule_family": "phase1_allocation_engine_v1",
                "strategy_role": "phase1_allocation_engine",
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "governor_boundary_mode": "consume_governor_sleeve_budget",
                "local_policy_mode": "phase1_bucket_allocation",
                "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                "exposure_policy_family": "phase1_governed_allocation_v1",
                "policy_scope": "broad_based_only",
                "broad_based_only": True,
                "rebalance_frequency": "monthly",
                "absolute_filter_mode": "none",
                "fallback_mode": "none",
                "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "max_selected_symbols": 3,
            }
        },
    )

    assert provider._etf_beta_requested_budget_arr[-1] == pytest.approx(0.2)
    assert provider._etf_beta_target_exposure_arr[-1] == pytest.approx(0.2)
    assert provider._risk_budget_multiplier_arr[-1] == pytest.approx(0.2)
    assert "GOVERNOR_BUDGET::UPSTREAM_RISK_BUDGET_MULTIPLIER_EXPLANATORY_ONLY" in provider._etf_beta_runtime_reason_codes_arr[-1]
    provider._etf_beta_rebalance_flag_arr[-1] = True
    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=10,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )

    day_signals = provider.day_signals(trading_days[-1], len(trading_days) - 1, ctx)

    assert len(day_signals.buy_signals) == 2
    assert all(signal.meta["target_exposure"] == pytest.approx(0.2) for signal in day_signals.buy_signals)
    assert all(float(signal.meta["target_weight"]) <= 1.0 for signal in day_signals.buy_signals)


def test_cn_etf_beta_trans_up_state_change_redeploy_emits_core_only_buy() -> None:
    provider, trading_days = _build_formal_trans_up_redeploy_provider()

    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=10,
        close_idx={(trading_days[-1], "sh510300"): 4.1},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="TRANS_UP",
    )

    day_signals = provider.day_signals(trading_days[-1], len(trading_days) - 1, ctx)

    assert len(day_signals.sell_signals) == 0
    assert len(day_signals.buy_signals) == 1
    assert len(day_signals.composed_buy_signals) == 1
    assert day_signals.buy_signals[0].symbol == "sh510300"
    assert day_signals.buy_signals[0].reason_code == "ETF_BETA_TRANS_UP_REDEPLOY"
    assert day_signals.composed_buy_signals[0].reason_code == "ETF_BETA_TRANS_UP_REDEPLOY"
    assert day_signals.buy_signals[0].meta["symbol_role"] == "core_accumulator"
    assert day_signals.buy_signals[0].meta["target_weight"] == pytest.approx(0.0527)
    assert "ETF_BETA_TRANS_UP_REDEPLOY_ACTIVE" in day_signals.diagnostics["etf_beta_runtime_reason_codes"]
    assert "ETF_BETA_AWAIT_MONTHLY_REBALANCE" not in day_signals.diagnostics["etf_beta_runtime_reason_codes"]
    formal_view, research_view = _extract_etf_views(day_signals)
    assert formal_view["target_exposure"] == pytest.approx(0.1)
    assert research_view["execution_path"] == "trans_up_state_change_redeploy"
    assert research_view["trans_up_contract_mode"] == "single_seat_core_recovery"
    assert research_view["trans_up_single_seat_core_recovery"] is True
    assert research_view["tactical_overlay_cap"] == pytest.approx(0.0323)
    assert research_view["pace_policy_gap"] == pytest.approx(0.0473)
    assert research_view["pace_policy_reason_code"] == "ETF_BETA_DEPLOYMENT_PACE_FLOOR_ONLY"
    assert research_view["trans_up_redeploy_active"] is True
    assert research_view["trans_up_redeploy_reason_code"] == "ETF_BETA_TRANS_UP_REDEPLOY_ACTIVE"
    assert research_view["trans_up_redeploy_floor_gap"] == pytest.approx(0.0527)
    assert research_view["trans_up_redeploy_edge_from_state"] == "RISK_OFF"


def test_cn_etf_beta_trans_up_monthly_rebalance_stays_single_seat_core_recovery() -> None:
    provider, trading_days = _build_formal_trans_up_redeploy_provider(rebalance_day=True)

    ctx = DayContext(
        positions={"sh512100": 100},
        position_avg_cost={"sh512100": 3.0},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=10,
        close_idx={(trading_days[-1], "sh510300"): 4.1, (trading_days[-1], "sh512100"): 3.1},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="TRANS_UP",
    )

    day_signals = provider.day_signals(trading_days[-1], len(trading_days) - 1, ctx)

    assert [signal.reason_code for signal in day_signals.sell_signals] == ["ETF_BETA_PHASE1_REBALANCE_RESET"]
    assert len(day_signals.buy_signals) == 1
    assert day_signals.buy_signals[0].symbol == "sh510300"
    assert day_signals.buy_signals[0].meta["symbol_role"] == "core_accumulator"
    assert day_signals.buy_signals[0].meta["target_weight"] == pytest.approx(0.0527)
    assert day_signals.diagnostics["etf_beta_execution_path"] == "monthly_rebalance"
    assert day_signals.diagnostics["etf_beta_selected_symbols"] == ["510300.SH"]
    research_view = _extract_etf_views(day_signals)[1]
    assert research_view["trans_up_contract_mode"] == "single_seat_core_recovery"
    assert research_view["trans_up_single_seat_core_recovery"] is True


def test_cn_etf_beta_standalone_trans_up_inter_rebalance_deploy_allows_top_up() -> None:
    provider, trading_days = _build_standalone_inter_rebalance_provider(
        previous_state="LIGHT",
        current_state="TRANS_UP",
        deployment_pace=0.9,
        target_exposure=0.9,
        min_deployable_exposure=0.35,
        selected_symbols=["510300.SH", "588000.SH"],
        targets={"510300.SH": 0.36, "588000.SH": 0.36},
    )
    ctx = DayContext(
        positions={"sh510300": 2500},
        position_avg_cost={"sh510300": 4.0},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=2,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="TRANS_UP",
    )

    day_signals = provider.day_signals(trading_days[-1], len(trading_days) - 1, ctx)

    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh510300", "sh588000"]
    assert {signal.reason_code for signal in day_signals.buy_signals} == {"ETF_BETA_TRANS_UP_INTER_REBALANCE_DEPLOY_ACTIVE"}
    assert day_signals.diagnostics["etf_beta_execution_path"] == "trans_up_inter_rebalance_deploy"
    assert "ETF_BETA_TRANS_UP_INTER_REBALANCE_DEPLOY_ACTIVE" in day_signals.diagnostics["etf_beta_runtime_reason_codes"]
    formal_view, research_view = _extract_etf_views(day_signals)
    assert formal_view["target_exposure"] == pytest.approx(0.9)
    assert research_view["execution_path"] == "trans_up_inter_rebalance_deploy"


def test_cn_etf_beta_standalone_risk_off_inter_rebalance_deploy_stays_core_only() -> None:
    provider, trading_days = _build_standalone_inter_rebalance_provider(
        previous_state="TRANS_DOWN",
        current_state="RISK_OFF",
        deployment_pace=0.15,
        target_exposure=0.15,
        min_deployable_exposure=0.05,
        selected_symbols=["510300.SH", "588000.SH"],
        targets={"510300.SH": 0.15},
    )
    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=2,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=False,
        market_state="RISK_OFF",
    )

    day_signals = provider.day_signals(trading_days[-1], len(trading_days) - 1, ctx)

    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh510300"]
    assert [signal.reason_code for signal in day_signals.buy_signals] == ["ETF_BETA_RISK_OFF_CORE_ACCUMULATION_ACTIVE"]
    assert day_signals.diagnostics["etf_beta_execution_path"] == "risk_off_core_accumulation_deploy"
    assert "ETF_BETA_RISK_OFF_CORE_ACCUMULATION_ACTIVE" in day_signals.diagnostics["etf_beta_runtime_reason_codes"]
    formal_view, research_view = _extract_etf_views(day_signals)
    assert formal_view["target_exposure"] == pytest.approx(0.15)
    assert research_view["execution_path"] == "risk_off_core_accumulation_deploy"
    assert research_view["pace_policy_gap"] == pytest.approx(0.0)
    assert research_view["pace_policy_reason_code"] is None


def test_cn_etf_beta_standalone_trans_up_inter_rebalance_deploy_uses_fallback_when_no_selection() -> None:
    provider, trading_days = _build_standalone_inter_rebalance_provider(
        previous_state="LIGHT",
        current_state="TRANS_UP",
        deployment_pace=0.9,
        target_exposure=0.9,
        min_deployable_exposure=0.35,
        selected_symbols=[],
        targets={"510300.SH": 0.36, "588000.SH": 0.36},
        fallback_mode="single_symbol",
        fallback_symbol="511010.SH",
    )
    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=2,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="TRANS_UP",
    )

    day_signals = provider.day_signals(trading_days[-1], len(trading_days) - 1, ctx)

    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh511010"]
    assert [signal.reason_code for signal in day_signals.buy_signals] == ["ETF_BETA_FALLBACK_BUY"]
    assert day_signals.diagnostics["etf_beta_execution_path"] == "trans_up_inter_rebalance_deploy"
    assert day_signals.diagnostics["etf_beta_selected_symbols"] == ["511010.SH"]
    assert "ETF_BETA_INTER_REBALANCE_FALLBACK_FILL_ACTIVE" in day_signals.diagnostics["etf_beta_runtime_reason_codes"]
    buy_meta = day_signals.buy_signals[0].meta
    assert float(buy_meta["final_target_weight"]) == pytest.approx(0.9)
    assert float(buy_meta["target_weight"]) == pytest.approx(0.9)
    assert buy_meta["target_weight_basis"] == "delta_deploy_gap"
    formal_view, research_view = _extract_etf_views(day_signals)
    assert formal_view["target_exposure"] == pytest.approx(0.9)
    assert research_view["execution_path"] == "trans_up_inter_rebalance_deploy"


def test_cn_etf_beta_standalone_bull_inter_rebalance_deploy_uses_fallback_when_no_selection() -> None:
    provider, trading_days = _build_standalone_inter_rebalance_provider(
        previous_state="LIGHT",
        current_state="BULL",
        deployment_pace=1.0,
        target_exposure=1.0,
        min_deployable_exposure=0.45,
        selected_symbols=[],
        targets={"510300.SH": 0.55, "588000.SH": 0.45},
        fallback_mode="single_symbol",
        fallback_symbol="511010.SH",
    )
    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=2,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )

    day_signals = provider.day_signals(trading_days[-1], len(trading_days) - 1, ctx)

    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh511010"]
    assert [signal.reason_code for signal in day_signals.buy_signals] == ["ETF_BETA_FALLBACK_BUY"]
    assert day_signals.diagnostics["etf_beta_execution_path"] == "bull_inter_rebalance_deploy"
    assert "ETF_BETA_INTER_REBALANCE_FALLBACK_FILL_ACTIVE" in day_signals.diagnostics["etf_beta_runtime_reason_codes"]
    buy_meta = day_signals.buy_signals[0].meta
    assert float(buy_meta["final_target_weight"]) == pytest.approx(1.0)
    assert float(buy_meta["target_weight"]) == pytest.approx(1.0)
    assert buy_meta["target_weight_basis"] == "delta_deploy_gap"
    formal_view, research_view = _extract_etf_views(day_signals)
    assert formal_view["target_exposure"] == pytest.approx(1.0)
    assert research_view["execution_path"] == "bull_inter_rebalance_deploy"


def test_cn_etf_beta_standalone_bull_inter_rebalance_deploy_uses_delta_target_weight() -> None:
    provider, trading_days = _build_standalone_inter_rebalance_provider(
        previous_state="LIGHT",
        current_state="BULL",
        deployment_pace=1.0,
        target_exposure=1.0,
        min_deployable_exposure=0.45,
        selected_symbols=["510300.SH"],
        targets={"510300.SH": 1.0},
    )
    held_qty = 6451  # 6451 * 3.1 / 100000 ~= 0.199981 defense exposure
    ctx = DayContext(
        positions={"sh511010": held_qty},
        position_avg_cost={"sh511010": 3.0},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=2,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )

    day_idx = len(trading_days) - 1
    day_signals = provider.day_signals(trading_days[day_idx], day_idx, ctx)

    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh510300"]
    buy_meta = day_signals.buy_signals[0].meta
    expected_gap = 1.0 - (held_qty * 3.1 / 100000.0)
    assert float(buy_meta["target_weight"]) == pytest.approx(expected_gap)
    assert float(buy_meta["final_target_weight"]) == pytest.approx(1.0)
    assert buy_meta["target_weight_basis"] == "delta_deploy_gap"
    assert float(buy_meta["target_weight"]) < 1.0
    assert day_signals.diagnostics["etf_beta_execution_path"] == "bull_inter_rebalance_deploy"


def test_cn_etf_beta_standalone_partial_fallback_fill_keeps_zero_target_contract() -> None:
    trading_day = date(2026, 3, 20)
    provider = CNETFBetaSignalProvider()
    provider._mx = SimpleNamespace(
        symbols=["sh510300", "sh511010"],
        close=np.array([[4.0, 3.1]], dtype=float),
        dates=[trading_day],
    )
    provider._feats = SimpleNamespace(
        trend_fast_ma=np.array([[3.5, 3.0]], dtype=float),
    )
    provider._sym_to_col = {"sh510300": 0, "sh511010": 1}
    provider._effective_state_5_arr = np.array(["BULL"], dtype=object)
    provider._trade_mode_name_arr = np.array(["TREND_MAIN"], dtype=object)
    provider._etf_beta_slot_cap_arr = np.array([2], dtype=np.int32)
    provider._etf_beta_rebalance_flag_arr = np.array([True], dtype=bool)
    provider._etf_beta_formal_scope_symbols = ["510300.SH"]
    provider._etf_beta_eligible_symbols_arr = np.array([["510300.SH"]], dtype=object)
    provider._etf_beta_selected_symbols_arr = np.array([["510300.SH", "511010.SH"]], dtype=object)
    provider._etf_beta_selection_reason_codes_arr = np.array(
        [
            {
                "510300.SH": ["ETF_BETA_CORE_SCOPE", "ABSOLUTE_MA120_PASS"],
                "511010.SH": [
                    "ETF_BETA_FALLBACK_SINGLE_SYMBOL",
                    "FALLBACK_SYMBOL::511010.SH",
                    "UNDERFILLED_DEPLOYMENT_FILL",
                ],
            }
        ],
        dtype=object,
    )
    provider._etf_beta_runtime_reason_codes_arr = np.array(
        [["ETF_BETA_STANDALONE_MAINLINE_ACTIVE", "ETF_BETA_FALLBACK_ACTIVE", "ETF_BETA_FALLBACK_PARTIAL_FILL_ACTIVE"]],
        dtype=object,
    )
    provider._etf_beta_rule_family = "broad_based_rotation_template_a"
    provider._etf_beta_strategy_role = "governed_broad_based_standalone_mainline"
    provider._etf_beta_local_policy_mode = "broad_based_rotation_mainline"
    provider._etf_beta_governor_boundary_mode = "consume_governor_state_and_budget"
    provider._etf_beta_boundary_policy_mode = "legacy_state_slot_caps_v1"
    provider._etf_beta_exposure_policy_family_arr = np.array(["broad_based_standalone_mainline_v1"], dtype=object)
    provider._etf_beta_absolute_filter_mode = "ma120"
    provider._etf_beta_fallback_mode = "single_symbol"
    provider._etf_beta_fallback_symbol = "sh511010"
    provider._etf_beta_max_selected_symbols = 2
    provider._etf_beta_rebalance_frequency = "biweekly"
    provider._etf_beta_target_exposure_arr = np.array([0.8], dtype=float)
    provider._etf_beta_target_exposure_source_arr = np.array(["state_map::BULL"], dtype=object)
    provider._etf_beta_min_deployable_exposure_arr = np.array([0.45], dtype=float)
    provider._etf_beta_min_deployable_exposure_source_arr = np.array(["state_map::BULL"], dtype=object)
    provider._etf_beta_target_selected_count_arr = np.array([2], dtype=np.int32)
    provider._etf_beta_target_exposure_per_symbol_arr = np.array([0.4], dtype=float)
    provider._etf_beta_target_actual_exposure_arr = np.array([0.8], dtype=float)
    provider._etf_beta_target_deployability_gap_arr = np.array([0.0], dtype=float)
    provider._etf_beta_fallback_allowed_arr = np.array([True], dtype=bool)
    provider._etf_beta_policy_scope_arr = np.array(["general"], dtype=object)
    provider._etf_beta_broad_based_only_arr = np.array([False], dtype=bool)
    provider._etf_beta_layering_policy_arr = np.array(["light_trans_down_accumulate"], dtype=object)
    provider._etf_beta_layering_band_arr = np.array(["RISK_ON_FULL"], dtype=object)
    provider._etf_beta_layering_active_arr = np.array([False], dtype=bool)
    provider._etf_beta_layering_reason_codes_arr = np.array([[]], dtype=object)
    provider._etf_beta_target_selected_count_source_arr = np.array(["state_map::BULL"], dtype=object)
    provider._etf_beta_fallback_allowed_source_arr = np.array(["state_map::BULL"], dtype=object)
    provider._etf_beta_core_slot_selected_symbol_arr = np.array(["510300.SH"], dtype=object)
    provider._etf_beta_growth_slot_selected_symbol_arr = np.array([""], dtype=object)
    provider._etf_beta_slot_selection_reason_codes_arr = np.array([{"core_slot": ["SLOT::CORE_SLOT"]}], dtype=object)
    provider._etf_beta_slot_under_deploy_reason_codes_arr = np.array([{"growth_slot": ["ETF_BETA_FALLBACK_PARTIAL_FILL_ACTIVE"]}], dtype=object)
    provider._etf_beta_core_slot_target_exposure_arr = np.array([0.8], dtype=float)
    provider._etf_beta_growth_slot_target_exposure_arr = np.array([np.nan], dtype=float)
    provider._etf_beta_core_slot_target_actual_exposure_arr = np.array([0.8], dtype=float)
    provider._etf_beta_growth_slot_target_actual_exposure_arr = np.array([np.nan], dtype=float)
    provider._etf_beta_absolute_filter_reject_count_arr = np.array([0], dtype=np.int32)
    provider._etf_beta_absolute_filter_reject_reason_counts_arr = np.array([{}], dtype=object)
    provider._etf_beta_selection_chain_winner_counts_arr = np.array([{"selected_count": 2}], dtype=object)
    provider._etf_beta_selection_chain_reject_reason_counts_arr = np.array([{}], dtype=object)
    provider._etf_beta_targets_arr = np.array([{"510300.SH": 1.0, "511010.SH": 0.0}], dtype=object)
    provider._etf_beta_requested_budget_arr = np.array([0.8], dtype=float)
    provider._etf_beta_applied_budget_arr = np.array([0.8], dtype=float)
    provider._etf_beta_cash_weight_arr = np.array([0.2], dtype=float)
    provider._etf_beta_defense_weight_arr = np.array([0.0], dtype=float)
    provider._etf_beta_equity_core_bucket_arr = np.array([1.0], dtype=float)
    provider._etf_beta_defense_tilt_bucket_arr = np.array([0.0], dtype=float)
    provider._etf_beta_cash_buffer_bucket_arr = np.array([0.0], dtype=float)
    provider._etf_beta_strategic_floor_cap_arr = np.array([0.8], dtype=float)
    provider._etf_beta_tactical_overlay_cap_arr = np.array([0.0], dtype=float)
    provider._etf_beta_limited_defense_cap_arr = np.array([0.0], dtype=float)
    provider._etf_beta_deployment_pace_arr = np.array([0.8], dtype=float)
    provider._etf_beta_pace_policy_gap_arr = np.array([0.0], dtype=float)
    provider._etf_beta_pace_policy_reason_code_arr = np.array([""], dtype=object)
    provider._etf_beta_pace_policy_mode_arr = np.array([""], dtype=object)
    provider._etf_beta_bull_partial_overlay_pace_ratio_arr = np.array([1.0], dtype=float)
    provider._etf_beta_bull_pace_mode_arr = np.array(["full_overlay_target_match"], dtype=object)
    provider._etf_beta_hard_block_flags_arr = np.array([[]], dtype=object)
    provider._etf_beta_core_accumulator_symbols_arr = np.array([["510300.SH"]], dtype=object)
    provider._etf_beta_tactical_satellite_symbols_arr = np.array([[]], dtype=object)
    provider._etf_beta_limited_defense_symbols_arr = np.array([["511010.SH"]], dtype=object)
    provider._etf_beta_symbol_role_map_arr = np.array([{"510300.SH": "core_accumulator", "511010.SH": "fallback_symbol"}], dtype=object)
    provider._etf_beta_allocation_reason_codes_arr = np.array([["STATE_5::BULL"]], dtype=object)

    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=2,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )

    day_signals = provider.day_signals(trading_day, 0, ctx)
    buy_meta_by_symbol = {signal.symbol: signal.meta for signal in day_signals.buy_signals}

    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh510300", "sh511010"]
    assert float(buy_meta_by_symbol["sh510300"]["final_target_weight"]) == pytest.approx(1.0)
    assert float(buy_meta_by_symbol["sh510300"]["target_weight"]) == pytest.approx(1.0)
    assert float(buy_meta_by_symbol["sh511010"]["final_target_weight"]) == pytest.approx(0.0)
    assert float(buy_meta_by_symbol["sh511010"]["target_weight"]) == pytest.approx(0.0)


def test_cn_etf_beta_standalone_bull_single_symbol_compresses_full_live_target() -> None:
    trading_day = date(2026, 3, 20)
    provider = CNETFBetaSignalProvider()
    provider._mx = SimpleNamespace(
        symbols=["sh510300"],
        close=np.array([[4.0]], dtype=float),
        dates=[trading_day],
    )
    provider._feats = SimpleNamespace(
        trend_fast_ma=np.array([[3.9]], dtype=float),
    )
    provider._sym_to_col = {"sh510300": 0}
    provider._effective_state_5_arr = np.array(["BULL"], dtype=object)
    provider._trade_mode_name_arr = np.array(["TREND_MAIN"], dtype=object)
    provider._etf_beta_slot_cap_arr = np.array([2], dtype=np.int32)
    provider._etf_beta_rebalance_flag_arr = np.array([True], dtype=bool)
    provider._etf_beta_formal_scope_symbols = ["510300.SH"]
    provider._etf_beta_eligible_symbols_arr = np.array([["510300.SH"]], dtype=object)
    provider._etf_beta_selected_symbols_arr = np.array([["510300.SH"]], dtype=object)
    provider._etf_beta_selection_reason_codes_arr = np.array(
        [{"510300.SH": ["ETF_BETA_CORE_SCOPE", "STATE::BULL"]}],
        dtype=object,
    )
    provider._etf_beta_runtime_reason_codes_arr = np.array([["ETF_BETA_STANDALONE_MAINLINE_ACTIVE"]], dtype=object)
    provider._etf_beta_target_exposure_arr = np.array([1.0], dtype=float)
    provider._etf_beta_target_exposure_source_arr = np.array(["state_map::BULL"], dtype=object)
    provider._etf_beta_min_deployable_exposure_arr = np.array([0.45], dtype=float)
    provider._etf_beta_min_deployable_exposure_source_arr = np.array(["state_map::BULL"], dtype=object)
    provider._etf_beta_target_selected_count_arr = np.array([2], dtype=np.int32)
    provider._etf_beta_target_exposure_per_symbol_arr = np.array([0.5], dtype=float)
    provider._etf_beta_target_actual_exposure_arr = np.array([1.0], dtype=float)
    provider._etf_beta_target_deployability_gap_arr = np.array([0.0], dtype=float)
    provider._etf_beta_fallback_allowed_arr = np.array([True], dtype=bool)
    provider._etf_beta_exposure_policy_family_arr = np.array(["broad_based_standalone_mainline_v1"], dtype=object)
    provider._etf_beta_policy_scope_arr = np.array(["general"], dtype=object)
    provider._etf_beta_broad_based_only_arr = np.array([False], dtype=bool)
    provider._etf_beta_layering_policy_arr = np.array(["light_trans_down_accumulate"], dtype=object)
    provider._etf_beta_layering_band_arr = np.array(["RISK_ON_FULL"], dtype=object)
    provider._etf_beta_layering_active_arr = np.array([False], dtype=bool)
    provider._etf_beta_layering_reason_codes_arr = np.array([[]], dtype=object)
    provider._etf_beta_target_selected_count_source_arr = np.array(["state_map::BULL"], dtype=object)
    provider._etf_beta_fallback_allowed_source_arr = np.array(["state_map::BULL"], dtype=object)
    provider._etf_beta_core_slot_selected_symbol_arr = np.array(["510300.SH"], dtype=object)
    provider._etf_beta_growth_slot_selected_symbol_arr = np.array([""], dtype=object)
    provider._etf_beta_slot_selection_reason_codes_arr = np.array([{"core_slot": ["SLOT::CORE_SLOT"]}], dtype=object)
    provider._etf_beta_slot_under_deploy_reason_codes_arr = np.array(
        [{"growth_slot": ["ETF_BETA_GROWTH_SLOT_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER"]}],
        dtype=object,
    )
    provider._etf_beta_core_slot_target_exposure_arr = np.array([1.0], dtype=float)
    provider._etf_beta_growth_slot_target_exposure_arr = np.array([np.nan], dtype=float)
    provider._etf_beta_core_slot_target_actual_exposure_arr = np.array([1.0], dtype=float)
    provider._etf_beta_growth_slot_target_actual_exposure_arr = np.array([np.nan], dtype=float)
    provider._etf_beta_absolute_filter_reject_count_arr = np.array([0], dtype=np.int32)
    provider._etf_beta_absolute_filter_reject_reason_counts_arr = np.array([{}], dtype=object)
    provider._etf_beta_selection_chain_winner_counts_arr = np.array([{"selected_count": 1}], dtype=object)
    provider._etf_beta_selection_chain_reject_reason_counts_arr = np.array([{}], dtype=object)
    provider._etf_beta_targets_arr = np.array([{"510300.SH": 1.0}], dtype=object)
    provider._etf_beta_requested_budget_arr = np.array([1.0], dtype=float)
    provider._etf_beta_applied_budget_arr = np.array([1.0], dtype=float)
    provider._etf_beta_cash_weight_arr = np.array([0.0], dtype=float)
    provider._etf_beta_defense_weight_arr = np.array([0.0], dtype=float)
    provider._etf_beta_equity_core_bucket_arr = np.array([1.0], dtype=float)
    provider._etf_beta_defense_tilt_bucket_arr = np.array([0.0], dtype=float)
    provider._etf_beta_cash_buffer_bucket_arr = np.array([0.0], dtype=float)
    provider._etf_beta_strategic_floor_cap_arr = np.array([0.6], dtype=float)
    provider._etf_beta_tactical_overlay_cap_arr = np.array([0.4], dtype=float)
    provider._etf_beta_limited_defense_cap_arr = np.array([0.0], dtype=float)
    provider._etf_beta_deployment_pace_arr = np.array([1.0], dtype=float)
    provider._etf_beta_pace_policy_gap_arr = np.array([0.0], dtype=float)
    provider._etf_beta_pace_policy_reason_code_arr = np.array([""], dtype=object)
    provider._etf_beta_pace_policy_mode_arr = np.array([""], dtype=object)
    provider._etf_beta_bull_partial_overlay_pace_ratio_arr = np.array([1.0], dtype=float)
    provider._etf_beta_bull_pace_mode_arr = np.array(["full_overlay_target_match"], dtype=object)
    provider._etf_beta_hard_block_flags_arr = np.array([[]], dtype=object)
    provider._etf_beta_core_accumulator_symbols_arr = np.array([["510300.SH"]], dtype=object)
    provider._etf_beta_tactical_satellite_symbols_arr = np.array([["588000.SH"]], dtype=object)
    provider._etf_beta_limited_defense_symbols_arr = np.array([["511010.SH"]], dtype=object)
    provider._etf_beta_symbol_role_map_arr = np.array([{"510300.SH": "core_accumulator"}], dtype=object)
    provider._etf_beta_allocation_reason_codes_arr = np.array([["STATE_5::BULL"]], dtype=object)
    provider._etf_beta_strategy_role = "governed_broad_based_standalone_mainline"
    provider._etf_beta_local_policy_mode = "broad_based_rotation_mainline"
    provider._etf_beta_boundary_policy_mode = "legacy_state_slot_caps_v1"
    provider._etf_beta_governor_boundary_mode = "consume_governor_state_and_budget"
    provider._etf_beta_rule_family = "broad_based_rotation_template_a"
    provider._etf_beta_rebalance_frequency = "biweekly"
    provider._etf_beta_bull_partial_overlay_pace_ratio = 1.0
    provider._etf_beta_candidate_pool_symbols = ["510300.SH"]
    provider._etf_beta_candidate_pool_coverage_summary = {}
    provider._etf_beta_candidate_pool_reject_reason_counts = {}

    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=2,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )

    day_signals = provider.day_signals(trading_day, 0, ctx)

    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh510300"]
    assert day_signals.buy_signals[0].meta["target_weight"] == pytest.approx(1.0)
    assert day_signals.buy_signals[0].meta["execution_path"] == "monthly_rebalance"
    formal_view, research_view = _extract_etf_views(day_signals)
    assert formal_view["target_exposure"] == pytest.approx(1.0)
    assert research_view["deployability_gap"] == pytest.approx(0.0)


def test_cn_etf_beta_bull_monthly_rebalance_emits_partial_overlay_pace_meta() -> None:
    trading_day = date(2026, 3, 20)
    provider = CNETFBetaSignalProvider()
    provider._mx = SimpleNamespace(
        symbols=["sh510300", "sh510500"],
        close=np.array([[4.1, 6.1]], dtype=float),
        dates=[trading_day],
    )
    provider._feats = SimpleNamespace(
        trend_fast_ma=np.array([[4.0, 6.0]], dtype=float),
    )
    provider._sym_to_col = {"sh510300": 0, "sh510500": 1}
    provider._effective_state_5_arr = np.array(["BULL"], dtype=object)
    provider._trade_mode_name_arr = np.array(["TREND_MAIN"], dtype=object)
    provider._etf_beta_slot_cap_arr = np.array([2], dtype=np.int32)
    provider._etf_beta_rebalance_flag_arr = np.array([True], dtype=bool)
    provider._etf_beta_formal_scope_symbols = ["510300.SH", "510500.SH"]
    provider._etf_beta_eligible_symbols_arr = np.array([["510300.SH", "510500.SH"]], dtype=object)
    provider._etf_beta_selected_symbols_arr = np.array([["510300.SH", "510500.SH"]], dtype=object)
    provider._etf_beta_selection_reason_codes_arr = np.array(
        [
            {
                "510300.SH": ["PHASE1_FORMAL_SCOPE", "ROLE::CORE_ACCUMULATOR"],
                "510500.SH": ["PHASE1_FORMAL_SCOPE", "ROLE::TACTICAL_SATELLITE"],
            }
        ],
        dtype=object,
    )
    provider._etf_beta_runtime_reason_codes_arr = np.array([["ETF_BETA_STRATEGIC_BETA_STABILIZER_ACTIVE"]], dtype=object)
    provider._etf_beta_target_exposure_arr = np.array([0.2], dtype=float)
    provider._etf_beta_target_exposure_source_arr = np.array(["governor_total_exposure_cap"], dtype=object)
    provider._etf_beta_min_deployable_exposure_arr = np.array([0.0], dtype=float)
    provider._etf_beta_min_deployable_exposure_source_arr = np.array(["phase1_allocation_engine"], dtype=object)
    provider._etf_beta_target_selected_count_arr = np.array([2], dtype=np.int32)
    provider._etf_beta_target_exposure_per_symbol_arr = np.array([0.072], dtype=float)
    provider._etf_beta_target_actual_exposure_arr = np.array([0.2], dtype=float)
    provider._etf_beta_target_deployability_gap_arr = np.array([0.0], dtype=float)
    provider._etf_beta_fallback_allowed_arr = np.array([False], dtype=bool)
    provider._etf_beta_exposure_policy_family_arr = np.array(["phase1_governed_allocation_v1"], dtype=object)
    provider._etf_beta_policy_scope_arr = np.array(["broad_based_only"], dtype=object)
    provider._etf_beta_broad_based_only_arr = np.array([True], dtype=bool)
    provider._etf_beta_layering_policy_arr = np.array(["none"], dtype=object)
    provider._etf_beta_layering_band_arr = np.array([""], dtype=object)
    provider._etf_beta_layering_active_arr = np.array([False], dtype=bool)
    provider._etf_beta_layering_reason_codes_arr = np.array([[]], dtype=object)
    provider._etf_beta_target_selected_count_source_arr = np.array(["input"], dtype=object)
    provider._etf_beta_fallback_allowed_source_arr = np.array([""], dtype=object)
    provider._etf_beta_core_slot_selected_symbol_arr = np.array([""], dtype=object)
    provider._etf_beta_growth_slot_selected_symbol_arr = np.array([""], dtype=object)
    provider._etf_beta_slot_selection_reason_codes_arr = np.array([{}], dtype=object)
    provider._etf_beta_slot_under_deploy_reason_codes_arr = np.array([{}], dtype=object)
    provider._etf_beta_core_slot_target_exposure_arr = np.array([np.nan], dtype=float)
    provider._etf_beta_growth_slot_target_exposure_arr = np.array([np.nan], dtype=float)
    provider._etf_beta_core_slot_target_actual_exposure_arr = np.array([np.nan], dtype=float)
    provider._etf_beta_growth_slot_target_actual_exposure_arr = np.array([np.nan], dtype=float)
    provider._etf_beta_absolute_filter_reject_count_arr = np.array([0], dtype=np.int32)
    provider._etf_beta_absolute_filter_reject_reason_counts_arr = np.array([{}], dtype=object)
    provider._etf_beta_selection_chain_winner_counts_arr = np.array([{}], dtype=object)
    provider._etf_beta_selection_chain_reject_reason_counts_arr = np.array([{}], dtype=object)
    provider._etf_beta_targets_arr = np.array([{"510300.SH": 0.108, "510500.SH": 0.036}], dtype=object)
    provider._etf_beta_requested_budget_arr = np.array([0.2], dtype=float)
    provider._etf_beta_applied_budget_arr = np.array([0.2], dtype=float)
    provider._etf_beta_cash_weight_arr = np.array([0.02], dtype=float)
    provider._etf_beta_defense_weight_arr = np.array([0.0], dtype=float)
    provider._etf_beta_equity_core_bucket_arr = np.array([0.9], dtype=float)
    provider._etf_beta_defense_tilt_bucket_arr = np.array([0.0], dtype=float)
    provider._etf_beta_cash_buffer_bucket_arr = np.array([0.1], dtype=float)
    provider._etf_beta_strategic_floor_cap_arr = np.array([0.108], dtype=float)
    provider._etf_beta_tactical_overlay_cap_arr = np.array([0.072], dtype=float)
    provider._etf_beta_limited_defense_cap_arr = np.array([0.0], dtype=float)
    provider._etf_beta_deployment_pace_arr = np.array([0.144], dtype=float)
    provider._etf_beta_pace_policy_gap_arr = np.array([0.056], dtype=float)
    provider._etf_beta_pace_policy_reason_code_arr = np.array(["ETF_BETA_DEPLOYMENT_PACE_BULL_PARTIAL_OVERLAY"], dtype=object)
    provider._etf_beta_pace_policy_mode_arr = np.array(["partial_overlay_v1_between_rebalances"], dtype=object)
    provider._etf_beta_bull_partial_overlay_pace_ratio_arr = np.array([0.5], dtype=float)
    provider._etf_beta_bull_pace_mode_arr = np.array(["partial_overlay_v1"], dtype=object)
    provider._etf_beta_hard_block_flags_arr = np.array([[]], dtype=object)
    provider._etf_beta_core_accumulator_symbols_arr = np.array([["510300.SH"]], dtype=object)
    provider._etf_beta_tactical_satellite_symbols_arr = np.array([["510500.SH"]], dtype=object)
    provider._etf_beta_limited_defense_symbols_arr = np.array([[]], dtype=object)
    provider._etf_beta_symbol_role_map_arr = np.array(
        [{"510300.SH": "core_accumulator", "510500.SH": "tactical_satellite"}],
        dtype=object,
    )
    provider._etf_beta_allocation_reason_codes_arr = np.array([["PHASE1_ALLOCATION_ENGINE::THREE_BUCKET"]], dtype=object)
    provider._etf_beta_strategy_role = "strategic_beta_stabilizer"
    provider._etf_beta_local_policy_mode = "phase1_bucket_allocation"
    provider._etf_beta_boundary_policy_mode = "formal_phase1_document_aligned_v1"
    provider._etf_beta_governor_boundary_mode = "consume_governor_sleeve_budget"
    provider._etf_beta_rule_family = "phase1_allocation_engine_v1"
    provider._etf_beta_rebalance_frequency = "monthly"
    provider._etf_beta_bull_partial_overlay_pace_ratio = 0.5
    provider._etf_beta_candidate_pool_symbols = ["510300.SH", "510500.SH"]
    provider._etf_beta_candidate_pool_coverage_summary = {}
    provider._etf_beta_candidate_pool_reject_reason_counts = {}

    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=10,
        close_idx={(trading_day, "sh510300"): 4.1, (trading_day, "sh510500"): 6.1},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )

    day_signals = provider.day_signals(trading_day, 0, ctx)

    assert len(day_signals.buy_signals) == 2
    assert {signal.symbol for signal in day_signals.buy_signals} == {"sh510300", "sh510500"}
    assert day_signals.diagnostics["etf_beta_execution_path"] == "monthly_rebalance"
    research_view = _extract_etf_views(day_signals)[1]
    assert research_view["bull_partial_overlay_pace_ratio"] == pytest.approx(0.5)
    assert research_view["bull_pace_mode"] == "partial_overlay_v1"
    assert research_view["pace_policy_gap"] == pytest.approx(0.056)
    assert research_view["pace_policy_reason_code"] == "ETF_BETA_DEPLOYMENT_PACE_BULL_PARTIAL_OVERLAY"
    assert research_view["pace_policy_mode"] == "partial_overlay_v1_between_rebalances"
    buy_meta_by_symbol = {signal.symbol: signal.meta for signal in day_signals.buy_signals}
    assert buy_meta_by_symbol["sh510300"]["target_weight"] == pytest.approx(0.108)
    assert buy_meta_by_symbol["sh510500"]["symbol_role"] == "tactical_satellite"
    assert buy_meta_by_symbol["sh510500"]["target_weight"] == pytest.approx(0.036)


def test_cn_etf_beta_trans_up_redeploy_rejects_without_state_change_edge() -> None:
    provider, trading_days = _build_formal_trans_up_redeploy_provider(previous_state="TRANS_UP", current_state="TRANS_UP")

    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=10,
        close_idx={(trading_days[-1], "sh510300"): 4.1},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="TRANS_UP",
    )

    day_signals = provider.day_signals(trading_days[-1], len(trading_days) - 1, ctx)

    assert day_signals.buy_signals == []
    research_view = _extract_etf_views(day_signals)[1]
    assert research_view["trans_up_redeploy_active"] is False
    assert research_view["trans_up_redeploy_reject_reason"] == "ETF_BETA_TRANS_UP_REDEPLOY_REJECT_NOT_STATE_CHANGE_EDGE"
    assert "ETF_BETA_TRANS_UP_REDEPLOY_REJECT_NOT_STATE_CHANGE_EDGE" in day_signals.diagnostics["etf_beta_runtime_reason_codes"]


def test_cn_etf_beta_trans_up_redeploy_rejects_when_floor_already_satisfied() -> None:
    provider, trading_days = _build_formal_trans_up_redeploy_provider()

    ctx = DayContext(
        positions={"sh510300": 1300},
        position_avg_cost={"sh510300": 4.0},
        cash=94670.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=10,
        close_idx={(trading_days[-1], "sh510300"): 4.1},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="TRANS_UP",
    )

    day_signals = provider.day_signals(trading_days[-1], len(trading_days) - 1, ctx)

    assert day_signals.buy_signals == []
    research_view = _extract_etf_views(day_signals)[1]
    assert research_view["trans_up_redeploy_active"] is False
    assert research_view["trans_up_redeploy_reject_reason"] == "ETF_BETA_TRANS_UP_REDEPLOY_REJECT_FLOOR_ALREADY_SATISFIED"
    assert research_view["trans_up_redeploy_floor_gap"] == pytest.approx(0.0)


def test_cn_etf_beta_trans_up_redeploy_rejects_on_governor_hard_block() -> None:
    provider, trading_days = _build_formal_trans_up_redeploy_provider(hard_blocked=True)

    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=10,
        close_idx={(trading_days[-1], "sh510300"): 4.1},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="TRANS_UP",
    )

    day_signals = provider.day_signals(trading_days[-1], len(trading_days) - 1, ctx)

    assert day_signals.buy_signals == []
    research_view = _extract_etf_views(day_signals)[1]
    assert research_view["trans_up_redeploy_active"] is False
    assert research_view["trans_up_redeploy_reject_reason"] == "ETF_BETA_TRANS_UP_REDEPLOY_REJECT_HARD_BLOCK"
    assert "ETF_BETA_TRANS_UP_REDEPLOY_REJECT_HARD_BLOCK" in research_view["under_deploy_reason_codes"]


def test_cn_etf_beta_precompute_biweekly_rebalance_has_fewer_switch_dates(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2025-01-02", periods=40)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 5.0, len(trading_days), dtype=float)
        close_510050 = np.linspace(3.0, 4.0, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510050.sh"],
            close=np.column_stack([close_510300, close_510050]),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack([close_510300 - 0.2, close_510050 - 0.2]),
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array([], dtype=object)
        self._effective_state_5_arr = np.array([], dtype=object)
        self._regime_risk_budget_multiplier_arr = np.array([], dtype=float)
        self._risk_budget_multiplier_arr = np.array([], dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    common_kwargs = {
        "history": pd.DataFrame(),
        "benchmark": pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 105.0, len(trading_days), dtype=float)}),
        "raw_history": pd.DataFrame(),
        "trading_days": trading_days,
        "strategy": SimpleNamespace(),
        "market_filter_cfg": {
            "enabled": True,
            "long_ma_window": 5,
            "slope_window": 1,
            "slope_ma_period": 3,
            "bull_multiplier": 1.0,
            "light_multiplier": 0.5,
            "trans_down_multiplier": 0.25,
            "trans_up_multiplier": 0.75,
            "bear_multiplier": 0.0,
        },
    }

    weekly = CNETFBetaSignalProvider()
    weekly.precompute(
        **common_kwargs,
        governed_a_share={"etf_beta": {"core_beta_symbols": ["510300.SH", "510050.SH"], "rebalance_frequency": "weekly"}},
    )
    biweekly = CNETFBetaSignalProvider()
    biweekly.precompute(
        **common_kwargs,
        governed_a_share={"etf_beta": {"core_beta_symbols": ["510300.SH", "510050.SH"], "rebalance_frequency": "biweekly"}},
    )

    assert weekly._etf_beta_rebalance_frequency == "weekly"
    assert biweekly._etf_beta_rebalance_frequency == "biweekly"
    assert int(weekly._etf_beta_rebalance_flag_arr.sum()) > int(biweekly._etf_beta_rebalance_flag_arr.sum())
    assert bool(weekly._etf_beta_rebalance_flag_arr[-1]) is True


def test_cn_etf_beta_precompute_supports_broad_based_rotation_template_a(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2024-01-02", periods=320)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 6.2, len(trading_days), dtype=float)
        close_510500 = np.linspace(3.0, 5.6, len(trading_days), dtype=float)
        close_512100 = np.linspace(2.0, 4.4, len(trading_days), dtype=float)
        close_512890 = np.linspace(2.5, 3.8, len(trading_days), dtype=float)
        close_159915 = np.linspace(3.2, 5.8, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510500.sh", "512100.sh", "512890.sh", "159915.sz"],
            close=np.column_stack([close_510300, close_510500, close_512100, close_512890, close_159915]),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.1,
                    close_510500 - 0.1,
                    close_512100 - 0.1,
                    close_512890 - 0.05,
                    close_159915 - 0.12,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array([], dtype=object)
        self._effective_state_5_arr = np.array([], dtype=object)
        self._regime_risk_budget_multiplier_arr = np.array([], dtype=float)
        self._risk_budget_multiplier_arr = np.array([], dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 120.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        market_filter_cfg={
            "enabled": True,
            "long_ma_window": 5,
            "slope_window": 1,
            "slope_ma_period": 3,
            "bull_multiplier": 1.0,
            "light_multiplier": 0.5,
            "trans_down_multiplier": 0.25,
            "trans_up_multiplier": 0.75,
            "bear_multiplier": 0.0,
        },
        governed_a_share={
            "etf_beta": {
                "research_rule_family": "broad_based_rotation_template_a",
                "strategy_role": "auxiliary_beta_sleeve",
                "source_entry_type": "cn_etf_research_entry",
                "local_policy_mode": "legacy_beta_selection",
                "exposure_policy_family": "default",
                "template_id": "broad_based_rotation_template_a",
                "template_asset_pool_version": "A0",
                "template_role_map": {
                    "510300.SH": "hs300",
                    "510500.SH": "csi500",
                    "512100.SH": "csi1000_proxy",
                    "512890.SH": "dividend_proxy",
                    "159915.SZ": "growth_seat",
                },
                "template_proxy_map": {
                    "512100.SH": "CSI1000_STANDARD",
                    "512890.SH": "DIVIDEND_STANDARD",
                },
                "template_target_formal_symbols": [
                    "510300.SH",
                    "510500.SH",
                    "CSI1000_STANDARD",
                    "DIVIDEND_STANDARD",
                ],
                "growth_seat_symbol": "159915.SZ",
                "core_beta_symbols": ["510300.SH", "510500.SH", "512100.SH", "512890.SH", "159915.SZ"],
                "limited_defense_candidates": [],
                "rebalance_frequency": "monthly",
                "absolute_filter_mode": "ma200_and_positive_12m",
                "fallback_mode": "cash",
                "relative_strength_fast_window": 63,
                "relative_strength_mid_window": 126,
                "relative_strength_slow_window": 252,
                "relative_strength_fast_weight": 0.2,
                "relative_strength_mid_weight": 0.3,
                "relative_strength_slow_weight": 0.5,
                "max_selected_symbols": 2,
            }
        },
    )

    assert provider._etf_beta_rule_family == "broad_based_rotation_template_a"
    assert provider._etf_beta_rebalance_frequency == "monthly"
    assert provider._etf_beta_absolute_filter_mode == "ma200_and_positive_12m"
    assert provider._etf_beta_rs_mid_window == 126
    assert provider._etf_beta_rs_mid_weight == 0.3
    assert provider._etf_beta_template_asset_pool_version == "A0"
    assert provider._etf_beta_template_proxy_map["512100.SH"] == "CSI1000_STANDARD"
    assert provider._etf_beta_growth_seat_symbol == "159915.SZ"
    assert int(provider._etf_beta_rebalance_flag_arr.sum()) < len(trading_days) // 4
    latest_selected = provider._etf_beta_selected_symbols_arr[-1]
    assert len(latest_selected) == 2
    assert "510500.SH" in latest_selected
    assert set(latest_selected).issubset(
        {"510300.SH", "510500.SH", "512100.SH", "512890.SH", "159915.SZ"}
    )
    latest_reason_codes = provider._etf_beta_selection_reason_codes_arr[-1]
    growth_or_proxy_symbol = next(
        symbol for symbol in latest_selected if symbol != "510500.SH"
    )
    assert "ABSOLUTE_MA200_PASS" in latest_reason_codes[growth_or_proxy_symbol]
    assert "ABSOLUTE_RET12_PASS" in latest_reason_codes[growth_or_proxy_symbol]
    assert "RS252_RANK_PASS" in latest_reason_codes[growth_or_proxy_symbol]
    assert "RS126_RANK_PASS" in latest_reason_codes[growth_or_proxy_symbol]
    assert "RS63_RANK_PASS" in latest_reason_codes[growth_or_proxy_symbol]
    assert "POOL::A0" in latest_reason_codes[growth_or_proxy_symbol]
    assert any(
        code.startswith("ROLE::") for code in latest_reason_codes[growth_or_proxy_symbol]
    )


def test_cn_etf_beta_precompute_supports_a0_core_satellite_v2(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2024-01-02", periods=320)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 5.9, len(trading_days), dtype=float)
        close_510500 = np.linspace(3.0, 6.1, len(trading_days), dtype=float)
        close_512100 = np.linspace(2.0, 4.6, len(trading_days), dtype=float)
        close_512890 = np.linspace(2.5, 3.7, len(trading_days), dtype=float)
        close_159915 = np.linspace(3.2, 6.4, len(trading_days), dtype=float)
        close_511010 = np.linspace(3.0, 3.3, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510500.sh", "512100.sh", "512890.sh", "159915.sz", "511010.sh"],
            close=np.column_stack([close_510300, close_510500, close_512100, close_512890, close_159915, close_511010]),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.1,
                    close_510500 - 0.1,
                    close_512100 - 0.1,
                    close_512890 - 0.05,
                    close_159915 - 0.12,
                    close_511010 - 0.03,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array(["BULL"] * len(trading_days), dtype=object)
        self._effective_state_5_arr = np.array(["BULL"] * len(trading_days), dtype=object)
        self._regime_risk_budget_multiplier_arr = np.ones(len(trading_days), dtype=float)
        self._risk_budget_multiplier_arr = np.ones(len(trading_days), dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 120.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        governed_a_share={
            "etf_beta": {
                "research_rule_family": "broad_based_rotation_template_a0_core_satellite_v2",
                "strategy_role": "auxiliary_beta_sleeve",
                "source_entry_type": "cn_etf_research_entry",
                "local_policy_mode": "legacy_beta_selection",
                "exposure_policy_family": "default",
                "template_id": "broad_based_rotation_template_a0_core_satellite_v2",
                "template_asset_pool_version": "A0_V2",
                "template_role_map": {
                    "510300.SH": "hs300",
                    "510500.SH": "csi500",
                    "512100.SH": "csi1000_proxy",
                    "512890.SH": "dividend_proxy",
                    "159915.SZ": "growth_seat",
                },
                "template_proxy_map": {
                    "512100.SH": "CSI1000_STANDARD",
                    "512890.SH": "DIVIDEND_STANDARD",
                },
                "template_target_formal_symbols": [
                    "510300.SH",
                    "510500.SH",
                    "159845.SZ",
                    "510880.SH",
                    "159915.SZ",
                ],
                "proxy_replacement_mode": "none",
                "formal_replacement_pairs": {
                    "512100.SH": "159845.SZ",
                    "512890.SH": "510880.SH",
                },
                "core_slot_symbols": ["510300.SH", "510500.SH", "512100.SH", "512890.SH"],
                "growth_slot_symbols": ["159915.SZ"],
                "growth_seat_symbol": "159915.SZ",
                "core_beta_symbols": ["510300.SH", "510500.SH", "512100.SH", "512890.SH", "159915.SZ"],
                "limited_defense_candidates": [],
                "rebalance_frequency": "monthly",
                "absolute_filter_mode": "ma200_and_positive_12m",
                "fallback_mode": "single_symbol",
                "fallback_symbol": "511010.SH",
                "relative_strength_fast_window": 63,
                "relative_strength_mid_window": 126,
                "relative_strength_slow_window": 252,
                "relative_strength_fast_weight": 0.2,
                "relative_strength_mid_weight": 0.3,
                "relative_strength_slow_weight": 0.5,
                "max_selected_symbols": 2,
            }
        },
    )

    assert provider._etf_beta_rule_family == "broad_based_rotation_template_a0_core_satellite_v2"
    assert provider._etf_beta_proxy_replacement_mode == "none"
    assert provider._etf_beta_formal_replacement_pairs["512100.SH"] == "159845.SZ"
    latest_selected = provider._etf_beta_selected_symbols_arr[-1]
    assert latest_selected == ["512100.SH", "159915.SZ"]
    assert provider._etf_beta_core_slot_selected_symbol_arr[-1] == "512100.SH"
    assert provider._etf_beta_growth_slot_selected_symbol_arr[-1] == "159915.SZ"
    latest_reason_codes = provider._etf_beta_selection_reason_codes_arr[-1]
    assert "SLOT::CORE_SLOT" in latest_reason_codes["512100.SH"]
    assert "SLOT::GROWTH_SLOT" in latest_reason_codes["159915.SZ"]
    slot_selection_reason_codes = provider._etf_beta_slot_selection_reason_codes_arr[-1]
    assert "SELECTED::512100.SH" in slot_selection_reason_codes["core_slot"]
    assert "SELECTED::159915.SZ" in slot_selection_reason_codes["growth_slot"]


def test_cn_etf_beta_a0_core_satellite_v2_light_state_only_keeps_core_slot(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2024-01-02", periods=320)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 5.9, len(trading_days), dtype=float)
        close_510500 = np.linspace(3.0, 6.1, len(trading_days), dtype=float)
        close_512100 = np.linspace(2.0, 4.6, len(trading_days), dtype=float)
        close_512890 = np.linspace(2.5, 3.7, len(trading_days), dtype=float)
        close_159915 = np.linspace(3.2, 6.4, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510500.sh", "512100.sh", "512890.sh", "159915.sz"],
            close=np.column_stack([close_510300, close_510500, close_512100, close_512890, close_159915]),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.1,
                    close_510500 - 0.1,
                    close_512100 - 0.1,
                    close_512890 - 0.05,
                    close_159915 - 0.12,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array(["LIGHT"] * len(trading_days), dtype=object)
        self._effective_state_5_arr = np.array(["LIGHT"] * len(trading_days), dtype=object)
        self._regime_risk_budget_multiplier_arr = np.full(len(trading_days), 0.5, dtype=float)
        self._risk_budget_multiplier_arr = np.full(len(trading_days), 0.5, dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 110.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        governed_a_share={
            "etf_beta": {
                "research_rule_family": "broad_based_rotation_template_a0_core_satellite_v2",
                "strategy_role": "auxiliary_beta_sleeve",
                "source_entry_type": "cn_etf_research_entry",
                "local_policy_mode": "legacy_beta_selection",
                "exposure_policy_family": "default",
                "core_slot_symbols": ["510300.SH", "510500.SH", "512100.SH", "512890.SH"],
                "growth_slot_symbols": ["159915.SZ"],
                "growth_seat_symbol": "159915.SZ",
                "core_beta_symbols": ["510300.SH", "510500.SH", "512100.SH", "512890.SH", "159915.SZ"],
                "rebalance_frequency": "monthly",
                "absolute_filter_mode": "ma200_and_positive_12m",
                "fallback_mode": "cash",
                "relative_strength_fast_window": 63,
                "relative_strength_mid_window": 126,
                "relative_strength_slow_window": 252,
                "relative_strength_fast_weight": 0.2,
                "relative_strength_mid_weight": 0.3,
                "relative_strength_slow_weight": 0.5,
                "max_selected_symbols": 2,
            }
        },
    )

    latest_selected = provider._etf_beta_selected_symbols_arr[-1]
    assert latest_selected == ["512100.SH", "159915.SZ"]
    assert provider._etf_beta_core_slot_selected_symbol_arr[-1] == "512100.SH"
    assert provider._etf_beta_growth_slot_selected_symbol_arr[-1] == "159915.SZ"
    slot_under_deploy = provider._etf_beta_slot_under_deploy_reason_codes_arr[-1]
    assert "growth_slot" not in slot_under_deploy


def test_cn_etf_beta_precompute_supports_broad_based_governed_policy(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2024-01-02", periods=320)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 5.9, len(trading_days), dtype=float)
        close_510500 = np.linspace(3.0, 6.1, len(trading_days), dtype=float)
        close_159915 = np.linspace(3.2, 6.4, len(trading_days), dtype=float)
        close_511010 = np.linspace(3.0, 3.3, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510500.sh", "159915.sz", "511010.sh"],
            close=np.column_stack([close_510300, close_510500, close_159915, close_511010]),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.1,
                    close_510500 - 0.1,
                    close_159915 - 0.12,
                    close_511010 - 0.03,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array(["TRANS_DOWN"] * len(trading_days), dtype=object)
        self._effective_state_5_arr = np.array(["TRANS_DOWN"] * len(trading_days), dtype=object)
        self._regime_risk_budget_multiplier_arr = np.full(len(trading_days), 0.4, dtype=float)
        self._risk_budget_multiplier_arr = np.full(len(trading_days), 0.4, dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 110.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        governed_a_share={
            "etf_beta": {
                "research_rule_family": "broad_based_rotation_template_a",
                "strategy_role": "auxiliary_beta_sleeve",
                "source_entry_type": "cn_etf_research_entry",
                "local_policy_mode": "legacy_beta_selection",
                "template_id": "broad_based_governed_exposure_policy",
                "template_asset_pool_version": "A0_GOVERNED",
                "template_role_map": {
                    "510300.SH": "hs300",
                    "510500.SH": "csi500",
                    "159915.SZ": "growth_style",
                },
                "core_beta_symbols": ["510300.SH", "510500.SH", "159915.SZ"],
                "limited_defense_candidates": [],
                "rebalance_frequency": "monthly",
                "absolute_filter_mode": "ma200_and_positive_12m",
                "fallback_mode": "single_symbol",
                "fallback_symbol": "511010.SH",
                "relative_strength_fast_window": 63,
                "relative_strength_mid_window": 126,
                "relative_strength_slow_window": 252,
                "relative_strength_fast_weight": 0.2,
                "relative_strength_mid_weight": 0.3,
                "relative_strength_slow_weight": 0.5,
                "max_selected_symbols": 2,
                "exposure_policy_family": "broad_based_governed_v1",
                "policy_scope": "broad_based_only",
                "broad_based_only": True,
                "layering_policy": "light_trans_down_accumulate",
                "target_exposure_by_state_5": {
                    "BULL": 1.0,
                    "TRANS_UP": 0.9,
                    "LIGHT": 0.7,
                    "TRANS_DOWN": 0.3,
                    "RISK_OFF": 0.0,
                },
                "min_deployable_exposure_by_state_5": {
                    "BULL": 0.5,
                    "TRANS_UP": 0.4,
                    "LIGHT": 0.25,
                    "TRANS_DOWN": 0.15,
                    "RISK_OFF": 0.0,
                },
                "target_selected_count_by_state_5": {
                    "BULL": 2,
                    "TRANS_UP": 2,
                    "LIGHT": 2,
                    "TRANS_DOWN": 1,
                    "RISK_OFF": 0,
                },
                "fallback_allowed_by_state_5": {
                    "BULL": True,
                    "TRANS_UP": True,
                    "LIGHT": True,
                    "TRANS_DOWN": True,
                    "RISK_OFF": False,
                },
            }
        },
    )

    assert provider._etf_beta_slot_cap_arr[-1] == 2
    assert provider._etf_beta_target_selected_count_arr[-1] == 2
    assert provider._etf_beta_exposure_policy_family_arr[-1] == "broad_based_governed_v1"
    assert provider._etf_beta_policy_scope_arr[-1] == "broad_based_only"
    assert bool(provider._etf_beta_broad_based_only_arr[-1]) is True
    assert provider._etf_beta_layering_policy_arr[-1] == "light_trans_down_accumulate"
    assert provider._etf_beta_layering_band_arr[-1] == "CONTROLLED_TRANS_DOWN"
    assert bool(provider._etf_beta_layering_active_arr[-1]) is True
    assert "ETF_BETA_LAYERING_CONTROLLED_TRANS_DOWN" in provider._etf_beta_layering_reason_codes_arr[-1]
    assert provider._etf_beta_target_selected_count_source_arr[-1] == "weak_state_defense_policy::TRANS_DOWN"
    assert provider._etf_beta_fallback_allowed_source_arr[-1] == "state_map::TRANS_DOWN"

    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=1,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=False,
        market_state="TRANS_DOWN",
    )

    day_signals = provider.day_signals(trading_days[-1], len(trading_days) - 1, ctx)

    formal_view, research_view = _extract_etf_views(day_signals)
    assert formal_view["exposure_policy_family"] == "broad_based_governed_v1"
    assert formal_view["policy_scope"] == "broad_based_only"
    assert formal_view["broad_based_only"] is True
    assert research_view["layering_policy"] == "light_trans_down_accumulate"
    assert research_view["layering_band"] == "CONTROLLED_TRANS_DOWN"
    assert research_view["layering_active"] is True
    assert "ETF_BETA_LAYERING_CONTROLLED_TRANS_DOWN" in research_view["layering_reason_codes"]
    assert formal_view["target_selected_count_source"] == "weak_state_defense_policy::TRANS_DOWN"
    assert formal_view["fallback_allowed_source"] == "state_map::TRANS_DOWN"
    assert "ETF_BETA_BROAD_BASED_GOVERNED_POLICY_ACTIVE" in day_signals.diagnostics["etf_beta_runtime_reason_codes"]


def test_cn_etf_beta_precompute_supports_governed_broad_based_standalone_mainline(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2024-01-02", periods=320)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 5.7, len(trading_days), dtype=float)
        close_510500 = np.linspace(3.0, 6.0, len(trading_days), dtype=float)
        close_159915 = np.linspace(3.2, 6.2, len(trading_days), dtype=float)
        close_511010 = np.linspace(3.0, 3.3, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510500.sh", "159915.sz", "511010.sh"],
            close=np.column_stack([close_510300, close_510500, close_159915, close_511010]),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.12,
                    close_510500 - 0.12,
                    close_159915 - 0.15,
                    close_511010 - 0.04,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array(["TRANS_DOWN"] * len(trading_days), dtype=object)
        self._effective_state_5_arr = np.array(["TRANS_DOWN"] * len(trading_days), dtype=object)
        self._regime_risk_budget_multiplier_arr = np.full(len(trading_days), 0.35, dtype=float)
        self._risk_budget_multiplier_arr = np.full(len(trading_days), 0.35, dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 110.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        governed_a_share={
            "etf_beta": {
                "strategy_role": "governed_broad_based_standalone_mainline",
                "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                "governor_boundary_mode": "consume_governor_state_and_budget",
                "local_policy_mode": "broad_based_rotation_mainline",
                "controlled_accumulation_mode": "light_and_controlled_trans_down",
                "research_rule_family": "broad_based_rotation_template_a",
                "template_id": "cn_broad_based_standalone_mainline",
                "template_asset_pool_version": "MAINLINE_V1",
                "absolute_filter_profile": "ma200_ret12",
                "candidate_pool_profile": "a0_proxy_pool",
                "selection_chain_profile": "global_top2_12_6_3",
                "template_role_map": {
                    "510300.SH": "hs300",
                    "510500.SH": "csi500",
                    "159915.SZ": "growth_style",
                },
                "core_beta_symbols": ["510300.SH", "510500.SH", "159915.SZ"],
                "limited_defense_candidates": [],
                "rebalance_frequency": "monthly",
                "absolute_filter_mode": "ma200_and_positive_12m",
                "fallback_mode": "single_symbol",
                "fallback_symbol": "511010.SH",
                "relative_strength_fast_window": 63,
                "relative_strength_mid_window": 126,
                "relative_strength_slow_window": 252,
                "relative_strength_fast_weight": 0.2,
                "relative_strength_mid_weight": 0.3,
                "relative_strength_slow_weight": 0.5,
                "max_selected_symbols": 2,
                "exposure_policy_family": "broad_based_standalone_mainline_v1",
                "policy_scope": "broad_based_only",
                "broad_based_only": True,
                "target_exposure_by_state_5": {
                    "BULL": 1.0,
                    "TRANS_UP": 0.9,
                    "LIGHT": 0.75,
                    "TRANS_DOWN": 0.35,
                    "RISK_OFF": 0.0,
                },
                "min_deployable_exposure_by_state_5": {
                    "BULL": 0.45,
                    "TRANS_UP": 0.35,
                    "LIGHT": 0.2,
                    "TRANS_DOWN": 0.1,
                    "RISK_OFF": 0.0,
                },
                "target_selected_count_by_state_5": {
                    "BULL": 2,
                    "TRANS_UP": 2,
                    "LIGHT": 2,
                    "TRANS_DOWN": 1,
                    "RISK_OFF": 0,
                },
                "fallback_allowed_by_state_5": {
                    "BULL": True,
                    "TRANS_UP": True,
                    "LIGHT": True,
                    "TRANS_DOWN": True,
                    "RISK_OFF": False,
                },
            }
        },
    )

    assert provider._etf_beta_strategy_role == "governed_broad_based_standalone_mainline"
    assert provider._etf_beta_governor_boundary_mode == "consume_governor_state_and_budget"
    assert provider._etf_beta_local_policy_mode == "broad_based_rotation_mainline"
    assert provider._etf_beta_controlled_accumulation_mode == "light_and_controlled_trans_down"
    assert provider._etf_beta_exposure_policy_family_arr[-1] == "broad_based_standalone_mainline_v1"
    assert provider._etf_beta_absolute_filter_profile == "ma200_ret12"
    assert provider._etf_beta_candidate_pool_profile == "a0_proxy_pool"
    assert provider._etf_beta_selection_chain_profile == "global_top2_12_6_3"

    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=2,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=False,
        market_state="TRANS_DOWN",
    )
    day_signals = provider.day_signals(trading_days[-1], len(trading_days) - 1, ctx)

    formal_view, research_view = _extract_etf_views(day_signals)
    assert formal_view["strategy_role"] == "governed_broad_based_standalone_mainline"
    assert formal_view["governor_boundary_mode"] == "consume_governor_state_and_budget"
    assert formal_view["local_policy_mode"] == "broad_based_rotation_mainline"
    assert research_view["controlled_accumulation_mode"] == "light_and_controlled_trans_down"
    assert research_view["runtime_selection"]["absolute_filter_profile"] == "ma200_ret12"
    assert research_view["runtime_selection"]["candidate_pool_profile"] == "a0_proxy_pool"
    assert research_view["runtime_selection"]["selection_chain_profile"] == "global_top2_12_6_3"
    assert "eligible_after_selection_chain" in research_view["selection_chain_winner_counts"]
    assert "ETF_BETA_STANDALONE_MAINLINE_ACTIVE" in day_signals.diagnostics["etf_beta_runtime_reason_codes"]
    assert any(code.startswith("GOVERNOR_BOUNDARY_MODE::CONSUME_GOVERNOR_STATE_AND_BUDGET") for code in day_signals.diagnostics["etf_beta_governor_boundary_reason_codes"])
    assert any(code.startswith("ETF_BETA_CONTROLLED_ACCUMULATION_MODE::LIGHT_AND_CONTROLLED_TRANS_DOWN") for code in day_signals.diagnostics["etf_beta_local_policy_reason_codes"])


def test_cn_etf_beta_precompute_supports_bottleneck_profiles(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2024-01-02", periods=320)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 6.0, len(trading_days), dtype=float)
        close_159845 = np.linspace(2.0, 3.2, len(trading_days), dtype=float)
        close_510880 = np.linspace(2.5, 3.4, len(trading_days), dtype=float)
        close_159915 = np.linspace(3.0, 5.8, len(trading_days), dtype=float)
        close_512100 = np.linspace(2.0, 4.0, len(trading_days), dtype=float)
        close_512890 = np.linspace(2.0, 3.0, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "159845.sz", "510880.sh", "159915.sz", "512100.sh", "512890.sh"],
            close=np.column_stack([close_510300, close_159845, close_510880, close_159915, close_512100, close_512890]),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.1,
                    close_159845 - 0.08,
                    close_510880 - 0.05,
                    close_159915 - 0.12,
                    close_512100 - 0.1,
                    close_512890 - 0.05,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array([], dtype=object)
        self._effective_state_5_arr = np.array([], dtype=object)
        self._regime_risk_budget_multiplier_arr = np.array([], dtype=float)
        self._risk_budget_multiplier_arr = np.array([], dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 120.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        market_filter_cfg={
            "enabled": True,
            "long_ma_window": 5,
            "slope_window": 1,
            "slope_ma_period": 3,
            "bull_multiplier": 1.0,
            "light_multiplier": 0.5,
            "trans_down_multiplier": 0.25,
            "trans_up_multiplier": 0.75,
            "bear_multiplier": 0.0,
        },
        governed_a_share={
            "etf_beta": {
                "research_rule_family": "broad_based_rotation_template_a",
                "absolute_filter_profile": "ma150_ret12",
                "candidate_pool_profile": "standard_overlap_pool",
                "selection_chain_profile": "global_top2_6_3_1",
                "core_beta_symbols": ["510300.SH", "159845.SZ", "510880.SH", "159915.SZ"],
                "fallback_mode": "cash",
            }
        },
    )

    assert provider._etf_beta_absolute_filter_mode == "ma150_and_positive_12m"
    assert provider._etf_beta_candidate_pool_symbols == ["510300.SH", "159845.SZ", "510880.SH", "159915.SZ"]
    assert provider._etf_beta_rs_fast_window == 21
    assert provider._etf_beta_rs_mid_window == 63
    assert provider._etf_beta_rs_slow_window == 126
    assert provider._etf_beta_max_selected_symbols == 2
    assert provider._etf_beta_candidate_pool_reject_reason_counts["POOL_PROFILE_EXCLUDED::SMALL_CAP_EQUITY"] >= 1


def test_cn_etf_beta_precompute_allows_research_only_symbol_mix_for_standalone_mainline(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2024-01-02", periods=260)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 5.0, len(trading_days), dtype=float)
        close_518880 = np.linspace(3.0, 4.0, len(trading_days), dtype=float)
        close_511010 = np.linspace(3.0, 3.1, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "518880.sh", "511010.sh"],
            close=np.column_stack([close_510300, close_518880, close_511010]),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack([close_510300 - 0.1, close_518880 - 0.1, close_511010 - 0.02]),
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array([], dtype=object)
        self._effective_state_5_arr = np.array([], dtype=object)
        self._regime_risk_budget_multiplier_arr = np.array([], dtype=float)
        self._risk_budget_multiplier_arr = np.array([], dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 110.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        governed_a_share={
            "etf_beta": {
                "strategy_role": "governed_broad_based_standalone_mainline",
                "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                "governor_boundary_mode": "consume_governor_state_and_budget",
                "local_policy_mode": "broad_based_rotation_mainline",
                "research_rule_family": "broad_based_rotation_template_a",
                "core_beta_symbols": ["510300.SH", "518880.SH"],
                "fallback_mode": "single_symbol",
                "fallback_symbol": "511010.SH",
                "exposure_policy_family": "broad_based_standalone_mainline_v1",
            }
        },
    )

    assert provider._etf_beta_strategy_role == "governed_broad_based_standalone_mainline"
    assert provider._etf_beta_formal_scope_symbols == ["510300.SH", "518880.SH"]
    assert provider._etf_beta_fallback_symbol == "sh511010"


def test_cn_etf_beta_day_signals_exposes_vol_target_scale(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2025-01-02", periods=260)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        vol_returns = np.array([0.03 if idx % 2 == 0 else -0.015 for idx in range(len(trading_days))], dtype=float)
        base_returns = np.array([0.001 for _ in range(len(trading_days))], dtype=float)
        close_510300 = 4.0 * np.cumprod(1.0 + vol_returns)
        close_510050 = 4.0 * np.cumprod(1.0 + base_returns)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510050.sh"],
            close=np.column_stack([close_510300, close_510050]),
        )
        self._sym_to_col = {"sh510300": 0, "sh510050": 1}
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack([close_510300 - 0.1, close_510050 - 0.1]),
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array([], dtype=object)
        self._effective_state_5_arr = np.array([], dtype=object)
        self._regime_risk_budget_multiplier_arr = np.array([], dtype=float)
        self._risk_budget_multiplier_arr = np.array([], dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 130.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        market_filter_cfg={
            "enabled": True,
            "long_ma_window": 5,
            "slope_window": 1,
            "slope_ma_period": 3,
            "bull_multiplier": 1.0,
            "light_multiplier": 0.5,
            "trans_down_multiplier": 0.25,
            "trans_up_multiplier": 0.75,
            "bear_multiplier": 0.0,
        },
        governed_a_share={
            "etf_beta": {
                "research_rule_family": "dual_momentum_vol_target",
                "strategy_role": "auxiliary_beta_sleeve",
                "source_entry_type": "cn_etf_research_entry",
                "local_policy_mode": "legacy_beta_selection",
                "exposure_policy_family": "default",
                "core_beta_symbols": ["510300.SH", "510050.SH"],
                "absolute_filter_mode": "ma120",
                "fallback_mode": "cash",
                "relative_strength_fast_window": 60,
                "relative_strength_slow_window": 120,
                "relative_strength_fast_weight": 0.4,
                "relative_strength_slow_weight": 0.6,
                "max_selected_symbols": 1,
                "vol_target_window": 20,
                "vol_target_annualized_target": 0.18,
                "vol_target_min_scale": 0.35,
                "vol_target_max_scale": 1.0,
            }
        },
    )

    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=1,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )
    day_idx = len(trading_days) - 1
    day_signals = provider.day_signals(trading_days[day_idx], day_idx, ctx)

    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh510300"]
    buy_meta = day_signals.buy_signals[0].meta
    assert float(buy_meta["target_weight"]) < float(buy_meta["target_exposure"])
    research_view = _extract_etf_views(day_signals)[1]
    assert research_view["runtime_vol_target"]["active"] is True
    assert int(research_view["runtime_vol_target"]["window"]) == 20
    assert "ETF_BETA_VOL_TARGET_ACTIVE" in day_signals.diagnostics["etf_beta_runtime_reason_codes"]
    assert float(research_view["runtime_vol_target"]["scale_by_symbol"]["510300.SH"]) < 1.0


def test_cn_etf_beta_day_signals_buy_fallback_symbol_when_selected() -> None:
    trading_day = date(2026, 3, 20)
    provider = CNETFBetaSignalProvider()
    provider._mx = SimpleNamespace(
        symbols=["sh510300", "sh511010"],
        close=np.array([[4.0, 3.1]], dtype=float),
        dates=[trading_day],
    )
    provider._feats = SimpleNamespace(
        trend_fast_ma=np.array([[3.5, 3.0]], dtype=float),
    )
    provider._sym_to_col = {"sh510300": 0, "sh511010": 1}
    provider._effective_state_5_arr = np.array(["BULL"], dtype=object)
    provider._trade_mode_name_arr = np.array(["TREND_MAIN"], dtype=object)
    provider._etf_beta_slot_cap_arr = np.array([1], dtype=np.int32)
    provider._etf_beta_rebalance_flag_arr = np.array([True], dtype=bool)
    provider._etf_beta_formal_scope_symbols = ["510300.SH"]
    provider._etf_beta_eligible_symbols_arr = np.array([[]], dtype=object)
    provider._etf_beta_selected_symbols_arr = np.array([["511010.SH"]], dtype=object)
    provider._etf_beta_selection_reason_codes_arr = np.array(
        [{"511010.SH": ["ETF_BETA_FALLBACK_SINGLE_SYMBOL", "FALLBACK_SYMBOL::511010.SH"]}],
        dtype=object,
    )
    provider._etf_beta_runtime_reason_codes_arr = np.array(
        [["ETF_BETA_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER", "ETF_BETA_FALLBACK_ACTIVE"]],
        dtype=object,
    )
    provider._etf_beta_rule_family = "dual_momentum_basic"
    provider._etf_beta_absolute_filter_mode = "positive_12m"
    provider._etf_beta_fallback_mode = "single_symbol"
    provider._etf_beta_fallback_symbol = "sh511010"

    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=1,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )

    day_signals = provider.day_signals(trading_day, 0, ctx)

    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh511010"]
    assert [signal.reason_code for signal in day_signals.buy_signals] == ["ETF_BETA_FALLBACK_BUY"]
    assert "ETF_BETA_FALLBACK_ACTIVE" in day_signals.diagnostics["etf_beta_runtime_reason_codes"]


def test_cn_etf_beta_day_signals_partial_fallback_fill_when_second_slot_missing() -> None:
    trading_day = date(2026, 3, 20)
    provider = CNETFBetaSignalProvider()
    provider._mx = SimpleNamespace(
        symbols=["sh510300", "sh510050", "sh511010"],
        close=np.array([[4.0, 2.8, 3.1]], dtype=float),
        dates=[trading_day],
    )
    provider._feats = SimpleNamespace(
        trend_fast_ma=np.array([[3.5, 2.7, 3.0]], dtype=float),
    )
    provider._sym_to_col = {"sh510300": 0, "sh510050": 1, "sh511010": 2}
    provider._effective_state_5_arr = np.array(["BULL"], dtype=object)
    provider._trade_mode_name_arr = np.array(["TREND_MAIN"], dtype=object)
    provider._etf_beta_slot_cap_arr = np.array([2], dtype=np.int32)
    provider._etf_beta_rebalance_flag_arr = np.array([True], dtype=bool)
    provider._etf_beta_formal_scope_symbols = ["510300.SH", "510050.SH"]
    provider._etf_beta_eligible_symbols_arr = np.array([["510300.SH"]], dtype=object)
    provider._etf_beta_selected_symbols_arr = np.array([["510300.SH", "511010.SH"]], dtype=object)
    provider._etf_beta_selection_reason_codes_arr = np.array(
        [
            {
                "510300.SH": ["ETF_BETA_CORE_SCOPE", "ABSOLUTE_MA120_PASS"],
                "511010.SH": [
                    "ETF_BETA_FALLBACK_SINGLE_SYMBOL",
                    "FALLBACK_SYMBOL::511010.SH",
                    "UNDERFILLED_DEPLOYMENT_FILL",
                ],
            }
        ],
        dtype=object,
    )
    provider._etf_beta_runtime_reason_codes_arr = np.array(
        [["ETF_BETA_WEEKLY_SELECTION_ACTIVE", "ETF_BETA_FALLBACK_ACTIVE", "ETF_BETA_FALLBACK_PARTIAL_FILL_ACTIVE"]],
        dtype=object,
    )
    provider._etf_beta_rule_family = "dual_momentum_basic"
    provider._etf_beta_strategy_role = "auxiliary_beta_sleeve"
    provider._etf_beta_local_policy_mode = "legacy_beta_selection"
    provider._etf_beta_absolute_filter_mode = "ma120"
    provider._etf_beta_fallback_mode = "single_symbol"
    provider._etf_beta_fallback_symbol = "sh511010"
    provider._etf_beta_max_selected_symbols = 2
    provider._etf_beta_rebalance_frequency = "weekly"

    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=2,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )

    day_signals = provider.day_signals(trading_day, 0, ctx)

    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh510300", "sh511010"]
    assert [signal.reason_code for signal in day_signals.buy_signals] == ["ETF_BETA_WEEKLY_RS", "ETF_BETA_FALLBACK_BUY"]
    assert day_signals.diagnostics["etf_beta_selected_cap"] == 2
    assert day_signals.diagnostics["etf_beta_fallback_active"] is True
    assert "ETF_BETA_FALLBACK_PARTIAL_FILL_ACTIVE" in _extract_etf_views(day_signals)[1]["under_deploy_reason_codes"]


def test_compress_research_mainline_live_targets_keeps_partial_fill_fallback_at_zero() -> None:
    compressed, per_symbol = _compress_research_mainline_live_targets(
        strategy_role="governed_broad_based_standalone_mainline",
        exposure_policy_family="broad_based_standalone_mainline_v1",
        state_5="BULL",
        selected_symbols=["510300.SH", "511010.SH"],
        target_exposure_by_symbol={"510300.SH": 1.0, "511010.SH": 0.0},
        live_target=0.8,
    )

    assert compressed["510300.SH"] == pytest.approx(0.8)
    assert compressed["511010.SH"] == pytest.approx(0.0)
    assert per_symbol == pytest.approx(0.8)


def test_compress_research_mainline_live_targets_preserves_full_fallback_replacement() -> None:
    compressed, per_symbol = _compress_research_mainline_live_targets(
        strategy_role="governed_broad_based_standalone_mainline",
        exposure_policy_family="broad_based_standalone_mainline_v1",
        state_5="RISK_OFF",
        selected_symbols=["511010.SH"],
        target_exposure_by_symbol={"511010.SH": 0.0},
        live_target=0.15,
    )

    assert compressed["511010.SH"] == pytest.approx(0.15)
    assert per_symbol == pytest.approx(0.15)


def test_resolve_standalone_live_seat_symbols_prefers_previous_live_seats_for_trans_up() -> None:
    symbols, source = _resolve_standalone_live_seat_symbols(
        strategy_role="governed_broad_based_standalone_mainline",
        exposure_policy_family="broad_based_standalone_mainline_v1",
        state_5="TRANS_UP",
        rebalance_day=False,
        governor_hard_blocked=False,
        target_exposure=0.9,
        selected_cap=2,
        current_selected_symbols=[],
        previous_selected_symbols=["510300.SH", "588000.SH"],
        target_exposure_by_symbol={"510300.SH": 0.36, "588000.SH": 0.36},
        core_accumulator_symbols=["510300.SH"],
    )

    assert symbols == ["510300.SH", "588000.SH"]
    assert source == "previous_live_seats"


def test_resolve_standalone_live_seat_symbols_keeps_risk_off_core_only() -> None:
    symbols, source = _resolve_standalone_live_seat_symbols(
        strategy_role="governed_broad_based_standalone_mainline",
        exposure_policy_family="broad_based_standalone_mainline_v1",
        state_5="RISK_OFF",
        rebalance_day=False,
        governor_hard_blocked=False,
        target_exposure=0.15,
        selected_cap=2,
        current_selected_symbols=[],
        previous_selected_symbols=[],
        target_exposure_by_symbol={"510300.SH": 0.15, "588000.SH": 0.05},
        core_accumulator_symbols=["510300.SH"],
    )

    assert symbols == ["510300.SH"]
    assert source == "target_contract_symbols"

