from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from backend.core.config.models import BacktestConfig
from backend.core.data.pg_provider import PostgresDataProvider
from backend.core.data.provider import DataProvider


def build_runtime_provider_from_config(
    cfg_obj: BacktestConfig,
    rules_path: str | Path,
    *,
    use_cache: bool = False,
) -> DataProvider:
    provider = PostgresDataProvider(
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
        data_source=cfg_obj.data_source,
        schema_mapping=cfg_obj.schema_mapping,
        rules_path=rules_path,
    )
    if not use_cache:
        return provider
    try:
        from backend.core.data.cached_provider import CachedDataProvider

        return CachedDataProvider(provider)
    except ImportError:
        return provider


def build_scoped_postgres_provider(
    cfg_obj: BacktestConfig,
    rules_path: str | Path,
    *,
    stocks_table: str,
) -> PostgresDataProvider:
    scoped_source = deepcopy(cfg_obj.data_source)
    scoped_source.stocks_table = str(stocks_table)
    scoped_source.v2_canonical_stocks_table = str(stocks_table)
    scoped_source.v2_runtime_stocks_table = str(stocks_table)
    scoped_source.v2_schema_mapping_table = str(stocks_table)
    return PostgresDataProvider(
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
        data_source=scoped_source,
        schema_mapping=cfg_obj.schema_mapping,
        rules_path=rules_path,
    )


__all__ = [
    "build_runtime_provider_from_config",
    "build_scoped_postgres_provider",
]
