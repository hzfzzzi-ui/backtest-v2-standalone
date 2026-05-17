from __future__ import annotations

import pandas as pd

from backend.cli.managed.update_pit_stock_fundamental_quality import (
    _normalize_fina_indicator_frame,
    _to_ts_code,
)


def test_to_ts_code_normalizes_cn_symbols() -> None:
    assert _to_ts_code("sh600000") == "600000.SH"
    assert _to_ts_code("000001.SZ") == "000001.SZ"


def test_normalize_fina_indicator_frame_keeps_plain_quality_fields() -> None:
    raw = pd.DataFrame(
        [
            {
                "ts_code": "600000.SH",
                "ann_date": "20240430",
                "end_date": "20240331",
                "roe": "2.3",
                "roa": "0.5",
                "grossprofit_margin": "30.0",
                "netprofit_margin": "10.0",
                "debt_to_assets": "60.0",
            }
        ]
    )

    normalized = _normalize_fina_indicator_frame(raw)

    assert normalized.loc[0, "symbol"] == "sh600000"
    assert normalized.loc[0, "ann_date"].isoformat() == "2024-04-30"
    assert normalized.loc[0, "end_date"].isoformat() == "2024-03-31"
    assert normalized.loc[0, "gross_margin"] == 30.0
    assert normalized.loc[0, "net_margin"] == 10.0
    assert normalized.loc[0, "source"] == "tushare_fina_indicator"
