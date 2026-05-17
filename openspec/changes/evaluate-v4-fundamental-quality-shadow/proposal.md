## Why

The next stock-leg research direction is to reduce position count and
concentrate capital in the most attributable names. Before changing ranking or
position sizing, we need to know whether a basic fundamental quality layer is
available, PIT-safe, and explanatory for V4 stock entries.

## What Changes

- Add a research-only fundamental quality shadow audit for the V4 stock leg.
- Audit existing database tables for PIT-safe fundamental quality coverage.
- Use only quality fields with a defensible observation date contract before
  computing any factor bucket.
- If coverage is missing or not PIT-safe, emit a DATA_BLOCKED result instead of
  fabricating a pseudo-factor.

## Non-Goals

- No V4 or baseline_V10.1 promotion.
- No production ranking, entry, exit, fill, account, or portfolio change.
- No valuation, industry, theme, liquidity, or market-state factor.
- No parameter search for return maximization.

## Validation

- Validate OpenSpec in strict mode.
- Add focused unit tests for PIT eligibility, coverage gating, and quality
  scoring.
- Run the shadow audit in Docker against the current V4 stock-leg anchor.
