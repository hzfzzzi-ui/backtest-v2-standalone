## Why

High Chase shadow audit showed one narrow label combination worth testing next:
`pre20_hot + turnover_hot + volume_surge`. This group had small sample size, but its realized loss was concentrated enough to justify a runtime AB. The right next step is not a hard no-buy rule; it is a default-off sizing test that reduces entry exposure and keeps the original entry/exit machinery intact.

## What Changes

- Add a research-only A2 stock-leg runtime AB: `pre20_hot + turnover_hot + volume_surge` buy size down by 50%.
- Compute A2 features from decision-date observable stock data:
  - `pre_ret_20d >= 0.50`
  - `avg_turnover_rate_f_20d >= 8.0`
  - `volume_20d_vs_60d >= 1.5`
- Apply the size-down in candidate buy planning by multiplying `order_value_scale`, not by deleting the buy signal.
- Emit diagnostic metadata for triggered and non-triggered buys so the AB can be audited after execution.
- Keep all new parameters default-off. Existing V3/B0 behavior must remain unchanged without explicit config patch.

## Capabilities

### New Capabilities

- `high-chase-a2-size-down-ab`: research-only contract for A2 high-chase activity buy size-down AB.

### Modified Capabilities

- `cn-stock-trend-alpha-core`: expose default-off A2 buy sizing parameters and runtime diagnostics while preserving baseline stock alpha behavior.

## Impact

- Source impact:
  - `backend/core/config/models.py`
  - `backend/core/engine_vector/breakout_signal_provider.py`
  - `backend/core/engine_vector/breakout_provider_day_signals.py`
  - `backend/core/portfolio/candidate_plan.py`
  - runtime adapters that pass sizing config into `build_candidate_plan`
  - targeted unit tests
- Does not change:
  - stock universe or PIT membership
  - ETF leg
  - ranking main factor
  - signal timing
  - fill timing
  - exit logic
  - baseline defaults
  - baseline promotion
