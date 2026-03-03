# breadth-score-engine

## Purpose

Cross-sectional breadth/dispersion score calculation engine. Computes daily scores in [0, 1] based on statistical measures of returns across a tradable universe of stocks.

## Requirements

### R1: Three Indicator Types
- **A (breadth_up)**: Proportion of stocks with positive daily return among tradable stocks, smoothed with SMA5
- **B (breadth_momo)**: Proportion of stocks where EMA(fast) > EMA(slow), smoothed with SMA5
- **C (dispersion)**: 20-day rolling z-score of cross-sectional return standard deviation, mapped to [0, 1] (low dispersion = high score)
- **combo**: 0.5 x B + 0.5 x C

### R2: Data Source and Adjustment
- Daily returns r_1d computed from hfq (back-adjusted) close prices to avoid ex-dividend jumps
- Denominator is count of stocks with tradable=True on that day (excluding suspended, ST, insufficient listing days)
- NaN values excluded from statistics (use nanmean/nanstd)

### R3: No Lookahead Bias
- All rolling/EMA calculations use only historical data (t and earlier)
- Daily score based on current and prior data only, no future references

### R4: Vectorized Implementation
- Use numpy (T x N) matrix operations, avoid symbols x days nested Python loops
- T-dimension loops (~2400 steps) acceptable; N-dimension (~700 stocks) must be vectorized

### R5: Output Interface
- Return `BreadthScoreResult` containing scores_A / B / C / combo as four (T,) arrays
- Each value in [0, 1], NaN indicates no valid data for that day
- Warmup period (EMA/rolling window not yet full) outputs NaN

### R6: Observability
- Score values written to daily_rows diagnostics (field name `breadth_score`)
- Logging: warmup day count, valid day ratio, score mean/std
