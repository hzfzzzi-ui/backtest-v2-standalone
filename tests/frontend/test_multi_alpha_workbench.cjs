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

test('legacy weighted-score baseline config stays on single-strategy path', () => {
  const baselinePath = path.join(PROJECT_ROOT, 'outputs', 'baselines', 'baseline_V1', 'config.json');
  const legacyBaseline = JSON.parse(fs.readFileSync(baselinePath, 'utf8'));
  const { context } = createWorkbenchHarness();

  context.applyConfigToUI(clone(legacyBaseline));

  assert.equal(context.byId('wbEnableComposition').checked, false);
  assert.equal(context.state.config_draft?.signal_composition?.enabled, false);
  assert.equal((context.validateConfigDraft(context.state.config_draft || {}) || []).length, 0);
});

test('baseline_V10 semantic config round-trips without dropping ranking or pre-profit exit fields', () => {
  const baselinePath = path.join(PROJECT_ROOT, 'outputs', 'baselines', 'baseline_V10', 'config.json');
  const baselineV10 = JSON.parse(fs.readFileSync(baselinePath, 'utf8'));
  const { context } = createWorkbenchHarness();

  context.state.loaded_source_config = clone(baselineV10);
  context.applyConfigToUI(clone(baselineV10));

  assert.deepEqual(clone(context.state.config_draft), clone(baselineV10));
  assert.equal(context.state.config_draft?.signal_generation?.ranking?.score_source_mode, 'residual_only');
  assert.equal(context.state.config_draft?.signal_generation?.ranking?.residual_window, 40);
  assert.equal(context.state.config_draft?.exit_rules?.trailing?.activate_profit_pct, 0.15);
  assert.equal(context.state.config_draft?.exit_rules?.trailing?.pre_profit_breakout_failure_enabled, true);
  assert.equal(context.state.config_draft?.exit_rules?.trailing?.pre_profit_breakout_failure_max_bars, 5);
  assert.equal(context.state.config_draft?.exit_rules?.trailing?.pre_profit_breakout_failure_atr_buffer_k, 0.5);
});

test('applyConfigToUI populates explicit S5 and S9 controls for baseline_V10', () => {
  const baselinePath = path.join(PROJECT_ROOT, 'outputs', 'baselines', 'baseline_V10', 'config.json');
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
  const baselinePath = path.join(PROJECT_ROOT, 'outputs', 'baselines', 'baseline_V10', 'config.json');
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

test('baseline_V9_1 round-trips without injecting V10-only overrides', () => {
  const baselinePath = path.join(PROJECT_ROOT, 'outputs', 'baselines', 'baseline_V9_1', 'config.json');
  const baselineV91 = JSON.parse(fs.readFileSync(baselinePath, 'utf8'));
  const { context } = createWorkbenchHarness();

  context.state.loaded_source_config = clone(baselineV91);
  context.applyConfigToUI(clone(baselineV91));

  assert.deepEqual(clone(context.state.config_draft), clone(baselineV91));
  assert.equal('residual_window' in (context.state.config_draft?.signal_generation?.ranking || {}), false);
  assert.equal('pre_profit_breakout_failure_enabled' in (context.state.config_draft?.exit_rules?.trailing || {}), false);
  assert.equal('pre_profit_breakout_failure_max_bars' in (context.state.config_draft?.exit_rules?.trailing || {}), false);
  assert.equal('pre_profit_breakout_failure_atr_buffer_k' in (context.state.config_draft?.exit_rules?.trailing || {}), false);
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
    config_id: 'baseline_V1',
    display_name: 'baseline_V1',
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
