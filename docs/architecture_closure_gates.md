# Architecture Closure Gates

This document defines the current P0 closure gates for the architecture
boundary and baseline regression surfaces.

## Scope

- Formal mainline anchor: `baseline_V10.1`
- Formal stock+ETF anchor: `CN_STOCK_ETF_FORMAL_V1`
- Foundation baseline regression contract:
  `backend/scripts/ops/v2_backend_refactor_baseline_contract.json`
- Active foundation regression experiment:
  `exp_20260426_005716047_8650`
- Historical missing foundation regression experiment:
  `exp_20260314_144548534_7db9`
- Historical missing `baseline_V10.1` rebase experiment:
  `exp_20260328_220801073_478b`

## P0 Entry Rule

`P1` work must not start until every `P0` gate below is green.

## P0 Gates

1. Default test collection must succeed.
   Command: `pytest -q --collect-only`
2. Script and CLI governance gates must pass.
   Command:
   `pytest -q tests/unit/test_script_surface_governance.py tests/unit/test_cli_main.py`
3. Current frontend runtime boundary gates must pass.
   Command:
   `pytest -q tests/unit/test_frontend_runtime_boundaries.py`
4. The baseline regression gate must pass against the active re-anchored
   formal artifact.
   Command: `python -m backend.cli audit --target baseline_regression`

## P0 Blocking Conditions

- `pytest -q --collect-only` fails or regresses back to import-time failure.
- Script surface governance or CLI surface governance tests fail.
- Frontend runtime boundary tests fail.
- The baseline regression gate reports unexplained behavioral drift.
- Any drift touches signal timing, execution timing, trade rules, universe
  definition, or canonical artifact protocol outside the contract's approved
  drift fields.

## Approved Drift Envelope

Only the contract-defined `allowed_drift_fields` may move during a foundation
baseline regression change. Everything else in the baseline comparison is
blocking by default.

## Current Notes

- `tests/unit/test_frontend_owner_boundaries.py` was retired with the desktop
  shell cutover. Runtime ownership is now guarded by
  `tests/unit/test_frontend_runtime_boundaries.py`.
- `outputs/` remains an artifact path, not a source path. Missing locked
  baseline artifacts must be restored or explicitly re-anchored; ledger-only
  metrics are not enough for a green P0.
- The former locked foundation artifact `exp_20260314_144548534_7db9`
  and the `baseline_V10.1` rebase linked artifact
  `exp_20260328_220801073_478b` are recorded as historical missing anchors.
  They must not be recreated from ledger-only metrics.
