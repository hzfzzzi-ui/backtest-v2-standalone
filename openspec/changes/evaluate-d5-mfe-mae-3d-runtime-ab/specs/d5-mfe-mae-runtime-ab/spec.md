## ADDED Requirements

### Requirement: D5 runtime AB MUST use the real runtime ledger

The system MUST evaluate D5 through the normal experiment runtime so cash, orders, fills, positions, NAV, and metrics come from one execution chain.

#### Scenario: D5 creates runtime sell orders

- **WHEN** the D5 AB variant runs
- **THEN** D5 partial sells MUST be produced by the stock signal provider at runtime
- **AND** the study MUST NOT consume precomputed D5 shadow rows as executable input

### Requirement: D5 MUST be a single-variable AB study

The D5 runtime AB MUST only change the D5 MFE/MAE confirmation settings under strategy runtime parameters.

#### Scenario: Study plan is built

- **WHEN** the execution plan is generated
- **THEN** B0 and D5 MUST share the same `runtime_config_path`
- **AND** D5 MUST set `enable_mfe_mae_confirmation_exit=true`
- **AND** D5 MUST keep stock universe, ranking, entry rules, execution timing, costs, sizing, and ETF sleeve unchanged

### Requirement: D5 default behavior MUST be disabled

D5 MUST NOT affect existing backtests unless it is explicitly enabled by runtime configuration.

#### Scenario: Existing strategy is built without D5 overrides

- **WHEN** a breakout strategy/provider is constructed from existing configs
- **THEN** `enable_mfe_mae_confirmation_exit` MUST default to `false`
- **AND** no D5 sell signal MUST be emitted

### Requirement: D5 3-day rule MUST be based only on post-entry own-stock close path

D5 3-day confirmation failure MUST use adjusted close prices from the stock itself and MUST NOT depend on industry, theme, benchmark, candidate list, or precomputed shadow files.

#### Scenario: A held stock fails early confirmation

- **WHEN** the current bar is exactly 3 trading bars after entry
- **AND** close-path MFE is below `+2%`
- **AND** close-path MAE is at or below `-5%`
- **AND** no higher-priority full exit exists for that symbol on the same bar
- **THEN** D5 MUST emit a sell signal for 50% of the current position

### Requirement: D5 acceptance evidence MUST run in Docker

The acceptance evidence for this study MUST come from commands executed inside the `backtest-v2-standalone` Docker container.

#### Scenario: Dry-run and runtime run are executed

- **WHEN** Codex runs dry-run or backtest commands
- **THEN** the command MUST be executed with `docker exec backtest-v2-standalone`
- **AND** output logs SHOULD be saved under `outputs/logs`

### Requirement: D5 conclusion MUST compare same-window B0 and D5

The D5 conclusion MUST prioritize same-window B0 versus D5 metrics over baseline registry deltas.

#### Scenario: Results are analyzed

- **WHEN** B0 and D5 experiment ids are available for the same window
- **THEN** the conclusion MUST report return, CAGR, Sharpe, max drawdown, Calmar, trade count, turnover, and runtime duration deltas
- **AND** the conclusion MUST inspect whether partial sells later re-entered, freed capital for better trades, or simply reduced exposure
- **AND** the conclusion MUST state that this run is not baseline promotion evidence unless guardrail and full-audit windows are also acceptable
