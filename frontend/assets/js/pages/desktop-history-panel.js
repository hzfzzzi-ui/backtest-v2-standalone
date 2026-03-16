(function initDesktopHistoryPanel(globalScope) {
  function reportHistoryFailure(action, error, sourceId = '') {
    const detail = String(error?.message || error || 'unknown error');
    if (typeof setTextById === 'function') setTextById('wbRunStatus', `${action} failed: ${detail}`);
    if (typeof setStatusItems === 'function') {
      setStatusItems([{
        title: `${action} failed`,
        message: sourceId ? `${action} ${sourceId}` : action,
        file: String(sourceId || '-'),
        detail,
      }]);
    }
    addLog(`${action} failed: ${detail}`);
  }

  async function loadExperimentList() {
    try {
      const data = await apiRequestJson('experiments', '/api/backtest_v2/experiments');
      renderHistoryPanel(data);
    } catch (error) {
      reportHistoryFailure('Load history', error);
      renderHistoryPanel([]);
    }
  }

  function renderHistoryPanel(experiments) {
    const container = byId('wbHistoryList');
    if (!container) return;
    if (!experiments || !experiments.length) {
      state.compare_selected_ids = [];
      const countEl = byId('wbHistoryCompareCount');
      if (countEl) countEl.textContent = 'Selected 0';
      container.innerHTML = `<div class="wb-empty" style="padding:24px 0">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      <span>No experiment history yet</span>
    </div>`;
      return;
    }
    const validIds = new Set((experiments || []).map((x) => String(x?.exp_id || '')));
    state.compare_selected_ids = (state.compare_selected_ids || []).filter((id) => validIds.has(String(id)));
    container.innerHTML = experiments.map((exp) => {
      const label = esc(compactExperimentLabel(exp));
      const expId = esc(exp.exp_id || '');
      const totalReturn = pct(exp.total_return);
      const maxDd = pct(exp.max_drawdown);
      const sharpe = num(exp.sharpe, 2);
      const trades = fmtInt(exp.trades);
      const trClass = Number(exp.total_return) >= 0 ? 'wb-green-text' : 'wb-red-text';
      const ddClass = 'wb-red-text';
      const created = exp.created_at ? exp.created_at.replace('T', ' ').slice(0, 16) : '-';
      const checked = (state.compare_selected_ids || []).includes(String(exp.exp_id || '')) ? 'checked' : '';
      return `<div class="wb-history-card" data-exp-id="${expId}">
      <div class="wb-hc-label">${label}</div>
      <div class="wb-mini"><label><input type="checkbox" class="wb-hc-compare" data-exp="${expId}" ${checked}/> Compare</label></div>
      <div class="wb-stat-row">
        <div class="wb-stat-item"><span class="wb-stat-label">Return</span><span class="wb-stat-value ${trClass}">${totalReturn}</span></div>
        <div class="wb-stat-item"><span class="wb-stat-label">MaxDD</span><span class="wb-stat-value ${ddClass}">${maxDd}</span></div>
        <div class="wb-stat-item"><span class="wb-stat-label">Sharpe</span><span class="wb-stat-value">${sharpe}</span></div>
        <div class="wb-stat-item"><span class="wb-stat-label">Trades</span><span class="wb-stat-value">${trades}</span></div>
      </div>
      <div class="wb-hc-actions">
        <button class="pill wb-hc-load" data-exp="${expId}">Load result</button>
      </div>
      <div class="wb-hc-time">${created}</div>
    </div>`;
    }).join('');

    container.querySelectorAll('.wb-hc-load').forEach((btn) => btn.addEventListener('click', async (ev) => {
      ev.stopPropagation();
      const expId = btn.getAttribute('data-exp');
      try {
        if (typeof setTextById === 'function') setTextById('wbRunStatus', `Loading ${expId}...`);
        await loadHistoricalExperiment(expId);
        if (typeof setTextById === 'function') setTextById('wbRunStatus', `Loaded ${expId}`);
      } catch (error) {
        reportHistoryFailure('Load history result', error, expId);
      }
    }));
    const syncCompareCount = () => {
      const count = (state.compare_selected_ids || []).length;
      const countEl = byId('wbHistoryCompareCount');
      if (countEl) countEl.textContent = `Selected ${count}`;
    };
    container.querySelectorAll('.wb-hc-compare').forEach((cb) => cb.addEventListener('change', () => {
      const expId = String(cb.getAttribute('data-exp') || '');
      const selected = new Set(state.compare_selected_ids || []);
      if (cb.checked) selected.add(expId);
      else selected.delete(expId);
      state.compare_selected_ids = Array.from(selected);
      syncCompareCount();
    }));
    syncCompareCount();
  }

  async function loadHistoricalExperiment(expId) {
    addLog(`Load historical experiment: ${expId}`);
    const manifest = await apiRequestJson('experiment_manifest', `/api/backtest_v2/experiments/${encodeURIComponent(expId)}/manifest`);
    const fakeResult = {
      exp_id: expId,
      experiment_id: expId,
      status: 'OK',
      artifacts: manifest?.artifacts || {},
      manifest,
    };
    state.active_exp = fakeResult;
    state.active_result = fakeResult;
    state.active_manifest = cloneJson(manifest) || null;
    state.active_surface_summary = null;
    state.active_asset_context = typeof assetContextFromPayload === 'function'
      ? assetContextFromPayload(manifest || {}, 'cn_a_equity')
      : { asset_scope: String(manifest?.asset_scope || 'cn_a_equity').trim() || 'cn_a_equity' };
    if (typeof rememberRuntimeSource === 'function') {
      rememberRuntimeSource('experiment', expId, manifest, state.active_asset_context);
    }
    await loadActiveArtifacts();
    renderRightInspector();
    addLog(`Historical experiment loaded: ${expId}`);
  }

  globalScope.loadExperimentList = loadExperimentList;
  globalScope.renderHistoryPanel = renderHistoryPanel;
  globalScope.loadHistoricalExperiment = loadHistoricalExperiment;
})(window);
