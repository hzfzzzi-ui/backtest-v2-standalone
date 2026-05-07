# Implementation Notes

## What changed
- Added a research-only moneyflow factor catalog for `monthly_divergence_rate`.
- Added moneyflow factor snapshots and factor score snapshots.
- Added `moneyflow_factor_surface` study runner mode and a demo study definition.
- Did not connect moneyflow factors into runtime ranking, gating, or budgeting.

## Impacted modules
- `backend/research/moneyflow_factor_catalog.py`
- `backend/research/moneyflow_factor_snapshots.py`
- `backend/research/moneyflow_factor_study.py`
- `backend/research/study_runner.py`
- `research/studies/factors/moneyflow_factor_surface_demo.study.yaml`
- related unit tests

## Validation
- Focused tests passed:
  - `tests/unit/test_moneyflow_factor_catalog.py`
  - `tests/unit/test_moneyflow_factor_study.py`
  - `tests/unit/test_study_runner.py`
- Real sample passed:
  - `python -m backend.cli study_run factors/moneyflow_factor_surface_demo --window 2326 --variant B0_EQUAL`

## Risks
- This surface is `RESEARCH_ONLY`; it is not evidence that moneyflow is already in runtime.
- First-wave factor definition is intentionally narrow and may still change before any runtime promotion.

## Rollback
- Revert the new research files, demo study YAML, and related tests, then restore the tasks file.
