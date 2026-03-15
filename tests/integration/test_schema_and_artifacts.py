from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.api.backtest_v2 import impl as backtest_impl
from backend.api.backtest_v2 import configs_impl as _config_store
from backend.core.tools import saved_config_access
from backend.core.tools.saved_config_access import create_saved_config_record, load_saved_config_record


def test_canonical_artifact_contract_and_missing_fields(tmp_path: Path) -> None:
    bt_root = tmp_path / "backtest_V2"
    bt_root.mkdir(parents=True, exist_ok=True)
    results_dir = tmp_path / "exp_case"

    base_cfg = {
        "universe": {"start": "2024-01-01", "end": "2024-12-31", "benchmark": "000300.SH"},
        "signal": {"strategy": "EMA_CROSS"},
    }
    result = {
        "exp_id": "exp_case",
        "results_dir": str(results_dir),
        "status": "OK",
        "total_return": -0.02,
        "max_drawdown": -0.1,
        "cagr": -0.02,
        "sharpe": 0.1,
        "trades": 0,
        "raw_signal": 0,
        "blocked": 0,
        "orders": 0,
        "skipped": 0,
        "closed_trades": 0,
    }

    out = backtest_impl.stabilize_experiment_result(
        bt_root=bt_root,
        result=result,
        base_cfg=base_cfg,
        overrides={},
        run_profile_summary=None,
    )

    artifacts = dict(out.get("artifacts") or {})
    effective_results_dir = Path(out["results_dir"])
    assert artifacts.get("reason_codes") == "reason_codes.csv"
    assert artifacts.get("symbol_performance") == "symbol_performance.csv"

    assert (effective_results_dir / "reason_codes.csv").exists()
    assert (effective_results_dir / "symbol_performance.csv").exists()

    run_meta = json.loads((effective_results_dir / "run_meta.json").read_text(encoding="utf-8"))
    counters = dict(run_meta.get("counters") or {})
    for key in ["raw_signal", "blocked", "orders", "skipped", "closed_trades"]:
        assert key in counters
    for legacy in ["raw_signal_count", "blocked_count", "orders_count", "skipped_count", "closed_trades_count"]:
        assert legacy not in counters

    missing = set(run_meta.get("missing_fields") or [])
    assert "missing_reason_code_source" in missing
    assert "missing_symbol_performance_source" in missing

    sp = pd.read_csv(effective_results_dir / "symbol_performance.csv")
    assert sp.empty


def test_reason_codes_and_counters_are_canonical_only(tmp_path: Path) -> None:
    group_dir = tmp_path / "G1"
    group_dir.mkdir(parents=True, exist_ok=True)
    (group_dir / "reason_codes.csv").write_text(
        "code,count\nATR_STOP_LOSS,3\nTIME_EXIT,2\n",
        encoding="utf-8",
    )

    reason_counts = backtest_impl._extract_reason_code_counts(group_dir)
    assert reason_counts.get("atr_stop_exit_count") == 3
    assert reason_counts.get("time_exit_count") == 2

    normalized, hits = backtest_impl._normalized_run_meta_counters(
        {
            "counters": {
                "raw_signal": 11,
                "blocked": 4,
                "orders": 7,
                "skipped": 2,
                "closed_trades": 5,
            }
        }
    )
    assert hits == 0
    assert normalized.get("raw_signal") == 11
    assert normalized.get("blocked") == 4
    assert normalized.get("orders") == 7
    assert normalized.get("skipped") == 2
    assert normalized.get("closed_trades") == 5


def test_builtin_config_metadata_refreshes_even_when_hash_is_unchanged(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configs_root = tmp_path / "configs"
    configs_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(_config_store, "_configs_root", lambda: configs_root)
    monkeypatch.setattr(saved_config_access, "configs_root", lambda: configs_root)

    stale = create_saved_config_record(
        _config_store._br35_atr10_csi800_10y_config_json(),
        config_id=_config_store._BR35_ATR10_CSI800_10Y_CONFIG_ID,
        name="BR35+ATR1.0+CSI800+10Y",
        display_name="BR35+ATR1.0+CSI800+10Y",
        tags=["builtin", "candidate", "breakout35", "atr10", "csi800", "10y"],
        source_type="template",
        owner="builtin",
        locked=True,
    )
    configs_root.joinpath(f"{_config_store._BR35_ATR10_CSI800_10Y_CONFIG_ID}.json").write_text(
        json.dumps(stale, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _config_store._ensure_builtin_champion_configs()

    refreshed = load_saved_config_record(_config_store._BR35_ATR10_CSI800_10Y_CONFIG_ID)
    assert refreshed is not None
    assert refreshed.get("display_name") == "BR35+ATR1.0+HS300+ZZ500+10Y (PIT)"
    assert "hs300_zz500" in list(refreshed.get("tags") or [])
    assert "pit_dynamic" in list(refreshed.get("tags") or [])
    assert "csi800" not in list(refreshed.get("tags") or [])
    assert ((refreshed.get("config_json") or {}).get("flow_script") or {}).get("script_id") == "br35_atr10_hs300_zz500_10y"
    assert ((refreshed.get("config_json") or {}).get("universe") or {}).get("membership_mode") == "PIT_DYNAMIC"


def test_run_meta_report_consistency_includes_resolved_config_details(tmp_path: Path) -> None:
    bt_root = tmp_path / "backtest_V2"
    bt_root.mkdir(parents=True, exist_ok=True)
    results_dir = tmp_path / "exp_case_resolved"

    base_cfg = {
        "universe": {"start": "2024-01-01", "end": "2024-12-31", "benchmark": "000300.SH"},
        "signal": {"strategy": "EMA_CROSS"},
    }
    result = {
        "exp_id": "exp_case_resolved",
        "results_dir": str(results_dir),
        "status": "OK",
        "total_return": 0.03,
        "max_drawdown": -0.08,
        "cagr": 0.03,
        "sharpe": 0.6,
        "trades": 2,
        "raw_signal": 4,
        "blocked": 1,
        "orders": 2,
        "skipped": 0,
        "closed_trades": 1,
        "universe_meta": {"universe_mode": "HS300_ZZ500", "raw_count": 812},
    }

    out = backtest_impl.stabilize_experiment_result(
        bt_root=bt_root,
        result=result,
        base_cfg=base_cfg,
        overrides={
            "config_source": "config_id",
            "config_conflict_policy": "saved_matches_draft",
            "resolved_config_mode": "saved_config_run",
            "resolved_config_id": "cfg_br35_atr10_csi800_10y",
            "resolved_config_hash": "abc123",
            "resolved_config_meta": {"display_name": "BR35+ATR1.0+HS300+ZZ500+10Y"},
        },
        run_profile_summary=None,
    )

    effective_results_dir = Path(out["results_dir"])
    run_meta = json.loads((effective_results_dir / "run_meta.json").read_text(encoding="utf-8"))
    consistency = dict(run_meta.get("report_consistency") or {})
    assert consistency.get("resolved_config_mode") == "saved_config_run"
    assert consistency.get("resolved_config_id") == "cfg_br35_atr10_csi800_10y"
    assert consistency.get("resolved_config_hash") == "abc123"
    assert (consistency.get("resolved_config_meta") or {}).get("display_name") == "BR35+ATR1.0+HS300+ZZ500+10Y"
    assert (consistency.get("resolved_config_meta") or {}).get("universe_mode") == "HS300_ZZ500"


def test_stage_summary_artifact_is_written_and_indexed(tmp_path: Path) -> None:
    bt_root = tmp_path / "backtest_V2"
    bt_root.mkdir(parents=True, exist_ok=True)
    results_dir = tmp_path / "exp_case_stage_summary"

    base_cfg = {
        "universe": {"start": "2024-01-01", "end": "2024-12-31", "benchmark": "000300.SH"},
        "signal": {"strategy": "EMA_CROSS"},
    }
    result = {
        "exp_id": "exp_case_stage_summary",
        "results_dir": str(results_dir),
        "status": "OK",
        "total_return": 0.03,
        "max_drawdown": -0.08,
        "cagr": 0.03,
        "sharpe": 0.6,
        "trades": 2,
        "raw_signal": 4,
        "blocked": 1,
        "orders": 2,
        "skipped": 0,
        "closed_trades": 1,
        "stage_summary": {
            "schema_version": "stage_pipeline_summary@1",
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
            "stage_order": ["S1", "S2", "S3", "S4", "S5", "S6", "S9", "S8", "S7"],
            "enabled_stages": ["S1", "S2", "S4", "S5", "S6", "S9", "S8", "S7"],
            "warnings": ["market_filter_warn"],
            "trading_days": 2,
            "days_with_warnings": 1,
            "days_with_fills": 1,
            "days_with_scheduled_orders": 1,
        },
        "stage_pipeline": {
            "schema_version": "stage_pipeline_summary@1",
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
            "stage_order": ["S1", "S2", "S3", "S4", "S5", "S6", "S9", "S8", "S7"],
            "enabled_stages": ["S1", "S2", "S4", "S5", "S6", "S9", "S8", "S7"],
            "warnings": ["market_filter_warn"],
            "trading_days": 2,
        },
        "metrics": {
            "audit": {
                "legacy_kernel": "strict_core",
            },
        },
    }

    out = backtest_impl.stabilize_experiment_result(
        bt_root=bt_root,
        result=result,
        base_cfg=base_cfg,
        overrides={},
        run_profile_summary=None,
    )

    artifacts = dict(out.get("artifacts") or {})
    effective_results_dir = Path(out["results_dir"])
    assert artifacts.get("stage_summary") == "stage_summary.json"

    stage_summary = json.loads((effective_results_dir / "stage_summary.json").read_text(encoding="utf-8"))
    assert stage_summary["execution_shell"] == "stage_pipeline_shell_bridge"
    assert stage_summary["route_id"] == "provider_breakout_runtime"

    run_meta = json.loads((effective_results_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert (run_meta.get("stage_pipeline") or {}).get("execution_shell") == "stage_pipeline_shell_bridge"

    audit = json.loads((effective_results_dir / "audit.json").read_text(encoding="utf-8"))
    assert audit.get("legacy_kernel") == "strict_core"
    assert (audit.get("stage_pipeline") or {}).get("stage_order") == ["S1", "S2", "S3", "S4", "S5", "S6", "S9", "S8", "S7"]
    assert (audit.get("research_audit") or {}).get("contract_version") == "research_audit@1"
    assert (audit.get("research_audit") or {}).get("evidence_refs", {}).get("run_meta") == "run_meta.json"
    assert (audit.get("research_audit") or {}).get("evidence_refs", {}).get("manifest") == "manifest.json"

    manifest = json.loads((effective_results_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifacts"]["stage_summary"] == "stage_summary.json"
    assert (manifest.get("stage_pipeline") or {}).get("route_id") == "provider_breakout_runtime"


def test_multi_alpha_artifacts_preserve_source_fields_and_audit_summary(tmp_path: Path) -> None:
    bt_root = tmp_path / "backtest_V2"
    bt_root.mkdir(parents=True, exist_ok=True)
    results_dir = tmp_path / "exp_case_multi_alpha"
    results_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "date": "2026-03-02",
                "symbol": "sh600000",
                "side": "SELL",
                "price": 10.0,
                "qty": 100,
                "reason_code": "RISK_OFF_EXIT",
                "exit_owner": "global_risk_override",
                "entry_alpha_id": "breakout_55",
                "entry_sleeve_id": "trend",
                "entry_reason_code": "BREAKOUT_HIGH",
                "entry_date": "2026-02-20",
            }
        ]
    ).to_csv(results_dir / "portfolio_trades.csv", index=False)

    base_cfg = {
        "universe": {"start": "2026-03-01", "end": "2026-03-31", "benchmark": "000300.SH"},
        "signal": {"strategy": "COMPOSITE"},
    }
    result = {
        "exp_id": "exp_case_multi_alpha",
        "results_dir": str(results_dir),
        "status": "OK",
        "total_return": 0.01,
        "max_drawdown": -0.02,
        "cagr": 0.01,
        "sharpe": 0.3,
        "trades": 1,
        "metrics": {
            "audit": {
                "contract_version": "multi_alpha_audit@1",
                "summary": {
                    "raw_signal_counts_by_alpha": {"breakout_55": 2},
                    "composed_signal_counts_by_alpha": {"breakout_55": 1},
                    "blocked_signal_counts_by_reason": {"SLEEVE_BUDGET_EXCEEDED": 1},
                    "conflict_resolution_counts": {"prefer_higher_score": 1},
                    "source_only_exit_count": 0,
                    "global_risk_override_count": 1,
                },
                "flagged_days": [
                    {
                        "date": "2026-03-02",
                        "global_risk_override_count": 1,
                    }
                ],
            }
        },
    }

    out = backtest_impl.stabilize_experiment_result(
        bt_root=bt_root,
        result=result,
        base_cfg=base_cfg,
        overrides={},
        run_profile_summary=None,
    )

    effective_results_dir = Path(out["results_dir"])
    trades_frame = pd.read_csv(effective_results_dir / "portfolio_trades.csv")
    orders_frame = pd.read_csv(effective_results_dir / "orders.csv")
    audit = json.loads((effective_results_dir / "audit.json").read_text(encoding="utf-8"))

    assert (out.get("artifacts") or {}).get("trades") == "portfolio_trades.csv"
    assert "trades_alias" not in dict(out.get("artifacts") or {})

    for df in (trades_frame, orders_frame):
        assert "exit_owner" in df.columns
        assert "entry_alpha_id" in df.columns
        assert "entry_sleeve_id" in df.columns
        assert df.loc[0, "exit_owner"] == "global_risk_override"
        assert df.loc[0, "entry_alpha_id"] == "breakout_55"

    assert audit["contract_version"] == "multi_alpha_audit@1"
    assert audit["summary"]["global_risk_override_count"] == 1
    assert audit["flagged_days"][0]["date"] == "2026-03-02"
