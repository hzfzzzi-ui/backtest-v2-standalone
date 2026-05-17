## ADDED Requirements

### Requirement: Quality sizing ladder MUST be research-only
The quality sizing ladder AB MUST NOT mutate baseline_V10.1 or default runtime
behavior.

#### Scenario: A sizing ladder variant runs
- **WHEN** the variant is executed
- **THEN** it MUST use study-specific runtime config overrides
- **AND** it MUST NOT change live baseline directories.

### Requirement: Quality sizing ladder MUST preserve candidate ordering
Quality sizing variants MUST NOT rerank or veto candidates.

#### Scenario: Quality score differs between candidates
- **WHEN** `soft_weight` is active
- **THEN** the original V4 candidate ordering MUST remain the selection order
- **AND** quality MAY only affect order-size scaling.

### Requirement: Ladder report MUST compare band strength
The report MUST compare conservative, medium, and wide sizing bands against B0.

#### Scenario: Main-window results are summarized
- **WHEN** results are reported
- **THEN** the report MUST include CAGR, Sharpe, MaxDD, Calmar, trades, turnover,
  runtime, and a decision on whether guardrail/full windows are warranted.
