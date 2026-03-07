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

The current codebase implements parts of this model in the frontend drawer, parts in `_experiment_runner_api.py`, parts in strategy/engine modules, and parts in report rendering. The contract is not fully synchronized.

## Goals / Non-Goals
**Goals:**
- enumerate fields per stage across all layers
- surface unsupported frontend fields clearly
- add UI for backend-supported but frontend-missing fields
- preserve existing baseline outputs

**Non-Goals:**
- refactor provider architecture
- remove unused strategies
- redesign experiment storage

## Decisions
### D1: Stage alignment matrix
For each stage, track four columns:
- frontend control exists
- API compiler consumes field
- engine/runtime consumes field
- report/config artifact shows field

Any field missing from one or more required columns becomes an explicit cleanup item.

### D2: Frontend-only fields
If the frontend exposes a field that the backend path does not implement, the UI must mark it `未实现` rather than pretending it is active.

### D3: Backend-only fields
If the backend/compiler supports a stage field that belongs in the 9-stage workbench, the frontend must add a corresponding control unless the field is explicitly classified as research-only.

### D4: Naming convergence
Where the same concept appears under different names between frontend draft keys, API mapping keys, and report labels, one canonical stage name must be chosen and compatibility aliases handled in code.

### D5: Baseline safety
Stage contract cleanup cannot change the runtime meaning of the March 7 baseline. Added controls must default to today’s effective behavior.

## Alternatives Considered
1. Fix mismatches opportunistically per feature. Rejected because the problem spans all nine stages.
2. Only update frontend copy without adding controls. Rejected because backend-supported fields would remain inaccessible.
3. Merge this with engine cleanup. Rejected because UI/API contract work and engine refactor have different regression surfaces.
