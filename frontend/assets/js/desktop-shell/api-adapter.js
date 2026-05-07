(function initDesktopAppShellApiAdapter(globalScope) {
  function getSharedApiRequest() {
    if (typeof globalScope.sharedApiRequest === 'function') {
      return globalScope.sharedApiRequest;
    }
    throw new Error('sharedApiRequest is unavailable');
  }

  function getSharedApiRequestJson() {
    if (typeof globalScope.sharedApiRequestJson === 'function') {
      return globalScope.sharedApiRequestJson;
    }
    throw new Error('sharedApiRequestJson is unavailable');
  }

  function getMarketDataSyncStatus() {
    if (typeof globalScope.refreshMarketDataSyncStatus === 'function') {
      return globalScope.refreshMarketDataSyncStatus();
    }
    return Promise.resolve(null);
  }

  function requestJson(key, url, options = {}) {
    return getSharedApiRequestJson()(key, url, options);
  }

  globalScope.createDesktopApiAdapter = function createDesktopApiAdapter() {
    return {
      boundary: {
        owner: 'desktop_api_adapter',
        transport: 'shared_api_transport',
        ui_direct_fetch_allowed: false,
        legacy_helpers_mode: 'compat_only',
      },
      request(url, options = {}) {
        return getSharedApiRequest()(url, options);
      },
      requestJson(key, url, options = {}) {
        return requestJson(key, url, options);
      },
      requestMarketDataSyncStatus() {
        return getMarketDataSyncStatus();
      },
      listBaselines() {
        return requestJson('baselines', '/api/backtest_v2/baselines');
      },
      getBaseline(baselineId) {
        return requestJson('baseline_get', `/api/backtest_v2/baselines/${encodeURIComponent(baselineId)}`);
      },
      listExperiments() {
        return requestJson('experiments', '/api/backtest_v2/experiments');
      },
      getExperimentManifest(expId) {
        return requestJson('experiment_manifest', `/api/backtest_v2/experiments/${encodeURIComponent(expId)}/manifest`);
      },
      clearExperiments() {
        return requestJson('clearExperiments', '/api/backtest_v2/experiments', { method: 'DELETE' });
      },
      runExperimentAsync(body) {
        return requestJson('experiment_run_async', '/api/backtest_v2/experiment/run_async', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
      },
      pollJob(jobId) {
        return requestJson('job_poll', `/api/backtest_v2/jobs/${encodeURIComponent(jobId)}`);
      },
      cancelJob(jobId) {
        return requestJson('job_cancel', `/api/backtest_v2/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' });
      },
      previewExecution(body) {
        return requestJson('execution_preview', '/api/backtest_v2/execution/preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
      },
      saveBaseline(body) {
        return requestJson('baseline_save', '/api/backtest_v2/baselines', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
      },
    };
  };

  globalScope.desktopApiAdapter = globalScope.createDesktopApiAdapter();
  globalScope.desktopApiAdapterBoundary = { ...globalScope.desktopApiAdapter.boundary };
})(window);
