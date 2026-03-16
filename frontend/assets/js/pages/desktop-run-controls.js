(function initDesktopRunControls(globalScope) {
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
    const assetScope = String((state.config_draft && state.config_draft.asset_scope) || 'cn_a_equity').trim() || 'cn_a_equity';
    if (isLockedCandidatePreset(requestedPreset)) {
      return {
        preset: requestedPreset,
        fast_mode: true,
        asset_scope: assetScope,
      };
    }
    const d = buildConfigDraft();
    return {
      preset: requestedPreset,
      config_json: d,
      fast_mode: true,
      asset_scope: String(d?.asset_scope || assetScope).trim() || 'cn_a_equity',
    };
  }

  function runPayloadFromDraft(preset) {
    return resolveRuntimeConfigHandoff(preset);
  }

  async function runExperiment(presetOverride = null) {
    const requestedPreset = selectedExperimentPreset(presetOverride || 'single');
    const draft = buildConfigDraft();
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
    buildConfigDraft();
    if (!state.active_exp?.exp_id) {
      throw new Error('execution preview 需要先运行或加载一个实验');
    }
    const body = {
      config_json: state.config_draft,
      asset_scope: String(state.config_draft?.asset_scope || 'cn_a_equity').trim() || 'cn_a_equity',
      exp_id: state.active_exp?.exp_id || null,
      as_of_date: byId('wbExecDate')?.value || null,
      top_n: Number(state.config_draft?.position_risk?.max_positions || 10),
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
})(window);
