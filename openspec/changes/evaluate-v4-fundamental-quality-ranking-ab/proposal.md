## Why

The V4 fundamental quality shadow showed that quality is not a strong timing
alpha, but low quality names have worse median outcomes and larger loss tails.
The next question is whether quality can help concentrate an unchanged trend
system by acting as a ranking overlay when same-day candidates compete for
limited slots.

## What Changes

- Add a research-only AB that uses PIT fundamental quality as a candidate
  ranking overlay.
- Keep entry signals, exits, market state, stock universe, execution, costs, and
  sizing unchanged.
- Use a daily factor snapshot built from `ann_date`-safe fundamental quality
  rows.
- Compare B0 replay against simple ranking-overlay variants.

## Non-Goals

- No baseline promotion.
- No direct quality-only entry signal.
- No hard q1/q2 veto in the first AB.
- No ETF/combo change.
- No industry/theme factor.

## Validation

- Validate OpenSpec in strict mode.
- Build and audit daily quality snapshot coverage before any AB run.
- Run Docker main-window AB first.
- Continue to guardrail/full windows only if the main-window result is
  interpretable and not obviously harmful.
