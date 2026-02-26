## 1. Pytest Configuration

- [x] 1.1 Register `smoke` marker in `pytest.ini` and add `addopts = -m "not smoke"` to exclude from default runs

## 2. Shared State Fixture

- [x] 2.1 Create `tests/test_flow_smoke.py` with module-scoped `_flow_state` dict fixture and `test_client` usage
- [x] 2.2 Define `SMOKE_CONFIG` constant matching the builtin flow script config (3 stocks, 2025-01-01~2025-03-31, G1-G4 preset)

## 3. Test Steps

- [x] 3.1 Implement `test_step_1_db_health_check` — GET benchmark API, assert 200 + points non-empty
- [x] 3.2 Implement `test_step_2_launch_experiment` — POST experiment/run_async with SMOKE_CONFIG, capture job_id into flow_state
- [x] 3.3 Implement `test_step_3_poll_to_success` — poll jobs/{job_id} at 2s interval, 120s timeout, assert success, capture run_id
- [x] 3.4 Implement `test_step_4_verify_artifacts` — GET results/{run_id}, assert groups non-empty, verify perf/nav/funnel/reason_codes structure
- [x] 3.5 Implement `test_step_5_benchmark_overlay` — GET benchmark API with run date range, assert points non-empty + first nav ≈ 1.0
- [x] 3.6 Implement `test_step_6_config_roundtrip` — POST configs save, GET configs load, assert deep equality
