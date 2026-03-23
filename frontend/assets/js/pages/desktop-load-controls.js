(function initDesktopLoadControls(globalScope) {
  function reportLoadFailure(sourceId, error) {
    const detail = String(error?.message || error || 'unknown error');
    if (typeof setTextById === 'function') setTextById('wbRunStatus', `Load failed: ${detail}`);
    if (typeof setStatusItems === 'function') {
      setStatusItems([{
        title: 'Load failed',
        message: `Failed to load ${sourceId || '-'}`,
        file: String(sourceId || '-'),
        detail,
      }]);
    }
    addLog(`Load failed: ${detail}`);
  }

  async function openExperimentLoadDropdown(anchorEl = null) {
    const existing = document.getElementById('wbLoadDropdown');
    if (existing) {
      existing.remove();
      return;
    }

    const baselinePayload = await apiRequestJson('baselines', '/api/backtest_v2/baselines');
    const experimentPayload = await apiRequestJson('experiments', '/api/backtest_v2/experiments');
    const experimentItems = Array.isArray(experimentPayload?.items)
      ? experimentPayload.items
      : (Array.isArray(experimentPayload) ? experimentPayload : []);
    const items = await enrichLoadItems(
      normalizeLoadItems(baselinePayload?.items || [], experimentItems),
      { experiments: experimentItems },
    );

    if (!items.length) {
      if (typeof setTextById === 'function') setTextById('wbRunStatus', 'No baseline or experiment available');
      if (typeof setStatusItems === 'function') {
        setStatusItems([{
          title: 'Load menu empty',
          message: 'No baseline or experiment available',
          file: '/api/backtest_v2/baselines + /api/backtest_v2/experiments',
          detail: 'quick load dropdown has no items',
        }]);
      }
      addLog('Load menu is empty');
      return;
    }

    const dropdown = document.createElement('div');
    dropdown.id = 'wbLoadDropdown';
    dropdown.className = 'wb-load-dropdown';

    const activeSourceId = String(state.loaded_source_id || '').trim();
    const activeSourceKind = String(state.loaded_source_kind || '').trim();

    items.forEach((item) => {
      const sourceId = String(item?.id || '').trim();
      const kindClass = item?.kind === 'baseline' ? 'baseline' : 'experiment';
      const isActive = sourceId && sourceId === activeSourceId && item.kind === activeSourceKind;
      const row = document.createElement('button');
      row.type = 'button';
      row.className = `wb-load-item wb-config-center-item wb-load-item-${kindClass}${isActive ? ' active' : ''}`;
      row.innerHTML = `
      <div class="wb-load-item-head">
        <span class="wb-load-kind ${loadItemBadgeClass(item)}">${esc(loadItemBadgeLabel(item))}</span>
        <span class="wb-config-center-title">${esc(item?.label || sourceId)}</span>
      </div>
      <span class="wb-config-center-desc">${esc(experimentLoadSummary(item))}</span>
    `;
      row.addEventListener('click', async () => {
        dropdown.remove();
        try {
          if (typeof setTextById === 'function') setTextById('wbRunStatus', `Loading ${sourceId}...`);
          if (item.kind === 'experiment') {
            await loadExperimentBundle(sourceId);
          } else {
            await loadBaselineToWorkbench(sourceId);
          }
          if (typeof setTextById === 'function') setTextById('wbRunStatus', `Loaded ${sourceId}`);
        } catch (error) {
          reportLoadFailure(sourceId, error);
        }
      });
      dropdown.appendChild(row);
    });

    (anchorEl || byId('wbQuickLoad') || byId('wbRunBtn'))?.parentElement?.appendChild(dropdown);
    const dismiss = (event) => {
      const trigger = anchorEl || byId('wbQuickLoad');
      if (!dropdown.contains(event.target) && event.target !== trigger) {
        dropdown.remove();
        document.removeEventListener('click', dismiss);
      }
    };
    setTimeout(() => document.addEventListener('click', dismiss), 0);
  }

  function extractWorkbenchConfigFromExperimentPayload(payload) {
    const cfg = payload && typeof payload === 'object' ? payload : {};
    return cfg?.overrides?.original_workbench_config
      || cfg?.overrides?.workbench_config
      || cfg?.workbench_config
      || null;
  }

  function clearActiveResultContext() {
    state.active_exp = null;
    state.active_result = null;
    state.active_artifacts = null;
    state.active_manifest = null;
    state.active_surface_summary = null;
    state.active_asset_context = null;
    state.execution_preview = null;
    state.selected_symbol = '';
    state.symbol_series_cache = {};
    state.symbol_series_loading = false;
    if (typeof clearRuntimeSource === 'function') clearRuntimeSource();
    if (typeof window.clearDesktopResultsWorkbenchState === 'function') {
      window.clearDesktopResultsWorkbenchState(state);
    }
    const bridge = getResultsWorkbenchBridge();
    if (bridge && typeof bridge.clear === 'function') bridge.clear();
  }

  function applyLoadedConfigToWorkbench(workbenchConfig, meta) {
    if (!workbenchConfig || typeof workbenchConfig !== 'object') {
      throw new Error('missing workbench config');
    }

    const applied = applyConfigToUI(workbenchConfig);
    if (applied?.unsupportedStrategy) {
      throw new Error(`unsupported strategy ${applied.unsupportedStrategy}`);
    }

    setSelectedLockedCandidatePreset('');
    clearActiveResultContext();

    const loadedSourceId = String(meta?.source_id || meta?.loaded_id || meta?.config_id || '').trim() || '-';
    const loadedAssetContext = typeof assetContextFromPayload === 'function'
      ? assetContextFromPayload(meta?.asset_context ? meta : (workbenchConfig || meta || {}), resolvePreferredAssetScope(workbenchConfig?.asset_scope))
      : { asset_scope: resolvePreferredAssetScope(workbenchConfig?.asset_scope) };
    state.loaded_source_meta = {
      source_id: loadedSourceId,
      config_ref: String(meta?.config_id || '').trim() || null,
      display_name: String(meta?.display_name || meta?.name || loadedSourceId).trim() || '-',
      name: String(meta?.name || meta?.display_name || loadedSourceId).trim() || '-',
      source_type: String(meta?.source_type || 'derived').trim() || 'derived',
      owner: String(meta?.owner || 'manual').trim() || 'manual',
      locked: !!meta?.locked,
      baseline_of: null,
      universe_mode: workbenchConfig?.universe_mode || null,
      membership_mode: workbenchConfig?.universe?.membership_mode || null,
      asset_context: cloneJson(loadedAssetContext) || loadedAssetContext,
    };
    state.loaded_source_asset_context = cloneJson(loadedAssetContext) || loadedAssetContext;
    state.loaded_source_config = cloneJson(workbenchConfig);
    state.loaded_source_kind = String(meta?.loaded_kind || '').trim() || '';
    state.loaded_source_id = loadedSourceId === '-' ? '' : loadedSourceId;
    syncWorkbenchLoadedSourceToUrl(state.loaded_source_kind, state.loaded_source_id);
    buildConfigDraft();
    syncAssetAwareShell(loadedAssetContext);
    state.loaded_source_snapshot = stableSerializeConfig(state.config_draft || {});
    syncLoadedSourceUI();
    renderRunHints();
    syncExitLinkage();
    updateAtrNote();
    syncLoadHint(state.loaded_source_id);
    renderRightInspector();
  }

  async function loadExperimentConfigToWorkbench(expId) {
    const normalizedExpId = String(expId || '').trim();
    if (!normalizedExpId) throw new Error('missing experiment_id');

    if (typeof setTextById === 'function') setTextById('wbRunStatus', `Importing experiment config ${normalizedExpId}...`);
    addLog(`Import experiment config: ${normalizedExpId}`);
    const configPayload = typeof window.ensureDesktopExperimentSurfaceSection === 'function'
      ? await window.ensureDesktopExperimentSurfaceSection(state, normalizedExpId, 'config')
      : await apiRequestJson(
        `experiment_surface_${normalizedExpId}_config`,
        `/api/backtest_v2/experiments/${encodeURIComponent(normalizedExpId)}/surface/config`,
      );

    const workbenchConfig = extractWorkbenchConfigFromExperimentPayload(configPayload?.data);
    if (!workbenchConfig || typeof workbenchConfig !== 'object') {
      throw new Error(`missing workbench_config for ${normalizedExpId}`);
    }

    applyLoadedConfigToWorkbench(workbenchConfig, {
      source_id: normalizedExpId,
      config_id: `expcfg:${normalizedExpId}`,
      display_name: `Experiment config ${normalizedExpId}`,
      name: `Experiment config ${normalizedExpId}`,
      source_type: 'derived',
      owner: 'manual',
      locked: false,
      loaded_kind: 'experiment',
      loaded_id: normalizedExpId,
    });
    addLog(`Experiment config imported: ${normalizedExpId}`);
  }

  async function loadBaselineToWorkbench(baselineId, options = {}) {
    const normalizedBaselineId = String(baselineId || '').trim();
    if (!normalizedBaselineId) throw new Error('missing baseline_id');
    const shouldLoadLinkedResult = options?.loadLinkedResult !== false;

    if (typeof setTextById === 'function') setTextById('wbRunStatus', `Importing baseline ${normalizedBaselineId}...`);
    addLog(`Import baseline: ${normalizedBaselineId}`);
    const payload = await apiRequestJson(
      `baseline_${normalizedBaselineId}`,
      `/api/backtest_v2/baselines/${encodeURIComponent(normalizedBaselineId)}`,
    );

    const workbenchConfig = payload?.config_json;
    if (!workbenchConfig || typeof workbenchConfig !== 'object') {
      throw new Error(`missing config_json for ${normalizedBaselineId}`);
    }

    applyLoadedConfigToWorkbench(workbenchConfig, {
      source_id: normalizedBaselineId,
      config_id: normalizedBaselineId,
      display_name: String(payload?.display_name || payload?.name || normalizedBaselineId),
      name: String(payload?.name || payload?.display_name || normalizedBaselineId),
      source_type: 'baseline',
      owner: String(payload?.owner || 'manual'),
      locked: true,
      loaded_kind: 'baseline',
      loaded_id: normalizedBaselineId,
    });

    const linkedExpId = String(payload?.linked_exp_id || '').trim();
    if (shouldLoadLinkedResult && linkedExpId && payload?.has_result) {
      await loadHistoricalExperiment(linkedExpId);
    } else {
      clearActiveResultContext();
      renderRightInspector();
    }

    addLog(`Baseline imported: ${normalizedBaselineId}`);
  }

  async function loadExperimentBundle(expId) {
    const normalizedExpId = String(expId || '').trim();
    if (!normalizedExpId) throw new Error('missing experiment_id');
    await loadExperimentConfigToWorkbench(normalizedExpId);
    await loadHistoricalExperiment(normalizedExpId);
  }

  function buildExperimentMetricMap(experiments) {
    const rows = Array.isArray(experiments) ? experiments : [];
    const metrics = new Map();
    rows.forEach((item) => {
      const expId = String(item?.exp_id || item?.id || '').trim();
      if (!expId) return;
      const perf = item?.perf || {};
      metrics.set(expId, {
        cagr: perf?.cagr ?? item?.cagr,
        max_drawdown: perf?.max_drawdown ?? item?.max_drawdown,
        universe_mode: String(item?.universe_mode || '').trim(),
        membership_mode: String(item?.membership_mode || '').trim(),
        start_year: Number.isFinite(Number(item?.start_year)) ? Number(item.start_year) : null,
        end_year: Number.isFinite(Number(item?.end_year)) ? Number(item.end_year) : null,
      });
    });
    return metrics;
  }

  async function fetchExperimentLoadMetrics(expId) {
    const normalizedExpId = String(expId || '').trim();
    if (!normalizedExpId) return {};

    const experimentsPayload = await apiRequestJson('experiments', '/api/backtest_v2/experiments');
    const rows = Array.isArray(experimentsPayload?.items)
      ? experimentsPayload.items
      : (Array.isArray(experimentsPayload) ? experimentsPayload : []);
    const row = rows.find((item) => String(item?.exp_id || '').trim() === normalizedExpId) || {};
    const perf = row?.perf || {};
    return {
      cagr: perf?.cagr ?? row?.cagr,
      max_drawdown: perf?.max_drawdown ?? row?.max_drawdown,
      universe_mode: String(row?.universe_mode || '').trim(),
      membership_mode: String(row?.membership_mode || '').trim(),
      start_year: Number.isFinite(Number(row?.start_year)) ? Number(row.start_year) : null,
      end_year: Number.isFinite(Number(row?.end_year)) ? Number(row.end_year) : null,
    };
  }

  async function enrichLoadItems(items, options = {}) {
    const rows = Array.isArray(items) ? items.map((item) => ({ ...item })) : [];
    const experimentMetrics = buildExperimentMetricMap(options.experiments);
    const experimentCache = new Map();

    const ensureExperimentMetrics = async (expId) => {
      const normalizedExpId = String(expId || '').trim();
      if (!normalizedExpId) return {};
      if (experimentMetrics.has(normalizedExpId)) {
        return experimentMetrics.get(normalizedExpId) || {};
      }
      if (!experimentCache.has(normalizedExpId)) {
        experimentCache.set(normalizedExpId, fetchExperimentLoadMetrics(normalizedExpId).catch(() => ({})));
      }
      const metrics = await experimentCache.get(normalizedExpId);
      if (metrics && Object.keys(metrics).length) {
        experimentMetrics.set(normalizedExpId, metrics);
      }
      return metrics;
    };

    await Promise.all(rows.map(async (item) => {
      if (item.kind === 'baseline') {
        try {
          const detail = await apiRequestJson(
            `baseline_${item.id}`,
            `/api/backtest_v2/baselines/${encodeURIComponent(item.id)}`,
          );
          const universe = detail?.config_json?.universe || {};
          if (!item.universe_mode) item.universe_mode = String(detail?.config_json?.universe_mode || '').trim();
          if (!item.membership_mode) item.membership_mode = String(universe?.membership_mode || '').trim();
          const start = String(universe?.start || '').trim();
          const end = String(universe?.end || '').trim();
          if (!item.start_year && /^\d{4}/.test(start)) item.start_year = Number(start.slice(0, 4));
          if (!item.end_year && /^\d{4}/.test(end)) item.end_year = Number(end.slice(0, 4));
          if (detail?.linked_exp_id && item.has_result) {
            const metrics = await ensureExperimentMetrics(detail.linked_exp_id);
            item.cagr = metrics?.cagr ?? item.cagr;
            item.max_drawdown = metrics?.max_drawdown ?? item.max_drawdown;
            item.universe_mode = item.universe_mode || metrics?.universe_mode || '';
            item.membership_mode = item.membership_mode || metrics?.membership_mode || '';
            item.start_year = item.start_year || metrics?.start_year;
            item.end_year = item.end_year || metrics?.end_year;
          }
        } catch (_) {
          // best effort only
        }
        return;
      }

      try {
        const metrics = await ensureExperimentMetrics(item.id);
        item.cagr = metrics?.cagr ?? item.cagr;
        item.max_drawdown = metrics?.max_drawdown ?? item.max_drawdown;
        item.universe_mode = item.universe_mode || metrics?.universe_mode || '';
        item.membership_mode = item.membership_mode || metrics?.membership_mode || '';
        item.start_year = item.start_year || metrics?.start_year;
        item.end_year = item.end_year || metrics?.end_year;
      } catch (_) {
        // best effort only
      }
    }));

    return rows;
  }

  globalScope.openExperimentLoadDropdown = openExperimentLoadDropdown;
  globalScope.extractWorkbenchConfigFromExperimentPayload = extractWorkbenchConfigFromExperimentPayload;
  globalScope.clearActiveResultContext = clearActiveResultContext;
  globalScope.applyLoadedConfigToWorkbench = applyLoadedConfigToWorkbench;
  globalScope.loadExperimentConfigToWorkbench = loadExperimentConfigToWorkbench;
  globalScope.loadBaselineToWorkbench = loadBaselineToWorkbench;
  globalScope.loadExperimentBundle = loadExperimentBundle;
})(window);
