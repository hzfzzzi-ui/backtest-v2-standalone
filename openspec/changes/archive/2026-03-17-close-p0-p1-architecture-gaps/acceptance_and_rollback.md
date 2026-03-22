# P0/P1 Acceptance And Rollback

This note closes tasks `7.1` and `7.2` for the
`close-p0-p1-architecture-gaps` change.

## Final Acceptance

Date: `2026-03-17`

Required commands and latest local results:

1. `pytest -q --collect-only`
   Result: pass, `563/569 tests collected (6 deselected)`
2. `pytest -q tests/unit/test_script_surface_governance.py tests/unit/test_cli_main.py tests/unit/test_architecture_closure_gates.py tests/unit/test_frontend_owner_boundaries.py tests/unit/test_frontend_runtime_boundaries.py tests/unit/test_architecture_docs.py tests/unit/test_api_compat_boundaries.py tests/unit/test_public_surface_convergence.py tests/unit/test_backtest_v2_protocol.py tests/unit/test_experiment_history_service.py tests/unit/test_experiment_query_service.py tests/integration/test_schema_and_artifacts.py`
   Result: pass, `99 passed`
3. `python -m backend.cli audit --target baseline_regression`
   Result: pass, status `PASS`, blocking mismatches `0`, warning mismatches `0`

Acceptance summary:

- `P0` gates are green: default test collect, script and CLI governance,
  frontend owner boundary, baseline regression audit.
- `P1` gates are green: API boundary regression, protocol regression,
  architecture and schema documentation checks.
- No behavioral drift was reported against the locked
  `baseline_V10.1` baseline snapshot.

Known residual warning:

- FastAPI emits an `on_event` deprecation warning from `backend/main.py`.
  This change does not address lifecycle migration because it is outside the
  approved `P0/P1` closure scope and does not affect baseline behavior.

## Stop Conditions

Do not continue apply or archive work for this change if any of the following
becomes true:

- `pytest -q --collect-only` regresses back to import-time failure.
- Script, CLI, frontend owner, API boundary, protocol, or schema tests fail.
- `python -m backend.cli audit --target baseline_regression` reports `FAIL`.
- Any drift touches signal timing, execution timing, universe definition,
  canonical artifact protocol, or other fields outside the contract-defined
  allowed drift envelope.

## Rollback

Rollback must happen by wave, not by ad hoc file picking.

### P0 rollback

Trigger:

- Default collect fails again.
- Script or CLI governance fails.
- Frontend owner boundary fails.
- Baseline regression audit is no longer `PASS`.

Actions:

1. Revert the CLI/script surface closure as one wave:
   `backend/cli`, `backend/core/cli`, `backend/scripts/generated`,
   `backend/scripts/*CSI1000*`, related governance tests, and the CLI README.
2. Revert the frontend owner closure as one wave:
   `docs/frontend_owner_map.md`, owner boundary tests, and the owner markers in
   legacy shell files and results workbench entry files.
3. Rerun the four `P0` gate commands before any further change is applied.

### P1 rollback

Trigger:

- Public history/list/compare semantics drift.
- API boundary or protocol tests fail after follow-up changes.
- Architecture/schema/example docs no longer match repository reality.

Actions:

1. Revert the service extraction wave as one unit:
   `backend/core/services/experiment_history_service.py`,
   `backend/api/backtest_v2/history_impl.py`,
   `backend/core/services/experiment_query_service.py`,
   `backend/core/services/experiment_compare_service.py`,
   and related regression tests.
2. Revert the documentation wave as one unit:
   `ARCHITECTURE.md`, schema docs, runbook, examples, guardrail sync, and
   architecture-doc tests.
3. Rerun the final acceptance command set before resuming work.

## Next Apply Entry

This change is ready for final verification/archive flow.

Recommended next steps:

1. Run OpenSpec verification against `close-p0-p1-architecture-gaps`.
2. If verification is clean, archive the change and sync any approved specs.
3. Start the next change only after the `P0/P1` closure status is preserved.
