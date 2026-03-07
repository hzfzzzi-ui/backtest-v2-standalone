# V2 Universe Data Audit

## What
Audit and rationalize the universe-related data path for `ALL_A`, `HS300_ZZ500`, `CSI1000`, and related index constituent imports so the codebase clearly distinguishes runtime dependencies from redundant import artifacts.

## Why
Universe resolution is split across security master tables, OHLCV availability, and index constituent tables. CSI800/CSI1000 imports may contain redundant or confusing data because the runtime path for some universe modes does not use the same tables. Cleanup needs a fact-based audit before any deletion or schema simplification.

## Current State
- `HS300_ZZ500` and `CSI1000` resolve through `pit_index_constituents`
- `ALL_A` resolves through security master plus OHLCV presence instead of index constituents
- Import scripts for CSI-related universes exist alongside runtime resolvers
- It is not yet clear which tables/files are required, redundant, stale, or only historical

## Scope
- audit runtime read paths for universe resolution
- audit import scripts and generated data for CSI-related universes
- identify redundant data, scripts, and assumptions
- define a safe cleanup plan that does not change the March 7 baseline

## Non-Goals
- No immediate table deletion in this proposal
- No redesign of market data storage
- No strategy logic changes

## Capabilities
### New Capabilities
- `universe-data-audit`: universe modes have a documented data lineage from import to runtime consumption

### Modified Capabilities
- `implement-universe-modes`: universe mode documentation becomes aligned with actual runtime sources

## Impact
- Database-facing documentation and scripts
- Universe resolver expectations
- Cleanup decisions for index-constituent-related artifacts
