# Spec: Market Regime MA60

## Requirement
When HS300 index close < MA60, all new entries are prohibited.

## Behavior
- Benchmark: HS300 index (default)
- MA period: 60 trading days (configurable via `regime_ma`)
- When `close < MA60`: `risk_on = False` → no buy signals generated
- When `close >= MA60`: `risk_on = True` → normal operation
- Existing positions NOT affected (no forced sell on regime change)
- Daily evaluation, no debounce/grace period

## Parameters
| Param | Default | Range |
|-------|---------|-------|
| `regime_ma` | 60 | 10-250 |
