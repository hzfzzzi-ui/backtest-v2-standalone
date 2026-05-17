## Context

The runtime already has an atomic rotation replacement path:

- `sizing.rotation_replace_enabled`
- `sizing.rotation_replace_only_strong_risk_on`
- `sizing.rotation_replace_max_swaps_per_day`
- `sizing.rotation_replace_candidate_top_n`
- `sizing.rotation_replace_min_score_gap`

When the stock leg is full, this path compares top current candidates against the weakest eligible held names by the same runtime score maps. If the score gap passes the floor, it emits a sell and buy as one atomic replacement pair. If the replacement buy is not executable, the sell is cancelled.

## Decision

Use the existing hook instead of adding a new industry/theme rule. This isolates the structural question:

> Does letting stronger candidates replace weaker current holdings improve the V4 stock leg?

The first V4 test uses a less restrictive replacement profile than the old B1 control:

- allow replacement outside only-strong-risk-on days
- inspect top 5 candidates
- allow 1 swap per day
- require a 0.05 score gap

## Non-Goals

- Do not add industry or theme data to runtime selection.
- Do not change signal timing, fill timing, stock pool, ranking formula, entry rules, or exit rules.
- Do not run ETF or combo sleeves in this AB.
- Do not promote a baseline from this test alone.

## Risks

- Lower score-gap threshold may increase turnover.
- If the score map is not sufficiently explanatory, replacement can churn rather than improve risk-adjusted return.
- Same-window B0 must be used as the primary comparison because registry baselines may have different end dates.

## Rollback

Do not use the study variant, or set `sizing.rotation_replace_enabled=false`. No shared defaults are changed.
