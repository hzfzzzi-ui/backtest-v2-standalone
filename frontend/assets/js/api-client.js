/* ── api-client.js ── API request helpers & status management ── */
/* Globals used: state, byId, esc, toggleStatusPanel (all from backtest_v2.js) */

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

function _mergeStatusItems() {
  const manual = Array.isArray(state.manual_status_items) ? state.manual_status_items : [];
  const validation = Array.isArray(state.validation_status_items) ? state.validation_status_items : [];
  return [...validation, ...manual, ..._apiFailureItems()];
}

function _refreshStatusCenter() {
  state.status_items = _mergeStatusItems();
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

function _sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function apiRequestJson(key, url, options = {}) {
  const requestOptions = { ...options };
  const method = String(requestOptions.method || 'GET').toUpperCase();
  const retryCount = Number.isFinite(Number(requestOptions.retryCount))
    ? Math.max(0, Number(requestOptions.retryCount))
    : (method === 'GET' ? 1 : 0);
  const retryDelayMs = Number.isFinite(Number(requestOptions.retryDelayMs))
    ? Math.max(0, Number(requestOptions.retryDelayMs))
    : 350;
  delete requestOptions.retryCount;
  delete requestOptions.retryDelayMs;

  let lastError = null;
  const startedAt = Date.now();
  _setApiLoading(key, url, method);

  for (let attempt = 0; attempt <= retryCount; attempt += 1) {
    try {
      const r = await fetch(url, requestOptions);
      const durationMs = Date.now() - startedAt;
      if (!r.ok) {
        const detail = await _readHttpErrorDetail(r);
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
      lastError = e;
      const durationMs = Date.now() - startedAt;
      const httpStatus = Number.isFinite(Number(e?.httpStatus)) ? Number(e.httpStatus) : null;
      const isFinalAttempt = attempt >= retryCount;
      if (isFinalAttempt) {
        _setApiFailed(key, url, method, httpStatus, durationMs, e?.message || String(e));
        setStatusItems(state.manual_status_items || []);
        throw e;
      }
      await _sleep(retryDelayMs);
    }
  }

  const durationMs = Date.now() - startedAt;
  _setApiFailed(key, url, method, null, durationMs, lastError?.message || '未知错误');
  setStatusItems(state.manual_status_items || []);
  throw lastError || new Error('未知错误');
}

function setStatusItems(items) {
  state.manual_status_items = Array.isArray(items) ? items : [];
  _refreshStatusCenter();
}

function setValidationStatusItems(items) {
  state.validation_status_items = Array.isArray(items) ? items : [];
  _refreshStatusCenter();
}

function toggleStatusPanel(force = null) {
  const panel = byId('wbStatusPanel');
  if (!panel) return;
  state.status_open = force == null ? !state.status_open : !!force;
  panel.hidden = !state.status_open;
}
