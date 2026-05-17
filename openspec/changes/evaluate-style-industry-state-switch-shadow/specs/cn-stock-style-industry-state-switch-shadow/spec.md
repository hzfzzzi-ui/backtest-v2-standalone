## ADDED Requirements

### Requirement: Style and industry state-switch shadow MUST be research-only

The system MUST provide a
`cn_stock_etf/cn_stock_style_industry_state_switch_shadow_v1` study that audits
market style leadership, industry weakening, and rotation pressure without
modifying runtime behavior, NAV, baseline, stock pool, ETF pool, ranking
factors, execution timing, allocation, or exits.

#### Scenario: Study result is written

- **WHEN** the runner completes a window
- **THEN** the run output MUST include `research_only=true`
- **THEN** the run output MUST include `not_nav_backtest=true`
- **THEN** the run output MUST not claim baseline promotion

### Requirement: Market style shadow MUST emit auditable daily style state

For each study window, the runner MUST emit a daily market style panel using the
style index history available in `pit_index_daily`.

#### Scenario: Daily style state is computed

- **WHEN** `000300.SH`, `000905.SH`, and `000852.SH` histories are available
- **THEN** the runner MUST compute daily raw style features and a daily
  `style_state_label`
- **THEN** outputs MUST preserve the raw component scores used to derive the
  label

### Requirement: Industry health shadow MUST emit daily SW L1 health labels

For each study window, the runner MUST emit daily SW L1 industry health rows
from SW L1 industry index history and sleeve context.

#### Scenario: Industry health is weak

- **WHEN** an industry meets the configured weakness persistence rules
- **THEN** the row MUST be labeled `watch` or `confirmed_weak`

#### Scenario: Industry health recovers

- **WHEN** a previously weak industry meets the configured recovery rules
- **THEN** the row MUST return to `healthy`

### Requirement: Rotation pressure shadow MUST quantify held-vs-candidate gap

The runner MUST emit a daily rotation-pressure layer joining held exposure,
candidate strength, and blocked-entry evidence.

#### Scenario: Stronger industries are blocked

- **WHEN** stronger candidate industries are present but entries are blocked by
  cash or capacity while held industries remain weak
- **THEN** the runner MUST record a non-null `blocked_rotation_gap` signal and
  persist the underlying evidence

### Requirement: State-switch shadow MUST mark coverage quality

The runner MUST mark coverage quality and MUST avoid overclaiming the result
when required style or industry index coverage is missing or partial for a
window.

#### Scenario: Coverage is partial

- **WHEN** any required style or industry index series is unavailable for part
  of a window
- **THEN** the output MUST mark the window `partial` or `inconclusive`
- **THEN** the report MUST state that the result is suitable for diagnosis, not
  baseline promotion
