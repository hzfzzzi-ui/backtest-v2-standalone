# V2 Stage 3: Industry Trend Gate (Top 30%)

## What
Add an industry-level trend gate: rank SW Level-1 industries by 60-day return, only allow stocks from top 30% industries to enter. This is V2 Stage 3 (Industry Trend).

## Why
Strong industries carry their constituent stocks. Trading in weak industries means fighting the sector tide. 60-day return is a clean, lag-free metric vs the current EMA-slope × ADX composite.

## Current State
Infrastructure exists: 31 SW L1 industry codes defined, `load_sector_indices()` loads sector OHLC, `RegimeFilter` has a sector layer (but uses EMA/ADX/spread scoring, not 60d return ranking). The sector gate only works through `RegimeRouterSignalProvider`, not the SMA path.

## Scope
- Compute sector 60d return for all 31 industries daily
- Cross-sectional rank: top 30% industries pass gate
- Map each stock to its industry, apply gate to buy candidates
- Wire through all engine paths (SMA + Generic + RegimeRouter)
- Expose `sector_rank_window=60`, `sector_top_pct=0.3` in config/API/frontend
