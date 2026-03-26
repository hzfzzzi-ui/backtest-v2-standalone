from __future__ import annotations

import json
from typing import Any

import pandas as pd

from backend.api.shared.json_utils import sanitize_json

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
CN_ETF_BETA_REBALANCE_FREQUENCY = "weekly"
CN_ETF_BETA_ABSOLUTE_FILTER_MODE = "ma120"
CN_ETF_BETA_FALLBACK_MODE = "none"
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
        "vol_target_window": CN_ETF_BETA_VOL_TARGET_WINDOW,
        "vol_target_annualized_target": CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET,
        "vol_target_min_scale": CN_ETF_BETA_VOL_TARGET_MIN_SCALE,
        "vol_target_max_scale": CN_ETF_BETA_VOL_TARGET_MAX_SCALE,
    }


def normalize_etf_beta_contract(raw: dict[str, Any] | None) -> dict[str, Any]:
    etf_beta = dict(raw or {})
    etf_beta["sleeve_id"] = _normalize_text(etf_beta.get("sleeve_id")) or CN_ETF_BETA_SLEEVE_ID
    etf_beta["system_role"] = _normalize_text(etf_beta.get("system_role")) or "market_beta_sleeve"
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
    etf_beta["source_entry_type"] = _normalize_text(etf_beta.get("source_entry_type")) or "cn_etf_research_entry"
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
    etf_beta["rebalance_frequency"] = _normalize_choice(
        etf_beta.get("rebalance_frequency"),
        default=CN_ETF_BETA_REBALANCE_FREQUENCY,
        allowed={"weekly", "biweekly", "monthly"},
    )
    etf_beta["absolute_filter_mode"] = _normalize_choice(
        etf_beta.get("absolute_filter_mode"),
        default=CN_ETF_BETA_ABSOLUTE_FILTER_MODE,
        allowed={"ma120", "positive_12m", "ma200_and_positive_12m"},
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
    effective_state_text = (
        canonical_state_5(effective_state_5)
        if _normalize_text(effective_state_5)
        else canonical_state_5(sleeve_budget.get("effective_state_5"))
        if _normalize_text(sleeve_budget.get("effective_state_5"))
        else ""
    )
    target_exposure_map = _normalize_state_float_map(etf_beta.get("target_exposure_by_state_5"))
    min_deployable_map = _normalize_state_float_map(etf_beta.get("min_deployable_exposure_by_state_5"))
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
    target_selected_count_value = _safe_int(target_selected_count)
    if target_selected_count_value <= 0:
        target_selected_count_value = _safe_int(sleeve_budget.get("target_selected_count"))
    if target_selected_count_value <= 0:
        target_selected_count_value = _safe_int(etf_beta.get("max_selected_symbols"))
    if target_selected_count_value <= 0:
        target_selected_count_value = _safe_int(slot_cap)
    if target_selected_count_value <= 0:
        target_selected_count_value = 1
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
    fallback_allowed = (
        bool(etf_beta.get("fallback_allowed"))
        if etf_beta.get("fallback_allowed") is not None
        else bool(sleeve_budget.get("fallback_allowed", False) or (fallback_mode_text and fallback_mode_text != "none"))
    )
    return {
        "effective_state_5": effective_state_text or None,
        "target_exposure": target_exposure,
        "target_exposure_source": target_exposure_source or None,
        "min_deployable_exposure": min_deployable_exposure,
        "min_deployable_exposure_source": min_deployable_exposure_source or None,
        "target_selected_count": int(target_selected_count_value),
        "fallback_allowed": bool(fallback_allowed),
        "target_exposure_by_state_5": target_exposure_map,
        "min_deployable_exposure_by_state_5": min_deployable_map,
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
    absolute_filter_mode = _normalize_choice(
        etf_beta.get("absolute_filter_mode"),
        default=CN_ETF_BETA_ABSOLUTE_FILTER_MODE,
        allowed={"ma120", "positive_12m", "ma200_and_positive_12m"},
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
    target_exposure = _safe_float(exposure_semantics.get("target_exposure"))
    target_exposure_source = _normalize_text(exposure_semantics.get("target_exposure_source")) or None
    min_deployable_exposure = _safe_float(exposure_semantics.get("min_deployable_exposure"))
    min_deployable_exposure_source = _normalize_text(exposure_semantics.get("min_deployable_exposure_source")) or None
    fallback_allowed = bool(exposure_semantics.get("fallback_allowed", False))
    target_selected_count = _safe_int(exposure_semantics.get("target_selected_count"), default=0) or None
    under_deploy_reason_codes = _normalize_reason_list([
        *runtime_under_deploy_reason_codes,
        *list((sleeve_budget_used or {}).get("under_deploy_reason_codes") or ()),
    ])
    if sleeve_budget_used is not None:
        sleeve_budget_used["target_exposure"] = target_exposure
        sleeve_budget_used["min_deployable_exposure"] = min_deployable_exposure
        sleeve_budget_used["target_exposure_source"] = target_exposure_source
        sleeve_budget_used["min_deployable_exposure_source"] = min_deployable_exposure_source
        sleeve_budget_used["fallback_allowed"] = fallback_allowed
        sleeve_budget_used["under_deploy_reason_codes"] = list(under_deploy_reason_codes)
        sleeve_budget_used["target_selected_count"] = target_selected_count

    return {
        "contract_version": "cn_etf_beta_phase1@3",
        "sleeve_id": sleeve_id,
        "system_role": _normalize_text(etf_beta.get("system_role")) or "market_beta_sleeve",
        "budget_semantics": _normalize_text(etf_beta.get("budget_semantics")) or CN_ETF_BETA_BUDGET_SEMANTICS,
        "total_budget_owner": _normalize_text(etf_beta.get("total_budget_owner")) or "global_portfolio_governor",
        "source_entry_type": _normalize_text(etf_beta.get("source_entry_type")) or "cn_etf_research_entry",
        "phase1_scope_mode": _normalize_text(etf_beta.get("phase1_scope_mode")) or "core_beta_plus_limited_defense",
        "research_rule_family": research_rule_family,
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
        "target_exposure": target_exposure,
        "target_exposure_source": target_exposure_source,
        "min_deployable_exposure": min_deployable_exposure,
        "min_deployable_exposure_source": min_deployable_exposure_source,
        "target_exposure_by_state_5": exposure_semantics.get("target_exposure_by_state_5") or {},
        "min_deployable_exposure_by_state_5": exposure_semantics.get("min_deployable_exposure_by_state_5") or {},
        "fallback_allowed": fallback_allowed,
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
        "fallback_scope_symbols": eligible_fallback_etfs,
        "eligible_core_beta_etfs": eligible_core_beta_etfs,
        "eligible_limited_defense_etfs": eligible_limited_defense_etfs,
        "eligible_etfs": eligible_etfs,
        "selected_etfs": selected_etfs,
        "selection_scope": selection_scope,
        "selection_reason_codes": selection_reason_codes,
        "runtime_reason_codes": runtime_reason_codes,
        "out_of_scope_etfs": out_of_scope_etfs,
        "out_of_scope_reason_codes": out_of_scope_reason_codes,
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
                "target_exposure": diagnostics.get("etf_beta_target_exposure"),
                "target_exposure_source": diagnostics.get("etf_beta_target_exposure_source"),
                "min_deployable_exposure": diagnostics.get("etf_beta_min_deployable_exposure"),
                "min_deployable_exposure_source": diagnostics.get("etf_beta_min_deployable_exposure_source"),
                "target_selected_count": diagnostics.get("etf_beta_target_selected_count"),
                "target_exposure_per_symbol": diagnostics.get("etf_beta_target_exposure_per_symbol"),
                "target_actual_exposure": diagnostics.get("etf_beta_target_actual_exposure"),
                "deployability_gap": diagnostics.get("etf_beta_target_deployability_gap"),
                "fallback_allowed": bool(diagnostics.get("etf_beta_fallback_allowed", False)),
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
            }
        )
    return None


__all__ = [
    "CN_ETF_BETA_ABSOLUTE_FILTER_MODE",
    "CN_ETF_BETA_BUDGET_SEMANTICS",
    "CN_ETF_BETA_CORE_SYMBOLS",
    "CN_ETF_BETA_FALLBACK_MODE",
    "CN_ETF_BETA_LIMITED_DEFENSE_CANDIDATES",
    "CN_ETF_BETA_REBALANCE_FREQUENCY",
    "CN_ETF_BETA_RS_FAST_WEIGHT",
    "CN_ETF_BETA_RS_FAST_WINDOW",
    "CN_ETF_BETA_RS_MID_WEIGHT",
    "CN_ETF_BETA_RS_MID_WINDOW",
    "CN_ETF_BETA_RS_SLOW_WEIGHT",
    "CN_ETF_BETA_RS_SLOW_WINDOW",
    "CN_ETF_BETA_RULE_FAMILY",
    "CN_ETF_BETA_SLEEVE_ID",
    "CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET",
    "CN_ETF_BETA_VOL_TARGET_MAX_SCALE",
    "CN_ETF_BETA_VOL_TARGET_MIN_SCALE",
    "CN_ETF_BETA_VOL_TARGET_WINDOW",
    "build_default_etf_beta_contract",
    "build_etf_beta_phase1_summary",
    "extract_latest_etf_beta_runtime_selection",
    "normalize_etf_beta_contract",
    "resolve_etf_beta_exposure_semantics",
]
