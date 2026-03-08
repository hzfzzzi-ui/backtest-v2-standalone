## Why

The public single-run path is already pinned to:

`config_json -> compiler -> DataBundle -> foundation shell -> stage pipeline shell -> legacy adapter -> legacy execution kernel`

That solved config truth, preload boundaries, and public orchestration truth. However, the current
`legacy_adapter.py` still mixes route resolution, provider setup, daily controls, candidate flow,
holding flow, order planning, fill accounting hooks, and metric augmentation in one file.

If we keep adding logic there, the code will become the next legacy shell. That would make the
stage architecture harder to audit, harder to replace incrementally, and easier to break without a
clear blame boundary.

## What Changes

- Split `legacy_adapter.py` into explicit internal modules with narrow responsibilities.
- Keep the public execution path unchanged: only the internal adapter structure is refactored.
- Preserve the locked baseline `exp_20260308_021045840_cde0` with stepwise verification.
- Make route-specific logic auditable and easier to replace stage-by-stage in later changes.

## Capabilities

### New Capabilities
- `stage-adapter-decomposition`: The backend SHALL decompose the stage adapter into explicit,
  independently testable internal modules while preserving the current single public stage path.

## Impact

- Affected code: `backend/core/stage_pipeline/adapters/legacy_adapter.py`, new internal adapter
  modules under `backend/core/stage_pipeline/adapters/`, route wiring in the foundation path, and
  tests that verify adapter behavior.
- No intended change to trading math, fills, costs, timing semantics, or public artifact names.
- All implementation steps must continue to pass:
  `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`
