"""Process-local OHLCV parquet cache with DB-signature invalidation.

The first `load_ohlcv_daily()` call dumps the full PostgreSQL OHLCV table to
`/tmp/ohlcv_cache.parquet`. Subsequent reads use parquet predicate pushdown on
date and in-memory symbol filtering.

To avoid stale-cache failures after DB repair work, the cache now tracks a
lightweight DB signature and invalidates itself when the signature changes.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
import pyarrow as pa
import pyarrow.parquet as pq

from .mapping import normalize_stock_symbol, safe_ident, to_canonical
from .pg_provider import PostgresDataProvider
from .provider import DataProvider

logger = logging.getLogger(__name__)

_CACHE_PATH = Path("/tmp/ohlcv_cache.parquet")
_CACHE_TMP = Path("/tmp/ohlcv_cache.parquet.tmp")
_META_PATH = Path("/tmp/ohlcv_cache.meta.json")
_CACHE_VERSION = 3

_CHUNK_SIZE = 500_000
_WARMUP_TIMEOUT_MS = 600_000
_TRUE_VALUES = {"1", "true", "yes", "on"}


def clear_ohlcv_cache_files() -> list[str]:
    removed: list[str] = []
    for path in (_CACHE_PATH, _CACHE_TMP, _META_PATH):
        try:
            if path.exists():
                path.unlink()
                removed.append(str(path))
        except FileNotFoundError:
            continue
    return removed


def get_ohlcv_cache_paths() -> dict[str, str]:
    return {
        "cache_path": str(_CACHE_PATH),
        "cache_tmp_path": str(_CACHE_TMP),
        "meta_path": str(_META_PATH),
    }


class CachedDataProvider(DataProvider):
    """Wrap PostgresDataProvider with parquet-backed OHLCV caching."""

    def __init__(self, inner: PostgresDataProvider) -> None:
        self._inner = inner
        self._cache_disabled = str(os.environ.get("OHLCV_CACHE_DISABLE", "")).strip().lower() in _TRUE_VALUES
        self._force_refresh = str(os.environ.get("OHLCV_CACHE_FORCE_REFRESH", "")).strip().lower() in _TRUE_VALUES
        self._db_signature: dict[str, Any] | None = None
        self._warm = False

        if self._cache_disabled:
            logger.info("OHLCV cache disabled by OHLCV_CACHE_DISABLE")
            return

        if self._force_refresh:
            removed = clear_ohlcv_cache_files()
            logger.info("OHLCV cache force refresh requested; removed=%s", removed)

        self._db_signature = self._current_db_signature()
        self._warm = self._is_cache_valid()

    def load_ohlcv_daily(
        self,
        symbols: list[str],
        start: date,
        end: date,
        source: str,
    ) -> pd.DataFrame:
        t0 = time.perf_counter()

        if self._cache_disabled:
            return self._inner.load_ohlcv_daily(symbols, start, end, source)

        if not self._warm:
            self._warmup_full_table()

        df = pd.read_parquet(
            _CACHE_PATH,
            filters=[
                ("date", ">=", pd.Timestamp(start)),
                ("date", "<=", pd.Timestamp(end)),
            ],
        )

        if symbols:
            norm = {normalize_stock_symbol(s) for s in symbols}
            df = df[df["symbol"].isin(norm)]

        elapsed = time.perf_counter() - t0
        logger.info(
            "OHLCV cache HIT: %s rows, %.2fs (parquet read + filter)",
            f"{len(df):,}",
            elapsed,
        )
        return df.reset_index(drop=True)

    def load_trading_calendar_cn(self, start: date, end: date) -> pd.DatetimeIndex:
        return self._inner.load_trading_calendar_cn(start, end)

    def get_previous_trading_day_cn(self, start: date) -> date | None:
        return self._inner.get_previous_trading_day_cn(start)

    def load_instrument_rules(self, symbols: list[str]) -> pd.DataFrame:
        return self._inner.load_instrument_rules(symbols)

    def load_benchmark_daily(self, benchmark_symbol: str, start: date, end: date) -> pd.DataFrame:
        return self._inner.load_benchmark_daily(benchmark_symbol, start, end)

    def load_st_history(self, symbols: list[str], start: date, end: date) -> pd.DataFrame:
        return self._inner.load_st_history(symbols, start, end)

    def load_sector_indices(self, start: date, end: date) -> pd.DataFrame:
        return self._inner.load_sector_indices(start, end)

    def load_industry_mapping(self, symbols: list[str]) -> dict[str, str]:
        return self._inner.load_industry_mapping(symbols)

    def load_industry_history(self, symbols: list[str], start: date, end: date) -> pd.DataFrame:
        return self._inner.load_industry_history(symbols, start, end)

    def load_security_master(self, symbols: list[str]) -> pd.DataFrame:
        return self._inner.load_security_master(symbols)

    def load_stock_moneyflow(
        self,
        symbols: list[str],
        start: date,
        end: date,
        table: str = "pit_stock_moneyflow_v2",
    ) -> pd.DataFrame:
        return self._inner.load_stock_moneyflow(symbols, start, end, table=table)

    def load_moneyflow_whitelist(
        self,
        start: date,
        end: date,
        table: str = "pit_stock_moneyflow_v2_whitelist_daily",
    ) -> pd.DataFrame:
        return self._inner.load_moneyflow_whitelist(start, end, table=table)

    def load_index_constituent_history(self, index_code: str, start: date, end: date) -> pd.DataFrame:
        return self._inner.load_index_constituent_history(index_code, start, end)

    def load_index_constituent_refresh_membership(self, index_code: str) -> pd.DataFrame:
        return self._inner.load_index_constituent_refresh_membership(index_code)

    def load_cn_etf_catalog(self, symbols: list[str] | None = None) -> pd.DataFrame:
        return self._inner.load_cn_etf_catalog(symbols)

    def load_cn_etf_coverage(self, symbols: list[str] | None = None) -> pd.DataFrame:
        return self._inner.load_cn_etf_coverage(symbols)

    @property
    def query_audit(self) -> list[dict]:
        return self._inner.query_audit

    def _warmup_full_table(self) -> None:
        logger.info("OHLCV cache MISS: rebuilding parquet cache from PostgreSQL")
        t0 = time.perf_counter()

        src = self._inner._source
        resolved_table = src.resolved_stocks_table()
        mapping_key = src.resolved_stocks_mapping_table()
        table = safe_ident(resolved_table)
        mapping = self._inner._schema[mapping_key]
        existing = self._inner._get_table_columns(resolved_table)

        ordered_keys = [
            "date",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "limit_up",
            "limit_down",
            "is_suspended",
            "is_st",
            "adj_factor",
            "turnover_rate",
            "turnover_rate_f",
            "volume_ratio",
            "float_share",
            "free_share",
            "circ_mv",
        ]
        cols = self._inner._filter_existing_cols(mapping, ordered_keys, existing)
        if "is_st" not in cols and "is_st" in existing:
            cols.append("is_st")
        cols_sql = ", ".join(safe_ident(c) for c in cols)
        date_col = safe_ident(mapping["date"])
        sym_col = safe_ident(mapping["symbol"])
        query = f"SELECT {cols_sql} FROM {table} ORDER BY {date_col}, {sym_col}"

        db = self._inner._db
        writer: pq.ParquetWriter | None = None
        total_rows = 0

        try:
            with psycopg.connect(
                host=db.host,
                port=db.port,
                dbname=db.dbname,
                user=db.user,
                password=db.password,
                autocommit=False,
            ) as conn:
                conn.execute(f"SET LOCAL statement_timeout = '{_WARMUP_TIMEOUT_MS}ms'")
                conn.execute("SET TRANSACTION READ ONLY")
                with conn.cursor(name="ohlcv_cache_warmup") as cur:
                    cur.execute(query)
                    col_names = [d.name for d in cur.description]

                    while True:
                        rows = cur.fetchmany(_CHUNK_SIZE)
                        if not rows:
                            break

                        chunk_df = pd.DataFrame(rows, columns=col_names)
                        chunk_out, _ = to_canonical(chunk_df, mapping)
                        chunk_out["symbol"] = chunk_out["symbol"].astype(str).str.lower()

                        arrow_table = pa.Table.from_pandas(chunk_out, preserve_index=False)
                        if writer is None:
                            writer = pq.ParquetWriter(
                                str(_CACHE_TMP),
                                arrow_table.schema,
                                compression="snappy",
                            )
                        writer.write_table(arrow_table)
                        total_rows += len(chunk_out)
                        logger.info("  cache warmup: %s rows written...", f"{total_rows:,}")

            if writer is None:
                logger.warning("OHLCV cache rebuild returned zero rows; cache skipped")
                self._warm = True
                return

            writer.close()
            os.replace(str(_CACHE_TMP), str(_CACHE_PATH))
            self._write_cache_meta()
        except Exception:
            _CACHE_TMP.unlink(missing_ok=True)
            logger.warning("OHLCV cache rebuild failed", exc_info=True)
            raise

        elapsed = time.perf_counter() - t0
        size_mb = _CACHE_PATH.stat().st_size / 1024 / 1024
        self._warm = True
        logger.info(
            "OHLCV cache rebuilt: %s rows, %.0f MB, %.1fs",
            f"{total_rows:,}",
            size_mb,
            elapsed,
        )

    def _load_cache_meta(self) -> dict[str, Any] | None:
        if not _META_PATH.exists():
            return None
        try:
            return json.loads(_META_PATH.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("OHLCV cache meta unreadable; clearing local cache files", exc_info=True)
            clear_ohlcv_cache_files()
            return None

    def _write_cache_meta(self) -> None:
        payload = {
            "cache_version": _CACHE_VERSION,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "db_signature": self._db_signature or self._current_db_signature(),
            **get_ohlcv_cache_paths(),
        }
        _META_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _is_cache_valid(self) -> bool:
        if not _CACHE_PATH.exists():
            return False
        meta = self._load_cache_meta()
        if not meta:
            logger.info("OHLCV cache exists but meta is missing; cache will be rebuilt")
            clear_ohlcv_cache_files()
            return False
        if int(meta.get("cache_version") or 0) != _CACHE_VERSION:
            logger.info("OHLCV cache version mismatch; cache will be rebuilt")
            clear_ohlcv_cache_files()
            return False
        cached_signature = dict(meta.get("db_signature") or {})
        current_signature = dict(self._db_signature or self._current_db_signature())
        if cached_signature != current_signature:
            logger.info(
                "OHLCV cache signature mismatch; rebuilding cache. cached=%s current=%s",
                cached_signature,
                current_signature,
            )
            clear_ohlcv_cache_files()
            self._db_signature = current_signature
            return False
        return True

    def _current_db_signature(self) -> dict[str, Any]:
        src = self._inner._source
        resolved_table = src.resolved_stocks_table()
        mapping_key = src.resolved_stocks_mapping_table()
        table = safe_ident(resolved_table)
        mapping = self._inner._schema[mapping_key]
        existing = self._inner._get_table_columns(resolved_table)

        date_col = safe_ident(mapping["date"])
        created_col = "created_at" if "created_at" in existing else None
        suspended_col = "is_suspended" if "is_suspended" in existing else None

        select_cols = [
            "count(*)::bigint as row_count",
            f"max({date_col}) as max_trade_date",
            f"max({safe_ident(created_col)}) as max_created_at" if created_col else "null::timestamptz as max_created_at",
            (
                f"count(*) filter (where coalesce({safe_ident(suspended_col)}, false))::bigint as suspended_rows"
                if suspended_col else
                "0::bigint as suspended_rows"
            ),
        ]
        query = f"SELECT {', '.join(select_cols)} FROM {table}"
        db = self._inner._db
        with psycopg.connect(
            host=db.host,
            port=db.port,
            dbname=db.dbname,
            user=db.user,
            password=db.password,
            autocommit=False,
        ) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute(f"SET LOCAL statement_timeout = '{_WARMUP_TIMEOUT_MS}ms'")
            with conn.cursor() as cur:
                cur.execute(query)
                row = cur.fetchone()

        if not row:
            return {
                "row_count": 0,
                "max_trade_date": None,
                "max_created_at": None,
                "suspended_rows": 0,
                "schema_columns": sorted(existing),
            }

        return {
            "row_count": int(row[0] or 0),
            "max_trade_date": row[1].isoformat() if row[1] is not None else None,
            "max_created_at": row[2].isoformat() if row[2] is not None else None,
            "suspended_rows": int(row[3] or 0),
            "schema_columns": sorted(existing),
        }
