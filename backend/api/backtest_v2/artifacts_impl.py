from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.api.backtest_v2.artifacts_diagnostics import (
    _build_alpha_funnel,
    _build_candidate_signals,
    _build_counters,
    _build_score_diagnostics,
    _resolve_stock_names,
    _resolve_trade_st_flags,
    _sanitize_historical_stock_names,
)
from backend.api.backtest_v2.artifacts_finalize import (
    _append_to_experiment_index,
    _finalize_research_audit,
    ensure_standard_artifacts,
)
from backend.api.backtest_v2.artifacts_io import (
    _bool_series,
    _coerce_bool_value,
    _resolve_runtime_path,
    _safe_float,
    _safe_int,
    _safe_read_csv,
    _safe_read_json,
    _to_rel,
    _write_canonical_csv,
)
from backend.api.backtest_v2.artifacts_manifest import (
    MANIFEST_SCHEMA_VERSION,
    _baseline_compare_status,
    _generate_experiment_label,
    _manifest_config_snapshots,
    write_manifest,
)
from backend.api.backtest_v2.artifacts_stage_summary import (
    _extract_stage_pipeline_summary,
    _extract_stage_summary,
)


def stabilize_experiment_result(
    *,
    bt_root: Path,
    result: dict[str, Any],
    base_cfg: dict[str, Any],
    overrides: dict[str, Any],
    run_profile_summary: dict[str, Any] | None,
    validation_audit_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from backend.core.services.experiment_artifact_service import stabilize_experiment_output

    return stabilize_experiment_output(
        bt_root=bt_root,
        result=result,
        base_cfg=base_cfg,
        overrides=overrides,
        run_profile_summary=run_profile_summary,
        validation_audit_ref=validation_audit_ref,
    )


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "_append_to_experiment_index",
    "_baseline_compare_status",
    "_bool_series",
    "_build_alpha_funnel",
    "_build_candidate_signals",
    "_build_counters",
    "_build_score_diagnostics",
    "_coerce_bool_value",
    "_extract_stage_pipeline_summary",
    "_extract_stage_summary",
    "_finalize_research_audit",
    "_generate_experiment_label",
    "_manifest_config_snapshots",
    "_resolve_runtime_path",
    "_resolve_stock_names",
    "_resolve_trade_st_flags",
    "_safe_float",
    "_safe_int",
    "_safe_read_csv",
    "_safe_read_json",
    "_sanitize_historical_stock_names",
    "_to_rel",
    "_write_canonical_csv",
    "ensure_standard_artifacts",
    "stabilize_experiment_result",
    "write_manifest",
]
