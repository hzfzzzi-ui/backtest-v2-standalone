(function initDesktopLoadControls(globalScope) {
  async function openExperimentLoadDropdown(anchorEl = null) {
    const existing = document.getElementById('wbLoadDropdown');
    if (existing) {
      existing.remove();
      return;
    }
    const baselinePayload = await apiRequestJson('baselines', '/api/backtest_v2/baselines');
    const experimentPayload = await apiRequestJson('experiments', '/api/backtest_v2/experiments');
    const items = await enrichLoadItems(normalizeLoadItems(baselinePayload?.items || [], experimentPayload));
    if (!items.length) {
      addLog('没有可加载的实验');
      return;
    }
    const dd = document.createElement('div');
    dd.id = 'wbLoadDropdown';
    dd.className = 'wb-load-dropdown';
    const activeSourceId = String(state.loaded_source_id || '').trim();
    const activeSourceKind = String(state.loaded_source_kind || '').trim();
    items.forEach((item) => {
      const sourceId = String(item?.id || '').trim();
      const kindClass = item?.kind === 'baseline' ? 'baseline' : 'experiment';
      const row = document.createElement('button');
      row.type = 'button';
      row.className = `wb-load-item wb-config-center-item wb-load-item-${kindClass}${sourceId && sourceId === activeSourceId && item.kind === activeSourceKind ? ' active' : ''}`;
      row.innerHTML = `
      <div class="wb-load-item-head">
        <span class="wb-load-kind ${loadItemBadgeClass(item)}">${esc(loadItemBadgeLabel(item))}</span>
        <span class="wb-config-center-title">${esc(item?.label || sourceId)}</span>
      </div>
      <span class="wb-config-center-desc">${esc(experimentLoadSummary(item))}</span>
    `;
      row.addEventListener('click', async () => {
        dd.remove();
        try {
          if (item.kind === 'experiment') await loadExperimentBundle(sourceId);
          else await loadBaselineToWorkbench(sourceId);
        } catch (e) {
          addLog(`加载失败: ${e?.message || e}`);
        }
      });
      dd.appendChild(row);
    });
    (anchorEl || byId('wbQuickLoad') || byId('wbRunBtn'))?.parentElement?.appendChild(dd);
    const dismiss = (e) => {
      const btn = anchorEl || byId('wbQuickLoad');
      if (!dd.contains(e.target) && e.target !== btn) {
        dd.remove();
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
    state.execution_preview = null;
    state.selected_symbol = '';
    state.symbol_series_cache = {};
    state.symbol_series_loading = false;
    if (typeof window.clearDesktopResultsWorkbenchState === 'function') {
      window.clearDesktopResultsWorkbenchState(state);
    }
    const bridge = getResultsWorkbenchBridge();
    if (bridge && typeof bridge.clear === 'function') bridge.clear();
  }

  function applyLoadedConfigToWorkbench(workbenchConfig, meta) {
    if (!workbenchConfig || typeof workbenchConfig !== 'object') throw new Error('缺少可回填配置');
    const applied = applyConfigToUI(workbenchConfig);
    if (applied?.unsupportedStrategy) {
      throw new Error(`配置使用已移除策略 ${applied.unsupportedStrategy}`);
    }
    setSelectedLockedCandidatePreset('');
    clearActiveResultContext();
    state.loaded_config_meta = {
      config_id: String(meta?.config_id || '').trim() || '-',
      display_name: String(meta?.display_name || meta?.name || meta?.config_id || '').trim() || '-',
      name: String(meta?.name || meta?.display_name || meta?.config_id || '').trim() || '-',
      source_type: String(meta?.source_type || 'derived').trim() || 'derived',
      owner: String(meta?.owner || 'manual').trim() || 'manual',
      locked: !!meta?.locked,
      baseline_of: null,
      universe_mode: workbenchConfig?.universe_mode || null,
      membership_mode: workbenchConfig?.universe?.membership_mode || null,
    };
    state.loaded_config_json = cloneJson(workbenchConfig);
    state.config_id = state.loaded_config_meta.config_id;
    state.loaded_source_kind = String(meta?.loaded_kind || '').trim() || '';
    state.loaded_source_id = String(meta?.loaded_id || '').trim() || '';
    syncWorkbenchConfigSourceToUrl(state.loaded_source_kind, state.loaded_source_id);
    buildConfigDraft();
    state.loaded_config_snapshot = stableSerializeConfig(state.config_draft || {});
    syncConfigSourceUI();
    renderRunHints();
    syncExitLinkage();
    updateAtrNote();
    syncLoadHint(state.loaded_source_id);
    renderRightInspector();
  }

  async function loadExperimentConfigToWorkbench(expId) {
    const normalizedExpId = String(expId || '').trim();
    if (!normalizedExpId) throw new Error('缺少 experiment_id');
    addLog(`导入实验配置: ${normalizedExpId}`);
    const manifest = await apiRequestJson(
      'experiment_manifest',
      `/api/backtest_v2/experiments/${encodeURIComponent(normalizedExpId)}/manifest`,
    );
    const configRel = String(manifest?.artifacts?.config || 'config.json').trim();
    const configPayload = await apiRequestJson(
      'artifact_read_config',
      '/api/backtest_v2/artifacts/read',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exp_id: normalizedExpId, rel_path: configRel }),
      },
    );
    const workbenchConfig = extractWorkbenchConfigFromExperimentPayload(configPayload?.data);
    if (!workbenchConfig || typeof workbenchConfig !== 'object') {
      throw new Error(`实验 ${normalizedExpId} 缺少可回填的 workbench_config`);
    }
    applyLoadedConfigToWorkbench(workbenchConfig, {
      config_id: `expcfg:${normalizedExpId}`,
      display_name: `实验配置 ${normalizedExpId}`,
      name: `实验配置 ${normalizedExpId}`,
      source_type: 'derived',
      owner: 'manual',
      locked: false,
      loaded_kind: 'experiment',
      loaded_id: normalizedExpId,
    });
    addLog(`已导入实验配置: ${normalizedExpId}`);
  }

  async function loadBaselineToWorkbench(baselineId) {
    const normalizedBaselineId = String(baselineId || '').trim();
    if (!normalizedBaselineId) throw new Error('缺少 baseline_id');
    addLog(`导入基线: ${normalizedBaselineId}`);
    const payload = await apiRequestJson(
      `baseline_${normalizedBaselineId}`,
      `/api/backtest_v2/baselines/${encodeURIComponent(normalizedBaselineId)}`,
    );
    const workbenchConfig = payload?.config_json;
    if (!workbenchConfig || typeof workbenchConfig !== 'object') {
      throw new Error(`基线 ${normalizedBaselineId} 缺少 config_json`);
    }
    applyLoadedConfigToWorkbench(workbenchConfig, {
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
    if (linkedExpId && payload?.has_result) {
      await loadHistoricalExperiment(linkedExpId);
    } else {
      clearActiveResultContext();
      renderRightInspector();
    }
    addLog(`已导入基线：${normalizedBaselineId}`);
  }

  async function loadExperimentBundle(expId) {
    const normalizedExpId = String(expId || '').trim();
    if (!normalizedExpId) throw new Error('缺少 experiment_id');
    await loadExperimentConfigToWorkbench(normalizedExpId);
    await loadHistoricalExperiment(normalizedExpId);
  }

  globalScope.openExperimentLoadDropdown = openExperimentLoadDropdown;
  globalScope.extractWorkbenchConfigFromExperimentPayload = extractWorkbenchConfigFromExperimentPayload;
  globalScope.clearActiveResultContext = clearActiveResultContext;
  globalScope.applyLoadedConfigToWorkbench = applyLoadedConfigToWorkbench;
  globalScope.loadExperimentConfigToWorkbench = loadExperimentConfigToWorkbench;
  globalScope.loadBaselineToWorkbench = loadBaselineToWorkbench;
  globalScope.loadExperimentBundle = loadExperimentBundle;
})(window);
