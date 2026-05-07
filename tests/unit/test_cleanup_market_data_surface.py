from __future__ import annotations

from pathlib import Path


def test_account_allocator_shadow_module_is_removed() -> None:
    assert not Path("backend/core/services/account_allocator_shadow.py").exists()


def test_writable_external_callers_use_market_data_access_surface() -> None:
    data_impl_text = Path("backend/api/backtest_v2/data_impl.py").read_text(encoding="utf-8")
    market_snapshot_utils_text = Path("backend/core/services/market_snapshot_utils.py").read_text(encoding="utf-8")
    research_audit_text = Path("backend/core/audit/research_audit.py").read_text(encoding="utf-8")
    runtime_data_access_text = Path("backend/core/tools/runtime_data_access.py").read_text(encoding="utf-8")
    data_bundle_builder_text = Path("backend/core/tools/data_bundle_builder.py").read_text(encoding="utf-8")
    rf_diagnostic_text = Path("backend/core/tools/rf_diagnostic.py").read_text(encoding="utf-8")

    assert ".provider.load_trading_calendar_cn(" not in data_impl_text
    assert ".provider.load_trading_calendar_cn(" not in market_snapshot_utils_text
    assert "load_trading_calendar_index(" in data_impl_text
    assert "load_trading_calendar_index(" in market_snapshot_utils_text
    assert "account_allocator_shadow" not in research_audit_text
    assert "from backend.core.data.pg_provider import PostgresDataProvider" not in research_audit_text
    assert "from backend.core.data.pg_provider import PostgresDataProvider" not in runtime_data_access_text
    assert "from backend.core.data.pg_provider import PostgresDataProvider" not in data_bundle_builder_text
    assert "from backend.core.data.pg_provider import PostgresDataProvider" not in rf_diagnostic_text
    assert "build_runtime_provider_from_config(" in runtime_data_access_text
    assert "build_runtime_provider_from_config(" in data_bundle_builder_text
    assert "build_runtime_provider_from_config(" in rf_diagnostic_text


def test_backend_core_tools_no_longer_directly_import_pg_provider() -> None:
    tools_dir = Path("backend/core/tools")
    offenders: list[str] = []
    for path in sorted(tools_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "from backend.core.data.pg_provider import PostgresDataProvider" in text:
            offenders.append(path.as_posix())
    assert offenders == []


def test_backend_research_no_longer_directly_import_pg_provider() -> None:
    research_dir = Path("backend/research")
    offenders: list[str] = []
    for path in sorted(research_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "from backend.core.data.pg_provider import PostgresDataProvider" in text:
            offenders.append(path.as_posix())
    assert offenders == []


def test_backend_scripts_ops_no_longer_directly_import_pg_provider() -> None:
    ops_dir = Path("backend/scripts/ops")
    offenders: list[str] = []
    for path in sorted(ops_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "from backend.core.data.pg_provider import PostgresDataProvider" in text:
            offenders.append(path.as_posix())
    assert offenders == []


def test_legacy_chart_override_file_is_removed_from_main_load_chain() -> None:
    assert not Path("frontend/assets/js/results-chart-nav-override.js").exists()
    index_html = Path("frontend/index.html").read_text(encoding="utf-8")
    assert "results-chart-nav-override.js" not in index_html


def test_frontend_semantic_serializer_only_exposes_config_draft_core_entry() -> None:
    config_draft_core = Path("frontend/assets/js/state/config-draft-core.js").read_text(encoding="utf-8")
    run_orchestration = Path("frontend/assets/js/desktop-shell/run-orchestration.js").read_text(encoding="utf-8")
    save_orchestration = Path("frontend/assets/js/desktop-shell/save-orchestration.js").read_text(encoding="utf-8")
    assert "globalScope.serializeFrontendSemanticConfig" not in config_draft_core
    assert "typeof serializeFrontendSemanticConfig" not in run_orchestration
    assert "typeof serializeFrontendSemanticConfig" not in save_orchestration


def test_multi_alpha_ui_no_longer_floods_window_with_helper_globals() -> None:
    multi_alpha_ui = Path("frontend/assets/js/state/multi-alpha-ui.js").read_text(encoding="utf-8")
    config_draft_core = Path("frontend/assets/js/state/config-draft-core.js").read_text(encoding="utf-8")
    config_workspace = Path("frontend/assets/js/desktop-shell/config-workspace.js").read_text(encoding="utf-8")
    harness = Path("tests/frontend/multi_alpha_workbench_harness.cjs").read_text(encoding="utf-8")
    assert "Object.assign(globalScope, api)" not in multi_alpha_ui
    assert "globalScope.multiAlphaUi || {}" in config_draft_core
    assert "window.multiAlphaUi || {}" in config_workspace
    assert "Object.assign(context, context.window.multiAlphaUi || {})" not in harness


def test_frontend_pages_directory_is_retired_from_mobile_shell() -> None:
    index_html = Path("frontend/index.html").read_text(encoding="utf-8")
    mobile_html = Path("frontend/mobile.html").read_text(encoding="utf-8")
    service_worker = Path("frontend/mobile-service-worker.js").read_text(encoding="utf-8")
    mobile_access = Path("backend/api/shared/mobile_access.py").read_text(encoding="utf-8")
    assert "assets/js/pages/" not in index_html
    assert "pages/mobile-dashboard-page.js" not in mobile_html
    assert "pages/mobile-dashboard-page.js" not in service_worker
    assert "pages/mobile-dashboard-page.js" not in mobile_access
    pages_dir = Path("frontend/assets/js/pages")
    assert not pages_dir.exists() or not any(pages_dir.iterdir())
