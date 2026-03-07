# Spec: Portfolio Sizing

## Requirement
Support inverse-volatility position sizing. Enforce 10-15 position band.

## Weight Modes

### Equal Weight (default)
```
weight_i = 1 / max_positions
target_amount_i = nav * weight_i
```

### Inverse Volatility
```
sigma_i = ATR14_i / close_i       (normalized vol)
weight_i = (1/sigma_i) / sum(1/sigma_j)
target_amount_i = nav * weight_i
```

Low-vol stocks get larger positions. High-vol stocks get smaller positions.

## Position Band
| Param | Default | Range |
|-------|---------|-------|
| `min_positions` | 10 | 3-20 |
| `max_positions` | 15 | 5-30 |
| `weight_mode` | "equal" | "equal" / "inverse_vol" |

- `min_positions` affects sizing denominator (prevents over-concentration)
- `max_positions` caps total positions (existing behavior)
- Weights applied to new entries only — no rebalancing of existing positions

## Edge Cases
- ATR14 = 0 or NaN: use equal weight for that stock
- Fewer candidates than min_positions: size as if min_positions stocks (smaller per-stock allocation)
- More candidates than max_positions: select top-ranked, then apply weights
