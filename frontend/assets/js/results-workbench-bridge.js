(function initResultsWorkbenchBridge(globalScope) {
  const listeners = new Set();

  function cloneJson(value) {
    if (value == null) return value;
    try {
      return JSON.parse(JSON.stringify(value));
    } catch (_) {
      return value;
    }
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
        listener(cloneJson(bridge.snapshot));
      } catch (_) {
        // subscriber failure should not break bridge setup
      }
      return function unsubscribe() {
        listeners.delete(listener);
      };
    },
    getSnapshot() {
      return cloneJson(bridge.snapshot);
    },
    setSnapshot(nextSnapshot) {
      const base = createEmptySnapshot();
      bridge.snapshot = {
        ...base,
        ...cloneJson(nextSnapshot || {}),
        source: {
          ...base.source,
          ...(cloneJson(nextSnapshot?.source || {}) || {}),
        },
        view: {
          ...base.view,
          ...(cloneJson(nextSnapshot?.view || {}) || {}),
          openPanels: {
            ...base.view.openPanels,
            ...(cloneJson(nextSnapshot?.view?.openPanels || {}) || {}),
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
          ...(cloneJson(patch || {}) || {}),
          openPanels: {
            ...(bridge.snapshot.view?.openPanels || {}),
            ...(cloneJson(patch?.openPanels || {}) || {}),
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
      const payload = cloneJson(bridge.snapshot);
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
