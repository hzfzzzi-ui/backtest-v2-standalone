# Design: Universe Data Audit

## Context
The baseline experiment uses `HS300_ZZ500` and draws symbols from `pit_index_constituents`. Other modes, especially `ALL_A`, use a different runtime source. This creates two risks:
- data import chains may appear required even when a runtime path does not consume them
- redundant data may be preserved because nobody has traced source-to-runtime lineage precisely

## Goals / Non-Goals
**Goals:**
- trace runtime data lineage for each supported universe mode
- trace CSI import lineage into runtime tables/files
- identify redundant or ambiguous universe data assets
- preserve baseline universe behavior exactly

**Non-Goals:**
- rewrite universe selection logic
- change table schemas immediately
- purge data during the audit phase

## Decisions
### D1: Audit by universe mode
Each supported universe mode is documented independently:
- runtime resolver entry point
- database tables consumed
- import scripts or upstream data dependencies
- filters applied after symbol resolution

### D2: Separate audit from deletion
This change produces a verified cleanup plan, not immediate destructive changes. Anything identified as redundant must still be validated against baseline and non-baseline workflows before removal.

### D3: Baseline-first policy
Because the accepted baseline uses `HS300_ZZ500`, any cleanup affecting `pit_index_constituents`, index code mapping, or symbol eligibility must prove that baseline symbol counts and results are unchanged.

### D4: Cross-check script assumptions
Scripts that import CSI800/CSI1000 constituents must be checked against the actual codes and tables used by runtime universe resolvers. Naming mismatches, dead scripts, or stale assumptions are cleanup targets.

## Alternatives Considered
1. Delete obvious old import files first. Rejected because runtime dependencies are not fully documented.
2. Treat all constituent imports as authoritative for every universe mode. Rejected because `ALL_A` already uses a different path.
3. Merge this into generic engine cleanup. Rejected because database lineage needs its own audit lens and verification criteria.
