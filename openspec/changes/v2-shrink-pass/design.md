# Design: V2 Shrink Pass

## Context
The March 7 cleanup sequence was baseline-safe precisely because it added
structure before removing anything. That was the correct first move, but it
left the codebase with several classes of transitional surface:

- helper modules created to make hidden behavior explicit
- deprecated or compatibility-only paths that now have classification labels
- operator-only scripts and generated audit docs mixed into product-adjacent
  directories
- folded-over compatibility branches that remain after truth is known

This change is the follow-up that actually shrinks the maintained system.

## Goals / Non-Goals
**Goals:**
- identify which new helpers are steady-state product abstractions and which are
  transitional
- merge or inline transitional helpers once their contracts are stable
- delete deprecated paths that are no longer reachable or justified
- move pure ops assets into explicit ops-oriented locations
- remove compatibility branches when baseline safety is already enforced
- require baseline rerun after each production-surface reduction step

**Non-Goals:**
- deleting baseline guardrails
- collapsing product/research separation back into ambiguity
- removing research-only tooling still needed by active search workflows
- large behavioral rewrites disguised as shrink work

## Decisions
### D1: Shrink by class, not by file count
This pass operates on four classes of code:
- transitional helpers
- deprecated runtime paths
- pure ops assets
- compatibility branches

Deletions or merges must be justified by class membership, not by “looks large”.

### D2: Product abstractions stay explicit; transitional ones get folded
Some newly added helpers are now part of the real contract and should remain
separate, while others only exist to bridge cleanup work.

Likely steady-state helpers:
- `backend/api/endpoints/_config_governance.py`
- `backend/scripts/baseline_regression_check.py`

Likely transitional or foldable helpers:
- `backend/core/engine_vector/runtime_surface.py`
- `backend/core/universe/lineage.py`

This change must decide which helpers get merged into owning modules and which
remain as long-term boundaries.

### D3: Deprecated means deletion candidate, not permanent annotation
Paths already classified as `deprecated` by the support matrices are now
deletion candidates if:
- no product-supported runtime depends on them
- no active research workflow explicitly requires them
- baseline and matrix-search checks stay green after removal

Examples to evaluate first:
- `backend/core/engine_vector/strategy_adapter.py`
- `backend/core/strategies/adaptive_regime.py` if compatibility no longer
  requires the standalone implementation file

### D4: Ops assets need an explicit home
Pure operator or audit artifacts should not continue to accumulate in
product-adjacent locations without a dedicated convention.

This pass should define a clearer home for:
- operator scripts such as baseline/audit checks
- governance and audit documentation generated for cleanup work

Possible destination patterns:
- `backend/scripts/ops/`
- `docs/ops/`

The exact destination is less important than having a clear, consistent rule.

### D5: Compatibility branches must justify their existence
Compatibility branches that were retained during cleanup should be revisited.
If a branch only protects legacy ambiguity that is no longer allowed by the new
contract, it should be removed.

Candidates:
- config/source compatibility branches that duplicate normalized behavior
- universe/source naming fallbacks whose old labels are no longer authoritative
- engine dispatch or reporting fallbacks that remain only for old naming

### D6: Baseline-first deletion protocol
Each production-surface reduction step must follow:
1. make one focused shrink change
2. run static verification
3. run baseline self-check
4. rerun baseline in container
5. only proceed if no blocking drift occurs

This pass should favor multiple small deletions over one large sweep.

### D7: Coordinate with existing specs instead of bypassing them
This pass must coordinate with:
- `dead-code-removal`
- `signal-provider-protocol`
- the March 7 cleanup changes already implemented

It should turn existing classifications into actual removals, not redefine the
taxonomy from scratch.

## Alternatives Considered
1. Leave the additive cleanup layer in place permanently.
   Rejected because it keeps maintenance cost high after ambiguity is already
   resolved.

2. Delete aggressively now that baseline gates exist.
   Rejected because research-only search workflows still need explicit
   protection and must be checked before removal.

3. Open multiple micro-changes instead of one shrink pass.
   Rejected because the problem is systemic and the shrink criteria should be
   centralized in one pass, even if implementation happens in batches.
