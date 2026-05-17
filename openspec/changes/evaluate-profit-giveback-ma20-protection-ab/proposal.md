## Why

Recent stock-leg path audits show that the 2025 computer drag was not mainly
an immediate failed breakout. Several names entered after strong prior gains,
kept meaningful unrealized profit for a while, then gave back sharply after
price structure broke below MA20. The current D5 research knob focuses on
early post-entry failure and does not test this later profit-protection case.

## What Changes

- Add a research-only stock-leg AB for peak-giveback plus MA20-break protection.
- Introduce default-off strategy params for a partial exit when:
  - the position has reached a minimum peak profit;
  - the current close has given back enough from that peak;
  - the close is below MA20;
  - a minimum holding age is satisfied.
- Keep stock universe, PIT membership, ranking, entry rules, execution timing,
  costs, sizing, market regime, ETF leg, and combo allocator unchanged.
- Run same-window comparisons against a stock-leg B0 replay before discussing
  combo or baseline impact.

## Non-Goals

- Do not promote a baseline.
- Do not use future MFE/MAE, shadow labels, industry/theme labels, or hand-picked
  symbols as runtime inputs.
- Do not change entry logic, ranking logic, stock pool, ETF pool, or account
  allocator behavior.
- Do not combine this with D5, industry health, theme health, or market-breadth
  rule changes in the same primary AB.

## Impact

- Runtime source:
  - `backend/core/strategies/breakout_trend.py`
  - `backend/core/strategies/registry.py`
  - `backend/core/engine_vector/breakout_signal_provider.py`
  - `backend/core/engine_vector/breakout_provider_day_signals.py`
  - `backend/core/engine_vector/breakout_provider_models.py`
  - `backend/core/engine_vector/multi_alpha_signal_provider.py`
- Research surface:
  - `research/studies/cn_stock_etf/cn_stock_profit_giveback_ma20_protection_ab_v1.study.yaml`
  - existing stock-rule/combo AB runner where possible
- Tests:
  - strategy-param preservation tests
  - exit trigger tests
  - study planning tests
