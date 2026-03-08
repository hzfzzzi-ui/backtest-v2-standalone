# V2 Config Source Governance

## What
Define a single, explicit runtime configuration contract for Backtest V2 so manual baseline runs and Claude-generated matrix runs no longer share ambiguous precedence, identity, or metadata.

## Why
Current runs can carry both `config_id` and `workbench_config`, while `_experiment_runner_api.py` silently lets `config_id` override the UI draft. At the same time, `config_id` is currently derived from the content hash of `config_json`, which means a manual baseline save and a Claude-generated search save can collide onto the same saved-config identity and overwrite provenance metadata. `run_async` and `execution_preview` both participate in this ambiguity.

## Current State
- Frontend run payload sends both `config_id` and `workbench_config`
- Backend precedence is `config_id > workbench_config`
- `config_id` is hash-derived from `config_json`, so content identity and saved-record identity are conflated
- Frontend has no explicit `loaded-clean / loaded-dirty / draft-only` state model after a config is loaded
- `run_async` and `execution_preview` both resolve saved config first, but the UI does not surface this clearly
- `outputs/configs/` mixes manual baselines, matrix-search artifacts, built-in templates, and derived configs without a stable source taxonomy

## Scope
- Separate content identity from saved-record identity while preserving legacy compatibility
- Define config source taxonomy: `baseline | search | template | derived`
- Define owner taxonomy: `manual | claude | script | builtin`
- Make runtime precedence explicit in API contract and frontend UI state
- Add visible mode distinction between `run current draft` and `run saved config`
- Add dirty-state semantics after loading a saved config
- Align `run_async`, `execution_preview`, config list/read, and built-in config injection under the same provenance model
- Normalize config metadata and list/display behavior

## Non-Goals
- No strategy logic changes
- No engine output changes
- No baseline metric changes
- No destructive migration of historical saved configs in this change

## Capabilities
### New Capabilities
- `config-source-governance`: runtime config source precedence is explicit, inspectable, and stable across frontend, API, preview, and saved config artifacts
- `config-identity-model`: content identity and saved-record identity are no longer implicitly the same concept
- `config-metadata-contract`: saved configs expose normalized metadata for source, owner, lock state, and baseline linkage

### Modified Capabilities
- `single-run-pipeline`: run requests and preview requests must expose whether execution came from current draft or saved config
- `champion-config-presets`: champion/baseline configs become distinguishable from search artifacts and built-in templates

## Impact
- Frontend: run buttons, config load state, dirty-state UX, saved-config labels, preview behavior
- Backend API: config save/list/get endpoints, run request resolution, preview resolution, metadata exposure
- Stored configs: normalized metadata, compatibility defaults, legacy hash-derived config handling
- Validation: baseline experiment `exp_20260307_051743747_77d8` must remain unchanged
