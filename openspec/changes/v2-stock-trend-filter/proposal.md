# V2 Stage 4: Stock Trend Filter (MA20/MA60)

## What
Implement a strict 3-condition stock trend filter: `close > MA60 AND MA20 > MA60`. Both conditions checked independently. This is V2 Stage 4 (Stock Trend).

## Why
Ensures we only buy stocks in confirmed uptrends. Avoids bottom-fishing. MA20 > MA60 confirms short-term trend is above medium-term. close > MA60 confirms price is above the medium-term average.

## Current State
Engine has `trend_fast_ma` (default 120) and `trend_slow_ma` (default 200) with filter `close > fast AND fast > slow`. Need to:
1. Support 3 independent MA lines (close vs MA60, MA20 vs MA60)
2. Change defaults to MA20/MA60
3. Add explicit `close > slow_ma` check separate from `fast > slow`

## Scope
- Add MA60 computation in `features.py` (or repurpose trend_slow_ma=60)
- Add MA20 computation (or repurpose trend_fast_ma=20)
- Ensure `close > MA60` is checked independently from `MA20 > MA60`
- Wire parameters through config/API/frontend
