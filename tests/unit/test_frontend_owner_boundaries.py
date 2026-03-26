from __future__ import annotations

from pathlib import Path


def _read_repo_file(*parts: str) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root.joinpath(*parts)).read_text(encoding="utf-8", errors="ignore")


def test_frontend_owner_map_document_freezes_formal_roles() -> None:
    source = _read_repo_file("docs", "frontend_owner_map.md")
    assert "legacy shell owner" in source
    assert "config draft core owner" in source
    assert "page shell bridge owner" in source
    assert "Vue results workbench owner" in source
    assert "frontend/assets/js/backtest_v2.js" in source
    assert "frontend/assets/js/ui-controls.js" in source
    assert "frontend/assets/js/artifacts.js" in source
    assert "frontend/assets/js/state/config-draft-core.js" in source
    assert "frontend/assets/js/results-workbench-bridge.js" in source
    assert "frontend/assets/js/pages/desktop-research-page.js" in source
    assert "frontend/app/results-workbench/main.js" in source
    assert "#wbResultsWorkbenchMount" in source


def test_legacy_shell_does_not_reclaim_config_compile_owner() -> None:
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    ui_controls_source = _read_repo_file("frontend", "assets", "js", "ui-controls.js")
    artifacts_source = _read_repo_file("frontend", "assets", "js", "artifacts.js")
    config_core_source = _read_repo_file("frontend", "assets", "js", "state", "config-draft-core.js")
    assert "function buildConfigDraftCore()" in config_core_source
    assert "function validateConfigDraftCore(draft)" in config_core_source
    assert "globalScope.configDraftCore = Object.freeze" in config_core_source
    assert "function buildConfigDraftCore()" not in controller_source
    assert "function buildConfigDraftCore()" not in ui_controls_source
    assert "function buildConfigDraftCore()" not in artifacts_source
    assert "function validateConfigDraftCore(draft)" not in controller_source
    assert "function validateConfigDraftCore(draft)" not in ui_controls_source
    assert "function validateConfigDraftCore(draft)" not in artifacts_source
    assert "configDraftCore.buildConfigDraft" in ui_controls_source
    assert "configDraftCore.validateConfigDraft" in ui_controls_source


def test_vue_shell_keeps_single_results_mount_owner() -> None:
    index_source = _read_repo_file("frontend", "index.html")
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    ui_controls_source = _read_repo_file("frontend", "assets", "js", "ui-controls.js")
    artifacts_source = _read_repo_file("frontend", "assets", "js", "artifacts.js")
    page_shell_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-research-page.js")
    bridge_source = _read_repo_file("frontend", "assets", "js", "results-workbench-bridge.js")
    vue_shell_source = _read_repo_file("frontend", "app", "results-workbench", "main.js")
    assert 'id="wbResultsWorkbenchMount"' in index_source
    assert "document.getElementById('wbResultsWorkbenchMount')" not in controller_source
    assert "document.getElementById('wbResultsWorkbenchMount')" not in ui_controls_source
    assert "document.getElementById('wbResultsWorkbenchMount')" not in artifacts_source
    assert "document.getElementById('wbResultsWorkbenchMount')" not in page_shell_source
    assert "document.getElementById('wbResultsWorkbenchMount')" not in bridge_source
    assert "document.getElementById('wbResultsWorkbenchMount')" in vue_shell_source
    assert "bridge.setMounted(true)" in vue_shell_source


def test_frontend_files_are_explicitly_marked_with_owner_boundaries() -> None:
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    ui_controls_source = _read_repo_file("frontend", "assets", "js", "ui-controls.js")
    artifacts_source = _read_repo_file("frontend", "assets", "js", "artifacts.js")
    config_core_source = _read_repo_file("frontend", "assets", "js", "state", "config-draft-core.js")
    page_shell_source = _read_repo_file("frontend", "assets", "js", "pages", "desktop-research-page.js")
    bridge_source = _read_repo_file("frontend", "assets", "js", "results-workbench-bridge.js")
    vue_shell_source = _read_repo_file("frontend", "app", "results-workbench", "main.js")
    assert "legacy shell bootstrap/controller only" in controller_source
    assert "transitional desktop control wiring only" in ui_controls_source
    assert "bridge publisher only" in artifacts_source
    assert "sole owner of desktop config compile/validate truth" in config_core_source
    assert "page shell bridge owner" in page_shell_source
    assert "transition bridge between desktop shell and Vue workbench" in bridge_source
    assert "sole visible DOM owner for #wbResultsWorkbenchMount" in vue_shell_source


def test_legacy_shell_avoids_duplicate_active_helpers_and_combo_truth_rebuilders() -> None:
    controller_source = _read_repo_file("frontend", "assets", "js", "backtest_v2.js")
    artifacts_source = _read_repo_file("frontend", "assets", "js", "artifacts.js")
    assert controller_source.count("function assetScopeDisplayName(") == 1
    assert "function buildResearchComboDisplay(" not in artifacts_source
    assert "function loadResearchComboComponent(" not in artifacts_source
    assert "function loadResearchComboComponentArtifacts(" not in artifacts_source
    assert "LegacyShim" in artifacts_source
