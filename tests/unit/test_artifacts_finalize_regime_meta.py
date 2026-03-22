from __future__ import annotations

import json

from backend.api.backtest_v2.artifacts_finalize import ensure_standard_artifacts


def test_ensure_standard_artifacts_writes_regime_engine_snapshot(tmp_path) -> None:
    results_dir = tmp_path / "exp_regime"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "portfolio_daily.csv").write_text(
        "date,nav\n2026-03-02,1.0\n2026-03-03,1.1\n",
        encoding="utf-8",
    )
    (results_dir / "run_config.json").write_text(
        json.dumps(
            {
                "universe": {"start": "2026-03-02", "end": "2026-03-03", "benchmark": "000300.SH"},
                "regime_engine": {
                    "engine": "market_regime_framework",
                    "benchmark": "000300.SH",
                    "fallback": {
                        "on_feature_unavailable": "ma200_legacy",
                        "required_blocks": ["trend_block", "risk_block"],
                        "emit_feature_availability": True,
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    base_cfg = {
        "universe": {"start": "2026-03-02", "end": "2026-03-03", "benchmark": "000300.SH"},
        "data_source": {"data_role": "v1"},
        "schema_mapping": {},
        "regime_engine": {
            "engine": "market_regime_framework",
            "benchmark": "000300.SH",
            "fallback": {
                "on_feature_unavailable": "ma200_legacy",
                "required_blocks": ["trend_block", "risk_block"],
                "emit_feature_availability": True,
            },
        },
    }
    result = {
        "exp_id": "exp_regime_meta",
        "status": "OK",
        "tier": "T0",
        "start_date": "2026-03-02",
        "end_date": "2026-03-03",
        "total_return": 0.1,
        "max_drawdown": -0.02,
        "cagr": 0.1,
        "sharpe": 1.0,
    }

    out = ensure_standard_artifacts(
        results_dir=results_dir,
        result=result,
        base_cfg=base_cfg,
        overrides={},
    )

    run_meta = json.loads((results_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert out["status"] == "OK"
    assert run_meta["regime"]["engine"] == "market_regime_framework"
    assert run_meta["regime"]["regime_semantics"] == "formal_multi_factor_regime"
    assert run_meta["regime"]["feature_availability_contract"]["required_blocks"] == ["trend_block", "risk_block"]
    assert run_meta["report_consistency"]["regime_engine"] == "market_regime_framework"


def test_ensure_standard_artifacts_writes_regime_audit_bundle(tmp_path) -> None:
    results_dir = tmp_path / "exp_regime_audit"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "portfolio_daily.csv").write_text(
        "\n".join(
            [
                "date,nav,market_state,trade_mode,regime_engine,regime_confidence,regime_duration_bars,regime_transition_reason,feature_availability_json",
                '2026-03-02,1.0,BULL,TREND_MAIN,market_regime_framework,0.82,6,,"{""trend_block"": true, ""risk_block"": true}"',
                '2026-03-03,1.1,TRANS_DOWN,TREND_LIGHT,market_regime_framework,0.44,1,RISK_BLOCK_WEAKNESS,"{""trend_block"": true, ""risk_block"": false}"',
            ]
        ),
        encoding="utf-8",
    )
    (results_dir / "run_config.json").write_text(
        json.dumps(
            {
                "universe": {"start": "2026-03-02", "end": "2026-03-03", "benchmark": "000300.SH"},
                "regime_engine": {
                    "engine": "market_regime_framework",
                    "persistence": {"confidence_floor": 0.55},
                    "fallback": {
                        "on_feature_unavailable": "ma200_legacy",
                        "required_blocks": ["trend_block", "risk_block"],
                        "emit_feature_availability": True,
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    out = ensure_standard_artifacts(
        results_dir=results_dir,
        result={
            "exp_id": "exp_regime_audit",
            "status": "OK",
            "tier": "T0",
            "start_date": "2026-03-02",
            "end_date": "2026-03-03",
            "total_return": 0.1,
            "max_drawdown": -0.02,
            "cagr": 0.1,
            "sharpe": 1.0,
        },
        base_cfg={
            "universe": {"start": "2026-03-02", "end": "2026-03-03", "benchmark": "000300.SH"},
            "schema_mapping": {},
            "regime_engine": {
                "engine": "market_regime_framework",
                "persistence": {"confidence_floor": 0.55},
                "fallback": {
                    "required_blocks": ["trend_block", "risk_block"],
                },
            },
        },
        overrides={},
    )

    artifacts = dict(out.get("artifacts") or {})
    assert artifacts.get("regime_audit_summary") == "regime_audit_summary.json"
    assert artifacts.get("regime_transition_debug") == "regime_transition_debug.csv"
    assert artifacts.get("regime_audit_report") == "regime_audit_report.md"

    summary = json.loads((results_dir / "regime_audit_summary.json").read_text(encoding="utf-8"))
    assert summary["summary"]["switch_count"] == 1
    assert summary["latest_state"]["why_today"] == "RISK_BLOCK_WEAKNESS"


def test_ensure_standard_artifacts_writes_weekly_five_state_regime_meta(tmp_path) -> None:
    results_dir = tmp_path / "exp_weekly_regime"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "portfolio_daily.csv").write_text(
        "\n".join(
            [
                "date,nav,market_state,market_state_5,trade_mode,regime_engine,market_state_score,risk_budget_multiplier,weekly_observation_flag",
                "2026-03-02,1.0,TURN_WEAK,TURN_WEAK,TREND_MAIN,weekly_five_state,2,0.15,1",
                "2026-03-03,1.1,TURN_WEAK,TURN_WEAK,TREND_MAIN,weekly_five_state,2,0.15,0",
            ]
        ),
        encoding="utf-8",
    )
    (results_dir / "run_config.json").write_text(
        json.dumps(
            {
                "universe": {"start": "2026-03-02", "end": "2026-03-03", "benchmark": "000300.SH"},
                "regime_engine": {
                    "engine": "weekly_five_state",
                    "benchmark": "000001.SH",
                    "weekly_five_state": {"turn_weak_budget": 0.15},
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    out = ensure_standard_artifacts(
        results_dir=results_dir,
        result={
            "exp_id": "exp_weekly_regime",
            "status": "OK",
            "tier": "T0",
            "start_date": "2026-03-02",
            "end_date": "2026-03-03",
            "total_return": 0.1,
            "max_drawdown": -0.02,
            "cagr": 0.1,
            "sharpe": 1.0,
        },
        base_cfg={
            "universe": {"start": "2026-03-02", "end": "2026-03-03", "benchmark": "000300.SH"},
            "schema_mapping": {},
            "regime_engine": {
                "engine": "weekly_five_state",
                "benchmark": "000001.SH",
                "weekly_five_state": {"turn_weak_budget": 0.15},
            },
        },
        overrides={},
    )

    run_meta = json.loads((results_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert out["status"] == "OK"
    assert run_meta["regime"]["engine"] == "weekly_five_state"
    assert run_meta["regime"]["regime_semantics"] == "weekly_five_state_regime"
