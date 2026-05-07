/* desktop shell owner: baseline save path */
(function initDesktopShellSaveOrchestration(globalScope) {
  function sanitizePersistedConfigDraft(draft) {
    if (typeof buildFrontendSemanticPayload === 'function') {
      return buildFrontendSemanticPayload(draft);
    }
    const core = globalScope.configDraftCore;
    if (core && typeof core.serializeFrontendSemanticConfig === 'function') {
      return core.serializeFrontendSemanticConfig(draft);
    }
    throw new Error('Frontend semantic config serializer is not available');
  }

  async function saveCurrentBaseline() {
    const currentDraft = buildConfigDraft();
    const formalDraft = sanitizePersistedConfigDraft(currentDraft);
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
        config_json: formalDraft,
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
      universe_mode: formalDraft?.universe_mode || null,
      membership_mode: formalDraft?.universe?.membership_mode || null,
    };
    state.loaded_source_config = cloneJson(formalDraft);
    state.loaded_source_snapshot = stableSerializeConfig(formalDraft || {});
    syncWorkbenchLoadedSourceToUrl(state.loaded_source_kind, state.loaded_source_id);
    syncLoadHint(state.loaded_source_id);
    syncLoadedSourceUI();
    addLog(`基线已保存：${state.loaded_source_id}${linkedExpId ? ` | 关联实验=${linkedExpId}` : ' | 无关联结果'}`);
  }

  globalScope.saveCurrentBaseline = saveCurrentBaseline;
  globalScope.sanitizePersistedConfigDraft = sanitizePersistedConfigDraft;
})(window);
