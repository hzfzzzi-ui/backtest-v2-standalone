## Why

Recent stock-leg research shows that local exit patches can fix some 2025
computer/basic-chemical samples, but they do not reliably improve drawdown at
the strategy level. The larger issue is structural: the current trend system is
primarily driven by stock-level breakout/ranking and reacts late when market
state, industry state, or rotation pressure deteriorates.

The next research direction is to design a state-driven trend strategy from the
top down: market state controls gross exposure, industry state controls where
risk is allowed, and stock trend quality only decides which names to execute.

## What Changes

- Add a research-only strategy design and shadow study for a state-driven trend
  framework.
- First phase is shadow-only:
  - no trading orders;
  - no NAV recompute;
  - no baseline mutation;
  - no replacement of `baseline_V10.1`.
- Reuse existing market/style state, industry health, rotation pressure, and
  current stock-leg path artifacts to audit whether a top-down state model would
  explain or filter recent loss clusters.
- Produce machine-readable and human-readable evidence for:
  - market exposure state;
  - industry permission state;
  - stock execution eligibility;
  - false positives and false negatives versus current stock-leg trades.

## Non-Goals

- Do not implement a live trading strategy in this change.
- Do not change entry timing, fill timing, stock universe, PIT membership,
  ranking factor, costs, sizing, account allocation, ETF leg, or combo runtime.
- Do not use future returns, future MFE/MAE, or shadow labels as runtime inputs.
- Do not promote a new baseline.

## Impact

- Expected source:
  - `backend/research/state_driven_trend_strategy_shadow.py`
  - `research/studies/cn_stock_etf/cn_stock_state_driven_trend_strategy_shadow_v1.study.yaml`
  - focused unit tests
- Expected outputs:
  - `outputs/studies/cn_stock_etf/state_driven_trend_strategy_shadow_v1/`
- Baseline/runtime impact:
  - none
