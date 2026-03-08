# Design: Breakout Entry (20-Day High)

## Approach

Create a new `BreakoutTrendProvider` that implements the `SignalProvider` protocol. Entry signal: `close > max(high[-20:])`.

## Architecture

```
SignalProvider (protocol)
├── SMASignalProvider        ← existing
├── GenericSignalProvider     ← existing
├── RegimeRouterSignalProvider ← existing
└── BreakoutTrendProvider    ← NEW
```

The provider uses the same `precompute()` → `day_signals()` → fill hooks pattern.

## Changes

### 1. Feature — `features.py`

Add to `FeatureMatrices`:
```python
high_max20: np.ndarray  # rolling max of high, window 20, shape (T, N)
```

Computation: `np.lib.stride_tricks.sliding_window_view(high, 20, axis=0).max(axis=-1)` or pandas `rolling(20).max()`.

### 2. New provider — `breakout_signal_provider.py`

```python
class BreakoutTrendProvider:
    def precompute(self, mx, strategy, ...):
        # Build high_max20 from mx.high
        # Build buy signal: close[t] > high_max20[t-1]  (use yesterday's 20d high to avoid lookahead)
        # Apply risk_on mask
        # Apply v2_trend_ok mask if enabled

    def day_signals(self, i, ...):
        # Generate buy orders for stocks with breakout signal
        # Generate sell orders for exit conditions (ATR stop, MA20 exit, etc.)
```

Key detail: compare today's close against **yesterday's** 20-day high to avoid lookahead bias. Signal on day T, buy at T+1 open.

### 3. Engine dispatch — `portfolio_simulator_strict.py`

Add dispatch branch:
```python
if strategy_name == "breakout_trend":
    provider = BreakoutTrendProvider()
```

### 4. Strategy — `strategies/breakout_trend.py`

New strategy dataclass with all V2 params:
```python
@dataclass(slots=True)
class BreakoutTrendStrategy(Strategy):
    breakout_window: int = 20
    regime_ma: int = 60
    enable_v2_trend_filter: bool = True
    v2_trend_short_ma: int = 20
    v2_trend_long_ma: int = 60
    # exit params...
    enable_atr_stop: bool = True
    atr_stop_k: float = 2.0
    # etc.
```

### 5. Registry + API

Register `breakout_trend` in `build_strategy()` and add API config mapping.
