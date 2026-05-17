## ADDED Requirements

### Requirement: Fundamental quality shadow MUST be research-only
The fundamental quality study MUST run as an isolated shadow audit and MUST NOT
mutate formal baseline or production runtime behavior.

#### Scenario: Shadow audit is executed
- **WHEN** the study runs
- **THEN** it MUST write outputs under `outputs/studies/`
- **AND** it MUST NOT alter strategies, signals, fills, account state, ranking,
  exits, or portfolio construction.

### Requirement: Fundamental inputs MUST be PIT-safe
Fundamental quality buckets MUST use only data observable at or before the
entry signal date.

#### Scenario: Fundamental rows are joined to entries
- **WHEN** a quality row is selected for an entry
- **THEN** its observation date MUST be on or before the entry signal date
- **AND** it MUST have financial-period lineage such as report/end period
- **AND** rows without a defensible observation date MUST NOT be used for
  factor scoring.

### Requirement: Imported fundamental quality rows MUST preserve announcement lineage
Imported fundamental quality data MUST preserve both the announcement date and
financial period date.

#### Scenario: Fundamental quality rows are imported
- **WHEN** rows are written from Tushare `fina_indicator`
- **THEN** `ann_date` MUST be stored as the observation date
- **AND** `end_date` MUST be stored as the financial reporting period
- **AND** imported fields MUST be limited to plain quality components needed by
  the first shadow score.

### Requirement: Missing quality coverage MUST block scoring
The study MUST fail closed when PIT-safe quality data is unavailable or too
sparse.

#### Scenario: Coverage is insufficient
- **WHEN** no candidate table satisfies the PIT quality contract
- **THEN** the study MUST emit `DATA_BLOCKED`
- **AND** it MUST explain the missing fields and row coverage
- **AND** it MUST NOT backfill from current snapshots, display labels, or
  non-PIT data.

### Requirement: Quality score MUST be simple and explainable
The first quality score MUST use plain profitability, margin, cashflow, and
leverage components only.

#### Scenario: Quality score is computed
- **WHEN** usable PIT data exists
- **THEN** higher profitability, higher margin, stronger cashflow conversion,
  and lower leverage MUST improve the score
- **AND** valuation, industry, theme, liquidity, and momentum MUST NOT enter
  this factor.

### Requirement: Outcomes MUST remain attribution labels
Future return and realized trade outcome MUST be used only to evaluate buckets,
not to define the quality factor.

#### Scenario: Bucket summaries are written
- **WHEN** entry quality buckets are summarized
- **THEN** the output MUST include sample count and later outcomes
- **AND** future outcomes MUST NOT influence the assigned quality bucket.
