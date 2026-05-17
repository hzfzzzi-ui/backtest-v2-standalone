## ADDED Requirements

### Requirement: Quality ranking AB MUST be research-only
The fundamental quality ranking AB MUST NOT mutate formal V4 or baseline_V10.1
behavior.

#### Scenario: AB variant is executed
- **WHEN** the quality ranking AB runs
- **THEN** it MUST use a study variant/config override
- **AND** it MUST NOT change the live baseline directory or default runtime
  config.

### Requirement: Quality overlay MUST use PIT-safe daily snapshots
The AB MUST use only quality values observable by the decision date.

#### Scenario: Daily quality snapshot is built
- **WHEN** a symbol/date quality value is emitted
- **THEN** its source fundamental row MUST have `ann_date <= date`
- **AND** the output MUST include the source `ann_date` and `end_date`
- **AND** future announcements MUST NOT be visible.

### Requirement: First AB MUST not hard-veto low quality
The first quality ranking AB MUST avoid hard low-quality vetoes.

#### Scenario: Candidate quality is weak
- **WHEN** a candidate has low quality
- **THEN** the first AB MAY lower its ranking priority through overlay ordering
- **AND** it MUST NOT automatically block the candidate solely because quality
  is low.

### Requirement: Trading semantics MUST remain fixed
The AB MUST preserve the existing V4 stock trading semantics except for
candidate ordering.

#### Scenario: Variant config is applied
- **WHEN** a quality overlay variant runs
- **THEN** stock universe, entry signal rules, exit rules, market state,
  execution timing, costs, and base sizing MUST match B0
- **AND** only the candidate ranking overlay configuration may differ.

### Requirement: Same-window comparison MUST include risk metrics
The AB report MUST compare return and risk, not only CAGR.

#### Scenario: Results are reported
- **WHEN** AB output is summarized
- **THEN** it MUST include CAGR, MaxDD, Calmar where available, trade count or
  buy count, and drawdown/loss-tail interpretation.
