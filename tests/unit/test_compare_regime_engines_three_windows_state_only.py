from __future__ import annotations

import json
from datetime import date

import numpy as np

from backend.scripts.ops.compare_regime_engines_three_windows import _build_state_only_daily_frame


def test_build_state_only_daily_frame_restores_labels_and_feature_flags() -> None:
    df = _build_state_only_daily_frame(
        trading_days=[date(2026, 3, 2), date(2026, 3, 3)],
        regime_engine="market_regime_framework",
        market_state=np.array([0, 1], dtype=np.int8),
        trade_mode=np.array([0, 1], dtype=np.int8),
        regime_confidence=np.array([0.81, 0.42], dtype=float),
        regime_duration_bars=np.array([6, 1], dtype=np.int32),
        regime_transition_reason=np.array(["", "BREAKDOWN_UNCONFIRMED"], dtype=object),
        feature_availability=np.array(
            [
                {"trend_block": True, "risk_block": True, "required_blocks_ready": True, "fallback_active": False},
                {"trend_block": True, "risk_block": False, "required_blocks_ready": False, "fallback_active": True},
            ],
            dtype=object,
        ),
    )

    assert list(df["market_state"]) == ["BULL", "TRANS_DOWN"]
    assert list(df["trade_mode"]) == ["TREND_MAIN", "TREND_LIGHT"]
    assert list(df["regime_engine"]) == ["market_regime_framework", "market_regime_framework"]

    latest_feature = json.loads(str(df.iloc[1]["feature_availability_json"]))
    assert latest_feature["trend_block"] is True
    assert latest_feature["risk_block"] is False
    assert latest_feature["required_blocks_ready"] is False
    assert latest_feature["fallback_active"] is True
