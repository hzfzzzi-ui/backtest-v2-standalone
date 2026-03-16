# Verification

## Summary

- Change: `decouple-runtime-diagnostics-from-execution`
- Baseline anchor: `baseline_V10.1 -> exp_20260314_144548534_7db9`
- Candidate rerun: `exp_20260315_185622636_35db`

## Targeted Tests

- `python -m pytest tests/unit/test_bridge_adapter_accounting.py tests/unit/test_backtest_v2_artifacts.py tests/unit/test_experiment_runner_daily_schema.py tests/unit/test_experiment_query_service.py tests/unit/test_baseline_regression_check.py tests/integration/test_schema_and_artifacts.py -q`
  - `43 passed`
- `python -m compileall backend/core/stage_pipeline backend/api/backtest_v2 backend/core/engine_vector tests/unit tests/integration`
  - PASS

## Runtime Smoke

Artifact: [outputs/ops/decouple_runtime_diagnostics_runtime_smoke.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/decouple_runtime_diagnostics_runtime_smoke.json)

- `status = PASS`
- `total_return = 4.425630011081876`
- `max_drawdown = -0.29025259513173496`
- `cagr = 0.2032763161631579`
- `sharpe = 0.8891097010317657`
- `calmar = 0.7003428033809594`
- `orders = 467`
- `closed_trades = 230`
- `buy_stage_funnel_match = true`

## Baseline Compare

Artifact: [outputs/ops/decouple_runtime_diagnostics_compare.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/decouple_runtime_diagnostics_compare.json)

Observed result:

- `portfolio_trades = PASS`
- `portfolio_candidates = PASS`
- `perf = PASS`
- `nav = PASS`
- `run_meta_core = PASS`
- `run_meta_universe = PASS`
- `config_truth = PASS`
- `manifest = PASS`
- `portfolio_daily = FAIL`

The `portfolio_daily` exact hash drift is expected in this change because:

1. `diagnostics_input_json` was added as the canonical diagnostics payload.
2. `buy_candidate_count / after_held_filter_count / after_slot_filter_count` in daily rows now represent raw execution observations instead of final route-normalized funnel semantics.
3. Final buy-stage funnel normalization moved to `artifacts_diagnostics.py`.

This is a structural contract change, not a `V10.1` execution result drift.

## Rollback Surface

If rollback is needed, revert these files together:

- [backend/core/stage_pipeline/contracts.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/stage_pipeline/contracts.py)
- [backend/core/stage_pipeline/adapters/daily_accounting.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/stage_pipeline/adapters/daily_accounting.py)
- [backend/api/backtest_v2/artifacts_diagnostics.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/artifacts_diagnostics.py)
- [backend/core/tools/experiment_runner.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/tools/experiment_runner.py)
- [backend/core/engine_vector/strict_runtime_daily_loop.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/strict_runtime_daily_loop.py)

Rolling back only one side of the contract is unsafe because execution emission and artifact normalization now rely on the same canonical diagnostics payload.
