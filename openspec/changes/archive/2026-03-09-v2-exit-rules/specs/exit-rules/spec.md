# Spec: V2 Exit Rules

## Requirement
Two new exit conditions (OR relation):
1. `close < MA20` — trend break exit
2. `close < min(low[-10:])` — 10-day low breakout exit

## Behavior
- Both use adjusted prices (后复权) for comparison consistency
- OR relation: either condition triggers exit
- Priority in exit chain: after ATR trail, before time exit
- New reason codes: `TREND_EXIT_MA20`, `TREND_EXIT_LOW10`
- New counters: `exit_ma20_count`, `exit_low10_count`

## Parameters
| Param | Default | Range |
|-------|---------|-------|
| `enable_ma20_exit` | false | bool |
| `ma20_exit_period` | 20 | 5-60 |
| `enable_low10_exit` | false | bool |
| `low10_exit_window` | 10 | 3-30 |

## Exit Priority (full chain)
```
1. RISK_OFF_EXIT (market regime)
2. TREND_BREAK_EXIT (legacy)
3. ATR_STOP_LOSS
4. FIXED_STOP_LOSS
5. ATR_TRAIL_EXIT
6. TAKE_PROFIT
7. TREND_EXIT_MA20   ← new
8. TREND_EXIT_LOW10  ← new
9. TIME_EXIT
10. SIGNAL_EXIT (MA cross down)
```
