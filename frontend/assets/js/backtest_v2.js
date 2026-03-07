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
  config_draft: {},
  universe_stats: null,
  active_exp: null,
  active_result: null,
  active_artifacts: null,
  execution_preview: null,
  execution_api_enabled: true,
  status_items: [],
  manual_status_items: [],
  api_status: {},
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

const COMPOSE_MODULES = ['Regime', 'Trend Quality', 'Strength Rank', 'MF Rank', 'Risk Gate'];

function byId(id) { return document.getElementById(id); }
function getStrategySelector() { return byId('wbTrendStrategy') || byId('wbStrategyPack') || byId('wbStrategyFamily'); }
function getStrategyPackValue() {
  const regimeOn = !!byId('wbRegimeEnabled')?.checked;
  if (regimeOn) return 'REGIME_ROUTER';
  return (byId('wbTrendStrategy') || byId('wbStrategyPack') || byId('wbStrategyFamily'))?.value || 'EMA_CROSS';
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

const LEGACY_ARTIFACT_FALLBACKS = {
  reason_codes: ['reason_code_counts.csv'],
};

const COUNTER_LEGACY_ALIASES = {
  raw_signal: ['raw_signal_count'],
  blocked: ['blocked_count'],
  orders: ['orders_count'],
  skipped: ['skipped_count'],
  closed_trades: ['closed_trades_count'],
};

function todayISO() { return new Date().toISOString().slice(0, 10); }

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

/* ── 主 Tab 切换 ── */

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
  renderSummaryBar();
  renderPerfPanel();
  renderExplainPanel();
  renderExecutionPanel();
}

function renderArtifacts(result) {
  const files = result?.files || {};
  byId('wbArtifacts').innerHTML = `exp_id=${esc(result?.exp_id || '-')}<br>results_dir=<span class="wb-code">${esc(result?.results_dir || '-')}</span><br>manifest=${esc(files.manifest || '-')}`;
}

async function saveConfig(kind = 'draft') {
  const cfg = buildConfigDraft();
  const body = { config_json: cfg, name: 'workbench', tags: ['draft'] };
  if (kind === 'template') {
    body.name = `template_${Date.now()}`;
    body.tags = ['template'];
  } else if (kind === 'flow_script') {
    body.name = `flow_script_${Date.now()}`;
    body.tags = ['flow_script'];
  }
  const j = await apiRequestJson('configs_save', '/api/backtest_v2/configs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  state.config_id = j.config_id;
  byId('wbConfigId').textContent = j.config_id;
  addLog(`配置已保存(${kind}): ${j.config_id}`);
  await loadConfigList();
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

  byId('wbValidateBtn')?.addEventListener('click', async () => {
    try { await doValidate(); } catch (e) { byId('wbRunStatus').textContent = `validate失败: ${e.message || e}`; addLog(String(e)); }
  });
  byId('wbRunBtn')?.addEventListener('click', async () => {
    try { setStatusItems([]); await runByMode(); } catch (e) {
      const msg = e.message || String(e);
      byId('wbRunStatus').textContent = `运行失败: ${msg}`;
      addLog(String(e));
      setStatusItems([{ title: '运行失败', message: msg, detail: String(e) }]);
    }
  });
  byId('wbRunPreset')?.addEventListener('click', async () => {
    try { setStatusItems([]); await runExperiment(); } catch (e) {
      const msg = e.message || String(e);
      byId('wbRunStatus').textContent = `预设运行失败: ${msg}`;
      addLog(String(e));
      setStatusItems([{ title: '预设运行失败', message: msg, detail: String(e) }]);
    }
  });

  byId('wbSaveConfig')?.addEventListener('click', async () => { try { await saveConfig('draft'); } catch (e) { addLog(`保存失败: ${e.message || e}`); } });
  byId('wbSaveTemplate')?.addEventListener('click', async () => { try { await saveConfig('template'); } catch (e) { addLog(`模板保存失败: ${e.message || e}`); } });
  byId('wbSaveFlowScript')?.addEventListener('click', async () => { try { await saveConfig('flow_script'); } catch (e) { addLog(`通流脚本保存失败: ${e.message || e}`); } });
  byId('wbQuickSave')?.addEventListener('click', async () => { try { await saveConfig('draft'); } catch (e) { addLog(`保存失败: ${e.message || e}`); } });
  byId('wbQuickLoad')?.addEventListener('click', async (evt) => {
    evt.stopPropagation();
    const existing = document.getElementById('wbLoadDropdown');
    if (existing) { existing.remove(); return; }
    try {
      const j = await apiRequestJson('configs_list', '/api/backtest_v2/configs?latest=20');
      const items = Array.isArray(j.items) ? j.items : [];
      if (!items.length) { addLog('没有可加载的配置'); return; }
      const dd = document.createElement('div');
      dd.id = 'wbLoadDropdown';
      dd.className = 'wb-load-dropdown';
      items.forEach((x) => {
        const tags = Array.isArray(x.tags) ? x.tags.map((t) => String(t)) : [];
        const isFlow = tags.includes('flow_script');
        const row = document.createElement('div');
        row.className = 'wb-load-item' + (isFlow ? ' wb-load-flow' : '');
        row.textContent = (isFlow ? '[通流] ' : '') + (x.name || x.config_id);
        row.addEventListener('click', async () => {
          dd.remove();
          try { await loadConfig(x.config_id); } catch (e2) { addLog(`加载失败: ${e2.message || e2}`); }
        });
        dd.appendChild(row);
      });
      byId('wbQuickLoad').parentElement.appendChild(dd);
      const dismiss = (e) => { if (!dd.contains(e.target) && e.target !== byId('wbQuickLoad')) { dd.remove(); document.removeEventListener('click', dismiss); } };
      setTimeout(() => document.addEventListener('click', dismiss), 0);
    } catch (e) { addLog(`加载失败: ${e.message || e}`); }
  });
  byId('wbCopyCfgJson')?.addEventListener('click', copyConfigJson);
  byId('wbPasteCfgJson')?.addEventListener('click', pasteConfigJson);
  byId('wbDiffCfg')?.addEventListener('click', renderConfigDiff);

  byId('wbLoadLatest')?.addEventListener('click', async () => {
    try {
      await loadConfigList();
      const options = Array.from(byId('wbConfigList')?.options || []);
      const firstNonEmpty = options.find((opt) => (opt.value || '').trim());
      if (firstNonEmpty?.value) await loadConfig(firstNonEmpty.value);
    } catch (e) { addLog(`加载失败: ${e.message || e}`); }
  });
  byId('wbConfigList')?.addEventListener('change', async (ev) => {
    const id = ev.target.value;
    if (!id) return;
    try { await loadConfig(id); } catch (e) { addLog(`加载失败: ${e.message || e}`); }
  });

  byId('wbApplyGroup')?.addEventListener('click', async () => {
    const cfg = state.active_artifacts?.config;
    if (!cfg) { addLog('当前结果缺少config.json'); return; }
    const draft = cfg?.overrides?.workbench_config || cfg?.workbench_config || cfg;
    applyConfigToUI(draft || {});
    addLog(`已应用 exp_id=${state.active_result?.exp_id || '-'} 配置`);
  });

  document.querySelectorAll('.wb-main-tabs button[data-main-tab]').forEach((btn) => btn.addEventListener('click', () => switchMainTab(btn.getAttribute('data-main-tab') || 'overview')));
  document.querySelectorAll('.wb-analysis-tabs button[data-dock]').forEach((btn) => btn.addEventListener('click', () => switchDockTab(btn.getAttribute('data-dock') || 'explain')));
  byId('wbPreviewExec')?.addEventListener('click', async () => { try { await previewExecution(); } catch (e) { addLog(`execution失败: ${e.message || e}`); } });
  byId('wbCopyExec')?.addEventListener('click', copyExecJson);
  byId('wbChartMode')?.addEventListener('change', (e) => {
    state.chart_mode = String(e.target.value || 'portfolio');
    renderPerfPanel();
  });
  byId('wbChartBenchToggle')?.addEventListener('change', (e) => { state.chart_show_benchmark = !!e.target.checked; renderPerfPanel(); });
  byId('wbChartRange')?.addEventListener('change', (e) => { state.chart_range = String(e.target.value || 'ALL'); renderPerfPanel(); });
  byId('wbSymbolFilter')?.addEventListener('input', (e) => {
    state.symbol_filter = String(e.target.value || '').trim();
    renderSymbolPerformancePanel();
  });
  byId('wbSymbolSort')?.addEventListener('change', (e) => {
    state.symbol_sort = String(e.target.value || 'return_desc');
    renderSymbolPerformancePanel();
  });
  byId('wbChartExport')?.addEventListener('click', () => {
    const payload = {
      exp_id: state.active_result?.exp_id || null,
      nav_points: state.active_artifacts?.navSeries?.length || 0,
      drawdown_points: state.active_artifacts?.drawdownSeries?.length || 0,
      range: state.chart_range,
      mode: state.chart_mode,
      symbol: state.selected_symbol || null,
    };
    navigator.clipboard?.writeText(JSON.stringify(payload, null, 2));
    addLog('图表摘要已复制');
  });
  byId('wbExportReport')?.addEventListener('click', () => { generateReport().catch((e) => addLog(`报告生成失败: ${e}`)); });
  byId('wbStatusBell')?.addEventListener('click', () => toggleStatusPanel());
  byId('wbErrorBannerView')?.addEventListener('click', () => toggleStatusPanel(true));
  byId('wbStatusCopy')?.addEventListener('click', () => {
    const rd = state.active_exp?.results_dir || '';
    if (rd) {
      navigator.clipboard?.writeText(rd);
      addLog(`results_dir 已复制: ${rd}`);
    }
  });
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

  // Exit checkbox ↔ input linkage
  byId('wbExitTrail')?.addEventListener('change', syncExitLinkage);
  byId('wbExitTime')?.addEventListener('change', syncExitLinkage);

  // ATR note updates when price adj / match price changes
  byId('wbPriceAdj')?.addEventListener('change', updateAtrNote);
  byId('wbMatchPrice')?.addEventListener('change', updateAtrNote);
}

function init() {
  setActiveNav();
  hydrateComposeRows(defaultComposeRows());
  byId('wbExecDate').value = todayISO();
  byId('wbChartBenchToggle').checked = true;
  byId('wbChartRange').value = 'D';
  if (byId('wbChartMode')) byId('wbChartMode').value = 'portfolio';
  if (byId('wbSymbolSort')) byId('wbSymbolSort').value = 'return_desc';
  bindEvents();
  setDrawerPanel('s1');
  switchMainTab('overview');
  switchDockTab('explain');
  updateUniverseInputVisibility();
  renderRunHints();
  buildConfigDraft();
  syncExitLinkage();
  updateAtrNote();
  setStatusItems([]);
  loadConfigList().catch((e) => { addLog(`加载配置列表失败: ${e?.message || e}`); });
  renderRightInspector();
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
    const label = esc(exp.label || exp.exp_id || '-');
    const expId = esc(exp.exp_id || '');
    const totalReturn = pct(exp.total_return);
    const maxDd = pct(exp.max_drawdown);
    const sharpe = num(exp.sharpe, 2);
    const trades = fmtInt(exp.trades);
    const trClass = Number(exp.total_return) >= 0 ? 'wb-green-text' : 'wb-red-text';
    const ddClass = 'wb-red-text';
    const created = exp.created_at ? exp.created_at.replace('T', ' ').slice(0, 16) : '-';
    const reportBtn = exp.has_report
      ? `<button class="pill wb-hc-report" data-exp="${expId}">查看报告</button>`
      : '';
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
        ${reportBtn}
        <button class="pill wb-hc-load" data-exp="${expId}">加载结果</button>
      </div>
      <div class="wb-hc-time">${created}</div>
    </div>`;
  }).join('');

  // Bind report buttons
  container.querySelectorAll('.wb-hc-report').forEach((btn) => btn.addEventListener('click', (ev) => {
    ev.stopPropagation();
    const expId = btn.getAttribute('data-exp');
    window.open(`/api/backtest_v2/experiments/${encodeURIComponent(expId)}/report`, '_blank');
  }));

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
  const resultsDir = `experiments/${expId}`;
  // Build a minimal result object so loadActiveArtifacts can work
  const fakeResult = {
    exp_id: expId,
    results_dir: resultsDir,
    status: 'OK',
    artifacts: {
      perf: 'perf.json',
      nav: 'nav.csv',
      funnel: 'funnel.csv',
      reason_codes: 'reason_codes.csv',
      run_meta: 'run_meta.json',
      config: 'config.json',
      stock_names: 'stock_names.json',
      symbol_performance: 'symbol_performance.csv',
      trades: 'portfolio_trades.csv',
      daily: 'portfolio_daily.csv',
    },
  };
  state.active_exp = fakeResult;
  state.active_result = fakeResult;
  await loadActiveArtifacts();
  renderRightInspector();
  addLog(`已加载历史实验: ${expId}`);
}
