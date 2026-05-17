## ADDED Requirements

### Requirement: High Chase D5 parameters MUST preserve default stock alpha behavior
The stock trend alpha core MUST expose High Chase D5 research parameters without changing existing strategy behavior when they are not set.

#### Scenario: Strategy is built without High Chase D5 parameters
- **WHEN** a breakout trend strategy is constructed from an existing config
- **THEN** D5 confirmation exit MUST remain disabled unless explicitly enabled
- **AND** high-chase-specific scope/action parameters MUST use default values that preserve the existing D5 behavior

### Requirement: High Chase D5 sell signals MUST use existing exit priority and fill lifecycle
High Chase D5 sell signals MUST be generated after higher-priority engine exits and MUST flow through the existing order planning and fill accounting lifecycle.

#### Scenario: Higher-priority exit already exists
- **WHEN** a symbol already has a full or higher-priority sell signal on the same bar
- **THEN** High Chase D5 MUST NOT emit an additional sell signal for that symbol

#### Scenario: High Chase D5 emits a sell signal
- **WHEN** the provider emits a High Chase D5 sell signal
- **THEN** the order MUST use normal next-open execution, suspension/limit handling, cash/accounting, and trade-row recording
