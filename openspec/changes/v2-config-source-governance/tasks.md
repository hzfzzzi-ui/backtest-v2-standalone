# Tasks: v2-config-source-governance

- [x] Document the distinction between content identity (`config_hash`) and saved-record identity (`config_id`)
- [x] Add a normalized saved-config metadata contract with compatibility defaults
- [x] Define legacy compatibility rules for existing hash-derived `cfg_<hash12>` records
- [x] Update config save/list/read endpoints to surface source metadata, content hash, and resolved mode
- [x] Update frontend run state to distinguish `draft-only`, `loaded-clean`, and `loaded-dirty`
- [x] Ensure `run_async` and `execution_preview` share the same config resolution and conflict-reporting policy
- [x] Show explicit UI warning/label when a saved config is the execution source of truth
- [x] Define built-in config injection and labeling rules separate from manual/search artifacts
- [x] Validate that baseline experiment `exp_20260307_051743747_77d8` produces unchanged `run_config.json` and `perf.json`, with `run_meta.json` remaining semantically equivalent except generated fields such as `exp_id`, `created_at`, and `report_consistency`
