from __future__ import annotations

from typing import Any, Mapping

from backend.api.shared.json_utils import sanitize_json
from backend.core.data.cn_etf_catalog import get_catalog_entry
from backend.core.config.etf_beta.defaults import *
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


def _normalize_symbol_float_map(values: Any) -> dict[str, float]:
    out: dict[str, float] = {}
    if not isinstance(values, dict):
        return out
    for key, raw in values.items():
        symbol = _normalize_text(key).upper()
        value = _safe_float(raw)
        if not symbol or value is None:
            continue
        out[symbol] = float(value)
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


def _select_etf_beta_view(
    source: Mapping[str, Any] | None,
    *,
    allowed_keys: frozenset[str],
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(source or {})
    if isinstance(extra, Mapping):
        for key, value in dict(extra).items():
            payload[str(key)] = value
    selected: dict[str, Any] = {}
    for key in allowed_keys:
        if key in payload:
            selected[key] = payload[key]
    return sanitize_json(selected)


def build_etf_beta_formal_view(
    source: Mapping[str, Any] | None,
    *,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _select_etf_beta_view(source, allowed_keys=_ETF_BETA_FORMAL_VIEW_KEYS, extra=extra)


def build_etf_beta_research_view(
    source: Mapping[str, Any] | None,
    *,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _select_etf_beta_view(source, allowed_keys=_ETF_BETA_RESEARCH_VIEW_KEYS, extra=extra)


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
        if symbol in CN_ETF_FORMAL_PHASE1_EXCLUDED_SYMBOLS:
            invalid.append(symbol)
            continue
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


def _safe_notional_exposure(value: Any) -> float | None:
    exposure = _safe_float(value)
    if exposure is None:
        return None
    if exposure < 0.0:
        return 0.0
    if exposure > 1.0 + 1e-12:
        return None
    return float(exposure)


def _is_formal_stabilizer_role(strategy_role: Any, local_policy_mode: Any = None) -> bool:
    role_text = _normalize_text(strategy_role).lower()
    local_policy_text = _normalize_text(local_policy_mode).lower()
    return role_text in {"phase1_allocation_engine", "strategic_beta_stabilizer"} or local_policy_text == "phase1_bucket_allocation"


def _is_standalone_mainline_role(
    strategy_role: Any,
    *,
    local_policy_mode: Any = None,
    exposure_policy_family: Any = None,
) -> bool:
    role_text = _normalize_text(strategy_role).lower()
    local_policy_text = _normalize_text(local_policy_mode).lower()
    exposure_policy_text = _normalize_text(exposure_policy_family).lower()
    return (
        role_text == "governed_broad_based_standalone_mainline"
        and local_policy_text == "broad_based_rotation_mainline"
        and exposure_policy_text == "broad_based_standalone_mainline_v1"
    )


def _resolve_stabilizer_role_map(etf_beta: dict[str, Any]) -> tuple[list[str], list[str], list[str], dict[str, str]]:
    core_beta_symbols = _normalize_symbol_list(etf_beta.get("core_beta_symbols")) or list(CN_ETF_BETA_CORE_SYMBOLS)
    limited_defense_candidates = (
        _normalize_symbol_list(etf_beta.get("limited_defense_candidates")) or list(CN_ETF_BETA_LIMITED_DEFENSE_CANDIDATES)
    )
    configured_core = _normalize_symbol_list(etf_beta.get("core_accumulator_symbols"))
    configured_satellite = _normalize_symbol_list(etf_beta.get("tactical_satellite_symbols"))
    core_accumulator_symbols = configured_core or [
        symbol for symbol in core_beta_symbols if symbol in set(CN_ETF_BETA_CORE_ACCUMULATOR_SYMBOLS)
    ]
    if not core_accumulator_symbols:
        core_accumulator_symbols = list(core_beta_symbols[:2] or core_beta_symbols)
    tactical_satellite_symbols = configured_satellite or [
        symbol for symbol in core_beta_symbols if symbol not in set(core_accumulator_symbols)
    ]
    role_by_symbol: dict[str, str] = {}
    for symbol in core_accumulator_symbols:
        role_by_symbol[symbol] = "core_accumulator"
    for symbol in tactical_satellite_symbols:
        role_by_symbol[symbol] = "tactical_satellite"
    for symbol in limited_defense_candidates:
        role_by_symbol[symbol] = "limited_defense"
    return core_accumulator_symbols, tactical_satellite_symbols, limited_defense_candidates, role_by_symbol


def _clamp_unit_float(value: Any, *, default: float = 0.0) -> float:
    out = _safe_float(value)
    if out is None:
        out = float(default)
    return float(max(0.0, min(float(out), 1.0)))


def _bull_pace_mode(
    *,
    effective_state_5: str,
    tactical_overlay_cap: float,
    bull_partial_overlay_pace_ratio: float,
    hard_blocked: bool,
) -> str | None:
    if hard_blocked:
        return None
    if canonical_state_5(effective_state_5) != "BULL":
        return None
    if float(tactical_overlay_cap) <= 1e-12:
        return None
    if float(bull_partial_overlay_pace_ratio) <= 1e-12:
        return None
    return "partial_overlay_v1"


def _deployment_pace_for_state(
    *,
    effective_state_5: str,
    strategic_floor_cap: float,
    tactical_overlay_cap: float,
    bull_partial_overlay_pace_ratio: float,
    target_exposure: float,
    min_deployable_exposure: float,
    standalone_mainline_active: bool,
    hard_blocked: bool,
) -> float:
    if hard_blocked:
        return 0.0
    state = canonical_state_5(effective_state_5)
    target_value = max(float(target_exposure or 0.0), 0.0)
    min_deployable_value = max(float(min_deployable_exposure or 0.0), 0.0)
    floor_value = max(float(strategic_floor_cap or 0.0), 0.0)
    overlay_value = max(float(tactical_overlay_cap or 0.0), 0.0)
    if state == "RISK_OFF":
        if standalone_mainline_active and target_value > 1e-12:
            return target_value
        return 0.0
    if target_value <= 1e-12 and floor_value <= 1e-12:
        return 0.0
    if state == "TRANS_DOWN":
        return floor_value
    if state == "BULL":
        if standalone_mainline_active:
            return target_value
        return floor_value + (_clamp_unit_float(bull_partial_overlay_pace_ratio, default=0.0) * overlay_value)
    if state == "TRANS_UP":
        if standalone_mainline_active:
            return target_value
        return floor_value
    return 0.0


def _pace_policy_mode(
    *,
    effective_state_5: Any,
    target_exposure: float,
    deployment_pace: float,
    bull_pace_mode: Any = None,
) -> str | None:
    state = canonical_state_5(effective_state_5)
    if float(target_exposure) <= float(deployment_pace) + 1e-12:
        return None
    if state == "BULL" and _normalize_text(bull_pace_mode):
        return "partial_overlay_v1_between_rebalances"
    if state in {"BULL", "TRANS_UP"}:
        return "floor_only_between_rebalances"
    return None


def _pace_policy_reason_code(
    *,
    effective_state_5: Any,
    target_exposure: float,
    deployment_pace: float,
    bull_pace_mode: Any = None,
) -> str | None:
    state = canonical_state_5(effective_state_5)
    if state not in {"BULL", "TRANS_UP"}:
        return None
    if float(target_exposure) > float(deployment_pace) + 1e-12:
        if state == "BULL" and _normalize_text(bull_pace_mode):
            return "ETF_BETA_DEPLOYMENT_PACE_BULL_PARTIAL_OVERLAY"
        return "ETF_BETA_DEPLOYMENT_PACE_FLOOR_ONLY"
    return None


def _trans_up_contract_mode(*, effective_state_5: Any, formal_stabilizer_active: bool) -> str | None:
    if formal_stabilizer_active and canonical_state_5(effective_state_5) == "TRANS_UP":
        return "single_seat_core_recovery"
    return None


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


def _normalize_state_symbol_list_map(values: Any) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not isinstance(values, dict):
        return out
    for key, raw in values.items():
        state_5 = canonical_state_5(key) if _normalize_text(key) else ""
        if not state_5:
            continue
        out[state_5] = _normalize_symbol_list(raw)
    return out


def _normalize_state_symbol_float_map(values: Any) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    if not isinstance(values, dict):
        return out
    for key, raw in values.items():
        state_5 = canonical_state_5(key) if _normalize_text(key) else ""
        if not state_5 or not isinstance(raw, dict):
            continue
        symbol_weights = _normalize_symbol_float_map(raw)
        total = sum(max(0.0, float(value)) for value in symbol_weights.values())
        if total <= 1e-12:
            continue
        out[state_5] = {
            symbol: float(max(0.0, float(value)) / total)
            for symbol, value in symbol_weights.items()
            if float(value) > 0.0
        }
    return out


def _resolve_phase1_bucket_split(values: Any, *, bucket_key: str) -> dict[str, float]:
    normalized = _normalize_state_float_map(values)
    return {
        state: float(normalized.get(state, defaults[bucket_key]))
        for state, defaults in CN_ETF_PHASE1_BUCKET_SPLIT_BY_STATE_5.items()
    }


def _resolve_phase1_equity_template(
    values: Any,
    *,
    effective_state_5: str,
    tilt_limits: dict[str, float] | None = None,
) -> dict[str, float]:
    base = dict(
        CN_ETF_PHASE1_EQUITY_TEMPLATE_WEIGHTS_BY_STATE_5.get(effective_state_5)
        or CN_ETF_PHASE1_EQUITY_TEMPLATE_WEIGHTS_BY_STATE_5["TRANS_UP"]
    )
    override = _normalize_symbol_float_map(values)
    if override:
        base.update(override)
    limits = dict(CN_ETF_PHASE1_EQUITY_TILT_LIMITS)
    if tilt_limits:
        limits.update(_normalize_symbol_float_map(tilt_limits))
    clipped: dict[str, float] = {}
    for symbol, raw in base.items():
        limit = float(limits.get(symbol, raw))
        clipped[symbol] = max(0.0, min(float(raw), limit))
    total = sum(clipped.values())
    if total <= 1e-12:
        return dict(CN_ETF_PHASE1_EQUITY_TEMPLATE_WEIGHTS_BY_STATE_5["TRANS_UP"])
    return {symbol: float(weight / total) for symbol, weight in clipped.items() if weight > 0.0}


def _resolve_phase1_defense_template(values: Any) -> dict[str, float]:
    template = dict(CN_ETF_PHASE1_DEFENSE_WEIGHTS)
    template.update(_normalize_symbol_float_map(values))
    total = sum(max(0.0, float(value)) for value in template.values())
    if total <= 1e-12:
        return dict(CN_ETF_PHASE1_DEFENSE_WEIGHTS)
    return {
        symbol: float(max(0.0, float(value)) / total)
        for symbol, value in template.items()
        if float(value) > 0.0
    }


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
    if state_5 == "RISK_OFF":
        if (
            exposure_policy_family == "broad_based_standalone_mainline_v1"
            and target_exposure is not None
            and float(target_exposure) > 1e-12
        ):
            return "RISK_OFF_CORE_ACCUMULATE", True, ["ETF_BETA_LAYERING_RISK_OFF_CORE_ACCUMULATE"]
        return "RISK_OFF_ZERO", False, []
    if target_exposure is None or float(target_exposure) <= 1e-12:
        return "NO_LAYERING", False, []
    if state_5 in {"BULL", "TRANS_UP"}:
        return "RISK_ON_FULL", False, []
    if state_5 == "TRANS_DOWN" and layering_policy == "light_trans_down_accumulate":
        return "CONTROLLED_TRANS_DOWN", True, ["ETF_BETA_LAYERING_CONTROLLED_TRANS_DOWN"]
    return "NO_LAYERING", False, []


def _phase1_scope_reason_codes(symbols: list[str], *, reason_code: str) -> dict[str, list[str]]:
    return {
        symbol: [reason_code, "IN_RESEARCH_ENTRY", "PHASE1_SCOPE_GATED"]
        for symbol in symbols
    }


__all__ = [
    name
    for name in globals()
    if name not in {"Any", "Mapping", "sanitize_json", "get_catalog_entry", "__builtins__", "__cached__", "__doc__", "__file__", "__loader__", "__name__", "__package__", "__spec__"}
]



__all__ = [name for name in globals() if name not in {'__builtins__', '__cached__', '__doc__', '__file__', '__loader__', '__name__', '__package__', '__spec__'}]

