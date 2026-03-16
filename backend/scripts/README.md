Script surface rules.

Active surfaces:
- `python -m backend.cli`
- `backend/scripts/generated/`

Current policy:
- Top-level `backend/scripts/` no longer hosts study-definition or archived-study entry points.
- Active research entry points must be `research/studies/*.study.yaml` plus `backend/scripts/generated/run_<study_id>.py`.
- Historical research scripts that were only kept for migration have been removed from the top-level surface.
- Reusable command flows belong in `backend/cli/managed/` or `backend/cli/commands/`.
- New research work must not add large top-level scripts under `backend/scripts/`.
- `backend/scripts/archive/` is a documentation-only historical marker and no longer keeps executable entrypoints.

Migration batches retained in generated form:
- `v10/residual_structure_s1`
- `v10/onset_ingress_minimal_s2`
- `v10/quality_then_residual_s3`
- `v10/regime_source_minimal_r1`
- `v10/rotation_replace_minimal_r1`
- `v10/upstream_pullback_minimal_p1`
- `v10/conditional_tiebreak_s4`
- `v10/strict_industry_relative_s5`
- `v10/industry_excess_median_s6`
- `v10/industry_second_stage_s7`
- `v10/industry_second_stage_tiebreak_s8`
- `v10/leadership_route_l1`
- `v10/state_conditional_residual_r2`
- `v10/state_conditional_window_r3`
