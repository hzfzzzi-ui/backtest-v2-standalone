## Why

Recent V4 stock-leg attribution showed that loss names are not primarily low
amount names. They often have higher turnover and hotter liquidity conditions.
Before turning liquidity or turnover into a runtime rule, we need a shadow audit
that separates capacity from crowding risk.

## What Changes

- Add a research-only liquidity/turnover crowding shadow audit for V4 stock
  entries.
- Use entry-time and pre-entry data only for factor labels.
- Compare all BUY samples, profit/loss outcomes, TOP50 profit/loss coverage,
  and liquidity x turnover cross buckets.
- Write machine CSV/JSON and a human report under `outputs/analysis/`.

## Non-Goals

- No strategy, ranking, entry, exit, portfolio, account, or baseline change.
- No hard veto, no position sizing rule, and no parameter promotion.
- No ETF/combo interpretation.

## Validation

- Validate OpenSpec.
- Run the shadow audit in Docker against the current V4 stock-leg B0 anchor.
- Report whether liquidity/turnover is useful enough for a later AB.
