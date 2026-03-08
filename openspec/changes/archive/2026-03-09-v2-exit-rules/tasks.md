# Tasks: v2-exit-rules

- [x] Add `low_min10` feature in `features.py`: rolling min of low, window 10
- [x] Reuse or add `sma20` feature in `features.py` (may exist from v2-stock-trend-filter)
- [x] Add `TREND_EXIT_MA20` exit check in engine sell loop: `cclose < sma20[i, col]`
- [x] Add `TREND_EXIT_LOW10` exit check in engine sell loop: `cclose < low_min10[i, col]`
- [x] Add exit counters: `exit_ma20_count`, `exit_low10_count` to metrics dict
- [x] Add params to strategy dataclasses: `enable_ma20_exit`, `enable_low10_exit`, periods
- [x] Pass params through `registry.py` builders
- [x] Wire through API (`_experiment_runner_api.py`)
