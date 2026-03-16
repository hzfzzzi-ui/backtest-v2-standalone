from __future__ import annotations

from typing import Any

from backend.api.backtest_v2.artifacts_io import _safe_int
from backend.api.shared.json_utils import sanitize_json


def _extract_stage_summary(result: dict[str, Any]) -> dict[str, Any] | None:
    direct = result.get("stage_summary")
    if isinstance(direct, dict) and direct:
        return sanitize_json(dict(direct))
    metrics = result.get("metrics")
    if isinstance(metrics, dict):
        nested = metrics.get("stage_summary")
        if isinstance(nested, dict) and nested:
            return sanitize_json(dict(nested))
    return None


def _extract_stage_pipeline_summary(
    result: dict[str, Any],
    stage_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    direct = result.get("stage_pipeline")
    if isinstance(direct, dict) and direct:
        return sanitize_json(dict(direct))
    metrics = result.get("metrics")
    if isinstance(metrics, dict):
        nested = metrics.get("stage_pipeline")
        if isinstance(nested, dict) and nested:
            return sanitize_json(dict(nested))
    if not isinstance(stage_summary, dict) or not stage_summary:
        return None
    return sanitize_json(
        {
            "schema_version": stage_summary.get("schema_version"),
            "execution_shell": stage_summary.get("execution_shell"),
            "daily_loop_mode": stage_summary.get("daily_loop_mode"),
            "route_id": stage_summary.get("route_id"),
            "stage_order": list(stage_summary.get("stage_order") or ()),
            "enabled_stages": list(stage_summary.get("enabled_stages") or ()),
            "warnings": list(stage_summary.get("warnings") or ()),
            "trading_days": _safe_int(stage_summary.get("trading_days")),
        }
    )


__all__ = [
    "_extract_stage_pipeline_summary",
    "_extract_stage_summary",
]
