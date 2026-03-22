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
    assert "_internal_helper.py" not in readme_text
    assert "no longer hosts study-definition or archived-study entry points" in readme_text
    assert "Active research entry points must be `research/studies/*.study.yaml` plus `backend/scripts/generated/run_<study_id>.py`." in readme_text
    assert "_archive_wrapper.py" not in readme_text
    assert "documentation-only historical marker" in readme_text


def test_archive_zone_is_documentation_only() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    archive_root = repo_root / "backend" / "scripts" / "archive"
    archive_files = sorted(path.name for path in archive_root.iterdir() if path.is_file())
    assert archive_files == ["README.md"]


def test_archive_wrapper_is_removed_from_top_level_surface() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / "backend" / "scripts" / "_archive_wrapper.py").exists()


def test_cli_commands_no_longer_target_top_level_scripts() -> None:
    from backend.cli.commands import audit, data_refresh

    assert all(target.startswith("backend.cli.managed.") for target in data_refresh._TARGETS.values())
    assert all(target.startswith("backend.cli.managed.") for target in audit._TARGETS.values())


def test_migrated_top_level_scripts_are_thin_wrappers() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    expected = {
        "baseline_regression_check.py": "backend.cli.managed.baseline_regression_check",
        "fetch_csi1000_pit_by_calendar.py": "backend.cli.managed.fetch_csi1000_pit_by_calendar",
        "report_consistency_check.py": "backend.cli.managed.report_consistency_check",
        "refresh_csi1000_pit.py": "backend.cli.managed.refresh_csi1000_pit",
        "refresh_csi800_pit.py": "backend.cli.managed.refresh_csi800_pit",
        "refresh_security_master.py": "backend.cli.managed.refresh_security_master",
        "update_pams_ohlcv_daily.py": "backend.cli.managed.update_pams_ohlcv_daily",
    }
    for filename, import_target in expected.items():
        text = (repo_root / "backend" / "scripts" / filename).read_text(encoding="utf-8")
        assert import_target in text
        assert "if __name__ == \"__main__\":" in text


def test_top_level_research_scripts_are_removed_from_top_level_surface() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    inventory_path = repo_root / "backend" / "scripts" / "inventory.json"
    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    research_rows = [
        row
        for row in rows
        if isinstance(row, dict)
        and str(row.get("tag") or "") in {"study-definition", "archived-study", "one-off-delete"}
    ]
    assert research_rows == []


def test_migrated_v10_research_wrappers_are_removed_from_top_level_surface() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    removed = [
        "run_v10_residual_structure_s1_research.py",
        "run_v10_onset_ingress_minimal_s2_research.py",
        "run_v10_quality_then_residual_s3_research.py",
        "run_v10_regime_source_minimal_research.py",
        "run_v10_rotation_replace_minimal_research.py",
        "run_v10_upstream_pullback_minimal_research.py",
        "run_v10_conditional_tiebreak_s4_research.py",
        "run_v10_strict_industry_relative_s5_research.py",
        "run_v10_industry_excess_median_s6_research.py",
        "run_v10_industry_second_stage_s7_research.py",
        "run_v10_industry_second_stage_tiebreak_s8_research.py",
        "run_v10_leadership_route_l1_research.py",
        "run_v10_state_conditional_residual_r2_research.py",
        "run_v10_state_conditional_window_r3_research.py",
    ]
    for filename in removed:
        assert not (repo_root / "backend" / "scripts" / filename).exists()


def test_generated_v10_scripts_exist_for_current_migration_batches() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    expected = {
        "run_v10_residual_structure_s1.py": "v10/residual_structure_s1",
        "run_v10_onset_ingress_minimal_s2.py": "v10/onset_ingress_minimal_s2",
        "run_v10_quality_then_residual_s3.py": "v10/quality_then_residual_s3",
        "run_v10_regime_source_minimal_r1.py": "v10/regime_source_minimal_r1",
        "run_v10_rotation_replace_minimal_r1.py": "v10/rotation_replace_minimal_r1",
        "run_v10_upstream_pullback_minimal_p1.py": "v10/upstream_pullback_minimal_p1",
        "run_v10_conditional_tiebreak_s4.py": "v10/conditional_tiebreak_s4",
        "run_v10_strict_industry_relative_s5.py": "v10/strict_industry_relative_s5",
        "run_v10_industry_excess_median_s6.py": "v10/industry_excess_median_s6",
        "run_v10_industry_second_stage_s7.py": "v10/industry_second_stage_s7",
        "run_v10_industry_second_stage_tiebreak_s8.py": "v10/industry_second_stage_tiebreak_s8",
        "run_v10_leadership_route_l1.py": "v10/leadership_route_l1",
        "run_v10_state_conditional_residual_r2.py": "v10/state_conditional_residual_r2",
        "run_v10_state_conditional_window_r3.py": "v10/state_conditional_window_r3",
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
    recorded = {
        str(item.get("study_id") or ""): (
            str(item.get("generated_script") or ""),
            item.get("entry_mode"),
            item.get("legacy_wrapper"),
        )
        for item in studies
        if isinstance(item, dict)
    }
    assert recorded == {
        "v10/residual_structure_s1": ("backend/scripts/generated/run_v10_residual_structure_s1.py", "generated-only", None),
        "v10/onset_ingress_minimal_s2": ("backend/scripts/generated/run_v10_onset_ingress_minimal_s2.py", "generated-only", None),
        "v10/quality_then_residual_s3": ("backend/scripts/generated/run_v10_quality_then_residual_s3.py", "generated-only", None),
    }


def test_inventory_records_second_generated_migration_batch() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    payload = json.loads((repo_root / "backend" / "scripts" / "inventory.json").read_text(encoding="utf-8"))
    batches = payload.get("migration_batches") if isinstance(payload.get("migration_batches"), list) else []
    assert batches
    second_batch = next((row for row in batches if row.get("batch_id") == "2026-03-15-v10-study-second-batch"), None)
    assert isinstance(second_batch, dict)
    assert second_batch.get("status") == "completed"
    studies = second_batch.get("studies") if isinstance(second_batch.get("studies"), list) else []
    recorded = {
        str(item.get("study_id") or ""): (
            str(item.get("generated_script") or ""),
            item.get("entry_mode"),
            item.get("legacy_wrapper"),
        )
        for item in studies
        if isinstance(item, dict)
    }
    assert recorded == {
        "v10/regime_source_minimal_r1": ("backend/scripts/generated/run_v10_regime_source_minimal_r1.py", "generated-only", None),
        "v10/rotation_replace_minimal_r1": ("backend/scripts/generated/run_v10_rotation_replace_minimal_r1.py", "generated-only", None),
        "v10/upstream_pullback_minimal_p1": ("backend/scripts/generated/run_v10_upstream_pullback_minimal_p1.py", "generated-only", None),
    }


def test_inventory_records_third_generated_migration_batch() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    payload = json.loads((repo_root / "backend" / "scripts" / "inventory.json").read_text(encoding="utf-8"))
    batches = payload.get("migration_batches") if isinstance(payload.get("migration_batches"), list) else []
    assert batches
    third_batch = next((row for row in batches if row.get("batch_id") == "2026-03-15-v10-study-third-batch"), None)
    assert isinstance(third_batch, dict)
    assert third_batch.get("status") == "completed"
    studies = third_batch.get("studies") if isinstance(third_batch.get("studies"), list) else []
    recorded = {
        str(item.get("study_id") or ""): (
            str(item.get("generated_script") or ""),
            item.get("entry_mode"),
            item.get("legacy_wrapper"),
        )
        for item in studies
        if isinstance(item, dict)
    }
    assert recorded == {
        "v10/conditional_tiebreak_s4": ("backend/scripts/generated/run_v10_conditional_tiebreak_s4.py", "generated-only", None),
        "v10/strict_industry_relative_s5": ("backend/scripts/generated/run_v10_strict_industry_relative_s5.py", "generated-only", None),
        "v10/industry_excess_median_s6": ("backend/scripts/generated/run_v10_industry_excess_median_s6.py", "generated-only", None),
    }


def test_every_current_study_has_generated_thin_script() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    studies_root = repo_root / "research" / "studies"
    generated_root = repo_root / "backend" / "scripts" / "generated"
    expected = set()
    for study_path in studies_root.rglob("*.study.yaml"):
        relative = study_path.relative_to(studies_root).with_suffix("").with_suffix("")
        parts = [part for part in relative.parts if part]
        expected.add("run_" + "_".join(parts) + ".py")
    actual = {path.name for path in generated_root.glob("run_*.py")}
    assert expected <= actual


def test_inventory_records_fourth_generated_migration_batch() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    payload = json.loads((repo_root / "backend" / "scripts" / "inventory.json").read_text(encoding="utf-8"))
    batches = payload.get("migration_batches") if isinstance(payload.get("migration_batches"), list) else []
    assert batches
    fourth_batch = next((row for row in batches if row.get("batch_id") == "2026-03-15-v10-study-fourth-batch"), None)
    assert isinstance(fourth_batch, dict)
    assert fourth_batch.get("status") == "completed"
    studies = fourth_batch.get("studies") if isinstance(fourth_batch.get("studies"), list) else []
    recorded = {
        str(item.get("study_id") or ""): (
            str(item.get("generated_script") or ""),
            item.get("entry_mode"),
            item.get("legacy_wrapper"),
        )
        for item in studies
        if isinstance(item, dict)
    }
    assert recorded == {
        "v10/industry_second_stage_s7": ("backend/scripts/generated/run_v10_industry_second_stage_s7.py", "generated-only", None),
        "v10/industry_second_stage_tiebreak_s8": ("backend/scripts/generated/run_v10_industry_second_stage_tiebreak_s8.py", "generated-only", None),
        "v10/leadership_route_l1": ("backend/scripts/generated/run_v10_leadership_route_l1.py", "generated-only", None),
    }


def test_inventory_records_fifth_generated_migration_batch() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    payload = json.loads((repo_root / "backend" / "scripts" / "inventory.json").read_text(encoding="utf-8"))
    batches = payload.get("migration_batches") if isinstance(payload.get("migration_batches"), list) else []
    assert batches
    fifth_batch = next((row for row in batches if row.get("batch_id") == "2026-03-15-v10-study-fifth-batch"), None)
    assert isinstance(fifth_batch, dict)
    assert fifth_batch.get("status") == "completed"
    studies = fifth_batch.get("studies") if isinstance(fifth_batch.get("studies"), list) else []
    recorded = {
        str(item.get("study_id") or ""): (
            str(item.get("generated_script") or ""),
            item.get("entry_mode"),
            item.get("legacy_wrapper"),
        )
        for item in studies
        if isinstance(item, dict)
    }
    assert recorded == {
        "v10/state_conditional_residual_r2": ("backend/scripts/generated/run_v10_state_conditional_residual_r2.py", "generated-only", None),
        "v10/state_conditional_window_r3": ("backend/scripts/generated/run_v10_state_conditional_window_r3.py", "generated-only", None),
    }
