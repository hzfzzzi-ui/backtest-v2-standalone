# V2 Config Source Governance

## What
Define a single, explicit runtime configuration contract for Backtest V2 so manual baseline runs and Claude-generated matrix runs no longer share ambiguous precedence or metadata.

## Why
Current runs can carry both `config_id` and `workbench_config`, while `_experiment_runner_api.py` silently lets `config_id` override the UI draft. This makes the page state, saved config, and executed config diverge. `outputs/configs/` also mixes manual baselines, matrix-search artifacts, built-in templates, and derived configs without a stable source taxonomy.

## Current State
- Frontend run payload sends both `config_id` and `workbench_config`
- Backend precedence is `config_id > workbench_config`
- Saved configs under `outputs/configs/` do not have a required `source_type/owner/locked` contract
- Manual baseline configs and search configs are hard to distinguish in API lists and experiment history

## Scope
- Define config source taxonomy: `baseline | search | template | derived`
- Define owner taxonomy: `manual | claude | script | builtin`
- Make runtime precedence explicit in API contract and frontend UI state
- Add visible mode distinction between `run current draft` and `run saved config`
- Normalize config metadata and list/display behavior

## Non-Goals
- No strategy logic changes
- No engine output changes
- No baseline metric changes

## Capabilities
### New Capabilities
- `config-source-governance`: runtime config source precedence is explicit, inspectable, and stable across frontend, API, and saved config artifacts
- `config-metadata-contract`: saved configs expose normalized metadata for source, owner, and lock state

### Modified Capabilities
- `single-run-pipeline`: run requests must expose whether execution came from current draft or saved config
- `champion-config-presets`: champion/baseline configs become distinguishable from search artifacts

## Impact
- Frontend: run buttons, config load state, saved-config labels
- Backend API: request/response metadata, saved config read/write paths
- Stored configs: metadata normalization and backward-compatible defaults
- Validation: baseline experiment `exp_20260307_051743747_77d8` must remain unchanged
