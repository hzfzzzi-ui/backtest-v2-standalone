from __future__ import annotations

import json
from pathlib import Path

from backend.cli.managed.baseline_regression_check import (
    _build_baseline_request,
    _load_contract,
    _write_json_output,
    compare_experiment_dirs,
)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_exp_dir(
    root: Path,
    exp_id: str,
    *,
    cagr: float = 0.1,
    manifest_exp_id: str | None = None,
    run_meta_exp_id: str | None = None,
    include_asset_fields: bool = False,
    include_daily_enrichment: bool = False,
    strategy_name: str = "breakout_trend",
) -> Path:
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
            "strategy": {"name": strategy_name},
            **(
                {
                    "asset_scope": "cn_a_equity",
                    "asset_context": {
                        "asset_scope": "cn_a_equity",
                        "asset_profile_id": "cn_a_equity_mainline",
                    },
                }
                if include_asset_fields
                else {}
            ),
        },
    )
    _write_json(
        exp_dir / "run_meta.json",
        {
            "exp_id": run_meta_exp_id or exp_id,
            "created_at": "2026-03-08T10:00:00",
            "tier": "T0",
            "status": "OK",
            "data": {
                "start": "2024-01-01",
                "end": "2024-12-31",
                "benchmark": "000300.SH",
                **({"asset_scope": "cn_a_equity"} if include_asset_fields else {}),
            },
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
            **(
                {
                    "asset_scope": "cn_a_equity",
                    "asset_profile_id": "cn_a_equity_mainline",
                    "market_profile_id": "cn_a_mainland_equity_market",
                    "execution_profile_id": "cn_a_tplus1_next_open",
                }
                if include_asset_fields
                else {}
            ),
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
    if include_daily_enrichment:
        _write_text(
            exp_dir / "portfolio_daily.csv",
            (
                "date,nav,cash,positions_count,positions_count_end_of_day,daily_return,drawdown,"
                "gross_exposure,turnover_pct,candidates_count,selected_count,raw_buy_signal_count,"
                "buy_candidate_count,after_cash_lot_count,market_state,trade_mode,diagnostics_input_json\n"
                "2024-01-01,1.0,100.0,0,0,0.0,0.0,0.0,0.0,1,0,1,1,0,BULL,TREND_MAIN,{}\n"
                "2024-01-02,1.1,110.0,1,1,0.1,0.0,1.0,0.1,2,1,2,2,1,BULL,TREND_MAIN,{}\n"
            ),
        )
    else:
        _write_text(
            exp_dir / "portfolio_daily.csv",
            (
                "date,nav,cash,positions_count,positions_count_end_of_day,daily_return,drawdown,"
                "gross_exposure,turnover_pct,candidates_count,selected_count,raw_buy_signal_count,"
                "buy_candidate_count,after_cash_lot_count,market_state,trade_mode\n"
                "2024-01-01,1.0,100.0,0,0,0.0,0.0,0.0,0.0,1,0,1,1,0,BULL,TREND_MAIN\n"
                "2024-01-02,1.1,110.0,1,1,0.1,0.0,1.0,0.1,2,1,2,2,1,BULL,TREND_MAIN\n"
            ),
        )
    _write_text(exp_dir / "portfolio_trades.csv", "date,symbol,side,reason_code\n2024-01-02,600000.sh,BUY,BUY_SIGNAL\n")
    _write_text(exp_dir / "portfolio_candidates.csv", "date,symbol\n")
    _write_text(exp_dir / "report.html", "<html><body>report</body></html>")
    return exp_dir


def test_load_contract_has_foundation_baseline() -> None:
    contract = _load_contract(Path("backend/scripts/ops/v2_backend_refactor_baseline_contract.json"))
    assert contract["baseline_exp_id"] == "exp_20260510_034302669_7790"
    assert contract["anchor_policy"] == "current_combo_baseline_v3_after_v4_overfit_rollback"
    assert contract["current_anchor"]["baseline_id"] == "CN_STOCK_ETF_COMBO_BASELINE_V3"
    assert contract["current_anchor"]["exp_id"] == "exp_20260510_034302669_7790"
    superseded = {row["exp_id"] for row in contract["superseded_anchors"]}
    assert "exp_20260511_073506050_3d22" in superseded
    assert "exp_20260510_034302669_7790" in superseded
    assert "exp_20260509_074944369_5f6c" in superseded
    assert "exp_20260508_124555553_fabd" in superseded
    assert "exp_20260426_005716047_8650" in superseded
    missing = {row["exp_id"] for row in contract["historical_missing_anchors"]}
    assert "exp_20260314_144548534_7db9" in missing
    assert "exp_20260328_220801073_478b" in missing
    assert "portfolio_daily.csv" in dict((contract.get("protected_artifacts") or {}).get("semantic_csv") or {})


def test_current_combo_baseline_main_logic_has_regression_contract() -> None:
    contract = _load_contract(Path("backend/scripts/ops/v2_backend_refactor_baseline_contract.json"))
    protected = contract["protected_artifacts"]

    assert contract["current_anchor"]["baseline_id"] == "CN_STOCK_ETF_COMBO_BASELINE_V3"
    assert contract["baseline_exp_id"] == contract["current_anchor"]["exp_id"]
    assert set(protected["exact_file_hash"]) >= {"portfolio_trades.csv", "portfolio_candidates.csv"}
    assert set(protected["summary_json"]["perf.json"]) >= {
        "total_return",
        "max_drawdown",
        "cagr",
        "sharpe",
        "trades",
        "turnover",
    }
    assert set(protected["semantic_csv"]["portfolio_daily.csv"]["stable_fields"]) >= {
        "date",
        "nav",
        "daily_return",
        "drawdown",
        "gross_exposure",
        "market_state",
        "trade_mode",
    }
    assert set(protected["semantic_surfaces"]) >= {
        "run_meta_core",
        "run_meta_universe",
        "config_truth",
        "manifest",
    }
    assert contract["verification_command"] == "python -m backend.cli.managed.baseline_regression_check --rerun --write-to-candidate"


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


def test_compare_experiment_dirs_ignores_component_exp_id_in_trades(tmp_path: Path) -> None:
    contract = _load_contract(Path("backend/scripts/ops/v2_backend_refactor_baseline_contract.json"))
    baseline_dir = _make_exp_dir(tmp_path, "exp_baseline", cagr=0.1)
    candidate_dir = _make_exp_dir(tmp_path, "exp_candidate", cagr=0.1)
    _write_text(
        baseline_dir / "portfolio_trades.csv",
        (
            "date,symbol,side,reason_code,qty,component_exp_id\n"
            "2024-01-02,600000.sh,BUY,BUY_SIGNAL,100,exp_component_a\n"
        ),
    )
    _write_text(
        candidate_dir / "portfolio_trades.csv",
        (
            "date,symbol,side,reason_code,qty,component_exp_id\n"
            "2024-01-02,600000.sh,BUY,BUY_SIGNAL,100,exp_component_b\n"
        ),
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


def test_compare_experiment_dirs_allows_approved_asset_and_daily_schema_enrichment(tmp_path: Path) -> None:
    contract = _load_contract(Path("backend/scripts/ops/v2_backend_refactor_baseline_contract.json"))
    baseline_dir = _make_exp_dir(tmp_path, "exp_baseline", cagr=0.1)
    baseline_manifest = json.loads((baseline_dir / "manifest.json").read_text(encoding="utf-8"))
    baseline_manifest.update(
        {
            "asset_scope": "cn_a_equity",
            "asset_profile_id": "cn_a_equity_mainline",
            "market_profile_id": "cn_a_mainland_equity_market",
            "execution_profile_id": "cn_a_tplus1_next_open",
        }
    )
    (baseline_dir / "manifest.json").write_text(json.dumps(baseline_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    candidate_dir = _make_exp_dir(
        tmp_path,
        "exp_candidate",
        cagr=0.1,
        include_asset_fields=True,
        include_daily_enrichment=True,
    )

    result = compare_experiment_dirs(baseline_dir=baseline_dir, candidate_dir=candidate_dir, contract=contract)

    assert result["status"] == "PASS"
    assert result["mismatch_counts"]["total"] == 0


def test_compare_experiment_dirs_fails_on_run_config_behavior_drift(tmp_path: Path) -> None:
    contract = _load_contract(Path("backend/scripts/ops/v2_backend_refactor_baseline_contract.json"))
    baseline_dir = _make_exp_dir(tmp_path, "exp_baseline", cagr=0.1, include_asset_fields=True)
    candidate_dir = _make_exp_dir(
        tmp_path,
        "exp_candidate",
        cagr=0.1,
        include_asset_fields=True,
        strategy_name="different_strategy",
    )

    result = compare_experiment_dirs(baseline_dir=baseline_dir, candidate_dir=candidate_dir, contract=contract)

    assert result["status"] == "FAIL"
    assert any(
        diff["artifact"] == "config_truth" and diff["surface"] == "config_truth.run_config_behavior_hash"
        for diff in result["blocking_diffs"]
    )


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


def test_build_baseline_request_prefers_workbench_config_when_baseline_requested(tmp_path: Path) -> None:
    exp_dir = tmp_path / "exp_baseline"
    exp_dir.mkdir(parents=True, exist_ok=True)

    original_workbench_config = {
        "mode": "draft_run",
        "universe_mode": "CUSTOM",
        "universe": {
            "start": "2012-01-04",
            "end": "2026-03-20",
            "benchmark": "000300.SH",
            "price_adj": "hfq",
            "symbols": ["600000.SH"],
        },
        "flow_script": {
            "recommended_preset": "single",
        },
    }
    compiled_runtime = {
        "db": {"enabled": True},
        "schema_mapping": {"stocks": "pams_ohlcv_daily_v2"},
        "runtime_only": True,
    }

    _write_json(
        exp_dir / "config.json",
        {
            "overrides": {
                "config_source": "workbench_config",
                "config_id": "baseline_v10_1",
                "workbench_mode": "draft_run",
                "original_workbench_config": original_workbench_config,
            }
        },
    )
    _write_json(exp_dir / "input_config.json", {"strategy": {"name": "baseline_v10_1"}})
    _write_json(exp_dir / "compiled_plan.json", {"runtime_config": compiled_runtime})

    payload = _build_baseline_request(exp_dir)

    assert payload["config_id"] == "baseline_v10_1"
    assert "workbench_config" in payload
    assert payload["workbench_config"] == original_workbench_config
    assert "runtime_config_json" not in payload
    assert "config_json" not in payload
