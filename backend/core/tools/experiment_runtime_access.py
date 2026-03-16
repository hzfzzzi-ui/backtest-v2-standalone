from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.tools import experiment_artifact_access


def _normalize_rel_path(value: Any) -> str | None:
    text = str(value or "").strip().replace("\\", "/").lstrip("/")
    if not text or text == ".":
        return None
    return text


def _safe_child_path(root: Path, rel_path: str | None) -> Path | None:
    rel = _normalize_rel_path(rel_path)
    if rel is None:
        return None
    target = (root / rel).resolve()
    if not str(target).startswith(str(root.resolve())):
        return None
    return target


def resolve_results_dir(
    *,
    exp_id: str | None = None,
    results_dir: str | Path | None = None,
) -> Path:
    resolved = None
    if exp_id:
        resolved = experiment_artifact_access.resolve_experiment_dir_by_id(str(exp_id))
    if resolved is None and results_dir is not None:
        resolved = experiment_artifact_access.resolve_experiment_dir_from_results_dir(str(results_dir))
    if resolved is None:
        raise FileNotFoundError(f"unable to resolve experiment directory: exp_id={exp_id!r} results_dir={results_dir!r}")
    return resolved.resolve()


def open_experiment_handle(
    *,
    exp_id: str | None = None,
    results_dir: str | Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    resolved = resolve_results_dir(exp_id=exp_id, results_dir=results_dir)
    return resolved, experiment_artifact_access.load_manifest(resolved)


def declared_artifact_path(results_dir: Path, manifest: dict[str, Any], artifact_key: str | None) -> Path | None:
    key = str(artifact_key or "").strip()
    if not key:
        return None
    rel_path = experiment_artifact_access.manifest_artifact_rel(manifest, key)
    if rel_path:
        return experiment_artifact_access.resolve_declared_artifact_path(results_dir, manifest, rel_path)
    return None


def optional_artifact_path(results_dir: Path, manifest: dict[str, Any], artifact_key: str | None) -> Path | None:
    key = str(artifact_key or "").strip()
    if not key:
        return None
    optional = manifest.get("optional_artifacts")
    if not isinstance(optional, dict):
        return None
    entry = optional.get(key)
    if not isinstance(entry, dict):
        return None
    rel_path = _normalize_rel_path(entry.get("path"))
    if rel_path is None:
        return None
    return experiment_artifact_access.resolve_declared_artifact_path(results_dir, manifest, rel_path) or _safe_child_path(results_dir, rel_path)


def resolve_artifact_path(
    *,
    exp_id: str | None = None,
    results_dir: str | Path | None = None,
    artifact_key: str | None = None,
    optional_artifact: str | None = None,
    rel_path: str | None = None,
    fallback_rel_path: str | None = None,
    require_declared: bool = False,
) -> Path | None:
    resolved_dir, manifest = open_experiment_handle(exp_id=exp_id, results_dir=results_dir)

    candidates: list[Path | None] = []
    candidates.append(declared_artifact_path(resolved_dir, manifest, artifact_key))
    candidates.append(optional_artifact_path(resolved_dir, manifest, optional_artifact))

    if rel_path:
        if require_declared:
            candidates.append(experiment_artifact_access.resolve_declared_artifact_path(resolved_dir, manifest, rel_path))
        else:
            candidates.append(_safe_child_path(resolved_dir, rel_path))

    if fallback_rel_path:
        candidates.append(_safe_child_path(resolved_dir, fallback_rel_path))

    first_candidate = None
    for candidate in candidates:
        if candidate is None:
            continue
        if first_candidate is None:
            first_candidate = candidate
        if candidate.exists():
            return candidate
    return first_candidate


def read_json_artifact(
    *,
    exp_id: str | None = None,
    results_dir: str | Path | None = None,
    artifact_key: str | None = None,
    optional_artifact: str | None = None,
    rel_path: str | None = None,
    fallback_rel_path: str | None = None,
    require_declared: bool = False,
) -> dict[str, Any]:
    path = resolve_artifact_path(
        exp_id=exp_id,
        results_dir=results_dir,
        artifact_key=artifact_key,
        optional_artifact=optional_artifact,
        rel_path=rel_path,
        fallback_rel_path=fallback_rel_path,
        require_declared=require_declared,
    )
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_text_artifact(
    *,
    exp_id: str | None = None,
    results_dir: str | Path | None = None,
    artifact_key: str | None = None,
    optional_artifact: str | None = None,
    rel_path: str | None = None,
    fallback_rel_path: str | None = None,
    require_declared: bool = False,
) -> str:
    path = resolve_artifact_path(
        exp_id=exp_id,
        results_dir=results_dir,
        artifact_key=artifact_key,
        optional_artifact=optional_artifact,
        rel_path=rel_path,
        fallback_rel_path=fallback_rel_path,
        require_declared=require_declared,
    )
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig")


def load_saved_config_record(config_id: str | None) -> dict[str, Any] | None:
    text = str(config_id or "").strip()
    if not text:
        return None
    from backend.core.tools.saved_config_access import load_saved_config_record

    return load_saved_config_record(text)


def run_experiment_sync(request_payload: dict[str, Any]) -> dict[str, Any]:
    from backend.core.services.experiment_runtime_service import run_experiment_request

    result = run_experiment_request(dict(request_payload or {}))
    return result if isinstance(result, dict) else {}


def stabilize_experiment_result(
    *,
    bt_root: Path,
    result: dict[str, Any],
    base_cfg: dict[str, Any],
    overrides: dict[str, Any],
    run_profile_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from backend.core.services.experiment_artifact_service import stabilize_experiment_output

    stabilized = stabilize_experiment_output(
        bt_root=bt_root,
        result=result,
        base_cfg=base_cfg,
        overrides=overrides,
        run_profile_summary=run_profile_summary,
    )
    return stabilized if isinstance(stabilized, dict) else {}


def candidate_presets_api() -> Any:
    from backend.core.tools import locked_candidate_presets

    return locked_candidate_presets
