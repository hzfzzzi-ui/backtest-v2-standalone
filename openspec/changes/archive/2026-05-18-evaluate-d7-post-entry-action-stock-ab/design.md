## Context

Current baseline D7 behavior:

- `enable_mfe_mae_confirmation_exit=true`
- `mfe_mae_confirmation_scope=high_chase`
- `mfe_mae_confirmation_action=exit`
- `mfe_mae_confirmation_lookahead_bars=3`
- `mfe_mae_confirmation_min_mfe_pct=0.02`
- `mfe_mae_confirmation_max_mae_pct=-0.08`
- `mfe_mae_confirmation_exit_pct=0.5`

The all-candidate D7 shadow showed that the D7-triggered group has worse
post-entry paths, but it did not prove that stronger selling is better inside a
portfolio.

## Design

### Variants

- `B0_CURRENT_D7_HALF_EXIT`: current `baseline_V10_1` stock replay.
- `D7_IMMEDIATE_50_CONTROL`: explicit current D7 50% half-exit control.
- `D7_IMMEDIATE_75`: sell 75% immediately.
- `D7_IMMEDIATE_100`: sell fully immediately.
- `D7_DELAYED_5D_HALF_EXIT`: wait until day5 before evaluating the same D7
  deep-failure condition, then half-exit.
- `D7_WATCH_DAY10_HALF_EXIT`: day3 D7 failures enter watch; unresolved cases
  half-exit on day10 when MFE remains weak and MAE remains deep.

### Why No Cooldown

Cooldown would mix exit action with future re-entry blocking. This study only
tests the immediate or delayed D7 action method. Re-entry blocking should be a
separate study if action method passes.

## Acceptance

A candidate worth continuing should:

- improve or preserve MaxDD and Calmar versus the current 50% control;
- not materially reduce CAGR or Sharpe;
- not increase churn without drawdown benefit;
- be explainable from same-window stock-only runtime outputs.

## Rollback

Remove this research study. No baseline default is changed.
