## Why

The wide candidate shadow audit found two weak candidate archetypes across all
surfaced stock signals:

- hot/crowded candidates had poor forward returns.
- high-volatility chase candidates also had poor forward returns.

The prior hard filters were too brittle. The next step is to test whether these
archetypes should only be deprioritized when candidates compete for cash or
slots, using the normal stock-leg runtime ledger.

## What Changes

- Add a research-only optional soft deprioritization to stock candidate
  `final_score`.
- The first AB candidate lowers score, rather than blocking signals, when a
  buy candidate is in:
  - the top same-day candidate rank bucket for short-term heat and turnover
    crowding.
  - the top same-day candidate rank bucket for realized volatility.
- Keep stock universe, PIT membership, entry rules, exits, sizing, execution
  timing, costs, and account/NAV calculation unchanged.
- Run the first validation on the 2016-2026 stock main window.

## Non-Goals

- Do not promote a baseline.
- Do not change ETF or combo behavior.
- Do not introduce industry/theme filters.
- Do not hard-veto candidates.
- Do not change signal date, fill date, exits, or portfolio construction.
- Do not use shadow rows as executable input.

## Impact

- Source:
  - `backend/core/strategies/breakout_trend.py`
  - `backend/core/strategies/registry.py`
  - `backend/core/engine_vector/breakout_provider_models.py`
  - `backend/core/engine_vector/breakout_provider_precompute.py`
  - `backend/core/engine_vector/breakout_provider_day_signals.py`
  - `tests/unit/test_signal_provider_exits.py`
  - `tests/unit/test_breakout_signal_provider.py`
  - `tests/unit/test_study_runner.py`
- Runtime artifacts:
  - new `outputs/experiments/*`
  - AB summary under `outputs/analysis/`
