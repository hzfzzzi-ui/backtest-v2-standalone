from __future__ import annotations

import json
from pathlib import Path

from backend.core.tools import experiment_runtime_access as helper


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_experiment_dir(tmp_path: Path, exp_id: str) -> Path:
    exp_dir = tmp_path / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        exp_dir / "manifest.json",
        {
            "exp_id": exp_id,
            "experiment_id": exp_id,
            "artifacts": {
                "perf": "perf.json",
                "run_meta": "run_meta.json",
            },
        },
    )
    _write_json(exp_dir / "perf.json", {"cagr": 0.12, "sharpe": 1.1})
    _write_json(exp_dir / "run_meta.json", {"status": "OK"})
    _write_json(exp_dir / "run_config.json", {"universe": {"start": "2024-01-01"}})
    return exp_dir


def test_read_json_artifact_prefers_declared_manifest_path(tmp_path: Path) -> None:
    exp_dir = _make_experiment_dir(tmp_path, "exp_declared")

    perf = helper.read_json_artifact(results_dir=exp_dir, artifact_key="perf")
    run_meta = helper.read_json_artifact(results_dir=exp_dir, artifact_key="run_meta")

    assert perf["cagr"] == 0.12
    assert run_meta["status"] == "OK"


def test_read_json_artifact_allows_sidecar_fallback(tmp_path: Path) -> None:
    exp_dir = _make_experiment_dir(tmp_path, "exp_sidecar")

    run_config = helper.read_json_artifact(
        results_dir=exp_dir,
        rel_path="run_config.json",
        fallback_rel_path="run_config.json",
    )

    assert run_config["universe"]["start"] == "2024-01-01"


def test_resolve_results_dir_can_find_archived_experiment_by_id(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    archived_dir = repo_root / "outputs" / "experiments" / "archive" / "retention_sweep" / "exp_archived_demo"
    _make_experiment_dir(archived_dir.parent, archived_dir.name)
    monkeypatch.setattr(helper.experiment_artifact_access, "_repo_root", lambda: repo_root)

    resolved = helper.resolve_results_dir(exp_id="exp_archived_demo")

    assert resolved == archived_dir.resolve()


def test_official_sources_use_core_runtime_access_boundary() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    helper_source = (repo_root / "backend" / "core" / "tools" / "experiment_runtime_access.py").read_text(encoding="utf-8")
    assert "backend.api.endpoints._experiment_surface" not in helper_source
    assert "experiment_artifact_access" in helper_source
    assert "backend.api.endpoints._config_governance" not in helper_source
    assert "backend.core.tools.saved_config_access" in helper_source
    assert "backend.api.endpoints._candidate_presets" not in helper_source
    assert "locked_candidate_presets" in helper_source
    assert "backend.core.report.report_generator" not in helper_source

    baseline_wrapper = (repo_root / "backend" / "scripts" / "baseline_regression_check.py").read_text(encoding="utf-8")
    baseline_source = (repo_root / "backend" / "cli" / "managed" / "baseline_regression_check.py").read_text(encoding="utf-8")
    assert "backend.cli.managed.baseline_regression_check" in baseline_wrapper
    assert "backend.scripts._internal_helper" not in baseline_source
    assert "backend.core.tools import experiment_runtime_access" in baseline_source

    report_wrapper = (repo_root / "backend" / "scripts" / "report_consistency_check.py").read_text(encoding="utf-8")
    report_source = (repo_root / "backend" / "cli" / "managed" / "report_consistency_check.py").read_text(encoding="utf-8")
    assert "backend.cli.managed.report_consistency_check" in report_wrapper
    assert "backend.scripts._internal_helper" not in report_source
    assert "backend.core.tools import experiment_runtime_access" in report_source
    assert "backend.core.report.report_generator" not in report_source


def test_archive_surface_is_documentation_only() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    archive_root = repo_root / "backend" / "scripts" / "archive"
    archive_files = sorted(path.name for path in archive_root.iterdir() if path.is_file())
    assert archive_files == []


def test_no_active_backend_source_references_internal_helper() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    backend_root = repo_root / "backend"
    matches: list[str] = []
    for path in backend_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "backend.scripts._internal_helper" in text:
            matches.append(str(path.relative_to(repo_root)).replace("\\", "/"))
    assert matches == []


def test_internal_script_helper_is_removed_from_active_tree() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / "backend" / "scripts" / "_internal_helper.py").exists()
    assert (repo_root / "backend" / "core" / "tools" / "experiment_runtime_access.py").exists()


def test_run_alpha_v1_is_retired_from_active_tree() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / "backend" / "scripts" / "run_alpha_v1.py").exists()


def test_experiment_surface_shim_is_retired_from_active_tree() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / "backend" / "api" / "endpoints" / "_experiment_surface.py").exists()


def test_no_active_backend_source_references_experiment_surface_shim() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    backend_root = repo_root / "backend"
    matches: list[str] = []
    for path in backend_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "backend.api.endpoints._experiment_surface" in text:
            matches.append(str(path.relative_to(repo_root)).replace("\\", "/"))
    assert matches == []


def test_config_governance_shim_is_retired_from_active_tree() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / "backend" / "api" / "endpoints" / "_config_governance.py").exists()


def test_no_active_backend_source_references_config_governance_shim() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    backend_root = repo_root / "backend"
    matches: list[str] = []
    for path in backend_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "_config_governance" in text:
            matches.append(str(path.relative_to(repo_root)).replace("\\", "/"))
    assert matches == []


def test_candidate_preset_shim_is_retired_from_active_tree() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / "backend" / "api" / "endpoints" / "_candidate_presets.py").exists()


def test_no_active_backend_source_references_candidate_preset_shim() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    backend_root = repo_root / "backend"
    matches: list[str] = []
    for path in backend_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "backend.api.endpoints._candidate_presets" in text:
            matches.append(str(path.relative_to(repo_root)).replace("\\", "/"))
    assert matches == []


def test_locked_candidate_core_helper_is_available() -> None:
    from backend.core.tools import locked_candidate_presets

    assert locked_candidate_presets.is_locked_candidate_preset("v2-breakout-atr-stop-k10-candidate") is True
    assert locked_candidate_presets.is_locked_candidate_preset("unknown") is False


def test_active_alpha_experiment_runner_spec_marks_retirement() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    spec_path = repo_root / "openspec" / "specs" / "alpha-experiment-runner" / "spec.md"
    text = spec_path.read_text(encoding="utf-8")
    assert "已于 2026-03-08" in text
    assert "`run_alpha_v1.py`" in text
