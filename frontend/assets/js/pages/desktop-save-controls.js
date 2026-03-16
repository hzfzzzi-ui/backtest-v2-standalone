(function initDesktopSaveControls(globalScope) {
  async function saveConfig(kind = 'draft') {
    const cfg = buildConfigDraft();
    const body = {
      config_json: cfg,
      name: 'workbench',
      display_name: 'workbench',
      tags: ['draft'],
      source_type: 'derived',
      owner: 'manual',
      locked: false,
      baseline_of: null,
    };
    if (kind === 'template') {
      body.name = `template_${Date.now()}`;
      body.display_name = body.name;
      body.tags = ['template'];
      body.source_type = 'template';
    } else if (kind === 'flow_script') {
      body.name = `flow_script_${Date.now()}`;
      body.display_name = body.name;
      body.tags = ['flow_script'];
    }
    const payload = await apiRequestJson('configs_save', '/api/backtest_v2/configs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    rememberLoadedSource(payload, stableSerializeConfig(cfg), cfg);
    addLog(`配置已保存(${kind}): ${payload.config_id}`);
    await loadConfigList();
  }

  async function saveCurrentBaseline() {
    const currentDraft = buildConfigDraft();
    const suggestedName = String(
      state.loaded_source_kind === 'baseline'
        ? (state.loaded_source_id || DEFAULT_BOOTSTRAP_BASELINE_ID)
        : (state.loaded_source_meta?.display_name || DEFAULT_BOOTSTRAP_BASELINE_ID)
    ).trim() || DEFAULT_BOOTSTRAP_BASELINE_ID;
    const baselineName = String(window.prompt('请输入基线名称', suggestedName) || '').trim();
    if (!baselineName) return;
    const linkedExpId = currentLoadedSourceMode() === 'loaded-clean'
      ? String(state.active_result?.exp_id || '').trim()
      : '';
    const payload = await apiRequestJson('baseline_save', '/api/backtest_v2/baselines', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        baseline_id: baselineName,
        name: baselineName,
        display_name: baselineName,
        config_json: currentDraft,
        linked_exp_id: linkedExpId || null,
        owner: 'manual',
        locked: true,
      }),
    });
    state.loaded_source_kind = 'baseline';
    state.loaded_source_id = String(payload?.baseline_id || baselineName).trim();
    state.loaded_source_meta = {
      source_id: state.loaded_source_id,
      config_ref: state.loaded_source_id,
      display_name: String(payload?.display_name || payload?.name || state.loaded_source_id),
      name: String(payload?.name || payload?.display_name || state.loaded_source_id),
      source_type: 'baseline',
      owner: String(payload?.owner || 'manual'),
      locked: true,
      baseline_of: null,
      universe_mode: currentDraft?.universe_mode || null,
      membership_mode: currentDraft?.universe?.membership_mode || null,
    };
    state.loaded_source_config = cloneJson(currentDraft);
    state.loaded_source_snapshot = stableSerializeConfig(state.config_draft || currentDraft || {});
    syncWorkbenchLoadedSourceToUrl(state.loaded_source_kind, state.loaded_source_id);
    syncLoadHint(state.loaded_source_id);
    syncLoadedSourceUI();
    addLog(`基线已保存：${state.loaded_source_id}${linkedExpId ? ` | 关联实验=${linkedExpId}` : ' | 无关联结果'}`);
  }

  globalScope.saveConfig = saveConfig;
  globalScope.saveCurrentBaseline = saveCurrentBaseline;
})(window);
