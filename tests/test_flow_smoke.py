"""End-to-end smoke flow test.

Exercises the full backtest data path through real DB + HTTP API:
  1. DB health check (benchmark API)
  2. Launch experiment (run_async)
  3. Poll to success
  4. Verify artifacts (flat result structure)
  5. Benchmark overlay (NAV normalization)
  6. Config save/load roundtrip

Run with:  pytest -m smoke
"""
from __future__ import annotations

import time
from typing import Any

import pytest
from starlette.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.smoke

# ---------------------------------------------------------------------------
# Smoke config: 3 stocks × 3 months, G1-G4 preset
# Mirrors the builtin _flow_script_config_json()
# ---------------------------------------------------------------------------
SMOKE_CONFIG: dict[str, Any] = {
    "mode": "experiment",
    "strategy_pack": "SMA_CROSS",
    "universe_mode": "CUSTOM",
    "universe": {
        "start": "2025-01-01",
        "end": "2025-03-31",
        "benchmark": "000300.SH",
        "symbols": ["600000.SH", "000001.SZ", "600519.SH"],
        "limit": 100,
        "filters": {
            "exclude_st": True,
            "exclude_suspended": True,
            "min_list_days": 120,
            "min_avg_turnover_20d": 100000000,
            "limit_rule": "skip",
        },
    },
    "signal_generation": {
        "enabled": True,
        "strategy": "SMA_CROSS",
        "sma": {"fast_ma": 5, "slow_ma": 20, "entry_buffer_pct": 1.0},
    },
    "signal_composition": {"enabled": True, "compose_mode": "WEIGHTED_SCORE"},
    "exit_rules": {
        "enabled": True,
        "signal_reverse": True,
        "atr_stop": {"enabled": True, "k": 0.8},
        "trailing": {"enabled": False, "k": 2.0},
    },
    "position_risk": {
        "enabled": True,
        "max_positions": 10,
        "single_stock_cap": 0.1,
        "industry_cap": 0.3,
        "lot": 100,
        "cash_shortage_policy": "skip",
    },
    "flow_script": {
        "script_id": "flow_smoke_v1",
        "description": "smoke flow test",
        "recommended_preset": "G1-G4",
    },
}

_POLL_INTERVAL_S = 2
_POLL_TIMEOUT_S = 120

# ---------------------------------------------------------------------------
# Module-scoped shared state: passes job_id / result between steps
# ---------------------------------------------------------------------------

_flow_state: dict[str, Any] = {}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def flow_state():
    return _flow_state


# ---------------------------------------------------------------------------
# Step 1: DB health check
# ---------------------------------------------------------------------------


def test_step_1_db_health_check(client: TestClient, flow_state: dict):
    """Verify DB is reachable by fetching a short benchmark series."""
    resp = client.get(
        "/api/backtest_v2/series/benchmark",
        params={"symbol": "000300.SH", "start": "2025-01-01", "end": "2025-01-31"},
    )
    assert resp.status_code == 200, f"benchmark API returned {resp.status_code}: {resp.text}"
    body = resp.json()
    points = body.get("points", [])
    assert len(points) > 0, "DB health check failed: benchmark returned 0 points"
    flow_state["db_healthy"] = True


# ---------------------------------------------------------------------------
# Step 2: Launch experiment
# ---------------------------------------------------------------------------


def test_step_2_launch_experiment(client: TestClient, flow_state: dict):
    """POST experiment/run_async and capture job_id."""
    assert flow_state.get("db_healthy"), "Skipped: DB health check did not pass"

    resp = client.post(
        "/api/backtest_v2/experiment/run_async",
        json={
            "preset": "G1-G4",
            "symbols": SMOKE_CONFIG["universe"]["symbols"],
            "start_date": SMOKE_CONFIG["universe"]["start"],
            "end_date": SMOKE_CONFIG["universe"]["end"],
            "benchmark": SMOKE_CONFIG["universe"]["benchmark"],
            "config_path": "configs/pams_cn_pg.json",
            "workbench_config": SMOKE_CONFIG,
        },
    )
    assert resp.status_code == 200, f"run_async returned {resp.status_code}: {resp.text}"
    body = resp.json()
    job_id = body.get("job_id")
    assert job_id, f"run_async response missing job_id: {body}"
    flow_state["job_id"] = job_id


# ---------------------------------------------------------------------------
# Step 3: Poll to success
# ---------------------------------------------------------------------------


def test_step_3_poll_to_success(client: TestClient, flow_state: dict):
    """Poll job status until terminal state; assert success."""
    job_id = flow_state.get("job_id")
    assert job_id, "Skipped: no job_id from step 2"

    deadline = time.monotonic() + _POLL_TIMEOUT_S
    last_status = "unknown"
    last_pct = 0

    while time.monotonic() < deadline:
        resp = client.get(f"/api/backtest_v2/jobs/{job_id}")
        assert resp.status_code == 200, f"job poll returned {resp.status_code}"
        body = resp.json()
        last_status = body.get("status", "unknown")
        last_pct = body.get("progress_pct", 0)

        if last_status == "success":
            flow_state["job_result"] = body.get("result", {})
            return
        if last_status in ("failed", "canceled"):
            error = body.get("error") or body.get("message") or "no detail"
            pytest.fail(f"experiment {last_status}: {error}")

        time.sleep(_POLL_INTERVAL_S)

    pytest.fail(
        f"timeout after {_POLL_TIMEOUT_S}s — last status: {last_status} ({last_pct}%)"
    )


# ---------------------------------------------------------------------------
# Step 4: Verify artifacts
# ---------------------------------------------------------------------------


def test_step_4_verify_artifacts(client: TestClient, flow_state: dict):
    """Check experiment result uses flat single-run schema."""
    result = flow_state.get("job_result", {})
    assert result, "Skipped: no job_result from step 3"

    assert "rows" not in result, "flat result should not include rows[]"
    assert result.get("status") == "OK", f"unexpected status: {result.get('status')!r}"

    for field in ("sharpe", "max_drawdown", "cagr"):
        val = result.get(field)
        assert val is not None, f"missing top-level field: {field}"
        assert isinstance(val, (int, float)), f"{field} is not numeric ({val!r})"

    artifacts = result.get("artifacts", {})
    assert isinstance(artifacts, dict), "result.artifacts should be a dict"
    for key in ("perf", "nav", "funnel", "reason_codes", "config", "run_meta"):
        assert artifacts.get(key), f"result.artifacts missing '{key}'"


# ---------------------------------------------------------------------------
# Step 5: Benchmark overlay
# ---------------------------------------------------------------------------


def test_step_5_benchmark_overlay(client: TestClient, flow_state: dict):
    """Verify benchmark API returns normalized NAV for the run date range."""
    resp = client.get(
        "/api/backtest_v2/series/benchmark",
        params={
            "symbol": SMOKE_CONFIG["universe"]["benchmark"],
            "start": SMOKE_CONFIG["universe"]["start"],
            "end": SMOKE_CONFIG["universe"]["end"],
        },
    )
    assert resp.status_code == 200, f"benchmark API returned {resp.status_code}"
    body = resp.json()
    points = body.get("points", [])
    assert len(points) > 0, "benchmark overlay returned 0 points"

    first_nav = points[0].get("nav")
    assert first_nav is not None, "first point missing nav"
    assert abs(float(first_nav) - 1.0) < 0.001, f"first NAV not normalized: {first_nav}"

    # dates should be ascending
    dates = [p["date"] for p in points]
    assert dates == sorted(dates), "benchmark dates not in ascending order"


# ---------------------------------------------------------------------------
# Step 6: Config roundtrip
# ---------------------------------------------------------------------------


def test_step_6_config_roundtrip(client: TestClient, flow_state: dict):
    """Save config → load config → deep equal."""
    resp = client.post(
        "/api/backtest_v2/configs",
        json={
            "config_json": SMOKE_CONFIG,
            "name": "smoke_flow_test",
            "tags": ["flow_test", "smoke"],
        },
    )
    assert resp.status_code == 200, f"config save returned {resp.status_code}: {resp.text}"
    body = resp.json()
    cfg_id = body.get("config_id")
    assert cfg_id, f"config save response missing config_id: {body}"

    resp2 = client.get(f"/api/backtest_v2/configs/{cfg_id}")
    assert resp2.status_code == 200, f"config load returned {resp2.status_code}"
    loaded = resp2.json()

    loaded_json = loaded.get("config_json", {})
    assert loaded_json == SMOKE_CONFIG, (
        f"config roundtrip mismatch: saved config_id={cfg_id}"
    )
