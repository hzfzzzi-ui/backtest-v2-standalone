const fs = require('fs');
const path = require('path');
const vm = require('vm');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const BACKTEST_SCRIPT = path.join(PROJECT_ROOT, 'frontend', 'assets', 'js', 'backtest_v2.js');
const UI_CONTROLS_SCRIPT = path.join(PROJECT_ROOT, 'frontend', 'assets', 'js', 'ui-controls.js');
const ACCEPTANCE_REQUEST = path.join(PROJECT_ROOT, 'backend', 'scripts', 'ops', 'multi_alpha_phase1_acceptance.request.json');

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

class FakeClassList {
  constructor() {
    this.tokens = new Set();
  }

  add(...tokens) {
    tokens.forEach((token) => this.tokens.add(String(token)));
  }

  remove(...tokens) {
    tokens.forEach((token) => this.tokens.delete(String(token)));
  }

  toggle(token, force) {
    const normalized = String(token);
    if (force === true) {
      this.tokens.add(normalized);
      return true;
    }
    if (force === false) {
      this.tokens.delete(normalized);
      return false;
    }
    if (this.tokens.has(normalized)) {
      this.tokens.delete(normalized);
      return false;
    }
    this.tokens.add(normalized);
    return true;
  }

  contains(token) {
    return this.tokens.has(String(token));
  }
}

class FakeElement {
  constructor(id = '', tagName = 'div') {
    this.id = id;
    this.tagName = String(tagName || 'div').toUpperCase();
    this._value = '';
    Object.defineProperty(this, 'value', {
      get: () => this._value,
      set: (next) => {
        this._value = next == null ? '' : String(next);
      },
      enumerable: true,
      configurable: true,
    });
    this.value = '';
    this.checked = false;
    this.textContent = '';
    this.innerHTML = '';
    this.style = {};
    this.hidden = false;
    this.disabled = false;
    this.dataset = {};
    this.title = '';
    this.className = '';
    this.children = [];
    this.parentElement = null;
    this.options = [];
    this.selectedIndex = 0;
    this.attributes = {};
    this.classList = new FakeClassList();
    this._listeners = new Map();
  }

  addEventListener(type, handler) {
    const key = String(type || '');
    if (!this._listeners.has(key)) this._listeners.set(key, []);
    this._listeners.get(key).push(handler);
  }

  removeEventListener(type, handler) {
    const key = String(type || '');
    const handlers = this._listeners.get(key) || [];
    this._listeners.set(key, handlers.filter((item) => item !== handler));
  }

  dispatchEvent(event) {
    const key = String(event?.type || '');
    const handlers = this._listeners.get(key) || [];
    handlers.forEach((handler) => handler.call(this, event));
    return true;
  }

  appendChild(child) {
    if (!child) return child;
    child.parentElement = this;
    this.children.push(child);
    if (this.tagName === 'SELECT' && child.tagName === 'OPTION') {
      this.options.push(child);
    }
    return child;
  }

  remove() {
    if (!this.parentElement) return;
    const siblings = this.parentElement.children || [];
    this.parentElement.children = siblings.filter((item) => item !== this);
    if (this.parentElement.tagName === 'SELECT') {
      this.parentElement.options = this.parentElement.options.filter((item) => item !== this);
    }
    this.parentElement = null;
  }

  setAttribute(name, value) {
    this.attributes[String(name)] = String(value);
  }

  getAttribute(name) {
    return this.attributes[String(name)] ?? null;
  }

  querySelectorAll(selector) {
    if (selector === 'li') return this.children.filter((child) => child.tagName === 'LI');
    if (selector === 'option[data-unsupported="1"]') {
      return this.children.filter((child) => child.tagName === 'OPTION' && child.dataset.unsupported === '1');
    }
    return [];
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
}

function createDocument(elements) {
  return {
    body: new FakeElement('body', 'body'),
    getElementById(id) {
      return elements.get(String(id)) || null;
    },
    querySelectorAll() {
      return [];
    },
    querySelector() {
      return null;
    },
    createElement(tagName) {
      return new FakeElement('', tagName);
    },
    addEventListener() {},
    removeEventListener() {},
  };
}

function registerElement(elements, id, tagName = 'input', props = {}) {
  const element = new FakeElement(id, tagName);
  Object.assign(element, props || {});
  elements.set(String(id), element);
  return element;
}

function defaultElementMap(elements) {
  registerElement(elements, 'wbEnableSignal', 'input', { checked: true });
  registerElement(elements, 'wbEnableComposition', 'input', { checked: false });
  registerElement(elements, 'wbUniverseMode', 'select', { value: 'HS300_ZZ500' });
  registerElement(elements, 'wbStartDate', 'input', { value: '2024-01-01' });
  registerElement(elements, 'wbEndDate', 'input', { value: '2025-03-01' });
  registerElement(elements, 'wbBenchmark', 'input', { value: '000300.SH' });
  registerElement(elements, 'wbSymbols', 'textarea', { value: '' });
  registerElement(elements, 'wbUniverseLimit', 'input', { value: '0' });
  registerElement(elements, 'wbConstituentWrap', 'div', { hidden: false });
  registerElement(elements, 'wbConstituent', 'select', { value: 'dynamic' });
  registerElement(elements, 'wbPriceAdj', 'select', { value: 'hfq' });
  registerElement(elements, 'wbExcludeSt', 'input', { checked: true });
  registerElement(elements, 'wbExcludeSuspended', 'input', { checked: true });
  registerElement(elements, 'wbMinListDays', 'input', { value: '120' });
  registerElement(elements, 'wbMinTurnover', 'input', { value: '100000000' });
  registerElement(elements, 'wbPriceMin', 'input', { value: '5' });
  registerElement(elements, 'wbPriceMax', 'input', { value: '99999' });
  registerElement(elements, 'wbAtrRange', 'input', { value: '0,100' });
  registerElement(elements, 'wbLimitRule', 'select', { value: 'ignore' });
  registerElement(elements, 'wbBreakoutWindow', 'input', { value: '55' });
  registerElement(elements, 'wbDualBreakout', 'input', { checked: false });
  registerElement(elements, 'wbBreakoutWindowShort', 'input', { value: '20' });
  registerElement(elements, 'wbBreakoutWindowLong', 'input', { value: '55' });
  registerElement(elements, 'wbBreakoutBuffer', 'input', { value: '0' });
  registerElement(elements, 'wbEntryConfirmMode', 'select', { value: 'none' });
  registerElement(elements, 'wbEntryDelayMode', 'select', { value: 'none' });
  registerElement(elements, 'wbTrendStrategy', 'select', { value: 'BREAKOUT_TREND' });
  registerElement(elements, 'wbFastMa', 'input', { value: '20' });
  registerElement(elements, 'wbSlowMa', 'input', { value: '60' });
  registerElement(elements, 'wbEntryBuffer', 'input', { value: '1' });
  registerElement(elements, 'wbMomentumTopPct', 'input', { value: '0' });
  registerElement(elements, 'wbScoreSourceMode', 'select', { value: '' });
  registerElement(elements, 'wbResidualWindow', 'input', { value: '' });
  registerElement(elements, 'wbMrStrategy', 'select', { value: 'RSI_REVERSAL' });
  registerElement(elements, 'wbMrRsiPeriod', 'input', { value: '6' });
  registerElement(elements, 'wbMrRsiBuy', 'input', { value: '20' });
  registerElement(elements, 'wbMrRsiSell', 'input', { value: '80' });
  registerElement(elements, 'wbMrMaxHold', 'input', { value: '5' });
  registerElement(elements, 'wbMrStopLoss', 'input', { value: '3' });
  registerElement(elements, 'wbEntryAboveSlowMa', 'input', { checked: false });
  registerElement(elements, 'wbEntrySlowMaSlope', 'input', { checked: false });
  registerElement(elements, 'wbEntrySlopeLookback', 'input', { value: '5' });
  registerElement(elements, 'wbComposeMode', 'select', { value: 'REGIME_ROUTE' });
  registerElement(elements, 'wbSameSymbolPolicy', 'select', { value: 'PREFER_HIGHER_SCORE' });
  registerElement(elements, 'wbHoldingOwnership', 'select', { value: 'SOURCE_ONLY' });
  registerElement(elements, 'wbRegimeEnabled', 'input', { checked: true });
  registerElement(elements, 'wbRegimeMa', 'input', { value: '60' });
  registerElement(elements, 'wbRegimeFilterEnabled', 'input', { checked: false });
  registerElement(elements, 'wbRfThreshold', 'input', { value: '0.3' });
  registerElement(elements, 'wbRfAlpha', 'input', { value: '2.0' });
  registerElement(elements, 'wbBenchmarkRegimeEnabled', 'input', { checked: true });
  registerElement(elements, 'wbBenchmarkRegimeFast', 'input', { value: '20' });
  registerElement(elements, 'wbBenchmarkRegimeSlow', 'input', { value: '120' });
  registerElement(elements, 'wbBenchmarkRegimeSlope', 'input', { value: '5' });
  registerElement(elements, 'wbStockTrendEnabled', 'input', { checked: false });
  registerElement(elements, 'wbStockTrendShortMa', 'input', { value: '20' });
  registerElement(elements, 'wbStockTrendLongMa', 'input', { value: '60' });
  registerElement(elements, 'wbSectorGateEnabled', 'input', { checked: false });
  registerElement(elements, 'wbSectorRankWindow', 'input', { value: '60' });
  registerElement(elements, 'wbSectorTopPct', 'input', { value: '0.3' });
  registerElement(elements, 'wbEnableRisk', 'input', { checked: true });
  registerElement(elements, 'wbMaxPositions', 'input', { value: '10' });
  registerElement(elements, 'wbSingleCap', 'input', { value: '10' });
  registerElement(elements, 'wbIndustryCap', 'input', { value: '30' });
  registerElement(elements, 'wbLot', 'input', { value: '100' });
  registerElement(elements, 'wbCashPolicy', 'select', { value: 'skip' });
  registerElement(elements, 'wbPortfolioMode', 'select', { value: 'equal_10' });
  registerElement(elements, 'wbEnableExit', 'input', { checked: true });
  registerElement(elements, 'wbExitReverse', 'input', { checked: true });
  registerElement(elements, 'wbExitAtr', 'input', { checked: true });
  registerElement(elements, 'wbAtrK', 'input', { value: '1.2' });
  registerElement(elements, 'wbExitTrail', 'input', { checked: true });
  registerElement(elements, 'wbTrailK', 'input', { value: '3.0' });
  registerElement(elements, 'wbTrailingActivateProfitPct', 'input', { value: '' });
  registerElement(elements, 'wbPreProfitBreakoutFailureEnabled', 'input', { checked: false });
  registerElement(elements, 'wbPreProfitBreakoutFailureMaxBars', 'input', { value: '5' });
  registerElement(elements, 'wbPreProfitBreakoutFailureAtrBufferK', 'input', { value: '0.5' });
  registerElement(elements, 'wbExitTime', 'input', { checked: false });
  registerElement(elements, 'wbExitDays', 'input', { value: '20' });
  registerElement(elements, 'wbExitTakeProfit', 'input', { checked: false });
  registerElement(elements, 'wbTakeProfitMode', 'select', { value: 'pct' });
  registerElement(elements, 'wbTakeProfitPct', 'input', { value: '20' });
  registerElement(elements, 'wbTakeProfitAtrK', 'input', { value: '3.0' });
  registerElement(elements, 'wbExitFixedStop', 'input', { checked: false });
  registerElement(elements, 'wbFixedStopPct', 'input', { value: '5' });
  registerElement(elements, 'wbExitMa20', 'input', { checked: false });
  registerElement(elements, 'wbExitLow10', 'input', { checked: true });
  registerElement(elements, 'wbMinHoldDays', 'input', { value: '5' });
  registerElement(elements, 'wbCooldownDays', 'input', { value: '5' });
  registerElement(elements, 'wbRiskBudget', 'input', { checked: true });
  registerElement(elements, 'wbBasePortfolioRisk', 'input', { value: '6' });
  registerElement(elements, 'wbAtrStopK', 'input', { value: '1.2' });
  registerElement(elements, 'wbMinActiveRatio', 'input', { value: '60' });
  registerElement(elements, 'wbDdScale10', 'input', { value: '0.8' });
  registerElement(elements, 'wbDdScale15', 'input', { value: '0.6' });
  registerElement(elements, 'wbDdFixed20', 'input', { value: '3' });
  registerElement(elements, 'wbDdStopPct', 'input', { value: '35' });
  registerElement(elements, 'wbDdStopCooldown', 'input', { value: '60' });
  registerElement(elements, 'wbDdStopProtect', 'input', { value: '30' });
  registerElement(elements, 'wbMarketFilter', 'input', { checked: true });
  registerElement(elements, 'wbMfSlopeMaPeriod', 'input', { value: '50' });
  registerElement(elements, 'wbMfSlopeWindow', 'input', { value: '10' });
  registerElement(elements, 'wbMfBullMult', 'input', { value: '1.8' });
  registerElement(elements, 'wbMfLightMult', 'input', { value: '0.6' });
  registerElement(elements, 'wbMfEmaFast', 'input', { value: '5' });
  registerElement(elements, 'wbMfEmaSlow', 'input', { value: '20' });
  registerElement(elements, 'wbBreadthEnabled', 'input', { checked: false });
  registerElement(elements, 'wbBreadthMode', 'select', { value: 'dynamic_maxpos' });
  registerElement(elements, 'wbBreadthScoreType', 'select', { value: 'B' });
  registerElement(elements, 'wbBreadthMappingMode', 'select', { value: 'smooth' });
  registerElement(elements, 'wbBreadthMinPositions', 'input', { value: '3' });
  registerElement(elements, 'wbBreadthMaxPositions', 'input', { value: '15' });
  registerElement(elements, 'wbBreadthStepHigh', 'input', { value: '0.6' });
  registerElement(elements, 'wbBreadthStepMid', 'input', { value: '0.45' });
  registerElement(elements, 'wbBreadthSmoothLo', 'input', { value: '0.4' });
  registerElement(elements, 'wbBreadthSmoothRange', 'input', { value: '0.2' });
  registerElement(elements, 'wbBreadthEmaFast', 'input', { value: '8' });
  registerElement(elements, 'wbBreadthEmaSlow', 'input', { value: '25' });
  registerElement(elements, 'wbBreadthGateThreshold', 'input', { value: '0.45' });
  registerElement(elements, 'wbBreadthGateWindow', 'input', { value: '252' });
  registerElement(elements, 'wbBreadthGatePct', 'input', { value: '0.2' });
  registerElement(elements, 'wbBreadthGatePersist', 'input', { value: '3' });
  registerElement(elements, 'wbBreadthScaleFloor', 'input', { value: '0.3' });
  registerElement(elements, 'wbWeightMode', 'select', { value: 'equal' });
  registerElement(elements, 'wbMinPositions', 'input', { value: '10' });
  registerElement(elements, 'wbRunStatus', 'div');
  registerElement(elements, 'wbLogs', 'div', { dataset: {} });
  registerElement(elements, 'wbConfigJsonPreview', 'pre');
  registerElement(elements, 'wbSchemaBadge', 'div');
  registerElement(elements, 'wbSignalCompositionNotice', 'div');
  registerElement(elements, 'wbCompOutput', 'div');
  registerElement(elements, 'wbConfigDiff', 'pre');
  registerElement(elements, 'wbStrategyPack', 'select', { value: 'EMA_CROSS' });
  registerElement(elements, 'wbComposeRows', 'tbody', { dataset: {} });
  registerElement(elements, 'wbRegimeMatrix', 'div', { dataset: {} });
  registerElement(elements, 'wbExitPriorityList', 'ul');
  registerElement(elements, 'wbMrPanel', 'div', { style: {} });
}

function patchWorkbench(context) {
  let composeRows = clone(context.defaultComposeRows());
  let regimeMatrix = clone(context.defaultRegimeMatrix());

  context.hydrateComposeRows = (rows, options = {}) => {
    const data = Array.isArray(rows) && rows.length
      ? clone(rows)
      : (options.useDefault !== false ? clone(context.defaultComposeRows()) : []);
    composeRows = data;
    const el = context.byId('wbComposeRows');
    if (el) el.dataset.rows = JSON.stringify(data);
  };

  context.currentComposeRows = () => clone(composeRows);

  context.hydrateRegimeMatrix = (matrix = null) => {
    regimeMatrix = clone(matrix && typeof matrix === 'object' ? matrix : context.defaultRegimeMatrix());
    const el = context.byId('wbRegimeMatrix');
    if (el) el.dataset.matrix = JSON.stringify(regimeMatrix);
  };

  context.buildRegimeMatrixFromUi = () => clone(regimeMatrix);
  context.setSelectValuePreserveUnsupported = (id, value, fallback = '') => {
    const el = context.byId(id);
    if (!el) return;
    const next = value == null || value === '' ? (fallback || el.value) : String(value);
    el.value = next;
  };
  context.refreshConfigPanels = () => {
    context.state.multi_alpha_validation_errors = context.validateConfigDraft(context.state.config_draft || {});
  };
  context.syncConfigSourceUI = () => 'draft-only';
  context.syncResultsWorkbenchSurface = () => {};
  context.renderSummaryBar = () => {};
  context.renderConfigDiff = () => {};
  context.updateSignalCompositionSurface = () => {};
  context.renderRightInspector = () => {};
  context.renderPerfPanel = () => {};
  context.loadActiveArtifacts = async () => {};
  context.renderArtifacts = () => {};
  context.__getComposeRows = () => clone(composeRows);
  context.__getRegimeMatrix = () => clone(regimeMatrix);
};

function createWorkbenchHarness() {
  const elements = new Map();
  const document = createDocument(elements);
  const location = { href: 'http://localhost/index.html', pathname: '/index.html', search: '' };
  const context = {
    console,
    setTimeout,
    clearTimeout,
    URLSearchParams,
    document,
    location,
    window: {
      location,
      history: { replaceState() {} },
      resultsWorkbenchBridge: null,
    },
    navigator: {
      clipboard: {
        async writeText() {},
        async readText() { return ''; },
      },
    },
    fetch: async () => ({ async json() { return {}; } }),
    confirm: () => true,
    prompt: () => '',
    requestAnimationFrame: (fn) => { if (typeof fn === 'function') fn(); return 1; },
    cancelAnimationFrame: () => {},
    Blob: class Blob {},
    URL: { createObjectURL() { return 'blob:fake'; }, revokeObjectURL() {} },
    setStatusItems() {},
    renderPerfPanel() {},
    renderNavChartLW() {},
    renderDdChartLW() {},
    renderArtifacts() {},
    loadActiveArtifacts: async () => {},
    renderRightInspector() {},
  };
  context.window.navigator = context.navigator;
  context.window.requestAnimationFrame = context.requestAnimationFrame;
  context.window.cancelAnimationFrame = context.cancelAnimationFrame;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(BACKTEST_SCRIPT, 'utf8'), context, { filename: 'backtest_v2.js' });
  vm.runInContext(fs.readFileSync(UI_CONTROLS_SCRIPT, 'utf8'), context, { filename: 'ui-controls.js' });
  vm.runInContext("this.__codexExports = { state, byId, buildConfigDraft, validateConfigDraft, applyConfigToUI, runExperiment, defaultComposeRows, defaultRegimeMatrix };", context);
  Object.assign(context, context.__codexExports || {});
  defaultElementMap(elements);
  patchWorkbench(context);
  context.state.loaded_config_json = null;
  context.state.config_draft = {};
  context.buildConfigDraft();
  return { context, elements };
}

function loadAcceptanceRequest() {
  return JSON.parse(fs.readFileSync(ACCEPTANCE_REQUEST, 'utf8'));
}

function normalizeDraftForAcceptance(config) {
  const draft = clone(config) || {};
  const universe = draft.universe || {};
  const filters = universe.filters || {};
  const signalGeneration = draft.signal_generation || {};
  const signalComposition = draft.signal_composition || {};
  const positionRisk = draft.position_risk || {};
  return {
    mode: draft.mode,
    initial_capital: draft.initial_capital,
    universe_mode: draft.universe_mode,
    industries: Array.isArray(draft.industries) ? draft.industries.slice() : [],
    universe: {
      start: universe.start,
      end: universe.end,
      benchmark: universe.benchmark,
      symbols: Array.isArray(universe.symbols) ? universe.symbols.slice() : [],
      limit: universe.limit,
      price_adj: universe.price_adj,
      filters: {
        exclude_st: filters.exclude_st,
        exclude_suspended: filters.exclude_suspended,
        min_list_days: filters.min_list_days,
        min_avg_turnover_20d: filters.min_avg_turnover_20d,
        price_min: filters.price_min,
        price_max: filters.price_max,
        atr_pct_range: filters.atr_pct_range,
        limit_rule: filters.limit_rule,
      },
    },
    signal_generation: {
      enabled: signalGeneration.enabled,
      modules: (Array.isArray(signalGeneration.modules) ? signalGeneration.modules : []).map((module) => ({
        name: module.name,
        alpha_id: module.alpha_id,
        family: module.family,
      })),
    },
    signal_composition: {
      enabled: signalComposition.enabled,
      compose_mode: signalComposition.compose_mode,
      same_symbol_policy: signalComposition.same_symbol_policy,
      holding_ownership: signalComposition.holding_ownership,
      modules: (Array.isArray(signalComposition.modules) ? signalComposition.modules : []).map((module) => ({
        name: module.name,
        role: module.role,
        priority: module.priority,
        weight: module.weight,
      })),
      regime_matrix: clone(signalComposition.regime_matrix || {}),
    },
    position_risk: {
      enabled: positionRisk.enabled,
      portfolio_mode: positionRisk.portfolio_mode,
      max_positions: positionRisk.max_positions,
      single_stock_cap: positionRisk.single_stock_cap,
      industry_cap: positionRisk.industry_cap,
      lot: positionRisk.lot,
      cash_shortage_policy: positionRisk.cash_shortage_policy,
    },
  };
}

module.exports = {
  PROJECT_ROOT,
  clone,
  createWorkbenchHarness,
  loadAcceptanceRequest,
  normalizeDraftForAcceptance,
};


