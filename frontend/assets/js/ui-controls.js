/* ui-controls.js: transitional desktop control wiring only. */
/* Config compile/validate truth belongs to window.configDraftCore, not this shell file. */
/* ui-controls.js: UI interactions, config building, drawer, dock tabs */
/* Globals used: state, byId, esc, num, pct, fmtInt, fmtMoney, setTextById, setHtmlById,
   getStrategySelector, getStrategyPackValue, COMPOSE_MODULES, reasonZh, addLog,
   apiRequestJson, setStatusItems, _apiTag,
   renderPerfPanel, renderNavChartLW, renderDdChartLW,
   loadActiveArtifacts, renderRightInspector, renderArtifacts (from other modules) */

const LOCKED_CANDIDATE_PRESETS = {
  'v2-breakout-atr-stop-k10-candidate': {
    hint: 'Locked candidate from baseline ATR stop 1.0 preset',
    title: 'This candidate reuses the baseline ATR stop 1.0 runtime config snapshot for preview and run.',
  },
  'v2-breakout-br35-atr10-candidate': {
    hint: 'Locked candidate from ATR1.0 + breakout_window=35 preset',
    title: 'This candidate reuses the ATR1.0 + breakout_window=35 runtime config snapshot for preview and run.',
  },
};

function lockedCandidatePresetMeta(preset) {
  const key = String(preset || '').trim().toLowerCase();
  return LOCKED_CANDIDATE_PRESETS[key] || null;
}

function isLockedCandidatePreset(preset) {
  return !!lockedCandidatePresetMeta(preset);
}

function selectedExperimentPreset(defaultPreset = 'single') {
  const selected = String(state.selected_locked_candidate_preset || '').trim();
  return selected || defaultPreset || 'single';
}

function resolveMultiAlphaUiHelper(name) {
  const globalHelper = globalThis?.[name];
  if (typeof globalHelper === 'function') return globalHelper;
  const namespaceHelper = globalThis?.multiAlphaUi?.[name];
  if (typeof namespaceHelper === 'function') return namespaceHelper;
  return null;
}

function cleanupUnsupportedOptionsCompat(selectEl) {
  const helper = resolveMultiAlphaUiHelper('cleanupUnsupportedOptions');
  if (helper) {
    helper(selectEl);
    return;
  }
  if (!selectEl) return;
  Array.from(selectEl.querySelectorAll('option[data-unsupported="1"]')).forEach((option) => option.remove());
}

function setSelectValuePreserveUnsupportedCompat(id, value, fallback = '') {
  const helper = resolveMultiAlphaUiHelper('setSelectValuePreserveUnsupported');
  if (helper) {
    helper(id, value, fallback);
    return;
  }
  const selectEl = byId(id);
  if (!selectEl) return;
  cleanupUnsupportedOptionsCompat(selectEl);
  const normalized = value == null ? '' : String(value);
  if (normalized && !Array.from(selectEl.options).some((option) => option.value === normalized)) {
    const option = document.createElement('option');
    option.value = normalized;
    option.textContent = 'UNSUPPORTED: ' + normalized;
    option.dataset.unsupported = '1';
    selectEl.appendChild(option);
  }
  const target = normalized || fallback || selectEl.value;
  if (target) selectEl.value = target;
}

function syncPresetHint() {
  const hint = byId('wbPresetHint');
  if (!hint) return;
  const executionMode = state.mode === 'execution';
  const preset = String(state.selected_locked_candidate_preset || '').trim();
  if (executionMode) {
    hint.textContent = preset
      ? 'Execution preview uses the locked candidate runtime snapshot'
      : 'Execution preview and run share the same runtime entry';
    hint.title = preset
      ? 'The locked candidate only affects the runtime snapshot used by preview and run.'
      : 'Execution preview and run share the same runtime entry';
    return;
  }
  const candidateMeta = lockedCandidatePresetMeta(preset);
  if (candidateMeta) {
    hint.textContent = `Preset: ${candidateMeta.hint}`;
    hint.title = candidateMeta.title;
    return;
  }
  const meta = state.loaded_source_meta;
  const sourceKind = String(state.loaded_source_kind || '').trim().toLowerCase();
  const sourceId = String(state.loaded_source_id || '').trim();
  const sourceLabel = meta?.display_name || meta?.name || compactLoadedSourceLabel(sourceKind, sourceId);
  const mode = currentLoadedSourceMode();
  if (sourceId && mode === 'source-clean') {
    hint.textContent = `Source: ${sourceLabel}`;
    hint.title = `Loaded source ${sourceLabel}; preview and run share the same runtime snapshot.`;
    return;
  }
  if (sourceId && mode === 'source-dirty') {
    hint.textContent = `Draft diverged from ${sourceLabel}`;
    hint.title = 'The source marker is kept, but preview and run now use the current draft snapshot.';
    return;
  }
  hint.textContent = 'Current draft';
  hint.title = 'Preview and run use the current draft by default.';
}

function setSelectedLockedCandidatePreset(preset) {
  state.selected_locked_candidate_preset = String(preset || '').trim();
  syncPresetHint();
  syncLoadedSourceUI();
}

const MEMBERSHIP_MODE_SUPPORTED_UNIVERSES = new Set(['HS300_ZZ500', 'CSI1000']);

function supportsMembershipMode(universeMode) {
  return MEMBERSHIP_MODE_SUPPORTED_UNIVERSES.has(String(universeMode || '').trim().toUpperCase());
}

function membershipModeFromUiValue(value) {
  return String(value || '').trim().toLowerCase() === 'fixed' ? 'START_SNAPSHOT' : 'PIT_DYNAMIC';
}

function membershipUiValueFromConfig(membershipMode, universeMode) {
  const normalizedMode = String(membershipMode || '').trim().toUpperCase();
  if (normalizedMode === 'START_SNAPSHOT' || normalizedMode === 'CURRENT_SNAPSHOT') return 'fixed';
  if (normalizedMode === 'PIT_DYNAMIC') return 'dynamic';
  return supportsMembershipMode(universeMode) ? 'fixed' : 'dynamic';
}

function syncMembershipModeButtons(value) {
  const uiValue = String(value || 'dynamic').trim().toLowerCase() === 'fixed' ? 'fixed' : 'dynamic';
  const selectEl = byId('wbConstituent');
  if (selectEl) selectEl.value = uiValue;
  document.querySelectorAll('#wbConstituentGroup button').forEach((button) => {
    button.classList.toggle('active', button.getAttribute('data-val') === uiValue);
  });
}

function updateMembershipModeVisibility(mode = null) {
  const universeMode = String(mode || byId('wbUniverseMode')?.value || '').trim().toUpperCase();
  const wrap = byId('wbConstituentWrap');
  if (wrap) wrap.hidden = !supportsMembershipMode(universeMode);
}

function updateUniverseInputVisibility() {
  const mode = byId('wbUniverseMode')?.value || 'ALL_A';
  const symbolsWrap = byId('wbSymbolsWrap');
  const industryWrap = byId('wbIndustryPickerWrap');
  if (symbolsWrap) symbolsWrap.style.display = mode === 'CUSTOM' ? '' : 'none';
  if (industryWrap) industryWrap.hidden = mode !== 'INDUSTRY';
  if (mode === 'INDUSTRY') loadIndustryPicker();
  updateMembershipModeVisibility(mode);
}

let _industryPickerLoaded = false;
async function loadIndustryPicker() {
  if (_industryPickerLoaded) return;
  const container = byId('wbIndustryPicker');
  if (!container) return;
  try {
    const data = await apiRequestJson('industries', '/api/backtest_v2/industries', {
      retryCount: 0,
    });
    const industries = Array.isArray(data.industries) ? data.industries : [];
    if (!industries.length) {
      container.innerHTML = '<span style="color:#888">Industry list is empty. Refresh industry data and retry.</span>';
      return;
    }
    container.innerHTML = '';
    for (const name of industries) {
      const label = document.createElement('label');
      label.className = 'wb-industry-chip';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.value = name;
      cb.addEventListener('change', () => buildConfigDraft());
      label.appendChild(cb);
      label.appendChild(document.createTextNode(' ' + name));
      container.appendChild(label);
    }
    _industryPickerLoaded = true;
  } catch (e) {
    container.innerHTML = '<span style="color:#c33">Failed to load industry list</span>';
  }
}

function getSelectedIndustries() {
  const container = byId('wbIndustryPicker');
  if (!container) return [];
  return Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value);
}

function setDrawerPanel(panel) {
  state.drawer_panel = panel || 's1';
  document.querySelectorAll('.wb-rail-btn').forEach((btn) => btn.classList.toggle('active', btn.getAttribute('data-panel') === state.drawer_panel));
  document.querySelectorAll('.wb-module').forEach((m) => m.classList.toggle('active', m.getAttribute('data-module') === state.drawer_panel));
  const titleEl = byId('wbDrawerTitle');
  if (titleEl) {
    const titles = {
      s1: 'S1 Universe',
      s2: 'S2 Market Regime',
      s3: 'S3 Signal Generation',
      s4: 'S4 Composite Signal',
      s5: 'S5 Ranking Score',
      s6: 'S6 Portfolio Build',
      s7: 'S7 Risk Budget',
      s8: 'S8 Market Filter',
      s9: 'S9 Exit Rules',
      json: 'JSON',
      history: 'Experiment History',
    };
    titleEl.textContent = titles[state.drawer_panel] || state.drawer_panel;
  }
}

function toggleDrawer(force = null) {
  const app = document.querySelector('.wb-app');
  if (!app) return;
  const hide = force == null ? !app.classList.contains('wb-drawer-hidden') : !!force;
  app.classList.toggle('wb-drawer-hidden', hide);
}

function switchDockTab(tab) {
  const aliases = {
    perf: 'buy_funnel',
    runner: 'buy_funnel',
    explain: 'buy_funnel',
    buy: 'buy_funnel',
    buy_funnel: 'buy_funnel',
    sell: 'buy_funnel',
    sell_funnel: 'buy_funnel',
    exec: 'execution',
    execution: 'execution',
    trades: 'execution',
    logs: 'logs',
  };
  const next = aliases[String(tab || 'buy_funnel').toLowerCase()] || 'buy_funnel';
  state.dock_tab = next;
  document.querySelectorAll('.wb-analysis-tabs button[data-dock], .wb-dock-tabs button[data-dock]').forEach((b) => {
    b.classList.toggle('active', b.getAttribute('data-dock') === next);
  });
  document.querySelectorAll('.wb-dock-panel').forEach((p) => p.classList.remove('active'));
  const bridge = window.resultsWorkbenchBridge || null;
  const mounted = !!bridge?.isMounted?.();
  const openPanels = {
    symbolPanel: false,
    funnelPanel: false,
    tradesPanel: false,
  };
  if (next === 'buy_funnel') openPanels.funnelPanel = true;
  if (next === 'execution') openPanels.tradesPanel = true;
  if (mounted && typeof bridge.patchViewState === 'function') {
    bridge.patchViewState({ openPanels });
    const targetPanel = Object.entries(openPanels).find(([, value]) => value)?.[0];
    if (targetPanel) {
      requestAnimationFrame(() => {
        document.querySelector(`[data-result-panel="${targetPanel}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
    return;
  }
  return;
}

function validateConfigDraft(draft) {
  const core = window.configDraftCore;
  if (!core || typeof core.validateConfigDraft !== 'function') {
    throw new Error('configDraftCore.validateConfigDraft is not available');
  }
  return core.validateConfigDraft(draft);
}

function flattenObject(obj, prefix = '', out = {}) {
  if (obj === null || obj === undefined) return out;
  if (typeof obj !== 'object') {
    out[prefix] = obj;
    return out;
  }
  if (Array.isArray(obj)) {
    out[prefix] = obj;
    return out;
  }
  Object.keys(obj).sort().forEach((k) => {
    const p = prefix ? `${prefix}.${k}` : k;
    const v = obj[k];
    if (v && typeof v === 'object' && !Array.isArray(v)) flattenObject(v, p, out);
    else out[p] = v;
  });
  return out;
}

function renderConfigDiff() {
  const el = byId('wbConfigDiff');
  if (!el) return;
  const draft = state.config_draft || {};
  const groupCfg = state.active_artifacts?.config || null;
  if (!groupCfg) {
    el.textContent = 'Current result is missing config.json';
    return;
  }
  const a = flattenObject(draft);
  const b = flattenObject(groupCfg);
  const keys = Array.from(new Set([...Object.keys(a), ...Object.keys(b)])).sort();
  const lines = [];
  keys.forEach((k) => {
    const va = JSON.stringify(a[k]);
    const vb = JSON.stringify(b[k]);
    if (va !== vb) lines.push(`${k}\n  draft=${va}\n  group=${vb}`);
  });
  el.textContent = lines.length ? lines.join('\n\n') : 'No diff';
}

function updateSignalCompositionSurface(draft, errors) {
  const notice = byId('wbSignalCompositionNotice');
  const output = byId('wbCompOutput');
  if (!notice && !output) return;
  const multiAlphaEnabled = !!(draft && draft.signal_composition && draft.signal_composition.enabled)
    || !!(Array.isArray(draft && draft.signal_generation && draft.signal_generation.modules) && draft.signal_generation.modules.length);
  if (!multiAlphaEnabled) {
    if (notice) notice.textContent = 'multi-alpha disabled; current run stays on the single-strategy path.';
    if (output) output.textContent = 'single-strategy draft only';
    return;
  }
  const modules = Array.isArray(draft && draft.signal_generation && draft.signal_generation.modules)
    ? draft.signal_generation.modules.map((module) => (supportedMultiAlphaDescriptor(module && module.name) || {}).label || String((module && module.name) || '-'))
    : [];
  const composition = draft && draft.signal_composition ? draft.signal_composition : {};
  const regimeBits = MULTI_ALPHA_REGIMES.map((regime) => {
    const values = Array.isArray(composition.regime_matrix && composition.regime_matrix[regime])
      ? composition.regime_matrix[regime]
      : [];
    return regime + '=' + (values.join('+') || '-');
  }).join(' | ');
  if (Array.isArray(errors) && errors.length) {
    if (notice) notice.textContent = 'multi-alpha blocked: ' + errors[0];
    if (output) output.textContent = 'run blocked until validation passes';
    return;
  }
  if (notice) {
    notice.textContent = 'multi-alpha ready: ' + (modules.join(' + ') || '-') + ' | '
      + String(composition.compose_mode || '-') + ' | '
      + String(composition.same_symbol_policy || '-') + ' | '
      + String(composition.holding_ownership || '-');
  }
  if (output) output.textContent = regimeBits + ' | S7=' + String((draft && draft.position_risk && draft.position_risk.portfolio_mode) || '-');
}

function refreshConfigPanels() {
  updateRegimeEngineUi();
  const preview = byId('wbConfigJsonPreview');
  if (preview) preview.textContent = JSON.stringify(state.config_draft || {}, null, 2);
  const errors = validateConfigDraft(state.config_draft || {});
  state.multi_alpha_validation_errors = errors.slice();
  const badge = byId('wbSchemaBadge');
  if (badge) {
    badge.hidden = true;
    if (errors.length) {
      badge.className = 'wb-chip wb-danger';
      badge.textContent = 'Config Error ' + errors.length;
      badge.title = errors.join('\n');
    } else {
      badge.className = 'wb-chip wb-ok';
      badge.textContent = 'Schema OK';
      badge.title = 'OK';
    }
  }
  if (typeof setValidationStatusItems === 'function') {
    setValidationStatusItems(errors.map((message, index) => ({
      title: '配置校验失败',
      message,
      file: 'config_draft',
      detail: 'validation #' + String(index + 1),
    })));
  }
  updateSignalCompositionSurface(state.config_draft || {}, errors);
  renderConfigDiff();
}

function buildConfigDraft() {
  const core = window.configDraftCore;
  if (!core || typeof core.buildConfigDraft !== 'function') {
    throw new Error('configDraftCore.buildConfigDraft is not available');
  }
  return core.buildConfigDraft();
}

function hydrateComposeRows(rows, options = {}) {
  const body = byId('wbComposeRows');
  if (!body) return;
  const useDefault = options.useDefault !== false;
  const data = Array.isArray(rows) && rows.length ? rows : (useDefault ? defaultComposeRows() : []);
  state.multi_alpha_module_state = Object.fromEntries(data.map((row) => [row.name, {
    alpha_id: normalizeMultiAlphaOption(row.alpha_id, row.name),
    family: normalizeMultiAlphaOption(row.family, ''),
    params: cloneJson(row.params) || {},
  }]));
  body.innerHTML = data.map((row) => {
    const supported = supportedMultiAlphaDescriptor(row.name);
    const label = row.label || (supported && supported.label) || row.name;
    const roleOptions = ['trend', 'mean_revert'];
    const selectedRole = normalizeMultiAlphaOption(row.role, (supported && supported.role) || 'trend');
    if (!roleOptions.includes(selectedRole)) roleOptions.push(selectedRole);
    const roleHtml = roleOptions.map((role) => '<option value="' + esc(role) + '"' + (role === selectedRole ? ' selected' : '') + '>' + esc(role) + (supported && role === selectedRole && !['trend', 'mean_revert'].includes(role) ? ' (unsupported)' : '') + '</option>').join('');
    return '<tr data-name="' + esc(row.name) + '" data-label="' + esc(label) + '">'
      + '<td>' + esc(label) + '<div class="wb-mini">' + esc(row.name) + '</div></td>'
      + '<td><input data-k="enabled" type="checkbox" ' + (row.enabled ? 'checked' : '') + '></td>'
      + '<td><select data-k="role" class="formInput" style="width:auto">' + roleHtml + '</select></td>'
      + '<td><input data-k="weight" type="number" step="0.1" class="formInput" value="' + Number(row.weight ?? 0) + '"></td>'
      + '<td><input data-k="priority" type="number" class="formInput" value="' + Number(row.priority ?? 0) + '"></td>'
      + '</tr>';
  }).join('');
  bindDraftListeners(body);
}

function hydrateRegimeMatrix(matrix = null, rows = [], options = {}) {
  const container = byId('wbRegimeMatrix');
  if (!container) return;
  const useDefault = options.useDefault !== false;
  const rowData = Array.isArray(rows) && rows.length ? rows : (useDefault ? defaultComposeRows() : []);
  const moduleNames = composeRowNames(rowData);
  if (!moduleNames.length) {
    container.innerHTML = '<div class="wb-mini">No modules configured</div>';
    return;
  }
  const resolvedMatrix = matrix && typeof matrix === 'object' ? matrix : defaultRegimeMatrix();
  const labels = Object.fromEntries(rowData.map((row) => [row.name, row.label || ((supportedMultiAlphaDescriptor(row.name) || {}).label) || row.name]));
  const header = moduleNames.map((name) => '<th>' + esc(labels[name] || name) + '</th>').join('');
  const body = MULTI_ALPHA_REGIMES.map((regime) => {
    const values = Array.isArray(resolvedMatrix[regime]) ? resolvedMatrix[regime].map((value) => normalizeMultiAlphaName(value)) : [];
    const cells = moduleNames.map((name) => '<td><input type="checkbox" data-regime="' + esc(regime) + '" data-module="' + esc(name) + '" ' + (values.includes(name) ? 'checked' : '') + '></td>').join('');
    return '<tr><td>' + esc(regime) + '</td>' + cells + '</tr>';
  }).join('');
  container.innerHTML = '<label class="wb-field-label">Regime Matrix</label>'
    + '<table class="wb-table wb-table-compact">'
    + '<thead><tr><th>Regime</th>' + header + '</tr></thead>'
    + '<tbody>' + body + '</tbody>'
    + '</table>';
  bindDraftListeners(container);
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll('#wbMode button').forEach((b) => b.classList.toggle('active', b.getAttribute('data-mode') === mode));
  addLog(`Mode switch: ${mode}`);
  buildConfigDraft();
  syncPresetHint();
}

function renderRunHints() {
  // Keep run hints aligned with the current draft and source provenance.
}

function resolveSummaryConfig() {
  const artCfg = (state.active_artifacts || {}).config;
  if (artCfg && typeof artCfg === 'object') {
    const preferredWorkbenchCfg = artCfg?.overrides?.original_workbench_config
      || artCfg?.overrides?.workbench_config
      || artCfg?.workbench_config;
    if (preferredWorkbenchCfg && typeof preferredWorkbenchCfg === 'object') {
      return preferredWorkbenchCfg;
    }
  }
  const runtimeCfg = artCfg && typeof artCfg === 'object' && artCfg.base_config && typeof artCfg.base_config === 'object'
    ? artCfg.base_config
    : artCfg;
  if (runtimeCfg && typeof runtimeCfg === 'object' && (runtimeCfg.strategy || runtimeCfg.universe)) return runtimeCfg;
  return state.config_draft || {};
}

function resolveMultiAlphaSummaryPayload(cfg) {
  const signalGeneration = cfg && cfg.signal_generation && typeof cfg.signal_generation === 'object' ? cfg.signal_generation : {};
  const signalComposition = cfg && cfg.signal_composition && typeof cfg.signal_composition === 'object' ? cfg.signal_composition : {};
  const draftModules = Array.isArray(signalGeneration.modules) ? signalGeneration.modules : [];
  if (draftModules.length) {
    return {
      modules: draftModules,
      composition: signalComposition,
      portfolioMode: (cfg && cfg.position_risk && cfg.position_risk.portfolio_mode) || MULTI_ALPHA_PORTFOLIO_MODE,
    };
  }
  const runtimeStrategy = cfg && cfg.strategy && typeof cfg.strategy === 'object' ? cfg.strategy : {};
  const runtimeParams = runtimeStrategy.params && typeof runtimeStrategy.params === 'object' ? runtimeStrategy.params : {};
  const runtimeMultiAlpha = runtimeParams.multi_alpha && typeof runtimeParams.multi_alpha === 'object' ? runtimeParams.multi_alpha : {};
  const runtimeModules = Array.isArray(runtimeMultiAlpha.signal_generation && runtimeMultiAlpha.signal_generation.modules)
    ? runtimeMultiAlpha.signal_generation.modules
    : [];
  if (!runtimeModules.length) return null;
  return {
    modules: runtimeModules,
    composition: runtimeMultiAlpha.signal_composition || {},
    portfolioMode: runtimeParams.portfolio_mode || (cfg && cfg.position_risk && cfg.position_risk.portfolio_mode) || MULTI_ALPHA_PORTFOLIO_MODE,
  };
}

function formatMultiAlphaModuleList(modules) {
  return (Array.isArray(modules) ? modules : [])
    .map((module) => {
      const name = normalizeMultiAlphaName(module && module.name);
      const desc = supportedMultiAlphaDescriptor(name);
      return (desc && desc.label) || String((module && module.name) || '-');
    })
    .filter(Boolean)
    .join(' + ');
}

function formatMultiAlphaRegimeSummary(regimeMatrix) {
  return MULTI_ALPHA_REGIMES.map((regime) => {
    const values = Array.isArray(regimeMatrix && regimeMatrix[regime]) ? regimeMatrix[regime] : [];
    return regime + '=' + (values.join('+') || '-');
  }).join(' | ');
}

function runtimeStrategySummary(cfg, art) {
  const multiAlpha = resolveMultiAlphaSummaryPayload(cfg);
  if (multiAlpha) {
    const composition = multiAlpha.composition || {};
    return 'COMPOSITE | ' + (formatMultiAlphaModuleList(multiAlpha.modules) || '-')
      + ' | ' + String(composition.compose_mode || MULTI_ALPHA_COMPOSE_MODE)
      + ' | ' + String(composition.same_symbol_policy || MULTI_ALPHA_SAME_SYMBOL_POLICY)
      + ' | ' + String(composition.holding_ownership || MULTI_ALPHA_HOLDING_OWNERSHIP)
      + ' | ' + formatMultiAlphaRegimeSummary(composition.regime_matrix || {});
  }
  const strategy = cfg?.strategy || {};
  const params = strategy.params || {};
  const strategyName = String(strategy.name || '').toUpperCase();
  const maxPositions = art?.run_meta?.counters?.max_positions ?? cfg?.position_risk?.max_positions ?? '-';
  const br = cfg?.benchmark_regime || {};
  const brTag = br.enabled ? ' | BR=' + (br.fast_period ?? 20) + '/' + (br.slow_period ?? 120) : '';
  if (strategyName === 'BREAKOUT_TREND') {
    return 'BREAKOUT_TREND | BreakoutWindow=' + (params.breakout_window ?? 55) + ' | ATRStop=' + (params.atr_stop_k ?? '-') + ' | ATRTrail=' + (params.atr_trail_k ?? '-') + ' | regime_ma=' + (params.regime_ma ?? '-') + brTag + ' | MaxPositions=' + maxPositions;
  }
  if (strategyName === 'SMA_CROSS' || strategyName === 'EMA_CROSS') {
    return strategyName + ' | Fast=' + (strategy.fast ?? '-') + ' | Slow=' + (strategy.slow ?? '-') + brTag + ' | MaxPositions=' + maxPositions;
  }
  return (strategyName || 'STRATEGY') + ' | MaxPositions=' + maxPositions;
}

function runtimeStrategyOverview(cfg, art) {
  const multiAlpha = resolveMultiAlphaSummaryPayload(cfg);
  if (multiAlpha) {
    const composition = multiAlpha.composition || {};
    return {
      name: 'COMPOSITE',
      core: formatMultiAlphaModuleList(multiAlpha.modules) || '-',
      portfolioMode: multiAlpha.portfolioMode || MULTI_ALPHA_PORTFOLIO_MODE,
      extra: String(composition.compose_mode || MULTI_ALPHA_COMPOSE_MODE)
        + ' | ' + String(composition.same_symbol_policy || MULTI_ALPHA_SAME_SYMBOL_POLICY)
        + ' | ' + String(composition.holding_ownership || MULTI_ALPHA_HOLDING_OWNERSHIP)
        + ' | ' + formatMultiAlphaRegimeSummary(composition.regime_matrix || {}),
    };
  }
  const strategy = cfg?.strategy || {};
  const params = strategy.params || {};
  const strategyName = String(strategy.name || '').toUpperCase();
  const maxPositions = art?.run_meta?.counters?.max_positions ?? cfg?.position_risk?.max_positions ?? '-';
  const portfolioMode = cfg?.position_risk?.portfolio_mode || cfg?.risk_budget?.portfolio_mode || 'equal_10';
  const br = cfg?.benchmark_regime || {};
  const brText = br.enabled ? 'BR ' + (br.fast_period ?? 20) + '/' + (br.slow_period ?? 120) + '/' + (br.slope_window ?? 5) : 'BR Off';
  if (strategyName === 'BREAKOUT_TREND') {
    return {
      name: 'BREAKOUT_TREND',
      core: 'BreakoutWindow=' + (params.breakout_window ?? 55) + ' | ATR ' + (params.atr_stop_k ?? '-') + ' / ' + (params.atr_trail_k ?? '-'),
      portfolioMode,
      extra: 'regime_ma=' + (params.regime_ma ?? '-') + ' | ' + brText + ' | MaxPositions=' + maxPositions,
    };
  }
  if (strategyName === 'SMA_CROSS' || strategyName === 'EMA_CROSS') {
    return {
      name: strategyName,
      core: 'Fast=' + (strategy.fast ?? '-') + ' | Slow=' + (strategy.slow ?? '-'),
      portfolioMode,
      extra: brText + ' | MaxPositions=' + maxPositions,
    };
  }
  const sg = cfg?.signal_generation || {};
  const trend = sg.trend || sg.sma || sg.ema || {};
  const stratName = String(sg.strategy || cfg.strategy_pack || 'SMA_CROSS').toUpperCase();
  if (sg.regime_detection?.enabled) {
    const mr = sg.mr || {};
    return {
      name: 'REGIME',
      core: 'Trend=' + String(trend.strategy || 'SMA').toUpperCase() + ' ' + (trend.fast_ma ?? 20) + '/' + (trend.slow_ma ?? 60),
      portfolioMode: cfg?.position_risk?.portfolio_mode ?? 'equal_10',
      extra: 'MR RSI(' + (mr.rsi_period ?? 6) + ') ' + (mr.rsi_buy_threshold ?? 20) + '/' + (mr.rsi_sell_threshold ?? 80) + ' | regime_ma=' + (sg.regime_detection?.regime_ma ?? 60),
    };
  }
  const breakout = sg.breakout || {};
  return {
    name: stratName || 'STRATEGY',
    core: stratName === 'BREAKOUT_TREND'
      ? 'BreakoutWindow=' + (breakout.breakout_window ?? 55) + ' | confirm=' + (breakout.entry_confirm_mode ?? 'none')
      : 'Fast=' + (trend.fast_ma ?? '-') + ' | Slow=' + (trend.slow_ma ?? '-'),
    portfolioMode: cfg?.position_risk?.portfolio_mode ?? 'equal_10',
    extra: 'MaxPositions=' + (cfg?.position_risk?.max_positions ?? '-') + ' | portfolio=' + (cfg?.position_risk?.portfolio_mode ?? 'equal_10'),
  };
}

function renderSummaryBar() {
  const row = state.active_result || {};
  const art = state.active_artifacts || {};
  const cfg = resolveSummaryConfig();
  const p = art.perf || {};
  const u = cfg?.universe || {};
  const rm = art.run_meta || {};
  const rmData = rm.data || {};
  const rmUni = rm.universe || {};
  const universeMode = rmData.universe_mode || rmUni.universe_mode || cfg?.universe_mode || '-';
  const start = rmData.start || u.start || '-';
  const end = rmData.end || u.end || '-';
  const benchmark = rmData.benchmark || u.benchmark || '-';
  const rawCount = rmUni.raw_count;
  const tradableCount = rmUni.tradable_symbols ?? rmUni.after_filters_symbols;
  const symbolsText = Number.isFinite(Number(rawCount))
    ? (Number.isFinite(Number(tradableCount)) ? `${fmtInt(rawCount)} -> ${fmtInt(tradableCount)}` : fmtInt(rawCount))
    : (Array.isArray(u.symbols) ? fmtInt(u.symbols.length) : '-');
  const strategyInfo = runtimeStrategyOverview(cfg, art);
  const inputSource = rm?.candidate?.candidate_name
    || rm?.report_consistency?.config_source
    || state.loaded_source_meta?.display_name
    || state.loaded_source_sync_mode
    || 'Current Draft';

  setTextById('wbOverviewExpId', row.exp_id || '-');
  setTextById('wbOverviewStatus', row.exp_id ? (row.status || '-') : 'Not loaded');
  setTextById('wbOverviewConfigSource', String(inputSource || '-'));
  setTextById('wbSummaryUniverse', `${start} ~ ${end}`);
  setTextById('wbOverviewBenchmark', benchmark);
  setTextById('wbOverviewUniverseMode', universeMode);
  setTextById('wbOverviewUniverseCount', symbolsText);
  setTextById('wbOverviewStrategyName', strategyInfo.name);
  setTextById('wbOverviewStrategyCore', strategyInfo.core);
  setTextById('wbOverviewPortfolioMode', strategyInfo.portfolioMode);
  setTextById('wbSummaryStrategy', strategyInfo.extra);
}

function selectedRegimeEngineValue() {
  return String(byId('wbRegimeEngine')?.value || 'ma200_legacy').trim().toLowerCase() || 'ma200_legacy';
}

function updateRegimeEngineUi(engine = null) {
  const normalized = String(engine || selectedRegimeEngineValue()).trim().toLowerCase() || 'ma200_legacy';
  const formal = normalized === 'market_regime_framework';
  const weekly = normalized === 'weekly_five_state';
  const selector = byId('wbRegimeEngine');
  if (selector) selector.value = normalized;
  const formalPanel = byId('wbRegimeFrameworkPanel');
  if (formalPanel) formalPanel.hidden = !formal;
  const weeklyPanel = byId('wbWeeklyFiveStatePanel');
  if (weeklyPanel) weeklyPanel.hidden = !weekly;
  const legacyPanel = byId('wbRegimeLegacyPanel');
  if (legacyPanel) legacyPanel.hidden = formal || weekly;
}

function regimeRequiredBlocksFromUi() {
  return [
    byId('wbRegimeRequiredTrend')?.checked ? 'trend_block' : null,
    byId('wbRegimeRequiredRisk')?.checked ? 'risk_block' : null,
    byId('wbRegimeRequiredBreadth')?.checked ? 'breadth_block' : null,
    byId('wbRegimeRequiredParticipation')?.checked ? 'participation_block' : null,
  ].filter(Boolean);
}

function applyConfigToUI(cfg) {
  const _set = (id, val) => { const el = byId(id); if (el && val != null) el.value = val; };
  const _chk = (id, val) => { const el = byId(id); if (el) el.checked = !!val; };

  const u = cfg?.universe || {};
  const f = u.filters || {};
  _set('wbStartDate', u.start);
  _set('wbEndDate', u.end);
  _set('wbBenchmark', u.benchmark);
  const loadedMode = cfg?.universe_mode || byId('wbUniverseMode')?.value || 'ALL_A';
  _set('wbUniverseMode', loadedMode);
  document.querySelectorAll('#wbUniverseModeGroup button').forEach((b) => {
    b.classList.toggle('active', b.getAttribute('data-val') === loadedMode);
  });
  const membershipUiValue = membershipUiValueFromConfig(u.membership_mode, loadedMode);
  syncMembershipModeButtons(membershipUiValue);
  updateMembershipModeVisibility(loadedMode);
  _set('wbSymbols', Array.isArray(u.symbols) ? u.symbols.join(',') : undefined);
  _set('wbUniverseLimit', u.limit);
  _chk('wbExcludeSt', f.exclude_st);
  _chk('wbExcludeSuspended', f.exclude_suspended);
  _chk('wbExcludeStarMarket', f.exclude_star_market);
  _set('wbMinListDays', f.min_list_days);
  _set('wbMinTurnover', f.min_avg_turnover_20d);
  _set('wbPriceMin', f.price_min ?? cfg?.universe_filter?.min_price);
  _set('wbPriceMax', f.price_max);
  _set('wbLimitRule', f.limit_rule);

  const loadedAdj = u.price_adj || 'hfq';
  _set('wbPriceAdj', loadedAdj);
  document.querySelectorAll('#wbAdjGroup button').forEach((b) => {
    b.classList.toggle('active', b.getAttribute('data-val') === loadedAdj);
  });

  const sgCfg = cfg?.signal_generation || {};
  const hasMultiAlphaModules = Array.isArray(sgCfg.modules) && sgCfg.modules.length > 0;
  const hasMultiAlphaIntent = hasPhase1MultiAlphaIntent(cfg);
  const rawStrategyName = String(hasMultiAlphaModules ? 'COMPOSITE' : (sgCfg.strategy || cfg?.strategy_pack || 'SMA_CROSS')).toUpperCase();
  const unsupportedAdaptiveRegime = rawStrategyName === 'ADAPTIVE_REGIME';
  const strategyName = unsupportedAdaptiveRegime ? 'REGIME_ROUTER' : rawStrategyName;
  _set('wbStrategyPack', strategyName);

  const rd = sgCfg.regime_detection || {};
  const regimeOn = strategyName === 'REGIME_ROUTER';
  _chk('wbRegimeEnabled', regimeOn);
  _set('wbRegimeMa', rd.regime_ma ?? 60);
  const regimeParams = byId('wbRegimeParams'); if (regimeParams) regimeParams.style.display = regimeOn ? '' : 'none';
  const rfBlock = byId('wbRegimeFilterBlock'); if (rfBlock) rfBlock.style.display = regimeOn ? '' : 'none';
  const rfCfg = rd.regime_filter || {};
  const rfOn = !!rfCfg.enabled;
  _chk('wbRegimeFilterEnabled', rfOn);
  _set('wbRfThreshold', rfCfg.regime_threshold ?? 0.3);
  _set('wbRfAlpha', rfCfg.alpha_m ?? 2.0);
  const rfParams = byId('wbRegimeFilterParams'); if (rfParams) rfParams.style.display = rfOn ? '' : 'none';

  const regimeEngineCfg = cfg?.regime_engine || {};
  const regimeTrend = regimeEngineCfg.trend_block || {};
  const regimeRisk = regimeEngineCfg.risk_block || {};
  const regimeBreadth = regimeEngineCfg.breadth_block || {};
  const regimeParticipation = regimeEngineCfg.participation_block || {};
  const regimePersistence = regimeEngineCfg.persistence || {};
  const regimeFallback = regimeEngineCfg.fallback || {};
  const regimeWeeklyFiveState = regimeEngineCfg.weekly_five_state || {};
  const regimeEngine = String(regimeEngineCfg.engine || 'ma200_legacy').trim().toLowerCase() || 'ma200_legacy';
  _set('wbRegimeEngine', regimeEngine);
  _set('wbFormalRegimeBenchmark', regimeEngineCfg.benchmark ?? (u.benchmark || '000001.SH'));
  _set('wbWeeklyTurnWeakBudget', regimeWeeklyFiveState.turn_weak_budget ?? 0.15);
  _chk('wbRegimeTrendEnabled', regimeTrend.enabled ?? true);
  _set('wbRegimeLongMaWindow', regimeTrend.long_ma_window ?? 200);
  _set('wbRegimeSlopeWindow', regimeTrend.slope_window ?? 20);
  _set('wbRegimeBreakoutLookback', regimeTrend.breakout_lookback ?? 20);
  _chk('wbRegimeRiskEnabled', regimeRisk.enabled ?? true);
  _set('wbRegimeRealizedVolWindow', regimeRisk.realized_vol_window ?? 20);
  _set('wbRegimeAtrWindow', regimeRisk.atr_window ?? 14);
  _set('wbRegimeDrawdownWindow', regimeRisk.drawdown_window ?? 60);
  _chk('wbRegimeBreadthEnabledFormal', regimeBreadth.enabled ?? true);
  _set('wbRegimeBreadthUniverse', regimeBreadth.universe ?? 'benchmark_constituents');
  _set('wbRegimeAboveMaShort', regimeBreadth.above_ma_short_window ?? 50);
  _set('wbRegimeAboveMaLong', regimeBreadth.above_ma_long_window ?? 200);
  _set('wbRegimeNewHighLowWindow', regimeBreadth.new_high_low_window ?? 20);
  _chk('wbRegimeParticipationEnabled', regimeParticipation.enabled ?? true);
  _set('wbRegimeTurnoverWindow', regimeParticipation.turnover_window ?? 20);
  _set('wbRegimeAmountWindow', regimeParticipation.amount_window ?? 20);
  _chk('wbRegimeUseTurnoverRate', regimeParticipation.use_turnover_rate ?? true);
  _set('wbRegimeEntryConfirmBars', regimePersistence.entry_confirm_bars ?? 3);
  _set('wbRegimeExitConfirmBars', regimePersistence.exit_confirm_bars ?? 2);
  _set('wbRegimeMinStateDuration', regimePersistence.min_state_duration ?? 5);
  _set('wbRegimeConfidenceFloor', regimePersistence.confidence_floor ?? 0.55);
  _set('wbRegimeTransitionCooldown', regimePersistence.transition_cooldown ?? 3);
  _set('wbRegimeFallbackMode', regimeFallback.on_feature_unavailable ?? 'ma200_legacy');
  _chk('wbRegimeEmitFeatureAvailability', regimeFallback.emit_feature_availability ?? (regimeEngine === 'market_regime_framework'));
  const requiredBlocks = Array.isArray(regimeFallback.required_blocks) ? regimeFallback.required_blocks : [];
  _chk('wbRegimeRequiredTrend', requiredBlocks.includes('trend_block') || (!requiredBlocks.length && regimeEngine === 'market_regime_framework'));
  _chk('wbRegimeRequiredRisk', requiredBlocks.includes('risk_block') || (!requiredBlocks.length && regimeEngine === 'market_regime_framework'));
  _chk('wbRegimeRequiredBreadth', requiredBlocks.includes('breadth_block'));
  _chk('wbRegimeRequiredParticipation', requiredBlocks.includes('participation_block'));
  updateRegimeEngineUi(regimeEngine);

  const trend = sgCfg.trend || {};
  const breakoutModule = hasMultiAlphaModules
    ? (sgCfg.modules.find((module) => normalizeMultiAlphaName(module?.name) === 'breakout_55') || {})
    : null;
  const breakoutParams = breakoutModule?.params || {};
  const trendName = hasMultiAlphaModules ? 'BREAKOUT_TREND' : (trend.strategy || strategyName || 'EMA_CROSS');
  _set('wbTrendStrategy', trendName);
  _set('wbFastMa', trend.fast_ma ?? sgCfg.sma?.fast_ma ?? 20);
  _set('wbSlowMa', trend.slow_ma ?? sgCfg.sma?.slow_ma ?? 60);
  _set('wbEntryBuffer', trend.entry_buffer_pct ?? sgCfg.sma?.entry_buffer_pct ?? 1);
  const breakout = hasMultiAlphaModules ? breakoutParams : (sgCfg.breakout || {});
  _set('wbBreakoutWindow', breakout.breakout_window ?? 55);
  _chk('wbDualBreakout', breakout.enable_dual_breakout);
  _set('wbBreakoutWindowShort', breakout.breakout_window_short ?? 20);
  _set('wbBreakoutWindowLong', breakout.breakout_window_long ?? 55);
  _set('wbBreakoutBuffer', breakout.breakout_entry_buffer_pct ?? 0);
  _set('wbEntryConfirmMode', breakout.entry_confirm_mode ?? 'none');
  _set('wbEntryDelayMode', breakout.entry_delay_mode ?? 'none');
  _set('wbMomentumTopPct', sgCfg.ranking?.momentum_top_pct ?? 0);
  const scoreSourceModeEl = byId('wbScoreSourceMode');
  if (scoreSourceModeEl) {
    cleanupUnsupportedOptionsCompat(scoreSourceModeEl);
    const scoreSourceMode = sgCfg.ranking?.score_source_mode;
    if (scoreSourceMode && !Array.from(scoreSourceModeEl.options).some((option) => option.value === scoreSourceMode)) {
      const option = document.createElement('option');
      option.value = scoreSourceMode;
      option.textContent = 'UNSUPPORTED: ' + scoreSourceMode;
      option.dataset.unsupported = '1';
      scoreSourceModeEl.appendChild(option);
    }
    scoreSourceModeEl.value = scoreSourceMode || '';
  }
  const residualWindowEl = byId('wbResidualWindow');
  if (residualWindowEl) residualWindowEl.value = sgCfg.ranking?.residual_window != null ? String(sgCfg.ranking.residual_window) : '';

  const mrModule = hasMultiAlphaModules
    ? (sgCfg.modules.find((module) => normalizeMultiAlphaName(module?.name) === 'rsi_reversal') || {})
    : null;
  const mr = hasMultiAlphaModules ? (mrModule?.params || {}) : (sgCfg.mr || {});
  _set('wbMrStrategy', mr.strategy || 'RSI_REVERSAL');
  _set('wbMrRsiPeriod', mr.rsi_period ?? 6);
  _set('wbMrRsiBuy', mr.rsi_buy_threshold ?? 20);
  _set('wbMrRsiSell', mr.rsi_sell_threshold ?? 80);
  _set('wbMrMaxHold', mr.mr_max_hold_days ?? mr.max_hold_days ?? 5);
  const mrStopRaw = mr.mr_stop_loss_pct ?? mr.stop_loss_pct;
  _set('wbMrStopLoss', mrStopRaw != null ? Number(mrStopRaw) * 100 : 3);

  const mrPanel = byId('wbMrPanel'); if (mrPanel) mrPanel.style.opacity = regimeOn || hasMultiAlphaIntent ? '1' : '0.45';

  const ef = sgCfg.entry_filter || {};
  _chk('wbEntryAboveSlowMa', ef.enable_entry_above_slow_ma);
  _chk('wbEntrySlowMaSlope', ef.enable_entry_slow_ma_slope);
  _set('wbEntrySlopeLookback', ef.entry_slope_lookback ?? 5);
  const slopeLb = byId('wbEntrySlopeLookback');
  if (slopeLb) slopeLb.disabled = !byId('wbEntrySlowMaSlope')?.checked;

  const ex = cfg?.exit_rules || {};
  _chk('wbExitReverse', ex.signal_reverse);
  _chk('wbExitAtr', ex.atr_stop?.enabled);
  _set('wbAtrK', ex.atr_stop?.k);
  _chk('wbExitTrail', ex.trailing?.enabled);
  _set('wbTrailK', ex.trailing?.k);
  const trailingActivateProfitEl = byId('wbTrailingActivateProfitPct');
  if (trailingActivateProfitEl) trailingActivateProfitEl.value = ex.trailing?.activate_profit_pct != null ? String(Number(ex.trailing.activate_profit_pct) * 100) : '';
  _chk('wbPreProfitBreakoutFailureEnabled', ex.trailing?.pre_profit_breakout_failure_enabled);
  const preProfitBarsEl = byId('wbPreProfitBreakoutFailureMaxBars');
  if (preProfitBarsEl) preProfitBarsEl.value = ex.trailing?.pre_profit_breakout_failure_max_bars != null ? String(ex.trailing.pre_profit_breakout_failure_max_bars) : '5';
  const preProfitAtrBufferEl = byId('wbPreProfitBreakoutFailureAtrBufferK');
  if (preProfitAtrBufferEl) preProfitAtrBufferEl.value = ex.trailing?.pre_profit_breakout_failure_atr_buffer_k != null ? String(ex.trailing.pre_profit_breakout_failure_atr_buffer_k) : '0.5';
  _chk('wbExitTime', ex.time_exit?.enabled);
  _set('wbExitDays', ex.time_exit?.n_days);
  const hc = ex.hold_constraint || {};
  _set('wbMinHoldDays', hc.min_hold_days ?? 0);
  _set('wbCooldownDays', hc.cooldown_days ?? 0);
  const tp = ex.take_profit || {};
  _chk('wbExitTakeProfit', tp.enabled);
  _set('wbTakeProfitMode', tp.mode);
  _set('wbTakeProfitPct', tp.pct != null ? Number(tp.pct) * 100 : undefined);
  _set('wbTakeProfitAtrK', tp.atr_k);
  const fs = ex.fixed_stop || {};
  _chk('wbExitFixedStop', fs.enabled);
  _set('wbFixedStopPct', fs.pct != null ? Number(fs.pct) * 100 : undefined);
  _chk('wbExitMa20', ex.ma20_exit?.enabled);
  _chk('wbExitLow10', ex.low10_exit?.enabled);

  const pr = cfg?.position_risk || {};
  _set('wbMaxPositions', pr.max_positions);
  _set('wbSingleCap', pr.single_stock_cap != null ? Number(pr.single_stock_cap) * 100 : undefined);
  _set('wbIndustryCap', pr.industry_cap != null ? Number(pr.industry_cap) * 100 : undefined);
  _set('wbLot', pr.lot);
  _set('wbCashPolicy', pr.cash_shortage_policy);
  if (hasMultiAlphaIntent) {
    _set('wbPortfolioMode', MULTI_ALPHA_PORTFOLIO_MODE);
  } else {
    setSelectValuePreserveUnsupportedCompat('wbPortfolioMode', pr.portfolio_mode ?? 'equal_10', 'equal_10');
  }

  const rb = pr.risk_budget || {};
  _chk('wbRiskBudget', rb.enabled);
  _set('wbBasePortfolioRisk', rb.base_portfolio_risk != null ? Number(rb.base_portfolio_risk) * 100 : undefined);
  _set('wbAtrStopK', rb.atr_stop_k);
  _set('wbMinActiveRatio', rb.min_active_ratio != null ? Number(rb.min_active_ratio) * 100 : undefined);
  _set('wbDdScale10', rb.dd_scale_10);
  _set('wbDdScale15', rb.dd_scale_15);
  _set('wbDdFixed20', rb.dd_fixed_20 != null ? Number(rb.dd_fixed_20) * 100 : undefined);
  _set('wbDdStopPct', rb.dd_stop_pct != null ? Number(rb.dd_stop_pct) * 100 : undefined);
  _set('wbDdStopCooldown', rb.dd_stop_cooldown_days);
  _set('wbDdStopProtect', rb.dd_stop_protect_days);

  const mf = pr.market_filter || {};
  _chk('wbMarketFilter', mf.enabled);
  _set('wbMfSlopeMaPeriod', mf.slope_ma_period);
  _set('wbMfSlopeWindow', mf.slope_window);
  _set('wbMfBullMult', mf.bull_multiplier);
  _set('wbMfLightMult', mf.light_multiplier);
  _set('wbMfEmaFast', mf.ema_light_fast);
  _set('wbMfEmaSlow', mf.ema_light_slow);

  const breadth = pr.breadth || {};
  _chk('wbBreadthEnabled', breadth.enabled);
  _set('wbBreadthMode', breadth.mode ?? 'dynamic_maxpos');
  _set('wbBreadthScoreType', breadth.score_type ?? 'B');
  _set('wbBreadthMappingMode', breadth.mapping_mode ?? 'smooth');
  _set('wbBreadthMinPositions', breadth.min_positions ?? 3);
  _set('wbBreadthMaxPositions', breadth.max_positions ?? 15);
  _set('wbBreadthStepHigh', breadth.step_high ?? 0.6);
  _set('wbBreadthStepMid', breadth.step_mid ?? 0.45);
  _set('wbBreadthSmoothLo', breadth.smooth_lo ?? 0.4);
  _set('wbBreadthSmoothRange', breadth.smooth_range ?? 0.2);
  _set('wbBreadthEmaFast', breadth.ema_fast ?? 8);
  _set('wbBreadthEmaSlow', breadth.ema_slow ?? 25);
  _set('wbBreadthGateThreshold', breadth.gate_threshold ?? 0.45);
  _set('wbBreadthGateWindow', breadth.gate_quantile_window ?? 252);
  _set('wbBreadthGatePct', breadth.gate_quantile_pct ?? 0.2);
  _set('wbBreadthGatePersist', breadth.gate_persist_days ?? 3);
  _set('wbBreadthScaleFloor', breadth.size_scale_floor ?? 0.3);

  const sizing = cfg?.sizing || {};
  _set('wbWeightMode', sizing.weight_mode ?? 'equal');
  _set('wbMinPositions', sizing.min_positions ?? 10);

  const br = cfg?.benchmark_regime || {};
  _chk('wbBenchmarkRegimeEnabled', br.enabled);
  _set('wbBenchmarkRegimeFast', br.fast_period ?? 20);
  _set('wbBenchmarkRegimeSlow', br.slow_period ?? 120);
  _set('wbBenchmarkRegimeSlope', br.slope_window ?? 5);

  const stockTrend = cfg?.stock_trend_filter || {};
  _chk('wbStockTrendEnabled', stockTrend.enabled);
  _set('wbStockTrendShortMa', stockTrend.short_ma ?? 20);
  _set('wbStockTrendLongMa', stockTrend.long_ma ?? 60);
  const sectorGate = cfg?.sector_gate || {};
  _chk('wbSectorGateEnabled', sectorGate.enabled);
  _set('wbSectorRankWindow', sectorGate.rank_window ?? 60);
  _set('wbSectorTopPct', sectorGate.top_pct ?? 0.3);

  const compositionEnabled = hasMultiAlphaIntent ? !!(cfg?.signal_composition?.enabled ?? true) : false;
  _chk('wbEnableComposition', compositionEnabled);
  if (hasMultiAlphaIntent) {
    _set('wbComposeMode', MULTI_ALPHA_COMPOSE_MODE);
    _set('wbSameSymbolPolicy', MULTI_ALPHA_SAME_SYMBOL_POLICY);
    _set('wbHoldingOwnership', MULTI_ALPHA_HOLDING_OWNERSHIP);
  } else {
    setSelectValuePreserveUnsupportedCompat('wbComposeMode', cfg?.signal_composition?.compose_mode ?? MULTI_ALPHA_COMPOSE_MODE, MULTI_ALPHA_COMPOSE_MODE);
    setSelectValuePreserveUnsupportedCompat('wbSameSymbolPolicy', cfg?.signal_composition?.same_symbol_policy ?? MULTI_ALPHA_SAME_SYMBOL_POLICY, MULTI_ALPHA_SAME_SYMBOL_POLICY);
    setSelectValuePreserveUnsupportedCompat('wbHoldingOwnership', cfg?.signal_composition?.holding_ownership ?? MULTI_ALPHA_HOLDING_OWNERSHIP, MULTI_ALPHA_HOLDING_OWNERSHIP);
  }

  const composeRows = hasMultiAlphaIntent ? ensurePhase1ComposeRows(mergeComposeRowsFromConfig(cfg)) : defaultComposeRows();
  hydrateComposeRows(composeRows, { useDefault: !hasMultiAlphaIntent });
  const regimeMatrix = hasMultiAlphaIntent
    ? normalizePhase1MultiAlphaRegimeMatrix(cfg?.signal_composition?.regime_matrix, composeRows)
    : defaultRegimeMatrix();
  hydrateRegimeMatrix(regimeMatrix, composeRows, { useDefault: !hasMultiAlphaIntent });

  const ep = cfg?.exit_priority;
  if (Array.isArray(ep) && ep.length) {
    const list = byId('wbExitPriorityList');
    if (list) {
      list.innerHTML = ep.map((name, i) =>
        '<li><span class="wb-priority-rank">' + (i + 1) + '</span> ' + esc(name) + '</li>'
      ).join('');
    }
  }

  buildConfigDraft();
  syncExitLinkage();
  updateAtrNote();
  return { unsupportedStrategy: unsupportedAdaptiveRegime ? rawStrategyName : null };
}


function switchInspectorTab(tab) {
  if (tab === 'perf' || tab === 'runner') return switchDockTab('buy_funnel');
  if (tab === 'explain') return switchDockTab('buy_funnel');
  if (tab === 'exec' || tab === 'execution') return switchDockTab('execution');
  if (tab === 'sell' || tab === 'sell_funnel') return switchDockTab('buy_funnel');
  if (tab === 'logs') return switchDockTab('logs');
}


/* Risk & Exit enhancement functions */

function syncExitLinkage() {
  const trailCb = byId('wbExitTrail');
  const trailInput = byId('wbTrailK');
  const trailingActivateProfitInput = byId('wbTrailingActivateProfitPct');
  const preProfitBreakoutFailureCb = byId('wbPreProfitBreakoutFailureEnabled');
  const preProfitBreakoutFailureMaxBars = byId('wbPreProfitBreakoutFailureMaxBars');
  const preProfitBreakoutFailureAtrBuffer = byId('wbPreProfitBreakoutFailureAtrBufferK');
  const timeCb = byId('wbExitTime');
  const timeInput = byId('wbExitDays');
  if (trailCb && trailInput) trailInput.disabled = !trailCb.checked;
  if (trailCb && trailingActivateProfitInput) trailingActivateProfitInput.disabled = !trailCb.checked;
  if (trailCb && preProfitBreakoutFailureCb) preProfitBreakoutFailureCb.disabled = !trailCb.checked;
  const preProfitEditable = !!trailCb?.checked && !!preProfitBreakoutFailureCb?.checked;
  if (preProfitBreakoutFailureMaxBars) preProfitBreakoutFailureMaxBars.disabled = !preProfitEditable;
  if (preProfitBreakoutFailureAtrBuffer) preProfitBreakoutFailureAtrBuffer.disabled = !preProfitEditable;
  if (timeCb && timeInput) timeInput.disabled = !timeCb.checked;
}

function updateAtrNote() {
  const el = byId('wbAtrNote');
  if (!el) return;
  const priceAdj = byId('wbPriceAdj');
  const matchPrice = byId('wbMatchPrice');
  const adjLabel = priceAdj ? (priceAdj.options[priceAdj.selectedIndex]?.text || priceAdj.value) : 'Forward Adjusted';
  const matchLabel = matchPrice ? (matchPrice.options[matchPrice.selectedIndex]?.text || matchPrice.value) : 'Next Open';
  el.textContent = `ATR Window: 14D | Price Adj: ${adjLabel} | Match Price: ${matchLabel}`;
}

function populateExitStats(counters) {
  const container = byId('wbExitStats');
  if (!container) return;
  const keys = ['reversal_exit_count', 'atr_stop_exit_count', 'atr_trail_exit_count', 'atr_trail_update_count', 'time_exit_count', 'take_profit_exit_count', 'fixed_stop_loss_exit_count', 'dd_stop_block_count'];
  keys.forEach((k) => {
    const el = container.querySelector(`[data-key="${k}"]`);
    if (el) {
      const v = counters[k];
      el.textContent = v != null && Number.isFinite(Number(v)) ? num(v, 0) : '-';
    }
  });
}

function populateConstraintStats(counters, config) {
  const container = byId('wbConstraintStats');
  if (!container) return;
  const maxPos = Number(config?.position_risk?.max_positions || byId('wbMaxPositions')?.value || 10);
  const avgPos = Number(counters.avg_positions ?? 0);
  const slotsLeft = counters.slots_left != null ? Number(counters.slots_left) : (maxPos - avgPos);
  const vals = {
    avg_positions: avgPos,
    slots_left: slotsLeft,
    cap_hit_single: counters.cap_hit_single ?? 0,
    cap_hit_industry: counters.cap_hit_industry ?? 0,
    cash_skip_count: counters.cash_skip_count ?? 0,
    lot_skip_count: counters.lot_skip_count ?? 0,
  };
  Object.entries(vals).forEach(([k, v]) => {
    const el = container.querySelector(`[data-key="${k}"]`);
    if (el) el.textContent = Number.isFinite(Number(v)) ? num(v, k === 'avg_positions' || k === 'slots_left' ? 1 : 0) : '-';
  });
}

function populateMarketStateStats(counters) {
  const container = byId('wbMarketStateStats');
  if (!container) return;
  const hasMf = Number(counters.market_state_bull_days ?? 0) + Number(counters.market_state_bear_days ?? 0) > 0;
  container.style.display = hasMf ? '' : 'none';
  if (!hasMf) return;
  const keys = ['market_state_bull_days', 'market_state_bear_days', 'market_state_trans_down_days', 'market_state_trans_up_days', 'trade_mode_main_days', 'trade_mode_light_days', 'trade_mode_notrade_days'];
  keys.forEach((k) => {
    const el = container.querySelector(`[data-key="${k}"]`);
    if (el) {
      const v = counters[k];
      el.textContent = v != null && Number.isFinite(Number(v)) ? num(v, 0) : '-';
    }
  });
}

