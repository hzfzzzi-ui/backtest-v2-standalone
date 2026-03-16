from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from backend.research import study_loader
from backend.research import study_runner


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


_STORED_PAYLOAD_ROOTS = {
    "v10_residual_structure_s1": "v10_residual_structure_s1_20260313",
    "v10_onset_ingress_minimal_s2": "v10_onset_ingress_minimal_s2_20260313",
    "v10_quality_then_residual_s3": "v10_quality_then_residual_s3_20260313",
    "v10_conditional_tiebreak_s4": "v10_conditional_tiebreak_s4_20260313",
    "v10_strict_industry_relative_s5": "v10_strict_industry_relative_s5_20260314",
    "v10_industry_excess_median_s6": "v10_industry_excess_median_s6_20260314",
    "v10_industry_second_stage_s7": "v10_industry_second_stage_s7_20260314",
    "v10_industry_second_stage_tiebreak_s8": "v10_industry_second_stage_tiebreak_s8_20260314",
    "v10_leadership_route_l1": "v10_leadership_route_l1_20260314",
    "v10_state_conditional_residual_r2": "v10_state_conditional_residual_r2_20260314",
    "v10_state_conditional_window_r3": "v10_state_conditional_window_r3_20260314",
}


def _stored_request_payload(study_slug: str, window_key: str, variant_name: str) -> dict[str, object]:
    root_dir = _STORED_PAYLOAD_ROOTS[study_slug]
    ops_root = _repo_root() / "outputs" / "ops" / root_dir / window_key
    direct_path = ops_root / f"request_payload_{variant_name}.json"
    nested_path = ops_root / variant_name / "request_payload.json"
    path = direct_path if direct_path.exists() else nested_path
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _script_dry_run(script_rel_path: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, script_rel_path, "--dry-run"],
        cwd=str(_repo_root()),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


def _plan_map(rows: list[dict[str, object]]) -> dict[tuple[str, str], dict[str, object]]:
    return {
        (str(row["window_key"]), str(row["variant_name"])): dict(row["request_payload"])
        for row in rows
    }


def _assert_runtime_equivalent(left: dict[str, object], right: dict[str, object]) -> None:
    right_run_params = right.get("run_params") if isinstance(right.get("run_params"), dict) else {}
    right_config = right.get("config_json") if isinstance(right.get("config_json"), dict) else {}
    right_flow_script = right_config.get("flow_script") if isinstance(right_config.get("flow_script"), dict) else {}
    right_preset = right.get("preset")
    if right_preset is None:
        right_preset = right_run_params.get("recommended_preset")
    if right_preset is None:
        right_preset = right_flow_script.get("recommended_preset")
    right_fast_mode = right.get("fast_mode")
    if right_fast_mode is None:
        right_fast_mode = right_run_params.get("fast_mode")
    assert left.get("preset") == right_preset
    assert left.get("fast_mode") == right_fast_mode
    if "asset_scope" in right:
        assert left.get("asset_scope") == right.get("asset_scope")
    assert left.get("config_json") == right.get("config_json")


def test_current_study_assets_declare_asset_scope() -> None:
    studies_root = _repo_root() / "research" / "studies"
    for study_path in studies_root.rglob("*.study.yaml"):
        text = study_path.read_text(encoding="utf-8")
        assert "asset_scope: cn_a_equity" in text


def test_residual_structure_s1_study_matches_script_dry_run_and_stored_payload() -> None:
    study = study_loader.load_study_definition("v10/residual_structure_s1")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/generated/run_v10_residual_structure_s1.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for variant in ("B0", "S1_B70_I30"):
        key = ("1626", variant)
        stored = _stored_request_payload("v10_residual_structure_s1", "1626", variant)
        _assert_runtime_equivalent(expected[key], actual[key])
        _assert_runtime_equivalent(expected[key], stored)


def test_onset_ingress_s2_study_matches_script_dry_run_and_stored_payload() -> None:
    study = study_loader.load_study_definition("v10/onset_ingress_minimal_s2")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/generated/run_v10_onset_ingress_minimal_s2.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for variant in ("B0", "S2_A_30_45"):
        key = ("1626", variant)
        stored = _stored_request_payload("v10_onset_ingress_minimal_s2", "1626", variant)
        _assert_runtime_equivalent(expected[key], actual[key])
        _assert_runtime_equivalent(expected[key], stored)


def test_quality_then_residual_s3_study_matches_script_dry_run_and_stored_payload() -> None:
    study = study_loader.load_study_definition("v10/quality_then_residual_s3")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/generated/run_v10_quality_then_residual_s3.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for variant in ("B0", "S3_A_Q55"):
        key = ("1626", variant)
        stored = _stored_request_payload("v10_quality_then_residual_s3", "1626", variant)
        _assert_runtime_equivalent(expected[key], actual[key])
        _assert_runtime_equivalent(expected[key], stored)


def test_regime_source_minimal_r1_study_matches_generated_entry_dry_run() -> None:
    study = study_loader.load_study_definition("v10/regime_source_minimal_r1")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/generated/run_v10_regime_source_minimal_r1.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for variant in ("B0_HS300", "R_BREADTH_REGIME"):
        key = ("1626", variant)
        _assert_runtime_equivalent(expected[key], actual[key])


def test_rotation_replace_minimal_r1_study_matches_generated_entry_dry_run() -> None:
    study = study_loader.load_study_definition("v10/rotation_replace_minimal_r1")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/generated/run_v10_rotation_replace_minimal_r1.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for key in (("1626", "B0"), ("1626", "R1"), ("0717", "R1b")):
        _assert_runtime_equivalent(expected[key], actual[key])


def test_upstream_pullback_minimal_p1_study_matches_generated_entry_dry_run() -> None:
    study = study_loader.load_study_definition("v10/upstream_pullback_minimal_p1")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/generated/run_v10_upstream_pullback_minimal_p1.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for key in (("1626", "B0"), ("1626", "P1"), ("0717", "P1b")):
        _assert_runtime_equivalent(expected[key], actual[key])


def test_conditional_tiebreak_s4_study_matches_generated_entry_and_stored_payload() -> None:
    study = study_loader.load_study_definition("v10/conditional_tiebreak_s4")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/generated/run_v10_conditional_tiebreak_s4.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for key in (("1626", "B0"), ("1626", "S4_A_TB10"), ("0717", "S4_B_TB20")):
        stored = _stored_request_payload("v10_conditional_tiebreak_s4", key[0], key[1])
        _assert_runtime_equivalent(expected[key], actual[key])
        _assert_runtime_equivalent(expected[key], stored)


def test_strict_industry_relative_s5_study_matches_generated_entry_and_stored_payload() -> None:
    study = study_loader.load_study_definition("v10/strict_industry_relative_s5")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/generated/run_v10_strict_industry_relative_s5.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for key in (("1626", "B0"), ("1626", "S5_A_STRICT_INDUSTRY_RANK"), ("0717", "S5_B_STRICT_INDUSTRY_RANK_STRONG")):
        stored = _stored_request_payload("v10_strict_industry_relative_s5", key[0], key[1])
        _assert_runtime_equivalent(expected[key], actual[key])
        _assert_runtime_equivalent(expected[key], stored)


def test_industry_excess_median_s6_study_matches_generated_entry_and_stored_payload() -> None:
    study = study_loader.load_study_definition("v10/industry_excess_median_s6")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/generated/run_v10_industry_excess_median_s6.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for key in (("1626", "B0"), ("1626", "S6_A_INDUSTRY_EXCESS_MEDIAN"), ("0717", "S6_B_INDUSTRY_EXCESS_MEDIAN_STRONG")):
        stored = _stored_request_payload("v10_industry_excess_median_s6", key[0], key[1])
        _assert_runtime_equivalent(expected[key], actual[key])
        _assert_runtime_equivalent(expected[key], stored)


def test_industry_second_stage_s7_study_matches_generated_entry_and_stored_payload() -> None:
    study = study_loader.load_study_definition("v10/industry_second_stage_s7")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/generated/run_v10_industry_second_stage_s7.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for key in (("1626", "B0"), ("1626", "S7_A_SOFT15"), ("0717", "S7_B_SOFT25")):
        stored = _stored_request_payload("v10_industry_second_stage_s7", key[0], key[1])
        _assert_runtime_equivalent(expected[key], actual[key])
        _assert_runtime_equivalent(expected[key], stored)


def test_industry_second_stage_tiebreak_s8_study_matches_generated_entry_and_stored_payload() -> None:
    study = study_loader.load_study_definition("v10/industry_second_stage_tiebreak_s8")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/generated/run_v10_industry_second_stage_tiebreak_s8.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for key in (("1626", "B0"), ("1626", "S8_A_TB85"), ("0717", "S8_B_TB90")):
        stored = _stored_request_payload("v10_industry_second_stage_tiebreak_s8", key[0], key[1])
        _assert_runtime_equivalent(expected[key], actual[key])
        _assert_runtime_equivalent(expected[key], stored)


def test_leadership_route_l1_study_matches_generated_entry_and_stored_payload() -> None:
    study = study_loader.load_study_definition("v10/leadership_route_l1")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/generated/run_v10_leadership_route_l1.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for key in (("1626", "B0"), ("1626", "L1_A_BUCKET2"), ("0717", "L1_B_BUCKET3")):
        stored = _stored_request_payload("v10_leadership_route_l1", key[0], key[1])
        _assert_runtime_equivalent(expected[key], actual[key])
        _assert_runtime_equivalent(expected[key], stored)


def test_state_conditional_residual_r2_study_matches_generated_entry_and_stored_payload() -> None:
    study = study_loader.load_study_definition("v10/state_conditional_residual_r2")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/generated/run_v10_state_conditional_residual_r2.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for key in (("1626", "B0"), ("1626", "R2_A_STRONG_IND_ONLY"), ("0717", "R2_B_STRONG_B30_I70")):
        stored = _stored_request_payload("v10_state_conditional_residual_r2", key[0], key[1])
        _assert_runtime_equivalent(expected[key], actual[key])
        _assert_runtime_equivalent(expected[key], stored)


def test_state_conditional_window_r3_study_matches_generated_entry_and_stored_payload() -> None:
    study = study_loader.load_study_definition("v10/state_conditional_window_r3")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/generated/run_v10_state_conditional_window_r3.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for key in (("1626", "B0"), ("1626", "R3_A_STRONG40_ELSE60"), ("0717", "R3_B_STRONG40_ELSE80")):
        stored = _stored_request_payload("v10_state_conditional_window_r3", key[0], key[1])
        _assert_runtime_equivalent(expected[key], actual[key])
        _assert_runtime_equivalent(expected[key], stored)


def test_current_study_assets_do_not_keep_legacy_script_metadata() -> None:
    studies_root = _repo_root() / "research" / "studies"
    for study_path in studies_root.rglob("*.study.yaml"):
        text = study_path.read_text(encoding="utf-8")
        assert "legacy_script:" not in text
