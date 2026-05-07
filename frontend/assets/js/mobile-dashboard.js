(function mobileDashboardBootstrap() {
  const POLL_INTERVAL_MS = 15000;
  const RECENT_WINDOW_DAYS = 7;
  const RECONCILE_REFRESH_POLL_MS = 2000;
  const RECONCILE_REFRESH_MAX_POLLS = 75;
  const INACTIVE_TICKET_STATUSES = new Set(['rejected', 'revoked', 'expired', 'cancelled']);
  const state = {
    authenticated: false,
    configured: false,
    dashboard: null,
    busy: false,
    pollTimer: null,
    page: 'home',
    tradeFocus: 'buy',
    tradePane: 'orders',
    runtimeMode: 'browser',
    secureContext: false,
    serviceWorkerReady: false,
  };

  const MOBILE_READONLY_RESULT_SURFACE = true;

  const labelMaps = {
    sourceMode: { position_aware_reconcile: '持仓重算', experiment_fallback: '只读回退' },
    holdingSync: { fresh: '已同步', stale: '已过期', unsynced: '未同步' },
    tradeMode: { TREND_MAIN: '趋势主模式' },
    marketState: { bull: '多头', bear: '弱势', warm: '偏强', hot: '偏热', neutral: '中性', partial: '部分可用', ok: '正常', cold: '偏弱' },
    action: { buy: '买入', sell: '卖出', hold: '持有' },
    decision: {
      approved_pending: '已确认待执行',
      claimed: '执行器已接单',
      submitted: '已提交',
      partially_filled: '部分成交',
      filled: '已成交',
      cancelled: '已撤单',
      rejected: '已拒单',
      revoked: '已撤回',
      expired: '已过期',
      none: '未确认',
    },
    priceBasis: { latest_close: '收盘价', missing_price: '未取到价格' },
    surfaceStatus: { current: '当前版本', stale_surface: '旧版本' },
  };

  const warningMap = {
    'latest holdings snapshot is missing': '当前账户尚未同步真实持仓',
    'latest reconcile run is missing': '当前没有最新动作单',
    'latest reconcile run does not match latest holdings snapshot': '最新动作单和持仓快照不匹配，请先重算',
    'latest experiment is missing': '当前没有可用实验来源',
    'mobile dashboard signal snapshot is stale': '当前信号已过期，请先刷新',
    'current dashboard is fallback read-only': '当前为只读回退模式，不能直接确认',
    'sellable_qty is 0': '当前可卖数量为 0',
    'holdings are not synced': '真实持仓尚未同步',
    'holdings sync is stale': '真实持仓已过期',
    'holdings changed during pending tickets': '待执行期间持仓发生变化',
    skip_no_cash: '现金不足，当前不能买入',
    stale_data: '当前数据已过期，请先刷新',
    duplicate_submission: '当前动作已经存在待执行 Ticket',
    risk_locked: '当前被风控锁定',
    executor_unavailable: '执行器当前不可用',
    'cash pool update is recomputing current orders': '资金已更新，策略正在重跑，当前委托稍后刷新',
  };

  function collectElements() {
    return {
      bootSplash: document.getElementById('mdBootSplash'),
      viewHost: document.getElementById('mdViewHost'),
      authView: document.getElementById('mdAuthView'),
      dashboardView: document.getElementById('mdDashboardView'),
      loginForm: document.getElementById('mdLoginForm'),
      passwordInput: document.getElementById('mdPasswordInput'),
      authMessage: document.getElementById('mdAuthMessage'),
      dashboardMessage: document.getElementById('mdDashboardMessage'),
      refreshBtn: document.getElementById('mdRefreshBtn'),
      logoutBtn: document.getElementById('mdLogoutBtn'),
      sessionBadge: document.getElementById('mdSessionBadge'),
      headerStatus: document.getElementById('mdHeaderStatus'),
      depositBtn: document.getElementById('mdDepositBtn'),
      homeNavValue: document.getElementById('mdHomeNavValue'),
      homeNavApprox: document.getElementById('mdHomeNavApprox'),
      homeDailyPnl: document.getElementById('mdHomeDailyPnl'),
      homeStrategyTitle: document.getElementById('mdHomeStrategyTitle'),
      homeStrategySubtitle: document.getElementById('mdHomeStrategySubtitle'),
      homeTagRow: document.getElementById('mdHomeTagRow'),
      homeCagr: document.getElementById('mdHomeCagr'),
      homeTotalReturn: document.getElementById('mdHomeTotalReturn'),
      homeSharpe: document.getElementById('mdHomeSharpe'),
      homeDrawdown: document.getElementById('mdHomeDrawdown'),
      homeTrades: document.getElementById('mdHomeTrades'),
      homeSignalDate: document.getElementById('mdHomeSignalDate'),
      preOpenHeadline: document.getElementById('mdPreOpenHeadline'),
      preOpenMeta: document.getElementById('mdPreOpenMeta'),
      preOpenList: document.getElementById('mdPreOpenList'),
      postCloseHeadline: document.getElementById('mdPostCloseHeadline'),
      postCloseMeta: document.getElementById('mdPostCloseMeta'),
      postCloseList: document.getElementById('mdPostCloseList'),
      holdingSync: document.getElementById('mdHoldingSync'),
      sourceMode: document.getElementById('mdSourceMode'),
      marketState: document.getElementById('mdMarketState'),
      tradeMode: document.getElementById('mdTradeMode'),
      syncedAt: document.getElementById('mdSyncedAt'),
      marketBadge: document.getElementById('mdMarketBadge'),
      marketSummary: document.getElementById('mdMarketSummary'),
      tradeTerminalHint: document.getElementById('mdTradeTerminalHint'),
      tradeSignalBadge: document.getElementById('mdTradeSignalBadge'),
      tradeRecentCount: document.getElementById('mdTradeRecentCount'),
      tradeMergedList: document.getElementById('mdTradeMergedList'),
      tradeSpotlightTitle: document.getElementById('mdTradeSpotlightTitle'),
      tradeSpotlightMeta: document.getElementById('mdTradeSpotlightMeta'),
      tradeSpotlightPrice: document.getElementById('mdTradeSpotlightPrice'),
      tradeSpotlightQty: document.getElementById('mdTradeSpotlightQty'),
      tradeSpotlightCurrentQty: document.getElementById('mdTradeSpotlightCurrentQty'),
      tradeSpotlightTargetQty: document.getElementById('mdTradeSpotlightTargetQty'),
      tradeSpotlightTags: document.getElementById('mdTradeSpotlightTags'),
      tradeSpotlightNote: document.getElementById('mdTradeSpotlightNote'),
      tradeSpotlightActions: document.getElementById('mdTradeSpotlightActions'),
      tradeOrdersCount: document.getElementById('mdTradeOrdersCount'),
      tradeConfirmedCount: document.getElementById('mdTradeConfirmedCount'),
      tradeIneffectiveCount: document.getElementById('mdTradeIneffectiveCount'),
      tradeRobotCount: document.getElementById('mdTradeRobotCount'),
      tradeOrdersList: document.getElementById('mdTradeOrdersList'),
      tradeConfirmedList: document.getElementById('mdTradeConfirmedList'),
      tradeIneffectiveList: document.getElementById('mdTradeIneffectiveList'),
      warningsList: document.getElementById('mdWarningsList'),
      assetTotalValue: document.getElementById('mdAssetTotalValue'),
      assetApprox: document.getElementById('mdAssetApprox'),
      assetDailyPnl: document.getElementById('mdAssetDailyPnl'),
      cashBalance: document.getElementById('mdCashBalance'),
      positionMarketValue: document.getElementById('mdPositionMarketValue'),
      positionCount: document.getElementById('mdPositionCount'),
      positionCountBadge: document.getElementById('mdPositionCountBadge'),
      positionList: document.getElementById('mdPositionList'),
      pages: Array.from(document.querySelectorAll('[data-page]')),
      navButtons: Array.from(document.querySelectorAll('[data-md-page]')),
      tradeFocusButtons: Array.from(document.querySelectorAll('[data-md-trade-focus]')),
      tradePaneButtons: Array.from(document.querySelectorAll('[data-md-trade-pane]')),
      tradePanes: Array.from(document.querySelectorAll('.md-trade-pane')),
    };
  }

  function getTemplateHtml(id) {
    const template = document.getElementById(id);
    return template ? template.innerHTML.trim() : '';
  }

  let els = collectElements();
  const templates = {
    authInner: getTemplateHtml('mdAuthTemplate'),
    dashboardInner: getTemplateHtml('mdDashboardTemplate'),
  };

  function fetch(path, options) {
    if (typeof window.sharedApiRequest === 'function') {
      return window.sharedApiRequest(path, { credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, ...options });
    }
    throw new Error('shared api transport is unavailable');
  }

  function api(path, options) {
    return fetch(path, { credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, ...options });
  }

  function esc(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;');
  }

  function uniq(items) {
    return [...new Set((Array.isArray(items) ? items : []).map((item) => String(item || '').trim()).filter(Boolean))];
  }

  function num(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function formatNumber(value, digits) {
    const parsed = num(value);
    if (parsed == null) return '--';
    return parsed.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  function formatQty(value) { return formatNumber(value, 0); }
  function formatPrice(value) { return formatNumber(value, 2); }
  function formatAmount(value) { return formatNumber(value, 2); }
  function formatMoney(value) { return num(value) == null ? '--' : `¥ ${formatAmount(value)}`; }
  function formatSignedMoney(value) { return num(value) == null ? '--' : `${num(value) > 0 ? '+' : ''}${formatMoney(value)}`; }
  function formatPct(value) { return num(value) == null ? '--' : `${(Number(value) * 100).toFixed(1)}%`; }
  function formatSignedPct(value) { return num(value) == null ? '--' : `${num(value) > 0 ? '+' : ''}${(Number(value) * 100).toFixed(2)}%`; }

  function formatDateTime(value) {
    if (!value) return '--';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  }

  function formatDate(value) {
    if (!value) return '--';
    const date = new Date(String(value).length === 10 ? `${value}T00:00:00` : value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
  }

  function mapLabel(group, value, fallback) {
    const key = String(value || '').trim();
    return (labelMaps[group] || {})[group === 'tradeMode' ? key.toUpperCase() : key.toLowerCase()] || value || fallback || '--';
  }

  function warningText(value) {
    const text = String(value || '').trim();
    return warningMap[text] || text;
  }

  function detectRuntimeMode() {
    const standalone = (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) || window.navigator.standalone === true;
    const localhost = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
    const secureContext = !!window.isSecureContext || localhost;
    state.runtimeMode = standalone ? 'pwa' : 'browser';
    state.secureContext = secureContext;
    document.documentElement.setAttribute('data-md-runtime', state.runtimeMode);
    document.documentElement.setAttribute('data-md-secure', secureContext ? '1' : '0');
    return { runtimeMode: state.runtimeMode, secureContext };
  }

  async function ensurePrivateServiceWorker() {
    const runtime = detectRuntimeMode();
    if (!runtime.secureContext) return;
    if (!('serviceWorker' in navigator)) return;
    try {
      await navigator.serviceWorker.register('/mobile-service-worker.js', { scope: '/' });
      state.serviceWorkerReady = true;
    } catch (_error) {
      state.serviceWorkerReady = false;
    }
  }

  function toneClass(value) {
    const parsed = num(value);
    if (parsed == null || parsed === 0) return 'md-tone-neutral';
    return parsed > 0 ? 'md-tone-positive' : 'md-tone-negative';
  }

  function directionClass(value) {
    const normalized = String(value || '').trim().toLowerCase();
    return normalized ? `md-direction-${normalized}` : 'md-direction-hold';
  }

  function setAlert(target, message, kind) {
    if (!target) return;
    target.hidden = !message;
    target.textContent = message || '';
    target.classList.toggle('is-error', kind === 'error');
    target.classList.toggle('is-success', kind === 'success');
  }

  function isReadonlyResultSurface() {
    return MOBILE_READONLY_RESULT_SURFACE;
  }

  function setAuthMessage(message, isError) { setAlert(els.authMessage, message, isError ? 'error' : 'info'); }
  function setDashboardMessage(message, kind) { setAlert(els.dashboardMessage, message, kind || 'info'); }
  function setSessionBadge(message) { if (els.sessionBadge) els.sessionBadge.textContent = message; }

  function currentSessionBadge() {
    if (!state.authenticated) return '未连接';
    return state.runtimeMode === 'pwa' ? 'PWA' : '浏览器';
  }

  function setToneText(target, text, toneValue) {
    if (!target) return;
    target.textContent = text;
    target.classList.remove('md-tone-positive', 'md-tone-negative', 'md-tone-neutral');
    target.classList.add(toneClass(toneValue));
  }

  function renderEmpty(target, message) {
    if (!target) return;
    target.innerHTML = `<div class="md-empty">${esc(message)}</div>`;
  }

  function mountAuthView() {
    if (!els.viewHost) return;
    els.viewHost.innerHTML = templates.authInner;
    els = collectElements();
    bindAuthView();
  }

  function mountDashboardView() {
    if (!els.viewHost) return;
    els.viewHost.innerHTML = templates.dashboardInner;
    els = collectElements();
    bindDashboardView();
    setPage(state.page);
    setTradeFocus(state.tradeFocus);
    setTradePane(state.tradePane);
  }

  function switchAuthenticated(authenticated) {
    state.authenticated = !!authenticated;
    if (state.authenticated) {
      mountDashboardView();
      setSessionBadge('已连接');
      return;
    }
    mountAuthView();
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
  }

  function setPage(page) {
    const nextPage = ['home', 'trade', 'assets'].includes(page) ? page : 'home';
    state.page = nextPage;
    els.pages.forEach((node) => {
      const active = node.getAttribute('data-page') === nextPage;
      node.classList.toggle('is-active', active);
      node.hidden = !active;
    });
    els.navButtons.forEach((button) => button.classList.toggle('is-active', button.getAttribute('data-md-page') === nextPage));
  }

  function setTradeFocus(focus) {
    state.tradeFocus = ['buy', 'sell'].includes(focus) ? focus : 'buy';
    els.tradeFocusButtons.forEach((button) => {
      const active = button.getAttribute('data-md-trade-focus') === state.tradeFocus;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    if (state.dashboard) renderTradeTerminal(state.dashboard);
  }

  function setTradePane(pane) {
    state.tradePane = ['orders', 'confirmed', 'ineffective', 'robot'].includes(pane) ? pane : 'orders';
    els.tradePaneButtons.forEach((button) => {
      const active = button.getAttribute('data-md-trade-pane') === state.tradePane;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    els.tradePanes.forEach((paneNode) => {
      const active = paneNode.id === `mdTrade${state.tradePane.charAt(0).toUpperCase()}${state.tradePane.slice(1)}Pane`;
      paneNode.classList.toggle('is-active', active);
      paneNode.hidden = !active;
    });
  }

  function getExperiment(payload) { return payload && payload.experiment ? payload.experiment : {}; }
  function getBriefing(payload) { return payload && payload.briefing ? payload.briefing : {}; }
  function getNotifications(payload) { return payload && payload.notifications ? payload.notifications : {}; }
  function getReconcile(payload) { return payload && payload.reconcile ? payload.reconcile : {}; }
  function getReconcileRefresh(payload) { return payload && payload.reconcile_refresh ? payload.reconcile_refresh : {}; }
  function getGuidance(payload) { return payload && payload.guidance ? payload.guidance : {}; }
  function getHoldingSync(payload) { return payload && payload.holding_sync ? payload.holding_sync : {}; }
  function getApprovalCards(payload) { const guidance = getGuidance(payload); return Array.isArray(guidance.approval_cards) ? guidance.approval_cards : []; }
  function getPendingTickets(payload) { const guidance = getGuidance(payload); return Array.isArray(guidance.pending_tickets) ? guidance.pending_tickets : []; }
  function getExecutionTickets(payload) {
    const guidance = getGuidance(payload);
    return Array.isArray(guidance.execution_tickets) ? guidance.execution_tickets : getPendingTickets(payload);
  }
  function getEffectiveTradeTickets(payload) {
    return getExecutionTickets(payload).filter((item) => !INACTIVE_TICKET_STATUSES.has(String(item && item.status ? item.status : '').trim().toLowerCase()));
  }
  function getIneffectiveTradeTickets(payload) {
    return getExecutionTickets(payload).filter((item) => INACTIVE_TICKET_STATUSES.has(String(item && item.status ? item.status : '').trim().toLowerCase()));
  }
  function getCardById(suggestionId) { return getApprovalCards(state.dashboard).find((item) => item && item.suggestion_id === suggestionId) || null; }

  function parseDate(value) {
    if (!value) return null;
    const date = new Date(String(value).length === 10 ? `${value}T00:00:00` : value);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function withinRecentDays(value, days) {
    const date = parseDate(value);
    if (!date) return false;
    const diffMs = Date.now() - date.getTime();
    return diffMs >= 0 && diffMs <= days * 24 * 60 * 60 * 1000;
  }

  function buildPositionView(payload) {
    const reconcile = getReconcile(payload);
    const positions = Array.isArray(payload.positions) ? payload.positions : [];
    const actionMap = new Map();
    for (const row of Array.isArray(reconcile.action_sheet) ? reconcile.action_sheet : []) {
      const symbol = String((row && row.symbol) || '').trim().toLowerCase();
      if (symbol) actionMap.set(symbol, row);
    }
    const cash = num(reconcile.cash);
    const rows = positions.map((item) => {
      const symbol = String(item.symbol || '').trim().toLowerCase();
      const qty = num(item.qty);
      const avgCost = num(item.avg_cost != null ? item.avg_cost : item.avg_fill_price);
      const action = actionMap.get(symbol) || {};
      const currentPrice = num(action.reference_price);
      const marketValue = currentPrice != null && qty != null ? currentPrice * qty : null;
      const costValue = avgCost != null && qty != null ? avgCost * qty : null;
      return {
        ...item,
        symbol,
        qty,
        avgCost,
        actionType: String(action.action_type || 'hold').trim().toLowerCase(),
        priceBasis: String(action.reference_price_basis || ''),
        currentPrice,
        marketValue,
        pnl: marketValue != null && costValue != null ? marketValue - costValue : null,
        weight: null,
      };
    });
    const totalPositionValue = rows.reduce((sum, item) => sum + (num(item.marketValue) || 0), 0);
    const totalAssets = cash != null && rows.some((item) => num(item.marketValue) != null) ? cash + totalPositionValue : null;
    rows.forEach((row) => {
      row.weight = totalAssets != null && num(row.marketValue) != null ? row.marketValue / totalAssets : null;
    });
    rows.sort((left, right) => (num(right.marketValue) || 0) - (num(left.marketValue) || 0));
    return { rows, cash, totalPositionValue: totalAssets != null ? totalPositionValue : null, totalAssets, totalPnl: rows.reduce((sum, item) => sum + (num(item.pnl) || 0), 0) };
  }

  function buildDailyPnlText(experiment) {
    const dailyPnl = num(experiment.daily_pnl);
    const dailyReturn = num(experiment.daily_return);
    if (dailyPnl == null && dailyReturn == null) return '--';
    const parts = [];
    if (dailyPnl != null) parts.push(formatSignedMoney(dailyPnl));
    if (dailyReturn != null) parts.push(`(${formatSignedPct(dailyReturn)})`);
    return parts.join(' ');
  }

  function buildHomeApprox(view, experiment) {
    if (view.cash != null) return `≈ 可用现金 ${formatMoney(view.cash)}`;
    if (num(experiment.cash) != null) return `≈ 可用现金 ${formatMoney(experiment.cash)}`;
    return '--';
  }

  function getSignalDate(payload) {
    const reconcile = getReconcile(payload);
    const guidance = getGuidance(payload);
    return reconcile.as_of_date || guidance.as_of_date_used || '--';
  }

  function getMergedTradeCards(payload) {
    const cards = getApprovalCards(payload).filter((item) => {
      if (!item || !['buy', 'sell'].includes(String(item.action_type || '').toLowerCase())) return false;
      const status = String(item.user_decision && item.user_decision.status ? item.user_decision.status : 'none').trim().toLowerCase();
      return status === 'none';
    });
    const recent = cards.filter((item) => withinRecentDays(item.as_of_date || item.signal_date, RECENT_WINDOW_DAYS));
    return (recent.length ? recent : cards).slice();
  }

  function getSpotlightCard(payload) {
    const merged = getMergedTradeCards(payload);
    return merged.find((item) => item.action_type === state.tradeFocus) || merged[0] || null;
  }

  function formatTradeOrderTitle(card) {
    const symbol = String(card && card.symbol ? card.symbol : '--').trim().toUpperCase();
    const rawName = String(card && card.name ? card.name : '').trim();
    if (!rawName) return symbol;
    if (rawName.toLowerCase() === String(card && card.symbol ? card.symbol : '').trim().toLowerCase()) return symbol;
    return `${symbol} ${rawName}`;
  }

  function isRefreshActive(payload) {
    const refresh = getReconcileRefresh(payload);
    const status = String(refresh && refresh.status ? refresh.status : '').trim().toLowerCase();
    if (!['queued', 'running'].includes(status)) return false;
    const requestedSnapshotId = String(refresh && refresh.requested_snapshot_id ? refresh.requested_snapshot_id : '').trim();
    const latestSnapshotId = String(getReconcile(payload).snapshot_id || '').trim();
    return !!requestedSnapshotId && requestedSnapshotId === latestSnapshotId;
  }

  function buildTicketReasonText(item) {
    const parts = [];
    if (item && item.reject_reason) parts.push(String(item.reject_reason));
    if (item && item.revoke_reason) parts.push(String(item.revoke_reason));
    if (item && item.last_error_message) parts.push(String(item.last_error_message));
    if (Array.isArray(item && item.recent_events) && item.recent_events.length) {
      const latest = item.recent_events[item.recent_events.length - 1];
      if (latest && latest.message) parts.push(String(latest.message));
    }
    return uniq(parts).join(' / ');
  }

  function getRobotWarnings(payload) {
    const riskFlags = payload && payload.risk_flags && typeof payload.risk_flags === 'object' ? payload.risk_flags : {};
    return uniq([
      ...(Array.isArray(payload.warnings) ? payload.warnings : []),
      ...(Array.isArray(payload.errors) ? payload.errors : []),
      ...(Array.isArray(getGuidance(payload).warnings) ? getGuidance(payload).warnings : []),
      ...(Array.isArray(getHoldingSync(payload).warnings) ? getHoldingSync(payload).warnings : []),
      ...(Array.isArray(getReconcile(payload).warnings) ? getReconcile(payload).warnings : []),
      riskFlags.risk_locked ? (riskFlags.risk_lock_reason || 'risk_locked') : '',
      riskFlags.executor_declared && !riskFlags.executor_available ? (riskFlags.executor_reason || 'executor_unavailable') : '',
    ].map(warningText));
  }

  function renderTagRow(target, items) {
    if (!target) return;
    const chips = uniq(items);
    target.innerHTML = chips.length ? chips.map((item) => `<span class="md-chip">${esc(item)}</span>`).join('') : '';
    target.hidden = !chips.length;
  }

  function renderPositionList(payload) {
    const holdingSync = getHoldingSync(payload);
    const view = buildPositionView(payload);
    if (els.positionCountBadge) els.positionCountBadge.textContent = formatQty(view.rows.length || 0);
    if (els.positionCount) els.positionCount.textContent = formatQty(view.rows.length || 0);
    if (!view.rows.length) {
      renderEmpty(els.positionList, String(holdingSync.status || '').toLowerCase() === 'unsynced' ? '先同步真实持仓后，这里会展示当前仓位' : '当前没有持仓');
      return view;
    }
    els.positionList.innerHTML = view.rows.map((item) => {
      const chips = [
        item.sellable_qty != null ? `可卖 ${formatQty(item.sellable_qty)} 股` : '',
        item.actionType ? `当前动作 ${mapLabel('action', item.actionType)}` : '',
        item.weight != null ? `仓位 ${formatPct(item.weight)}` : '',
      ].filter(Boolean);
      return `
        <div class="md-list-item md-asset-item">
          <div class="md-asset-item-top">
            <div class="md-symbol-block">
              <strong>${esc(item.name || item.symbol || '--')}</strong>
              <span>${esc(item.symbol || '--')}</span>
            </div>
            <div class="md-figure-block">
              <strong>${esc(formatQty(item.qty))} 股</strong>
              <span>${esc(formatMoney(item.marketValue))}</span>
            </div>
          </div>
          <div class="md-asset-item-sub">
            <span>平均买入价 ${esc(formatPrice(item.avgCost))}</span>
            <strong class="${toneClass(item.pnl)}">${esc(formatSignedMoney(item.pnl))}</strong>
          </div>
          ${chips.length ? `<div class="md-chip-row">${chips.map((chip) => `<span class="md-chip">${esc(chip)}</span>`).join('')}</div>` : ''}
        </div>`;
    }).join('');
    return view;
  }

  function renderMarket(payload) {
    const summary = payload && payload.market && payload.market.summary ? payload.market.summary : null;
    if (!summary || !summary.trade_date) {
      if (els.marketBadge) els.marketBadge.textContent = '--';
      renderEmpty(els.marketSummary, '市场快照暂不可用');
      return;
    }
    if (els.marketBadge) els.marketBadge.textContent = mapLabel('marketState', summary.sentiment_regime || summary.build_status);
    const rows = [
      { label: '快照日期', value: summary.trade_date || '--', tone: null },
      { label: '情绪温度', value: formatNumber(summary.sentiment_score, 1), tone: summary.sentiment_score },
      { label: '流动性', value: formatNumber(summary.turnover_heat, 3), tone: summary.turnover_heat },
      { label: '距 60 日高点', value: formatPct(summary.risk_drawdown_from_60d_high), tone: summary.risk_drawdown_from_60d_high },
      { label: '告警数量', value: formatQty(summary.warning_count || (Array.isArray(summary.warnings) ? summary.warnings.length : 0)), tone: null },
    ];
    els.marketSummary.innerHTML = rows.map((row) => `<div class="md-market-row"><span>${esc(row.label)}</span><strong class="${row.tone == null ? 'md-tone-neutral' : toneClass(row.tone)}">${esc(row.value)}</strong></div>`).join('');
  }

  function renderHome(payload, view) {
    const experiment = getExperiment(payload);
    const refresh = getReconcileRefresh(payload);
    const totalAssets = view.totalAssets != null ? view.totalAssets : num(experiment.nav);
    if (els.homeNavValue) els.homeNavValue.textContent = formatAmount(totalAssets);
    if (els.homeNavApprox) els.homeNavApprox.textContent = buildHomeApprox(view, experiment);
    if (els.homeDailyPnl) setToneText(els.homeDailyPnl, buildDailyPnlText(experiment), experiment.daily_pnl);
    if (els.depositBtn) {
      const refreshActive = ['queued', 'running'].includes(String(refresh.status || '').toLowerCase());
      els.depositBtn.disabled = refreshActive;
      els.depositBtn.textContent = refreshActive ? '重跑中' : '存入资金';
    }
    if (els.homeStrategyTitle) els.homeStrategyTitle.textContent = experiment.title || '暂无策略';
    if (els.homeStrategySubtitle) els.homeStrategySubtitle.textContent = experiment.subtitle || '当前没有可展示的实验副标题';
    renderTagRow(els.homeTagRow, Array.isArray(experiment.tags) ? experiment.tags : []);
    if (els.homeCagr) setToneText(els.homeCagr, formatPct(experiment.cagr), experiment.cagr);
    if (els.homeTotalReturn) setToneText(els.homeTotalReturn, formatPct(experiment.total_return), experiment.total_return);
    if (els.homeSharpe) els.homeSharpe.textContent = formatNumber(experiment.sharpe, 2);
    if (els.homeDrawdown) setToneText(els.homeDrawdown, formatPct(experiment.max_drawdown), experiment.max_drawdown);
    if (els.homeTrades) els.homeTrades.textContent = formatQty(experiment.trades);
    if (els.homeSignalDate) els.homeSignalDate.textContent = getSignalDate(payload);
  }

  function renderBriefRows(target, items, emptyMessage) {
    if (!target) return;
    const rows = Array.isArray(items) ? items : [];
    if (!rows.length) {
      target.innerHTML = `<div class="md-brief-empty">${esc(emptyMessage || '--')}</div>`;
      return;
    }
    target.innerHTML = rows.map((item) => {
      const label = String(item && item.label ? item.label : '--');
      const message = String(item && item.message ? item.message : '');
      const count = num(item && item.count) != null ? ` · ${formatQty(item.count)}` : '';
      const extra = Array.isArray(item && item.messages)
        ? item.messages.slice(0, 2).join(' / ')
        : Array.isArray(item && item.symbols)
          ? item.symbols.slice(0, 3).join(' / ')
          : Array.isArray(item && item.ticket_ids)
            ? item.ticket_ids.slice(0, 2).map((value) => String(value).slice(-6)).join(' / ')
            : '';
      return `
        <div class="md-brief-row">
          <span>${esc(label)}${esc(count)}</span>
          <strong>${esc(message || extra || '--')}</strong>
        </div>`;
    }).join('');
  }

  function renderBriefing(payload) {
    const briefing = getBriefing(payload);
    const preOpen = briefing && briefing.pre_open && typeof briefing.pre_open === 'object' ? briefing.pre_open : {};
    const postClose = briefing && briefing.post_close && typeof briefing.post_close === 'object' ? briefing.post_close : {};

    if (els.preOpenHeadline) els.preOpenHeadline.textContent = preOpen.message || '无新增待确认动作';
    if (els.preOpenMeta) {
      els.preOpenMeta.textContent = [
        preOpen.trade_date || '--',
        `待确认 ${formatQty(preOpen.pending_confirmation_count || 0)}`,
        `未完成 ${formatQty(preOpen.unfinished_ticket_count || 0)}`,
      ].join(' · ');
    }
    renderBriefRows(els.preOpenList, preOpen.items, '当前没有额外待办');

    if (els.postCloseHeadline) els.postCloseHeadline.textContent = postClose.message || '当日无移动端交易操作';
    if (els.postCloseMeta) {
      els.postCloseMeta.textContent = [
        postClose.trade_date || '--',
        `已确认 ${formatQty(postClose.confirmed_count || 0)}`,
        `已执行 ${formatQty(postClose.executed_count || 0)}`,
        `未完成 ${formatQty(postClose.unfinished_count || 0)}`,
      ].join(' · ');
    }
    renderBriefRows(
      els.postCloseList,
      [
        ...(Array.isArray(postClose.major_slippages) ? postClose.major_slippages.slice(0, 2).map((item) => ({
          label: `${item.symbol || '--'} 偏差`,
          message: item.variance_qty != null ? `${formatQty(item.variance_qty)} 股` : (item.message || '--'),
        })) : []),
        ...(Array.isArray(postClose.holding_changes) ? postClose.holding_changes.slice(0, 2).map((item) => ({
          label: `${item.symbol || '--'} ${mapLabel('action', item.action_type)}`,
          message: item.filled_qty != null ? `${formatQty(item.filled_qty)} 股` : '--',
        })) : []),
      ],
      '当前没有复盘变动'
    );
  }

  function renderTradeBoard(payload) {
    const cards = getMergedTradeCards(payload);
    if (els.tradeRecentCount) els.tradeRecentCount.textContent = String(cards.length || 0);
    if (!cards.length) {
      renderEmpty(els.tradeMergedList, '最近一周没有新的买入卖出动作');
      return;
    }
    els.tradeMergedList.innerHTML = `
      <div class="md-trade-ladder-head">
        <span>股票</span>
        <span>价位</span>
        <span>股数</span>
      </div>
      ${cards.map((card) => {
        const suggestion = card.system_suggestion || {};
        return `
          <div class="md-trade-ladder-row ${directionClass(card.action_type)}">
            <div class="md-trade-ladder-symbol">
              <strong>${esc(card.symbol || '--')}</strong>
              <span>${esc(formatDate(card.as_of_date || card.signal_date))}</span>
            </div>
            <div class="md-trade-ladder-price">${esc(suggestion.reference_price != null ? formatPrice(suggestion.reference_price) : '--')}</div>
            <div class="md-trade-ladder-qty">${esc(suggestion.suggested_qty != null ? formatQty(suggestion.suggested_qty) : '--')}</div>
          </div>`;
      }).join('')}
    `;
  }

  function renderTradeSpotlight(payload) {
    const card = getSpotlightCard(payload);
    if (els.tradeTerminalHint) els.tradeTerminalHint.textContent = card ? '当前候选与最近动作概览' : '当前没有可操作候选';
    if (els.tradeSignalBadge) els.tradeSignalBadge.textContent = getSignalDate(payload);
    if (!card) {
      if (els.tradeSpotlightTitle) els.tradeSpotlightTitle.textContent = '暂无候选';
      if (els.tradeSpotlightMeta) els.tradeSpotlightMeta.textContent = '当前没有新的买入卖出候选';
      if (els.tradeSpotlightPrice) els.tradeSpotlightPrice.textContent = '--';
      if (els.tradeSpotlightQty) els.tradeSpotlightQty.textContent = '--';
      if (els.tradeSpotlightCurrentQty) els.tradeSpotlightCurrentQty.textContent = '--';
      if (els.tradeSpotlightTargetQty) els.tradeSpotlightTargetQty.textContent = '--';
      renderTagRow(els.tradeSpotlightTags, []);
      if (els.tradeSpotlightNote) {
        els.tradeSpotlightNote.hidden = true;
        els.tradeSpotlightNote.textContent = '';
      }
      if (els.tradeSpotlightActions) els.tradeSpotlightActions.innerHTML = '';
      return;
    }

    const suggestion = card.system_suggestion || {};
    const blockers = uniq((Array.isArray(card.blockers) ? card.blockers : []).map((item) => warningText(item.message || item.code)));
    const tags = uniq([...(Array.isArray(card.reason_tags) ? card.reason_tags : []), ...(Array.isArray(card.exit_tags) ? card.exit_tags : [])]);
    if (els.tradeSpotlightTitle) els.tradeSpotlightTitle.textContent = `${card.name || card.symbol || '--'} · ${mapLabel('action', card.action_type)}`;
    if (els.tradeSpotlightMeta) els.tradeSpotlightMeta.textContent = `${card.symbol || '--'} · ${card.as_of_date || '--'}${card.user_decision && card.user_decision.status !== 'none' ? ` · ${mapLabel('decision', card.user_decision.status)}` : ''}`;
    if (els.tradeSpotlightPrice) els.tradeSpotlightPrice.textContent = suggestion.reference_price != null ? `${formatPrice(suggestion.reference_price)}${suggestion.reference_price_basis ? ` · ${mapLabel('priceBasis', suggestion.reference_price_basis, '')}` : ''}` : '--';
    if (els.tradeSpotlightQty) els.tradeSpotlightQty.textContent = suggestion.suggested_qty != null ? `${formatQty(suggestion.suggested_qty)} 股` : '--';
    if (els.tradeSpotlightCurrentQty) els.tradeSpotlightCurrentQty.textContent = suggestion.current_qty != null ? `${formatQty(suggestion.current_qty)} 股` : '--';
    if (els.tradeSpotlightTargetQty) els.tradeSpotlightTargetQty.textContent = suggestion.target_qty != null ? `${formatQty(suggestion.target_qty)} 股` : '--';
    renderTagRow(els.tradeSpotlightTags, [
      suggestion.target_weight != null ? `目标权重 ${formatPct(suggestion.target_weight)}` : '',
      suggestion.sellable_qty != null && card.action_type === 'sell' ? `可卖 ${formatQty(suggestion.sellable_qty)} 股` : '',
      ...tags.slice(0, 4),
    ]);
    if (els.tradeSpotlightNote) {
      els.tradeSpotlightNote.hidden = !blockers.length;
      els.tradeSpotlightNote.textContent = blockers.length ? `风险提示：${blockers.join(' / ')}` : '';
    }
    if (els.tradeSpotlightActions) {
      els.tradeSpotlightActions.innerHTML = `
        ${card.can_confirm ? `<button class="md-inline-btn md-inline-btn-primary" type="button" data-md-action="approve" data-suggestion-id="${esc(card.suggestion_id)}">确认</button>` : ''}
        ${card.can_confirm ? `<button class="md-inline-btn" type="button" data-md-action="edit" data-suggestion-id="${esc(card.suggestion_id)}">改单</button>` : ''}
        ${card.can_reject ? `<button class="md-inline-btn md-inline-btn-danger" type="button" data-md-action="reject" data-suggestion-id="${esc(card.suggestion_id)}">驳回</button>` : ''}
      `;
    }
  }

  function renderTradeOrders(payload) {
    if (isRefreshActive(payload)) {
      if (els.tradeOrdersCount) els.tradeOrdersCount.textContent = '0';
      renderEmpty(els.tradeOrdersList, '资金已更新，策略重跑中，当前委托稍后刷新');
      return;
    }
    const readOnly = isReadonlyResultSurface();
    const cards = getMergedTradeCards(payload);
    if (els.tradeOrdersCount) els.tradeOrdersCount.textContent = String(cards.length || 0);
    if (!cards.length) {
      renderEmpty(els.tradeOrdersList, '最近一周没有新的买入卖出动作');
      return;
    }
    els.tradeOrdersList.innerHTML = cards.map((card) => {
      const suggestion = card.system_suggestion || {};
      const blockers = uniq((Array.isArray(card.blockers) ? card.blockers : []).map((item) => warningText(item.message || item.code)));
      const statusText = card.user_decision && card.user_decision.status !== 'none' ? mapLabel('decision', card.user_decision.status) : '未确认';
      return `
        <div class="md-list-item">
          <div class="md-card-head">
            <div class="md-symbol-block">
              <strong>${esc(formatTradeOrderTitle(card))}</strong>
            </div>
            <div class="md-figure-block">
              <span>${esc(card.as_of_date ? `${statusText} · ${card.as_of_date}` : statusText)}</span>
            </div>
          </div>
          <div class="md-card-grid md-card-grid-trade-order">
            <div class="md-metric"><span>参考价</span><strong>${esc(suggestion.reference_price != null ? formatPrice(suggestion.reference_price) : '--')}</strong></div>
            <div class="md-metric"><span>建议股数</span><strong>${esc(suggestion.suggested_qty != null ? `${formatQty(suggestion.suggested_qty)} 股` : '--')}</strong></div>
            <div class="md-metric"><span>当前股数</span><strong>${esc(suggestion.current_qty != null ? `${formatQty(suggestion.current_qty)} 股` : '--')}</strong></div>
          </div>
          ${blockers.length ? `<div class="md-card-note">风险提示：${esc(blockers.join(' / '))}</div>` : ''}
          <div class="md-button-row">
            ${!readOnly && card.can_confirm ? `<button class="md-inline-btn" type="button" data-md-action="edit" data-suggestion-id="${esc(card.suggestion_id)}">改单</button>` : ''}
            ${!readOnly && card.can_reject ? `<button class="md-inline-btn md-inline-btn-danger" type="button" data-md-action="reject" data-suggestion-id="${esc(card.suggestion_id)}">驳回</button>` : ''}
            ${!readOnly && card.can_confirm ? `<button class="md-inline-btn md-inline-btn-primary" type="button" data-md-action="approve" data-suggestion-id="${esc(card.suggestion_id)}">确认</button>` : ''}
            <span class="md-direction-pill ${directionClass(card.action_type)}">${esc(mapLabel('action', card.action_type))}</span>
          </div>
        </div>`;
    }).join('');
  }

  function renderTradeConfirmed(payload) {
    const tickets = getEffectiveTradeTickets(payload);
    const readOnly = isReadonlyResultSurface();
    if (els.tradeConfirmedCount) els.tradeConfirmedCount.textContent = String(tickets.length || 0);
    if (!tickets.length) {
      renderEmpty(els.tradeConfirmedList, '当前还没有手动确认后的交易记录');
      return;
    }
    els.tradeConfirmedList.innerHTML = tickets.map((item) => {
      const qtyText = item.final_qty != null ? `${formatQty(item.final_qty)} 股` : (item.final_target_weight != null ? formatPct(item.final_target_weight) : '--');
      const filledText = item.filled_qty != null ? `${formatQty(item.filled_qty)} 股` : '--';
      const priceText = item.avg_fill_price != null ? formatPrice(item.avg_fill_price) : '--';
      const statusText = mapLabel('decision', item.status || 'approved_pending');
      const eventText = Array.isArray(item.recent_events) && item.recent_events.length
        ? item.recent_events.slice(-3).reverse().map((event) => {
            const parts = [mapLabel('decision', event.status || ''), formatDateTime(event.at)];
            if (event.filled_qty != null) parts.push(`已成 ${formatQty(event.filled_qty)} 股`);
            if (event.avg_fill_price != null) parts.push(`均价 ${formatPrice(event.avg_fill_price)}`);
            if (event.message) parts.push(String(event.message));
            return parts.filter(Boolean).join(' · ');
          }).join('\n')
        : '';
      return `
        <div class="md-list-item">
          <div class="md-card-head">
            <div class="md-symbol-block">
              <strong>${esc(item.name || item.symbol || '--')}</strong>
              <span>${esc(item.symbol || '--')} · ${esc(formatDateTime(item.updated_at || item.created_at))}</span>
            </div>
            <div class="md-figure-block">
              <div class="md-direction-pill ${directionClass(item.action_type)}">${esc(mapLabel('action', item.action_type))}</div>
              <span>${esc(statusText)}</span>
            </div>
          </div>
          <div class="md-card-grid">
            <div class="md-metric"><span>最终数量</span><strong>${esc(qtyText)}</strong></div>
            <div class="md-metric"><span>当前状态</span><strong>${esc(statusText)}</strong></div>
            <div class="md-metric"><span>已成数量</span><strong>${esc(filledText)}</strong></div>
            <div class="md-metric"><span>成交均价</span><strong>${esc(priceText)}</strong></div>
          </div>
          <div class="md-chip-row">
            ${item.manual_adjusted ? '<span class="md-chip">人工调整</span>' : ''}
            ${item.ticket_id ? `<span class="md-chip">Ticket ${esc(String(item.ticket_id).slice(-6))}</span>` : ''}
            ${item.executor_id ? `<span class="md-chip">执行器 ${esc(item.executor_id)}</span>` : ''}
            ${item.surface_status ? `<span class="md-chip">${esc(mapLabel('surfaceStatus', item.surface_status, item.surface_status || '--'))}</span>` : ''}
          </div>
          ${eventText ? `<div class="md-card-note">${esc(eventText).replaceAll('\n', '<br />')}</div>` : ''}
          <div class="md-button-row">
            ${!readOnly && item.status === 'approved_pending' ? `<button class="md-inline-btn md-inline-btn-danger" type="button" data-md-action="revoke" data-ticket-id="${esc(item.ticket_id)}">撤回</button>` : ''}
          </div>
        </div>`;
    }).join('');
  }

  function renderTradeIneffective(payload) {
    const tickets = getIneffectiveTradeTickets(payload);
    if (els.tradeIneffectiveCount) els.tradeIneffectiveCount.textContent = String(tickets.length || 0);
    if (!tickets.length) {
      renderEmpty(els.tradeIneffectiveList, '当前没有未生效交易');
      return;
    }
    els.tradeIneffectiveList.innerHTML = tickets.map((item) => {
      const qtyText = item.final_qty != null ? `${formatQty(item.final_qty)} 股` : (item.final_target_weight != null ? formatPct(item.final_target_weight) : '--');
      const reasonText = buildTicketReasonText(item);
      const statusText = mapLabel('decision', item.status || 'expired');
      return `
        <div class="md-list-item">
          <div class="md-card-head">
            <div class="md-symbol-block">
              <strong>${esc(item.name || item.symbol || '--')}</strong>
              <span>${esc(item.symbol || '--')} · ${esc(formatDateTime(item.updated_at || item.created_at))}</span>
            </div>
            <div class="md-figure-block">
              <div class="md-direction-pill ${directionClass(item.action_type)}">${esc(mapLabel('action', item.action_type))}</div>
              <span>${esc(statusText)}</span>
            </div>
          </div>
          <div class="md-card-grid md-card-grid-trade-order">
            <div class="md-metric"><span>最终数量</span><strong>${esc(qtyText)}</strong></div>
            <div class="md-metric"><span>状态</span><strong>${esc(statusText)}</strong></div>
            <div class="md-metric"><span>信号日期</span><strong>${esc(item.as_of_date || item.signal_date || '--')}</strong></div>
          </div>
          ${reasonText ? `<div class="md-card-note">未生效原因：${esc(reasonText)}</div>` : ''}
        </div>`;
    }).join('');
  }

  function renderRobotWarnings(payload) {
    const warnings = getRobotWarnings(payload);
    const briefing = getBriefing(payload);
    const anomalies = briefing && briefing.execution_anomalies && Array.isArray(briefing.execution_anomalies.items)
      ? briefing.execution_anomalies.items
      : [];
    if (els.tradeRobotCount) els.tradeRobotCount.textContent = String((warnings.length || 0) + (anomalies.length || 0));
    if (!warnings.length && !anomalies.length) {
      renderEmpty(els.warningsList, '当前没有额外风险与降级条目');
      return;
    }
    const anomalyHtml = anomalies.length
      ? `
        <section class="md-robot-section">
          <div class="md-robot-section-title">执行异常</div>
          <div class="md-warning-list">
            ${anomalies.slice(0, 6).map((item) => `<div class="md-warning-item"><strong>${esc(item.symbol || item.status || '--')}</strong><span>${esc(item.message || item.suggested_action || '--')}</span></div>`).join('')}
          </div>
        </section>`
      : '';
    const warningHtml = warnings.length
      ? `
        <section class="md-robot-section">
          <div class="md-robot-section-title">风险与降级</div>
          <div class="md-warning-list">
            ${warnings.slice(0, 8).map((text) => `<div class="md-warning-item">${esc(text)}</div>`).join('')}
          </div>
        </section>`
      : '';
    els.warningsList.innerHTML = `${anomalyHtml}${warningHtml}`;
  }

  function renderTradeTerminal(payload) {
    if (!els.tradeTerminalHint) return payload;
    if (isReadonlyResultSurface()) {
      els.tradeTerminalHint.textContent = '当前为只读结果面，仅查看摘要、信号与执行结果，不提供移动端交易动作。';
    }
    return payload;
  }

  function renderAssets(payload, view) {
    const experiment = getExperiment(payload);
    const totalAssets = view.totalAssets != null ? view.totalAssets : num(experiment.nav);
    const cashBalance = view.cash != null ? view.cash : num(experiment.cash);
    const positionValue = view.totalPositionValue != null ? view.totalPositionValue : (totalAssets != null && cashBalance != null ? totalAssets - cashBalance : null);
    if (els.assetTotalValue) els.assetTotalValue.textContent = formatAmount(totalAssets);
    if (els.assetApprox) els.assetApprox.textContent = cashBalance != null ? `≈ 可用现金 ${formatMoney(cashBalance)}` : '--';
    if (els.assetDailyPnl) setToneText(els.assetDailyPnl, buildDailyPnlText(experiment), experiment.daily_pnl);
    if (els.cashBalance) els.cashBalance.textContent = formatMoney(cashBalance);
    if (els.positionMarketValue) els.positionMarketValue.textContent = formatMoney(positionValue);
  }

  function renderDashboard(payload) {
    state.dashboard = payload || {};
    const experiment = getExperiment(state.dashboard);
    const guidance = getGuidance(state.dashboard);
    const holdingSync = getHoldingSync(state.dashboard);
    const notifications = getNotifications(state.dashboard);
    const view = renderPositionList(state.dashboard);
    setSessionBadge(currentSessionBadge());
    const readonlySurfaceNote = isReadonlyResultSurface() ? '当前为只读结果面，仅展示摘要、信号与执行结果。' : '';
    const runtimeNotificationNote = notifications && notifications.active_channel === 'in_app_feed'
      ? (state.runtimeMode === 'pwa' && state.secureContext ? '当前为 PWA 模式，站内提醒已可用' : '当前为浏览器模式，仅提供站内提醒')
      : '';

    if (els.headerStatus) {
      els.headerStatus.textContent = String(holdingSync.status || '').toLowerCase() === 'unsynced'
        ? '当前未同步真实持仓，仅展示只读信息'
        : '持仓已同步，可查看今日动作与资产状态';
      if (readonlySurfaceNote) els.headerStatus.textContent = `${els.headerStatus.textContent}；${readonlySurfaceNote}`;
    }
    if (els.holdingSync) els.holdingSync.textContent = `${mapLabel('holdingSync', holdingSync.status)}${holdingSync.trade_date ? ` / ${holdingSync.trade_date}` : ''}`;
    if (els.sourceMode) els.sourceMode.textContent = mapLabel('sourceMode', state.dashboard.source_mode || guidance.source_mode);
    if (els.marketState) els.marketState.textContent = mapLabel('marketState', experiment.market_state || (state.dashboard.market || {}).summary?.sentiment_regime);
    if (els.tradeMode) els.tradeMode.textContent = mapLabel('tradeMode', experiment.trade_mode);
    if (els.syncedAt) els.syncedAt.textContent = formatDateTime(holdingSync.synced_at);
    if (els.headerStatus && runtimeNotificationNote) els.headerStatus.textContent = `${els.headerStatus.textContent}；${runtimeNotificationNote}`;

    renderHome(state.dashboard, view);
    renderBriefing(state.dashboard);
    renderMarket(state.dashboard);
    renderTradeTerminal(state.dashboard);
    renderTradeOrders(state.dashboard);
    renderTradeConfirmed(state.dashboard);
    renderTradeIneffective(state.dashboard);
    renderRobotWarnings(state.dashboard);
    renderAssets(state.dashboard, view);
  }

  async function refreshDashboard(options) {
    const silent = !!(options && options.silent);
    if (els.refreshBtn) els.refreshBtn.disabled = true;
    try {
      const response = await api('/api/mobile/dashboard');
      if (response.status === 401) {
        switchAuthenticated(false);
        setAuthMessage('登录已失效，请重新输入口令', true);
        return;
      }
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(warningText(payload.detail || '看板刷新失败'));
      }
      switchAuthenticated(true);
      renderDashboard(await response.json());
      if (!silent) setDashboardMessage('已刷新到最新状态', 'success');
    } catch (error) {
      setDashboardMessage(error.message || String(error), 'error');
    } finally {
      if (els.refreshBtn) els.refreshBtn.disabled = false;
    }
  }

  function ensurePolling() {
    if (state.pollTimer != null) return;
    state.pollTimer = window.setInterval(() => {
      refreshDashboard({ silent: true }).catch(() => {});
    }, POLL_INTERVAL_MS);
  }

  function generateIdempotencyKey() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
    return `mobile-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function buildConfirmMessage(preview) {
    const lines = [`股票: ${(preview.symbol || '--')} ${(preview.name || '')}`.trim(), `动作: ${preview.decision || '--'}`];
    if (preview.final_qty != null && preview.final_qty !== '') lines.push(`最终股数: ${preview.final_qty}`);
    else if (preview.final_target_weight != null && preview.final_target_weight !== '') lines.push(`最终权重: ${formatPct(preview.final_target_weight)}`);
    if (preview.reference_price != null && preview.reference_price !== '') lines.push(`参考价: ${formatPrice(preview.reference_price)}`);
    if (preview.reject_reason) lines.push(`原因: ${preview.reject_reason}`);
    lines.push('确认继续提交吗？');
    return lines.join('\n');
  }

  function parseEditInput(card, rawValue) {
    const raw = String(rawValue || '').trim();
    if (!raw) return {};
    if (card.action_type === 'sell') {
      const qty = Number(raw);
      if (!Number.isFinite(qty) || qty <= 0 || !Number.isInteger(qty)) throw new Error('请输入正整数股数');
      return { final_qty: qty };
    }
    if (raw.endsWith('%')) {
      const pct = Number(raw.slice(0, -1));
      if (!Number.isFinite(pct) || pct < 0 || pct > 100) throw new Error('百分比必须在 0 到 100 之间');
      return { final_target_weight: pct / 100 };
    }
    const numeric = Number(raw);
    if (!Number.isFinite(numeric) || numeric <= 0) throw new Error('请输入有效数值');
    if (Number.isInteger(numeric) && numeric >= 1) return { final_qty: numeric };
    if (numeric <= 1) return { final_target_weight: numeric };
    if (numeric <= 100) return { final_target_weight: numeric / 100 };
    throw new Error('买入改单请输入目标权重、百分比或股数');
  }

  async function prepareApproval(params) {
    const response = await api('/api/mobile/approvals/prepare', { method: 'POST', body: JSON.stringify(params) });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (Array.isArray(payload.blockers) && payload.blockers.length) throw new Error(warningText(payload.blockers[0].message || payload.blockers[0].code));
      throw new Error(warningText(payload.detail || '准备确认失败'));
    }
    return payload;
  }

  async function commitApproval(confirmToken) {
    const response = await api('/api/mobile/approvals/commit', {
      method: 'POST',
      body: JSON.stringify({ confirm_token: confirmToken, idempotency_key: generateIdempotencyKey() }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(warningText(payload.detail || '提交确认失败'));
    return payload;
  }

  async function depositCashPool(amount) {
    const response = await api('/api/mobile/cash-pool/deposit', {
      method: 'POST',
      body: JSON.stringify({ amount }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(warningText(payload.detail || '现金池存入失败'));
    return payload;
  }

  async function getCashPoolStatus() {
    const response = await api('/api/mobile/cash-pool/status');
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(warningText(payload.detail || '现金池状态读取失败'));
    return payload.refresh_status || {};
  }

  function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  async function waitForReconcileRefresh(expectedSnapshotId) {
    const targetSnapshotId = String(expectedSnapshotId || '').trim();
    if (!targetSnapshotId) return null;
    for (let index = 0; index < RECONCILE_REFRESH_MAX_POLLS; index += 1) {
      const refreshStatus = await getCashPoolStatus();
      const status = String(refreshStatus.status || '').trim().toLowerCase();
      const requestedSnapshotId = String(refreshStatus.requested_snapshot_id || '').trim();
      if (requestedSnapshotId === targetSnapshotId && status === 'succeeded') return refreshStatus;
      if (requestedSnapshotId === targetSnapshotId && status === 'failed') {
        throw new Error(refreshStatus.error || '策略重跑失败');
      }
      await sleep(RECONCILE_REFRESH_POLL_MS);
    }
    throw new Error('策略重跑超时，请稍后手动刷新');
  }

  async function handleApprove(card, editable) {
    const params = { suggestion_id: card.suggestion_id, decision: 'approve' };
    if (editable) {
      const rawValue = window.prompt(card.action_type === 'sell' ? '输入最终卖出股数' : '输入目标仓位(0.12 / 12%) 或买入股数', '');
      if (rawValue == null) return;
      Object.assign(params, parseEditInput(card, rawValue));
    }
    const prepared = await prepareApproval(params);
    if (!window.confirm(buildConfirmMessage(prepared.preview || {}))) return;
    await commitApproval(prepared.confirm_token);
    setDashboardMessage('动作已提交到待执行队列', 'success');
    await refreshDashboard({ silent: true });
  }

  async function handleReject(card) {
    const reason = window.prompt('请输入驳回原因', '');
    if (reason == null) return;
    if (!String(reason).trim()) throw new Error('驳回需要填写原因');
    const prepared = await prepareApproval({ suggestion_id: card.suggestion_id, decision: 'reject', reject_reason: String(reason).trim() });
    if (!window.confirm(buildConfirmMessage(prepared.preview || {}))) return;
    await commitApproval(prepared.confirm_token);
    setDashboardMessage('已记录驳回结果', 'success');
    await refreshDashboard({ silent: true });
  }

  async function handleRevoke(ticketId) {
    if (!window.confirm('确定撤回这张待执行 Ticket 吗？')) return;
    const response = await api(`/api/mobile/approval-tickets/${encodeURIComponent(ticketId)}/revoke`, {
      method: 'POST',
      body: JSON.stringify({ reason: 'manual revoke from mobile dashboard' }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(warningText(payload.detail || '撤回失败'));
    setDashboardMessage('待执行 Ticket 已撤回', 'success');
    await refreshDashboard({ silent: true });
  }

  async function handleDeposit() {
    if (isReadonlyResultSurface()) {
      throw new Error('当前为只读结果面，不支持移动端存入资金');
    }
    const rawValue = window.prompt('输入存入金额（元）', '10000');
    if (rawValue == null) return;
    const amount = Number(String(rawValue).replaceAll(',', '').trim());
    if (!Number.isFinite(amount) || amount <= 0) throw new Error('请输入大于 0 的金额');
    if (!window.confirm(`确认向现金池存入 ${formatMoney(amount)} 吗？`)) return;
    const result = await depositCashPool(amount);
    await refreshDashboard({ silent: true });
    setDashboardMessage(`已存入 ${formatMoney(result.amount)}，正在重跑策略并刷新当前委托`, 'success');
    const refreshStatus = result.refresh_status || {};
    const refreshState = String(refreshStatus.status || '').trim().toLowerCase();
    if (['queued', 'running'].includes(refreshState)) {
      await waitForReconcileRefresh(refreshStatus.requested_snapshot_id || result.snapshot_id);
      await refreshDashboard({ silent: true });
      setDashboardMessage('策略已重跑完成，当前委托已刷新', 'success');
      return;
    }
    setDashboardMessage(`已存入 ${formatMoney(result.amount)}`, 'success');
  }

  async function handleDashboardAction(action, suggestionId, ticketId) {
    if (isReadonlyResultSurface()) {
      throw new Error('当前为只读结果面，不支持移动端交易动作');
    }
    if (state.busy) return;
    state.busy = true;
    try {
      if (action === 'revoke') return await handleRevoke(ticketId);
      const card = getCardById(suggestionId);
      if (!card) throw new Error('建议卡片已过期，请先刷新');
      if (action === 'approve') return await handleApprove(card, false);
      if (action === 'edit') return await handleApprove(card, true);
      if (action === 'reject') return await handleReject(card);
    } finally {
      state.busy = false;
    }
  }

  function bindAuthView() {
    if (!els.loginForm || els.loginForm.dataset.bound === '1') return;
    els.loginForm.dataset.bound = '1';
    els.loginForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const password = els.passwordInput ? els.passwordInput.value.trim() : '';
      if (!password) {
        setAuthMessage('请输入访问口令', true);
        return;
      }
      setAuthMessage('登录中...', false);
      const response = await api('/api/mobile/login', { method: 'POST', body: JSON.stringify({ password }) });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        setAuthMessage(warningText(payload.detail || '登录失败'), true);
        return;
      }
      if (els.passwordInput) els.passwordInput.value = '';
      switchAuthenticated(true);
      setAuthMessage('', false);
      await refreshDashboard({ silent: true });
      ensurePolling();
    });
  }

  function bindDashboardView() {
    if (els.logoutBtn && els.logoutBtn.dataset.bound !== '1') {
      els.logoutBtn.dataset.bound = '1';
      els.logoutBtn.addEventListener('click', async () => {
        await api('/api/mobile/logout', { method: 'POST' });
        state.dashboard = null;
        switchAuthenticated(false);
        setAuthMessage('已退出登录', false);
      });
    }
    if (els.refreshBtn && els.refreshBtn.dataset.bound !== '1') {
      els.refreshBtn.dataset.bound = '1';
      els.refreshBtn.addEventListener('click', async () => {
        setDashboardMessage('', 'info');
        await refreshDashboard({ silent: false });
      });
    }
    if (els.depositBtn && els.depositBtn.dataset.bound !== '1') {
      els.depositBtn.dataset.bound = '1';
      els.depositBtn.addEventListener('click', async () => {
        if (isReadonlyResultSurface()) return;
        if (state.busy) return;
        state.busy = true;
        try {
          await handleDeposit();
        } catch (error) {
          setDashboardMessage(error.message || String(error), 'error');
        } finally {
          state.busy = false;
        }
      });
    }
  }

  function hideBootSplash() {
    if (!els.bootSplash) return;
    window.setTimeout(() => {
      els.bootSplash.classList.add('is-hidden');
    }, 220);
  }

  async function bootstrap() {
    detectRuntimeMode();
    ensurePrivateServiceWorker().catch(() => {});
    setPage('home');
    setTradeFocus('buy');
    setTradePane('orders');
    const response = await api('/api/mobile/session');
    if (!response.ok) {
      switchAuthenticated(false);
      setAuthMessage('无法读取手机端会话状态', true);
      hideBootSplash();
      return;
    }
    const payload = await response.json();
    state.configured = !!payload.configured;
    if (!state.configured) {
      switchAuthenticated(false);
      setAuthMessage('服务端尚未配置手机端访问口令', true);
      hideBootSplash();
      return;
    }
    if (payload.authenticated) {
      switchAuthenticated(true);
      await refreshDashboard({ silent: true });
      ensurePolling();
      hideBootSplash();
      return;
    }
    switchAuthenticated(false);
    setAuthMessage('输入口令后进入交易助手', false);
    hideBootSplash();
  }

  document.addEventListener('click', async (event) => {
    const pageButton = event.target.closest('[data-md-page]');
    if (pageButton) {
      setPage(pageButton.getAttribute('data-md-page'));
      return;
    }
    const shortcutButton = event.target.closest('[data-md-shortcut]');
    if (shortcutButton) {
      const shortcut = shortcutButton.getAttribute('data-md-shortcut');
      if (shortcut === 'refresh') {
        setDashboardMessage('', 'info');
        await refreshDashboard({ silent: false });
      }
      return;
    }
    const focusButton = event.target.closest('[data-md-trade-focus]');
    if (focusButton) {
      setTradeFocus(focusButton.getAttribute('data-md-trade-focus'));
      return;
    }
    const paneButton = event.target.closest('[data-md-trade-pane]');
    if (paneButton) {
      setTradePane(paneButton.getAttribute('data-md-trade-pane'));
      return;
    }
    const actionButton = event.target.closest('[data-md-action]');
    if (!actionButton) return;
    try {
      actionButton.disabled = true;
      await handleDashboardAction(
        actionButton.getAttribute('data-md-action'),
        actionButton.getAttribute('data-suggestion-id') || '',
        actionButton.getAttribute('data-ticket-id') || '',
      );
    } catch (error) {
      setDashboardMessage(error.message || String(error), 'error');
    } finally {
      actionButton.disabled = false;
    }
  });

  bootstrap().catch((error) => {
    switchAuthenticated(false);
    setAuthMessage(`初始化失败: ${error.message || error}`, true);
    hideBootSplash();
  });
})();
