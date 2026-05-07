## ADDED Requirements
### Requirement: Defensive states must maintain a formal defense exposure floor
The ETF weak-state formal allocation MUST expose and consume a minimum defense exposure floor in `TRANS_DOWN` and `RISK_OFF` so the formal defense asset is capital-real rather than edge-only.

#### Scenario: defensive floor emitted from formal weak-state targets
- **WHEN** ETF exposure semantics resolves `TRANS_DOWN` or `RISK_OFF`
- **THEN** it emits `minimum_defense_exposure_floor`
- **AND** the floor is greater than zero
- **AND** it is aligned with the formal limited-defense bucket implied by weak-state targets

#### Scenario: weak-state execution consumes defense floor
- **WHEN** ETF runtime is in `TRANS_DOWN` or `RISK_OFF`
- **AND** current defense exposure is below the emitted floor
- **THEN** weak-state deploy attempts to close the defense gap using formal defense symbols
- **AND** defense persistence does not rely only on transition-edge establish orders
