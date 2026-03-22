from __future__ import annotations

from datetime import date

from backend.cli.managed import pams_ohlcv_daily_v2_common as common


def test_historical_bj_symbol_heuristic_maps_92_prefix() -> None:
    assert common.historical_bj_symbol_heuristic("bj920047") == "bj430047"
    assert common.historical_bj_symbol_heuristic("920047.BJ") == "bj430047"
    assert common.historical_bj_symbol_heuristic("sh600000") is None


def test_symbol_lineage_resolver_prefers_explicit_then_heuristic() -> None:
    resolver = common.SymbolLineageResolver(
        {
            "bj920047": [
                {
                    "historical_symbol": "bj430047",
                    "phase_start": None,
                    "phase_end": date(2021, 11, 14),
                    "mapping_source": "seed_mapping",
                    "mapping_confidence": 2,
                }
            ]
        }
    )

    candidates = resolver.candidates_for_trade_date("bj920047", date(2020, 1, 2), "bj_pre_20211115")

    assert [item.symbol for item in candidates] == ["bj920047", "bj430047"]
    assert [item.source for item in candidates] == ["current_symbol", "seed_mapping"]


def test_akshare_turnover_cache_uses_lineage_candidate_source() -> None:
    resolver = common.SymbolLineageResolver(
        {
            "bj920047": [
                {
                    "historical_symbol": "bj430047",
                    "phase_start": None,
                    "phase_end": date(2021, 11, 14),
                    "mapping_source": "seed_mapping",
                    "mapping_confidence": 2,
                }
            ]
        }
    )
    cache = common.AkShareTurnoverCache(lineage_resolver=resolver)
    cache._cache["bj920047"] = {}
    cache._cache["bj430047"] = {date(2020, 1, 2): 1.23}

    value, source = cache.get("bj920047", date(2020, 1, 2), "bj_pre_20211115")

    assert value == 1.23
    assert source == "akshare_stock_zh_a_hist_lineage"


def test_akshare_turnover_cache_does_not_use_heuristic_when_no_explicit_lineage() -> None:
    cache = common.AkShareTurnoverCache()
    cache._cache["bj920090"] = {}
    cache._cache["bj430090"] = {date(2020, 1, 2): 0.66}

    value, source = cache.get("bj920090", date(2020, 1, 2), "bj_pre_20211115")

    assert value is None
    assert source is None
