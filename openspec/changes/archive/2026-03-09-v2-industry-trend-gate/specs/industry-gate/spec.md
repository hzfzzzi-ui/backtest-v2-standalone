# Spec: Industry Trend Gate

## Requirement
Only allow stocks from top 30% industries (by 60-day return) to enter positions.

## Behavior
- 31 SW Level-1 industry indices ranked daily by 60d return
- Top 30% = top 9-10 industries (ceil(31 * 0.3) = 10)
- Stocks in bottom 70% industries cannot generate buy signals
- Existing positions NOT affected (no forced exit on industry demotion)
- Gate re-evaluated daily

## Parameters
| Param | Default | Range |
|-------|---------|-------|
| `enable_sector_gate` | false | bool |
| `sector_rank_window` | 60 | 20-120 |
| `sector_top_pct` | 0.30 | 0.1-1.0 |

## Data Source
- `pit_index_daily` table: SW L1 index daily OHLCV
- 31 indices: 801010.SI through 801790.SI
- Stock-to-industry mapping from `pit_security_master`

## Edge Cases
- First 60 trading days: no sector ranking available → gate disabled (all pass)
- Industry index with no data on a given day: excluded from ranking
- Stock with no industry mapping: excluded from buy candidates
