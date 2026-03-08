# V2 Stage 9: Exit Rules (MA20 Level + 10-Day Low)

## What
Add two new exit conditions: `close < MA20` (level check) and `close < min(low[-10:])` (10-day low breakout). Either triggers exit (OR relation). This is V2 Stage 9 (Exit).

## Why
Current exit uses MA crossover (`fast_ma crosses below slow_ma`), which is slower than a direct level check. `close < MA20` catches trend breaks earlier. The 10-day low exit provides a price-action based safety net for sharp drops that MA may miss.

## Current State
Engine has MA cross_down exit, ATR stop, ATR trail, take profit, fixed stop, time exit. Missing: MA20 level-based exit and 10-day low exit. No `rolling_min` computation exists in features.

## Scope
- Add `low_min10` feature in `features.py`: `rolling_min(low, 10)`
- Add `close_below_ma20` check (level, not crossover)
- Add `close_below_low10` exit condition
- Both are OR: either triggers exit
- New exit reason codes: `TREND_EXIT_MA20`, `TREND_EXIT_LOW10`
- Wire through all engine paths
