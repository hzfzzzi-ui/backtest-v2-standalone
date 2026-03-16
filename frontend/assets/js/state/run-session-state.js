(function initRunSessionStateSlice(globalScope) {
  globalScope.createRunSessionState = function createRunSessionState() {
    return {
      execution_preview: null,
      execution_api_enabled: true,
      market_data_sync_status: null,
      status_items: [],
      manual_status_items: [],
      validation_status_items: [],
      api_status: {},
      status_open: false,
    };
  };
})(window);
