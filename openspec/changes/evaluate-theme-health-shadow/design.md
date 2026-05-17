## Context

The V3 attribution bundle already contains daily stock theme exposure, daily candidate pressure, and ETF theme proxy strength:

- `long_daily_theme_alignment.csv`
- `long_daily_stock_theme_exposure.csv`
- `long_daily_stock_theme_candidate_pressure.csv`
- `long_daily_etf_theme_proxy_strength.csv`
- `manifest.json`

C1 should use those artifacts as evidence. The source of truth remains the V3 run artifacts; C1 is an audit layer over those artifacts.

## Design

The runner computes theme health only for daily rows where a stock theme is actually held. For each held theme/day it records:

- trend pressure: weak ETF proxy return over 20/60 days;
- relative rank pressure: theme proxy rank among available themes;
- candidate pressure: visible candidates and selected rows are absent while exposure remains;
- held exposure pressure: held exposure remains while proxy is weak;
- health score: 0 to 100, derived from the above evidence;
- labels: `healthy`, `watch`, or `confirmed_weak`.

The first version intentionally avoids a hard trading prescription. It only answers:

1. Which held themes were already weakening?
2. How many held days would have been watch/confirmed weak?
3. Which windows show the delay risk most clearly?
4. Is the evidence complete enough to justify a later runtime AB?

## Scoring

Default shadow thresholds:

- `proxy_ret20_weak_threshold`: `0.0`
- `proxy_ret60_weak_threshold`: `0.0`
- `rank_pct_weak_threshold`: `0.60`
- `candidate_collapse_days`: `10`
- `confirmed_min_flags`: `3`
- `watch_min_flags`: `2`

The runner should keep thresholds in the output so later AB tests can be traced.

## Risks

- ETF proxy coverage is incomplete for older windows and some themes. The runner must mark coverage risk and avoid treating early windows as baseline-upgrade evidence.
- Proxy returns are not exact stock basket returns. Reports must call this an attribution proxy, not a tradable signal.
- A confirmed weak label is a research flag only. It must not be interpreted as a sell instruction until a separate L3 runtime AB is specified.
