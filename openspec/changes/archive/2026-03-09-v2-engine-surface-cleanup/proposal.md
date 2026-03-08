# V2 Engine Surface Cleanup

## What
Clean up the production engine surface by separating product-supported strategies from research-only code, making an explicit decision on the partial provider architecture, removing or isolating dead paths, and converging duplicated routing logic without changing baseline results.

## Why
The engine currently exposes more strategy and provider surface area than the main product path actually uses. Registry entries, provider files, simulator branches, and script-driven search paths have drifted apart. The codebase also already contains a `signal-provider-protocol` spec, but the current runtime only partially follows it.

## Current State
- `registry.py` can build more strategies than the workbench/API path truly supports
- `portfolio_simulator_strict.py` contains strategy-specific routing and duplicated generic logic
- provider-based architecture is only partially adopted
- research scripts and production paths share modules without a clear boundary
- existing dead-code-removal work does not yet establish a product-vs-research support matrix for these engine surfaces

## Scope
- classify strategy/engine surfaces as product-supported vs research-only vs deprecated
- make an explicit keep/integrate/isolate decision for provider-based architecture
- reduce duplicated routing logic on the production path
- clean up dead or misleading code paths that are not part of the supported V2 baseline path
- define script boundary rules so matrix-search capability does not masquerade as product support

## Non-Goals
- No new strategy behavior
- No optimization work beyond cleanup needed for maintainability
- No database cleanup in this change
- No full engine rewrite

## Capabilities
### New Capabilities
- `engine-support-matrix`: supported engine/strategy surfaces are explicitly classified for product vs research usage
- `engine-architecture-decision`: provider protocol status is explicit rather than half-adopted

### Modified Capabilities
- `signal-provider-protocol`: provider adoption becomes intentional instead of partial and ambiguous
- `single-run-pipeline`: runtime strategy routing becomes easier to reason about and verify
- `dead-code-removal`: engine-side removals are gated by support classification rather than zero-reference alone

## Impact
- Strategy registry and adapter surfaces
- Vector engine routing
- Production vs research boundaries in backend scripts and strategy modules
- Coordination with existing provider/dead-code specs
- Baseline regression workflow
