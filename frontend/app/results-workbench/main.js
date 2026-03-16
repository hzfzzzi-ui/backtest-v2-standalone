import { createApp } from 'vue';
import App from './App.vue';

function mountResultsWorkbench() {
  const mountEl = document.getElementById('wbResultsWorkbenchMount');
  const bridge = window.resultsWorkbenchBridge || null;
  if (!mountEl || !bridge) return;
  mountEl.dataset.vueShell = 'starting';
  delete mountEl.dataset.vueError;
  delete mountEl.dataset.vueReason;

  try {
    createApp(App).mount(mountEl);
    mountEl.hidden = false;
    mountEl.dataset.vueShell = 'mounted';
    if (typeof bridge.setMounted === 'function') bridge.setMounted(true);
  } catch (error) {
    console.error('results-workbench-vue-shell mount failed:', error);
    mountEl.hidden = true;
    mountEl.dataset.vueShell = 'failed';
    mountEl.dataset.vueError = String(error?.message || error || 'unknown');
    mountEl.dataset.vueReason = 'mount-failed';
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
