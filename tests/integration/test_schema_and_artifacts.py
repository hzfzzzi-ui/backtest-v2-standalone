from __future__ import annotations

import ast
import json
import math
import sys
import types
from pathlib import Path

import pytest

from backend.api.endpoints import backtest_v2 as router_mod
from backend.api.endpoints.backtest_v2_artifacts import discover_group_dirs


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def test_discover_group_dirs_priority_and_ambiguous_fallback(tmp_path: Path) -> None:
    root = tmp_path / "exp"
    g_row = root / "groups" / "G1"
    g_run = root / "run_g2"
    g_row.mkdir(parents=True, exist_ok=True)
    g_run.mkdir(parents=True, exist_ok=True)
    (g_row / "perf.json").write_text("{}", encoding="utf-8")
    (g_run / "report_summary.json").write_text("{}", encoding="utf-8")

    # unique fallback candidate for G3
    g3 = root / "nested" / "G3_bucket"
    g3.mkdir(parents=True, exist_ok=True)
    (g3 / "perf.json").write_text("{}", encoding="utf-8")

    rows = [{"group_id": "G1", "group_dir": str(g_row)}]
    runs = [{"group_id": "G2", "results_dir": str(g_run)}]
    mapping = discover_group_dirs(results_dir=root, rows=rows, runs=runs, group_ids=["G1", "G2", "G3"])
    assert mapping["G1"] == g_row
    assert mapping["G2"] == g_run
    assert mapping["G3"] == g3

    # ambiguous fallback for G4 must raise
    g4a = root / "x1" / "G4_hit_a"
    g4b = root / "x2" / "G4_hit_b"
    g4a.mkdir(parents=True, exist_ok=True)
    g4b.mkdir(parents=True, exist_ok=True)
    (g4a / "perf.json").write_text("{}", encoding="utf-8")
    (g4b / "report_summary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        discover_group_dirs(results_dir=root, rows=rows, runs=runs, group_ids=["G4"])
    msg = str(exc.value)
    assert "G4" in msg
    assert "candidate" in msg.lower()
    # deterministic conflict must print candidate list for direct diagnosis.
    marker = "candidates="
    assert marker in msg
    candidates_text = msg.split(marker, 1)[1].strip()
    candidates = set(ast.literal_eval(candidates_text))
    assert candidates == {str(g4a), str(g4b)}


def _fake_run_experiment(_cfg_path: str, preset: str, overrides: dict, progress_hook=None) -> dict:
    if progress_hook:
        progress_hook(10, "fake-run")
    results_dir = Path(str(overrides["_results_dir"]))
    results_dir.mkdir(parents=True, exist_ok=True)
    g1 = results_dir / "groups" / "G1"
    g2 = results_dir / "groups" / "G2"
    g1.mkdir(parents=True, exist_ok=True)
    g2.mkdir(parents=True, exist_ok=True)

    # G1: equity_curve source exists but lacks nav/strategy_nav; must fallback to equity.
    (g1 / "equity_curve.csv").write_text(
        "dt,equity\n2026-01-02,1.0\n2026-01-03,1.1\n",
        encoding="utf-8",
    )

    # G2: no nav source, no funnel/reason/atr trigger counters.
    rows = [
        {
            "group_id": "G1",
            "status": "OK",
            "total_return": 0.1,
            "max_drawdown": -0.08,
            "cagr": 0.09,
            "sharpe": 1.2,
            "trades_count": 320,
            "raw_signals_total": 500,
            "blocked_signals_total": 100,
            "tradable_orders_total": 210,
            "skipped_orders_total": 20,
            "closed_trades": 180,
        },
        {
            "group_id": "G2",
            "status": "OK",
            "total_return": 0.02,
            "max_drawdown": -0.05,
            "cagr": 0.01,
            "sharpe": 0.2,
            "trades_count": 20,
        },
    ]
    return {
        "exp_id": "exp_schema_case",
        "preset": preset,
        "results_dir": str(results_dir),
        "rows": rows,
        "matrix_head": rows[:1],
        "runs": [
            {"group_id": "G1", "run_id": "run_g1", "status": "OK", "results_dir": str(g1)},
            {"group_id": "G2", "run_id": "run_g2", "status": "OK", "results_dir": str(g2)},
        ],
    }


def test_run_sync_schema_and_artifacts_contract(tmp_path: Path, monkeypatch) -> None:
    bt_root = tmp_path / "backtest_V2"
    (bt_root / "configs").mkdir(parents=True, exist_ok=True)
    (bt_root / "results").mkdir(parents=True, exist_ok=True)
    _write_json(
        bt_root / "configs" / "pams_cn_pg.json",
        {
            "universe": {"start": "2021-01-01", "end": "2026-02-01", "benchmark": "000300.SH"},
            "strategy": {"name": "sma_cross_regime_atr", "params": {}},
        },
    )
    monkeypatch.setattr(router_mod, "_bt_root", lambda: bt_root)

    fake_exp_mod = types.ModuleType("backtest_v2.tools.experiment_runner")
    fake_bundle_mod = types.ModuleType("backtest_v2.tools.bundles")
    fake_bundle_mod.run_bundle = lambda *args, **kwargs: {}
    target_results = bt_root / "results" / "experiments" / "exp_schema_case"
    fake_exp_mod.run_experiment = lambda cfg, preset, ov, progress_hook=None: _fake_run_experiment(
        cfg, preset, {**ov, "_results_dir": str(target_results)}, progress_hook
    )
    monkeypatch.setitem(sys.modules, "backtest_v2.tools.experiment_runner", fake_exp_mod)
    monkeypatch.setitem(sys.modules, "backtest_v2.tools.bundles", fake_bundle_mod)

    req = router_mod.BacktestV2ExperimentRequest(
        preset="G1-G4",
        start_date="2021-01-01",
        end_date="2026-02-01",
        universe_limit=50,
        fast_mode=True,
        config_path="configs/pams_cn_pg.json",
    )
    result = router_mod._run_backtest_v2_experiment_sync(req)

    # Root artifacts
    assert result.get("exp_id") == "exp_schema_case"
    assert isinstance(result.get("rows"), list)
    results_dir = Path(str(result.get("results_dir") or ""))
    assert results_dir.exists(), f"results_dir not found: {results_dir}"
    manifest = results_dir / "manifest.json"
    assert manifest.exists()
    manifest_obj = json.loads(manifest.read_text(encoding="utf-8-sig"))
    assert isinstance(manifest_obj.get("groups"), list)
    rows = list(result.get("rows") or [])
    assert int(manifest_obj.get("groups_count") or -1) == len(rows), "manifest.groups_count must equal len(rows)"

    # Row schema + required files
    required_base = ["group_id", "status", "tier", "group_dir", "group_files"]
    required_numeric = [
        "total_return",
        "max_drawdown",
        "cagr",
        "sharpe",
        "calmar",
        "trades",
        "turnover",
        "top10_profit_concentration",
        "raw_signal",
        "blocked",
        "orders",
        "skipped",
        "closed_trades",
        "gate_on_rate",
        "mf_rank_applied_rate",
        "trend_slope_block_count",
        "atr_stop_exit_count",
        "atr_trail_exit_count",
        "atr_trail_update_count",
    ]
    assert len(rows) == 2
    for row in rows:
        missing = [k for k in required_base + required_numeric if k not in row]
        assert not missing, f"missing required row keys: {missing}"
        assert isinstance(row.get("group_id"), str)
        assert row.get("status") in {"OK", "FAILED", "CANCELED"}
        assert row.get("tier") in {"T0", "T1", "T2", "T3"}
        # rows must be strict JSON-safe payload: no PowerShell @{...}, no NaN/Inf.
        for _, raw_v in row.items():
            if isinstance(raw_v, str):
                assert not raw_v.strip().startswith("@{"), f"row contains PowerShell object string: {raw_v}"
        for key in required_numeric:
            v = row.get(key)
            assert v is None or isinstance(v, (int, float)), f"{key} must be number/null"
            if isinstance(v, float):
                assert not math.isnan(v), f"{key} must not be NaN"
                assert not math.isinf(v), f"{key} must not be Inf"
        gf = dict(row.get("group_files") or {})
        row_group_dir = results_dir / str(row.get("group_dir") or "")
        assert row_group_dir.exists(), f"group_dir not found: {row_group_dir}"
        required_files = {
            "run_meta": "run_meta.json",
            "perf": "perf.json",
            "nav": "nav.csv",
            "funnel": "funnel.csv",
            "reason_codes": "reason_code_counts.csv",
            "config": "config.json",
        }
        for name, expected_file in required_files.items():
            p = results_dir / str(gf.get(name, ""))
            assert p.exists(), f"missing file {name}: {p}"
            assert p.parent.resolve() == row_group_dir.resolve(), f"{name} must live under group_dir"
            assert p.name == expected_file, f"{name} file name drift: expected {expected_file}, got {p.name}"

    # G2 has no sources => must mark precise missing_fields in run_meta
    g2 = next(x for x in rows if x.get("group_id") == "G2")
    g2_meta_path = results_dir / str(g2["group_files"]["run_meta"])
    g2_meta = json.loads(g2_meta_path.read_text(encoding="utf-8-sig"))
    missing = set(g2_meta.get("missing_fields") or [])
    assert "missing_nav_source" in missing
    assert "missing_funnel_source" in missing
    assert "missing_reason_code_source" in missing
    assert "missing_atr_trigger_counters" in missing

    # result must be strict json serializable
    json.dumps(result, ensure_ascii=False)
