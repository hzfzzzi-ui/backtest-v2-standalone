# Tasks: v2-market-regime-ma60

- [x] Change `regime_ma` default from 120 to 60 in `portfolio_simulator_strict.py`
- [x] Change `regime_ma` default from 120 to 60 in `sma_signal_provider.py`
- [x] Add `regime_ma: int = 60` attribute to `SMACrossStrategy` and `EMACrossStrategy`
- [x] Pass `regime_ma` through `build_strategy()` in `registry.py` for sma_cross and ema_cross
- [x] Ensure `regime_ma` is set in `strategy.params` via `_experiment_runner_api.py`
- [x] Verify RegimeRouter path already uses default 60 (no change needed, just confirm)
