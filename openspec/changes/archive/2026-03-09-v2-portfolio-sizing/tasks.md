# Tasks: v2-portfolio-sizing

- [x] Add `weight_mode: str = "equal"` and `min_positions: int = 10` to config
- [x] Implement inverse-vol weight computation in `build_rebalance_orders()`
- [x] Use `sigma = ATR14 / close` for normalized volatility per stock
- [x] Apply `min_positions` floor to sizing denominator
- [x] Pass ATR14 data to `build_rebalance_orders()` (from feature matrices)
- [x] Add `weight_mode` and `min_positions` to SizingConfig (portfolio-level, not strategy dataclasses)
- [x] Wire through API (`_experiment_runner_api.py`) and config loader
