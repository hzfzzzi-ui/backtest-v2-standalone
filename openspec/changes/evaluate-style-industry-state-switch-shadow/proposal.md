## Why

Recent stock-leg research keeps converging on the same pain point: the system is
not mainly failing because it cannot find strong breakout candidates, but
because it reacts too slowly when market style leadership or held-industry
leadership has already changed.

The current runtime has market regime controls and stock-level ranking inputs,
but it does not yet expose a single auditable daily surface that answers:

- which market style is leading now;
- whether held industries are weakening;
- whether stronger candidate industries are being blocked by old holdings or
  cash limits.

This change adds a research-only shadow surface for state-switch diagnosis
before any runtime AB modifies trading behavior.

## What Changes

- Add a research-only `cn_stock_etf/cn_stock_style_industry_state_switch_shadow_v1`
  study definition.
- Add a runner that builds three daily layers:
  - `style_state`: market style leadership and risk contraction state;
  - `industry_health`: daily SW L1 industry health labels;
  - `rotation_pressure`: held-industry pressure, candidate-industry pull, and
    blocked rotation gap.
- Register the runner in `study_runner`.
- Add unit tests for data lineage, daily state computation, and output
  contracts.

## Non-Goals

- No runtime buy/sell/exposure change.
- No NAV recomputation.
- No baseline promotion.
- No direct theme-aware replacement rule.
- No new stock pool, ETF pool, or benchmark semantics.
- No frontend-side research calculation.

## Impact

- Source implementation:
  - `backend/research/style_industry_state_switch_shadow_study.py`
  - `backend/research/study_runner.py`
  - `research/studies/cn_stock_etf/cn_stock_style_industry_state_switch_shadow_v1.study.yaml`
  - `tests/unit/test_style_industry_state_switch_shadow_study.py`
- Output artifacts:
  - `outputs/studies/cn_stock_etf/cn_stock_style_industry_state_switch_shadow_v1/**`
- Unchanged:
  - `baseline_V10.1`
  - `CN_STOCK_ETF_FORMAL_V1`
  - trading runtime, signal timing, fill timing, stock/ETF pools, allocation,
    exits, account state.
