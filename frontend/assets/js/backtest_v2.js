
import { setActiveNav } from './ui.js';

const state = {
  mode: 'experiment',
  strategy_pack: 'SMA_CROSS',
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
  drawer_panel: 'universe',
  drawer_pinned: false,
  dock_tab: 'explain',
  chart_show_benchmark: true,
  chart_range: 'D',
};

const COMPOSE_MODULES = ['Regime', 'Trend Quality', 'Strength Rank', 'MF Rank', 'Risk Gate'];

function byId(id) { return document.getElementById(id); }
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
  SIGNAL_REVERSE: '信号反转', ATR_STOP_LOSS: 'ATR止损',
  ATR_TRAIL_STOP: 'ATR追踪止损', TIME_EXIT: '到期平仓',
  TREND_REVERSE: '趋势反转', TREND_BREAK_EXIT: '趋势破位平仓',
  RISK_OFF_EXIT: '风控平仓', MANUAL_CLOSE: '手动平仓',
  MAX_HOLD_DAYS: '持仓到期', TAKE_PROFIT: '止盈',
  STOP_LOSS: '止损',
};
function reasonZh(code) { return REASON_MAP[code] || String(code ?? ''); }

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

function _apiFailureItems() {
  return Object.values(state.api_status || {})
    .filter((x) => x && x.status === 'failed')
    .map((x) => ({
      title: `接口失败: ${x.key || ''}`,
      message: `${x.method || 'GET'} ${x.endpoint || ''} -> ${x.httpStatus || '-'}`,
      file: String(x.endpoint || ''),
      detail: String(x.error || '未知错误'),
    }));
}

function _mergeStatusItems(manualItems) {
  const manual = Array.isArray(manualItems) ? manualItems : [];
  return [...manual, ..._apiFailureItems()];
}

function _upsertApiStatus(key, patch) {
  const prev = state.api_status[key] || {};
  state.api_status[key] = {
    key,
    ...prev,
    ...patch,
    updatedAt: new Date().toISOString(),
  };
}

function _setApiLoading(key, endpoint, method = 'GET') {
  _upsertApiStatus(key, { status: 'loading', endpoint, method, error: '' });
}

function _setApiSuccess(key, endpoint, method, httpStatus, durationMs) {
  _upsertApiStatus(key, { status: 'success', endpoint, method, httpStatus, durationMs, error: '' });
}

function _setApiFailed(key, endpoint, method, httpStatus, durationMs, errorText) {
  _upsertApiStatus(key, { status: 'failed', endpoint, method, httpStatus, durationMs, error: String(errorText || '未知错误') });
}

function _apiTag(key) {
  const s = state.api_status?.[key];
  if (!s || !s.status) return 'not_requested';
  return s.status;
}

async function _readHttpErrorDetail(response) {
  try {
    const obj = await response.json();
    if (obj && typeof obj === 'object') return String(obj.detail || obj.message || JSON.stringify(obj));
  } catch (_) {
    // ignore json parse errors
  }
  return `${response.status} ${response.statusText}`;
}

async function apiRequestJson(key, url, options = {}) {
  const method = String(options.method || 'GET').toUpperCase();
  const startedAt = Date.now();
  _setApiLoading(key, url, method);
  try {
    const r = await fetch(url, options);
    const durationMs = Date.now() - startedAt;
    if (!r.ok) {
      const detail = await _readHttpErrorDetail(r);
      _setApiFailed(key, url, method, r.status, durationMs, detail);
      const err = new Error(`${r.status} ${detail}`);
      err.httpStatus = r.status;
      err.endpoint = url;
      throw err;
    }
    const payload = await r.json();
    _setApiSuccess(key, url, method, r.status, durationMs);
    setStatusItems(state.manual_status_items || []);
    return payload;
  } catch (e) {
    const durationMs = Date.now() - startedAt;
    if (!state.api_status[key] || state.api_status[key].status !== 'failed') {
      _setApiFailed(key, url, method, null, durationMs, e?.message || String(e));
    }
    setStatusItems(state.manual_status_items || []);
    throw e;
  }
}

function setStatusItems(items) {
  state.manual_status_items = Array.isArray(items) ? items : [];
  state.status_items = _mergeStatusItems(state.manual_status_items);
  const count = state.status_items.length;
  const countEl = byId('wbStatusCount');
  if (countEl) {
    countEl.textContent = String(count);
    countEl.hidden = count === 0;
  }

  const bell = byId('wbStatusBell');
  if (bell) {
    bell.classList.remove('wb-bell-ok', 'wb-bell-error');
    bell.classList.add(count > 0 ? 'wb-bell-error' : 'wb-bell-ok');
  }

  const listEl = byId('wbStatusList');
  if (listEl) {
    if (!count) {
      listEl.innerHTML = '<div class="wb-status-item">暂无错误状态</div>';
    } else {
      listEl.innerHTML = state.status_items.map((x) => {
        const file = String(x.file || '');
        const detail = String(x.detail || '');
        const tip = file.startsWith('/app/outputs') ? '<div class="wb-mini">浏览器不可直连容器内 /app/outputs</div>' : '';
        const detailHtml = detail ? `<div class="wb-code wb-mini" style="color:var(--wb-red);margin-top:4px">${esc(detail)}</div>` : '';
        return `<div class="wb-status-item"><div><strong>${esc(x.title || '状态')}</strong></div><div class="wb-mini">${esc(x.message || '')}</div><div class="wb-code wb-mini">${esc(file)}</div>${detailHtml}${tip}</div>`;
      }).join('');
    }
  }

  const banner = byId('wbErrorBanner');
  const bannerText = byId('wbErrorBannerText');
  if (banner && bannerText) {
    if (!count) {
      banner.hidden = true;
      bannerText.textContent = '';
    } else {
      const top = state.status_items[0];
      banner.hidden = false;
      bannerText.textContent = `${top.title || '错误'}: ${top.message || top.file || '未知'}`;
    }
  }

  if (count > 0) toggleStatusPanel(true);
}

function toggleStatusPanel(force = null) {
  const panel = byId('wbStatusPanel');
  if (!panel) return;
  state.status_open = force == null ? !state.status_open : !!force;
  panel.hidden = !state.status_open;
}

function updateUniverseInputVisibility() {
  const mode = byId('wbUniverseMode')?.value || 'ALL_A';
  const wrap = byId('wbSymbolsWrap');
  if (wrap) wrap.style.display = mode === 'CUSTOM' ? '' : 'none';
}

function setDrawerPanel(panel) {
  state.drawer_panel = panel || 'universe';
  document.querySelectorAll('.wb-rail-btn').forEach((btn) => btn.classList.toggle('active', btn.getAttribute('data-panel') === state.drawer_panel));
  document.querySelectorAll('.wb-module').forEach((m) => m.classList.toggle('active', m.getAttribute('data-module') === state.drawer_panel));
  const titleEl = byId('wbDrawerTitle');
  if (titleEl) {
    const titles = { universe: 'Universe', signal: 'Signal', compose: 'Composition', risk: 'Risk & Exit', json: 'JSON' };
    titleEl.textContent = titles[state.drawer_panel] || state.drawer_panel;
  }
}

function toggleDrawer(force = null) {
  const app = document.querySelector('.wb-app');
  if (!app) return;
  const hide = force == null ? !app.classList.contains('wb-drawer-hidden') : !!force;
  app.classList.toggle('wb-drawer-hidden', hide);
}

function filterSeriesByRange(points, range) {
  const arr = Array.isArray(points) ? points : [];
  if (!arr.length || !range || range === 'ALL' || range === 'D') return arr;
  const n = range === '1M' ? 22 : (range === '3M' ? 66 : (range === '1Y' ? 252 : arr.length));
  return arr.slice(Math.max(0, arr.length - n));
}

// 将日线 OHLC 聚合为周线/月线/年线
function aggregateOhlc(dailyOhlc, period) {
  if (!dailyOhlc?.length || !period || period === 'D') return dailyOhlc;
  const buckets = new Map();
  for (const bar of dailyOhlc) {
    const d = bar.time; // 'YYYY-MM-DD'
    let key;
    if (period === 'W') {
      // 按周聚合：算出周一的日期作为 key
      const dt = new Date(d + 'T00:00:00');
      const day = dt.getDay();
      const mon = new Date(dt);
      mon.setDate(dt.getDate() - ((day + 6) % 7));
      key = mon.toISOString().slice(0, 10);
    } else if (period === 'M') {
      key = d.slice(0, 7) + '-01'; // YYYY-MM-01
    } else if (period === 'Y') {
      key = d.slice(0, 4) + '-01-01'; // YYYY-01-01
    } else {
      return dailyOhlc;
    }
    if (!buckets.has(key)) {
      buckets.set(key, { time: key, open: bar.open, high: bar.high, low: bar.low, close: bar.close });
    } else {
      const b = buckets.get(key);
      if (bar.high > b.high) b.high = bar.high;
      if (bar.low < b.low) b.low = bar.low;
      b.close = bar.close; // 最后一天的 close
    }
  }
  return [...buckets.values()];
}

// 将日线 NAV 聚合为周线/月线/年线（取每个周期最后一个值）
function aggregateNav(dailyNav, period) {
  if (!dailyNav?.length || !period || period === 'D') return dailyNav;
  const buckets = new Map();
  for (const pt of dailyNav) {
    const d = pt.date || pt.time;
    let key;
    if (period === 'W') {
      const dt = new Date(d + 'T00:00:00');
      const day = dt.getDay();
      const mon = new Date(dt);
      mon.setDate(dt.getDate() - ((day + 6) % 7));
      key = mon.toISOString().slice(0, 10);
    } else if (period === 'M') {
      key = d.slice(0, 7) + '-01';
    } else if (period === 'Y') {
      key = d.slice(0, 4) + '-01-01';
    } else {
      return dailyNav;
    }
    buckets.set(key, { date: key, value: pt.value }); // 覆盖为最后一天的值
  }
  return [...buckets.values()];
}

function switchDockTab(tab) {
  const next = tab || 'explain';
  state.dock_tab = next;
  document.querySelectorAll('.wb-dock-tabs button[data-dock]').forEach((b) => b.classList.toggle('active', b.getAttribute('data-dock') === next));
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
  const fast = Number(draft?.signal_generation?.sma?.fast_ma);
  const slow = Number(draft?.signal_generation?.sma?.slow_ma);
  if (!(Number.isFinite(fast) && Number.isFinite(slow) && fast < slow)) errors.push('fast_ma 必须小于 slow_ma');
  const maxPos = Number(draft?.position_risk?.max_positions);
  if (!(Number.isFinite(maxPos) && maxPos > 0)) errors.push('max_positions 必须 > 0');
  const singlePct = Number(draft?.position_risk?.single_stock_cap) * 100;
  if (!(Number.isFinite(singlePct) && singlePct >= 0 && singlePct <= 100)) errors.push('单票上限% 必须在 0-100');
  const indPct = Number(draft?.position_risk?.industry_cap) * 100;
  if (!(Number.isFinite(indPct) && indPct >= 0 && indPct <= 100)) errors.push('行业上限% 必须在 0-100');
  const entry = Number(draft?.signal_generation?.sma?.entry_buffer_pct);
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
    strategy_pack: byId('wbStrategyPack')?.value || 'SMA_CROSS',
    universe_mode: byId('wbUniverseMode')?.value || 'ALL_A',
    universe: {
      start: byId('wbStartDate')?.value || '2021-01-01',
      end: byId('wbEndDate')?.value || '2026-02-01',
      benchmark: byId('wbBenchmark')?.value || '000300.SH',
      symbols: (byId('wbSymbols')?.value || '').split(',').map((s) => s.trim()).filter(Boolean),
      limit: Number(byId('wbUniverseLimit')?.value || 1000),
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
      strategy: byId('wbStrategyPack')?.value || 'SMA_CROSS',
      sma: {
        fast_ma: Number(byId('wbFastMa')?.value || 5),
        slow_ma: Number(byId('wbSlowMa')?.value || 20),
        entry_buffer_pct: Number(byId('wbEntryBuffer')?.value || 1),
      },
      breakout: { lookback: 20, breakout_buffer_pct: 1 },
      mean_reversion: { lookback: 20, zscore_entry: 2, zscore_exit: 0.5 },
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
    },
    position_risk: {
      enabled: !!byId('wbEnableRisk')?.checked,
      max_positions: Number(byId('wbMaxPositions')?.value || 10),
      single_stock_cap: Number(byId('wbSingleCap')?.value || 10) / 100,
      industry_cap: Number(byId('wbIndustryCap')?.value || 30) / 100,
      lot: Number(byId('wbLot')?.value || 100),
      cash_shortage_policy: byId('wbCashPolicy')?.value || 'skip',
      cost_model: {
        commission: 'fixed_assumption',
        stamp_tax: 'fixed_assumption',
        slippage: 'fixed_assumption',
        matching: 'next_open',
      },
    },
    risk_gate: {
      enabled: !!byId('wbRiskGateEnabled')?.checked,
      drawdown_threshold: Number(byId('wbRiskGateThreshold')?.value || -10) / 100,
      action: byId('wbRiskGateAction')?.value || 'reduce',
      cooldown_days: Number(byId('wbRiskGateCooldown')?.value || 5),
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
  if (mode === 'HS300') return ['600519.SH', '601318.SH', '000001.SZ'];
  if (mode === 'ZZ500') return ['300750.SZ', '002415.SZ', '601012.SH'];
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
    for (let i = 0; i < 900; i += 1) {
      if (canceled) {
        byId('wbRunStatus').textContent = '已取消';
        return null;
      }
      const j = await apiRequestJson('job_poll', `/api/backtest_v2/jobs/${encodeURIComponent(jobId)}`);
      byId('wbRunStatus').textContent = `${j.status} ${j.progress_pct ?? 0}% ${j.message || ''}`;
      if (j.status === 'success') return j.result || null;
      if (j.status === 'failed') throw new Error(j.error || 'job failed');
      if (j.status === 'canceled') { byId('wbRunStatus').textContent = '已取消'; return null; }
      await new Promise((resolve) => setTimeout(resolve, 800));
    }
    throw new Error('job timeout');
  } finally {
    if (typeof _cleanupCancel === 'function') _cleanupCancel();
  }
}
function runPayloadFromDraft(preset) {
  const d = buildConfigDraft();
  return {
    preset,
    start_date: d.universe.start,
    end_date: d.universe.end,
    benchmark: d.universe.benchmark,
    compare_symbol: '000001.SH',
    symbols: d.universe.symbols,
    universe_limit: d.universe.limit,
    max_positions: d.position_risk.max_positions,
    lot_size: d.position_risk.lot,
    config_id: state.config_id,
    workbench_mode: state.mode,
    workbench_config: d,
    fast_mode: true,
  };
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
  const sma = sg.sma || {};
  const row = state.active_result || {};
  const art = state.active_artifacts || {};
  const p = art.perf || {};
  const symbols = Array.isArray(u.symbols) ? u.symbols.length : 0;

  setTextById(
    'wbSummaryUniverse',
    `区间 ${u.start || '-'} ~ ${u.end || '-'} | 基准 ${u.benchmark || '-'} | 标的 ${symbols} 个`
  );
  setTextById(
    'wbSummaryStrategy',
    `${sg.strategy || cfg.strategy_pack || 'SMA_CROSS'} | 快线=${sma.fast_ma ?? '-'} 慢线=${sma.slow_ma ?? '-'} | 最大持仓=${cfg?.position_risk?.max_positions ?? '-'}`
  );
  const flow = `接口状态 验证=${_apiTag('validate_data')} 运行=${_apiTag('experiment_run_async')} 轮询=${_apiTag('job_poll')} 产物=${_apiTag('artifact_read_nav')} 基准=${_apiTag('series_benchmark')} 执行=${_apiTag('execution_preview')}`;
  const stat = row.exp_id
    ? `实验=${row.exp_id} | 状态=${row.status || '-'} | 年化=${pct(p.cagr ?? row.cagr)} | 回撤=${pct(p.max_drawdown ?? row.max_drawdown)} | 夏普=${num(p.sharpe ?? row.sharpe, 2)} | ${flow}`
    : `等待运行结果... | ${flow}`;
  setTextById('wbSummaryTrade', stat);
}

async function readArtifactWithStatus(resultsDir, relPath, keyName) {
  if (!relPath) return { ok: false, key: keyName, missing: true, error: `${keyName} 缺失` };
  let reqResultsDir = resultsDir;
  let reqRelPath = relPath;
  const relText = String(relPath);
  const isAbsPosix = relText.startsWith('/');
  const isAbsWin = /^[A-Za-z]:[\\/]/.test(relText);
  if (isAbsPosix || isAbsWin) {
    const normalized = relText.replaceAll('\\', '/');
    const idx = normalized.lastIndexOf('/');
    if (idx > 0) {
      reqResultsDir = normalized.slice(0, idx);
      reqRelPath = normalized.slice(idx + 1);
    }
  }
  try {
    const payload = await apiRequestJson(
      `artifact_read_${keyName}`,
      '/api/backtest_v2/artifacts/read',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ results_dir: reqResultsDir, rel_path: reqRelPath }),
      },
    );
    return { ok: true, key: keyName, relPath: reqRelPath, payload };
  } catch (e) {
    return { ok: false, key: keyName, missing: true, error: String(e?.message || e), relPath: reqRelPath };
  }
}

function normalizeNavRows(rows) {
  const out = [];
  (rows || []).forEach((r) => {
    const date = String(r.date ?? r.datetime ?? r.trade_date ?? '').trim();
    const nav = Number(r.nav ?? r.strategy_nav ?? r.equity ?? r.portfolio_value ?? r.value);
    if (!date || !Number.isFinite(nav) || nav <= 0) return;
    out.push({ date, nav });
  });
  out.sort((a, b) => (a.date < b.date ? -1 : 1));
  return out;
}

function computeDrawdownSeries(navRows) {
  let peak = null;
  const out = [];
  (navRows || []).forEach((r) => {
    const nav = Number(r.nav);
    if (!Number.isFinite(nav) || nav <= 0) return;
    peak = peak == null ? nav : Math.max(peak, nav);
    const dd = peak > 0 ? (nav - peak) / peak : 0;
    out.push({ date: r.date, value: dd });
  });
  return out;
}

async function loadBenchmarkSeries(navPoints) {
  // 总是走 API 获取真实数据库行情，不使用 artifact 预计算数据
  const symbol = state.config_draft?.universe?.benchmark || '000300.SH';
  const start = navPoints?.[0]?.date || state.config_draft?.universe?.start;
  const end = navPoints?.[navPoints.length - 1]?.date || state.config_draft?.universe?.end;
  const url = `/api/backtest_v2/series/benchmark?symbol=${encodeURIComponent(symbol)}&start=${encodeURIComponent(start || '')}&end=${encodeURIComponent(end || '')}`;
  try {
    const j = await apiRequestJson('series_benchmark', url);
    const raw = j?.points || [];
    const points = normalizeNavRows(raw.map((x) => ({ date: x.date, nav: x.nav })));
    // 保留 OHLC 数据供蜡烛图渲染
    const ohlc = raw.map((x) => ({
      time: x.date,
      open: x.open ?? x.nav,
      high: x.high ?? x.nav,
      low: x.low ?? x.nav,
      close: x.close ?? x.nav,
    }));
    return { points, ohlc, source: 'api' };
  } catch (e) {
    return { points: [], ohlc: [], source: 'api_failed', error: String(e?.message || e) };
  }
}

function renderLoadingSkeleton() {
  setHtmlById('wbGroupLoadStatus', '<span class="wb-mini">加载组产物中...</span>');
  // 清理 lightweight-charts 实例后再替换 innerHTML
  if (_lwChart) { _lwChart.remove(); _lwChart = null; }
  setHtmlById('wbNavChart', '<div class="wb-skeleton" style="height:100%"></div>');
  setHtmlById('wbDdChart', '<div class="wb-skeleton" style="height:100%"></div>');
}

function linePath(points, width, height, minY, maxY, pad) {
  if (!points.length) return '';
  const w = width - pad * 2;
  const h = height - pad * 2;
  const span = Math.max(maxY - minY, 1e-9);
  return points.map((p, i) => {
    const x = pad + (points.length <= 1 ? 0 : (i / (points.length - 1)) * w);
    const y = pad + (1 - (p.value - minY) / span) * h;
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(' ');
}

function renderLineChart(containerId, series, yFmt = (v) => num(v, 4)) {
  const container = byId(containerId);
  if (!container) return;
  const cleanSeries = (series || []).filter((s) => Array.isArray(s.points) && s.points.length);
  if (!cleanSeries.length) {
    const isMain = containerId === 'wbNavChart';
    const svgSize = isMain ? 48 : 32;
    container.innerHTML = `<div class="wb-empty"><svg width="${svgSize}" height="${svgSize}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg><span>${isMain ? '运行实验后显示净值曲线' : '回撤曲线'}</span></div>`;
    return;
  }
  const width = container.clientWidth || 600;
  const height = container.clientHeight || 280;
  const pad = 28;
  const values = cleanSeries.flatMap((s) => s.points.map((p) => Number(p.value)));
  const minY = Math.min(...values);
  const maxY = Math.max(...values);
  const y0 = Number.isFinite(minY) ? minY : 0;
  const y1 = Number.isFinite(maxY) ? maxY : 1;
  const legend = cleanSeries.map((s) => `<span style="display:inline-flex;align-items:center;gap:4px;margin-right:12px"><span style="display:inline-block;width:10px;height:2px;background:${s.color}"></span>${esc(s.name)}</span>`).join('');
  const paths = cleanSeries.map((s) => {
    const pts = s.points.map((p) => ({ value: Number(p.value) })).filter((p) => Number.isFinite(p.value));
    const d = linePath(pts, width, height, y0, y1, pad);
    return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2"/>`;
  }).join('');
  container.innerHTML = `
    <div class="wb-mini" style="margin-bottom:6px">${legend}</div>
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      <rect x="0" y="0" width="${width}" height="${height}" fill="transparent"/>
      <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="#334155" stroke-width="1"/>
      <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="#334155" stroke-width="1"/>
      ${paths}
      <text x="4" y="${pad}" fill="#94a3b8" font-size="11">${esc(yFmt(y1))}</text>
      <text x="4" y="${height - pad}" fill="#94a3b8" font-size="11">${esc(yFmt(y0))}</text>
    </svg>
  `;
}

// lightweight-charts 蜡烛图 + 折线叠加渲染
let _lwChart = null;
function renderNavChartLW(containerId, benchOhlc, navSeries, showBenchmark) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const hasNav = Array.isArray(navSeries) && navSeries.length > 0;
  const hasBench = Array.isArray(benchOhlc) && benchOhlc.length > 0;


  // 无任何数据时显示空状态
  if (!hasNav && !hasBench) {
    if (_lwChart) { _lwChart.remove(); _lwChart = null; }
    container.innerHTML = '<div class="wb-empty"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg><span>运行实验后显示净值曲线</span></div>';
    return;
  }

  // 清理旧实例
  if (_lwChart) { _lwChart.remove(); _lwChart = null; }
  container.innerHTML = '';

  const LWC = window.LightweightCharts;
  if (!LWC) {
    container.innerHTML = '<div class="wb-empty"><span>lightweight-charts 加载失败</span></div>';
    return;
  }

  const chart = LWC.createChart(container, {
    width: container.clientWidth,
    height: container.clientHeight || 420,
    layout: {
      background: { type: LWC.ColorType ? LWC.ColorType.Solid : 'solid', color: 'transparent' },
      textColor: '#94a3b8',
      fontSize: 11,
    },
    grid: {
      vertLines: { color: 'rgba(51,65,85,0.4)' },
      horzLines: { color: 'rgba(51,65,85,0.4)' },
    },
    crosshair: { mode: LWC.CrosshairMode ? LWC.CrosshairMode.Normal : 0 },
    rightPriceScale: { borderColor: '#334155' },
    timeScale: {
      borderColor: '#334155',
      timeVisible: false,
      barSpacing: 6,       // 默认蜡烛间距（像素），参考东方财富/同花顺
      minBarSpacing: 2,    // 缩放下限
      rightOffset: 5,      // 右侧留白
    },
  });
  _lwChart = chart;

  // Benchmark 蜡烛图（兼容 v4.0+ 和 v4.2+ API）
  if (showBenchmark && hasBench) {
    const candleSeries = typeof chart.addCandlestickSeries === 'function'
      ? chart.addCandlestickSeries({
          upColor: '#26a69a', downColor: '#ef5350',
          borderDownColor: '#ef5350', borderUpColor: '#26a69a',
          wickDownColor: '#ef5350', wickUpColor: '#26a69a',
        })
      : chart.addSeries(LWC.CandlestickSeries, {
          upColor: '#26a69a', downColor: '#ef5350',
          borderDownColor: '#ef5350', borderUpColor: '#26a69a',
          wickDownColor: '#ef5350', wickUpColor: '#26a69a',
        });
    candleSeries.setData(benchOhlc);
  }

  // Strategy NAV 折线（归一化后与 Benchmark 同量级）
  if (hasNav) {
    const lineSeries = typeof chart.addLineSeries === 'function'
      ? chart.addLineSeries({ color: '#58a6ff', lineWidth: 2, crosshairMarkerVisible: true, priceLineVisible: false })
      : chart.addSeries(LWC.LineSeries, { color: '#58a6ff', lineWidth: 2, crosshairMarkerVisible: true, priceLineVisible: false });
    // NAV 可能是原始组合价值（如 100000），需要归一化为从 1.0 开始
    const firstVal = navSeries[0]?.value || 1;
    const lineData = navSeries.map((p) => ({ time: p.date, value: p.value / firstVal }));
    lineSeries.setData(lineData);
  }

  // 数据量大时只显示最近一段，保证蜡烛清晰可见；数据少时全部显示
  const totalBars = Math.max(benchOhlc?.length || 0, navSeries?.length || 0);
  const chartWidth = container.clientWidth || 600;
  const maxVisibleBars = Math.floor(chartWidth / 6); // 6px 间距
  if (totalBars > maxVisibleBars) {
    chart.timeScale().scrollToPosition(5, false);
  } else {
    chart.timeScale().fitContent();
  }

  // 响应容器大小变化
  const ro = new ResizeObserver(() => {
    if (_lwChart === chart) {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight || 420 });
    }
  });
  ro.observe(container);
}

async function loadActiveArtifacts() {
  const resultsDir = state.active_exp?.results_dir;
  const result = state.active_result;
  if (!resultsDir || !result) return;
  state.active_artifacts = null;
  renderLoadingSkeleton();
  const gf = result.artifacts || {};
  const [perfR, navR, funnelR, reasonR, runMetaR, configR, tradesR, dailyR] = await Promise.all([
    readArtifactWithStatus(resultsDir, gf.perf, 'perf'),
    readArtifactWithStatus(resultsDir, gf.nav, 'nav'),
    readArtifactWithStatus(resultsDir, gf.funnel, 'funnel'),
    readArtifactWithStatus(resultsDir, gf.reason_codes, 'reason_codes'),
    readArtifactWithStatus(resultsDir, gf.run_meta, 'run_meta'),
    readArtifactWithStatus(resultsDir, gf.config, 'config'),
    gf.trades ? readArtifactWithStatus(resultsDir, gf.trades, 'trades') : Promise.resolve({ ok: false, key: 'trades', missing: true }),
    gf.daily ? readArtifactWithStatus(resultsDir, gf.daily, 'daily') : Promise.resolve({ ok: false, key: 'daily', missing: true }),
  ]);
  const allR = [perfR, navR, funnelR, reasonR, runMetaR, configR, tradesR, dailyR];
  const missing = allR.filter((x) => !x.ok).map((x) => x.key);
  const errors = allR.filter((x) => !x.ok && x.error).map((x) => `${x.key}: ${x.error}`);
  const statusItems = [perfR, navR, funnelR, reasonR, runMetaR, configR]
    .filter((x) => !x.ok)
    .map((x) => ({
      title: '产物缺失',
      message: `${x.key} 不可用`,
      file: String(x.relPath || x.key || ''),
      detail: String(x.error || ''),
    }));
  setStatusItems(statusItems);

  const navResolved = normalizeNavRows(navR.ok ? navR.payload?.rows || [] : []);
  const strategySeries = navResolved.map((x) => ({ date: x.date, value: x.nav }));
  const drawdownSeries = computeDrawdownSeries(navResolved);
  const benchmark = await loadBenchmarkSeries(navResolved);
  const benchmarkSeries = (benchmark.points || []).map((x) => ({ date: x.date, value: x.nav }));
  const benchmarkDd = computeDrawdownSeries((benchmark.points || []).map((x) => ({ date: x.date, nav: x.nav })));

  const tradesRows = tradesR.ok ? tradesR.payload?.rows || [] : [];
  state.active_artifacts = {
    perf: perfR.ok ? perfR.payload?.data || {} : {},
    nav: navResolved,
    navSeries: strategySeries,
    drawdownSeries,
    benchmarkSeries,
    benchmarkOhlc: benchmark.ohlc || [],
    benchmarkDrawdownSeries: benchmarkDd,
    benchmarkSource: benchmark.source,
    benchmarkError: benchmark.error || '',
    run_meta: runMetaR.ok ? runMetaR.payload?.data || {} : {},
    funnelRows: funnelR.ok ? funnelR.payload?.rows || [] : [],
    reasonRows: reasonR.ok ? reasonR.payload?.rows || [] : [],
    config: configR.ok ? configR.payload?.data || null : null,
    tradesRows,
    dailyRows: dailyR.ok ? dailyR.payload?.rows || [] : [],
    stockNames: {},
    missing,
    errors,
  };

  // Fetch Chinese stock names for trade symbols
  if (tradesRows.length) {
    const symbols = [...new Set(tradesRows.map((r) => String(r.symbol || '')).filter(Boolean))];
    if (symbols.length) {
      try {
        const resp = await fetch('/api/backtest_v2/stock_names', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ symbols }),
        });
        if (resp.ok) {
          const data = await resp.json();
          state.active_artifacts.stockNames = data.names || {};
        }
      } catch (_) { /* stock names are optional */ }
    }
  }

  refreshConfigPanels();
}

function reasonByPrefix(rows) {
  const out = { blocked: [], skipped: [], exit: [], other: [] };
  (rows || []).forEach((r) => {
    const code = String(r.code || '').toUpperCase();
    if (code.startsWith('BLOCKED_')) out.blocked.push(r);
    else if (code.startsWith('SKIPPED_')) out.skipped.push(r);
    else if (code.includes('EXIT') || code.includes('ATR_')) out.exit.push(r);
    else out.other.push(r);
  });
  Object.values(out).forEach((arr) => arr.sort((a, b) => Number(b.count || 0) - Number(a.count || 0)));
  return out;
}

function renderPerfPanel() {
  const row = state.active_result || {};
  const art = state.active_artifacts || {};
  const p = art.perf || {};
  const kpis = byId('wbPerfKpis');
  if (kpis) {
    const items = [
      ['年化收益', p.cagr ?? row.cagr, pct],
      ['最大回撤', p.max_drawdown ?? row.max_drawdown, pct],
      ['夏普比率', p.sharpe ?? row.sharpe, (v) => num(v, 2)],
      ['卡尔马比率', p.calmar ?? row.calmar, (v) => num(v, 2)],
      ['交易次数', p.trades ?? row.trades, fmtInt],
      ['换手率', p.turnover ?? row.turnover, pct],
      ['Top10集中度', p.top10_profit_concentration ?? row.top10_profit_concentration, pct],
      ['评级', row.tier, null],
    ];
    kpis.innerHTML = items.map(([k, v, fmt]) => `<div class="wb-kpi"><div class="wb-mini">${esc(k)}</div><div class="wb-code">${fmt && typeof v === 'number' ? fmt(v) : esc(String(v ?? '-'))}</div></div>`).join('');
  }

  const missingMsg = art?.missing?.length ? `缺失 ${art.missing.length} 个产物，详情见状态中心` : '产物已加载';
  setTextById('wbGroupLoadStatus', missingMsg);

  const period = state.chart_range; // D / W / M / Y

  // 按周期聚合 OHLC 和 NAV
  const benchOhlc = aggregateOhlc(art.benchmarkOhlc || [], period);
  const navSeries = aggregateNav(art.navSeries || [], period);
  const ddSeries = aggregateNav(art.drawdownSeries || [], period);
  const benchDdSeries = aggregateNav(art.benchmarkDrawdownSeries || [], period);

  // 主图：lightweight-charts 蜡烛图 + 折线叠加
  renderNavChartLW('wbNavChart', benchOhlc, navSeries, state.chart_show_benchmark);

  // 回撤图：保持 SVG 折线
  const ddPlot = [{ name: '策略回撤', color: '#ef4444', points: ddSeries }];
  if (state.chart_show_benchmark) {
    ddPlot.push({ name: '基准回撤', color: '#f97316', points: benchDdSeries });
  }
  renderLineChart('wbDdChart', [
    ...ddPlot,
  ], (v) => pct(v));

  const navInfo = navSeries.length ? `净值=${navSeries.length}点` : `净值缺失(${art.errors?.find((x) => String(x).startsWith('nav:')) || '未提供'})`;
  const bmInfo = art.benchmarkError ? `基准异常=${art.benchmarkError}` : `基准来源=${art.benchmarkSource || '无'}`;
  setHtmlById('wbPerfSeries', `${navInfo} | 回撤=${ddSeries.length}点 | ${bmInfo} ${state.chart_show_benchmark ? '' : '| 基准=关'}`);
}

function renderFunnelBars(funnel) {
  const keys = [
    ['原始信号', Number(funnel.raw_signal || 0)],
    ['被拦截', Number(funnel.blocked || 0)],
    ['下单', Number(funnel.orders || 0)],
    ['跳过', Number(funnel.skipped || 0)],
    ['已平仓', Number(funnel.closed_trades || 0)],
  ];
  const maxV = Math.max(...keys.map((x) => x[1]), 1);
  return keys.map(([k, v]) => `<div style="display:grid;grid-template-columns:110px 1fr 70px;gap:6px;align-items:center;margin-bottom:4px"><span>${k}</span><div class="wb-bar"><span style="width:${(v / maxV) * 100}%"></span></div><span class="wb-code">${num(v, 0)}</span></div>`).join('');
}

function renderExplainPanel() {
  const row = state.active_result || {};
  const art = state.active_artifacts || {};
  if (!row.exp_id && !Object.keys(art || {}).length) {
    setHtmlById('wbFunnel', '<div class="wb-mini">运行后显示信号漏斗</div>');
    setHtmlById('wbTriggers', '<div class="wb-mini">运行后显示触发统计</div>');
    setHtmlById('wbReasons', '<div class="wb-mini">运行后显示原因码分布</div>');
    setTextById('wbBaselineDiff', '结果: - | 状态=-');
    return;
  }
  const counters = art?.run_meta?.counters || row || {};
  const funnel = (art.funnelRows || [])[0] || {};
  setHtmlById('wbFunnel', `<div class="wb-mini" style="margin-bottom:6px">信号漏斗</div>${renderFunnelBars({
    raw_signal: funnel.raw_signal ?? row.raw_signal ?? 0,
    blocked: funnel.blocked ?? row.blocked ?? 0,
    orders: funnel.orders ?? row.orders ?? 0,
    skipped: funnel.skipped ?? row.skipped ?? 0,
    closed_trades: funnel.closed_trades ?? row.closed_trades ?? 0,
  })}`);

  const tRows = [
    ['ATR止损平仓', counters.atr_stop_exit_count ?? row.atr_stop_exit_count ?? 0, false],
    ['ATR追踪平仓', counters.atr_trail_exit_count ?? row.atr_trail_exit_count ?? 0, false],
    ['ATR追踪更新', counters.atr_trail_update_count ?? row.atr_trail_update_count ?? 0, false],
    ['资金流排名应用率', counters.mf_rank_applied_rate ?? row.mf_rank_applied_rate ?? 0, true],
    ['门控触发率', counters.gate_on_rate ?? row.gate_on_rate ?? 0, true],
    ['趋势斜率拦截', counters.trend_slope_block_count ?? row.trend_slope_block_count ?? 0, false],
  ];
  setHtmlById('wbTriggers', `<table class="wb-table"><thead><tr><th>计数器</th><th>值</th></tr></thead><tbody>${tRows.map(([k, v, isRate]) => `<tr><td>${esc(k)}</td><td>${isRate ? pct(v) : num(v, 0)}</td></tr>`).join('')}</tbody></table>`);

  const reasonBuckets = reasonByPrefix(art.reasonRows || []);
  const top = (arr) => arr.slice(0, 20).map((x) => `${reasonZh(x.code)}:${x.count}`).join(', ') || '无';
  const errPart = art.errors?.length ? `<br>异常: ${esc(art.errors.join(' | '))}` : '';
  setHtmlById('wbReasons', `拦截: ${esc(top(reasonBuckets.blocked))}<br>跳过: ${esc(top(reasonBuckets.skipped))}<br>退出: ${esc(top(reasonBuckets.exit))}${errPart}`);
  setTextById('wbBaselineDiff', `结果: ${row.exp_id || '-'} | 状态=${row.status || '-'}`);

  // Populate Drawer stats panels
  populateExitStats(counters);
  populateConstraintStats(counters, state.config_draft);
}

function renderExecutionPanel() {
  const p = state.execution_preview;
  const execStatus = state.api_status?.execution_preview || null;
  if (!state.execution_api_enabled) {
    setTextById('wbExecDateNote', '后端未启用 execution preview');
    setTextById('wbExecCandidates', '候选标的: -');
    setTextById('wbExecTargets', '目标持仓: -');
  } else if (!p) {
    if (execStatus?.status === 'failed') {
      setTextById('wbExecDateNote', `执行接口失败: ${execStatus.error || '未知错误'}`);
    } else if (execStatus?.status === 'loading') {
      setTextById('wbExecDateNote', '执行接口请求中...');
    } else {
      setTextById('wbExecDateNote', '未生成执行清单（可点击”生成今日执行清单”）');
    }
    setTextById('wbExecCandidates', '候选标的: -');
    setTextById('wbExecTargets', '目标持仓: -');
  } else {
    setTextById('wbExecDateNote', `基准日期=${p.as_of_date_used} (来源=${p.source || '未知'})`);
    setHtmlById('wbExecCandidates', `候选标的 TopN: ${(p.candidates || []).map((x) => `${x.rank}.${x.symbol}(${num(x.score, 6)})`).join(' | ')}`);
    setHtmlById('wbExecTargets', `目标持仓: ${(p.target_positions || []).map((x) => `${x.symbol}:${pct(x.target_weight)}`).join(' | ')}`);
  }
  // 渲染交易明细表
  renderTradesList();
}

function stockZh(symbol) {
  const names = (state.active_artifacts || {}).stockNames || {};
  const name = names[symbol];
  return name ? `${name}` : String(symbol ?? '');
}

function renderTradesList() {
  const rows = (state.active_artifacts || {}).tradesRows || [];
  const el = byId('wbTradesList');
  if (!el) return;
  if (!rows.length) {
    el.innerHTML = '<div class=”wb-mini”>运行后显示交易明细</div>';
    return;
  }
  const labels = ['日期', '标的', '方向', '价格', '数量', '金额', '原因'];
  const aligns = ['', '', '', 'num', 'num', 'num', ''];
  const header = `<tr>${labels.map((l, i) => `<th${aligns[i] ? ' class=”num”' : ''}>${esc(l)}</th>`).join('')}</tr>`;
  const body = rows.map((r) => {
    const isBuy = String(r.side || '').toUpperCase() === 'BUY';
    const sideBadge = isBuy
      ? '<span class=”wb-badge-buy”>买入</span>'
      : '<span class=”wb-badge-sell”>卖出</span>';
    const sym = String(r.symbol ?? '');
    const displayName = stockZh(sym);
    const symbolCell = displayName !== sym ? `<span title=”${esc(sym)}”>${esc(displayName)}</span>` : esc(sym);
    return `<tr><td>${esc(String(r.date ?? ''))}</td><td>${symbolCell}</td><td>${sideBadge}</td><td class=”num”>${num(r.price, 3)}</td><td class=”num”>${fmtInt(r.qty)}</td><td class=”num”>${fmtMoney(r.value)}</td><td>${esc(reasonZh(r.reason_code))}</td></tr>`;
  }).join('');
  el.innerHTML = `<div class=”wb-mini” style=”margin-bottom:4px”>交易明细 (${fmtInt(rows.length)} 条)</div><table class=”wb-table”><thead>${header}</thead><tbody>${body}</tbody></table>`;
}

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

function applyConfigToUI(cfg) {
  const u = cfg?.universe || {};
  const f = u.filters || {};
  byId('wbStartDate').value = u.start || byId('wbStartDate').value;
  byId('wbEndDate').value = u.end || byId('wbEndDate').value;
  byId('wbBenchmark').value = u.benchmark || byId('wbBenchmark').value;
  byId('wbUniverseMode').value = cfg?.universe_mode || byId('wbUniverseMode').value;
  byId('wbSymbols').value = Array.isArray(u.symbols) ? u.symbols.join(',') : byId('wbSymbols').value;
  byId('wbUniverseLimit').value = u.limit ?? byId('wbUniverseLimit').value;
  byId('wbExcludeSt').checked = !!f.exclude_st;
  byId('wbExcludeSuspended').checked = !!f.exclude_suspended;
  byId('wbMinListDays').value = f.min_list_days ?? byId('wbMinListDays').value;
  byId('wbMinTurnover').value = f.min_avg_turnover_20d ?? byId('wbMinTurnover').value;

  const sma = cfg?.signal_generation?.sma || {};
  byId('wbFastMa').value = sma.fast_ma ?? byId('wbFastMa').value;
  byId('wbSlowMa').value = sma.slow_ma ?? byId('wbSlowMa').value;
  byId('wbEntryBuffer').value = sma.entry_buffer_pct ?? byId('wbEntryBuffer').value;

  const ex = cfg?.exit_rules || {};
  byId('wbExitReverse').checked = !!ex.signal_reverse;
  byId('wbExitAtr').checked = !!(ex.atr_stop?.enabled);
  byId('wbAtrK').value = ex.atr_stop?.k ?? byId('wbAtrK').value;
  byId('wbExitTrail').checked = !!(ex.trailing?.enabled);
  byId('wbTrailK').value = ex.trailing?.k ?? byId('wbTrailK').value;
  byId('wbExitTime').checked = !!(ex.time_exit?.enabled);
  byId('wbExitDays').value = ex.time_exit?.n_days ?? byId('wbExitDays').value;

  const pr = cfg?.position_risk || {};
  byId('wbMaxPositions').value = pr.max_positions ?? byId('wbMaxPositions').value;
  byId('wbSingleCap').value = pr.single_stock_cap != null ? Number(pr.single_stock_cap) * 100 : byId('wbSingleCap').value;
  byId('wbIndustryCap').value = pr.industry_cap != null ? Number(pr.industry_cap) * 100 : byId('wbIndustryCap').value;
  byId('wbLot').value = pr.lot ?? byId('wbLot').value;
  byId('wbCashPolicy').value = pr.cash_shortage_policy || byId('wbCashPolicy').value;

  // Risk Gate
  const rg = cfg?.risk_gate || {};
  byId('wbRiskGateEnabled').checked = !!rg.enabled;
  byId('wbRiskGateThreshold').value = rg.drawdown_threshold != null ? Number(rg.drawdown_threshold) * 100 : byId('wbRiskGateThreshold').value;
  byId('wbRiskGateAction').value = rg.action || byId('wbRiskGateAction').value;
  byId('wbRiskGateCooldown').value = rg.cooldown_days ?? byId('wbRiskGateCooldown').value;

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
  const keys = ['reversal_exit_count', 'atr_stop_exit_count', 'atr_trail_exit_count', 'atr_trail_update_count', 'time_exit_count'];
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

function bindEvents() {
  document.querySelectorAll('#wbMode button').forEach((btn) => btn.addEventListener('click', () => setMode(btn.getAttribute('data-mode') || 'experiment')));
  byId('wbUniverseMode')?.addEventListener('change', () => { updateUniverseInputVisibility(); buildConfigDraft(); renderRunHints(); });
  byId('wbStrategyPack')?.addEventListener('change', buildConfigDraft);
  document.querySelectorAll('.wb-rail-btn').forEach((btn) => btn.addEventListener('click', () => {
    const panel = btn.getAttribute('data-panel') || 'universe';
    setDrawerPanel(panel);
    /* open drawer if collapsed */
    const app = document.querySelector('.wb-app');
    if (app && app.classList.contains('wb-drawer-hidden')) toggleDrawer(false);
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

  document.querySelectorAll('.wb-dock-tabs button[data-dock]').forEach((btn) => btn.addEventListener('click', () => switchDockTab(btn.getAttribute('data-dock') || 'explain')));
  byId('wbPreviewExec')?.addEventListener('click', async () => { try { await previewExecution(); } catch (e) { addLog(`execution失败: ${e.message || e}`); } });
  byId('wbCopyExec')?.addEventListener('click', copyExecJson);
  byId('wbChartBenchToggle')?.addEventListener('change', (e) => { state.chart_show_benchmark = !!e.target.checked; renderPerfPanel(); });
  byId('wbChartRange')?.addEventListener('change', (e) => { state.chart_range = String(e.target.value || 'ALL'); renderPerfPanel(); });
  byId('wbChartExport')?.addEventListener('click', () => {
    const payload = {
      exp_id: state.active_result?.exp_id || null,
      nav_points: state.active_artifacts?.navSeries?.length || 0,
      drawdown_points: state.active_artifacts?.drawdownSeries?.length || 0,
      range: state.chart_range,
    };
    navigator.clipboard?.writeText(JSON.stringify(payload, null, 2));
    addLog('图表摘要已复制');
  });
  byId('wbExportReport')?.addEventListener('click', () => { generateReport(); });
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

  const resizeHandle = byId('wbDockResize');
  const dock = byId('wbDock');
  if (resizeHandle && dock) {
    resizeHandle.addEventListener('mousedown', (ev) => {
      ev.preventDefault();
      const startY = ev.clientY;
      const startH = dock.getBoundingClientRect().height;
      const onMove = (mv) => {
        const next = Math.min(520, Math.max(180, startH + (startY - mv.clientY)));
        dock.style.height = `${next}px`;
      };
      const onUp = () => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    });
  }

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
  bindEvents();
  setDrawerPanel('universe');
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

init();

// ── 报告生成 ──────────────────────────────────────────
function generateReport() {
  const art = state.active_artifacts;
  const result = state.active_result;
  if (!art || !result || !result.exp_id) {
    addLog('请先运行回测');
    return;
  }
  const perf = art.perf || {};
  const meta = art.run_meta || {};
  const counters = meta.counters || {};
  const trades = art.tradesRows || [];
  const daily = art.dailyRows || [];
  const config = art.config || {};
  const funnel = (art.funnelRows || [])[0] || {};

  const e = (v) => String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const p = (v) => { const n = Number(v); return Number.isFinite(n) ? `${(n * 100).toFixed(2)}%` : '-'; };
  const n2 = (v) => { const n = Number(v); return Number.isFinite(n) ? n.toFixed(2) : '-'; };
  const iNum = (v) => { const n = Number(v); return Number.isFinite(n) ? Math.round(n).toLocaleString('en-US') : '-'; };
  const mNum = (v) => { const n = Number(v); return Number.isFinite(n) ? n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-'; };
  const rZh = (code) => REASON_MAP[code] || String(code ?? '');

  // §2 月度/年度收益
  function buildMonthlyReturns() {
    if (!daily.length) return '<p>日级数据不可用</p>';
    const byYM = {};
    daily.forEach((d) => {
      const dt = String(d.date || '');
      if (dt.length < 7) return;
      const y = dt.slice(0, 4);
      const m = parseInt(dt.slice(5, 7), 10);
      if (!byYM[y]) byYM[y] = {};
      if (!byYM[y][m]) byYM[y][m] = [];
      byYM[y][m].push(Number(d.daily_return || 0));
    });
    const years = Object.keys(byYM).sort();
    let html = '<table><thead><tr><th>年份</th>';
    for (let m = 1; m <= 12; m++) html += `<th>${m}月</th>`;
    html += '<th>年度</th></tr></thead><tbody>';
    years.forEach((y) => {
      html += `<tr><td><b>${e(y)}</b></td>`;
      let yearReturn = 1;
      for (let m = 1; m <= 12; m++) {
        const rets = byYM[y][m] || [];
        const monthReturn = rets.reduce((acc, r) => acc * (1 + r), 1) - 1;
        yearReturn *= (1 + monthReturn);
        const color = monthReturn > 0 ? '#2e7d32' : monthReturn < 0 ? '#c62828' : '#888';
        html += `<td style="color:${color}">${rets.length ? p(monthReturn) : '-'}</td>`;
      }
      yearReturn -= 1;
      const yColor = yearReturn > 0 ? '#2e7d32' : yearReturn < 0 ? '#c62828' : '#888';
      html += `<td style="color:${yColor};font-weight:600">${p(yearReturn)}</td></tr>`;
    });
    html += '</tbody></table>';
    return html;
  }

  // §3 最大回撤分析
  function buildDrawdownAnalysis() {
    if (!daily.length) return '<p>日级数据不可用</p>';
    let maxDd = 0, ddStart = '', ddBottom = '';
    let peak = 0, peakDate = '';
    daily.forEach((d) => {
      const nav = Number(d.nav || 0);
      if (nav > peak) { peak = nav; peakDate = String(d.date || ''); }
      if (peak > 0) {
        const dd = (nav - peak) / peak;
        if (dd < maxDd) { maxDd = dd; ddStart = peakDate; ddBottom = String(d.date || ''); }
      }
    });
    return `<table>
      <tr><td>最大回撤幅度</td><td><b>${p(maxDd)}</b></td></tr>
      <tr><td>回撤起始日</td><td>${e(ddStart)}</td></tr>
      <tr><td>回撤最低点日</td><td>${e(ddBottom)}</td></tr>
      <tr><td>夏普比率</td><td>${n2(perf.sharpe)}</td></tr>
      <tr><td>卡尔马比率</td><td>${n2(perf.calmar)}</td></tr>
    </table>`;
  }

  // §4 交易分析
  function buildTradeAnalysis() {
    const buys = trades.filter((t) => String(t.side || '').toUpperCase() === 'BUY');
    const sells = trades.filter((t) => String(t.side || '').toUpperCase() === 'SELL');
    const reasonCounts = {};
    sells.forEach((t) => {
      const rc = String(t.reason_code || '未知');
      reasonCounts[rc] = (reasonCounts[rc] || 0) + 1;
    });
    const sortedReasons = Object.entries(reasonCounts).sort((a, b) => b[1] - a[1]);

    let html = `<table>
      <tr><td>总交易次数</td><td><b>${iNum(trades.length)}</b></td></tr>
      <tr><td>买入次数</td><td>${iNum(buys.length)}</td></tr>
      <tr><td>卖出次数</td><td>${iNum(sells.length)}</td></tr>
    </table>`;

    if (sortedReasons.length) {
      html += '<h4>平仓原因分布</h4><table><thead><tr><th>原因</th><th>次数</th><th>占比</th></tr></thead><tbody>';
      sortedReasons.forEach(([code, cnt]) => {
        html += `<tr><td>${e(rZh(code))}</td><td>${iNum(cnt)}</td><td>${p(sells.length ? cnt / sells.length : 0)}</td></tr>`;
      });
      html += '</tbody></table>';
    }

    const fRaw = Number(funnel.raw_signal || counters.raw_signal || 0);
    const fBlocked = Number(funnel.blocked || counters.blocked || 0);
    const fOrders = Number(funnel.orders || counters.orders || 0);
    const fSkipped = Number(funnel.skipped || counters.skipped || 0);
    const fClosed = Number(funnel.closed_trades || counters.closed_trades || 0);
    if (fRaw || fOrders || fClosed) {
      html += `<h4>信号漏斗</h4><table>
        <tr><td>原始信号</td><td>${iNum(fRaw)}</td></tr>
        <tr><td>被拦截</td><td>${iNum(fBlocked)}</td></tr>
        <tr><td>下单</td><td>${iNum(fOrders)}</td></tr>
        <tr><td>跳过</td><td>${iNum(fSkipped)}</td></tr>
        <tr><td>已平仓</td><td>${iNum(fClosed)}</td></tr>
      </table>`;
    }
    return html;
  }

  // §5 持仓分析
  function buildPositionAnalysis() {
    const maxPos = Number(counters.max_positions || 10);
    const avgPos = Number(counters.avg_positions || 0);
    const slotsLeft = counters.slots_left != null ? Number(counters.slots_left) : (maxPos - avgPos);
    const utilization = maxPos > 0 ? avgPos / maxPos : 0;
    return `<table>
      <tr><td>平均持仓数</td><td>${n2(avgPos)}</td></tr>
      <tr><td>最大持仓数</td><td>${iNum(maxPos)}</td></tr>
      <tr><td>空余仓位</td><td>${n2(slotsLeft)}</td></tr>
      <tr><td>仓位利用率</td><td>${p(utilization)}</td></tr>
    </table>
    <h4>约束触发统计</h4>
    <table>
      <tr><td>个股上限触发</td><td>${iNum(counters.cap_hit_single || 0)}</td></tr>
      <tr><td>行业上限触发</td><td>${iNum(counters.cap_hit_industry || 0)}</td></tr>
      <tr><td>资金不足跳过</td><td>${iNum(counters.cash_skip_count || 0)}</td></tr>
      <tr><td>最小手数跳过</td><td>${iNum(counters.lot_skip_count || 0)}</td></tr>
    </table>`;
  }

  // §6 策略参数摘要
  function buildConfigSummary() {
    const bc = config.base_config || config || {};
    const pr = bc.position_risk || {};
    const sig = bc.signal || {};
    const exitCfg = bc.exit || {};
    return `<table>
      <tr><td>引擎模式</td><td>${e(meta.code?.engine_mode || '-')}</td></tr>
      <tr><td>最大持仓数</td><td>${iNum(pr.max_positions || '-')}</td></tr>
      <tr><td>单票仓位上限</td><td>${p(pr.single_position_cap || 0)}</td></tr>
      <tr><td>行业仓位上限</td><td>${p(pr.industry_cap || 0)}</td></tr>
      <tr><td>信号类型</td><td>${e(sig.type || sig.signal_type || '-')}</td></tr>
      <tr><td>ATR止损倍数</td><td>${n2(exitCfg.atr_stop_multiplier || exitCfg.atr_stop?.multiplier || '-')}</td></tr>
      <tr><td>ATR追踪倍数</td><td>${n2(exitCfg.atr_trail_multiplier || exitCfg.atr_trail?.multiplier || '-')}</td></tr>
      <tr><td>最大持仓天数</td><td>${iNum(exitCfg.max_hold_days || '-')}</td></tr>
    </table>`;
  }

  // §7 交易明细附录
  function buildTradeAppendix() {
    if (!trades.length) return '<p>无交易记录</p>';
    const names = (art.stockNames || {});
    let html = '<table><thead><tr><th>日期</th><th>标的</th><th>方向</th><th style="text-align:right">价格</th><th style="text-align:right">数量</th><th style="text-align:right">金额</th><th>原因</th></tr></thead><tbody>';
    trades.forEach((t) => {
      const isBuy = String(t.side || '').toUpperCase() === 'BUY';
      const side = isBuy ? '<span style="color:#2e7d32;font-weight:600">买入</span>' : '<span style="color:#c62828;font-weight:600">卖出</span>';
      const sym = String(t.symbol || '');
      const displayName = names[sym] || sym;
      const symbolCell = displayName !== sym ? `<span title="${e(sym)}">${e(displayName)}</span>` : e(sym);
      html += `<tr><td>${e(t.date || '')}</td><td>${symbolCell}</td><td>${side}</td><td style="text-align:right">${Number(t.price || 0).toFixed(3)}</td><td style="text-align:right">${iNum(t.qty)}</td><td style="text-align:right">${mNum(t.value)}</td><td>${e(rZh(t.reason_code))}</td></tr>`;
    });
    html += '</tbody></table>';
    return html;
  }

  const now = new Date().toLocaleString('zh-CN');
  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>回测报告 - ${e(result.exp_id || '')}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, 'Microsoft YaHei', sans-serif; color: #1a1a1a; padding: 40px 60px; max-width: 1000px; margin: 0 auto; line-height: 1.6; }
  h1 { font-size: 24px; border-bottom: 2px solid #1a1a1a; padding-bottom: 8px; margin-bottom: 6px; }
  .subtitle { color: #666; font-size: 13px; margin-bottom: 30px; }
  h2 { font-size: 18px; color: #1a1a1a; margin: 30px 0 12px; padding-bottom: 4px; border-bottom: 1px solid #ddd; }
  h3 { font-size: 15px; margin: 20px 0 8px; }
  h4 { font-size: 14px; margin: 16px 0 6px; color: #444; }
  table { width: 100%; border-collapse: collapse; margin: 8px 0 16px; font-size: 13px; }
  th { background: #f5f5f5; font-weight: 600; text-align: left; padding: 6px 10px; border: 1px solid #ddd; white-space: nowrap; }
  td { padding: 5px 10px; border: 1px solid #eee; }
  .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0; }
  .kpi-card { border: 1px solid #e0e0e0; border-radius: 6px; padding: 12px; text-align: center; }
  .kpi-label { font-size: 12px; color: #888; margin-bottom: 4px; }
  .kpi-value { font-size: 20px; font-weight: 700; font-family: ui-monospace, monospace; }
  .kpi-value.positive { color: #2e7d32; }
  .kpi-value.negative { color: #c62828; }
  @media print { body { padding: 20px; } h2 { page-break-before: auto; } table { page-break-inside: auto; } }
</style>
</head>
<body>
<h1>量化回测分析报告</h1>
<div class="subtitle">实验 ${e(result.exp_id || '-')} | 生成于 ${e(now)}</div>

<h2>§1 概览</h2>
<table>
  <tr><td>回测区间</td><td>${e(meta.data?.start || '-')} ~ ${e(meta.data?.end || '-')}</td></tr>
  <tr><td>基准指数</td><td>${e(meta.data?.benchmark || '-')}</td></tr>
  <tr><td>对照指数</td><td>${e(meta.data?.compare_symbol || '-')}</td></tr>
  <tr><td>股票池数量</td><td>${iNum(meta.data?.universe_limit || '-')}</td></tr>
</table>
<div class="kpi-grid">
  ${[
    ['年化收益', p(perf.cagr)],
    ['最大回撤', p(perf.max_drawdown)],
    ['夏普比率', n2(perf.sharpe)],
    ['卡尔马比率', n2(perf.calmar)],
    ['交易次数', iNum(perf.trades)],
    ['换手率', p(perf.turnover)],
    ['累计收益', p(perf.total_return)],
    ['评级', e(String(result.tier || '-'))],
  ].map(([label, val]) => {
    const cls = String(val).startsWith('-') ? 'negative' : (String(val).match(/^[0-9]/) ? 'positive' : '');
    return `<div class="kpi-card"><div class="kpi-label">${label}</div><div class="kpi-value ${cls}">${val}</div></div>`;
  }).join('')}
</div>

<h2>§2 收益分析</h2>
<h3>月度收益率</h3>
${buildMonthlyReturns()}

<h2>§3 风险分析</h2>
${buildDrawdownAnalysis()}

<h2>§4 交易分析</h2>
${buildTradeAnalysis()}

<h2>§5 持仓分析</h2>
${buildPositionAnalysis()}

<h2>§6 策略参数</h2>
${buildConfigSummary()}

<h2>§7 附录：全部交易明细</h2>
<p style="color:#666;font-size:12px;margin-bottom:8px">共 ${iNum(trades.length)} 条交易记录</p>
${buildTradeAppendix()}

</body>
</html>`;

  const win = window.open('', '_blank');
  if (win) {
    win.document.write(html);
    win.document.close();
  } else {
    addLog('浏览器阻止了弹出窗口，请允许弹出窗口后重试');
  }
}

