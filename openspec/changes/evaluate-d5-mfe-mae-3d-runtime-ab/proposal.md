## Why

D5 shadow showed a clear post-entry path difference between profit TOP30 and loss TOP30: losing trades often had weak early MFE and expanding MAE. But the shadow result only simulated an isolated half-sell. It did not rebuild orders, cash, fills, positions, NAV, or later re-entry/reallocation behavior.

The user correctly pointed out that early drawdown followed by later recovery should be judged by a real runtime AB, not by a one-sided hindsight shadow. This change tests the 3-day D5 version as a true runtime experiment.

## What Changes

- Add a research-only runtime exit switch for D5 post-entry confirmation failure.
- Add a declarative study `cn_stock_etf/cn_stock_etf_d5_mfe_mae_3d_runtime_ab_v1`.
- Keep the V3 stock runtime source, stock universe, ranking, entry rules, costs, execution timing, ETF leg, and baseline comparison window unchanged.
- Enable only the D5 3-day rule in the AB variant:
  - evaluate at 3 trading bars after entry
  - trigger when close-path MFE is below `+2%`
  - and close-path MAE is at or below `-5%`
  - sell `50%` of the current position
- Run the comparison through normal runtime so NAV and account state come from one execution chain.

## Impact

- New OpenSpec change artifacts under `openspec/changes/evaluate-d5-mfe-mae-3d-runtime-ab/`.
- New optional strategy/provider parameters for D5 confirmation failure, defaulting off.
- New study YAML under `research/studies/cn_stock_etf/`.
- Focused unit tests for strategy mapping, signal generation, and study plan isolation.
- Runtime outputs are written under `outputs/experiments` and study/conclusion outputs through the existing study runner.
