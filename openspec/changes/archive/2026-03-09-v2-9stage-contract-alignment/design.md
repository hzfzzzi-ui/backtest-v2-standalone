# Design: 9-Stage Contract Alignment

## Context
The V2 pipeline is conceptually divided into nine stages:
- S1 Universe
- S2 Market regime
- S3 Industry gate
- S4 Stock trend filter
- S5 Ranking
- S6 Entry / strategy signal
- S7 Portfolio construction
- S8 Risk control
- S9 Exit rules

The current codebase implements parts of this model in the frontend drawer, parts in `_experiment_runner_api.py`, parts in strategy/engine modules, and parts in report rendering. In addition, stage-adjacent surfaces such as S1 validation, summary bars, config diff, execution preview, and `signal_composition` create additional user-visible contract drift.

## Goals / Non-Goals
**Goals:**
- enumerate fields per stage across all relevant layers
- surface unsupported frontend fields clearly
- add UI for backend-supported but frontend-missing fields
- align S1 validation semantics with real universe resolution
- classify ghost or non-stage surfaces such as `signal_composition`
- preserve existing baseline outputs

**Non-Goals:**
- refactor provider architecture
- remove unused strategies
- redesign experiment storage

## Decisions
### D1: Expanded stage alignment matrix
For each stage, track these columns:
- frontend control exists
- validation/summary surface exists
- API compiler consumes field
- engine/runtime consumes field
- preview/report artifact shows field
- support status (`product-supported | research-only | unimplemented`)

Any field missing from one or more required columns becomes an explicit cleanup item.

### D2: Frontend-only fields
If the frontend exposes a field that the backend path does not implement, the UI must mark it `未实现` rather than pretending it is active.

### D3: Backend-only fields
If the backend/compiler supports a stage field that belongs in the 9-stage workbench, the frontend must add a corresponding control unless the field is explicitly classified as research-only.

### D4: S1 validation alignment
S1 validation must either:
- use the real resolver path for `ALL_A`, `HS300_ZZ500`, `CSI1000`, and `INDUSTRY`, or
- explicitly declare that a given validation surface is sample-only and not representative of the runtime universe

The current sample-symbol fallback for non-`CUSTOM` modes is not an acceptable implicit contract.

### D5: Ghost-surface disposition
Non-stage or ghost surfaces must be classified explicitly:
- `signal_composition`
- summary bar strategy/universe text
- config diff panel
- execution preview payload semantics

A surface may remain only if its relationship to the compiled runtime config is explicit.

### D6: Known mismatch backlog
This change begins with a concrete mismatch set already visible in the current codebase:
- `RSI_REVERSAL` exists in frontend/registry but is not part of the main strategy compile map
- `benchmark_regime` is compiled/consumed inconsistently across UI and runtime
- `breadth` is supported in backend config/runtime but not surfaced in frontend stage controls
- `sizing.weight_mode` and `sizing.min_positions` are backend-supported but frontend-missing
- breakout advanced fields such as `enable_dual_breakout`, `entry_confirm_mode`, `entry_delay_mode`, and `portfolio_mode` are not fully represented in the current stage UI
- `ma20_exit`, `low10_exit`, and `universe_filter.min_price` are not fully aligned across UI/compiler/report surfaces
- `signal_composition` is user-visible despite not being a first-class main-path runtime contract

### D7: Naming convergence
Where the same concept appears under different names between frontend draft keys, API mapping keys, and report labels, one canonical stage name must be chosen and compatibility aliases handled in code.

### D8: Baseline safety
Stage contract cleanup cannot change the runtime meaning of the March 7 baseline. Added controls must default to today’s effective behavior.

## Alternatives Considered
1. Fix mismatches opportunistically per feature. Rejected because the problem spans all nine stages and adjacent surfaces.
2. Only update frontend copy without adding controls. Rejected because backend-supported fields would remain inaccessible.
3. Leave S1 validation as sample-only behavior without labeling it. Rejected because it creates false confidence in universe behavior.
4. Merge this with engine cleanup. Rejected because UI/API contract work and engine refactor have different regression surfaces.
