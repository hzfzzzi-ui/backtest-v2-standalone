# V2 Stage 1: Universe Price Filter

## What
Add a minimum price filter (`close > 5 CNY`) to the universe filtering pipeline. This is part of the V2 9-stage trend strategy, Stage 1 (Universe).

## Why
Low-priced stocks (< 5 CNY) in A-shares tend to have poor liquidity, higher manipulation risk, and are often ST/delisting candidates. Filtering them improves signal quality.

## Current State
`UniverseFilterConfig` already has: `exclude_st`, `exclude_suspended`, `min_list_days=120`, `min_avg_turnover_20d=1e8`. Missing: `min_price`.

## Scope
- Add `min_price: float = 5.0` to `UniverseFilterConfig`
- Add price filter logic in `apply_universe_filters()`
- Wire through API + frontend (Universe tab placeholder)
