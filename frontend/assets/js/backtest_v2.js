/* backtest_v2.js: desktop legacy shell bootstrap/controller only. */
/* It must not own config compile truth or visible DOM under #wbResultsWorkbenchMount. */
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
  ...((window.createWorkbenchConfigDraftState && window.createWorkbenchConfigDraftState()) || {}),
  ...((window.createRunSessionState && window.createRunSessionState()) || {}),
  ...((window.createActiveExperimentState && window.createActiveExperimentState()) || {}),
  ...((window.createViewState && window.createViewState()) || {}),
};

const DEFAULT_BOOTSTRAP_CONFIG_ID = 'cfg_cn_stock_etf_v1';
const DEFAULT_BOOTSTRAP_BASELINE_ID = 'baseline_V10_2';
const DEFAULT_BOOTSTRAP_SOURCE = {
  kind: 'config',
  id: DEFAULT_BOOTSTRAP_CONFIG_ID,
  label: 'A股个股+ETFV1',
};
const FALLBACK_BOOTSTRAP_SOURCE = {
  kind: 'baseline',
  id: 'baseline_V10_2',
  label: 'V10.2 | 2012-2026',
};

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
const DEFAULT_ASSET_SCOPE = 'cn_a_equity';
const ASSET_CONTEXT_DEFAULTS = Object.freeze({
  cn_a_equity: Object.freeze({
    asset_scope: 'cn_a_equity',
    asset_profile_id: 'cn_a_equity_mainline',
    market_profile_id: 'cn_a_mainland_equity_market',
    execution_profile_id: 'cn_a_tplus1_next_open',
    asset_family: 'equity',
    asset_class: 'equity',
  }),
  cn_etf: Object.freeze({
    asset_scope: 'cn_etf',
    asset_profile_id: 'cn_etf_first_wave_research',
    market_profile_id: 'cn_etf_mainland_fund_market',
    execution_profile_id: 'cn_etf_tplus1_next_open',
    asset_family: 'fund',
    asset_class: 'etf',
  }),
  us_equity: Object.freeze({
    asset_scope: 'us_equity',
    asset_profile_id: 'us_equity_prepare_mainline',
    market_profile_id: 'us_equity_primary_market',
    execution_profile_id: 'us_equity_tplus1_next_open',
    asset_family: 'equity',
    asset_class: 'equity',
  }),
});
const DEFAULT_ASSET_PROFILE_ID = ASSET_CONTEXT_DEFAULTS.cn_a_equity.asset_profile_id;
const DEFAULT_MARKET_PROFILE_ID = ASSET_CONTEXT_DEFAULTS.cn_a_equity.market_profile_id;
const DEFAULT_EXECUTION_PROFILE_ID = ASSET_CONTEXT_DEFAULTS.cn_a_equity.execution_profile_id;

function canonicalAssetScope(scope) {
  const raw = scope && typeof scope === 'object' ? scope.asset_scope : scope;
  const text = String(raw || '').trim().toLowerCase();
  if (!text) return DEFAULT_ASSET_SCOPE;
  if (['cn_etf', 'a_share_etf', 'a_shares_etf', 'cn_fund_etf'].includes(text)) return 'cn_etf';
  if (['us_equity', 'us_stock', 'us_stocks', 'us_equities'].includes(text)) return 'us_equity';
  return 'cn_a_equity';
}

function assetContextDefaults(scope = DEFAULT_ASSET_SCOPE) {
  const canonicalScope = canonicalAssetScope(scope);
  return ASSET_CONTEXT_DEFAULTS[canonicalScope] || ASSET_CONTEXT_DEFAULTS[DEFAULT_ASSET_SCOPE];
}

function resolvePreferredAssetScope(scope = null) {
  const candidates = [
    scope,
    state?.config_draft?.asset_scope,
    state?.active_asset_context?.asset_scope,
    state?.loaded_source_asset_context?.asset_scope,
    DEFAULT_ASSET_SCOPE,
  ];
  for (const candidate of candidates) {
    const raw = candidate && typeof candidate === 'object' ? candidate.asset_scope : candidate;
    const text = String(raw || '').trim();
    if (text) return canonicalAssetScope(raw);
  }
  return DEFAULT_ASSET_SCOPE;
}

function isCnAAssetScope(scope = null) {
  return resolvePreferredAssetScope(scope) === 'cn_a_equity';
}

function isCnEtfAssetScope(scope = null) {
  return resolvePreferredAssetScope(scope) === 'cn_etf';
}

function isRuntimeSupportedAssetScope(scope = null) {
  const resolvedScope = resolvePreferredAssetScope(scope);
  return resolvedScope === 'cn_a_equity' || resolvedScope === 'cn_etf';
}

function assetScopeDisplayNameLegacyShim(scope = null) {
  return isCnAAssetScope(scope) ? 'A股' : '美股';
}

function syncAssetAwareShell(scope = null) {
  const resolvedScope = resolvePreferredAssetScope(scope);
  const isCn = isCnAAssetScope(resolvedScope);
  const brandText = isCn ? '多资产趋势研究台 | A股' : '多资产趋势研究台 | 美股入口准备中';
  document.title = brandText;
  const brandEl = document.querySelector('.wb-brand');
  if (brandEl) brandEl.textContent = brandText;
  document.body.dataset.assetScope = resolvedScope;

  const runBtn = byId('wbRunBtn');
  if (runBtn) {
    runBtn.disabled = !isRuntimeSupportedAssetScope(resolvedScope);
    runBtn.title = isCn ? '运行当前资产草稿' : '当前仅完成美股个股入口边界，尚未支持运行';
  }

  const pitStatus = byId('wbPitStatus');
  if (pitStatus) {
    pitStatus.textContent = isCn ? 'PIT 启用' : '美股入口准备中';
    pitStatus.className = isCn ? 'wb-chip wb-ok' : 'wb-chip';
  }

  const universeModeGroup = byId('wbUniverseModeGroup');
  if (universeModeGroup) {
    universeModeGroup.dataset.assetScope = resolvedScope;
    universeModeGroup.title = isCn ? '当前为 A 股 universe 入口' : '当前 universe 控件仅支持 A 股，切换到美股时不会运行';
  }
}

function assetScopeDisplayName(scope = null) {
  const resolvedScope = resolvePreferredAssetScope(scope);
  if (resolvedScope === 'cn_etf') return 'A股ETF';
  if (resolvedScope === 'us_equity') return '美股';
  return 'A股个股';
}

function joinSummaryCodes(values) {
  const items = Array.isArray(values)
    ? values.map((value) => String(value || '').trim()).filter(Boolean)
    : [];
  return items.length ? items.join(', ') : '-';
}

function summarizeGlobalManualOverride(payload) {
  const overridePayload = payload && typeof payload === 'object' ? payload : {};
  if (!overridePayload.active) return '无';
  const parts = [
    String(overridePayload.scope || 'override').trim(),
    String(overridePayload.target_state_5 || '').trim(),
    String(overridePayload.reason || '').trim(),
  ].filter(Boolean);
  return parts.length ? parts.join(' | ') : '已启用';
}

function resolveAssetScopedPanelMeta(scope = null) {
  const resolvedScope = resolvePreferredAssetScope(scope);
  if (resolvedScope === 'cn_etf') {
    return {
      s1: { label: 'ETF池', title: 'ETF Beta 范围', hidden: false },
      s2: { label: 'Regime', title: 'Regime 规则', hidden: true },
      s3: { label: '候选池', title: 'ETF 候选池', hidden: false },
      s4: { label: 'Beta', title: 'ETF Beta 规则', hidden: false },
      s5: { label: '排序', title: 'ETF 排序', hidden: false },
      s6: { label: '调仓', title: '调仓 / 配置', hidden: false },
      s7: { label: 'Governor', title: 'Governor 预算', hidden: true },
      s8: { label: '风险', title: '风险约束', hidden: false },
      s9: { label: '退出', title: '退出 / 保护', hidden: false },
    };
  }
  if (resolvedScope === 'us_equity') {
    return {
      s1: { label: '入口', title: '美股入口', hidden: false },
      s2: { label: 'Regime', title: 'Regime 规则', hidden: true },
      s3: { label: '预留', title: '预留', hidden: true },
      s4: { label: '预留', title: '预留', hidden: true },
      s5: { label: '预留', title: '预留', hidden: true },
      s6: { label: '预留', title: '预留', hidden: true },
      s7: { label: 'Governor', title: 'Governor 预算', hidden: true },
      s8: { label: '预留', title: '预留', hidden: true },
      s9: { label: '预留', title: '预留', hidden: true },
    };
  }
  return {
    s1: { label: '股票池', title: '股票 Alpha 范围', hidden: false },
    s2: { label: 'Regime', title: 'Regime 规则', hidden: true },
    s3: { label: '范围', title: '股票范围 / 行业', hidden: false },
    s4: { label: '趋势', title: '趋势 / 信号', hidden: false },
    s5: { label: '排序', title: '残差排序', hidden: false },
    s6: { label: '建仓', title: '组合构建', hidden: false },
    s7: { label: 'Governor', title: 'Governor 预算', hidden: true },
    s8: { label: '风控', title: '风险控制', hidden: false },
    s9: { label: '退出', title: '退出规则', hidden: false },
  };
}

function syncAssetScopedRail(scope = null) {
  const resolvedScope = resolvePreferredAssetScope(scope);
  const panelMeta = resolveAssetScopedPanelMeta(resolvedScope);
  const fallbackPanel = Object.entries(panelMeta).find(([, meta]) => !meta.hidden)?.[0] || 's1';

  Object.entries(panelMeta).forEach(([panel, meta]) => {
    const upperPanel = String(panel || '').toUpperCase();
    const button = byId(`wbStage${upperPanel}Btn`) || document.querySelector(`.wb-rail-btn[data-panel="${panel}"]`);
    const labelEl = byId(`wbStage${upperPanel}Label`) || button?.querySelector?.('.wb-rail-label') || null;
    if (button) {
      button.hidden = !!meta.hidden;
      if (meta.title) button.title = meta.title;
    }
    if (labelEl && meta.label) labelEl.textContent = meta.label;
  });

  if (state.drawer_panel && panelMeta[state.drawer_panel]?.hidden && typeof setDrawerPanel === 'function') {
    setDrawerPanel(fallbackPanel);
  }
}

function syncGlobalControlStrip(scope = null) {
  const resolvedScope = resolvePreferredAssetScope(scope);
  const runMeta = state?.active_artifacts?.run_meta && typeof state.active_artifacts.run_meta === 'object'
    ? state.active_artifacts.run_meta
    : {};
  const comboTruth = state?.active_artifacts?.comboTruth
    && typeof state.active_artifacts.comboTruth === 'object'
      ? state.active_artifacts.comboTruth
      : null;
  const researchComboDisplay = comboTruth?.display && typeof comboTruth.display === 'object'
    ? comboTruth.display
    : (
      state?.active_artifacts?.researchComboDisplay
      && typeof state.active_artifacts.researchComboDisplay === 'object'
        ? state.active_artifacts.researchComboDisplay
        : null
    );
  const configDraft = state?.config_draft && typeof state.config_draft === 'object'
    ? state.config_draft
    : {};
  const universe = configDraft.universe && typeof configDraft.universe === 'object'
    ? configDraft.universe
    : {};
  const isResearchCombo = String(runMeta?.data?.asset_role || '').trim().toLowerCase() === 'research_combo';
  const latestRegime = runMeta.regime?.latest_state && typeof runMeta.regime.latest_state === 'object'
    ? runMeta.regime.latest_state
    : {};
  const governedSnapshot = runMeta.governed_snapshot && typeof runMeta.governed_snapshot === 'object'
    ? runMeta.governed_snapshot
    : {};
  const comboRegime = researchComboDisplay?.regime && typeof researchComboDisplay.regime === 'object'
    ? researchComboDisplay.regime
    : {};
  const comboGovernor = researchComboDisplay?.governor && typeof researchComboDisplay.governor === 'object'
    ? researchComboDisplay.governor
    : {};

  const assetModeSummary = resolvedScope === 'cn_etf'
    ? `ETF池：${String(runMeta.universe?.preset_id || configDraft.universe_mode || 'CUSTOM').trim() || 'CUSTOM'}`
    : `股票池：${String(configDraft.universe_mode || 'ALL_A').trim() || 'ALL_A'}`;
  const timeWindowSummary = `窗口：${String(universe.start || '-')} ~ ${String(universe.end || '-')}`;
  const baseState = isResearchCombo
    ? String(comboRegime.base_state || '-')
    : String(latestRegime.base_state || governedSnapshot.regime_source_state || '-');
  const effectiveState = isResearchCombo
    ? String(comboRegime.effective_state || '-')
    : String(latestRegime.effective_state || governedSnapshot.regime_effective_state || '-');
  const coarseState = isResearchCombo
    ? String(comboRegime.coarse_state || '-')
    : String(latestRegime.effective_coarse_state || latestRegime.coarse_state || governedSnapshot.effective_coarse_state || governedSnapshot.coarse_state || '-');
  const budgetMultiplier = isResearchCombo
    ? String(comboRegime.risk_budget_multiplier_text || '-')
    : (latestRegime.risk_budget_multiplier != null ? num(latestRegime.risk_budget_multiplier, 2) : '-');
  const regimeReason = isResearchCombo
    ? String(comboRegime.reason_text || '-')
    : joinSummaryCodes(latestRegime.reason_codes || governedSnapshot.regime_reason_codes);
  const manualOverrideSummary = isResearchCombo
    ? String(comboRegime.manual_override_text || '无')
    : summarizeGlobalManualOverride(latestRegime.manual_override || governedSnapshot.manual_override);

  const budgetConsumer = isResearchCombo
    ? String(comboGovernor.budget_consumer_text || '-')
    : (String(
      governedSnapshot.budget_consumer_sleeve_id
      || runMeta.etf_beta?.sleeve_id
      || runMeta.report_consistency?.stock_alpha_core_role
      || '-',
    ).trim() || '-');
  const budgetReason = isResearchCombo
    ? String(comboGovernor.budget_reason_text || '-')
    : joinSummaryCodes(governedSnapshot.budget_reason_codes);
  const totalRiskBudget = isResearchCombo
    ? String(comboGovernor.total_risk_budget_text || '-')
    : (governedSnapshot.total_risk_budget != null ? pct(governedSnapshot.total_risk_budget) : '-');
  const totalExposureCap = isResearchCombo
    ? String(comboGovernor.total_exposure_cap_text || '-')
    : (governedSnapshot.total_exposure_cap != null ? pct(governedSnapshot.total_exposure_cap) : '-');
  const defenseBias = governedSnapshot.defense_bias != null
    ? governedSnapshot.defense_bias
    : latestRegime.defense_bias;
  const hasRunResult = !!(state?.active_result?.exp_id || state?.active_artifacts?.run_meta);
  const hasFormalRegimeData = Boolean(
    (isResearchCombo && comboRegime.available)
    || latestRegime.base_state
    || latestRegime.effective_state
    || latestRegime.reason_codes?.length
    || governedSnapshot.regime_source_state
    || governedSnapshot.regime_effective_state
  );
  const hasGovernorData = Boolean(
    (isResearchCombo && comboGovernor.available)
    || governedSnapshot.total_risk_budget != null
    || governedSnapshot.total_exposure_cap != null
    || governedSnapshot.budget_consumer_sleeve_id
    || governedSnapshot.budget_reason_codes?.length
  );

  setTextById('wbGlobalAssetSummary', assetScopeDisplayName(resolvedScope));
  setTextById('wbGlobalAssetModeSummary', assetModeSummary);
  setTextById('wbGlobalDataWindowSummary', timeWindowSummary);
  setTextById('wbGlobalRegimeBase', baseState);
  setTextById('wbGlobalRegimeEffective', effectiveState);
  setTextById('wbGlobalRegimeCoarse', coarseState);
  setTextById('wbGlobalRegimeBudgetMultiplier', budgetMultiplier);
  setTextById('wbGlobalRegimeReason', regimeReason);
  setTextById('wbGlobalRegimeManual', manualOverrideSummary);
  setTextById('wbGlobalGovernorBudget', totalRiskBudget);
  setTextById('wbGlobalGovernorExposure', totalExposureCap);
  setTextById('wbGlobalGovernorSleeve', budgetConsumer);
  setTextById('wbGlobalGovernorDefense', defenseBias != null ? pct(defenseBias) : '-');
  setTextById('wbGlobalGovernorReason', budgetReason);

  const regimeDetail = byId('wbGlobalRegimeDetail');
  const regimeEmpty = byId('wbGlobalRegimeEmpty');
  if (regimeDetail) regimeDetail.hidden = !hasFormalRegimeData;
  if (regimeEmpty) {
    regimeEmpty.hidden = hasFormalRegimeData;
    regimeEmpty.textContent = hasRunResult
      ? '当前结果未提供 formal regime 数据'
      : '运行后在这里显示 formal regime 摘要';
  }

  const governorDetail = byId('wbGlobalGovernorDetail');
  const governorEmpty = byId('wbGlobalGovernorEmpty');
  if (governorDetail) governorDetail.hidden = !hasGovernorData;
  if (governorEmpty) {
    governorEmpty.hidden = hasGovernorData;
    governorEmpty.textContent = hasRunResult
      ? '当前结果未提供 governed snapshot'
      : '运行后在这里显示 Governor 摘要';
  }
}

function syncAssetAwareShell(scope = null) {
  const resolvedScope = resolvePreferredAssetScope(scope);
  const isCn = isCnAAssetScope(resolvedScope);
  const isEtf = isCnEtfAssetScope(resolvedScope);
  const isSupported = isRuntimeSupportedAssetScope(resolvedScope);
  const brandText = isCn
    ? '多资产趋势研究台 | A股个股'
    : (isEtf ? '多资产趋势研究台 | A股ETF' : '多资产趋势研究台 | 美股入口准备中');
  document.title = brandText;
  const brandEl = document.querySelector('.wb-brand');
  if (brandEl) brandEl.textContent = brandText;
  document.body.dataset.assetScope = resolvedScope;

  const runBtn = byId('wbRunBtn');
  if (runBtn) {
    runBtn.disabled = !isSupported;
    runBtn.title = isSupported ? '运行当前资产草稿' : '当前仅完成入口边界，尚未支持运行';
  }

  const pitStatus = byId('wbPitStatus');
  if (pitStatus) {
    pitStatus.textContent = isCn ? 'PIT 启用' : (isEtf ? 'ETF 目录研究' : '美股入口准备中');
    pitStatus.className = isSupported ? 'wb-chip wb-ok' : 'wb-chip';
  }

  const universeModeGroup = byId('wbUniverseModeGroup');
  if (universeModeGroup) {
    universeModeGroup.dataset.assetScope = resolvedScope;
    universeModeGroup.title = isCn
      ? '当前为 A 股个股 universe 入口'
      : (isEtf ? '当前为 A 股 ETF 入口，仅支持 CUSTOM 和预设名单' : '当前 universe 控件仅支持 A 股与 ETF，切换到美股时不会运行');
  }

  setTextById('wbAssetScopeLabel', '资产范围');
  setTextById('wbUniverseModeLabel', isEtf ? 'ETF 预设 / 标的' : '股票池范围');
  setTextById('wbSymbolsLabel', isEtf ? 'ETF 代码 / 预设' : '自选代码');
  setTextById('wbPitStatusLabel', isEtf ? '研究口径' : '点位一致');
  setTextById('wbBenchmarkLabel', isEtf ? '比较基准' : '基准');
  syncAssetScopedRail(resolvedScope);
  syncGlobalControlStrip(resolvedScope);
}

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
  SMA_CROSS_UP: 'Golden Cross', SMA_CROSS_DOWN: 'Death Cross',
  EMA_CROSS_UP: 'EMA Golden Cross', EMA_CROSS_DOWN: 'EMA Death Cross',
  SIGNAL_REVERSE: 'Signal Reverse', ATR_STOP_LOSS: 'ATR Stop',
  ATR_TRAIL_STOP: 'ATR Trail Stop', TIME_EXIT: 'Time Exit',
  TREND_REVERSE: 'Trend Reverse', TREND_BREAK_EXIT: 'Trend Break Exit',
  RISK_OFF_EXIT: 'Risk Off Exit', MANUAL_CLOSE: 'Manual Close',
  MAX_HOLD_DAYS: 'Max Hold Days', TAKE_PROFIT: 'Take Profit',
  STOP_LOSS: 'Stop Loss',
};
function reasonZh(code) { return REASON_MAP[code] || String(code ?? ''); }

function todayISO() { return new Date().toISOString().slice(0, 10); }

const LOADED_SOURCE_LABELS = { baseline: 'Baseline', search: 'Search', template: 'Template', derived: 'Derived', config: 'Config' };
const CONFIG_OWNER_LABELS = { manual: 'Manual', claude: 'Claude', script: 'Script', builtin: 'Built-in' };

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
  return `Membership=${normalized}`;
}

function normalizeAssetContext(value, fallbackScope = DEFAULT_ASSET_SCOPE) {
  const raw = (value && typeof value === 'object') ? (cloneJson(value) || {}) : {};
  const scope = resolvePreferredAssetScope(raw.asset_scope || fallbackScope);
  const defaults = assetContextDefaults(scope);
  return {
    ...defaults,
    ...raw,
    asset_scope: scope,
    asset_profile_id: String(raw.asset_profile_id || defaults.asset_profile_id || '').trim(),
    market_profile_id: String(raw.market_profile_id || defaults.market_profile_id || '').trim(),
    execution_profile_id: String(raw.execution_profile_id || defaults.execution_profile_id || '').trim(),
    asset_family: String(raw.asset_family || defaults.asset_family || defaults.asset_class || '').trim(),
    asset_class: String(raw.asset_class || defaults.asset_class || defaults.asset_family || '').trim(),
  };
}

function assetContextFromPayload(payload, fallbackScope = DEFAULT_ASSET_SCOPE) {
  if (payload && typeof payload === 'object') {
    if (payload.asset_context && typeof payload.asset_context === 'object') {
      return normalizeAssetContext(payload.asset_context, payload.asset_scope || fallbackScope);
    }
    return normalizeAssetContext({
      asset_scope: payload.asset_scope,
      asset_profile_id: payload.asset_profile_id,
      market_profile_id: payload.market_profile_id,
      execution_profile_id: payload.execution_profile_id,
    }, fallbackScope);
  }
  return normalizeAssetContext(null, fallbackScope);
}

function cloneLoadedSourceMeta(record) {
  if (!record || typeof record !== 'object') return null;
  const sourceId = String(record.source_id || record.loaded_id || record.config_id || '').trim() || null;
  const universeMode = record.universe_mode || record?.config_json?.universe_mode || null;
  const membershipMode = record.membership_mode || record?.config_json?.universe?.membership_mode || null;
  const assetContext = assetContextFromPayload(record, record?.config_json?.asset_scope || DEFAULT_ASSET_SCOPE);
  const rawDisplay = record.display_name || record.name || sourceId || '';
  const displayNameWithUniverse = rawDisplay && universeMode ? `${rawDisplay} | Universe=${universeMode}` : rawDisplay;
  const membershipLabel = membershipModeDisplayLabel(universeMode, membershipMode);
  const displayName = displayNameWithUniverse && membershipLabel
    ? `${displayNameWithUniverse} | ${membershipLabel}`
    : displayNameWithUniverse;
  return {
    source_id: sourceId,
    config_ref: record.config_id || null,
    config_hash: record.config_hash || null,
    display_name: displayName,
    name: record.name || record.display_name || rawDisplay,
    source_type: record.source_type || 'derived',
    owner: record.owner || 'manual',
    locked: !!record.locked,
    baseline_of: record.baseline_of || null,
    universe_mode: universeMode,
    membership_mode: membershipMode,
    asset_context: assetContext,
  };
}

function loadedSourceMetaLabel(record) {
  const meta = cloneLoadedSourceMeta(record) || {};
  const source = LOADED_SOURCE_LABELS[meta.source_type] || meta.source_type || 'Derived';
  const owner = CONFIG_OWNER_LABELS[meta.owner] || meta.owner || 'Manual';
  return `[${source}|${owner}]`;
}

function currentLoadedSourceMode() {
  const sourceId = String(state.loaded_source_id || '').trim();
  if (!sourceId) return 'draft-only';
  const snapshot = state.loaded_source_snapshot || '';
  const current = stableSerializeConfig(state.config_draft || {});
  return snapshot && snapshot === current ? 'loaded-clean' : 'loaded-dirty';
}

function currentRuntimeSourceRef() {
  const runtimeKind = String(state.runtime_source_kind || '').trim();
  const runtimeId = String(state.runtime_source_id || '').trim();
  if (runtimeKind && runtimeId) return { kind: runtimeKind, id: runtimeId };
  const manifestExpId = String(state.active_manifest?.exp_id || '').trim();
  if (manifestExpId) return { kind: 'experiment', id: manifestExpId };
  const activeExpId = String(state.active_result?.exp_id || state.active_exp?.exp_id || '').trim();
  if (activeExpId) return { kind: 'experiment', id: activeExpId };
  return { kind: '', id: '' };
}

function rememberRuntimeSource(kind, sourceId, manifest = null, assetContext = null) {
  state.runtime_source_kind = String(kind || '').trim();
  state.runtime_source_id = String(sourceId || '').trim();
  if (manifest && typeof manifest === 'object') {
    state.active_manifest = cloneJson(manifest);
  }
  if (assetContext || (manifest && typeof manifest === 'object')) {
    state.active_asset_context = assetContextFromPayload(
      assetContext || manifest,
      state.loaded_source_asset_context?.asset_scope || DEFAULT_ASSET_SCOPE,
    );
  }
  return currentRuntimeSourceRef();
}

function clearRuntimeSource() {
  state.active_manifest = null;
  state.active_surface_summary = null;
  state.active_asset_context = null;
  state.runtime_source_kind = '';
  state.runtime_source_id = '';
}

function getResultsWorkbenchBridge() {
  if (typeof window.getDesktopResultsWorkbenchBridge === 'function') {
    return window.getDesktopResultsWorkbenchBridge();
  }
  const bridge = window.resultsWorkbenchBridge;
  return bridge && typeof bridge === 'object' ? bridge : null;
}

function buildResultsWorkbenchSnapshot() {
  if (typeof window.buildDesktopResultsWorkbenchSnapshot === 'function') {
    const bridge = getResultsWorkbenchBridge();
    const currentSnapshot = bridge && typeof bridge.getSnapshot === 'function'
      ? (bridge.getSnapshot() || {})
      : {};
    const currentView = currentSnapshot?.view || {};
    const openPanels = { ...(currentView.openPanels || {}) };
    return window.buildDesktopResultsWorkbenchSnapshot({
      state,
      currentSnapshot,
      openPanels,
    });
  }
  const bridge = getResultsWorkbenchBridge();
  const currentSnapshot = bridge && typeof bridge.getSnapshot === 'function'
    ? (bridge.getSnapshot() || {})
    : {};
  const currentView = currentSnapshot?.view || {};
  const openPanels = { ...(currentView.openPanels || {}) };
  if (window.buildDesktopResultsWorkbenchSnapshot) {
    return window.buildDesktopResultsWorkbenchSnapshot({
      state,
      currentSnapshot,
      openPanels,
    });
  }
  return {
    active: !!(state.active_result?.exp_id || state.active_artifacts),
    source: {
      kind: currentRuntimeSourceRef().kind || String(state.loaded_source_kind || '').trim() || (state.active_result?.exp_id ? 'experiment' : ''),
      id: currentRuntimeSourceRef().id || String(state.loaded_source_id || '').trim() || String(state.active_result?.exp_id || ''),
    },
    assetContext: normalizeAssetContext(
      state.active_asset_context
      || state.loaded_source_asset_context
      || currentSnapshot.assetContext
      || null,
      state.config_draft?.asset_scope || DEFAULT_ASSET_SCOPE,
    ),
    result: cloneJson(state.active_result) || null,
    manifest: cloneJson(state.active_manifest) || null,
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

function publishResultsWorkbenchSnapshot(options = {}) {
  if (typeof window.publishDesktopResultsWorkbenchSnapshot === 'function') {
    return window.publishDesktopResultsWorkbenchSnapshot({
      state,
      lazySections: options.lazySections || [],
      viewPatch: options.viewPatch || null,
      openPanels: options.openPanels || null,
      sourceKind: options.sourceKind || '',
      sourceId: options.sourceId || '',
    });
  }
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
  if (summary) renderSummaryBar();
  if (perf) renderPerfPanel();
  if (explain) renderExplainPanel();
  if (execution) renderExecutionPanel();
}

function syncResultsWorkbenchVisuals() {
  publishResultsWorkbenchSnapshot();
  renderPerfPanel();
}

function syncResultsWorkbenchSymbols() {
  publishResultsWorkbenchSnapshot();
  renderSymbolPerformancePanel();
}

function syncResultsWorkbenchExecution() {
  publishResultsWorkbenchSnapshot();
  renderExecutionPanel();
}

function applyResultsWorkbenchViewPatchToState(patch = {}) {
  if (!patch || typeof patch !== 'object') return;
  if (patch.chartMode != null) state.chart_mode = String(patch.chartMode || 'portfolio');
  if (patch.chartRange != null) state.chart_range = String(patch.chartRange || 'D');
  if (typeof patch.showBenchmark === 'boolean') state.chart_show_benchmark = !!patch.showBenchmark;
  if (patch.symbolFilter != null) state.symbol_filter = String(patch.symbolFilter || '');
  if (patch.symbolSort != null) state.symbol_sort = String(patch.symbolSort || 'return_desc');
  if (patch.selectedSymbol != null) state.selected_symbol = String(patch.selectedSymbol || '').toLowerCase();
}

function patchDesktopResultsWorkbenchViewState(patch = {}) {
  applyResultsWorkbenchViewPatchToState(patch);
  return publishResultsWorkbenchSnapshot({
    viewPatch: patch,
    openPanels: patch && typeof patch === 'object' ? (patch.openPanels || null) : null,
  });
}

function syncLoadedSourceUI() {
  const meta = state.loaded_source_meta;
  const mode = currentLoadedSourceMode();
  state.loaded_source_sync_mode = mode;
  state.loaded_source_dirty = mode === 'loaded-dirty';
  const runtimeSource = currentRuntimeSourceRef();
  const sourceKind = String(state.loaded_source_kind || '').trim();
  const sourceId = String(state.loaded_source_id || '').trim();
  const sourceLabel = compactLoadedSourceLabel(sourceKind, sourceId);
  const idEl = byId('wbConfigId');
  if (idEl) idEl.textContent = runtimeSource.id || sourceId || '-';
  const chip = byId('wbInputSourceChip');
  const textEl = byId('wbInputSourceText');
  if (!chip || !textEl) return mode;
  const setDetail = (value, title = '') => {
    const normalized = String(value || '').trim();
    textEl.textContent = normalized;
    textEl.title = title || normalized;
    textEl.hidden = !normalized;
  };

  const selectedCandidatePreset = String(state.selected_locked_candidate_preset || '').trim();
  if (selectedCandidatePreset) {
    const candidateLabel = selectedCandidatePreset === 'v2-breakout-br35-atr10-candidate'
      ? 'Candidate BR35 + ATR1.0'
      : (selectedCandidatePreset === 'v2-breakout-atr-stop-k10-candidate' ? 'Candidate ATR 1.0' : selectedCandidatePreset);
    chip.className = 'wb-chip wb-ok';
    chip.textContent = 'Candidate';
    setDetail(candidateLabel, 'Current run source is a locked candidate preset');
    if (typeof syncPresetHint === 'function') syncPresetHint();
    return 'selected-candidate';
  }

  const runMeta = (state.active_artifacts || {}).run_meta || {};
  const candidate = runMeta.candidate;
  if (candidate && state.active_result?.exp_id) {
    chip.className = 'wb-chip wb-ok';
    chip.textContent = 'Result';
    setDetail(
      `${candidate.candidate_name || 'locked_candidate'} | baseline=${candidate.source_baseline_exp_id || '-'}`,
      'Current result comes from a locked runtime candidate'
    );
    if (typeof syncPresetHint === 'function') syncPresetHint();
    return 'active-candidate';
  }

  if (runtimeSource.kind === 'experiment' && runtimeSource.id) {
    const manifest = state.active_manifest || state.active_result?.manifest || {};
    const summary = state.active_surface_summary || state.active_artifacts?.surfaceSummary || {};
    const runtimeDisplay = String(
      summary?.label
      || summary?.display_name
      || manifest?.display_name
      || manifest?.title
      || `Runtime ${runtimeSource.id}`
    ).trim();
    chip.className = 'wb-chip wb-ok';
    chip.textContent = 'Result';
    setDetail(runtimeDisplay, `Current runtime source: ${runtimeSource.id}`);
    if (typeof syncPresetHint === 'function') syncPresetHint();
    return 'runtime-result';
  }

  const display = meta?.display_name || meta?.name || sourceLabel || sourceId || 'Current draft';
  if (mode === 'draft-only') {
    chip.className = 'wb-chip';
    chip.textContent = 'Draft';
    setDetail('');
    if (typeof syncPresetHint === 'function') syncPresetHint();
    return mode;
  }
  if (mode === 'loaded-clean') {
    chip.className = 'wb-chip wb-ok';
    chip.textContent = 'Loaded';
    setDetail(display, `Current page matches loaded source: ${display}`);
    if (typeof syncPresetHint === 'function') syncPresetHint();
    return mode;
  }
  chip.className = 'wb-chip wb-danger';
  chip.textContent = 'Diverged';
  setDetail(`Draft diverged from ${display}`, `Current run will use the page draft instead of reusing ${display}`);
  if (typeof syncPresetHint === 'function') syncPresetHint();
  return mode;
}
function rememberLoadedSource(record, snapshot = null, sourceConfig = null) {
  state.loaded_source_meta = cloneLoadedSourceMeta(record);
  state.loaded_source_asset_context = cloneJson(state.loaded_source_meta?.asset_context)
    || assetContextFromPayload(sourceConfig || record?.config_json || record, DEFAULT_ASSET_SCOPE);
  state.loaded_source_config = cloneJson(sourceConfig || record?.config_json || null);
  state.loaded_source_kind = String(record?.loaded_kind || 'config').trim() || 'config';
  state.loaded_source_id = String(state.loaded_source_meta?.source_id || '').trim();
  syncWorkbenchLoadedSourceToUrl(state.loaded_source_kind, state.loaded_source_id);
  state.loaded_source_snapshot = snapshot || stableSerializeConfig(state.config_draft || {});
  syncLoadedSourceUI();
}

function clearLoadedSource(reason = '') {
  state.loaded_source_meta = null;
  state.loaded_source_asset_context = null;
  state.loaded_source_config = null;
  state.loaded_source_snapshot = '';
  state.loaded_source_kind = '';
  state.loaded_source_id = '';
  syncWorkbenchLoadedSourceToUrl('', '');
  if (reason) addLog(reason);
  syncLoadHint();
  syncLoadedSourceUI();
}

function configDisplayName(record) {
  const base = record?.display_name || record?.name || record?.config_id || '';
  const universeMode = record?.universe_mode || record?.config_json?.universe_mode || '';
  if (!base) return universeMode ? `Universe=${universeMode}` : '';
  if (!universeMode || base.includes(`Universe=${universeMode}`)) return base;
  return universeMode ? `${base} | Universe=${universeMode}` : base;
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
  if (String(kind || '').trim().toLowerCase() === 'experiment') return `Experiment ${normalizedId}`;
  if (String(kind || '').trim().toLowerCase() === 'baseline') return `Baseline ${normalizedId}`;
  if (String(kind || '').trim().toLowerCase() === 'config') return `Config ${normalizedId}`;
  return `Source ${normalizedId}`;
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
  if (item?.kind === 'config') return 'Config';
  return item?.kind === 'baseline' ? 'Baseline' : 'Experiment';
}

function loadItemBadgeClass(item) {
  if (item?.kind === 'config') return 'wb-load-kind-config';
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

function currentWorkbenchInputSourceFromUrl() {
  try {
    const params = new URLSearchParams(window.location.search || '');
    const loadId = String(params.get('load_id') || '').trim();
    const loadKind = String(params.get('load_kind') || '').trim().toLowerCase();
    if (loadId) {
      if (loadKind === 'config') return { kind: 'config', id: loadId };
      return { kind: loadKind === 'experiment' ? 'experiment' : 'baseline', id: loadId };
    }
  } catch (_) {
    return null;
  }
  return null;
}

function syncWorkbenchLoadedSourceToUrl(kind, sourceId) {
  try {
    const url = new URL(window.location.href);
    const normalizedId = String(sourceId || '').trim();
    const normalizedKind = String(kind || '').trim().toLowerCase();
    url.searchParams.delete('exp_id');
    if (normalizedId) {
      const persistedKind = normalizedKind === 'experiment'
        ? 'experiment'
        : (normalizedKind === 'config' ? 'config' : 'baseline');
      url.searchParams.set('load_kind', persistedKind);
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

async function resolveBootstrapSource(source) {
  const normalizedKind = String(source?.kind || '').trim().toLowerCase();
  const normalizedId = String(source?.id || '').trim();
  if (!normalizedId) return null;
  try {
    if (normalizedKind === 'config') {
      const payload = await apiRequestJson(
        `bootstrap_config_${normalizedId}`,
        `/api/backtest_v2/configs/${encodeURIComponent(normalizedId)}`,
        { suppressStatusOnError: true },
      );
      if (String(payload?.config_id || '').trim() === normalizedId) return source;
    } else if (normalizedKind === 'experiment') {
      const payload = await apiRequestJson(
        'bootstrap_experiments_index',
        '/api/backtest_v2/experiments',
        { suppressStatusOnError: true },
      );
      const rows = Array.isArray(payload?.items) ? payload.items : (Array.isArray(payload) ? payload : []);
      if (rows.some((item) => String(item?.exp_id || '').trim() === normalizedId)) return source;
    } else {
      const payload = await apiRequestJson(
        'bootstrap_baselines_index',
        '/api/backtest_v2/baselines',
        { suppressStatusOnError: true },
      );
      const rows = Array.isArray(payload?.items) ? payload.items : (Array.isArray(payload) ? payload : []);
      if (rows.some((item) => String(item?.baseline_id || '').trim() === normalizedId)) return source;
    }
  } catch (_) {
    return source;
  }
  if (String(FALLBACK_BOOTSTRAP_SOURCE?.id || '').trim() && normalizedId !== String(FALLBACK_BOOTSTRAP_SOURCE.id || '').trim()) {
    return FALLBACK_BOOTSTRAP_SOURCE;
  }
  if (String(DEFAULT_BOOTSTRAP_BASELINE_ID || '').trim()) {
    return { kind: 'baseline', id: DEFAULT_BOOTSTRAP_BASELINE_ID, label: `Baseline ${DEFAULT_BOOTSTRAP_BASELINE_ID}` };
  }
  return source;
}

async function bootstrapInitialExperiment() {
  const explicitSource = currentWorkbenchInputSourceFromUrl();
  const source = await resolveBootstrapSource(explicitSource || DEFAULT_BOOTSTRAP_SOURCE);
  if (!source?.id || currentRuntimeSourceRef().id || state.loaded_source_id) return;
  try {
    if (source.kind === 'config') await loadConfig(source.id);
    else if (source.kind === 'experiment') await loadExperimentBundle(source.id);
    else await loadBaselineToWorkbench(source.id, { loadLinkedResult: !!explicitSource });
  } catch (e) {
    addLog(`Load source failed: ${source?.id || '-'} | ${e?.message || e}`);
    const fallback = FALLBACK_BOOTSTRAP_SOURCE;
    const shouldFallback = !!fallback?.id
      && String(source?.id || '').trim() !== String(fallback.id || '').trim();
    if (!shouldFallback) return;
    try {
      addLog(`Fallback to preserved source: ${fallback.id}`);
      if (fallback.kind === 'experiment') await loadExperimentBundle(fallback.id);
      else await loadBaselineToWorkbench(fallback.id, { loadLinkedResult: true });
    } catch (fallbackError) {
      addLog(`Fallback source failed: ${fallback?.id || '-'} | ${fallbackError?.message || fallbackError}`);
    }
  }
}

/* Main tab switch */

function syncLoadHint(expId = '') {
  const hint = byId('wbLoadHint');
  if (!hint) return;
  const runtimeSource = currentRuntimeSourceRef();
  const activeId = String(expId || runtimeSource.id || state.loaded_source_id || '').trim();
  const activeKind = String(
    (expId ? 'experiment' : '')
    || runtimeSource.kind
      || state.loaded_source_kind
    || ''
  ).trim().toLowerCase();
  if (activeId) {
    hint.textContent = compactLoadedSourceLabel(activeKind, activeId);
    hint.title = activeKind === 'experiment'
      ? `Current page result source: ${activeId}`
      : (activeKind === 'config'
        ? `Current page config source: ${activeId}`
        : (activeKind === 'baseline' ? `Current page baseline source: ${activeId}` : `Current page source: ${activeId}`));
    return;
  }
  hint.textContent = DEFAULT_BOOTSTRAP_SOURCE.label || `Baseline ${DEFAULT_BOOTSTRAP_BASELINE_ID}`;
  hint.title = 'Click load to import a baseline or experiment. Without a loaded source, the page uses the current draft.';
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
  if (Number.isFinite(Number(item?.max_drawdown))) parts.push(`MaxDD ${pct(item.max_drawdown)}`);
  const yearLabel = loadItemYearLabel(item);
  if (yearLabel) parts.push(yearLabel);
  if (item?.universe_mode) parts.push(item.universe_mode);
  const membershipLabel = membershipModeDisplayLabel(item?.universe_mode, item?.membership_mode);
  if (membershipLabel) parts.push(membershipLabel);
  if (!parts.length && item?.kind === 'baseline') {
    parts.push(item?.has_result ? 'Has result' : 'Config only');
  }
  if (!parts.length && item?.kind === 'experiment' && Number.isFinite(Number(item?.trades))) {
    parts.push(`Trades ${fmtInt(item.trades)}`);
  }
  return parts.join(' | ') || 'Pending result';
}

async function fetchExperimentLoadMetrics(expId) {
  const normalizedExpId = String(expId || '').trim();
  if (!normalizedExpId) return {};
  const experiments = await apiRequestJson('experiments', '/api/backtest_v2/experiments');
  const row = (Array.isArray(experiments) ? experiments : []).find((item) => String(item?.exp_id || '').trim() === normalizedExpId) || {};
  const perf = row?.perf || {};
  return {
    cagr: perf?.cagr,
    max_drawdown: perf?.max_drawdown,
    universe_mode: String(row?.universe_mode || '').trim(),
    membership_mode: String(row?.membership_mode || '').trim(),
    start_year: Number.isFinite(Number(row?.start_year)) ? Number(row.start_year) : null,
    end_year: Number.isFinite(Number(row?.end_year)) ? Number(row.end_year) : null,
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


function switchMainTab(tab) {
  const next = tab || 'overview';
  state.main_tab = next;
  document.querySelectorAll('.wb-main-tabs button[data-main-tab]').forEach((b) => b.classList.toggle('active', b.getAttribute('data-main-tab') === next));
  document.querySelectorAll('.wb-main-panel').forEach((p) => p.classList.remove('active'));
  const panel = byId(next === 'overview' ? 'wbTabOverview' : 'wbTabAnalysis');
  if (panel) panel.classList.add('active');
}

/* Wrapper functions that delegate into page modules */

function renderRightInspector() {
  syncResultsWorkbenchSurface();
}


function bindEvents() {
  document.querySelectorAll('#wbMode button').forEach((btn) => btn.addEventListener('click', () => setMode(btn.getAttribute('data-mode') || 'experiment')));
  document.querySelectorAll('[data-open-panel]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const panel = String(btn.getAttribute('data-open-panel') || '').trim();
      if (!panel || typeof setDrawerPanel !== 'function') return;
      toggleDrawer(false);
      setDrawerPanel(panel);
    });
  });
  document.querySelectorAll('#wbAssetScopeGroup button').forEach((btn) => {
    btn.addEventListener('click', () => {
      const val = btn.getAttribute('data-val');
      if (!val) return;
      document.querySelectorAll('#wbAssetScopeGroup button').forEach((button) => button.classList.remove('active'));
      btn.classList.add('active');
      const selectEl = byId('wbAssetScope');
      if (selectEl) selectEl.value = val;
      updateUniverseInputVisibility();
      buildConfigDraft();
      renderRunHints();
    });
  });
  byId('wbAssetScope')?.addEventListener('change', () => {
    const value = byId('wbAssetScope')?.value || DEFAULT_ASSET_SCOPE;
    document.querySelectorAll('#wbAssetScopeGroup button').forEach((button) => {
      button.classList.toggle('active', button.getAttribute('data-val') === value);
    });
    updateUniverseInputVisibility();
    buildConfigDraft();
    renderRunHints();
  });
  // Universe mode buttons keep the hidden select in sync
  document.querySelectorAll('#wbUniverseModeGroup button').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (btn.disabled) return;
      const val = btn.getAttribute('data-val');
      if (!val) return;
      // Toggle active style
      document.querySelectorAll('#wbUniverseModeGroup button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      // Sync hidden select
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
  document.querySelectorAll('#wbEtfPresetWrap button[data-preset]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const preset = String(btn.getAttribute('data-preset') || '').trim();
      const symbolsValue = String(btn.getAttribute('data-symbols') || '').trim();
      const assetScopeSelect = byId('wbAssetScope');
      if (assetScopeSelect) assetScopeSelect.value = 'cn_etf';
      document.querySelectorAll('#wbAssetScopeGroup button').forEach((button) => {
        button.classList.toggle('active', button.getAttribute('data-val') === 'cn_etf');
      });
      const presetInput = byId('wbEtfPreset');
      if (presetInput) presetInput.value = preset;
      const symbolsInput = byId('wbSymbols');
      if (symbolsInput) symbolsInput.value = symbolsValue;
      document.querySelectorAll('#wbEtfPresetWrap button[data-preset]').forEach((button) => {
        button.classList.toggle('active', button === btn);
      });
      updateUniverseInputVisibility();
      buildConfigDraft();
      renderRunHints();
    });
  });
  // Price adjustment toggle buttons keep the hidden select in sync
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
  byId('wbRegimeEngine')?.addEventListener('change', () => {
    if (typeof updateRegimeEngineUi === 'function') updateRegimeEngineUi(byId('wbRegimeEngine')?.value || 'ma200_legacy');
    buildConfigDraft();
  });
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
      const statusEl = byId('wbRunStatus');
      if (statusEl) statusEl.textContent = `Run failed: ${msg}`;
      addLog(String(e));
      setStatusItems([{ title: 'Run failed', message: msg, detail: String(e) }]);
    }
  });
  byId('wbPresetSelect')?.addEventListener('change', () => { syncPresetHint(); });
  byId('wbRunPreset')?.addEventListener('click', async () => {
    try { setStatusItems([]); await runExperiment(); } catch (e) {
      const msg = e.message || String(e);
      const statusEl = byId('wbRunStatus');
      if (statusEl) statusEl.textContent = `Preset run failed: ${msg}`;
      addLog(String(e));
      setStatusItems([{ title: 'Preset run failed', message: msg, detail: String(e) }]);
    }
  });
  byId('wbSaveBaseline')?.addEventListener('click', async () => {
    try {
      await saveCurrentBaseline();
    } catch (e) {
        addLog(`Save baseline failed: ${e?.message || e}`);
    }
  });

  byId('wbSaveConfig')?.addEventListener('click', async () => { try { await saveConfig('draft'); } catch (e) { addLog(`Save config failed: ${e.message || e}`); } });
  byId('wbSaveTemplate')?.addEventListener('click', async () => { try { await saveConfig('template'); } catch (e) { addLog(`Save template failed: ${e.message || e}`); } });
  byId('wbSaveFlowScript')?.addEventListener('click', async () => { try { await saveConfig('flow_script'); } catch (e) { addLog(`Save flow script failed: ${e.message || e}`); } });
  byId('wbCopyCfgJson')?.addEventListener('click', copyConfigJson);
  byId('wbPasteCfgJson')?.addEventListener('click', pasteConfigJson);
  byId('wbDiffCfg')?.addEventListener('click', renderConfigDiff);
  byId('wbApplyGroup')?.addEventListener('click', async () => {
    const cfg = state.active_artifacts?.config;
    if (!cfg) { addLog('Current result is missing config.json'); return; }
    const draft = cfg?.overrides?.workbench_config || cfg?.workbench_config || cfg;
    applyConfigToUI(draft || {});
    clearLoadedSource();
    addLog(`Applied result config back into draft: exp_id=${state.active_result?.exp_id || '-'}`);
  });

  document.querySelectorAll('.wb-main-tabs button[data-main-tab]').forEach((btn) => btn.addEventListener('click', () => switchMainTab(btn.getAttribute('data-main-tab') || 'overview')));
  document.querySelectorAll('.wb-analysis-tabs button[data-dock], .wb-dock-tabs button[data-dock]').forEach((btn) => {
    btn.addEventListener('click', () => switchDockTab(btn.getAttribute('data-dock') || 'explain'));
  });
  byId('wbPreviewExec')?.addEventListener('click', async () => { try { await previewExecution(); } catch (e) { addLog(`Execution preview failed: ${e.message || e}`); } });
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
    addLog(state.drawer_pinned ? 'Drawer pinned' : 'Drawer unpinned');
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
    if (!confirm('Clear all experiments? This cannot be undone.')) return;
    try {
      await apiRequestJson('clearExperiments', '/api/backtest_v2/experiments', { method: 'DELETE' });
      addLog('All experiments cleared');
      renderHistoryPanel([]);
    } catch (e) {
      addLog(`Clear failed: ${e?.message || e}`);
    }
  });
  byId('wbHistoryCompare')?.addEventListener('click', async () => {
    try {
      await openExperimentCompare();
    } catch (e) {
      addLog(`Open experiment compare failed: ${e?.message || e}`);
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

  // Exit checkbox/input linkage
  byId('wbExitTrail')?.addEventListener('change', syncExitLinkage);
  byId('wbExitTime')?.addEventListener('change', syncExitLinkage);

  // Update ATR hint when price adjustment or match price changes
  byId('wbPriceAdj')?.addEventListener('change', updateAtrNote);
  byId('wbMatchPrice')?.addEventListener('change', updateAtrNote);

// Public surface keeps one unified load entry for config / baseline / experiment.
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
        addLog(`Open experiment load menu failed: ${e?.message || e}`);
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
  syncAssetAwareShell();
  updateUniverseInputVisibility();
  if (typeof updateRegimeEngineUi === 'function') updateRegimeEngineUi();
  renderRunHints();
  buildConfigDraft();
  syncExitLinkage();
  updateAtrNote();
  syncPresetHint();
  syncLoadHint();
  if (typeof renderMarketDataSyncStatus === 'function') {
    renderMarketDataSyncStatus({ status: 'running', message: '正在读取市场数据同步状态' });
  }
  setStatusItems([]);
  renderRightInspector();
  if (typeof refreshMarketDataSyncStatus === 'function') {
    refreshMarketDataSyncStatus().catch((e) => { addLog(`Market data sync status bootstrap failed: ${e?.message || e}`); });
    if (!window.__wbMarketDataSyncPoller) {
      window.__wbMarketDataSyncPoller = window.setInterval(() => {
        refreshMarketDataSyncStatus().catch((e) => { addLog(`Market data sync status refresh failed: ${e?.message || e}`); });
      }, 300000);
    }
  }
  bootstrapInitialExperiment().catch((e) => { addLog(`Default experiment bootstrap failed: ${e?.message || e}`); });
  addLog('Strategy Workbench ready');
}

// Desktop experiment history panel is provided by desktop-history-panel.js.




