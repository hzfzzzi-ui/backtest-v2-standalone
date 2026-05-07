(function initSharedApiTransport(globalScope) {
  const LOCAL_BACKEND_FALLBACK_PORT = '8091';
  const nativeFetch = typeof globalScope.fetch === 'function'
    ? globalScope.fetch.bind(globalScope)
    : null;

  function apiBase() {
    const host = String(globalScope.location?.hostname || '').trim();
    const port = String(globalScope.location?.port || '').trim();
    if (!host || port === '' || port === '80' || host === 'pams.local') {
      return '';
    }
    return `http://${host}:8090`;
  }

  function dedupe(values) {
    const seen = new Set();
    return values.filter((value) => {
      const text = String(value || '').trim();
      if (!text || seen.has(text)) return false;
      seen.add(text);
      return true;
    });
  }

  function buildApiEndpointCandidates(url) {
    const rawUrl = String(url || '').trim();
    if (!rawUrl || !rawUrl.startsWith('/api/')) return [rawUrl];
    const locationLike = globalScope.location || null;
    const protocol = String(locationLike?.protocol || '').trim().toLowerCase();
    const hostname = String(locationLike?.hostname || '').trim();
    const port = String(locationLike?.port || '').trim();
    const candidates = [rawUrl];
    if (protocol === 'file:') {
      candidates.push(`http://127.0.0.1:${LOCAL_BACKEND_FALLBACK_PORT}${rawUrl}`);
      return dedupe(candidates);
    }
    if (!['http:', 'https:'].includes(protocol)) return dedupe(candidates);
    const isLocalHost = ['localhost', '127.0.0.1', '::1'].includes(hostname.toLowerCase());
    if (!isLocalHost) return dedupe(candidates);
    if (port !== LOCAL_BACKEND_FALLBACK_PORT) {
      candidates.push(`${protocol}//${hostname || '127.0.0.1'}:${LOCAL_BACKEND_FALLBACK_PORT}${rawUrl}`);
    }
    return dedupe(candidates);
  }

  async function readHttpErrorDetail(response) {
    try {
      const payload = await response.json();
      if (payload && typeof payload === 'object') {
        return String(payload.detail || payload.message || JSON.stringify(payload));
      }
    } catch (_) {
      // ignore json parse errors
    }
    return `${response.status} ${response.statusText}`;
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function sharedApiRequest(url, options = {}) {
    if (typeof nativeFetch !== 'function') {
      throw new Error('native fetch is unavailable');
    }
    const requestOptions = { ...options };
    const method = String(requestOptions.method || 'GET').toUpperCase();
    const retryCount = Number.isFinite(Number(requestOptions.retryCount))
      ? Math.max(0, Number(requestOptions.retryCount))
      : (method === 'GET' ? 1 : 0);
    const retryDelayMs = Number.isFinite(Number(requestOptions.retryDelayMs))
      ? Math.max(0, Number(requestOptions.retryDelayMs))
      : 350;
    const timeoutMs = Number.isFinite(Number(requestOptions.timeoutMs))
      ? Math.max(0, Number(requestOptions.timeoutMs))
      : 0;
    delete requestOptions.retryCount;
    delete requestOptions.retryDelayMs;
    delete requestOptions.timeoutMs;

    const startedAt = Date.now();
    const endpointCandidates = buildApiEndpointCandidates(url);
    let lastError = null;

    for (let attempt = 0; attempt <= retryCount; attempt += 1) {
      for (const endpoint of endpointCandidates) {
        try {
          const fetchOptions = { ...requestOptions };
          let timeoutHandle = null;
          if (timeoutMs > 0 && !fetchOptions.signal && typeof AbortController === 'function') {
            const ctrl = new AbortController();
            fetchOptions.signal = ctrl.signal;
            timeoutHandle = setTimeout(() => ctrl.abort(), timeoutMs);
          }
          let response;
          try {
            response = await nativeFetch(endpoint, fetchOptions);
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
          if (!response.ok) {
            const detail = await readHttpErrorDetail(response);
            const err = new Error(`${response.status} ${detail}`);
            err.httpStatus = response.status;
            err.endpoint = endpoint;
            throw err;
          }
          return response;
        } catch (error) {
          lastError = error;
          const hasFallbackCandidate = endpoint !== endpointCandidates[endpointCandidates.length - 1];
          if (hasFallbackCandidate) continue;
        }
      }
      if (attempt < retryCount) {
        await sleep(retryDelayMs);
      }
    }

    const durationMs = Date.now() - startedAt;
    const error = lastError || new Error('unknown api request failure');
    error.durationMs = durationMs;
    throw error;
  }

  async function sharedApiRequestJson(key, url, options = {}) {
    const response = await sharedApiRequest(url, options);
    const payload = await response.json();
    return payload;
  }

  globalScope.sharedApiBase = apiBase;
  globalScope.sharedApiRequest = sharedApiRequest;
  globalScope.sharedApiRequestJson = sharedApiRequestJson;
  globalScope.sharedApiTransport = {
    baseUrl: apiBase(),
    request: sharedApiRequest,
    requestJson: sharedApiRequestJson,
  };
})(window);
