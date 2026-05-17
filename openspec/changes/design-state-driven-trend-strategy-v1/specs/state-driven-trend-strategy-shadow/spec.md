## ADDED Requirements

### Requirement: State-driven trend strategy V1 MUST start as shadow-only
The first state-driven trend strategy implementation MUST be diagnostic and
MUST NOT emit runtime orders or alter baseline behavior.

#### Scenario: Shadow study is executed
- **WHEN** the state-driven trend shadow study runs
- **THEN** it MUST NOT mutate `baseline_V10.1`
- **AND** it MUST NOT change NAV, orders, fills, costs, sizing, or account state
- **AND** it MUST write outputs under `outputs/studies/`

### Requirement: State labels MUST be live-safe
The market, industry, and stock eligibility labels MUST be derived only from
same-day or prior-day data.

#### Scenario: Labels are built
- **WHEN** the shadow labels a date/symbol row
- **THEN** it MAY use current or prior market state, industry state, candidate
  state, and current stock metadata
- **AND** it MUST NOT use future return, future MFE/MAE, realized trade outcome,
  or manually selected future information as label inputs

### Requirement: Shadow audit MUST separate market, industry, and stock layers
The study MUST make clear which layer explains each blocked/reduced sample.

#### Scenario: Trade/path sample is audited
- **WHEN** a stock trade or position path is evaluated
- **THEN** the output MUST include market permission, industry permission, stock
  eligibility, and final shadow action
- **AND** the report MUST distinguish market blocks, industry blocks, reduced
  exposure cases, and allowed cases

### Requirement: Shadow conclusion MUST include false-positive and false-negative evidence
The state-driven trend shadow conclusion MUST not only count filtered losers.

#### Scenario: Results are summarized
- **WHEN** the study produces a conclusion
- **THEN** it MUST report losing samples filtered or reduced
- **AND** it MUST report winning samples that would have been filtered or reduced
- **AND** it MUST state continue, reject, or hold without proposing baseline
  promotion
