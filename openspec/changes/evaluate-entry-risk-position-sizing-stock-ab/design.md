## Rule Contract

The AB tests a position sizing rule, not a selection or exit rule.

Default risk tier mapping:

- `0_low`: risk flag count <= 0, multiplier 1.0.
- `1_watch`: risk flag count == 1, multiplier 0.8.
- `2_high`: risk flag count == 2, multiplier 0.5.
- `3_plus_extreme`: risk flag count >= 3, multiplier 0.3333333333.

The risk flag count comes from existing decision-date formal entry archetype
features:

- recent own-stock return rank;
- distance to MA60 rank;
- volatility rank;
- turnover/crowding rank;
- fade or open-gap rank.

These are cross-sectional ranks among current buy candidates on the same
decision date. They are not outcome labels.

## Execution Semantics

When enabled, a normal buy signal receives:

- `entry_risk_position_sizing_enabled`;
- `entry_risk_position_tier`;
- `entry_risk_position_flag_count`;
- `entry_risk_position_multiplier`.

The candidate planner then multiplies the normal `order_value_scale` by the
entry-risk multiplier. This preserves the existing sizing chain, including rank
tilts and score-weight adjustments.

The candidate remains in the same ranked buy list. Lot sizing, cash feasibility,
and execution orders continue through the existing pipeline. Unused exposure is
not redistributed to other candidates.

Restore/top-up candidate signals keep their existing delta target semantics and
are not modified by this AB.

## Audit

The conclusion must compare the enabled AB against the same-window stock-leg
control with at least:

- total return;
- CAGR;
- Sharpe;
- max drawdown;
- Calmar;
- turnover or trade count;
- average exposure or average positions when available;
- number of buys by tier.

## Risks

- Rank-based entry archetypes are more relative than the simple absolute labels;
  good results must be treated as a formal-runtime candidate, not direct proof of
  the simple labels.
- Lower position size can mechanically improve drawdown while reducing upside.
- If the control window differs, the comparison is not decisive.
