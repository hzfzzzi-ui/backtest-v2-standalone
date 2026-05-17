## Design

### Entry Veto

The candidate adds a default-off `bad_breakout_quality_veto` to the breakout
provider. When enabled, it computes two pre-entry matrices from adjusted close:

- `bad_breakout_quality_ret5`: 5-bar return.
- `bad_breakout_quality_r2_60`: rolling 60-bar linear-trend R2 on log close.

The matrices are converted into same-day cross-sectional ranks inside the
breakout candidate set. The veto mask is applied before candidate indexing:

```text
breakout_buy
AND ret5_rank >= threshold
AND r2_60_rank <= threshold
```

The first AB thresholds are rank cutoffs, not absolute price-pattern cutoffs:

- `ret5_rank >= 0.80`
- `r2_60_rank <= 0.20`

### Scope

The rule only gates breakout entries. It does not change:

- stock universe or PIT eligibility
- ranking score
- pullback candidate behavior
- sell rules
- account ledger
- sizing
- cash blocking

### Audit

The provider records `BAD_BREAKOUT_QUALITY_VETO` in diagnostic reason counts.
When the switch is disabled, all new matrices remain empty or neutral and the
baseline path is unchanged.

### Risk

The shadow sample is small and rank thresholds are still a research hypothesis.
Passing the main window is not enough for promotion; the result must later pass
the 2012-2017 hard gate and 2012-2026 full audit.
