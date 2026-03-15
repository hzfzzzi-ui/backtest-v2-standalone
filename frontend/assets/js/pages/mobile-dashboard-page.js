(function initMobileDashboardPageShell(globalScope) {
  globalScope.getMobileDashboardPayload = function getMobileDashboardPayload(payload) {
    return payload && typeof payload === 'object' ? payload : {};
  };
})(window);
