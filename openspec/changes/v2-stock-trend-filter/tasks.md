# Tasks: v2-stock-trend-filter

- [x] Add `sma20` and `sma60` to `FeatureMatrices` in `features.py` (rolling mean of close)
- [x] Add `v2_trend_ok` signal matrix in `signal_matrix.py`: `(close > sma60) & (sma20 > sma60)`
- [x] Add `enable_v2_trend_filter` param extraction in `portfolio_simulator_strict.py`
- [x] Apply `v2_trend_ok` mask to buy candidates in engine buy loop
- [x] Add params to strategy dataclasses (`SMACrossStrategy`, `EMACrossStrategy`)
- [x] Pass params through `registry.py` builders
- [x] Wire `enable_v2_trend_filter` + MA periods through API (`_experiment_runner_api.py`)
