## ADDED Requirements
### Requirement: Unified combo must emit account-layer daily state fields
The unified combo runtime MUST emit non-empty account-layer daily state fields whenever component daily frames are available, even if the incoming combo payload omits an explicit `account_budget_control` block.

#### Scenario: omitted account_budget_control still yields account-layer state output
- **WHEN** unified combo runs with stock and ETF component daily artifacts available
- **AND** `unified_runtime.account_budget_control` is omitted
- **THEN** the runtime synthesizes enabled account-budget control with 50/50 fallback weights
- **AND** `portfolio_daily.csv` writes non-empty `account_budget_effective_state_5`
- **AND** the state source is account-layer, not reference-only fallback
