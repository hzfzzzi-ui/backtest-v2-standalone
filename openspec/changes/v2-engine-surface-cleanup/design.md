# Design: Engine Surface Cleanup

## Context
The current backend contains a mixture of production pathways and exploratory implementations:
- product-facing strategies reachable from workbench/API
- research-only strategies reachable mainly from scripts or direct registry usage
- provider modules that represent an unfinished architectural direction

This change focuses on the production surface area, not on inventing a new engine architecture.

## Goals / Non-Goals
**Goals:**
- classify supported strategies and code paths
- shrink ambiguity in strategy routing
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

Classification must consider frontend reachability, API compiler support, and stable engine execution support.

### D2: Registry convergence
The registry remains useful, but it must not imply that all registered strategies are first-class product features. Product-supported strategies should be discoverable separately from research-only entries.

### D3: Provider cleanup rule
Half-integrated provider modules are not allowed to remain ambiguous. For each provider surface:
- fully integrate into the production routing path, or
- move behind a research-only boundary, or
- remove if unreferenced

### D4: Routing simplification
`portfolio_simulator_strict.py` should not keep accumulating ad hoc strategy-specific branching where a stable protocol already exists. Cleanup should reduce duplicate generic logic while preserving existing behavior.

### D5: Script boundary
Backend scripts used for matrix search may keep broader experimentation capability, but that boundary must be explicit so they do not define the apparent production contract.

## Alternatives Considered
1. Keep all code and only add comments. Rejected because the current problem is structural ambiguity.
2. Delete all non-UI strategies immediately. Rejected because some remain valid for research and parameter search.
3. Merge engine cleanup with 9-stage alignment. Rejected because engine internals and frontend/API contract should be stabilized separately.
