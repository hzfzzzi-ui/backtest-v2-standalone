# Implementation Notes

## What changed
- Added canonical runtime fields `final_score_value`, `final_score_rank`, and `final_score_rank_*` on candidate audit, debug plan, daily rows, metrics, and artifact counters.
- Kept legacy `mf_score`, `mf_rank`, and `mf_rank*` fields as compatibility aliases.
- Did not change ranking, topk, tilt, gate, cash planning, or execution timing behavior.

## Impacted modules
- `backend/core/portfolio/candidate_plan.py`
- `backend/core/portfolio/execution_orders.py`
- `backend/core/stage_pipeline/adapters/daily_accounting.py`
- `backend/core/portfolio/portfolio_loop.py`
- `backend/core/engine_vector/strict_runtime_breakout.py`
- `backend/core/portfolio/metrics.py`
- `backend/api/backtest_v2/artifacts_diagnostics.py`
- `backend/core/tools/experiment_runner.py`
- related runtime diagnostics tests

## Validation
- Focused tests passed:
  - `tests/integration/test_selection_minimal_flow.py`
  - `tests/unit/test_backtest_v2_artifacts.py`

## Risks
- Runtime outputs now double-write canonical and legacy fields, so schema is temporarily wider.
- Legacy config names such as `enable_multifactor_rank` and `mf_rank_tilt` are intentionally unchanged in this change.

## Rollback
- Revert the files above and restore the tasks file.
