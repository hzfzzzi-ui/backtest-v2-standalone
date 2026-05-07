/* desktop-shell/host.js: formal desktop host owner for shared state bootstrap and main init dispatch. */
/* legacy shell has been retired from the desktop page load chain. */
(function initDesktopAppHostOwner(globalScope) {
  const HOST_VERSION = 'desktop-app-host-v1';
  let initialized = false;

  function existingSharedState() {
    const directState = globalScope.state;
    if (directState && typeof directState === 'object') return directState;
    const legacyState = globalScope.__WB_STATE__;
    return legacyState && typeof legacyState === 'object' ? legacyState : null;
  }

  function createSharedState() {
    const state = {
      ...((globalScope.createWorkbenchConfigDraftState && globalScope.createWorkbenchConfigDraftState()) || {}),
      ...((globalScope.createRunSessionState && globalScope.createRunSessionState()) || {}),
      ...((globalScope.createActiveExperimentState && globalScope.createActiveExperimentState()) || {}),
      ...((globalScope.createViewState && globalScope.createViewState()) || {}),
      ...((globalScope.createDesktopAppShellState && globalScope.createDesktopAppShellState()) || {}),
    };
    globalScope.__WB_STATE__ = state;
    globalScope.state = state;
    return state;
  }

  function ensureSharedState() {
    const currentState = existingSharedState();
    if (currentState) {
      globalScope.__WB_STATE__ = currentState;
      globalScope.state = currentState;
      return currentState;
    }
    return createSharedState();
  }

  function markHostOwnership(state) {
    if (!state || typeof state !== 'object') return;
    if (!state.desktop_shell || typeof state.desktop_shell !== 'object') {
      state.desktop_shell = {};
    }
    state.desktop_shell.host_owner = 'desktop_shell_host';
    state.desktop_shell.host_version = HOST_VERSION;
    state.desktop_shell.bootstrap_owner = 'desktop_shell_host';
  }

  function initDesktopAppHost() {
    const state = ensureSharedState();
    markHostOwnership(state);
    if (initialized) return true;
    initialized = true;
    if (typeof globalScope.initDesktopAppShell === 'function') {
      return globalScope.initDesktopAppShell();
    }
    if (typeof globalScope.init === 'function') {
      return globalScope.init();
    }
    return true;
  }

  const state = ensureSharedState();
  markHostOwnership(state);

  globalScope.ensureDesktopAppHostState = ensureSharedState;
  globalScope.initDesktopAppHost = initDesktopAppHost;
  globalScope.desktopAppHostOwner = {
    version: HOST_VERSION,
    getState: ensureSharedState,
  };
})(window);

