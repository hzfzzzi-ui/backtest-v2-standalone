from __future__ import annotations

import sys
from types import SimpleNamespace

import pandas as pd

from backend.scripts import fetch_csi800_pit as mod


def test_tushare_snapshot_builder_skips_partial_trade_dates(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
            {"con_code": f"{i:06d}.SZ", "trade_date": "20250731"} for i in range(400)
        ]
        + [
            {"con_code": f"{i:06d}.SZ", "trade_date": "20250829"} for i in range(800)
        ]
    )

    class _DummyPro:
        def index_weight(self, **kwargs):
            return frame

    monkeypatch.setitem(
        sys.modules,
        "tushare",
        SimpleNamespace(set_token=lambda token: None, pro_api=lambda token: _DummyPro()),
    )

    snapshots = mod._build_with_tushare(
        [pd.Timestamp("2025-07-31").date(), pd.Timestamp("2025-08-31").date()],
        "dummy-token",
    )

    assert snapshots == [("2025-08-31", [f"{i:06d}.SZ" for i in range(800)])]
