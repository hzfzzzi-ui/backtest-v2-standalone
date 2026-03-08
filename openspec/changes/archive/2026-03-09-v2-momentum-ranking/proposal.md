# V2 Stage 5: Momentum Ranking (Top 10%)

## What
Implement a 3-factor momentum ranking system: `score = 20d_return + 60d_return + 120d_return`. Select top 10% of eligible stocks. This is V2 Stage 5 (Relative Strength Ranking).

## Why
After filtering for trend stocks (Stage 4), we want the strongest among them. A composite momentum score using multiple timeframes captures both short-term acceleration and long-term strength. Top 10% concentrates capital in the highest-conviction names.

## Current State
`_build_daily_multifactor_scores()` computes `roc20` + `rs60` + amount_z + BB_pos (4 factors). Missing: 120d return. Uses `mf_topk=10` (absolute count) not top 10% (percentage).

## Scope
- Add 120d return factor to momentum scoring
- Change scoring to simple 3-factor: `20d + 60d + 120d` returns
- Change selection from `topN` to `top_pct` (percentage-based)
- Wire `momentum_top_pct` parameter through config/API/frontend
