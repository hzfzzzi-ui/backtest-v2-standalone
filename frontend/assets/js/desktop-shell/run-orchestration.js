/* desktop shell owner: run_orchestration dispatch/poll path */
(function initDesktopShellRunOrchestration(globalScope) {
  function sanitizeRuntimeConfigDraft(draft) {
    if (typeof buildFrontendSemanticPayload === 'function') {
      return buildFrontendSemanticPayload(draft);
    }
    const core = globalScope.configDraftCore;
    if (core && typeof core.serializeFrontendSemanticConfig === 'function') {
      return core.serializeFrontendSemanticConfig(draft);
    }
    throw new Error('Frontend semantic config serializer is not available');
  }

  function setRunStatusText(text) {
    const statusEl = byId('wbRunStatus');
    if (statusEl) statusEl.textContent = text;
  }

  async function pollJob(jobId) {
    const btn = byId('wbRunBtn');
    const originalText = btn ? btn.textContent : '';
    const originalClass = btn ? btn.className : '';
    let canceled = false;
    const startedAt = Date.now();
    const baseWindowMs = 30 * 60 * 1000;
    const extendStepMs = 5 * 60 * 1000;
    const hardCapMs = 60 * 60 * 1000;
    let deadlineTs = startedAt + baseWindowMs;
    let lastProgress = -1;

    if (btn) {
      btn.textContent = '取消运行';
      btn.className = 'wb-btn-run wb-btn-danger';
      const onCancel = async () => {
        canceled = true;
        btn.removeEventListener('click', onCancel);
        try {
          await apiRequestJson('job_cancel', `/api/backtest_v2/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' });
        } catch (_) {
          // best effort
        }
      };
      btn.addEventListener('click', onCancel);
      var _cleanupCancel = () => {
        btn.removeEventListener('click', onCancel);
        btn.textContent = originalText;
        btn.className = originalClass;
      };
    }

    try {
      for (;;) {
        if (canceled) {
          setRunStatusText('已取消');
          return null;
        }
        const j = await apiRequestJson('job_poll', `/api/backtest_v2/jobs/${encodeURIComponent(jobId)}`);
        const curProgress = Number(j.progress_pct ?? 0);
        if (Number.isFinite(curProgress) && curProgress > lastProgress) {
          lastProgress = curProgress;
          const hardDeadline = startedAt + hardCapMs;
          deadlineTs = Math.min(deadlineTs + extendStepMs, hardDeadline);
        }
        const remainSec = Math.max(0, Math.floor((deadlineTs - Date.now()) / 1000));
        setRunStatusText(`${j.status} ${j.progress_pct ?? 0}% ${j.message || ''} | 剩余${remainSec}s`);
        if (j.status === 'success') return j.result || null;
        if (j.status === 'failed') throw new Error(j.error || 'job failed');
        if (j.status === 'canceled') {
          setRunStatusText('已取消');
          return null;
        }
        if (Date.now() >= deadlineTs) {
          throw new Error(`job timeout (exceeded ${Math.floor((Date.now() - startedAt) / 1000)}s; cap=${Math.floor(hardCapMs / 1000)}s)`);
        }
        await new Promise((resolve) => setTimeout(resolve, 800));
      }
    } finally {
      if (typeof _cleanupCancel === 'function') _cleanupCancel();
    }
  }

  function resolveRuntimeConfigHandoff(preset) {
    const requestedPreset = selectedExperimentPreset(preset);
    const assetScope = resolvePreferredAssetScope(state.config_draft && state.config_draft.asset_scope);
    if (isLockedCandidatePreset(requestedPreset)) {
      return {
        preset: requestedPreset,
        fast_mode: true,
        asset_scope: assetScope,
      };
    }
    const loadedSourceConfig = cloneJson(state.loaded_source_config) || null;
    const executionContract = loadedSourceConfig?.unified_runtime?.execution_contract
      && typeof loadedSourceConfig.unified_runtime.execution_contract === 'object'
      ? loadedSourceConfig.unified_runtime.execution_contract
      : (
        loadedSourceConfig?.unified_runtime?.combo_context?.execution_contract
        && typeof loadedSourceConfig.unified_runtime.combo_context.execution_contract === 'object'
          ? loadedSourceConfig.unified_runtime.combo_context.execution_contract
          : null
      );
    const componentSourceContract = loadedSourceConfig?.unified_runtime?.component_source_contract
      && typeof loadedSourceConfig.unified_runtime.component_source_contract === 'object'
      ? loadedSourceConfig.unified_runtime.component_source_contract
      : (
        loadedSourceConfig?.unified_runtime?.combo_context?.component_source_contract
        && typeof loadedSourceConfig.unified_runtime.combo_context.component_source_contract === 'object'
          ? loadedSourceConfig.unified_runtime.combo_context.component_source_contract
          : null
      );
    const unifiedRuntimePassthrough = !!(
      loadedSourceConfig &&
      loadedSourceConfig.unified_runtime &&
      typeof loadedSourceConfig.unified_runtime === 'object' &&
      loadedSourceConfig.unified_runtime.enabled === true &&
      (executionContract || componentSourceContract)
    );
    const d = unifiedRuntimePassthrough ? loadedSourceConfig : buildConfigDraft();
    const configJson = sanitizeRuntimeConfigDraft(d);
    const payload = {
      preset: requestedPreset,
      config_json: configJson,
      fast_mode: true,
      asset_scope: resolvePreferredAssetScope(configJson?.asset_scope || d?.asset_scope || assetScope),
    };
    if (
      String(state.loaded_source_kind || '').trim().toLowerCase() === 'baseline' &&
      String(state.loaded_source_id || '').trim() &&
      state.loaded_source_dirty !== true &&
      state.loaded_source_meta?.execution_contract_ref &&
      typeof state.loaded_source_meta.execution_contract_ref === 'object'
    ) {
      payload.baseline_id = String(state.loaded_source_id || '').trim();
      payload.execution_contract_ref = cloneJson(state.loaded_source_meta.execution_contract_ref);
    }
    return payload;
  }

  function runPayloadFromDraft(preset) {
    return resolveRuntimeConfigHandoff(preset);
  }

  async function runExperiment(presetOverride = null) {
    const requestedPreset = selectedExperimentPreset(presetOverride || 'single');
    const draft = buildConfigDraft();
    const assetScope = resolvePreferredAssetScope(draft?.asset_scope);
    if (!isRuntimeSupportedAssetScope(assetScope)) {
      throw new Error(`${assetScopeDisplayName(assetScope)}入口准备中，当前未支持运行`);
    }
    const errors = validateConfigDraft(draft);
    if (errors.length) {
      const message = '配置校验失败：' + errors.join('；');
      const statusEl = byId('wbRunStatus');
      if (statusEl) statusEl.textContent = message;
      throw new Error(message);
    }
    const payload = runPayloadFromDraft(requestedPreset);
    addLog('POST /api/backtest_v2/experiment/run_async (' + requestedPreset + ')');
    const q = await apiRequestJson('experiment_run_async', '/api/backtest_v2/experiment/run_async', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await pollJob(q.job_id);
    state.active_exp = result;
    state.active_result = result;
    if (typeof syncExperimentIdToUrl === 'function') syncExperimentIdToUrl(result?.exp_id || result?.experiment_id || '');
    await loadActiveArtifacts();
    if (isLockedCandidatePreset(requestedPreset) && !state.active_artifacts?.run_meta?.candidate) {
      throw new Error('candidate preset mismatch: ' + (result?.exp_id || '-') + ' did not return locked candidate artifacts');
    }
    renderExperimentResult(result);
    renderRightInspector();
  }

  function renderExperimentResult(result) {
    const dimsEl = byId('wbDims');
    if (dimsEl) dimsEl.textContent = `exp_id=${result?.exp_id || '-'} | status=${result?.status || '-'}`;
  }

  async function previewExecution() {
    const draft = buildConfigDraft();
    if (!state.active_exp?.exp_id) {
      throw new Error('execution preview 需要先运行或加载一个实验');
    }
    const configJson = sanitizeRuntimeConfigDraft(draft);
    const body = {
      config_json: configJson,
      asset_scope: resolvePreferredAssetScope(configJson?.asset_scope || draft?.asset_scope),
      exp_id: state.active_exp?.exp_id || null,
      as_of_date: byId('wbExecDate')?.value || null,
      top_n: Number(draft?.position_risk?.max_positions || 10),
    };
    let payload;
    try {
      payload = await apiRequestJson('execution_preview', '/api/backtest_v2/execution/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch (e) {
      const httpStatus = e?.httpStatus;
      if (httpStatus === 404 || httpStatus === 405) {
        state.execution_api_enabled = false;
        if (typeof syncResultsWorkbenchExecution === 'function') syncResultsWorkbenchExecution();
        else renderExecutionPanel();
        throw new Error('后端未启用 execution preview');
      }
      throw e;
    }
    state.execution_api_enabled = true;
    state.execution_preview = payload;
    if (typeof syncResultsWorkbenchExecution === 'function') syncResultsWorkbenchExecution();
    else renderExecutionPanel();
    if (state.execution_preview?.files?.execution_list_json_path) addLog(`execution_list: ${state.execution_preview.files.execution_list_json_path}`);
  }

  function copyExecJson() {
    if (!state.execution_preview) return;
    navigator.clipboard?.writeText(JSON.stringify(state.execution_preview, null, 2));
    addLog('执行清单已复制到剪贴板');
  }

  async function runByMode() {
    if (state.mode === 'execution') {
      await previewExecution();
      switchInspectorTab('exec');
      return;
    }
    if (state.mode === 'single') {
      await runExperiment('SINGLE_RUN_V1');
      return;
    }
    await runExperiment();
  }

  globalScope.pollJob = pollJob;
  globalScope.resolveRuntimeConfigHandoff = resolveRuntimeConfigHandoff;
  globalScope.runPayloadFromDraft = runPayloadFromDraft;
  globalScope.runExperiment = runExperiment;
  globalScope.renderExperimentResult = renderExperimentResult;
  globalScope.previewExecution = previewExecution;
  globalScope.copyExecJson = copyExecJson;
  globalScope.runByMode = runByMode;
  globalScope.sanitizeRuntimeConfigDraft = sanitizeRuntimeConfigDraft;
})(window);
