## Context

`v2-single-path-9stage-engine` established the only public orchestration path and introduced a
real stage shell. The next risk is not public routing any more; it is internal adapter sprawl.

Today `legacy_adapter.py` still owns too many concerns:

- route selection
- provider precompute and route controls
- daily state preparation
- candidate flow stage outputs
- holding flow stage outputs
- S7 order planning
- trade row / daily row assembly
- metric augmentation

This makes it difficult to answer simple audit questions such as:

- which code path controls candidate generation for a given route
- which module owns exit vs risk vs order planning behavior
- which parts can be replaced without touching fills and NAV accounting

## Goals

- Split the adapter into internal modules without changing public behavior.
- Keep a single adapter entrypoint for the stage shell.
- Isolate candidate flow, holding flow, and order planning responsibilities.
- Preserve the current execution kernel and the locked baseline.

## Non-Goals

- Do not change strategy formulas, costs, fills, or timing semantics.
- Do not introduce a second public execution path.
- Do not rewrite the execution kernel in this change.

## Decisions

### D1. Keep one public adapter entrypoint

`run_legacy_stage_pipeline_backtest(...)` remains the only adapter entrypoint used by the public
foundation shell. Internal refactoring must stay behind that function.

### D2. Extract internal modules by responsibility, not by strategy name

The first split should follow stable responsibilities:

- `runtime_state.py`: shared mutable state, daily preparation, fills, accounting-facing state
- `route_runtime.py`: route resolution and provider-specific controls
- `candidate_flow.py`: S1-S6 outputs
- `holding_flow.py`: S9-S8 outputs
- `order_planning.py`: S7 output and candidate audit rows

This keeps future route replacement incremental.

### D3. Reuse the current execution kernel unchanged

All fill, cash, position, NAV, and metrics calculations continue to reuse the current execution
kernel helpers. Only adapter composition changes.

### D4. Verify every extraction step against the locked baseline

Each extraction step must be small enough that a failing baseline rerun can be attributed to one
responsibility move.

## Risks

- If state ownership is split incorrectly, candidate flow and holding flow may diverge from the
  current route semantics.
- If helper extraction changes mutation order, the T+1 order schedule could drift.
- If route-specific controls leak into generic modules, the refactor will only rename complexity.

## Mitigations

- Extract state and route resolution first, before splitting stage logic.
- Keep the old adapter entrypoint and result object shape unchanged until the end of the change.
- Run targeted unit tests plus the locked baseline rerun after each task group.

## Migration Plan

1. Extract shared runtime state and route resolution helpers out of `legacy_adapter.py`.
2. Extract candidate flow and holding flow stage output builders.
3. Extract S7 order planning wrapper.
4. Rerun targeted tests and the locked baseline gate.
5. Freeze the old monolithic adapter structure once the split is stable.
