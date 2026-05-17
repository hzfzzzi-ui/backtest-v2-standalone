## Context

The previous High Chase shadow audit separated price/activity labels on realized stock trades. A2 is the narrow activity-heavy label `pre20_hot + turnover_hot + volume_surge`. It is only an exploratory hypothesis because the sample count is small and thresholds came from an audit. Therefore the implementation must be default-off, same-runtime, and reversible.

## Goals / Non-Goals

**Goals:**

- Test whether reducing initial exposure for A2-labeled buys improves risk-adjusted stock-leg results.
- Use only decision-date observable own-stock data.
- Keep the buy signal, ranking, order planning, fill accounting, NAV, and exits in the normal runtime chain.
- Provide enough meta/debug output to count triggered buys and compare realized impact.

**Non-Goals:**

- Do not ban A2 buys.
- Do not add industry/theme conditions.
- Do not change stock pool, PIT membership, ranking, entry timing, exit timing, or ETF logic.
- Do not promote A2 to a baseline in this change.

## Decisions

### 1. A2 label is computed at signal time

The signal provider materializes three matrices aligned to trading date and symbol:

- 20-day adjusted close return.
- 20-day average `turnover_rate_f`, falling back to `turnover_rate` when needed.
- 20-day average volume divided by 60-day average volume.

These values are attached to buy signal meta. Missing values make the A2 label false.

### 2. A2 action is a sizing multiplier

The candidate planner evaluates the label and, when enabled, multiplies the existing `order_value_scale` by `high_chase_a2_size_down_scale` before quantity and cash-aware feasibility are calculated.

This keeps the original signal and ranking visible while testing whether lower exposure is enough to improve drawdown or loss contribution.

### 3. Diagnostics are part of the execution evidence

Runtime meta/debug output must include:

- whether A2 size-down is enabled;
- whether the current buy triggered A2;
- feature values and thresholds;
- the applied size-down scale.

## Risks / Trade-offs

- [Risk] Thresholds are audit-derived and may overfit. Mitigation: keep default-off and require same-window B0/A2 comparison before interpretation.
- [Risk] Size-down can reduce both losses and future winners. Mitigation: compare CAGR, max drawdown, Calmar, Sharpe, turnover/trade count, and triggered trade contribution.
- [Risk] Missing turnover data can silently reduce trigger coverage. Mitigation: missing features produce no trigger and are visible in diagnostics.
