from __future__ import annotations

import json
import types
from pathlib import Path

from backend.api.endpoints import backtest_v2 as mod


def _fake_run_experiment(_cfg_path: str, preset: str, _overrides: dict, progress_hook=None) -> dict:
    if progress_hook:
        progress_hook(20, "fake-start")
    results_dir = Path(_overrides.get("_results_dir"))
    results_dir.mkdir(parents=True, exist_ok=True)

    group_a = results_dir / "groups" / "G1"
    group_b = results_dir / "groups" / "G2"
    group_a.mkdir(parents=True, exist_ok=True)
    group_b.mkdir(parents=True, exist_ok=True)
    # one existing legacy file to be converted
    (group_a / "equity_curve.csv").write_text("date,strategy_nav\n2026-01-02,1.0\n2026-01-03,1.1\n", encoding="utf-8")

    rows = [
        {
            "group_id": "G1",
            "status": "OK",
            "total_return": 0.12,
            "max_drawdown": -0.08,
            "cagr": 0.10,
            "sharpe": 1.5,
            "trades_count": 320,
            "raw_signals_total": 500,
            "blocked_signals_total": 120,
            "tradable_orders_total": 200,
            "skipped_orders_total": 15,
            "closed_trades": 180,
            "atr_stop_exit_count": 12,
            "atr_trail_exit_count": 20,
        },
        {
            "group_id": "G2",
            "status": "FAILED",
            "total_return": None,
            "max_drawdown": None,
            "cagr": None,
            "sharpe": None,
            "trades_count": 0,
        },
    ]
    return {
        "exp_id": "exp_test_001",
        "preset": preset,
        "results_dir": str(results_dir),
        "rows": rows,
        "matrix_head": rows[:1],
        "runs": [
            {"group_id": "G1", "run_id": "run_x", "status": "OK", "results_dir": str(group_a)},
            {"group_id": "G2", "run_id": "run_x", "status": "FAILED", "results_dir": str(group_b)},
        ],
    }


def test_experiment_sync_writes_manifest_and_group_files(tmp_path: Path, monkeypatch) -> None:
    bt_root = tmp_path / "backtest_V2"
    (bt_root / "configs").mkdir(parents=True, exist_ok=True)
    (bt_root / "results").mkdir(parents=True, exist_ok=True)
    (bt_root / "configs" / "pams_cn_pg.json").write_text(
        json.dumps(
            {
                "universe": {"start": "2021-01-01", "end": "2026-02-01", "benchmark": "000300.SH"},
                "strategy": {"name": "sma_cross_regime_atr", "params": {}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_bt_root", lambda: bt_root)

    fake_exp_mod = types.ModuleType("backtest_v2.tools.experiment_runner")
    fake_exp_mod.run_experiment = _fake_run_experiment  # type: ignore[attr-defined]
    fake_bundle_mod = types.ModuleType("backtest_v2.tools.bundles")
    fake_bundle_mod.run_bundle = lambda *args, **kwargs: {}  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "backtest_v2.tools.experiment_runner", fake_exp_mod)
    monkeypatch.setitem(__import__("sys").modules, "backtest_v2.tools.bundles", fake_bundle_mod)

    req = mod.BacktestV2ExperimentRequest(
        preset="G1-G4",
        start_date="2021-01-01",
        end_date="2026-02-01",
        universe_limit=50,
        fast_mode=True,
    )
    # pass result dir to fake runner via overrides side-channel
    target_results = bt_root / "results" / "experiments" / "exp_test_001"
    req.config_path = "configs/pams_cn_pg.json"

    # monkeypatch fake runner to know output dir from cfg side file not available, use deterministic dir
    monkeypatch.setattr(
        fake_exp_mod,
        "run_experiment",
        lambda cfg_path, preset, overrides, progress_hook=None: _fake_run_experiment(
            cfg_path,
            preset,
            {**overrides, "_results_dir": str(target_results)},
            progress_hook,
        ),
    )

    result = mod._run_backtest_v2_experiment_sync(req)
    manifest = Path(result["files"]["manifest"])
    assert manifest.exists()
    rows = result.get("rows") or []
    assert len(rows) == 2
    for row in rows:
        gf = row.get("group_files") or {}
        for key in ["run_meta", "perf", "nav", "funnel", "reason_codes", "config"]:
            p = target_results / gf.get(key, "")
            assert p.exists(), f"{key} missing for {row.get('group_id')}: {p}"


def test_rows_schema_numeric_or_null(tmp_path: Path, monkeypatch) -> None:
    bt_root = tmp_path / "backtest_V2"
    (bt_root / "configs").mkdir(parents=True, exist_ok=True)
    (bt_root / "results").mkdir(parents=True, exist_ok=True)
    (bt_root / "configs" / "pams_cn_pg.json").write_text(
        json.dumps({"universe": {"start": "2021-01-01", "end": "2026-02-01"}, "strategy": {"name": "x"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_bt_root", lambda: bt_root)
    fake_exp_mod = types.ModuleType("backtest_v2.tools.experiment_runner")
    fake_exp_mod.run_experiment = _fake_run_experiment  # type: ignore[attr-defined]
    fake_bundle_mod = types.ModuleType("backtest_v2.tools.bundles")
    fake_bundle_mod.run_bundle = lambda *args, **kwargs: {}  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "backtest_v2.tools.experiment_runner", fake_exp_mod)
    monkeypatch.setitem(__import__("sys").modules, "backtest_v2.tools.bundles", fake_bundle_mod)
    target_results = bt_root / "results" / "experiments" / "exp_test_002"
    monkeypatch.setattr(
        fake_exp_mod,
        "run_experiment",
        lambda cfg_path, preset, overrides, progress_hook=None: _fake_run_experiment(
            cfg_path,
            preset,
            {**overrides, "_results_dir": str(target_results)},
            progress_hook,
        ),
    )

    req = mod.BacktestV2ExperimentRequest(preset="G1-G4", universe_limit=50, fast_mode=True, config_path="configs/pams_cn_pg.json")
    result = mod._run_backtest_v2_experiment_sync(req)
    numeric_fields = [
        "total_return",
        "max_drawdown",
        "cagr",
        "sharpe",
        "trades",
        "avg_positions",
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
        "top10_profit_concentration",
    ]
    for row in result.get("rows", []):
        for f in numeric_fields:
            v = row.get(f)
            assert (v is None) or isinstance(v, (int, float)), f"{f} must be number/null, got {type(v)}"


def test_legacy_preset_alias_does_not_raise_unsupported(tmp_path: Path, monkeypatch) -> None:
    bt_root = tmp_path / "backtest_V2"
    (bt_root / "configs").mkdir(parents=True, exist_ok=True)
    (bt_root / "results").mkdir(parents=True, exist_ok=True)
    (bt_root / "configs" / "pams_cn_pg.json").write_text(
        json.dumps({"universe": {"start": "2021-01-01", "end": "2026-02-01"}, "strategy": {"name": "x"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_bt_root", lambda: bt_root)

    target_results = bt_root / "results" / "experiments" / "exp_alias"
    called: dict[str, str] = {}

    fake_exp_mod = types.ModuleType("backtest_v2.tools.experiment_runner")

    def _fake_run_experiment_alias(cfg_path, preset, overrides, progress_hook=None):
        called["preset"] = str(preset)
        return _fake_run_experiment(cfg_path, "G1-G4", {**overrides, "_results_dir": str(target_results)}, progress_hook)

    fake_exp_mod.run_experiment = _fake_run_experiment_alias  # type: ignore[attr-defined]
    fake_bundle_mod = types.ModuleType("backtest_v2.tools.bundles")
    fake_bundle_mod.run_bundle = lambda *args, **kwargs: {}  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "backtest_v2.tools.experiment_runner", fake_exp_mod)
    monkeypatch.setitem(__import__("sys").modules, "backtest_v2.tools.bundles", fake_bundle_mod)

    req = mod.BacktestV2ExperimentRequest(preset="G1-G4", universe_limit=50, fast_mode=True, config_path="configs/pams_cn_pg.json")
    result = mod._run_backtest_v2_experiment_sync(req)
    assert result.get("requested_preset") == "G1-G4"
    assert result.get("resolved_preset") == "TREND_QUALITY_VALIDATE_V1"
    assert called.get("preset") == "TREND_QUALITY_VALIDATE_V1"
