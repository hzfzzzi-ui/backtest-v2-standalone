from __future__ import annotations

import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(*parts: str) -> str:
    return _repo_root().joinpath(*parts).read_text(encoding="utf-8", errors="ignore")


def test_architecture_doc_covers_main_paths_and_entrypoints() -> None:
    source = _read("ARCHITECTURE.md")
    for marker in (
        "backend/api",
        "backend/core",
        "backend/research",
        "frontend",
        "research",
        "tests",
        "openspec",
        "backend/scripts",
        "outputs",
        "backend/main.py",
        "python -m backend.cli",
        "frontend/index.html",
        "backend/core/services/experiment_history_service.py",
    ):
        assert marker in source


def test_schema_docs_and_runbook_exist() -> None:
    repo_root = _repo_root()
    for rel in (
        "docs/SCHEMA_rows.json.md",
        "docs/SCHEMA_run_meta.json.md",
        "docs/SCHEMA_manifest.json.md",
        "docs/RUNBOOK_baseline_regression.md",
    ):
        assert repo_root.joinpath(rel).exists(), rel


def test_guardrails_reference_real_docs_and_examples() -> None:
    source = _read("ARCHITECTURE_GUARDRAILS.md")
    for marker in (
        "docs/SCHEMA_rows.json.md",
        "docs/SCHEMA_run_meta.json.md",
        "docs/SCHEMA_manifest.json.md",
        "docs/RUNBOOK_baseline_regression.md",
        "examples/experiment_contract_minimal/",
        "tests/integration/test_schema_and_artifacts.py",
    ):
        assert marker in source


def test_example_experiment_contract_minimal_exists_and_is_parseable() -> None:
    root = _repo_root().joinpath("examples", "experiment_contract_minimal")
    for rel in (
        "manifest.json",
        "run_meta.json",
        "perf.json",
        "config.json",
        "nav.csv",
        "funnel.csv",
        "reason_codes.csv",
    ):
        assert root.joinpath(rel).exists(), rel

    manifest = json.loads(root.joinpath("manifest.json").read_text(encoding="utf-8"))
    run_meta = json.loads(root.joinpath("run_meta.json").read_text(encoding="utf-8"))
    perf = json.loads(root.joinpath("perf.json").read_text(encoding="utf-8"))
    config = json.loads(root.joinpath("config.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == "backtest_v2_experiment_manifest@2"
    assert manifest["core_artifacts"]["run_meta"] == "run_meta.json"
    assert run_meta["counters"]["raw_signal"] == 2
    assert run_meta["asset_context"]["asset_scope"] == "cn_a_equity"
    assert perf["effective_execution_start_date"] == "2024-01-03"
    assert config["base_config"]["signal"]["strategy"] == "EMA_CROSS"
