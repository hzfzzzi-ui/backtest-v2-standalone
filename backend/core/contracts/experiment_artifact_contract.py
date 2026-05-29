from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.core.contracts.manifest import ExperimentManifest


REQUIRED_ARTIFACT_KEYS: tuple[str, ...] = (
    "run_meta",
    "perf",
    "nav",
    "funnel",
    "reason_codes",
    "config",
)

CSV_REQUIRED_COLUMN_SETS: dict[str, tuple[tuple[str, ...], ...]] = {
    "nav": (("date", "nav"), ("date", "strategy_nav")),
    "funnel": (("raw_signal", "blocked", "orders", "skipped", "closed_trades"), ("stage", "count")),
    "reason_codes": (("reason_code", "count"), ("code", "count")),
}


class ExperimentArtifactValidationIssue(BaseModel):
    code: str
    detail: str
    artifact_key: str | None = None
    path: str | None = None


class ExperimentArtifactValidationResult(BaseModel):
    ok: bool
    experiment_id: str | None = None
    checked_artifacts: dict[str, str] = Field(default_factory=dict)
    issues: list[ExperimentArtifactValidationIssue] = Field(default_factory=list)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _csv_columns(path: Path) -> tuple[str, ...] | None:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            return tuple(next(reader))
    except Exception:
        return None


def _issue(
    issues: list[ExperimentArtifactValidationIssue],
    code: str,
    detail: str,
    *,
    artifact_key: str | None = None,
    path: Path | None = None,
) -> None:
    issues.append(
        ExperimentArtifactValidationIssue(
            code=code,
            detail=detail,
            artifact_key=artifact_key,
            path=str(path) if path is not None else None,
        )
    )


def _artifact_path(root: Path, rel_path: str) -> Path:
    return (root / rel_path).resolve()


def validate_experiment_artifact_dir(root: Path | str) -> ExperimentArtifactValidationResult:
    artifact_root = Path(root)
    issues: list[ExperimentArtifactValidationIssue] = []
    checked: dict[str, str] = {}

    manifest_path = artifact_root / "manifest.json"
    manifest_payload = _read_json(manifest_path)
    if manifest_payload is None:
        _issue(issues, "missing_or_invalid_manifest", "manifest.json must be a JSON object.", path=manifest_path)
        return ExperimentArtifactValidationResult(ok=False, issues=issues)

    try:
        manifest = ExperimentManifest.model_validate(manifest_payload)
    except Exception as exc:
        _issue(issues, "invalid_manifest_schema", str(exc), path=manifest_path)
        return ExperimentArtifactValidationResult(ok=False, issues=issues)

    checked["manifest"] = "manifest.json"
    artifact_refs = dict(manifest.core_artifacts or manifest.artifacts or {})
    for key in REQUIRED_ARTIFACT_KEYS:
        rel = artifact_refs.get(key)
        if not rel:
            _issue(issues, "missing_artifact_ref", f"{key} must be listed in manifest artifacts.", artifact_key=key)
            continue
        rel_text = str(rel)
        rel_path = Path(rel_text)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            _issue(
                issues,
                "unsafe_artifact_path",
                f"{key} artifact path must be relative and stay inside the experiment directory.",
                artifact_key=key,
                path=rel_path,
            )
            continue
        path = _artifact_path(artifact_root, rel_text)
        if not path.exists():
            _issue(issues, "missing_artifact_file", f"{key} artifact file does not exist.", artifact_key=key, path=path)
            continue
        checked[key] = rel_text

        if path.suffix.lower() == ".json" and _read_json(path) is None:
            _issue(issues, "invalid_json_artifact", f"{key} artifact must be a JSON object.", artifact_key=key, path=path)
        required_column_sets = CSV_REQUIRED_COLUMN_SETS.get(key)
        if required_column_sets:
            columns = _csv_columns(path)
            if columns is None:
                _issue(issues, "invalid_csv_artifact", f"{key} artifact must be a readable CSV.", artifact_key=key, path=path)
            elif not any(set(required).issubset(set(columns)) for required in required_column_sets):
                expected = " or ".join(", ".join(required) for required in required_column_sets)
                _issue(
                    issues,
                    "invalid_csv_schema",
                    f"{key} artifact must include columns: {expected}.",
                    artifact_key=key,
                    path=path,
                )

    return ExperimentArtifactValidationResult(
        ok=not issues,
        experiment_id=manifest.exp_id,
        checked_artifacts=checked,
        issues=issues,
    )


__all__ = [
    "CSV_REQUIRED_COLUMN_SETS",
    "ExperimentArtifactValidationIssue",
    "ExperimentArtifactValidationResult",
    "REQUIRED_ARTIFACT_KEYS",
    "validate_experiment_artifact_dir",
]
