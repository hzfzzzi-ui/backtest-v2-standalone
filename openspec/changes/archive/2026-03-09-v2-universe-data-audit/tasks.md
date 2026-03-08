# Tasks: v2-universe-data-audit

- [x] Trace runtime data lineage for `ALL_A`, `HS300_ZZ500`, `CSI1000`, and any other supported universe modes
- [x] Trace `resolve_asof` semantics for each supported universe mode
- [x] Trace CSI import scripts and the tables/files they populate
- [x] Compare import-time assumptions with resolver-time database usage and index-code mappings
- [x] Audit the relationship between S1 validation and actual runtime universe resolution
- [x] Identify redundant or stale scripts, tables, cache files, source labels, and metadata assumptions
- [x] Produce a safe cleanup plan that preserves baseline symbol counts and results for `exp_20260307_051743747_77d8`
- [x] Validate any proposed removal against both baseline and script-driven search workflows
