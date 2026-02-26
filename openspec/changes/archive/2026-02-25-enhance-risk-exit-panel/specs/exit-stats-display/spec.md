## ADDED Requirements

### Requirement: Exit trigger statistics display
The Exit accordion block SHALL display a statistics row below the configuration controls, showing exit trigger counts from the most recent run.

#### Scenario: Statistics populated after run
- **WHEN** a backtest run completes and results are loaded for the active group
- **THEN** the Exit stats row SHALL display: `reversal_exit_count`, `atr_stop_exit_count`, `atr_trail_exit_count`, `atr_trail_update_count`, `time_exit_count`
- **THEN** each counter SHALL show its label and numeric value

#### Scenario: Statistics empty before run
- **WHEN** no run results are available
- **THEN** each counter SHALL display "—" as placeholder

### Requirement: ATR caliber note
The Exit accordion block SHALL display a read-only ATR caliber note showing the ATR computation parameters derived from current configuration.

#### Scenario: ATR note reflects current settings
- **WHEN** the user views the Exit block
- **THEN** the note SHALL display: ATR window (14日), price adjustment (read from Universe 价格口径 setting), and trigger price (read from Universe 成交价假设 setting)

#### Scenario: ATR note updates on config change
- **WHEN** the user changes 价格口径 or 成交价假设 in the Universe module
- **THEN** the ATR note in Exit block SHALL update to reflect the new values

### Requirement: Checkbox-input linkage
Inputs associated with optional exit strategies SHALL be disabled when their corresponding checkbox is unchecked.

#### Scenario: Trail input disabled
- **WHEN** "移动止盈" checkbox (wbExitTrail) is unchecked
- **THEN** the `trail_k` input (wbTrailK) SHALL be disabled and visually dimmed
- **THEN** the `trail_k` label SHALL show unit annotation "×ATR"

#### Scenario: Trail input enabled
- **WHEN** "移动止盈" checkbox is checked
- **THEN** the `trail_k` input SHALL be enabled and editable

#### Scenario: Time exit input disabled
- **WHEN** "时间退出" checkbox (wbExitTime) is unchecked
- **THEN** the `N days` input (wbExitDays) SHALL be disabled and visually dimmed

#### Scenario: Time exit input enabled
- **WHEN** "时间退出" checkbox is checked
- **THEN** the `N days` input SHALL be enabled and editable

#### Scenario: Initial state matches defaults
- **WHEN** the page first loads with default config (wbExitTrail unchecked, wbExitTime unchecked)
- **THEN** both `trail_k` and `N days` inputs SHALL be disabled

### Requirement: Backend supplies reversal and time exit counts
The results API response SHALL include `reversal_exit_count` and `time_exit_count` fields.

#### Scenario: Counters present in results
- **WHEN** results are fetched for a completed run via `/api/backtest_v2/results/{run_id}`
- **THEN** the response SHALL contain `reversal_exit_count` (integer) counting sell orders triggered by signal reversal
- **THEN** the response SHALL contain `time_exit_count` (integer) counting sell orders triggered by time-based exit

#### Scenario: Counters default to zero when unavailable
- **WHEN** the underlying run data does not contain explicit reversal/time exit reason codes
- **THEN** both counters SHALL default to 0
