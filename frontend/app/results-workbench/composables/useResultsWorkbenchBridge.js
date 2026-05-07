import { onBeforeUnmount, onMounted, shallowRef } from 'vue';

function emptySnapshot() {
  return {
    active: false,
    source: { kind: '', id: '' },
    assetContext: {},
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

export function useResultsWorkbenchBridge() {
  const snapshot = shallowRef(emptySnapshot());
  let unsubscribe = null;

  const bridge = typeof window.getDesktopResultsWorkbenchBridge === 'function'
    ? window.getDesktopResultsWorkbenchBridge()
    : (window.resultsWorkbenchBridge || null);

  onMounted(() => {
    if (!bridge || typeof bridge.subscribe !== 'function') return;
    unsubscribe = bridge.subscribe((nextSnapshot) => {
      snapshot.value = nextSnapshot || emptySnapshot();
    });
  });

  onBeforeUnmount(() => {
    if (typeof unsubscribe === 'function') unsubscribe();
  });

  const patchViewState = (patch) => {
    if (typeof window.patchDesktopResultsWorkbenchViewState === 'function') {
      window.patchDesktopResultsWorkbenchViewState(patch || {});
      return;
    }
    if (bridge && typeof bridge.patchViewState === 'function') bridge.patchViewState(patch || {});
  };

  return {
    snapshot,
    patchViewState,
    bridge,
  };
}
