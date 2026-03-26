const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const LOAD_SCRIPT = path.join(PROJECT_ROOT, 'frontend', 'assets', 'js', 'pages', 'desktop-load-controls.js');

class FakeElement {
  constructor(id = '', tagName = 'div') {
    this.id = id;
    this.tagName = String(tagName || 'div').toUpperCase();
    this.children = [];
    this.parentElement = null;
    this.innerHTML = '';
    this.textContent = '';
    this.className = '';
    this.hidden = false;
  }

  appendChild(child) {
    if (!child) return child;
    child.parentElement = this;
    this.children.push(child);
    return child;
  }

  addEventListener() {}

  remove() {
    if (!this.parentElement) return;
    this.parentElement.children = this.parentElement.children.filter((item) => item !== this);
    this.parentElement = null;
  }

  contains(target) {
    if (target === this) return true;
    return this.children.some((child) => child === target || (typeof child.contains === 'function' && child.contains(target)));
  }
}

function createContext() {
  const elements = new Map();
  const commandBar = new FakeElement('wbCmdRight', 'div');
  const quickLoad = new FakeElement('wbQuickLoad', 'button');
  const runBtn = new FakeElement('wbRunBtn', 'button');
  const runStatus = new FakeElement('wbRunStatus', 'div');
  commandBar.appendChild(quickLoad);
  commandBar.appendChild(runBtn);
  commandBar.appendChild(runStatus);
  elements.set('wbQuickLoad', quickLoad);
  elements.set('wbRunBtn', runBtn);
  elements.set('wbRunStatus', runStatus);

  const document = {
    getElementById(id) {
      return elements.get(String(id)) || null;
    },
    createElement(tagName) {
      return new FakeElement('', tagName);
    },
    addEventListener() {},
    removeEventListener() {},
  };

  const loaded = [];
  const context = {
    window: null,
    document,
    state: { loaded_source_id: '', loaded_source_kind: '' },
    byId(id) {
      return document.getElementById(id);
    },
    apiRequestJson: async (_tag, url) => {
      if (String(url).includes('/configs?')) {
        return {
          items: [
            {
              config_id: 'cfg_cn_stock_etf_v1',
              display_name: 'A股个股+ETFV1',
              source_type: 'template',
              owner: 'manual',
              locked: true,
              universe_mode: 'HS300_ZZ500',
              saved_at: '2026-03-25T13:16:00.278707',
              tags: ['frontier', 'template'],
            },
          ],
        };
      }
      if (String(url).includes('/baselines')) {
        return { items: [{ baseline_id: 'baseline_V10_2', display_name: 'baseline_V10.2' }] };
      }
      if (String(url).includes('/experiments')) {
        return { items: [{ exp_id: 'exp_demo', created_at: '2026-03-25T10:00:00', perf: { cagr: 0.1, max_drawdown: -0.2 } }] };
      }
      throw new Error(`unexpected url ${url}`);
    },
    normalizeLoadItems(baselines, experiments) {
      return [
        ...(Array.isArray(baselines) ? baselines.map((item) => ({ kind: 'baseline', id: item.baseline_id, label: item.display_name })) : []),
        ...(Array.isArray(experiments) ? experiments.map((item) => ({ kind: 'experiment', id: item.exp_id, label: item.exp_id, cagr: item.perf?.cagr, max_drawdown: item.perf?.max_drawdown })) : []),
      ];
    },
    enrichLoadItems: async (items) => items,
    loadItemBadgeLabel(item) {
      if (item?.kind === 'config') return 'Config';
      return item?.kind === 'baseline' ? 'Baseline' : 'Experiment';
    },
    loadItemBadgeClass(item) {
      if (item?.kind === 'config') return 'wb-load-kind-config';
      return item?.kind === 'baseline' ? 'wb-load-kind-baseline' : 'wb-load-kind-experiment';
    },
    experimentLoadSummary(item) {
      return item?.kind === 'baseline' ? 'Has result' : 'CAGR 10.00% | MaxDD -20.00%';
    },
    configDisplayName(item) {
      return String(item?.display_name || item?.config_id || '');
    },
    loadConfig: async (id) => {
      loaded.push(['config', id]);
    },
    loadBaselineToWorkbench: async (id) => {
      loaded.push(['baseline', id]);
    },
    loadExperimentBundle: async (id) => {
      loaded.push(['experiment', id]);
    },
    setTextById(id, text) {
      const element = document.getElementById(id);
      if (element) element.textContent = String(text || '');
    },
    setStatusItems() {},
    addLog() {},
    esc(value) {
      return String(value ?? '');
    },
    setTimeout(fn) {
      fn();
      return 1;
    },
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(LOAD_SCRIPT, 'utf8'), context, { filename: 'desktop-load-controls.js' });
  return { context, commandBar, loaded };
}

test('openExperimentLoadDropdown pins the default config above anchors, baselines, and experiments', async () => {
  const { context, commandBar } = createContext();

  await context.openExperimentLoadDropdown(context.byId('wbQuickLoad'));

  const dropdown = commandBar.children.find((child) => child.id === 'wbLoadDropdown');
  assert.ok(dropdown, 'expected quick-load dropdown to be attached');
  const payload = dropdown.children.map((child) => `${child.textContent || ''}${child.innerHTML || ''}`).join('\n');

  assert.match(payload, /默认配置/);
  assert.match(payload, /A股个股\+ETFV1/);
  assert.match(payload, /配置锚点|基线/);
  assert.match(payload, /基线/);
  assert.match(payload, /实验结果/);
});
