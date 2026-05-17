## Why

The trend-quality shadow audit found a narrow loss-tail pattern: entries with
very high 5-day pre-entry return and very low 60-day trend smoothness had no
profit TOP30 hits and several loss TOP30 hits. The next step is to test whether
this shadow pattern survives as an executable stock-leg AB, using the normal
runtime ledger.

## What Changes

- Add a research-only optional entry veto for bad breakout quality.
- The first AB candidate blocks breakout entries only when both daily
  cross-sectional conditions are true:
  - pre-entry 5-day return ranks in the hottest 20% of that day's breakout
    candidates.
  - 60-day trend R2 ranks in the weakest 20% of that day's breakout candidates.
- Keep stock universe, PIT membership, ranking, exits, sizing, execution timing,
  costs, and account/NAV calculation unchanged.
- Run the first validation on the 2016-2026 main stock window only.

## Non-Goals

- Do not promote a baseline.
- Do not change ETF or combo behavior.
- Do not introduce industry/theme filters.
- Do not use fixed absolute cutoffs copied from the shadow sample.
- Do not change signal date, fill date, exits, or portfolio construction.
- Do not use shadow rows as executable input.

## Impact

- Source:
  - `backend/core/strategies/breakout_trend.py`
  - `backend/core/strategies/registry.py`
  - `backend/core/engine_vector/breakout_provider_models.py`
  - `backend/core/engine_vector/breakout_provider_precompute.py`
  - `backend/core/engine_vector/breakout_signal_provider.py`
  - `backend/core/engine_vector/breakout_support.py`
  - `tests/unit/test_signal_provider_exits.py`
- Runtime artifacts:
  - new `outputs/experiments/*`
  - AB summary under `outputs/analysis/`
