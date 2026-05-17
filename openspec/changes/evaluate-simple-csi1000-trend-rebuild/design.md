## Plain Trading Idea

This study starts from the simplest possible A-share trend-following idea:

> In a broad stock pool, hold a small basket of liquid stocks whose own price
> trend is already strong. Rebalance periodically. Sell when that trend is no
> longer strong enough.

This intentionally removes the recent research layers:

- no industry health gate;
- no market-style state gate;
- no theme proxy;
- no residual-vs-industry ranking;
- no post-entry confirmation rule;
- no special failure/watch/restore state.

## First Rule Contract

Default first-pass rules:

- PIT universe: `HS300_ZZ500_CSI1000`.
- Rebalance frequency: weekly, first available trading day of each ISO week.
- Candidate requirement:
  - at least 120 available bars;
  - latest close above MA120;
  - 60-day return positive;
  - 20-day average turnover >= CNY 100m.
- Ranking:
  - primary: 120-day return;
  - tie-breaker: 60-day return;
  - optional diagnostic fields: 20-day return, MA120 distance, turnover.
- Portfolio:
  - equal weight;
  - max positions: 20;
  - no leverage;
  - unfilled cash stays cash.
- Exit:
  - sell if close <= MA120;
  - sell if 60-day return <= 0;
  - sell if no longer in top 40 eligible candidates at a rebalance.
- Costs:
  - approximate turnover cost for buys and sells.

## Why This Is Different From Current Baseline

Current baseline is a breakout/residual system. This study is a slow, simple
cross-sectional trend system. It asks whether the high-level idea works before
we add industry, market, or failure-handling complexity.

## Required Audits

- Membership bucket attribution:
  - `csi800_only`;
  - `csi1000_new`;
  - `overlap`;
  - `unclassified`.
- Trade reason attribution:
  - trend fail;
  - rank exit;
  - rebalance buy.
- Window metrics:
  - CAGR;
  - max drawdown;
  - Sharpe;
  - Calmar;
  - annual return;
  - trade count;
  - turnover;
  - average positions.

## Risks

- Weekly close-to-close research backtest is not a production execution model.
- CSI1000 PIT provider floor before 2015 remains partial for full-cycle
  interpretation.
- A simple strategy may underperform current baseline; that is acceptable if it
  clarifies the next design direction.
