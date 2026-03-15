from __future__ import annotations

import json
from pathlib import Path


def test_script_inventory_covers_all_top_level_python_scripts() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    inventory_path = repo_root / "backend" / "scripts" / "inventory.json"
    assert inventory_path.exists()
    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    indexed = {str(row.get("path") or "") for row in rows if isinstance(row, dict)}

    actual = {
        str(path.relative_to(repo_root)).replace("\\", "/")
        for path in (repo_root / "backend" / "scripts").glob("*.py")
    }
    assert actual == indexed


def test_script_surface_has_generated_and_archive_zones() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    generated_root = repo_root / "backend" / "scripts" / "generated"
    archive_root = repo_root / "backend" / "scripts" / "archive"
    readme_path = repo_root / "backend" / "scripts" / "README.md"
    assert generated_root.is_dir()
    assert archive_root.is_dir()
    assert (archive_root / "README.md").exists()
    assert readme_path.exists()
    readme_text = readme_path.read_text(encoding="utf-8")
    assert "generated/" in readme_text
    assert "archive/" in readme_text
    assert "_internal_helper.py" in readme_text
    assert "First migration batch:" in readme_text


def test_cli_commands_no_longer_target_top_level_scripts() -> None:
    from backend.cli.commands import audit, data_refresh

    assert all(target.startswith("backend.cli.managed.") for target in data_refresh._TARGETS.values())
    assert all(target.startswith("backend.cli.managed.") for target in audit._TARGETS.values())


def test_migrated_top_level_scripts_are_thin_wrappers() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    expected = {
        "baseline_regression_check.py": "backend.cli.managed.baseline_regression_check",
        "report_consistency_check.py": "backend.cli.managed.report_consistency_check",
        "refresh_csi1000_pit.py": "backend.cli.managed.refresh_csi1000_pit",
        "refresh_security_master.py": "backend.cli.managed.refresh_security_master",
        "update_pams_ohlcv_daily.py": "backend.cli.managed.update_pams_ohlcv_daily",
    }
    for filename, import_target in expected.items():
        text = (repo_root / "backend" / "scripts" / filename).read_text(encoding="utf-8")
        assert import_target in text
        assert "if __name__ == \"__main__\":" in text


def test_top_level_research_scripts_are_frozen_to_study_or_archive_targets() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    inventory_path = repo_root / "backend" / "scripts" / "inventory.json"
    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    frozen_rows = [
        row
        for row in rows
        if isinstance(row, dict)
        and str(row.get("path") or "").startswith("backend/scripts/run_")
        and str(row.get("path") or "").endswith("_research.py")
    ]
    assert frozen_rows
    for row in frozen_rows:
        tag = str(row.get("tag") or "")
        target = str(row.get("target") or "")
        assert tag in {"study-definition", "archived-study"}
        assert ("research/studies/" in target) or ("archive" in target)


def test_migrated_v10_research_scripts_are_thin_study_wrappers() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    expected = {
        "run_v10_residual_structure_s1_research.py": "v10/residual_structure_s1",
        "run_v10_onset_ingress_minimal_s2_research.py": "v10/onset_ingress_minimal_s2",
        "run_v10_quality_then_residual_s3_research.py": "v10/quality_then_residual_s3",
    }
    for filename, study_id in expected.items():
        text = (repo_root / "backend" / "scripts" / filename).read_text(encoding="utf-8")
        assert "from backend.cli.main import main" in text
        assert "if __name__ == \"__main__\":" in text
        assert f"\"study_run\", \"{study_id}\"" in text


def test_generated_v10_scripts_exist_for_first_migration_batch() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    expected = {
        "run_v10_residual_structure_s1.py": "v10/residual_structure_s1",
        "run_v10_onset_ingress_minimal_s2.py": "v10/onset_ingress_minimal_s2",
        "run_v10_quality_then_residual_s3.py": "v10/quality_then_residual_s3",
    }
    generated_root = repo_root / "backend" / "scripts" / "generated"
    for filename, study_id in expected.items():
        text = (generated_root / filename).read_text(encoding="utf-8")
        assert "from backend.cli.main import main" in text
        assert f"\"study_run\", \"{study_id}\"" in text


def test_inventory_records_first_generated_migration_batch() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    payload = json.loads((repo_root / "backend" / "scripts" / "inventory.json").read_text(encoding="utf-8"))
    batches = payload.get("migration_batches") if isinstance(payload.get("migration_batches"), list) else []
    assert batches
    first_batch = next((row for row in batches if row.get("batch_id") == "2026-03-15-v10-study-first-batch"), None)
    assert isinstance(first_batch, dict)
    assert first_batch.get("status") == "completed"
    studies = first_batch.get("studies") if isinstance(first_batch.get("studies"), list) else []
    recorded = {str(item.get("study_id") or ""): str(item.get("generated_script") or "") for item in studies if isinstance(item, dict)}
    assert recorded == {
        "v10/residual_structure_s1": "backend/scripts/generated/run_v10_residual_structure_s1.py",
        "v10/onset_ingress_minimal_s2": "backend/scripts/generated/run_v10_onset_ingress_minimal_s2.py",
        "v10/quality_then_residual_s3": "backend/scripts/generated/run_v10_quality_then_residual_s3.py",
    }
