from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from backend.research import study_loader
from backend.research import study_runner


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _stored_request_payload(study_slug: str, window_key: str, variant_name: str) -> dict[str, object]:
    path = (
        _repo_root()
        / "outputs"
        / "ops"
        / f"{study_slug}_20260313"
        / window_key
        / f"request_payload_{variant_name}.json"
    )
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
    assert left.get("preset") == right.get("preset")
    assert left.get("fast_mode") == right.get("fast_mode")
    assert left.get("config_json") == right.get("config_json")


def test_residual_structure_s1_study_matches_script_dry_run_and_stored_payload() -> None:
    study = study_loader.load_study_definition("v10/residual_structure_s1")
    expected = _plan_map(study_runner.build_execution_plan(study))
    script_payload = _script_dry_run("backend/scripts/run_v10_residual_structure_s1_research.py")
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
    script_payload = _script_dry_run("backend/scripts/run_v10_onset_ingress_minimal_s2_research.py")
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
    script_payload = _script_dry_run("backend/scripts/run_v10_quality_then_residual_s3_research.py")
    assert script_payload["study"]["study_id"] == study.study_id
    actual = _plan_map(list(script_payload["plan"]))

    for variant in ("B0", "S3_A_Q55"):
        key = ("1626", variant)
        stored = _stored_request_payload("v10_quality_then_residual_s3", "1626", variant)
        _assert_runtime_equivalent(expected[key], actual[key])
        _assert_runtime_equivalent(expected[key], stored)
