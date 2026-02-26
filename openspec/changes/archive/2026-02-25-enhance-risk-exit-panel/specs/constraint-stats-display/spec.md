## ADDED Requirements

### Requirement: Constraint trigger statistics display
The Position & Risk accordion block SHALL display a statistics row below the configuration controls, showing constraint trigger counts from the most recent run.

#### Scenario: Statistics populated after run
- **WHEN** a backtest run completes and results are loaded
- **THEN** the constraint stats row SHALL display: `avg_positions`, `slots_left`, `cap_hit_single`, `cap_hit_industry`, `cash_skip_count`, `lot_skip_count`

#### Scenario: Statistics empty before run
- **WHEN** no run results are available
- **THEN** each counter SHALL display "—" as placeholder

### Requirement: Backend supplies constraint counters
The results API response SHALL include `cap_hit_single`, `cap_hit_industry`, `slots_left`, `cash_skip_count`, and `lot_skip_count`.

#### Scenario: Counters in results response
- **WHEN** results are fetched for a completed run
- **THEN** `cash_skip_count` SHALL equal `diag_reason_counts["SKIP_CASH_INSUFFICIENT"]` (or 0)
- **THEN** `lot_skip_count` SHALL equal `diag_reason_counts["SKIP_LOT_TOO_SMALL"]` (or 0)
- **THEN** `slots_left` SHALL be computed as `max_positions - avg_positions` (rounded to 1 decimal)
- **THEN** `cap_hit_single` and `cap_hit_industry` SHALL be extracted from diag_reason_counts or default to 0
