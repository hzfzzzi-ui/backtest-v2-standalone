## Design

### Soft Deprioritization

The candidate adds default-off `risk_archetype_soft_deprioritize` parameters to
the breakout provider. When enabled, it computes same-day cross-sectional ranks
inside the executable buy candidate set.

Inputs:

- `pre_ret20_rank`: 20-bar return rank.
- `dist_ma60_rank`: close versus 60-bar moving average rank.
- `vol60_rank`: 60-bar daily return volatility rank.
- `turnover20_rank`: 20-bar average turnover rank.
- `fade_rank`: breakout fade rank.
- `open_gap_rank`: breakout open gap rank.

Flags:

```text
hot_crowded = pre_ret20_rank >= q AND turnover20_rank >= q
high_volatility_chase = vol60_rank >= q
```

The first AB uses:

- `q = 0.80`
- hot/crowded score scale `0.80`
- high-volatility score scale `0.85`

If both flags trigger, the score scales compound. No candidate is removed.

### Scope

The rule only adjusts `final_score` before daily candidate indexing. It does not
change:

- stock universe or PIT eligibility
- breakout/pullback signal generation
- sell rules
- account ledger
- sizing
- cash blocking

Because candidate ordering consumes `final_score`, the rule should only affect
execution when there is candidate competition.

### Audit

Buy signal metadata records the risk archetype flags, ranks, original score,
adjusted score, and scale. The provider runtime notes also record whether the
rule was applied and how many candidate cells received each penalty.

When the switch is disabled, the matrices are neutral and the baseline path is
unchanged.

### Risk

The shadow signal is broad but still observational. The first AB is not a
promotion candidate unless the result passes same-window B0 comparison and later
2012-2017 and 2012-2026 validation. A main-window failure should stop the
branch.
