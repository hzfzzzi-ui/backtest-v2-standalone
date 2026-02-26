from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.config.models import DBConfig, DBRuntimeConfig, DataSourceConfig
from .errors import DatabaseConnectionError, DatabaseQueryError
from .mapping import normalize_index_symbol, normalize_stock_symbol, safe_ident, to_canonical
from .provider import DataProvider
from .rules_loader import load_rules_csv

try:
    import psycopg
except Exception as exc:  # pragma: no cover
    psycopg = None
    _PSYCOPG_IMPORT_ERROR = exc
else:
    _PSYCOPG_IMPORT_ERROR = None


class PostgresDataProvider(DataProvider):
    def __init__(
        self,
        db: DBConfig,
        runtime: DBRuntimeConfig,
        data_source: DataSourceConfig,
        schema_mapping: dict[str, dict[str, str]],
        rules_path: str | Path,
    ) -> None:
        if psycopg is None:  # pragma: no cover
            raise RuntimeError(f"psycopg is required: {_PSYCOPG_IMPORT_ERROR}")
        self._db = db
        self._runtime = runtime
        self._source = data_source
        self._schema = schema_mapping
        self._rules_path = str(rules_path)
        self._audit: list[dict[str, Any]] = []
        self._table_columns_cache: dict[str, set[str]] = {}

    @property
    def query_audit(self) -> list[dict]:
        return list(self._audit)

    def _conn(self):
        try:
            return psycopg.connect(
                host=self._db.host,
                port=self._db.port,
                dbname=self._db.dbname,
                user=self._db.user,
                password=self._db.password,
                autocommit=False,
            )
        except psycopg.OperationalError as exc:
            msg = str(exc)
            if "authentication" in msg.lower() or "password" in msg.lower():
                raise DatabaseConnectionError(
                    "database authentication failed",
                    context={"host": self._db.host, "port": self._db.port, "user": self._db.user},
                ) from exc
            raise DatabaseConnectionError(
                f"database connection failed: {msg}",
                context={"host": self._db.host, "port": self._db.port},
            ) from exc

    def _exec_df(self, query: str, params: tuple[Any, ...], audit_meta: dict[str, Any]) -> pd.DataFrame:
        table = audit_meta.get("table", "unknown")
        query_type = audit_meta.get("source", "unknown")
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    cur.execute(f"SET LOCAL statement_timeout = '{int(self._runtime.statement_timeout_ms)}ms'")
                    cur.execute(query, params)
                    rows = cur.fetchall()
                    cols = [d.name for d in cur.description] if cur.description else []
        except DatabaseConnectionError:
            raise
        except psycopg.errors.QueryCanceled as exc:
            raise DatabaseQueryError(
                f"query timed out after {self._runtime.statement_timeout_ms}ms",
                context={"table": table, "query_type": query_type, "timeout_ms": self._runtime.statement_timeout_ms},
            ) from exc
        except psycopg.Error as exc:
            raise DatabaseQueryError(
                f"query failed: {exc}",
                context={"table": table, "query_type": query_type},
            ) from exc
        df = pd.DataFrame(rows, columns=cols)
        meta = dict(audit_meta)
        meta["query_template"] = query
        meta["params"] = [str(p) for p in params]
        meta["row_count"] = int(len(df))
        self._audit.append(meta)
        return df

    def _get_table_columns(self, table_name: str) -> set[str]:
        if table_name in self._table_columns_cache:
            return self._table_columns_cache[table_name]
        q = (
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = %s"
        )
        raw = self._exec_df(
            q,
            (table_name,),
            {
                "provider": "postgres",
                "source": "schema_columns",
                "table": table_name,
                "symbols": [],
                "start": "",
                "end": "",
            },
        )
        cols = set(raw.get("column_name", pd.Series(dtype=str)).astype(str).tolist())
        self._table_columns_cache[table_name] = cols
        return cols

    @staticmethod
    def _filter_existing_cols(mapping: dict[str, str], ordered_keys: list[str], existing_cols: set[str]) -> list[str]:
        cols: list[str] = []
        for key in ordered_keys:
            col = mapping.get(key, "")
            if col and col in existing_cols:
                cols.append(col)
        return cols

    def load_ohlcv_daily(self, symbols: list[str], start: date, end: date, source: str) -> pd.DataFrame:
        table = safe_ident(self._source.stocks_table)
        mapping = self._schema[self._source.stocks_table]
        existing_cols = self._get_table_columns(self._source.stocks_table)
        cols = self._filter_existing_cols(
            mapping,
            ["date", "symbol", "open", "high", "low", "close", "volume", "amount"],
            existing_cols,
        )
        cols_sql = ", ".join(safe_ident(c) for c in cols)
        q = (
            f"SELECT {cols_sql} FROM {table} "
            f"WHERE {safe_ident(mapping['date'])} >= %s AND {safe_ident(mapping['date'])} <= %s "
            f"AND {safe_ident(mapping['symbol'])} = ANY(%s) "
            f"ORDER BY {safe_ident(mapping['date'])}, {safe_ident(mapping['symbol'])}"
        )
        db_symbols = [normalize_stock_symbol(s) for s in symbols]
        raw = self._exec_df(
            q,
            (start, end, db_symbols),
            {
                "provider": "postgres",
                "source": source,
                "table": self._source.stocks_table,
                "symbols": sorted(db_symbols),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "db": asdict(self._db) | {"password": "***"},
            },
        )
        out, warnings = to_canonical(raw, mapping)
        out["symbol"] = out["symbol"].astype(str).str.lower()
        self._audit[-1]["warnings"] = warnings
        return out

    def load_benchmark_daily(self, benchmark_symbol: str, start: date, end: date) -> pd.DataFrame:
        idx_table = safe_ident(self._source.index_table)
        idx_map = self._schema[self._source.index_table]
        idx_existing_cols = self._get_table_columns(self._source.index_table)
        idx_cols = self._filter_existing_cols(
            idx_map,
            ["date", "symbol", "open", "high", "low", "close", "volume", "amount"],
            idx_existing_cols,
        )
        idx_cols_sql = ", ".join(safe_ident(c) for c in idx_cols)
        idx_query = (
            f"SELECT {idx_cols_sql} FROM {idx_table} "
            f"WHERE {safe_ident(idx_map['date'])} >= %s AND {safe_ident(idx_map['date'])} <= %s "
            f"AND {safe_ident(idx_map['symbol'])} = %s "
            f"ORDER BY {safe_ident(idx_map['date'])}, {safe_ident(idx_map['symbol'])}"
        )

        target_ts = normalize_index_symbol(benchmark_symbol)
        if self._source.prefer_index_table:
            raw_idx = self._exec_df(
                idx_query,
                (start, end, target_ts),
                {
                    "provider": "postgres",
                    "source": "benchmark",
                    "table": self._source.index_table,
                    "symbols": [target_ts],
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                },
            )
            idx_can, warnings = to_canonical(raw_idx, idx_map)
            self._audit[-1]["warnings"] = warnings
            if not idx_can.empty:
                idx_can["symbol"] = benchmark_symbol
                return idx_can

        if not self._source.allow_cn_index_in_stocks_table:
            raise ValueError(
                f"benchmark {benchmark_symbol} not found in {self._source.index_table} and fallback is disabled"
            )

        stock_table = safe_ident(self._source.stocks_table)
        stock_map = self._schema[self._source.stocks_table]
        stock_existing_cols = self._get_table_columns(self._source.stocks_table)
        cols = self._filter_existing_cols(
            stock_map,
            ["date", "symbol", "open", "high", "low", "close", "volume", "amount"],
            stock_existing_cols,
        )
        cols_sql = ", ".join(safe_ident(c) for c in cols)

        filter_col = safe_ident(self._source.cn_index_filter_column)
        stock_q = (
            f"SELECT {cols_sql} FROM {stock_table} "
            f"WHERE {safe_ident(stock_map['date'])} >= %s AND {safe_ident(stock_map['date'])} <= %s "
            f"AND {safe_ident(stock_map['symbol'])} = %s "
            f"AND {filter_col} = %s "
            f"ORDER BY {safe_ident(stock_map['date'])}, {safe_ident(stock_map['symbol'])}"
        )
        internal_symbol = normalize_stock_symbol(benchmark_symbol)
        raw = self._exec_df(
            stock_q,
            (start, end, internal_symbol, self._source.cn_index_filter_value),
            {
                "provider": "postgres",
                "source": "benchmark_fallback",
                "table": self._source.stocks_table,
                "symbols": [internal_symbol],
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
        )
        can, warnings = to_canonical(raw, stock_map)
        self._audit[-1]["warnings"] = warnings
        if can.empty:
            raise ValueError(f"benchmark {benchmark_symbol} empty after fallback query")
        can["symbol"] = benchmark_symbol
        return can

    def load_trading_calendar_cn(self, start: date, end: date) -> pd.DatetimeIndex:
        table = safe_ident(self._source.stocks_table)
        date_col = safe_ident(self._schema[self._source.stocks_table]["date"])
        q = f"SELECT DISTINCT {date_col} AS date FROM {table} WHERE {date_col} >= %s AND {date_col} <= %s ORDER BY {date_col}"
        raw = self._exec_df(
            q,
            (start, end),
            {
                "provider": "postgres",
                "source": "calendar",
                "table": self._source.stocks_table,
                "symbols": [],
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
        )
        return pd.DatetimeIndex(pd.to_datetime(raw["date"]).dt.normalize().tolist())

    def get_previous_trading_day_cn(self, start: date) -> date | None:
        idx_table = safe_ident(self._source.index_table)
        idx_date_col = safe_ident(self._schema[self._source.index_table]["date"])
        q_idx = (
            f"SELECT MAX({idx_date_col}) AS prev_day "
            f"FROM {idx_table} "
            f"WHERE {idx_date_col} < %s"
        )
        raw_idx = self._exec_df(
            q_idx,
            (start,),
            {
                "provider": "postgres",
                "source": "prev_day",
                "table": self._source.index_table,
                "symbols": [],
                "start": start.isoformat(),
                "end": start.isoformat(),
            },
        )
        if not raw_idx.empty and raw_idx.iloc[0]["prev_day"] is not None:
            return pd.Timestamp(raw_idx.iloc[0]["prev_day"]).date()

        stocks_table = safe_ident(self._source.stocks_table)
        stocks_date_col = safe_ident(self._schema[self._source.stocks_table]["date"])
        q_stk = (
            f"SELECT MAX({stocks_date_col}) AS prev_day "
            f"FROM {stocks_table} "
            f"WHERE {stocks_date_col} < %s"
        )
        raw_stk = self._exec_df(
            q_stk,
            (start,),
            {
                "provider": "postgres",
                "source": "prev_day_fallback",
                "table": self._source.stocks_table,
                "symbols": [],
                "start": start.isoformat(),
                "end": start.isoformat(),
            },
        )
        if raw_stk.empty or raw_stk.iloc[0]["prev_day"] is None:
            return None
        return pd.Timestamp(raw_stk.iloc[0]["prev_day"]).date()

    def load_instrument_rules(self, symbols: list[str]) -> pd.DataFrame:
        return load_rules_csv(self._rules_path, symbols)
