from __future__ import annotations

from datetime import date

import pandas as pd

from backend.core.data.mapping import to_canonical
from backend.core.data.validate_pg import _evaluate_frames
from backend.scripts.import_cn_daily_basic_liquidity import _normalize_daily_basic_frame


def test_to_canonical_keeps_daily_basic_liquidity_extras() -> None:
    raw = pd.DataFrame(
        [
            {
                "trade_date": "2024-01-02",
                "symbol": "sh600000",
                "open": "10.0",
                "high": "10.5",
                "low": "9.8",
                "close": "10.1",
                "volume": "1000",
                "turnover": "10000",
                "turnover_rate_f": "1.23",
                "turnover_rate": "1.11",
                "volume_ratio": "0.98",
                "float_share": "1000000",
                "free_share": "800000",
                "circ_mv": "123456789",
            }
        ]
    )
    mapping = {
        "date": "trade_date",
        "symbol": "symbol",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "amount": "turnover",
        "turnover_rate": "turnover_rate",
        "turnover_rate_f": "turnover_rate_f",
        "volume_ratio": "volume_ratio",
        "float_share": "float_share",
        "free_share": "free_share",
        "circ_mv": "circ_mv",
    }

    out, warnings = to_canonical(raw, mapping)

    assert warnings == []
    assert out.loc[0, "turnover_rate_f"] == 1.23
    assert out.loc[0, "turnover_rate"] == 1.11
    assert out.loc[0, "volume_ratio"] == 0.98
    assert out.loc[0, "float_share"] == 1000000.0
    assert out.loc[0, "free_share"] == 800000.0
    assert out.loc[0, "circ_mv"] == 123456789.0


def test_evaluate_frames_fails_when_required_turnover_rate_field_is_missing() -> None:
    stocks = pd.DataFrame(
        [
            {
                "symbol": "sh600000",
                "market": "CN_A",
                "trade_date": "2024-01-02",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.1,
                "volume": 1000,
                "turnover": 10000,
                "limit_up": 11.0,
                "limit_down": 9.0,
                "is_suspended": False,
            }
        ]
    )
    benchmark = pd.DataFrame(
        [
            {
                "index_code": "000300.SH",
                "trade_date": "2024-01-02",
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": 1.0,
                "turnover": 1.0,
            }
        ]
    )

    result = _evaluate_frames(
        stocks_df=stocks,
        benchmark_df=benchmark,
        symbols=["sh600000"],
        benchmark="000300.SH",
        strict_suspended=False,
        allow_cn_index_fallback=False,
        schema_ok=False,
        schema_missing={"pams_ohlcv_daily": ["turnover_rate_f"], "pit_index_daily": []},
        start=date(2024, 1, 2),
        end=date(2024, 1, 2),
        required_turnover_rate_field="turnover_rate_f",
    )

    assert result["pass"] is False
    assert result["checks"]["turnover_rate_field"]["pass"] is False
    assert result["checks"]["turnover_rate_field"]["field"] == "turnover_rate_f"


def test_evaluate_frames_warns_on_turnover_rate_coverage_gap() -> None:
    stocks = pd.DataFrame(
        [
            {
                "symbol": "sh600000",
                "market": "CN_A",
                "trade_date": "2024-01-02",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.1,
                "volume": 1000,
                "turnover": 10000,
                "limit_up": 11.0,
                "limit_down": 9.0,
                "is_suspended": False,
                "turnover_rate_f": 1.0,
            },
            {
                "symbol": "sh600000",
                "market": "CN_A",
                "trade_date": "2024-01-03",
                "open": 10.1,
                "high": 10.6,
                "low": 9.9,
                "close": 10.2,
                "volume": 1100,
                "turnover": 11000,
                "limit_up": 11.2,
                "limit_down": 9.1,
                "is_suspended": False,
                "turnover_rate_f": None,
            },
        ]
    )
    benchmark = pd.DataFrame(
        [
            {
                "index_code": "000300.SH",
                "trade_date": "2024-01-02",
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": 1.0,
                "turnover": 1.0,
            }
        ]
    )

    result = _evaluate_frames(
        stocks_df=stocks,
        benchmark_df=benchmark,
        symbols=["sh600000"],
        benchmark="000300.SH",
        strict_suspended=False,
        allow_cn_index_fallback=False,
        schema_ok=True,
        schema_missing={"pams_ohlcv_daily": [], "pit_index_daily": []},
        start=date(2024, 1, 2),
        end=date(2024, 1, 3),
        required_turnover_rate_field="turnover_rate_f",
    )

    assert result["checks"]["turnover_rate_field"]["pass"] is True
    assert result["checks"]["turnover_rate_field"]["missing_rows"] == 1
    assert any(item["code"] == "TURNOVER_RATE_COVERAGE_WARNING" for item in result["warnings"])


def test_normalize_daily_basic_frame_maps_ts_symbols_to_internal_symbols() -> None:
    raw = pd.DataFrame(
        [
            {
                "ts_code": "600000.SH",
                "trade_date": "20240102",
                "turnover_rate": 1.1,
                "turnover_rate_f": 1.2,
                "volume_ratio": 0.9,
                "float_share": 1000000,
                "free_share": 800000,
                "circ_mv": 123456789,
            }
        ]
    )

    out = _normalize_daily_basic_frame(raw, symbol_filter=set())

    assert out.loc[0, "symbol"] == "sh600000"
    assert out.loc[0, "trade_date"].isoformat() == "2024-01-02"
    assert out.loc[0, "turnover_rate_f"] == 1.2
