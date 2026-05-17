## Scope

The study audits V4/B0 stock-leg BUY entries from `exp_20260516_224942916_8830`
and asks:

1. Does high turnover explain losing entries better than low amount?
2. Is high amount a capacity feature or just a hot-name feature?
3. Does `high turnover + high pre-entry position` concentrate losses?
4. Does a simple crowding label cover more loss TOP50 than profit TOP50?

## Factor Contract

All factor labels are computed from data observable on or before the signal date.

- `amount20`: 20-trading-day mean turnover amount.
- `turnover_rate20`: 20-trading-day mean free-float turnover rate.
- `amount_accel_20_60`: `amount20 / amount60`.
- `turnover_accel_20_60`: `turnover_rate20 / turnover_rate60`.
- `pre_ret_20`: adjusted close return over the prior 20 trading days.
- `dist_ma20`: adjusted close distance versus 20-day average.

Percentiles are computed inside the logged signal pool for the same signal date:
selected BUY rows plus `candidate_signals.csv` rows. This is not a full-market
percentile and the report must state that limitation.

## Labels

- `LOW_AMOUNT`: low signal-pool amount percentile.
- `HOT_TURNOVER`: high signal-pool turnover percentile.
- `AMOUNT_SURGE`: high amount acceleration percentile.
- `TURNOVER_SURGE`: high turnover acceleration percentile.
- `HIGH_POSITION`: high signal-pool pre-entry return or MA20 distance.
- `CROWDING_RISK`: `HOT_TURNOVER` and `TURNOVER_SURGE`.
- `HOT_LIQUIDITY_CHASE`: `HOT_TURNOVER` and `HIGH_POSITION`.
- `HEALTHY_LIQUIDITY`: not low amount, not hot turnover, not turnover surge.

## Follow-up Complete Shadow

The complete shadow extends the same entry panel with quality and volatility:

- `quality_score`: daily fundamental quality score joined by signal date and
  symbol from the research snapshot.
- `quality_score_pct`: signal-pool percentile of `quality_score`.
- `LOW_QUALITY`: low quality percentile.
- `HIGH_VOLATILITY`: high 20-day realized volatility percentile.
- `HOT_AMOUNT_TURNOVER`: high amount and high turnover.
- `HOT_POSITION_TURNOVER`: high position and high turnover.
- `COMPOSITE_RISK_3OF5`: at least three of high amount, high turnover, high
  position, low quality, and high volatility.
- `COMPOSITE_RISK_4OF5`: at least four of those five labels.
- `HOT_POSITION_TURNOVER_WITH_QV`: high position and high turnover, plus low
  quality or high volatility.

This remains a shadow audit. The thresholds are descriptive signal-pool
percentiles, not accepted runtime parameters.

## Output Contract

The audit writes under
`outputs/analysis/v4_liquidity_turnover_crowding_shadow_<date>/`:

- `entry_panel.csv`
- `bucket_summary.csv`
- `cross_bucket_summary.csv`
- `top50_coverage.csv`
- `complete_composite_coverage.csv`
- `complete_composite_bucket_summary.csv`
- `summary.json`
- `report.md`

## Decision Rule

This shadow can only recommend a future AB if a label increases loss coverage
without also covering a similar or larger share of profit TOP50. It cannot
promote a runtime rule by itself.
