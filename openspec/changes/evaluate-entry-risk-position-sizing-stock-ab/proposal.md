## Why

The simple CSI1000 trend rebuild found a persistent pattern: entry-time risk
labels reduced drawdown and loss severity when mapped to lower position size,
but the naive standalone strategy still had negative CAGR.

The next useful question is narrower:

Can the same idea improve the formal stock leg if it only changes buy size, while
keeping the formal universe, ranking, exits, fills, costs, and NAV accounting
unchanged?

## What

Add a default-off formal stock-leg AB for entry-risk position sizing.

- Reuse existing formal entry-time risk archetype fields.
- Convert risk flag count to a buy-size multiplier.
- Apply the multiplier through normal buy target sizing.
- Leave unused capital as cash.
- Preserve audit fields on buy signals and executed orders.
- Run same-window stock-leg comparison against the control.

## Non-Goals

- Do not change `baseline_V10.1` default behavior.
- Do not change stock universe, PIT membership, listing-age rules, ST filters,
  liquidity filters, ranking, exit rules, market regime, fills, costs, or ETF leg.
- Do not promote this to a baseline in this change.
- Do not use future returns, TOP30 labels, study output files, or realized PnL to
  decide the multiplier.

## Acceptance

- OpenSpec validates.
- Existing configs keep identical behavior when the switch is disabled.
- Enabled AB uses the formal stock runtime and one NAV/account ledger.
- Executed buy order metadata records tier, labels/flag count, multiplier, and
  target weight basis.
- Main-window run completes in Docker and is compared to the same-window control.
