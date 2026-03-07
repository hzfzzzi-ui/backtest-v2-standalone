# V2 Stage 7: Portfolio Sizing (Inverse-Vol + Position Band)

## What
Add inverse-volatility position sizing and a dynamic position count band (10-15 stocks). This is V2 Stage 7 (Portfolio Construction).

## Why
Equal weight gives the same capital to high-vol and low-vol stocks, creating unequal risk contribution. Inverse-vol sizing ensures each position contributes roughly equal risk. A 10-15 position band ensures minimum diversification (floor 10) while capping management complexity (ceiling 15).

## Current State
`max_positions` hard cap with equal weight (`nav / max_positions`). ATR-based sizing path exists (`risk_amount > 0` branch in `build_rebalance_orders()`) but is rarely activated. No `min_positions` enforcement.

## Scope
- Add `weight_mode: str = "equal"` config option (values: "equal", "inverse_vol")
- For inverse_vol: weight_i = (1/sigma_i) / sum(1/sigma_j) where sigma = ATR14/close
- Add `min_positions: int = 10` enforcement in `build_rebalance_orders()`
- Existing `max_positions` acts as ceiling (default 15)
- Wire through config/API/frontend (Portfolio tab)
