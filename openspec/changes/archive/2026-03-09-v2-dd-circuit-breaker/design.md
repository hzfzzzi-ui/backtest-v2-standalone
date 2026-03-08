# Design: Drawdown Circuit Breaker

## Approach

Wire the existing `RiskBudgetConfig` into the engine daily loop. When portfolio drawdown exceeds thresholds, progressively reduce exposure.

## Changes

### 1. Engine daily loop — `portfolio_simulator_strict.py`

After drawdown computation (line ~440), add exposure scaling:

```python
# Already computed:
peak_nav = max(peak_nav, nav)
drawdown = (nav / peak_nav - 1.0) if peak_nav > 0 else 0.0

# NEW: compute effective max_positions based on drawdown
dd_abs = abs(drawdown)
if dd_abs >= dd_stop_pct:          # default 25%
    effective_max_positions = 0     # halt all new entries
elif dd_abs >= 0.20:
    effective_max_positions = max(1, int(max_positions * dd_scale_20))  # or fixed risk
elif dd_abs >= 0.15:
    effective_max_positions = max(1, int(max_positions * dd_scale_15))
elif dd_abs >= 0.10:
    effective_max_positions = max(1, int(max_positions * dd_scale_10))
else:
    effective_max_positions = max_positions
```

Use `effective_max_positions` instead of `max_positions` in the buy slot calculation.

### 2. Config reading

Extract `RiskBudgetConfig` fields in engine init:
```python
dd_scale_10 = float(getattr(risk_budget, "dd_scale_10", 0.8))
dd_scale_15 = float(getattr(risk_budget, "dd_scale_15", 0.6))
dd_scale_20 = float(getattr(risk_budget, "dd_fixed_20", 0.3))  # use as scale
dd_stop_pct = float(getattr(risk_budget, "dd_stop_pct", 0.25))
```

### 3. Metrics

Add to daily_rows:
- `effective_max_positions`: the DD-adjusted position limit for that day
- `dd_state`: "NORMAL" / "SCALE_10" / "SCALE_15" / "SCALE_20" / "HALTED"

### 4. Recovery

When drawdown improves (crosses back above threshold), positions scale back up immediately. No hysteresis (keep it simple for V1).
