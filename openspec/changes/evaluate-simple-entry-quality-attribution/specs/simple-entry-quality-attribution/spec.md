## ADDED Requirements

### Requirement: Entry quality attribution MUST be research-only
The entry quality attribution MUST run as an isolated shadow study and MUST
NOT mutate formal baseline or production runtime behavior.

#### Scenario: Attribution study is executed
- **WHEN** the study runs
- **THEN** it MUST write outputs under `outputs/studies/`
- **AND** it MUST NOT alter strategies, signals, fills, account state, or
  portfolio construction.

### Requirement: Entry buckets MUST use entry-time information only
The attribution buckets MUST be derived only from information observable at the
entry date.

#### Scenario: Entry factors are computed
- **WHEN** an entry is classified
- **THEN** buckets MUST use historical price, volume, liquidity, and PIT
  membership data available at entry time
- **AND** buckets MUST NOT use future return, future MFE/MAE, realized PnL, or
  sell reason.

### Requirement: Outcomes MUST be labels for attribution
Future path metrics MUST be recorded only as labels for analysis.

#### Scenario: Outcome labels are computed
- **WHEN** the study computes forward return, MFE, MAE, or realized holding
  result
- **THEN** those values MUST be stored as outcome labels
- **AND** they MUST NOT be used to define entry buckets.

### Requirement: Attribution MUST cover single and paired factors
The study MUST summarize both one-factor buckets and selected two-factor
crosses.

#### Scenario: Results are summarized
- **WHEN** the study completes
- **THEN** it MUST report sample count, median/mean forward return, MFE, MAE,
  realized return where available, and loss-tail metrics
- **AND** it MUST include both single-factor and pair-factor summaries.

### Requirement: Composite entry risk labels MUST remain descriptive
Composite entry risk labels MUST be used only for attribution and MUST NOT
become trading rules in this study.

#### Scenario: Risk labels are assigned
- **WHEN** an entry receives composite risk labels
- **THEN** labels MUST be derived only from entry-time buckets
- **AND** labels MUST record which visible risk shapes are present
- **AND** labels MUST NOT use future return, future MFE/MAE, realized PnL, or
  sell reason.

### Requirement: Position mapping shadow MUST be counterfactual only
The position mapping shadow MUST evaluate whether descriptive risk labels can
explain exposure risk, without changing production portfolio construction.

#### Scenario: Position mapping shadow is executed
- **WHEN** entry risk tiers are mapped to smaller weights
- **THEN** the mapping MUST be fixed before the run and based only on entry-time
  risk tiers
- **AND** unused exposure MUST remain cash
- **AND** the shadow MUST report return, drawdown, turnover proxy, average
  exposure, and same-window comparison to the unscaled source study
- **AND** it MUST NOT mutate baseline configs, production ranking, exits, fills,
  or account state.
