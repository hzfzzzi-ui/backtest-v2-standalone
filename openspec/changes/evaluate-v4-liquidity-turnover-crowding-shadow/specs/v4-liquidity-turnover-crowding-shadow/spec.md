## ADDED Requirements

### Requirement: Liquidity turnover crowding shadow MUST be research-only
The liquidity/turnover crowding audit MUST NOT alter production strategy,
ranking, entry, exit, account, or portfolio behavior.

#### Scenario: Shadow audit is executed
- **WHEN** the audit runs
- **THEN** it MUST write outputs under `outputs/analysis/`
- **AND** it MUST NOT mutate formal baselines or runtime configuration.

### Requirement: Entry labels MUST use only pre-entry data
Liquidity, turnover, acceleration, and position labels MUST be computed using
data observable on or before the signal date.

#### Scenario: Entry factors are joined
- **WHEN** a factor row is assigned to a BUY entry
- **THEN** the price/liquidity observation date MUST be on or before the signal
  date
- **AND** future return, realized PnL, or exit information MUST NOT influence
  the label.

### Requirement: Percentile scope MUST be explicit
Signal-pool percentile labels MUST document that the pool is selected BUY rows
plus logged candidate rows, not a full-market cross section.

#### Scenario: Report is written
- **WHEN** the human report describes percentile labels
- **THEN** it MUST identify the percentile scope and its limitation.

### Requirement: Outcomes MUST remain attribution labels
Realized trade return, forward return, and TOP50 profit/loss membership MUST be
used only for evaluation, not for factor construction.

#### Scenario: Bucket summaries are written
- **WHEN** summaries are computed
- **THEN** they MAY group by later outcomes
- **BUT** the labels themselves MUST remain entry-time labels.

### Requirement: Complete composite shadow MUST keep factor families separate
The complete shadow MUST expose quality, trend/position, volatility, and
liquidity/turnover labels separately before reporting any composite label.

#### Scenario: Composite report is written
- **WHEN** a composite risk label is reported
- **THEN** the report MUST also include the component label coverage
- **AND** it MUST state that composite thresholds are descriptive shadow labels,
  not promoted trading parameters.

### Requirement: Hot amount/turnover AB MUST only alter order sizing
The hot amount/turnover AB MUST keep entry, exit, ranking, market state,
execution timing, costs, and ETF behavior unchanged.

#### Scenario: Hot amount/turnover size-down is enabled
- **WHEN** a CN stock BUY candidate has both `amount20_pct >= 0.8` and
  `turnover_rate20_pct >= 0.8` within the same day's eligible BUY candidate
  pool
- **THEN** the candidate planner MAY multiply that candidate's
  `order_value_scale` by the configured size-down scale
- **AND** it MUST NOT veto the candidate or reorder candidates.

#### Scenario: Hot amount/turnover size-down is disabled
- **WHEN** the default configuration is used
- **THEN** runtime behavior MUST match the existing baseline sizing path.
