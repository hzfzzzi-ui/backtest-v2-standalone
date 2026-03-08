from __future__ import annotations

from typing import Any


def _unique_warnings(raw_warnings: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in list(raw_warnings or ()):
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def build_stage_summary(*, route_id: str, pipeline_result: Any) -> dict[str, Any]:
    summary = dict(getattr(pipeline_result, "summary", {}) or {})
    daily_results = tuple(getattr(pipeline_result, "daily_results", ()) or ())
    warnings: list[str] = []
    days_with_warnings = 0
    days_with_fills = 0
    days_with_scheduled_orders = 0

    for day_result in daily_results:
        warnings.extend(list(getattr(day_result, "warnings", ()) or ()))
        if getattr(day_result, "warnings", ()):
            days_with_warnings += 1
        if getattr(day_result, "filled_orders", ()):
            days_with_fills += 1
        if getattr(day_result, "scheduled_for_next_day", ()):
            days_with_scheduled_orders += 1

    return {
        "schema_version": str(summary.get("schema_version") or ""),
        "execution_shell": str(summary.get("execution_shell") or getattr(pipeline_result, "execution_shell", "")),
        "daily_loop_mode": str(summary.get("daily_loop_mode") or getattr(pipeline_result, "daily_loop_mode", "")),
        "route_id": str(route_id),
        "stage_order": list(summary.get("stage_order") or ()),
        "enabled_stages": list(summary.get("enabled_stages") or ()),
        "warnings": _unique_warnings(warnings or list(summary.get("warnings") or ())),
        "trading_days": int(summary.get("trading_days") or len(daily_results)),
        "days_with_warnings": int(days_with_warnings),
        "days_with_fills": int(days_with_fills),
        "days_with_scheduled_orders": int(days_with_scheduled_orders),
    }


def build_stage_pipeline_meta(stage_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": str(stage_summary.get("schema_version") or ""),
        "execution_shell": str(stage_summary.get("execution_shell") or ""),
        "daily_loop_mode": str(stage_summary.get("daily_loop_mode") or ""),
        "route_id": str(stage_summary.get("route_id") or ""),
        "stage_order": list(stage_summary.get("stage_order") or ()),
        "enabled_stages": list(stage_summary.get("enabled_stages") or ()),
        "warnings": list(stage_summary.get("warnings") or ()),
        "trading_days": int(stage_summary.get("trading_days") or 0),
    }


def build_stage_pipeline_audit(
    stage_pipeline: dict[str, Any] | None,
    stage_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(stage_pipeline, dict) and not isinstance(stage_summary, dict):
        return None
    audit_obj: dict[str, Any] = {}
    if isinstance(stage_pipeline, dict) and stage_pipeline:
        audit_obj["stage_pipeline"] = dict(stage_pipeline)
    if isinstance(stage_summary, dict) and stage_summary:
        audit_obj["warnings"] = list(stage_summary.get("warnings") or ())
        audit_obj["days_with_warnings"] = int(stage_summary.get("days_with_warnings") or 0)
        audit_obj["days_with_fills"] = int(stage_summary.get("days_with_fills") or 0)
        audit_obj["days_with_scheduled_orders"] = int(stage_summary.get("days_with_scheduled_orders") or 0)
    return audit_obj or None


def merge_experiment_audit(
    base_audit: dict[str, Any] | None,
    *,
    stage_pipeline: dict[str, Any] | None = None,
    stage_summary: dict[str, Any] | None = None,
    exp_id: str | None = None,
) -> dict[str, Any]:
    audit = dict(base_audit or {})
    stage_audit = build_stage_pipeline_audit(stage_pipeline, stage_summary)
    if isinstance(stage_audit, dict) and stage_audit:
        audit.update(stage_audit)
    if exp_id is not None:
        audit["exp_id"] = str(exp_id)
    return audit
