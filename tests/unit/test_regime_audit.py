from __future__ import annotations

import json

import pandas as pd

from backend.core.audit.regime_audit import build_regime_audit_summary
from backend.core.audit.regime_audit import write_regime_audit_artifacts


def _sample_daily_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-03-02",
                "market_state": "BULL",
                "trade_mode": "TREND_MAIN",
                "regime_engine": "market_regime_framework",
                "regime_confidence": 0.82,
                "regime_duration_bars": 6,
                "regime_transition_reason": "",
                "feature_availability_json": json.dumps(
                    {
                        "trend_block": True,
                        "risk_block": True,
                        "breadth_block": True,
                        "participation_block": True,
                    }
                ),
            },
            {
                "date": "2026-03-03",
                "market_state": "TRANS_DOWN",
                "trade_mode": "TREND_LIGHT",
                "regime_engine": "market_regime_framework",
                "regime_confidence": 0.48,
                "regime_duration_bars": 1,
                "regime_transition_reason": "RISK_BLOCK_WEAKNESS",
                "feature_availability_json": json.dumps(
                    {
                        "trend_block": True,
                        "risk_block": True,
                        "breadth_block": False,
                        "participation_block": True,
                    }
                ),
            },
            {
                "date": "2026-03-04",
                "market_state": "TRANS_DOWN",
                "trade_mode": "NO_TRADE",
                "regime_engine": "market_regime_framework",
                "regime_confidence": 0.44,
                "regime_duration_bars": 2,
                "regime_transition_reason": "CONFIDENCE_BELOW_FLOOR",
                "feature_availability_json": json.dumps(
                    {
                        "trend_block": True,
                        "risk_block": True,
                        "breadth_block": False,
                        "participation_block": True,
                    }
                ),
            },
        ]
    )


def test_build_regime_audit_summary_counts_switches_and_feature_unavailability() -> None:
    summary = build_regime_audit_summary(
        daily_df=_sample_daily_frame(),
        run_meta={
            "regime": {
                "engine": "market_regime_framework",
                "persistence": {"confidence_floor": 0.55},
                "feature_availability_contract": {
                    "required_blocks": ["trend_block", "risk_block", "breadth_block"],
                },
            }
        },
    )

    assert summary is not None
    assert summary["regime_engine"] == "market_regime_framework"
    assert summary["summary"]["switch_count"] == 2
    assert summary["summary"]["transition_event_count"] == 2
    assert summary["summary"]["low_confidence_days"] == 2
    assert summary["summary"]["feature_unavailable_days"] == 2
    assert summary["feature_missing_counts"]["breadth_block"] == 2
    assert summary["latest_state"]["market_state"] == "TRANS_DOWN"
    assert summary["latest_state"]["why_today"] == "CONFIDENCE_BELOW_FLOOR"


def test_write_regime_audit_artifacts_writes_summary_debug_and_report(tmp_path) -> None:
    out = write_regime_audit_artifacts(
        results_dir=tmp_path,
        daily_df=_sample_daily_frame(),
        run_meta={
            "regime": {
                "engine": "market_regime_framework",
                "persistence": {"confidence_floor": 0.55},
                "feature_availability_contract": {
                    "required_blocks": ["trend_block", "risk_block", "breadth_block"],
                },
            }
        },
    )

    assert out is not None
    assert (tmp_path / "regime_audit_summary.json").exists()
    assert (tmp_path / "regime_transition_debug.csv").exists()
    assert (tmp_path / "regime_audit_report.md").exists()

    payload = json.loads((tmp_path / "regime_audit_summary.json").read_text(encoding="utf-8"))
    assert payload["summary"]["switch_count"] == 2

    debug_df = pd.read_csv(tmp_path / "regime_transition_debug.csv")
    assert len(debug_df) == 2
    assert set(debug_df["regime_transition_reason"].astype(str)) == {
        "RISK_BLOCK_WEAKNESS",
        "CONFIDENCE_BELOW_FLOOR",
    }
