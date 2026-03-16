from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from backend.api.backtest_v2.data_impl import (
    BacktestV2ExecutionPreviewRequest,
    _extract_reason_code_counts,
    _load_manifest_or_404,
    _normalized_run_meta_counters,
    get_backtest_v2_manifest,
    get_benchmark_series,
    get_industries,
    get_market_data_sync_status,
    get_stock_names,
    get_symbol_series,
    preview_backtest_v2_execution,
    validate_backtest_v2_data,
)
from backend.api.backtest_v2.runner_impl import (
    BacktestV2ExperimentRequest,
    _attach_public_experiment_id,
    _attach_run_profile_summary,
    _build_runtime_cfg_from_workbench,
    _compile_semantic_config_bundle,
    _execution_override_snapshot,
    _looks_like_backend_runtime_config,
    _request_semantic_blocks,
    _run_backtest_v2_experiment_sync,
    _run_locked_candidate_preset_sync,
    _semantic_ranking_execution_overrides,
    _semantic_sizing_execution_overrides,
    _write_config_snapshots,
    cancel_backtest_v2_job,
    get_backtest_v2_job,
    run_backtest_v2_experiment,
    run_backtest_v2_experiment_async,
)
from backend.api.shared.paths import bt_root as _bt_root
from backend.api.backtest_v2.artifacts_impl import (
    _build_counters,
    _resolve_runtime_path,
    _sanitize_historical_stock_names,
    _to_rel,
    stabilize_experiment_result,
    write_manifest,
)


class BacktestV2RunRequest(BaseModel):
    start_date: str
    end_date: str
    symbols: list[str]
    benchmark: str
    validation_request_id: str | None = None
    validation_passed: bool | None = None
    validation_warnings: list[str] | None = None


def write_data_validation_section(run_dir: Path, req: BacktestV2RunRequest, bt_root: Path | None = None) -> None:
    report_path = Path(run_dir) / "report.json"
    payload = {}
    if report_path.exists():
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8-sig"))
        except Exception:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload["data_validation"] = {
        "request_id": req.validation_request_id,
        "passed": bool(req.validation_passed),
        "warnings": list(req.validation_warnings or []),
        "scope": {
            "start_date": req.start_date,
            "end_date": req.end_date,
            "symbols": list(req.symbols or []),
            "benchmark": req.benchmark,
        },
        "bt_root": str(bt_root) if bt_root else None,
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = [
    "BacktestV2ExperimentRequest",
    "BacktestV2ExecutionPreviewRequest",
    "BacktestV2RunRequest",
    "_bt_root",
    "_attach_public_experiment_id",
    "_attach_run_profile_summary",
    "_build_runtime_cfg_from_workbench",
    "_build_counters",
    "_compile_semantic_config_bundle",
    "_execution_override_snapshot",
    "_extract_reason_code_counts",
    "_load_manifest_or_404",
    "_looks_like_backend_runtime_config",
    "_normalized_run_meta_counters",
    "_request_semantic_blocks",
    "_resolve_runtime_path",
    "_run_backtest_v2_experiment_sync",
    "_run_locked_candidate_preset_sync",
    "_sanitize_historical_stock_names",
    "_semantic_ranking_execution_overrides",
    "_semantic_sizing_execution_overrides",
    "_to_rel",
    "_write_config_snapshots",
    "cancel_backtest_v2_job",
    "get_backtest_v2_job",
    "get_backtest_v2_manifest",
    "get_benchmark_series",
    "get_industries",
    "get_market_data_sync_status",
    "get_stock_names",
    "get_symbol_series",
    "preview_backtest_v2_execution",
    "run_backtest_v2_experiment",
    "run_backtest_v2_experiment_async",
    "stabilize_experiment_result",
    "validate_backtest_v2_data",
    "write_data_validation_section",
    "write_manifest",
]
