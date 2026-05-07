## Added Requirements

### Requirement: Multi-alpha constants must have a formal owner
Shared multi-alpha constants MUST live in a formal `frontend/assets/js/state/` module rather than the legacy `backtest_v2.js` shell.

#### Scenario: Downstream scripts consume formal constants surface
- **WHEN** desktop frontend scripts need multi-alpha compose constants
- **THEN** they read them from a dedicated formal constants module
- **AND** `backtest_v2.js` does not define those constants
