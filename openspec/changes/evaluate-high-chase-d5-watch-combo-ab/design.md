## Context

The large-sample shadow diagnosis found:

- Actual combo AB D5 runtime exits are too few for rule fitting: 27 full-cycle exits and 6 recent exits.
- V3 closed-trade shadow has 39 day3 D5 failures among 388 closed trades.
- Candidate-signal shadow has 2061 day3 D5 failures among 9826 valid opportunity rows.
- Day3 D5 failure is a weak signal, but immediate day3 half-exit is not stable enough.

This change therefore tests watch timing, not a new eligibility filter.

## Design

### Variants

- `B0_COMBO_V3_REPLAY`: window-only replay.
- `HC_D5_IMMEDIATE_COMBO`: existing high-chase day3 immediate half-exit.
- `HC_D5_WATCH_DAY5_COMBO`: high-chase day3 D5 failure enters watch; mild failures are reviewed at day5.
- `HC_D5_WATCH_DAY10_COMBO`: high-chase day3 D5 failure enters watch; mild failures are reviewed at day10.

Both watch variants use existing runtime fields:

- `mfe_mae_confirmation_action=watch_day10`
- `mfe_mae_confirmation_lookahead_bars=3`
- `mfe_mae_watch_review_bars=5` or `10`
- `mfe_mae_watch_deep_mae_immediate_pct=-0.08`

The action name remains `watch_day10` because the runtime already exposes review timing as a separate parameter. The study label carries the actual review day.

### Runtime Contract

The combo runner must still:

1. Start from the V3 combo template.
2. Rerun stock and ETF components through normal runtime inputs.
3. Patch only stock runtime strategy params for the D5 candidate.
4. Remove stale execution contracts before unified runtime materialization.
5. Build combo NAV from generated component NAVs.
6. Never use `precomputed_component_results`.

### Reporting

The matrix must compare each non-B0 variant against same-window B0, and must include:

- combo exp id
- stock component exp id
- ETF component exp id
- total return, CAGR, Sharpe, max drawdown, Calmar, trades
- immediate D5 exit count
- watch D5 exit count
- total D5-related exit count

## Risks

- Watch variants can reduce churn but may also delay valid loss cutting.
- Day5/day10 timing may overfit if accepted from one recent right-tail example.
- Combo-level effect may be small because ETF sleeve dilutes stock-leg changes.

Mitigation: require three-window evidence and inspect stock-leg counts before considering promotion.
