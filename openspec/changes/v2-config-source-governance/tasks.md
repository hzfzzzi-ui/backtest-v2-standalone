# Tasks: v2-config-source-governance

- [ ] Document runtime config source modes and precedence in API-facing artifacts
- [ ] Add normalized saved-config metadata contract with compatibility defaults
- [ ] Update config list/read endpoints to surface source metadata and resolved mode
- [ ] Update frontend run state to distinguish draft-run vs saved-config-run
- [ ] Show explicit UI warning/label when a loaded saved config is the execution source of truth
- [ ] Define champion/baseline config labeling rules separate from search artifacts
- [ ] Validate that baseline experiment `exp_20260307_051743747_77d8` produces unchanged `run_config.json`, `run_meta.json`, and `perf.json`
