# Spec: Momentum Ranking

## Requirement
Rank eligible stocks by composite momentum score (20d + 60d + 120d returns). Select top 10%.

## Behavior
- Score = average of (20d_return, 60d_return, 120d_return)
- If any factor has insufficient data, use available factors only
- Top 10% of eligible stocks pass the ranking gate
- If top 10% yields fewer than `min_positions`, allow `min_positions` through
- If top 10% yields more than `max_positions`, cap at `max_positions`

## Parameters
| Param | Default | Range |
|-------|---------|-------|
| `momentum_top_pct` | 0.10 | 0.01-1.0 |
| `momentum_windows` | [20, 60, 120] | list of ints |

## Scoring Detail
```
roc_N = close[today] / close[today - N] - 1
score = mean(roc_20, roc_60, roc_120)
```

Uses adjusted close (后复权) for return computation to handle ex-rights correctly.
