from __future__ import annotations

import json
from pathlib import Path


FORMAL_CN_NAME = "个人多资产趋势配置系统"
FORMAL_EN_NAME = "OpenClaw Personal Multi-Asset Trend Allocation System"
DEPRECATED_FORMAL_NAMES = (
    "专业量化研究平台",
    "OpenClaw Quant Research Platform",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(*parts: str) -> str:
    return _repo_root().joinpath(*parts).read_text(encoding="utf-8", errors="ignore")


def _has_checked_line_with(checklist: str, *tokens: str) -> bool:
    return any(
        line.startswith("- [x]") and all(token in line for token in tokens)
        for line in checklist.splitlines()
    )


def test_root_readme_uses_formal_product_positioning() -> None:
    source = _read("README.md")

    assert source.startswith(f"# {FORMAL_EN_NAME}")
    assert f"**{FORMAL_CN_NAME}**" in source
    assert "受研究纪律约束" in source
    assert "不加杠杆" in source
    assert "不作为个人资产管理或记账系统" in source
    assert "PAMS 系统承接" in source
    assert "`outputs/` 运行产物" in source

    for deprecated_name in DEPRECATED_FORMAL_NAMES:
        assert deprecated_name not in source


def test_product_launch_docs_keep_formal_positioning_consistent() -> None:
    required_docs = (
        ("docs", "product_launch", "README.md"),
        ("docs", "product_launch", "FEATURES.md"),
        ("docs", "product_launch", "ARCHITECTURE.md"),
        ("docs", "product_launch", "MODULE_OWNERSHIP.md"),
        ("docs", "product_launch", "NAMING_AND_DEPRECATION.md"),
        ("docs", "product_launch", "RELEASE_CHECKLIST.md"),
    )

    for rel_parts in required_docs:
        source = _read(*rel_parts)
        assert FORMAL_CN_NAME in source, "/".join(rel_parts)
        for deprecated_name in DEPRECATED_FORMAL_NAMES:
            assert deprecated_name not in source, "/".join(rel_parts)

    product_readme = _read("docs", "product_launch", "README.md")
    naming_doc = _read("docs", "product_launch", "NAMING_AND_DEPRECATION.md")
    architecture_doc = _read("docs", "product_launch", "ARCHITECTURE.md")

    assert FORMAL_EN_NAME in product_readme
    assert FORMAL_EN_NAME in naming_doc
    assert FORMAL_EN_NAME in architecture_doc
    assert "openclaw-personal-multi-asset-trend-allocation" in product_readme
    assert "openclaw-personal-multi-asset-trend-allocation" in naming_doc


def test_pams_externalization_checklist_matches_boundary_registry() -> None:
    from backend.core.services.service_boundary_status import SERVICE_BOUNDARY_BY_MODULE

    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    contract_path = _repo_root().joinpath(
        "docs",
        "product_launch",
        "contracts",
        "daily_position_adjustment_package_v1.md",
    )

    assert SERVICE_BOUNDARY_BY_MODULE["backend.api.mobile"].target_system == "pams"
    assert SERVICE_BOUNDARY_BY_MODULE["backend.api.mobile"].launch_status == "externalize_to_pams"
    assert SERVICE_BOUNDARY_BY_MODULE["backend.core.services.mobile_ops_service"].target_system == "pams"
    assert SERVICE_BOUNDARY_BY_MODULE["backend.core.services.sim_account_service"].launch_status == "compat_audit_only"
    assert SERVICE_BOUNDARY_BY_MODULE["backend.core.services.transaction_lifecycle_service"].target_system == "pams"
    assert contract_path.exists()

    for checked_item in (
        "`api.mobile` 不属于正式研究平台主路径。",
        "`mobile_*` services 标记为 externalized_to_pams 或 deprecated。",
        "`sim_account` 不作为账户真值。",
        "`transaction_lifecycle_service` 不作为研究平台正式交易主表 owner。",
        "调仓包合同存在。",
        "PAMS 是正式通知、审批、执行状态 owner。",
    ):
        assert f"- [x] {checked_item}" in checklist


def test_naming_governance_checklist_matches_naming_doc() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    naming_doc = _read("docs", "product_launch", "NAMING_AND_DEPRECATION.md")

    for marker in (
        FORMAL_EN_NAME,
        "个人多资产趋势配置系统",
        "`openclaw-personal-multi-asset-trend-allocation`",
        "当前名称废弃",
        "`pams_` 作为研究平台正式对象前缀",
        "`shadow` | `diagnostic_probe`",
        "`AB` | `controlled_experiment`",
    ):
        assert marker in naming_doc

    for checked_item in (
        "新增正式命名清单。",
        "新增废弃命名清单。",
        "`backtest_V2_standalone` 不再作为产品名。",
        "`PAMS/pams_` 不再作为研究平台正式命名前缀。",
        "`shadow` 和 `AB` 已映射到 `diagnostic_probe` 和 `controlled_experiment`。",
    ):
        assert f"- [x] {checked_item}" in checklist


def test_testing_audit_checklist_matches_boundary_tests() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    api_boundary_tests = _read("tests", "unit", "test_api_compat_boundaries.py")

    for marker in (
        "test_api_method_path_pairs_have_single_owner",
        "test_http_decorators_stay_in_route_owner_modules",
        "test_api_impl_modules_do_not_declare_route_owners",
        "test_api_layer_does_not_import_route_functions_from_other_routes",
        "test_pams_transition_boundary_registry_covers_legacy_services",
        "test_mobile_surface_declares_compat_internal_preview_boundary",
    ):
        assert marker in api_boundary_tests

    for checked_item in (
        "边界测试覆盖 API route owner。",
        "边界测试覆盖 PAMS/mobile/sim_account 禁止主路径新增引用。",
    ):
        assert f"- [x] {checked_item}" in checklist


def test_api_schema_checklist_matches_contract_boundary_tests() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    api_schema_tests = _read("tests", "unit", "test_api_schema_contracts.py")

    for marker in (
        "test_api_query_contracts_reexport_core_owner",
        "test_api_query_contracts_expose_pydantic_schema",
    ):
        assert marker in api_schema_tests

    assert _has_checked_line_with(checklist, "API schema")


def test_frontend_checklist_matches_frontend_boundary_tests() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    frontend_tests = _read("tests", "unit", "test_frontend_runtime_boundaries.py")
    module_ownership = _read("docs", "product_launch", "MODULE_OWNERSHIP.md")

    for marker in (
        "test_research_workbench_uses_api_adapter_instead_of_direct_fetch",
        "test_results_workspace_uses_canonical_surface_sections",
        "test_mobile_shell_uses_mobile_owner_and_shared_api_only",
        "test_frontend_chart_data_comes_from_platform_api_not_vendors",
    ):
        assert marker in frontend_tests

    assert "`frontend/mobile*` | 不进入研究平台正式主路径" in module_ownership

    for checked_item in (
        "Research Workbench 只消费 API 和 artifact surface。",
        "移动端资产/审批页面不属于研究平台正式上线范围。",
        "图表数据来自平台 API，不直连供应商数据。",
    ):
        assert f"- [x] {checked_item}" in checklist


def test_data_chain_checklist_matches_source_matrix_and_freshness_tests() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    source_matrix_path = _repo_root().joinpath("docs", "02_系统架构设计", "数据库", "v2_source_matrix.md")
    source_matrix = source_matrix_path.read_text(encoding="utf-8", errors="ignore")
    sync_service_tests = _read("tests", "unit", "test_market_data_sync_service.py")
    sync_api_tests = _read("tests", "integration", "test_market_data_sync_api.py")

    for marker in (
        "Tushare trade_cal",
        "Tushare daily",
        "Tushare adj_factor",
        "Tushare daily_basic",
        "Tushare suspend_d",
        "source matrix",
    ):
        assert marker in source_matrix

    for marker in (
        "test_build_market_data_sync_status_returns_fresh",
        "test_build_market_data_sync_status_returns_failed_when_db_unavailable",
        "test_build_market_data_sync_status_returns_unsupported_for_us_equity",
    ):
        assert marker in sync_service_tests

    assert "test_market_data_sync_status_endpoint_returns_thin_status_payload" in sync_api_tests
    assert "test_market_data_sync_status_endpoint_passes_asset_scope_query" in sync_api_tests

    for checked_item in (
        "字段 source matrix 存在。",
        "数据 freshness 状态可查询。",
    ):
        assert f"- [x] {checked_item}" in checklist


def test_research_artifact_checklist_matches_artifact_contract_tests() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    artifact_sync_tests = _read("tests", "integration", "test_backtest_v2_experiment_artifacts.py")
    schema_artifact_tests = _read("tests", "integration", "test_schema_and_artifacts.py")
    example_manifest = json.loads(
        _read("examples", "experiment_contract_minimal", "manifest.json")
    )

    for marker in (
        "test_experiment_sync_writes_manifest_and_group_files",
        '"run_meta", "perf", "nav", "funnel", "reason_codes", "config"',
    ):
        assert marker in artifact_sync_tests

    for marker in (
        "test_canonical_artifact_contract_and_missing_fields",
        "test_reason_codes_and_counters_are_canonical_only",
        "test_run_meta_report_consistency_defaults_to_canonical_market_contract",
    ):
        assert marker in schema_artifact_tests

    for contract_key in ("artifacts", "core_artifacts"):
        artifact_refs = example_manifest[contract_key]
        for artifact_key in ("run_meta", "perf", "nav", "funnel", "reason_codes"):
            rel_path = Path(artifact_refs[artifact_key])
            assert not rel_path.is_absolute()
            assert ".." not in rel_path.parts

    assert _has_checked_line_with(checklist, "`run_meta.json`")
    assert _has_checked_line_with(checklist, "manifest")
    assert _has_checked_line_with(checklist, "perf/nav/funnel/reason codes")
    assert _has_checked_line_with(checklist, "artifact")
