from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from backend.core.universe.hs300_csi500 import UniverseLoadError
from backend.core.universe.universe_resolver import resolve_universe_by_mode


def test_resolve_universe_by_mode_rejects_unsupported_asset_scope() -> None:
    with pytest.raises(UniverseLoadError) as exc_info:
        resolve_universe_by_mode(
            mode="CUSTOM",
            as_of=date(2026, 3, 20),
            db=SimpleNamespace(),
            runtime=SimpleNamespace(),
            asset_scope="us_equity",
            symbols=["AAPL"],
        )

    exc = exc_info.value
    assert exc.status == "ERROR:UNSUPPORTED_ASSET_SCOPE"
    assert exc.meta["asset_scope"] == "us_equity"
    assert exc.meta["asset_profile_id"] == "us_equity_prepare_mainline"


def test_resolve_universe_by_mode_supports_cn_etf_custom_catalog_symbols() -> None:
    symbols, meta = resolve_universe_by_mode(
        mode="CUSTOM",
        as_of=date(2026, 3, 20),
        db=SimpleNamespace(),
        runtime=SimpleNamespace(),
        asset_scope="cn_etf",
        symbols=["512100.SH", "cn_etf_first_wave_core"],
    )

    assert "sh512100" in symbols
    assert meta["asset_scope"] == "cn_etf"
    assert meta["symbols_source"] == "cn_etf_catalog_whitelist"
    assert meta["catalog_table"] == "pit_cn_etf_master"
    assert "512100.SH" in meta["etf_symbols"]
    assert meta["preset_id"] == "cn_etf_first_wave_core"
    assert meta["etf_batch"] == "cn_etf_first_wave_core"


def test_resolve_universe_by_mode_rejects_non_custom_mode_for_cn_etf() -> None:
    with pytest.raises(UniverseLoadError) as exc_info:
        resolve_universe_by_mode(
            mode="ALL_A",
            as_of=date(2026, 3, 20),
            db=SimpleNamespace(),
            runtime=SimpleNamespace(),
            asset_scope="cn_etf",
            symbols=["512100.SH"],
        )

    exc = exc_info.value
    assert exc.status == "ERROR:UNSUPPORTED_MODE"
    assert exc.meta["asset_scope"] == "cn_etf"
