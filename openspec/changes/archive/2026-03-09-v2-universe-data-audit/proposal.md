# V2 Universe Data Audit

## What
Audit and rationalize the universe-related data path for `ALL_A`, `HS300_ZZ500`, `CSI1000`, and related index constituent imports so the codebase clearly distinguishes runtime dependencies from redundant import artifacts, `resolve_asof` semantics, and validation-path assumptions.

## Why
Universe resolution is split across security master tables, OHLCV availability, and index constituent tables. CSI800/CSI1000 imports may contain redundant or confusing data because the runtime path for some universe modes does not use the same tables. In addition, runtime universe resolution and S1 validation are not currently aligned under one clearly documented contract.

## Current State
- `HS300_ZZ500` and `CSI1000` resolve through `pit_index_constituents`
- `ALL_A` resolves through security master plus OHLCV presence instead of index constituents
- `ALL_A` and index-based universes do not currently share the same `resolve_asof` semantics
- Import scripts for CSI-related universes exist alongside runtime resolvers
- S1 validation does not currently represent real non-`CUSTOM` universe resolution
- It is not yet clear which tables/files are required, redundant, stale, or only historical

## Scope
- audit runtime read paths for universe resolution
- audit `resolve_asof` semantics by universe mode
- audit import scripts and generated data for CSI-related universes
- audit the relationship between S1 validation and actual runtime universe resolution
- identify redundant data, scripts, source labels, and assumptions
- define a safe cleanup plan that does not change the March 7 baseline

## Non-Goals
- No immediate table deletion in this proposal
- No redesign of market data storage
- No strategy logic changes
- No destructive purge during the audit phase

## Capabilities
### New Capabilities
- `universe-data-audit`: universe modes have a documented data lineage from import to runtime consumption
- `universe-resolution-semantics`: `resolve_asof`, symbol source, and validation-path semantics are explicit per universe mode

### Modified Capabilities
- `implement-universe-modes`: universe mode documentation becomes aligned with actual runtime sources and timing semantics
- `single-run-pipeline`: S1 validation must not imply a universe contract different from runtime resolution

## Impact
- Database-facing documentation and scripts
- Universe resolver expectations
- Validation-path expectations
- Cleanup decisions for index-constituent-related artifacts and metadata names
