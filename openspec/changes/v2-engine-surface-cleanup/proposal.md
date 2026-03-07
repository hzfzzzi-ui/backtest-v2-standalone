# V2 Engine Surface Cleanup

## What
Clean up the production engine surface by separating product-supported strategies from research-only code, removing or isolating dead paths, and converging duplicated routing logic without changing baseline results.

## Why
The engine currently exposes more strategy and provider surface area than the main product path actually uses. Registry entries, provider files, and simulator branches have drifted apart. This raises the cost of every change and makes it unclear what is safe to rely on.

## Current State
- `registry.py` can build more strategies than the workbench/API path truly supports
- `portfolio_simulator_strict.py` contains strategy-specific routing and duplicated generic logic
- provider-based architecture is only partially adopted
- research scripts and production paths share modules without a clear boundary

## Scope
- classify strategy/engine surfaces as product-supported vs research-only
- reduce duplicated routing logic on the production path
- decide whether half-integrated provider modules should be integrated, isolated, or removed
- clean up dead or misleading code paths that are not part of the supported V2 baseline path

## Non-Goals
- No new strategy behavior
- No optimization work beyond cleanup needed for maintainability
- No database cleanup in this change

## Capabilities
### New Capabilities
- `engine-support-matrix`: supported engine/strategy surfaces are explicitly classified for product vs research usage

### Modified Capabilities
- `signal-provider-protocol`: provider adoption becomes intentional instead of partial and ambiguous
- `single-run-pipeline`: runtime strategy routing becomes easier to reason about and verify

## Impact
- Strategy registry and adapter surfaces
- Vector engine routing
- Production vs research boundaries in backend scripts and strategy modules
- Baseline regression workflow
