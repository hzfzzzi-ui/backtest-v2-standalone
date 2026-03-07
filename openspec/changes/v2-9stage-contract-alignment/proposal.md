# V2 9-Stage Contract Alignment

## What
Audit and align the full 9-stage pipeline contract across frontend controls, API compilation, engine consumption, and report display, without changing baseline behavior.

## Why
The current system has three conflicting truths:
- what the frontend claims can be configured
- what `_experiment_runner_api.py` actually compiles
- what the engine and reports really consume

This creates UI controls that do nothing, backend parameters with no UI, and stage fields that appear in one layer but not another.

## Current State
- Some frontend options are not implemented in the backend path
- Some backend-supported fields have no frontend controls
- The project has existing stage-specific changes, but no single contract audit across all 9 stages
- Strategy-specific fields are mixed with stage fields in the current UI

## Scope
- Build a stage-by-stage alignment matrix for S1-S9
- Mark frontend-only unsupported fields as `未实现`
- Add missing frontend controls for backend-supported stage fields
- Normalize naming drift between frontend draft schema, API compiler schema, and report schema

## Non-Goals
- No new strategy algorithms
- No performance optimization
- No provider refactor in this change

## Capabilities
### New Capabilities
- `9stage-contract-matrix`: a single source of truth for stage ownership and support status across frontend, API, engine, and report layers

### Modified Capabilities
- `9stage-drawer-layout`: stage controls must match backend-supported fields
- `artifact-protocol-consistency`: stage data shown in reports must reflect compiled runtime config

## Impact
- Frontend controls and labels
- API compiler field mapping
- Report/config display consistency
- Validation against the March 7 baseline
