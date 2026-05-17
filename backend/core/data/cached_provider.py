"""Process-local OHLCV parquet cache with DB-signature invalidation.

The cache is scoped by the provider's resolved market-data table/mapping and
can materialize either full-table parquet files or window/symbol slices. Slice
mode is the default because experiment runs normally need one bounded window and
one bounded asset pool, not the entire backing table.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
import pyarrow as pa
import pyarrow.parquet as pq

from .cn_etf_catalog import normalize_cn_etf_symbol
from .mapping import normalize_stock_symbol, safe_ident, to_canonical
from .pg_provider import PostgresDataProvider
from .provider import DataProvider

logger = logging.getLogger(__name__)

_LEGACY_CACHE_PATH = Path("/tmp/ohlcv_cache.parquet")
_LEGACY_CACHE_TMP = Path("/tmp/ohlcv_cache.parquet.tmp")
_LEGACY_META_PATH = Path("/tmp/ohlcv_cache.meta.json")
_DEFAULT_CACHE_DIR = Path("/tmp/ohlcv_cache")
_CACHE_VERSION = 4

_CHUNK_SIZE = 500_000
_WARMUP_TIMEOUT_MS = 600_000
_TRUE_VALUES = {"1", "true", "yes", "on"}
_TABLE_CACHE_MODES = {"table", "full", "full_table"}
_SAFE_PART_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _cache_root() -> Path:
    raw = str(os.environ.get("OHLCV_CACHE_DIR") or "").strip()
    return Path(raw).expanduser() if raw else _DEFAULT_CACHE_DIR


def _cache_mode() -> str:
    raw = str(os.environ.get("OHLCV_CACHE_MODE") or "slice").strip().lower()
    return "table" if raw in _TABLE_CACHE_MODES else "slice"


def _safe_part(value: Any) -> str:
    text = str(value or "unknown").strip() or "unknown"
    return _SAFE_PART_RE.sub("_", text)[:96]


def _hash_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _legacy_tmp_candidates() -> list[Path]:
    candidates = [_LEGACY_CACHE_TMP]
    candidates.extend(sorted(_LEGACY_CACHE_PATH.parent.glob(f"{_LEGACY_CACHE_PATH.name}.*.tmp")))
    return candidates


def _tmp_candidates(path: Path) -> list[Path]:
    return [path.with_suffix(path.suffix + ".tmp"), *sorted(path.parent.glob(f"{path.name}.*.tmp"))]


def _next_tmp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")


def _remove_paths(paths: list[Path]) -> list[str]:
    removed: list[str] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        try:
            if path.exists() and path.is_file():
                path.unlink()
                removed.append(key)
        except FileNotFoundError:
            continue
    return removed


def clear_ohlcv_cache_files() -> list[str]:
    removed = _remove_paths([_LEGACY_CACHE_PATH, *_legacy_tmp_candidates(), _LEGACY_META_PATH])
    root = _cache_root()
    if not root.exists():
        return removed

    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        try:
            if path.is_file():
                path.unlink()
                removed.append(str(path))
            elif path.is_dir():
                path.rmdir()
        except FileNotFoundError:
            continue
        except OSError:
            continue
    try:
        root.rmdir()
    except OSError:
        pass
    return removed


def get_ohlcv_cache_paths() -> dict[str, str]:
    root = _cache_root()
    return {
        "cache_dir": str(root),
        "table_cache_dir": str(root / "tables"),
        "slice_cache_dir": str(root / "slices"),
        "legacy_cache_path": str(_LEGACY_CACHE_PATH),
        "legacy_cache_tmp_path": str(_LEGACY_CACHE_TMP),
        "legacy_meta_path": str(_LEGACY_META_PATH),
    }


class CachedDataProvider(DataProvider):
    """Wrap PostgresDataProvider with parquet-backed OHLCV caching."""

    def __init__(self, inner: PostgresDataProvider) -> None:
        self._inner = inner
        self._cache_disabled = str(os.environ.get("OHLCV_CACHE_DISABLE", "")).strip().lower() in _TRUE_VALUES
        self._force_refresh = str(os.environ.get("OHLCV_CACHE_FORCE_REFRESH", "")).strip().lower() in _TRUE_VALUES
        self._cache_mode = _cache_mode()
        self._cache_audit: list[dict[str, Any]] = []
        self._db_signature: dict[str, Any] | None = None
        self._warm = False

        self._resolved_table = self._inner._source.resolved_stocks_table()
        self._mapping_key = self._inner._source.resolved_stocks_mapping_table()
        self._namespace = self._build_cache_namespace()
        root = _cache_root()
        self._table_cache_path = root / "tables" / f"{self._namespace}.parquet"
        self._table_meta_path = root / "tables" / f"{self._namespace}.meta.json"
        self._slice_dir = root / "slices" / self._namespace

        if self._cache_disabled:
            logger.info("OHLCV cache disabled by OHLCV_CACHE_DISABLE")
            return

        if self._force_refresh:
            removed = clear_ohlcv_cache_files()
            logger.info("OHLCV cache force refresh requested; removed=%s", removed)

        self._db_signature = self._current_db_signature()
        self._warm = self._is_table_cache_valid()

    def load_ohlcv_daily(
        self,
        symbols: list[str],
        start: date,
        end: date,
        source: str,
    ) -> pd.DataFrame:
        if self._cache_disabled:
            return self._inner.load_ohlcv_daily(symbols, start, end, source)
        if self._cache_mode == "slice":
            return self._load_slice_cache(symbols, start, end, source)
        return self._load_table_cache(symbols, start, end, source)

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

    def load_cn_etf_dividend_events(
        self,
        symbols: list[str] | None,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        return self._inner.load_cn_etf_dividend_events(symbols, start, end)

    @property
    def query_audit(self) -> list[dict]:
        return [*self._inner.query_audit, *self._cache_audit]

    def _build_cache_namespace(self) -> str:
        db = getattr(self._inner, "_db", None)
        payload = {
            "host": str(getattr(db, "host", "")),
            "port": str(getattr(db, "port", "")),
            "dbname": str(getattr(db, "dbname", "")),
            "resolved_table": self._resolved_table,
            "mapping_key": self._mapping_key,
            "cache_version": _CACHE_VERSION,
        }
        digest = _hash_json(payload)[:12]
        return f"{_safe_part(self._resolved_table)}__{_safe_part(self._mapping_key)}__{digest}"

    def _normalize_symbols(self, symbols: list[str]) -> list[str]:
        if self._resolved_table == "pams_cn_etf_daily":
            normalized = [normalize_cn_etf_symbol(s) for s in symbols]
        else:
            normalized = [normalize_stock_symbol(str(s)) for s in symbols]
        return sorted({str(symbol).strip().lower() for symbol in normalized if str(symbol).strip()})

    @staticmethod
    def _symbols_hash(symbols: list[str]) -> str:
        return hashlib.sha1("\n".join(sorted(symbols)).encode("utf-8")).hexdigest()

    def _record_cache_audit(
        self,
        *,
        source: str,
        cache_mode: str,
        cache_hit: bool,
        start: date,
        end: date,
        symbols: list[str],
        rows: int,
        elapsed: float,
        path: Path,
    ) -> None:
        self._cache_audit.append(
            {
                "provider": "ohlcv_cache",
                "source": source,
                "table": self._resolved_table,
                "mapping_key": self._mapping_key,
                "cache_mode": cache_mode,
                "cache_hit": bool(cache_hit),
                "symbol_count": int(len(symbols)),
                "symbols_hash": self._symbols_hash(symbols),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "row_count": int(rows),
                "elapsed_seconds": float(elapsed),
                "cache_path": str(path),
            }
        )

    def _load_table_cache(self, symbols: list[str], start: date, end: date, source: str) -> pd.DataFrame:
        t0 = time.perf_counter()
        norm_symbols = self._normalize_symbols(symbols)
        cache_hit = bool(self._warm)
        if not self._warm:
            self._warmup_full_table()

        df = pd.read_parquet(
            self._table_cache_path,
            filters=[
                ("date", ">=", pd.Timestamp(start)),
                ("date", "<=", pd.Timestamp(end)),
            ],
        )

        if norm_symbols:
            df = df[df["symbol"].isin(set(norm_symbols))]

        elapsed = time.perf_counter() - t0
        self._record_cache_audit(
            source=source,
            cache_mode="table",
            cache_hit=cache_hit,
            start=start,
            end=end,
            symbols=norm_symbols,
            rows=len(df),
            elapsed=elapsed,
            path=self._table_cache_path,
        )
        logger.info(
            "OHLCV table cache %s: %s rows, %.2fs",
            "HIT" if cache_hit else "MISS",
            f"{len(df):,}",
            elapsed,
        )
        return df.reset_index(drop=True)

    def _slice_paths(self, symbols: list[str], start: date, end: date) -> tuple[Path, Path, str]:
        key_payload = {
            "cache_version": _CACHE_VERSION,
            "resolved_table": self._resolved_table,
            "mapping_key": self._mapping_key,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "symbols_hash": self._symbols_hash(symbols),
            "symbol_count": len(symbols),
        }
        digest = _hash_json(key_payload)
        stem = f"{start.isoformat()}_{end.isoformat()}_{len(symbols)}_{digest[:16]}"
        cache_path = self._slice_dir / f"{stem}.parquet"
        meta_path = self._slice_dir / f"{stem}.meta.json"
        return cache_path, meta_path, digest

    def _load_slice_cache(self, symbols: list[str], start: date, end: date, source: str) -> pd.DataFrame:
        t0 = time.perf_counter()
        norm_symbols = self._normalize_symbols(symbols)
        if not norm_symbols:
            return self._inner.load_ohlcv_daily(symbols, start, end, source)

        cache_path, meta_path, slice_hash = self._slice_paths(norm_symbols, start, end)
        cache_hit = self._is_slice_cache_valid(
            cache_path=cache_path,
            meta_path=meta_path,
            start=start,
            end=end,
            symbols=norm_symbols,
            slice_hash=slice_hash,
        )
        if cache_hit:
            df = pd.read_parquet(cache_path)
        else:
            df = self._inner.load_ohlcv_daily(norm_symbols, start, end, source)
            df = df.reset_index(drop=True)
            self._write_slice_cache(cache_path, meta_path, df, start, end, norm_symbols, slice_hash)

        elapsed = time.perf_counter() - t0
        self._record_cache_audit(
            source=source,
            cache_mode="slice",
            cache_hit=cache_hit,
            start=start,
            end=end,
            symbols=norm_symbols,
            rows=len(df),
            elapsed=elapsed,
            path=cache_path,
        )
        logger.info(
            "OHLCV slice cache %s: %s rows, %.2fs, symbols=%s",
            "HIT" if cache_hit else "MISS",
            f"{len(df):,}",
            elapsed,
            len(norm_symbols),
        )
        return df.reset_index(drop=True)

    def _write_parquet_frame(self, path: Path, df: pd.DataFrame) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = _next_tmp_path(path)
        try:
            df.to_parquet(tmp_path, index=False, compression="snappy")
            os.replace(str(tmp_path), str(path))
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    def _write_slice_cache(
        self,
        cache_path: Path,
        meta_path: Path,
        df: pd.DataFrame,
        start: date,
        end: date,
        symbols: list[str],
        slice_hash: str,
    ) -> None:
        self._write_parquet_frame(cache_path, df)
        payload = {
            "cache_version": _CACHE_VERSION,
            "cache_mode": "slice",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "resolved_table": self._resolved_table,
            "mapping_key": self._mapping_key,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "symbol_count": int(len(symbols)),
            "symbols_hash": self._symbols_hash(symbols),
            "slice_hash": slice_hash,
            "row_count": int(len(df)),
            "db_signature": self._db_signature or self._current_db_signature(),
            "cache_path": str(cache_path),
        }
        meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _is_slice_cache_valid(
        self,
        *,
        cache_path: Path,
        meta_path: Path,
        start: date,
        end: date,
        symbols: list[str],
        slice_hash: str,
    ) -> bool:
        if not cache_path.exists():
            return False
        meta = self._load_cache_meta(meta_path, cache_path)
        if not meta:
            return False
        checks = {
            "cache_version": _CACHE_VERSION,
            "cache_mode": "slice",
            "resolved_table": self._resolved_table,
            "mapping_key": self._mapping_key,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "symbol_count": int(len(symbols)),
            "symbols_hash": self._symbols_hash(symbols),
            "slice_hash": slice_hash,
        }
        for key, expected in checks.items():
            if meta.get(key) != expected:
                _remove_paths([cache_path, meta_path, *_tmp_candidates(cache_path)])
                return False
        cached_signature = dict(meta.get("db_signature") or {})
        current_signature = dict(self._db_signature or self._current_db_signature())
        if cached_signature != current_signature:
            _remove_paths([cache_path, meta_path, *_tmp_candidates(cache_path)])
            self._db_signature = current_signature
            return False
        return True

    def _warmup_full_table(self) -> None:
        logger.info("OHLCV table cache MISS: rebuilding parquet cache from PostgreSQL")
        t0 = time.perf_counter()
        self._table_cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_tmp_path = _next_tmp_path(self._table_cache_path)

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
                                str(cache_tmp_path),
                                arrow_table.schema,
                                compression="snappy",
                            )
                        writer.write_table(arrow_table)
                        total_rows += len(chunk_out)
                        logger.info("  table cache warmup: %s rows written...", f"{total_rows:,}")

            if writer is None:
                logger.warning("OHLCV table cache rebuild returned zero rows; cache skipped")
                self._warm = True
                return

            writer.close()
            os.replace(str(cache_tmp_path), str(self._table_cache_path))
            self._write_table_cache_meta(total_rows)
        except Exception:
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass
            cache_tmp_path.unlink(missing_ok=True)
            logger.warning("OHLCV table cache rebuild failed", exc_info=True)
            raise

        elapsed = time.perf_counter() - t0
        size_mb = self._table_cache_path.stat().st_size / 1024 / 1024
        self._warm = True
        logger.info(
            "OHLCV table cache rebuilt: %s rows, %.0f MB, %.1fs",
            f"{total_rows:,}",
            size_mb,
            elapsed,
        )

    def _load_cache_meta(self, meta_path: Path, cache_path: Path) -> dict[str, Any] | None:
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("OHLCV cache meta unreadable; clearing cache path=%s", cache_path, exc_info=True)
            _remove_paths([cache_path, meta_path, *_tmp_candidates(cache_path)])
            return None

    def _write_table_cache_meta(self, row_count: int) -> None:
        payload = {
            "cache_version": _CACHE_VERSION,
            "cache_mode": "table",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "resolved_table": self._resolved_table,
            "mapping_key": self._mapping_key,
            "row_count": int(row_count),
            "db_signature": self._db_signature or self._current_db_signature(),
            "cache_path": str(self._table_cache_path),
            "meta_path": str(self._table_meta_path),
        }
        self._table_meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _is_table_cache_valid(self) -> bool:
        if not self._table_cache_path.exists():
            return False
        meta = self._load_cache_meta(self._table_meta_path, self._table_cache_path)
        if not meta:
            logger.info("OHLCV table cache exists but meta is missing; cache will be rebuilt")
            _remove_paths([self._table_cache_path, self._table_meta_path, *_tmp_candidates(self._table_cache_path)])
            return False
        expected = {
            "cache_version": _CACHE_VERSION,
            "cache_mode": "table",
            "resolved_table": self._resolved_table,
            "mapping_key": self._mapping_key,
        }
        for key, value in expected.items():
            if meta.get(key) != value:
                logger.info("OHLCV table cache %s mismatch; cache will be rebuilt", key)
                _remove_paths([self._table_cache_path, self._table_meta_path, *_tmp_candidates(self._table_cache_path)])
                return False
        cached_signature = dict(meta.get("db_signature") or {})
        current_signature = dict(self._db_signature or self._current_db_signature())
        if cached_signature != current_signature:
            logger.info(
                "OHLCV table cache signature mismatch; rebuilding cache. cached=%s current=%s",
                cached_signature,
                current_signature,
            )
            _remove_paths([self._table_cache_path, self._table_meta_path, *_tmp_candidates(self._table_cache_path)])
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

        base = {
            "resolved_table": resolved_table,
            "mapping_key": mapping_key,
            "schema_columns": sorted(existing),
        }
        if not row:
            return {
                **base,
                "row_count": 0,
                "max_trade_date": None,
                "max_created_at": None,
                "suspended_rows": 0,
            }

        return {
            **base,
            "row_count": int(row[0] or 0),
            "max_trade_date": row[1].isoformat() if row[1] is not None else None,
            "max_created_at": row[2].isoformat() if row[2] is not None else None,
            "suspended_rows": int(row[3] or 0),
        }
