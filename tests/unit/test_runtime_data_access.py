from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from backend.core.tools import runtime_data_access


def test_resolve_validation_universe_uses_shared_filter_path(monkeypatch) -> None:
    provider = SimpleNamespace(
        load_ohlcv_daily=lambda symbols, start, end, source="stocks": pd.DataFrame(
            {"symbol": ["sh600000"], "date": [pd.Timestamp(start)], "close": [10.0]}
        ),
        load_st_history=lambda symbols, start, end: pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type"]),
        load_security_master=lambda symbols: pd.DataFrame(columns=["symbol", "list_date", "delist_date"]),
    )
    access = runtime_data_access.RuntimeDataAccess(
        bt_root=Path("C:/tmp"),
        cfg_obj=SimpleNamespace(db="db", db_runtime="runtime"),
        cfg_path=Path("C:/tmp/config.json"),
        provider=provider,
    )

    monkeypatch.setattr(runtime_data_access, "load_runtime_data_access", lambda bt_root=None: access)
    monkeypatch.setattr(runtime_data_access, "resolve_universe_timing", lambda mode, start, end: (start, False))
    monkeypatch.setattr(
        runtime_data_access,
        "resolve_universe_by_mode",
        lambda **kwargs: (["sh600000", "sz000001"], {"raw_count": 2}),
    )
    monkeypatch.setattr(
        runtime_data_access,
        "build_candidates_from_ohlcv",
        lambda history, filter_asof, st_history=None, security_master=None: pd.DataFrame({"symbol": ["sh600000"]}),
    )
    monkeypatch.setattr(
        runtime_data_access,
        "apply_universe_filters",
        lambda candidates, filter_cfg: (candidates, None, {"st": 1}),
    )

    snapshot = runtime_data_access.resolve_validation_universe(
        bt_root=Path("C:/tmp"),
        universe_mode="CUSTOM",
        symbols=["sh600000", "sz000001"],
        industries=[],
        universe_limit=None,
        start=pd.Timestamp("2024-01-02").date(),
        end=pd.Timestamp("2024-01-31").date(),
        exclude_st=True,
        exclude_suspended=True,
        min_list_days=120,
        min_avg_turnover_20d=1e8,
        price_min=0.0,
        price_max=99999.0,
        limit_rule="ignore",
    )

    assert snapshot.resolved_symbols == ["sh600000"]
    assert snapshot.resolved_meta["excluded_counts"] == {"st": 1}
    assert snapshot.resolved_meta["tradable_symbols"] == 1
    assert snapshot.resolved_meta["after_filters_symbols"] == 1
