## Why

The all-candidate D7 post-entry path shadow expanded the sample and confirmed
that D7 confirmation failure concentrates bad candidates. The remaining
question is not whether the D7 state is meaningful, but what runtime action is
least harmful: keep the current half-exit, sell more, sell fully, or delay the
confirmation.

## What Changes

- Add a research-only stock-leg AB study for D7 post-entry action.
- Compare current 50% immediate half-exit against 75%, 100%, day5 delayed
  half-exit, and day10 watch half-exit.
- Keep universe, ranking, entry rules, execution timing, costs, and sizing
  fixed.
- Use the current `baseline_V10_1` runtime config as the source of truth.

## Non-Goals

- Do not promote a baseline.
- Do not introduce ETF, combo, industry, theme, quality, or replacement-buy
  behavior.
- Do not use shadow rows as executable input.
- Do not change the D7 MFE/MAE trigger definition in the same study.

## Impact

- Source:
  - `research/studies/cn_stock_etf/cn_stock_etf_d7_post_entry_action_stock_ab_v1.study.yaml`
  - `tests/unit/test_study_runner.py`
- Runtime artifacts:
  - new `outputs/experiments/*`
  - new study conclusion registry rows
