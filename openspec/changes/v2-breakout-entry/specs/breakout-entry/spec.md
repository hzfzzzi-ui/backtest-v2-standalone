# Spec: Breakout Entry

## Requirement
Generate buy signal when `close > max(high[-20:])` — price breaks above the 20-day highest high.

## Behavior
- Breakout reference: `max(high[t-20:t])` — uses high prices, not close
- Signal check: `close[t] > high_max20[t-1]` (yesterday's 20d high to avoid lookahead)
- Execution: T+1 open price
- Combined with Stage 2 (market regime) and Stage 4 (stock trend) gates

## Parameters
| Param | Default | Range |
|-------|---------|-------|
| `breakout_window` | 20 | 5-60 |

## Signal Flow
```
risk_on[t] = True                    (Stage 2)
  AND v2_trend_ok[t, stock]          (Stage 4)
  AND rank_eligible[t, stock]        (Stage 5)
  AND close[t] > high_max20[t-1]     (Stage 6 — this)
  → BUY signal → T+1 open execution
```

## Edge Cases
- First 20 days: no signal (insufficient data for rolling max)
- Stock resumes from suspension: first day tradable, but 20d high may include pre-suspension levels — acceptable
- Breakout can fire on limit-up days: entry at T+1 open may gap up significantly — accepted risk
