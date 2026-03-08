# Design: Portfolio Sizing (Inverse-Vol + Position Band)

## Approach

Add inverse-volatility weighting as an alternative to equal weight. Add minimum position floor.

## Changes

### 1. Weight computation — `portfolio_builder.py`

In `build_rebalance_orders()`, after selecting buy candidates, compute weights:

```python
if weight_mode == "inverse_vol":
    # sigma = ATR14 / close (normalized volatility)
    sigmas = {sym: atr14[sym] / close[sym] for sym in buy_candidates}
    inv_sigmas = {sym: 1.0 / max(s, 1e-8) for sym, s in sigmas.items()}
    total = sum(inv_sigmas.values())
    weights = {sym: v / total for sym, v in inv_sigmas.items()}
    # target_amount per stock = nav * weight
    for sym in buy_candidates:
        target_amount = nav_for_buying * weights[sym]
else:
    # equal weight (existing behavior)
    target_amount = nav_for_buying / max_positions
```

### 2. Position band — `portfolio_builder.py`

Add `min_positions` enforcement:
```python
# If we have fewer buy candidates than min_positions, still use min_positions for sizing
effective_positions = max(min_positions, min(len(buy_candidates), max_positions))
```

This prevents over-concentration when few candidates pass the filters.

### 3. Config

- `weight_mode: str = "equal"` — values: "equal", "inverse_vol"
- `min_positions: int = 10`
- `max_positions: int = 15` (existing, change default)

### 4. ATR data availability

ATR14 is already computed in `features.py`. Need to pass it to `build_rebalance_orders()` or extract from feature matrices.

### 5. Rebalance consideration

Inverse-vol weights change daily as volatility changes. We do NOT rebalance existing positions — only apply weights to new entries. This keeps turnover low.
