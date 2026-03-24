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
    assert "setDesktopFallbackMode" not in source
    assert "readDesktopFallback" not in source


def test_desktop_results_have_single_vue_owner_without_fallback_dom() -> None:
    index_source = _read_repo_file("frontend", "index.html")
    page_shell_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-research-page.js")
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    artifacts_source = _read_repo_file("frontend", "assets", "js", "artifacts.js")
    vue_shell_source = _read_repo_file("frontend", "app", "results-workbench", "main.js")
    assert 'id="wbResultsWorkbenchMount"' in index_source
    assert 'id="wbResultsFallbackRoot"' not in index_source
    assert "assets/js/report.js" not in index_source
    assert "setDesktopFallbackMode" not in page_shell_source
    assert "isDesktopFallbackModeEnabled" not in controller_source
    assert "wbResultsFallbackRoot" not in controller_source
    assert "Fallback only" not in artifacts_source
    assert "bridge.setMounted(true)" in vue_shell_source
    assert "bridge.setMounted(false)" in vue_shell_source
    assert "setDesktopFallbackMode" not in vue_shell_source


def test_desktop_main_path_uses_canonical_surface_and_sections_only() -> None:
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    artifacts_source = _read_repo_file("frontend", "assets", "js", "artifacts.js")
    load_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-load-controls.js")
    assert "/artifacts/read" not in controller_source
    assert "/artifacts/read" not in artifacts_source
    assert "/artifacts/read" not in load_controls_source
    assert "/surface/${encodeURIComponent(normalizedSection)}" in artifacts_source
    assert "const requiredSections = ['nav', 'run_meta', 'config'];" in artifacts_source
    assert "const optionalSections = [];" in artifacts_source
    assert "ensureDesktopExperimentSurfaceSection(state, normalizedExpId, 'config')" in load_controls_source


def test_legacy_desktop_controller_delegates_to_page_shell_helpers() -> None:
    source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    load_controls = _read_repo_file("frontend", "assets", "js", "pages", "desktop-load-controls.js")
    assert "window.getDesktopResultsWorkbenchBridge" in source
    assert "window.buildDesktopResultsWorkbenchSnapshot" in source
    assert "window.publishDesktopResultsWorkbenchSnapshot" in source
    assert "window.clearDesktopResultsWorkbenchState" in load_controls
    assert "window.isDesktopFallbackModeEnabled" not in source
    assert "window.readDesktopFallbackOpenPanels" not in source
    assert "generateReport(" not in source
    assert "copyAgentMarkdownReport(" not in source


def test_artifact_renderers_publish_canonical_lazy_sections() -> None:
    source = _read_repo_file("frontend", "assets", "js", "artifacts.js")
    assert "surfaceLazySections: cloneJson(surface?.lazy_sections) || {}" in source
    assert "funnelRows: Array.isArray(sectionData.stage_funnel) ? sectionData.stage_funnel : []" in source
    assert "reasonRows: Array.isArray(sectionData.reason_codes) ? sectionData.reason_codes : []" in source
    assert "tradesRows: Array.isArray(sectionData.trades) ? sectionData.trades : []" in source
    assert "symbolPerformanceRows: normalizeSymbolPerformanceRows(symbolStats)" in source
    assert "stockNames," in source


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


def test_frontend_exposes_market_data_sync_status_surface() -> None:
    index_source = _read_repo_file("frontend", "index.html")
    api_client_source = _read_repo_file("frontend", "assets", "js", "api-client.js")
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    assert 'id="wbDataSyncHint"' in index_source
    assert 'id="wbMarketDataSyncStatus"' in index_source
    assert "resolvePreferredAssetScope" in api_client_source
    assert "/api/backtest_v2/market_data/sync_status?asset_scope=${encodeURIComponent(assetScope)}" in api_client_source
    assert "renderMarketDataSyncStatus" in api_client_source
    assert "refreshMarketDataSyncStatus" in controller_source


def test_frontend_api_client_supports_local_backend_port_fallback() -> None:
    api_client_source = _read_repo_file("frontend", "assets", "js", "api-client.js")
    assert "const LOCAL_BACKEND_FALLBACK_PORT = '8091';" in api_client_source
    assert "function _buildApiEndpointCandidates(url)" in api_client_source
    assert "protocol === 'file:'" in api_client_source
    assert "http://127.0.0.1:${LOCAL_BACKEND_FALLBACK_PORT}" in api_client_source
    assert "const endpointCandidates = _buildApiEndpointCandidates(url);" in api_client_source


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


def test_config_draft_core_is_extracted_from_ui_controls() -> None:
    index_source = _read_repo_file("frontend", "index.html")
    core_source = _read_repo_file("frontend", "assets", "js", "state", "config-draft-core.js")
    ui_controls_source = _read_repo_file("frontend", "assets", "js", "ui-controls.js")
    assert "assets/js/state/config-draft-core.js" in index_source
    assert "function validateConfigDraftCore(draft)" in core_source
    assert "function buildConfigDraftCore()" in core_source
    assert "globalScope.configDraftCore = Object.freeze" in core_source
    assert "configDraftCore.validateConfigDraft" in ui_controls_source
    assert "configDraftCore.buildConfigDraft" in ui_controls_source
    assert "const loadedBase = cloneJson(state.loaded_config_json) || {};" not in ui_controls_source


def test_frontend_source_truth_is_not_driven_by_state_config_id() -> None:
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    workbench_state_source = _read_repo_file("frontend", "assets", "js", "state", "workbench-state.js")
    load_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-load-controls.js")
    save_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-save-controls.js")
    assert "state.config_id" not in controller_source
    assert "config_id: null" not in workbench_state_source
    assert "state.config_id" not in load_controls_source
    assert "state.config_id" not in save_controls_source


def test_frontend_loaded_source_state_uses_runtime_friendly_names() -> None:
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    ui_controls_source = _read_repo_file("frontend", "assets", "js", "ui-controls.js")
    workbench_state_source = _read_repo_file("frontend", "assets", "js", "state", "workbench-state.js")
    active_experiment_state_source = _read_repo_file("frontend", "assets", "js", "state", "active-experiment-state.js")
    assert "loaded_config_meta" not in controller_source
    assert "loaded_config_snapshot" not in controller_source
    assert "config_source_mode" not in controller_source
    assert "currentLoadedSourceMode" in controller_source
    assert "currentRuntimeSourceRef" in controller_source
    assert "rememberRuntimeSource" in controller_source
    assert "syncLoadedSourceUI" in controller_source
    assert "input_source_meta" not in ui_controls_source
    assert "currentLoadedSourceMode" in ui_controls_source
    assert "syncLoadedSourceUI" in ui_controls_source
    assert "loaded_source_meta" in workbench_state_source
    assert "loaded_source_asset_context" in workbench_state_source
    assert "loaded_source_config" in workbench_state_source
    assert "loaded_source_snapshot" in workbench_state_source
    assert "active_manifest" in active_experiment_state_source
    assert "active_surface_summary" in active_experiment_state_source
    assert "active_asset_context" in active_experiment_state_source
    assert "runtime_source_kind" in active_experiment_state_source
    assert "runtime_source_id" in active_experiment_state_source
    assert "loaded_source_kind" in active_experiment_state_source
    assert "loaded_source_id" in active_experiment_state_source


def test_runtime_snapshot_source_is_preferred_over_loaded_source_metadata() -> None:
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    page_shell_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-research-page.js")
    history_panel_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-history-panel.js")
    load_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-load-controls.js")
    artifacts_source = _read_repo_file("frontend", "assets", "js", "artifacts.js")
    assert "currentRuntimeSourceRef" in controller_source
    assert "runtime_source_kind" in page_shell_source
    assert "runtime_source_id" in page_shell_source
    assert "assetContext" in page_shell_source
    assert "manifest: cloneJson(state.active_manifest) || null" in page_shell_source
    assert "rememberRuntimeSource('experiment', expId, manifest, state.active_asset_context)" in history_panel_source
    assert "clearRuntimeSource" in load_controls_source
    assert "state.active_surface_summary" in artifacts_source
    assert "state.active_asset_context" in artifacts_source
    assert "rememberRuntimeSource('experiment', expId, state.active_manifest, state.active_asset_context)" in artifacts_source
    assert "state.loaded_source_meta =" not in artifacts_source
    assert "rememberLoadedSource" not in artifacts_source


def test_frontend_runtime_payloads_and_snapshot_include_asset_scope_context() -> None:
    config_core_source = _read_repo_file("frontend", "assets", "js", "state", "config-draft-core.js")
    run_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-run-controls.js")
    bridge_source = _read_repo_file("frontend", "app", "results-workbench", "composables", "useResultsWorkbenchBridge.js")
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    assert "asset_scope:" in config_core_source
    assert "asset_scope: assetScope" in run_controls_source
    assert "resolvePreferredAssetScope(state.config_draft?.asset_scope)" in run_controls_source
    assert "assetContext: {}" in bridge_source
    assert "normalizeAssetContext" in controller_source
    assert "assetContextFromPayload" in controller_source
    assert "syncAssetAwareShell" in controller_source
    assert "resolvePreferredAssetScope" in controller_source


def test_frontend_shell_is_asset_aware_instead_of_a_share_global_default() -> None:
    index_source = _read_repo_file("frontend", "index.html")
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    ui_controls_source = _read_repo_file("frontend", "assets", "js", "ui-controls.js")
    assert 'id="wbAssetScopeGroup"' in index_source
    assert 'id="wbEtfPresetWrap"' in index_source
    assert 'id="wbStageS1Btn"' in index_source
    assert "function syncAssetAwareShell(scope = null)" in controller_source
    assert "A股ETF" in controller_source
    assert "ETF 目录研究" in controller_source
    assert "wbPitStatusLabel" in controller_source
    assert "cn_etf_first_wave_core" in ui_controls_source
    assert "S1 ETF Universe" in ui_controls_source


def test_results_workbench_exposes_etf_specific_summary_fields() -> None:
    overview_source = _read_repo_file("frontend", "app", "results-workbench", "components", "ResultsOverview.vue")
    chart_source = _read_repo_file("frontend", "app", "results-workbench", "components", "ResultsChart.vue")
    formatting_source = _read_repo_file("frontend", "app", "results-workbench", "helpers", "resultsFormatting.js")
    assert "ETF批次" in overview_source
    assert "覆盖窗口" in overview_source
    assert "价格语义" in overview_source
    assert "ETF名单" in overview_source
    assert "portfolioBenchmarkSymbol" in chart_source
    assert "对比 ${portfolioBenchmarkSymbol.value}" in chart_source
    assert "ETF研究口径" in formatting_source
    assert "ETF名单" in formatting_source


def test_frontend_industry_picker_uses_api_client_instead_of_raw_fetch() -> None:
    ui_controls_source = _read_repo_file("frontend", "assets", "js", "ui-controls.js")
    assert "fetch('/api/backtest_v2/industries')" not in ui_controls_source
    assert "apiRequestJson('industries', '/api/backtest_v2/industries'" in ui_controls_source


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


def test_load_controls_are_extracted_from_backtest_controller() -> None:
    index_source = _read_repo_file("frontend", "index.html")
    load_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-load-controls.js")
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    assert "assets/js/pages/desktop-load-controls.js" in index_source
    assert "async function openExperimentLoadDropdown(anchorEl = null)" in load_controls_source
    assert "function applyLoadedConfigToWorkbench(workbenchConfig, meta)" in load_controls_source
    assert "async function loadBaselineToWorkbench(baselineId, options = {})" in load_controls_source
    assert "async function loadExperimentBundle(expId)" in load_controls_source
    assert "async function openExperimentLoadDropdown(anchorEl = null)" not in controller_source
    assert "function applyLoadedConfigToWorkbench(workbenchConfig, meta)" not in controller_source
    assert "async function loadBaselineToWorkbench(baselineId, options = {})" not in controller_source
    assert "async function loadExperimentBundle(expId)" not in controller_source


def test_load_controls_reuse_initial_experiment_payload_when_building_dropdown() -> None:
    load_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-load-controls.js")
    assert "const experimentItems = Array.isArray(experimentPayload?.items)" in load_controls_source
    assert "normalizeLoadItems(baselinePayload?.items || [], experimentItems)" in load_controls_source
    assert "{ experiments: experimentItems }" in load_controls_source
    assert "function buildExperimentMetricMap(experiments)" in load_controls_source


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
    assert "function setRunStatusText(text)" in run_controls_source
    assert "const dimsEl = byId('wbDims');" in run_controls_source


def test_save_controls_are_extracted_from_backtest_controller() -> None:
    index_source = _read_repo_file("frontend", "index.html")
    save_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-save-controls.js")
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    assert "assets/js/pages/desktop-save-controls.js" in index_source
    assert "async function saveConfig(kind = 'draft')" in save_controls_source
    assert "async function saveCurrentBaseline()" in save_controls_source
    assert "async function saveConfig(kind = 'draft')" not in controller_source
    assert "async function saveCurrentBaseline()" not in controller_source


def test_frontend_config_load_legacy_params_are_removed() -> None:
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    load_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-load-controls.js")
    save_controls_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-save-controls.js")
    assert "load_exp_id" not in controller_source
    assert "legacy_config_id" not in controller_source
    assert "legacy_config_id" not in load_controls_source
    assert "legacy_config_id" not in save_controls_source
