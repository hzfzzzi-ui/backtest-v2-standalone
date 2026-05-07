/* desktop-shell/runtime-surface.js: formal shared runtime surface for desktop shell modules. */
const state = (window.state && typeof window.state === 'object')
  ? window.state
  : (
    (window.__WB_STATE__ && typeof window.__WB_STATE__ === 'object')
      ? window.__WB_STATE__
      : {
        ...((window.createWorkbenchConfigDraftState && window.createWorkbenchConfigDraftState()) || {}),
        ...((window.createRunSessionState && window.createRunSessionState()) || {}),
        ...((window.createActiveExperimentState && window.createActiveExperimentState()) || {}),
        ...((window.createViewState && window.createViewState()) || {}),
        ...((window.createDesktopAppShellState && window.createDesktopAppShellState()) || {}),
      }
  );
window.__WB_STATE__ = state;
window.state = state;

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

function assetScopeDisplayName(scope = null) {
  const resolvedScope = resolvePreferredAssetScope(scope);
  if (resolvedScope === 'cn_etf') return 'A股ETF';
  if (resolvedScope === 'us_equity') return '美股';
  return 'A股个股';
}

function currentComboRuntimeMeta() {
  return state?.active_artifacts?.run_meta && typeof state.active_artifacts.run_meta === 'object'
    ? state.active_artifacts.run_meta
    : {};
}

function comboRuntimeState(runMeta = null) {
  const meta = runMeta && typeof runMeta === 'object' ? runMeta : currentComboRuntimeMeta();
  const data = meta?.data && typeof meta.data === 'object' ? meta.data : {};
  const comboRuntime = meta?.combo_runtime && typeof meta.combo_runtime === 'object' ? meta.combo_runtime : {};
  const comboResult = meta?.combo_result && typeof meta.combo_result === 'object' ? meta.combo_result : {};
  const researchCombo = meta?.research_combo && typeof meta.research_combo === 'object' ? meta.research_combo : {};
  const comboContext = meta?.combo_context && typeof meta.combo_context === 'object' ? meta.combo_context : {};
  const provenance = meta?.provenance && typeof meta.provenance === 'object' ? meta.provenance : {};
  const executionContract = meta?.execution_contract && typeof meta.execution_contract === 'object'
    ? meta.execution_contract
    : {};
  const executionContractRef = meta?.execution_contract_ref && typeof meta.execution_contract_ref === 'object'
    ? meta.execution_contract_ref
    : {};
  const componentSourceContract = provenance.component_source_contract && typeof provenance.component_source_contract === 'object'
    ? provenance.component_source_contract
    : {};
  const assetRole = String(data.asset_role || '').trim().toLowerCase();
  const systemAssetScope = String(data.system_asset_scope || '').trim().toLowerCase();
  const comboSourceMode = (
    Object.keys(executionContractRef).length || Object.keys(executionContract).length
      ? 'execution_contract'
      : (Object.keys(componentSourceContract).length ? 'provenance' : '')
  );
  const researchComboOnly = Boolean(
    comboResult.research_combo_only
    || researchCombo.research_combo_only
    || comboRuntime.research_combo_only
  );
  const isComboRuntime = assetRole === 'research_combo'
    || assetRole === 'unified_multi_sleeve_combo'
    || systemAssetScope === 'cn_a_multi_sleeve'
    || Boolean(comboResult.type)
    || Boolean(researchCombo.mode);
  return {
    assetRole,
    systemAssetScope,
    comboSourceMode,
    researchComboOnly,
    isComboRuntime,
    isResearchLikeCombo: isComboRuntime && researchComboOnly,
  };
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

function getDesktopConfigWorkspaceStageCatalog() {
  const shellState = state?.desktop_shell && typeof state.desktop_shell === 'object'
    ? state.desktop_shell
    : null;
  const workspace = shellState?.config_workspace && typeof shellState.config_workspace === 'object'
    ? shellState.config_workspace
    : null;
  if (Array.isArray(workspace?.stage_catalog) && workspace.stage_catalog.length) {
    return workspace.stage_catalog;
  }
  if (typeof window.desktopAppShell?.getConfigWorkspaceStageCatalog === 'function') {
    const catalog = window.desktopAppShell.getConfigWorkspaceStageCatalog();
    if (Array.isArray(catalog) && catalog.length) return catalog;
  }
  return [];
}

function catalogToPanelMeta(catalog) {
  const meta = {};
  (Array.isArray(catalog) ? catalog : []).forEach((item) => {
    const panel = String(item?.panel || '').trim().toLowerCase();
    if (!panel) return;
    meta[panel] = {
      label: String(item?.label || '').trim() || panel.toUpperCase(),
      title: String(item?.title || '').trim() || String(item?.label || panel.toUpperCase()),
      hidden: !!item?.hidden,
    };
  });
  return meta;
}

function resolveAssetScopedPanelMeta(scope = null) {
  const resolvedScope = resolvePreferredAssetScope(scope);
  const stageCatalog = catalogToPanelMeta(getDesktopConfigWorkspaceStageCatalog());
  if (resolvedScope === 'cn_a_equity' && Object.keys(stageCatalog).length >= 9) {
    return stageCatalog;
  }
  if (resolvedScope === 'cn_etf') {
    return {
      s1: { label: 'ETF池', title: 'ETF 池与基础过滤', hidden: false },
      s2: { label: '环境', title: '高级环境参数', hidden: true },
      s3: { label: '候选', title: 'ETF 候选池', hidden: false },
      s4: { label: '信号', title: 'ETF Beta 规则', hidden: false },
      s5: { label: '排序', title: 'ETF 排序与候选保留', hidden: false },
      s6: { label: '建仓', title: '调仓与组合约束', hidden: false },
      s7: { label: '预算', title: '高级预算参数', hidden: true },
      s8: { label: '风险', title: '风险保护', hidden: false },
      s9: { label: '退出', title: '退出规则', hidden: false },
    };
  }
  if (resolvedScope === 'us_equity') {
    return {
      s1: { label: '入口', title: '美股入口', hidden: false },
      s2: { label: '环境', title: '高级环境参数', hidden: true },
      s3: { label: '预留', title: '预留', hidden: true },
      s4: { label: '预留', title: '预留', hidden: true },
      s5: { label: '预留', title: '预留', hidden: true },
      s6: { label: '预留', title: '预留', hidden: true },
      s7: { label: '预算', title: '高级预算参数', hidden: true },
      s8: { label: '预留', title: '预留', hidden: true },
      s9: { label: '预留', title: '预留', hidden: true },
    };
  }
  return {
    s1: { label: '资产池', title: '资产池与基础过滤', hidden: false },
    s2: { label: '环境', title: '高级环境参数', hidden: true },
    s3: { label: '行业', title: '行业门控', hidden: true },
    s4: { label: '信号', title: '入场信号与组合', hidden: false },
    s5: { label: '排序', title: '排序与候选保留', hidden: false },
    s6: { label: '建仓', title: '建仓与组合约束', hidden: false },
    s7: { label: '预算', title: '高级预算参数', hidden: true },
    s8: { label: '风险', title: '风险保护', hidden: false },
    s9: { label: '退出', title: '退出规则', hidden: false },
  };
}

function syncAssetScopedRail(scope = null) {
  const resolvedScope = resolvePreferredAssetScope(scope);
  const comboRuntime = comboRuntimeState();
  const panelMeta = resolveAssetScopedPanelMeta(resolvedScope);
  const fallbackPanel = Object.entries(panelMeta).find(([, meta]) => !meta.hidden)?.[0] || 's1';

  Object.entries(panelMeta).forEach(([panel, meta]) => {
    const upperPanel = String(panel || '').toUpperCase();
    const button = byId(`wbStage${upperPanel}Btn`) || document.querySelector(`.wb-rail-btn[data-panel="${panel}"]`);
    const labelEl = byId(`wbStage${upperPanel}Label`) || button?.querySelector?.('.wb-rail-label') || null;
    if (button) {
      button.hidden = !!meta.hidden;
      if (meta.title) {
        button.title = comboRuntime.isComboRuntime
          ? `组合结果页：${meta.title}`
          : meta.title;
      }
    }
    if (labelEl && meta.label) labelEl.textContent = meta.label;
  });

  if (state.drawer_panel && panelMeta[state.drawer_panel]?.hidden && typeof setDrawerPanel === 'function') {
    setDrawerPanel(fallbackPanel);
  }
}

function syncGlobalControlStrip(scope = null) {
  const resolvedScope = resolvePreferredAssetScope(scope);
  const runMeta = currentComboRuntimeMeta();
  const comboRuntime = comboRuntimeState(runMeta);
  const comboTruth = state?.active_artifacts?.comboTruth
    && typeof state.active_artifacts.comboTruth === 'object'
      ? state.active_artifacts.comboTruth
      : null;
  const comboTruthDisplay = comboTruth?.display && typeof comboTruth.display === 'object'
    ? comboTruth.display
    : null;
  const configDraft = state?.config_draft && typeof state.config_draft === 'object'
    ? state.config_draft
    : {};
  const universe = configDraft.universe && typeof configDraft.universe === 'object'
    ? configDraft.universe
    : {};
  const comboMetrics = runMeta?.combo_metrics && typeof runMeta.combo_metrics === 'object'
    ? runMeta.combo_metrics
    : {};
  const accountAllocatorRuntime = runMeta?.account_allocator_runtime
    && typeof runMeta.account_allocator_runtime === 'object'
      ? runMeta.account_allocator_runtime
      : {};
  const comboMode = String(
    accountAllocatorRuntime.runtime_truth_source === 'account_allocator'
      ? 'account_allocator_runtime'
      : (
        runMeta?.combo_runtime?.mode
        || runMeta?.research_combo?.mode
        || runMeta?.combo_result?.mode
        || runMeta?.combo_context?.combo_mode
        || '-'
      ),
  ).trim() || '-';
  const comboWindowStart = String(
    comboMetrics.start
    || runMeta?.data?.coverage_start
    || universe.start
    || '-',
  ).trim() || '-';
  const comboWindowEnd = String(
    comboMetrics.end
    || runMeta?.data?.coverage_end
    || universe.end
    || '-',
  ).trim() || '-';
  const isComboResult = comboRuntime.isComboRuntime;
  const useComboDisplay = isComboResult && Boolean(comboTruthDisplay);
  const isResearchCombo = useComboDisplay;
  const latestRegime = runMeta.regime?.latest_state && typeof runMeta.regime.latest_state === 'object'
    ? runMeta.regime.latest_state
    : {};
  const governedSnapshot = runMeta.governed_snapshot && typeof runMeta.governed_snapshot === 'object'
    ? runMeta.governed_snapshot
    : {};
  const comboRegime = comboTruthDisplay?.regime && typeof comboTruthDisplay.regime === 'object'
    ? comboTruthDisplay.regime
    : {};
  const comboGovernor = comboTruthDisplay?.governor && typeof comboTruthDisplay.governor === 'object'
    ? comboTruthDisplay.governor
    : {};

  const assetModeSummary = isComboResult
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

  setTextById('wbGlobalAssetSummary', isComboResult ? 'A股个股 + A股ETF 组合' : assetScopeDisplayName(resolvedScope));
  setTextById(
    'wbGlobalAssetModeSummary',
    isComboResult
      ? `组合模式：${comboMode}`
      : (resolvedScope === 'cn_etf'
        ? `ETF池：${String(runMeta.universe?.preset_id || configDraft.universe_mode || 'CUSTOM').trim() || 'CUSTOM'}`
        : assetModeSummary),
  );
  setTextById('wbGlobalDataWindowSummary', isComboResult ? `窗口：${comboWindowStart} ~ ${comboWindowEnd}` : timeWindowSummary);
  setTextById('wbGlobalRegimeBase', baseState);
  setTextById('wbGlobalRegimeEffective', effectiveState);
  setTextById('wbGlobalRegimeCoarse', coarseState);
  setTextById('wbGlobalRegimeBudgetMultiplier', budgetMultiplier);
  setTextById('wbGlobalRegimeReason', regimeReason);
  setTextById('wbGlobalRegimeManual', manualOverrideSummary);
  setTextById('wbGlobalRegimeSummaryPrimary', `基础：${baseState} / 生效：${effectiveState}`);
  setTextById('wbGlobalRegimeSummarySecondary', `预算倍率：${budgetMultiplier}`);
  setTextById('wbGlobalGovernorBudget', totalRiskBudget);
  setTextById('wbGlobalGovernorExposure', totalExposureCap);
  setTextById('wbGlobalGovernorSleeve', budgetConsumer);
  setTextById('wbGlobalGovernorDefense', defenseBias != null ? pct(defenseBias) : '-');
  setTextById('wbGlobalGovernorReason', budgetReason);
  setTextById('wbGlobalGovernorSummaryPrimary', `预算：${totalRiskBudget} / 暴露：${totalExposureCap}`);
  setTextById('wbGlobalGovernorSummarySecondary', `消费者：${budgetConsumer}`);

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
  const regimeCard = byId('wbGlobalRegimeCard');
  if (regimeCard) regimeCard.hidden = !!hasRunResult;
  const governorCard = byId('wbGlobalGovernorCard');
  if (governorCard) governorCard.hidden = !!hasRunResult;
}

function syncAssetAwareShell(scope = null) {
  const resolvedScope = resolvePreferredAssetScope(scope);
  const isCn = isCnAAssetScope(resolvedScope);
  const isEtf = isCnEtfAssetScope(resolvedScope);
  const isSupported = isRuntimeSupportedAssetScope(resolvedScope);
  const comboRuntime = comboRuntimeState();
  const etfResearchConfig = state?.config_draft?.governed_a_share?.etf_beta
    || state?.loaded_source_config?.governed_a_share?.etf_beta
    || {};
  const etfResearchLabel = String(
    etfResearchConfig?.template_id
      ? `模板 ${etfResearchConfig.template_id}`
      : (etfResearchConfig?.research_rule_family
        ? `规则 ${etfResearchConfig.research_rule_family}`
        : (etfResearchConfig?.source_entry_type
          ? `入口 ${etfResearchConfig.source_entry_type}`
          : 'ETF 目录研究'))
  ).trim() || 'ETF 目录研究';
  const brandText = isCn
    ? '多资产趋势研究台 | A股个股'
    : (isEtf ? '多资产趋势研究台 | A股ETF' : '多资产趋势研究台 | 美股入口准备中');
  document.title = comboRuntime.isComboRuntime ? '多资产趋势研究台 | A股个股+ETF组合' : brandText;
  const brandEl = document.querySelector('.wb-brand');
  if (brandEl) brandEl.textContent = comboRuntime.isComboRuntime ? '多资产趋势研究台 | A股个股+ETF组合' : brandText;
  document.body.dataset.assetScope = resolvedScope;

  const runBtn = byId('wbRunBtn');
  if (runBtn) {
    runBtn.disabled = !isSupported;
    runBtn.title = isSupported ? '运行当前资产草稿' : '当前仅完成入口边界，尚未支持运行';
  }

  const pitStatus = byId('wbPitStatus');
  if (pitStatus) {
    pitStatus.textContent = isCn ? 'PIT 启用' : (isEtf ? etfResearchLabel : '美股入口准备中');
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

const LOADED_SOURCE_LABELS = { baseline: 'Baseline', search: 'Search', template: 'Template', derived: 'Derived', config: 'Source' };
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
  state.loaded_source_kind = String(
    record?.loaded_kind
    || (String(record?.source_type || '').trim().toLowerCase() === 'experiment' ? 'experiment' : 'baseline'),
  ).trim() || 'baseline';
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
  return item?.kind === 'baseline' ? 'Baseline' : 'Experiment';
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

function currentWorkbenchInputSourceFromUrl() {
  try {
    const params = new URLSearchParams(window.location.search || '');
    const loadId = String(params.get('load_id') || '').trim();
    const loadKind = String(params.get('load_kind') || '').trim().toLowerCase();
    if (loadId) {
      return { kind: loadKind === 'experiment' ? 'experiment' : 'baseline', id: loadId };
    }
    const experimentId = String(
      params.get('exp_id')
      || params.get('experiment_id')
      || '',
    ).trim();
    if (experimentId) return { kind: 'experiment', id: experimentId };
    const baselineId = String(params.get('baseline_id') || '').trim();
    if (baselineId) return { kind: 'baseline', id: baselineId };
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
    url.searchParams.delete('experiment_id');
    url.searchParams.delete('baseline_id');
    if (normalizedId) {
      const persistedKind = normalizedKind === 'experiment' ? 'experiment' : 'baseline';
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



