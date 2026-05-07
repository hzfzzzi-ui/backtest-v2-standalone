## ADDED Requirements

### Requirement: Shared risk-on to defensive transition completes defense establish
The shared account execution runtime MUST, on `risk_on -> defensive` transition edges, connect released cash to a defense establish buy action for the configured defense symbol.

#### Scenario: shared transition release activates
- **WHEN** the shared transition owner activates on a `risk_on -> defensive` edge
- **THEN** it emits sell-first release orders
- **AND** it emits a defense establish buy signal for the defense symbol using released cash
- **AND** the execution path is recorded as shared-account-owned transition execution

#### Scenario: defense position already exists
- **WHEN** the configured defense symbol is already held
- **THEN** shared transition defense establish MAY top up the held defense position
- **AND** candidate planning MUST not reject it as `ALREADY_HELD`
