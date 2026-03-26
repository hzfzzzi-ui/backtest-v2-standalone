## Current Progress

- All tasks are complete.
- This change now has:
  - ETF V1 control
  - Dual Momentum basic family
  - Dual Momentum buffered family
  - Dual Momentum + Vol Target family
  - consolidated rule-family compare and recommendation

## Completed Outputs

### 1. ETF V1 control

- Study: [research/studies/etf/cn_etf_beta_v1_control.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_beta_v1_control.study.yaml)
- Reference experiment: [exp_20260325_073348815_5fe3](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260325_073348815_5fe3)

### 2. Dual Momentum basic

- Study: [research/studies/etf/cn_etf_beta_dual_momentum_basic.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_beta_dual_momentum_basic.study.yaml)
- Experiments:
  - `DM_BASIC_CASH_MA120`: [exp_20260325_073348842_6728](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260325_073348842_6728)
  - `DM_BASIC_BOND_MA120`: [exp_20260325_073355395_ef83](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260325_073355395_ef83)
  - `DM_BASIC_BOND_RET12`: [exp_20260325_073401181_0691](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260325_073401181_0691)
- Compare:
  - [dual_momentum_basic_compare.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_etf_beta_rule_families_20260325/dual_momentum_basic_compare.csv)
  - [dual_momentum_basic_summary.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_etf_beta_rule_families_20260325/dual_momentum_basic_summary.json)

### 3. Dual Momentum buffered

- Study: [research/studies/etf/cn_etf_beta_dual_momentum_buffered.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_beta_dual_momentum_buffered.study.yaml)
- Experiments:
  - `DM_BUFFER_WEEKLY_CONTROL`: [exp_20260325_074234122_aa7e](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260325_074234122_aa7e)
  - `DM_BUFFER_BIWEEKLY_MA120`: [exp_20260325_074239928_808a](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260325_074239928_808a)
- Compare:
  - [dual_momentum_buffered_compare.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_etf_beta_rule_families_20260325/dual_momentum_buffered_compare.csv)
  - [dual_momentum_buffered_summary.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_etf_beta_rule_families_20260325/dual_momentum_buffered_summary.json)

### 4. Dual Momentum + Vol Target

- Study: [research/studies/etf/cn_etf_beta_dual_momentum_vol_target.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_beta_dual_momentum_vol_target.study.yaml)
- Experiments:
  - `DM_VOL_CONTROL_CASH_MA120`: [exp_20260325_080049884_c1f6](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260325_080049884_c1f6)
  - `DM_VOL20_CASH_MA120`: [exp_20260325_080055718_445b](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260325_080055718_445b)
  - `DM_VOL30_CASH_MA120`: [exp_20260325_080101517_ee5a](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260325_080101517_ee5a)
- Compare:
  - [dual_momentum_vol_target_compare.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_etf_beta_rule_families_20260325/dual_momentum_vol_target_compare.csv)
  - [dual_momentum_vol_target_summary.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_etf_beta_rule_families_20260325/dual_momentum_vol_target_summary.json)

### 5. Consolidated family compare

- [rule_family_compare.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_etf_beta_rule_families_20260325/rule_family_compare.csv)
- [rule_family_summary.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_etf_beta_rule_families_20260325/rule_family_summary.json)

## Current Findings

### 1. Dual Momentum basic

- `MA120 + cash fallback` is the strongest minimal control.
- `MA120 + 511010 fallback` is close, but slightly weaker.
- `12M > 0 + 511010 fallback` is materially weaker and is not recommended for the next round.

### 2. Dual Momentum buffered

- `biweekly` does reduce trades and turnover.
- In the current window it also worsens `CAGR`, `Sharpe`, and `MaxDD`.
- Current conclusion: the current `biweekly` buffered variant is not recommended as the next formal ETF sleeve baseline.

### 3. Dual Momentum + Vol Target

- Vol Target is now wired through:
  - governed ETF contract
  - ETF provider runtime diagnostics
  - order sizing path
  - `run_meta.etf_beta.vol_target`
  - `research_audit.gates.etf_beta_sleeve`
- `20D` and `30D` realized-vol scaling both reduced turnover and drawdown versus the same `MA120 + cash fallback` control.
- Real scaling did occur in-window:
  - `DM_VOL20_CASH_MA120`: `7/29` buy orders were scaled below `1.0`, average scale `0.914`, minimum scale `0.35`
  - `DM_VOL30_CASH_MA120`: `9/29` buy orders were scaled below `1.0`, average scale `0.916`, minimum scale `0.352`
- `DM_VOL30_CASH_MA120` is the strongest Vol Target variant in this round:
  - `CAGR -0.000089`
  - `Sharpe 0.00268`
  - `MaxDD -0.04956`
- Important qualification:
  - latest `run_meta.etf_beta.vol_target.active` can be `false` because the latest governed state is `RISK_OFF`
  - but the order-level scale distribution proves the Vol Target rule was active during deployable periods

## Final Recommendation

- Keep `DM_BASIC_CASH_MA120` as the formal control.
- Do not promote:
  - `DM_BASIC_BOND_RET12`
  - `DM_BUFFER_BIWEEKLY_MA120`
- Promote only one next-round ETF V2 candidate:
  - `DM_VOL30_CASH_MA120`

This means the next ETF research step should be:

1. `DM_BASIC_CASH_MA120` as control
2. `DM_VOL30_CASH_MA120` as the only promoted enhancement candidate

## Validation Completed

- `pytest tests/unit/test_semantic_config_compiler.py tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_multi_alpha_order_planning.py tests/unit/test_artifacts_finalize_regime_meta.py tests/unit/test_research_audit_contract.py -q`
- `docker exec backtest-v2-standalone python -m backend.cli study_run etf/cn_etf_beta_dual_momentum_basic`
- `docker exec backtest-v2-standalone python -m backend.cli study_run etf/cn_etf_beta_dual_momentum_buffered`
- `docker exec backtest-v2-standalone python -m backend.cli study_run etf/cn_etf_beta_dual_momentum_vol_target`
- `openspec validate study-cn-etf-beta-rule-families --type change --strict`

## Rollback

- Revert ETF research rule-family support:
  - [backend/core/config/cn_a_governed_mainline.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/cn_a_governed_mainline.py)
  - [backend/core/engine_vector/cn_etf_beta_signal_provider.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/cn_etf_beta_signal_provider.py)
  - [backend/core/portfolio/portfolio_runtime.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/portfolio/portfolio_runtime.py)
  - [backend/api/backtest_v2/artifacts_finalize.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/artifacts_finalize.py)
  - [backend/core/audit/research_audit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)
- Revert study entry points:
  - [research/studies/etf/cn_etf_beta_v1_control.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_beta_v1_control.study.yaml)
  - [research/studies/etf/cn_etf_beta_dual_momentum_basic.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_beta_dual_momentum_basic.study.yaml)
  - [research/studies/etf/cn_etf_beta_dual_momentum_buffered.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_beta_dual_momentum_buffered.study.yaml)
  - [research/studies/etf/cn_etf_beta_dual_momentum_vol_target.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_beta_dual_momentum_vol_target.study.yaml)
- Revert tests:
  - [tests/unit/test_semantic_config_compiler.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_semantic_config_compiler.py)
  - [tests/unit/test_cn_etf_beta_signal_provider.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_cn_etf_beta_signal_provider.py)
  - [tests/unit/test_multi_alpha_order_planning.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_multi_alpha_order_planning.py)
  - [tests/unit/test_artifacts_finalize_regime_meta.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_artifacts_finalize_regime_meta.py)
