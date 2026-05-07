(function initMultiAlphaUi(globalScope) {
const MULTI_ALPHA_MODULE_DESCRIPTORS = (Array.isArray(COMPOSE_MODULES) ? COMPOSE_MODULES : [])
  .map((module) => ({
    name: String((module && module.name) || '').trim().toLowerCase(),
    label: String((module && (module.label || module.name)) || '').trim(),
    alpha_id: String((module && (module.alpha_id || module.name)) || '').trim().toLowerCase(),
    family: String((module && module.family) || '').trim(),
    role: String((module && module.role) || '').trim(),
    weight: Number(module && module.weight != null ? module.weight : 0),
    priority: Number(module && module.priority != null ? module.priority : 0),
  }))
  .filter((module) => module.name);
const MULTI_ALPHA_MODULE_MAP = new Map(MULTI_ALPHA_MODULE_DESCRIPTORS.map((module) => [module.name, module]));

function normalizeMultiAlphaName(value) {
  return String(value || '').trim().toLowerCase();
}

function normalizeMultiAlphaOption(value, fallback = '') {
  const text = String(value || '').trim();
  return text || fallback;
}

function coercePhase1MultiAlphaOption(value, supportedValue) {
  const normalized = normalizeMultiAlphaOption(value, supportedValue).toUpperCase();
  return normalized === String(supportedValue || '').toUpperCase() ? supportedValue : supportedValue;
}

function supportedMultiAlphaDescriptor(name) {
  return MULTI_ALPHA_MODULE_MAP.get(normalizeMultiAlphaName(name)) || null;
}

function defaultRegimeMatrix() {
  return {
    TREND_UP: ['breakout_55'],
    RANGE: ['breakout_55', 'rsi_reversal'],
    WEAK_DOWN: ['rsi_reversal'],
  };
}

function defaultComposeRows() {
  const rows = MULTI_ALPHA_MODULE_DESCRIPTORS.map((module) => ({
    name: module.name,
    label: module.label,
    enabled: true,
    role: module.role,
    weight: module.weight,
    priority: module.priority,
    alpha_id: module.alpha_id,
    family: module.family,
    params: {},
    supported: true,
  }));
  state.multi_alpha_module_state = Object.fromEntries(rows.map((row) => [row.name, {
    alpha_id: row.alpha_id,
    family: row.family,
    params: cloneJson(row.params) || {},
  }]));
  return rows;
}

function composeRowNames(rows) {
  return (Array.isArray(rows) ? rows : [])
    .map((row) => normalizeMultiAlphaName(row && row.name))
    .filter(Boolean);
}

function normalizePhase1MultiAlphaRegimeMatrix(matrix, rows = []) {
  const normalizedRows = Array.isArray(rows) ? rows : [];
  const declaredNames = composeRowNames(normalizedRows);
  const declaredSet = new Set(declaredNames);
  const fallback = defaultRegimeMatrix();
  const resolved = matrix && typeof matrix === 'object' ? matrix : {};
  const next = {};
  MULTI_ALPHA_REGIMES.forEach((regime) => {
    const rawValues = Array.isArray(resolved[regime]) ? resolved[regime] : [];
    const values = rawValues
      .map((value) => normalizeMultiAlphaName(value))
      .filter((name, idx, arr) => name && declaredSet.has(name) && arr.indexOf(name) === idx);
    if (values.length) {
      next[regime] = values;
      return;
    }
    const fallbackValues = (fallback[regime] || [])
      .map((value) => normalizeMultiAlphaName(value))
      .filter((name, idx, arr) => name && declaredSet.has(name) && arr.indexOf(name) === idx);
    next[regime] = fallbackValues;
  });
  return next;
}

function hasPhase1MultiAlphaIntent(cfg) {
  const draft = cfg && typeof cfg === 'object' ? cfg : {};
  const signalGeneration = draft.signal_generation && typeof draft.signal_generation === 'object'
    ? draft.signal_generation
    : {};
  const signalComposition = draft.signal_composition && typeof draft.signal_composition === 'object'
    ? draft.signal_composition
    : {};
  const strategyName = String(
    draft.strategy_pack
      || signalGeneration.strategy
      || (draft.strategy && draft.strategy.name)
      || ''
  ).trim().toUpperCase();
  const signalModules = Array.isArray(signalGeneration.modules) ? signalGeneration.modules : [];
  if (signalModules.length) return true;
  if (strategyName === 'COMPOSITE') return true;

  const compositionModules = Array.isArray(signalComposition.modules) ? signalComposition.modules : [];
  const hasSupportedCompositionModule = compositionModules.some((module) => !!supportedMultiAlphaDescriptor(module && module.name));
  const regimeMatrix = signalComposition.regime_matrix && typeof signalComposition.regime_matrix === 'object'
    ? signalComposition.regime_matrix
    : {};
  const hasSupportedRegimeModule = Object.values(regimeMatrix).some((values) =>
    Array.isArray(values) && values.some((value) => !!supportedMultiAlphaDescriptor(value))
  );
  const composeMode = normalizeMultiAlphaOption(signalComposition.compose_mode, '').toUpperCase();
  const sameSymbolPolicy = normalizeMultiAlphaOption(signalComposition.same_symbol_policy, '').toUpperCase();
  const holdingOwnership = normalizeMultiAlphaOption(signalComposition.holding_ownership, '').toUpperCase();
  const portfolioMode = String((draft.position_risk && draft.position_risk.portfolio_mode) || '').trim();

  return hasSupportedCompositionModule
    || hasSupportedRegimeModule
    || composeMode === MULTI_ALPHA_COMPOSE_MODE
    || sameSymbolPolicy === MULTI_ALPHA_SAME_SYMBOL_POLICY
    || holdingOwnership === MULTI_ALPHA_HOLDING_OWNERSHIP
    || portfolioMode === MULTI_ALPHA_PORTFOLIO_MODE;
}

function ensurePhase1ComposeRows(rows = []) {
  const current = Array.isArray(rows) ? rows.filter((row) => row && normalizeMultiAlphaName(row.name)) : [];
  if (current.length) return current;
  const fallbackRows = defaultComposeRows();
  hydrateComposeRows(fallbackRows, { useDefault: true });
  return fallbackRows;
}

function currentComposeRows() {
  const moduleState = state.multi_alpha_module_state && typeof state.multi_alpha_module_state === 'object'
    ? state.multi_alpha_module_state
    : {};
  return Array.from(document.querySelectorAll('#wbComposeRows tr[data-name]')).map((tr) => {
    const name = normalizeMultiAlphaName(tr.getAttribute('data-name'));
    const desc = supportedMultiAlphaDescriptor(name);
    const preserved = moduleState[name] || {};
    return {
      name,
      label: tr.getAttribute('data-label') || (desc && desc.label) || name,
      enabled: !!tr.querySelector('[data-k="enabled"]')?.checked,
      role: normalizeMultiAlphaOption(tr.querySelector('[data-k="role"]')?.value, (desc && desc.role) || 'trend'),
      weight: Number(tr.querySelector('[data-k="weight"]')?.value || ((desc && desc.weight) || 0)),
      priority: Number(tr.querySelector('[data-k="priority"]')?.value || ((desc && desc.priority) || 0)),
      alpha_id: normalizeMultiAlphaOption(preserved.alpha_id, (desc && desc.alpha_id) || name),
      family: normalizeMultiAlphaOption(preserved.family, (desc && desc.family) || ''),
      params: cloneJson(preserved.params) || {},
      supported: !!desc,
    };
  });
}

function bindDraftListeners(root) {
  if (!root || typeof root.querySelectorAll !== 'function') return;
  root.querySelectorAll('input,select,textarea').forEach((el) => {
    if (el.dataset.wbDraftBound === '1') return;
    el.dataset.wbDraftBound = '1';
    el.addEventListener('input', () => buildConfigDraft());
    el.addEventListener('change', () => buildConfigDraft());
  });
}

function cleanupUnsupportedOptions(selectEl) {
  if (!selectEl) return;
  Array.from(selectEl.querySelectorAll('option[data-unsupported="1"]')).forEach((option) => option.remove());
}

function setSelectValuePreserveUnsupported(id, value, fallback = '') {
  const selectEl = byId(id);
  if (!selectEl) return;
  cleanupUnsupportedOptions(selectEl);
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

function hasOwnConfigKey(obj, key) {
  return !!obj && Object.prototype.hasOwnProperty.call(obj, key);
}

function readOptionalInputValue(id) {
  const el = byId(id);
  if (!el) return null;
  const raw = String(el.value ?? '').trim();
  return raw ? raw : null;
}

function readOptionalNumberInput(id) {
  const raw = readOptionalInputValue(id);
  if (raw == null) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

function mergeComposeRowsFromConfig(cfg) {
  const signalModules = Array.isArray(cfg && cfg.signal_generation && cfg.signal_generation.modules)
    ? cfg.signal_generation.modules
    : [];
  const compositionModules = Array.isArray(cfg && cfg.signal_composition && cfg.signal_composition.modules)
    ? cfg.signal_composition.modules
    : [];
  const regimeMatrix = cfg && cfg.signal_composition && typeof cfg.signal_composition.regime_matrix === 'object'
    ? cfg.signal_composition.regime_matrix
    : {};
  const orderedNames = [];
  const addName = (value) => {
    const name = normalizeMultiAlphaName(value);
    if (!name || orderedNames.includes(name)) return;
    orderedNames.push(name);
  };
  MULTI_ALPHA_MODULE_DESCRIPTORS.forEach((module) => addName(module.name));
  signalModules.forEach((module) => addName(module && module.name));
  compositionModules.forEach((module) => addName(module && module.name));
  Object.values(regimeMatrix).forEach((values) => {
    if (!Array.isArray(values)) return;
    values.forEach((value) => addName(value));
  });
  const rows = orderedNames.map((name) => {
    const signalModule = signalModules.find((module) => normalizeMultiAlphaName(module && module.name) === name) || {};
    const compositionModule = compositionModules.find((module) => normalizeMultiAlphaName(module && module.name) === name) || {};
    const desc = supportedMultiAlphaDescriptor(name);
    return {
      name,
      label: (desc && desc.label) || name,
      enabled: signalModule.enabled != null ? signalModule.enabled : (compositionModule.enabled != null ? compositionModule.enabled : true),
      role: normalizeMultiAlphaOption(compositionModule.role, (desc && desc.role) || 'trend'),
      weight: Number(compositionModule.weight != null ? compositionModule.weight : ((desc && desc.weight) || 0)),
      priority: Number(compositionModule.priority != null ? compositionModule.priority : ((desc && desc.priority) || 0)),
      alpha_id: normalizeMultiAlphaOption(signalModule.alpha_id, (desc && desc.alpha_id) || name),
      family: normalizeMultiAlphaOption(signalModule.family, (desc && desc.family) || ''),
      params: cloneJson(signalModule.params) || {},
      supported: !!desc,
    };
  });
  state.multi_alpha_module_state = Object.fromEntries(rows.map((row) => [row.name, {
    alpha_id: row.alpha_id,
    family: row.family,
    params: cloneJson(row.params) || {},
  }]));
  return rows;
}

function buildKnownModuleParams(name, previousParams = {}) {
  const base = cloneJson(previousParams) || {};
  const normalized = normalizeMultiAlphaName(name);
  if (normalized === 'breakout_55') {
    return {
      ...base,
      breakout_window: Number(byId('wbBreakoutWindow')?.value || base.breakout_window || 55),
      enable_dual_breakout: !!byId('wbDualBreakout')?.checked,
      breakout_window_short: Number(byId('wbBreakoutWindowShort')?.value || base.breakout_window_short || 20),
      breakout_window_long: Number(byId('wbBreakoutWindowLong')?.value || base.breakout_window_long || 55),
      breakout_entry_buffer_pct: Number(byId('wbBreakoutBuffer')?.value || base.breakout_entry_buffer_pct || 0),
      entry_confirm_mode: normalizeMultiAlphaOption(byId('wbEntryConfirmMode')?.value, base.entry_confirm_mode || 'none'),
      entry_delay_mode: normalizeMultiAlphaOption(byId('wbEntryDelayMode')?.value, base.entry_delay_mode || 'none'),
    };
  }
  if (normalized === 'rsi_reversal') {
    return {
      ...base,
      rsi_period: Number(byId('wbMrRsiPeriod')?.value || base.rsi_period || 6),
      rsi_buy_threshold: Number(byId('wbMrRsiBuy')?.value || base.rsi_buy_threshold || 20),
      rsi_sell_threshold: Number(byId('wbMrRsiSell')?.value || base.rsi_sell_threshold || 80),
      mr_max_hold_days: Number(byId('wbMrMaxHold')?.value || base.mr_max_hold_days || base.max_hold_days || 5),
      mr_stop_loss_pct: Number(byId('wbMrStopLoss')?.value || 3) / 100,
    };
  }
  return base;
}

function buildRegimeMatrixFromUi(moduleNames = []) {
  const names = Array.isArray(moduleNames) && moduleNames.length ? moduleNames : composeRowNames(currentComposeRows());
  const matrix = {};
  MULTI_ALPHA_REGIMES.forEach((regime) => {
    matrix[regime] = names.filter((name) => !!document.querySelector('#wbRegimeMatrix input[data-regime="' + regime + '"][data-module="' + name + '"]')?.checked);
  });
  return matrix;
}

function validateMultiAlphaDraft(draft) {
  const errors = [];
  const signalModules = Array.isArray(draft && draft.signal_generation && draft.signal_generation.modules)
    ? draft.signal_generation.modules
    : [];
  const composition = draft && draft.signal_composition ? draft.signal_composition : {};
  const compositionModules = Array.isArray(composition.modules) ? composition.modules : [];
  const declaredNames = signalModules.map((module) => normalizeMultiAlphaName(module && module.name)).filter(Boolean);
  const duplicateNames = declaredNames.filter((name, idx) => declaredNames.indexOf(name) !== idx);
  if (!signalModules.length) errors.push('multi-alpha requires signal_generation.modules');
  if (duplicateNames.length) errors.push('duplicate multi-alpha modules: ' + Array.from(new Set(duplicateNames)).join(', '));
  declaredNames.forEach((name) => {
    if (!supportedMultiAlphaDescriptor(name)) errors.push('unsupported multi-alpha module: ' + name);
  });
  if (normalizeMultiAlphaOption(composition.compose_mode, MULTI_ALPHA_COMPOSE_MODE).toUpperCase() !== MULTI_ALPHA_COMPOSE_MODE) {
    errors.push('compose_mode must be ' + MULTI_ALPHA_COMPOSE_MODE);
  }
  if (normalizeMultiAlphaOption(composition.same_symbol_policy, MULTI_ALPHA_SAME_SYMBOL_POLICY).toUpperCase() !== MULTI_ALPHA_SAME_SYMBOL_POLICY) {
    errors.push('same_symbol_policy must be ' + MULTI_ALPHA_SAME_SYMBOL_POLICY);
  }
  if (normalizeMultiAlphaOption(composition.holding_ownership, MULTI_ALPHA_HOLDING_OWNERSHIP).toUpperCase() !== MULTI_ALPHA_HOLDING_OWNERSHIP) {
    errors.push('holding_ownership must be ' + MULTI_ALPHA_HOLDING_OWNERSHIP);
  }
  if (String((draft && draft.position_risk && draft.position_risk.portfolio_mode) || '').trim() !== MULTI_ALPHA_PORTFOLIO_MODE) {
    errors.push('portfolio_mode must be ' + MULTI_ALPHA_PORTFOLIO_MODE + ' when multi-alpha is enabled');
  }
  compositionModules.forEach((module) => {
    const name = normalizeMultiAlphaName(module && module.name);
    if (!name) errors.push('signal_composition.modules[*].name is required');
    else if (!declaredNames.includes(name)) errors.push('signal_composition.modules contains undeclared module: ' + name);
  });
  const regimeMatrix = composition && typeof composition.regime_matrix === 'object' ? composition.regime_matrix : {};
  MULTI_ALPHA_REGIMES.forEach((regime) => {
    const entries = Array.isArray(regimeMatrix[regime]) ? regimeMatrix[regime] : [];
    if (!entries.length) errors.push('regime_matrix.' + regime + ' must include at least one module');
    entries.forEach((name) => {
      const normalized = normalizeMultiAlphaName(name);
      if (!declaredNames.includes(normalized)) errors.push('regime_matrix.' + regime + ' references undeclared module: ' + normalized);
      if (normalized && !supportedMultiAlphaDescriptor(normalized)) errors.push('regime_matrix.' + regime + ' contains unsupported module: ' + normalized);
    });
  });
  const maxPos = Number(draft && draft.position_risk && draft.position_risk.max_positions);
  if (!(Number.isFinite(maxPos) && maxPos > 0)) errors.push('max_positions must be > 0');
  const singlePct = Number(draft && draft.position_risk && draft.position_risk.single_stock_cap) * 100;
  if (!(Number.isFinite(singlePct) && singlePct >= 0 && singlePct <= 100)) errors.push('single_stock_cap must be within 0-100');
  const industryPct = Number(draft && draft.position_risk && draft.position_risk.industry_cap) * 100;
  if (!(Number.isFinite(industryPct) && industryPct >= 0 && industryPct <= 100)) errors.push('industry_cap must be within 0-100');
  return errors;
}


  const api = {
    normalizeMultiAlphaName,
    normalizeMultiAlphaOption,
    coercePhase1MultiAlphaOption,
    supportedMultiAlphaDescriptor,
    defaultRegimeMatrix,
    defaultComposeRows,
    composeRowNames,
    normalizePhase1MultiAlphaRegimeMatrix,
    hasPhase1MultiAlphaIntent,
    ensurePhase1ComposeRows,
    currentComposeRows,
    bindDraftListeners,
    cleanupUnsupportedOptions,
    setSelectValuePreserveUnsupported,
    hasOwnConfigKey,
    readOptionalInputValue,
    readOptionalNumberInput,
    mergeComposeRowsFromConfig,
    buildKnownModuleParams,
    buildRegimeMatrixFromUi,
    validateMultiAlphaDraft,
  };

  globalScope.multiAlphaUi = Object.freeze(api);
})(window);
