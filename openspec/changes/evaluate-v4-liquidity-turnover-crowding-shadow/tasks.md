## 1. Contract

- [x] 1.1 Create OpenSpec change.
- [x] 1.2 Define proposal, design, requirements, and tasks.
- [x] 1.3 Validate OpenSpec.

## 2. Implementation

- [x] 2.1 Add research-only liquidity/turnover shadow script.
- [x] 2.2 Compute signal-pool percentiles for amount, turnover, accelerations,
  and position.
- [x] 2.3 Generate all-BUY bucket summaries and TOP50 coverage.

## 3. Verification

- [x] 3.1 Run Docker shadow audit on V4/B0 stock-leg anchor.
- [x] 3.2 Inspect output coverage, sample counts, and report.

## 4. Reporting

- [x] 4.1 Separate facts from interpretation.
- [x] 4.2 State whether this should proceed to AB.
- [x] 4.3 Do not promote any trading rule.

## Notes

- Docker audit completed for `exp_20260516_224942916_8830`.
- Coverage: 320 BUY entries, 4985 logged signal-pool rows, 320 matched entries.
- Single liquidity/turnover tags are not strong enough for AB. `hot_turnover`
  only improved loss TOP50 coverage by 3.3 percentage points versus profit
  TOP50. `turnover_surge` and `amount_surge` covered profit TOP50 more than
  loss TOP50.
- Continue only with narrower composite shadow: high amount/turnover plus high
  position, quality, and volatility.

## 5. Complete Composite Shadow

- [x] 5.1 Extend shadow with quality and volatility labels.
- [x] 5.2 Generate component and composite coverage tables.
- [x] 5.3 Run Docker complete shadow.
- [x] 5.4 Update report with complete-shadow conclusion.

## Complete Shadow Notes

- Docker complete shadow completed for `exp_20260516_224942916_8830`.
- Coverage: 320 BUY entries, 4985 signal-pool rows, 320 liquidity/volatility
  matches, 288 quality matches.
- Best risk image: `hot_amount_turnover` with 47 entries, realized median
  -5.59%, fwd60 median -13.84%, loss TOP50 coverage 26.47% versus profit TOP50
  coverage 16.67%.
- Composite `3of5` and `4of5` also look adverse, but they are less plain and
  should remain shadow until a simpler rule is tested.
- Recommended next AB, if any: stock-leg only, `hot_amount_turnover` light
  size-down, no veto, no parameter search.

## 6. Hot Amount/Turnover Size-Down AB

- [x] 6.1 Add research-only sizing config and runtime hook.
- [x] 6.2 Emit PIT-safe amount20 and turnover_rate20 features into stock BUY
  signal meta only when the hook is enabled.
- [x] 6.3 Add focused unit coverage for candidate-level size-down.
- [x] 6.4 Add stock-only study YAML.
- [x] 6.5 Run Docker validation and main-window AB.
- [x] 6.6 Compare against same-window B0 and report whether guardrail/full
  audit is warranted.

## AB Contract Notes

- This AB must not change entry signal, exit signal, candidate ordering, market
  state, ETF leg, costs, or execution timing.
- The trigger is `amount20_pct >= 0.8` and `turnover_rate20_pct >= 0.8` within
  the same day's eligible BUY candidate pool.
- The action is order-value size-down only: `order_value_scale *= 0.8`.
- No veto, no promotion, and no parameter search in this round.

## AB Result Notes

- Same-window Docker main-window B0:
  `exp_20260517_014120602_426b`, CAGR 18.77%, Sharpe 0.833,
  MaxDD -26.25%, Calmar 0.715, trades 651.
- Hot amount/turnover 0.8 size-down:
  `exp_20260517_014120601_4807`, CAGR 18.33%, Sharpe 0.821,
  MaxDD -29.20%, Calmar 0.628, trades 641.
- Versus B0, the AB worsened CAGR by 0.43 percentage points, Sharpe by
  0.013, MaxDD by 2.96 percentage points, and Calmar by 0.087.
- The rule triggered 55 BUY orders out of 316 BUY orders in the AB run. The
  triggered orders were mostly high-ranked candidates: median final-score rank
  2, with 37 of 55 ranked top 3 and 46 of 55 ranked top 5.
- Do not continue to guardrail/full audit for this exact hard size-down. The
  shadow label finds a real risk cluster, but the simple action cuts too many
  strong winners.
