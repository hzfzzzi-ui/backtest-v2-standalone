(function mobileDashboardBootstrap() {
  const POLL_INTERVAL_MS = 15000;
  const state = (window.createMobileDashboardState && window.createMobileDashboardState()) || {
    authenticated: false,
    configured: false,
    pollTimer: null,
    dashboard: null,
    busy: false,
  };

  const els = {
    authView: document.getElementById('mdAuthView'),
    dashboardView: document.getElementById('mdDashboardView'),
    loginForm: document.getElementById('mdLoginForm'),
    passwordInput: document.getElementById('mdPasswordInput'),
    authMessage: document.getElementById('mdAuthMessage'),
    sessionBadge: document.getElementById('mdSessionBadge'),
    logoutBtn: document.getElementById('mdLogoutBtn'),
    experimentTitle: document.getElementById('mdExperimentTitle'),
    experimentSubtitle: document.getElementById('mdExperimentSubtitle'),
    experimentTags: document.getElementById('mdExperimentTags'),
    updatedAt: document.getElementById('mdUpdatedAt'),
    cagr: document.getElementById('mdCagr'),
    drawdown: document.getElementById('mdDrawdown'),
    sharpe: document.getElementById('mdSharpe'),
    positionCount: document.getElementById('mdPositionCount'),
    tradeMode: document.getElementById('mdTradeMode'),
    marketState: document.getElementById('mdMarketState'),
    signalDate: document.getElementById('mdSignalDate'),
    buyCount: document.getElementById('mdBuyCount'),
    sellCount: document.getElementById('mdSellCount'),
    holdCount: document.getElementById('mdHoldCount'),
    pendingCount: document.getElementById('mdPendingCount'),
    buyList: document.getElementById('mdBuyList'),
    sellList: document.getElementById('mdSellList'),
    positionList: document.getElementById('mdPositionList'),
    pendingList: document.getElementById('mdPendingList'),
    marketBadge: document.getElementById('mdMarketBadge'),
    marketSummary: document.getElementById('mdMarketSummary'),
    warningsList: document.getElementById('mdWarningsList'),
  };

  function api(path, options) {
    return fetch(path, {
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
      },
      ...options,
    });
  }

  function setAuthMessage(message, isError) {
    els.authMessage.textContent = message || '';
    els.authMessage.style.color = isError ? '#bf4f2d' : '';
  }

  function setSessionBadge(text) {
    els.sessionBadge.textContent = text;
  }

  function formatPct(value) {
    if (value == null || value === '') return '--';
    const number = Number(value);
    if (!Number.isFinite(number)) return '--';
    return `${(number * 100).toFixed(1)}%`;
  }

  function formatWeight(value) {
    if (value == null || value === '') return '--';
    const number = Number(value);
    if (!Number.isFinite(number)) return '--';
    return `${(number * 100).toFixed(1)}%`;
  }

  function formatNumber(value) {
    if (value == null || value === '') return '--';
    const number = Number(value);
    if (!Number.isFinite(number)) return '--';
    return number.toLocaleString('zh-CN');
  }

  function formatDateTime(value) {
    if (!value) return '--';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;');
  }

  function renderEmpty(target, message) {
    target.innerHTML = `<div class="md-empty">${escapeHtml(message)}</div>`;
  }

  function renderChipRow(target, items) {
    const values = (Array.isArray(items) ? items : [])
      .map((item) => String(item || '').trim())
      .filter(Boolean);
    target.hidden = values.length === 0;
    target.innerHTML = values.map((item) => `<span class="md-chip">${escapeHtml(item)}</span>`).join('');
  }

  function renderWarnings(items, errors) {
    const merged = [
      ...(Array.isArray(items) ? items : []),
      ...(Array.isArray(errors) ? errors : []),
    ].filter(Boolean);
    if (!merged.length) {
      renderEmpty(els.warningsList, '\u5f53\u524d\u6ca1\u6709\u544a\u8b66');
      return;
    }
    els.warningsList.innerHTML = merged
      .map((message) => `<div class="md-warning-item">${escapeHtml(message)}</div>`)
      .join('');
  }

  function renderMarket(market) {
    const summary = market && market.summary ? market.summary : null;
    if (!summary) {
      els.marketBadge.textContent = '--';
      renderEmpty(els.marketSummary, '\u5e02\u573a\u5feb\u7167\u6682\u4e0d\u53ef\u7528');
      return;
    }
    els.marketBadge.textContent = summary.sentiment_regime || summary.build_status || '--';
    els.marketSummary.innerHTML = `
      <div class="md-market-row"><span>Snapshot</span><strong>${escapeHtml(summary.trade_date || '--')}</strong></div>
      <div class="md-market-row"><span>Sentiment</span><strong>${escapeHtml(formatNumber(summary.sentiment_score))}</strong></div>
      <div class="md-market-row"><span>Liquidity</span><strong>${escapeHtml(formatNumber(summary.turnover_heat))}</strong></div>
      <div class="md-market-row"><span>DD from 60D High</span><strong>${escapeHtml(formatPct(summary.risk_drawdown_from_60d_high))}</strong></div>
    `;
  }

  function getCardsByBucket(bucket) {
    const guidance = state.dashboard && state.dashboard.guidance ? state.dashboard.guidance : {};
    const cards = Array.isArray(guidance.approval_cards) ? guidance.approval_cards : [];
    return cards.filter((item) => item && item.bucket === bucket);
  }

  function getCardById(suggestionId) {
    const guidance = state.dashboard && state.dashboard.guidance ? state.dashboard.guidance : {};
    const cards = Array.isArray(guidance.approval_cards) ? guidance.approval_cards : [];
    return cards.find((item) => item && item.suggestion_id === suggestionId) || null;
  }

  function getDecisionValue(card) {
    const user = card && card.user_decision ? card.user_decision : {};
    if (!user || user.status === 'none') return '\u672a\u786e\u8ba4';
    if (user.final_qty != null && user.final_qty !== '') return `${formatNumber(user.final_qty)} \u80a1`;
    if (user.final_target_weight != null && user.final_target_weight !== '') return formatWeight(user.final_target_weight);
    return user.status_label || user.status || '--';
  }

  function getSystemValue(card) {
    const suggestion = card && card.system_suggestion ? card.system_suggestion : {};
    if (card.action_type === 'sell') {
      return suggestion.suggested_qty != null ? `${formatNumber(suggestion.suggested_qty)} \u80a1` : '--';
    }
    return suggestion.target_weight != null ? formatWeight(suggestion.target_weight) : '--';
  }

  function getActionLabel(card) {
    if (!card) return '--';
    if (card.action_type === 'buy') return '\u4e70\u5165';
    if (card.action_type === 'sell') return '\u5356\u51fa';
    return '\u6301\u6709';
  }

  function renderActionButtons(card) {
    const buttons = [];
    if (card.can_confirm) {
      buttons.push(`<button class="md-inline-btn md-inline-btn-primary" type="button" data-md-action="approve" data-suggestion-id="${escapeHtml(card.suggestion_id)}">\u786e\u8ba4</button>`);
      buttons.push(`<button class="md-inline-btn" type="button" data-md-action="edit" data-suggestion-id="${escapeHtml(card.suggestion_id)}">\u6539\u5355</button>`);
    }
    if (card.can_reject) {
      buttons.push(`<button class="md-inline-btn md-inline-btn-danger" type="button" data-md-action="reject" data-suggestion-id="${escapeHtml(card.suggestion_id)}">\u9a73\u56de</button>`);
    }
    if (!buttons.length) return '';
    return `<div class="md-action-row">${buttons.join('')}</div>`;
  }

  function renderCardMeta(card) {
    const suggestion = card && card.system_suggestion ? card.system_suggestion : {};
    const reasons = Array.isArray(card.reason_tags) ? card.reason_tags : [];
    const exits = Array.isArray(card.exit_tags) ? card.exit_tags : [];
    const blockers = Array.isArray(card.blockers) ? card.blockers : [];
    const chips = [];
    if (suggestion.cap_reason) chips.push(suggestion.cap_reason);
    if (suggestion.current_qty != null && suggestion.current_qty !== '' && card.action_type !== 'sell') {
      chips.push(`Current ${formatNumber(suggestion.current_qty)}`);
    }
    if (card.freshness && card.freshness.data_age_days != null) {
      chips.push(`Age ${formatNumber(card.freshness.data_age_days)}D`);
    }
    reasons.slice(0, 3).forEach((item) => chips.push(item));
    exits.slice(0, 2).forEach((item) => chips.push(item));
    blockers.slice(0, 2).forEach((item) => chips.push(`BLOCK: ${item.message || item.code}`));
    return chips.map((item) => `<span class="md-chip">${escapeHtml(item)}</span>`).join('');
  }

  function renderActionCards(target, cards, emptyMessage) {
    if (!Array.isArray(cards) || !cards.length) {
      renderEmpty(target, emptyMessage);
      return;
    }
    target.innerHTML = cards.map((card) => {
      const user = card.user_decision || {};
      const manualAdjusted = user.manual_adjusted ? `<span class="md-chip">\u4eba\u5de5\u8c03\u6574</span>` : '';
      const decisionReason = user.reason ? `<div class="md-decision-note">${escapeHtml(user.reason)}</div>` : '';
      return `
        <div class="md-list-item md-action-card" data-suggestion-id="${escapeHtml(card.suggestion_id)}">
          <div class="md-list-item-head">
            <div class="md-symbol-block">
              <strong>${escapeHtml(card.name || card.symbol || '--')}</strong>
              <span>${escapeHtml(card.symbol || '--')} · ${escapeHtml(getActionLabel(card))}</span>
            </div>
            <div class="md-weight">${escapeHtml(getSystemValue(card))}</div>
          </div>
          <div class="md-decision-grid">
            <div class="md-decision-col">
              <span class="md-mini-label">System</span>
              <strong>${escapeHtml(getSystemValue(card))}</strong>
            </div>
            <div class="md-decision-col">
              <span class="md-mini-label">User</span>
              <strong>${escapeHtml(getDecisionValue(card))}</strong>
            </div>
          </div>
          <div class="md-status-row">
            <span class="md-status-pill md-status-${escapeHtml(user.status || 'none')}">${escapeHtml(user.status_label || '\u672a\u786e\u8ba4')}</span>
            ${manualAdjusted}
          </div>
          <div class="md-list-meta">${renderCardMeta(card)}</div>
          ${decisionReason}
          ${renderActionButtons(card)}
        </div>
      `;
    }).join('');
  }

  function renderPositionList(target, items) {
    if (!Array.isArray(items) || !items.length) {
      renderEmpty(target, '\u5f53\u524d\u6ca1\u6709\u6301\u4ed3');
      return;
    }
    target.innerHTML = items.map((item) => {
      const meta = [];
      if (item.avg_fill_price != null) meta.push(`<span class="md-chip">\u6210\u672c ${escapeHtml(formatNumber(item.avg_fill_price))}</span>`);
      if (item.last_reason_code) meta.push(`<span class="md-chip">${escapeHtml(item.last_reason_code)}</span>`);
      return `
        <div class="md-list-item">
          <div class="md-list-item-head">
            <div class="md-symbol-block">
              <strong>${escapeHtml(item.name || item.symbol || '--')}</strong>
              <span>${escapeHtml(item.symbol || '--')}</span>
            </div>
            <div class="md-weight">${escapeHtml(formatNumber(item.qty))}</div>
          </div>
          <div class="md-list-meta">
            <span class="md-chip">\u6570\u91cf ${escapeHtml(formatNumber(item.qty))}</span>
            ${meta.join('')}
          </div>
        </div>
      `;
    }).join('');
  }

  function renderPendingList(items) {
    if (!Array.isArray(items) || !items.length) {
      renderEmpty(els.pendingList, '\u6682\u65e0\u5f85\u6267\u884c ticket');
      return;
    }
    els.pendingList.innerHTML = items.map((item) => {
      const finalValue = item.final_qty != null && item.final_qty !== ''
        ? `${formatNumber(item.final_qty)} \u80a1`
        : (item.final_target_weight != null && item.final_target_weight !== ''
          ? formatWeight(item.final_target_weight)
          : '--');
      const manualAdjusted = item.manual_adjusted ? `<span class="md-chip">\u4eba\u5de5\u8c03\u6574</span>` : '';
      return `
        <div class="md-list-item">
          <div class="md-list-item-head">
            <div class="md-symbol-block">
              <strong>${escapeHtml(item.name || item.symbol || '--')}</strong>
              <span>${escapeHtml(item.symbol || '--')} · ${escapeHtml(item.ticket_id || '--')}</span>
            </div>
            <div class="md-weight">${escapeHtml(finalValue)}</div>
          </div>
          <div class="md-status-row">
            <span class="md-status-pill md-status-${escapeHtml(item.status || 'approved_pending')}">${escapeHtml(item.status || 'approved_pending')}</span>
            ${manualAdjusted}
          </div>
          <div class="md-list-meta">
            <span class="md-chip">${escapeHtml(item.action_type || '--')}</span>
            <span class="md-chip">Updated ${escapeHtml(formatDateTime(item.updated_at))}</span>
            ${item.expires_at ? `<span class="md-chip">Expire ${escapeHtml(formatDateTime(item.expires_at))}</span>` : ''}
          </div>
          <div class="md-action-row">
            <button class="md-inline-btn md-inline-btn-danger" type="button" data-md-action="revoke" data-ticket-id="${escapeHtml(item.ticket_id)}">\u64a4\u56de</button>
          </div>
        </div>
      `;
    }).join('');
  }

  function renderDashboard(payload) {
    const normalizedPayload = (window.getMobileDashboardPayload && window.getMobileDashboardPayload(payload)) || payload || {};
    state.dashboard = normalizedPayload;
    const experiment = normalizedPayload && normalizedPayload.experiment ? normalizedPayload.experiment : null;
    const guidance = normalizedPayload && normalizedPayload.guidance ? normalizedPayload.guidance : {};
    const positions = Array.isArray(payload && payload.positions) ? payload.positions : [];
    const buyCards = getCardsByBucket('buy');
    const sellCards = getCardsByBucket('sell');

    els.experimentTitle.textContent = experiment
      ? (experiment.title || experiment.label || experiment.exp_id || '\u6700\u65b0\u5b9e\u9a8c')
      : '\u6682\u65e0\u5b9e\u9a8c';
    els.experimentSubtitle.textContent = experiment
      ? (experiment.subtitle || experiment.exp_id || '--')
      : '--';
    renderChipRow(els.experimentTags, experiment ? experiment.tags : []);
    els.updatedAt.textContent = payload && payload.updated_at ? `Updated ${formatDateTime(payload.updated_at)}` : '--';
    els.cagr.textContent = experiment ? formatPct(experiment.cagr) : '--';
    els.drawdown.textContent = experiment ? formatPct(experiment.max_drawdown) : '--';
    els.sharpe.textContent = experiment ? formatNumber(experiment.sharpe) : '--';
    els.positionCount.textContent = experiment ? formatNumber(experiment.position_count) : '0';
    els.tradeMode.textContent = experiment ? (experiment.trade_mode || '--') : '--';
    els.marketState.textContent = experiment ? (experiment.market_state || '--') : '--';
    els.signalDate.textContent = guidance.as_of_date_used || '--';

    els.buyCount.textContent = String(buyCards.length || 0);
    els.sellCount.textContent = String(sellCards.length || 0);
    els.holdCount.textContent = String(positions.length || 0);
    els.pendingCount.textContent = String(guidance.pending_count || 0);

    renderActionCards(els.buyList, buyCards, '\u5f53\u524d\u6ca1\u6709\u65b0\u7684\u4e70\u5165\u5efa\u8bae');
    renderActionCards(els.sellList, sellCards, '\u5f53\u524d\u6ca1\u6709\u5356\u51fa\u5efa\u8bae');
    renderPositionList(els.positionList, positions);
    renderPendingList(Array.isArray(guidance.pending_tickets) ? guidance.pending_tickets : []);
    renderMarket(payload && payload.market ? payload.market : null);
    renderWarnings(payload && payload.warnings, payload && payload.errors);
  }

  function switchAuthenticated(authenticated) {
    state.authenticated = !!authenticated;
    els.authView.hidden = state.authenticated;
    els.dashboardView.hidden = !state.authenticated;
    els.logoutBtn.hidden = !state.authenticated;
    setSessionBadge(state.authenticated ? '\u5df2\u767b\u5f55' : '\u672a\u767b\u5f55');
    if (!state.authenticated) {
      window.clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  async function refreshDashboard() {
    const response = await api('/api/mobile/dashboard');
    if (response.status === 401) {
      switchAuthenticated(false);
      setAuthMessage('\u767b\u5f55\u5df2\u5931\u6548\uff0c\u8bf7\u91cd\u65b0\u8f93\u5165\u53e3\u4ee4', true);
      return;
    }
    if (!response.ok) {
      const text = await response.text();
      renderWarnings([`\u770b\u677f\u5237\u65b0\u5931\u8d25: ${text || response.status}`], []);
      return;
    }
    const payload = await response.json();
    switchAuthenticated(true);
    renderDashboard(payload);
  }

  function ensurePolling() {
    if (state.pollTimer != null) return;
    state.pollTimer = window.setInterval(() => {
      refreshDashboard().catch((error) => {
        renderWarnings([`\u8f6e\u8be2\u5931\u8d25: ${error.message || error}`], []);
      });
    }, POLL_INTERVAL_MS);
  }

  function generateIdempotencyKey() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID();
    }
    return `mobile-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function buildConfirmMessage(preview) {
    const lines = [];
    lines.push(`Symbol: ${preview.symbol || '--'} ${preview.name || ''}`.trim());
    lines.push(`Decision: ${preview.decision}`);
    if (preview.final_qty != null && preview.final_qty !== '') {
      lines.push(`Final Qty: ${preview.final_qty}`);
    } else if (preview.final_target_weight != null && preview.final_target_weight !== '') {
      lines.push(`Final Weight: ${formatWeight(preview.final_target_weight)}`);
    } else if (preview.original_qty != null && preview.original_qty !== '') {
      lines.push(`Original Qty: ${preview.original_qty}`);
    } else if (preview.original_target_weight != null && preview.original_target_weight !== '') {
      lines.push(`Original Weight: ${formatWeight(preview.original_target_weight)}`);
    }
    if (preview.reject_reason) lines.push(`Reason: ${preview.reject_reason}`);
    lines.push('\u8fd9\u662f\u4e8c\u6b21\u786e\u8ba4\uff0c\u786e\u5b9a\u7ee7\u7eed\u5417\uff1f');
    return lines.join('\n');
  }

  function parseEditInput(card, rawValue) {
    const raw = String(rawValue || '').trim();
    if (!raw) return {};
    if (card.action_type === 'sell') {
      const qty = Number(raw);
      if (!Number.isFinite(qty) || qty <= 0 || !Number.isInteger(qty)) {
        throw new Error('\u8bf7\u8f93\u5165\u6b63\u6574\u6570\u80a1\u6570');
      }
      return { final_qty: qty };
    }
    if (raw.endsWith('%')) {
      const pct = Number(raw.slice(0, -1));
      if (!Number.isFinite(pct) || pct < 0 || pct > 100) {
        throw new Error('\u767e\u5206\u6bd4\u5fc5\u987b\u5728 0-100 \u4e4b\u95f4');
      }
      return { final_target_weight: pct / 100 };
    }
    const numeric = Number(raw);
    if (!Number.isFinite(numeric) || numeric <= 0) {
      throw new Error('\u8bf7\u8f93\u5165\u6709\u6548\u6570\u503c');
    }
    if (Number.isInteger(numeric) && numeric >= 1) {
      return { final_qty: numeric };
    }
    if (numeric <= 1) {
      return { final_target_weight: numeric };
    }
    if (numeric <= 100) {
      return { final_target_weight: numeric / 100 };
    }
    throw new Error('\u4e70\u5165\u6539\u5355\u8bf7\u8f93\u5165 0-1 \u6743\u91cd / \u767e\u5206\u6bd4 / \u80a1\u6570');
  }

  async function prepareApproval(params) {
    const response = await api('/api/mobile/approvals/prepare', {
      method: 'POST',
      body: JSON.stringify(params),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (Array.isArray(payload.blockers) && payload.blockers.length) {
        const first = payload.blockers[0];
        throw new Error(first.message || first.code || '\u64cd\u4f5c\u88ab\u963b\u65ad');
      }
      throw new Error(payload.detail || '\u51c6\u5907\u786e\u8ba4\u5931\u8d25');
    }
    return payload;
  }

  async function commitApproval(confirmToken) {
    const response = await api('/api/mobile/approvals/commit', {
      method: 'POST',
      body: JSON.stringify({
        confirm_token: confirmToken,
        idempotency_key: generateIdempotencyKey(),
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || '\u63d0\u4ea4\u786e\u8ba4\u5931\u8d25');
    }
    return payload;
  }

  async function handleApprove(card, isEdit) {
    const params = {
      suggestion_id: card.suggestion_id,
      decision: 'approve',
    };
    if (isEdit) {
      const placeholder = card.action_type === 'sell'
        ? '\u8f93\u5165\u6700\u7ec8\u5356\u51fa\u80a1\u6570'
        : '\u8f93\u5165\u76ee\u6807\u4ed3\u4f4d(0.12 / 12%) \u6216\u4e70\u5165\u80a1\u6570';
      const rawValue = window.prompt(placeholder, '');
      if (rawValue == null) return;
      Object.assign(params, parseEditInput(card, rawValue));
    }
    const prepared = await prepareApproval(params);
    if (!window.confirm(buildConfirmMessage(prepared.preview || {}))) return;
    await commitApproval(prepared.confirm_token);
    await refreshDashboard();
  }

  async function handleReject(card) {
    const reason = window.prompt('\u9a73\u56de\u539f\u56e0', '');
    if (reason == null) return;
    if (!String(reason).trim()) {
      throw new Error('\u9a73\u56de\u9700\u8981\u539f\u56e0');
    }
    const prepared = await prepareApproval({
      suggestion_id: card.suggestion_id,
      decision: 'reject',
      reject_reason: String(reason).trim(),
    });
    if (!window.confirm(buildConfirmMessage(prepared.preview || {}))) return;
    await commitApproval(prepared.confirm_token);
    await refreshDashboard();
  }

  async function handleRevoke(ticketId) {
    if (!window.confirm('\u786e\u5b9a\u64a4\u56de\u8fd9\u5f20 pending ticket \u5417\uff1f')) return;
    const response = await api(`/api/mobile/approval-tickets/${encodeURIComponent(ticketId)}/revoke`, {
      method: 'POST',
      body: JSON.stringify({ reason: 'manual revoke from mobile dashboard' }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || '\u64a4\u56de\u5931\u8d25');
    }
    await refreshDashboard();
  }

  async function handleDashboardAction(action, suggestionId, ticketId) {
    if (state.busy) return;
    state.busy = true;
    try {
      if (action === 'revoke') {
        await handleRevoke(ticketId);
        return;
      }
      const card = getCardById(suggestionId);
      if (!card) {
        throw new Error('\u5efa\u8bae\u5361\u7247\u5df2\u8fc7\u671f\uff0c\u8bf7\u5148\u5237\u65b0');
      }
      if (action === 'approve') {
        await handleApprove(card, false);
        return;
      }
      if (action === 'edit') {
        await handleApprove(card, true);
        return;
      }
      if (action === 'reject') {
        await handleReject(card);
      }
    } finally {
      state.busy = false;
    }
  }

  async function bootstrap() {
    setSessionBadge('\u68c0\u67e5\u4e2d');
    const response = await api('/api/mobile/session');
    if (!response.ok) {
      setSessionBadge('\u4e0d\u53ef\u7528');
      setAuthMessage('\u65e0\u6cd5\u8bfb\u53d6\u624b\u673a\u7aef\u4f1a\u8bdd\u72b6\u6001', true);
      return;
    }
    const payload = await response.json();
    state.configured = !!payload.configured;
    if (!state.configured) {
      switchAuthenticated(false);
      setSessionBadge('\u672a\u914d\u7f6e');
      setAuthMessage('\u670d\u52a1\u7aef\u5c1a\u672a\u914d\u7f6e\u624b\u673a\u770b\u677f\u53e3\u4ee4', true);
      return;
    }
    if (payload.authenticated) {
      switchAuthenticated(true);
      await refreshDashboard();
      ensurePolling();
      return;
    }
    switchAuthenticated(false);
    setAuthMessage('\u8f93\u5165\u53e3\u4ee4\u540e\u8fdb\u5165\u624b\u673a\u770b\u677f', false);
  }

  els.loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const password = els.passwordInput.value.trim();
    if (!password) {
      setAuthMessage('\u8bf7\u8f93\u5165\u8bbf\u95ee\u53e3\u4ee4', true);
      return;
    }
    setAuthMessage('\u767b\u5f55\u4e2d...', false);
    const response = await api('/api/mobile/login', {
      method: 'POST',
      body: JSON.stringify({ password }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      setAuthMessage(payload.detail || '\u767b\u5f55\u5931\u8d25', true);
      return;
    }
    els.passwordInput.value = '';
    switchAuthenticated(true);
    setAuthMessage('', false);
    await refreshDashboard();
    ensurePolling();
  });

  els.logoutBtn.addEventListener('click', async () => {
    await api('/api/mobile/logout', { method: 'POST' });
    switchAuthenticated(false);
    renderEmpty(els.buyList, '\u5df2\u9000\u51fa\u767b\u5f55');
    renderEmpty(els.sellList, '\u5df2\u9000\u51fa\u767b\u5f55');
    renderEmpty(els.positionList, '\u5df2\u9000\u51fa\u767b\u5f55');
    renderEmpty(els.pendingList, '\u5df2\u9000\u51fa\u767b\u5f55');
    renderEmpty(els.marketSummary, '\u5df2\u9000\u51fa\u767b\u5f55');
    renderWarnings([], []);
    setAuthMessage('\u5df2\u9000\u51fa\u767b\u5f55', false);
  });

  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-md-action]');
    if (!button) return;
    const action = button.getAttribute('data-md-action');
    const suggestionId = button.getAttribute('data-suggestion-id') || '';
    const ticketId = button.getAttribute('data-ticket-id') || '';
    try {
      button.disabled = true;
      await handleDashboardAction(action, suggestionId, ticketId);
      setAuthMessage('', false);
    } catch (error) {
      setAuthMessage(error.message || String(error), true);
    } finally {
      button.disabled = false;
    }
  });

  bootstrap().catch((error) => {
    setSessionBadge('\u5f02\u5e38');
    setAuthMessage(`\u521d\u59cb\u5316\u5931\u8d25: ${error.message || error}`, true);
  });
})();
