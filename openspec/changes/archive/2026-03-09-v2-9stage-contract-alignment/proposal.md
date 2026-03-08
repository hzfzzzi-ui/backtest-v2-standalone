# V2 9-Stage Contract Alignment

## What
Audit and align the full 9-stage pipeline contract across frontend controls, S1 validation flow, API compilation, engine consumption, preview/report display, and auxiliary UI surfaces, without changing baseline behavior.

## Why
The current system has more than one conflicting truth:
- what the frontend claims can be configured
- what `_experiment_runner_api.py` actually compiles
- what the engine and reports really consume
- what S1 validation, summary bars, and preview surfaces imply to the user

This creates UI controls that do nothing, backend parameters with no UI, universe validation that does not reflect actual universe resolution, and stage-adjacent surfaces that drift away from the compiled runtime config.

## Current State
- Some frontend options are not implemented in the backend path
- Some backend-supported fields have no frontend controls
- S1 validation for non-`CUSTOM` modes does not represent real universe resolution
- `signal_composition` still exists in the UI, but the main experiment compiler path does not make it a first-class runtime contract
- The project has existing stage-specific changes, but no single contract audit across all 9 stages and their adjacent surfaces

## Scope
- Build a stage-by-stage alignment matrix for S1-S9 plus stage-adjacent surfaces
- Mark frontend-only unsupported fields as `未实现`
- Add missing frontend controls for backend-supported stage fields
- Align S1 validation with the real universe-resolution semantics or explicitly classify its limitations
- Decide the disposition of `signal_composition` and other non-stage/ghost surfaces
- Normalize naming drift between frontend draft schema, API compiler schema, preview/report schema, and summary displays

## Non-Goals
- No new strategy algorithms
- No performance optimization
- No provider refactor in this change

## Capabilities
### New Capabilities
- `9stage-contract-matrix`: a single source of truth for stage ownership and support status across frontend, validation, API, engine, preview, and report layers

### Modified Capabilities
- `9stage-drawer-layout`: stage controls must match backend-supported fields
- `artifact-protocol-consistency`: stage data shown in previews and reports must reflect compiled runtime config
- `single-run-pipeline`: S1 validation and summary surfaces must not imply a universe/runtime truth they do not actually execute

## Impact
- Frontend controls, warnings, and labels
- API compiler field mapping
- Validation, summary, preview, and report consistency
- Validation against the March 7 baseline
