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

test('results formatting builds regime, governor and attribution panel models from formal snapshot fields', () => {
  const snapshot = {
    result: { exp_id: 'exp_panel', status: 'OK' },
    artifacts: {
      perf: {},
      run_meta: {
        regime: {
          latest_state: {
            base_state: 'TRANS_DOWN',
            effective_state: 'LIGHT',
            coarse_state: 'RISK_OFF',
            effective_coarse_state: 'NEUTRAL',
            confidence: 0.62,
            risk_budget_multiplier: 0.5,
            reason_codes: ['BREADTH_WEAK', 'COOLDOWN_HOLD'],
            manual_override: {
              active: true,
              scope: 'state_override',
              target_state_5: 'LIGHT',
              reason: 'MANUAL_HOLD',
            },
            subscores: {
              technical: 0.48,
              sentiment: 0.31,
            },
            block_scores: {
              breadth_block: 0.22,
            },
            state_stability_metrics: {
              cooldown_active: true,
            },
          },
        },
        governed_snapshot: {
          asset_scope: 'cn_etf',
          budget_owner: 'global_portfolio_governor',
          budget_consumer_sleeve_id: 'cn_etf_beta',
          budget_consumer_system_role: 'market_beta_sleeve',
          total_risk_budget: 0.3,
          total_exposure_cap: 0.35,
          drawdown_state: 'REDUCED',
          recovery_state: 'RECOVERY_PENDING',
          cooldown_state: 'INACTIVE',
          defense_floor: 0.1,
          budget_reason_codes: ['TOTAL_RISK_BUDGET_REDUCED'],
          sleeve_budgets: {
            cn_etf_beta: {
              system_role: 'market_beta_sleeve',
              slot_cap: 2,
              available_slots: 1,
              selected_count: 1,
              candidate_count: 2,
              budget_share: 0.5,
            },
          },
        },
        attribution: {
          summary: {
            state_log_count: 12,
            budget_log_count: 24,
            sleeve_log_count: 3,
            manual_override_log_count: 1,
            state_transition_count: 4,
            budget_change_count: 6,
            reason_code_family_count: 2,
            latest_state_date: '2026-03-20',
            latest_budget_date: '2026-03-20',
            latest_manual_override_date: '2026-03-19',
            sleeves: ['cn_etf_beta'],
          },
          reason_code_summary: {
            budget_reason_codes: {
              TOTAL_RISK_BUDGET_REDUCED: 24,
            },
            sleeve_reason_codes: {
              FORMAL_CORE_BETA: 4,
            },
            manual_override_reasons: {
              MANUAL_HOLD: 1,
            },
          },
          refs: {
            attribution_audit: 'attribution_audit.json',
          },
        },
      },
    },
  };

  const regimeModel = resultsFormatting.buildRegimePanelModel(snapshot);
  const governorModel = resultsFormatting.buildGovernorPanelModel(snapshot);
  const attributionModel = resultsFormatting.buildAttributionPanelModel(snapshot);

  assert.equal(regimeModel.baseState, 'TRANS_DOWN');
  assert.equal(regimeModel.effectiveState, 'LIGHT');
  assert.match(regimeModel.manualOverrideSummary, /MANUAL_HOLD/);
  assert.ok(regimeModel.subscores.some((entry) => entry.name === 'technical'));

  assert.equal(governorModel.consumerSleeveId, 'cn_etf_beta');
  assert.equal(governorModel.totalRiskBudget, '30.00%');
  assert.ok(governorModel.sleeveBudgets.some((entry) => entry.sleeveId === 'cn_etf_beta'));

  assert.equal(attributionModel.latestStateDate, '2026-03-20');
  assert.ok(attributionModel.budgetReasonCodes.some((entry) => entry.name === 'TOTAL_RISK_BUDGET_REDUCED'));
  assert.ok(attributionModel.manualOverrideReasons.some((entry) => entry.name === 'MANUAL_HOLD'));
});

test('results formatting detects research combo snapshots and surfaces combo component summary', () => {
  const summary = resultsFormatting.summarizeSnapshot({
    result: {
      exp_id: 'exp_combo',
      status: 'OK',
      total_return: 1.3050198284768593,
      cagr: 0.09319861164215593,
      max_drawdown: -0.1779555467413692,
      sharpe: 0.7556515416453639,
    },
    artifacts: {
      perf: {
        total_return: 1.3050198284768593,
        cagr: 0.09319861164215593,
        max_drawdown: -0.1779555467413692,
        sharpe: 0.7556515416453639,
      },
      run_meta: {
        data: {
          asset_scope: 'cn_a_equity',
          asset_role: 'research_combo',
          coverage_start: '2016-11-04',
          coverage_end: '2026-03-20',
          benchmark: 'CN_STOCK_ETF_50_50',
        },
        combo_metrics: {
          start: '2016-11-04',
          end: '2026-03-20',
        },
        combo_components: {
          stock_component: { exp_id: 'exp_stock' },
          etf_component: { exp_id: 'exp_etf' },
        },
        research_combo: {
          mode: 'daily_rebalanced_equal_weight_50_50',
          assumption: 'research_combo_daily_rebalanced_equal_weight_50_50',
          stock_nav_column: 'stock_nav',
          etf_nav_column: 'etf_nav',
        },
      },
      nav: [
        { date: '2016-11-04', nav: 1.0, stock_nav: 1000000, etf_nav: 1000000 },
        { date: '2026-03-20', nav: 2.3050198284768593, stock_nav: 4973000, etf_nav: 959600 },
      ],
      navSeries: [
        { date: '2016-11-04', value: 1.0 },
        { date: '2026-03-20', value: 2.3050198284768593 },
      ],
      benchmarkSeries: [],
      tradesRows: [],
      symbolPerformanceRows: [],
      audit: { summary: {} },
      missing: [],
    },
  });

  assert.equal(summary.isResearchCombo, true);
  assert.equal(summary.assetRole, 'research_combo');
  assert.equal(summary.universeSectionTitle, '组合研究口径');
  assert.equal(summary.universeMode, 'daily_rebalanced_equal_weight_50_50');
  assert.equal(summary.benchmark, '-');
  assert.equal(summary.comboStockExpId, 'exp_stock');
  assert.equal(summary.comboEtfExpId, 'exp_etf');
  assert.equal(summary.comboWindow, '2016-11-04 ~ 2026-03-20');
  assert.equal(summary.comboStockTotalReturn, '397.30%');
  assert.equal(summary.comboEtfTotalReturn, '-4.04%');
});

test('results formatting builds regime and governor models from backend combo truth payload', () => {
  const snapshot = {
    result: { exp_id: 'exp_combo_display', status: 'OK' },
    artifacts: {
      run_meta: {
        data: {
          asset_scope: 'cn_a_equity',
          asset_role: 'research_combo',
        },
      },
      comboTruth: {
        display: {
          regime: {
            available: true,
            base_state: '个股 TRANS_DOWN',
            effective_state: 'ETF RISK_OFF',
            coarse_state: '个股 RISK_OFF | ETF RISK_OFF',
            risk_budget_multiplier_text: '个股 60.00% | ETF 0.00%',
            reason_text: '个股 TRANS_DOWN | ETF RISK_OFF',
            manual_override_text: '无',
          },
          governor: {
            available: true,
            total_risk_budget_text: '个股 60.00% | ETF 0.00%',
            total_exposure_cap_text: '研究组合 daily_rebalanced_equal_weight_50_50',
            budget_consumer_text: 'cn_stock_trend_alpha_core + cn_etf_beta',
            budget_reason_text: '个股 TOTAL_RISK_BUDGET_REDUCED | ETF NO_DEPLOYABLE_SLOTS',
          },
        },
        components: {
          stock: {
            snapshot: {
              artifacts: {
                run_meta: {
                  regime: {
                    latest_state: {
                      effective_state: 'TRANS_DOWN',
                    },
                  },
                  governed_snapshot: {
                    budget_consumer_sleeve_id: 'cn_stock_trend_alpha_core',
                    budget_consumer_system_role: 'stock_alpha_sleeve',
                    total_risk_budget: 0.6,
                    effective_max_positions: 6,
                    budget_reason_codes: ['TOTAL_RISK_BUDGET_REDUCED'],
                  },
                },
              },
            },
          },
          etf: {
            snapshot: {
              artifacts: {
                run_meta: {
                  regime: {
                    latest_state: {
                      effective_state: 'RISK_OFF',
                    },
                  },
                  governed_snapshot: {
                    budget_consumer_sleeve_id: 'cn_etf_beta',
                    budget_consumer_system_role: 'market_beta_sleeve',
                    total_risk_budget: 0,
                    effective_max_positions: 0,
                    budget_reason_codes: ['NO_DEPLOYABLE_SLOTS'],
                  },
                },
              },
            },
          },
        },
      },
    },
  };

  const regimeModel = resultsFormatting.buildRegimePanelModel(snapshot);
  const governorModel = resultsFormatting.buildGovernorPanelModel(snapshot);

  assert.equal(regimeModel.available, true);
  assert.equal(regimeModel.baseState, '个股 TRANS_DOWN');
  assert.equal(regimeModel.effectiveState, 'ETF RISK_OFF');
  assert.match(regimeModel.reasonCodes.join(' | '), /个股 TRANS_DOWN/);
  assert.match(regimeModel.reasonCodes.join(' | '), /ETF RISK_OFF/);

  assert.equal(governorModel.available, true);
  assert.equal(governorModel.consumerSleeveId, 'cn_stock_trend_alpha_core + cn_etf_beta');
  assert.equal(governorModel.totalRiskBudget, '个股 60.00% | ETF 0.00%');
  assert.equal(governorModel.sleeveBudgets.length, 2);
});

test('results formatting treats unified runtime combo as combo result instead of ordinary single-sleeve run', () => {
  const summary = resultsFormatting.summarizeSnapshot({
    result: {
      exp_id: 'exp_unified_combo',
      status: 'OK',
      total_return: 0.12,
      cagr: 0.08,
      max_drawdown: -0.11,
      sharpe: 0.76,
    },
    artifacts: {
      perf: {
        total_return: 0.12,
        cagr: 0.08,
        max_drawdown: -0.11,
        sharpe: 0.76,
      },
      run_meta: {
        data: {
          asset_scope: 'cn_a_equity',
          asset_role: 'unified_multi_sleeve_combo',
          coverage_start: '2021-01-04',
          coverage_end: '2026-03-24',
          benchmark: 'CN_STOCK_ETF_50_50',
        },
        combo_metrics: {
          start: '2021-01-04',
          end: '2026-03-24',
        },
        combo_components: {
          stock_component: { exp_id: 'exp_stock' },
          etf_component: { exp_id: 'exp_etf' },
        },
        combo_result: {
          type: 'unified_runtime_combo',
          mode: 'daily_rebalanced_equal_weight_50_50',
          assumption: 'cn_stock_etf_unified_runtime_phase1_daily_rebalanced_equal_weight_50_50',
          stock_nav_column: 'stock_nav',
          etf_nav_column: 'etf_nav',
        },
      },
      nav: [
        { date: '2021-01-04', nav: 1.0, stock_nav: 1.0, etf_nav: 1.0 },
        { date: '2026-03-24', nav: 1.12, stock_nav: 1.35, etf_nav: 1.01 },
      ],
      navSeries: [
        { date: '2021-01-04', value: 1.0 },
        { date: '2026-03-24', value: 1.12 },
      ],
      benchmarkSeries: [],
      tradesRows: [],
      symbolPerformanceRows: [],
      audit: { summary: {} },
      missing: [],
    },
  });

  assert.equal(summary.isResearchCombo, false);
  assert.equal(summary.isUnifiedCombo, true);
  assert.equal(summary.isComboResult, true);
  assert.equal(summary.universeSectionTitle, '组合结果口径');
  assert.equal(summary.comboMode, 'daily_rebalanced_equal_weight_50_50');
  assert.match(summary.comboReadOnlyNote, /unified runtime/i);
  assert.equal(summary.comboStockExpId, 'exp_stock');
  assert.equal(summary.comboEtfExpId, 'exp_etf');
});
