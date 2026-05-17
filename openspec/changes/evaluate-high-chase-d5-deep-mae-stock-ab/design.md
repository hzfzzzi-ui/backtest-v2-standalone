## Context

The existing D5 runtime implementation can already express the required
variants with strategy params:

1. Day3 D5 failure: close-path MFE is below the configured minimum and
   close-path MAE is at or below the configured maximum.
2. `watch_day10`: a day3 failure can enter watch and be reviewed later.
3. `mfe_mae_watch_deep_mae_immediate_pct`: failures deeper than this threshold
   can still exit immediately instead of entering watch.

This study does not add new runtime behavior. It fixes a stock-only AB contract
around the existing knobs.

## Design

### Variants

- `B0_V3_STOCK_REPLAY`: no D5 override.
- `HC_D5_IMMEDIATE_HALF_EXIT`: incumbent candidate; all High Chase D5 day3
  failures with `MAE <= -5%` exit half immediately.
- `D7_DEEP_ONLY_IMMEDIATE_HALF_EXIT`: only High Chase D5 day3 failures with
  `MAE <= -8%` exit half immediately; mild failures are ignored.
- `D7_MILD_WATCH_DEEP_IMMEDIATE_DAY10`: High Chase D5 day3 mild failures
  (`-8% < MAE <= -5%`) enter watch, while `MAE <= -8%` exits half immediately.
  Watch exits only if day10 is still unrepaired: `MFE < +5%` and `MAE <= -8%`.
- `D7_ALL_WATCH_DEEP_REVIEW_DAY10`: all High Chase D5 day3 failures with
  `MAE <= -5%` enter watch. Day10 exits only if unrepaired:
  `MFE < +5%` and `MAE <= -8%`.

### Runtime Knobs

This change intentionally reuses existing runtime parameters:

- `enable_mfe_mae_confirmation_exit=true`
- `mfe_mae_confirmation_scope=high_chase`
- `mfe_mae_confirmation_lookahead_bars=3`
- `mfe_mae_confirmation_min_mfe_pct=0.02`
- `mfe_mae_confirmation_max_mae_pct=-0.05` or `-0.08`
- `mfe_mae_confirmation_action=exit` or `watch_day10`
- `mfe_mae_confirmation_exit_pct=0.5`
- `mfe_mae_watch_review_bars=10`
- `mfe_mae_watch_review_min_mfe_pct=0.05`
- `mfe_mae_watch_review_max_current_return_pct=0.05`
- `mfe_mae_watch_review_max_mae_pct=-0.08`
- `mfe_mae_watch_deep_mae_immediate_pct=-0.08` or `-1.0`

Using `-1.0` disables the deep-immediate branch for practical A-share price
paths and lets deep failures enter watch.

## Acceptance

The result is acceptable for further research only if a candidate:

- improves or preserves same-window B0 MaxDD, Calmar, and Sharpe;
- does not materially worsen 2012-2017 hard-gate behavior;
- improves or at least does not worsen 2025-2026 stock-leg drag;
- has explainable D5 immediate/watch counts and no contract drift.

## Risks

- Deep-MAE samples are small, so improvements may be sample-sensitive.
- All-watch variants may keep true failed breakouts too long.
- A stock-only win must still pass later combo validation before any baseline
  promotion discussion.
