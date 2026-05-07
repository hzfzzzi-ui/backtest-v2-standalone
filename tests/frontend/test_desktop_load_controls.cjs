const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const LOAD_SCRIPT = path.join(PROJECT_ROOT, 'frontend', 'assets', 'js', 'desktop-shell', 'load-orchestration.js');

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
    this.type = '';
    this._listeners = new Map();
  }

  appendChild(child) {
    if (!child) return child;
    child.parentElement = this;
    this.children.push(child);
    return child;
  }

  addEventListener(type, handler) {
    const key = String(type || '');
    if (!this._listeners.has(key)) this._listeners.set(key, []);
    this._listeners.get(key).push(handler);
  }

  removeEventListener(type, handler) {
    const key = String(type || '');
    const handlers = this._listeners.get(key) || [];
    this._listeners.set(key, handlers.filter((item) => item !== handler));
  }

  async dispatchEvent(event) {
    const key = String(event?.type || '');
    const handlers = this._listeners.get(key) || [];
    for (const handler of handlers) {
      await handler.call(this, event);
    }
    return true;
  }

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

function findById(node, id) {
  if (!node) return null;
  if (node.id === id) return node;
  for (const child of node.children || []) {
    const found = findById(child, id);
    if (found) return found;
  }
  return null;
}

function createContext() {
  const commandBar = new FakeElement('wbCmdRight', 'div');
  const quickLoad = new FakeElement('wbQuickLoad', 'button');
  const runBtn = new FakeElement('wbRunBtn', 'button');
  const runStatus = new FakeElement('wbRunStatus', 'div');
  commandBar.appendChild(quickLoad);
  commandBar.appendChild(runBtn);
  commandBar.appendChild(runStatus);

  const elements = new Map([
    ['wbCmdRight', commandBar],
    ['wbQuickLoad', quickLoad],
    ['wbRunBtn', runBtn],
    ['wbRunStatus', runStatus],
  ]);

  const documentListeners = new Map();
  const document = {
    getElementById(id) {
      const normalized = String(id || '');
      if (elements.has(normalized)) return elements.get(normalized);
      for (const root of elements.values()) {
        const found = findById(root, normalized);
        if (found) return found;
      }
      return null;
    },
    createElement(tagName) {
      return new FakeElement('', tagName);
    },
    addEventListener(type, handler) {
      const key = String(type || '');
      if (!documentListeners.has(key)) documentListeners.set(key, []);
      documentListeners.get(key).push(handler);
    },
    removeEventListener(type, handler) {
      const key = String(type || '');
      const handlers = documentListeners.get(key) || [];
      documentListeners.set(key, handlers.filter((item) => item !== handler));
    },
  };

  const requestedUrls = [];
  const context = {
    window: null,
    document,
    state: { loaded_source_id: '', loaded_source_kind: '' },
    byId(id) {
      return document.getElementById(id);
    },
    apiRequestJson: async (_tag, url) => {
      requestedUrls.push(String(url));
      if (String(url).includes('/surface/config')) {
        return {
          data: {
            workbench_config: {
              asset_scope: 'cn_a_equity',
              universe: { start: '2021-01-01', end: '2021-12-31' },
            },
          },
        };
      }
      if (String(url).endsWith('/baselines/baseline_formal')) {
        return {
          config_json: {
            asset_scope: 'cn_a_equity',
            universe: { start: '2021-01-01', end: '2021-12-31' },
          },
          display_name: 'Formal Baseline',
          owner: 'manual',
          has_result: false,
        };
      }
      if (String(url).includes('/baselines')) {
        return {
          items: [
            { baseline_id: 'baseline_formal', display_name: 'Formal Baseline' },
          ],
        };
      }
      if (String(url).includes('/experiments')) {
        return {
          items: [
            {
              exp_id: 'exp_demo',
              created_at: '2026-03-25T10:00:00',
              perf: { cagr: 0.1, max_drawdown: -0.2 },
            },
          ],
        };
      }
      throw new Error(`unexpected url ${url}`);
    },
    normalizeLoadItems(baselines, experiments) {
      return [
        ...(Array.isArray(baselines) ? baselines.map((item) => ({
          kind: 'baseline',
          id: item.baseline_id,
          label: item.display_name,
        })) : []),
        ...(Array.isArray(experiments) ? experiments.map((item) => ({
          kind: 'experiment',
          id: item.exp_id,
          label: item.exp_id,
          cagr: item.perf?.cagr,
          max_drawdown: item.perf?.max_drawdown,
        })) : []),
      ];
    },
    enrichLoadItems: async (items) => items,
    loadItemBadgeLabel(item) {
      return item?.kind === 'baseline' ? 'Baseline' : 'Experiment';
    },
    loadItemBadgeClass(item) {
      return item?.kind === 'baseline' ? 'wb-load-kind-baseline' : 'wb-load-kind-experiment';
    },
    experimentLoadSummary(item) {
      return item?.kind === 'baseline' ? 'Has result' : 'CAGR 10.00% | MaxDD -20.00%';
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
  vm.runInContext(fs.readFileSync(LOAD_SCRIPT, 'utf8'), context, { filename: 'desktop-shell/load-orchestration.js' });
  return { context, commandBar, requestedUrls };
}

function findDropdown(commandBar) {
  return commandBar.children.find((child) => child.id === 'wbLoadDropdown') || null;
}

test('openExperimentLoadDropdown only renders baseline and experiment sections', async () => {
  const { context, commandBar } = createContext();

  await context.openExperimentLoadDropdown(context.byId('wbQuickLoad'));

  const dropdown = findDropdown(commandBar);
  assert.ok(dropdown, 'expected dropdown to be attached');

  const sectionHeaders = dropdown.children.filter((child) => child.className === 'wb-config-center-section');
  const baselineRows = dropdown.children.filter((child) => child.className.includes('wb-load-item-baseline'));
  const experimentRows = dropdown.children.filter((child) => child.className.includes('wb-load-item-experiment'));
  const loadRows = dropdown.children.filter((child) => child.className.includes('wb-load-item'));

  assert.equal(sectionHeaders.length, 2);
  assert.equal(loadRows.length, 2);
  assert.equal(baselineRows.length, 1);
  assert.equal(experimentRows.length, 1);
});

test('openExperimentLoadDropdown dispatches into current desktop-shell baseline and experiment flows', async () => {
  const { context, commandBar, requestedUrls } = createContext();

  await context.openExperimentLoadDropdown(context.byId('wbQuickLoad'));

  const dropdown = findDropdown(commandBar);
  assert.ok(dropdown, 'expected dropdown to be attached');

  const baselineRow = dropdown.children.find((child) => child.className.includes('wb-load-item-baseline'));
  assert.ok(baselineRow, 'expected baseline row');
  await baselineRow.dispatchEvent({ type: 'click' });
  assert.ok(requestedUrls.includes('/api/backtest_v2/baselines/baseline_formal'));

  await context.openExperimentLoadDropdown(context.byId('wbQuickLoad'));
  const secondDropdown = findDropdown(commandBar);
  const experimentRow = secondDropdown.children.find((child) => child.className.includes('wb-load-item-experiment'));
  assert.ok(experimentRow, 'expected experiment row');
  await experimentRow.dispatchEvent({ type: 'click' });
  assert.ok(requestedUrls.includes('/api/backtest_v2/experiments/exp_demo/surface/config'));
});
