# Tasks: v2-engine-surface-cleanup

- [x] Build a strategy/engine support matrix covering UI reachability, API compile support, runtime execution support, and script-only reachability
- [x] Classify strategies and engine paths as product-supported, research-only, or deprecated
- [x] Audit provider modules against the existing `signal-provider-protocol` spec and record the keep/integrate/isolate decision
- [x] Audit duplicated simulator logic and choose convergence/removal targets
- [x] Separate script-only experimentation paths from the product runtime contract
- [x] Coordinate engine-side removals with the existing `dead-code-removal` spec so support classification is preserved
- [x] Clean up or isolate dead/misleading production-surface code paths
- [x] Rerun the March 7 baseline after each production-surface cleanup step
