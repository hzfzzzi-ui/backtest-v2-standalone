/* Inlined from ui.js to avoid ES-module scope isolation */
function setActiveNav() {
  const path = (location.pathname || '/').split('/').pop() || 'index.html';
  document.querySelectorAll('[data-nav]')?.forEach(a => {
    const href = a.getAttribute('href') || '';
    const key = href.split('/').pop();
    if (key === path) a.classList.add('active');
  });
}

const state = {
  mode: 'experiment',
  strategy_pack: 'EMA_CROSS',
  universe_mode: 'ALL_A',
  config_id: null,
  loaded_config_meta: null,
  loaded_config_json: null,
  loaded_config_snapshot: '',
  config_source_mode: 'draft-only',
  config_dirty: false,
  selected_locked_candidate_preset: '',
  config_draft: {},
  universe_stats: null,
  active_exp: null,
  active_result: null,
  active_artifacts: null,
  loaded_source_kind: '',
  loaded_source_id: '',
  execution_preview: null,
  execution_api_enabled: true,
  status_items: [],
  manual_status_items: [],
  validation_status_items: [],
  api_status: {},
  multi_alpha_module_state: {},
  multi_alpha_validation_errors: [],
  status_open: false,
  drawer_panel: 's1',
  drawer_pinned: false,
  main_tab: 'overview',
  dock_tab: 'explain',
  chart_show_benchmark: true,
  chart_range: 'D',
  chart_mode: 'portfolio',
  symbol_filter: '',
  symbol_sort: 'return_desc',
  selected_symbol: '',
  symbol_series_cache: {},
  symbol_series_loading: false,
  compare_selected_ids: [],
};

const DEFAULT_BOOTSTRAP_BASELINE_ID = 'baseline_V10';

const COMPOSE_MODULES = [
  {
    name: 'breakout_55',
    label: 'Breakout 55',
    alpha_id: 'breakout_55',
    family: 'trend',
    role: 'trend',
    weight: 0.7,
    priority: 100,
  },
  {
    name: 'rsi_reversal',
    label: 'RSI Reversal',
    alpha_id: 'rsi_reversal',
    family: 'mean_revert',
    role: 'mean_revert',
    weight: 0.3,
    priority: 80,
  },
];
const MULTI_ALPHA_COMPOSE_MODE = 'REGIME_ROUTE';
const MULTI_ALPHA_SAME_SYMBOL_POLICY = 'PREFER_HIGHER_SCORE';
const MULTI_ALPHA_HOLDING_OWNERSHIP = 'SOURCE_ONLY';
const MULTI_ALPHA_PORTFOLIO_MODE = 'hard_sleeve_budget';
const MULTI_ALPHA_REGIMES = ['TREND_UP', 'RANGE', 'WEAK_DOWN'];
const DEFAULT_MULTI_ALPHA_REGIME_MATRIX = {
  TREND_UP: ['breakout_55'],
  RANGE: ['breakout_55', 'rsi_reversal'],
  WEAK_DOWN: ['rsi_reversal'],
};

function byId(id) { return document.getElementById(id); }
function getStrategySelector() { return byId('wbTrendStrategy') || byId('wbStrategyPack') || byId('wbStrategyFamily'); }
function getStrategyPackValue() {
  if (byId('wbEnableComposition')?.checked) return 'COMPOSITE';
  const selected = String((byId('wbTrendStrategy') || byId('wbStrategyPack') || byId('wbStrategyFamily'))?.value || 'EMA_CROSS').toUpperCase();
  if (selected === 'BREAKOUT_TREND') return 'BREAKOUT_TREND';
  const regimeOn = !!byId('wbRegimeEnabled')?.checked;
  if (regimeOn) return 'REGIME_ROUTER';
  return selected || 'EMA_CROSS';
}
function setHtmlById(id, html) {
  const el = byId(id);
  if (!el) return;
  el.innerHTML = html;
}
function setTextById(id, text) {
  const el = byId(id);
  if (!el) return;
  el.textContent = text;
}
function esc(v) { return String(v ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;'); }
function num(v, d = 4) { const n = Number(v); return Number.isFinite(n) ? n.toFixed(d) : '-'; }
function pct(v) { const n = Number(v); return Number.isFinite(n) ? `${(n * 100).toFixed(2)}%` : '-'; }
function fmtInt(v) { const n = Number(v); return Number.isFinite(n) ? Math.round(n).toLocaleString('en-US') : '-'; }
function fmtMoney(v) { const n = Number(v); return Number.isFinite(n) ? n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-'; }

const REASON_MAP = {
  SMA_CROSS_UP: '均线金叉', SMA_CROSS_DOWN: '均线死叉',
  EMA_CROSS_UP: 'EMA金叉', EMA_CROSS_DOWN: 'EMA死叉',
  SIGNAL_REVERSE: '信号反转', ATR_STOP_LOSS: 'ATR止损',
  ATR_TRAIL_STOP: 'ATR追踪止损', TIME_EXIT: '到期平仓',
  TREND_REVERSE: '趋势反转', TREND_BREAK_EXIT: '趋势破位平仓',
  RISK_OFF_EXIT: '风控平仓', MANUAL_CLOSE: '手动平仓',
  MAX_HOLD_DAYS: '持仓到期', TAKE_PROFIT: '止盈',
  STOP_LOSS: '止损',
};
function reasonZh(code) { return REASON_MAP[code] || String(code ?? ''); }

function todayISO() { return new Date().toISOString().slice(0, 10); }

const CONFIG_SOURCE_LABELS = { baseline: '基线', search: '搜索', template: '模板', derived: '派生' };
const CONFIG_OWNER_LABELS = { manual: '手工', claude: 'Claude', script: '脚本', builtin: '内建' };

function stableSerializeConfig(value) {
  if (Array.isArray(value)) return `[${value.map((item) => stableSerializeConfig(item)).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableSerializeConfig(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value ?? null);
}

function cloneJson(value) {
  if (!value || typeof value !== 'object') return null;
  try { return JSON.parse(JSON.stringify(value)); } catch (_) { return null; }
}

function membershipModeDisplayLabel(universeMode, membershipMode) {
  const normalized = String(membershipMode || '').trim();
  if (!normalized) return '';
  if (normalized.toUpperCase() === 'PIT_DYNAMIC') return '';
  return `成分=${normalized}`;
}

function cloneConfigMeta(record) {
  if (!record || typeof record !== 'object') return null;
  const universeMode = record.universe_mode || record?.config_json?.universe_mode || null;
  const membershipMode = record.membership_mode || record?.config_json?.universe?.membership_mode || null;
  const rawDisplay = record.display_name || record.name || record.config_id || '';
  const displayNameWithUniverse = rawDisplay && universeMode ? `${rawDisplay} · 池=${universeMode}` : rawDisplay;
  const membershipLabel = membershipModeDisplayLabel(universeMode, membershipMode);
  const displayName = displayNameWithUniverse && membershipLabel
    ? `${displayNameWithUniverse} · ${membershipLabel}`
    : displayNameWithUniverse;
  return {
    config_id: record.config_id || null,
    config_hash: record.config_hash || null,
    display_name: displayName,
    name: record.name || record.display_name || rawDisplay,
    source_type: record.source_type || 'derived',
    owner: record.owner || 'manual',
    locked: !!record.locked,
    baseline_of: record.baseline_of || null,
    legacy_config_id: record.legacy_config_id || null,
    universe_mode: universeMode,
    membership_mode: membershipMode,
  };
}

function configMetaLabel(record) {
  const meta = cloneConfigMeta(record) || {};
  const source = CONFIG_SOURCE_LABELS[meta.source_type] || meta.source_type || '派生';
  const owner = CONFIG_OWNER_LABELS[meta.owner] || meta.owner || '手工';
  return `[${source}|${owner}]`;
}

function currentConfigSourceMode() {
  const meta = state.loaded_config_meta;
  if (!meta?.config_id) return 'draft-only';
  const snapshot = state.loaded_config_snapshot || '';
  const current = stableSerializeConfig(state.config_draft || {});
  return snapshot && snapshot === current ? 'loaded-clean' : 'loaded-dirty';
}

function getResultsWorkbenchBridge() {
  const bridge = window.resultsWorkbenchBridge;
  return bridge && typeof bridge === 'object' ? bridge : null;
}

function readLegacyOpenPanels() {
  return {
    symbolPanel: !!byId('wbAccSymbolPanel')?.classList.contains('wb-open'),
    funnelPanel: !!byId('wbAccBuyFunnel')?.classList.contains('wb-open'),
    tradesPanel: !!byId('wbAccTrades')?.classList.contains('wb-open'),
  };
}

function buildResultsWorkbenchSnapshot() {
  const bridge = getResultsWorkbenchBridge();
  const currentSnapshot = bridge && typeof bridge.getSnapshot === 'function'
    ? (bridge.getSnapshot() || {})
    : {};
  const currentView = currentSnapshot?.view || {};
  const openPanels = bridge
    ? { ...(currentView.openPanels || {}) }
    : readLegacyOpenPanels();
  const sourceKind = String(state.loaded_source_kind || '').trim()
    || (state.active_result?.exp_id ? 'experiment' : '');
  const sourceId = String(state.loaded_source_id || '').trim()
    || String(state.active_result?.exp_id || '');
  return {
    active: !!(state.active_result?.exp_id || state.active_artifacts),
    source: {
      kind: sourceKind,
      id: sourceId,
    },
    result: cloneJson(state.active_result) || null,
    artifacts: cloneJson(state.active_artifacts) || null,
    view: {
      chartMode: String(state.chart_mode || currentView.chartMode || 'portfolio'),
      chartRange: String(state.chart_range || currentView.chartRange || 'D'),
      showBenchmark: typeof state.chart_show_benchmark === 'boolean'
        ? state.chart_show_benchmark
        : !!currentView.showBenchmark,
      symbolFilter: String(state.symbol_filter || currentView.symbolFilter || ''),
      symbolSort: String(state.symbol_sort || currentView.symbolSort || 'return_desc'),
      selectedSymbol: String(state.selected_symbol || currentView.selectedSymbol || '').toLowerCase(),
      openPanels,
    },
  };
}

function publishResultsWorkbenchSnapshot() {
  const bridge = getResultsWorkbenchBridge();
  if (!bridge || typeof bridge.setSnapshot !== 'function') return false;
  bridge.setSnapshot(buildResultsWorkbenchSnapshot());
  return true;
}

function syncResultsWorkbenchSurface(options = {}) {
  const {
    summary = true,
    perf = true,
    explain = true,
    execution = true,
  } = options;
  publishResultsWorkbenchSnapshot();
  if (getResultsWorkbenchBridge()?.isMounted?.()) return;
  if (summary) renderSummaryBar();
  if (perf) renderPerfPanel();
  if (explain) renderExplainPanel();
  if (execution) renderExecutionPanel();
}

function syncResultsWorkbenchVisuals() {
  publishResultsWorkbenchSnapshot();
  if (getResultsWorkbenchBridge()?.isMounted?.()) return;
  renderPerfPanel();
}

function syncResultsWorkbenchSymbols() {
  publishResultsWorkbenchSnapshot();
  if (getResultsWorkbenchBridge()?.isMounted?.()) return;
  renderSymbolPerformancePanel();
}

function syncResultsWorkbenchExecution() {
  publishResultsWorkbenchSnapshot();
  if (getResultsWorkbenchBridge()?.isMounted?.()) return;
  renderExecutionPanel();
}

function syncConfigSourceUI() {
  const meta = state.loaded_config_meta;
  const mode = currentConfigSourceMode();
  state.config_source_mode = mode;
  state.config_dirty = mode === 'loaded-dirty';
  const idEl = byId('wbConfigId');
  if (idEl) idEl.textContent = meta?.config_id || '-';
  const chip = byId('wbConfigSourceChip');
  const text = byId('wbConfigSourceText');
  if (!chip || !text) return mode;
  const runMeta = (state.active_artifacts || {}).run_meta || {};
  const candidate = runMeta.candidate;
  if (candidate && state.active_result?.exp_id) {
    chip.className = 'wb-chip wb-ok';
    chip.textContent = '候选预设';
    text.textContent = `${candidate.candidate_name || 'locked_candidate'} | baseline=${candidate.source_baseline_exp_id || '-'}`;
    return 'active-candidate';
  }
  const display = meta?.display_name || meta?.name || meta?.config_id || '当前草稿';
  if (mode === 'draft-only') {
    chip.className = 'wb-chip';
    chip.textContent = '草稿运行';
    text.textContent = '当前运行/预览基于页面草稿';
    return mode;
  }
  if (mode === 'loaded-clean') {
    chip.className = 'wb-chip wb-ok';
    chip.textContent = `${configMetaLabel(meta)} 已加载`;
    text.textContent = `运行/预览以 ${display} (${meta.config_id}) 为准`;
    return mode;
  }
  chip.className = 'wb-chip wb-danger';
  chip.textContent = '草稿已偏离';
  text.textContent = `页面已偏离 ${meta.config_id}，运行/预览将基于当前草稿`;
  return mode;
}

syncConfigSourceUI = function syncConfigSourceUIV2() {
  const meta = state.loaded_config_meta;
  const mode = currentConfigSourceMode();
  state.config_source_mode = mode;
  state.config_dirty = mode === 'loaded-dirty';
  const idEl = byId('wbConfigId');
  if (idEl) idEl.textContent = meta?.config_id || '-';
  const chip = byId('wbConfigSourceChip');
  const text = byId('wbConfigSourceText');
  if (!chip || !text) return mode;
  const setDetail = (value, title = '') => {
    const normalized = String(value || '').trim();
    text.textContent = normalized;
    text.title = title || normalized;
    text.hidden = !normalized;
  };

  const selectedCandidatePreset = String(state.selected_locked_candidate_preset || '').trim();
  if (selectedCandidatePreset) {
    const candidateLabel = selectedCandidatePreset === 'v2-breakout-br35-atr10-candidate'
      ? '候选 BR35 + ATR1.0'
      : (selectedCandidatePreset === 'v2-breakout-atr-stop-k10-candidate' ? '候选 ATR 1.0' : selectedCandidatePreset);
    chip.className = 'wb-chip wb-ok';
    chip.textContent = '锁定候选';
    setDetail(candidateLabel, '当前运行将忽略页面草稿，按锁定候选执行');
    if (typeof syncPresetHint === 'function') syncPresetHint();
    return 'selected-candidate';
  }

  const runMeta = (state.active_artifacts || {}).run_meta || {};
  const candidate = runMeta.candidate;
  if (candidate && state.active_result?.exp_id) {
    chip.className = 'wb-chip wb-ok';
    chip.textContent = '候选';
    setDetail(
      `${candidate.candidate_name || 'locked_candidate'} | baseline=${candidate.source_baseline_exp_id || '-'}`,
      '当前右侧展示的是锁定候选结果',
    );
    if (typeof syncPresetHint === 'function') syncPresetHint();
    return 'active-candidate';
  }

  const display = meta?.display_name || meta?.name || meta?.config_id || '当前草稿';
  if (mode === 'draft-only') {
    chip.className = 'wb-chip';
    chip.textContent = '草稿';
    setDetail('');
    if (typeof syncPresetHint === 'function') syncPresetHint();
    return mode;
  }
  if (mode === 'loaded-clean') {
    chip.className = 'wb-chip wb-ok';
    chip.textContent = '已加载';
    const sourceLabel = compactLoadedSourceLabel(state.loaded_source_kind, state.loaded_source_id) || display;
    setDetail(sourceLabel, `当前运行 / 预览以 ${sourceLabel} 为准`);
    if (typeof syncPresetHint === 'function') syncPresetHint();
    return mode;
  }
  chip.className = 'wb-chip wb-danger';
  chip.textContent = '草稿已改动';
  setDetail(
    `已偏离 ${compactLoadedSourceLabel(state.loaded_source_kind, state.loaded_source_id) || meta.config_id}`,
    `页面已偏离 ${meta.config_id}，运行 / 预览将基于当前草稿`,
  );
  if (typeof syncPresetHint === 'function') syncPresetHint();
  return mode;
};

function rememberLoadedConfig(record, snapshot = null, sourceConfig = null) {
  state.loaded_config_meta = cloneConfigMeta(record);
  state.loaded_config_json = cloneJson(sourceConfig || record?.config_json || null);
  state.config_id = state.loaded_config_meta?.config_id || null;
  state.loaded_config_snapshot = snapshot || stableSerializeConfig(state.config_draft || {});
  syncConfigSourceUI();
}

function clearLoadedConfig(reason = '') {
  state.loaded_config_meta = null;
  state.loaded_config_json = null;
  state.loaded_config_snapshot = '';
  state.config_id = null;
  state.loaded_source_kind = '';
  state.loaded_source_id = '';
  syncWorkbenchConfigSourceToUrl('', '');
  if (reason) addLog(reason);
  syncLoadHint();
  syncConfigSourceUI();
}

function effectiveConfigIdForExecution() {
  return state.loaded_config_meta?.config_id || null;
}

function configDisplayName(record) {
  const base = record?.display_name || record?.name || record?.config_id || '';
  const universeMode = record?.universe_mode || record?.config_json?.universe_mode || '';
  if (!base) return universeMode ? `池=${universeMode}` : '';
  if (!universeMode || base.includes(`池=${universeMode}`)) return base;
  return universeMode ? `${base} · 池=${universeMode}` : base;
}

function isVerboseExperimentLabel(label) {
  const text = String(label || '').trim();
  if (!text) return false;
  const upper = text.toUpperCase();
  return text.length > 96
    || text.startsWith('{')
    || upper.includes("'PARAMS'")
    || upper.includes('"PARAMS"')
    || upper.includes('BREAKOUT_WINDOW')
    || upper.includes('REGIME_MA')
    || upper.includes('SECTOR_TOP_PCT');
}

function compactExperimentLabel(record) {
  const expId = String(record?.exp_id || record?.id || '').trim();
  const label = String(record?.label || '').trim();
  if (!label) return expId || '-';
  if (!isVerboseExperimentLabel(label)) return label;
  return expId || label.slice(0, 48);
}

function compactLoadedSourceLabel(kind, sourceId) {
  const normalizedId = String(sourceId || '').trim();
  if (!normalizedId) return '';
  return String(kind || '').trim().toLowerCase() === 'experiment'
    ? `实验 ${normalizedId}`
    : `基线 ${normalizedId}`;
}

function loadItemYearLabel(item) {
  const startYear = Number(item?.start_year);
  const endYear = Number(item?.end_year);
  if (Number.isFinite(startYear) && Number.isFinite(endYear)) return `${startYear}-${endYear}`;
  if (Number.isFinite(startYear)) return `${startYear}-`;
  if (Number.isFinite(endYear)) return `-${endYear}`;
  return '';
}

function loadItemBadgeLabel(item) {
  return item?.kind === 'baseline' ? '基线' : '实验';
}

function loadItemBadgeClass(item) {
  return item?.kind === 'baseline' ? 'wb-load-kind-baseline' : 'wb-load-kind-experiment';
}

function addLog(msg) {
  const el = byId('wbLogs');
  if (!el) return;
  const now = new Date().toLocaleTimeString();
  const line = `${esc(now)} ${esc(msg)}`;
  let prev = [];
  if (el.dataset.lines) {
    try { prev = JSON.parse(el.dataset.lines); } catch (_) { prev = []; }
  }
  const lines = [line, ...prev].slice(0, 20);
  el.dataset.lines = JSON.stringify(lines);
  el.innerHTML = lines.join('<br>');
}

function currentWorkbenchConfigSourceFromUrl() {
  try {
    const params = new URLSearchParams(window.location.search || '');
    const loadId = String(params.get('load_id') || '').trim();
    const loadKind = String(params.get('load_kind') || '').trim().toLowerCase();
    if (loadId) return { kind: loadKind === 'experiment' ? 'experiment' : 'baseline', id: loadId };
    const legacyLoadExpId = String(params.get('load_exp_id') || '').trim();
    if (legacyLoadExpId) return { kind: 'experiment', id: legacyLoadExpId };
  } catch (_) {
    return null;
  }
  return null;
}

function syncWorkbenchConfigSourceToUrl(kind, sourceId) {
  try {
    const url = new URL(window.location.href);
    const normalizedId = String(sourceId || '').trim();
    const normalizedKind = String(kind || '').trim().toLowerCase();
    url.searchParams.delete('exp_id');
    url.searchParams.delete('load_exp_id');
    if (normalizedId) {
      url.searchParams.set('load_kind', normalizedKind === 'experiment' ? 'experiment' : 'baseline');
      url.searchParams.set('load_id', normalizedId);
    } else {
      url.searchParams.delete('load_kind');
      url.searchParams.delete('load_id');
    }
    window.history.replaceState({}, '', url.toString());
  } catch (_) {
    // URL sync failure should not block experiment loading.
  }
}

async function bootstrapInitialExperiment() {
  const source = currentWorkbenchConfigSourceFromUrl() || { kind: 'baseline', id: DEFAULT_BOOTSTRAP_BASELINE_ID };
  if (!source?.id || state.loaded_source_id) return;
  try {
    if (source.kind === 'experiment') await loadExperimentBundle(source.id);
    else await loadBaselineToWorkbench(source.id);
  } catch (e) {
    addLog(`默认加载失败: ${source?.id || '-'} | ${e?.message || e}`);
  }
}

/* ── 主 Tab 切换 ── */

function syncLoadHint(expId = '') {
  const hint = byId('wbLoadHint');
  if (!hint) return;
  const activeId = String(expId || state.loaded_source_id || '').trim();
  const activeKind = String(state.loaded_source_kind || '').trim().toLowerCase();
  if (activeId) {
    hint.textContent = compactLoadedSourceLabel(activeKind, activeId);
    hint.title = activeKind === 'experiment'
      ? `当前控件与结果来源实验：${activeId}`
      : `当前控件来源：基线 ${activeId}`;
    return;
  }
  hint.textContent = `基线：${DEFAULT_BOOTSTRAP_BASELINE_ID}`;
  hint.title = '点击“加载”可导入基线或实验；基线无关联结果时，结果面板保持为空';
}

function normalizeLoadItems(baselines, experiments) {
  const baselineRows = (Array.isArray(baselines) ? baselines : [])
    .filter((item) => String(item?.baseline_id || '').trim())
    .map((item) => ({
      kind: 'baseline',
      id: String(item.baseline_id || '').trim(),
      label: String(item.display_name || item.name || item.baseline_id || '').trim(),
      created_at: String(item.updated_at || item.created_at || '').trim(),
      has_result: !!item.has_result,
      linked_exp_id: String(item.linked_exp_id || '').trim(),
      universe_mode: String(item.universe_mode || '').trim(),
      membership_mode: String(item.membership_mode || '').trim(),
      start_year: item?.start_year,
      end_year: item?.end_year,
      cagr: item?.cagr,
      max_drawdown: item?.max_drawdown,
      trades: null,
    }));
  const experimentRows = (Array.isArray(experiments) ? experiments : [])
    .filter((item) => String(item?.exp_id || '').trim())
    .map((item) => ({
      kind: 'experiment',
      id: String(item.exp_id || '').trim(),
      label: compactExperimentLabel(item),
      created_at: String(item.created_at || '').trim(),
      has_result: true,
      linked_exp_id: String(item.exp_id || '').trim(),
      universe_mode: String(item?.universe_mode || '').trim(),
      membership_mode: String(item?.membership_mode || '').trim(),
      start_year: item?.start_year,
      end_year: item?.end_year,
      cagr: item?.cagr,
      max_drawdown: item?.max_drawdown,
      trades: item?.trades,
    }));
  const ensureDefault = baselineRows.some((item) => item.id === DEFAULT_BOOTSTRAP_BASELINE_ID);
  if (!ensureDefault) {
    baselineRows.unshift({
      kind: 'baseline',
      id: DEFAULT_BOOTSTRAP_BASELINE_ID,
      label: DEFAULT_BOOTSTRAP_BASELINE_ID,
      created_at: '',
      has_result: false,
      linked_exp_id: '',
      universe_mode: '',
      membership_mode: '',
      cagr: null,
      trades: null,
    });
  }
  baselineRows.sort((a, b) => {
    if (a.id === DEFAULT_BOOTSTRAP_BASELINE_ID && b.id !== DEFAULT_BOOTSTRAP_BASELINE_ID) return -1;
    if (b.id === DEFAULT_BOOTSTRAP_BASELINE_ID && a.id !== DEFAULT_BOOTSTRAP_BASELINE_ID) return 1;
    return (Date.parse(b.created_at) || 0) - (Date.parse(a.created_at) || 0);
  });
  experimentRows.sort((a, b) => (Date.parse(b.created_at) || 0) - (Date.parse(a.created_at) || 0));
  return [...baselineRows, ...experimentRows];
}

function experimentLoadSummary(item) {
  const parts = [];
  if (Number.isFinite(Number(item?.cagr))) parts.push(`CAGR ${pct(item.cagr)}`);
  if (Number.isFinite(Number(item?.max_drawdown))) parts.push(`回撤 ${pct(item.max_drawdown)}`);
  const yearLabel = loadItemYearLabel(item);
  if (yearLabel) parts.push(yearLabel);
  if (item?.universe_mode) parts.push(item.universe_mode);
  const membershipLabel = membershipModeDisplayLabel(item?.universe_mode, item?.membership_mode);
  if (membershipLabel) parts.push(membershipLabel);
  if (!parts.length && item?.kind === 'baseline') {
    parts.push(item?.has_result ? '已关联结果' : '仅配置');
  }
  if (!parts.length && item?.kind === 'experiment' && Number.isFinite(Number(item?.trades))) {
    parts.push(`交易 ${fmtInt(item.trades)}`);
  }
  return parts.join(' | ') || '等待结果';
}

async function fetchExperimentLoadMetrics(expId) {
  const normalizedExpId = String(expId || '').trim();
  if (!normalizedExpId) return {};
  const manifest = await apiRequestJson(
    `experiment_manifest_${normalizedExpId}`,
    `/api/backtest_v2/experiments/${encodeURIComponent(normalizedExpId)}/manifest`,
  );
  const perfRel = String(manifest?.artifacts?.perf || 'perf.json').trim();
  const configRel = String(manifest?.artifacts?.config || 'config.json').trim();
  const [perfPayload, configPayload] = await Promise.all([
    apiRequestJson(
      `artifact_read_perf_${normalizedExpId}`,
      '/api/backtest_v2/artifacts/read',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exp_id: normalizedExpId, rel_path: perfRel }),
      },
    ),
    apiRequestJson(
      `artifact_read_config_${normalizedExpId}`,
      '/api/backtest_v2/artifacts/read',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exp_id: normalizedExpId, rel_path: configRel }),
      },
    ),
  ]);
  const perf = perfPayload?.data || {};
  const cfgPayload = configPayload?.data || {};
  const workbenchCfg = extractWorkbenchConfigFromExperimentPayload(cfgPayload) || {};
  const universe = workbenchCfg?.universe || {};
  const start = String(universe?.start || '').trim();
  const end = String(universe?.end || '').trim();
  const startYear = start && /^\d{4}/.test(start) ? Number(start.slice(0, 4)) : null;
  const endYear = end && /^\d{4}/.test(end) ? Number(end.slice(0, 4)) : null;
  return {
    cagr: perf?.cagr,
    max_drawdown: perf?.max_drawdown,
    universe_mode: String(workbenchCfg?.universe_mode || '').trim(),
    membership_mode: String(workbenchCfg?.universe?.membership_mode || '').trim(),
    start_year: Number.isFinite(startYear) ? startYear : null,
    end_year: Number.isFinite(endYear) ? endYear : null,
  };
}

async function enrichLoadItems(items) {
  const rows = Array.isArray(items) ? items.map((item) => ({ ...item })) : [];
  const experimentCache = new Map();
  const ensureExperimentMetrics = async (expId) => {
    const normalizedExpId = String(expId || '').trim();
    if (!normalizedExpId) return {};
    if (!experimentCache.has(normalizedExpId)) {
      experimentCache.set(normalizedExpId, fetchExperimentLoadMetrics(normalizedExpId).catch(() => ({})));
    }
    return experimentCache.get(normalizedExpId);
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
    legacy_config_id: null,
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
  addLog(`导入基线：${normalizedBaselineId}`);
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

function switchMainTab(tab) {
  const next = tab || 'overview';
  state.main_tab = next;
  document.querySelectorAll('.wb-main-tabs button[data-main-tab]').forEach((b) => b.classList.toggle('active', b.getAttribute('data-main-tab') === next));
  document.querySelectorAll('.wb-main-panel').forEach((p) => p.classList.remove('active'));
  const panel = byId(next === 'overview' ? 'wbTabOverview' : 'wbTabAnalysis');
  if (panel) panel.classList.add('active');
}

/* ── Wrapper functions that call into other modules ── */

function renderRightInspector() {
  // Legacy fallback only: migrated result workbench is owned by the Vue shell.
  syncResultsWorkbenchSurface();
}

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
  const j = await apiRequestJson('configs_save', '/api/backtest_v2/configs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  rememberLoadedConfig(j, stableSerializeConfig(cfg), cfg);
  addLog(`配置已保存(${kind}): ${j.config_id}`);
  await loadConfigList();
}

async function saveCurrentBaseline() {
  const currentDraft = buildConfigDraft();
  const suggestedName = String(
    state.loaded_source_kind === 'baseline'
      ? (state.loaded_source_id || DEFAULT_BOOTSTRAP_BASELINE_ID)
      : (state.loaded_config_meta?.display_name || DEFAULT_BOOTSTRAP_BASELINE_ID)
  ).trim() || DEFAULT_BOOTSTRAP_BASELINE_ID;
  const baselineName = String(window.prompt('请输入基线名称', suggestedName) || '').trim();
  if (!baselineName) return;
  const linkedExpId = currentConfigSourceMode() === 'loaded-clean' ? String(state.active_result?.exp_id || '').trim() : '';
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
  state.loaded_config_meta = {
    config_id: state.loaded_source_id,
    display_name: String(payload?.display_name || payload?.name || state.loaded_source_id),
    name: String(payload?.name || payload?.display_name || state.loaded_source_id),
    source_type: 'baseline',
    owner: String(payload?.owner || 'manual'),
    locked: true,
    baseline_of: null,
    legacy_config_id: null,
    universe_mode: currentDraft?.universe_mode || null,
    membership_mode: currentDraft?.universe?.membership_mode || null,
  };
  state.loaded_config_json = cloneJson(currentDraft);
  state.loaded_config_snapshot = stableSerializeConfig(state.config_draft || currentDraft || {});
  state.config_id = state.loaded_source_id;
  syncWorkbenchConfigSourceToUrl(state.loaded_source_kind, state.loaded_source_id);
  syncLoadHint(state.loaded_source_id);
  syncConfigSourceUI();
  addLog(`基线已保存：${state.loaded_source_id}${linkedExpId ? ` | 关联实验=${linkedExpId}` : ' | 无关联结果'}`);
}

function bindEvents() {
  document.querySelectorAll('#wbMode button').forEach((btn) => btn.addEventListener('click', () => setMode(btn.getAttribute('data-mode') || 'experiment')));
  // Universe 模式按钮绑定
  document.querySelectorAll('#wbUniverseModeGroup button').forEach((btn) => {
    btn.addEventListener('click', () => {
      const val = btn.getAttribute('data-val');
      if (!val) return;
      // 切换 active 样式
      document.querySelectorAll('#wbUniverseModeGroup button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      // 更新 hidden select
      const sel = byId('wbUniverseMode');
      if (sel) sel.value = val;
      updateUniverseInputVisibility();
      buildConfigDraft();
      renderRunHints();
    });
  });
  byId('wbUniverseMode')?.addEventListener('change', () => { updateUniverseInputVisibility(); buildConfigDraft(); renderRunHints(); });
  document.querySelectorAll('#wbConstituentGroup button').forEach((btn) => {
    btn.addEventListener('click', () => {
      const val = btn.getAttribute('data-val');
      if (!val) return;
      if (typeof syncMembershipModeButtons === 'function') syncMembershipModeButtons(val);
      else {
        document.querySelectorAll('#wbConstituentGroup button').forEach((button) => button.classList.remove('active'));
        btn.classList.add('active');
        const sel = byId('wbConstituent');
        if (sel) sel.value = val;
      }
      buildConfigDraft();
      renderRunHints();
    });
  });
  byId('wbConstituent')?.addEventListener('change', () => {
    if (typeof syncMembershipModeButtons === 'function') syncMembershipModeButtons(byId('wbConstituent')?.value || 'dynamic');
    buildConfigDraft();
    renderRunHints();
  });
  // 价格口径按钮绑定
  document.querySelectorAll('#wbAdjGroup button').forEach((btn) => {
    btn.addEventListener('click', () => {
      const val = btn.getAttribute('data-val');
      if (!val) return;
      document.querySelectorAll('#wbAdjGroup button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const sel = byId('wbPriceAdj');
      if (sel) sel.value = val;
      buildConfigDraft();
      updateAtrNote();
    });
  });
  byId('wbTrendStrategy')?.addEventListener('change', () => { buildConfigDraft(); });
  byId('wbMrStrategy')?.addEventListener('change', () => { buildConfigDraft(); });
  byId('wbRegimeEnabled')?.addEventListener('change', () => {
    const on = !!byId('wbRegimeEnabled').checked;
    const regimeParams = byId('wbRegimeParams'); if (regimeParams) regimeParams.style.display = on ? '' : 'none';
    const mrPanel = byId('wbMrPanel'); if (mrPanel) mrPanel.style.opacity = on ? '1' : '0.45';
    const rfBlock = byId('wbRegimeFilterBlock'); if (rfBlock) rfBlock.style.display = on ? '' : 'none';
    buildConfigDraft();
  });
  byId('wbRegimeFilterEnabled')?.addEventListener('change', () => {
    const on = !!byId('wbRegimeFilterEnabled').checked;
    const rfParams = byId('wbRegimeFilterParams'); if (rfParams) rfParams.style.display = on ? '' : 'none';
    buildConfigDraft();
  });
  // 入场过滤：斜率 checkbox 控制 lookback 输入的 disabled 状态
  byId('wbEntrySlowMaSlope')?.addEventListener('change', () => {
    const lb = byId('wbEntrySlopeLookback');
    if (lb) lb.disabled = !byId('wbEntrySlowMaSlope').checked;
    buildConfigDraft();
  });
  byId('wbEntryAboveSlowMa')?.addEventListener('change', buildConfigDraft);
  document.querySelectorAll('.wb-rail-btn').forEach((btn) => btn.addEventListener('click', () => {
    const panel = btn.getAttribute('data-panel') || 's1';
    setDrawerPanel(panel);
    /* open drawer if collapsed */
    const app = document.querySelector('.wb-app');
    if (app && app.classList.contains('wb-drawer-hidden')) toggleDrawer(false);
    if (panel === 'history') loadExperimentList();
  }));

  byId('wbRunBtn')?.addEventListener('click', async () => {
    try { setStatusItems([]); await runByMode(); } catch (e) {
      const msg = e.message || String(e);
      byId('wbRunStatus').textContent = `运行失败: ${msg}`;
      addLog(String(e));
      setStatusItems([{ title: '运行失败', message: msg, detail: String(e) }]);
    }
  });
  byId('wbPresetSelect')?.addEventListener('change', () => { syncPresetHint(); });
  byId('wbRunPreset')?.addEventListener('click', async () => {
    try { setStatusItems([]); await runExperiment(); } catch (e) {
      const msg = e.message || String(e);
      byId('wbRunStatus').textContent = `预设运行失败: ${msg}`;
      addLog(String(e));
      setStatusItems([{ title: '预设运行失败', message: msg, detail: String(e) }]);
    }
  });
  byId('wbSaveBaseline')?.addEventListener('click', async () => {
    try {
      await saveCurrentBaseline();
    } catch (e) {
        addLog(`保存基线失败：${e?.message || e}`);
    }
  });

  byId('wbSaveConfig')?.addEventListener('click', async () => { try { await saveConfig('draft'); } catch (e) { addLog(`保存失败: ${e.message || e}`); } });
  byId('wbSaveTemplate')?.addEventListener('click', async () => { try { await saveConfig('template'); } catch (e) { addLog(`模板保存失败: ${e.message || e}`); } });
  byId('wbSaveFlowScript')?.addEventListener('click', async () => { try { await saveConfig('flow_script'); } catch (e) { addLog(`通流脚本保存失败: ${e.message || e}`); } });
  byId('wbCopyCfgJson')?.addEventListener('click', copyConfigJson);
  byId('wbPasteCfgJson')?.addEventListener('click', pasteConfigJson);
  byId('wbDiffCfg')?.addEventListener('click', renderConfigDiff);
  byId('wbApplyGroup')?.addEventListener('click', async () => {
    const cfg = state.active_artifacts?.config;
    if (!cfg) { addLog('当前结果缺少config.json'); return; }
    const draft = cfg?.overrides?.workbench_config || cfg?.workbench_config || cfg;
    applyConfigToUI(draft || {});
    clearLoadedConfig();
    addLog(`已应用 exp_id=${state.active_result?.exp_id || '-'} 配置`);
  });

  document.querySelectorAll('.wb-main-tabs button[data-main-tab]').forEach((btn) => btn.addEventListener('click', () => switchMainTab(btn.getAttribute('data-main-tab') || 'overview')));
  document.querySelectorAll('.wb-analysis-tabs button[data-dock], .wb-dock-tabs button[data-dock]').forEach((btn) => {
    btn.addEventListener('click', () => switchDockTab(btn.getAttribute('data-dock') || 'explain'));
  });
  document.querySelectorAll('#wbResultsLegacyRoot .wb-result-acc').forEach((acc) => {
    const summary = acc.querySelector(':scope > .wb-result-acc-toggle');
    const body = acc.querySelector(':scope > .wb-result-acc-body');
    if (!summary || !body) return;
    const syncResultAccordion = () => {
      const isOpen = acc.classList.contains('wb-open');
      body.hidden = !isOpen;
      summary.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    };
    syncResultAccordion();
    if (acc.dataset.boundToggle === '1') return;
    acc.dataset.boundToggle = '1';
    summary.addEventListener('click', () => {
      acc.classList.toggle('wb-open');
      syncResultAccordion();
    });
  });
  byId('wbPreviewExec')?.addEventListener('click', async () => { try { await previewExecution(); } catch (e) { addLog(`execution失败: ${e.message || e}`); } });
  byId('wbCopyExec')?.addEventListener('click', copyExecJson);
  byId('wbChartMode')?.addEventListener('change', (e) => {
    state.chart_mode = String(e.target.value || 'portfolio');
    syncResultsWorkbenchVisuals();
  });
  byId('wbChartBenchToggle')?.addEventListener('change', (e) => { state.chart_show_benchmark = !!e.target.checked; syncResultsWorkbenchVisuals(); });
  byId('wbChartRange')?.addEventListener('change', (e) => { state.chart_range = String(e.target.value || 'ALL'); syncResultsWorkbenchVisuals(); });
  byId('wbSymbolFilter')?.addEventListener('input', (e) => {
    state.symbol_filter = String(e.target.value || '').trim();
    syncResultsWorkbenchSymbols();
  });
  byId('wbSymbolSort')?.addEventListener('change', (e) => {
    state.symbol_sort = String(e.target.value || 'return_desc');
    syncResultsWorkbenchSymbols();
  });
  byId('wbExportReport')?.addEventListener('click', () => { generateReport().catch((e) => addLog(`报告生成失败: ${e}`)); });
  byId('wbCopyReportMd')?.addEventListener('click', () => { copyAgentMarkdownReport().catch((e) => addLog(`Markdown 复制失败: ${e}`)); });
  byId('wbStatusBell')?.addEventListener('click', () => toggleStatusPanel());
  byId('wbErrorBannerView')?.addEventListener('click', () => toggleStatusPanel(true));
  byId('wbDrawerToggle')?.addEventListener('click', () => {
    const app = document.querySelector('.wb-app');
    if (!app) return;
    toggleDrawer(!app.classList.contains('wb-drawer-hidden'));
  });
  byId('wbDrawerPin')?.addEventListener('click', () => {
    state.drawer_pinned = !state.drawer_pinned;
    const btn = byId('wbDrawerPin');
    if (btn) btn.classList.toggle('active', state.drawer_pinned);
    addLog(state.drawer_pinned ? '抽屉已固定' : '抽屉已取消固定');
  });

  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && (e.key === 'b' || e.key === 'B')) {
      e.preventDefault();
      const app = document.querySelector('.wb-app');
      if (!app) return;
      toggleDrawer(!app.classList.contains('wb-drawer-hidden'));
    }
  });

  // Clear all experiments handler
  byId('wbHistoryClear')?.addEventListener('click', async () => {
    if (!confirm('确定清空所有实验记录？此操作不可恢复。')) return;
    try {
      await apiRequestJson('clearExperiments', '/api/backtest_v2/experiments', { method: 'DELETE' });
      addLog('所有实验记录已清空');
      renderHistoryPanel([]);
    } catch (e) {
      addLog(`清空失败: ${e?.message || e}`);
    }
  });
  byId('wbHistoryCompare')?.addEventListener('click', async () => {
    try {
      await openExperimentCompare();
    } catch (e) {
      addLog(`对比失败: ${e?.message || e}`);
    }
  });
  byId('wbCompareClose')?.addEventListener('click', () => closeExperimentCompare());

  document.querySelectorAll('input,select,textarea').forEach((el) => {
    el.addEventListener('input', () => buildConfigDraft());
    el.addEventListener('change', () => buildConfigDraft());
  });

  byId('wbEnableComposition')?.addEventListener('change', () => {
    const enabled = !!byId('wbEnableComposition')?.checked;
    const portfolioMode = byId('wbPortfolioMode');
    if (!portfolioMode) return;
    if (enabled && ['equal_10', 'profit_release', ''].includes(String(portfolioMode.value || '').trim())) {
      portfolioMode.value = MULTI_ALPHA_PORTFOLIO_MODE;
    }
    if (!enabled && String(portfolioMode.value || '').trim() === MULTI_ALPHA_PORTFOLIO_MODE) {
      portfolioMode.value = 'equal_10';
    }
    buildConfigDraft();
  });

  // Exit checkbox ↔ input linkage
  byId('wbExitTrail')?.addEventListener('change', syncExitLinkage);
  byId('wbExitTime')?.addEventListener('change', syncExitLinkage);

  // ATR note updates when price adj / match price changes
  byId('wbPriceAdj')?.addEventListener('change', updateAtrNote);
  byId('wbMatchPrice')?.addEventListener('change', updateAtrNote);

  // Public surface only keeps experiment loading; replace any legacy config-load bindings.
  const quickLoadBtn = byId('wbQuickLoad');
  if (quickLoadBtn) {
    const cleanQuickLoadBtn = quickLoadBtn.cloneNode(true);
    quickLoadBtn.replaceWith(cleanQuickLoadBtn);
    cleanQuickLoadBtn.addEventListener('click', async (evt) => {
      evt.preventDefault();
      evt.stopImmediatePropagation();
      evt.stopPropagation();
      try {
        await openExperimentLoadDropdown(cleanQuickLoadBtn);
      } catch (e) {
        addLog(`加载实验失败: ${e?.message || e}`);
      }
    });
  }
}

function init() {
  setActiveNav();
  hydrateComposeRows(defaultComposeRows());
  if (byId('wbExecDate')) byId('wbExecDate').value = todayISO();
  if (byId('wbChartBenchToggle')) byId('wbChartBenchToggle').checked = true;
  if (byId('wbChartRange')) byId('wbChartRange').value = 'D';
  if (byId('wbChartMode')) byId('wbChartMode').value = 'portfolio';
  if (byId('wbSymbolSort')) byId('wbSymbolSort').value = 'return_desc';
  bindEvents();
  setDrawerPanel('s1');
  switchMainTab('overview');
  document.querySelectorAll('#wbResultsLegacyRoot .wb-result-acc').forEach((acc) => {
    acc.classList.remove('wb-open');
    const body = acc.querySelector(':scope > .wb-result-acc-body');
    if (body) body.hidden = true;
  });
  updateUniverseInputVisibility();
  renderRunHints();
  buildConfigDraft();
  syncExitLinkage();
  updateAtrNote();
  syncPresetHint();
  syncLoadHint();
  setStatusItems([]);
  renderRightInspector();
  bootstrapInitialExperiment().catch((e) => { addLog(`默认实验启动失败: ${e?.message || e}`); });
  addLog('Strategy Workbench 已就绪');
}

// ── 实验历史面板 ──────────────────────────────────────────

async function loadExperimentList() {
  try {
    const data = await apiRequestJson('experiments', '/api/backtest_v2/experiments');
    renderHistoryPanel(data);
  } catch (e) {
    addLog(`加载实验列表失败: ${e?.message || e}`);
    renderHistoryPanel([]);
  }
}

function renderHistoryPanel(experiments) {
  const container = byId('wbHistoryList');
  if (!container) return;
  if (!experiments || !experiments.length) {
    state.compare_selected_ids = [];
    const countEl = byId('wbHistoryCompareCount');
    if (countEl) countEl.textContent = '已选 0';
    container.innerHTML = `<div class="wb-empty" style="padding:24px 0">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      <span>暂无实验记录，运行回测后将自动保存</span>
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
      <div class="wb-mini"><label><input type="checkbox" class="wb-hc-compare" data-exp="${expId}" ${checked}/> 加入对比</label></div>
      <div class="wb-stat-row">
        <div class="wb-stat-item"><span class="wb-stat-label">收益</span><span class="wb-stat-value ${trClass}">${totalReturn}</span></div>
        <div class="wb-stat-item"><span class="wb-stat-label">回撤</span><span class="wb-stat-value ${ddClass}">${maxDd}</span></div>
        <div class="wb-stat-item"><span class="wb-stat-label">夏普</span><span class="wb-stat-value">${sharpe}</span></div>
        <div class="wb-stat-item"><span class="wb-stat-label">交易</span><span class="wb-stat-value">${trades}</span></div>
      </div>
      <div class="wb-hc-actions">
        <button class="pill wb-hc-load" data-exp="${expId}">加载结果</button>
      </div>
      <div class="wb-hc-time">${created}</div>
    </div>`;
  }).join('');

  // Bind load buttons
  container.querySelectorAll('.wb-hc-load').forEach((btn) => btn.addEventListener('click', async (ev) => {
    ev.stopPropagation();
    const expId = btn.getAttribute('data-exp');
    await loadHistoricalExperiment(expId);
  }));
  const syncCompareCount = () => {
    const count = (state.compare_selected_ids || []).length;
    const countEl = byId('wbHistoryCompareCount');
    if (countEl) countEl.textContent = `已选 ${count}`;
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
  addLog(`加载历史实验: ${expId}`);
  const manifest = await apiRequestJson('experiment_manifest', `/api/backtest_v2/experiments/${encodeURIComponent(expId)}/manifest`);
  // Build a minimal result object so loadActiveArtifacts can work
  const fakeResult = {
    exp_id: expId,
    experiment_id: expId,
    status: 'OK',
    artifacts: manifest?.artifacts || {},
    manifest,
  };
  state.active_exp = fakeResult;
  state.active_result = fakeResult;
  await loadActiveArtifacts();
  renderRightInspector();
  addLog(`已加载历史实验: ${expId}`);
}

