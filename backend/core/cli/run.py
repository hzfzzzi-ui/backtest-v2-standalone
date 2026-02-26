from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd


def _ensure_columns(df: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = None
    return out


def main() -> Any:
    from backend.core.cli.main import main as _main

    return _main()


if __name__ == "__main__":
    main()
