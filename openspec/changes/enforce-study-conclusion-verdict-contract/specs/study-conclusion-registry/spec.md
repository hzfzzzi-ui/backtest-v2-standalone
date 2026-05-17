## ADDED Requirements

### Requirement: conclusion verdict MUST use formal research outcome enum

Study conclusion registry MUST write formal research outcomes in `verdict`. New records SHALL only use `confirmed`, `falsified`, or `inconclusive` for `verdict`. Runtime hard-gate values such as `PASS` and `FAIL` MUST NOT be written as canonical `verdict`.

#### Scenario: hard gate pass but study direction is not accepted
- **WHEN** a study run passes execution hard gates but same-window compare shows the candidate materially worse than the compared baseline
- **THEN** the registry MUST write `verdict = "falsified"` or `verdict = "inconclusive"`
- **THEN** the registry MUST NOT write `verdict = "PASS"`

#### Scenario: hard gate pass and study direction is accepted
- **WHEN** a study run passes execution hard gates and same-window compare supports the study hypothesis
- **THEN** the registry MUST write `verdict = "confirmed"`
- **THEN** the hard-gate result MUST remain available outside canonical `verdict`

### Requirement: conclusion registry MUST preserve hard gate status separately

Study conclusion registry MUST preserve execution hard-gate information in fields separate from canonical research verdict. At minimum, a new conclusion record MUST include `gate_status`; when available, it SHOULD also include `gate_reason` and `gate_checks`.

#### Scenario: write a conclusion from a PASS hard gate
- **WHEN** the study runner receives a hard-gate payload with `status = "PASS"`
- **THEN** the registry MUST write `gate_status = "PASS"`
- **THEN** the registry MUST still derive canonical `verdict` from research outcome semantics

#### Scenario: read a conclusion record
- **WHEN** a caller reads a conclusion record
- **THEN** the caller MUST be able to distinguish canonical research `verdict` from execution `gate_status`
