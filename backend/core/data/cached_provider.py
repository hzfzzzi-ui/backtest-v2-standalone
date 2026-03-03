"""进程级 Parquet 缓存层 — 透明加速 OHLCV 数据加载。

首次调用 load_ohlcv_daily() 时从 PostgreSQL 全表 dump 到 /tmp/ohlcv_cache.parquet；
后续调用直接从 Parquet 读取，使用 predicate pushdown 按日期过滤。
缓存生命周期 = 容器生命周期（/tmp 非持久化，容器重启自动清空）。
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date
from pathlib import Path

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

# 全表 dump: 每次从 DB 取 50 万行，避免一次性 OOM
_CHUNK_SIZE = 500_000
# 全表 dump 超时 10 分钟
_WARMUP_TIMEOUT_MS = 600_000


class CachedDataProvider(DataProvider):
    """包装 PostgresDataProvider，对 load_ohlcv_daily 添加 Parquet 缓存。"""

    def __init__(self, inner: PostgresDataProvider) -> None:
        self._inner = inner
        self._warm: bool = _CACHE_PATH.exists()

    # ── OHLCV: 缓存核心 ──────────────────────────────────────

    def load_ohlcv_daily(
        self, symbols: list[str], start: date, end: date, source: str,
    ) -> pd.DataFrame:
        t0 = time.perf_counter()

        if not self._warm:
            self._warmup_full_table()

        # 从 Parquet 读取，predicate pushdown 按日期过滤
        df = pd.read_parquet(
            _CACHE_PATH,
            filters=[
                ("date", ">=", pd.Timestamp(start)),
                ("date", "<=", pd.Timestamp(end)),
            ],
        )

        # 内存过滤 symbols
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

    # ── 其他方法: 直接委托给内部 provider ──────────────────

    def load_trading_calendar_cn(self, start: date, end: date) -> pd.DatetimeIndex:
        return self._inner.load_trading_calendar_cn(start, end)

    def get_previous_trading_day_cn(self, start: date) -> date | None:
        return self._inner.get_previous_trading_day_cn(start)

    def load_instrument_rules(self, symbols: list[str]) -> pd.DataFrame:
        return self._inner.load_instrument_rules(symbols)

    def load_benchmark_daily(
        self, benchmark_symbol: str, start: date, end: date,
    ) -> pd.DataFrame:
        return self._inner.load_benchmark_daily(benchmark_symbol, start, end)

    def load_st_history(
        self, symbols: list[str], start: date, end: date,
    ) -> pd.DataFrame:
        return self._inner.load_st_history(symbols, start, end)

    def load_sector_indices(self, start: date, end: date) -> pd.DataFrame:
        return self._inner.load_sector_indices(start, end)

    def load_industry_mapping(self, symbols: list[str]) -> dict[str, str]:
        return self._inner.load_industry_mapping(symbols)

    @property
    def query_audit(self) -> list[dict]:
        return self._inner.query_audit

    # ── 内部: 全表 dump ──────────────────────────────────────

    def _warmup_full_table(self) -> None:
        """从 PostgreSQL 流式 dump 全表到 Parquet 文件。

        使用 server-side cursor 分块读取 + pyarrow ParquetWriter 增量写入，
        避免一次性将 13.6M 行加载到内存导致 OOM。
        """
        logger.info("OHLCV cache MISS — 正在从数据库流式 dump 全表到 Parquet...")
        t0 = time.perf_counter()

        # 构建全表查询（复用内部 provider 的 schema 发现逻辑）
        src = self._inner._source
        table = safe_ident(src.stocks_table)
        mapping = self._inner._schema[src.stocks_table]
        existing = self._inner._get_table_columns(src.stocks_table)

        ordered_keys = [
            "date", "symbol", "open", "high", "low", "close",
            "volume", "amount", "limit_up", "limit_down",
            "is_suspended", "adj_factor",
        ]
        cols = self._inner._filter_existing_cols(mapping, ordered_keys, existing)
        cols_sql = ", ".join(safe_ident(c) for c in cols)
        date_col = safe_ident(mapping["date"])
        sym_col = safe_ident(mapping["symbol"])

        query = f"SELECT {cols_sql} FROM {table} ORDER BY {date_col}, {sym_col}"

        # 使用 server-side cursor 流式读取，分块写入 Parquet
        db = self._inner._db
        writer: pq.ParquetWriter | None = None
        total_rows = 0

        try:
            with psycopg.connect(
                host=db.host, port=db.port, dbname=db.dbname,
                user=db.user, password=db.password, autocommit=False,
            ) as conn:
                # SET LOCAL 必须在普通 cursor 上执行（named cursor 会包装为 DECLARE）
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
                                str(_CACHE_TMP), arrow_table.schema, compression="snappy",
                            )
                        writer.write_table(arrow_table)
                        total_rows += len(chunk_out)
                        logger.info("  cache warmup: %s rows written...", f"{total_rows:,}")

            if writer is not None:
                writer.close()
                os.replace(str(_CACHE_TMP), str(_CACHE_PATH))
            else:
                logger.warning("OHLCV cache: 数据库返回 0 行，跳过缓存创建")
                self._warm = True
                return

        except Exception:
            _CACHE_TMP.unlink(missing_ok=True)
            logger.warning("OHLCV cache 写入失败，fallback 到无缓存模式", exc_info=True)
            raise

        elapsed = time.perf_counter() - t0
        size_mb = _CACHE_PATH.stat().st_size / 1024 / 1024
        self._warm = True
        logger.info(
            "OHLCV cache 已创建: %s rows, %.0f MB, %.1fs",
            f"{total_rows:,}",
            size_mb,
            elapsed,
        )
