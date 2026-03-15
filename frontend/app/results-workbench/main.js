import { createApp } from 'vue';
import App from './App.vue';

function mountResultsWorkbench() {
  const mountEl = document.getElementById('wbResultsWorkbenchMount');
  const fallbackRoot = document.getElementById('wbResultsFallbackRoot');
  const bridge = window.resultsWorkbenchBridge || null;
  if (!mountEl || !bridge) return;
  if (window.isDesktopFallbackRequested?.()) {
    mountEl.hidden = true;
    mountEl.dataset.vueShell = 'skipped';
    mountEl.dataset.vueReason = 'explicit-debug';
    window.setDesktopFallbackMode?.(true, 'explicit-debug');
    if (typeof bridge.setMounted === 'function') bridge.setMounted(false);
    return;
  }
  mountEl.dataset.vueShell = 'starting';
  delete mountEl.dataset.vueError;
  delete mountEl.dataset.vueReason;

  try {
    createApp(App).mount(mountEl);
    mountEl.hidden = false;
    mountEl.dataset.vueShell = 'mounted';
    window.setDesktopFallbackMode?.(false, 'vue-mounted');
    if (fallbackRoot) delete fallbackRoot.dataset.fallbackReason;
    if (typeof bridge.setMounted === 'function') bridge.setMounted(true);
  } catch (error) {
    console.error('results-workbench-vue-shell mount failed:', error);
    mountEl.hidden = true;
    mountEl.dataset.vueShell = 'failed';
    mountEl.dataset.vueError = String(error?.message || error || 'unknown');
    mountEl.dataset.vueReason = 'mount-failed';
    window.setDesktopFallbackMode?.(true, 'vue-mount-failed');
    if (typeof bridge.setMounted === 'function') bridge.setMounted(false);
  }
}

if (document.getElementById('wbResultsWorkbenchMount')) {
  mountResultsWorkbench();
} else if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mountResultsWorkbench, { once: true });
} else {
  mountResultsWorkbench();
}
