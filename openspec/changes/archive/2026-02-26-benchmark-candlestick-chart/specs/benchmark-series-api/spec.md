## MODIFIED Requirements

### Requirement: Benchmark series API endpoint
The backend SHALL provide a `GET /api/backtest_v2/series/benchmark` endpoint that returns benchmark index time series for chart overlay, including normalized OHLC data for candlestick rendering.

#### Scenario: Successful benchmark query
- **WHEN** the frontend calls `GET /api/backtest_v2/series/benchmark?symbol=000300.SH&start=2024-01-01&end=2024-12-31`
- **THEN** the response SHALL be `200 OK` with body `{"points": [{"date": "...", "nav": ..., "open": ..., "high": ..., "low": ..., "close": ...}, ...], "source": "api"}`
- **THEN** the `nav` values SHALL be normalized to the first trading day's close price (first day nav = 1.0)
- **THEN** the `open`, `high`, `low`, `close` values SHALL all be normalized to the first trading day's close price
- **THEN** the `close` normalized value SHALL equal the `nav` value for the same date

#### Scenario: Benchmark symbol not found in database
- **WHEN** the requested symbol does not exist in `pit_index_daily` or fallback tables
- **THEN** the response SHALL be `200 OK` with body `{"points": [], "source": "empty"}`

#### Scenario: Missing query parameters
- **WHEN** `symbol`, `start`, or `end` query parameters are missing
- **THEN** the response SHALL be `422 Unprocessable Entity` with validation error details

#### Scenario: Database connection failure
- **WHEN** the database is unreachable during the benchmark query
- **THEN** the response SHALL be `503 Service Unavailable` with body `{"detail": "database connection failed"}`

#### Scenario: First day OHLC data has zero or null close
- **WHEN** the first trading day's close price is 0 or null
- **THEN** the response SHALL be `200 OK` with body `{"points": [], "source": "empty"}`
