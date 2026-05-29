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


def _has_unchecked_line_with(checklist: str, *tokens: str) -> bool:
    return any(
        line.startswith("- [ ]") and all(token in line for token in tokens)
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
    assert "不是生产 READY 声明" in source
    assert "iFinD / TradingView / IBKR 的正式生产接入" in source

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
    assert "本仓库不是生产 READY 状态" in product_readme
    assert "iFinD、TradingView、IBKR" in product_readme


def test_release_checklist_tracks_current_not_ready_items() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")

    assert "本仓库不是生产 READY 状态" in checklist
    assert _has_unchecked_line_with(checklist, "backtest_V2_standalone", "仓库")
    assert _has_unchecked_line_with(checklist, "pams_ohlcv_daily_v2", "canonical market")
    assert _has_unchecked_line_with(checklist, "iFinD raw vendor 同步器未实现")
    assert _has_unchecked_line_with(checklist, "TradingView", "IBKR", "未实现生产数据接入")
    assert _has_unchecked_line_with(checklist, "PAMS app/web", "端到端验证")
    assert _has_unchecked_line_with(checklist, "OpenSpec", "用户确认项仍未完成")
    assert _has_unchecked_line_with(checklist, "clean worktree", "全量 CI")


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
    ):
        assert f"- [x] {checked_item}" in checklist

    assert _has_unchecked_line_with(
        checklist,
        "PAMS app/web",
        "通知",
        "审批",
        "端到端验证",
    )


def test_naming_governance_checklist_matches_naming_doc() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    naming_doc = _read("docs", "product_launch", "NAMING_AND_DEPRECATION.md")

    for marker in (
        FORMAL_EN_NAME,
        "个人多资产趋势配置系统",
        "`openclaw-personal-multi-asset-trend-allocation`",
        "仓库目录尚未迁移",
        "`pams_` 作为研究平台正式对象前缀",
        "`shadow` | `diagnostic_probe`",
        "`AB` | `controlled_experiment`",
        "`pams_cn_etf_daily`",
    ):
        assert marker in naming_doc

    for checked_item in (
        "新增正式命名清单。",
        "新增废弃命名清单。",
        "文档不再把 `backtest_V2_standalone` 作为产品名。",
        "文档不再把 `PAMS/pams_` 作为研究平台正式命名前缀。",
        "`shadow` 和 `AB` 已映射到 `diagnostic_probe` 和 `controlled_experiment`。",
    ):
        assert f"- [x] {checked_item}" in checklist

    assert _has_unchecked_line_with(checklist, "`backtest_V2_standalone`", "尚未完成")
    assert _has_unchecked_line_with(checklist, "`pams_ohlcv_daily_v2`", "尚未完成")


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


def test_api_json_safety_checklist_matches_safe_response_tests() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    api_json_tests = _read("tests", "unit", "test_api_json_safety.py")
    safe_response = _read("backend", "api", "shared", "safe_json_response.py")

    for marker in (
        "test_api_json_sanitizer_removes_nonfinite_values",
        "test_safe_json_response_renders_nonfinite_values_as_null",
        "test_formal_api_routers_use_safe_json_response",
        "test_backtest_v2_router_sanitizes_service_payload",
        "test_mobile_router_sanitizes_service_payload",
    ):
        assert marker in api_json_tests

    assert "sanitize_for_json(content)" in safe_response
    assert _has_checked_line_with(checklist, "API 返回无 NaN/Inf")


def test_frontend_checklist_matches_frontend_boundary_tests() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    frontend_tests = _read("tests", "unit", "test_frontend_runtime_boundaries.py")
    module_ownership = _read("docs", "product_launch", "MODULE_OWNERSHIP.md")

    for marker in (
        "test_research_workbench_uses_api_adapter_instead_of_direct_fetch",
        "test_results_workspace_uses_canonical_surface_sections",
        "test_frontend_core_research_math_is_backend_owned_or_display_only",
        "test_mobile_shell_uses_mobile_owner_and_shared_api_only",
        "test_frontend_chart_data_comes_from_platform_api_not_vendors",
    ):
        assert marker in frontend_tests

    assert "`frontend/mobile*` | 不进入研究平台正式主路径" in module_ownership

    for checked_item in (
        "Research Workbench 只消费 API 和 artifact surface。",
        "前端不重算核心研究口径。",
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


def test_vendor_raw_checklist_matches_tushare_raw_contract_and_ifind_boundary() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    features_doc = _read("docs", "product_launch", "FEATURES.md")
    architecture_doc = _read("docs", "product_launch", "ARCHITECTURE.md")
    vendor_raw_contract = _read(
        "docs",
        "product_launch",
        "contracts",
        "market_data_vendor_raw_v1.md",
    )
    raw_tests = _read("tests", "unit", "test_update_pams_ohlcv_daily_v2_raw.py")
    raw_common = _read("backend", "cli", "managed", "pams_ohlcv_daily_v2_common.py")
    raw_updater = _read("backend", "cli", "managed", "update_pams_ohlcv_daily_v2_raw.py")
    raw_sql = _read("docs", "02_系统架构设计", "数据库", "pams_ohlcv_daily_v2_apply.sql")

    for marker in (
        "Tushare raw vendor 接入",
        "iFinD 仅有 raw vendor 预留合同",
        "TradingView 不作为本仓库数据真值",
    ):
        assert marker in features_doc

    for marker in (
        "Tushare | implemented | `raw_tushare_*`",
        "iFinD | reserved | `raw_ifind_*`",
        "未实现正式同步器",
        "vendor API / files -> raw vendor tables -> quality checks -> canonical_market -> market_data_access",
    ):
        assert marker in vendor_raw_contract

    assert 'IFIND["iFinD 预留"]' in architecture_doc
    assert 'RawTushare["raw_tushare_*"]' in architecture_doc
    assert "IFIND -.接入前必须新增同步器和测试.-> RawReserved" in architecture_doc
    assert "test_tushare_source_tables_land_in_raw_vendor_namespace" in raw_tests

    for table in (
        "raw_tushare_stock_basic",
        "raw_tushare_trade_cal",
        "raw_tushare_daily",
        "raw_tushare_adj_factor",
        "raw_tushare_daily_basic",
        "raw_tushare_suspend_d",
        "raw_tushare_stk_limit",
        "raw_tushare_moneyflow",
    ):
        assert table in raw_common
        assert table in raw_sql

    assert "SOURCE_TABLES = {" in raw_updater
    assert _has_checked_line_with(checklist, "Tushare", "raw vendor")
    assert _has_unchecked_line_with(checklist, "iFinD raw vendor 同步器未实现")


def test_research_artifact_checklist_matches_artifact_contract_tests() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    artifact_sync_tests = _read("tests", "integration", "test_backtest_v2_experiment_artifacts.py")
    schema_artifact_tests = _read("tests", "integration", "test_schema_and_artifacts.py")
    artifact_contract_tests = _read("tests", "unit", "test_experiment_artifact_contract.py")
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

    for marker in (
        "test_validate_experiment_artifact_dir_accepts_minimal_contract",
        "test_validate_experiment_artifact_dir_rejects_absolute_manifest_artifact_path",
        "test_validate_experiment_artifact_dir_rejects_missing_required_artifact",
        "test_validate_experiment_artifact_dir_rejects_invalid_csv_schema",
    ):
        assert marker in artifact_contract_tests

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
    assert _has_checked_line_with(checklist, "schema", "校验")


def test_baseline_regression_checklist_matches_cli_and_contract_tests() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    baseline_tests = _read("tests", "unit", "test_baseline_regression_check.py")
    cli_tests = _read("tests", "unit", "test_baseline_regression_cli.py")
    closure_doc = _read("docs", "architecture_closure_gates.md")

    for marker in (
        "test_load_contract_has_foundation_baseline",
        "test_current_combo_baseline_main_logic_has_regression_contract",
        "test_compare_experiment_dirs_passes_with_allowed_drift",
        "test_compare_experiment_dirs_fails_on_perf_drift_and_writes_report",
        "test_compare_experiment_dirs_fails_on_run_config_behavior_drift",
    ):
        assert marker in baseline_tests

    assert "test_cli_audit_lists_baseline_regression_target" in cli_tests
    assert "python -m backend.cli audit --target baseline_regression" in closure_doc
    assert _has_checked_line_with(checklist, "baseline 主逻辑")
    assert _has_checked_line_with(checklist, "baseline regression check")


def test_research_publication_governance_checklist_matches_live_gate_tests() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    study_runner_tests = _read("tests", "unit", "test_study_runner.py")
    registry_tests = _read("tests", "unit", "test_live_strategy_registry_service.py")
    publisher_tests = _read("tests", "unit", "test_live_package_publisher_service.py")
    registry_contract = _read("docs", "product_launch", "contracts", "live_strategy_registry_v1.md")

    for marker in (
        "diagnostic_probe",
        "controlled_experiment",
        "test_non_live_approved_strategy_is_blocked",
        "test_live_publish_gate_blocks_all_non_live_strategy_statuses",
    ):
        assert marker in registry_tests or marker in publisher_tests

    assert "`diagnostic_probe`" in registry_contract
    assert "`controlled_experiment`" in registry_contract
    assert "run[\"baseline_outputs\"] == {}" in study_runner_tests
    assert "test_run_study_can_opt_in_to_baseline_append" in study_runner_tests
    assert _has_checked_line_with(checklist, "controlled experiment")
    assert _has_checked_line_with(checklist, "diagnostic probe")


def test_three_window_research_discipline_checklist_matches_journal_and_audit_tests() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    study_journal_tests = _read("tests", "unit", "test_study_journal.py")
    formal_audit_tests = _read("tests", "unit", "test_run_pams_ohlcv_daily_v2_formal_audits.py")

    for marker in (
        "test_study_journal_three_window_ready_round_is_reviewable",
        "2016_2026",
        "2012_2017",
        "2012_2026",
        "三窗口证据尚不完整，不能作为 baseline 升级依据。",
    ):
        assert marker in study_journal_tests

    assert "test_formal_audit_windows_use_2012_formal_policy" in formal_audit_tests
    assert "test_formal_audits_runner_executes_all_required_windows" in formal_audit_tests
    assert _has_checked_line_with(checklist, "三窗口研究纪律")


def test_signal_execution_price_basis_checklist_matches_live_package_contract_tests() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    package_contract_doc = _read(
        "docs",
        "product_launch",
        "contracts",
        "daily_position_adjustment_package_v1.md",
    )
    package_contract_tests = _read("tests", "unit", "test_daily_position_adjustment_package_contract.py")
    publisher_tests = _read("tests", "unit", "test_live_package_publisher_service.py")
    publisher_integration_tests = _read("tests", "integration", "test_live_package_publisher_contract.py")
    stage_contract_tests = _read("tests", "unit", "test_stage_pipeline_contracts.py")

    for marker in (
        "`clock.signal_date`",
        "`clock.execution_date`",
        "`clock.signal_clock`",
        "`clock.execution_clock`",
        "`clock.reference_price_basis`",
        "`reference_price`",
        "`reference_price_basis`",
    ):
        assert marker in package_contract_doc

    for marker in (
        "test_clock_requires_explicit_signal_execution_and_price_basis",
        "test_action_sheet_requires_explicit_reference_price_fields",
    ):
        assert marker in package_contract_tests

    for marker in (
        "validated.clock.signal_date",
        "validated.clock.execution_date",
        "validated.clock.signal_clock",
        "validated.clock.execution_clock",
        "validated.clock.reference_price_basis",
        "validated.action_sheet[0].reference_price",
        "validated.action_sheet[0].reference_price_basis",
    ):
        assert marker in publisher_tests
        assert marker in publisher_integration_tests

    assert 'ctx.signal_clock == "POST_CLOSE"' in stage_contract_tests
    assert 'ctx.execution_clock == "NEXT_OPEN"' in stage_contract_tests
    assert _has_checked_line_with(checklist, "信号时点", "成交时点", "价格口径")


def test_data_contract_checklist_matches_data_contract_tests() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    v2_daily_tests = _read("tests", "unit", "test_update_pams_ohlcv_daily_v2.py")
    v2_common_tests = _read("tests", "unit", "test_pams_ohlcv_daily_v2_common.py")
    audit_tests = _read("tests", "unit", "test_audit_pams_ohlcv_daily_v2.py")
    runtime_data_tests = _read("tests", "unit", "test_runtime_data_access.py")

    for marker in (
        "test_build_trade_date_rows_reclassifies_delist_tail_confirmed",
        "test_build_trade_date_rows_reclassifies_sh_side_evidence_gap_fill",
        "test_build_trade_date_rows_reclassifies_official_terminal_override_for_suspension_window",
    ):
        assert marker in v2_daily_tests

    assert "test_canonical_row_statuses_cover_data_quality_states" in v2_common_tests
    assert "test_build_runtime_gate_tracks_exclusion_reasons" in audit_tests
    assert "test_build_trade_date_audit_excludes_synthetic_gap_fill_from_eligible_no_source" in audit_tests
    assert "test_resolve_validation_universe_uses_shared_filter_path" in runtime_data_tests
    assert _has_checked_line_with(checklist, "数据合同测试")


def test_market_data_status_checklist_matches_v2_row_status_contracts() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    schema_contract = _read(
        "docs",
        "02_系统架构设计",
        "数据库",
        "pams_ohlcv_daily_v2_schema_contract.md",
    )
    runtime_contract = _read(
        "docs",
        "02_系统架构设计",
        "数据库",
        "pams_ohlcv_daily_v2_runtime_contract.md",
    )
    common_tests = _read("tests", "unit", "test_pams_ohlcv_daily_v2_common.py")
    v2_daily_tests = _read("tests", "unit", "test_update_pams_ohlcv_daily_v2.py")
    audit_tests = _read("tests", "unit", "test_audit_pams_ohlcv_daily_v2.py")

    for marker in (
        "`traded`",
        "`suspended_confirmed`",
        "`delist_tail_confirmed`",
        "`synthetic_gap_fill`",
        "`source_unresolved`",
    ):
        assert marker in schema_contract

    for marker in (
        "`source_unresolved` 不进入 runtime",
        "`delist_tail_confirmed` 不进入 runtime",
        "`synthetic_gap_fill` 不进入 runtime",
    ):
        assert marker in runtime_contract

    assert "test_canonical_row_statuses_cover_data_quality_states" in common_tests
    for marker in (
        "test_build_trade_date_rows_reclassifies_delist_tail_confirmed",
        "test_build_trade_date_rows_reclassifies_sh_side_evidence_gap_fill",
        "test_build_trade_date_rows_reclassifies_official_terminal_override_for_suspension_window",
    ):
        assert marker in v2_daily_tests

    assert "test_build_trade_date_audit_excludes_synthetic_gap_fill_from_eligible_no_source" in audit_tests
    assert "test_build_trade_date_audit_tracks_delist_tail_confirmed_separately" in audit_tests
    assert _has_checked_line_with(checklist, "停牌", "退市", "缺口", "合成补位")


def test_canonical_market_data_checklist_matches_access_contracts() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    architecture_doc = _read("docs", "product_launch", "ARCHITECTURE.md")
    features_doc = _read("docs", "product_launch", "FEATURES.md")
    runtime_contract = _read(
        "docs",
        "02_系统架构设计",
        "数据库",
        "pams_ohlcv_daily_v2_runtime_contract.md",
    )
    data_access_boundary = _read("docs", "02_系统架构设计", "数据库", "市场数据访问边界.md")
    market_data_tests = _read("tests", "unit", "test_market_data_access.py")
    runtime_data_tests = _read("tests", "unit", "test_runtime_data_access.py")
    schema_artifact_tests = _read("tests", "integration", "test_schema_and_artifacts.py")

    for marker in (
        "RawTushare --> Quality",
        "Quality --> Canonical",
        "Canonical --> Engine",
        "Canonical --> Study",
    ):
        assert marker in architecture_doc

    assert "canonical market data 访问合同" in features_doc
    assert "`canonical_market`" in runtime_contract
    assert "研究 / 回测默认只消费 `canonical_market`" in data_access_boundary
    assert "test_market_data_access_builds_canonical_data_source_from_runtime_config" in market_data_tests
    assert "test_price_history_audit_uses_fixed_contract_fields" in market_data_tests
    assert "test_resolve_validation_universe_uses_shared_filter_path" in runtime_data_tests
    assert "test_run_meta_report_consistency_defaults_to_canonical_market_contract" in schema_artifact_tests
    assert _has_checked_line_with(checklist, "canonical market data")


def test_report_generation_checklist_matches_report_services_and_cli() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    baseline_report_tests = _read("tests", "unit", "test_baseline_report_service.py")
    launch_report_tests = _read("tests", "unit", "test_product_launch_report_service.py")
    baseline_report_service = _read("backend", "core", "services", "baseline_report_service.py")
    launch_report_service = _read("backend", "core", "services", "product_launch_report_service.py")
    audit_command = _read("backend", "cli", "commands", "audit.py")

    for marker in (
        "baseline_report.md",
        "build_baseline_report_append",
        "append_experiment_to_baseline",
    ):
        assert marker in baseline_report_service

    assert "test_append_experiment_to_baseline_appends_fail_and_only_promotes_pass" in baseline_report_tests

    assert "build_launch_readiness_report" in launch_report_service
    assert "write_launch_readiness_report" in launch_report_service
    for marker in (
        "test_build_launch_readiness_report_marks_unfinished_items_not_ready",
        "test_product_launch_report_cli_writes_report",
        "launch_readiness_report",
    ):
        assert marker in launch_report_tests

    assert '"launch_readiness_report": "backend.cli.managed.product_launch_report"' in audit_command
    assert _has_checked_line_with(checklist, "研究报告", "上线报告")
