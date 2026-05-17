## Context

The existing `profit_decay_exit` requires residual-score deterioration and
fully exits the position. That is not the narrow behavior needed here. The
recent-path audit points to a simpler condition: a position has already produced
material unrealized profit, then gives back a large part of that profit and
breaks below MA20.

This change adds one default-off runtime branch and wires it only through a
research study. It intentionally does not consume shadow outputs, industry
state, market-breadth state, or future-return fields.

## Design

### Runtime Rule

Add optional params:

- `enable_peak_giveback_ma20_exit`: default `false`
- `peak_giveback_ma20_min_peak_profit_pct`: default `0.20`
- `peak_giveback_ma20_min_giveback_pct`: default `0.25`
- `peak_giveback_ma20_min_hold_bars`: default `10`
- `peak_giveback_ma20_exit_pct`: default `0.5`

For each held stock not already selected for exit:

1. Track peak close using the existing `peak_state`.
2. Compute peak profit: `peak_close / avg_cost - 1`.
3. Compute giveback from peak: `peak_close / current_close - 1`.
4. Require `bars_since_entry >= min_hold_bars`.
5. Require `peak_profit >= min_peak_profit_pct`.
6. Require `giveback_from_peak >= min_giveback_pct`.
7. Require current close below MA20 using current-day SMA20.
8. Emit a partial sell with reason code `PEAK_GIVEBACK_MA20_EXIT`.

The partial quantity uses the same round-lot behavior as D5 exits:

- if configured pct is `>= 1`, sell all;
- otherwise sell approximately `exit_pct`, rounded down to 100-share lots;
- avoid leaving an odd lot below 100 shares.

### Study Variants

Stock-only first:

- `B0_V4_STOCK_REPLAY`: current stock-leg replay.
- `GIVEBACK20_MA20_HALF`: peak profit `>= 20%`, giveback `>= 20%`, half exit.
- `GIVEBACK25_MA20_HALF`: peak profit `>= 20%`, giveback `>= 25%`, half exit.
- `GIVEBACK30_MA20_HALF`: peak profit `>= 20%`, giveback `>= 30%`, half exit.

The first run should use `2016-2026`. Only if results are interpretable should
the hard-gate `2012-2017` and full audit `2012-2026` windows run.

### Acceptance

Continue only if the candidate:

- improves or preserves same-window MaxDD and Calmar;
- does not materially reduce CAGR;
- reduces 2025 computer/giveback losses or their realized drawdown;
- does not create excessive churn;
- has clear reason-code counts and no contract drift.

## Risks

- This rule may sell strong trends too early if giveback is just normal
  volatility.
- A fixed giveback percentage may be sample-sensitive.
- Stock-only improvements must still pass combo validation before any baseline
  promotion.
