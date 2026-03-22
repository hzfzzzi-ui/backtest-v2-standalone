# Architecture Closure Gates

This document freezes the entry and pass conditions for the
`close-p0-p1-architecture-gaps` change.

## Scope

- Formal mainline anchor: `baseline_V10.1`
- Formal baseline contract:
  `backend/scripts/ops/v2_backend_refactor_baseline_contract.json`
- Locked baseline experiment:
  `exp_20260314_144548534_7db9`

## P0 Entry Rule

`P1` work must not start until every `P0` gate below is green.

## P0 Gates

1. Default test collection must succeed.
   Command: `pytest -q --collect-only`
2. Script and CLI governance gates must pass.
   Command:
   `pytest -q tests/unit/test_script_surface_governance.py tests/unit/test_cli_main.py`
3. Frontend owner boundary gates must pass.
   Command:
   `pytest -q tests/unit/test_frontend_owner_boundaries.py tests/unit/test_frontend_runtime_boundaries.py`
4. The baseline regression gate must pass without behavioral drift.
   Command: `python -m backend.cli audit --target baseline_regression`

## P0 Blocking Conditions

- `pytest -q --collect-only` fails or regresses back to import-time failure.
- Script surface governance or CLI surface governance tests fail.
- Frontend owner boundary or runtime boundary tests fail.
- The baseline regression gate reports `FAIL`.
- Any drift touches signal timing, execution timing, trade rules, universe
  definition, or canonical artifact protocol outside the contract's approved
  drift fields.

## Approved Drift Envelope

Only the contract-defined `allowed_drift_fields` may move during this change.
Everything else in the baseline comparison is blocking by default.

## Last Local Verification

- Date: `2026-03-17`
- `pytest -q --collect-only`: pass, `563/569 tests collected (6 deselected)`
- `pytest -q tests/unit/test_script_surface_governance.py tests/unit/test_cli_main.py tests/unit/test_architecture_closure_gates.py tests/unit/test_frontend_owner_boundaries.py tests/unit/test_frontend_runtime_boundaries.py tests/unit/test_architecture_docs.py tests/unit/test_api_compat_boundaries.py tests/unit/test_public_surface_convergence.py tests/unit/test_backtest_v2_protocol.py tests/unit/test_experiment_history_service.py tests/unit/test_experiment_query_service.py tests/integration/test_schema_and_artifacts.py`: pass, `99 passed`
- `pytest -q tests/unit/test_frontend_owner_boundaries.py tests/unit/test_frontend_runtime_boundaries.py`: pass, `25 passed`
- `python -m backend.cli audit --target baseline_regression`: pass, status `PASS`
- Residual warning: FastAPI `on_event` deprecation from `backend/main.py`; no functional drift observed in this change
