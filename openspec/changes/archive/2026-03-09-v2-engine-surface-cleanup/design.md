# Design: Engine Surface Cleanup

## Context
The current backend contains a mixture of production pathways and exploratory implementations:
- product-facing strategies reachable from workbench/API
- research-only strategies reachable mainly from scripts or direct registry usage
- provider modules that represent an unfinished architectural direction

This change focuses on the production surface area, not on inventing a new engine architecture. It must also reconcile with the existing `signal-provider-protocol` spec instead of ignoring it.

## Goals / Non-Goals
**Goals:**
- classify supported strategies and code paths
- shrink ambiguity in strategy routing
- make an explicit decision about provider protocol status
- isolate or remove dead misleading code that is not part of the supported path
- preserve the March 7 baseline exactly

**Non-Goals:**
- rewrite the vector engine from scratch
- make every research script use the product path
- change strategy math

## Decisions
### D1: Support classification
Every strategy and routing path should be tagged as one of:
- `product-supported`
- `research-only`
- `deprecated`

Classification must consider frontend reachability, API compiler support, stable engine execution support, and whether the path participates in baseline-safe runtime behavior.

### D2: Provider decision is mandatory
This change does not allow the current “half-adopted provider” state to remain. For each provider surface, the final state must be one of:
- integrated into the production runtime and aligned with `signal-provider-protocol`
- explicitly isolated behind a research-only boundary
- removed if unreferenced and unsupported

### D3: Registry convergence
The registry remains useful, but it must not imply that all registered strategies are first-class product features. Product-supported strategies should be discoverable separately from research-only entries.

### D4: Routing simplification
`portfolio_simulator_strict.py` should not keep accumulating ad hoc strategy-specific branching where a stable protocol already exists. Cleanup should reduce duplicate generic logic while preserving existing behavior.

### D5: Script boundary contract
Backend scripts used for matrix search may keep broader experimentation capability, but that boundary must be explicit so they do not define the apparent production contract. Script reachability alone is not evidence of product support.

### D6: Coordination with existing cleanup specs
This change must coordinate with existing `signal-provider-protocol` and `dead-code-removal` specs:
- provider cleanup cannot contradict the chosen provider-protocol outcome
- deletions cannot be justified solely by zero-reference if the code remains part of an explicitly supported research or production path

## Alternatives Considered
1. Keep all code and only add comments. Rejected because the current problem is structural ambiguity.
2. Delete all non-UI strategies immediately. Rejected because some remain valid for research and parameter search.
3. Ignore the existing provider spec and clean files opportunistically. Rejected because it would preserve architectural ambiguity.
4. Merge engine cleanup with 9-stage alignment. Rejected because engine internals and frontend/API contract should be stabilized separately.
