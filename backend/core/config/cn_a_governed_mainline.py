from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.core.config.etf_beta_contract import (
    CN_ETF_BETA_ABSOLUTE_FILTER_MODE,
    CN_ETF_BETA_BUDGET_SEMANTICS,
    CN_ETF_BETA_CORE_SYMBOLS,
    CN_ETF_BETA_FALLBACK_MODE,
    CN_ETF_BETA_LIMITED_DEFENSE_CANDIDATES,
    CN_ETF_BETA_REBALANCE_FREQUENCY,
    CN_ETF_BETA_RS_FAST_WEIGHT,
    CN_ETF_BETA_RS_FAST_WINDOW,
    CN_ETF_BETA_RS_MID_WEIGHT,
    CN_ETF_BETA_RS_MID_WINDOW,
    CN_ETF_BETA_RS_SLOW_WEIGHT,
    CN_ETF_BETA_RS_SLOW_WINDOW,
    CN_ETF_BETA_RULE_FAMILY,
    CN_ETF_BETA_SLEEVE_ID,
    CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET,
    CN_ETF_BETA_VOL_TARGET_MAX_SCALE,
    CN_ETF_BETA_VOL_TARGET_MIN_SCALE,
    CN_ETF_BETA_VOL_TARGET_WINDOW,
    build_default_etf_beta_contract,
    build_etf_beta_phase1_summary as build_cn_etf_beta_phase1_summary,
    normalize_etf_beta_contract,
    resolve_etf_beta_exposure_semantics as resolve_cn_etf_beta_exposure_semantics,
)

GOVERNED_A_SHARE_CONTRACT_VERSION = "cn_a_governed_mainline@1"
GOVERNED_A_SHARE_GOVERNOR_BUDGET_CONTRACT_VERSION = "cn_a_governor_budget@1"
CN_STOCK_TREND_ALPHA_CORE_SLEEVE_ID = "cn_stock_trend_alpha_core"
CN_STOCK_ALPHA_CORE_BUDGET_SEMANTICS = "consume_governor_sleeve_budget"
CN_STOCK_ALPHA_CORE_LOCAL_BUDGET_CONTROLS = (
    "max_positions",
    "single_stock_cap",
    "industry_cap",
)
CN_STOCK_ALPHA_CORE_PHASE1_EXCLUDED_CAPABILITIES = (
    "value_bluechip_satellite",
    "cn_etf_beta",
    "insurance_overlay",
)

_CANONICAL_STATE_5_ALIASES = {
    "BULL": "BULL",
    "BULL_MAIN": "BULL",
    "TRANS_UP": "TRANS_UP",
    "TURN_STRONG": "TRANS_UP",
    "LIGHT": "TRANS_UP",
    "LIGHT_TREND": "TRANS_UP",
    "TRANS_DOWN": "TRANS_DOWN",
    "TURN_WEAK": "TRANS_DOWN",
    "RISK_OFF": "RISK_OFF",
    "BEAR": "RISK_OFF",
    "DEFENSIVE": "RISK_OFF",
}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _merge_nested_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_nested_dict(dict(merged.get(key) or {}), value)
        else:
            merged[key] = value
    return merged


def is_governed_a_share_asset_scope(asset_scope: Any) -> bool:
    return _normalize_text(asset_scope) in {"cn_a_equity", "cn_etf"}


def canonical_state_5(value: Any, *, trade_mode: Any | None = None) -> str:
    text = _normalize_text(value).upper()
    if text in _CANONICAL_STATE_5_ALIASES:
        return _CANONICAL_STATE_5_ALIASES[text]
    trade_mode_text = _normalize_text(trade_mode).upper()
    if trade_mode_text == "TREND_LIGHT":
        return "TRANS_UP"
    if trade_mode_text == "NO_TRADE":
        return "RISK_OFF"
    return text


def coarse_state_from_state_5(value: Any) -> str:
    state = canonical_state_5(value)
    if state in {"BULL", "TRANS_UP"}:
        return "RISK_ON"
    if state in {"TRANS_DOWN", "RISK_OFF"}:
        return "RISK_OFF"
    return ""


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


def _phase1_scope_reason_codes(
    symbols: list[str],
    *,
    reason_code: str,
) -> dict[str, list[str]]:
    return {
        symbol: [reason_code, "IN_RESEARCH_ENTRY", "PHASE1_SCOPE_GATED"]
        for symbol in symbols
    }


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


def _normalized_count_map(raw: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        text = _normalize_text(key)
        if not text:
            continue
        out[text] = _safe_int(value)
    return out


def _default_system_sleeve_meta(asset_scope: Any) -> tuple[str, str]:
    scope = _normalize_text(asset_scope)
    if scope == "cn_etf":
        return CN_ETF_BETA_SLEEVE_ID, "market_beta_sleeve"
    return CN_STOCK_TREND_ALPHA_CORE_SLEEVE_ID, "stock_alpha_sleeve"


def _phase1_excluded_capabilities_for_sleeve(sleeve_id: str) -> list[str]:
    if str(sleeve_id or "").strip() == CN_STOCK_TREND_ALPHA_CORE_SLEEVE_ID:
        return list(CN_STOCK_ALPHA_CORE_PHASE1_EXCLUDED_CAPABILITIES)
    return []


def _local_budget_controls_for_sleeve(sleeve_id: str) -> list[str]:
    if str(sleeve_id or "").strip() == CN_STOCK_TREND_ALPHA_CORE_SLEEVE_ID:
        return list(CN_STOCK_ALPHA_CORE_LOCAL_BUDGET_CONTROLS)
    return []


# ETF canonical owner lives in backend.core.config.etf_beta_contract.


def _budget_reason_codes(
    *,
    hard_max_positions: int,
    effective_max_positions: int,
    total_exposure_cap: float | None,
    total_risk_budget: float | None,
    drawdown_state: str,
    recovery_state: str,
    cooldown_state: str,
    regime_transition_reason: str,
    breadth_max_positions: int | None,
    breadth_cap_active: bool,
    sleeve_slot_cap_active: bool,
    sleeve_slot_cap_reason_code: str,
    sleeve_budget_reject_count: int,
    manual_override_active: bool,
) -> list[str]:
    reasons: list[str] = []
    if drawdown_state == "REDUCED":
        reasons.append("DRAWDOWN_REDUCED")
    if recovery_state != "INACTIVE":
        reasons.append(f"RECOVERY::{recovery_state}")
    if cooldown_state != "INACTIVE":
        reasons.append(f"COOLDOWN::{cooldown_state}")
    if total_risk_budget is not None and total_risk_budget < 0.999:
        reasons.append("TOTAL_RISK_BUDGET_REDUCED")
    if total_exposure_cap is not None and total_exposure_cap < 0.999:
        reasons.append("TOTAL_EXPOSURE_CAP_REDUCED")
    if bool(breadth_cap_active) and breadth_max_positions is not None and breadth_max_positions < hard_max_positions:
        reasons.append("BREADTH_CAP_ACTIVE")
    if bool(sleeve_slot_cap_active) and _normalize_text(sleeve_slot_cap_reason_code):
        reasons.append(_normalize_text(sleeve_slot_cap_reason_code))
    if effective_max_positions <= 0:
        reasons.append("NO_DEPLOYABLE_SLOTS")
    if regime_transition_reason:
        reasons.append(f"REGIME_TRANSITION::{regime_transition_reason}")
    if int(sleeve_budget_reject_count) > 0:
        reasons.append("SLEEVE_BUDGET_REJECTS")
    if bool(manual_override_active):
        reasons.append("MANUAL_OVERRIDE_ACTIVE")
    return reasons


def build_governor_budget_snapshot(
    *,
    asset_scope: Any,
    hard_max_positions: Any,
    effective_max_positions: Any,
    risk_budget_multiplier: Any = None,
    drawdown: Any = None,
    drawdown_state: Any = None,
    regime_transition_reason: Any = None,
    base_state_5: Any = None,
    effective_state_5: Any = None,
    coarse_state: Any = None,
    effective_coarse_state: Any = None,
    reason_codes: Any = None,
    defense_bias: Any = None,
    manual_override: Any = None,
    breadth_max_positions: Any = None,
    breadth_cap_active: Any = None,
    sleeve_slot_cap_active: Any = None,
    sleeve_slot_cap_source: Any = None,
    positions_after_sell: Any = None,
    sleeve_budget_mode: Any = None,
    raw_sleeve_slot_caps: dict[str, Any] | None = None,
    raw_sleeve_available_slots: dict[str, Any] | None = None,
    raw_sleeve_positions_after_sell: dict[str, Any] | None = None,
    raw_sleeve_candidate_counts: dict[str, Any] | None = None,
    raw_sleeve_selected_counts: dict[str, Any] | None = None,
    sleeve_budget_reject_count: Any = None,
    target_exposure: Any = None,
    strategic_floor_cap: Any = None,
    tactical_overlay_cap: Any = None,
    deployment_pace: Any = None,
    hard_block_flags: Any = None,
    min_deployable_exposure: Any = None,
    target_exposure_source: Any = None,
    min_deployable_exposure_source: Any = None,
    fallback_allowed: Any = None,
    under_deploy_reason_codes: Any = None,
    actual_exposure: Any = None,
    actual_risk_exposure: Any = None,
    actual_fallback_exposure: Any = None,
    actual_other_exposure: Any = None,
    deployability_gap: Any = None,
) -> dict[str, Any]:
    hard_positions = max(1, _safe_int(hard_max_positions, default=1))
    effective_positions = max(0, _safe_int(effective_max_positions))
    breadth_cap = _safe_int(breadth_max_positions) if breadth_max_positions is not None else None
    breadth_cap_active_value = bool(breadth_cap_active) if breadth_cap_active is not None else bool(
        breadth_cap is not None and breadth_cap < hard_positions
    )
    sleeve_slot_cap_active_value = bool(sleeve_slot_cap_active) if sleeve_slot_cap_active is not None else False
    sleeve_slot_cap_source_text = _normalize_text(sleeve_slot_cap_source) or None
    sleeve_slot_cap_reason_code = (
        "ETF_BETA_SLOT_CAP_ACTIVE"
        if sleeve_slot_cap_active_value and _normalize_text(asset_scope).lower() == "cn_etf"
        else "SLEEVE_SLOT_CAP_ACTIVE"
        if sleeve_slot_cap_active_value
        else ""
    )
    drawdown_value = _safe_float(drawdown)
    risk_budget_value = _safe_float(risk_budget_multiplier)
    total_exposure_cap = min(float(effective_positions) / float(hard_positions), 1.0) if hard_positions > 0 else None
    total_risk_budget = risk_budget_value if risk_budget_value is not None else total_exposure_cap
    drawdown_state_text = _normalize_text(drawdown_state).upper() or "NORMAL"
    regime_reason_text = _normalize_text(regime_transition_reason)
    base_state_text = canonical_state_5(base_state_5) if _normalize_text(base_state_5) else None
    effective_state_text = canonical_state_5(effective_state_5) if _normalize_text(effective_state_5) else base_state_text
    coarse_state_text = _normalize_text(coarse_state).upper() or (coarse_state_from_state_5(base_state_text) if base_state_text else "")
    effective_coarse_state_text = _normalize_text(effective_coarse_state).upper() or (
        coarse_state_from_state_5(effective_state_text) if effective_state_text else ""
    )
    reason_code_list = [text for text in (_normalize_text(item) for item in list(reason_codes or ())) if text]
    defense_bias_value = _safe_float(defense_bias)
    manual_override_payload = dict(manual_override or {}) if isinstance(manual_override, dict) else {}
    manual_override_active = bool(manual_override_payload.get("active", False))
    recovery_state = "DRAWDOWN_RECOVERY_PENDING" if drawdown_state_text == "REDUCED" else "INACTIVE"
    cooldown_state = "REGIME_TRANSITION_COOLDOWN" if "COOLDOWN" in regime_reason_text.upper() else "INACTIVE"
    default_sleeve_id, default_system_role = _default_system_sleeve_meta(asset_scope)
    positions_after_sell_value = max(0, _safe_int(positions_after_sell))
    available_slots = max(effective_positions - positions_after_sell_value, 0)
    sleeve_budget_mode_text = _normalize_text(sleeve_budget_mode) or "governed_single_sleeve"
    reject_count = max(0, _safe_int(sleeve_budget_reject_count))

    raw_slot_caps = _normalized_count_map(raw_sleeve_slot_caps)
    raw_available_slots = _normalized_count_map(raw_sleeve_available_slots)
    raw_positions_after_sell = _normalized_count_map(raw_sleeve_positions_after_sell)
    raw_candidate_counts = _normalized_count_map(raw_sleeve_candidate_counts)
    raw_selected_counts = _normalized_count_map(raw_sleeve_selected_counts)
    raw_sleeve_ids = sorted(
        {
            *raw_slot_caps.keys(),
            *raw_available_slots.keys(),
            *raw_positions_after_sell.keys(),
            *raw_candidate_counts.keys(),
            *raw_selected_counts.keys(),
        }
    )

    if raw_sleeve_ids:
        slot_cap_value = sum(raw_slot_caps.values())
        available_slots_value = sum(raw_available_slots.values())
        positions_after_sell_value = sum(raw_positions_after_sell.values())
        candidate_count_value = sum(raw_candidate_counts.values())
        selected_count_value = sum(raw_selected_counts.values())
    else:
        slot_cap_value = effective_positions
        available_slots_value = available_slots
        candidate_count_value = 0
        selected_count_value = 0
    target_exposure_value = _safe_float(target_exposure)
    if target_exposure_value is None and _normalize_text(asset_scope).lower() == "cn_etf":
        target_exposure_value = total_exposure_cap
    strategic_floor_cap_value = _safe_float(strategic_floor_cap)
    tactical_overlay_cap_value = _safe_float(tactical_overlay_cap)
    deployment_pace_value = _safe_float(deployment_pace)
    hard_block_flag_list = _normalize_reason_list(hard_block_flags)
    min_deployable_exposure_value = _safe_float(min_deployable_exposure)
    if min_deployable_exposure_value is None and target_exposure_value is not None and _normalize_text(asset_scope).lower() == "cn_etf":
        deploy_divisor = max(1, int(slot_cap_value or 1))
        min_deployable_exposure_value = float(target_exposure_value) / float(deploy_divisor)
    fallback_allowed_value = bool(fallback_allowed) if fallback_allowed is not None else False
    under_deploy_reason_code_list = _normalize_reason_list(under_deploy_reason_codes)
    target_exposure_source_text = _normalize_text(target_exposure_source) or None
    min_deployable_exposure_source_text = _normalize_text(min_deployable_exposure_source) or None
    actual_exposure_value = _safe_float(actual_exposure)
    actual_risk_exposure_value = _safe_float(actual_risk_exposure)
    actual_fallback_exposure_value = _safe_float(actual_fallback_exposure)
    actual_other_exposure_value = _safe_float(actual_other_exposure)
    deployability_gap_value = _safe_float(deployability_gap)

    snapshot = {
        "contract_version": GOVERNED_A_SHARE_GOVERNOR_BUDGET_CONTRACT_VERSION,
        "asset_scope": _normalize_text(asset_scope) or "cn_a_equity",
        "budget_owner": "global_portfolio_governor",
        "budget_consumer_sleeve_id": default_sleeve_id,
        "budget_consumer_system_role": default_system_role,
        "budget_semantics": CN_STOCK_ALPHA_CORE_BUDGET_SEMANTICS,
        "regime_source_state": base_state_text,
        "regime_effective_state": effective_state_text,
        "coarse_state": coarse_state_text or None,
        "effective_coarse_state": effective_coarse_state_text or None,
        "regime_reason_codes": reason_code_list,
        "total_risk_budget": total_risk_budget,
        "total_exposure_cap": total_exposure_cap,
        "target_exposure": target_exposure_value,
        "hard_max_positions": hard_positions,
        "effective_max_positions": effective_positions,
        "drawdown": drawdown_value,
        "drawdown_state": drawdown_state_text,
        "recovery_state": recovery_state,
        "cooldown_state": cooldown_state,
        "defense_floor": defense_bias_value if defense_bias_value is not None else 0.0,
        "defense_floor_state": "INACTIVE",
        "defense_bias": defense_bias_value,
        "breadth_cap_active": breadth_cap_active_value,
        "sleeve_slot_cap_active": sleeve_slot_cap_active_value,
        "sleeve_slot_cap_source": sleeve_slot_cap_source_text,
        "manual_override": {
            "active": manual_override_active,
            "reason": _normalize_text(manual_override_payload.get("reason")) or None,
            "scope": _normalize_text(manual_override_payload.get("scope")) or None,
            "actor": _normalize_text(manual_override_payload.get("actor")) or None,
            "effective_window": dict(manual_override_payload.get("effective_window") or {})
            if isinstance(manual_override_payload.get("effective_window"), dict)
            else None,
            "target_state_5": canonical_state_5(manual_override_payload.get("target_state_5"))
            if _normalize_text(manual_override_payload.get("target_state_5"))
            else None,
        },
        "sleeve_budget_mode": sleeve_budget_mode_text,
        "sleeve_budget_reject_count": reject_count,
        "budget_reason_codes": _budget_reason_codes(
            hard_max_positions=hard_positions,
            effective_max_positions=effective_positions,
            total_exposure_cap=total_exposure_cap,
            total_risk_budget=total_risk_budget,
            drawdown_state=drawdown_state_text,
            recovery_state=recovery_state,
            cooldown_state=cooldown_state,
            regime_transition_reason=regime_reason_text,
            breadth_max_positions=breadth_cap,
            breadth_cap_active=breadth_cap_active_value,
            sleeve_slot_cap_active=sleeve_slot_cap_active_value,
            sleeve_slot_cap_reason_code=sleeve_slot_cap_reason_code,
            sleeve_budget_reject_count=reject_count,
            manual_override_active=manual_override_active,
        ),
        "sleeve_budgets": {
            default_sleeve_id: {
                "system_role": default_system_role,
                "budget_source": "global_portfolio_governor",
                "slot_cap": slot_cap_value,
                "available_slots": available_slots_value,
                "positions_after_sell": positions_after_sell_value,
                "candidate_count": candidate_count_value,
                "selected_count": selected_count_value,
                "budget_share": 1.0,
                "target_exposure": target_exposure_value,
                "target_selected_count": slot_cap_value if _normalize_text(asset_scope).lower() == "cn_etf" else None,
                "raw_sleeve_ids": raw_sleeve_ids,
            }
        },
        "raw_sleeve_budget": {
            "slot_caps": raw_slot_caps,
            "available_slots": raw_available_slots,
            "positions_after_sell": raw_positions_after_sell,
            "candidate_counts": raw_candidate_counts,
            "selected_counts": raw_selected_counts,
        },
    }
    return snapshot


def merge_governor_budget_snapshot(
    snapshot: dict[str, Any] | None,
    **kwargs: Any,
) -> dict[str, Any]:
    base = deepcopy(snapshot or {})
    merged = build_governor_budget_snapshot(
        asset_scope=kwargs.get("asset_scope", base.get("asset_scope")),
        hard_max_positions=kwargs.get("hard_max_positions", base.get("hard_max_positions")),
        effective_max_positions=kwargs.get("effective_max_positions", base.get("effective_max_positions")),
        risk_budget_multiplier=kwargs.get("risk_budget_multiplier", base.get("total_risk_budget")),
        drawdown=kwargs.get("drawdown", base.get("drawdown")),
        drawdown_state=kwargs.get("drawdown_state", base.get("drawdown_state")),
        regime_transition_reason=kwargs.get(
            "regime_transition_reason",
            next(
                (
                    str(code).split("::", 1)[1]
                    for code in list(base.get("budget_reason_codes") or ())
                    if str(code).startswith("REGIME_TRANSITION::")
                ),
                "",
            ),
        ),
        base_state_5=kwargs.get("base_state_5", base.get("regime_source_state")),
        effective_state_5=kwargs.get("effective_state_5", base.get("regime_effective_state")),
        coarse_state=kwargs.get("coarse_state", base.get("coarse_state")),
        effective_coarse_state=kwargs.get("effective_coarse_state", base.get("effective_coarse_state")),
        reason_codes=kwargs.get("reason_codes", list(base.get("regime_reason_codes") or ())),
        defense_bias=kwargs.get("defense_bias", base.get("defense_bias")),
        manual_override=kwargs.get("manual_override", dict(base.get("manual_override") or {})),
        breadth_max_positions=kwargs.get(
            "breadth_max_positions",
            _safe_int(base.get("total_exposure_cap") * base.get("hard_max_positions", 0))
            if base.get("total_exposure_cap") is not None and base.get("hard_max_positions") is not None
            else None,
        ),
        breadth_cap_active=kwargs.get("breadth_cap_active", base.get("breadth_cap_active")),
        sleeve_slot_cap_active=kwargs.get("sleeve_slot_cap_active", base.get("sleeve_slot_cap_active")),
        sleeve_slot_cap_source=kwargs.get("sleeve_slot_cap_source", base.get("sleeve_slot_cap_source")),
        positions_after_sell=kwargs.get(
            "positions_after_sell",
            next(
                (
                    sleeve_payload.get("positions_after_sell")
                    for sleeve_payload in list((base.get("sleeve_budgets") or {}).values())
                    if isinstance(sleeve_payload, dict)
                ),
                0,
            ),
        ),
        sleeve_budget_mode=kwargs.get("sleeve_budget_mode", base.get("sleeve_budget_mode")),
        raw_sleeve_slot_caps=kwargs.get(
            "raw_sleeve_slot_caps",
            dict((base.get("raw_sleeve_budget") or {}).get("slot_caps") or {}),
        ),
        raw_sleeve_available_slots=kwargs.get(
            "raw_sleeve_available_slots",
            dict((base.get("raw_sleeve_budget") or {}).get("available_slots") or {}),
        ),
        raw_sleeve_positions_after_sell=kwargs.get(
            "raw_sleeve_positions_after_sell",
            dict((base.get("raw_sleeve_budget") or {}).get("positions_after_sell") or {}),
        ),
        raw_sleeve_candidate_counts=kwargs.get(
            "raw_sleeve_candidate_counts",
            dict((base.get("raw_sleeve_budget") or {}).get("candidate_counts") or {}),
        ),
        raw_sleeve_selected_counts=kwargs.get(
            "raw_sleeve_selected_counts",
            dict((base.get("raw_sleeve_budget") or {}).get("selected_counts") or {}),
        ),
        sleeve_budget_reject_count=kwargs.get("sleeve_budget_reject_count", base.get("sleeve_budget_reject_count")),
        target_exposure=kwargs.get("target_exposure", base.get("target_exposure")),
        strategic_floor_cap=kwargs.get("strategic_floor_cap", base.get("strategic_floor_cap")),
        tactical_overlay_cap=kwargs.get("tactical_overlay_cap", base.get("tactical_overlay_cap")),
        deployment_pace=kwargs.get("deployment_pace", base.get("deployment_pace")),
        hard_block_flags=kwargs.get("hard_block_flags", list(base.get("hard_block_flags") or ())),
        min_deployable_exposure=kwargs.get("min_deployable_exposure", base.get("min_deployable_exposure")),
        target_exposure_source=kwargs.get("target_exposure_source", base.get("target_exposure_source")),
        min_deployable_exposure_source=kwargs.get("min_deployable_exposure_source", base.get("min_deployable_exposure_source")),
        fallback_allowed=kwargs.get("fallback_allowed", base.get("fallback_allowed")),
        under_deploy_reason_codes=kwargs.get("under_deploy_reason_codes", list(base.get("under_deploy_reason_codes") or ())),
        actual_exposure=kwargs.get("actual_exposure", base.get("actual_exposure")),
        actual_risk_exposure=kwargs.get("actual_risk_exposure", base.get("actual_risk_exposure")),
        actual_fallback_exposure=kwargs.get("actual_fallback_exposure", base.get("actual_fallback_exposure")),
        actual_other_exposure=kwargs.get("actual_other_exposure", base.get("actual_other_exposure")),
        deployability_gap=kwargs.get("deployability_gap", base.get("deployability_gap")),
    )
    return merged


def _default_contract(asset_scope: str) -> dict[str, Any] | None:
    scope = _normalize_text(asset_scope)
    if scope not in {"cn_a_equity", "cn_etf"}:
        return None
    return {
        "enabled": True,
        "contract_version": GOVERNED_A_SHARE_CONTRACT_VERSION,
        "system_id": "cn_a_governed_multi_sleeve_phase1",
        "phase": "phase1_contract",
        "regime": {
            "enabled": True,
            "owner": "market_regime_engine",
            "primary_state_model": "five_state",
            "coarse_state_model": "derived_two_state",
            "subscore_contract": ["technical", "sentiment", "macro_global"],
            "manual_override": {
                "active": False,
                "reason": None,
                "scope": None,
                "actor": None,
                "effective_window": None,
                "target_state_5": None,
                "risk_budget_multiplier": None,
                "defense_bias": None,
            },
        },
        "governor": {
            "enabled": True,
            "owner": "global_portfolio_governor",
            "contract_only": True,
            "budget_source_of_truth": True,
        },
        "stock_alpha_core": {
            "enabled": scope == "cn_a_equity",
            "sleeve_id": CN_STOCK_TREND_ALPHA_CORE_SLEEVE_ID,
            "system_role": "stock_alpha_sleeve",
            "legacy_anchor": "baseline_V10.1",
            "strategy_semantics": "trend_breakout_residual",
            "budget_semantics": CN_STOCK_ALPHA_CORE_BUDGET_SEMANTICS,
            "total_budget_owner": "global_portfolio_governor",
            "local_budget_controls": list(CN_STOCK_ALPHA_CORE_LOCAL_BUDGET_CONTROLS),
            "phase1_excluded_capabilities": list(CN_STOCK_ALPHA_CORE_PHASE1_EXCLUDED_CAPABILITIES),
        },
        "etf_beta": build_default_etf_beta_contract(enabled=scope == "cn_etf"),
    }


def build_governed_a_share_contract(
    raw: dict[str, Any] | None,
    *,
    asset_scope: Any,
) -> dict[str, Any] | None:
    scope = _normalize_text(asset_scope)
    default_contract = _default_contract(scope)
    if default_contract is None:
        return None
    merged = _merge_nested_dict(default_contract, dict(raw or {}))
    regime = dict(merged.get("regime") or {})
    manual_override = dict(regime.get("manual_override") or {})
    regime["manual_override"] = {
        "active": bool(manual_override.get("active", False)),
        "reason": _normalize_text(manual_override.get("reason")) or None,
        "scope": _normalize_text(manual_override.get("scope")) or None,
        "actor": _normalize_text(manual_override.get("actor")) or None,
        "effective_window": dict(manual_override.get("effective_window") or {})
        if isinstance(manual_override.get("effective_window"), dict)
        else None,
        "target_state_5": canonical_state_5(manual_override.get("target_state_5"))
        if _normalize_text(manual_override.get("target_state_5"))
        else None,
        "risk_budget_multiplier": _safe_float(manual_override.get("risk_budget_multiplier")),
        "defense_bias": _safe_float(manual_override.get("defense_bias")),
    }
    regime["subscore_contract"] = [
        text
        for text in (_normalize_text(item).lower() for item in list(regime.get("subscore_contract") or ()))
        if text
    ] or ["technical", "sentiment", "macro_global"]
    merged["regime"] = regime
    merged["etf_beta"] = normalize_etf_beta_contract(dict(merged.get("etf_beta") or {}))
    stock_alpha = dict(merged.get("stock_alpha_core") or {})
    stock_alpha["legacy_anchor"] = _normalize_text(stock_alpha.get("legacy_anchor")) or "baseline_V10.1"
    stock_alpha["sleeve_id"] = _normalize_text(stock_alpha.get("sleeve_id")) or CN_STOCK_TREND_ALPHA_CORE_SLEEVE_ID
    stock_alpha["system_role"] = _normalize_text(stock_alpha.get("system_role")) or "stock_alpha_sleeve"
    stock_alpha["budget_semantics"] = (
        _normalize_text(stock_alpha.get("budget_semantics")) or CN_STOCK_ALPHA_CORE_BUDGET_SEMANTICS
    )
    stock_alpha["total_budget_owner"] = (
        _normalize_text(stock_alpha.get("total_budget_owner")) or "global_portfolio_governor"
    )
    stock_alpha["local_budget_controls"] = [
        text
        for text in (_normalize_text(item) for item in list(stock_alpha.get("local_budget_controls") or ()))
        if text
    ] or list(CN_STOCK_ALPHA_CORE_LOCAL_BUDGET_CONTROLS)
    stock_alpha["phase1_excluded_capabilities"] = [
        text
        for text in (_normalize_text(item) for item in list(stock_alpha.get("phase1_excluded_capabilities") or ()))
        if text
    ] or list(CN_STOCK_ALPHA_CORE_PHASE1_EXCLUDED_CAPABILITIES)
    merged["stock_alpha_core"] = stock_alpha
    governor = dict(merged.get("governor") or {})
    governor["owner"] = _normalize_text(governor.get("owner")) or "global_portfolio_governor"
    merged["governor"] = governor
    merged["enabled"] = bool(merged.get("enabled", True))
    merged["contract_version"] = _normalize_text(merged.get("contract_version")) or GOVERNED_A_SHARE_CONTRACT_VERSION
    merged["system_id"] = _normalize_text(merged.get("system_id")) or "cn_a_governed_multi_sleeve_phase1"
    merged["phase"] = _normalize_text(merged.get("phase")) or "phase1_contract"
    return merged


__all__ = [
    "GOVERNED_A_SHARE_CONTRACT_VERSION",
    "GOVERNED_A_SHARE_GOVERNOR_BUDGET_CONTRACT_VERSION",
    "CN_STOCK_TREND_ALPHA_CORE_SLEEVE_ID",
    "CN_ETF_BETA_SLEEVE_ID",
    "CN_STOCK_ALPHA_CORE_BUDGET_SEMANTICS",
    "CN_ETF_BETA_BUDGET_SEMANTICS",
    "CN_STOCK_ALPHA_CORE_LOCAL_BUDGET_CONTROLS",
    "CN_STOCK_ALPHA_CORE_PHASE1_EXCLUDED_CAPABILITIES",
    "CN_ETF_BETA_CORE_SYMBOLS",
    "CN_ETF_BETA_LIMITED_DEFENSE_CANDIDATES",
    "CN_ETF_BETA_RULE_FAMILY",
    "CN_ETF_BETA_REBALANCE_FREQUENCY",
    "CN_ETF_BETA_ABSOLUTE_FILTER_MODE",
    "CN_ETF_BETA_FALLBACK_MODE",
    "CN_ETF_BETA_RS_FAST_WINDOW",
    "CN_ETF_BETA_RS_MID_WINDOW",
    "CN_ETF_BETA_RS_SLOW_WINDOW",
    "CN_ETF_BETA_RS_FAST_WEIGHT",
    "CN_ETF_BETA_RS_MID_WEIGHT",
    "CN_ETF_BETA_RS_SLOW_WEIGHT",
    "CN_ETF_BETA_VOL_TARGET_WINDOW",
    "CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET",
    "CN_ETF_BETA_VOL_TARGET_MIN_SCALE",
    "CN_ETF_BETA_VOL_TARGET_MAX_SCALE",
    "build_governed_a_share_contract",
    "build_cn_etf_beta_phase1_summary",
    "build_governor_budget_snapshot",
    "canonical_state_5",
    "coarse_state_from_state_5",
    "is_governed_a_share_asset_scope",
    "merge_governor_budget_snapshot",
    "resolve_cn_etf_beta_exposure_semantics",
]
