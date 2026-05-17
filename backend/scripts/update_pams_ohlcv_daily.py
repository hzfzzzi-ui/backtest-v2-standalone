from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.cli.managed.update_pams_ohlcv_daily import (
    _compute_limit_prices,
    _load_cn_index_daily_tushare,
    _limit_pct_for_symbol,
    _merge_index_symbols,
    _normalize_cn_a_rows,
    _normalize_cn_index_rows,
    _normalize_daily_basic_frame,
    build_update_args,
    main,
)


if __name__ == "__main__":
    main()
