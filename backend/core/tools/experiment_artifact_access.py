from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _results_root() -> Path:
    raw = os.environ.get("RESULTS_ROOT", "outputs").strip() or "outputs"
    path = Path(raw)
    if not path.is_absolute():
        path = (_repo_root() / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def experiments_root() -> Path:
    return _results_root() / "experiments"


def resolve_experiment_dir_by_id(exp_id: str | None) -> Path | None:
    text = str(exp_id or "").strip()
    if not text:
        return None
    path = (experiments_root() / text).resolve()
    if path.exists() and path.is_dir():
        return path
    return None


def resolve_experiment_dir_from_results_dir(results_dir: str | None) -> Path | None:
    text = str(results_dir or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = (_repo_root() / path).resolve()
    else:
        path = path.resolve()
    if path.exists() and path.is_dir():
        return path
    return None


def load_manifest(results_dir: Path) -> dict[str, Any]:
    path = results_dir / "manifest.json"
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _normalize_rel_path(value: Any) -> str | None:
    text = str(value or "").strip().replace("\\", "/").lstrip("/")
    if not text or text == ".":
        return None
    return text


def manifest_declared_paths(manifest: dict[str, Any]) -> set[str]:
    declared: set[str] = {"manifest.json"}

    for key in ("artifacts", "config_snapshots", "files"):
        mapping = manifest.get(key)
        if not isinstance(mapping, dict):
            continue
        for value in mapping.values():
            rel = _normalize_rel_path(value)
            if rel:
                declared.add(rel)

    stage_summary = manifest.get("stage_summary")
    if isinstance(stage_summary, dict):
        rel = _normalize_rel_path(stage_summary.get("artifact"))
        if rel:
            declared.add(rel)

    optional_artifacts = manifest.get("optional_artifacts")
    if isinstance(optional_artifacts, dict):
        for entry in optional_artifacts.values():
            if not isinstance(entry, dict):
                continue
            rel = _normalize_rel_path(entry.get("path"))
            if rel:
                declared.add(rel)

    return declared


def manifest_artifact_rel(manifest: dict[str, Any], key: str) -> str | None:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    return _normalize_rel_path(artifacts.get(key))


def resolve_declared_artifact_path(results_dir: Path, manifest: dict[str, Any], rel_path: str) -> Path | None:
    rel = _normalize_rel_path(rel_path)
    if rel is None:
        return None
    if rel not in manifest_declared_paths(manifest):
        return None
    target = (results_dir / rel).resolve()
    if not str(target).startswith(str(results_dir.resolve())):
        return None
    return target


def experiment_surface_flags(results_dir: Path) -> dict[str, bool]:
    manifest_path = results_dir / "manifest.json"
    report_path = results_dir / "report.html"
    has_manifest = manifest_path.exists()
    manifest = load_manifest(results_dir) if has_manifest else {}
    core_keys = ("perf", "nav", "run_meta", "config")
    has_core_artifacts = bool(manifest) and all(manifest_artifact_rel(manifest, key) for key in core_keys)
    return {
        "has_manifest": has_manifest,
        "has_report": report_path.exists(),
        "has_core_artifacts": has_core_artifacts,
    }
