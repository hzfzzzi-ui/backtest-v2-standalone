# V2 Shrink Inventory (2026-03-07)

This inventory now lives under `docs/ops/` because it is a cleanup control
artifact for maintainers.

This inventory classifies the additive surfaces introduced or formalized during
the March 7 cleanup sequence. It is the starting point for `v2-shrink-pass`.

## Classification rules

- `steady-state`
  - keep as a maintained product abstraction or operational guardrail
- `transitional`
  - useful during cleanup, but should be folded into owning modules once the
    contract is stable
- `deprecated-delete-candidate`
  - explicitly deprecated and eligible for deletion once no supported path or
    active workflow depends on it
- `ops-only`
  - useful for operators, audit, or maintenance, but not part of the product
    runtime surface and should live in an explicit ops-oriented location

## Inventory

| Surface | Class | Current role | Recommended action | Evidence |
| --- | --- | --- | --- | --- |
| `backend/api/endpoints/_config_governance.py` | `steady-state` | Canonical config identity and runtime-resolution contract shared by save/list/read/run/preview | Keep separate | Imported by `_config_store.py`, `_experiment_runner_api.py`, and `backtest_v2.py` |
| `backend/scripts/baseline_regression_check.py` | `steady-state` | Baseline gate required before each production-surface cleanup step | Keep, but later consider moving under an ops script namespace | Used directly in cleanup validation workflow and documented in `docs/ops/baseline_regression_contract_2026-03-07.md` |
| `backend/core/engine_vector/runtime_surface.py` | `transitional` | Made product/research/deprecated runtime classification explicit during cleanup | Merged into `portfolio_simulator_strict.py` in the second shrink batch and removed | Runtime import surface was only `portfolio_simulator_strict.py`; route metadata had no independent consumer |
| `backend/core/universe/lineage.py` | `steady-state` | Centralizes universe timing/source semantics shared by runtime, API validation, and audit tooling | Keep separate | Imported by `experiment_runner.py`, `backtest_v2.py`, `universe_resolver.py`, `hs300_csi500.py`, and `backend/scripts/ops/universe_data_audit.py` |
| `backend/core/engine_vector/strategy_adapter.py` | `deprecated-delete-candidate` | Legacy helper outside current provider contract | Deleted in first shrink batch | No live imports; only referenced by `runtime_surface.py` metadata |
| `backend/core/strategies/adaptive_regime.py` | `deprecated-delete-candidate` | Standalone legacy strategy implementation replaced by `RegimeRouter` compatibility build path | Deleted after confirming live compiler/registry no longer accepts the legacy strategy name | No live imports; `adaptive_regime` is now rejected in runtime entrypoints |
| `backend/scripts/ops/universe_data_audit.py` | `ops-only` | Emits universe lineage audit JSON and inventories runtime/import assets | Moved to explicit ops script namespace | No product runtime imports; used for operator audit |
| `docs/ops/baseline_regression_contract_2026-03-07.md` | `ops-only` | Operator runbook for baseline gate | Moved under `docs/ops/` | Pure operator workflow documentation |
| `docs/ops/v2_engine_surface_matrix_2026-03-07.md` | `ops-only` | Cleanup support matrix documenting product/research/deprecated engine surfaces | Moved under `docs/ops/` | Not part of product behavior |
| `docs/ops/v2_universe_data_audit_2026-03-07.md` | `ops-only` | Cleanup audit report for universe lineage and import chains | Moved under `docs/ops/` | Not part of product behavior |
| `docs/ops/v2_9stage_contract_matrix_2026-03-07.md` | `ops-only` | Cleanup alignment matrix for UI/API/runtime/report surfaces | Moved under `docs/ops/` | Product-adjacent reference, but not runtime documentation |

## Helper decisions

- Merge `backend/core/engine_vector/runtime_surface.py` into
  `backend/core/engine_vector/portfolio_simulator_strict.py`
  - reason: only one live runtime consumer, and that consumer only used the
    route id branch result
- Keep `backend/core/universe/lineage.py` separate
  - reason: it is no longer just cleanup scaffolding; runtime execution, API
    validation, and audit tooling now share the same universe timing/source
    contract through this module

## First shrink batch

The first deletion target was:
- `backend/core/engine_vector/strategy_adapter.py`

Reason:
- already classified as `deprecated`
- no runtime imports
- no matrix-search workflow dependency
- no baseline contract dependency

## Deprecated path cleanup status

- `backend/core/engine_vector/strategy_adapter.py`
  - deleted in the first shrink batch
- `backend/core/strategies/adaptive_regime.py`
  - deleted after removing the live `adaptive_regime` compatibility path from
    compiler/registry entrypoints
  - remaining mentions in specs and archived changes are historical references,
    not live runtime dependencies

## Second shrink batch

The second shrink target was:
- `backend/core/engine_vector/runtime_surface.py`

Reason:
- already classified as `transitional`
- only one live runtime consumer
- live runtime only needed route ids, not a separate metadata layer
- product/research classification remains documented in
  `docs/ops/v2_engine_surface_matrix_2026-03-07.md`

## Compatibility cleanup batch

The compatibility branch removed in this batch was:
- `ADAPTIVE_REGIME` as a live compiler/runtime strategy identifier

Reason:
- no saved configs or experiment artifacts in `outputs/` still used it
- it was no longer part of the supported 9-stage or product runtime contract
- keeping it would preserve an execution path that the UI no longer exposes
- existing retained fallbacks such as artifact filename aliases are read-only
  compatibility and therefore not part of this removal batch

## Artifact compatibility cleanup batch

The read-only fallbacks removed in this batch were:
- `reason_code_counts.csv -> reason_codes.csv`
- `raw_signal_count/blocked_count/orders_count/skipped_count/closed_trades_count`
  -> canonical funnel counter keys

Reason:
- all current `outputs/experiments/*` artifacts already use canonical filenames
  and canonical counter fields
- retaining the aliases preserved dead read paths in both API preview and
  frontend artifact rendering
- `symbol_performance.json` fallback remains intentionally retained as a
  separate compatibility case

## Next actions

1. Rerun static checks
2. Run baseline self-check
3. Rerun baseline in container
4. Record the result
5. Choose the next shrink target from historical spec/archive cleanup or
   operator-only script consolidation
