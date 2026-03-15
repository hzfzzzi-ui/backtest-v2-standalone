# Execution Compat Audit

Date: 2026-03-15

## Facts

- `backend/core/engine_compat/foundation_shell.py` remains the active compat entry from runtime services into the execution bus.
- `backend/core/engine_vector/portfolio_simulator_strict.py` is already a thin shim over `strict_runtime_impl.py`.
- `backend/core/portfolio/portfolio_builder.py` is a frozen legacy compatibility layer.
- `backend/core/portfolio/legacy_loop.py` holds the legacy main loop.
- Shared execution/result types now live in `backend/core/portfolio/types.py`.

## Safe Externalization Completed

- `PortfolioOrder`
- `PortfolioBacktestResult`

These were moved out of `portfolio_builder.py` so newer code can depend on stable shared types without depending on the legacy carrier file.

## Remaining Active Compat Responsibilities

- `foundation_shell.py`
  - runtime plan coercion
  - delegation into the current stage-pipeline-backed execution path
- `portfolio_builder.py`
  - frozen compatibility exports and helper surface
- `legacy_loop.py`
  - old execution loop retained for compatibility only

## Guardrails

- No new strategy logic may enter:
  - `foundation_shell.py`
  - `portfolio_builder.py`
  - `legacy_loop.py`
  - `portfolio_simulator_strict.py`
- Any cleanup touching these files must re-check:
  - `baseline_V10_1`
  - `exp_20260314_144548534_7db9`

## Follow-up Targets

1. Keep pushing active responsibilities into stable modules outside legacy carriers.
2. Reduce `foundation_shell.py` to routing/coercion only.
3. Preserve 10.1 timing semantics while shrinking compat layers further.

