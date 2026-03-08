# Tasks: v2-shrink-pass

- [x] Build a shrink inventory that classifies current additive surfaces as `steady-state`, `transitional`, `deprecated-delete-candidate`, or `ops-only`
- [x] Decide which new helpers stay separate and which should be merged into owning modules (`runtime_surface.py`, `lineage.py`, and similar transitional layers)
- [x] Remove or fold one transitional helper at a time, rerunning the March 7 baseline after each production-surface change
- [x] Delete deprecated paths that no longer have a justified runtime or research-only consumer
- [x] Move pure operator/audit scripts and docs into an explicit ops-oriented location without breaking their usability
- [x] Remove compatibility branches whose legacy behavior is no longer part of the supported contract
- [x] Reconcile this shrink pass with `dead-code-removal` so deletions are tracked coherently instead of ad hoc
- [x] Produce a before/after shrink summary including net line-count reduction and any intentionally retained surfaces
