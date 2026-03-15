Script surface freeze rules.

Active direction:
- `python -m backend.cli`
- `backend/scripts/generated/`
- `backend/scripts/archive/`
- `backend/scripts/_internal_helper.py`

First migration batch:
- `v10/residual_structure_s1` -> `backend/scripts/generated/run_v10_residual_structure_s1.py`
- `v10/onset_ingress_minimal_s2` -> `backend/scripts/generated/run_v10_onset_ingress_minimal_s2.py`
- `v10/quality_then_residual_s3` -> `backend/scripts/generated/run_v10_quality_then_residual_s3.py`

Rules:
- Do not add new top-level large experiment scripts under `backend/scripts/`.
- Reusable command flows must move into `backend/cli/managed/` or `backend/cli/commands/`.
- Research matrices must move into `research/studies/*.study.yaml` and run through `backend.cli study_run`.
- When a study becomes a maintained entry point, generate `backend/scripts/generated/run_<study_id>.py` instead of adding a new top-level research script.
- Top-level script files that remain in place should be thin wrappers or frozen historical assets awaiting migration.
- Existing top-level `run_*_research.py` files are frozen historical references only; they must point to a study/archive target in `inventory.json` and must not receive new experiment logic.
