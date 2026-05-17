## Why

The High Chase + D5 candidate has real loss-tail explanatory power, but the
runtime AB history shows that broad or overly early D5 action can create churn
and hurt recent performance. The next question is whether the rule should treat
mild early MAE and deep early MAE differently in the stock leg before any combo
or baseline discussion.

## What Changes

- Add a research-only stock-leg AB study for High Chase + D5 MAE-depth handling.
- Compare same-window B0, incumbent immediate half-exit, deep-only immediate
  half-exit, mild-watch/deep-immediate, and all-watch/deep-review variants.
- Keep stock universe, ranking, entry rules, execution timing, costs, sizing,
  and baseline defaults fixed.
- Use the normal stock runtime ledger; do not consume shadow rows as executable
  input.

## Non-Goals

- Do not promote a new baseline.
- Do not mix ETF or combo NAV into this stock-leg decision.
- Do not introduce industry/theme filters, strong-trend exemptions, or
  hand-picked symbols.
- Do not change signal timing, fill timing, stock universe, or account
  allocator policy.

## Impact

- Source:
  - `research/studies/cn_stock_etf/cn_stock_etf_high_chase_d5_deep_mae_stock_ab_v1.study.yaml`
  - `tests/unit/test_study_runner.py`
- Runtime artifacts:
  - new `outputs/experiments/*`
  - new study conclusion registry entries
