## 1. Database Exception Module

- [x] 1.1 Create `backend/core/data/errors.py` with `DatabaseError` base class, `DatabaseConnectionError`, and `DatabaseQueryError` (each carrying `message` and `context` dict)
- [x] 1.2 Wrap `PostgresDataProvider._conn()` to catch `psycopg.OperationalError` and raise `DatabaseConnectionError` with host/port context
- [x] 1.3 Wrap `PostgresDataProvider._exec_df()` to catch query errors and raise `DatabaseQueryError` with table name and query type from `audit_meta`
- [x] 1.4 Handle statement timeout in `_exec_df()` — detect timeout error and raise `DatabaseQueryError` with timeout message

## 2. Benchmark Series API Endpoint

- [x] 2.1 Add `GET /api/backtest_v2/series/benchmark` route in `backtest_v2.py` with `symbol`, `start`, `end` query params
- [x] 2.2 Call `PostgresDataProvider.load_benchmark_daily()`, normalize NAV to first day close, return `{points, source}` format
- [x] 2.3 Handle empty result (symbol not found) — return `{points: [], source: "empty"}`
- [x] 2.4 Handle `DatabaseConnectionError` — return 503 with `{detail: "database connection failed"}`

## 3. Test Infrastructure

- [x] 3.1 Add `pytest>=7.4.0`, `pytest-cov>=4.0.0`, `pytest-asyncio>=0.21.0` to `backend/requirements.txt`
- [x] 3.2 Create `pytest.ini` at project root with `testpaths = tests` and `asyncio_mode = auto`
- [x] 3.3 Create `tests/conftest.py` with `test_client` fixture (FastAPI TestClient) and `mock_db_provider` fixture (returns configurable DataFrames)

## 4. Job Cancel UI

- [x] 4.1 In `pollJob()`, change Run button text to "取消运行" and apply danger style when polling starts
- [x] 4.2 On cancel button click, send `POST /api/backtest_v2/jobs/{job_id}/cancel`, exit polling loop, display "已取消" in `wbRunStatus`
- [x] 4.3 Revert Run button to original text and style when job completes (success, failed, or canceled)
