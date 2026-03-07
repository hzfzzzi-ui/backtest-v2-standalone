# Spec: Universe Price Filter

## Requirement
Stocks with close price < 5 CNY must be excluded from the trading universe.

## Behavior
- Filter applied daily: if a stock's latest close < `min_price`, it is excluded
- Default threshold: 5.0 CNY
- Configurable via `UniverseFilterConfig.min_price`
- Exclusion reason code: `EXCLUDE_LOW_PRICE`
- If `min_price = 0`, filter is disabled

## Edge Cases
- Stocks that drop below 5 CNY after entry: NOT affected (universe filter is entry-only)
- Suspended stocks (no close): excluded by separate `exclude_suspended` filter
