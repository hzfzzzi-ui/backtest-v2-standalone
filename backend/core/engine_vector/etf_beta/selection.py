from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from backend.core.config.etf_beta_contract import (
    CN_ETF_BETA_ABSOLUTE_FILTER_MODE,
    CN_ETF_BETA_BULL_PARTIAL_OVERLAY_PACE_RATIO,
    CN_ETF_BETA_CORE_SYMBOLS,
    CN_ETF_BETA_CONTROLLED_ACCUMULATION_MODE,
    CN_ETF_BETA_EXPOSURE_POLICY_FAMILY,
    CN_ETF_BETA_FALLBACK_MODE,
    CN_ETF_BETA_FORMAL_BOUNDARY_POLICY_MODE,
    CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE,
    CN_ETF_BETA_LAYERING_POLICY,
    CN_ETF_BETA_LEGACY_BOUNDARY_POLICY_MODE,
    CN_ETF_BETA_LOCAL_POLICY_MODE,
    CN_ETF_BETA_POLICY_SCOPE,
    CN_ETF_BETA_REBALANCE_FREQUENCY,
    CN_ETF_BETA_RS_FAST_WEIGHT,
    CN_ETF_BETA_RS_FAST_WINDOW,
    CN_ETF_BETA_RS_MID_WEIGHT,
    CN_ETF_BETA_RS_MID_WINDOW,
    CN_ETF_BETA_RS_SLOW_WEIGHT,
    CN_ETF_BETA_RS_SLOW_WINDOW,
    CN_ETF_BETA_RULE_FAMILY,
    CN_ETF_BETA_STRATEGY_ROLE,
    CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET,
    CN_ETF_BETA_VOL_TARGET_MAX_SCALE,
    CN_ETF_BETA_VOL_TARGET_MIN_SCALE,
    CN_ETF_BETA_VOL_TARGET_WINDOW,
    _controlled_accumulation_mode_from_layering_policy,
    _is_formal_stabilizer_role,
    _layering_policy_from_controlled_accumulation_mode,
    _normalize_controlled_accumulation_mode,
    resolve_etf_beta_exposure_semantics as resolve_cn_etf_beta_exposure_semantics,
)
from backend.core.engine_vector.breakout_signal_provider import (
    _build_legacy_market_filter_multipliers,
    _build_legacy_market_filter_state,
    _coerce_market_filter_cfg,
    _legacy_market_state_names,
    _legacy_trade_mode_names,
)

from .candidate_pool import *
from .provider_config import *
from backend.core.config.cn_a_governed_mainline import canonical_state_5, coarse_state_from_state_5


def _compress_research_mainline_live_targets(
    *,
    strategy_role: str,
    exposure_policy_family: str,
    state_5: str,
    selected_symbols: list[str],
    target_exposure_by_symbol: dict[str, float],
    live_target: float | None,
) -> tuple[dict[str, float], float | None]:
    normalized_state = canonical_state_5(state_5)
    if (
        str(strategy_role or "").strip().lower() != "governed_broad_based_standalone_mainline"
        or str(exposure_policy_family or "").strip().lower() != "broad_based_standalone_mainline_v1"
        or normalized_state not in {"BULL", "TRANS_UP", "RISK_OFF"}
    ):
        return dict(target_exposure_by_symbol or {}), None

    normalized_symbols = [str(symbol).strip().upper() for symbol in list(selected_symbols or []) if str(symbol).strip()]
    target_value = max(float(live_target or 0.0), 0.0)
    if not normalized_symbols or target_value <= 1e-12:
        return dict(target_exposure_by_symbol or {}), None

    scoped_weights = {
        symbol: max(float(dict(target_exposure_by_symbol or {}).get(symbol, 0.0)), 0.0)
        for symbol in normalized_symbols
    }
    positive_symbols = [symbol for symbol, value in scoped_weights.items() if float(value) > 1e-12]
    if positive_symbols:
        total_weight = float(sum(scoped_weights[symbol] for symbol in positive_symbols))
        compressed = {
            symbol: float(target_value) * float(scoped_weights[symbol]) / float(total_weight)
            for symbol in positive_symbols
        }
        for symbol in normalized_symbols:
            compressed.setdefault(symbol, 0.0)
        compressed_per_symbol = float(target_value) / float(len(positive_symbols))
    else:
        equal_weight = float(target_value) / float(len(normalized_symbols))
        compressed = {symbol: float(equal_weight) for symbol in normalized_symbols}
        compressed_per_symbol = float(equal_weight)
    return compressed, compressed_per_symbol


def _resolve_standalone_live_seat_symbols(
    *,
    strategy_role: str,
    exposure_policy_family: str,
    state_5: str,
    rebalance_day: bool,
    governor_hard_blocked: bool,
    target_exposure: float | None,
    selected_cap: int,
    current_selected_symbols: list[str],
    previous_selected_symbols: list[str],
    target_exposure_by_symbol: dict[str, float],
    core_accumulator_symbols: list[str],
) -> tuple[list[str], str | None]:
    normalized_state = canonical_state_5(state_5)
    if (
        str(strategy_role or "").strip().lower() != "governed_broad_based_standalone_mainline"
        or str(exposure_policy_family or "").strip().lower() != "broad_based_standalone_mainline_v1"
        or normalized_state not in {"TRANS_UP", "RISK_OFF"}
        or bool(rebalance_day)
        or bool(governor_hard_blocked)
        or max(float(target_exposure or 0.0), 0.0) <= 1e-12
    ):
        return list(current_selected_symbols or []), None

    normalized_current = [
        str(symbol).strip().upper()
        for symbol in list(current_selected_symbols or [])
        if str(symbol).strip()
    ]
    if normalized_current:
        return normalized_current, None

    limit = max(int(selected_cap or 0), 0)
    if limit <= 0:
        return [], None

    normalized_previous = [
        str(symbol).strip().upper()
        for symbol in list(previous_selected_symbols or [])
        if str(symbol).strip()
    ]
    positive_target_symbols = [
        str(symbol).strip().upper()
        for symbol, value in dict(target_exposure_by_symbol or {}).items()
        if str(symbol).strip() and float(value or 0.0) > 1e-12
    ]
    normalized_core = {
        str(symbol).strip().upper()
        for symbol in list(core_accumulator_symbols or [])
        if str(symbol).strip()
    }

    if normalized_state == "RISK_OFF":
        positive_target_symbols = [symbol for symbol in positive_target_symbols if symbol in normalized_core]
        normalized_previous = [symbol for symbol in normalized_previous if symbol in normalized_core]

    if normalized_previous:
        carried = [symbol for symbol in normalized_previous if symbol in set(positive_target_symbols or normalized_previous)]
        if carried:
            return carried[:limit], "previous_live_seats"

    if positive_target_symbols:
        return positive_target_symbols[:limit], "target_contract_symbols"
    return [], None


def precompute_etf_beta(provider, *, benchmark: Any, kwargs: dict[str, Any]) -> None:
    self = provider
    mx = self._mx
    feats = self._feats
    dates = list(mx.dates)
    symbols = [_normalize_etf_symbol_key(symbol) for symbol in list(mx.symbols)]
    display_symbols = [_display_etf_symbol(symbol) for symbol in list(mx.symbols)]
    governed_a_share = dict(kwargs.get("governed_a_share") or {}) if isinstance(kwargs.get("governed_a_share"), dict) else {}
    etf_beta_cfg = dict(governed_a_share.get("etf_beta") or {})
    weak_state_defense_policy_cfg = dict(etf_beta_cfg.get("weak_state_defense_policy") or {})
    shared_transition_execution_cfg = dict(etf_beta_cfg.get("shared_transition_execution") or {})
    risk_on_to_defensive_transition_cfg = dict(
        (shared_transition_execution_cfg.get("transition_families") or {}).get("risk_on_to_defensive") or {}
    )
    self._etf_beta_weak_state_defense_policy_id = _normalize_text(weak_state_defense_policy_cfg.get("policy_id"))
    self._etf_beta_shared_transition_execution_enabled = bool(shared_transition_execution_cfg.get("enabled"))
    self._etf_beta_shared_transition_execution_owner = (
        _normalize_text(shared_transition_execution_cfg.get("owner")) or "shared_account_execution_runtime"
    )
    self._etf_beta_shared_transition_reference_paths = [
        str(item).strip()
        for item in list(shared_transition_execution_cfg.get("diagnostics_reference_paths") or [])
        if str(item).strip()
    ]
    self._etf_beta_shared_transition_risk_on_to_defensive_enabled = bool(
        risk_on_to_defensive_transition_cfg.get("enabled")
    )
    self._etf_beta_shared_transition_release_ratio_cap = max(
        min(float(risk_on_to_defensive_transition_cfg.get("release_ratio_cap") or 0.2), 1.0),
        0.0,
    )
    self._etf_beta_shared_transition_min_defense_lots = max(
        int(risk_on_to_defensive_transition_cfg.get("minimum_defense_lots") or 1),
        1,
    )
    self._etf_beta_shared_transition_defense_symbol = _normalize_etf_symbol_key(
        risk_on_to_defensive_transition_cfg.get("defense_symbol") or "511010.SH"
    )
    self._etf_beta_shared_transition_core_beta_symbol = _normalize_etf_symbol_key(
        risk_on_to_defensive_transition_cfg.get("core_beta_symbol") or "510300.SH"
    )
    self._etf_beta_shared_transition_defense_establish_enabled = bool(
        risk_on_to_defensive_transition_cfg.get("defense_establish_enabled", True)
    )
    self._etf_beta_shared_transition_defense_establish_mode = (
        _normalize_text(risk_on_to_defensive_transition_cfg.get("defense_establish_mode"))
        or "buy_after_sell_same_edge"
    )
    self._etf_beta_shared_transition_defense_establish_variant_id = (
        _normalize_text(risk_on_to_defensive_transition_cfg.get("defense_establish_variant_id"))
        or "all_defensive"
    )
    self._etf_beta_shared_transition_defense_establish_edge_to_states = {
        canonical_state_5(str(item).strip())
        for item in list(risk_on_to_defensive_transition_cfg.get("defense_establish_edge_to_states") or [])
        if canonical_state_5(str(item).strip())
    }
    self._etf_beta_shared_transition_defense_establish_top_up_existing_defense = bool(
        risk_on_to_defensive_transition_cfg.get("defense_establish_top_up_existing_defense", True)
    )
    self._etf_beta_template_id = _normalize_text(etf_beta_cfg.get("template_id"))
    self._etf_beta_template_asset_pool_version = _normalize_text(etf_beta_cfg.get("template_asset_pool_version"))
    self._etf_beta_template_role_map = _normalize_symbol_map(etf_beta_cfg.get("template_role_map"))
    self._etf_beta_template_proxy_map = _normalize_symbol_map(etf_beta_cfg.get("template_proxy_map"))
    self._etf_beta_template_target_formal_symbols = [
        _display_etf_symbol(item).upper()
        for item in list(etf_beta_cfg.get("template_target_formal_symbols") or [])
        if _normalize_text(item)
    ]
    self._etf_beta_proxy_replacement_mode = _normalize_choice(
        etf_beta_cfg.get("proxy_replacement_mode"),
        default="none",
        allowed={"none", "csi1000_proxy_only", "dividend_proxy_only", "full_standard_swap"},
    )
    self._etf_beta_formal_replacement_pairs = _normalize_symbol_pairs(etf_beta_cfg.get("formal_replacement_pairs"))
    self._etf_beta_core_slot_symbols = [
        _display_etf_symbol(item).upper()
        for item in list(etf_beta_cfg.get("core_slot_symbols") or [])
        if _normalize_text(item)
    ]
    self._etf_beta_growth_slot_symbols = [
        _display_etf_symbol(item).upper()
        for item in list(etf_beta_cfg.get("growth_slot_symbols") or [])
        if _normalize_text(item)
    ]
    self._etf_beta_growth_seat_symbol = (
        _display_etf_symbol(etf_beta_cfg.get("growth_seat_symbol")).upper()
        if _normalize_text(etf_beta_cfg.get("growth_seat_symbol"))
        else ""
    )
    self._etf_beta_rule_family = _normalize_choice(
        etf_beta_cfg.get("research_rule_family"),
        default=CN_ETF_BETA_RULE_FAMILY,
        allowed={
            "etf_beta_v1_control",
            "dual_momentum_basic",
            "dual_momentum_vol_target",
            "broad_based_rotation_template_a",
            "broad_based_rotation_template_a0_core_satellite_v2",
            "phase1_allocation_engine_v1",
        },
    )
    self._etf_beta_absolute_filter_profile = _normalize_optional_choice(
        etf_beta_cfg.get("absolute_filter_profile"),
        allowed=set(_ABSOLUTE_FILTER_PROFILE_TO_MODE.keys()),
    )
    self._etf_beta_candidate_pool_profile = _normalize_optional_choice(
        etf_beta_cfg.get("candidate_pool_profile"),
        allowed={"a0_proxy_pool", "proxy_expanded_pool", "standard_overlap_pool"},
    )
    self._etf_beta_selection_chain_profile = _normalize_optional_choice(
        etf_beta_cfg.get("selection_chain_profile"),
        allowed={"global_top2_12_6_3", "global_top2_6_3_1", "core_growth_slot"},
    )
    self._etf_beta_rebalance_frequency = _normalize_choice(
        etf_beta_cfg.get("rebalance_frequency"),
        default=CN_ETF_BETA_REBALANCE_FREQUENCY,
        allowed={"weekly", "biweekly", "monthly"},
    )
    self._etf_beta_absolute_filter_mode = _normalize_choice(
        etf_beta_cfg.get("absolute_filter_mode"),
        default=CN_ETF_BETA_ABSOLUTE_FILTER_MODE,
        allowed={"none", "ma120", "positive_12m", "ma200_and_positive_12m", "ma200_only", "ma150_and_positive_12m"},
    )
    if self._etf_beta_absolute_filter_profile:
        self._etf_beta_absolute_filter_mode = _ABSOLUTE_FILTER_PROFILE_TO_MODE[self._etf_beta_absolute_filter_profile]
    self._etf_beta_fallback_mode = _normalize_choice(
        etf_beta_cfg.get("fallback_mode"),
        default=CN_ETF_BETA_FALLBACK_MODE,
        allowed={"none", "cash", "single_symbol"},
    )
    self._etf_beta_fallback_symbol = _normalize_etf_symbol_key(etf_beta_cfg.get("fallback_symbol"))
    self._etf_beta_strategy_role = _normalize_choice(
        etf_beta_cfg.get("strategy_role"),
        default=CN_ETF_BETA_STRATEGY_ROLE,
        allowed={"auxiliary_beta_sleeve", "governed_broad_based_standalone_mainline", "phase1_allocation_engine", "strategic_beta_stabilizer"},
    )
    self._etf_beta_governor_boundary_mode = _normalize_choice(
        etf_beta_cfg.get("governor_boundary_mode"),
        default=CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE,
        allowed={"consume_governor_sleeve_budget", "consume_governor_state_and_budget"},
    )
    self._etf_beta_local_policy_mode = _normalize_choice(
        etf_beta_cfg.get("local_policy_mode"),
        default=CN_ETF_BETA_LOCAL_POLICY_MODE,
        allowed={"legacy_beta_selection", "broad_based_rotation_mainline", "phase1_bucket_allocation"},
    )
    self._etf_beta_boundary_policy_mode = _normalize_choice(
        etf_beta_cfg.get("boundary_policy_mode"),
        default=(
            CN_ETF_BETA_FORMAL_BOUNDARY_POLICY_MODE
            if (
                _is_formal_stabilizer_role(self._etf_beta_strategy_role, self._etf_beta_local_policy_mode)
                or self._etf_beta_local_policy_mode == "phase1_bucket_allocation"
            )
            else CN_ETF_BETA_LEGACY_BOUNDARY_POLICY_MODE
        ),
        allowed={CN_ETF_BETA_FORMAL_BOUNDARY_POLICY_MODE, CN_ETF_BETA_LEGACY_BOUNDARY_POLICY_MODE},
    )
    self._etf_beta_allocation_engine_mode = _normalize_choice(
        etf_beta_cfg.get("allocation_engine_mode"),
        default="phase1_three_bucket_v1",
        allowed={"phase1_three_bucket_v1"},
    )
    self._etf_beta_bucket_policy_profile = _normalize_choice(
        etf_beta_cfg.get("bucket_policy_profile"),
        default="phase1_state_template_v1",
        allowed={"phase1_state_template_v1"},
    )
    self._etf_beta_exposure_policy_family = _normalize_choice(
        etf_beta_cfg.get("exposure_policy_family"),
        default=CN_ETF_BETA_EXPOSURE_POLICY_FAMILY,
        allowed={"default", "broad_based_governed_v1", "broad_based_standalone_mainline_v1", "phase1_governed_allocation_v1"},
    )
    self._etf_beta_policy_scope = _normalize_choice(
        etf_beta_cfg.get("policy_scope"),
        default=CN_ETF_BETA_POLICY_SCOPE,
        allowed={"general", "broad_based_only"},
    )
    self._etf_beta_broad_based_only = (
        bool(etf_beta_cfg.get("broad_based_only"))
        if etf_beta_cfg.get("broad_based_only") is not None
        else self._etf_beta_policy_scope == "broad_based_only"
    )
    self._etf_beta_layering_policy = _normalize_choice(
        etf_beta_cfg.get("layering_policy"),
        default=CN_ETF_BETA_LAYERING_POLICY,
        allowed={"none", "light_accumulate", "light_trans_down_accumulate"},
    )
    self._etf_beta_controlled_accumulation_mode = _normalize_controlled_accumulation_mode(
        etf_beta_cfg.get("controlled_accumulation_mode")
    )
    if _normalize_text(etf_beta_cfg.get("controlled_accumulation_mode")):
        self._etf_beta_layering_policy = _layering_policy_from_controlled_accumulation_mode(
            self._etf_beta_controlled_accumulation_mode
        )
    else:
        self._etf_beta_controlled_accumulation_mode = _controlled_accumulation_mode_from_layering_policy(
            self._etf_beta_layering_policy
        )
    self._etf_beta_rs_fast_window = max(2, int(etf_beta_cfg.get("relative_strength_fast_window") or CN_ETF_BETA_RS_FAST_WINDOW))
    mid_window = int(etf_beta_cfg.get("relative_strength_mid_window") or CN_ETF_BETA_RS_MID_WINDOW or 0)
    self._etf_beta_rs_mid_window = max(2, mid_window) if mid_window >= 2 else None
    self._etf_beta_rs_slow_window = max(2, int(etf_beta_cfg.get("relative_strength_slow_window") or CN_ETF_BETA_RS_SLOW_WINDOW))
    fast_weight = float(etf_beta_cfg.get("relative_strength_fast_weight") or CN_ETF_BETA_RS_FAST_WEIGHT)
    mid_weight = float(etf_beta_cfg.get("relative_strength_mid_weight") or CN_ETF_BETA_RS_MID_WEIGHT)
    slow_weight = float(etf_beta_cfg.get("relative_strength_slow_weight") or CN_ETF_BETA_RS_SLOW_WEIGHT)
    if fast_weight < 0.0:
        fast_weight = 0.0
    if mid_weight < 0.0:
        mid_weight = 0.0
    if slow_weight < 0.0:
        slow_weight = 0.0
    if self._etf_beta_rs_mid_window is None:
        mid_weight = 0.0
    if fast_weight + mid_weight + slow_weight <= 1e-12:
        fast_weight = CN_ETF_BETA_RS_FAST_WEIGHT
        mid_weight = CN_ETF_BETA_RS_MID_WEIGHT
        slow_weight = CN_ETF_BETA_RS_SLOW_WEIGHT
    if self._etf_beta_selection_chain_profile == "global_top2_12_6_3":
        self._etf_beta_rs_fast_window = 63
        self._etf_beta_rs_mid_window = 126
        self._etf_beta_rs_slow_window = 252
        fast_weight = 0.2
        mid_weight = 0.3
        slow_weight = 0.5
        self._etf_beta_max_selected_symbols = 2
    elif self._etf_beta_selection_chain_profile == "global_top2_6_3_1":
        self._etf_beta_rs_fast_window = 21
        self._etf_beta_rs_mid_window = 63
        self._etf_beta_rs_slow_window = 126
        fast_weight = 0.2
        mid_weight = 0.3
        slow_weight = 0.5
        self._etf_beta_max_selected_symbols = 2
    elif self._etf_beta_selection_chain_profile == "core_growth_slot":
        self._etf_beta_rs_fast_window = 63
        self._etf_beta_rs_mid_window = 126
        self._etf_beta_rs_slow_window = 252
        fast_weight = 0.2
        mid_weight = 0.3
        slow_weight = 0.5
        self._etf_beta_max_selected_symbols = 2
    self._etf_beta_rs_fast_weight = fast_weight
    self._etf_beta_rs_mid_weight = mid_weight
    self._etf_beta_rs_slow_weight = slow_weight
    max_selected_symbols = int(etf_beta_cfg.get("max_selected_symbols") or 0)
    self._etf_beta_max_selected_symbols = max_selected_symbols if max_selected_symbols > 0 else None
    if self._etf_beta_selection_chain_profile in {"global_top2_12_6_3", "global_top2_6_3_1", "core_growth_slot"}:
        self._etf_beta_max_selected_symbols = 2
    raw_bull_partial_overlay_ratio = etf_beta_cfg.get("bull_partial_overlay_pace_ratio")
    try:
        bull_partial_overlay_ratio = float(
            CN_ETF_BETA_BULL_PARTIAL_OVERLAY_PACE_RATIO
            if raw_bull_partial_overlay_ratio is None
            else raw_bull_partial_overlay_ratio
        )
    except Exception:
        bull_partial_overlay_ratio = float(CN_ETF_BETA_BULL_PARTIAL_OVERLAY_PACE_RATIO)
    self._etf_beta_bull_partial_overlay_pace_ratio = max(0.0, min(float(bull_partial_overlay_ratio), 1.0))
    self._etf_beta_vol_target_window = max(
        5,
        int(etf_beta_cfg.get("vol_target_window") or CN_ETF_BETA_VOL_TARGET_WINDOW),
    )
    target_vol = float(etf_beta_cfg.get("vol_target_annualized_target") or CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET)
    if target_vol <= 0.0:
        target_vol = CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET
    self._etf_beta_vol_target_annualized_target = float(target_vol)
    min_scale = float(etf_beta_cfg.get("vol_target_min_scale") or CN_ETF_BETA_VOL_TARGET_MIN_SCALE)
    max_scale = float(etf_beta_cfg.get("vol_target_max_scale") or CN_ETF_BETA_VOL_TARGET_MAX_SCALE)
    min_scale = max(0.0, min(min_scale, 1.0))
    max_scale = max(0.0, min(max_scale, 1.0))
    if min_scale > max_scale:
        min_scale, max_scale = max_scale, min_scale
    self._etf_beta_vol_target_min_scale = float(min_scale)
    self._etf_beta_vol_target_max_scale = float(max_scale)
    configured_core_scope_source = (
        list(etf_beta_cfg.get("core_beta_symbols") or CN_ETF_BETA_CORE_SYMBOLS)
        + list(etf_beta_cfg.get("limited_defense_candidates") or ())
        if _is_formal_stabilizer_role(self._etf_beta_strategy_role, self._etf_beta_local_policy_mode)
        else (
            list(self._etf_beta_core_slot_symbols) + list(self._etf_beta_growth_slot_symbols)
            if (self._etf_beta_core_slot_symbols or self._etf_beta_growth_slot_symbols)
            else list(etf_beta_cfg.get("core_beta_symbols") or CN_ETF_BETA_CORE_SYMBOLS)
        )
    )
    configured_core_scope = [
        _normalize_etf_symbol_key(symbol)
        for symbol in configured_core_scope_source
        if _normalize_etf_symbol_key(symbol)
    ]
    scope_set = set(configured_core_scope or _FORMAL_CORE_SCOPE)
    scope_cols = [idx for idx, symbol in enumerate(symbols) if symbol in scope_set]
    candidate_pool_profile = self._etf_beta_candidate_pool_profile
    candidate_pool_cols = list(scope_cols)
    candidate_pool_reason_counter: Counter[str] = Counter()
    if candidate_pool_profile:
        configured_scope_display = {_display_etf_symbol(symbol).upper() for symbol in scope_set}
        candidate_pool_cols = []
        for col_idx, symbol_text in enumerate(display_symbols):
            include_symbol, reason_codes = _candidate_pool_reason_codes(
                symbol=symbol_text,
                profile=candidate_pool_profile,
                configured_scope=configured_scope_display,
            )
            for code in reason_codes:
                candidate_pool_reason_counter[str(code).strip()] += 1
            if include_symbol:
                candidate_pool_cols.append(col_idx)
    self._etf_beta_candidate_pool_symbols = [display_symbols[idx] for idx in candidate_pool_cols]
    self._etf_beta_formal_scope_symbols = [display_symbols[idx] for idx in scope_cols]
    self._etf_beta_candidate_pool_coverage_summary = _candidate_pool_coverage_summary(
        candidate_pool_symbols=self._etf_beta_candidate_pool_symbols,
        close=np.asarray(mx.close, dtype=float),
        dates=dates,
        sym_to_col={str(symbol).upper(): idx for idx, symbol in enumerate(display_symbols)},
    )
    self._etf_beta_candidate_pool_reject_reason_counts = dict(sorted(candidate_pool_reason_counter.items()))
    day_count = len(dates)

    source_state_name_arr = getattr(self, "_market_state_name_arr", None)
    source_trade_mode_name_arr = getattr(self, "_trade_mode_name_arr", None)
    source_raw_state_name_arr = getattr(self, "_market_state_raw_name_arr", None)
    source_smoothed_state_name_arr = getattr(self, "_market_state_smoothed_name_arr", None)
    source_base_state_arr = getattr(self, "_base_state_5_arr", None)
    source_effective_state_arr = getattr(self, "_effective_state_5_arr", None)
    source_risk_budget_arr = getattr(self, "_regime_risk_budget_multiplier_arr", None)
    market_filter_cfg = _coerce_market_filter_cfg(kwargs.get("market_filter_cfg"))

    if not _has_text_payload(source_effective_state_arr):
        legacy_state_arr, legacy_trade_mode_arr = _build_legacy_market_filter_state(
            benchmark=benchmark,
            dates=np.array(mx.dates),
            market_filter_cfg=market_filter_cfg,
        )
        legacy_state_names = _legacy_market_state_names(np.asarray(legacy_state_arr, dtype=np.int8))
        legacy_trade_mode_names = _legacy_trade_mode_names(np.asarray(legacy_trade_mode_arr, dtype=np.int8))
        legacy_budget_arr = _build_legacy_market_filter_multipliers(
            market_state=np.asarray(legacy_state_arr, dtype=np.int8),
            trade_mode=np.asarray(legacy_trade_mode_arr, dtype=np.int8),
            market_filter_cfg=market_filter_cfg,
        )

        self._market_state = np.asarray(legacy_state_arr, dtype=np.int8)
        self._trade_mode = np.asarray(legacy_trade_mode_arr, dtype=np.int8)
        self._market_state_name_arr = np.asarray(legacy_state_names, dtype=object)
        self._trade_mode_name_arr = np.asarray(legacy_trade_mode_names, dtype=object)
        self._market_state_raw_name_arr = np.asarray(legacy_state_names, dtype=object)
        self._market_state_smoothed_name_arr = np.asarray(legacy_state_names, dtype=object)
        self._market_state_score_arr = np.full(day_count, np.nan, dtype=float)
        self._risk_budget_multiplier_arr = np.asarray(legacy_budget_arr, dtype=float)
        self._regime_risk_budget_multiplier_arr = np.asarray(legacy_budget_arr, dtype=float)
        self._weekly_observation_flag_arr = np.zeros(day_count, dtype=bool)
        source_state_name_arr = self._market_state_name_arr
        source_trade_mode_name_arr = self._trade_mode_name_arr
        source_raw_state_name_arr = self._market_state_raw_name_arr
        source_smoothed_state_name_arr = self._market_state_smoothed_name_arr
        source_base_state_arr = self._base_state_5_arr
        source_effective_state_arr = self._effective_state_5_arr
        source_risk_budget_arr = self._regime_risk_budget_multiplier_arr

    base_state_5_arr = np.empty(day_count, dtype=object)
    effective_state_5_arr = np.empty(day_count, dtype=object)
    coarse_state_arr = np.empty(day_count, dtype=object)
    effective_coarse_state_arr = np.empty(day_count, dtype=object)
    for idx in range(day_count):
        source_trade_mode = _array_item(source_trade_mode_name_arr, idx)
        raw_base = (
            _array_item(source_base_state_arr, idx)
            or _array_item(source_raw_state_name_arr, idx)
            or _array_item(source_state_name_arr, idx)
        )
        raw_effective = (
            _array_item(source_effective_state_arr, idx)
            or _array_item(source_smoothed_state_name_arr, idx)
            or _array_item(source_state_name_arr, idx)
        )
        base_state_text = canonical_state_5(raw_base, trade_mode=source_trade_mode)
        effective_state_text = canonical_state_5(raw_effective, trade_mode=source_trade_mode) or base_state_text
        base_state_5_arr[idx] = base_state_text
        effective_state_5_arr[idx] = effective_state_text
        coarse_state_arr[idx] = coarse_state_from_state_5(base_state_text)
        effective_coarse_state_arr[idx] = coarse_state_from_state_5(effective_state_text)

    self._base_state_5_arr = base_state_5_arr
    self._effective_state_5_arr = effective_state_5_arr
    self._coarse_state_arr = coarse_state_arr
    self._effective_coarse_state_arr = effective_coarse_state_arr
    if not isinstance(source_risk_budget_arr, np.ndarray) or len(source_risk_budget_arr) != day_count:
        source_risk_budget_arr = np.array(getattr(self, "_risk_budget_multiplier_arr", np.array([], dtype=float)), dtype=float)
    if not isinstance(source_risk_budget_arr, np.ndarray) or len(source_risk_budget_arr) != day_count:
        source_risk_budget_arr = np.ones(day_count, dtype=float)
    self._regime_risk_budget_multiplier_arr = np.array(source_risk_budget_arr, dtype=float)
    if not isinstance(getattr(self, "_reason_codes_arr", None), np.ndarray) or len(
        getattr(self, "_reason_codes_arr", np.array([], dtype=object))
    ) != day_count:
        reason_codes_arr = np.empty(day_count, dtype=object)
        for idx in range(day_count):
            reason_codes_arr[idx] = []
        self._reason_codes_arr = reason_codes_arr
    if not isinstance(getattr(self, "_block_scores_arr", None), np.ndarray) or len(
        getattr(self, "_block_scores_arr", np.array([], dtype=object))
    ) != day_count:
        block_scores_arr = np.empty(day_count, dtype=object)
        for idx in range(day_count):
            block_scores_arr[idx] = {}
        self._block_scores_arr = block_scores_arr
    if not isinstance(getattr(self, "_subscores_arr", None), np.ndarray) or len(
        getattr(self, "_subscores_arr", np.array([], dtype=object))
    ) != day_count:
        subscores_arr = np.empty(day_count, dtype=object)
        for idx in range(day_count):
            subscores_arr[idx] = {}
        self._subscores_arr = subscores_arr
    if not isinstance(getattr(self, "_manual_override_arr", None), np.ndarray) or len(
        getattr(self, "_manual_override_arr", np.array([], dtype=object))
    ) != day_count:
        manual_override_arr = np.empty(day_count, dtype=object)
        for idx in range(day_count):
            manual_override_arr[idx] = {"active": False, "reason": None, "scope": None, "actor": None}
        self._manual_override_arr = manual_override_arr
    if not isinstance(getattr(self, "_state_stability_metrics_arr", None), np.ndarray) or len(
        getattr(self, "_state_stability_metrics_arr", np.array([], dtype=object))
    ) != day_count:
        stability_arr = np.empty(day_count, dtype=object)
        for idx in range(day_count):
            stability_arr[idx] = {}
        self._state_stability_metrics_arr = stability_arr

    state_5_arr = np.array(
        [
            str(self._effective_state_5_arr[idx] or "")
            for idx in range(day_count)
        ],
        dtype=object,
    )
    self._market_state_name_arr = state_5_arr.copy()
    self._market_state_smoothed_name_arr = state_5_arr.copy()
    is_formal_phase1_boundary = (
        _is_formal_stabilizer_role(self._etf_beta_strategy_role, self._etf_beta_local_policy_mode)
        and self._etf_beta_boundary_policy_mode == CN_ETF_BETA_FORMAL_BOUNDARY_POLICY_MODE
    )
    runtime_hard_max_positions = max(1, int(kwargs.get("max_positions") or 10))
    upstream_trade_mode_arr = np.array(
        [
            str(_array_item(source_trade_mode_name_arr, idx) or "").strip().upper()
            for idx in range(day_count)
        ],
        dtype=object,
    )
    trade_mode_arr = np.array(
        [
            _trade_mode_from_slot_cap(_formal_phase1_slot_cap_from_state(state))
            if is_formal_phase1_boundary
            else "TREND_MAIN"
            if _STATE_SLOT_CAPS.get(str(state).strip().upper(), 0) >= 2
            else "TREND_LIGHT"
            if _STATE_SLOT_CAPS.get(str(state).strip().upper(), 0) == 1
            else "NO_TRADE"
            for idx, state in enumerate(state_5_arr)
        ],
        dtype=object,
    )
    self._trade_mode_name_arr = trade_mode_arr
    self._market_state_name_map = {day: str(state_5_arr[idx] or "") for idx, day in enumerate(dates)}
    self._trade_mode_name_map = {day: str(trade_mode_arr[idx] or "") for idx, day in enumerate(dates)}
    self._etf_beta_rebalance_flag_arr = _rebalance_flags(dates, frequency=self._etf_beta_rebalance_frequency)
    governor_slot_cap_arr = np.array(
        [
            _formal_phase1_slot_cap_from_state(state)
            if is_formal_phase1_boundary
            else _STATE_SLOT_CAPS.get(str(state).strip().upper(), 0)
            for idx, state in enumerate(state_5_arr)
        ],
        dtype=np.int32,
    )
    formal_boundary_runtime_budget_rows = np.array(source_risk_budget_arr, dtype=float)

    close = np.asarray(mx.close, dtype=float)
    ma120 = np.asarray(feats.trend_fast_ma, dtype=float)
    ma150 = np.full_like(close, np.nan, dtype=float)
    ma200 = np.full_like(close, np.nan, dtype=float)
    for col_idx in candidate_pool_cols:
        ma150[:, col_idx] = pd.Series(close[:, col_idx]).rolling(150, min_periods=150).mean().to_numpy(dtype=float)
        ma200[:, col_idx] = pd.Series(close[:, col_idx]).rolling(200, min_periods=200).mean().to_numpy(dtype=float)
    score_windows: list[tuple[int, float]] = [
        (int(self._etf_beta_rs_slow_window), float(self._etf_beta_rs_slow_weight)),
    ]
    if self._etf_beta_rs_mid_window is not None and float(self._etf_beta_rs_mid_weight) > 1e-12:
        score_windows.append((int(self._etf_beta_rs_mid_window), float(self._etf_beta_rs_mid_weight)))
    score_windows.append((int(self._etf_beta_rs_fast_window), float(self._etf_beta_rs_fast_weight)))
    windows_needed = {window for window, _weight in score_windows}
    if self._etf_beta_absolute_filter_mode in {"positive_12m", "ma200_and_positive_12m", "ma150_and_positive_12m"}:
        windows_needed.add(252)
    returns_by_window = {
        window: np.full_like(close, np.nan, dtype=float)
        for window in sorted(windows_needed)
    }
    for row_idx in range(day_count):
        for col_idx in candidate_pool_cols:
            close_now = float(close[row_idx, col_idx])
            for window, arr in returns_by_window.items():
                if row_idx >= window:
                    arr[row_idx, col_idx] = _safe_return(close_now, float(close[row_idx - window, col_idx]))
    daily_returns = np.full_like(close, np.nan, dtype=float)
    for row_idx in range(1, day_count):
        for col_idx in candidate_pool_cols:
            daily_returns[row_idx, col_idx] = _safe_return(float(close[row_idx, col_idx]), float(close[row_idx - 1, col_idx]))

    eligible_rows: list[list[str]] = []
    selected_rows: list[list[str]] = []
    selection_reason_rows: list[dict[str, list[str]]] = []
    runtime_reason_rows: list[list[str]] = []
    vol_target_rows: list[dict[str, Any]] = []
    target_exposure_rows = np.full(day_count, np.nan, dtype=float)
    target_exposure_source_rows = np.full(day_count, "", dtype=object)
    min_deployable_exposure_rows = np.full(day_count, np.nan, dtype=float)
    min_deployable_exposure_source_rows = np.full(day_count, "", dtype=object)
    target_selected_count_rows = np.zeros(day_count, dtype=np.int32)
    target_exposure_per_symbol_rows = np.full(day_count, np.nan, dtype=float)
    target_actual_exposure_rows = np.full(day_count, np.nan, dtype=float)
    target_deployability_gap_rows = np.full(day_count, np.nan, dtype=float)
    fallback_allowed_rows = np.zeros(day_count, dtype=bool)
    exposure_policy_family_rows = np.full(day_count, "", dtype=object)
    policy_scope_rows = np.full(day_count, "", dtype=object)
    broad_based_only_rows = np.zeros(day_count, dtype=bool)
    layering_policy_rows = np.full(day_count, "", dtype=object)
    layering_band_rows = np.full(day_count, "", dtype=object)
    layering_active_rows = np.zeros(day_count, dtype=bool)
    layering_reason_rows: list[list[str]] = []
    target_selected_count_source_rows = np.full(day_count, "", dtype=object)
    fallback_allowed_source_rows = np.full(day_count, "", dtype=object)
    core_slot_selected_rows: list[str | None] = [None] * day_count
    growth_slot_selected_rows: list[str | None] = [None] * day_count
    slot_selection_reason_rows: list[dict[str, list[str]]] = [{} for _ in range(day_count)]
    slot_under_deploy_reason_rows: list[dict[str, list[str]]] = [{} for _ in range(day_count)]
    core_slot_target_exposure_rows = np.full(day_count, np.nan, dtype=float)
    growth_slot_target_exposure_rows = np.full(day_count, np.nan, dtype=float)
    core_slot_target_actual_exposure_rows = np.full(day_count, np.nan, dtype=float)
    growth_slot_target_actual_exposure_rows = np.full(day_count, np.nan, dtype=float)
    absolute_filter_reject_count_rows = np.zeros(day_count, dtype=np.int32)
    absolute_filter_reject_reason_rows: list[dict[str, int]] = []
    selection_chain_winner_rows: list[dict[str, int]] = []
    selection_chain_reject_reason_rows: list[dict[str, int]] = []
    requested_budget_rows = np.full(day_count, np.nan, dtype=float)
    applied_budget_rows = np.full(day_count, np.nan, dtype=float)
    cash_weight_rows = np.full(day_count, np.nan, dtype=float)
    defense_weight_rows = np.full(day_count, np.nan, dtype=float)
    equity_core_bucket_rows = np.full(day_count, np.nan, dtype=float)
    defense_tilt_bucket_rows = np.full(day_count, np.nan, dtype=float)
    cash_buffer_bucket_rows = np.full(day_count, np.nan, dtype=float)
    strategic_floor_cap_rows = np.full(day_count, np.nan, dtype=float)
    tactical_overlay_cap_rows = np.full(day_count, np.nan, dtype=float)
    limited_defense_cap_rows = np.full(day_count, np.nan, dtype=float)
    deployment_pace_rows = np.full(day_count, np.nan, dtype=float)
    pace_policy_gap_rows = np.full(day_count, np.nan, dtype=float)
    pace_policy_reason_code_rows = np.full(day_count, "", dtype=object)
    pace_policy_mode_rows = np.full(day_count, "", dtype=object)
    bull_partial_overlay_pace_ratio_rows = np.full(day_count, np.nan, dtype=float)
    bull_pace_mode_rows = np.full(day_count, "", dtype=object)
    hard_block_flag_rows: list[list[str]] = [[] for _ in range(day_count)]
    core_accumulator_symbol_rows: list[list[str]] = [[] for _ in range(day_count)]
    tactical_satellite_symbol_rows: list[list[str]] = [[] for _ in range(day_count)]
    limited_defense_symbol_rows: list[list[str]] = [[] for _ in range(day_count)]
    symbol_role_map_rows: list[dict[str, str]] = [{} for _ in range(day_count)]
    targets_rows: list[dict[str, float]] = [{} for _ in range(day_count)]
    allocation_reason_rows: list[list[str]] = [[] for _ in range(day_count)]
    for row_idx in range(day_count):
        governor_slot_cap = int(governor_slot_cap_arr[row_idx]) if row_idx < len(governor_slot_cap_arr) else 0
        rebalance_day = bool(self._etf_beta_rebalance_flag_arr[row_idx]) if row_idx < len(self._etf_beta_rebalance_flag_arr) else False
        eligible_scores_by_window: dict[int, dict[int, float]] = {window: {} for window, _weight in score_windows}
        absolute_filter_reject_counter: Counter[str] = Counter()
        selection_chain_reject_counter: Counter[str] = Counter()
        selection_chain_winner_counter: Counter[str] = Counter()
        eligible_after_absolute_cols: list[int] = []
        for col_idx in candidate_pool_cols:
            close_now = float(close[row_idx, col_idx])
            ma120_now = float(ma120[row_idx, col_idx])
            ma150_now = float(ma150[row_idx, col_idx])
            ma200_now = float(ma200[row_idx, col_idx])
            absolute_pass = False
            reject_codes: list[str] = []
            if close_now != close_now:
                reject_codes.append("ABSOLUTE_PRICE_UNAVAILABLE")
            elif self._etf_beta_absolute_filter_mode == "positive_12m":
                ret12 = float(returns_by_window[252][row_idx, col_idx])
                if ret12 != ret12:
                    reject_codes.append("ABSOLUTE_RET12_HISTORY_UNAVAILABLE")
                elif ret12 <= 0.0:
                    reject_codes.append("ABSOLUTE_RET12_NON_POSITIVE")
                else:
                    absolute_pass = True
            elif self._etf_beta_absolute_filter_mode == "ma200_and_positive_12m":
                ret12 = float(returns_by_window[252][row_idx, col_idx])
                if ma200_now != ma200_now:
                    reject_codes.append("ABSOLUTE_MA200_HISTORY_UNAVAILABLE")
                elif close_now <= ma200_now:
                    reject_codes.append("ABSOLUTE_MA200_NOT_ABOVE")
                if ret12 != ret12:
                    reject_codes.append("ABSOLUTE_RET12_HISTORY_UNAVAILABLE")
                elif ret12 <= 0.0:
                    reject_codes.append("ABSOLUTE_RET12_NON_POSITIVE")
                if not reject_codes:
                    absolute_pass = True
            elif self._etf_beta_absolute_filter_mode == "ma200_only":
                if ma200_now != ma200_now:
                    reject_codes.append("ABSOLUTE_MA200_HISTORY_UNAVAILABLE")
                elif close_now <= ma200_now:
                    reject_codes.append("ABSOLUTE_MA200_NOT_ABOVE")
                else:
                    absolute_pass = True
            elif self._etf_beta_absolute_filter_mode == "ma150_and_positive_12m":
                ret12 = float(returns_by_window[252][row_idx, col_idx])
                if ma150_now != ma150_now:
                    reject_codes.append("ABSOLUTE_MA150_HISTORY_UNAVAILABLE")
                elif close_now <= ma150_now:
                    reject_codes.append("ABSOLUTE_MA150_NOT_ABOVE")
                if ret12 != ret12:
                    reject_codes.append("ABSOLUTE_RET12_HISTORY_UNAVAILABLE")
                elif ret12 <= 0.0:
                    reject_codes.append("ABSOLUTE_RET12_NON_POSITIVE")
                if not reject_codes:
                    absolute_pass = True
            else:
                if ma120_now != ma120_now:
                    reject_codes.append("ABSOLUTE_MA120_HISTORY_UNAVAILABLE")
                elif close_now <= ma120_now:
                    reject_codes.append("ABSOLUTE_MA120_NOT_ABOVE")
                else:
                    absolute_pass = True
            if not absolute_pass:
                for code in reject_codes or ["ABSOLUTE_FILTER_UNSPECIFIED_REJECT"]:
                    absolute_filter_reject_counter[str(code).strip()] += 1
                continue
            eligible_after_absolute_cols.append(col_idx)
            window_returns: dict[int, float] = {}
            has_all_returns = True
            for window, _weight in score_windows:
                value = float(returns_by_window[window][row_idx, col_idx])
                if value != value:
                    selection_chain_reject_counter[f"SELECTION_CHAIN_WINDOW_{int(window)}_INSUFFICIENT_HISTORY"] += 1
                    has_all_returns = False
                    break
                window_returns[int(window)] = float(value)
            if not has_all_returns:
                continue
            for window, _weight in score_windows:
                eligible_scores_by_window[int(window)][col_idx] = float(window_returns[int(window)])

        primary_window = int(score_windows[0][0])
        eligible_cols = sorted(eligible_scores_by_window[primary_window].keys(), key=lambda col: symbols[col])
        ranks_by_window = {
            int(window): _rank_score(eligible_scores_by_window[int(window)])
            for window, _weight in score_windows
        }
        combined_scores = {
            col_idx: sum(
                float(weight) * float(ranks_by_window[int(window)].get(col_idx, 0.0))
                for window, weight in score_windows
            )
            for col_idx in eligible_cols
        }
        ranked_cols = sorted(
            eligible_cols,
            key=lambda col_idx: (
                -float(combined_scores.get(col_idx, 0.0)),
                *[
                    -float(eligible_scores_by_window[int(window)].get(col_idx, float("-inf")))
                    for window, _weight in score_windows
                ],
                symbols[col_idx],
            ),
        )
        upstream_trade_mode = str(trade_mode_arr[row_idx] or "").strip().upper()
        upstream_risk_budget_multiplier = (
            float(source_risk_budget_arr[row_idx])
            if row_idx < len(source_risk_budget_arr) and float(source_risk_budget_arr[row_idx]) == float(source_risk_budget_arr[row_idx])
            else None
        )
        provisional_sleeve_budget = None
        provisional_target_exposure = _safe_notional_exposure(
            float(max(0, int(governor_slot_cap))) / float(runtime_hard_max_positions)
            if int(runtime_hard_max_positions) > 0
            else 0.0
        )
        if is_formal_phase1_boundary:
            provisional_sleeve_budget = {
                "effective_state_5": state_5_arr[row_idx],
                "target_exposure": provisional_target_exposure,
                "target_selected_count": int(governor_slot_cap),
                "slot_cap": int(governor_slot_cap),
                "budget_reason_codes": [f"UPSTREAM_TRADE_MODE::{upstream_trade_mode or 'UNKNOWN'}"],
            }
            if upstream_risk_budget_multiplier is not None:
                provisional_sleeve_budget["upstream_risk_budget_multiplier"] = float(upstream_risk_budget_multiplier)
                provisional_sleeve_budget["budget_reason_codes"].append("UPSTREAM_RISK_BUDGET_MULTIPLIER_EXPLANATORY_ONLY")
            if provisional_target_exposure is None or provisional_target_exposure <= 1e-12:
                provisional_sleeve_budget["budget_reason_codes"].append("PROVISIONAL_TARGET_EXPOSURE_FALLBACK")
        exposure_semantics = resolve_cn_etf_beta_exposure_semantics(
            etf_beta_contract=etf_beta_cfg,
            effective_state_5=state_5_arr[row_idx],
            total_exposure_cap=provisional_target_exposure,
            slot_cap=governor_slot_cap,
            target_selected_count=governor_slot_cap,
            sleeve_budget_snapshot=provisional_sleeve_budget,
        )
        strategy_role = str(exposure_semantics.get("strategy_role") or self._etf_beta_strategy_role).strip()
        governor_boundary_mode = str(
            exposure_semantics.get("governor_boundary_mode") or self._etf_beta_governor_boundary_mode
        ).strip()
        local_policy_mode = str(exposure_semantics.get("local_policy_mode") or self._etf_beta_local_policy_mode).strip()
        boundary_policy_mode = str(
            exposure_semantics.get("boundary_policy_mode") or self._etf_beta_boundary_policy_mode
        ).strip()
        exposure_policy_family = str(exposure_semantics.get("exposure_policy_family") or self._etf_beta_exposure_policy_family).strip()
        policy_scope = str(exposure_semantics.get("policy_scope") or self._etf_beta_policy_scope).strip()
        broad_based_only = bool(exposure_semantics.get("broad_based_only", self._etf_beta_broad_based_only))
        layering_policy = str(exposure_semantics.get("layering_policy") or self._etf_beta_layering_policy).strip()
        controlled_accumulation_mode = str(
            exposure_semantics.get("controlled_accumulation_mode") or self._etf_beta_controlled_accumulation_mode
        ).strip()
        layering_band = str(exposure_semantics.get("layering_band") or "").strip()
        layering_active = bool(exposure_semantics.get("layering_active", False))
        layering_reason_codes = [
            str(code).strip()
            for code in list(exposure_semantics.get("layering_reason_codes") or ())
            if str(code).strip()
        ]
        target_exposure = (
            float(exposure_semantics.get("target_exposure"))
            if exposure_semantics.get("target_exposure") is not None
            else None
        )
        target_exposure_source = str(exposure_semantics.get("target_exposure_source") or "").strip()
        min_deployable_exposure = (
            float(exposure_semantics.get("min_deployable_exposure"))
            if exposure_semantics.get("min_deployable_exposure") is not None
            else None
        )
        min_deployable_exposure_source = str(exposure_semantics.get("min_deployable_exposure_source") or "").strip()
        target_selected_count = int(exposure_semantics.get("target_selected_count") or 0)
        target_selected_count_source = str(exposure_semantics.get("target_selected_count_source") or "").strip()
        if self._etf_beta_max_selected_symbols is not None and target_selected_count > 0:
            target_selected_count = min(target_selected_count, int(self._etf_beta_max_selected_symbols))
        selected_cap = max(0, int(target_selected_count))
        slot_cap = int(selected_cap)
        target_exposure_per_symbol = (
            float(target_exposure) / float(max(target_selected_count, 1))
            if target_exposure is not None
            else None
        )
        fallback_allowed = bool(exposure_semantics.get("fallback_allowed", False))
        fallback_allowed_source = str(exposure_semantics.get("fallback_allowed_source") or "").strip()
        weak_state_defense_policy_active = bool(exposure_semantics.get("weak_state_defense_policy_active", False))
        weak_state_defense_candidate_symbols = [
            str(symbol).strip().upper()
            for symbol in list(exposure_semantics.get("weak_state_defense_candidate_symbols") or ())
            if str(symbol).strip()
        ]
        weak_state_defense_allow_core_beta = bool(exposure_semantics.get("weak_state_defense_allow_core_beta", False))
        weak_state_defense_deployability_floor_applied = bool(
            exposure_semantics.get("weak_state_defense_deployability_floor_applied", False)
        )
        weak_state_defense_unavailable_reason_codes = [
            str(code).strip()
            for code in list(exposure_semantics.get("weak_state_defense_unavailable_reason_codes") or ())
            if str(code).strip()
        ]
        is_phase1_allocation_engine = _is_formal_stabilizer_role(strategy_role, local_policy_mode)
        requested_budget = (
            float(exposure_semantics.get("requested_budget"))
            if exposure_semantics.get("requested_budget") is not None
            else None
        )
        applied_budget = (
            float(exposure_semantics.get("applied_budget"))
            if exposure_semantics.get("applied_budget") is not None
            else None
        )
        target_exposure_by_symbol = {
            str(symbol).strip().upper(): float(value)
            for symbol, value in dict(exposure_semantics.get("targets") or {}).items()
            if str(symbol).strip() and value is not None and float(value) > 0.0
        }
        governor_hard_blocked = bool(exposure_semantics.get("governor_hard_blocked", False))
        governor_hard_block_reason_codes = [
            str(code).strip()
            for code in list(exposure_semantics.get("governor_hard_block_reason_codes") or ())
            if str(code).strip()
        ]
        governor_budget_reason_codes = [
            str(code).strip()
            for code in list(exposure_semantics.get("governor_budget_reason_codes") or ())
            if str(code).strip()
        ]
        local_boundary_state = str(exposure_semantics.get("local_boundary_state") or "").strip()
        local_boundary_reason_codes = [
            str(code).strip()
            for code in list(exposure_semantics.get("local_boundary_reason_codes") or ())
            if str(code).strip()
        ]
        allocation_reason_codes = [
            str(code).strip()
            for code in list(exposure_semantics.get("reason_codes") or ())
            if str(code).strip()
        ]
        cash_weight = (
            float(exposure_semantics.get("cash_weight"))
            if exposure_semantics.get("cash_weight") is not None
            else None
        )
        defense_weight = (
            float(exposure_semantics.get("defense_weight"))
            if exposure_semantics.get("defense_weight") is not None
            else None
        )
        equity_core_bucket = (
            float(exposure_semantics.get("equity_core_bucket"))
            if exposure_semantics.get("equity_core_bucket") is not None
            else None
        )
        defense_tilt_bucket = (
            float(exposure_semantics.get("defense_tilt_bucket"))
            if exposure_semantics.get("defense_tilt_bucket") is not None
            else None
        )
        cash_buffer_bucket = (
            float(exposure_semantics.get("cash_buffer_bucket"))
            if exposure_semantics.get("cash_buffer_bucket") is not None
            else None
        )
        strategic_floor_cap = (
            float(exposure_semantics.get("strategic_floor_cap"))
            if exposure_semantics.get("strategic_floor_cap") is not None
            else None
        )
        tactical_overlay_cap = (
            float(exposure_semantics.get("tactical_overlay_cap"))
            if exposure_semantics.get("tactical_overlay_cap") is not None
            else None
        )
        limited_defense_cap = (
            float(exposure_semantics.get("limited_defense_cap"))
            if exposure_semantics.get("limited_defense_cap") is not None
            else None
        )
        deployment_pace = (
            float(exposure_semantics.get("deployment_pace"))
            if exposure_semantics.get("deployment_pace") is not None
            else None
        )
        pace_policy_gap = (
            float(exposure_semantics.get("pace_policy_gap"))
            if exposure_semantics.get("pace_policy_gap") is not None
            else None
        )
        pace_policy_reason_code = str(exposure_semantics.get("pace_policy_reason_code") or "").strip()
        pace_policy_mode = str(exposure_semantics.get("pace_policy_mode") or "").strip()
        bull_partial_overlay_pace_ratio = (
            float(exposure_semantics.get("bull_partial_overlay_pace_ratio"))
            if exposure_semantics.get("bull_partial_overlay_pace_ratio") is not None
            else None
        )
        bull_pace_mode = str(exposure_semantics.get("bull_pace_mode") or "").strip()
        trans_up_contract_mode = str(exposure_semantics.get("trans_up_contract_mode") or "").strip()
        trans_up_single_seat_core_recovery = bool(
            exposure_semantics.get("trans_up_single_seat_core_recovery", False)
        )
        hard_block_flags = [
            str(code).strip()
            for code in list(exposure_semantics.get("hard_block_flags") or ())
            if str(code).strip()
        ]
        core_accumulator_symbols = [
            str(symbol).strip().upper()
            for symbol in list(exposure_semantics.get("core_accumulator_symbols") or ())
            if str(symbol).strip()
        ]
        tactical_satellite_symbols = [
            str(symbol).strip().upper()
            for symbol in list(exposure_semantics.get("tactical_satellite_symbols") or ())
            if str(symbol).strip()
        ]
        limited_defense_symbols = [
            str(symbol).strip().upper()
            for symbol in list(exposure_semantics.get("limited_defense_symbols") or ())
            if str(symbol).strip()
        ]
        symbol_role_map = {
            str(symbol).strip().upper(): str(role).strip()
            for symbol, role in dict(exposure_semantics.get("symbol_role_map") or {}).items()
            if str(symbol).strip() and str(role).strip()
        }
        if strategic_floor_cap is not None:
            strategic_floor_cap_rows[row_idx] = float(strategic_floor_cap)
        if tactical_overlay_cap is not None:
            tactical_overlay_cap_rows[row_idx] = float(tactical_overlay_cap)
        if limited_defense_cap is not None:
            limited_defense_cap_rows[row_idx] = float(limited_defense_cap)
        if deployment_pace is not None:
            deployment_pace_rows[row_idx] = float(deployment_pace)
        if pace_policy_gap is not None:
            pace_policy_gap_rows[row_idx] = float(pace_policy_gap)
        if pace_policy_reason_code:
            pace_policy_reason_code_rows[row_idx] = str(pace_policy_reason_code)
        if pace_policy_mode:
            pace_policy_mode_rows[row_idx] = str(pace_policy_mode)
        if bull_partial_overlay_pace_ratio is not None:
            bull_partial_overlay_pace_ratio_rows[row_idx] = float(bull_partial_overlay_pace_ratio)
        if bull_pace_mode:
            bull_pace_mode_rows[row_idx] = str(bull_pace_mode)
        hard_block_flag_rows[row_idx] = list(hard_block_flags)
        core_accumulator_symbol_rows[row_idx] = list(core_accumulator_symbols)
        tactical_satellite_symbol_rows[row_idx] = list(tactical_satellite_symbols)
        limited_defense_symbol_rows[row_idx] = list(limited_defense_symbols)
        symbol_role_map_rows[row_idx] = dict(symbol_role_map)
        is_a0_core_satellite_v2 = (
            self._etf_beta_rule_family == "broad_based_rotation_template_a0_core_satellite_v2"
            or self._etf_beta_selection_chain_profile == "core_growth_slot"
        )
        core_slot_display_symbols = (
            list(self._etf_beta_core_slot_symbols)
            if self._etf_beta_core_slot_symbols
            else [
                symbol.upper()
                for symbol in self._etf_beta_candidate_pool_symbols
                if symbol.upper() not in set(self._etf_beta_growth_slot_symbols)
                and symbol.upper() != self._etf_beta_growth_seat_symbol
                and _symbol_bucket(symbol) not in _GROWTH_BUCKETS
            ]
        )
        growth_slot_display_symbols = (
            list(self._etf_beta_growth_slot_symbols)
            if self._etf_beta_growth_slot_symbols
            else [self._etf_beta_growth_seat_symbol] if self._etf_beta_growth_seat_symbol else [
                symbol.upper()
                for symbol in self._etf_beta_candidate_pool_symbols
                if _symbol_bucket(symbol) in _GROWTH_BUCKETS
            ]
        )
        core_slot_set = {symbol.upper() for symbol in core_slot_display_symbols if symbol}
        growth_slot_set = {symbol.upper() for symbol in growth_slot_display_symbols if symbol}
        core_slot_selected_col: int | None = None
        growth_slot_selected_col: int | None = None
        slot_selection_reason_codes: dict[str, list[str]] = {}
        slot_under_deploy_reason_codes: dict[str, list[str]] = {}
        if is_a0_core_satellite_v2:
            core_ranked_cols = [col_idx for col_idx in ranked_cols if display_symbols[col_idx].upper() in core_slot_set]
            growth_ranked_cols = [col_idx for col_idx in ranked_cols if display_symbols[col_idx].upper() in growth_slot_set]
            slot_under_deploy_reason_codes["core_slot"] = []
            slot_under_deploy_reason_codes["growth_slot"] = []
            if selected_cap <= 0:
                slot_under_deploy_reason_codes["core_slot"].append("ETF_BETA_CORE_SLOT_SUPPRESSED_BY_SLOT_CAP")
                slot_under_deploy_reason_codes["growth_slot"].append("ETF_BETA_GROWTH_SLOT_SUPPRESSED_BY_SLOT_CAP")
            else:
                if core_ranked_cols:
                    core_slot_selected_col = core_ranked_cols[0]
                else:
                    slot_under_deploy_reason_codes["core_slot"].append("ETF_BETA_CORE_SLOT_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER")
                if selected_cap >= 2:
                    for col_idx in growth_ranked_cols:
                        if core_slot_selected_col is not None and col_idx == core_slot_selected_col:
                            continue
                        growth_slot_selected_col = col_idx
                        break
                    if growth_slot_selected_col is None:
                        slot_under_deploy_reason_codes["growth_slot"].append("ETF_BETA_GROWTH_SLOT_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER")
                else:
                    slot_under_deploy_reason_codes["growth_slot"].append("ETF_BETA_GROWTH_SLOT_SUPPRESSED_BY_SLOT_CAP")
            selected_cols = []
            if core_slot_selected_col is not None:
                selected_cols.append(core_slot_selected_col)
            if growth_slot_selected_col is not None and growth_slot_selected_col not in selected_cols:
                selected_cols.append(growth_slot_selected_col)
            if core_slot_selected_col is not None:
                core_symbol = display_symbols[core_slot_selected_col].upper()
                slot_selection_reason_codes["core_slot"] = [
                    "SLOT::CORE_SLOT",
                    f"SELECTED::{core_symbol}",
                    f"STATE::{str(state_5_arr[row_idx]).upper()}",
                    f"REBALANCE::{self._etf_beta_rebalance_frequency.upper()}",
                ]
            if growth_slot_selected_col is not None:
                growth_symbol = display_symbols[growth_slot_selected_col].upper()
                slot_selection_reason_codes["growth_slot"] = [
                    "SLOT::GROWTH_SLOT",
                    f"SELECTED::{growth_symbol}",
                    f"STATE::{str(state_5_arr[row_idx]).upper()}",
                    f"REBALANCE::{self._etf_beta_rebalance_frequency.upper()}",
                ]
            for col_idx in ranked_cols:
                symbol_text = display_symbols[col_idx].upper()
                if symbol_text in core_slot_set and core_slot_selected_col is not None and col_idx != core_slot_selected_col:
                    selection_chain_reject_counter["SELECTION_CHAIN_CORE_SLOT_RANK_LOSS"] += 1
                elif symbol_text in growth_slot_set and growth_slot_selected_col is not None and col_idx != growth_slot_selected_col:
                    selection_chain_reject_counter["SELECTION_CHAIN_GROWTH_SLOT_RANK_LOSS"] += 1
                elif symbol_text not in core_slot_set and symbol_text not in growth_slot_set:
                    selection_chain_reject_counter["SELECTION_CHAIN_OUTSIDE_SLOT_POOL"] += 1
        else:
            selected_cols = ranked_cols[:selected_cap] if selected_cap > 0 else []
            if selected_cap > 0 and len(ranked_cols) > len(selected_cols):
                selection_chain_reject_counter["SELECTION_CHAIN_RANK_BELOW_CUTOFF"] += int(len(ranked_cols) - len(selected_cols))
        selected_display_symbols = [display_symbols[col_idx] for col_idx in selected_cols]
        standalone_live_seat_source = None
        standalone_live_seat_carry_enabled = (
            not is_phase1_allocation_engine
            and str(strategy_role or "").strip().lower() == "governed_broad_based_standalone_mainline"
            and str(exposure_policy_family or "").strip().lower() == "broad_based_standalone_mainline_v1"
            and canonical_state_5(str(state_5_arr[row_idx]).upper()) in {"TRANS_UP", "RISK_OFF"}
        )
        if standalone_live_seat_carry_enabled:
            previous_selected_symbols = list(selected_rows[-1]) if selected_rows else []
            selected_display_symbols, standalone_live_seat_source = _resolve_standalone_live_seat_symbols(
                strategy_role=strategy_role,
                exposure_policy_family=exposure_policy_family,
                state_5=str(state_5_arr[row_idx]).upper(),
                rebalance_day=rebalance_day,
                governor_hard_blocked=governor_hard_blocked,
                target_exposure=target_exposure,
                selected_cap=selected_cap,
                current_selected_symbols=list(selected_display_symbols),
                previous_selected_symbols=previous_selected_symbols,
                target_exposure_by_symbol=target_exposure_by_symbol,
                core_accumulator_symbols=core_accumulator_symbols,
            )
            display_sym_to_col = {
                str(display_symbol).strip().upper(): idx for idx, display_symbol in enumerate(display_symbols)
            }
            selected_cols = [
                display_sym_to_col.get(str(symbol_text).strip().upper())
                for symbol_text in list(selected_display_symbols)
            ]
            selected_cols = [col_idx for col_idx in selected_cols if col_idx is not None]
        selection_chain_winner_counter["candidate_pool_count"] = int(len(candidate_pool_cols))
        selection_chain_winner_counter["eligible_after_absolute_filter"] = int(len(eligible_after_absolute_cols))
        selection_chain_winner_counter["eligible_after_selection_chain"] = int(len(ranked_cols))
        selection_chain_winner_counter["selected_count"] = int(len(selected_cols))
        if core_slot_selected_col is not None:
            selection_chain_winner_counter["core_slot_selected"] = 1
        if growth_slot_selected_col is not None:
            selection_chain_winner_counter["growth_slot_selected"] = 1

        core_slot_target_exposure = (
            float(target_exposure_per_symbol)
            if is_a0_core_satellite_v2 and selected_cap >= 1 and target_exposure_per_symbol is not None
            else None
        )
        growth_slot_target_exposure = (
            float(target_exposure_per_symbol)
            if is_a0_core_satellite_v2 and selected_cap >= 2 and target_exposure_per_symbol is not None
            else None
        )
        selection_reason_codes = {
            display_symbols[col_idx]: [
                "ETF_BETA_CORE_SCOPE",
                *list(_absolute_filter_reason_codes(self._etf_beta_absolute_filter_mode)),
                *[f"RS{int(window)}_RANK_PASS" for window, _weight in score_windows],
                f"FILTER_PROFILE::{self._etf_beta_absolute_filter_profile.upper()}" if self._etf_beta_absolute_filter_profile else "",
                f"POOL_PROFILE::{self._etf_beta_candidate_pool_profile.upper()}" if self._etf_beta_candidate_pool_profile else "",
                f"SELECTION_PROFILE::{self._etf_beta_selection_chain_profile.upper()}" if self._etf_beta_selection_chain_profile else "",
                f"STATE::{str(state_5_arr[row_idx]).upper()}",
                f"RULE_FAMILY::{self._etf_beta_rule_family.upper()}",
                f"REBALANCE::{self._etf_beta_rebalance_frequency.upper()}",
                _rebalance_selection_reason_code(self._etf_beta_rebalance_frequency, rebalance_day=rebalance_day),
            ]
            for col_idx in selected_cols
        }
        selection_reason_codes = {
            symbol_text: [code for code in list(codes or []) if str(code).strip()]
            for symbol_text, codes in selection_reason_codes.items()
        }
        if standalone_live_seat_source:
            for symbol_text in list(selected_display_symbols):
                selection_reason_codes.setdefault(symbol_text, [])
                selection_reason_codes[symbol_text].extend(
                    [
                        "INTER_REBALANCE_LIVE_SEAT_CARRY_FORWARD",
                        f"LIVE_SEAT_SOURCE::{standalone_live_seat_source.upper()}",
                    ]
                )
        for symbol_text, codes in selection_reason_codes.items():
            role_text = self._etf_beta_template_role_map.get(symbol_text.upper())
            proxy_text = self._etf_beta_template_proxy_map.get(symbol_text.upper())
            if strategy_role:
                codes.append(f"STRATEGY_ROLE::{strategy_role.upper()}")
            if local_policy_mode:
                codes.append(f"LOCAL_POLICY::{local_policy_mode.upper()}")
            if self._etf_beta_template_id:
                codes.append(f"TEMPLATE::{self._etf_beta_template_id.upper()}")
            if self._etf_beta_template_asset_pool_version:
                codes.append(f"POOL::{self._etf_beta_template_asset_pool_version.upper()}")
            if role_text:
                codes.append(f"ROLE::{str(role_text).upper()}")
            if proxy_text:
                codes.append(f"PROXY::{str(proxy_text).upper()}")
            if is_a0_core_satellite_v2:
                if core_slot_selected_col is not None and symbol_text.upper() == display_symbols[core_slot_selected_col].upper():
                    codes.append("SLOT::CORE_SLOT")
                if growth_slot_selected_col is not None and symbol_text.upper() == display_symbols[growth_slot_selected_col].upper():
                    codes.append("SLOT::GROWTH_SLOT")
                if self._etf_beta_proxy_replacement_mode:
                    codes.append(f"PROXY_REPLACEMENT_MODE::{self._etf_beta_proxy_replacement_mode.upper()}")
            if layering_band:
                codes.append(f"LAYERING::{layering_band}")
            codes.extend(layering_reason_codes)
        if is_phase1_allocation_engine:
            absolute_filter_reject_counter = Counter()
            selection_chain_reject_counter = Counter()
            formal_selected_cols: list[int] = []
            provisional_selected_cols: list[int] = []
            formal_selection_reason_codes: dict[str, list[str]] = {}
            ranked_priority = {col_idx: idx for idx, col_idx in enumerate(ranked_cols)}
            positive_target_candidates: list[tuple[int, str, float]] = []
            for symbol_text, symbol_target in target_exposure_by_symbol.items():
                col_idx = self._sym_to_col.get(_normalize_etf_symbol_key(symbol_text))
                if col_idx is None:
                    continue
                positive_target_candidates.append((col_idx, symbol_text.upper(), float(symbol_target)))
            positive_target_candidates.sort(
                key=lambda item: (
                    -float(item[2]),
                    ranked_priority.get(item[0], len(ranked_priority)),
                    item[1],
                )
            )
            selection_cap = max(0, int(target_selected_count))
            if positive_target_candidates and selection_cap > 0:
                positive_target_candidates = positive_target_candidates[:selection_cap]
            for col_idx, symbol_text, symbol_target in positive_target_candidates:
                formal_selected_cols.append(col_idx)
                reason_codes = [
                    "PHASE1_FORMAL_SCOPE",
                    f"STATE::{str(state_5_arr[row_idx]).upper()}",
                    f"RULE_FAMILY::{self._etf_beta_rule_family.upper()}",
                    f"LOCAL_POLICY::{local_policy_mode.upper()}",
                    f"BOUNDARY_POLICY::{boundary_policy_mode.upper()}" if boundary_policy_mode else "",
                    f"LOCAL_BOUNDARY_STATE::{local_boundary_state}" if local_boundary_state else "",
                    f"TARGET_EXPOSURE::{float(symbol_target):.6f}",
                    *list(local_boundary_reason_codes),
                    *list(allocation_reason_codes),
                ]
                formal_selection_reason_codes[symbol_text] = [code for code in reason_codes if code]
            if not formal_selected_cols and governor_slot_cap > 0 and not governor_hard_blocked:
                # Break the precompute self-lock: before Governor budget is materialized,
                # fall back to the state slot cap so Phase 1 can emit provisional picks.
                provisional_candidates = list(ranked_cols)
                if not provisional_candidates:
                    provisional_candidates = [
                        self._sym_to_col.get(_normalize_etf_symbol_key(symbol_text))
                        for symbol_text in self._etf_beta_formal_scope_symbols
                    ]
                    provisional_candidates = [col_idx for col_idx in provisional_candidates if col_idx is not None]
                provisional_selected_cols = provisional_candidates[: max(0, int(governor_slot_cap))]
                if provisional_selected_cols:
                    target_selected_count_source = "state_slot_cap_fallback"
                    for col_idx in provisional_selected_cols:
                        symbol_text = display_symbols[col_idx]
                        reason_codes = [
                            "PHASE1_FORMAL_SCOPE",
                            f"STATE::{str(state_5_arr[row_idx]).upper()}",
                            f"RULE_FAMILY::{self._etf_beta_rule_family.upper()}",
                            f"LOCAL_POLICY::{local_policy_mode.upper()}",
                            f"PROVISIONAL_SLOT_CAP::{int(governor_slot_cap)}",
                            "PHASE1_GOVERNOR_BUDGET_PENDING",
                            f"BOUNDARY_POLICY::{boundary_policy_mode.upper()}" if boundary_policy_mode else "",
                            *list(allocation_reason_codes),
                        ]
                        formal_selection_reason_codes[symbol_text.upper()] = [code for code in reason_codes if code]
            selected_cols = formal_selected_cols or provisional_selected_cols
            selected_cap = len(selected_cols)
            slot_cap = selected_cap
            target_selected_count = selected_cap
            target_exposure_per_symbol = None
            core_slot_selected_col = None
            growth_slot_selected_col = None
            slot_selection_reason_codes = {}
            slot_under_deploy_reason_codes = {}
            selection_reason_codes = formal_selection_reason_codes
            selected_display_symbols = [display_symbols[col_idx] for col_idx in selected_cols]
            eligible_symbols = list(self._etf_beta_formal_scope_symbols)
            selection_chain_winner_counter = Counter()
            selection_chain_winner_counter["candidate_pool_count"] = int(len(self._etf_beta_formal_scope_symbols))
            selection_chain_winner_counter["eligible_after_absolute_filter"] = int(len(self._etf_beta_formal_scope_symbols))
            selection_chain_winner_counter["eligible_after_selection_chain"] = int(len(self._etf_beta_formal_scope_symbols))
            selection_chain_winner_counter["selected_count"] = int(selected_cap)
            if trans_up_single_seat_core_recovery:
                selected_core_cols = [
                    col_idx
                    for col_idx in selected_cols
                    if display_symbols[col_idx].upper() in set(core_accumulator_symbols)
                ]
                selected_cols = selected_core_cols[:1] if selected_core_cols else selected_cols[:1]
                selected_cap = len(selected_cols)
                slot_cap = selected_cap
                target_selected_count = selected_cap
                selected_display_symbols = [display_symbols[col_idx] for col_idx in selected_cols]
                selection_chain_winner_counter["selected_count"] = int(selected_cap)
                selected_recovery_symbol = selected_display_symbols[0].upper() if selected_display_symbols else ""
                if selected_recovery_symbol:
                    target_exposure_by_symbol = {
                        selected_recovery_symbol: float(strategic_floor_cap or 0.0)
                    }
                    selection_reason_codes[selected_recovery_symbol] = [
                        code
                        for code in [
                            *list(selection_reason_codes.get(selected_recovery_symbol) or []),
                            "TRANS_UP_SINGLE_SEAT_CORE_RECOVERY",
                        ]
                        if str(code).strip()
                    ]
                else:
                    target_exposure_by_symbol = {}
            core_slot_target_exposure = None
            growth_slot_target_exposure = None
            core_slot_target_actual_exposure = None
            growth_slot_target_actual_exposure = None
        if is_formal_phase1_boundary:
            effective_slot_cap = max(0, int(selected_cap))
            trade_mode_arr[row_idx] = _trade_mode_from_slot_cap(effective_slot_cap)
            governor_slot_cap_arr[row_idx] = effective_slot_cap
            if requested_budget is not None and requested_budget > 1e-12:
                formal_boundary_runtime_budget_rows[row_idx] = float(requested_budget)
            elif effective_slot_cap > 0:
                formal_boundary_runtime_budget_rows[row_idx] = float(effective_slot_cap) / float(runtime_hard_max_positions)
            else:
                formal_boundary_runtime_budget_rows[row_idx] = 0.0
        governor_boundary_reason_codes = [
            f"GOVERNOR_STATE::{str(state_5_arr[row_idx]).upper()}",
            f"GOVERNOR_BOUNDARY_MODE::{governor_boundary_mode.upper()}" if governor_boundary_mode else "",
            f"GOVERNOR_BOUNDARY_POLICY::{boundary_policy_mode.upper()}" if boundary_policy_mode else "",
            f"GOVERNOR_TARGET_EXPOSURE_SOURCE::{target_exposure_source.upper()}" if target_exposure_source else "",
            f"GOVERNOR_TARGET_SELECTED_COUNT_SOURCE::{target_selected_count_source.upper()}" if target_selected_count_source else "",
            f"GOVERNOR_FALLBACK_ALLOWED_SOURCE::{fallback_allowed_source.upper()}" if fallback_allowed_source else "",
            f"GOVERNOR_LAYERING_BAND::{layering_band}" if layering_band else "",
            *[
                f"GOVERNOR_BUDGET::{code.upper()}"
                for code in governor_budget_reason_codes
                if str(code).strip()
            ],
            *[
                f"GOVERNOR_HARD_BLOCK::{code.upper()}"
                for code in governor_hard_block_reason_codes
                if str(code).strip()
            ],
        ]
        governor_boundary_reason_codes = [code for code in governor_boundary_reason_codes if code]
        runtime_reason_codes: list[str] = []
        runtime_reason_codes.extend(
            [
                f"GOVERNOR_BUDGET::{code.upper()}"
                for code in governor_budget_reason_codes
                if str(code).strip()
            ]
        )
        selected_display_symbols = list(selected_display_symbols)
        fallback_active = False
        vol_target_payload: dict[str, Any] = {
            "active": False,
            "window": self._etf_beta_vol_target_window,
            "annualized_target": self._etf_beta_vol_target_annualized_target,
            "min_scale": self._etf_beta_vol_target_min_scale,
            "max_scale": self._etf_beta_vol_target_max_scale,
            "scale_by_symbol": {},
            "realized_vol_by_symbol": {},
        }
        if self._etf_beta_rule_family == "dual_momentum_vol_target" and selected_cols:
            scale_by_symbol: dict[str, float] = {}
            realized_vol_by_symbol: dict[str, float] = {}
            scale_changed = False
            for col_idx in selected_cols:
                symbol_text = display_symbols[col_idx]
                realized_vol = _realized_vol_annualized(daily_returns[:, col_idx], row_idx, self._etf_beta_vol_target_window)
                if realized_vol is None:
                    scale = self._etf_beta_vol_target_max_scale
                else:
                    raw_scale = self._etf_beta_vol_target_annualized_target / float(realized_vol)
                    scale = min(self._etf_beta_vol_target_max_scale, max(self._etf_beta_vol_target_min_scale, float(raw_scale)))
                    realized_vol_by_symbol[symbol_text] = float(realized_vol)
                scale_by_symbol[symbol_text] = float(scale)
                selection_reason_codes.setdefault(symbol_text, []).extend(
                    [
                        f"VOL_TARGET_WINDOW::{int(self._etf_beta_vol_target_window)}",
                        f"VOL_TARGET_SCALE::{float(scale):.4f}",
                    ]
                )
                if float(scale) < float(self._etf_beta_vol_target_max_scale) - 1e-9:
                    scale_changed = True
            vol_target_payload = {
                "active": True,
                "window": self._etf_beta_vol_target_window,
                "annualized_target": self._etf_beta_vol_target_annualized_target,
                "min_scale": self._etf_beta_vol_target_min_scale,
                "max_scale": self._etf_beta_vol_target_max_scale,
                "scale_by_symbol": scale_by_symbol,
                "realized_vol_by_symbol": realized_vol_by_symbol,
            }
            runtime_reason_codes.append("ETF_BETA_VOL_TARGET_ACTIVE")
            if scale_changed:
                runtime_reason_codes.append("ETF_BETA_VOL_TARGET_SCALED_DOWN")
        if is_phase1_allocation_engine:
            runtime_reason_codes.extend(list(allocation_reason_codes))
            if strategy_role == "strategic_beta_stabilizer":
                runtime_reason_codes.append("ETF_BETA_STRATEGIC_BETA_STABILIZER_ACTIVE")
            else:
                runtime_reason_codes.append("ETF_BETA_PHASE1_ALLOCATION_ENGINE_ACTIVE")
            if boundary_policy_mode:
                runtime_reason_codes.append(f"ETF_BETA_BOUNDARY_POLICY::{boundary_policy_mode.upper()}")
            if local_boundary_state:
                runtime_reason_codes.append(f"ETF_BETA_LOCAL_BOUNDARY_STATE::{local_boundary_state}")
            runtime_reason_codes.extend(list(local_boundary_reason_codes))
            if governor_hard_blocked:
                runtime_reason_codes.append("ETF_BETA_PHASE1_GOVERNOR_HARD_BLOCK")
            if provisional_selected_cols:
                runtime_reason_codes.append("ETF_BETA_PHASE1_PROVISIONAL_SLOT_CAP_FALLBACK")
        if exposure_policy_family == "broad_based_governed_v1":
            runtime_reason_codes.append("ETF_BETA_BROAD_BASED_GOVERNED_POLICY_ACTIVE")
        if exposure_policy_family == "broad_based_standalone_mainline_v1":
            runtime_reason_codes.append("ETF_BETA_STANDALONE_MAINLINE_POLICY_ACTIVE")
        if strategy_role == "governed_broad_based_standalone_mainline":
            runtime_reason_codes.append("ETF_BETA_STANDALONE_MAINLINE_ACTIVE")
        if standalone_live_seat_source:
            runtime_reason_codes.append("ETF_BETA_INTER_REBALANCE_LIVE_SEAT_CARRY_FORWARD_ACTIVE")
            runtime_reason_codes.append(f"ETF_BETA_LIVE_SEAT_SOURCE::{standalone_live_seat_source.upper()}")
        if exposure_policy_family == "phase1_governed_allocation_v1":
            runtime_reason_codes.append("ETF_BETA_PHASE1_GOVERNED_ALLOCATION_POLICY_ACTIVE")
        if trans_up_single_seat_core_recovery:
            runtime_reason_codes.append("ETF_BETA_TRANS_UP_SINGLE_SEAT_CORE_RECOVERY_ACTIVE")
        if broad_based_only:
            runtime_reason_codes.append("ETF_BETA_BROAD_BASED_ONLY_SCOPE")
        runtime_reason_codes.extend(layering_reason_codes)
        if weak_state_defense_policy_active:
            runtime_reason_codes.append("ETF_BETA_WEAK_STATE_DEFENSE_POLICY_ACTIVE")
        if weak_state_defense_allow_core_beta:
            runtime_reason_codes.append("ETF_BETA_WEAK_STATE_ALLOW_CORE_BETA")
        if weak_state_defense_deployability_floor_applied:
            runtime_reason_codes.append("ETF_BETA_WEAK_STATE_DEFENSE_SEAT_FLOOR_ACTIVE")
        runtime_reason_codes.extend(list(weak_state_defense_unavailable_reason_codes))
        if slot_cap <= 0:
            runtime_reason_codes.append("ETF_BETA_SLOT_CAP_ZERO")
        elif not rebalance_day:
            runtime_reason_codes.append(_await_rebalance_reason_code(self._etf_beta_rebalance_frequency))
        if not is_phase1_allocation_engine and slot_cap > 0 and not eligible_after_absolute_cols:
            runtime_reason_codes.append("ETF_BETA_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER")
        elif not is_phase1_allocation_engine and slot_cap > 0 and eligible_after_absolute_cols and not eligible_cols:
            runtime_reason_codes.append("ETF_BETA_NO_ELIGIBLE_AFTER_SELECTION_CHAIN")
        if slot_cap > 0 and rebalance_day and selected_cols:
            runtime_reason_codes.append(_selection_active_reason_code(self._etf_beta_rebalance_frequency))
        if is_a0_core_satellite_v2:
            for codes in slot_under_deploy_reason_codes.values():
                for code in codes:
                    runtime_reason_codes.append(str(code))
        if (
            slot_cap > 0
            and rebalance_day
            and self._etf_beta_fallback_mode == "single_symbol"
            and fallback_allowed
            and self._etf_beta_fallback_symbol
            and self._etf_beta_fallback_symbol in self._sym_to_col
            and len(selected_display_symbols) < selected_cap
        ):
            fallback_display_symbol = _display_etf_symbol(self._etf_beta_fallback_symbol)
            fallback_symbol_key = fallback_display_symbol.upper()
            if fallback_display_symbol not in selected_display_symbols:
                selected_display_symbols.append(fallback_display_symbol)
                selection_reason_codes[fallback_symbol_key] = [
                    "ETF_BETA_FALLBACK_SINGLE_SYMBOL",
                    f"FALLBACK_SYMBOL::{fallback_display_symbol}",
                    f"STATE::{str(state_5_arr[row_idx]).upper()}",
                    f"RULE_FAMILY::{self._etf_beta_rule_family.upper()}",
                    "UNDERFILLED_DEPLOYMENT_FILL",
                ]
                fallback_active = True
                runtime_reason_codes.append("ETF_BETA_FALLBACK_ACTIVE")
                if ranked_cols:
                    runtime_reason_codes.append("ETF_BETA_FALLBACK_PARTIAL_FILL_ACTIVE")
                else:
                    runtime_reason_codes.append("ETF_BETA_FALLBACK_FULL_REPLACEMENT_ACTIVE")
        if (
            slot_cap > 0
            and rebalance_day
            and len(selected_display_symbols) < selected_cap
        ):
            runtime_reason_codes.append("ETF_BETA_UNDERFILLED_DEPLOYMENT")
        if (
            weak_state_defense_policy_active
            and rebalance_day
            and slot_cap > 0
            and float(target_exposure or 0.0) > 1e-12
            and weak_state_defense_candidate_symbols
            and not selected_display_symbols
        ):
            runtime_reason_codes.append("ETF_BETA_WEAK_STATE_NO_DEPLOYABLE_DEFENSE_CANDIDATES")
        compressed_target_exposure_per_symbol = None
        if not is_phase1_allocation_engine:
            target_exposure_by_symbol, compressed_target_exposure_per_symbol = _compress_research_mainline_live_targets(
                strategy_role=strategy_role,
                exposure_policy_family=exposure_policy_family,
                state_5=str(state_5_arr[row_idx]).upper(),
                selected_symbols=list(selected_display_symbols),
                target_exposure_by_symbol=target_exposure_by_symbol,
                live_target=deployment_pace if deployment_pace is not None else target_exposure,
            )
            if compressed_target_exposure_per_symbol is not None:
                target_exposure_per_symbol = float(compressed_target_exposure_per_symbol)

        local_policy_reason_codes = list(runtime_reason_codes)
        if controlled_accumulation_mode != "none":
            local_policy_reason_codes.append(f"ETF_BETA_CONTROLLED_ACCUMULATION_MODE::{controlled_accumulation_mode.upper()}")
        actual_target_exposure = (
            float(applied_budget if applied_budget is not None else requested_budget or 0.0)
            if is_phase1_allocation_engine
            else sum(
                float(target_exposure_by_symbol.get(str(symbol).strip().upper(), float(target_exposure_per_symbol or 0.0)))
                for symbol in list(selected_display_symbols)
                if str(symbol).strip()
            )
            if selected_display_symbols and target_exposure_per_symbol is not None
            else None
        )
        core_slot_selected_symbol = (
            display_symbols[core_slot_selected_col].upper()
            if core_slot_selected_col is not None
            else None
        )
        growth_slot_selected_symbol = (
            display_symbols[growth_slot_selected_col].upper()
            if growth_slot_selected_col is not None
            else None
        )
        core_slot_target_actual_exposure = (
            float(target_exposure_by_symbol.get(core_slot_selected_symbol, float(target_exposure_per_symbol or 0.0)))
            if core_slot_selected_symbol is not None and target_exposure_per_symbol is not None
            else None
        )
        growth_slot_target_actual_exposure = (
            float(target_exposure_by_symbol.get(growth_slot_selected_symbol, float(target_exposure_per_symbol or 0.0)))
            if growth_slot_selected_symbol is not None and target_exposure_per_symbol is not None
            else None
        )
        deployability_gap = (
            max(0.0, float((applied_budget if applied_budget is not None else target_exposure) or 0.0) - float(actual_target_exposure))
            if is_phase1_allocation_engine and actual_target_exposure is not None
            else max(0.0, float(target_exposure) - float(actual_target_exposure))
            if target_exposure is not None and actual_target_exposure is not None
            else None
        )
        if (
            min_deployable_exposure is not None
            and actual_target_exposure is not None
            and float(actual_target_exposure) + 1e-12 < float(min_deployable_exposure)
        ):
            runtime_reason_codes.append("ETF_BETA_MIN_DEPLOYABLE_EXPOSURE_UNMET")
        if target_exposure is not None:
            target_exposure_rows[row_idx] = float(target_exposure)
        target_exposure_source_rows[row_idx] = target_exposure_source
        if min_deployable_exposure is not None:
            min_deployable_exposure_rows[row_idx] = float(min_deployable_exposure)
        min_deployable_exposure_source_rows[row_idx] = min_deployable_exposure_source
        target_selected_count_rows[row_idx] = int(target_selected_count)
        if target_exposure_per_symbol is not None:
            target_exposure_per_symbol_rows[row_idx] = float(target_exposure_per_symbol)
        if actual_target_exposure is not None:
            target_actual_exposure_rows[row_idx] = float(actual_target_exposure)
        if deployability_gap is not None:
            target_deployability_gap_rows[row_idx] = float(deployability_gap)
        fallback_allowed_rows[row_idx] = bool(fallback_allowed)
        target_selected_count_source_rows[row_idx] = target_selected_count_source
        fallback_allowed_source_rows[row_idx] = fallback_allowed_source
        exposure_policy_family_rows[row_idx] = exposure_policy_family
        policy_scope_rows[row_idx] = policy_scope
        broad_based_only_rows[row_idx] = bool(broad_based_only)
        layering_policy_rows[row_idx] = layering_policy
        layering_band_rows[row_idx] = layering_band
        layering_active_rows[row_idx] = bool(layering_active)
        layering_reason_rows.append(list(layering_reason_codes))
        core_slot_selected_rows[row_idx] = core_slot_selected_symbol
        growth_slot_selected_rows[row_idx] = growth_slot_selected_symbol
        slot_selection_reason_rows[row_idx] = dict(slot_selection_reason_codes)
        slot_under_deploy_reason_rows[row_idx] = {
            slot: list(codes)
            for slot, codes in slot_under_deploy_reason_codes.items()
            if list(codes)
        }
        if core_slot_target_exposure is not None:
            core_slot_target_exposure_rows[row_idx] = float(core_slot_target_exposure)
        if growth_slot_target_exposure is not None:
            growth_slot_target_exposure_rows[row_idx] = float(growth_slot_target_exposure)
        if core_slot_target_actual_exposure is not None:
            core_slot_target_actual_exposure_rows[row_idx] = float(core_slot_target_actual_exposure)
        if growth_slot_target_actual_exposure is not None:
            growth_slot_target_actual_exposure_rows[row_idx] = float(growth_slot_target_actual_exposure)
        if requested_budget is not None:
            requested_budget_rows[row_idx] = float(requested_budget)
        if applied_budget is not None:
            applied_budget_rows[row_idx] = float(applied_budget)
        if cash_weight is not None:
            cash_weight_rows[row_idx] = float(cash_weight)
        if defense_weight is not None:
            defense_weight_rows[row_idx] = float(defense_weight)
        if equity_core_bucket is not None:
            equity_core_bucket_rows[row_idx] = float(equity_core_bucket)
        if defense_tilt_bucket is not None:
            defense_tilt_bucket_rows[row_idx] = float(defense_tilt_bucket)
        if cash_buffer_bucket is not None:
            cash_buffer_bucket_rows[row_idx] = float(cash_buffer_bucket)
        targets_rows[row_idx] = dict(target_exposure_by_symbol)
        allocation_reason_rows[row_idx] = list(allocation_reason_codes)

        eligible_rows.append(list(eligible_symbols) if is_phase1_allocation_engine else [display_symbols[col_idx] for col_idx in ranked_cols])
        selected_rows.append(list(selected_display_symbols))
        selection_reason_rows.append(selection_reason_codes)
        runtime_reason_rows.append(runtime_reason_codes)
        vol_target_rows.append(vol_target_payload)
        absolute_filter_reject_count_rows[row_idx] = int(sum(absolute_filter_reject_counter.values()))
        absolute_filter_reject_reason_rows.append(dict(sorted(absolute_filter_reject_counter.items())))
        selection_chain_winner_rows.append(dict(selection_chain_winner_counter))
        selection_chain_reject_reason_rows.append(dict(sorted(selection_chain_reject_counter.items())))

    if is_formal_phase1_boundary:
        self._trade_mode_name_arr = np.array([str(value or "").strip().upper() for value in trade_mode_arr], dtype=object)
        self._trade_mode = np.array(
            [_trade_mode_code_from_name(value) for value in self._trade_mode_name_arr],
            dtype=np.int8,
        )
        self._risk_budget_multiplier_arr = np.array(formal_boundary_runtime_budget_rows, dtype=float)
        self._regime_risk_budget_multiplier_arr = np.array(formal_boundary_runtime_budget_rows, dtype=float)
        self._formal_phase1_runtime_boundary_active = True
    else:
        self._formal_phase1_runtime_boundary_active = False
    self._etf_beta_slot_cap_arr = target_selected_count_rows.astype(np.int32, copy=False)
    self._etf_beta_eligible_symbols_arr = np.empty(day_count, dtype=object)
    self._etf_beta_selected_symbols_arr = np.empty(day_count, dtype=object)
    self._etf_beta_selection_reason_codes_arr = np.empty(day_count, dtype=object)
    self._etf_beta_runtime_reason_codes_arr = np.empty(day_count, dtype=object)
    self._etf_beta_vol_target_info_arr = np.empty(day_count, dtype=object)
    self._etf_beta_target_exposure_arr = target_exposure_rows
    self._etf_beta_target_exposure_source_arr = target_exposure_source_rows
    self._etf_beta_min_deployable_exposure_arr = min_deployable_exposure_rows
    self._etf_beta_min_deployable_exposure_source_arr = min_deployable_exposure_source_rows
    self._etf_beta_target_selected_count_arr = target_selected_count_rows
    self._etf_beta_target_exposure_per_symbol_arr = target_exposure_per_symbol_rows
    self._etf_beta_target_actual_exposure_arr = target_actual_exposure_rows
    self._etf_beta_target_deployability_gap_arr = target_deployability_gap_rows
    self._etf_beta_fallback_allowed_arr = fallback_allowed_rows
    self._etf_beta_exposure_policy_family_arr = exposure_policy_family_rows
    self._etf_beta_policy_scope_arr = policy_scope_rows
    self._etf_beta_broad_based_only_arr = broad_based_only_rows
    self._etf_beta_layering_policy_arr = layering_policy_rows
    self._etf_beta_layering_band_arr = layering_band_rows
    self._etf_beta_layering_active_arr = layering_active_rows
    self._etf_beta_layering_reason_codes_arr = np.empty(day_count, dtype=object)
    self._etf_beta_target_selected_count_source_arr = target_selected_count_source_rows
    self._etf_beta_fallback_allowed_source_arr = fallback_allowed_source_rows
    self._etf_beta_core_slot_selected_symbol_arr = np.empty(day_count, dtype=object)
    self._etf_beta_growth_slot_selected_symbol_arr = np.empty(day_count, dtype=object)
    self._etf_beta_slot_selection_reason_codes_arr = np.empty(day_count, dtype=object)
    self._etf_beta_slot_under_deploy_reason_codes_arr = np.empty(day_count, dtype=object)
    self._etf_beta_core_slot_target_exposure_arr = core_slot_target_exposure_rows
    self._etf_beta_growth_slot_target_exposure_arr = growth_slot_target_exposure_rows
    self._etf_beta_core_slot_target_actual_exposure_arr = core_slot_target_actual_exposure_rows
    self._etf_beta_growth_slot_target_actual_exposure_arr = growth_slot_target_actual_exposure_rows
    self._etf_beta_absolute_filter_reject_count_arr = absolute_filter_reject_count_rows
    self._etf_beta_absolute_filter_reject_reason_counts_arr = np.empty(day_count, dtype=object)
    self._etf_beta_selection_chain_winner_counts_arr = np.empty(day_count, dtype=object)
    self._etf_beta_selection_chain_reject_reason_counts_arr = np.empty(day_count, dtype=object)
    self._etf_beta_targets_arr = np.empty(day_count, dtype=object)
    self._etf_beta_requested_budget_arr = requested_budget_rows
    self._etf_beta_applied_budget_arr = applied_budget_rows
    self._etf_beta_cash_weight_arr = cash_weight_rows
    self._etf_beta_defense_weight_arr = defense_weight_rows
    self._etf_beta_equity_core_bucket_arr = equity_core_bucket_rows
    self._etf_beta_defense_tilt_bucket_arr = defense_tilt_bucket_rows
    self._etf_beta_cash_buffer_bucket_arr = cash_buffer_bucket_rows
    self._etf_beta_strategic_floor_cap_arr = strategic_floor_cap_rows
    self._etf_beta_tactical_overlay_cap_arr = tactical_overlay_cap_rows
    self._etf_beta_limited_defense_cap_arr = limited_defense_cap_rows
    self._etf_beta_deployment_pace_arr = deployment_pace_rows
    self._etf_beta_pace_policy_gap_arr = pace_policy_gap_rows
    self._etf_beta_pace_policy_reason_code_arr = pace_policy_reason_code_rows
    self._etf_beta_pace_policy_mode_arr = pace_policy_mode_rows
    self._etf_beta_bull_partial_overlay_pace_ratio_arr = bull_partial_overlay_pace_ratio_rows
    self._etf_beta_bull_pace_mode_arr = bull_pace_mode_rows
    self._etf_beta_hard_block_flags_arr = np.empty(day_count, dtype=object)
    self._etf_beta_core_accumulator_symbols_arr = np.empty(day_count, dtype=object)
    self._etf_beta_tactical_satellite_symbols_arr = np.empty(day_count, dtype=object)
    self._etf_beta_limited_defense_symbols_arr = np.empty(day_count, dtype=object)
    self._etf_beta_symbol_role_map_arr = np.empty(day_count, dtype=object)
    self._etf_beta_allocation_reason_codes_arr = np.empty(day_count, dtype=object)
    for row_idx in range(day_count):
        self._etf_beta_eligible_symbols_arr[row_idx] = list(eligible_rows[row_idx])
        self._etf_beta_selected_symbols_arr[row_idx] = list(selected_rows[row_idx])
        self._etf_beta_selection_reason_codes_arr[row_idx] = dict(selection_reason_rows[row_idx])
        self._etf_beta_runtime_reason_codes_arr[row_idx] = list(runtime_reason_rows[row_idx])
        self._etf_beta_vol_target_info_arr[row_idx] = dict(vol_target_rows[row_idx])
        self._etf_beta_layering_reason_codes_arr[row_idx] = list(layering_reason_rows[row_idx])
        self._etf_beta_core_slot_selected_symbol_arr[row_idx] = core_slot_selected_rows[row_idx]
        self._etf_beta_growth_slot_selected_symbol_arr[row_idx] = growth_slot_selected_rows[row_idx]
        self._etf_beta_slot_selection_reason_codes_arr[row_idx] = dict(slot_selection_reason_rows[row_idx])
        self._etf_beta_slot_under_deploy_reason_codes_arr[row_idx] = dict(slot_under_deploy_reason_rows[row_idx])
        self._etf_beta_absolute_filter_reject_reason_counts_arr[row_idx] = dict(absolute_filter_reject_reason_rows[row_idx])
        self._etf_beta_selection_chain_winner_counts_arr[row_idx] = dict(selection_chain_winner_rows[row_idx])
        self._etf_beta_selection_chain_reject_reason_counts_arr[row_idx] = dict(selection_chain_reject_reason_rows[row_idx])
        self._etf_beta_targets_arr[row_idx] = dict(targets_rows[row_idx])
        self._etf_beta_hard_block_flags_arr[row_idx] = list(hard_block_flag_rows[row_idx])
        self._etf_beta_core_accumulator_symbols_arr[row_idx] = list(core_accumulator_symbol_rows[row_idx])
        self._etf_beta_tactical_satellite_symbols_arr[row_idx] = list(tactical_satellite_symbol_rows[row_idx])
        self._etf_beta_limited_defense_symbols_arr[row_idx] = list(limited_defense_symbol_rows[row_idx])
        self._etf_beta_symbol_role_map_arr[row_idx] = dict(symbol_role_map_rows[row_idx])
        self._etf_beta_allocation_reason_codes_arr[row_idx] = list(allocation_reason_rows[row_idx])


