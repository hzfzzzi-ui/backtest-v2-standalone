# Design: Universe Data Audit

## Context
The baseline experiment uses `HS300_ZZ500` and draws symbols from `pit_index_constituents`. Other modes, especially `ALL_A`, use a different runtime source. This creates three risks:
- data import chains may appear required even when a runtime path does not consume them
- redundant data may be preserved because nobody has traced source-to-runtime lineage precisely
- validation/summary surfaces may imply universe behavior that differs from actual runtime resolution

## Goals / Non-Goals
**Goals:**
- trace runtime data lineage for each supported universe mode
- trace CSI import lineage into runtime tables/files
- trace `resolve_asof` semantics per mode
- identify redundant or ambiguous universe data assets and naming
- preserve baseline universe behavior exactly

**Non-Goals:**
- rewrite universe selection logic
- change table schemas immediately
- purge data during the audit phase

## Decisions
### D1: Audit by universe mode
Each supported universe mode is documented independently with:
- runtime resolver entry point
- `resolve_asof` date source
- database tables consumed
- import scripts or upstream data dependencies
- filters applied after symbol resolution
- validation-path behavior shown to the user

### D2: Separate audit from deletion
This change produces a verified cleanup plan, not immediate destructive changes. Anything identified as redundant must still be validated against baseline and non-baseline workflows before removal.

### D3: Baseline-first policy
Because the accepted baseline uses `HS300_ZZ500`, any cleanup affecting `pit_index_constituents`, index code mapping, symbol eligibility, or timing semantics must prove that baseline symbol counts and results are unchanged.

### D4: Cross-check script assumptions
Scripts that import CSI800/CSI1000 constituents must be checked against the actual codes, tables, and timing semantics used by runtime universe resolvers. Naming mismatches, dead scripts, or stale assumptions are cleanup targets.

### D5: `resolve_asof` semantics are first-class
The audit must explicitly document the current difference between:
- `ALL_A` dynamic entry behavior, which resolves from end-date semantics in the current runtime path
- index-constituent universe modes, which currently resolve from start-date semantics

This timing difference is part of the universe contract and cannot be treated as incidental implementation detail.

### D6: Validation-path linkage
The audit must document whether `/validate_data` is:
- a true runtime-universe validation path, or
- a sample-symbol validation helper

If it is sample-only for non-`CUSTOM` modes, that limitation must be explicit and aligned with S1 contract work.

### D7: Source-label cleanup
Metadata labels such as `symbols_source` and related source descriptors must match actual runtime behavior. Historical names that imply index-constituent loading for `ALL_A`-style flows are cleanup candidates.

## Alternatives Considered
1. Delete obvious old import files first. Rejected because runtime dependencies are not fully documented.
2. Treat all constituent imports as authoritative for every universe mode. Rejected because `ALL_A` already uses a different path.
3. Ignore validation-path semantics and only audit tables. Rejected because user-facing S1 behavior is part of the system contract.
4. Merge this into generic engine cleanup. Rejected because database lineage needs its own audit lens and verification criteria.
