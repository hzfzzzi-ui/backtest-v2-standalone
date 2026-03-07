# Tasks: v2-universe-data-audit

- [ ] Trace runtime data lineage for `ALL_A`, `HS300_ZZ500`, `CSI1000`, and any other supported universe modes
- [ ] Trace CSI import scripts and the tables/files they populate
- [ ] Compare import-time assumptions with resolver-time database usage
- [ ] Identify redundant or stale scripts, tables, cache files, and metadata assumptions
- [ ] Produce a safe cleanup plan that preserves baseline symbol counts and results for `exp_20260307_051743747_77d8`
- [ ] Validate any proposed removal against both baseline and script-driven search workflows
