# V2 Stage 6: Breakout Entry (20-Day High)

## What
Create a new `BreakoutTrendProvider` signal provider that generates buy signals when `close > max(high[-20:])`. T+1 open price execution. This is V2 Stage 6 (Entry Trigger).

## Why
Price breakout above 20-day high is a classic momentum entry signal. It captures stocks making new short-term highs, indicating fresh buying pressure. This replaces MA crossover as the entry trigger for the V2 trend strategy.

## Current State
No breakout detection exists. Current entry signals use MA cross/level checks (SMASignalProvider, GenericSignalProvider). T+1 open execution is already implemented.

## Scope
- Add `high_max20` feature in `features.py`: `rolling_max(high, 20)`
- Create `breakout_signal_provider.py` implementing `SignalProvider` protocol
- Register new provider in engine dispatch logic
- Add `breakout_trend` strategy type in registry
- Wire through API/frontend (Stage 6 Entry tab with SMA/EMA/Breakout options)
