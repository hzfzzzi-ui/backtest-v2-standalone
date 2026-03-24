import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const EXP_DIR = path.join(PROJECT_ROOT, 'outputs', 'experiments', 'exp_20260309_011329170_a9f5');
const HAS_FIXTURE = fs.existsSync(path.join(EXP_DIR, 'perf.json'));

function prepareResultsFormattingModule() {
  const sourceDir = path.join(PROJECT_ROOT, 'frontend', 'app', 'results-workbench', 'helpers');
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'multi-alpha-results-'));
  for (const name of ['stageFunnelFormatting', 'agentReportFormatting', 'resultsFormatting']) {
    let text = fs.readFileSync(path.join(sourceDir, `${name}.js`), 'utf8');
    text = text.replaceAll('./stageFunnelFormatting.js', './stageFunnelFormatting.mjs');
    text = text.replaceAll('./agentReportFormatting.js', './agentReportFormatting.mjs');
    fs.writeFileSync(path.join(tempDir, `${name}.mjs`), text, 'utf8');
  }
  return import(pathToFileURL(path.join(tempDir, 'resultsFormatting.mjs')).href);
}

const resultsFormatting = await prepareResultsFormattingModule();

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let inQuotes = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (inQuotes) {
      if (char === '"' && next === '"') {
        cell += '"';
        index += 1;
      } else if (char === '"') {
        inQuotes = false;
      } else {
        cell += char;
      }
      continue;
    }
    if (char === '"') {
      inQuotes = true;
      continue;
    }
    if (char === ',') {
      row.push(cell);
      cell = '';
      continue;
    }
    if (char === '\r') continue;
    if (char === '\n') {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = '';
      continue;
    }
    cell += char;
  }
  if (cell.length || row.length) {
    row.push(cell);
    rows.push(row);
  }
  if (!rows.length) return [];
  const [header, ...body] = rows;
  return body.filter((cols) => cols.length && cols.some((value) => String(value).trim().length)).map((cols) => Object.fromEntries(header.map((key, idx) => [key, cols[idx] ?? ''])));
}

function loadJson(name) {
  return JSON.parse(fs.readFileSync(path.join(EXP_DIR, name), 'utf8'));
}

function loadCsv(name) {
  return parseCsv(fs.readFileSync(path.join(EXP_DIR, name), 'utf8'));
}

function buildSnapshot() {
  const perf = loadJson('perf.json');
  const audit = loadJson('audit.json');
  const config = loadJson('config.json');
  const runMeta = loadJson('run_meta.json');
  const symbolRows = loadJson('symbol_performance.json').rows || [];
  const navSeries = loadCsv('nav.csv').map((row) => ({
    date: row.date,
    value: Number(row.nav),
  }));
  const tradesRows = loadCsv('trades.csv');
  const reasonRows = loadCsv('reason_codes.csv');
  const dailyRows = loadCsv('portfolio_daily.csv');
  return {
    result: {
      exp_id: runMeta.exp_id,
      status: runMeta.status,
      cagr: perf.cagr,
      total_return: perf.total_return,
      max_drawdown: perf.max_drawdown,
      sharpe: perf.sharpe,
      calmar: perf.calmar,
      trades: perf.trades,
      turnover: perf.turnover,
    },
    artifacts: {
      perf,
      audit,
      config,
      run_meta: runMeta,
      navSeries,
      tradesRows,
      reasonRows,
      dailyRows,
      symbolPerformanceRows: symbolRows,
    },
  };
}

test('results formatting exposes composite summary and source-aware trade fields', { skip: !HAS_FIXTURE }, () => {
  const snapshot = buildSnapshot();
  const summary = resultsFormatting.summarizeSnapshot(snapshot);
  const trades = resultsFormatting.normalizeTradesRows(snapshot);
  const markdown = resultsFormatting.buildAgentMarkdown(snapshot);

  assert.equal(summary.strategy, 'COMPOSITE');
  assert.equal(summary.portfolioMode, 'hard_sleeve_budget');
  assert.match(summary.strategyCore, /Breakout 55/);
  assert.match(summary.strategySummary, /REGIME_ROUTE/);
  assert.match(summary.strategySummary, /SOURCE_ONLY/);
  assert.match(summary.auditSummary.composedSignals, /RSI Reversal/);
  assert.match(summary.auditSummary.sourceOnlyExitCount, /97/);

  assert.ok(trades.some((row) => row.entry_alpha_id === 'rsi_reversal'));
  assert.ok(trades.some((row) => row.entry_alpha_id === 'breakout_55'));
  assert.ok(trades.some((row) => row.exit_owner && row.exit_owner !== '-'));

  assert.match(markdown, /## 6\. Multi-Alpha Audit/);
  assert.match(markdown, /## 7\. Strategy Config/);
  assert.match(markdown, /COMPOSITE/);
  assert.match(markdown, /Breakout 55 \+ RSI Reversal/);
  assert.match(markdown, /source_only_exit_count/);
});

test('normalizeSymbolRows derives return_pct from pnl and buy_notional when artifact return is missing', () => {
  const rows = resultsFormatting.normalizeSymbolRows({
    artifacts: {
      symbolPerformanceRows: [
        {
          symbol: 'SZ000001',
          return_pct: '',
          net_pnl: '2500',
          buy_notional: '10000',
          max_drawdown: '-0.12',
          trades: '2',
        },
      ],
    },
  });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].symbol, 'sz000001');
  assert.equal(rows[0].return_pct, 0.25);
  assert.equal(rows[0].max_drawdown, -0.12);
  assert.equal(rows[0].trades, 2);
});

test('results formatting surfaces governed regime snapshot from formal fields instead of legacy market_state', () => {
  const summary = resultsFormatting.summarizeSnapshot({
    result: {
      exp_id: 'exp_governed',
      status: 'OK',
    },
    artifacts: {
      perf: {},
      run_meta: {
        governed_snapshot: {
          base_state: 'TRANS_DOWN',
          effective_state: 'LIGHT',
          coarse_state: 'RISK_OFF',
          effective_coarse_state: 'NEUTRAL',
          risk_budget_multiplier: 0.5,
          total_risk_budget: 0.3,
          total_exposure_cap: 0.35,
          defense_bias: 0.6,
          budget_reason_codes: ['TOTAL_RISK_BUDGET_REDUCED'],
        },
        regime: {
          latest_state: {
            base_state: 'TRANS_DOWN',
            effective_state: 'LIGHT',
            coarse_state: 'RISK_OFF',
            effective_coarse_state: 'NEUTRAL',
            reason_codes: ['BREADTH_WEAK', 'COOLDOWN_HOLD'],
            manual_override: {
              active: true,
              scope: 'state_override',
              target_state_5: 'LIGHT',
              reason: 'MANUAL_HOLD',
            },
          },
        },
      },
      navSeries: [],
      benchmarkSeries: [],
      tradesRows: [],
      symbolPerformanceRows: [],
      audit: { summary: {} },
      missing: [],
    },
  });

  assert.equal(summary.hasGovernedSnapshot, true);
  assert.equal(summary.governedBaseState, 'TRANS_DOWN');
  assert.equal(summary.governedEffectiveState, 'LIGHT');
  assert.equal(summary.governedEffectiveCoarseState, 'NEUTRAL');
  assert.equal(summary.governedRiskBudgetMultiplier, '0.50');
  assert.equal(summary.governedTotalRiskBudget, '30.00%');
  assert.equal(summary.governedTotalExposureCap, '35.00%');
  assert.equal(summary.governedDefenseBias, '60.00%');
  assert.match(summary.governedReasonCodes, /BREADTH_WEAK/);
  assert.match(summary.governedBudgetReasonCodes, /TOTAL_RISK_BUDGET_REDUCED/);
  assert.match(summary.governedManualOverride, /MANUAL_HOLD/);
});
