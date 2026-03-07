# Design: Config Source Governance

## Context
Backtest V2 currently has two configuration production chains:
- manual workbench usage for user-driven baseline runs
- Claude/script-driven matrix search that writes many saved configs

Both chains land in `outputs/configs/` and both can be referenced by the same frontend load/run flow. The main confusion point is that the UI draft is not always the executed source of truth.

## Goals / Non-Goals
**Goals:**
- make runtime config origin explicit
- prevent hidden `config_id` overrides
- classify all saved configs by source and owner
- preserve compatibility with existing saved configs and experiments

**Non-Goals:**
- redesign the experiment engine
- migrate old experiment results
- delete historical configs in this change

## Decisions
### D1: Config source modes
All run requests are interpreted as one of two explicit modes:
- `draft_run`: execute the current UI draft only
- `saved_config_run`: execute a saved `config_id`

A request may still carry both fields for compatibility, but the API must emit resolved mode metadata and the frontend must clearly indicate which mode is active.

### D2: Saved config metadata contract
Each saved config should expose normalized metadata:
- `source_type`: `baseline | search | template | derived`
- `owner`: `manual | claude | script | builtin`
- `locked`: boolean
- `baseline_of`: nullable experiment id
- `display_name`: existing `name` remains supported

Older configs without these fields are mapped through compatibility defaults during read.

### D3: UI mode separation
Frontend should distinguish:
- run current draft
- run loaded saved config

If a saved config is loaded, the page must show that edits on screen are not the executed truth unless the user switches back to draft mode or explicitly resaves.

### D4: API response truth surface
Experiment metadata should expose:
- `resolved_config_mode`
- `resolved_config_id`
- `config_conflict_policy`
- normalized metadata for the resolved config source

This allows report/history pages to explain whether an experiment came from baseline, search, template, or derived source.

### D5: Backward compatibility
Existing files in `outputs/configs/` remain readable. The normalization layer supplies missing metadata defaults without changing strategy semantics.

## Alternatives Considered
1. Keep `config_id` silently overriding the draft and only add docs. Rejected because the current failure mode is operational, not documentation-only.
2. Remove `config_id` entirely from frontend payloads. Rejected because saved config replay is still a valid workflow.
3. Split search configs into a different directory immediately. Deferred because metadata governance is the lower-risk first step.
