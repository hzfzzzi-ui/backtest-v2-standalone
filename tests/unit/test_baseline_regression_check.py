from __future__ import annotations

import json
from pathlib import Path

from backend.scripts.baseline_regression_check import _load_contract, _write_json_output, compare_experiment_dirs


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_exp_dir(root: Path, exp_id: str, *, cagr: float = 0.1, manifest_exp_id: str | None = None, run_meta_exp_id: str | None = None) -> Path:
    exp_dir = root / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        exp_dir / "config.json",
        {
            "overrides": {
                "config_source": "runtime_config_json",
                "config_conflict_policy": "config_id_provenance_only",
            }
        },
    )
    _write_json(
        exp_dir / "run_config.json",
        {
            "universe": {"start": "2024-01-01", "end": "2024-12-31", "benchmark": "000300.SH"},
            "strategy": {"name": "breakout_trend"},
        },
    )
    _write_json(
        exp_dir / "run_meta.json",
        {
            "exp_id": run_meta_exp_id or exp_id,
            "created_at": "2026-03-08T10:00:00",
            "tier": "T0",
            "status": "OK",
            "data": {"start": "2024-01-01", "end": "2024-12-31", "benchmark": "000300.SH"},
            "code": {"engine_mode": "VECTOR_FAST_STRICT", "fast_mode": True},
            "counters": {
                "avg_positions": 5.0,
                "max_positions": 10,
                "raw_signal": 10,
                "blocked": 0,
                "orders": 4,
                "skipped": 0,
                "closed_trades": 2,
                "atr_stop_exit_count": 1,
                "atr_trail_exit_count": 1,
                "time_exit_count": 0,
                "take_profit_exit_count": 0,
                "fixed_stop_loss_exit_count": 0,
                "buy_stage_funnel": [],
            },
            "report_consistency": {
                "sources": {"start": "run_config.universe.start"},
                "fallbacks": {"start": False},
                "resolved_config_meta": {"saved_at": "2026-03-08T07:45:15.446340"},
            },
            "universe": {
                "universe_mode": "HS300_ZZ500",
                "symbols_source": "pit_index_constituents",
                "raw_count": 800,
                "constituents_load_status": "OK",
                "load_table": "pit_index_constituents",
                "index_code": "000906.SH",
                "as_of": "2024-01-01",
                "resolve_asof": "2024-01-01",
                "dynamic_all_a_entry": False,
                "filters_config": {"price_min": 5},
                "excluded_counts": {},
                "tradable_symbols": 519,
                "after_filters_symbols": 519,
            },
        },
    )
    _write_json(
        exp_dir / "manifest.json",
        {
            "exp_id": manifest_exp_id or exp_id,
            "status": "OK",
            "created_at": "2026-03-08T10:01:00",
            "artifacts": {
                "perf": "perf.json",
                "nav": "nav.csv",
                "trades": "portfolio_trades.csv",
                "daily": "portfolio_daily.csv",
            },
            "metrics": {
                "total_return": 0.25,
                "max_drawdown": -0.1,
                "cagr": cagr,
                "sharpe": 1.1,
                "trades": 4,
                "turnover": 0.2,
            },
        },
    )
    _write_json(
        exp_dir / "perf.json",
        {
            "total_return": 0.25,
            "max_drawdown": -0.1,
            "cagr": cagr,
            "sharpe": 1.1,
            "calmar": 1.0,
            "trades": 4,
            "turnover": 0.2,
        },
    )
    _write_text(exp_dir / "nav.csv", "date,nav\n2024-01-01,1.0\n2024-01-02,1.1\n")
    _write_text(exp_dir / "portfolio_daily.csv", "date,nav\n2024-01-01,1.0\n2024-01-02,1.1\n")
    _write_text(exp_dir / "portfolio_trades.csv", "date,symbol,side,reason_code\n2024-01-02,600000.sh,BUY,BUY_SIGNAL\n")
    _write_text(exp_dir / "portfolio_candidates.csv", "date,symbol\n")
    _write_text(exp_dir / "report.html", "<html><body>report</body></html>")
    return exp_dir


def test_load_contract_has_foundation_baseline() -> None:
    contract = _load_contract(Path("backend/scripts/ops/v2_backend_refactor_baseline_contract.json"))
    assert contract["baseline_exp_id"] == "exp_20260308_021045840_cde0"
    assert "portfolio_daily.csv" in list((contract.get("protected_artifacts") or {}).get("exact_file_hash") or [])


def test_compare_experiment_dirs_passes_with_allowed_drift(tmp_path: Path) -> None:
    contract = _load_contract(Path("backend/scripts/ops/v2_backend_refactor_baseline_contract.json"))
    baseline_dir = _make_exp_dir(tmp_path, "exp_baseline", cagr=0.1)
    candidate_dir = _make_exp_dir(
        tmp_path,
        "exp_candidate",
        cagr=0.1,
        manifest_exp_id="exp_candidate",
        run_meta_exp_id="exp_candidate",
    )

    result = compare_experiment_dirs(baseline_dir=baseline_dir, candidate_dir=candidate_dir, contract=contract)

    assert result["status"] == "PASS"
    assert result["mismatch_counts"]["total"] == 0


def test_compare_experiment_dirs_fails_on_perf_drift_and_writes_report(tmp_path: Path) -> None:
    contract = _load_contract(Path("backend/scripts/ops/v2_backend_refactor_baseline_contract.json"))
    baseline_dir = _make_exp_dir(tmp_path, "exp_baseline", cagr=0.1)
    candidate_dir = _make_exp_dir(tmp_path, "exp_candidate", cagr=0.2)

    result = compare_experiment_dirs(baseline_dir=baseline_dir, candidate_dir=candidate_dir, contract=contract)
    _write_json_output(result, candidate_dir / "baseline_compare.json")

    assert result["status"] == "FAIL"
    assert result["mismatch_counts"]["blocking"] >= 1
    written = json.loads((candidate_dir / "baseline_compare.json").read_text(encoding="utf-8"))
    assert written["status"] == "FAIL"
    assert written["candidate_exp_id"] == "exp_candidate"


def test_write_json_output_updates_manifest_with_baseline_compare(tmp_path: Path) -> None:
    candidate_dir = _make_exp_dir(tmp_path, "exp_candidate", cagr=0.1)
    for name in ("input_config.json", "resolved_config.json", "compiled_plan.json"):
        _write_text(candidate_dir / name, "{}")

    _write_json_output({"status": "WARN", "candidate_exp_id": "exp_candidate"}, candidate_dir / "baseline_compare.json")

    manifest = json.loads((candidate_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "backtest_v2_experiment_manifest@2"
    assert manifest["baseline_compare_status"] == "WARN"
    assert manifest["artifacts"]["baseline_compare"] == "baseline_compare.json"
    assert manifest["config_snapshots"] == {
        "input_config": "input_config.json",
        "resolved_config": "resolved_config.json",
        "compiled_plan": "compiled_plan.json",
    }
