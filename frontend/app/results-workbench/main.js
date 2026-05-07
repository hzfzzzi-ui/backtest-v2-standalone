import { createApp } from 'vue';
import App from './App.vue';

// main.js: sole visible DOM owner for #wbResultsWorkbenchMount after Vue mount.
function mountResultsWorkbench() {
  const mountEl = document.getElementById('wbResultsWorkbenchMount');
  const bridge = typeof window.getDesktopResultsWorkbenchBridge === 'function'
    ? window.getDesktopResultsWorkbenchBridge()
    : (window.resultsWorkbenchBridge || null);
  if (!mountEl || !bridge) return;
  mountEl.dataset.vueShell = 'starting';
  delete mountEl.dataset.vueError;
  delete mountEl.dataset.vueReason;

  try {
    createApp(App).mount(mountEl);
    mountEl.hidden = false;
    mountEl.dataset.vueShell = 'mounted';
    if (typeof bridge.setMounted === 'function') bridge.setMounted(true);
    if (window.desktopAppShell && typeof window.desktopAppShell.markWorkspaceMounted === 'function') {
      window.desktopAppShell.markWorkspaceMounted('results_workspace', true);
    }
    if (window.desktopAppShell && typeof window.desktopAppShell.setActiveWorkspace === 'function') {
      window.desktopAppShell.setActiveWorkspace('results_workspace');
    }
  } catch (error) {
    console.error('results-workbench-vue-shell mount failed:', error);
    mountEl.hidden = true;
    mountEl.dataset.vueShell = 'failed';
    mountEl.dataset.vueError = String(error?.message || error || 'unknown');
    mountEl.dataset.vueReason = 'mount-failed';
    if (typeof bridge.setMounted === 'function') bridge.setMounted(false);
    if (window.desktopAppShell && typeof window.desktopAppShell.markWorkspaceMounted === 'function') {
      window.desktopAppShell.markWorkspaceMounted('results_workspace', false);
    }
    if (window.desktopAppShell && typeof window.desktopAppShell.setActiveWorkspace === 'function') {
      window.desktopAppShell.setActiveWorkspace('config_workspace');
    }
  }
}

if (document.getElementById('wbResultsWorkbenchMount')) {
  mountResultsWorkbench();
} else if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mountResultsWorkbench, { once: true });
} else {
  mountResultsWorkbench();
}
