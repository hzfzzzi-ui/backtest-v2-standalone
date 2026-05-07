/* desktop-shell/api-surface.js: formal desktop API/status surface owner. */
/* Globals used: state, byId, esc (from desktop-shell/runtime-surface.js). */

function apiTransportFetch(url, init = {}) {
  if (globalThis.desktopApiAdapter && typeof globalThis.desktopApiAdapter.request === 'function') {
    return globalThis.desktopApiAdapter.request(url, init);
  }
  if (typeof globalThis.sharedApiRequest === 'function') {
    return globalThis.sharedApiRequest(url, init);
  }
  throw new Error('sharedApiRequest is unavailable');
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

function _mergeStatusItems() {
  const manual = Array.isArray(state.manual_status_items) ? state.manual_status_items : [];
  const validation = Array.isArray(state.validation_status_items) ? state.validation_status_items : [];
  return [...validation, ...manual, ..._apiFailureItems()];
}

function _marketDataSyncHeadline(syncStatus) {
  const status = String(syncStatus?.status || '').trim().toLowerCase();
  const displayDate = String(syncStatus?.latest_display_trade_date || '').trim();
  if (status === 'fresh' && displayDate) return `数据同步：${displayDate}`;
  if (status === 'running') {
    return `数据同步中：${String(syncStatus?.target_trade_date || displayDate || '-').trim() || '-'}`;
  }
  if (status === 'stale') {
    return displayDate ? `数据滞后：${displayDate}` : '数据滞后';
  }
  if (status === 'failed') return '数据同步失败';
  if (status === 'disabled') {
    return displayDate ? `定时同步关闭：${displayDate}` : '定时同步关闭';
  }
  if (status === 'never_synced') {
    return displayDate ? `未建档：${displayDate}` : '未建档';
  }
  return displayDate ? `数据同步：${displayDate}` : '数据同步：未知';
}

function _marketDataSyncDetail(syncStatus) {
  const message = String(syncStatus?.message || '').trim();
  const target = String(syncStatus?.target_trade_date || '').trim();
  const latest = String(syncStatus?.latest_display_trade_date || '').trim();
  const lagDays = Number(syncStatus?.lag_days);
  const parts = [];
  if (message) parts.push(message);
  if (target) parts.push(`目标交易日 ${target}`);
  if (latest) parts.push(`当前可见日期 ${latest}`);
  if (Number.isFinite(lagDays) && lagDays > 0) parts.push(`落后 ${lagDays} 天`);
  return parts.join(' | ');
}

function renderMarketDataSyncStatus(syncStatus) {
  state.market_data_sync_status = syncStatus && typeof syncStatus === 'object' ? { ...syncStatus } : null;
  const hintEl = byId('wbDataSyncHint');
  if (hintEl) {
    const headline = _marketDataSyncHeadline(state.market_data_sync_status);
    hintEl.textContent = headline;
    hintEl.title = _marketDataSyncDetail(state.market_data_sync_status) || '市场数据同步状态';
    hintEl.classList.toggle('wb-ok', String(state.market_data_sync_status?.status || '').trim().toLowerCase() === 'fresh');
  }

  const panelEl = byId('wbMarketDataSyncStatus');
  if (panelEl) {
    const status = String(state.market_data_sync_status?.status || 'unknown').trim().toLowerCase() || 'unknown';
    const headline = _marketDataSyncHeadline(state.market_data_sync_status);
    const detail = _marketDataSyncDetail(state.market_data_sync_status);
    panelEl.innerHTML = [
      '<div class="wb-status-item">',
      `<div><strong>市场数据</strong></div>`,
      `<div class="wb-mini">${esc(headline)}</div>`,
      `<div class="wb-code wb-mini">${esc(status)}</div>`,
      detail ? `<div class="wb-mini">${esc(detail)}</div>` : '',
      '</div>',
    ].join('');
  }
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

function _clearApiStatus(key) {
  if (!state.api_status || !state.api_status[key]) return;
  delete state.api_status[key];
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

const LOCAL_BACKEND_FALLBACK_PORT = '8091';

function _dedupeApiEndpointCandidates(candidates) {
  const seen = new Set();
  return candidates.filter((candidate) => {
    const text = String(candidate || '').trim();
    if (!text || seen.has(text)) return false;
    seen.add(text);
    return true;
  });
}

function _buildApiEndpointCandidates(url) {
  const rawUrl = String(url || '').trim();
  if (!rawUrl || !rawUrl.startsWith('/api/')) return [rawUrl];
  const locationLike = globalThis?.location || null;
  const protocol = String(locationLike?.protocol || '').trim().toLowerCase();
  const hostname = String(locationLike?.hostname || '').trim();
  const port = String(locationLike?.port || '').trim();
  const candidates = [rawUrl];
  if (protocol === 'file:') {
    candidates.push(`http://127.0.0.1:${LOCAL_BACKEND_FALLBACK_PORT}${rawUrl}`);
    return _dedupeApiEndpointCandidates(candidates);
  }
  if (!['http:', 'https:'].includes(protocol)) return _dedupeApiEndpointCandidates(candidates);
  const normalizedHost = hostname.toLowerCase();
  const isLocalHost = ['localhost', '127.0.0.1', '::1'].includes(normalizedHost);
  if (!isLocalHost) return _dedupeApiEndpointCandidates(candidates);
  if (port !== LOCAL_BACKEND_FALLBACK_PORT) {
    candidates.push(`${protocol}//${hostname || '127.0.0.1'}:${LOCAL_BACKEND_FALLBACK_PORT}${rawUrl}`);
  }
  return _dedupeApiEndpointCandidates(candidates);
}

async function apiRequestJson(key, url, options = {}) {
  const requestOptions = { ...options };
  const method = String(requestOptions.method || 'GET').toUpperCase();
  const suppressStatusOnError = !!requestOptions.suppressStatusOnError;
  const retryCount = Number.isFinite(Number(requestOptions.retryCount))
    ? Math.max(0, Number(requestOptions.retryCount))
    : (method === 'GET' ? 1 : 0);
  const retryDelayMs = Number.isFinite(Number(requestOptions.retryDelayMs))
    ? Math.max(0, Number(requestOptions.retryDelayMs))
    : 350;
  const timeoutMs = Number.isFinite(Number(requestOptions.timeoutMs))
    ? Math.max(0, Number(requestOptions.timeoutMs))
    : 0;
  delete requestOptions.suppressStatusOnError;
  delete requestOptions.retryCount;
  delete requestOptions.retryDelayMs;
  delete requestOptions.timeoutMs;

  let lastError = null;
  const startedAt = Date.now();
  const endpointCandidates = _buildApiEndpointCandidates(url);
  _setApiLoading(key, endpointCandidates[0] || url, method);

  for (let attempt = 0; attempt <= retryCount; attempt += 1) {
    for (let candidateIndex = 0; candidateIndex < endpointCandidates.length; candidateIndex += 1) {
      const endpoint = endpointCandidates[candidateIndex];
      try {
        const fetchOptions = { ...requestOptions };
        let timeoutHandle = null;
        if (timeoutMs > 0 && !fetchOptions.signal && typeof AbortController === 'function') {
          const ctrl = new AbortController();
          fetchOptions.signal = ctrl.signal;
          timeoutHandle = setTimeout(() => ctrl.abort(), timeoutMs);
        }
        let r;
        try {
          r = await apiTransportFetch(endpoint, fetchOptions);
        } catch (rawError) {
          if (rawError?.name === 'AbortError' && timeoutHandle !== null) {
            const timeoutErr = new Error(`Request timeout (${Math.max(1, Math.round(timeoutMs / 1000))}s)`);
            timeoutErr.endpoint = endpoint;
            throw timeoutErr;
          }
          throw rawError;
        } finally {
          if (timeoutHandle !== null) clearTimeout(timeoutHandle);
        }
        const durationMs = Date.now() - startedAt;
        if (!r.ok) {
          const detail = await _readHttpErrorDetail(r);
          const err = new Error(`${r.status} ${detail}`);
          err.httpStatus = r.status;
          err.endpoint = endpoint;
          throw err;
        }
        const payload = await r.json();
        _setApiSuccess(key, endpoint, method, r.status, durationMs);
        if (suppressStatusOnError) _clearApiStatus(key);
        setStatusItems(state.manual_status_items || []);
        return payload;
      } catch (e) {
        lastError = e;
        const durationMs = Date.now() - startedAt;
        const httpStatus = Number.isFinite(Number(e?.httpStatus)) ? Number(e.httpStatus) : null;
        const isFinalAttempt = attempt >= retryCount;
        const hasFallbackCandidate = candidateIndex < endpointCandidates.length - 1;
        if (hasFallbackCandidate) {
          continue;
        }
        if (isFinalAttempt) {
          if (suppressStatusOnError) {
            _clearApiStatus(key);
            setStatusItems(state.manual_status_items || []);
            throw e;
          }
          _setApiFailed(key, e?.endpoint || endpoint, method, httpStatus, durationMs, e?.message || String(e));
          setStatusItems(state.manual_status_items || []);
          throw e;
        }
        await _sleep(retryDelayMs);
      }
    }
  }

  const durationMs = Date.now() - startedAt;
  if (suppressStatusOnError) {
    _clearApiStatus(key);
    setStatusItems(state.manual_status_items || []);
    throw lastError || new Error('未知错误');
  }
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

async function refreshMarketDataSyncStatus() {
  try {
    const assetScope = typeof resolvePreferredAssetScope === 'function'
      ? resolvePreferredAssetScope()
      : 'cn_a_equity';
    const payload = await apiRequestJson(
      'market_data_sync_status',
      `/api/backtest_v2/market_data/sync_status?asset_scope=${encodeURIComponent(assetScope)}`,
      {
        retryCount: 0,
        suppressStatusOnError: true,
        timeoutMs: 5000,
      },
    );
    renderMarketDataSyncStatus(payload);
    return payload;
  } catch (error) {
    renderMarketDataSyncStatus({
      status: 'failed',
      message: String(error?.message || error || 'unknown error'),
      latest_display_trade_date: '',
      target_trade_date: '',
      lag_days: null,
    });
    return null;
  }
}

const apiSurfaceBoundary = {
  owner: 'desktop_api_surface',
  primary_transport: 'desktop_api_adapter',
  direct_fetch_allowed: false,
};

globalThis.apiClientBoundary = apiSurfaceBoundary;
globalThis.desktopApiSurfaceBoundary = apiSurfaceBoundary;
