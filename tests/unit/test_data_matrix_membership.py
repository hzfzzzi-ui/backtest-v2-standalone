from __future__ import annotations

from datetime import date

import pandas as pd

from backend.core.engine_vector.data_matrix import build_ohlc_matrices_from_history


def test_membership_history_gates_tradable_outside_active_ranges() -> None:
    history = pd.DataFrame(
        [
            {"date": "2024-01-02", "symbol": "sh600000", "open": 10.0, "high": 10.5, "low": 9.9, "close": 10.2, "volume": 1000, "amount": 10000},
            {"date": "2024-01-03", "symbol": "sh600000", "open": 10.1, "high": 10.6, "low": 10.0, "close": 10.3, "volume": 1000, "amount": 10000},
            {"date": "2024-01-04", "symbol": "sh600000", "open": 10.2, "high": 10.7, "low": 10.1, "close": 10.4, "volume": 1000, "amount": 10000},
            {"date": "2024-01-02", "symbol": "sz000001", "open": 8.0, "high": 8.2, "low": 7.9, "close": 8.1, "volume": 1000, "amount": 9000},
            {"date": "2024-01-03", "symbol": "sz000001", "open": 8.1, "high": 8.3, "low": 8.0, "close": 8.2, "volume": 1000, "amount": 9200},
            {"date": "2024-01-04", "symbol": "sz000001", "open": 8.2, "high": 8.4, "low": 8.1, "close": 8.3, "volume": 1000, "amount": 9300},
        ]
    )
    membership_history = pd.DataFrame(
        [
            {"index_code": "000906.SH", "symbol": "sh600000", "start_date": "2024-01-01", "end_date": None},
            {"index_code": "000906.SH", "symbol": "sz000001", "start_date": "2024-01-03", "end_date": "2024-01-04"},
        ]
    )

    mx = build_ohlc_matrices_from_history(
        history,
        [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)],
        membership_history=membership_history,
    )

    sym_to_col = {sym: idx for idx, sym in enumerate(mx.symbols)}
    assert mx.tradable[0, sym_to_col["sh600000"]]
    assert mx.tradable[1, sym_to_col["sh600000"]]
    assert mx.tradable[2, sym_to_col["sh600000"]]

    # [start_date, end_date) right-open semantics
    assert bool(mx.tradable[0, sym_to_col["sz000001"]]) is False
    assert bool(mx.tradable[1, sym_to_col["sz000001"]]) is True
    assert bool(mx.tradable[2, sym_to_col["sz000001"]]) is False
    assert mx.close[2, sym_to_col["sz000001"]] == 8.3
