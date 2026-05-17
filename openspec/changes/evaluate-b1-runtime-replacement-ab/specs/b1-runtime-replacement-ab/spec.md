## ADDED Requirements

### Requirement: B1 runtime replacement AB MUST use the real runtime ledger

The system MUST evaluate B1 through the normal experiment runtime so cash, orders, fills, positions, NAV, and metrics come from one execution chain.

#### Scenario: B1 creates runtime orders

- **WHEN** the B1 variant runs
- **THEN** replacement sells and buys MUST be produced by runtime candidate planning
- **AND** the study MUST NOT consume a precomputed shadow daily plan as executable input

### Requirement: B1 MUST be a single-variable control study

The B1 runtime control MUST only change replacement settings under `sizing.rotation_replace_*`.

#### Scenario: Study plan is built

- **WHEN** the execution plan is generated
- **THEN** B0 and B1 MUST share the same `runtime_config_path`
- **AND** B1 MUST set `rotation_replace_enabled=true`
- **AND** B1 MUST keep stock universe, ranking, entry rules, exit rules, execution timing, and costs unchanged

### Requirement: B1 MUST run in Docker for acceptance evidence

The acceptance evidence for this study MUST come from commands executed inside the `backtest-v2-standalone` Docker container.

#### Scenario: Dry-run and runtime run are executed

- **WHEN** Codex runs dry-run or backtest commands
- **THEN** the command MUST be executed with `docker exec backtest-v2-standalone`
- **AND** output logs SHOULD be saved under `outputs/logs`

### Requirement: B1 conclusion MUST compare same-window B0 and B1

The B1 conclusion MUST prioritize same-window B0 versus B1 metrics over baseline registry deltas.

#### Scenario: Results are analyzed

- **WHEN** B0 and B1 experiment ids are available for the same window
- **THEN** the conclusion MUST report return, CAGR, Sharpe, max drawdown, Calmar, trade count, turnover, and runtime duration deltas
- **AND** the conclusion MUST state that this run is not baseline promotion evidence unless guardrail and full-audit windows are also acceptable
