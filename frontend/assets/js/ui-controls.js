/* ── ui-controls.js ── UI interactions, config building, drawer, dock tabs ── */
/* Globals used: state, byId, esc, num, pct, fmtInt, fmtMoney, setTextById, setHtmlById,
   getStrategySelector, getStrategyPackValue, COMPOSE_MODULES, reasonZh, addLog,
   apiRequestJson, setStatusItems, _apiTag,
   renderPerfPanel, renderNavChartLW, renderDdChartLW,
   loadActiveArtifacts, renderRightInspector, renderArtifacts (from other modules) */

const LOCKED_CANDIDATE_PRESETS = {
  'v2-breakout-atr-stop-k10-candidate': {
    hint: '候选：锁定 baseline，仅覆盖 atr_stop_k=1.0',
    title: '显式 candidate preset；忽略当前草稿参数，仍保持 locked baseline 成本、股票池、成交与评价口径',
  },
  'v2-breakout-br35-atr10-candidate': {
    hint: '候选：锁定 ATR1.0 底座，仅覆盖 breakout_window=35',
    title: '显式 candidate preset；忽略当前草稿参数，保持 ATR1.0 底座、股票池、成本、成交与评价口径不变',
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

function syncPresetHint() {
  const hint = byId('wbConfigCenterHint') || byId('wbPresetHint');
  if (!hint) return;
  const executionMode = state.mode === 'execution';
  const preset = String(state.selected_locked_candidate_preset || '').trim();
  if (executionMode) {
    hint.textContent = preset ? '执行预览不消费锁定候选；将使用当前草稿 / 已加载配置' : '当前：草稿 / 已加载配置';
    hint.title = preset ? 'execution mode 只生成执行预览；locked candidate 仅用于回测运行' : '执行预览与回测运行共用同一 runtime config handoff';
    return;
  }
  const candidateMeta = lockedCandidatePresetMeta(preset);
  if (candidateMeta) {
    hint.textContent = `当前：${candidateMeta.hint}`;
    hint.title = candidateMeta.title;
    return;
  }
  const meta = state.loaded_config_meta;
  const mode = currentConfigSourceMode();
  if (meta?.config_id && mode === 'loaded-clean') {
    const display = meta.display_name || meta.name || meta.config_id;
    hint.textContent = `当前：${display}`;
    hint.title = `配置中心当前已锁定 ${display}；运行与预览共用同一 runtime config json`;
    return;
  }
  if (meta?.config_id && mode === 'loaded-dirty') {
    hint.textContent = `当前：草稿（偏离 ${meta.config_id}）`;
    hint.title = '已加载配置仅保留 provenance；运行与预览将基于当前草稿 runtime config json';
    return;
  }
  hint.textContent = '当前：草稿';
  hint.title = '默认入口按当前草稿运行 / 预览';
}

function setSelectedLockedCandidatePreset(preset) {
  state.selected_locked_candidate_preset = String(preset || '').trim();
  syncPresetHint();
  syncConfigSourceUI();
}

function updateUniverseInputVisibility() {
  const mode = byId('wbUniverseMode')?.value || 'ALL_A';
  const symbolsWrap = byId('wbSymbolsWrap');
  const industryWrap = byId('wbIndustryPickerWrap');
  if (symbolsWrap) symbolsWrap.style.display = mode === 'CUSTOM' ? '' : 'none';
  if (industryWrap) industryWrap.hidden = mode !== 'INDUSTRY';
  if (mode === 'INDUSTRY') loadIndustryPicker();
}

let _industryPickerLoaded = false;
async function loadIndustryPicker() {
  if (_industryPickerLoaded) return;
  const container = byId('wbIndustryPicker');
  if (!container) return;
  try {
    const resp = await fetch('/api/backtest_v2/industries');
    const data = await resp.json();
    const industries = Array.isArray(data.industries) ? data.industries : [];
    if (!industries.length) {
      container.innerHTML = '<span style="color:#888">暂无行业数据，请先运行导入脚本</span>';
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
    container.innerHTML = '<span style="color:#c33">加载行业列表失败</span>';
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
      s1: 'S1 股票池',
      s2: 'S2 大盘环境',
      s3: 'S3 行业趋势',
      s4: 'S4 个股趋势',
      s5: 'S5 个股排序',
      s6: 'S6 入场信号',
      s7: 'S7 组合构建',
      s8: 'S8 风险控制',
      s9: 'S9 退出',
      json: 'JSON',
      history: '实验历史',
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
    sell: 'sell_funnel',
    sell_funnel: 'sell_funnel',
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
  const accordionMap = {
    buy_funnel: 'wbAccBuyFunnel',
    sell_funnel: 'wbAccSellFunnel',
    execution: 'wbAccTrades',
    logs: 'wbAccLogs',
  };
  const accId = accordionMap[next];
  const details = accId ? byId(accId) : null;
  if (details && details.tagName === 'DETAILS') {
    document.querySelectorAll('.wb-result-acc').forEach((node) => {
      if (node !== details) node.open = false;
    });
    details.open = true;
    requestAnimationFrame(() => {
      details.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    return;
  }
  const capFirst = next.charAt(0).toUpperCase() + next.slice(1);
  const panel = byId(`wbDock${capFirst}`);
  if (panel) panel.classList.add('active');
}

function defaultComposeRows() {
  return COMPOSE_MODULES.map((name, idx) => ({
    name,
    enabled: true,
    role: idx < 2 ? 'Hard Gate' : (idx < 4 ? 'Rank' : 'Soft Weight'),
    weight: idx < 2 ? 1 : 0.5,
    priority: idx + 1,
  }));
}

function validateConfigDraft(draft) {
  const errors = [];
  const trend = draft?.signal_generation?.trend || draft?.signal_generation?.sma || {};
  const strategyPack = String(draft?.strategy_pack || draft?.signal_generation?.strategy || '').toUpperCase();
  const regimeOn = !!draft?.signal_generation?.regime_detection?.enabled;
  const fast = Number(trend.fast_ma);
  const slow = Number(trend.slow_ma);
  if (!(Number.isFinite(fast) && Number.isFinite(slow) && fast < slow)) errors.push('fast_ma 必须小于 slow_ma');
  const maxPos = Number(draft?.position_risk?.max_positions);
  if (!(Number.isFinite(maxPos) && maxPos > 0)) errors.push('max_positions 必须 > 0');
  const singlePct = Number(draft?.position_risk?.single_stock_cap) * 100;
  if (!(Number.isFinite(singlePct) && singlePct >= 0 && singlePct <= 100)) errors.push('单票上限% 必须在 0-100');
  const indPct = Number(draft?.position_risk?.industry_cap) * 100;
  if (!(Number.isFinite(indPct) && indPct >= 0 && indPct <= 100)) errors.push('行业上限% 必须在 0-100');
  const entry = Number((draft?.signal_generation?.trend || draft?.signal_generation?.sma || {}).entry_buffer_pct);
  if (!(Number.isFinite(entry) && entry >= 0 && entry <= 5)) errors.push('entry_buffer% 必须在 0-5');
  if (strategyPack === 'RSI_REVERSAL' && !regimeOn) errors.push('RSI_REVERSAL 主策略未接入主实验编译链，当前仅支持作为 Regime Router 的 MR 臂');
  if (regimeOn && !['EMA_CROSS', 'SMA_CROSS'].includes(String(trend.strategy || '').toUpperCase())) {
    errors.push('Regime Router 趋势臂当前只支持 EMA_CROSS / SMA_CROSS');
  }
  return errors;
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
    el.textContent = '当前结果无 config.json，无法对比';
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
  el.textContent = lines.length ? lines.join('\n\n') : '无差异';
}

function refreshConfigPanels() {
  const preview = byId('wbConfigJsonPreview');
  if (preview) preview.textContent = JSON.stringify(state.config_draft || {}, null, 2);
  const errors = validateConfigDraft(state.config_draft || {});
  const badge = byId('wbSchemaBadge');
  if (badge) {
    if (errors.length) {
      badge.className = 'wb-chip wb-danger';
      badge.textContent = `配置错误 ${errors.length}`;
      badge.title = errors.join('\n');
    } else {
      badge.className = 'wb-chip wb-ok';
      badge.textContent = 'Schema OK';
      badge.title = '通过';
    }
  }
  renderConfigDiff();
}

function buildConfigDraft() {
  const loadedBase = cloneJson(state.loaded_config_json) || {};
  const loadedUniverse = loadedBase.universe || {};
  const loadedUniverseFilters = loadedUniverse.filters || {};
  const loadedSignalGeneration = loadedBase.signal_generation || {};
  const loadedExitRules = loadedBase.exit_rules || {};
  const loadedPositionRisk = loadedBase.position_risk || {};
  const loadedRiskBudget = loadedPositionRisk.risk_budget || {};
  const loadedMarketFilter = loadedPositionRisk.market_filter || {};
  const loadedBreadth = loadedPositionRisk.breadth || {};
  const loadedSizing = loadedBase.sizing || {};
  const breadthEnabled = !!byId('wbBreadthEnabled')?.checked;
  const weightMode = byId('wbWeightMode')?.value || loadedSizing.weight_mode || 'equal';
  const minPositions = Number(byId('wbMinPositions')?.value || loadedSizing.min_positions || 10);
  const includeBreadth = !!loadedPositionRisk.breadth || breadthEnabled;
  const includeSizing = !!loadedBase.sizing || weightMode !== 'equal' || minPositions !== 10;
  const compose = [];
  document.querySelectorAll('#wbComposeRows tr').forEach((tr) => {
    compose.push({
      name: tr.getAttribute('data-name') || '',
      enabled: tr.querySelector('[data-k="enabled"]')?.checked || false,
      role: tr.querySelector('[data-k="role"]')?.value || 'Hard Gate',
      weight: Number(tr.querySelector('[data-k="weight"]')?.value || 0),
      priority: Number(tr.querySelector('[data-k="priority"]')?.value || 0),
    });
  });
  const draft = {
    ...loadedBase,
    mode: state.mode,
    strategy_pack: getStrategyPackValue(),
    universe_mode: byId('wbUniverseMode')?.value || 'ALL_A',
    industries: getSelectedIndustries(),
    initial_capital: Number(loadedBase.initial_capital ?? state.config_draft?.initial_capital ?? 100000),
    universe: {
      ...loadedUniverse,
      start: byId('wbStartDate')?.value || '2021-01-01',
      end: byId('wbEndDate')?.value || '2026-02-01',
      benchmark: byId('wbBenchmark')?.value || '000300.SH',
      symbols: (byId('wbSymbols')?.value || '').split(',').map((s) => s.trim()).filter(Boolean),
      limit: Number(byId('wbUniverseLimit')?.value || 1000),
      price_adj: byId('wbPriceAdj')?.value || 'hfq',
      filters: {
        ...loadedUniverseFilters,
        exclude_st: !!byId('wbExcludeSt')?.checked,
        exclude_suspended: !!byId('wbExcludeSuspended')?.checked,
        min_list_days: Number(byId('wbMinListDays')?.value || 120),
        min_avg_turnover_20d: Number(byId('wbMinTurnover')?.value || 1e8),
        price_min: Number(byId('wbPriceMin')?.value || 0),
        price_max: Number(byId('wbPriceMax')?.value || 99999),
        atr_pct_range: byId('wbAtrRange')?.value || '0,100',
        limit_rule: byId('wbLimitRule')?.value || 'ignore',
      },
    },
    signal_generation: {
      ...loadedSignalGeneration,
      enabled: !!byId('wbEnableSignal')?.checked,
      strategy: getStrategyPackValue(),
      regime_detection: {
        enabled: !!byId('wbRegimeEnabled')?.checked,
        regime_ma: Number(byId('wbRegimeMa')?.value || 60),
        regime_filter: {
          enabled: !!byId('wbRegimeFilterEnabled')?.checked,
          regime_threshold: Number(byId('wbRfThreshold')?.value || 0.3),
          alpha_m: Number(byId('wbRfAlpha')?.value || 2.0),
          alpha_sec: Number(byId('wbRfAlpha')?.value || 2.0),
          alpha_i: Number(byId('wbRfAlpha')?.value || 2.0),
        },
      },
      trend: {
        strategy: (byId('wbTrendStrategy')?.value || 'EMA_CROSS').toUpperCase(),
        fast_ma: Number(byId('wbFastMa')?.value || 20),
        slow_ma: Number(byId('wbSlowMa')?.value || 60),
        entry_buffer_pct: Number(byId('wbEntryBuffer')?.value || 1),
      },
      mr: {
        strategy: (byId('wbMrStrategy')?.value || 'RSI_REVERSAL').toUpperCase(),
        rsi_period: Number(byId('wbMrRsiPeriod')?.value || 6),
        rsi_buy_threshold: Number(byId('wbMrRsiBuy')?.value || 20),
        rsi_sell_threshold: Number(byId('wbMrRsiSell')?.value || 80),
        mr_max_hold_days: Number(byId('wbMrMaxHold')?.value || 5),
        mr_stop_loss_pct: Number(byId('wbMrStopLoss')?.value || 3) / 100,
      },
      sma: {
        fast_ma: Number(byId('wbFastMa')?.value || 20),
        slow_ma: Number(byId('wbSlowMa')?.value || 60),
        entry_buffer_pct: Number(byId('wbEntryBuffer')?.value || 1),
      },
      ema: {
        fast_ma: Number(byId('wbFastMa')?.value || 20),
        slow_ma: Number(byId('wbSlowMa')?.value || 60),
        entry_buffer_pct: Number(byId('wbEntryBuffer')?.value || 1),
      },
      breakout: {
        breakout_window: Number(byId('wbBreakoutWindow')?.value || 55),
        enable_dual_breakout: !!byId('wbDualBreakout')?.checked,
        breakout_window_short: Number(byId('wbBreakoutWindowShort')?.value || 20),
        breakout_window_long: Number(byId('wbBreakoutWindowLong')?.value || 55),
        breakout_entry_buffer_pct: Number(byId('wbBreakoutBuffer')?.value || 0),
        entry_confirm_mode: byId('wbEntryConfirmMode')?.value || 'none',
        entry_delay_mode: byId('wbEntryDelayMode')?.value || 'none',
      },
      entry_filter: {
        enable_entry_above_slow_ma: !!byId('wbEntryAboveSlowMa')?.checked,
        enable_entry_slow_ma_slope: !!byId('wbEntrySlowMaSlope')?.checked,
        entry_slope_lookback: Number(byId('wbEntrySlopeLookback')?.value || 5),
      },
      ranking: {
        momentum_top_pct: Number(byId('wbMomentumTopPct')?.value || 0),
      },
    },
    benchmark_regime: {
      ...(loadedBase.benchmark_regime || {}),
      enabled: !!byId('wbBenchmarkRegimeEnabled')?.checked,
      fast_period: Number(byId('wbBenchmarkRegimeFast')?.value || 20),
      slow_period: Number(byId('wbBenchmarkRegimeSlow')?.value || 120),
      slope_window: Number(byId('wbBenchmarkRegimeSlope')?.value || 5),
    },
    stock_trend_filter: {
      ...(loadedBase.stock_trend_filter || {}),
      enabled: !!byId('wbStockTrendEnabled')?.checked,
      short_ma: Number(byId('wbStockTrendShortMa')?.value || 20),
      long_ma: Number(byId('wbStockTrendLongMa')?.value || 60),
    },
    sector_gate: {
      ...(loadedBase.sector_gate || {}),
      enabled: !!byId('wbSectorGateEnabled')?.checked,
      rank_window: Number(byId('wbSectorRankWindow')?.value || 60),
      top_pct: Number(byId('wbSectorTopPct')?.value || 0.3),
    },
    signal_composition: {
      ...(loadedBase.signal_composition || {}),
      enabled: !!byId('wbEnableComposition')?.checked,
      compose_mode: byId('wbComposeMode')?.value || 'WEIGHTED_SCORE',
      score_threshold: Number(byId('wbScoreThreshold')?.value || 0.6),
      modules: compose,
    },
    exit_rules: {
      ...loadedExitRules,
      enabled: !!byId('wbEnableExit')?.checked,
      signal_reverse: !!byId('wbExitReverse')?.checked,
      atr_stop: { enabled: !!byId('wbExitAtr')?.checked, k: Number(byId('wbAtrK')?.value || 0.8) },
      trailing: { enabled: !!byId('wbExitTrail')?.checked, k: Number(byId('wbTrailK')?.value || 2.0) },
      time_exit: { enabled: !!byId('wbExitTime')?.checked, n_days: Number(byId('wbExitDays')?.value || 20) },
      hold_constraint: {
        min_hold_days: Number(byId('wbMinHoldDays')?.value || 0),
        cooldown_days: Number(byId('wbCooldownDays')?.value || 0),
      },
      take_profit: {
        enabled: !!byId('wbExitTakeProfit')?.checked,
        mode: byId('wbTakeProfitMode')?.value || 'pct',
        pct: Number(byId('wbTakeProfitPct')?.value || 10) / 100,
        atr_k: Number(byId('wbTakeProfitAtrK')?.value || 3.0),
      },
      fixed_stop: {
        enabled: !!byId('wbExitFixedStop')?.checked,
        pct: Number(byId('wbFixedStopPct')?.value || 5) / 100,
      },
      ma20_exit: {
        enabled: !!byId('wbExitMa20')?.checked,
      },
      low10_exit: {
        enabled: !!byId('wbExitLow10')?.checked,
      },
    },
    universe_filter: {
      ...(loadedBase.universe_filter || {}),
      min_price: Number(byId('wbPriceMin')?.value || 0),
    },
    position_risk: {
      ...loadedPositionRisk,
      enabled: !!byId('wbEnableRisk')?.checked,
      max_positions: Number(byId('wbMaxPositions')?.value || 10),
      single_stock_cap: Number(byId('wbSingleCap')?.value || 10) / 100,
      industry_cap: Number(byId('wbIndustryCap')?.value || 30) / 100,
      lot: Number(byId('wbLot')?.value || 100),
      cash_shortage_policy: byId('wbCashPolicy')?.value || 'skip',
      portfolio_mode: byId('wbPortfolioMode')?.value || 'equal_10',
      risk_budget: {
        ...loadedRiskBudget,
        enabled: !!byId('wbRiskBudget')?.checked,
        base_portfolio_risk: Number(byId('wbBasePortfolioRisk')?.value || 6) / 100,
        atr_stop_k: Number(byId('wbAtrStopK')?.value || 2.0),
        min_active_ratio: Number(byId('wbMinActiveRatio')?.value || 60) / 100,
        dd_scale_10: Number(byId('wbDdScale10')?.value || 0.8),
        dd_scale_15: Number(byId('wbDdScale15')?.value || 0.6),
        dd_fixed_20: Number(byId('wbDdFixed20')?.value || 3) / 100,
        dd_stop_pct: Number(byId('wbDdStopPct')?.value || 35) / 100,
        dd_stop_cooldown_days: Number(byId('wbDdStopCooldown')?.value || 60),
        dd_stop_protect_days: Number(byId('wbDdStopProtect')?.value || 30),
      },
      market_filter: {
        ...loadedMarketFilter,
        enabled: !!byId('wbMarketFilter')?.checked,
        slope_ma_period: Number(byId('wbMfSlopeMaPeriod')?.value || 50),
        slope_window: Number(byId('wbMfSlopeWindow')?.value || 10),
        bull_multiplier: Number(byId('wbMfBullMult')?.value || 1.5),
        light_multiplier: Number(byId('wbMfLightMult')?.value || 0.6),
        ema_light_fast: Number(byId('wbMfEmaFast')?.value || 5),
        ema_light_slow: Number(byId('wbMfEmaSlow')?.value || 20),
      },
      cost_model: {
        commission: 'fixed_assumption',
        stamp_tax: 'fixed_assumption',
        slippage: 'fixed_assumption',
        matching: 'next_open',
      },
      ...(includeBreadth ? { breadth: {
        ...loadedBreadth,
        enabled: !!byId('wbBreadthEnabled')?.checked,
        mode: byId('wbBreadthMode')?.value || 'dynamic_maxpos',
        score_type: byId('wbBreadthScoreType')?.value || 'B',
        mapping_mode: byId('wbBreadthMappingMode')?.value || 'smooth',
        min_positions: Number(byId('wbBreadthMinPositions')?.value || 3),
        max_positions: Number(byId('wbBreadthMaxPositions')?.value || 15),
        step_high: Number(byId('wbBreadthStepHigh')?.value || 0.6),
        step_mid: Number(byId('wbBreadthStepMid')?.value || 0.45),
        smooth_lo: Number(byId('wbBreadthSmoothLo')?.value || 0.4),
        smooth_range: Number(byId('wbBreadthSmoothRange')?.value || 0.2),
        ema_fast: Number(byId('wbBreadthEmaFast')?.value || 8),
        ema_slow: Number(byId('wbBreadthEmaSlow')?.value || 25),
        gate_threshold: Number(byId('wbBreadthGateThreshold')?.value || 0.45),
        gate_quantile_window: Number(byId('wbBreadthGateWindow')?.value || 252),
        gate_quantile_pct: Number(byId('wbBreadthGatePct')?.value || 0.2),
        gate_persist_days: Number(byId('wbBreadthGatePersist')?.value || 3),
        size_scale_floor: Number(byId('wbBreadthScaleFloor')?.value || 0.3),
      } } : {}),
    },
    ...(includeSizing ? { sizing: {
      ...loadedSizing,
      weight_mode: weightMode,
      min_positions: minPositions,
    } } : {}),
    exit_priority: Array.from(byId('wbExitPriorityList')?.querySelectorAll('li') || []).map(
      (li) => li.textContent.replace(/^\d+\s*/, '').trim()
    ),
  };
  state.config_draft = draft;
  state.strategy_pack = draft.strategy_pack;
  state.universe_mode = draft.universe_mode;
  if (byId('wbStrategyPack')) byId('wbStrategyPack').value = draft.strategy_pack;
  refreshConfigPanels();
  syncConfigSourceUI();
  renderSummaryBar();
  return draft;
}

function hydrateComposeRows(rows) {
  const body = byId('wbComposeRows');
  if (!body) return;
  const data = Array.isArray(rows) && rows.length ? rows : defaultComposeRows();
  body.innerHTML = data.map((r) => `
    <tr data-name="${esc(r.name)}">
      <td>${esc(r.name)}</td>
      <td><input data-k="enabled" type="checkbox" ${r.enabled ? 'checked' : ''}></td>
      <td><select data-k="role" class="formInput" style="width:auto"><option ${r.role === 'Hard Gate' ? 'selected' : ''}>Hard Gate</option><option ${r.role === 'Soft Weight' ? 'selected' : ''}>Soft Weight</option><option ${r.role === 'Rank' ? 'selected' : ''}>Rank</option></select></td>
      <td><input data-k="weight" type="number" class="formInput" value="${Number(r.weight ?? 0)}"></td>
      <td><input data-k="priority" type="number" class="formInput" value="${Number(r.priority ?? 0)}"></td>
    </tr>
  `).join('');
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll('#wbMode button').forEach((b) => b.classList.toggle('active', b.getAttribute('data-mode') === mode));
  addLog(`切换模式: ${mode}`);
  buildConfigDraft();
  syncPresetHint();
}

function estimatedTier() {
  const u = Number(byId('wbUniverseLimit')?.value || 0);
  if (u >= 700) return 'T3?';
  if (u >= 300) return 'T2?';
  if (u >= 50) return 'T1?';
  return 'T0?';
}

function renderRunHints() {
  byId('wbEstimatedGroups').textContent = '运行模式: Single Run';
  byId('wbEstimatedTier').textContent = `Tier预估: ${estimatedTier()}`;
}

function renderUniverseStats(stats) {
  const el = byId('wbUniverseStats');
  if (!el) return;
  if (!stats) {
    el.textContent = '等待 validate_data...';
    return;
  }
  const funnel = (stats.filter_breakdown || []).map((x) => `${x.name}:${x.before}→${x.after}`).join(' | ');
  const scope = stats.scope_label ? `${esc(stats.scope_label)} | ` : '';
  el.innerHTML = `${scope}全市场 ${stats.total_symbols} → 可交易 ${stats.tradable_symbols} → 流动性过滤 ${stats.after_filters_symbols} → 最终 ${stats.universe_size}<br>
    交易日=${stats.trading_days} | 缺失率=${pct(stats.missing_rate)} | 数据快照=${esc(stats.data_snapshot_id || '无')}<br>${esc(funnel)}`;
}

function currentSymbolsForValidate() {
  const mode = byId('wbUniverseMode')?.value || 'ALL_A';
  const custom = (byId('wbSymbols')?.value || '').split(',').map((s) => s.trim()).filter(Boolean);
  if (mode === 'CUSTOM') return custom;
  return [];
}

async function doValidate() {
  buildConfigDraft();
  const q = new URLSearchParams();
  const syms = currentSymbolsForValidate();
  if (syms.length) q.set('symbols', syms.join(','));
  q.set('start', byId('wbStartDate')?.value || '2021-01-01');
  q.set('end', byId('wbEndDate')?.value || '2026-02-01');
  q.set('benchmark', byId('wbBenchmark')?.value || '000300.SH');
  q.set('universe_mode', byId('wbUniverseMode')?.value || 'ALL_A');
  q.set('industries', getSelectedIndustries().join(','));
  q.set('universe_limit', String(Number(byId('wbUniverseLimit')?.value || 0) || 0));
  q.set('strict_suspended', String(!!byId('wbExcludeSuspended')?.checked));
  q.set('exclude_st', String(!!byId('wbExcludeSt')?.checked));
  q.set('exclude_suspended', String(!!byId('wbExcludeSuspended')?.checked));
  q.set('min_list_days', String(Number(byId('wbMinListDays')?.value || 120)));
  q.set('min_avg_turnover_20d', String(Number(byId('wbMinTurnover')?.value || 1e8)));
  q.set('price_min', String(Number(byId('wbPriceMin')?.value || 0)));
  q.set('price_max', String(Number(byId('wbPriceMax')?.value || 99999)));
  q.set('limit_rule', byId('wbLimitRule')?.value || 'ignore');
  q.set('audit_dump', 'true');
  const url = `/api/backtest_v2/validate_data?${q.toString()}`;
  byId('wbRunStatus').textContent = '数据验收中...';
  addLog(`GET ${url}`);
  const j = await apiRequestJson('validate_data', url);
  state.universe_stats = j.universe_stats || null;
  renderUniverseStats(state.universe_stats);
  byId('wbRunStatus').textContent = j.pass ? `验收通过 request_id=${j.request_id}` : `验收未通过 request_id=${j.request_id}`;
}

async function pollJob(jobId) {
  const btn = byId('wbRunBtn');
  const originalText = btn ? btn.textContent : '';
  const originalClass = btn ? btn.className : '';
  let canceled = false;
  const startedAt = Date.now();
  const baseWindowMs = 30 * 60 * 1000; // 30 min base window
  const extendStepMs = 5 * 60 * 1000;  // +5 min per progress advance
  const hardCapMs = 60 * 60 * 1000;    // 60 min hard cap
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
      } catch (_) { /* best effort */ }
    };
    btn.addEventListener('click', onCancel);
    var _cleanupCancel = () => {
      btn.removeEventListener('click', onCancel);
      btn.textContent = originalText;
      btn.className = originalClass;
    };
  }

  try {
    for (let i = 0; ; i += 1) {
      if (canceled) {
        byId('wbRunStatus').textContent = '已取消';
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
      byId('wbRunStatus').textContent = `${j.status} ${j.progress_pct ?? 0}% ${j.message || ''} | 剩余${remainSec}s`;
      if (j.status === 'success') return j.result || null;
      if (j.status === 'failed') throw new Error(j.error || 'job failed');
      if (j.status === 'canceled') { byId('wbRunStatus').textContent = '已取消'; return null; }
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
  if (isLockedCandidatePreset(requestedPreset)) {
    return {
      preset: requestedPreset,
      fast_mode: true,
      workbench_mode: state.mode,
    };
  }
  const d = buildConfigDraft();
  const payload = {
      preset: requestedPreset,
      config_id: effectiveConfigIdForExecution(),
      runtime_config_json: d,
      workbench_mode: state.mode,
      fast_mode: true,
  };
  return payload;
}

function runPayloadFromDraft(preset) {
  return resolveRuntimeConfigHandoff(preset);
}

async function runExperiment(presetOverride = null) {
  const requestedPreset = selectedExperimentPreset(presetOverride || 'single');
  const payload = runPayloadFromDraft(requestedPreset);
  addLog(`POST /api/backtest_v2/experiment/run_async (${requestedPreset})`);
  const q = await apiRequestJson('experiment_run_async', '/api/backtest_v2/experiment/run_async', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  const result = await pollJob(q.job_id);
  state.active_exp = result;
  state.active_result = result;
  await loadActiveArtifacts();
  if (isLockedCandidatePreset(requestedPreset) && !state.active_artifacts?.run_meta?.candidate) {
    throw new Error(`candidate preset mismatch: ${result?.exp_id || '-'} did not return locked candidate artifacts`);
  }
  renderExperimentResult(result);
  renderRightInspector();
  renderArtifacts(result);
}

function renderExperimentResult(result) {
  byId('wbDims').textContent = `exp_id=${result?.exp_id || '-'} | status=${result?.status || '-'}`;
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

function runtimeStrategySummary(cfg, art) {
  const strategy = cfg?.strategy || {};
  const params = strategy.params || {};
  const strategyName = String(strategy.name || '').toUpperCase();
  const maxPositions = art?.run_meta?.counters?.max_positions ?? cfg?.position_risk?.max_positions ?? '-';
  const br = cfg?.benchmark_regime || {};
  const brTag = br.enabled ? ` | BR=${br.fast_period ?? 20}/${br.slow_period ?? 120}` : '';
  if (strategyName === 'BREAKOUT_TREND') {
    return `BREAKOUT_TREND | 突破=${params.breakout_window ?? 55} | ATR止损=${params.atr_stop_k ?? '-'} | ATR追踪=${params.atr_trail_k ?? '-'} | regime_ma=${params.regime_ma ?? '-'}${brTag} | 最大持仓=${maxPositions}`;
  }
  if (strategyName === 'SMA_CROSS' || strategyName === 'EMA_CROSS') {
    return `${strategyName} | 快线=${strategy.fast ?? '-'} 慢线=${strategy.slow ?? '-'}${brTag} | 最大持仓=${maxPositions}`;
  }
  return `${strategyName || 'STRATEGY'} | 最大持仓=${maxPositions}`;
}

function compactResultsDir(path) {
  const text = String(path || '').trim();
  if (!text) return '-';
  const parts = text.replaceAll('\\', '/').split('/').filter(Boolean);
  return parts.length ? parts[parts.length - 1] : text;
}

function runtimeStrategyOverview(cfg, art) {
  const strategy = cfg?.strategy || {};
  const params = strategy.params || {};
  const strategyName = String(strategy.name || '').toUpperCase();
  const maxPositions = art?.run_meta?.counters?.max_positions ?? cfg?.position_risk?.max_positions ?? '-';
  const portfolioMode = cfg?.position_risk?.portfolio_mode || cfg?.risk_budget?.portfolio_mode || 'equal_10';
  const br = cfg?.benchmark_regime || {};
  const brText = br.enabled ? `BR ${br.fast_period ?? 20}/${br.slow_period ?? 120}/${br.slope_window ?? 5}` : 'BR 关闭';
  if (strategyName === 'BREAKOUT_TREND') {
    return {
      name: 'BREAKOUT_TREND',
      core: `突破 ${params.breakout_window ?? 55} | ATR ${params.atr_stop_k ?? '-'} / ${params.atr_trail_k ?? '-'}`,
      portfolioMode,
      extra: `regime_ma=${params.regime_ma ?? '-'} | ${brText} | 最大持仓=${maxPositions}`,
    };
  }
  if (strategyName === 'SMA_CROSS' || strategyName === 'EMA_CROSS') {
    return {
      name: strategyName,
      core: `快线 ${strategy.fast ?? '-'} | 慢线 ${strategy.slow ?? '-'}`,
      portfolioMode,
      extra: `${brText} | 最大持仓=${maxPositions}`,
    };
  }
  const sg = cfg?.signal_generation || {};
  const trend = sg.trend || sg.sma || sg.ema || {};
  const stratName = String(sg.strategy || cfg.strategy_pack || 'SMA_CROSS').toUpperCase();
  if (sg.regime_detection?.enabled) {
    const mr = sg.mr || {};
    return {
      name: 'REGIME',
      core: `趋势 ${String(trend.strategy || 'SMA').toUpperCase()} ${trend.fast_ma ?? 20}/${trend.slow_ma ?? 60}`,
      portfolioMode: cfg?.position_risk?.portfolio_mode ?? 'equal_10',
      extra: `MR RSI(${mr.rsi_period ?? 6}) ${mr.rsi_buy_threshold ?? 20}/${mr.rsi_sell_threshold ?? 80} | regime_ma=${sg.regime_detection?.regime_ma ?? 60}`,
    };
  }
  const breakout = sg.breakout || {};
  return {
    name: stratName || 'STRATEGY',
    core: stratName === 'BREAKOUT_TREND'
      ? `突破 ${breakout.breakout_window ?? 55} | confirm=${breakout.entry_confirm_mode ?? 'none'}`
      : `快线 ${trend.fast_ma ?? '-'} | 慢线 ${trend.slow_ma ?? '-'}`,
    portfolioMode: cfg?.position_risk?.portfolio_mode ?? 'equal_10',
    extra: `最大持仓=${cfg?.position_risk?.max_positions ?? '-'} | 组合=${cfg?.position_risk?.portfolio_mode ?? 'equal_10'}`,
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
    ? (Number.isFinite(Number(tradableCount)) ? `${fmtInt(rawCount)} → ${fmtInt(tradableCount)}` : fmtInt(rawCount))
    : (Array.isArray(u.symbols) ? fmtInt(u.symbols.length) : '-');
  const strategyInfo = runtimeStrategyOverview(cfg, art);
  const configSource = rm?.candidate?.candidate_name
    || rm?.report_consistency?.config_source
    || state.loaded_config_meta?.display_name
    || state.config_source_mode
    || '草稿';

  setTextById('wbOverviewExpId', row.exp_id || '-');
  setTextById('wbOverviewStatus', row.exp_id ? (row.status || '-') : '等待运行');
  setTextById('wbOverviewConfigSource', String(configSource || '-'));
  setTextById('wbOverviewResultsDir', compactResultsDir(row.results_dir || state.active_exp?.results_dir || ''));
  setTextById('wbSummaryUniverse', `${start} ~ ${end}`);
  setTextById('wbOverviewBenchmark', benchmark);
  setTextById('wbOverviewUniverseMode', universeMode);
  setTextById('wbOverviewUniverseCount', symbolsText);
  setTextById('wbOverviewStrategyName', strategyInfo.name);
  setTextById('wbOverviewStrategyCore', strategyInfo.core);
  setTextById('wbOverviewPortfolioMode', strategyInfo.portfolioMode);
  setTextById('wbSummaryStrategy', strategyInfo.extra);
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
  document.querySelectorAll('#wbUniverseModeGroup button').forEach(b => {
    b.classList.toggle('active', b.getAttribute('data-val') === loadedMode);
  });
  _set('wbSymbols', Array.isArray(u.symbols) ? u.symbols.join(',') : undefined);
  _set('wbUniverseLimit', u.limit);
  _chk('wbExcludeSt', f.exclude_st);
  _chk('wbExcludeSuspended', f.exclude_suspended);
  _set('wbMinListDays', f.min_list_days);
  _set('wbMinTurnover', f.min_avg_turnover_20d);
  _set('wbPriceMin', f.price_min ?? cfg?.universe_filter?.min_price);
  _set('wbPriceMax', f.price_max);
  _set('wbLimitRule', f.limit_rule);

  // 价格口径
  const loadedAdj = u.price_adj || 'hfq';
  _set('wbPriceAdj', loadedAdj);
  document.querySelectorAll('#wbAdjGroup button').forEach(b => {
    b.classList.toggle('active', b.getAttribute('data-val') === loadedAdj);
  });

  // --- 信号生成: 新结构 (regime_detection + trend + mr) ---
  const sgCfg = cfg?.signal_generation || {};
  const rawStrategyName = String(sgCfg.strategy || cfg?.strategy_pack || 'SMA_CROSS').toUpperCase();
  const unsupportedAdaptiveRegime = rawStrategyName === 'ADAPTIVE_REGIME';
  const strategyName = unsupportedAdaptiveRegime ? 'REGIME_ROUTER' : rawStrategyName;
  _set('wbStrategyPack', strategyName);

  // Regime detection
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

  // Trend strategy
  const trend = sgCfg.trend || {};
  const trendName = trend.strategy || strategyName || 'EMA_CROSS';
  _set('wbTrendStrategy', trendName);
  _set('wbFastMa', trend.fast_ma ?? sgCfg.sma?.fast_ma ?? 20);
  _set('wbSlowMa', trend.slow_ma ?? sgCfg.sma?.slow_ma ?? 60);
  _set('wbEntryBuffer', trend.entry_buffer_pct ?? sgCfg.sma?.entry_buffer_pct ?? 1);
  const breakout = sgCfg.breakout || {};
  _set('wbBreakoutWindow', breakout.breakout_window ?? 55);
  _chk('wbDualBreakout', breakout.enable_dual_breakout);
  _set('wbBreakoutWindowShort', breakout.breakout_window_short ?? 20);
  _set('wbBreakoutWindowLong', breakout.breakout_window_long ?? 55);
  _set('wbBreakoutBuffer', breakout.breakout_entry_buffer_pct ?? 0);
  _set('wbEntryConfirmMode', breakout.entry_confirm_mode ?? 'none');
  _set('wbEntryDelayMode', breakout.entry_delay_mode ?? 'none');
  _set('wbMomentumTopPct', sgCfg.ranking?.momentum_top_pct ?? 0);

  // MR strategy
  const mr = sgCfg.mr || {};
  _set('wbMrStrategy', mr.strategy || 'RSI_REVERSAL');
  _set('wbMrRsiPeriod', mr.rsi_period ?? 6);
  _set('wbMrRsiBuy', mr.rsi_buy_threshold ?? 20);
  _set('wbMrRsiSell', mr.rsi_sell_threshold ?? 80);
  _set('wbMrMaxHold', mr.mr_max_hold_days ?? 5);
  const mrStopRaw = mr.mr_stop_loss_pct;
  _set('wbMrStopLoss', mrStopRaw != null ? Number(mrStopRaw) * 100 : 3);

  // MR panel visibility — always visible, dimmed when regime off
  const mrPanel = byId('wbMrPanel'); if (mrPanel) mrPanel.style.opacity = regimeOn ? '1' : '0.45';

  // 入场趋势过滤
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
  _chk('wbExitTime', ex.time_exit?.enabled);
  _set('wbExitDays', ex.time_exit?.n_days);
  // 持仓约束
  const hc = ex.hold_constraint || {};
  _set('wbMinHoldDays', hc.min_hold_days ?? 0);
  _set('wbCooldownDays', hc.cooldown_days ?? 0);
  // 止盈
  const tp = ex.take_profit || {};
  _chk('wbExitTakeProfit', tp.enabled);
  _set('wbTakeProfitMode', tp.mode);
  _set('wbTakeProfitPct', tp.pct != null ? Number(tp.pct) * 100 : undefined);
  _set('wbTakeProfitAtrK', tp.atr_k);
  // 固定止损
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
  _set('wbPortfolioMode', pr.portfolio_mode ?? 'equal_10');
  // 风险预算
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
  // MA200 市场过滤
  const mf = pr.market_filter || {};
  _chk('wbMarketFilter', mf.enabled);
  _set('wbMfSlopeMaPeriod', mf.slope_ma_period);
  _set('wbMfSlopeWindow', mf.slope_window);
  _set('wbMfBullMult', mf.bull_multiplier);
  _set('wbMfLightMult', mf.light_multiplier);
  _set('wbMfEmaFast', mf.ema_light_fast);
  _set('wbMfEmaSlow', mf.ema_light_slow);
  // breadth
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
  // sizing
  const sizing = cfg?.sizing || {};
  _set('wbWeightMode', sizing.weight_mode ?? 'equal');
  _set('wbMinPositions', sizing.min_positions ?? 10);
  // benchmark regime
  const br = cfg?.benchmark_regime || {};
  _chk('wbBenchmarkRegimeEnabled', br.enabled);
  _set('wbBenchmarkRegimeFast', br.fast_period ?? 20);
  _set('wbBenchmarkRegimeSlow', br.slow_period ?? 120);
  _set('wbBenchmarkRegimeSlope', br.slope_window ?? 5);
  // stock trend / sector gate
  const stockTrend = cfg?.stock_trend_filter || {};
  _chk('wbStockTrendEnabled', stockTrend.enabled);
  _set('wbStockTrendShortMa', stockTrend.short_ma ?? 20);
  _set('wbStockTrendLongMa', stockTrend.long_ma ?? 60);
  const sectorGate = cfg?.sector_gate || {};
  _chk('wbSectorGateEnabled', sectorGate.enabled);
  _set('wbSectorRankWindow', sectorGate.rank_window ?? 60);
  _set('wbSectorTopPct', sectorGate.top_pct ?? 0.3);
  _set('wbScoreThreshold', cfg?.signal_composition?.score_threshold ?? 0.6);

  // Exit priority
  const ep = cfg?.exit_priority;
  if (Array.isArray(ep) && ep.length) {
    const list = byId('wbExitPriorityList');
    if (list) {
      list.innerHTML = ep.map((name, i) =>
        `<li><span class="wb-priority-rank">${i + 1}</span> ${esc(name)}</li>`
      ).join('');
    }
  }

  hydrateComposeRows(cfg?.signal_composition?.modules || defaultComposeRows());
  buildConfigDraft();
  syncExitLinkage();
  updateAtrNote();
  return { unsupportedStrategy: unsupportedAdaptiveRegime ? rawStrategyName : null };
}

async function loadConfig(configId) {
  const j = await apiRequestJson('configs_get', `/api/backtest_v2/configs/${encodeURIComponent(configId)}`);
  state.loaded_config_json = cloneJson(j.config_json || {});
  const applied = applyConfigToUI(j.config_json || {});
  if (applied?.unsupportedStrategy) {
    clearLoadedConfig(`配置 ${j.config_id} 使用已移除策略 ${applied.unsupportedStrategy}；请改用 REGIME_ROUTER 重新配置`);
    byId('wbRunStatus').textContent = `配置 ${j.config_id} 使用已移除策略 ${applied.unsupportedStrategy}`;
    return;
  }
  setSelectedLockedCandidatePreset('');
  rememberLoadedConfig(j, stableSerializeConfig(state.config_draft || {}), j.config_json || {});
  addLog(`已加载配置: ${j.config_id}`);
}

async function loadConfigList() {
  const j = await apiRequestJson('configs_list', '/api/backtest_v2/configs?latest=50');
  const items = Array.isArray(j.items) ? j.items : [];
  const sel = byId('wbConfigList');
  if (!sel) return items;
  sel.innerHTML = '<option value="">选择配置...</option>' + items.map((x) => {
    const label = `${configMetaLabel(x)} ${configDisplayName(x) || x.config_id}`;
    return `<option value="${esc(x.config_id)}">${esc(label)} | ${esc(x.saved_at || '')}</option>`;
  }).join('');
  return items;
}

function configCenterBadgeText(item) {
  const sourceMap = { baseline: '基线', search: '搜索', template: '内置', derived: '保存' };
  const ownerMap = { manual: '手工', claude: 'Codex', script: '脚本', builtin: '内置' };
  const parts = [];
  const source = sourceMap[String(item?.source_type || '').trim()] || String(item?.source_type || '').trim() || '保存';
  const owner = ownerMap[String(item?.owner || '').trim()] || String(item?.owner || '').trim() || '手工';
  parts.push(source, owner);
  if (item?.locked) parts.push('锁定');
  return parts.join(' / ');
}

function buildConfigCenterGroups(items) {
  const builtin = [];
  const saved = [];
  (Array.isArray(items) ? items : []).forEach((item) => {
    const tags = new Set((Array.isArray(item?.tags) ? item.tags : []).map((tag) => String(tag || '').trim().toLowerCase()));
    if (String(item?.owner || '').trim().toLowerCase() === 'builtin' || tags.has('builtin') || String(item?.source_type || '').trim().toLowerCase() === 'template') {
      builtin.push(item);
      return;
    }
    saved.push(item);
  });
  return {
    draft: [
      {
        key: 'draft',
        title: '当前草稿',
        desc: state.loaded_config_meta?.config_id ? '脱离已加载配置 provenance，后续运行只认当前页面草稿' : '直接使用当前页面草稿作为运行真相',
        active: !String(state.selected_locked_candidate_preset || '').trim() && (!state.loaded_config_meta || currentConfigSourceMode() === 'loaded-dirty'),
        onClick: () => {
          setSelectedLockedCandidatePreset('');
          clearLoadedConfig('已切换到当前草稿');
        },
      },
    ],
    candidate: Object.keys(LOCKED_CANDIDATE_PRESETS).map((preset) => ({
      key: `candidate:${preset}`,
      title: preset === 'v2-breakout-br35-atr10-candidate' ? '候选 BR35 + ATR1.0' : '候选 ATR 1.0',
      desc: lockedCandidatePresetMeta(preset)?.hint || '锁定候选入口',
      active: String(state.selected_locked_candidate_preset || '').trim() === preset,
      onClick: () => {
        setSelectedLockedCandidatePreset(preset);
        addLog(`已选择锁定候选: ${preset}`);
      },
    })),
    builtin: builtin.map((item) => ({
      key: `config:${item.config_id}`,
      title: configDisplayName(item) || item.config_id,
      desc: `${configCenterBadgeText(item)} | ${item.saved_at || ''}`,
      active: !String(state.selected_locked_candidate_preset || '').trim() && currentConfigSourceMode() === 'loaded-clean' && String(state.loaded_config_meta?.config_id || '') === String(item.config_id || ''),
      onClick: async () => {
        await loadConfig(item.config_id);
      },
    })),
    saved: saved.map((item) => ({
      key: `config:${item.config_id}`,
      title: configDisplayName(item) || item.config_id,
      desc: `${configCenterBadgeText(item)} | ${item.saved_at || ''}`,
      active: !String(state.selected_locked_candidate_preset || '').trim() && currentConfigSourceMode() === 'loaded-clean' && String(state.loaded_config_meta?.config_id || '') === String(item.config_id || ''),
      onClick: async () => {
        await loadConfig(item.config_id);
      },
    })),
  };
}

async function openConfigCenterDropdown(anchorEl = null) {
  const existing = document.getElementById('wbConfigCenterDropdown');
  if (existing) {
    existing.remove();
    return;
  }
  const items = await loadConfigList();
  const groups = buildConfigCenterGroups(items);
  const dd = document.createElement('div');
  dd.id = 'wbConfigCenterDropdown';
  dd.className = 'wb-load-dropdown wb-config-center-dropdown';
  const sections = [
    ['当前草稿', groups.draft],
    ['锁定 Candidate', groups.candidate],
    ['内置模板', groups.builtin],
    ['已保存配置', groups.saved],
  ];
  sections.forEach(([label, rows]) => {
    if (!Array.isArray(rows) || !rows.length) return;
    const head = document.createElement('div');
    head.className = 'wb-config-center-section';
    head.textContent = label;
    dd.appendChild(head);
    rows.forEach((row) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = `wb-load-item wb-config-center-item${row.active ? ' active' : ''}`;
      item.innerHTML = `<span class="wb-config-center-title">${esc(row.title)}</span><span class="wb-config-center-desc">${esc(row.desc)}</span>`;
      item.addEventListener('click', async () => {
        dd.remove();
        try {
          await row.onClick();
        } catch (e) {
          addLog(`配置中心操作失败: ${e?.message || e}`);
        }
      });
      dd.appendChild(item);
    });
  });
  (anchorEl || byId('wbConfigCenterBtn') || byId('wbQuickLoad') || byId('wbRunBtn'))?.parentElement?.appendChild(dd);
  const dismiss = (e) => {
    const btn = anchorEl || byId('wbConfigCenterBtn') || byId('wbQuickLoad');
    if (!dd.contains(e.target) && e.target !== btn) {
      dd.remove();
      document.removeEventListener('click', dismiss);
    }
  };
  setTimeout(() => document.addEventListener('click', dismiss), 0);
}

async function previewExecution() {
  buildConfigDraft();
  const body = {
    config_id: effectiveConfigIdForExecution(),
    runtime_config_json: state.config_draft,
    exp_id: state.active_exp?.exp_id || null,
    results_dir: state.active_exp?.results_dir || null,
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
      renderExecutionPanel();
      throw new Error('后端未启用 execution preview');
    }
    throw e;
  }
  state.execution_api_enabled = true;
  state.execution_preview = payload;
  renderExecutionPanel();
  if (state.execution_preview?.files?.execution_list_json_path) addLog(`execution_list: ${state.execution_preview.files.execution_list_json_path}`);
}

function copyExecJson() {
  if (!state.execution_preview) return;
  navigator.clipboard?.writeText(JSON.stringify(state.execution_preview, null, 2));
  addLog('执行清单已复制到剪贴板');
}

function copyConfigJson() {
  navigator.clipboard?.writeText(JSON.stringify(state.config_draft || {}, null, 2));
  addLog('配置JSON已复制');
}

async function pasteConfigJson() {
  try {
    const text = await navigator.clipboard.readText();
    const obj = JSON.parse(text);
    applyConfigToUI(obj || {});
    clearLoadedConfig();
    addLog('已从剪贴板粘贴配置JSON');
  } catch (e) {
    addLog(`粘贴JSON失败: ${e.message || e}`);
  }
}

function switchInspectorTab(tab) {
  if (tab === 'perf' || tab === 'runner') return switchDockTab('buy_funnel');
  if (tab === 'explain') return switchDockTab('buy_funnel');
  if (tab === 'exec' || tab === 'execution') return switchDockTab('execution');
  if (tab === 'sell' || tab === 'sell_funnel') return switchDockTab('sell_funnel');
  if (tab === 'logs') return switchDockTab('logs');
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

/* ── Risk & Exit Enhancement Functions ── */

function syncExitLinkage() {
  const trailCb = byId('wbExitTrail');
  const trailInput = byId('wbTrailK');
  const timeCb = byId('wbExitTime');
  const timeInput = byId('wbExitDays');
  if (trailCb && trailInput) trailInput.disabled = !trailCb.checked;
  if (timeCb && timeInput) timeInput.disabled = !timeCb.checked;
}

function updateAtrNote() {
  const el = byId('wbAtrNote');
  if (!el) return;
  const priceAdj = byId('wbPriceAdj');
  const matchPrice = byId('wbMatchPrice');
  const adjLabel = priceAdj ? (priceAdj.options[priceAdj.selectedIndex]?.text || priceAdj.value) : '前复权';
  const matchLabel = matchPrice ? (matchPrice.options[matchPrice.selectedIndex]?.text || matchPrice.value) : '次日开盘';
  el.textContent = `ATR 窗口: 14日 · 价格口径: ${adjLabel} · 触发价: ${matchLabel}`;
}

function populateExitStats(counters) {
  const container = byId('wbExitStats');
  if (!container) return;
  const keys = ['reversal_exit_count', 'atr_stop_exit_count', 'atr_trail_exit_count', 'atr_trail_update_count', 'time_exit_count', 'take_profit_exit_count', 'fixed_stop_loss_exit_count', 'dd_stop_block_count'];
  keys.forEach((k) => {
    const el = container.querySelector(`[data-key="${k}"]`);
    if (el) {
      const v = counters[k];
      el.textContent = v != null && Number.isFinite(Number(v)) ? num(v, 0) : '—';
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
    if (el) el.textContent = Number.isFinite(Number(v)) ? num(v, k === 'avg_positions' || k === 'slots_left' ? 1 : 0) : '—';
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
      el.textContent = v != null && Number.isFinite(Number(v)) ? num(v, 0) : '—';
    }
  });
}
