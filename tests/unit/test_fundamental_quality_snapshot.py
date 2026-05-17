from __future__ import annotations

import pandas as pd

from backend.research.fundamental_quality_snapshot import load_symbols_from_csv


def test_load_symbols_from_csv_normalizes_unique_symbols(tmp_path) -> None:
    path = tmp_path / "symbols.csv"
    pd.DataFrame({"symbol": ["600000.SH", "sh600000", "000001.SZ", ""]}).to_csv(path, index=False)

    symbols = load_symbols_from_csv(path)

    assert symbols == ["sh600000", "sz000001"]
