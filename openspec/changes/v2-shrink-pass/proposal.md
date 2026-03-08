# V2 Shrink Pass

## What
Run a second-phase shrink pass over the March 7 cleanup work so the codebase
starts removing temporary governance scaffolding, deprecated runtime paths,
pure ops assets in product-facing locations, and stale compatibility branches
that are now protected by the baseline regression gate.

## Why
The first cleanup phase was intentionally additive:
- config governance was made explicit
- baseline regression was formalized
- 9-stage alignment exposed contract truth
- engine and universe surfaces were classified

That phase reduced ambiguity, but it also increased code surface area. The
branch now carries nearly 3k lines of net growth, much of which belongs to:
- one-time governance helpers
- compatibility layers kept for safety
- operator-only scripts and audit documents in product-adjacent paths

This pass exists to convert that additive safety layer into a smaller, clearer
steady-state system.

## Current State
- baseline guardrails are present and repeatable
- support matrices now classify product vs research vs deprecated paths
- some helpers exist only to explain or stabilize transitional architecture
- several deprecated or research-only paths are still physically present
- pure ops artifacts now live alongside product runtime code and docs
- compatibility logic remains layered rather than folded back into the mainline

## Scope
- merge or downshift one-time governance helpers that are no longer earning
  their own abstraction boundary
- remove deprecated paths that the support matrices no longer justify keeping
- move pure operator/audit assets to more explicit ops locations
- reduce compatibility branches that are now covered by baseline regression
- preserve the March 7 baseline exactly while shrinking the maintained surface

## Non-Goals
- no redesign of product behavior
- no change to baseline strategy math or universe results
- no removal of baseline regression capability itself
- no deletion of research-only paths that are still explicitly needed for
  matrix-search workflows

## Capabilities
### New Capabilities
- `cleanup-shrink-pass`: additive cleanup layers can be folded or removed once
  baseline protection exists

### Modified Capabilities
- `config-source-governance`: governance behavior remains, but temporary helper
  surfaces may be merged into steady-state ownership boundaries
- `engine-surface-cleanup`: deprecated surfaces move from classified to deleted
  when no supported path depends on them
- `universe-data-audit`: audit outputs remain available, but pure ops assets may
  move out of product-adjacent locations

## Impact
- backend architecture boundaries
- deprecated runtime paths
- operator-facing scripts and docs placement
- future maintenance cost and review load
