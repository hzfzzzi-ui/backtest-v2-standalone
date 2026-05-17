from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(*parts: str) -> str:
    return _repo_root().joinpath(*parts).read_text(encoding="utf-8", errors="ignore")


def test_desktop_entry_loads_formal_desktop_shell_chain() -> None:
    index_source = _read("frontend", "index.html")
    expected_order = [
        "assets/js/desktop-shell/state.js",
        "assets/js/desktop-shell/host.js",
        "assets/js/desktop-shell/runtime-surface.js",
        "assets/js/desktop-shell/workspaces.js",
        "assets/js/shared-api.js",
        "assets/js/desktop-shell/api-adapter.js",
        "assets/js/desktop-shell/bootstrap.js",
        "assets/js/desktop-shell/results-workspace.js",
        "assets/js/desktop-shell/history-workspace.js",
        "assets/js/desktop-shell/load-orchestration.js",
        "assets/js/desktop-shell/save-orchestration.js",
        "assets/js/desktop-shell/run-orchestration.js",
        "assets/js/desktop-shell/app-shell.js",
        "assets/js/desktop-shell/api-surface.js",
        "assets/js/desktop-shell/config-workspace.js",
    ]
    positions = [index_source.index(item) for item in expected_order]
    assert positions == sorted(positions)
    assert "assets/js/pages/" not in index_source
    assert "assets/js/backtest_v2.js" not in index_source


def test_desktop_shell_files_exist_and_legacy_pages_are_retired() -> None:
    root = _repo_root()
    for rel in (
        "frontend/assets/js/desktop-shell/host.js",
        "frontend/assets/js/desktop-shell/runtime-surface.js",
        "frontend/assets/js/desktop-shell/app-shell.js",
        "frontend/assets/js/desktop-shell/results-workspace.js",
        "frontend/assets/js/desktop-shell/history-workspace.js",
        "frontend/assets/js/desktop-shell/load-orchestration.js",
        "frontend/assets/js/desktop-shell/run-orchestration.js",
        "frontend/assets/js/desktop-shell/save-orchestration.js",
        "frontend/assets/js/desktop-shell/config-workspace.js",
        "frontend/assets/js/desktop-shell/api-surface.js",
    ):
        assert root.joinpath(rel).exists(), rel
    pages_dir = root / "frontend" / "assets" / "js" / "pages"
    assert not pages_dir.exists() or not any(pages_dir.iterdir())


def test_desktop_host_owns_shared_state_bootstrap() -> None:
    host_source = _read("frontend", "assets", "js", "desktop-shell", "host.js")
    state_source = _read("frontend", "assets", "js", "desktop-shell", "state.js")
    bootstrap_source = _read("frontend", "assets", "js", "desktop-shell", "bootstrap.js")
    assert "desktop-shell/host.js" in host_source
    assert "createDesktopAppShellState" in state_source
    assert "desktop_shell" in state_source
    assert "desktop-app-shell-v1" in state_source
    assert "desktop-app-shell-v1" in bootstrap_source
    assert "initDesktop" in host_source


def test_runtime_surface_owns_shared_runtime_helpers() -> None:
    source = _read("frontend", "assets", "js", "desktop-shell", "runtime-surface.js")
    for marker in (
        "resolvePreferredAssetScope",
        "normalizeAssetContext",
        "rememberRuntimeSource",
        "currentRuntimeSourceRef",
        "buildDesktopResultsWorkbenchSnapshot",
        "publishDesktopResultsWorkbenchSnapshot",
    ):
        assert marker in source


def test_app_shell_bootstraps_formal_baseline_and_bridge_wiring() -> None:
    source = _read("frontend", "assets", "js", "desktop-shell", "app-shell.js")
    assert "CN_STOCK_ETF_COMBO_BASELINE_V4" in source
    assert "baseline_V10_1" in source
    assert "syncResultsWorkbenchSurface" in source
    assert "syncAssetAwareShell" in source
    assert "bootstrapInitialExperiment" in source


def test_results_workspace_uses_canonical_surface_sections() -> None:
    source = _read("frontend", "assets", "js", "desktop-shell", "results-workspace.js")
    assert "/api/backtest_v2/experiments/${encodeURIComponent(normalizedExpId)}/surface" in source
    assert "/surface/${encodeURIComponent(normalizedSection)}" in source
    assert "surfaceLazySections" in source
    assert "publishDesktopResultsWorkbenchSnapshot" in source
    assert "/artifacts/read" not in source


def test_api_surface_owns_market_data_sync_status_and_port_fallback() -> None:
    index_source = _read("frontend", "index.html")
    source = _read("frontend", "assets", "js", "desktop-shell", "api-surface.js")
    assert 'id="wbMarketDataSyncStatus"' in index_source
    assert "resolvePreferredAssetScope" in source
    assert "/api/backtest_v2/market_data/sync_status?asset_scope=${encodeURIComponent(assetScope)}" in source
    assert "renderMarketDataSyncStatus" in source
    assert "refreshMarketDataSyncStatus" in source
    assert "const LOCAL_BACKEND_FALLBACK_PORT = '8091';" in source


def test_config_workspace_owns_etf_preset_and_config_draft_bridge() -> None:
    source = _read("frontend", "assets", "js", "desktop-shell", "config-workspace.js")
    config_core_source = _read("frontend", "assets", "js", "state", "config-draft-core.js")
    assert "cn_etf_first_wave_core" in source
    assert "configDraftCore" in source
    assert "copyConfigJson" in source
    assert "pasteConfigJson" in source
    assert "buildConfigDraft" in source
    assert "function validateConfigDraftCore" in config_core_source
    assert "function buildConfigDraftCore" in config_core_source


def test_run_orchestration_sends_asset_scope_without_recomputing_research_logic() -> None:
    source = _read("frontend", "assets", "js", "desktop-shell", "run-orchestration.js")
    assert "resolvePreferredAssetScope" in source
    assert "asset_scope: assetScope" in source
    assert "apiRequestJson" in source
    assert "monthly_divergence_rate" not in source
    assert "rank(" not in source


def test_mobile_shell_uses_mobile_owner_and_shared_api_only() -> None:
    mobile_html = _read("frontend", "mobile.html")
    service_worker = _read("frontend", "mobile-service-worker.js")
    assert "/assets/js/shared-api.js" in mobile_html
    assert "/assets/js/mobile-dashboard.js" in mobile_html
    assert "pages/mobile-dashboard-page.js" not in mobile_html
    assert "pages/mobile-dashboard-page.js" not in service_worker
