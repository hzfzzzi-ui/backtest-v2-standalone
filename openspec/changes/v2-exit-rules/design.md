# Design: Exit Rules (MA20 Level + 10-Day Low)

## Approach

Add two new exit conditions to the engine sell loop. Both are OR — either triggers exit.

## Changes

### 1. Features — `features.py`

Add two new feature matrices:
```python
sma20: np.ndarray       # 20-day SMA of close (may reuse from v2-stock-trend-filter)
low_min10: np.ndarray   # rolling min of low, window 10
```

`low_min10` computation: `pd.Series(low[:, col]).rolling(10).min()` per stock column.

### 2. Exit logic — engine sell loop

In the exit priority chain, add two new checks **after ATR trail but before existing signal exit**:

```
RISK_OFF > TREND_BREAK > ATR_STOP > FIXED_STOP > ATR_TRAIL >
TAKE_PROFIT > MA20_EXIT > LOW10_EXIT > TIME_EXIT > SIGNAL_EXIT
```

Logic:
```python
elif enable_ma20_exit and cclose < sma20[i, col]:
    reason = "TREND_EXIT_MA20"
elif enable_low10_exit and cclose < low_min10[i, col]:
    reason = "TREND_EXIT_LOW10"
```

Note: uses adjusted close (`cclose`) and adjusted MA20/low_min10 (same scale).

### 3. Exit counters

Add `exit_ma20_count` and `exit_low10_count` to metrics.

### 4. Config

- `enable_ma20_exit: bool = False`
- `ma20_exit_period: int = 20`
- `enable_low10_exit: bool = False`
- `low10_exit_window: int = 10`

### 5. Price scale

Both MA20 and low_min10 are computed on adjusted close/low from the feature matrix — same scale as `cclose`. No raw/adjusted mismatch.
