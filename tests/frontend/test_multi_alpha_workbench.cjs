const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const {
  createWorkbenchHarness,
  loadAcceptanceRequest,
  normalizeDraftForAcceptance,
  clone,
} = require('./multi_alpha_workbench_harness.cjs');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');

function readJsonIfExists(...parts) {
  const filePath = path.join(PROJECT_ROOT, ...parts);
  if (!fs.existsSync(filePath)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function moduleSummary(draft) {
  return {
    signal_generation: (draft.signal_generation?.modules || []).map((module) => ({
      name: module.name,
      alpha_id: module.alpha_id,
      family: module.family,
    })),
    signal_composition: {
      compose_mode: draft.signal_composition?.compose_mode,
      same_symbol_policy: draft.signal_composition?.same_symbol_policy,
      holding_ownership: draft.signal_composition?.holding_ownership,
      modules: (draft.signal_composition?.modules || []).map((module) => ({
        name: module.name,
        role: module.role,
        weight: module.weight,
        priority: module.priority,
      })),
      regime_matrix: clone(draft.signal_composition?.regime_matrix || {}),
    },
    portfolio_mode: draft.position_risk?.portfolio_mode,
  };
}

test('buildConfigDraft emits canonical multi-alpha config when composition is enabled', () => {
  const { context } = createWorkbenchHarness();
  context.byId('wbEnableComposition').checked = true;
  context.byId('wbPortfolioMode').value = 'hard_sleeve_budget';

  const draft = context.buildConfigDraft();
  const summary = moduleSummary(draft);

  assert.equal(draft.strategy_pack, 'COMPOSITE');
  assert.deepEqual(summary.signal_generation, [
    { name: 'breakout_55', alpha_id: 'breakout_55', family: 'trend' },
    { name: 'rsi_reversal', alpha_id: 'rsi_reversal', family: 'mean_revert' },
  ]);
  assert.equal(summary.signal_composition.compose_mode, 'REGIME_ROUTE');
  assert.equal(summary.signal_composition.same_symbol_policy, 'PREFER_HIGHER_SCORE');
  assert.equal(summary.signal_composition.holding_ownership, 'SOURCE_ONLY');
  assert.deepEqual(summary.signal_composition.modules, [
    { name: 'breakout_55', role: 'trend', weight: 0.7, priority: 100 },
    { name: 'rsi_reversal', role: 'mean_revert', weight: 0.3, priority: 80 },
  ]);
  assert.deepEqual(summary.signal_composition.regime_matrix, {
    TREND_UP: ['breakout_55'],
    RANGE: ['breakout_55', 'rsi_reversal'],
    WEAK_DOWN: ['rsi_reversal'],
  });
  assert.equal(summary.portfolio_mode, 'hard_sleeve_budget');
});

test('buildConfigDraft emits star-market filter only when enabled or loaded', () => {
  const { context } = createWorkbenchHarness();

  let draft = context.buildConfigDraft();
  assert.equal(Object.prototype.hasOwnProperty.call(draft.universe.filters, 'exclude_star_market'), false);

  context.byId('wbExcludeStarMarket').checked = true;
  draft = context.buildConfigDraft();
  assert.equal(draft.universe.filters.exclude_star_market, true);
});

test('applyConfigToUI round-trips the phase1 acceptance config semantics', () => {
  const request = loadAcceptanceRequest();
  const expected = normalizeDraftForAcceptance(request.config_json);
  const { context } = createWorkbenchHarness();
  context.state.loaded_source_config = clone(request.config_json);

  context.applyConfigToUI(clone(request.config_json));
  const actual = normalizeDraftForAcceptance(context.state.config_draft);

  assert.deepEqual(actual, expected);
  assert.equal(context.byId('wbEnableComposition').checked, true);
  assert.equal(context.byId('wbComposeMode').value, 'REGIME_ROUTE');
  assert.equal(context.byId('wbSameSymbolPolicy').value, 'PREFER_HIGHER_SCORE');
  assert.equal(context.byId('wbHoldingOwnership').value, 'SOURCE_ONLY');
  assert.equal(context.byId('wbPortfolioMode').value, 'hard_sleeve_budget');
});

test('applyConfigToUI restores star-market filter state from config', () => {
  const { context } = createWorkbenchHarness();
  const config = {
    mode: 'experiment',
    universe_mode: 'ALL_A',
    universe: {
      start: '2024-01-01',
      end: '2024-02-01',
      benchmark: '000300.SH',
      symbols: [],
      limit: 0,
      price_adj: 'hfq',
      filters: {
        exclude_st: true,
        exclude_suspended: true,
        exclude_star_market: true,
        min_list_days: 120,
        min_avg_turnover_20d: 100000000,
        price_min: 5,
        price_max: 99999,
        atr_pct_range: '0,100',
        limit_rule: 'ignore',
      },
    },
  };
  context.state.loaded_source_config = clone(config);

  context.applyConfigToUI(clone(config));

  assert.equal(context.byId('wbExcludeStarMarket').checked, true);
  assert.equal(context.state.config_draft?.universe?.filters?.exclude_star_market, true);
});

test('applyConfigToUI normalizes legacy unsupported combo values into phase1 multi-alpha defaults', () => {
  const request = loadAcceptanceRequest();
  const { context } = createWorkbenchHarness();
  context.state.loaded_source_config = clone(request.config_json);
  const invalidConfig = clone(request.config_json);
  invalidConfig.signal_composition.compose_mode = 'WEIGHTED_SCORE';
  invalidConfig.signal_composition.same_symbol_policy = 'AND';
  invalidConfig.signal_composition.holding_ownership = 'BOOK_LEVEL';
  invalidConfig.signal_composition.regime_matrix = {};
  invalidConfig.position_risk.portfolio_mode = 'equal_10';

  context.applyConfigToUI(invalidConfig);

  assert.equal(context.byId('wbComposeMode').value, 'REGIME_ROUTE');
  assert.equal(context.byId('wbSameSymbolPolicy').value, 'PREFER_HIGHER_SCORE');
  assert.equal(context.byId('wbHoldingOwnership').value, 'SOURCE_ONLY');
  assert.equal(context.byId('wbPortfolioMode').value, 'hard_sleeve_budget');
  assert.equal((context.validateConfigDraft(context.state.config_draft || {}) || []).length, 0);
});

test('applyConfigToUI derives visible date window from unified runtime provenance stock component contract when top-level universe is absent', () => {
  const { context } = createWorkbenchHarness();
  const config = {
    asset_scope: 'cn_a_equity',
    unified_runtime: {
      enabled: true,
      provenance: {
        component_source_contract: {
        components: {
          stock_component: {
            compile_input: {
              semantic_config: {
                universe_mode: 'HS300_ZZ500',
                universe: {
                  start: '2012-01-04',
                  end: '2026-03-20',
                  benchmark: '000300.SH',
                  symbols: [],
                  limit: 0,
                  price_adj: 'hfq',
                  membership_mode: 'PIT_DYNAMIC',
                  filters: {
                    exclude_st: true,
                    exclude_suspended: true,
                    min_list_days: 120,
                    min_avg_turnover_20d: 100000000,
                    price_min: 5,
                    price_max: 99999,
                    atr_pct_range: '0,100',
                    limit_rule: 'ignore',
                  },
                },
              },
            },
          },
        },
        },
      },
    },
  };

  context.applyConfigToUI(clone(config));

  assert.equal(context.byId('wbStartDate').value, '2012-01-04');
  assert.equal(context.byId('wbEndDate').value, '2026-03-20');
  assert.equal(context.byId('wbUniverseMode').value, 'HS300_ZZ500');
});

test('formal frontend payload serializer strips auxiliary runtime fields before run/save submission', () => {
  const { context } = createWorkbenchHarness();
  const raw = {
    asset_scope: 'cn_a_equity',
    mode: 'experiment',
    strategy_pack: 'EMA_CROSS',
    universe_mode: 'HS300_ZZ500',
    universe: {
      start: '2012-01-04',
      end: '2026-03-20',
      benchmark: '000300.SH',
      symbols: [],
      limit: 0,
      price_adj: 'hfq',
      membership_mode: 'PIT_DYNAMIC',
      filters: {
        exclude_st: true,
        exclude_suspended: true,
      },
    },
    signal_generation: {
      enabled: true,
      strategy: 'EMA_CROSS',
    },
    position_risk: {
      enabled: true,
      max_positions: 10,
    },
    data_source: {
      data_role: 'v1',
      stocks_table: 'pams_ohlcv_daily',
      benchmark_table: 'pams_index_daily_v2',
    },
    asset_context: {
      asset_scope: 'cn_a_equity',
    },
    unified_runtime: {
      enabled: true,
    },
    combo_context: {
      source: 'research_combo',
    },
  };

  const formal = context.buildFrontendSemanticPayload(raw);
  const runtimePayload = context.sanitizeRuntimeConfigDraft(raw);
  const persistedPayload = context.sanitizePersistedConfigDraft(raw);

  assert.equal('asset_context' in formal, false);
  assert.equal('unified_runtime' in formal, false);
  assert.equal('combo_context' in formal, false);
  assert.equal(formal.data_source?.data_role, undefined);
  assert.equal(formal.data_source?.stocks_table, undefined);
  assert.equal(formal.data_source?.benchmark_table, 'pams_index_daily_v2');
  assert.deepEqual(runtimePayload, formal);
  assert.deepEqual(persistedPayload, formal);
});

test('applyConfigToUI refreshes ETF drawer from unified runtime provenance contract when combo source stays on stock asset scope', () => {
  const { context } = createWorkbenchHarness();
  const config = {
    asset_scope: 'cn_a_equity',
    unified_runtime: {
      enabled: true,
      provenance: {
        component_source_contract: {
          components: {
            etf_component: {
              compile_input: {
                semantic_config: {
                  template_id: 'cn_broad_based_research_mainline_r1',
                  research_rule_family: 'broad_based_rotation_template_a',
                  source_entry_type: 'cn_etf_broad_based_standalone_mainline_entry',
                  universe_mode: 'HS300_ZZ500',
                  universe: {
                    start: '2012-01-01',
                    end: '2026-03-24',
                    benchmark: '510300.SH',
                    symbols: ['510050.SH', '510300.SH', '510500.SH', '512100.SH', '512890.SH', '588000.SH'],
                    limit: 6,
                    price_adj: 'none',
                    membership_mode: 'PIT_DYNAMIC',
                    filters: {
                      exclude_st: true,
                      exclude_suspended: true,
                      min_list_days: 120,
                      min_avg_turnover_20d: 100000000,
                      price_min: 5,
                      price_max: 99999,
                      atr_pct_range: '0,100',
                      limit_rule: 'ignore',
                    },
                  },
                  template_target_formal_symbols: ['510050.SH', '510300.SH', '510500.SH', '512100.SH', '512890.SH', '588000.SH'],
                  limited_defense_candidates: ['511010.SH', '518880.SH'],
                  fallback_symbol: '511010.SH',
                  rebalance_frequency: 'biweekly',
                  absolute_filter_mode: 'ma150_and_positive_12m',
                  selection_chain_profile: 'core_growth_slot',
                },
              },
            },
          },
        },
      },
    },
  };

  context.state.active_asset_context = { asset_scope: 'cn_etf' };
  context.state.loaded_source_asset_context = { asset_scope: 'cn_etf' };
  context.state.loaded_source_config = clone(config);

  context.applyConfigToUI(clone(config));

  assert.equal(context.byId('wbAssetScope').value, 'cn_etf');
  assert.match(context.byId('wbSymbols').value, /510050\.SH/);
  assert.match(context.byId('wbSymbols').value, /511010\.SH/);
  assert.equal(context.resolveEtfSemanticConfig(clone(config))?.template_id, 'cn_broad_based_research_mainline_r1');
  assert.equal(context.state.config_draft?.asset_scope, 'cn_etf');
});

test('baseline_V10_1 semantic config round-trips without dropping ranking or pre-profit exit fields', () => {
  const baselinePath = path.join(PROJECT_ROOT, 'outputs', 'baselines', 'baseline_V10_1', 'config.json');
  const baselineV10 = JSON.parse(fs.readFileSync(baselinePath, 'utf8'));
  const { context } = createWorkbenchHarness();

  context.state.loaded_source_config = clone(baselineV10);
  context.applyConfigToUI(clone(baselineV10));

  const expected = clone(baselineV10);
  expected.asset_scope = expected.asset_scope || 'cn_a_equity';
  assert.deepEqual(clone(context.state.config_draft), expected);
  assert.equal(context.state.config_draft?.signal_generation?.ranking?.score_source_mode, 'residual_only');
  assert.equal(context.state.config_draft?.signal_generation?.ranking?.residual_window, 40);
  assert.equal(context.state.config_draft?.exit_rules?.trailing?.activate_profit_pct, 0.15);
  assert.equal(context.state.config_draft?.exit_rules?.trailing?.pre_profit_breakout_failure_enabled, true);
  assert.equal(context.state.config_draft?.exit_rules?.trailing?.pre_profit_breakout_failure_max_bars, 5);
  assert.equal(context.state.config_draft?.exit_rules?.trailing?.pre_profit_breakout_failure_atr_buffer_k, 0.5);
});

test('formal regime engine config round-trips with grouped parameters intact', () => {
  const { context } = createWorkbenchHarness();
  const config = {
    asset_scope: 'cn_a_equity',
    mode: 'experiment',
    universe_mode: 'HS300_ZZ500',
    universe: {
      start: '2016-03-01',
      end: '2026-03-01',
      benchmark: '000300.SH',
      symbols: [],
      limit: 0,
      price_adj: 'hfq',
      membership_mode: 'PIT_DYNAMIC',
      filters: {
        exclude_st: true,
        exclude_suspended: true,
        min_list_days: 120,
        min_avg_turnover_20d: 100000000,
        price_min: 5,
        price_max: 99999,
        atr_pct_range: '0,100',
        limit_rule: 'ignore',
      },
    },
    signal_generation: {
      strategy: 'BREAKOUT_TREND',
      trend: { strategy: 'BREAKOUT_TREND', fast_ma: 20, slow_ma: 60, entry_buffer_pct: 1 },
      ranking: { score_source_mode: 'residual_only', residual_window: 40 },
      regime_detection: { enabled: false, regime_ma: 60, regime_filter: { enabled: false, regime_threshold: 0.3, alpha_m: 2.0 } },
    },
    exit_rules: {
      enabled: true,
      trailing: { enabled: true, k: 3.0 },
      atr_stop: { enabled: true, k: 1.2 },
      time_exit: { enabled: false, n_days: 20 },
      hold_constraint: { min_hold_days: 5, cooldown_days: 5 },
      take_profit: { enabled: false, mode: 'pct', pct: 0.1, atr_k: 3.0 },
      fixed_stop: { enabled: false, pct: 0.05 },
      ma20_exit: { enabled: false },
      low10_exit: { enabled: true },
    },
    position_risk: {
      enabled: true,
      max_positions: 10,
      single_stock_cap: 0.1,
      industry_cap: 0.3,
      lot: 100,
      cash_shortage_policy: 'skip',
      portfolio_mode: 'equal_10',
      risk_budget: { enabled: true, base_portfolio_risk: 0.06, atr_stop_k: 2.0, min_active_ratio: 0.6, dd_scale_10: 0.8, dd_scale_15: 0.6, dd_fixed_20: 0.03, dd_stop_pct: 0.35, dd_stop_cooldown_days: 60, dd_stop_protect_days: 30 },
      market_filter: { enabled: true, slope_ma_period: 50, slope_window: 10, bull_multiplier: 1.5, light_multiplier: 0.6, ema_light_fast: 5, ema_light_slow: 20 },
    },
    regime_engine: {
      engine: 'market_regime_framework',
      benchmark: '000001.SH',
      trend_block: { enabled: true, long_ma_window: 220, slope_window: 30, breakout_lookback: 25 },
      risk_block: { enabled: true, realized_vol_window: 30, atr_window: 18, drawdown_window: 80 },
      breadth_block: { enabled: true, universe: 'benchmark_constituents', above_ma_short_window: 55, above_ma_long_window: 210, new_high_low_window: 30 },
      participation_block: { enabled: true, turnover_window: 30, amount_window: 25, use_turnover_rate: true },
      persistence: { entry_confirm_bars: 4, exit_confirm_bars: 3, min_state_duration: 6, confidence_floor: 0.62, transition_cooldown: 4 },
      fallback: { on_feature_unavailable: 'ma200_legacy', required_blocks: ['trend_block', 'risk_block', 'breadth_block'], emit_feature_availability: true },
    },
  };

  context.state.loaded_source_config = clone(config);
  context.applyConfigToUI(clone(config));

  assert.equal(context.byId('wbRegimeEngine').value, 'market_regime_framework');
  assert.equal(context.byId('wbRegimeFrameworkPanel').hidden, false);
  assert.equal(context.byId('wbRegimeLegacyPanel').hidden, true);
  assert.deepEqual(clone(context.state.config_draft?.regime_engine), config.regime_engine);
});

test('syncAssetAwareShell moves public summary to global strip and scopes left rail for ETF', () => {
  const { context } = createWorkbenchHarness();
  context.state.config_draft = {
    asset_scope: 'cn_etf',
    universe_mode: 'CUSTOM',
    universe: {
      start: '2012-01-04',
      end: '2026-03-24',
    },
  };
  context.state.active_artifacts = {
    run_meta: {
      regime: {
        latest_state: {
          base_state: 'TRANS_UP',
          effective_state: 'LIGHT',
          effective_coarse_state: 'NEUTRAL',
          risk_budget_multiplier: 0.5,
          reason_codes: ['BREADTH_WEAK'],
          manual_override: {
            active: true,
            scope: 'state_override',
            target_state_5: 'LIGHT',
            reason: 'MANUAL_HOLD',
          },
        },
      },
      governed_snapshot: {
        budget_consumer_sleeve_id: 'cn_etf_beta',
        total_risk_budget: 0.3,
        total_exposure_cap: 0.35,
        budget_reason_codes: ['TOTAL_RISK_BUDGET_REDUCED'],
      },
      universe: {
        preset_id: 'cn_etf_first_wave_core',
      },
    },
  };

  context.syncAssetAwareShell('cn_etf');

  assert.equal(context.byId('wbStageS1Label').textContent, 'ETF池');
  assert.equal(context.byId('wbStageS2Btn').hidden, true);
  assert.equal(context.byId('wbStageS7Btn').hidden, true);
  assert.match(context.byId('wbGlobalAssetModeSummary').textContent, /ETF池/);
  assert.equal(context.byId('wbGlobalRegimeBase').textContent, 'TRANS_UP');
  assert.equal(context.byId('wbGlobalRegimeEffective').textContent, 'LIGHT');
  assert.match(context.byId('wbGlobalRegimeReason').textContent, /BREADTH_WEAK/);
  assert.match(context.byId('wbGlobalRegimeManual').textContent, /MANUAL_HOLD/);
  assert.equal(context.byId('wbGlobalGovernorSleeve').textContent, 'cn_etf_beta');
  assert.match(context.byId('wbGlobalGovernorReason').textContent, /TOTAL_RISK_BUDGET_REDUCED/);
  assert.equal(context.byId('wbGlobalRegimeDetail').hidden, false);
  assert.equal(context.byId('wbGlobalRegimeEmpty').hidden, true);
  assert.equal(context.byId('wbGlobalGovernorDetail').hidden, false);
  assert.equal(context.byId('wbGlobalGovernorEmpty').hidden, true);
});

test('comboRuntimeState prefers execution_contract_ref over legacy provenance source contract', () => {
  const { context } = createWorkbenchHarness();
  const comboState = context.comboRuntimeState({
    data: {
      asset_role: 'research_combo',
      system_asset_scope: 'cn_a_multi_sleeve',
    },
    execution_contract_ref: {
      contract_type: 'unified_combo',
      contract_version: 'backtest_execution_contract@1',
    },
    provenance: {
      component_source_contract: {
        contract_version: 'unified_combo_component_source_contract@1',
        runtime_entry_mode: 'contract_only',
        source_mode: 'contract_only',
      },
    },
    combo_result: {
      type: 'unified_runtime_combo',
    },
  });

  assert.equal(comboState.comboSourceMode, 'execution_contract');
  assert.equal(comboState.isComboRuntime, true);
  assert.equal(comboState.researchComboOnly, false);
});

test('comboRuntimeState ignores legacy top-level source contract when provenance is absent', () => {
  const { context } = createWorkbenchHarness();
  const comboState = context.comboRuntimeState({
    data: {
      asset_role: 'research_combo',
      system_asset_scope: 'cn_a_multi_sleeve',
    },
    component_source_contract: {
      contract_version: 'unified_combo_component_source_contract@1',
      runtime_entry_mode: 'contract_only',
    },
    combo_result: {
      type: 'unified_runtime_combo',
    },
  });

  assert.equal(comboState.comboSourceMode, '');
  assert.equal(comboState.isComboRuntime, true);
});

/*
test('syncAssetAwareShell renders research combo summaries from backend combo truth display', () => {
  const { context } = createWorkbenchHarness();
  context.state.config_draft = {
    asset_scope: 'cn_a_equity',
    universe_mode: 'HS300_ZZ500',
    universe: {
      start: '2021-01-04',
      end: '2026-03-20',
    },
  };
  context.state.active_result = { exp_id: 'exp_combo' };
  context.state.active_artifacts = {
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
        base_state: '涓偂 TRANS_DOWN',
        effective_state: 'ETF RISK_OFF',
        coarse_state: '涓偂 RISK_OFF | ETF RISK_OFF',
        risk_budget_multiplier_text: '涓偂 60.00% | ETF 0.00%',
        reason_text: '涓偂 TRANS_DOWN | ETF RISK_OFF | 妯″紡 daily_rebalanced_equal_weight_50_50',
        manual_override_text: '鏃?,
      },
        governor: {
        available: true,
        total_risk_budget_text: '涓偂 60.00% | ETF 0.00%',
        total_exposure_cap_text: '鐮旂┒缁勫悎 daily_rebalanced_equal_weight_50_50',
        budget_consumer_text: 'cn_stock_trend_alpha_core + cn_etf_beta',
        budget_reason_text: '涓偂 TOTAL_RISK_BUDGET_REDUCED | ETF NO_DEPLOYABLE_SLOTS',
        },
      },
    },
  };

  context.syncAssetAwareShell('cn_a_equity');

  assert.equal(context.byId('wbGlobalRegimeBase').textContent, '涓偂 TRANS_DOWN');
  assert.equal(context.byId('wbGlobalRegimeEffective').textContent, 'ETF RISK_OFF');
  assert.match(context.byId('wbGlobalRegimeReason').textContent, /daily_rebalanced_equal_weight_50_50/);
  assert.equal(context.byId('wbGlobalGovernorBudget').textContent, '涓偂 60.00% | ETF 0.00%');
  assert.equal(context.byId('wbGlobalGovernorSleeve').textContent, 'cn_stock_trend_alpha_core + cn_etf_beta');
  assert.equal(context.byId('wbGlobalRegimeDetail').hidden, false);
  assert.equal(context.byId('wbGlobalGovernorDetail').hidden, false);
});

*/

test('syncAssetAwareShell renders research combo summaries from backend combo truth display', () => {
  const { context } = createWorkbenchHarness();
  context.state.config_draft = {
    asset_scope: 'cn_a_equity',
    universe_mode: 'HS300_ZZ500',
    universe: {
      start: '2021-01-04',
      end: '2026-03-20',
    },
  };
  context.state.active_result = { exp_id: 'exp_combo' };
  context.state.active_artifacts = {
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
          base_state: 'stock TRANS_DOWN',
          effective_state: 'ETF RISK_OFF',
          coarse_state: 'stock RISK_OFF | ETF RISK_OFF',
          risk_budget_multiplier_text: 'stock 60.00% | ETF 0.00%',
          reason_text: 'stock TRANS_DOWN | ETF RISK_OFF | mode daily_rebalanced_equal_weight_50_50',
          manual_override_text: 'none',
        },
        governor: {
          available: true,
          total_risk_budget_text: 'stock 60.00% | ETF 0.00%',
          total_exposure_cap_text: 'combo daily_rebalanced_equal_weight_50_50',
          budget_consumer_text: 'cn_stock_trend_alpha_core + cn_etf_beta',
          budget_reason_text: 'stock TOTAL_RISK_BUDGET_REDUCED | ETF NO_DEPLOYABLE_SLOTS',
        },
      },
    },
  };

  context.syncAssetAwareShell('cn_a_equity');

  assert.equal(context.byId('wbGlobalRegimeBase').textContent, 'stock TRANS_DOWN');
  assert.equal(context.byId('wbGlobalRegimeEffective').textContent, 'ETF RISK_OFF');
  assert.match(context.byId('wbGlobalRegimeReason').textContent, /daily_rebalanced_equal_weight_50_50/);
  assert.equal(context.byId('wbGlobalGovernorBudget').textContent, 'stock 60.00% | ETF 0.00%');
  assert.equal(context.byId('wbGlobalGovernorSleeve').textContent, 'cn_stock_trend_alpha_core + cn_etf_beta');
  assert.equal(context.byId('wbGlobalRegimeDetail').hidden, false);
  assert.equal(context.byId('wbGlobalGovernorDetail').hidden, false);
});

test('frontend load surface only exposes baseline and experiment sources', () => {
  const { context } = createWorkbenchHarness();
  context.URL = URL;
  let replacedUrl = '';
  context.window.history.replaceState = (_state, _title, nextUrl) => {
    replacedUrl = String(nextUrl || '');
    const parsed = new URL(replacedUrl);
    context.location.href = parsed.toString();
    context.location.search = parsed.search;
    context.window.location.href = parsed.toString();
    context.window.location.search = parsed.search;
  };

  assert.equal(context.loadItemBadgeLabel({ kind: 'baseline' }), 'Baseline');
  assert.equal(context.loadItemBadgeClass({ kind: 'baseline' }), 'wb-load-kind-baseline');

  context.syncWorkbenchLoadedSourceToUrl('baseline', 'CN_STOCK_ETF_FORMAL_V1');
  assert.match(replacedUrl, /load_kind=baseline/);
  assert.match(replacedUrl, /load_id=CN_STOCK_ETF_FORMAL_V1/);

  const parsedSource = context.currentWorkbenchInputSourceFromUrl();
  assert.equal(parsedSource?.kind, 'baseline');
  assert.equal(parsedSource?.id, 'CN_STOCK_ETF_FORMAL_V1');
});

test('applyConfigToUI populates explicit S5 and S9 controls for baseline_V10_1', () => {
  const baselinePath = path.join(PROJECT_ROOT, 'outputs', 'baselines', 'baseline_V10_1', 'config.json');
  const baselineV10 = JSON.parse(fs.readFileSync(baselinePath, 'utf8'));
  const { context } = createWorkbenchHarness();

  context.state.loaded_source_config = clone(baselineV10);
  context.applyConfigToUI(clone(baselineV10));

  assert.equal(context.byId('wbScoreSourceMode').value, 'residual_only');
  assert.equal(context.byId('wbResidualWindow').value, '40');
  assert.equal(context.byId('wbTrailingActivateProfitPct').value, '15');
  assert.equal(context.byId('wbPreProfitBreakoutFailureEnabled').checked, true);
  assert.equal(context.byId('wbPreProfitBreakoutFailureMaxBars').value, '5');
  assert.equal(context.byId('wbPreProfitBreakoutFailureAtrBufferK').value, '0.5');
});

test('explicit S5 and S9 controls write back into semantic config', () => {
  const baselinePath = path.join(PROJECT_ROOT, 'outputs', 'baselines', 'baseline_V10_1', 'config.json');
  const baselineV10 = JSON.parse(fs.readFileSync(baselinePath, 'utf8'));
  const { context } = createWorkbenchHarness();

  context.state.loaded_source_config = clone(baselineV10);
  context.applyConfigToUI(clone(baselineV10));

  context.byId('wbResidualWindow').value = '55';
  context.byId('wbTrailingActivateProfitPct').value = '18';
  context.byId('wbPreProfitBreakoutFailureMaxBars').value = '7';
  context.byId('wbPreProfitBreakoutFailureAtrBufferK').value = '0.9';

  const draft = context.buildConfigDraft();

  assert.equal(draft.signal_generation?.ranking?.score_source_mode, 'residual_only');
  assert.equal(draft.signal_generation?.ranking?.residual_window, 55);
  assert.equal(draft.exit_rules?.trailing?.activate_profit_pct, 0.18);
  assert.equal(draft.exit_rules?.trailing?.pre_profit_breakout_failure_enabled, true);
  assert.equal(draft.exit_rules?.trailing?.pre_profit_breakout_failure_max_bars, 7);
  assert.equal(draft.exit_rules?.trailing?.pre_profit_breakout_failure_atr_buffer_k, 0.9);
});

test('buildConfigDraft emits PIT dynamic membership for supported index universes by default', () => {
  const { context } = createWorkbenchHarness();
  context.byId('wbUniverseMode').value = 'HS300_ZZ500';
  context.byId('wbConstituent').value = 'dynamic';

  const draft = context.buildConfigDraft();

  assert.equal(draft.universe_mode, 'HS300_ZZ500');
  assert.equal(draft.universe?.membership_mode, 'PIT_DYNAMIC');
});

test('applyConfigToUI preserves legacy start-snapshot semantics when membership_mode is missing', () => {
  const { context } = createWorkbenchHarness();
  const legacyConfig = {
    mode: 'experiment',
    universe_mode: 'HS300_ZZ500',
    universe: {
      start: '2016-03-01',
      end: '2026-03-01',
      benchmark: '000300.SH',
      symbols: [],
      limit: 0,
      price_adj: 'hfq',
      filters: {
        exclude_st: true,
        exclude_suspended: true,
        min_list_days: 120,
        min_avg_turnover_20d: 100000000,
        price_min: 5,
        price_max: 99999,
        atr_pct_range: '0,100',
        limit_rule: 'ignore',
      },
    },
  };
  context.state.loaded_source_config = clone(legacyConfig);

  context.applyConfigToUI(clone(legacyConfig));

  assert.equal(context.byId('wbConstituent').value, 'fixed');
  assert.equal(context.state.config_draft?.universe?.membership_mode, 'START_SNAPSHOT');
});

test('default PIT membership is hidden in config meta display', () => {
  const { context } = createWorkbenchHarness();

  const meta = context.cloneLoadedSourceMeta({
    config_id: 'baseline_V10_1',
    display_name: 'baseline_V10.1',
    universe_mode: 'HS300_ZZ500',
    membership_mode: 'PIT_DYNAMIC',
  });

  assert.equal(meta.display_name.includes('Membership='), false);
  assert.equal(meta.display_name.includes('Universe=HS300_ZZ500'), true);
});

test('non-default membership mode is shown in config meta and load summary', () => {
  const { context } = createWorkbenchHarness();

  const meta = context.cloneLoadedSourceMeta({
    config_id: 'legacy_baseline',
    display_name: 'legacy_baseline',
    universe_mode: 'HS300_ZZ500',
    membership_mode: 'START_SNAPSHOT',
  });
  const summary = context.experimentLoadSummary({
    kind: 'baseline',
    universe_mode: 'HS300_ZZ500',
    membership_mode: 'START_SNAPSHOT',
  });

  assert.equal(meta.display_name.includes('Membership=START_SNAPSHOT'), true);
  assert.equal(summary.includes('Membership=START_SNAPSHOT'), true);
});


