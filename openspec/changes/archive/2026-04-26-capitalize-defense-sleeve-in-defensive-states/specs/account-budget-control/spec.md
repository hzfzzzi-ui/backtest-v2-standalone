## MODIFIED Requirements

### Requirement: Account defensive-state budgets MUST map to a capital-real defense sleeve
Account-layer defensive-state budgets MUST map to a defense sleeve that exists in the governed ETF formal allocation scope, not only in explain metadata or transition-only execution.

#### Scenario: account budget enters defensive states
- **WHEN** account budget effective state is `TRANS_DOWN` or `RISK_OFF`
- **THEN** the governed ETF sleeve MUST be able to persist defense capital in the configured defense asset
- **AND** the configured defense asset MUST match formal ETF limited-defense scope
