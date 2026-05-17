## Context

The current D5 evidence is diagnostic, not executable. It identifies trades where the close path after entry shows low upside excursion and expanding downside excursion. That diagnostic cannot answer whether freeing capital early helps the full runtime because the shadow did not model cash reuse, missed future entries, later re-entry, order failures, or NAV.

The correct next step is a single-variable runtime AB against the V3 stock component source config.

## Goals

- Run D5 3-day confirmation failure as a real runtime exit.
- Preserve one-variable attribution: only D5 exit settings change.
- Keep the rule independent of industry/theme/market index data.
- Use `runtime_config_json` overrides rather than frontend semantic config.
- Produce same-window B0 and D5 experiments for main, guardrail, and full-audit windows.

## Non-Goals

- Do not promote D5 to a baseline default in this change.
- Do not add industry, theme, liquidity, market regime, candidate, or buyback logic.
- Do not change signal timing, fill timing, stock pool, ETF pool, ranking formula, position sizing, or costs.
- Do not replay precomputed D5 shadow rows as executable orders.

## Rule Definition

For a held stock position, the D5 rule MAY emit one partial sell signal only when all conditions are true:

- `enable_mfe_mae_confirmation_exit=true`
- the current bar is exactly `mfe_mae_confirmation_lookahead_bars` bars after the recorded entry bar
- the adjusted close path from entry bar through current bar has MFE `< mfe_mae_confirmation_min_mfe_pct`
- the same path has MAE `<= mfe_mae_confirmation_max_mae_pct`
- no higher-priority full exit for the symbol was already emitted on the same bar

The default D5 3-day AB values are:

- `mfe_mae_confirmation_lookahead_bars=3`
- `mfe_mae_confirmation_min_mfe_pct=0.02`
- `mfe_mae_confirmation_max_mae_pct=-0.05`
- `mfe_mae_confirmation_exit_pct=0.5`

## Runtime Placement

The rule belongs in the breakout stock signal provider path after standard engine exits are evaluated. This keeps full exits such as stop or trailing risk above D5. D5 emits only an ordinary sell signal; order planning, fill accounting, cash, positions, and NAV remain owned by the normal runtime.

## Risks

- A 3-day confirmation rule can sell positions that later recover; the AB must inspect re-entry/capital reuse rather than treating the shadow delta as decisive.
- It can increase turnover and costs through additional partial sells.
- Exact-bar evaluation is intentionally conservative; if the signal cannot be filled, the existing order lifecycle determines execution, not D5-specific retry logic.
- Same-window comparison to B0 is decisive for this study; registry baseline deltas are secondary.

## Rollback

Disable D5 by leaving `enable_mfe_mae_confirmation_exit=false` or removing the study override. No shared baseline default is changed.
