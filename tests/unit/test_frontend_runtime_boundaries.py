from __future__ import annotations

from pathlib import Path


def _read_repo_file(*parts: str) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root.joinpath(*parts)).read_text(encoding="utf-8", errors="ignore")


def test_desktop_page_shell_owns_surface_fetch_and_snapshot_bridge() -> None:
    source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-research-page.js")
    assert "publishDesktopResultsWorkbenchSnapshot" in source
    assert "/api/backtest_v2/experiments/${encodeURIComponent(normalizedExpId)}/surface" in source
    assert "/surface/${encodeURIComponent(normalizedSection)}" in source
    assert "mergeDesktopSurfaceIntoSnapshot" in source
    assert "mergeDesktopSurfaceSectionIntoSnapshot" in source


def test_legacy_desktop_controller_delegates_to_page_shell_helpers() -> None:
    source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    load_controls = _read_repo_file("frontend", "assets", "js", "pages", "desktop-load-controls.js")
    assert "window.getDesktopResultsWorkbenchBridge" in source
    assert "window.isDesktopFallbackModeEnabled" in source
    assert "window.readDesktopFallbackOpenPanels" in source
    assert "window.buildDesktopResultsWorkbenchSnapshot" in source
    assert "window.publishDesktopResultsWorkbenchSnapshot" in source
    assert "window.clearDesktopResultsWorkbenchState" in load_controls


def test_artifact_renderers_request_lazy_surface_sections_via_bridge() -> None:
    source = _read_repo_file("frontend", "assets", "js", "artifacts.js")
    assert "lazySections: ['nav', 'symbol_stats', 'stage_funnel']" in source
    assert "lazySections: ['symbol_stats']" in source
    assert "lazySections: ['nav']" in source
    assert "lazySections: ['stage_funnel']" in source


def test_stage_funnel_workbench_accepts_surface_funnel_rows() -> None:
    source = _read_repo_file("frontend", "app", "results-workbench", "helpers", "stageFunnelFormatting.js")
    assert "artifacts?.funnelRows" in source


def test_optional_market_series_requests_are_silent_on_backend_outage() -> None:
    artifacts_source = _read_repo_file("frontend", "assets", "js", "artifacts.js")
    api_client_source = _read_repo_file("frontend", "assets", "js", "api-client.js")
    assert "suppressStatusOnError: true" in artifacts_source
    assert "retryCount: 0" in artifacts_source
    assert "const suppressStatusOnError = !!requestOptions.suppressStatusOnError" in api_client_source
    assert "if (suppressStatusOnError) _clearApiStatus(key);" in api_client_source


def test_fallback_root_is_hidden_by_default_and_only_enabled_explicitly() -> None:
    index_source = _read_repo_file("frontend", "index.html")
    page_shell_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-research-page.js")
    vue_shell_source = _read_repo_file("frontend", "app", "results-workbench", "main.js")
    bundle_source = _read_repo_file("frontend", "assets", "dist", "results-workbench-vue-shell.js")
    assert 'id="wbResultsFallbackRoot"' in index_source
    assert "hidden" in index_source
    assert "inert" in index_source
    assert 'data-fallback-mode="disabled"' in index_source
    assert "function readDesktopFallbackQueryFlag()" in page_shell_source
    assert "function setDesktopFallbackMode(enabled, reason = '')" in page_shell_source
    assert "window.setDesktopFallbackMode?.(false, 'vue-mounted')" in vue_shell_source
    assert "window.setDesktopFallbackMode?.(true, 'vue-mount-failed')" in vue_shell_source
    assert (
        'window.setDesktopFallbackMode?.(false,"vue-mounted")' in bundle_source
        or 'window.setDesktopFallbackMode?.(!1,"vue-mounted")' in bundle_source
    )
    assert (
        'window.setDesktopFallbackMode?.(true,"vue-mount-failed")' in bundle_source
        or 'window.setDesktopFallbackMode?.(!0,"vue-mount-failed")' in bundle_source
    )


def test_legacy_result_renderers_only_touch_fallback_dom_in_explicit_fallback_mode() -> None:
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    ui_controls_source = _read_repo_file("frontend", "assets", "js", "ui-controls.js")
    artifacts_source = _read_repo_file("frontend", "assets", "js", "artifacts.js")
    assert "if (!isResultsFallbackModeEnabled()) return;" in controller_source
    assert "bindDesktopFallbackAccordions()" in controller_source
    assert "resetDesktopFallbackAccordions()" in controller_source
    assert "window.isDesktopFallbackModeEnabled" in ui_controls_source
    assert "window.isDesktopFallbackModeEnabled" in artifacts_source


def test_config_center_controls_are_extracted_from_ui_controls() -> None:
    index_source = _read_repo_file("frontend", "index.html")
    config_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-config-controls.js")
    ui_controls_source = _read_repo_file("frontend", "assets", "js", "ui-controls.js")
    assert "assets/js/pages/desktop-config-controls.js" in index_source
    assert "function buildConfigCenterGroups(items)" in config_controls_source
    assert "async function openConfigCenterDropdown(anchorEl = null)" in config_controls_source
    assert "function copyConfigJson()" in config_controls_source
    assert "async function loadConfig(configId)" not in ui_controls_source
    assert "async function loadConfigList()" not in ui_controls_source
    assert "function buildConfigCenterGroups(items)" not in ui_controls_source
    assert "async function openConfigCenterDropdown(anchorEl = null)" not in ui_controls_source
    assert "function copyConfigJson()" not in ui_controls_source


def test_history_panel_controls_are_extracted_from_backtest_controller() -> None:
    index_source = _read_repo_file("frontend", "index.html")
    history_panel_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-history-panel.js")
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    assert "assets/js/pages/desktop-history-panel.js" in index_source
    assert "async function loadExperimentList()" in history_panel_source
    assert "function renderHistoryPanel(experiments)" in history_panel_source
    assert "async function loadHistoricalExperiment(expId)" in history_panel_source
    assert "async function loadExperimentList()" not in controller_source
    assert "function renderHistoryPanel(experiments)" not in controller_source
    assert "async function loadHistoricalExperiment(expId)" not in controller_source
    assert "_legacyLoadExperimentListMovedToDesktopHistoryPanel" not in controller_source
    assert "_legacyRenderHistoryPanelMovedToDesktopHistoryPanel" not in controller_source
    assert "_legacyLoadHistoricalExperimentMovedToDesktopHistoryPanel" not in controller_source


def test_load_controls_are_extracted_from_backtest_controller() -> None:
    index_source = _read_repo_file("frontend", "index.html")
    load_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-load-controls.js")
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    assert "assets/js/pages/desktop-load-controls.js" in index_source
    assert "async function openExperimentLoadDropdown(anchorEl = null)" in load_controls_source
    assert "function applyLoadedConfigToWorkbench(workbenchConfig, meta)" in load_controls_source
    assert "async function loadBaselineToWorkbench(baselineId)" in load_controls_source
    assert "async function loadExperimentBundle(expId)" in load_controls_source
    assert "async function openExperimentLoadDropdown(anchorEl = null)" not in controller_source
    assert "function applyLoadedConfigToWorkbench(workbenchConfig, meta)" not in controller_source
    assert "async function loadBaselineToWorkbench(baselineId)" not in controller_source
    assert "async function loadExperimentBundle(expId)" not in controller_source
    assert "_legacyOpenExperimentLoadDropdownMovedToDesktopLoadControls" not in controller_source
    assert "_legacyApplyLoadedConfigToWorkbenchMovedToDesktopLoadControls" not in controller_source
    assert "_legacyLoadExperimentBundleMovedToDesktopLoadControls" not in controller_source


def test_run_controls_are_extracted_from_ui_controls() -> None:
    index_source = _read_repo_file("frontend", "index.html")
    run_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-run-controls.js")
    ui_controls_source = _read_repo_file("frontend", "assets", "js", "ui-controls.js")
    assert "assets/js/pages/desktop-run-controls.js" in index_source
    assert "async function pollJob(jobId)" in run_controls_source
    assert "async function runExperiment(presetOverride = null)" in run_controls_source
    assert "async function previewExecution()" in run_controls_source
    assert "async function runByMode()" in run_controls_source
    assert "async function pollJob(jobId)" not in ui_controls_source
    assert "async function runExperiment(presetOverride = null)" not in ui_controls_source
    assert "async function previewExecution()" not in ui_controls_source
    assert "async function runByMode()" not in ui_controls_source
    assert "_legacyPollJobMovedToDesktopRunControls" not in ui_controls_source
    assert "_legacyRunExperimentMovedToDesktopRunControls" not in ui_controls_source
    assert "_legacyPreviewExecutionMovedToDesktopRunControls" not in ui_controls_source
    assert "_legacyRunByModeMovedToDesktopRunControls" not in ui_controls_source


def test_save_controls_are_extracted_from_backtest_controller() -> None:
    index_source = _read_repo_file("frontend", "index.html")
    save_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-save-controls.js")
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    assert "assets/js/pages/desktop-save-controls.js" in index_source
    assert "async function saveConfig(kind = 'draft')" in save_controls_source
    assert "async function saveCurrentBaseline()" in save_controls_source
    assert "async function saveConfig(kind = 'draft')" not in controller_source
    assert "async function saveCurrentBaseline()" not in controller_source
    assert "_legacySaveConfigMovedToDesktopSaveControls" not in controller_source
    assert "_legacySaveCurrentBaselineMovedToDesktopSaveControls" not in controller_source


def test_config_legacy_wrappers_are_removed_from_ui_controls() -> None:
    ui_controls_source = _read_repo_file("frontend", "assets", "js", "ui-controls.js")
    assert "_legacyLoadConfigMovedToDesktopConfigControls" not in ui_controls_source
    assert "_legacyLoadConfigListMovedToDesktopConfigControls" not in ui_controls_source
    assert "_legacyOpenConfigCenterDropdownMovedToDesktopConfigControls" not in ui_controls_source
    assert "_legacyCopyConfigJsonMovedToDesktopConfigControls" not in ui_controls_source
    assert "_legacyPasteConfigJsonMovedToDesktopConfigControls" not in ui_controls_source


def test_frontend_config_load_legacy_params_are_removed() -> None:
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    load_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-load-controls.js")
    save_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-save-controls.js")
    assert "load_exp_id" not in controller_source
    assert "legacy_config_id" not in controller_source
    assert "legacy_config_id" not in load_controls_source
    assert "legacy_config_id" not in save_controls_source

