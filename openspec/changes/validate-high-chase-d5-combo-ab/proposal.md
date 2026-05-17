## Why

The stock-leg High Chase + D5 runtime AB showed the cleanest candidate is `HC_D5_IMMEDIATE_HALF_EXIT`, but that result is not enough for a stock+ETF combo decision. The combo baseline V3 uses the unified runtime to run stock and ETF sleeves separately, then builds a shared NAV through the account allocator. The candidate must be validated through that same combo runtime, not by reusing stock-only NAV or precomputed component results.

## What Changes

- Add a research-only combo AB study for `HC_D5_IMMEDIATE_HALF_EXIT`.
- Add a combo study runner that starts from `CN_STOCK_ETF_COMBO_BASELINE_V3`, fixes the ETF sleeve/runtime, and only patches the stock component runtime D5 parameters.
- Run B0 combo replay and candidate combo through the unified runtime for:
  - 2016-2026 main window
  - 2012-2017 hard gate
  - 2012-2026 full audit
- Record combo exp ids plus component stock/ETF exp ids, metrics, D5 trigger counts, and study journal evidence.

## Non-Goals

- Do not promote a new combo baseline in this change.
- Do not change ETF pool, ETF defense policy, account allocator, weights, stock pool, ranking, entry timing, fill timing, or cost model.
- Do not use `precomputed_component_results` or any shortcut NAV.
- Do not test watch or delayed confirmation in this combo validation round.

## Impact

- Source:
  - `backend/research/cn_stock_etf_stock_rule_combo_ab_study.py`
  - `backend/research/study_runner.py`
  - `research/studies/cn_stock_etf/*.study.yaml`
  - `tests/unit/*`
- Artifacts:
  - new `outputs/experiments/*`
  - new `outputs/studies/cn_stock_etf/*`
  - new `research/study_journal/rounds/*`
