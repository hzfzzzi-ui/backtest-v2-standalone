from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from backend.research.study_definition import StudyDefinition, validate_study_payload


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def studies_root() -> Path:
    return (_repo_root() / "research" / "studies").resolve()


def study_id_to_path(study_id: str) -> Path:
    text = str(study_id or "").strip().replace("\\", "/").strip("/")
    if not text:
        raise FileNotFoundError("study id is required")
    return (studies_root() / f"{text}.study.yaml").resolve()


def resolve_study_path(study_ref: str | Path) -> Path:
    candidate = Path(study_ref)
    if candidate.suffix.lower() in {".yaml", ".yml"}:
        path = candidate if candidate.is_absolute() else (_repo_root() / candidate).resolve()
        if path.exists():
            return path
    path = study_id_to_path(str(study_ref))
    if path.exists():
        return path
    raise FileNotFoundError(f"study definition not found: {study_ref}")


def load_study_payload(study_ref: str | Path) -> dict[str, Any]:
    path = resolve_study_path(study_ref)
    payload = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"study definition must be an object: {path}")
    return payload


def load_study_definition(study_ref: str | Path) -> StudyDefinition:
    return validate_study_payload(load_study_payload(study_ref))
