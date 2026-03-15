from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.api.shared.paths import results_root as _results_root
from backend.api.shared.json_utils import sanitize_json

logger = logging.getLogger(__name__)


def _api_module():
    from backend.api.backtest_v2 import impl as api_module

    return api_module


def ensure_standard_artifacts(
    *,
    results_dir: Path,
    result: dict[str, Any],
    base_cfg: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    from backend.api.backtest_v2.artifacts_impl import ensure_standard_artifacts as _ensure_standard_artifacts

    payload = _ensure_standard_artifacts(
        results_dir=results_dir,
        result=result,
        base_cfg=base_cfg,
        overrides=overrides,
    )
    return payload if isinstance(payload, dict) else {}


def write_manifest(results_dir: Path, result: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    api_module = _api_module()
    path, manifest = api_module.write_manifest(results_dir, result)
    return path, manifest if isinstance(manifest, dict) else {}


def stabilize_experiment_output(
    *,
    bt_root: Path,
    result: dict[str, Any],
    base_cfg: dict[str, Any],
    overrides: dict[str, Any],
    run_profile_summary: dict[str, Any] | None = None,
    validation_audit_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    api_module = _api_module()
    out = dict(result or {})

    results_dir = api_module._resolve_runtime_path(str(out.get("results_dir") or ""), bt_root)
    if results_dir is None:
        results_dir = (_results_root() / "experiments" / str(out.get("exp_id") or "exp_unknown")).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    out["exp_id"] = str(out.get("exp_id") or "")
    out["results_dir"] = str(results_dir)
    out["status"] = str(out.get("status") or "OK")

    out = ensure_standard_artifacts(
        results_dir=results_dir,
        result=out,
        base_cfg=base_cfg,
        overrides=overrides,
    )
    artifacts = dict(out.get("artifacts") or {})
    artifacts.pop("report", None)
    out["artifacts"] = artifacts

    manifest_path, manifest_obj = write_manifest(results_dir, out)
    files = dict(out.get("files") or {})
    files["manifest"] = api_module._to_rel(manifest_path, results_dir)
    out["files"] = files
    out["manifest"] = manifest_obj

    try:
        from backend.api.backtest_v2 import artifacts_impl

        audit_payload = artifacts_impl._finalize_research_audit(
            bt_root=bt_root,
            results_dir=results_dir,
            result=out,
            base_cfg=base_cfg,
            overrides=overrides,
            validation_audit_ref=validation_audit_ref,
        )
        if isinstance(audit_payload, dict):
            metrics = dict(out.get("metrics") or {})
            metrics["audit"] = audit_payload
            out["metrics"] = sanitize_json(metrics)
    except Exception as exc:
        logger.warning("Failed to finalize research audit: %s", exc)

    if run_profile_summary:
        out["run_profile_summary"] = run_profile_summary

    try:
        from backend.api.backtest_v2 import artifacts_impl

        artifacts_impl._append_to_experiment_index(results_dir, out, base_cfg, overrides)
    except Exception as exc:
        logger.warning("Failed to update experiment index: %s", exc)

    return sanitize_json(out)
