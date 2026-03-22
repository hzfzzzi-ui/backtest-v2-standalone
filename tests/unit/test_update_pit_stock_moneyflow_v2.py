from __future__ import annotations

from datetime import date

import pandas as pd

from backend.cli.managed import update_pit_stock_moneyflow_v2 as updater


def test_build_trade_date_frame_aligns_to_v2_main_keys() -> None:
    main_frame = pd.DataFrame(
        [
            {"symbol": "sh600000", "trade_date": date(2026, 3, 16)},
            {"symbol": "sz000001", "trade_date": date(2026, 3, 16)},
        ]
    )
    raw_frame = pd.DataFrame(
        [
            {
                "symbol": "sh600000",
                "trade_date": date(2026, 3, 16),
                "buy_sm_vol": 1,
                "sell_sm_vol": 2,
                "buy_md_vol": 3,
                "sell_md_vol": 4,
                "buy_lg_vol": 5,
                "sell_lg_vol": 6,
                "buy_elg_vol": 7,
                "sell_elg_vol": 8,
                "net_mf_vol": 9,
                "buy_sm_amount": 1.1,
                "sell_sm_amount": 2.2,
                "buy_md_amount": 3.3,
                "sell_md_amount": 4.4,
                "buy_lg_amount": 5.5,
                "sell_lg_amount": 6.6,
                "buy_elg_amount": 7.7,
                "sell_elg_amount": 8.8,
                "net_mf_amount": 9.9,
            }
        ]
    )

    frame, stats = updater._build_trade_date_frame(
        trade_date=date(2026, 3, 16),
        main_frame=main_frame,
        raw_frame=raw_frame,
        build_run_id="run_1",
    )

    assert len(frame) == 2
    first = frame[frame["symbol"] == "sh600000"].iloc[0]
    second = frame[frame["symbol"] == "sz000001"].iloc[0]
    assert bool(first["source_moneyflow_present"]) is True
    assert bool(first["net_fields_present"]) is True
    assert int(first["buy_elg_vol"]) == 7
    assert float(first["net_mf_amount"]) == 9.9
    assert bool(second["source_moneyflow_present"]) is False
    assert bool(second["net_fields_present"]) is False
    assert pd.isna(second["net_mf_amount"])
    assert stats["traded_rows"] == 2
    assert stats["source_rows"] == 1
    assert stats["net_rows"] == 1
    assert stats["row_coverage_ratio"] == 0.5
