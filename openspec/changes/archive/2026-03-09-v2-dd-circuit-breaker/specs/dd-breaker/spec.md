# Spec: Drawdown Circuit Breaker

## Requirement
When portfolio drawdown exceeds thresholds, progressively reduce position exposure.

## Behavior

| Drawdown | Action | Default Scale |
|----------|--------|---------------|
| < 10% | Normal | 100% positions |
| >= 10% | Scale down | 80% of max_positions |
| >= 15% | Scale further | 60% of max_positions |
| >= 20% | Minimal | 30% of max_positions |
| >= 25% | Halt | 0 new entries |

- Affects new entries only — existing positions NOT force-sold
- `effective_max_positions = floor(max_positions * scale_factor)`
- Recovery is immediate when DD improves (no hysteresis)
- DD state recorded in daily row for observability

## Parameters
| Param | Default | Range |
|-------|---------|-------|
| `enable_dd_breaker` | false | bool |
| `dd_scale_10` | 0.8 | 0.1-1.0 |
| `dd_scale_15` | 0.6 | 0.1-1.0 |
| `dd_scale_20` | 0.3 | 0.1-1.0 |
| `dd_stop_pct` | 0.25 | 0.1-0.5 |
