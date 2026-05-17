## ADDED Requirements

### Requirement: A2 sizing parameters MUST preserve default stock alpha behavior
The stock trend alpha core MUST expose A2 research sizing parameters without changing existing strategy behavior when they are not enabled.

#### Scenario: Strategy is built without A2 sizing parameters
- **WHEN** an existing stock runtime config is executed
- **THEN** A2 size-down MUST be disabled by default
- **AND** buy signal generation, ranking, order planning, fill timing, and exit timing MUST remain unchanged

### Requirement: A2 metadata MUST be auditable at buy execution
The stock runtime MUST preserve enough A2 metadata on executed buys to audit which trades were size-adjusted.

#### Scenario: A2 buy order is created
- **WHEN** a buy order is emitted after candidate planning
- **THEN** the order metadata MUST include A2 trigger state, configured thresholds, observed feature values, and applied scale
