# Tasks: v2-breakout-entry

- [x] Add `high_max20` feature computation in `features.py` (rolling max of high, window 20)
- [x] Create `breakout_signal_provider.py` implementing SignalProvider protocol
- [x] Implement `precompute()`: build high_max20, buy_breakout signal matrix, apply risk_on + trend masks
- [x] Implement `day_signals()`: generate buy orders for breakout signals, sell orders for exits
- [x] Implement fill hooks: `on_buy_fill()` and `on_sell_fill()` for position state tracking
- [x] Create `strategies/breakout_trend.py` with BreakoutTrendStrategy dataclass
- [x] Register `breakout_trend` in `registry.py` `build_strategy()`
- [x] Add engine dispatch for `breakout_trend` strategy in `portfolio_simulator_strict.py`
- [x] Wire through API (`_experiment_runner_api.py`) — config mapping for breakout params
