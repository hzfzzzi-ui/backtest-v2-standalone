# Tasks: v2-dd-circuit-breaker

- [x] Extract `RiskBudgetConfig` fields in engine init (dd_scale_10, dd_scale_15, dd_stop_pct, etc.)
- [x] Compute `effective_max_positions` based on current drawdown in daily loop
- [x] Replace `max_positions` with `effective_max_positions` in buy slot calculation
- [x] Add `effective_max_positions` and `dd_state` to daily_rows
- [x] Add `enable_dd_breaker` flag to strategy params / config
- [x] Wire through API (`_experiment_runner_api.py`)
