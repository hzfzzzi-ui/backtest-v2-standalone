## ADDED Requirements

### Requirement: Strong quality AB MUST remain research-only
The strong quality AB MUST NOT mutate formal V4 or baseline_V10.1 behavior.

#### Scenario: Strong quality variant is executed
- **WHEN** a strong quality AB variant runs
- **THEN** it MUST use study-specific config overrides
- **AND** it MUST NOT change live baseline directories or default runtime config.

### Requirement: Strong quality AB MUST preserve trend entry eligibility
Quality MUST NOT create standalone buy candidates.

#### Scenario: Quality score is high
- **WHEN** a stock has a high quality score but no V4 trend buy signal
- **THEN** the AB MUST NOT create a buy signal solely from quality.

### Requirement: Quality veto variants MUST be explicit stress variants
Any low-quality veto MUST be labeled as a veto/stress variant and compared
against B0 before being considered for further research.

#### Scenario: Candidate is in the low quality tail
- **WHEN** a veto variant blocks the candidate
- **THEN** candidate diagnostics MUST record the overlay veto mode and reject
  reason
- **AND** the report MUST check whether large winners were missed.

### Requirement: Same-window comparison MUST include risk and churn
The strong quality AB report MUST compare return, risk, and trading behavior.

#### Scenario: Results are summarized
- **WHEN** AB output is reported
- **THEN** it MUST include CAGR, MaxDD, Calmar or Sharpe when available, trade
  count, turnover or buy count, and a short interpretation of missed-winner risk.
