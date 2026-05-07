(function initDesktopAppShell(globalScope) {
  const SHELL_VERSION = 'desktop-app-shell-v1';
  let bootstrapScheduled = false;

  function getSharedState() {
    const globalState = globalScope.state || globalScope.__WB_STATE__;
    return globalState && typeof globalState === 'object' ? globalState : null;
  }

  function getShellState() {
    const currentState = getSharedState();
    return currentState && typeof currentState.desktop_shell === 'object'
      ? currentState.desktop_shell
      : null;
  }

  function getRootState() {
    return getSharedState();
  }

  function syncShellAttributes() {
    const shellState = getShellState();
    const root = document.getElementById(shellState?.root_mount_id || 'wbDesktopAppShell');
    if (!shellState || !root) return;
    root.dataset.shell = 'desktop-app';
    root.dataset.shellVersion = SHELL_VERSION;
    root.dataset.moduleRoot = String(shellState.module_root || 'desktop_shell');
    root.dataset.shellState = String(shellState.mount_state || 'booting');
    root.dataset.activeWorkspace = String(shellState.active_workspace || 'config_workspace');
    root.dataset.apiBoundaryOwner = String(shellState.api_boundary_owner || 'desktop_api_adapter');
    root.dataset.shellMode = 'formal';
  }

  function markWorkspaceMounted(workspaceName, mounted) {
    const shellState = getShellState();
    if (!shellState) return;
    const name = String(workspaceName || '').trim() || 'results_workspace';
    const now = new Date().toISOString();
    shellState.shell_ready = !!mounted;
    shellState.mount_state = mounted ? 'ready' : 'booting';
    if (!shellState.workspaces || typeof shellState.workspaces !== 'object') {
      shellState.workspaces = {};
    }
    shellState.workspaces[name] = {
      ...(shellState.workspaces[name] || {}),
      mounted: !!mounted,
      updated_at: now,
    };
    syncShellAttributes();
  }

  function setActiveWorkspace(workspaceName) {
    const shellState = getShellState();
    if (!shellState) return;
    shellState.active_workspace = String(workspaceName || 'config_workspace').trim() || 'config_workspace';
    shellState.active_panel = shellState.active_workspace;
    syncShellAttributes();
  }

  function getWorkspaceState(workspaceName) {
    const currentState = getRootState();
    if (!currentState) return null;
    const name = String(workspaceName || '').trim();
    if (!name) return null;
    return currentState[name] && typeof currentState[name] === 'object' ? currentState[name] : null;
  }

  function getConfigWorkspaceStageCatalog() {
    const workspaceState = getWorkspaceState('config_workspace');
    return Array.isArray(workspaceState?.stage_catalog) ? workspaceState.stage_catalog : [];
  }

  function getWorkspaceRegistry() {
    const shellState = getShellState();
    return Array.isArray(shellState?.workspace_registry) ? shellState.workspace_registry : [];
  }

  function ensureBootstrap() {
    const currentState = getSharedState();
    if (!currentState) return false;
    if (!currentState.desktop_shell && typeof globalScope.createDesktopAppShellState === 'function') {
      currentState.desktop_shell = globalScope.createDesktopAppShellState().desktop_shell;
    }
    if (currentState.desktop_shell) {
      globalScope.desktopAppShell = {
        version: SHELL_VERSION,
        getState() {
          return typeof state !== 'undefined' ? state : null;
        },
        getShellState() {
          return getShellState();
        },
        getAdapter() {
          return globalScope.desktopApiAdapter || null;
        },
        getWorkspaceState,
        getWorkspaceRegistry,
        getConfigWorkspaceStageCatalog,
        markWorkspaceMounted,
        setActiveWorkspace,
      };
      globalScope.desktopAppShellBoundary = {
        module_root: String(currentState.desktop_shell.module_root || 'desktop_shell'),
        api_boundary_owner: String(currentState.desktop_shell.api_boundary_owner || 'desktop_api_adapter'),
      };
      syncShellAttributes();
      markWorkspaceMounted('desktop_shell', true);
      markWorkspaceMounted('results_workspace', !!document.getElementById(currentState.desktop_shell.results_mount_id || 'wbResultsWorkbenchMount'));
      return true;
    }
    return false;
  }

  function scheduleBootstrapRetry() {
    if (bootstrapScheduled) return;
    bootstrapScheduled = true;
    globalScope.setTimeout(() => {
      bootstrapScheduled = false;
      if (!ensureBootstrap()) {
        if (document.readyState === 'complete') {
          return;
        }
        scheduleBootstrapRetry();
      }
    }, 0);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureBootstrap, { once: true });
    scheduleBootstrapRetry();
  } else {
    if (!ensureBootstrap()) {
      scheduleBootstrapRetry();
    }
  }
})(window);
