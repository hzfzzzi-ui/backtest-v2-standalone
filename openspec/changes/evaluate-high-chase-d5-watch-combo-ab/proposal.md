## Why

The immediate High Chase D5 combo AB improved the full-cycle combo result only modestly, while recent diagnostics showed that the day3 failure shape is a useful weak signal but day3 immediate half-exit can be too early. The next research question is whether using day3 D5 as a watch signal, then exiting only unresolved cases at day5 or day10, preserves drawdown prevention while reducing right-tail opportunity cost.

## What Changes

- Extend the existing research-only combo stock-rule AB study with:
  - `HC_D5_WATCH_DAY5_COMBO`
  - `HC_D5_WATCH_DAY10_COMBO`
- Keep `B0_COMBO_V3_REPLAY` and `HC_D5_IMMEDIATE_COMBO` as same-window controls.
- Compare every candidate against the same-window B0 replay in the unified stock+ETF runtime.
- Report immediate D5 exits and watch D5 exits separately.

## Non-Goals

- Do not promote a new combo baseline.
- Do not change stock pool, ETF pool, ranking, entry rules, fills, cost model, account allocator, or combo NAV assembly.
- Do not add industry/theme protection, strong-trend exemptions, or sample-fitted filters in this round.
- Do not use `precomputed_component_results` or any shortcut NAV.

## Impact

- Source:
  - `backend/research/cn_stock_etf_stock_rule_combo_ab_study.py`
  - `research/studies/cn_stock_etf/cn_stock_etf_high_chase_d5_combo_ab_v1.study.yaml`
  - `tests/unit/test_cn_stock_etf_stock_rule_combo_ab_study.py`
- Artifacts:
  - new `outputs/experiments/*`
  - updated study matrix under `outputs/studies/cn_stock_etf/cn_stock_etf_high_chase_d5_combo_ab_v1`
  - updated study journal round
