/* ── ui-controls.js ── UI interactions, config building, drawer, dock tabs ── */
/* Globals used: state, byId, esc, num, pct, fmtInt, fmtMoney, setTextById, setHtmlById,
   getStrategySelector, getStrategyPackValue, COMPOSE_MODULES, reasonZh, addLog,
   apiRequestJson, setStatusItems, _apiTag,
   renderPerfPanel, renderNavChartLW, renderDdChartLW,
   loadActiveArtifacts, renderRightInspector, renderArtifacts (from other modules) */

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
  state.drawer_panel = panel || 'universe';
  document.querySelectorAll('.wb-rail-btn').forEach((btn) => btn.classList.toggle('active', btn.getAttribute('data-panel') === state.drawer_panel));
  document.querySelectorAll('.wb-module').forEach((m) => m.classList.toggle('active', m.getAttribute('data-module') === state.drawer_panel));
  const titleEl = byId('wbDrawerTitle');
  if (titleEl) {
    const titles = { universe: 'Universe', signal: 'Signal', compose: 'Composition', risk: 'Risk & Exit', json: 'JSON', history: '实验历史' };
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
  const next = tab || 'explain';
  state.dock_tab = next;
  document.querySelectorAll('.wb-analysis-tabs button[data-dock]').forEach((b) => b.classList.toggle('active', b.getAttribute('data-dock') === next));
  document.querySelectorAll('.wb-dock-panel').forEach((p) => p.classList.remove('active'));
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
    mode: state.mode,
    strategy_pack: getStrategyPackValue(),
    universe_mode: byId('wbUniverseMode')?.value || 'ALL_A',
    industries: getSelectedIndustries(),
    universe: {
      start: byId('wbStartDate')?.value || '2021-01-01',
      end: byId('wbEndDate')?.value || '2026-02-01',
      benchmark: byId('wbBenchmark')?.value || '000300.SH',
      symbols: (byId('wbSymbols')?.value || '').split(',').map((s) => s.trim()).filter(Boolean),
      limit: Number(byId('wbUniverseLimit')?.value || 1000),
      price_adj: byId('wbPriceAdj')?.value || 'hfq',
      filters: {
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
      entry_filter: {
        enable_entry_above_slow_ma: !!byId('wbEntryAboveSlowMa')?.checked,
        enable_entry_slow_ma_slope: !!byId('wbEntrySlowMaSlope')?.checked,
        entry_slope_lookback: Number(byId('wbEntrySlopeLookback')?.value || 5),
      },
    },
    signal_composition: {
      enabled: !!byId('wbEnableComposition')?.checked,
      compose_mode: byId('wbComposeMode')?.value || 'WEIGHTED_SCORE',
      modules: compose,
    },
    exit_rules: {
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
    },
    position_risk: {
      enabled: !!byId('wbEnableRisk')?.checked,
      max_positions: Number(byId('wbMaxPositions')?.value || 10),
      single_stock_cap: Number(byId('wbSingleCap')?.value || 10) / 100,
      industry_cap: Number(byId('wbIndustryCap')?.value || 30) / 100,
      lot: Number(byId('wbLot')?.value || 100),
      cash_shortage_policy: byId('wbCashPolicy')?.value || 'skip',
      risk_budget: {
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
    },
    exit_priority: Array.from(byId('wbExitPriorityList')?.querySelectorAll('li') || []).map(
      (li) => li.textContent.replace(/^\d+\s*/, '').trim()
    ),
  };
  state.config_draft = draft;
  state.strategy_pack = draft.strategy_pack;
  state.universe_mode = draft.universe_mode;
  refreshConfigPanels();
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
  el.innerHTML = `全市场 ${stats.total_symbols} → 可交易 ${stats.tradable_symbols} → 流动性过滤 ${stats.after_filters_symbols} → 最终 ${stats.universe_size}<br>
    交易日=${stats.trading_days} | 缺失率=${pct(stats.missing_rate)} | 数据快照=${esc(stats.data_snapshot_id || '无')}<br>${esc(funnel)}`;
}

function currentSymbolsForValidate() {
  const mode = byId('wbUniverseMode')?.value || 'ALL_A';
  const custom = (byId('wbSymbols')?.value || '').split(',').map((s) => s.trim()).filter(Boolean);
  if (mode === 'CUSTOM' && custom.length) return custom;
  // 非 CUSTOM 模式下 resolver 会动态解析，这里用少量样本做验证
  return custom.length ? custom : ['600000.SH', '000001.SZ', '600519.SH'];
}

async function doValidate() {
  buildConfigDraft();
  const q = new URLSearchParams();
  const syms = currentSymbolsForValidate();
  q.set('symbols', syms.join(','));
  q.set('start', byId('wbStartDate')?.value || '2021-01-01');
  q.set('end', byId('wbEndDate')?.value || '2026-02-01');
  q.set('benchmark', byId('wbBenchmark')?.value || '000300.SH');
  q.set('strict_suspended', String(!!byId('wbExcludeSuspended')?.checked));
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
function runPayloadFromDraft(preset) {
  const d = buildConfigDraft();
  const mode = d.universe_mode || 'CUSTOM';
  const payload = {
    preset,
    start_date: d.universe.start,
    end_date: d.universe.end,
    benchmark: d.universe.benchmark,
    compare_symbol: byId('wbBenchmark')?.value || '000001.SH',
    universe_limit: d.universe.limit,
    max_positions: d.position_risk.max_positions,
    lot_size: d.position_risk.lot,
    config_id: state.config_id,
    workbench_mode: state.mode,
    workbench_config: d,
    fast_mode: true,
    universe_mode: mode,
    price_adj: d.universe.price_adj || 'hfq',
  };
  // CUSTOM 模式传 symbols，INDUSTRY 模式传 industries
  if (mode === 'CUSTOM') {
    payload.symbols = d.universe.symbols;
  } else if (mode === 'INDUSTRY') {
    payload.industries = d.industries || [];
  }
  return payload;
}

async function runExperiment(presetOverride = null) {
  const payload = runPayloadFromDraft(presetOverride || 'single');
  addLog('POST /api/backtest_v2/experiment/run_async (single-run)');
  const q = await apiRequestJson('experiment_run_async', '/api/backtest_v2/experiment/run_async', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  const result = await pollJob(q.job_id);
  state.active_exp = result;
  state.active_result = result;
  await loadActiveArtifacts();
  renderExperimentResult(result);
  renderRightInspector();
  renderArtifacts(result);
}

function renderExperimentResult(result) {
  byId('wbDims').textContent = `exp_id=${result?.exp_id || '-'} | status=${result?.status || '-'}`;
}

function renderSummaryBar() {
  const cfg = state.config_draft || {};
  const u = cfg.universe || {};
  const sg = cfg.signal_generation || {};
  const stratName = String(sg.strategy || cfg.strategy_pack || 'SMA_CROSS').toUpperCase();
  const trend = sg.trend || sg.sma || sg.ema || {};
  const row = state.active_result || {};
  const art = state.active_artifacts || {};
  const p = art.perf || {};
  const rmUni = (art.run_meta || {}).universe;
  const symbols = (rmUni && rmUni.raw_count != null) ? rmUni.raw_count : (Array.isArray(u.symbols) ? u.symbols.length : 0);

  setTextById(
    'wbSummaryUniverse',
    `区间 ${u.start || '-'} ~ ${u.end || '-'} | 基准 ${u.benchmark || '-'} | 标的 ${symbols} 个`
  );
  let stratSummary;
  const regimeOn = sg.regime_detection?.enabled;
  if (regimeOn) {
    const mr = sg.mr || {};
    const trendName = (trend.strategy || 'SMA').toUpperCase();
    const rfOn = sg.regime_detection?.regime_filter?.enabled;
    const rfTag = rfOn ? ` | RF=ON(thr=${sg.regime_detection.regime_filter.regime_threshold ?? 0.3})` : '';
    stratSummary = `REGIME | 趋势:${trendName} ${trend.fast_ma ?? 20}/${trend.slow_ma ?? 60} | MR:RSI(${mr.rsi_period ?? 6}) ${mr.rsi_buy_threshold ?? 20}/${mr.rsi_sell_threshold ?? 80} | regime_ma=${sg.regime_detection?.regime_ma ?? 60}${rfTag} | 最大持仓=${cfg?.position_risk?.max_positions ?? '-'}`;
  } else {
    const trendName = (trend.strategy || stratName).toUpperCase();
    stratSummary = `${trendName} | 快线=${trend.fast_ma ?? '-'} 慢线=${trend.slow_ma ?? '-'} | 最大持仓=${cfg?.position_risk?.max_positions ?? '-'}`;
  }
  setTextById('wbSummaryStrategy', stratSummary);
  const flow = `接口状态 验证=${_apiTag('validate_data')} 运行=${_apiTag('experiment_run_async')} 轮询=${_apiTag('job_poll')} 产物=${_apiTag('artifact_read_nav')} 基准=${_apiTag('series_benchmark')} 执行=${_apiTag('execution_preview')}`;
  const stat = row.exp_id
    ? `实验=${row.exp_id} | 状态=${row.status || '-'} | 年化=${pct(p.cagr ?? row.cagr)} | 回撤=${pct(p.max_drawdown ?? row.max_drawdown)} | 夏普=${num(p.sharpe ?? row.sharpe, 2)} | ${flow}`
    : `等待运行结果... | ${flow}`;
  setTextById('wbSummaryTrade', stat);
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

  // 价格口径
  const loadedAdj = u.price_adj || 'hfq';
  _set('wbPriceAdj', loadedAdj);
  document.querySelectorAll('#wbAdjGroup button').forEach(b => {
    b.classList.toggle('active', b.getAttribute('data-val') === loadedAdj);
  });

  // --- 信号生成: 新结构 (regime_detection + trend + mr) ---
  const sgCfg = cfg?.signal_generation || {};
  const strategyName = String(sgCfg.strategy || cfg?.strategy_pack || 'SMA_CROSS').toUpperCase();

  // 兼容旧 adaptive_regime 格式 → 转换为新结构
  const oldAr = sgCfg.adaptive_regime || {};
  const hasOldAr = strategyName === 'ADAPTIVE_REGIME' && (oldAr.regime_ma || oldAr.rsi_period);

  // Regime detection
  const rd = sgCfg.regime_detection || {};
  const regimeOn = hasOldAr ? true : !!rd.enabled;
  _chk('wbRegimeEnabled', regimeOn);
  _set('wbRegimeMa', hasOldAr ? (oldAr.regime_ma ?? 60) : (rd.regime_ma ?? 60));
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
  const trendName = hasOldAr ? 'EMA_CROSS' : (trend.strategy || strategyName || 'EMA_CROSS');
  _set('wbTrendStrategy', trendName);
  _set('wbFastMa', hasOldAr ? (oldAr.fast_ma ?? 20) : (trend.fast_ma ?? sgCfg.sma?.fast_ma ?? 20));
  _set('wbSlowMa', hasOldAr ? (oldAr.slow_ma ?? 60) : (trend.slow_ma ?? sgCfg.sma?.slow_ma ?? 60));
  _set('wbEntryBuffer', trend.entry_buffer_pct ?? sgCfg.sma?.entry_buffer_pct ?? 1);

  // MR strategy
  const mr = sgCfg.mr || {};
  _set('wbMrStrategy', mr.strategy || 'RSI_REVERSAL');
  _set('wbMrRsiPeriod', hasOldAr ? (oldAr.rsi_period ?? 6) : (mr.rsi_period ?? 6));
  _set('wbMrRsiBuy', hasOldAr ? (oldAr.rsi_buy_threshold ?? 20) : (mr.rsi_buy_threshold ?? 20));
  _set('wbMrRsiSell', hasOldAr ? (oldAr.rsi_sell_threshold ?? 80) : (mr.rsi_sell_threshold ?? 80));
  _set('wbMrMaxHold', hasOldAr ? (oldAr.mr_max_hold_days ?? 5) : (mr.mr_max_hold_days ?? 5));
  const mrStopRaw = hasOldAr ? oldAr.mr_stop_loss_pct : mr.mr_stop_loss_pct;
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

  const pr = cfg?.position_risk || {};
  _set('wbMaxPositions', pr.max_positions);
  _set('wbSingleCap', pr.single_stock_cap != null ? Number(pr.single_stock_cap) * 100 : undefined);
  _set('wbIndustryCap', pr.industry_cap != null ? Number(pr.industry_cap) * 100 : undefined);
  _set('wbLot', pr.lot);
  _set('wbCashPolicy', pr.cash_shortage_policy);
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
}

async function loadConfig(configId) {
  const j = await apiRequestJson('configs_get', `/api/backtest_v2/configs/${encodeURIComponent(configId)}`);
  state.config_id = j.config_id;
  byId('wbConfigId').textContent = j.config_id;
  applyConfigToUI(j.config_json || {});
  addLog(`已加载配置: ${j.config_id}`);
}

async function loadConfigList() {
  const j = await apiRequestJson('configs_list', '/api/backtest_v2/configs?latest=20');
  const items = Array.isArray(j.items) ? j.items : [];
  const sel = byId('wbConfigList');
  if (!sel) return;
  sel.innerHTML = '<option value="">选择配置...</option>' + items.map((x) => {
    const tags = Array.isArray(x.tags) ? x.tags.map((t) => String(t)) : [];
    const prefix = tags.includes('flow_script') ? '[通流脚本] ' : '';
    const name = x.name ? ` | ${x.name}` : '';
    return `<option value="${esc(x.config_id)}">${esc(prefix + x.config_id)}${esc(name)} | ${esc(x.saved_at || '')}</option>`;
  }).join('');
}

async function previewExecution() {
  buildConfigDraft();
  const body = {
    config_id: state.config_id,
    config_json: state.config_draft,
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
    addLog('已从剪贴板粘贴配置JSON');
  } catch (e) {
    addLog(`粘贴JSON失败: ${e.message || e}`);
  }
}

function switchInspectorTab(tab) {
  if (tab === 'perf' || tab === 'runner') return switchDockTab('explain');
  if (tab === 'explain') return switchDockTab('explain');
  if (tab === 'exec' || tab === 'execution') return switchDockTab('execution');
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
