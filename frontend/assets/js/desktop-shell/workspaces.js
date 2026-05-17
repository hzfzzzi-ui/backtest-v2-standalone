(function initDesktopAppShellWorkspaces(globalScope) {
  const CONFIG_WORKSPACE_STAGE_CATALOG = Object.freeze([
    { panel: 's1', label: '资产池', title: '资产池与基础过滤', hidden: false },
    { panel: 's2', label: '环境', title: '高级环境参数', hidden: true },
    { panel: 's3', label: '行业', title: '行业门控', hidden: true },
    { panel: 's4', label: '信号', title: '入场信号与组合', hidden: false },
    { panel: 's5', label: '排序', title: '排序与候选保留', hidden: false },
    { panel: 's6', label: '建仓', title: '建仓与组合约束', hidden: false },
    { panel: 's7', label: '预算', title: '高级预算参数', hidden: true },
    { panel: 's8', label: '风险', title: '风险保护', hidden: false },
    { panel: 's9', label: '退出', title: '退出规则', hidden: false },
  ]);

  const DESKTOP_WORKSPACE_DEFINITIONS = Object.freeze([
    { id: 'desktop_shell', role: 'host_shell' },
    { id: 'config_workspace', role: 'config_editor' },
    { id: 'run_orchestration', role: 'run_loader_save_hydrate' },
    { id: 'results_workspace', role: 'results_display' },
    { id: 'study_journal_workspace', role: 'research_journal_display' },
    { id: 'status_center', role: 'status_summary_only' },
  ]);

  function cloneJsonSafe(value) {
    if (value == null) return value;
    try {
      return JSON.parse(JSON.stringify(value));
    } catch (_) {
      return value;
    }
  }

  function getRootState() {
    return typeof state !== 'undefined' && state && typeof state === 'object' ? state : null;
  }

  function ensureConfigWorkspaceState() {
    const currentState = getRootState();
    if (!currentState || !currentState.config_workspace || typeof currentState.config_workspace !== 'object') return null;
    if (!Array.isArray(currentState.config_workspace.stage_catalog) || !currentState.config_workspace.stage_catalog.length) {
      currentState.config_workspace.stage_catalog = CONFIG_WORKSPACE_STAGE_CATALOG.map((item) => ({ ...item }));
    }
    return currentState.config_workspace;
  }

  function ensureDesktopShellWorkspaceRegistry() {
    const currentState = getRootState();
    if (!currentState || !currentState.desktop_shell || typeof currentState.desktop_shell !== 'object') return null;
    if (!Array.isArray(currentState.desktop_shell.workspace_registry) || !currentState.desktop_shell.workspace_registry.length) {
      currentState.desktop_shell.workspace_registry = DESKTOP_WORKSPACE_DEFINITIONS.map((item) => ({ ...item }));
    }
    return currentState.desktop_shell.workspace_registry;
  }

  function getConfigWorkspaceStageCatalog() {
    const workspaceState = ensureConfigWorkspaceState();
    const catalog = Array.isArray(workspaceState?.stage_catalog) ? workspaceState.stage_catalog : [];
    return catalog.map((item) => ({ ...item }));
  }

  function getWorkspaceRegistry() {
    const registry = ensureDesktopShellWorkspaceRegistry();
    return Array.isArray(registry) ? registry.map((item) => ({ ...item })) : [];
  }

  function hydrateWorkspaceState() {
    ensureConfigWorkspaceState();
    ensureDesktopShellWorkspaceRegistry();
  }

  globalScope.getDesktopConfigWorkspaceStageCatalog = getConfigWorkspaceStageCatalog;
  globalScope.getDesktopWorkspaceRegistry = getWorkspaceRegistry;
  globalScope.createDesktopWorkspaceCatalogSnapshot = function createDesktopWorkspaceCatalogSnapshot() {
    return {
      config_workspace: {
        stage_catalog: cloneJsonSafe(getConfigWorkspaceStageCatalog()) || [],
      },
      desktop_shell: {
        workspace_registry: cloneJsonSafe(getWorkspaceRegistry()) || [],
      },
    };
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', hydrateWorkspaceState, { once: true });
  } else {
    hydrateWorkspaceState();
  }
})(window);
