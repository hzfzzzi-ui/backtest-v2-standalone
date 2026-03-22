from __future__ import annotations

import json

import pandas as pd

from backend.core.audit.regime_compare import build_regime_compare_delta
from backend.core.audit.regime_compare import build_regime_engine_compare_config
from backend.core.audit.regime_compare import summarize_regime_experiment


def test_build_regime_engine_compare_config_sets_window_and_engine() -> None:
    cfg = build_regime_engine_compare_config(
        {
            "universe": {"start": "2020-01-01", "end": "2020-12-31"},
            "regime_engine": {"engine": "ma200_legacy"},
        },
        start="2016-03-01",
        end="2026-03-01",
        regime_engine="market_regime_framework",
    )

    assert cfg["universe"]["start"] == "2016-03-01"
    assert cfg["universe"]["end"] == "2026-03-01"
    assert cfg["regime_engine"]["engine"] == "market_regime_framework"


def test_summarize_regime_experiment_reads_regime_audit_inputs(tmp_path) -> None:
    exp_dir = tmp_path / "exp_regime_compare"
    exp_dir.mkdir(parents=True, exist_ok=True)
    (exp_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "data": {"data_role": "v1"},
                "regime": {
                    "engine": "market_regime_framework",
                    "persistence": {"confidence_floor": 0.55},
                    "feature_availability_contract": {
                        "required_blocks": ["trend_block", "risk_block"],
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "date": "2026-03-02",
                "market_state": "BULL",
                "trade_mode": "TREND_MAIN",
                "regime_engine": "market_regime_framework",
                "regime_confidence": 0.82,
                "regime_duration_bars": 5,
                "regime_transition_reason": "",
                "feature_availability_json": json.dumps({"trend_block": True, "risk_block": True}),
            },
            {
                "date": "2026-03-03",
                "market_state": "TRANS_DOWN",
                "trade_mode": "TREND_LIGHT",
                "regime_engine": "market_regime_framework",
                "regime_confidence": 0.41,
                "regime_duration_bars": 1,
                "regime_transition_reason": "RISK_BLOCK_WEAKNESS",
                "feature_availability_json": json.dumps({"trend_block": True, "risk_block": False}),
            },
        ]
    ).to_csv(exp_dir / "portfolio_daily.csv", index=False)

    row = summarize_regime_experiment(
        exp_dir=exp_dir,
        window_key="2016_2026",
        window_label="2016-2026",
        regime_engine="market_regime_framework",
    )

    assert row["switch_count"] == 1
    assert row["low_confidence_days"] == 1
    assert row["feature_unavailable_days"] == 1
    assert row["latest_state"] == "TRANS_DOWN"


def test_build_regime_compare_delta_uses_formal_minus_legacy() -> None:
    delta = build_regime_compare_delta(
        legacy_row={
            "window_key": "2016_2026",
            "window_label": "2016-2026",
            "exp_id": "exp_legacy",
            "switch_count": 4,
            "transition_event_count": 6,
            "low_confidence_days": 0,
            "feature_unavailable_days": 0,
            "regime_confidence_mean": 0.0,
        },
        formal_row={
            "window_key": "2016_2026",
            "window_label": "2016-2026",
            "exp_id": "exp_formal",
            "switch_count": 7,
            "transition_event_count": 9,
            "low_confidence_days": 12,
            "feature_unavailable_days": 3,
            "regime_confidence_mean": 0.63,
        },
    )

    assert delta["delta_switch_count"] == 3
    assert delta["delta_transition_event_count"] == 3
    assert delta["delta_low_confidence_days"] == 12
    assert delta["delta_feature_unavailable_days"] == 3
    assert delta["delta_regime_confidence_mean"] == 0.63
