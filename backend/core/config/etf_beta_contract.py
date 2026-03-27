from __future__ import annotations

import json
from typing import Any

import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.core.data.cn_etf_catalog import get_catalog_entry

CN_ETF_BETA_SLEEVE_ID = "cn_etf_beta"
CN_ETF_BETA_BUDGET_SEMANTICS = "consume_governor_sleeve_budget"
CN_ETF_BETA_CORE_SYMBOLS = (
    "510300.SH",
    "510500.SH",
    "510050.SH",
    "512100.SH",
)
CN_ETF_BETA_LIMITED_DEFENSE_CANDIDATES = ("512890.SH",)
CN_ETF_BETA_RULE_FAMILY = "etf_beta_v1_control"
CN_ETF_BETA_EXPOSURE_POLICY_FAMILY = "default"
CN_ETF_BETA_POLICY_SCOPE = "general"
CN_ETF_BETA_LAYERING_POLICY = "none"
CN_ETF_BETA_STRATEGY_ROLE = "auxiliary_beta_sleeve"
CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE = "consume_governor_sleeve_budget"
CN_ETF_BETA_LOCAL_POLICY_MODE = "legacy_beta_selection"
CN_ETF_BETA_CONTROLLED_ACCUMULATION_MODE = "none"
CN_ETF_BETA_REBALANCE_FREQUENCY = "weekly"
CN_ETF_BETA_ABSOLUTE_FILTER_MODE = "ma120"
CN_ETF_BETA_FALLBACK_MODE = "none"
CN_ETF_BETA_ABSOLUTE_FILTER_PROFILE: str | None = None
CN_ETF_BETA_CANDIDATE_POOL_PROFILE: str | None = None
CN_ETF_BETA_SELECTION_CHAIN_PROFILE: str | None = None
CN_ETF_BETA_RS_FAST_WINDOW = 60
CN_ETF_BETA_RS_MID_WINDOW = 0
CN_ETF_BETA_RS_SLOW_WINDOW = 120
CN_ETF_BETA_RS_FAST_WEIGHT = 0.4
CN_ETF_BETA_RS_MID_WEIGHT = 0.0
CN_ETF_BETA_RS_SLOW_WEIGHT = 0.6
CN_ETF_BETA_VOL_TARGET_WINDOW = 20
CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET = 0.18
CN_ETF_BETA_VOL_TARGET_MIN_SCALE = 0.35
CN_ETF_BETA_VOL_TARGET_MAX_SCALE = 1.0
CN_ETF_FORMAL_ALIGNMENT_REFERENCE = "A股ETF子系统策略思路md"
CN_ETF_FORMAL_ALIGNMENT_CLASSIFICATIONS = (
    "formal_mainline",
    "research_only",
    "do_not_promote",
)
CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS = CN_ETF_BETA_CORE_SYMBOLS
CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES = CN_ETF_BETA_LIMITED_DEFENSE_CANDIDATES
CN_ETF_FORMAL_PHASE1_EXCLUDED_SYMBOLS = (
    "518880.SH",
    "511010.SH",
    "588000.SH",
    "159915.SZ",
)

_CANONICAL_STATE_5_ALIASES = {
    "BULL": "BULL",
    "BULL_MAIN": "BULL",
    "TRANS_UP": "TRANS_UP",
    "TURN_STRONG": "TRANS_UP",
    "LIGHT": "LIGHT",
    "LIGHT_TREND": "LIGHT",
    "TRANS_DOWN": "TRANS_DOWN",
    "TURN_WEAK": "TRANS_DOWN",
    "RISK_OFF": "RISK_OFF",
    "BEAR": "RISK_OFF",
    "DEFENSIVE": "RISK_OFF",
}

_BROAD_BASED_MAINLINE_ALLOWED_BUCKETS = {
    "broad_equity",
    "large_cap_equity",
    "mid_cap_equity",
    "small_cap_equity",
    "small_cap_equity_standard",
    "growth_equity",
    "technology_growth",
    "dividend_low_vol",
    "dividend_standard",
}
_BROAD_BASED_MAINLINE_FALLBACK_BUCKETS = {"bond"}
_ABSOLUTE_FILTER_PROFILES = {"ma200_ret12", "ma200_only", "ma150_ret12"}
_CANDIDATE_POOL_PROFILES = {"a0_proxy_pool", "proxy_expanded_pool", "standard_overlap_pool"}
_SELECTION_CHAIN_PROFILES = {"global_top2_12_6_3", "global_top2_6_3_1", "core_growth_slot"}
_FORMAL_PHASE1_SYMBOL_SCOPE = set(CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS) | set(CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES)
_FORMAL_SIGNAL_SEMANTICS_ALLOWED = {
    "research_rule_family": {"etf_beta_v1_control"},
    "strategy_role": {"auxiliary_beta_sleeve"},
    "local_policy_mode": {"legacy_beta_selection"},
}
_FORMAL_GOVERNOR_BOUNDARY_ALLOWED = {
    "governor_boundary_mode": {"consume_governor_sleeve_budget"},
    "source_entry_type": {"cn_etf_research_entry"},
}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def canonical_state_5(value: Any) -> str:
    text = _normalize_text(value).upper()
    return _CANONICAL_STATE_5_ALIASES.get(text, text)


def _normalize_symbol_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in values:
        text = _normalize_text(item).upper()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _normalize_symbol_map(values: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(values, dict):
        return out
    for key, value in values.items():
        symbol = _normalize_text(key).upper()
        text = _normalize_text(value)
        if not symbol or not text:
            continue
        out[symbol] = text
    return out


def _normalize_symbol_pairs(values: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(values, dict):
        return out
    for key, value in values.items():
        symbol = _normalize_text(key).upper()
        replacement = _normalize_symbol_list([value])
        if not symbol or not replacement:
            continue
        out[symbol] = replacement[0]
    return out


def _normalize_choice(value: Any, *, default: str, allowed: set[str]) -> str:
    text = _normalize_text(value).lower()
    if text in allowed:
        return text
    return default


def _normalize_optional_choice(value: Any, *, allowed: set[str]) -> str | None:
    text = _normalize_text(value).lower()
    if not text:
        return None
    if text in allowed:
        return text
    return None


def _normalize_reason_list(values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in list(values or ()):
        text = _normalize_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _append_reason(reasons: list[str], reason: str) -> None:
    text = _normalize_text(reason)
    if text and text not in reasons:
        reasons.append(text)


def _collect_formal_scope_violations(
    values: Any,
    *,
    allowed: set[str],
    excluded: set[str],
    field_name: str,
    reasons: list[str],
    evidence: dict[str, Any],
) -> None:
    symbols = _normalize_symbol_list(values)
    if not symbols:
        return
    excluded_used = [symbol for symbol in symbols if symbol in excluded]
    extra_scope = [symbol for symbol in symbols if symbol not in allowed and symbol not in excluded]
    if excluded_used:
        evidence[f"{field_name}_excluded_symbols"] = excluded_used
        for symbol in excluded_used:
            _append_reason(reasons, f"FORMAL_EXCLUDED_ASSET_USED::{field_name}::{symbol}")
    if extra_scope:
        evidence[f"{field_name}_extra_scope_symbols"] = extra_scope
        for symbol in extra_scope:
            _append_reason(reasons, f"RESEARCH_SCOPE_ASSET_USED::{field_name}::{symbol}")


def _normalize_controlled_accumulation_mode(value: Any) -> str:
    return _normalize_choice(
        value,
        default=CN_ETF_BETA_CONTROLLED_ACCUMULATION_MODE,
        allowed={"none", "light_only", "light_and_controlled_trans_down"},
    )


def _layering_policy_from_controlled_accumulation_mode(mode: Any) -> str:
    text = _normalize_controlled_accumulation_mode(mode)
    if text == "light_only":
        return "light_accumulate"
    if text == "light_and_controlled_trans_down":
        return "light_trans_down_accumulate"
    return "none"


def _controlled_accumulation_mode_from_layering_policy(policy: Any) -> str:
    text = _normalize_choice(
        policy,
        default=CN_ETF_BETA_LAYERING_POLICY,
        allowed={"none", "light_accumulate", "light_trans_down_accumulate"},
    )
    if text == "light_accumulate":
        return "light_only"
    if text == "light_trans_down_accumulate":
        return "light_and_controlled_trans_down"
    return "none"


def _invalid_broad_based_mainline_symbols(
    symbols: Any,
    *,
    allow_fallback_buckets: bool = False,
) -> list[str]:
    invalid: list[str] = []
    for symbol in _normalize_symbol_list(symbols):
        entry = get_catalog_entry(symbol)
        if entry is None:
            invalid.append(symbol)
            continue
        bucket = str(entry.exposure_bucket or "").strip().lower()
        if bucket in _BROAD_BASED_MAINLINE_ALLOWED_BUCKETS:
            continue
        if allow_fallback_buckets and bucket in _BROAD_BASED_MAINLINE_FALLBACK_BUCKETS:
            continue
        invalid.append(symbol)
    return invalid


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        out = float(value)
    except Exception:
        return None
    if out != out:
        return None
    return float(out)


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return int(default)


def _normalize_state_float_map(values: Any) -> dict[str, float]:
    out: dict[str, float] = {}
    if not isinstance(values, dict):
        return out
    for key, raw in values.items():
        state_5 = canonical_state_5(key) if _normalize_text(key) else ""
        value = _safe_float(raw)
        if not state_5 or value is None:
            continue
        out[state_5] = float(value)
    return out


def _normalize_state_int_map(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    if not isinstance(values, dict):
        return out
    for key, raw in values.items():
        state_5 = canonical_state_5(key) if _normalize_text(key) else ""
        value = _safe_int(raw, default=0)
        if not state_5 or int(value) < 0:
            continue
        out[state_5] = int(value)
    return out


def _normalize_state_bool_map(values: Any) -> dict[str, bool]:
    out: dict[str, bool] = {}
    if not isinstance(values, dict):
        return out
    for key, raw in values.items():
        state_5 = canonical_state_5(key) if _normalize_text(key) else ""
        if not state_5:
            continue
        out[state_5] = bool(raw)
    return out


def _derive_layering_semantics(
    *,
    exposure_policy_family: str,
    layering_policy: str,
    effective_state_5: str,
    target_exposure: float | None,
) -> tuple[str | None, bool, list[str]]:
    state_5 = canonical_state_5(effective_state_5)
    if exposure_policy_family not in {"broad_based_governed_v1", "broad_based_standalone_mainline_v1"}:
        return None, False, []
    if state_5 == "RISK_OFF" or target_exposure is None or float(target_exposure) <= 1e-12:
        return "RISK_OFF_ZERO" if state_5 == "RISK_OFF" else "NO_LAYERING", False, []
    if state_5 in {"BULL", "TRANS_UP"}:
        return "RISK_ON_FULL", False, []
    if state_5 == "LIGHT" and layering_policy in {"light_accumulate", "light_trans_down_accumulate"}:
        return "LIGHT_ACCUMULATE", True, ["ETF_BETA_LAYERING_LIGHT_ACCUMULATE"]
    if state_5 == "TRANS_DOWN" and layering_policy == "light_trans_down_accumulate":
        return "CONTROLLED_TRANS_DOWN", True, ["ETF_BETA_LAYERING_CONTROLLED_TRANS_DOWN"]
    return "NO_LAYERING", False, []


def _phase1_scope_reason_codes(symbols: list[str], *, reason_code: str) -> dict[str, list[str]]:
    return {
        symbol: [reason_code, "IN_RESEARCH_ENTRY", "PHASE1_SCOPE_GATED"]
        for symbol in symbols
    }


def build_default_etf_beta_contract(*, enabled: bool) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "sleeve_id": CN_ETF_BETA_SLEEVE_ID,
        "system_role": "market_beta_sleeve",
        "strategy_role": CN_ETF_BETA_STRATEGY_ROLE,
        "governor_boundary_mode": CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE,
        "local_policy_mode": CN_ETF_BETA_LOCAL_POLICY_MODE,
        "exposure_policy_family": CN_ETF_BETA_EXPOSURE_POLICY_FAMILY,
        "policy_scope": CN_ETF_BETA_POLICY_SCOPE,
        "broad_based_only": None,
        "layering_policy": CN_ETF_BETA_LAYERING_POLICY,
        "controlled_accumulation_mode": CN_ETF_BETA_CONTROLLED_ACCUMULATION_MODE,
        "template_id": None,
        "template_asset_pool_version": None,
        "template_role_map": None,
        "template_proxy_map": None,
        "template_target_formal_symbols": None,
        "proxy_replacement_mode": None,
        "formal_replacement_pairs": None,
        "core_slot_symbols": None,
        "growth_slot_symbols": None,
        "growth_seat_symbol": None,
        "budget_semantics": CN_ETF_BETA_BUDGET_SEMANTICS,
        "total_budget_owner": "global_portfolio_governor",
        "source_entry_type": "cn_etf_research_entry",
        "phase1_scope_mode": "core_beta_plus_limited_defense",
        "core_beta_symbols": list(CN_ETF_BETA_CORE_SYMBOLS),
        "limited_defense_candidates": list(CN_ETF_BETA_LIMITED_DEFENSE_CANDIDATES),
        "research_rule_family": CN_ETF_BETA_RULE_FAMILY,
        "absolute_filter_profile": CN_ETF_BETA_ABSOLUTE_FILTER_PROFILE,
        "candidate_pool_profile": CN_ETF_BETA_CANDIDATE_POOL_PROFILE,
        "selection_chain_profile": CN_ETF_BETA_SELECTION_CHAIN_PROFILE,
        "rebalance_frequency": CN_ETF_BETA_REBALANCE_FREQUENCY,
        "absolute_filter_mode": CN_ETF_BETA_ABSOLUTE_FILTER_MODE,
        "fallback_mode": CN_ETF_BETA_FALLBACK_MODE,
        "fallback_symbol": None,
        "relative_strength_fast_window": CN_ETF_BETA_RS_FAST_WINDOW,
        "relative_strength_mid_window": None,
        "relative_strength_slow_window": CN_ETF_BETA_RS_SLOW_WINDOW,
        "relative_strength_fast_weight": CN_ETF_BETA_RS_FAST_WEIGHT,
        "relative_strength_mid_weight": None,
        "relative_strength_slow_weight": CN_ETF_BETA_RS_SLOW_WEIGHT,
        "max_selected_symbols": None,
        "target_exposure": None,
        "min_deployable_exposure": None,
        "target_exposure_by_state_5": None,
        "min_deployable_exposure_by_state_5": None,
        "fallback_allowed": None,
        "target_selected_count_by_state_5": None,
        "fallback_allowed_by_state_5": None,
        "vol_target_window": CN_ETF_BETA_VOL_TARGET_WINDOW,
        "vol_target_annualized_target": CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET,
        "vol_target_min_scale": CN_ETF_BETA_VOL_TARGET_MIN_SCALE,
        "vol_target_max_scale": CN_ETF_BETA_VOL_TARGET_MAX_SCALE,
    }


def normalize_etf_beta_contract(raw: dict[str, Any] | None) -> dict[str, Any]:
    etf_beta = dict(raw or {})
    etf_beta["sleeve_id"] = _normalize_text(etf_beta.get("sleeve_id")) or CN_ETF_BETA_SLEEVE_ID
    etf_beta["system_role"] = _normalize_text(etf_beta.get("system_role")) or "market_beta_sleeve"
    etf_beta["strategy_role"] = _normalize_choice(
        etf_beta.get("strategy_role"),
        default=CN_ETF_BETA_STRATEGY_ROLE,
        allowed={"auxiliary_beta_sleeve", "governed_broad_based_standalone_mainline"},
    )
    etf_beta["governor_boundary_mode"] = _normalize_choice(
        etf_beta.get("governor_boundary_mode"),
        default=CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE,
        allowed={"consume_governor_sleeve_budget", "consume_governor_state_and_budget"},
    )
    etf_beta["local_policy_mode"] = _normalize_choice(
        etf_beta.get("local_policy_mode"),
        default=CN_ETF_BETA_LOCAL_POLICY_MODE,
        allowed={"legacy_beta_selection", "broad_based_rotation_mainline"},
    )
    etf_beta["exposure_policy_family"] = _normalize_choice(
        etf_beta.get("exposure_policy_family"),
        default=CN_ETF_BETA_EXPOSURE_POLICY_FAMILY,
        allowed={"default", "broad_based_governed_v1", "broad_based_standalone_mainline_v1"},
    )
    etf_beta["policy_scope"] = _normalize_choice(
        etf_beta.get("policy_scope"),
        default=CN_ETF_BETA_POLICY_SCOPE,
        allowed={"general", "broad_based_only"},
    )
    if etf_beta.get("broad_based_only") is None:
        etf_beta["broad_based_only"] = etf_beta["policy_scope"] == "broad_based_only"
    else:
        etf_beta["broad_based_only"] = bool(etf_beta.get("broad_based_only"))
    etf_beta["layering_policy"] = _normalize_choice(
        etf_beta.get("layering_policy"),
        default=CN_ETF_BETA_LAYERING_POLICY,
        allowed={"none", "light_accumulate", "light_trans_down_accumulate"},
    )
    controlled_accumulation_mode = _normalize_controlled_accumulation_mode(etf_beta.get("controlled_accumulation_mode"))
    if _normalize_text(etf_beta.get("controlled_accumulation_mode")):
        etf_beta["layering_policy"] = _layering_policy_from_controlled_accumulation_mode(controlled_accumulation_mode)
    else:
        controlled_accumulation_mode = _controlled_accumulation_mode_from_layering_policy(etf_beta["layering_policy"])
    etf_beta["controlled_accumulation_mode"] = controlled_accumulation_mode
    etf_beta["template_id"] = _normalize_text(etf_beta.get("template_id")) or None
    etf_beta["template_asset_pool_version"] = _normalize_text(etf_beta.get("template_asset_pool_version")) or None
    etf_beta["template_role_map"] = _normalize_symbol_map(etf_beta.get("template_role_map"))
    etf_beta["template_proxy_map"] = _normalize_symbol_map(etf_beta.get("template_proxy_map"))
    etf_beta["template_target_formal_symbols"] = _normalize_symbol_list(etf_beta.get("template_target_formal_symbols"))
    etf_beta["proxy_replacement_mode"] = _normalize_choice(
        etf_beta.get("proxy_replacement_mode"),
        default="none",
        allowed={"none", "csi1000_proxy_only", "dividend_proxy_only", "full_standard_swap"},
    )
    etf_beta["formal_replacement_pairs"] = _normalize_symbol_pairs(etf_beta.get("formal_replacement_pairs"))
    etf_beta["core_slot_symbols"] = _normalize_symbol_list(etf_beta.get("core_slot_symbols"))
    etf_beta["growth_slot_symbols"] = _normalize_symbol_list(etf_beta.get("growth_slot_symbols"))
    etf_beta["growth_seat_symbol"] = (
        _normalize_symbol_list([etf_beta.get("growth_seat_symbol")])[0]
        if _normalize_symbol_list([etf_beta.get("growth_seat_symbol")])
        else None
    )
    etf_beta["budget_semantics"] = _normalize_text(etf_beta.get("budget_semantics")) or CN_ETF_BETA_BUDGET_SEMANTICS
    etf_beta["total_budget_owner"] = _normalize_text(etf_beta.get("total_budget_owner")) or "global_portfolio_governor"
    default_source_entry_type = (
        "cn_etf_broad_based_standalone_mainline_entry"
        if etf_beta["strategy_role"] == "governed_broad_based_standalone_mainline"
        else "cn_etf_research_entry"
    )
    etf_beta["source_entry_type"] = _normalize_text(etf_beta.get("source_entry_type")) or default_source_entry_type
    etf_beta["phase1_scope_mode"] = _normalize_text(etf_beta.get("phase1_scope_mode")) or "core_beta_plus_limited_defense"
    etf_beta["core_beta_symbols"] = _normalize_symbol_list(etf_beta.get("core_beta_symbols"))
    etf_beta["limited_defense_candidates"] = _normalize_symbol_list(etf_beta.get("limited_defense_candidates"))
    etf_beta["research_rule_family"] = _normalize_choice(
        etf_beta.get("research_rule_family"),
        default=CN_ETF_BETA_RULE_FAMILY,
        allowed={
            "etf_beta_v1_control",
            "dual_momentum_basic",
            "dual_momentum_vol_target",
            "broad_based_rotation_template_a",
            "broad_based_rotation_template_a0_core_satellite_v2",
        },
    )
    etf_beta["absolute_filter_profile"] = _normalize_optional_choice(
        etf_beta.get("absolute_filter_profile"),
        allowed=_ABSOLUTE_FILTER_PROFILES,
    )
    etf_beta["candidate_pool_profile"] = _normalize_optional_choice(
        etf_beta.get("candidate_pool_profile"),
        allowed=_CANDIDATE_POOL_PROFILES,
    )
    etf_beta["selection_chain_profile"] = _normalize_optional_choice(
        etf_beta.get("selection_chain_profile"),
        allowed=_SELECTION_CHAIN_PROFILES,
    )
    etf_beta["rebalance_frequency"] = _normalize_choice(
        etf_beta.get("rebalance_frequency"),
        default=CN_ETF_BETA_REBALANCE_FREQUENCY,
        allowed={"weekly", "biweekly", "monthly"},
    )
    etf_beta["absolute_filter_mode"] = _normalize_choice(
        etf_beta.get("absolute_filter_mode"),
        default=CN_ETF_BETA_ABSOLUTE_FILTER_MODE,
        allowed={"ma120", "positive_12m", "ma200_and_positive_12m", "ma200_only", "ma150_and_positive_12m"},
    )
    etf_beta["fallback_mode"] = _normalize_choice(
        etf_beta.get("fallback_mode"),
        default=CN_ETF_BETA_FALLBACK_MODE,
        allowed={"none", "cash", "single_symbol"},
    )
    etf_beta["fallback_symbol"] = (
        _normalize_symbol_list([etf_beta.get("fallback_symbol")])[0]
        if _normalize_symbol_list([etf_beta.get("fallback_symbol")])
        else None
    )
    etf_beta["relative_strength_fast_window"] = max(
        2,
        _safe_int(etf_beta.get("relative_strength_fast_window"), default=CN_ETF_BETA_RS_FAST_WINDOW),
    )
    mid_window = _safe_int(etf_beta.get("relative_strength_mid_window"), default=CN_ETF_BETA_RS_MID_WINDOW)
    etf_beta["relative_strength_mid_window"] = max(2, mid_window) if int(mid_window or 0) >= 2 else None
    etf_beta["relative_strength_slow_window"] = max(
        2,
        _safe_int(etf_beta.get("relative_strength_slow_window"), default=CN_ETF_BETA_RS_SLOW_WINDOW),
    )
    fast_weight = _safe_float(etf_beta.get("relative_strength_fast_weight"))
    mid_weight = _safe_float(etf_beta.get("relative_strength_mid_weight"))
    slow_weight = _safe_float(etf_beta.get("relative_strength_slow_weight"))
    fast_weight = CN_ETF_BETA_RS_FAST_WEIGHT if fast_weight is None else max(0.0, fast_weight)
    mid_weight = CN_ETF_BETA_RS_MID_WEIGHT if mid_weight is None else max(0.0, mid_weight)
    slow_weight = CN_ETF_BETA_RS_SLOW_WEIGHT if slow_weight is None else max(0.0, slow_weight)
    if etf_beta["relative_strength_mid_window"] is None:
        mid_weight = 0.0
    if fast_weight + mid_weight + slow_weight <= 1e-12:
        fast_weight = CN_ETF_BETA_RS_FAST_WEIGHT
        mid_weight = CN_ETF_BETA_RS_MID_WEIGHT
        slow_weight = CN_ETF_BETA_RS_SLOW_WEIGHT
    etf_beta["relative_strength_fast_weight"] = fast_weight
    etf_beta["relative_strength_mid_weight"] = mid_weight
    etf_beta["relative_strength_slow_weight"] = slow_weight
    max_selected_symbols = _safe_int(etf_beta.get("max_selected_symbols"), default=0)
    etf_beta["max_selected_symbols"] = max_selected_symbols if max_selected_symbols > 0 else None
    etf_beta["target_exposure"] = _safe_float(etf_beta.get("target_exposure"))
    etf_beta["min_deployable_exposure"] = _safe_float(etf_beta.get("min_deployable_exposure"))
    etf_beta["target_exposure_by_state_5"] = _normalize_state_float_map(etf_beta.get("target_exposure_by_state_5"))
    etf_beta["min_deployable_exposure_by_state_5"] = _normalize_state_float_map(etf_beta.get("min_deployable_exposure_by_state_5"))
    etf_beta["fallback_allowed"] = bool(etf_beta.get("fallback_allowed")) if etf_beta.get("fallback_allowed") is not None else None
    etf_beta["target_selected_count_by_state_5"] = _normalize_state_int_map(etf_beta.get("target_selected_count_by_state_5"))
    etf_beta["fallback_allowed_by_state_5"] = _normalize_state_bool_map(etf_beta.get("fallback_allowed_by_state_5"))
    vol_target_window = _safe_int(etf_beta.get("vol_target_window"), default=CN_ETF_BETA_VOL_TARGET_WINDOW)
    etf_beta["vol_target_window"] = max(5, int(vol_target_window or CN_ETF_BETA_VOL_TARGET_WINDOW))
    vol_target_annualized_target = _safe_float(etf_beta.get("vol_target_annualized_target"))
    etf_beta["vol_target_annualized_target"] = (
        CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET
        if vol_target_annualized_target is None or float(vol_target_annualized_target) <= 0.0
        else float(vol_target_annualized_target)
    )
    vol_target_min_scale = _safe_float(etf_beta.get("vol_target_min_scale"))
    vol_target_min_scale = (
        CN_ETF_BETA_VOL_TARGET_MIN_SCALE
        if vol_target_min_scale is None
        else max(0.0, min(float(vol_target_min_scale), 1.0))
    )
    vol_target_max_scale = _safe_float(etf_beta.get("vol_target_max_scale"))
    vol_target_max_scale = (
        CN_ETF_BETA_VOL_TARGET_MAX_SCALE
        if vol_target_max_scale is None
        else max(0.0, min(float(vol_target_max_scale), 1.0))
    )
    if vol_target_min_scale > vol_target_max_scale:
        vol_target_min_scale, vol_target_max_scale = vol_target_max_scale, vol_target_min_scale
    etf_beta["vol_target_min_scale"] = vol_target_min_scale
    etf_beta["vol_target_max_scale"] = vol_target_max_scale
    if etf_beta["strategy_role"] == "governed_broad_based_standalone_mainline":
        invalid_scope_symbols = [
            *_invalid_broad_based_mainline_symbols(etf_beta.get("core_beta_symbols")),
            *_invalid_broad_based_mainline_symbols(etf_beta.get("core_slot_symbols")),
            *_invalid_broad_based_mainline_symbols(etf_beta.get("growth_slot_symbols")),
            *_invalid_broad_based_mainline_symbols(
                [etf_beta.get("growth_seat_symbol")] if etf_beta.get("growth_seat_symbol") else []
            ),
        ]
        invalid_fallback_symbols = _invalid_broad_based_mainline_symbols(
            [etf_beta.get("fallback_symbol")] if etf_beta.get("fallback_symbol") else [],
            allow_fallback_buckets=True,
        )
        invalid_scope_symbols.extend(invalid_fallback_symbols)
        if invalid_scope_symbols:
            invalid_text = ", ".join(sorted({str(symbol).upper() for symbol in invalid_scope_symbols if str(symbol).strip()}))
            raise ValueError(
                "governed broad-based standalone mainline only accepts broad-based ETF symbols"
                + (f" (invalid: {invalid_text})" if invalid_text else "")
            )
    return etf_beta


def resolve_etf_beta_exposure_semantics(
    *,
    etf_beta_contract: dict[str, Any] | None,
    effective_state_5: Any = None,
    total_exposure_cap: Any = None,
    slot_cap: Any = None,
    target_selected_count: Any = None,
    sleeve_budget_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    etf_beta = dict(etf_beta_contract or {})
    sleeve_budget = dict(sleeve_budget_snapshot or {})
    exposure_policy_family = _normalize_choice(
        etf_beta.get("exposure_policy_family"),
        default=CN_ETF_BETA_EXPOSURE_POLICY_FAMILY,
        allowed={"default", "broad_based_governed_v1", "broad_based_standalone_mainline_v1"},
    )
    strategy_role = _normalize_choice(
        etf_beta.get("strategy_role"),
        default=CN_ETF_BETA_STRATEGY_ROLE,
        allowed={"auxiliary_beta_sleeve", "governed_broad_based_standalone_mainline"},
    )
    governor_boundary_mode = _normalize_choice(
        etf_beta.get("governor_boundary_mode"),
        default=CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE,
        allowed={"consume_governor_sleeve_budget", "consume_governor_state_and_budget"},
    )
    local_policy_mode = _normalize_choice(
        etf_beta.get("local_policy_mode"),
        default=CN_ETF_BETA_LOCAL_POLICY_MODE,
        allowed={"legacy_beta_selection", "broad_based_rotation_mainline"},
    )
    policy_scope = _normalize_choice(
        etf_beta.get("policy_scope"),
        default=CN_ETF_BETA_POLICY_SCOPE,
        allowed={"general", "broad_based_only"},
    )
    broad_based_only = bool(etf_beta.get("broad_based_only")) if etf_beta.get("broad_based_only") is not None else policy_scope == "broad_based_only"
    layering_policy = _normalize_choice(
        etf_beta.get("layering_policy"),
        default=CN_ETF_BETA_LAYERING_POLICY,
        allowed={"none", "light_accumulate", "light_trans_down_accumulate"},
    )
    controlled_accumulation_mode = _normalize_controlled_accumulation_mode(
        etf_beta.get("controlled_accumulation_mode")
    )
    if _normalize_text(etf_beta.get("controlled_accumulation_mode")):
        layering_policy = _layering_policy_from_controlled_accumulation_mode(controlled_accumulation_mode)
    else:
        controlled_accumulation_mode = _controlled_accumulation_mode_from_layering_policy(layering_policy)
    effective_state_text = (
        canonical_state_5(effective_state_5)
        if _normalize_text(effective_state_5)
        else canonical_state_5(sleeve_budget.get("effective_state_5"))
        if _normalize_text(sleeve_budget.get("effective_state_5"))
        else ""
    )
    target_exposure_map = _normalize_state_float_map(etf_beta.get("target_exposure_by_state_5"))
    min_deployable_map = _normalize_state_float_map(etf_beta.get("min_deployable_exposure_by_state_5"))
    target_selected_count_map = _normalize_state_int_map(etf_beta.get("target_selected_count_by_state_5"))
    fallback_allowed_map = _normalize_state_bool_map(etf_beta.get("fallback_allowed_by_state_5"))
    target_exposure = None
    target_exposure_source = ""
    if effective_state_text and effective_state_text in target_exposure_map:
        target_exposure = float(target_exposure_map[effective_state_text])
        target_exposure_source = f"state_map::{effective_state_text}"
    else:
        fixed_target_exposure = _safe_float(etf_beta.get("target_exposure"))
        if fixed_target_exposure is not None:
            target_exposure = float(fixed_target_exposure)
            target_exposure_source = "fixed"
        else:
            budget_target_exposure = _safe_float(sleeve_budget.get("target_exposure"))
            if budget_target_exposure is not None:
                target_exposure = float(budget_target_exposure)
                target_exposure_source = "budget_snapshot"
            else:
                exposure_cap = _safe_float(total_exposure_cap)
                if exposure_cap is None:
                    exposure_cap = _safe_float(sleeve_budget.get("total_exposure_cap"))
                if exposure_cap is not None:
                    target_exposure = float(exposure_cap)
                    target_exposure_source = "slot_cap_default"
    target_selected_count_value = 0
    target_selected_count_source = ""
    if effective_state_text and effective_state_text in target_selected_count_map:
        target_selected_count_value = int(target_selected_count_map[effective_state_text])
        target_selected_count_source = f"state_map::{effective_state_text}"
    if target_selected_count_value <= 0:
        target_selected_count_value = _safe_int(target_selected_count)
        if target_selected_count_value > 0:
            target_selected_count_source = "input"
    if target_selected_count_value <= 0:
        target_selected_count_value = _safe_int(sleeve_budget.get("target_selected_count"))
        if target_selected_count_value > 0:
            target_selected_count_source = "budget_snapshot"
    if target_selected_count_value <= 0:
        target_selected_count_value = _safe_int(etf_beta.get("max_selected_symbols"))
        if target_selected_count_value > 0:
            target_selected_count_source = "max_selected_symbols"
    if target_selected_count_value <= 0:
        target_selected_count_value = _safe_int(slot_cap)
        if target_selected_count_value > 0:
            target_selected_count_source = "slot_cap_default"
    if target_selected_count_value <= 0:
        target_selected_count_value = 1
        target_selected_count_source = "fallback_default"
    min_deployable_exposure = None
    min_deployable_exposure_source = ""
    if effective_state_text and effective_state_text in min_deployable_map:
        min_deployable_exposure = float(min_deployable_map[effective_state_text])
        min_deployable_exposure_source = f"state_map::{effective_state_text}"
    else:
        fixed_min_deployable = _safe_float(etf_beta.get("min_deployable_exposure"))
        if fixed_min_deployable is not None:
            min_deployable_exposure = float(fixed_min_deployable)
            min_deployable_exposure_source = "fixed"
        else:
            budget_min_deployable = _safe_float(sleeve_budget.get("min_deployable_exposure"))
            if budget_min_deployable is not None:
                min_deployable_exposure = float(budget_min_deployable)
                min_deployable_exposure_source = "budget_snapshot"
            elif target_exposure is not None:
                min_deployable_exposure = float(target_exposure) / float(max(1, int(target_selected_count_value)))
                min_deployable_exposure_source = "derived_from_target"
    fallback_mode_text = _normalize_text(etf_beta.get("fallback_mode")).lower()
    fallback_allowed_source = ""
    if effective_state_text and effective_state_text in fallback_allowed_map:
        fallback_allowed = bool(fallback_allowed_map[effective_state_text])
        fallback_allowed_source = f"state_map::{effective_state_text}"
    elif etf_beta.get("fallback_allowed") is not None:
        fallback_allowed = bool(etf_beta.get("fallback_allowed"))
        fallback_allowed_source = "fixed"
    elif sleeve_budget.get("fallback_allowed") is not None:
        fallback_allowed = bool(sleeve_budget.get("fallback_allowed"))
        fallback_allowed_source = "budget_snapshot"
    else:
        fallback_allowed = bool(fallback_mode_text and fallback_mode_text != "none")
        fallback_allowed_source = "fallback_mode_default"
    layering_band, layering_active, layering_reason_codes = _derive_layering_semantics(
        exposure_policy_family=exposure_policy_family,
        layering_policy=layering_policy,
        effective_state_5=effective_state_text,
        target_exposure=target_exposure,
    )
    return {
        "effective_state_5": effective_state_text or None,
        "strategy_role": strategy_role,
        "governor_boundary_mode": governor_boundary_mode,
        "local_policy_mode": local_policy_mode,
        "exposure_policy_family": exposure_policy_family,
        "policy_scope": policy_scope,
        "broad_based_only": broad_based_only,
        "layering_policy": layering_policy,
        "controlled_accumulation_mode": controlled_accumulation_mode,
        "layering_band": layering_band,
        "layering_active": layering_active,
        "layering_reason_codes": list(layering_reason_codes),
        "target_exposure": target_exposure,
        "target_exposure_source": target_exposure_source or None,
        "min_deployable_exposure": min_deployable_exposure,
        "min_deployable_exposure_source": min_deployable_exposure_source or None,
        "target_selected_count": int(target_selected_count_value),
        "target_selected_count_source": target_selected_count_source or None,
        "fallback_allowed": bool(fallback_allowed),
        "fallback_allowed_source": fallback_allowed_source or None,
        "target_exposure_by_state_5": target_exposure_map,
        "min_deployable_exposure_by_state_5": min_deployable_map,
        "target_selected_count_by_state_5": target_selected_count_map,
        "fallback_allowed_by_state_5": fallback_allowed_map,
    }


def classify_etf_formal_alignment(
    *,
    input_etfs: Any,
    core_beta_symbols: Any,
    limited_defense_candidates: Any,
    fallback_mode: Any,
    fallback_symbol: Any,
    strategy_role: Any,
    governor_boundary_mode: Any,
    local_policy_mode: Any,
    source_entry_type: Any,
    research_rule_family: Any,
    absolute_filter_profile: Any,
    candidate_pool_profile: Any,
    selection_chain_profile: Any,
    controlled_accumulation_mode: Any,
    template_target_formal_symbols: Any,
    template_proxy_map: Any,
    proxy_replacement_mode: Any,
    formal_replacement_pairs: Any,
    core_slot_symbols: Any,
    growth_slot_symbols: Any,
    growth_seat_symbol: Any,
    runtime_selection_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    evidence: dict[str, Any] = {
        "reference_doc": CN_ETF_FORMAL_ALIGNMENT_REFERENCE,
        "formal_phase1_core_symbols": list(CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS),
        "formal_phase1_limited_defense_candidates": list(CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES),
        "formal_phase1_excluded_symbols": list(CN_ETF_FORMAL_PHASE1_EXCLUDED_SYMBOLS),
    }
    allowed_symbols = set(_FORMAL_PHASE1_SYMBOL_SCOPE)
    excluded_symbols = set(CN_ETF_FORMAL_PHASE1_EXCLUDED_SYMBOLS)

    _collect_formal_scope_violations(
        input_etfs,
        allowed=allowed_symbols,
        excluded=excluded_symbols,
        field_name="input_etfs",
        reasons=reasons,
        evidence=evidence,
    )
    _collect_formal_scope_violations(
        core_beta_symbols,
        allowed=set(CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS),
        excluded=excluded_symbols,
        field_name="core_beta_symbols",
        reasons=reasons,
        evidence=evidence,
    )
    _collect_formal_scope_violations(
        limited_defense_candidates,
        allowed=set(CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES),
        excluded=excluded_symbols,
        field_name="limited_defense_candidates",
        reasons=reasons,
        evidence=evidence,
    )
    _collect_formal_scope_violations(
        [fallback_symbol] if _normalize_text(fallback_symbol) else [],
        allowed=set(CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES),
        excluded=excluded_symbols,
        field_name="fallback_symbol",
        reasons=reasons,
        evidence=evidence,
    )
    _collect_formal_scope_violations(
        template_target_formal_symbols,
        allowed=allowed_symbols,
        excluded=excluded_symbols,
        field_name="template_target_formal_symbols",
        reasons=reasons,
        evidence=evidence,
    )
    _collect_formal_scope_violations(
        core_slot_symbols,
        allowed=allowed_symbols,
        excluded=excluded_symbols,
        field_name="core_slot_symbols",
        reasons=reasons,
        evidence=evidence,
    )
    _collect_formal_scope_violations(
        growth_slot_symbols,
        allowed=allowed_symbols,
        excluded=excluded_symbols,
        field_name="growth_slot_symbols",
        reasons=reasons,
        evidence=evidence,
    )
    _collect_formal_scope_violations(
        [growth_seat_symbol] if _normalize_text(growth_seat_symbol) else [],
        allowed=allowed_symbols,
        excluded=excluded_symbols,
        field_name="growth_seat_symbol",
        reasons=reasons,
        evidence=evidence,
    )

    fallback_mode_text = _normalize_choice(
        fallback_mode,
        default=CN_ETF_BETA_FALLBACK_MODE,
        allowed={"none", "cash", "single_symbol"},
    )
    if fallback_mode_text == "single_symbol":
        _append_reason(reasons, "LIMITED_DEFENSE_SCOPE_OUT_OF_SCOPE::single_symbol_fallback")
        evidence["uses_single_symbol_fallback"] = True

    for field_name, allowed_values in _FORMAL_GOVERNOR_BOUNDARY_ALLOWED.items():
        raw_value = {
            "governor_boundary_mode": governor_boundary_mode,
            "source_entry_type": source_entry_type,
        }.get(field_name)
        text = _normalize_text(raw_value)
        if text and text not in allowed_values:
            _append_reason(reasons, f"GOVERNOR_BOUNDARY_OUT_OF_SCOPE::{field_name}::{text}")
            evidence.setdefault("governor_boundary_out_of_scope", {})[field_name] = text

    for field_name, allowed_values in _FORMAL_SIGNAL_SEMANTICS_ALLOWED.items():
        raw_value = {
            "research_rule_family": research_rule_family,
            "strategy_role": strategy_role,
            "local_policy_mode": local_policy_mode,
        }.get(field_name)
        text = _normalize_text(raw_value)
        if text and text not in allowed_values:
            _append_reason(reasons, f"SIGNAL_SEMANTICS_OUT_OF_SCOPE::{field_name}::{text}")
            evidence.setdefault("signal_semantics_out_of_scope", {})[field_name] = text

    if _normalize_text(controlled_accumulation_mode) and _normalize_text(controlled_accumulation_mode).lower() != "none":
        _append_reason(reasons, f"SIGNAL_SEMANTICS_OUT_OF_SCOPE::controlled_accumulation_mode::{_normalize_text(controlled_accumulation_mode)}")
        evidence["controlled_accumulation_mode"] = _normalize_text(controlled_accumulation_mode)

    if absolute_filter_profile:
        _append_reason(reasons, f"SIGNAL_SEMANTICS_OUT_OF_SCOPE::absolute_filter_profile::{_normalize_text(absolute_filter_profile)}")
    if candidate_pool_profile:
        _append_reason(reasons, f"SIGNAL_SEMANTICS_OUT_OF_SCOPE::candidate_pool_profile::{_normalize_text(candidate_pool_profile)}")
    if selection_chain_profile:
        _append_reason(reasons, f"SIGNAL_SEMANTICS_OUT_OF_SCOPE::selection_chain_profile::{_normalize_text(selection_chain_profile)}")

    if _normalize_symbol_map(template_proxy_map):
        _append_reason(reasons, "OUTPUT_CONTRACT_OUT_OF_SCOPE::template_proxy_map")
        evidence["template_proxy_map_keys"] = sorted(_normalize_symbol_map(template_proxy_map).keys())
    if _normalize_text(proxy_replacement_mode) and _normalize_text(proxy_replacement_mode).lower() != "none":
        _append_reason(reasons, f"OUTPUT_CONTRACT_OUT_OF_SCOPE::proxy_replacement_mode::{_normalize_text(proxy_replacement_mode)}")
    if _normalize_symbol_pairs(formal_replacement_pairs):
        _append_reason(reasons, "OUTPUT_CONTRACT_OUT_OF_SCOPE::formal_replacement_pairs")
        evidence["formal_replacement_pairs"] = _normalize_symbol_pairs(formal_replacement_pairs)

    runtime_selection_obj = dict(runtime_selection_summary or {})
    if _normalize_text(runtime_selection_obj.get("core_slot_selected_symbol")):
        _append_reason(reasons, "OUTPUT_CONTRACT_OUT_OF_SCOPE::core_slot_selected_symbol")
    if _normalize_text(runtime_selection_obj.get("growth_slot_selected_symbol")):
        _append_reason(reasons, "OUTPUT_CONTRACT_OUT_OF_SCOPE::growth_slot_selected_symbol")
    if dict(runtime_selection_obj.get("slot_selection_reason_codes") or {}):
        _append_reason(reasons, "OUTPUT_CONTRACT_OUT_OF_SCOPE::slot_selection_reason_codes")
    if dict(runtime_selection_obj.get("slot_under_deploy_reason_codes") or {}):
        _append_reason(reasons, "OUTPUT_CONTRACT_OUT_OF_SCOPE::slot_under_deploy_reason_codes")

    classification = "formal_mainline"
    if reasons:
        classification = "research_only"
    if any(
        reason.startswith(prefix)
        for reason in reasons
        for prefix in (
            "FORMAL_EXCLUDED_ASSET_USED::",
            "LIMITED_DEFENSE_SCOPE_OUT_OF_SCOPE::",
            "SIGNAL_SEMANTICS_OUT_OF_SCOPE::",
            "OUTPUT_CONTRACT_OUT_OF_SCOPE::",
            "GOVERNOR_BOUNDARY_OUT_OF_SCOPE::",
        )
    ):
        classification = "do_not_promote"

    return {
        "classification": classification,
        "formal_mainline_compatible": classification == "formal_mainline",
        "reason_codes": reasons,
        "evidence": sanitize_json(evidence),
    }


def build_etf_beta_phase1_summary(
    *,
    governed_contract: dict[str, Any] | None,
    universe_meta: dict[str, Any] | None,
    governor_snapshot: dict[str, Any] | None = None,
    runtime_selection_summary: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    governed_obj = dict(governed_contract or {})
    etf_beta = dict(governed_obj.get("etf_beta") or {})
    if not bool(etf_beta.get("enabled")):
        return None

    universe_obj = dict(universe_meta or {})
    input_etfs = _normalize_symbol_list(universe_obj.get("etf_symbols") or [])
    if not input_etfs:
        return None

    core_beta_symbols = _normalize_symbol_list(etf_beta.get("core_beta_symbols"))
    limited_defense_candidates = _normalize_symbol_list(etf_beta.get("limited_defense_candidates"))
    fallback_mode = _normalize_choice(
        etf_beta.get("fallback_mode"),
        default=CN_ETF_BETA_FALLBACK_MODE,
        allowed={"none", "cash", "single_symbol"},
    )
    fallback_symbol = (
        _normalize_symbol_list([etf_beta.get("fallback_symbol")])[0]
        if _normalize_symbol_list([etf_beta.get("fallback_symbol")])
        else None
    )
    research_rule_family = _normalize_choice(
        etf_beta.get("research_rule_family"),
        default=CN_ETF_BETA_RULE_FAMILY,
        allowed={
            "etf_beta_v1_control",
            "dual_momentum_basic",
            "dual_momentum_vol_target",
            "broad_based_rotation_template_a",
            "broad_based_rotation_template_a0_core_satellite_v2",
        },
    )
    strategy_role = _normalize_choice(
        etf_beta.get("strategy_role"),
        default=CN_ETF_BETA_STRATEGY_ROLE,
        allowed={"auxiliary_beta_sleeve", "governed_broad_based_standalone_mainline"},
    )
    governor_boundary_mode = _normalize_choice(
        etf_beta.get("governor_boundary_mode"),
        default=CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE,
        allowed={"consume_governor_sleeve_budget", "consume_governor_state_and_budget"},
    )
    local_policy_mode = _normalize_choice(
        etf_beta.get("local_policy_mode"),
        default=CN_ETF_BETA_LOCAL_POLICY_MODE,
        allowed={"legacy_beta_selection", "broad_based_rotation_mainline"},
    )
    proxy_replacement_mode = _normalize_choice(
        etf_beta.get("proxy_replacement_mode"),
        default="none",
        allowed={"none", "csi1000_proxy_only", "dividend_proxy_only", "full_standard_swap"},
    )
    formal_replacement_pairs = _normalize_symbol_pairs(etf_beta.get("formal_replacement_pairs"))
    core_slot_symbols = _normalize_symbol_list(etf_beta.get("core_slot_symbols"))
    growth_slot_symbols = _normalize_symbol_list(etf_beta.get("growth_slot_symbols"))
    rebalance_frequency = _normalize_choice(
        etf_beta.get("rebalance_frequency"),
        default=CN_ETF_BETA_REBALANCE_FREQUENCY,
        allowed={"weekly", "biweekly", "monthly"},
    )
    absolute_filter_profile = _normalize_optional_choice(
        etf_beta.get("absolute_filter_profile"),
        allowed=_ABSOLUTE_FILTER_PROFILES,
    )
    candidate_pool_profile = _normalize_optional_choice(
        etf_beta.get("candidate_pool_profile"),
        allowed=_CANDIDATE_POOL_PROFILES,
    )
    selection_chain_profile = _normalize_optional_choice(
        etf_beta.get("selection_chain_profile"),
        allowed=_SELECTION_CHAIN_PROFILES,
    )
    absolute_filter_mode = _normalize_choice(
        etf_beta.get("absolute_filter_mode"),
        default=CN_ETF_BETA_ABSOLUTE_FILTER_MODE,
        allowed={"ma120", "positive_12m", "ma200_and_positive_12m", "ma200_only", "ma150_and_positive_12m"},
    )
    relative_strength_fast_window = _safe_int(etf_beta.get("relative_strength_fast_window"), default=CN_ETF_BETA_RS_FAST_WINDOW)
    relative_strength_mid_window = _safe_int(etf_beta.get("relative_strength_mid_window"), default=CN_ETF_BETA_RS_MID_WINDOW) or None
    relative_strength_slow_window = _safe_int(etf_beta.get("relative_strength_slow_window"), default=CN_ETF_BETA_RS_SLOW_WINDOW)
    relative_strength_fast_weight = _safe_float(etf_beta.get("relative_strength_fast_weight"))
    relative_strength_mid_weight = _safe_float(etf_beta.get("relative_strength_mid_weight"))
    relative_strength_slow_weight = _safe_float(etf_beta.get("relative_strength_slow_weight"))
    max_selected_symbols = _safe_int(etf_beta.get("max_selected_symbols"), default=0) or None
    vol_target_window = max(5, int(_safe_int(etf_beta.get("vol_target_window"), default=CN_ETF_BETA_VOL_TARGET_WINDOW) or CN_ETF_BETA_VOL_TARGET_WINDOW))
    vol_target_annualized_target = _safe_float(etf_beta.get("vol_target_annualized_target"))
    vol_target_annualized_target = (
        CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET
        if vol_target_annualized_target is None or float(vol_target_annualized_target) <= 0.0
        else float(vol_target_annualized_target)
    )
    vol_target_min_scale = _safe_float(etf_beta.get("vol_target_min_scale"))
    vol_target_min_scale = (
        CN_ETF_BETA_VOL_TARGET_MIN_SCALE
        if vol_target_min_scale is None
        else max(0.0, min(float(vol_target_min_scale), 1.0))
    )
    vol_target_max_scale = _safe_float(etf_beta.get("vol_target_max_scale"))
    vol_target_max_scale = (
        CN_ETF_BETA_VOL_TARGET_MAX_SCALE
        if vol_target_max_scale is None
        else max(0.0, min(float(vol_target_max_scale), 1.0))
    )
    if vol_target_min_scale > vol_target_max_scale:
        vol_target_min_scale, vol_target_max_scale = vol_target_max_scale, vol_target_min_scale
    core_beta_scope = set(core_beta_symbols)
    limited_defense_scope = set(limited_defense_candidates)
    fallback_scope = {fallback_symbol} if fallback_mode == "single_symbol" and fallback_symbol else set()
    formal_scope = core_beta_scope | limited_defense_scope | fallback_scope
    eligible_core_beta_etfs = [symbol for symbol in input_etfs if symbol in core_beta_scope]
    eligible_limited_defense_etfs = [symbol for symbol in input_etfs if symbol in limited_defense_scope]
    eligible_fallback_etfs = [symbol for symbol in input_etfs if symbol in fallback_scope]
    selected_etfs = [*eligible_core_beta_etfs, *eligible_limited_defense_etfs]
    eligible_etfs = list(selected_etfs)
    out_of_scope_etfs = [
        symbol
        for symbol in input_etfs
        if symbol not in core_beta_scope and symbol not in limited_defense_scope
    ]
    selection_reason_codes = {
        **_phase1_scope_reason_codes(eligible_core_beta_etfs, reason_code="FORMAL_CORE_BETA"),
        **_phase1_scope_reason_codes(eligible_limited_defense_etfs, reason_code="LIMITED_DEFENSE_CANDIDATE"),
        **_phase1_scope_reason_codes(eligible_fallback_etfs, reason_code="FALLBACK_SYMBOL"),
    }
    out_of_scope_reason_codes = {
        symbol: ["OUT_OF_PHASE1_FORMAL_SCOPE", "RESEARCH_ENTRY_ONLY"]
        for symbol in out_of_scope_etfs
    }
    selection_scope = "phase1_formal_sleeve_universe"
    runtime_selection_obj = dict(runtime_selection_summary or {})
    runtime_eligible_etfs = _normalize_symbol_list(runtime_selection_obj.get("eligible_etfs"))
    runtime_selected_etfs = _normalize_symbol_list(runtime_selection_obj.get("selected_etfs"))
    runtime_reason_codes = [text for text in (_normalize_text(item) for item in list(runtime_selection_obj.get("runtime_reason_codes") or ())) if text]
    target_selected_count = _safe_int(runtime_selection_obj.get("selected_cap"), default=0) or None
    runtime_under_deploy_reason_codes = _normalize_reason_list(runtime_selection_obj.get("under_deploy_reason_codes"))
    runtime_selection_reason_codes = {
        str(symbol).strip().upper(): [str(code).strip() for code in list(codes or ()) if str(code).strip()]
        for symbol, codes in dict(runtime_selection_obj.get("selection_reason_codes") or {}).items()
        if str(symbol).strip()
    }
    core_slot_selected_symbol = (
        _normalize_symbol_list([runtime_selection_obj.get("core_slot_selected_symbol")])[0]
        if _normalize_symbol_list([runtime_selection_obj.get("core_slot_selected_symbol")])
        else None
    )
    growth_slot_selected_symbol = (
        _normalize_symbol_list([runtime_selection_obj.get("growth_slot_selected_symbol")])[0]
        if _normalize_symbol_list([runtime_selection_obj.get("growth_slot_selected_symbol")])
        else None
    )
    slot_selection_reason_codes = {
        str(slot).strip(): [str(code).strip() for code in list(codes or ()) if str(code).strip()]
        for slot, codes in dict(runtime_selection_obj.get("slot_selection_reason_codes") or {}).items()
        if str(slot).strip()
    }
    slot_under_deploy_reason_codes = {
        str(slot).strip(): [str(code).strip() for code in list(codes or ()) if str(code).strip()]
        for slot, codes in dict(runtime_selection_obj.get("slot_under_deploy_reason_codes") or {}).items()
        if str(slot).strip()
    }
    core_slot_target_exposure = _safe_float(runtime_selection_obj.get("core_slot_target_exposure"))
    growth_slot_target_exposure = _safe_float(runtime_selection_obj.get("growth_slot_target_exposure"))
    core_slot_target_actual_exposure = _safe_float(runtime_selection_obj.get("core_slot_target_actual_exposure"))
    growth_slot_target_actual_exposure = _safe_float(runtime_selection_obj.get("growth_slot_target_actual_exposure"))
    if runtime_selection_obj:
        selection_scope = "phase1_runtime_selection"
        eligible_etfs = [symbol for symbol in runtime_eligible_etfs if symbol in formal_scope]
        selected_etfs = [symbol for symbol in runtime_selected_etfs if symbol in formal_scope]
        if runtime_selection_reason_codes:
            selection_reason_codes = {
                symbol: list(runtime_selection_reason_codes.get(symbol) or selection_reason_codes.get(symbol) or [])
                for symbol in selected_etfs
            }
    runtime_vol_target = {
        "active": bool(runtime_selection_obj.get("vol_target_active", False)),
        "window": _safe_int(runtime_selection_obj.get("vol_target_window"), default=vol_target_window),
        "annualized_target": _safe_float(runtime_selection_obj.get("vol_target_annualized_target")),
        "min_scale": _safe_float(runtime_selection_obj.get("vol_target_min_scale")),
        "max_scale": _safe_float(runtime_selection_obj.get("vol_target_max_scale")),
        "scale_by_symbol": {
            str(symbol).strip().upper(): _safe_float(scale)
            for symbol, scale in dict(runtime_selection_obj.get("vol_target_scale_by_symbol") or {}).items()
            if str(symbol).strip()
        },
        "realized_vol_by_symbol": {
            str(symbol).strip().upper(): _safe_float(vol)
            for symbol, vol in dict(runtime_selection_obj.get("vol_target_realized_vol_by_symbol") or {}).items()
            if str(symbol).strip()
        },
    }
    sleeve_id = _normalize_text(etf_beta.get("sleeve_id")) or CN_ETF_BETA_SLEEVE_ID
    sleeve_budget = {}
    if isinstance(governor_snapshot, dict):
        sleeve_budget = dict((governor_snapshot.get("sleeve_budgets") or {}).get(sleeve_id) or {})
    sleeve_budget_used = (
        {
            "budget_owner": _normalize_text(governed_obj.get("governor", {}).get("owner")) or "global_portfolio_governor",
            "total_risk_budget": _safe_float((governor_snapshot or {}).get("total_risk_budget")),
            "total_exposure_cap": _safe_float((governor_snapshot or {}).get("total_exposure_cap")),
            "slot_cap": _safe_int(sleeve_budget.get("slot_cap")),
            "available_slots": _safe_int(sleeve_budget.get("available_slots")),
            "positions_after_sell": _safe_int(sleeve_budget.get("positions_after_sell")),
            "candidate_count": len(eligible_etfs) if runtime_selection_obj else _safe_int(sleeve_budget.get("candidate_count")),
            "selected_count": len(selected_etfs) if runtime_selection_obj else _safe_int(sleeve_budget.get("selected_count")),
            "budget_share": _safe_float(sleeve_budget.get("budget_share")),
            "raw_sleeve_ids": [text for text in (_normalize_text(item) for item in list(sleeve_budget.get("raw_sleeve_ids") or ())) if text],
            "budget_reason_codes": [text for text in (_normalize_text(item) for item in list((governor_snapshot or {}).get("budget_reason_codes") or ())) if text],
            "target_exposure": _safe_float(sleeve_budget.get("target_exposure")),
            "min_deployable_exposure": _safe_float(sleeve_budget.get("min_deployable_exposure")),
            "target_exposure_source": _normalize_text(sleeve_budget.get("target_exposure_source")) or None,
            "min_deployable_exposure_source": _normalize_text(sleeve_budget.get("min_deployable_exposure_source")) or None,
            "fallback_allowed": bool(sleeve_budget.get("fallback_allowed", False)),
            "under_deploy_reason_codes": _normalize_reason_list(sleeve_budget.get("under_deploy_reason_codes")),
            "target_selected_count": _safe_int(sleeve_budget.get("target_selected_count"), default=0) or None,
            "actual_exposure": _safe_float(sleeve_budget.get("actual_exposure")),
            "actual_risk_exposure": _safe_float(sleeve_budget.get("actual_risk_exposure")),
            "actual_fallback_exposure": _safe_float(sleeve_budget.get("actual_fallback_exposure")),
            "actual_other_exposure": _safe_float(sleeve_budget.get("actual_other_exposure")),
            "deployability_gap": _safe_float(sleeve_budget.get("deployability_gap")),
        }
        if sleeve_budget or isinstance(governor_snapshot, dict)
        else None
    )
    exposure_semantics = resolve_etf_beta_exposure_semantics(
        etf_beta_contract=etf_beta,
        effective_state_5=(governor_snapshot or {}).get("regime_effective_state"),
        total_exposure_cap=(governor_snapshot or {}).get("total_exposure_cap"),
        slot_cap=(sleeve_budget_used or {}).get("slot_cap"),
        target_selected_count=target_selected_count,
        sleeve_budget_snapshot=sleeve_budget_used,
    )
    exposure_policy_family = _normalize_text(exposure_semantics.get("exposure_policy_family")) or CN_ETF_BETA_EXPOSURE_POLICY_FAMILY
    policy_scope = _normalize_text(exposure_semantics.get("policy_scope")) or CN_ETF_BETA_POLICY_SCOPE
    broad_based_only = bool(exposure_semantics.get("broad_based_only", False))
    layering_policy = _normalize_text(exposure_semantics.get("layering_policy")) or CN_ETF_BETA_LAYERING_POLICY
    controlled_accumulation_mode = _normalize_text(exposure_semantics.get("controlled_accumulation_mode")) or CN_ETF_BETA_CONTROLLED_ACCUMULATION_MODE
    layering_band = _normalize_text(exposure_semantics.get("layering_band")) or None
    layering_active = bool(exposure_semantics.get("layering_active", False))
    layering_reason_codes = _normalize_reason_list(exposure_semantics.get("layering_reason_codes"))
    target_exposure = _safe_float(exposure_semantics.get("target_exposure"))
    target_exposure_source = _normalize_text(exposure_semantics.get("target_exposure_source")) or None
    min_deployable_exposure = _safe_float(exposure_semantics.get("min_deployable_exposure"))
    min_deployable_exposure_source = _normalize_text(exposure_semantics.get("min_deployable_exposure_source")) or None
    fallback_allowed = bool(exposure_semantics.get("fallback_allowed", False))
    target_selected_count = _safe_int(exposure_semantics.get("target_selected_count"), default=0) or None
    target_selected_count_source = _normalize_text(exposure_semantics.get("target_selected_count_source")) or None
    fallback_allowed_source = _normalize_text(exposure_semantics.get("fallback_allowed_source")) or None
    under_deploy_reason_codes = _normalize_reason_list([
        *runtime_under_deploy_reason_codes,
        *list((sleeve_budget_used or {}).get("under_deploy_reason_codes") or ()),
    ])
    if sleeve_budget_used is not None:
        sleeve_budget_used["strategy_role"] = strategy_role
        sleeve_budget_used["governor_boundary_mode"] = governor_boundary_mode
        sleeve_budget_used["local_policy_mode"] = local_policy_mode
        sleeve_budget_used["exposure_policy_family"] = exposure_policy_family
        sleeve_budget_used["policy_scope"] = policy_scope
        sleeve_budget_used["broad_based_only"] = broad_based_only
        sleeve_budget_used["layering_policy"] = layering_policy
        sleeve_budget_used["controlled_accumulation_mode"] = controlled_accumulation_mode
        sleeve_budget_used["layering_band"] = layering_band
        sleeve_budget_used["layering_active"] = layering_active
        sleeve_budget_used["layering_reason_codes"] = list(layering_reason_codes)
        sleeve_budget_used["target_exposure"] = target_exposure
        sleeve_budget_used["min_deployable_exposure"] = min_deployable_exposure
        sleeve_budget_used["target_exposure_source"] = target_exposure_source
        sleeve_budget_used["min_deployable_exposure_source"] = min_deployable_exposure_source
        sleeve_budget_used["fallback_allowed"] = fallback_allowed
        sleeve_budget_used["fallback_allowed_source"] = fallback_allowed_source
        sleeve_budget_used["under_deploy_reason_codes"] = list(under_deploy_reason_codes)
        sleeve_budget_used["target_selected_count"] = target_selected_count
        sleeve_budget_used["target_selected_count_source"] = target_selected_count_source

    governor_boundary = {
        "effective_state_5": exposure_semantics.get("effective_state_5"),
        "budget_owner": (sleeve_budget_used or {}).get("budget_owner"),
        "total_exposure_cap": (sleeve_budget_used or {}).get("total_exposure_cap"),
        "slot_cap": (sleeve_budget_used or {}).get("slot_cap"),
        "budget_reason_codes": list((sleeve_budget_used or {}).get("budget_reason_codes") or []),
        "target_exposure": target_exposure,
        "target_exposure_source": target_exposure_source,
        "min_deployable_exposure": min_deployable_exposure,
        "min_deployable_exposure_source": min_deployable_exposure_source,
        "target_selected_count": target_selected_count,
        "target_selected_count_source": target_selected_count_source,
        "fallback_allowed": fallback_allowed,
        "fallback_allowed_source": fallback_allowed_source,
        "layering_band": layering_band,
        "layering_active": layering_active,
        "layering_reason_codes": list(layering_reason_codes),
    }
    local_policy_decision = {
        "strategy_role": strategy_role,
        "local_policy_mode": local_policy_mode,
        "controlled_accumulation_mode": controlled_accumulation_mode,
        "eligible_etfs": list(eligible_etfs),
        "selected_etfs": list(selected_etfs),
        "selection_reason_codes": dict(selection_reason_codes),
        "runtime_reason_codes": list(runtime_reason_codes),
        "under_deploy_reason_codes": list(under_deploy_reason_codes),
        "fallback_mode": fallback_mode,
        "fallback_symbol": fallback_symbol,
        "fallback_active": bool(runtime_selection_obj.get("fallback_active", False)),
        "target_actual_exposure": _safe_float(runtime_selection_obj.get("target_actual_exposure")),
        "deployability_gap": _safe_float(runtime_selection_obj.get("deployability_gap")),
        "layering_band": layering_band,
        "layering_active": layering_active,
        "layering_reason_codes": list(layering_reason_codes),
    }
    formal_alignment = classify_etf_formal_alignment(
        input_etfs=input_etfs,
        core_beta_symbols=core_beta_symbols,
        limited_defense_candidates=limited_defense_candidates,
        fallback_mode=fallback_mode,
        fallback_symbol=fallback_symbol,
        strategy_role=strategy_role,
        governor_boundary_mode=governor_boundary_mode,
        local_policy_mode=local_policy_mode,
        source_entry_type=_normalize_text(etf_beta.get("source_entry_type")) or "cn_etf_research_entry",
        research_rule_family=research_rule_family,
        absolute_filter_profile=absolute_filter_profile,
        candidate_pool_profile=candidate_pool_profile,
        selection_chain_profile=selection_chain_profile,
        controlled_accumulation_mode=controlled_accumulation_mode,
        template_target_formal_symbols=_normalize_symbol_list(etf_beta.get("template_target_formal_symbols")),
        template_proxy_map=_normalize_symbol_map(etf_beta.get("template_proxy_map")),
        proxy_replacement_mode=proxy_replacement_mode,
        formal_replacement_pairs=formal_replacement_pairs,
        core_slot_symbols=core_slot_symbols,
        growth_slot_symbols=growth_slot_symbols,
        growth_seat_symbol=(
            _normalize_symbol_list([etf_beta.get("growth_seat_symbol")])[0]
            if _normalize_symbol_list([etf_beta.get("growth_seat_symbol")])
            else None
        ),
        runtime_selection_summary=runtime_selection_obj,
    )
    return {
        "contract_version": "cn_etf_beta_phase1@6",
        "sleeve_id": sleeve_id,
        "system_role": _normalize_text(etf_beta.get("system_role")) or "market_beta_sleeve",
        "strategy_role": strategy_role,
        "governor_boundary_mode": governor_boundary_mode,
        "local_policy_mode": local_policy_mode,
        "exposure_policy_family": exposure_policy_family,
        "policy_scope": policy_scope,
        "broad_based_only": broad_based_only,
        "layering_policy": layering_policy,
        "controlled_accumulation_mode": controlled_accumulation_mode,
        "layering_band": layering_band,
        "layering_active": layering_active,
        "layering_reason_codes": layering_reason_codes,
        "budget_semantics": _normalize_text(etf_beta.get("budget_semantics")) or CN_ETF_BETA_BUDGET_SEMANTICS,
        "total_budget_owner": _normalize_text(etf_beta.get("total_budget_owner")) or "global_portfolio_governor",
        "source_entry_type": _normalize_text(etf_beta.get("source_entry_type")) or "cn_etf_research_entry",
        "phase1_scope_mode": _normalize_text(etf_beta.get("phase1_scope_mode")) or "core_beta_plus_limited_defense",
        "research_rule_family": research_rule_family,
        "absolute_filter_profile": absolute_filter_profile,
        "candidate_pool_profile": candidate_pool_profile,
        "selection_chain_profile": selection_chain_profile,
        "template_id": _normalize_text(etf_beta.get("template_id")) or None,
        "template_asset_pool_version": _normalize_text(etf_beta.get("template_asset_pool_version")) or None,
        "template_role_map": _normalize_symbol_map(etf_beta.get("template_role_map")),
        "template_proxy_map": _normalize_symbol_map(etf_beta.get("template_proxy_map")),
        "template_target_formal_symbols": _normalize_symbol_list(etf_beta.get("template_target_formal_symbols")),
        "proxy_replacement_mode": proxy_replacement_mode,
        "formal_replacement_pairs": formal_replacement_pairs,
        "core_slot_symbols": core_slot_symbols,
        "growth_slot_symbols": growth_slot_symbols,
        "growth_seat_symbol": (
            _normalize_symbol_list([etf_beta.get("growth_seat_symbol")])[0]
            if _normalize_symbol_list([etf_beta.get("growth_seat_symbol")])
            else None
        ),
        "rebalance_frequency": rebalance_frequency,
        "absolute_filter_mode": absolute_filter_mode,
        "fallback_mode": fallback_mode,
        "fallback_symbol": fallback_symbol,
        "relative_strength_fast_window": relative_strength_fast_window,
        "relative_strength_mid_window": relative_strength_mid_window,
        "relative_strength_slow_window": relative_strength_slow_window,
        "relative_strength_fast_weight": relative_strength_fast_weight if relative_strength_fast_weight is not None else CN_ETF_BETA_RS_FAST_WEIGHT,
        "relative_strength_mid_weight": relative_strength_mid_weight if relative_strength_mid_weight is not None else CN_ETF_BETA_RS_MID_WEIGHT,
        "relative_strength_slow_weight": relative_strength_slow_weight if relative_strength_slow_weight is not None else CN_ETF_BETA_RS_SLOW_WEIGHT,
        "max_selected_symbols": max_selected_symbols,
        "target_selected_count": target_selected_count,
        "target_selected_count_source": target_selected_count_source,
        "target_exposure": target_exposure,
        "target_exposure_source": target_exposure_source,
        "min_deployable_exposure": min_deployable_exposure,
        "min_deployable_exposure_source": min_deployable_exposure_source,
        "target_exposure_by_state_5": exposure_semantics.get("target_exposure_by_state_5") or {},
        "min_deployable_exposure_by_state_5": exposure_semantics.get("min_deployable_exposure_by_state_5") or {},
        "target_selected_count_by_state_5": exposure_semantics.get("target_selected_count_by_state_5") or {},
        "fallback_allowed": fallback_allowed,
        "fallback_allowed_source": fallback_allowed_source,
        "fallback_allowed_by_state_5": exposure_semantics.get("fallback_allowed_by_state_5") or {},
        "under_deploy_reason_codes": under_deploy_reason_codes,
        "actual_exposure": _safe_float((sleeve_budget_used or {}).get("actual_exposure")),
        "actual_risk_exposure": _safe_float((sleeve_budget_used or {}).get("actual_risk_exposure")),
        "actual_fallback_exposure": _safe_float((sleeve_budget_used or {}).get("actual_fallback_exposure")),
        "actual_other_exposure": _safe_float((sleeve_budget_used or {}).get("actual_other_exposure")),
        "deployability_gap": _safe_float((sleeve_budget_used or {}).get("deployability_gap")),
        "core_slot_selected_symbol": core_slot_selected_symbol,
        "growth_slot_selected_symbol": growth_slot_selected_symbol,
        "slot_selection_reason_codes": slot_selection_reason_codes,
        "slot_under_deploy_reason_codes": slot_under_deploy_reason_codes,
        "core_slot_target_exposure": core_slot_target_exposure,
        "growth_slot_target_exposure": growth_slot_target_exposure,
        "core_slot_target_actual_exposure": core_slot_target_actual_exposure,
        "growth_slot_target_actual_exposure": growth_slot_target_actual_exposure,
        "vol_target_window": vol_target_window,
        "vol_target_annualized_target": vol_target_annualized_target,
        "vol_target_min_scale": vol_target_min_scale,
        "vol_target_max_scale": vol_target_max_scale,
        "source_preset_id": _normalize_text(universe_obj.get("preset_id")) or None,
        "source_batch_id": _normalize_text(universe_obj.get("etf_batch")) or None,
        "input_etfs": input_etfs,
        "formal_core_beta_symbols": core_beta_symbols,
        "limited_defense_candidates": limited_defense_candidates,
        "formal_alignment_reference": CN_ETF_FORMAL_ALIGNMENT_REFERENCE,
        "formal_alignment_status": formal_alignment.get("classification"),
        "formal_mainline_compatible": bool(formal_alignment.get("formal_mainline_compatible", False)),
        "formal_alignment_reason_codes": list(formal_alignment.get("reason_codes") or []),
        "formal_alignment_evidence": sanitize_json(formal_alignment.get("evidence") or {}),
        "fallback_scope_symbols": eligible_fallback_etfs,
        "eligible_core_beta_etfs": eligible_core_beta_etfs,
        "eligible_limited_defense_etfs": eligible_limited_defense_etfs,
        "eligible_etfs": eligible_etfs,
        "selected_etfs": selected_etfs,
        "selection_scope": selection_scope,
        "selection_reason_codes": selection_reason_codes,
        "runtime_reason_codes": runtime_reason_codes,
        "absolute_filter_reject_count": runtime_selection_obj.get("absolute_filter_reject_count"),
        "absolute_filter_reject_reason_counts": dict(runtime_selection_obj.get("absolute_filter_reject_reason_counts") or {}),
        "candidate_pool_symbols": list(runtime_selection_obj.get("candidate_pool_symbols") or []),
        "candidate_pool_coverage_summary": dict(runtime_selection_obj.get("candidate_pool_coverage_summary") or {}),
        "candidate_pool_reject_reason_counts": dict(runtime_selection_obj.get("candidate_pool_reject_reason_counts") or {}),
        "selection_chain_winner_counts": dict(runtime_selection_obj.get("selection_chain_winner_counts") or {}),
        "selection_chain_reject_reason_counts": dict(runtime_selection_obj.get("selection_chain_reject_reason_counts") or {}),
        "out_of_scope_etfs": out_of_scope_etfs,
        "out_of_scope_reason_codes": out_of_scope_reason_codes,
        "governor_boundary": sanitize_json(governor_boundary),
        "local_policy_decision": sanitize_json(local_policy_decision),
        "sleeve_budget_used": sanitize_json(sleeve_budget_used) if sleeve_budget_used is not None else None,
        "sleeve_budget_snapshot": sanitize_json(sleeve_budget_used) if sleeve_budget_used is not None else None,
        "runtime_selection": sanitize_json(runtime_selection_obj) if runtime_selection_obj else None,
        "vol_target": sanitize_json(runtime_vol_target),
        "runtime_vol_target": sanitize_json(runtime_vol_target),
    }


def extract_latest_etf_beta_runtime_selection(daily_df: pd.DataFrame) -> dict[str, Any] | None:
    if daily_df.empty or "date" not in daily_df.columns or "diagnostics_input_json" not in daily_df.columns:
        return None
    df = daily_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")
    if df.empty:
        return None
    for _, row in df.iloc[::-1].iterrows():
        raw = row.get("diagnostics_input_json")
        payload: dict[str, Any] = {}
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                payload = parsed
        diagnostics = dict(payload.get("diagnostics") or {})
        eligible_etfs = [str(item).strip().upper() for item in list(diagnostics.get("etf_beta_eligible_symbols") or ()) if str(item).strip()]
        selected_etfs = [str(item).strip().upper() for item in list(diagnostics.get("etf_beta_selected_symbols") or ()) if str(item).strip()]
        selection_reason_codes = {
            str(symbol).strip().upper(): [str(code).strip() for code in list(codes or ()) if str(code).strip()]
            for symbol, codes in dict(diagnostics.get("etf_beta_selection_reason_codes") or {}).items()
            if str(symbol).strip()
        }
        runtime_reason_codes = [str(item).strip() for item in list(diagnostics.get("etf_beta_runtime_reason_codes") or ()) if str(item).strip()]
        if not any((eligible_etfs, selected_etfs, selection_reason_codes, runtime_reason_codes)):
            continue
        vol_target_scale_by_symbol = {
            str(symbol).strip().upper(): value
            for symbol, value in dict(diagnostics.get("etf_beta_vol_target_scale_by_symbol") or {}).items()
            if str(symbol).strip()
        }
        vol_target_realized_vol_by_symbol = {
            str(symbol).strip().upper(): value
            for symbol, value in dict(diagnostics.get("etf_beta_vol_target_realized_vol_by_symbol") or {}).items()
            if str(symbol).strip()
        }
        return sanitize_json(
            {
                "date": row["date"].strftime("%Y-%m-%d"),
                "eligible_etfs": eligible_etfs,
                "selected_etfs": selected_etfs,
                "selection_reason_codes": selection_reason_codes,
                "runtime_reason_codes": runtime_reason_codes,
                "proxy_replacement_mode": diagnostics.get("etf_beta_proxy_replacement_mode"),
                "formal_replacement_pairs": dict(diagnostics.get("etf_beta_formal_replacement_pairs") or {}),
                "core_slot_symbols": list(diagnostics.get("etf_beta_core_slot_symbols") or []),
                "growth_slot_symbols": list(diagnostics.get("etf_beta_growth_slot_symbols") or []),
                "core_slot_selected_symbol": diagnostics.get("etf_beta_core_slot_selected_symbol"),
                "growth_slot_selected_symbol": diagnostics.get("etf_beta_growth_slot_selected_symbol"),
                "slot_selection_reason_codes": dict(diagnostics.get("etf_beta_slot_selection_reason_codes") or {}),
                "slot_under_deploy_reason_codes": dict(diagnostics.get("etf_beta_slot_under_deploy_reason_codes") or {}),
                "core_slot_target_exposure": diagnostics.get("etf_beta_core_slot_target_exposure"),
                "growth_slot_target_exposure": diagnostics.get("etf_beta_growth_slot_target_exposure"),
                "core_slot_target_actual_exposure": diagnostics.get("etf_beta_core_slot_target_actual_exposure"),
                "growth_slot_target_actual_exposure": diagnostics.get("etf_beta_growth_slot_target_actual_exposure"),
                "selected_cap": diagnostics.get("etf_beta_selected_cap"),
                "max_selected_symbols": diagnostics.get("etf_beta_max_selected_symbols"),
                "absolute_filter_profile": diagnostics.get("etf_beta_absolute_filter_profile"),
                "candidate_pool_profile": diagnostics.get("etf_beta_candidate_pool_profile"),
                "selection_chain_profile": diagnostics.get("etf_beta_selection_chain_profile"),
                "strategy_role": diagnostics.get("etf_beta_strategy_role"),
                "governor_boundary_mode": diagnostics.get("etf_beta_governor_boundary_mode"),
                "local_policy_mode": diagnostics.get("etf_beta_local_policy_mode"),
                "controlled_accumulation_mode": diagnostics.get("etf_beta_controlled_accumulation_mode"),
                "governor_boundary_reason_codes": [
                    str(item).strip()
                    for item in list(diagnostics.get("etf_beta_governor_boundary_reason_codes") or ())
                    if str(item).strip()
                ],
                "local_policy_reason_codes": [
                    str(item).strip()
                    for item in list(diagnostics.get("etf_beta_local_policy_reason_codes") or ())
                    if str(item).strip()
                ],
                "target_exposure": diagnostics.get("etf_beta_target_exposure"),
                "target_exposure_source": diagnostics.get("etf_beta_target_exposure_source"),
                "min_deployable_exposure": diagnostics.get("etf_beta_min_deployable_exposure"),
                "min_deployable_exposure_source": diagnostics.get("etf_beta_min_deployable_exposure_source"),
                "target_selected_count": diagnostics.get("etf_beta_target_selected_count"),
                "target_selected_count_source": diagnostics.get("etf_beta_target_selected_count_source"),
                "target_exposure_per_symbol": diagnostics.get("etf_beta_target_exposure_per_symbol"),
                "target_actual_exposure": diagnostics.get("etf_beta_target_actual_exposure"),
                "deployability_gap": diagnostics.get("etf_beta_target_deployability_gap"),
                "exposure_policy_family": diagnostics.get("etf_beta_exposure_policy_family"),
                "policy_scope": diagnostics.get("etf_beta_policy_scope"),
                "broad_based_only": bool(diagnostics.get("etf_beta_broad_based_only", False)),
                "layering_policy": diagnostics.get("etf_beta_layering_policy"),
                "layering_band": diagnostics.get("etf_beta_layering_band"),
                "layering_active": bool(diagnostics.get("etf_beta_layering_active", False)),
                "layering_reason_codes": [
                    str(item).strip()
                    for item in list(diagnostics.get("etf_beta_layering_reason_codes") or ())
                    if str(item).strip()
                ],
                "fallback_allowed": bool(diagnostics.get("etf_beta_fallback_allowed", False)),
                "fallback_allowed_source": diagnostics.get("etf_beta_fallback_allowed_source"),
                "fallback_active": bool(diagnostics.get("etf_beta_fallback_active", False)),
                "under_deploy_reason_codes": [
                    str(item).strip()
                    for item in list(diagnostics.get("etf_beta_under_deploy_reason_codes") or ())
                    if str(item).strip()
                ],
                "rebalance_day": bool(diagnostics.get("etf_beta_rebalance_day", False)),
                "deployable_slot_cap": diagnostics.get("etf_beta_deployable_slot_cap"),
                "vol_target_active": bool(diagnostics.get("etf_beta_vol_target_active", False)),
                "vol_target_window": diagnostics.get("etf_beta_vol_target_window"),
                "vol_target_annualized_target": diagnostics.get("etf_beta_vol_target_annualized_target"),
                "vol_target_min_scale": diagnostics.get("etf_beta_vol_target_min_scale"),
                "vol_target_max_scale": diagnostics.get("etf_beta_vol_target_max_scale"),
                "vol_target_scale_by_symbol": vol_target_scale_by_symbol,
                "vol_target_realized_vol_by_symbol": vol_target_realized_vol_by_symbol,
                "absolute_filter_reject_count": diagnostics.get("etf_beta_absolute_filter_reject_count"),
                "absolute_filter_reject_reason_counts": dict(diagnostics.get("etf_beta_absolute_filter_reject_reason_counts") or {}),
                "candidate_pool_symbols": list(diagnostics.get("etf_beta_candidate_pool_symbols") or []),
                "candidate_pool_coverage_summary": dict(diagnostics.get("etf_beta_candidate_pool_coverage_summary") or {}),
                "candidate_pool_reject_reason_counts": dict(diagnostics.get("etf_beta_candidate_pool_reject_reason_counts") or {}),
                "selection_chain_winner_counts": dict(diagnostics.get("etf_beta_selection_chain_winner_counts") or {}),
                "selection_chain_reject_reason_counts": dict(diagnostics.get("etf_beta_selection_chain_reject_reason_counts") or {}),
            }
        )
    return None


__all__ = [
    "CN_ETF_BETA_ABSOLUTE_FILTER_MODE",
    "CN_ETF_BETA_ABSOLUTE_FILTER_PROFILE",
    "CN_ETF_BETA_BUDGET_SEMANTICS",
    "CN_ETF_BETA_CANDIDATE_POOL_PROFILE",
    "CN_ETF_BETA_CORE_SYMBOLS",
    "CN_ETF_BETA_FALLBACK_MODE",
    "CN_ETF_BETA_EXPOSURE_POLICY_FAMILY",
    "CN_ETF_BETA_POLICY_SCOPE",
    "CN_ETF_BETA_LAYERING_POLICY",
    "CN_ETF_BETA_LIMITED_DEFENSE_CANDIDATES",
    "CN_ETF_BETA_REBALANCE_FREQUENCY",
    "CN_ETF_BETA_RS_FAST_WEIGHT",
    "CN_ETF_BETA_RS_FAST_WINDOW",
    "CN_ETF_BETA_RS_MID_WEIGHT",
    "CN_ETF_BETA_RS_MID_WINDOW",
    "CN_ETF_BETA_RS_SLOW_WEIGHT",
    "CN_ETF_BETA_RS_SLOW_WINDOW",
    "CN_ETF_BETA_RULE_FAMILY",
    "CN_ETF_BETA_SELECTION_CHAIN_PROFILE",
    "CN_ETF_BETA_SLEEVE_ID",
    "CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET",
    "CN_ETF_BETA_VOL_TARGET_MAX_SCALE",
    "CN_ETF_BETA_VOL_TARGET_MIN_SCALE",
    "CN_ETF_BETA_VOL_TARGET_WINDOW",
    "CN_ETF_FORMAL_ALIGNMENT_CLASSIFICATIONS",
    "CN_ETF_FORMAL_ALIGNMENT_REFERENCE",
    "CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS",
    "CN_ETF_FORMAL_PHASE1_EXCLUDED_SYMBOLS",
    "CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES",
    "build_default_etf_beta_contract",
    "build_etf_beta_phase1_summary",
    "classify_etf_formal_alignment",
    "extract_latest_etf_beta_runtime_selection",
    "normalize_etf_beta_contract",
    "resolve_etf_beta_exposure_semantics",
]
