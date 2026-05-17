## Context

The current D5 runtime behavior has two layers:

1. A day3 D5 failure is identified when close-path MFE is below the configured minimum and close-path MAE is at or below the configured maximum.
2. In `watch_day10` mode, only failures with MAE above `mfe_mae_watch_deep_mae_immediate_pct` enter watch. Deeper failures still exit immediately.

The last combo AB used `mfe_mae_watch_deep_mae_immediate_pct=-0.08`, so `MAE <= -8%` was still treated as an immediate failure.

## Design

### Variants

- `B0_COMBO_V3_REPLAY`: no D5 override.
- `HC_D5_IMMEDIATE_COMBO`: all High Chase D5 failures with `MAE <= -5%` exit immediately.
- `HC_D5_DEEP_ONLY_IMMEDIATE_COMBO`: only deep High Chase D5 failures with `MAE <= -8%` exit immediately; mild failures are ignored.
- `HC_D5_MILD_WATCH_DEEP_IMMEDIATE_DAY10_COMBO`: failures with `-8% < MAE <= -5%` enter watch; `MAE <= -8%` exits immediately.
- `HC_D5_DEEP_ONLY_WATCH_DAY10_COMBO`: only deep High Chase D5 failures with `MAE <= -8%` enter watch; mild failures are ignored.
- `HC_D5_ALL_WATCH_DAY10_COMBO`: all High Chase D5 failures with `MAE <= -5%` enter watch, including deep failures.

### Runtime Knobs

This change intentionally reuses existing runtime parameters:

- `mfe_mae_confirmation_scope=high_chase`
- `mfe_mae_confirmation_lookahead_bars=3`
- `mfe_mae_confirmation_min_mfe_pct=0.02`
- `mfe_mae_confirmation_max_mae_pct=-0.05` or `-0.08`
- `mfe_mae_confirmation_action=exit` or `watch_day10`
- `mfe_mae_watch_review_bars=10`
- `mfe_mae_watch_deep_mae_immediate_pct=-0.08` or `-1.0`

Using `-1.0` disables the deep-immediate branch for practical A-share price paths and lets deep failures enter watch.

### Acceptance

The result is acceptable for further research only if a candidate:

- beats same-window B0 on full-cycle risk-adjusted metrics,
- does not worsen 2012-2017 materially,
- improves or at least does not worsen 2025-2026 stock-leg drag,
- has explainable D5 counts and no contract drift.

## Risks

- Deep MAE samples are fewer than all D5 samples, so apparent improvements can still be sample-sensitive.
- Allowing all deep failures to watch may keep true failed breakouts too long.
- Combo-level improvements can be diluted by ETF sleeve behavior.
