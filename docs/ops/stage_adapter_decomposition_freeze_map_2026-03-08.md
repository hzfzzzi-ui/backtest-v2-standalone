# Stage Adapter Decomposition Freeze Map (2026-03-08)

## Conclusion

As of `v2-stage-adapter-decomposition`, the public single-run path remains:

`config_json -> compiler -> DataBundle -> foundation shell -> stage pipeline shell -> legacy adapter -> legacy execution kernel`

The adapter is still a single public entrypoint, but its internal responsibilities are now split
and frozen by module ownership. New stage logic must not be added back into the monolithic
`legacy_adapter.py` body.

## Internal Ownership

### Public adapter entrypoint

- `backend/core/stage_pipeline/adapters/legacy_adapter.py`
  - Owns:
    - `run_legacy_stage_pipeline_backtest(...)`
    - adapter runtime composition
    - day preparation
    - open-fill application
    - NAV and metric assembly
  - Frozen rule:
    - keep this file as the public compatibility boundary
    - do not add new candidate-stage, holding-stage, or S7 planning logic here

### Route and provider runtime ownership

- `backend/core/stage_pipeline/adapters/route_runtime.py`
  - Owns:
    - strategy route selection
    - provider construction
    - route-specific precompute
    - market-filter and benchmark-regime control arrays
  - Change rule:
    - route-specific behavior starts here, not in stage output modules

### Shared mutable runtime ownership

- `backend/core/stage_pipeline/adapters/runtime_state.py`
  - Owns:
    - runtime bootstrap values
    - ledger defaults
    - counters and timing-facing mutable state
  - Change rule:
    - default bootstrapping and shared state setup belong here

### Candidate flow ownership

- `backend/core/stage_pipeline/adapters/candidate_flow.py`
  - Owns:
    - `S1` through `S6` output assembly
    - candidate-flow neutral outputs when a stage is disabled
  - Change rule:
    - candidate generation and candidate-stage summaries belong here

### Holding flow ownership

- `backend/core/stage_pipeline/adapters/holding_flow.py`
  - Owns:
    - `S9` and `S8` output assembly
    - holding-flow neutral outputs when a stage is disabled
  - Change rule:
    - exit and risk-stage summaries belong here

### S7 order planning ownership

- `backend/core/stage_pipeline/adapters/order_planning.py`
  - Owns:
    - `S7` glue around the legacy rebalance planner
    - candidate audit row forwarding
    - decision diagnostics handoff
  - Change rule:
    - order planning glue belongs here, even if the legacy planner kernel is reused

## Frozen Monolithic Layout

The following logic is now frozen out of `legacy_adapter.py` and must stay in dedicated modules:

- route resolution
- provider precompute wiring
- route control initialization
- `S1` to `S6` stage output assembly
- `S9` and `S8` stage output assembly
- `S7` order planning glue

`legacy_adapter.py` may still orchestrate those modules, but it must not re-absorb their logic.

## Allowed Follow-up Work

- further split the remaining accounting-facing helpers inside `legacy_adapter.py`
- replace dedicated adapter modules incrementally while keeping the public entrypoint stable
- add focused tests around module boundaries

## Explicitly Disallowed

- adding new stage-specific branching directly into `legacy_adapter.py`
- creating a second public adapter entrypoint outside `run_legacy_stage_pipeline_backtest(...)`
- bypassing the locked baseline gate for adapter refactors

## Regression Gate

Every follow-up adapter refactor must continue to pass:

- `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`
- locked baseline: `exp_20260308_021045840_cde0`
- accepted non-blocking drift: `report.html` diagnostic hash drift only
