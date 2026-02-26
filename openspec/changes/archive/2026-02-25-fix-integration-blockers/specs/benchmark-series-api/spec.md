## ADDED Requirements

### Requirement: Benchmark series API endpoint
The backend SHALL provide a `GET /api/backtest_v2/series/benchmark` endpoint that returns benchmark index NAV time series for chart overlay.

#### Scenario: Successful benchmark query
- **WHEN** the frontend calls `GET /api/backtest_v2/series/benchmark?symbol=000300.SH&start=2024-01-01&end=2024-12-31`
- **THEN** the response SHALL be `200 OK` with body `{"points": [{"date": "...", "nav": ...}, ...], "source": "api"}`
- **THEN** the `nav` values SHALL be normalized to the first trading day's close price (first day nav = 1.0)

#### Scenario: Benchmark symbol not found in database
- **WHEN** the requested symbol does not exist in `pit_index_daily` or fallback tables
- **THEN** the response SHALL be `200 OK` with body `{"points": [], "source": "empty"}`

#### Scenario: Missing query parameters
- **WHEN** `symbol`, `start`, or `end` query parameters are missing
- **THEN** the response SHALL be `422 Unprocessable Entity` with validation error details

#### Scenario: Database connection failure
- **WHEN** the database is unreachable during the benchmark query
- **THEN** the response SHALL be `503 Service Unavailable` with body `{"detail": "database connection failed"}`
