## Why

The watch timing AB showed that delaying mild High Chase D5 failures can improve some full-cycle metrics, but it did not repair the recent 2025-2026 drag. The current watch contract still immediately exits deep early MAE cases (`MAE <= -8%`). The next question is whether deep early MAE should be treated as a hard failure, watched like mild failures, or isolated from mild failures.

## What Changes

- Add a research-only combo AB study focused on D5 MAE depth handling.
- Compare same-window B0, all-failure immediate exit, deep-only immediate exit, mild-watch/deep-immediate, deep-only watch, and all-watch day10.
- Keep stock pool, ETF pool, ranking, entry rules, execution, costs, account allocator, and combo NAV assembly fixed.
- Report D5 immediate and watch exit counts separately.

## Non-Goals

- Do not promote a new baseline.
- Do not introduce industry/theme filters, strong-trend exemptions, or hand-picked symbols.
- Do not change signal timing, fill timing, stock universe, ETF universe, or account allocator policy.
- Do not use `precomputed_component_results` or any shortcut NAV.

## Impact

- Source:
  - `research/studies/cn_stock_etf/cn_stock_etf_high_chase_d5_deep_mae_combo_ab_v1.study.yaml`
  - `tests/unit/test_cn_stock_etf_stock_rule_combo_ab_study.py`
- Runtime artifacts:
  - new `outputs/experiments/*`
  - new `outputs/studies/cn_stock_etf/cn_stock_etf_high_chase_d5_deep_mae_combo_ab_v1/*`
  - new study journal round
