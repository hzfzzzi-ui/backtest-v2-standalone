(function initMobileStateSlice(globalScope) {
  globalScope.createMobileDashboardState = function createMobileDashboardState() {
    return {
      authenticated: false,
      configured: false,
      pollTimer: null,
      dashboard: null,
      busy: false,
    };
  };
})(window);
