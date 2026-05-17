## Why

Recent research has become too layered: state labels, industry health, residual
strength, high-chase tags, and exit patches are all useful diagnostics, but they
do not yet answer the simpler question:

Can a plain trend-following stock strategy work on a PIT stock pool that includes
CSI1000, before we add complex market, industry, or execution rules?

The user wants a fresh design from the most basic trading idea, with CSI1000
included in the stock pool.

## What

Add a research-only simplified backtest:

- Universe: PIT `HS300_ZZ500_CSI1000` using `000906.SH + 000852.SH`.
- Signal: no industry/theme/state/residual logic.
- Entry selection: periodically buy the strongest stocks that are already in an
  uptrend.
- Exit: leave positions when the basic trend fails or the stock falls out of the
  top group.
- Output: NAV, trades, metrics, universe coverage, and simple attribution by
  membership bucket (`csi800_only`, `csi1000_new`, `overlap`).

## Non-Goals

- Do not change `baseline_V10.1`.
- Do not change `CN_STOCK_ETF_COMBO_BASELINE_V3/V4`.
- Do not change production universe resolver, ranking, execution, fills, costs,
  ETF leg, or combo allocator.
- Do not promote this result as a baseline.
- Do not add market or industry filters in this first version.

## Acceptance

- OpenSpec validates.
- The study is explicitly research-only.
- The simple strategy has a readable rule contract.
- The 2016-2026 main-window run completes in Docker.
- If the main-window result is interpretable, run 2012-2017 and 2012-2026.
- Report whether the simple idea is worth iterating, rejected, or held.
