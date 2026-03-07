# Design: Market Regime MA60

## Approach

Change the default `regime_ma` from 120 to 60 across all engine paths. Verify all paths consistently use this parameter.

## Changes

### 1. Default change — `portfolio_simulator_strict.py`

Line 231: `regime_ma = int(getattr(strategy, "regime_ma", 120))` → change default to `60`.

### 2. SMA path — `sma_signal_provider.py`

Line 230: Same `getattr(strategy, "regime_ma", 120)` → change to `60`.

### 3. RegimeRouter path — `regime_router_signal_provider.py`

Already defaults to 60 via `getattr(detector, "regime_ma", 60)` — no change needed.

### 4. Strategy dataclasses

Add `regime_ma: int = 60` to `SMACrossStrategy` and `EMACrossStrategy` if not present.

### 5. Registry — `registry.py`

Pass `regime_ma` in `build_strategy()` for sma_cross and ema_cross builders.

### 6. API — `_experiment_runner_api.py`

Ensure `regime_ma` is in `strategy.params` when market filter is enabled.

## Verification

After change, all engine paths should:
- Default to MA60 if not specified
- Accept `regime_ma` override via strategy config
- HS300 close > MA60 → `risk_on=True` (allow entries)
- HS300 close < MA60 → `risk_on=False` (block all entries)
