## MODIFIED Requirements

### Requirement: Shared risk-on to defensive transition completes defense establish
The shared account execution runtime MUST, on `risk_on -> defensive` transition edges, connect released cash to a defense establish buy action for the configured defense symbol. The defense establish behavior MUST be parameterized by the active research tuning variant, including which defensive edge states can trigger the buy action and whether an existing defense position may be topped up.

#### Scenario: shared transition release activates
- **WHEN** the shared transition owner activates on a `risk_on -> defensive` edge
- **AND** the edge target state is included in the active `defense establish` tuning variant
- **THEN** it emits sell-first release orders
- **AND** it emits a defense establish buy signal for the defense symbol using released cash
- **AND** the execution path is recorded as shared-account-owned transition execution

#### Scenario: defense position already exists
- **WHEN** the configured defense symbol is already held
- **AND** the active tuning variant allows `top_up_existing_defense`
- **THEN** shared transition defense establish MAY top up the held defense position
- **AND** candidate planning MUST not reject it as `ALREADY_HELD`

#### Scenario: edge state not in active variant
- **WHEN** the shared transition owner activates on a `risk_on -> defensive` edge
- **AND** the edge target state is not included in the active tuning variant
- **THEN** the system SHALL NOT emit a defense establish buy signal
- **AND** sell-first release behavior MAY still continue independently
