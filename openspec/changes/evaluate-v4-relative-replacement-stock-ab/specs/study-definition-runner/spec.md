## ADDED Requirements

### Requirement: V4 stock relative replacement AB study

The system SHALL provide a research-only stock-leg AB study that compares the promoted V4 stock runtime against an atomic relative replacement variant without changing universe, entry, exit, ranking, execution timing, costs, or ETF behavior.

#### Scenario: Build V4 stock replacement execution plan

- **GIVEN** the study id `cn_stock_etf/cn_stock_v4_relative_replacement_stock_ab_v1`
- **WHEN** the study runner builds the `1626` execution plan
- **THEN** the plan SHALL contain exactly `B0_V4_STOCK_REPLAY` and `REL_REPLACE_GAP005_TOP5`
- **AND** both variants SHALL use `outputs/baselines/baseline_V10_1/run_config.json`
- **AND** the candidate variant SHALL only patch `runtime_config_json.sizing` replacement controls
- **AND** the candidate variant SHALL keep the study stock-only.
