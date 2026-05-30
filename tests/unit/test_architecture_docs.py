from __future__ import annotations

import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(*parts: str) -> str:
    return _repo_root().joinpath(*parts).read_text(encoding="utf-8", errors="ignore")


def test_architecture_doc_covers_main_paths_and_entrypoints() -> None:
    source = _read("docs", "02_系统架构设计", "全系统架构设计.md")
    for marker in (
        "backend/api/",
        "backend/core/",
        "backend/research/",
        "frontend/",
        "tests/",
        "openspec/",
        "outputs/",
        "frontend/index.html",
        "frontend/assets/js/desktop-shell/host.js",
        "execution_contract",
    ):
        assert marker in source


def test_schema_docs_and_runbook_exist() -> None:
    repo_root = _repo_root()
    for rel in (
        "docs/01_系统接口模块定义/产物协议/行明细产物协议.md",
        "docs/01_系统接口模块定义/产物协议/运行元数据产物协议.md",
        "docs/01_系统接口模块定义/产物协议/清单产物协议.md",
        "docs/02_系统架构设计/运行与基线/基线回归运行手册.md",
    ):
        assert repo_root.joinpath(rel).exists(), rel


def test_guardrails_reference_real_docs_and_examples() -> None:
    source = _read("docs", "01_系统接口模块定义", "架构守门", "架构守门规则.md")
    for marker in (
        "host.js -> runtime-surface.js -> app-shell.js",
        "execution_contract",
        "manifest.json",
        "run_meta.json",
    ):
        assert marker in source


def test_architecture_map_and_boundary_rules_cover_current_owner_surfaces() -> None:
    source = _read("docs", "02_系统架构设计", "架构地图与边界规则.md")
    for marker in (
        "backend.api.shared.json_utils",
        "backend.core.shared.json_utils",
        "backend.core.shared.artifact_io",
        "backend.core.contracts.artifacts",
        "backend.core.services.experiment_manifest_service",
        "backend.core.services.experiment_output_helpers",
        "backend.core.services.experiment_index_service",
        "backend.core.services.backtest_data_surface_helpers",
        "backend.core.services.experiment_public_run_surface",
        "backend.core.services.experiment_artifacts_finalize_helpers",
        "backend.core.config.semantic_config_compiler",
        "backend.core.config.builtin_config_library",
        "backend.core.config.runtime_config_bundle",
        "backend.core.studies",
        "backend.core.contracts.requests.BacktestV2ExperimentRequest",
        "backend.core.services.locked_candidate_runtime_service",
        "backend.api.backtest_v2.artifacts_impl",
        "backend.api.backtest_v2.semantic_config_schema",
        "backend.api.backtest_v2.builtin_config_library",
        "backend.api.backtest_v2.runner_config_*",
        "outputs/",
        "pytest tests\\unit\\test_shared_helper_boundary.py -q",
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
