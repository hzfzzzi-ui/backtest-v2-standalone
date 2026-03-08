from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.api.endpoints import _config_store
from backend.api.endpoints._config_governance import create_saved_config_record, load_saved_config_record
from backend.api.endpoints.backtest_v2 import _extract_reason_code_counts, _normalized_run_meta_counters
from backend.api.endpoints.backtest_v2_artifacts import stabilize_experiment_result


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

    out = stabilize_experiment_result(
        bt_root=bt_root,
        result=result,
        base_cfg=base_cfg,
        overrides={},
        run_profile_summary=None,
    )

    artifacts = dict(out.get("artifacts") or {})
    assert artifacts.get("reason_codes") == "reason_codes.csv"
    assert artifacts.get("symbol_performance") == "symbol_performance.csv"

    assert (results_dir / "reason_codes.csv").exists()
    assert (results_dir / "symbol_performance.csv").exists()

    run_meta = json.loads((results_dir / "run_meta.json").read_text(encoding="utf-8"))
    counters = dict(run_meta.get("counters") or {})
    for key in ["raw_signal", "blocked", "orders", "skipped", "closed_trades"]:
        assert key in counters
    for legacy in ["raw_signal_count", "blocked_count", "orders_count", "skipped_count", "closed_trades_count"]:
        assert legacy not in counters

    missing = set(run_meta.get("missing_fields") or [])
    assert "missing_reason_code_source" in missing
    assert "missing_symbol_performance_source" in missing

    sp = pd.read_csv(results_dir / "symbol_performance.csv")
    assert sp.empty


def test_legacy_read_compatibility_reason_file_and_counter_alias(tmp_path: Path) -> None:
    group_dir = tmp_path / "G1"
    group_dir.mkdir(parents=True, exist_ok=True)
    (group_dir / "reason_code_counts.csv").write_text(
        "code,count\nATR_STOP_LOSS,3\nTIME_EXIT,2\n",
        encoding="utf-8",
    )

    reason_counts = _extract_reason_code_counts(group_dir)
    assert reason_counts.get("atr_stop_exit_count") == 3
    assert reason_counts.get("time_exit_count") == 2

    normalized, hits = _normalized_run_meta_counters(
        {
            "counters": {
                "raw_signal_count": 11,
                "blocked_count": 4,
                "orders_count": 7,
                "skipped_count": 2,
                "closed_trades_count": 5,
            }
        }
    )
    assert hits == 5
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
    assert refreshed.get("display_name") == "BR35+ATR1.0+HS300+ZZ500+10Y"
    assert "hs300_zz500" in list(refreshed.get("tags") or [])
    assert "csi800" not in list(refreshed.get("tags") or [])
    assert ((refreshed.get("config_json") or {}).get("flow_script") or {}).get("script_id") == "br35_atr10_hs300_zz500_10y"


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

    stabilize_experiment_result(
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

    run_meta = json.loads((results_dir / "run_meta.json").read_text(encoding="utf-8"))
    consistency = dict(run_meta.get("report_consistency") or {})
    assert consistency.get("resolved_config_mode") == "saved_config_run"
    assert consistency.get("resolved_config_id") == "cfg_br35_atr10_csi800_10y"
    assert consistency.get("resolved_config_hash") == "abc123"
    assert (consistency.get("resolved_config_meta") or {}).get("display_name") == "BR35+ATR1.0+HS300+ZZ500+10Y"
    assert (consistency.get("resolved_config_meta") or {}).get("universe_mode") == "HS300_ZZ500"
