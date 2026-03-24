from __future__ import annotations

import json
from collections import Counter
from typing import Any, Mapping

import pandas as pd

from backend.core.config.cn_a_governed_mainline import canonical_state_5, coarse_state_from_state_5

ATTRIBUTION_AUDIT_CONTRACT_VERSION = "cn_a_attribution_audit@1"


def _parse_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _parse_json_list(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return list(raw)
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    return list(parsed) if isinstance(parsed, list) else []


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except Exception:
        return None
    if pd.isna(out):
        return None
    return out


def _normalized_state_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    base_state = canonical_state_5(
        row.get("base_state_5") or row.get("market_state_5") or row.get("market_state"),
        trade_mode=row.get("trade_mode"),
    )
    effective_state = canonical_state_5(
        row.get("effective_state_5") or row.get("market_state_5") or row.get("market_state"),
        trade_mode=row.get("trade_mode"),
    )
    reason_codes = [str(item).strip() for item in _parse_json_list(row.get("reason_codes_json")) if str(item).strip()]
    manual_override = _parse_json_object(row.get("manual_override_json"))
    manual_override_payload = {
        "active": bool(manual_override.get("active", False)),
        "reason": manual_override.get("reason"),
        "scope": manual_override.get("scope"),
        "actor": manual_override.get("actor"),
        "effective_window": manual_override.get("effective_window"),
        "target_state_5": manual_override.get("target_state_5"),
        "risk_budget_multiplier": _safe_float(manual_override.get("risk_budget_multiplier")),
        "defense_bias": _safe_float(manual_override.get("defense_bias")),
    }
    subscores = _parse_json_object(row.get("subscores_json"))
    block_scores = _parse_json_object(row.get("block_scores_json"))
    state_stability = _parse_json_object(row.get("state_stability_metrics_json"))
    return {
        "date": str(row.get("date") or ""),
        "base_state": base_state,
        "effective_state": effective_state,
        "coarse_state": coarse_state_from_state_5(base_state),
        "effective_coarse_state": coarse_state_from_state_5(effective_state),
        "confidence": _safe_float(row.get("regime_confidence")),
        "risk_budget_multiplier": _safe_float(row.get("risk_budget_multiplier")),
        "defense_bias": _safe_float(row.get("defense_bias")),
        "reason_codes": reason_codes,
        "why_today": str(row.get("regime_transition_reason") or "").strip() or None,
        "manual_override": manual_override_payload,
        "subscores": subscores,
        "block_scores": block_scores,
        "state_stability_metrics": state_stability,
    }


def _normalized_budget_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    budget = _parse_json_object(row.get("governor_budget_json"))
    reason_codes = [str(item).strip() for item in list(budget.get("budget_reason_codes") or []) if str(item).strip()]
    return {
        "date": str(row.get("date") or ""),
        "budget_owner": str(budget.get("budget_owner") or "").strip() or None,
        "budget_consumer_sleeve_id": str(budget.get("budget_consumer_sleeve_id") or "").strip() or None,
        "budget_consumer_system_role": str(budget.get("budget_consumer_system_role") or "").strip() or None,
        "total_risk_budget": _safe_float(budget.get("total_risk_budget")),
        "total_exposure_cap": _safe_float(budget.get("total_exposure_cap")),
        "drawdown_state": str(budget.get("drawdown_state") or "").strip() or None,
        "recovery_state": str(budget.get("recovery_state") or "").strip() or None,
        "cooldown_state": str(budget.get("cooldown_state") or "").strip() or None,
        "defense_floor_state": str(budget.get("defense_floor_state") or "").strip() or None,
        "defense_floor": _safe_float(budget.get("defense_floor")),
        "budget_reason_codes": reason_codes,
    }


def _build_state_logs(daily_df: pd.DataFrame) -> tuple[list[dict[str, Any]], Counter[str], list[dict[str, Any]]]:
    state_logs: list[dict[str, Any]] = []
    manual_override_logs: list[dict[str, Any]] = []
    reason_counter: Counter[str] = Counter()
    prev_key: tuple[Any, ...] | None = None
    for row in daily_df.to_dict(orient="records"):
        state = _normalized_state_snapshot(row)
        for code in state.get("reason_codes") or []:
            reason_counter.update([str(code)])
        manual_override = dict(state.get("manual_override") or {})
        if manual_override.get("active") or any(manual_override.get(k) for k in ("reason", "scope", "actor")):
            manual_override_logs.append(
                {
                    "date": state["date"],
                    "active": bool(manual_override.get("active", False)),
                    "reason": manual_override.get("reason"),
                    "scope": manual_override.get("scope"),
                    "actor": manual_override.get("actor"),
                    "effective_window": manual_override.get("effective_window"),
                    "target_state_5": manual_override.get("target_state_5"),
                    "base_state": state["base_state"],
                    "effective_state": state["effective_state"],
                }
            )
        current_key = (
            state["base_state"],
            state["effective_state"],
            state["coarse_state"],
            state["effective_coarse_state"],
        )
        if current_key != prev_key or state["reason_codes"] or manual_override.get("active"):
            state_logs.append(state)
        prev_key = current_key
    return state_logs, reason_counter, manual_override_logs


def _build_budget_logs(daily_df: pd.DataFrame) -> tuple[list[dict[str, Any]], Counter[str]]:
    budget_logs: list[dict[str, Any]] = []
    reason_counter: Counter[str] = Counter()
    prev_key: tuple[Any, ...] | None = None
    for row in daily_df.to_dict(orient="records"):
        budget = _normalized_budget_snapshot(row)
        for code in budget.get("budget_reason_codes") or []:
            reason_counter.update([str(code)])
        current_key = (
            budget["budget_owner"],
            budget["budget_consumer_sleeve_id"],
            budget["total_risk_budget"],
            budget["total_exposure_cap"],
            budget["drawdown_state"],
            budget["recovery_state"],
            budget["cooldown_state"],
            budget["defense_floor_state"],
            budget["defense_floor"],
        )
        if current_key != prev_key or budget["budget_reason_codes"]:
            budget_logs.append(budget)
        prev_key = current_key
    return budget_logs, reason_counter


def _build_sleeve_logs(run_meta: Mapping[str, Any] | None) -> tuple[list[dict[str, Any]], Counter[str]]:
    run_meta_obj = dict(run_meta or {})
    governed_snapshot = dict(run_meta_obj.get("governed_snapshot") or {})
    etf_beta = dict(run_meta_obj.get("etf_beta") or {})
    sleeve_budgets = dict(governed_snapshot.get("sleeve_budgets") or {})
    sleeve_selection = dict(governed_snapshot.get("sleeve_selection_summary") or {})
    sleeve_ids = sorted(set(sleeve_budgets.keys()) | set(sleeve_selection.keys()))
    logs: list[dict[str, Any]] = []
    reason_counter: Counter[str] = Counter()
    for sleeve_id in sleeve_ids:
        budget = dict(sleeve_budgets.get(sleeve_id) or {})
        selection = dict(sleeve_selection.get(sleeve_id) or {})
        entry = {
            "sleeve_id": sleeve_id,
            "system_role": budget.get("system_role"),
            "budget_source": budget.get("budget_source"),
            "slot_cap": budget.get("slot_cap"),
            "available_slots": budget.get("available_slots"),
            "positions_after_sell": budget.get("positions_after_sell"),
            "candidate_count": budget.get("candidate_count"),
            "selected_count": budget.get("selected_count"),
            "budget_share": budget.get("budget_share"),
            "raw_sleeve_ids": list(budget.get("raw_sleeve_ids") or []),
            "eligible_etfs": list(selection.get("eligible_etfs") or []),
            "selected_etfs": list(selection.get("selected_etfs") or []),
            "out_of_scope_etfs": list(selection.get("out_of_scope_etfs") or []),
            "selection_reason_codes": dict(selection.get("selection_reason_codes") or {}),
        }
        if sleeve_id == "cn_etf_beta":
            entry["source_entry_type"] = etf_beta.get("source_entry_type")
            entry["formal_core_beta_symbols"] = list(etf_beta.get("formal_core_beta_symbols") or [])
            entry["limited_defense_candidates"] = list(etf_beta.get("limited_defense_candidates") or [])
            out_of_scope_reason_codes = dict(etf_beta.get("out_of_scope_reason_codes") or {})
            entry["out_of_scope_reason_codes"] = out_of_scope_reason_codes
            for codes in list(entry["selection_reason_codes"].values()) + list(out_of_scope_reason_codes.values()):
                reason_counter.update(str(code) for code in codes if str(code).strip())
        else:
            for codes in entry["selection_reason_codes"].values():
                reason_counter.update(str(code) for code in codes if str(code).strip())
        logs.append(entry)
    return logs, reason_counter


def build_attribution_audit(
    *,
    daily_df: pd.DataFrame | None,
    run_meta: Mapping[str, Any] | None,
) -> dict[str, Any]:
    daily = daily_df.copy() if isinstance(daily_df, pd.DataFrame) else pd.DataFrame()
    if not daily.empty and "date" in daily.columns:
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
        daily = daily.dropna(subset=["date"]).sort_values("date")
        daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")

    state_logs, state_reason_codes, manual_override_logs = _build_state_logs(daily)
    budget_logs, budget_reason_codes = _build_budget_logs(daily)
    sleeve_logs, sleeve_reason_codes = _build_sleeve_logs(run_meta)

    manual_override_reason_codes = Counter(
        str(log.get("reason")).strip()
        for log in manual_override_logs
        if str(log.get("reason") or "").strip()
    )

    reason_code_summary = {
        "state_reason_codes": dict(sorted(state_reason_codes.items())),
        "budget_reason_codes": dict(sorted(budget_reason_codes.items())),
        "sleeve_reason_codes": dict(sorted(sleeve_reason_codes.items())),
        "manual_override_reasons": dict(sorted(manual_override_reason_codes.items())),
    }

    summary = {
        "state_log_count": len(state_logs),
        "budget_log_count": len(budget_logs),
        "sleeve_log_count": len(sleeve_logs),
        "manual_override_log_count": len(manual_override_logs),
        "state_transition_count": sum(1 for item in state_logs if item.get("why_today")),
        "budget_change_count": len(budget_logs),
        "reason_code_family_count": sum(1 for family in reason_code_summary.values() if family),
        "latest_state_date": state_logs[-1]["date"] if state_logs else None,
        "latest_budget_date": budget_logs[-1]["date"] if budget_logs else None,
        "latest_manual_override_date": manual_override_logs[-1]["date"] if manual_override_logs else None,
        "sleeves": [entry["sleeve_id"] for entry in sleeve_logs],
    }

    return {
        "contract_version": ATTRIBUTION_AUDIT_CONTRACT_VERSION,
        "summary": summary,
        "state_logs": state_logs,
        "budget_logs": budget_logs,
        "sleeve_logs": sleeve_logs,
        "manual_override_logs": manual_override_logs,
        "reason_code_summary": reason_code_summary,
    }


__all__ = ["ATTRIBUTION_AUDIT_CONTRACT_VERSION", "build_attribution_audit"]
