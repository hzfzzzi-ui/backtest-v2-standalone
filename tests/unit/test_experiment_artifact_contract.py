from __future__ import annotations

import json
import shutil
from pathlib import Path

from backend.core.contracts.experiment_artifact_contract import validate_experiment_artifact_dir


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _copy_minimal_contract(tmp_path: Path) -> Path:
    src = _repo_root() / "examples" / "experiment_contract_minimal"
    dst = tmp_path / "exp_example_minimal"
    shutil.copytree(src, dst)
    return dst


def test_validate_experiment_artifact_dir_accepts_minimal_contract(tmp_path: Path) -> None:
    artifact_dir = _copy_minimal_contract(tmp_path)

    result = validate_experiment_artifact_dir(artifact_dir)

    assert result.ok is True
    assert result.experiment_id == "exp_example_minimal"
    assert set(result.checked_artifacts) == {
        "manifest",
        "run_meta",
        "perf",
        "nav",
        "funnel",
        "reason_codes",
        "config",
    }
    assert result.issues == []


def test_validate_experiment_artifact_dir_rejects_absolute_manifest_artifact_path(tmp_path: Path) -> None:
    artifact_dir = _copy_minimal_contract(tmp_path)
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["core_artifacts"]["nav"] = str((artifact_dir / "nav.csv").resolve())
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    result = validate_experiment_artifact_dir(artifact_dir)

    assert result.ok is False
    assert any(issue.code == "unsafe_artifact_path" and issue.artifact_key == "nav" for issue in result.issues)


def test_validate_experiment_artifact_dir_rejects_missing_required_artifact(tmp_path: Path) -> None:
    artifact_dir = _copy_minimal_contract(tmp_path)
    (artifact_dir / "reason_codes.csv").unlink()

    result = validate_experiment_artifact_dir(artifact_dir)

    assert result.ok is False
    assert any(
        issue.code == "missing_artifact_file" and issue.artifact_key == "reason_codes"
        for issue in result.issues
    )


def test_validate_experiment_artifact_dir_rejects_invalid_csv_schema(tmp_path: Path) -> None:
    artifact_dir = _copy_minimal_contract(tmp_path)
    (artifact_dir / "nav.csv").write_text("date,value\n2026-01-02,1.0\n", encoding="utf-8")

    result = validate_experiment_artifact_dir(artifact_dir)

    assert result.ok is False
    assert any(issue.code == "invalid_csv_schema" and issue.artifact_key == "nav" for issue in result.issues)
