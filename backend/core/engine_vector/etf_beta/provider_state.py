from __future__ import annotations

import numpy as np
from datetime import date

from backend.core.config.etf_beta_contract import *


def reset_etf_beta_provider_state(provider) -> None:
    self = provider
    self._etf_beta_slot_cap_arr: np.ndarray = np.array([], dtype=np.int32)
    self._etf_beta_rebalance_flag_arr: np.ndarray = np.array([], dtype=bool)
    self._etf_beta_formal_scope_symbols: list[str] = []
    self._etf_beta_eligible_symbols_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_selected_symbols_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_selection_reason_codes_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_runtime_reason_codes_arr: np.ndarray = np.array([], dtype=object)
    self._market_state_name_map: dict[date, str] = {}
    self._trade_mode_name_map: dict[date, str] = {}
    self._etf_beta_rule_family = CN_ETF_BETA_RULE_FAMILY
    self._etf_beta_template_id = ""
    self._etf_beta_template_asset_pool_version = ""
    self._etf_beta_template_role_map: dict[str, str] = {}
    self._etf_beta_template_proxy_map: dict[str, str] = {}
    self._etf_beta_template_target_formal_symbols: list[str] = []
    self._etf_beta_proxy_replacement_mode = "none"
    self._etf_beta_formal_replacement_pairs: dict[str, str] = {}
    self._etf_beta_core_slot_symbols: list[str] = []
    self._etf_beta_growth_slot_symbols: list[str] = []
    self._etf_beta_growth_seat_symbol = ""
    self._etf_beta_absolute_filter_profile = CN_ETF_BETA_ABSOLUTE_FILTER_PROFILE
    self._etf_beta_candidate_pool_profile = CN_ETF_BETA_CANDIDATE_POOL_PROFILE
    self._etf_beta_selection_chain_profile = CN_ETF_BETA_SELECTION_CHAIN_PROFILE
    self._etf_beta_rebalance_frequency = CN_ETF_BETA_REBALANCE_FREQUENCY
    self._etf_beta_absolute_filter_mode = CN_ETF_BETA_ABSOLUTE_FILTER_MODE
    self._etf_beta_fallback_mode = CN_ETF_BETA_FALLBACK_MODE
    self._etf_beta_fallback_symbol = ""
    self._etf_beta_strategy_role = CN_ETF_BETA_STRATEGY_ROLE
    self._etf_beta_governor_boundary_mode = CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE
    self._etf_beta_local_policy_mode = CN_ETF_BETA_LOCAL_POLICY_MODE
    self._etf_beta_allocation_engine_mode = "phase1_three_bucket_v1"
    self._etf_beta_bucket_policy_profile = "phase1_state_template_v1"
    self._etf_beta_exposure_policy_family = CN_ETF_BETA_EXPOSURE_POLICY_FAMILY
    self._etf_beta_policy_scope = CN_ETF_BETA_POLICY_SCOPE
    self._etf_beta_broad_based_only = False
    self._etf_beta_layering_policy = CN_ETF_BETA_LAYERING_POLICY
    self._etf_beta_controlled_accumulation_mode = CN_ETF_BETA_CONTROLLED_ACCUMULATION_MODE
    self._etf_beta_rs_fast_window = CN_ETF_BETA_RS_FAST_WINDOW
    self._etf_beta_rs_mid_window: int | None = None
    self._etf_beta_rs_slow_window = CN_ETF_BETA_RS_SLOW_WINDOW
    self._etf_beta_rs_fast_weight = CN_ETF_BETA_RS_FAST_WEIGHT
    self._etf_beta_rs_mid_weight = CN_ETF_BETA_RS_MID_WEIGHT
    self._etf_beta_rs_slow_weight = CN_ETF_BETA_RS_SLOW_WEIGHT
    self._etf_beta_max_selected_symbols: int | None = None
    self._etf_beta_bull_partial_overlay_pace_ratio = CN_ETF_BETA_BULL_PARTIAL_OVERLAY_PACE_RATIO
    self._etf_beta_vol_target_window = CN_ETF_BETA_VOL_TARGET_WINDOW
    self._etf_beta_vol_target_annualized_target = CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET
    self._etf_beta_vol_target_min_scale = CN_ETF_BETA_VOL_TARGET_MIN_SCALE
    self._etf_beta_vol_target_max_scale = CN_ETF_BETA_VOL_TARGET_MAX_SCALE
    self._etf_beta_vol_target_info_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_target_exposure_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_target_exposure_source_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_min_deployable_exposure_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_min_deployable_exposure_source_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_target_selected_count_arr: np.ndarray = np.array([], dtype=np.int32)
    self._etf_beta_target_exposure_per_symbol_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_target_actual_exposure_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_target_deployability_gap_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_fallback_allowed_arr: np.ndarray = np.array([], dtype=bool)
    self._etf_beta_exposure_policy_family_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_policy_scope_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_broad_based_only_arr: np.ndarray = np.array([], dtype=bool)
    self._etf_beta_layering_policy_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_layering_band_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_layering_active_arr: np.ndarray = np.array([], dtype=bool)
    self._etf_beta_layering_reason_codes_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_target_selected_count_source_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_fallback_allowed_source_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_core_slot_selected_symbol_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_growth_slot_selected_symbol_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_slot_selection_reason_codes_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_slot_under_deploy_reason_codes_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_core_slot_target_exposure_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_growth_slot_target_exposure_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_core_slot_target_actual_exposure_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_growth_slot_target_actual_exposure_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_absolute_filter_reject_count_arr: np.ndarray = np.array([], dtype=np.int32)
    self._etf_beta_absolute_filter_reject_reason_counts_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_candidate_pool_symbols: list[str] = []
    self._etf_beta_candidate_pool_coverage_summary: dict[str, Any] = {}
    self._etf_beta_candidate_pool_reject_reason_counts: dict[str, int] = {}
    self._etf_beta_selection_chain_winner_counts_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_selection_chain_reject_reason_counts_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_targets_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_requested_budget_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_applied_budget_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_cash_weight_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_defense_weight_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_equity_core_bucket_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_defense_tilt_bucket_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_cash_buffer_bucket_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_strategic_floor_cap_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_tactical_overlay_cap_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_limited_defense_cap_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_deployment_pace_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_pace_policy_gap_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_pace_policy_reason_code_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_pace_policy_mode_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_bull_partial_overlay_pace_ratio_arr: np.ndarray = np.array([], dtype=float)
    self._etf_beta_bull_pace_mode_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_hard_block_flags_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_core_accumulator_symbols_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_tactical_satellite_symbols_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_limited_defense_symbols_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_symbol_role_map_arr: np.ndarray = np.array([], dtype=object)
    self._etf_beta_allocation_reason_codes_arr: np.ndarray = np.array([], dtype=object)

