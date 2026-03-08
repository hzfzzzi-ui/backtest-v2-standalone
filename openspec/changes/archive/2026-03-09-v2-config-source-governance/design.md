# Design: Config Source Governance

## Context
Backtest V2 currently has two configuration production chains:
- manual workbench usage for user-driven baseline runs
- Claude/script-driven matrix search that writes many saved configs

Both chains land in `outputs/configs/` and both can be referenced by the same frontend load/run flow. The main confusion point is not just metadata; it is that the current system conflates content identity, saved-record identity, and runtime execution truth.

Two concrete issues shape this change:
- `config_id` is currently derived from the hash of `config_json`, so the same content saved by different actors can overwrite provenance metadata
- both `run_async` and `execution_preview` resolve `config_id` ahead of the current draft, while the UI does not make that execution mode explicit

## Goals / Non-Goals
**Goals:**
- make runtime config origin explicit
- prevent hidden `config_id` overrides
- separate content identity from saved-record identity
- classify all saved configs by source and owner
- preserve compatibility with existing saved configs and experiments

**Non-Goals:**
- redesign the experiment engine
- migrate old experiment results
- delete historical configs in this change

## Decisions
### D1: Identity model
The system distinguishes two identities:
- `config_hash`: deterministic hash of canonical `config_json`; represents content identity
- `config_id`: saved-record identity; represents a concrete saved artifact and its provenance metadata

Legacy hash-derived ids such as `cfg_<hash12>` remain readable. Read/list endpoints must expose both the saved-record identity and the underlying content hash so collisions become observable instead of implicit.

### D2: Saved config metadata contract
Each saved config should expose normalized metadata:
- `source_type`: `baseline | search | template | derived`
- `owner`: `manual | claude | script | builtin`
- `locked`: boolean
- `baseline_of`: nullable experiment id
- `display_name`: existing `name` remains supported
- `legacy_config_id`: nullable legacy hash-derived id when applicable

Older configs without these fields are mapped through compatibility defaults during read.

### D3: Runtime modes and dirty-state semantics
All run and preview requests are interpreted as one of two explicit modes:
- `draft_run`: execute the current UI draft only
- `saved_config_run`: execute a saved `config_id`

Frontend state distinguishes:
- `draft-only`
- `loaded-clean`
- `loaded-dirty`

When the user edits a loaded config, the page enters `loaded-dirty`. In that state, the UI must no longer silently imply that the saved config is still the source of truth.

### D4: Run/preview parity
`run_async` and `execution_preview` must share the same config resolution policy, the same resolved-mode metadata, and the same conflict reporting. Preview is part of the runtime contract, not a secondary path.

### D5: Built-in injection policy
Built-in configs are classified as `source_type=template` and `owner=builtin`. Built-in injection must not overwrite the provenance metadata of manual baseline saves or matrix-search saves that happen to share the same content hash.

### D6: API response truth surface
Experiment and preview metadata should expose:
- `resolved_config_mode`
- `resolved_config_id`
- `resolved_config_hash`
- `config_conflict_policy`
- normalized metadata for the resolved config source

This allows report/history pages to explain whether an experiment came from baseline, search, template, or derived source.

### D7: Backward compatibility
Existing files in `outputs/configs/` remain readable. The normalization layer supplies missing metadata defaults without changing strategy semantics. Legacy `cfg_<hash12>` artifacts are treated as compatibility records rather than rewritten immediately.

## Alternatives Considered
1. Keep `config_id` silently overriding the draft and only add docs. Rejected because the current failure mode is operational, not documentation-only.
2. Keep content-hash-derived `config_id` and only add `source_type`. Rejected because provenance collisions would remain unsolved.
3. Remove `config_id` entirely from frontend payloads. Rejected because saved config replay is still a valid workflow.
4. Split search configs into a different directory immediately. Deferred because identity/provenance governance is the lower-risk first step.
