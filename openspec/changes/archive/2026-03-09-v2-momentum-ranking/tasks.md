# Tasks: v2-momentum-ranking

- [x] Add 120d return (`roc120`) computation in `_build_daily_multifactor_scores()`
- [x] Simplify scoring to 3-factor momentum: `mean(roc20, roc60, roc120)`
- [x] Add `momentum_top_pct: float = 0.10` parameter to config
- [x] Change selection logic from `topN` to `top_pct` in `build_rebalance_orders()`
- [x] Add `momentum_top_pct` to strategy dataclasses and registry builders
- [x] Wire through API (`_experiment_runner_api.py`)
