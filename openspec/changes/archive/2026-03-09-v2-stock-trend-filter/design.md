# Design: Stock Trend Filter (MA20/MA60)

## Approach

Support strict 3-condition check: `close > MA60 AND MA20 > MA60`. Both independently verified.

The key insight: both conditions compare against MA60. So we need MA20 and MA60 as computed features, and two independent boolean checks.

## Changes

### 1. Features — `features.py`

Add two new feature matrices to `FeatureMatrices`:
- `sma20`: rolling mean of close, window=20
- `sma60`: rolling mean of close, window=60

These are separate from existing `trend_fast_ma`/`trend_slow_ma` (which remain for backward compat).

### 2. Signal matrix — `signal_matrix.py`

Add new signal key `v2_trend_ok` (T×N bool matrix):
```python
v2_trend_ok = (close > sma60) & (sma20 > sma60) & ~np.isnan(sma20) & ~np.isnan(sma60)
```

This is independent of the existing `trend_filter` mechanism. The new filter is applied as a mask on buy signals when `enable_v2_trend_filter=True`.

### 3. Engine integration

In the buy signal evaluation loop, AND the `v2_trend_ok[i, col]` mask with existing buy conditions when the V2 trend filter is enabled.

### 4. Config

Add to strategy params:
- `enable_v2_trend_filter: bool = False`
- `v2_trend_short_ma: int = 20`
- `v2_trend_long_ma: int = 60`

### 5. Backward compatibility

Old `trend_fast_ma`/`trend_slow_ma` mechanism unchanged. V2 trend filter is additive (AND with existing filters).
