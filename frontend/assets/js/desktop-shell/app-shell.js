/* desktop-shell/app-shell.js: formal desktop page shell owner for init, navigation, and UI bridge wiring. */
(function initDesktopAppShellModule(globalScope) {
  const DEFAULT_BOOTSTRAP_BASELINE_ID = 'CN_STOCK_ETF_FORMAL_V1';
  const MAX_FRONTEND_EXPERIMENT_LOAD_ITEMS = 12;
  const DEFAULT_BOOTSTRAP_SOURCE = {
    kind: 'baseline',
    id: DEFAULT_BOOTSTRAP_BASELINE_ID,
    label: 'Baseline CN_STOCK_ETF_FORMAL_V1',
  };
  const FALLBACK_BOOTSTRAP_SOURCE = {
    kind: 'baseline',
    id: 'baseline_V10_1',
    label: 'baseline_V10.1',
  };

  function setActiveNav() {
    const path = (location.pathname || '/').split('/').pop() || 'index.html';
    document.querySelectorAll('[data-nav]')?.forEach((a) => {
      const href = a.getAttribute('href') || '';
      const key = href.split('/').pop();
      if (key === path) a.classList.add('active');
    });
  }

  async function resolveBootstrapSource(source) {
    const normalizedKind = String(source?.kind || '').trim().toLowerCase();
    const normalizedId = String(source?.id || '').trim();
    if (!normalizedId) return null;
    try {
      if (normalizedKind === 'experiment') {
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
    const source = explicitSource || await resolveBootstrapSource(DEFAULT_BOOTSTRAP_SOURCE);
    if (!source?.id || currentRuntimeSourceRef().id || state.loaded_source_id) return;
    try {
      if (source.kind === 'experiment') await loadExperimentBundle(source.id);
      else await loadBaselineToWorkbench(source.id, { loadLinkedResult: true });
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

  function syncLoadHint() {
    const hint = byId('wbLoadHint');
    if (!hint) return;
    const runtimeSource = currentRuntimeSourceRef();
    const loadedSourceId = String(state.loaded_source_id || '').trim();
    const loadedSourceKind = String(state.loaded_source_kind || '').trim().toLowerCase();
    const runtimeSourceId = String(runtimeSource.id || '').trim();
    const runtimeSourceKind = String(runtimeSource.kind || '').trim().toLowerCase();
    const activeId = loadedSourceId || runtimeSourceId;
    const activeKind = String(
      loadedSourceKind
        || runtimeSourceKind
        || ''
    ).trim().toLowerCase();
    if (activeId) {
      hint.textContent = compactLoadedSourceLabel(activeKind, activeId);
      hint.title = activeKind === 'experiment'
        ? `Current page result source: ${activeId}`
        : (activeKind === 'baseline' ? `Current page baseline source: ${activeId}` : `Current page source: ${activeId}`);
      return;
    }
    hint.textContent = DEFAULT_BOOTSTRAP_SOURCE.label || `Baseline ${DEFAULT_BOOTSTRAP_BASELINE_ID}`;
    hint.title = 'Click load to import a baseline or experiment. Without a loaded source, the page uses the current draft.';
  }

  function setSelectorText(selector, text) {
    const element = document.querySelector(selector);
    if (element) element.textContent = text;
  }

  function setSelectorTitle(selector, text) {
    const element = document.querySelector(selector);
    if (element) element.title = text;
  }

  function setSelectOptionText(selectId, value, text) {
    const option = document.querySelector(`#${selectId} option[value="${value}"]`);
    if (option) option.textContent = text;
  }

  function setToggleLabel(inputId, text) {
    const input = byId(inputId);
    const label = input?.closest('label');
    if (!label) return;
    const textNode = Array.from(label.childNodes || []).find((node) => node.nodeType === 3);
    if (textNode) {
      textNode.textContent = ` ${text}`;
    } else {
      label.appendChild(document.createTextNode(` ${text}`));
    }
  }

  function setFieldLabelByControl(controlId, text) {
    const field = byId(controlId)?.closest('.wb-field');
    const label = field?.querySelector('.wb-field-label');
    if (label) label.textContent = text;
  }

  function setFieldNoteByControl(controlId, text, noteIndex = 0) {
    const field = byId(controlId)?.closest('.wb-field');
    const notes = field?.querySelectorAll('.wb-mini') || [];
    if (notes[noteIndex]) notes[noteIndex].textContent = text;
  }

  function repairStaticShellCopy() {
    document.title = '多资产趋势研究台';

    [
      ['.wb-brand', '多资产趋势研究台'],
      ['#wbMode [data-mode="experiment"]', '实验'],
      ['#wbMode [data-mode="execution"]', '执行'],
      ['#wbMode [data-mode="single"]', '单项'],
      ['#wbRunBtn', '运行'],
      ['#wbQuickLoad', '加载'],
      ['#wbSaveBaseline', '保存基线'],
      ['#wbDataSyncHint', '数据同步：读取中'],
      ['#wbPresetHint', '草稿 | 已加载来源'],
      ['#wbInputSourceChip', '草稿'],
      ['#wbGlobalControlStrip .wb-global-card-primary .wb-global-eyebrow', '公共控制'],
      ['#wbGlobalControlStrip .wb-global-card-primary strong', '资产范围与时间窗口'],
      ['#wbAssetScopeLabel', '资产范围'],
      ['#wbGlobalAssetModeSummary', '资产池摘要'],
      ['#wbGlobalDataWindowSummary', '窗口信息'],
      ['#wbSchemaBadge', '结构正常'],
      ['#wbUniverseModeGroup [data-val="ALL_A"]', '全A'],
      ['#wbUniverseModeGroup [data-val="HS300_ZZ500"]', '沪深300+中证500'],
      ['#wbUniverseModeGroup [data-val="CSI1000"]', '中证1000'],
      ['#wbUniverseModeGroup [data-val="INDUSTRY"]', '自选行业'],
      ['#wbUniverseModeGroup [data-val="CUSTOM"]', '个股'],
      ['#wbSymbolsLabel', '自选代码'],
      ['#wbStockBasicFiltersWrap .wb-field-label', '基础过滤'],
      ['#wbMinListDaysWrap .wb-field-label', '上市天数 >='],
      ['#wbMinTurnoverWrap .wb-field-label', '成交额 >= 20日均额（元）'],
      ['#wbIndustryFilterWrap .wb-field-label', '行业范围'],
      ['#wbPitStatusLabel', 'PIT 状态'],
      ['#wbPitStatus', 'PIT 启用'],
      ['#wbMktCapWrap .wb-field-label', '市值范围（亿元）'],
      ['#wbAdjGroup', ''],
      ['#wbBenchmarkLabel', '基准'],
      ['#wbGlobalRegimeCard .wb-global-eyebrow', '公共控制'],
      ['#wbGlobalGovernorCard .wb-global-eyebrow', '公共控制'],
      ['#wbGlobalRegimeCard .wb-cmd-btn', '编辑'],
      ['#wbGlobalGovernorCard .wb-cmd-btn', '编辑'],
      ['#wbGlobalRegimeSummaryPrimary', '基础状态 / 生效状态'],
      ['#wbGlobalRegimeSummarySecondary', '预算倍率'],
      ['#wbGlobalGovernorSummaryPrimary', '预算上限 / 暴露上限'],
      ['#wbGlobalGovernorSummarySecondary', '预算原因'],
      ['section[data-module="s2"] summary', '高级环境参数'],
      ['section[data-module="s3"] summary', '行业门控'],
      ['section[data-module="s4"] summary', '入场信号与组合'],
      ['section[data-module="s6"] summary', '建仓与组合约束'],
      ['section[data-module="s7"] summary', '高级预算参数'],
      ['section[data-module="s8"] summary', '风险保护'],
      ['section[data-module="s9"] summary', '退出规则'],
      ['section[data-module="json"] details:first-of-type summary', '配置草稿'],
      ['section[data-module="json"] details:last-of-type summary', '校验与差异'],
      ['section[data-module="history"] strong', '实验历史'],
      ['#wbHistoryClear', '清空'],
      ['#wbStatusPanel strong', '状态中心'],
    ].forEach(([selector, text]) => {
      if (!text && selector === '#wbAdjGroup') return;
      setSelectorText(selector, text);
    });

    setSelectorTitle('#wbDataSyncHint', '读取市场数据同步状态');
    setSelectorTitle('#wbStatusBell', '查看运行状态');
    setSelectorTitle('#wbDrawerPin', '固定抽屉');
    setSelectorTitle('#wbDrawerToggle', '收起抽屉 (Ctrl+B)');
    setSelectorTitle('.wb-rail-btn[data-panel="json"]', '配置 JSON');
    setSelectorTitle('.wb-rail-btn[data-panel="history"]', '实验历史');
    setSelectorTitle('#wbStatusClose', '关闭');

    setSelectorText('.wb-rail-btn[data-panel="json"] .wb-rail-label', '配置');
    setSelectorText('.wb-rail-btn[data-panel="history"] .wb-rail-label', '历史');

    setSelectorText('#wbGlobalRegimeCard summary', '查看 Regime 详情');
    setSelectorText('#wbGlobalGovernorCard summary', '查看 Governor 详情');
    setSelectorText('#wbGlobalRegimeEmpty', '当前结果未提供 formal regime 数据');
    setSelectorText('#wbGlobalGovernorEmpty', '当前结果未提供 governed snapshot');

    [
      ['#wbAssetScopeGroup [data-val="cn_a_equity"]', 'A股个股'],
      ['#wbAssetScopeGroup [data-val="cn_etf"]', 'A股ETF'],
      ['#wbAssetScopeGroup [data-val="us_equity"]', '美股入口'],
    ].forEach(([selector, text]) => setSelectorText(selector, text));
    setSelectOptionText('wbAssetScope', 'cn_a_equity', 'A股个股');
    setSelectOptionText('wbAssetScope', 'cn_etf', 'A股ETF');
    setSelectOptionText('wbAssetScope', 'us_equity', '美股入口');

    setSelectorText('#wbGlobalControlStrip .wb-global-date-range .wb-field-label', '时间范围');
    setSelectorText('#wbGlobalControlStrip .wb-note', '至');

    const presetSelect = byId('wbPresetSelect');
    if (presetSelect) {
      presetSelect.title = '运行候选入口';
      if (presetSelect.options[0]) presetSelect.options[0].textContent = '草稿入口';
      if (presetSelect.options[1]) presetSelect.options[1].textContent = '候选：BR35 + ATR1.0';
      if (presetSelect.options[2]) presetSelect.options[2].textContent = '候选：ATR 1.0';
    }

    const symbolsInput = byId('wbSymbols');
    if (symbolsInput) symbolsInput.placeholder = '逗号分隔，例如 600000.SH,000001.SZ';
    const industryFilterList = byId('wbIndustryFilterList');
    if (industryFilterList) industryFilterList.placeholder = '留空表示不设置，多个用逗号';
    ['wbMktCapMin', 'wbMktCapMax', 'wbAtrMin', 'wbAtrMax'].forEach((id) => {
      const input = byId(id);
      if (input) input.placeholder = '留空表示不限';
    });

    setSelectorText('#wbIndustryPickerWrap .wb-field-label', '行业选择');
    setSelectorText('#wbEtfPresetWrap [data-preset="cn_etf_single_asset_template"]', '单标的 512100');
    setSelectorText('#wbEtfPresetWrap [data-preset="cn_etf_first_wave_core"]', 'Core 6');
    setSelectorText('#wbEtfPresetWrap [data-preset="cn_etf_first_wave_all"]', 'All 9');
    setToggleLabel('wbExcludeSt', 'ST过滤');
    setToggleLabel('wbExcludeSuspended', '停牌过滤');
    setToggleLabel('wbExcludeStarMarket', '科创板过滤');

    const industryFilterMode = byId('wbIndustryFilterMode');
    if (industryFilterMode) {
      if (industryFilterMode.options[0]) industryFilterMode.options[0].textContent = '不限';
      if (industryFilterMode.options[1]) industryFilterMode.options[1].textContent = '包含';
      if (industryFilterMode.options[2]) industryFilterMode.options[2].textContent = '排除';
    }

    setSelectorText('#wbAdjGroup [data-val="qfq"]', '前复权');
    setSelectorText('#wbAdjGroup [data-val="hfq"]', '后复权');
    setSelectorText('#wbAdjGroup [data-val="none"]', '不复权');
    setSelectOptionText('wbPriceAdj', 'qfq', '前复权');
    setSelectOptionText('wbPriceAdj', 'hfq', '后复权');
    setSelectOptionText('wbPriceAdj', 'none', '不复权');
    setSelectorText('#wbMatchGroup [data-val="next_open"]', '次日开盘');
    setSelectorText('#wbMatchGroup [data-val="close"]', '当日收盘');
    setSelectOptionText('wbMatchPrice', 'next_open', '次日开盘');
    setSelectOptionText('wbMatchPrice', 'close', '当日收盘');
    setSelectorText('#wbMatchGroup.closest .wb-mini', '');

    setSelectorText('#wbLimitTradeGroup [data-val="forbid"]', '禁止');
    setSelectorText('#wbLimitTradeGroup [data-val="allow"]', '允许');
    setSelectOptionText('wbLimitTrade', 'forbid', '禁止');
    setSelectOptionText('wbLimitTrade', 'allow', '允许');
    const limitRule = byId('wbLimitRule');
    if (limitRule) {
      if (limitRule.options[0]) limitRule.options[0].textContent = '不可成交则跳过（推荐）';
      if (limitRule.options[1]) limitRule.options[1].textContent = '忽略';
      if (limitRule.options[2]) limitRule.options[2].textContent = '涨停不可买入';
      if (limitRule.options[3]) limitRule.options[3].textContent = '跌停不可卖出';
    }

    setSelectorText('#wbConstituentWrap .wb-field-label', '成分口径');
    setSelectorText('#wbConstituentGroup [data-val="dynamic"]', '历史动态');
    setSelectorText('#wbConstituentGroup [data-val="fixed"]', '起始日快照');
    setSelectOptionText('wbConstituent', 'dynamic', '历史动态');
    setSelectOptionText('wbConstituent', 'fixed', '起始日快照');

    setSelectorText('#wbIndustrySystemWrap .wb-field-label', '行业体系');
    setSelectorText('#wbIndustrySystemWrap .wb-chip', 'PIT 启用');
    setSelectOptionText('wbIndustrySystem', 'sw_l1', '申万一级');

    setFieldLabelByControl('wbAtrMin', '波动过滤（ATR%）');
    setFieldLabelByControl('wbPriceAdj', '价格口径');
    setFieldLabelByControl('wbMatchPrice', '成交价假设');
    setFieldLabelByControl('wbLimitTrade', '涨跌停成交');
    setFieldLabelByControl('wbLimitRule', '涨跌停规则');
    setFieldLabelByControl('wbConstituent', '成分口径');
    setFieldLabelByControl('wbIndustrySystem', '行业体系');
    setFieldLabelByControl('wbPriceMin', '价格范围');

    setFieldNoteByControl('wbMatchPrice', '主实验执行层当前固定使用“次日开盘”。');
    setFieldNoteByControl('wbLimitTrade', '默认禁止在涨跌停无法成交时强行成交。');
    setFieldNoteByControl('wbConstituent', '当前已接通成分时点控制，仅对宽基指数池生效。');
    setFieldNoteByControl('wbIndustrySystem', '当前固定使用 pit_industry_history.industry_l1。');
    setFieldNoteByControl('wbPriceMin', '主实验执行层当前只消费 min_price；max_price 仅保留在草稿展示与报告口径中。');
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
    return [...baselineRows, ...experimentRows.slice(0, MAX_FRONTEND_EXPERIMENT_LOAD_ITEMS)];
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
      parts.push(item?.has_result ? 'Has result' : 'No linked result');
    }
    if (!parts.length && item?.kind === 'experiment' && Number.isFinite(Number(item?.trades))) {
      parts.push(`Trades ${fmtInt(item.trades)}`);
    }
    return parts.join(' | ') || 'Pending result';
  }

  function switchMainTab(tab) {
    const next = tab || 'overview';
    state.main_tab = next;
    document.querySelectorAll('.wb-main-tabs button[data-main-tab]').forEach((button) => button.classList.toggle('active', button.getAttribute('data-main-tab') === next));
    document.querySelectorAll('.wb-main-panel').forEach((panel) => panel.classList.remove('active'));
    const panel = byId(next === 'overview' ? 'wbTabOverview' : 'wbTabAnalysis');
    if (panel) panel.classList.add('active');
  }

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
    document.querySelectorAll('#wbUniverseModeGroup button').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (btn.disabled) return;
        const val = btn.getAttribute('data-val');
        if (!val) return;
        document.querySelectorAll('#wbUniverseModeGroup button').forEach((button) => button.classList.remove('active'));
        btn.classList.add('active');
        const selectEl = byId('wbUniverseMode');
        if (selectEl) selectEl.value = val;
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
          const selectEl = byId('wbConstituent');
          if (selectEl) selectEl.value = val;
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
    document.querySelectorAll('#wbAdjGroup button').forEach((btn) => {
      btn.addEventListener('click', () => {
        const val = btn.getAttribute('data-val');
        if (!val) return;
        document.querySelectorAll('#wbAdjGroup button').forEach((button) => button.classList.remove('active'));
        btn.classList.add('active');
        const selectEl = byId('wbPriceAdj');
        if (selectEl) selectEl.value = val;
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
    byId('wbExitTrail')?.addEventListener('change', syncExitLinkage);
    byId('wbExitTime')?.addEventListener('change', syncExitLinkage);
    byId('wbPriceAdj')?.addEventListener('change', updateAtrNote);
    byId('wbMatchPrice')?.addEventListener('change', updateAtrNote);

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

  function initDesktopAppShell() {
    repairStaticShellCopy();
    setActiveNav();
    hydrateComposeRows((window.multiAlphaUi?.defaultComposeRows && window.multiAlphaUi.defaultComposeRows()) || []);
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
      if (!globalScope.__wbMarketDataSyncPoller) {
        globalScope.__wbMarketDataSyncPoller = globalScope.setInterval(() => {
          refreshMarketDataSyncStatus().catch((e) => { addLog(`Market data sync status refresh failed: ${e?.message || e}`); });
        }, 300000);
      }
    }
    bootstrapInitialExperiment().catch((e) => { addLog(`Default experiment bootstrap failed: ${e?.message || e}`); });
    addLog('Strategy Workbench ready');
  }

  const exportScope = typeof globalThis === 'object' && globalThis ? globalThis : globalScope;
  const expose = (name, value) => {
    globalScope[name] = value;
    if (exportScope && exportScope !== globalScope) exportScope[name] = value;
  };

  expose('setActiveNav', setActiveNav);
  expose('resolveBootstrapSource', resolveBootstrapSource);
  expose('bootstrapInitialExperiment', bootstrapInitialExperiment);
  expose('syncLoadHint', syncLoadHint);
  expose('normalizeLoadItems', normalizeLoadItems);
  expose('experimentLoadSummary', experimentLoadSummary);
  expose('switchMainTab', switchMainTab);
  expose('renderRightInspector', renderRightInspector);
  expose('bindDesktopAppShellEvents', bindEvents);
  expose('initDesktopAppShell', initDesktopAppShell);
  expose('init', initDesktopAppShell);
})(window);
