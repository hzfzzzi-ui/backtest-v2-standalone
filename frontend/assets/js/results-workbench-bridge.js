/* results-workbench-bridge.js: transition bridge between desktop shell and Vue workbench. */
(function initResultsWorkbenchBridge(globalScope) {
  const listeners = new Set();

  function shallowClone(value) {
    if (Array.isArray(value)) return value.slice();
    if (value && typeof value === 'object') return { ...value };
    return value;
  }

  function createEmptySnapshot() {
    return {
      active: false,
      source: {
        kind: '',
        id: '',
      },
      result: null,
      artifacts: null,
      view: {
        chartMode: 'portfolio',
        chartRange: 'D',
        showBenchmark: true,
        symbolFilter: '',
        symbolSort: 'return_desc',
        selectedSymbol: '',
        openPanels: {},
      },
      updatedAt: null,
    };
  }

  const bridge = {
    snapshot: createEmptySnapshot(),
    mounted: false,
    subscribe(listener) {
      if (typeof listener !== 'function') return function noop() {};
      listeners.add(listener);
      try {
        listener(bridge.snapshot);
      } catch (_) {
        // subscriber failure should not break bridge setup
      }
      return function unsubscribe() {
        listeners.delete(listener);
      };
    },
    getSnapshot() {
      return bridge.snapshot;
    },
    setSnapshot(nextSnapshot) {
      const base = createEmptySnapshot();
      bridge.snapshot = {
        ...base,
        ...(nextSnapshot || {}),
        source: {
          ...base.source,
          ...(shallowClone(nextSnapshot?.source || {}) || {}),
        },
        view: {
          ...base.view,
          ...(shallowClone(nextSnapshot?.view || {}) || {}),
          openPanels: {
            ...base.view.openPanels,
            ...(shallowClone(nextSnapshot?.view?.openPanels || {}) || {}),
          },
        },
        updatedAt: new Date().toISOString(),
      };
      bridge.emit();
    },
    patchViewState(patch) {
      bridge.snapshot = {
        ...bridge.snapshot,
        view: {
          ...bridge.snapshot.view,
          ...(shallowClone(patch || {}) || {}),
          openPanels: {
            ...(bridge.snapshot.view?.openPanels || {}),
            ...(shallowClone(patch?.openPanels || {}) || {}),
          },
        },
        updatedAt: new Date().toISOString(),
      };
      bridge.emit();
    },
    clear() {
      bridge.snapshot = createEmptySnapshot();
      bridge.snapshot.updatedAt = new Date().toISOString();
      bridge.emit();
    },
    setMounted(value) {
      bridge.mounted = !!value;
      bridge.emit();
    },
    isMounted() {
      return !!bridge.mounted;
    },
    emit() {
      const payload = bridge.snapshot;
      listeners.forEach((listener) => {
        try {
          listener(payload, { mounted: !!bridge.mounted });
        } catch (_) {
          // listener failures are isolated
        }
      });
    },
  };

  globalScope.resultsWorkbenchBridge = bridge;
})(window);
