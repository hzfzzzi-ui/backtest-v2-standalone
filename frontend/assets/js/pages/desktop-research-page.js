/* desktop-research-page.js: page shell bridge owner for canonical surface fetch and snapshot merge. */
(function initDesktopResearchPageShell(globalScope) {
  const ALLOWED_LAZY_SECTIONS = [
    'nav',
    'drawdown',
    'symbol_stats',
    'stage_funnel',
    'run_meta',
    'config',
    'trades',
    'daily',
    'reason_codes',
    'stock_names',
  ];

  function cloneJson(value) {
    if (Array.isArray(value)) return value.slice();
    if (value && typeof value === 'object') return { ...value };
    return value;
  }

  function getDesktopResultsWorkbenchBridge() {
    const bridge = globalScope.resultsWorkbenchBridge;
    return bridge && typeof bridge === 'object' ? bridge : null;
  }

  function currentExperimentId(state) {
    return String(state?.active_result?.exp_id || state?.active_exp?.exp_id || '').trim();
  }

  function ensureDesktopSurfaceRuntime(state) {
    if (!state || typeof state !== 'object') {
      return {
        main: { expId: '', payload: null, promise: null },
        sections: {},
      };
    }
    if (!state.__desktopSurfaceRuntime || typeof state.__desktopSurfaceRuntime !== 'object') {
      state.__desktopSurfaceRuntime = {};
    }
    const holder = state.__desktopSurfaceRuntime;
    if (!holder.main || typeof holder.main !== 'object') {
      holder.main = { expId: '', payload: null, promise: null };
    }
    if (!holder.sections || typeof holder.sections !== 'object') {
      holder.sections = {};
    }
    const activeExpId = currentExperimentId(state);
    if (holder.main.expId && activeExpId && holder.main.expId !== activeExpId) {
      holder.main = { expId: activeExpId, payload: null, promise: null };
      holder.sections = {};
    } else if (!holder.main.expId) {
      holder.main.expId = activeExpId;
    }
    return holder;
  }

  function clearDesktopResultsWorkbenchState(state) {
    if (!state || typeof state !== 'object') return;
    state.__desktopSurfaceRuntime = null;
  }

  async function fetchJson(tag, url) {
    if (typeof globalScope.apiRequestJson === 'function') {
      return globalScope.apiRequestJson(tag, url);
    }
    const response = await globalScope.fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  }

  function normalizeLazySections(sections) {
    const requested = Array.isArray(sections) ? sections : [];
    const unique = [];
    requested.forEach((section) => {
      const normalized = String(section || '').trim().toLowerCase();
      if (!ALLOWED_LAZY_SECTIONS.includes(normalized) || unique.includes(normalized)) return;
      unique.push(normalized);
      if (normalized === 'nav' && !unique.includes('drawdown')) unique.push('drawdown');
    });
    return unique;
  }

  function pushLazySection(sections, name) {
    const normalized = String(name || '').trim().toLowerCase();
    if (!ALLOWED_LAZY_SECTIONS.includes(normalized) || sections.includes(normalized)) return;
    sections.push(normalized);
    if (normalized === 'nav' && !sections.includes('drawdown')) sections.push('drawdown');
  }

  function resolveLazySectionsForSnapshot(snapshot, sections) {
    const resolved = normalizeLazySections(sections);
    const view = snapshot?.view && typeof snapshot.view === 'object' ? snapshot.view : {};
    const openPanels = view?.openPanels && typeof view.openPanels === 'object' ? view.openPanels : {};
    if (snapshot?.active) {
      pushLazySection(resolved, 'nav');
      pushLazySection(resolved, 'config');
      // Portfolio regime overlays depend on daily rows being present.
      pushLazySection(resolved, 'daily');
    }
    if (String(view.chartMode || '').trim().toLowerCase() === 'symbol') {
      pushLazySection(resolved, 'symbol_stats');
      pushLazySection(resolved, 'stock_names');
      pushLazySection(resolved, 'trades');
    }
    if (openPanels.symbolPanel) {
      pushLazySection(resolved, 'symbol_stats');
      pushLazySection(resolved, 'stock_names');
    }
    if (openPanels.funnelPanel) {
      pushLazySection(resolved, 'stage_funnel');
      pushLazySection(resolved, 'run_meta');
      pushLazySection(resolved, 'reason_codes');
      pushLazySection(resolved, 'daily');
    }
    if (openPanels.tradesPanel) {
      pushLazySection(resolved, 'trades');
      pushLazySection(resolved, 'stock_names');
    }
    return resolved;
  }

  async function ensureDesktopExperimentSurface(state, expId) {
    const normalizedExpId = String(expId || '').trim();
    if (!normalizedExpId) return null;
    const runtime = ensureDesktopSurfaceRuntime(state);
    if (runtime.main.expId === normalizedExpId && runtime.main.payload) {
      return cloneJson(runtime.main.payload);
    }
    if (runtime.main.expId === normalizedExpId && runtime.main.promise) {
      const payload = await runtime.main.promise;
      return cloneJson(payload);
    }
    runtime.main.expId = normalizedExpId;
    runtime.main.payload = null;
    runtime.sections = {};
    runtime.main.promise = (async () => {
      try {
        const payload = await fetchJson(
          `experiment_surface_${normalizedExpId}`,
          `/api/backtest_v2/experiments/${encodeURIComponent(normalizedExpId)}/surface`,
        );
        runtime.main.payload = payload && typeof payload === 'object' ? payload : null;
        return runtime.main.payload;
      } finally {
        runtime.main.promise = null;
      }
    })();
    const payload = await runtime.main.promise;
    return cloneJson(payload);
  }

  async function ensureDesktopExperimentSurfaceSection(state, expId, section) {
    const normalizedExpId = String(expId || '').trim();
    const normalizedSection = String(section || '').trim().toLowerCase();
    if (!normalizedExpId || !ALLOWED_LAZY_SECTIONS.includes(normalizedSection)) return null;
    const runtime = ensureDesktopSurfaceRuntime(state);
    if (runtime.main.expId !== normalizedExpId) {
      runtime.main = { expId: normalizedExpId, payload: null, promise: null };
      runtime.sections = {};
    }
    if (!runtime.sections[normalizedSection] || typeof runtime.sections[normalizedSection] !== 'object') {
      runtime.sections[normalizedSection] = { payload: null, promise: null };
    }
    const cache = runtime.sections[normalizedSection];
    if (cache.payload) return cloneJson(cache.payload);
    if (cache.promise) {
      const payload = await cache.promise;
      return cloneJson(payload);
    }
    cache.promise = (async () => {
      try {
        const payload = await fetchJson(
          `experiment_surface_${normalizedExpId}_${normalizedSection}`,
          `/api/backtest_v2/experiments/${encodeURIComponent(normalizedExpId)}/surface/${encodeURIComponent(normalizedSection)}`,
        );
        cache.payload = payload && typeof payload === 'object' ? payload : null;
        return cache.payload;
      } finally {
        cache.promise = null;
      }
    })();
    const payload = await cache.promise;
    return cloneJson(payload);
  }

  function normalizeNavSectionData(rows) {
    return (Array.isArray(rows) ? rows : [])
      .map((row) => ({
        date: String(row?.date || '').trim().slice(0, 10),
        nav: Number(row?.nav),
      }))
      .filter((row) => row.date && Number.isFinite(row.nav) && row.nav > 0);
  }

  function normalizeDrawdownSectionData(rows) {
    return (Array.isArray(rows) ? rows : [])
      .map((row) => ({
        date: String(row?.date || '').trim().slice(0, 10),
        value: Number(row?.drawdown),
      }))
      .filter((row) => row.date && Number.isFinite(row.value));
  }

  function normalizeSymbolStatsSectionData(rows) {
    const rawRows = Array.isArray(rows) ? rows : [];
    if (typeof globalScope.normalizeSymbolPerformanceRows === 'function') {
      return cloneJson(globalScope.normalizeSymbolPerformanceRows(rawRows)) || [];
    }
    return cloneJson(rawRows) || [];
  }

  function mergeDesktopSurfaceIntoSnapshot(snapshot, surface) {
    const nextSnapshot = cloneJson(snapshot) || {};
    const summary = surface && typeof surface.summary === 'object' ? cloneJson(surface.summary) : {};
    const assetContext = cloneJson(surface?.asset_context || summary?.asset_context || nextSnapshot.assetContext || {}) || {};
    const artifacts = nextSnapshot.artifacts && typeof nextSnapshot.artifacts === 'object'
      ? { ...nextSnapshot.artifacts }
      : {};
    artifacts.perf = {
      ...(artifacts.perf || {}),
      ...((surface && typeof surface.perf === 'object') ? cloneJson(surface.perf) : {}),
    };
    artifacts.audit = {
      ...(artifacts.audit || {}),
      ...((surface && typeof surface.audit === 'object') ? cloneJson(surface.audit) : {}),
    };
    artifacts.surfaceSummary = summary;
    artifacts.assetContext = assetContext;
    artifacts.machineOutputs = cloneJson(surface?.machine_outputs) || {};
    artifacts.humanOutputs = cloneJson(surface?.human_outputs) || {};
    artifacts.surfaceLazySections = cloneJson(surface?.lazy_sections) || {};
    nextSnapshot.surface = cloneJson(surface) || null;
    nextSnapshot.assetContext = assetContext;
    nextSnapshot.result = {
      ...(nextSnapshot.result || {}),
      ...(summary.exp_id ? { exp_id: summary.exp_id } : {}),
      ...(summary.status ? { status: summary.status } : {}),
      surface_summary: summary,
    };
    nextSnapshot.artifacts = artifacts;
    return nextSnapshot;
  }

  async function mergeDesktopSurfaceSectionIntoSnapshot(snapshot, state, expId, sectionPayload, options = {}) {
    const section = String(sectionPayload?.section || '').trim().toLowerCase();
    if (!ALLOWED_LAZY_SECTIONS.includes(section)) return cloneJson(snapshot) || {};
    const nextSnapshot = cloneJson(snapshot) || {};
    const artifacts = nextSnapshot.artifacts && typeof nextSnapshot.artifacts === 'object'
      ? { ...nextSnapshot.artifacts }
      : {};
    const sections = artifacts.surfaceSections && typeof artifacts.surfaceSections === 'object'
      ? { ...artifacts.surfaceSections }
      : {};
    const data = cloneJson(sectionPayload?.data);
    sections[section] = data;
    artifacts.surfaceSections = sections;

    if (!nextSnapshot.surface || typeof nextSnapshot.surface !== 'object') {
      nextSnapshot.surface = { lazy_sections: {} };
    }
    if (!nextSnapshot.surface.lazy_sections || typeof nextSnapshot.surface.lazy_sections !== 'object') {
      nextSnapshot.surface.lazy_sections = {};
    }
    nextSnapshot.surface.lazy_sections[section] = {
      ...(cloneJson(nextSnapshot.surface.lazy_sections[section]) || {}),
      section,
      available: true,
      inline: true,
      data: data == null ? null : data,
    };

    if (section === 'nav') {
      const navRows = normalizeNavSectionData(Array.isArray(data) ? data : []);
      artifacts.nav = navRows;
      artifacts.navSeries = navRows.map((row) => ({ date: row.date, value: row.nav }));
      if (!Array.isArray(artifacts.drawdownSeries) || !artifacts.drawdownSeries.length) {
        artifacts.drawdownSeries = navRows.reduce((acc, row) => {
          const peak = acc.length ? Math.max(acc[acc.length - 1].__peak || row.nav, row.nav) : row.nav;
          const value = peak > 0 ? ((row.nav - peak) / peak) : 0;
          acc.push({ date: row.date, value, __peak: peak });
          return acc;
        }, []).map((row) => ({ date: row.date, value: row.value }));
      }
      const benchmarkSeriesExists = Array.isArray(artifacts.benchmarkSeries) && artifacts.benchmarkSeries.length;
      const benchmarkOhlcExists = Array.isArray(artifacts.benchmarkOhlc) && artifacts.benchmarkOhlc.length;
      if ((!benchmarkSeriesExists || !benchmarkOhlcExists || !options.reuseExistingBenchmark) && typeof globalScope.loadBenchmarkSeries === 'function') {
        try {
          const benchmark = await globalScope.loadBenchmarkSeries(navRows);
          const benchmarkPoints = Array.isArray(benchmark?.points) ? benchmark.points : [];
          artifacts.benchmarkSeries = benchmarkPoints.map((row) => ({ date: row.date, value: row.nav }));
          artifacts.benchmarkOhlc = Array.isArray(benchmark?.ohlc) ? benchmark.ohlc : [];
          artifacts.benchmarkDrawdownSeries = benchmarkPoints.reduce((acc, row) => {
            const nav = Number(row?.nav);
            if (!Number.isFinite(nav) || nav <= 0) return acc;
            const peak = acc.length ? Math.max(acc[acc.length - 1].__peak || nav, nav) : nav;
            acc.push({ date: row.date, value: peak > 0 ? ((nav - peak) / peak) : 0, __peak: peak });
            return acc;
          }, []).map((row) => ({ date: row.date, value: row.value }));
          artifacts.benchmarkSource = String(benchmark?.source || '');
          artifacts.benchmarkError = String(benchmark?.error || '');
        } catch (error) {
          artifacts.benchmarkError = String(error?.message || error || '');
        }
      }
    } else if (section === 'drawdown') {
      artifacts.drawdownSeries = normalizeDrawdownSectionData(Array.isArray(data) ? data : []);
    } else if (section === 'symbol_stats') {
      artifacts.symbolPerformanceRows = normalizeSymbolStatsSectionData(Array.isArray(data) ? data : []);
    } else if (section === 'stage_funnel') {
      artifacts.funnelRows = Array.isArray(data) ? cloneJson(data) || [] : [];
    } else if (section === 'run_meta') {
      const normalizeRunMetaCounters = globalScope.normalizeRunMetaCounters;
      artifacts.run_meta = typeof normalizeRunMetaCounters === 'function'
        ? normalizeRunMetaCounters(data || {})
        : (cloneJson(data) || {});
    } else if (section === 'config') {
      artifacts.config = data && typeof data === 'object' ? cloneJson(data) : null;
    } else if (section === 'trades') {
      artifacts.tradesRows = Array.isArray(data) ? cloneJson(data) || [] : [];
    } else if (section === 'daily') {
      const dailyRows = Array.isArray(data) ? cloneJson(data) || [] : [];
      artifacts.dailyRows = dailyRows;
      const parseMarketStates = globalScope._parseMarketStates;
      artifacts.marketStates = typeof parseMarketStates === 'function' ? parseMarketStates(dailyRows) : [];
    } else if (section === 'reason_codes') {
      artifacts.reasonRows = Array.isArray(data) ? cloneJson(data) || [] : [];
    } else if (section === 'stock_names') {
      artifacts.stockNames = data && typeof data === 'object' ? cloneJson(data) || {} : {};
    }

    nextSnapshot.artifacts = artifacts;
    return nextSnapshot;
  }

  function buildDesktopResultsWorkbenchSnapshot(args) {
    const state = args && args.state ? args.state : {};
    const currentSnapshot = args && args.currentSnapshot ? args.currentSnapshot : {};
    const currentView = currentSnapshot && currentSnapshot.view ? currentSnapshot.view : {};
    const viewPatch = args && args.viewPatch && typeof args.viewPatch === 'object' ? args.viewPatch : {};
    const openPanels = args && args.openPanels ? args.openPanels : (currentView.openPanels || {});
    const runtimeSourceKind = String(state.runtime_source_kind || '').trim()
      || (state.active_manifest && state.active_manifest.exp_id ? 'experiment' : '');
    const runtimeSourceId = String(state.runtime_source_id || '').trim()
      || String((state.active_manifest && state.active_manifest.exp_id) || '');
    const sourceKind = String((args && args.sourceKind) || runtimeSourceKind || state.loaded_source_kind || '').trim()
      || (state.active_result && state.active_result.exp_id ? 'experiment' : '');
    const sourceId = String((args && args.sourceId) || runtimeSourceId || state.loaded_source_id || '').trim()
      || String((state.active_result && state.active_result.exp_id) || '');
    const currentArtifacts = currentSnapshot && currentSnapshot.artifacts ? cloneJson(currentSnapshot.artifacts) : {};
    const assetContext = cloneJson(
      state.active_asset_context
      || state.loaded_source_asset_context
      || currentSnapshot?.assetContext
      || currentArtifacts?.assetContext
      || {},
    ) || {};
    return {
      active: !!((state.active_result && state.active_result.exp_id) || state.active_artifacts),
      source: {
        kind: sourceKind,
        id: sourceId,
      },
      assetContext,
      result: cloneJson(state.active_result) || null,
      manifest: cloneJson(state.active_manifest) || null,
      artifacts: {
        ...(currentArtifacts || {}),
        ...(cloneJson(state.active_artifacts) || {}),
      },
      surface: cloneJson(currentSnapshot.surface) || null,
      view: {
        chartMode: String(viewPatch.chartMode || state.chart_mode || currentView.chartMode || 'portfolio'),
        chartRange: String(viewPatch.chartRange || state.chart_range || currentView.chartRange || 'D'),
        showBenchmark: typeof viewPatch.showBenchmark === 'boolean'
          ? !!viewPatch.showBenchmark
          : (typeof state.chart_show_benchmark === 'boolean'
          ? state.chart_show_benchmark
          : !!currentView.showBenchmark),
        symbolFilter: String(viewPatch.symbolFilter || state.symbol_filter || currentView.symbolFilter || ''),
        symbolSort: String(viewPatch.symbolSort || state.symbol_sort || currentView.symbolSort || 'return_desc'),
        selectedSymbol: String(viewPatch.selectedSymbol || state.selected_symbol || currentView.selectedSymbol || '').toLowerCase(),
        openPanels: {
          ...(currentView.openPanels || {}),
          ...(openPanels || {}),
        },
      },
    };
  }

  async function publishDesktopResultsWorkbenchSnapshot(args) {
    const state = args && args.state ? args.state : {};
    const bridge = getDesktopResultsWorkbenchBridge();
    if (!bridge || typeof bridge.setSnapshot !== 'function') return false;
    const currentSnapshot = typeof bridge.getSnapshot === 'function' ? (bridge.getSnapshot() || {}) : {};
    const openPanels = args && args.openPanels ? args.openPanels : (currentSnapshot?.view?.openPanels || {});
    const expId = currentExperimentId(state);
    let snapshot = buildDesktopResultsWorkbenchSnapshot({
      state,
      currentSnapshot,
      viewPatch: args?.viewPatch,
      openPanels,
      sourceKind: args?.sourceKind,
      sourceId: args?.sourceId,
    });

    const lazySections = resolveLazySectionsForSnapshot(snapshot, args?.lazySections || []);

    if (expId) {
      try {
        const surface = await ensureDesktopExperimentSurface(state, expId);
        if (surface && currentExperimentId(state) === expId) {
          snapshot = mergeDesktopSurfaceIntoSnapshot(snapshot, surface);
        }
      } catch (_) {
        // Surface fetch should not break the local snapshot publish path.
      }
    }

    if (expId && currentExperimentId(state) === expId && lazySections.length) {
      const payloads = await Promise.all(lazySections.map(async (section) => {
        try {
          return await ensureDesktopExperimentSurfaceSection(state, expId, section);
        } catch (_) {
          return null;
        }
      }));
      for (const payload of payloads) {
        if (!payload || currentExperimentId(state) !== expId) continue;
        snapshot = await mergeDesktopSurfaceSectionIntoSnapshot(snapshot, state, expId, payload, {
          reuseExistingBenchmark: true,
        });
      }
    }

    bridge.setSnapshot(snapshot);
    return true;
  }

  globalScope.getDesktopResultsWorkbenchBridge = getDesktopResultsWorkbenchBridge;
  globalScope.ensureDesktopExperimentSurface = ensureDesktopExperimentSurface;
  globalScope.ensureDesktopExperimentSurfaceSection = ensureDesktopExperimentSurfaceSection;
  globalScope.buildDesktopResultsWorkbenchSnapshot = buildDesktopResultsWorkbenchSnapshot;
  globalScope.publishDesktopResultsWorkbenchSnapshot = publishDesktopResultsWorkbenchSnapshot;
  globalScope.clearDesktopResultsWorkbenchState = clearDesktopResultsWorkbenchState;
})(window);
