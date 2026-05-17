## ADDED Requirements

### Requirement: Runtime stage timing artifact

The experiment runtime SHALL write a run performance artifact that records wall-clock seconds for major runtime stages without changing strategy metrics.

#### Scenario: Single run writes timing profile

- **WHEN** a standard `run_experiment()` call completes successfully
- **THEN** `run_profile.json` is written under the experiment result directory
- **AND** the profile includes `total_wall_seconds` and `stage_seconds`
- **AND** `run_meta.json` includes a sanitized runtime profile summary

### Requirement: OHLCV cache isolation

The OHLCV cache SHALL be isolated by resolved market-data table and mapping contract.

#### Scenario: Stock and ETF providers use distinct cache files

- **WHEN** one provider resolves to an A-share daily table and another resolves to the CN ETF daily table
- **THEN** their table-level parquet cache paths are distinct
- **AND** rebuilding one cache does not overwrite the other

### Requirement: OHLCV slice cache

The OHLCV cache SHALL support a default slice mode keyed by resolved table, date window, and normalized symbol set.

#### Scenario: Repeated identical slice load hits local cache

- **GIVEN** a provider loads OHLCV for a fixed table, start/end window, and symbol set
- **WHEN** the same normalized request is loaded again
- **THEN** the second request reads from the slice parquet cache
- **AND** does not call PostgreSQL for the OHLCV rows again
