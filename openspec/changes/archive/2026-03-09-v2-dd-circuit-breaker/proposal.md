# V2 Stage 8: Drawdown Circuit Breaker

## What
When portfolio drawdown exceeds 10%, reduce position exposure. This is V2 Stage 8 (Risk Management), the portfolio-level component.

## Why
ATR stop handles single-stock risk. But systemic market drops can cause multiple stops simultaneously. A portfolio-level circuit breaker reduces new entries and/or forces partial liquidation when drawdown is severe, protecting against cascading losses.

## Current State
`RiskBudgetConfig` defines `dd_scale_10=0.8`, `dd_scale_15=0.6`, `dd_fixed_20=0.03`, `dd_stop_pct=0.25` but these are never read in the engine loop. Drawdown is computed daily (`nav / peak_nav - 1`) and stored in `daily_rows` but triggers no action.

## Scope
- Read `RiskBudgetConfig` in engine daily loop
- When DD > 10%: scale `max_positions` by `dd_scale_10` (0.8 → allow 80% of normal positions)
- When DD > 15%: scale by `dd_scale_15` (0.6)
- When DD > 20%: use `dd_fixed_20` (fixed 3% risk per trade)
- When DD > `dd_stop_pct` (25%): halt all new entries
- Add DD state tracking and recovery logic
