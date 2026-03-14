from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.data.price_limits import round_price_to_tick

DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "ops"
DEFAULT_CONFIG_PATH = ROOT / "backend" / "configs" / "pams_cn_pg.json"
DEFAULT_INDEX_CODE = "000906.SH"
DEFAULT_START = "2007-01-15"
DEFAULT_END = "2026-03-10"
SOURCE_FIELDS = "date,code,preclose,isST"


@dataclass(slots=True)
class DbSettings:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def _load_env_file() -> dict[str, str]:
    env_path = ROOT / ".env"
    out: dict[str, str] = {}
    if not env_path.exists():
        return out
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def _load_db_settings() -> DbSettings:
    file_env = _load_env_file()
    cfg = {}
    if DEFAULT_CONFIG_PATH.exists():
        cfg = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    db_cfg = dict(cfg.get("db") or {})
    return DbSettings(
        host=str(os.environ.get("PGHOST") or os.environ.get("PAMS_PG_HOST") or db_cfg.get("host") or "pams-postgres"),
        port=int(os.environ.get("PGPORT") or os.environ.get("PAMS_PG_PORT") or db_cfg.get("port") or 5432),
        dbname=str(os.environ.get("PGDATABASE") or os.environ.get("PAMS_PG_DBNAME") or db_cfg.get("dbname") or "pams"),
        user=str(os.environ.get("PGUSER") or os.environ.get("PAMS_PG_USER") or db_cfg.get("user") or "pams"),
        password=str(
            os.environ.get("PGPASSWORD")
            or os.environ.get("PAMS_PG_PASSWORD")
            or file_env.get("POSTGRES_PASSWORD")
            or db_cfg.get("password")
            or ""
        ),
    )


def _connect():
    if psycopg is None:  # pragma: no cover
        raise RuntimeError("psycopg is required")
    db = _load_db_settings()
    return psycopg.connect(
        host=db.host,
        port=db.port,
        dbname=db.dbname,
        user=db.user,
        password=db.password,
        autocommit=False,
    )


def _load_baostock():
    try:
        import baostock as bs
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("baostock is required") from exc
    return bs


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fetchall(cur, sql: str, params: tuple[Any, ...] = ()) -> tuple[list[tuple[Any, ...]], list[str]]:
    cur.execute(sql, params)
    rows = cur.fetchall()
    cols = [d.name for d in cur.description] if cur.description else []
    return rows, cols


def _fetchdf(cur, sql: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
    rows, cols = _fetchall(cur, sql, params)
    return pd.DataFrame(rows, columns=cols)


def _normalize_ts_symbol(symbol: str) -> str:
    text = str(symbol or "").strip()
    if not text:
        raise ValueError("empty symbol")
    if "." in text:
        code, exch = text.split(".", 1)
        return f"{code.upper()}.{exch.upper()}"
    lower = text.lower()
    if lower.startswith(("sh", "sz", "bj")) and len(lower) == 8:
        return f"{lower[2:].upper()}.{lower[:2].upper()}"
    raise ValueError(f"unsupported symbol: {symbol}")


def _ts_to_internal(symbol: str) -> str:
    ts_symbol = _normalize_ts_symbol(symbol)
    code, exch = ts_symbol.split(".", 1)
    return f"{exch.lower()}{code}"


def _internal_to_ts(symbol: str) -> str:
    text = str(symbol or "").strip().lower()
    if text.startswith(("sh", "sz", "bj")) and len(text) == 8:
        return f"{text[2:].upper()}.{text[:2].upper()}"
    if "." in text:
        code, exch = text.split(".", 1)
        return f"{code.upper()}.{exch.upper()}"
    raise ValueError(f"unsupported symbol: {symbol}")


def _ts_to_bs(symbol: str) -> str:
    ts_symbol = _normalize_ts_symbol(symbol)
    code, exch = ts_symbol.split(".", 1)
    return f"{exch.lower()}.{code}"


def _parse_symbol_list(raw: str) -> list[str]:
    tokens = [item.strip() for item in str(raw or "").replace(";", ",").split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if not token:
            continue
        normalized = _normalize_ts_symbol(token)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _is_login_error(exc: Exception) -> bool:
    text = str(exc)
    return "10001001" in text or "用户未登录" in text


def _limit_pct_for_row(symbol: str, trade_date: date, is_st: bool) -> float:
    normalized = str(symbol or "").strip().lower()
    if normalized.startswith("bj") and trade_date >= date(2021, 11, 15):
        return 0.30
    if normalized.startswith("sh688") and trade_date >= date(2019, 7, 22):
        return 0.20
    if normalized.startswith("sz301"):
        return 0.20
    if normalized.startswith("sz300") and trade_date >= date(2020, 8, 24):
        return 0.20
    if is_st:
        return 0.05
    return 0.10


def _compute_source_limits(symbol: str, trade_date: date, preclose: Any, is_st: bool) -> tuple[float | None, float | None]:
    previous = pd.to_numeric(pd.Series([preclose]), errors="coerce").iloc[0]
    if pd.isna(previous) or float(previous) <= 0.0:
        return None, None
    pct = _limit_pct_for_row(symbol, trade_date, is_st)
    previous_value = float(previous)
    return (
        round_price_to_tick(previous_value * (1.0 + pct), symbol),
        round_price_to_tick(previous_value * (1.0 - pct), symbol),
    )


def _load_candidate_spans(start: date, end: date, index_code: str, explicit_symbols: list[str]) -> pd.DataFrame:
    if explicit_symbols:
        rows = [(symbol, start, end, 0) for symbol in explicit_symbols]
        return pd.DataFrame(rows, columns=["ts_symbol", "start_date", "end_date", "suspect_rows"])
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '1200000ms'")
            spans = _fetchdf(
                cur,
                """
                WITH membership AS (
                    SELECT
                        symbol AS ts_symbol,
                        lower(
                            CASE
                                WHEN symbol LIKE '%%.SH' THEN 'sh' || split_part(symbol, '.', 1)
                                WHEN symbol LIKE '%%.SZ' THEN 'sz' || split_part(symbol, '.', 1)
                                WHEN symbol LIKE '%%.BJ' THEN 'bj' || split_part(symbol, '.', 1)
                                ELSE symbol
                            END
                        ) AS symbol,
                        start_date,
                        COALESCE(end_date, CURRENT_DATE) AS end_date
                    FROM public.pit_index_constituents
                    WHERE index_code = %s
                ),
                st AS (
                    SELECT
                        lower(
                            CASE
                                WHEN ts_code LIKE '%%.SH' THEN 'sh' || split_part(ts_code, '.', 1)
                                WHEN ts_code LIKE '%%.SZ' THEN 'sz' || split_part(ts_code, '.', 1)
                                WHEN ts_code LIKE '%%.BJ' THEN 'bj' || split_part(ts_code, '.', 1)
                                ELSE ts_code
                            END
                        ) AS symbol,
                        start_date,
                        end_date
                    FROM public.pit_st_history
                    WHERE lower(
                            CASE
                                WHEN ts_code LIKE '%%.SH' THEN 'sh' || split_part(ts_code, '.', 1)
                                WHEN ts_code LIKE '%%.SZ' THEN 'sz' || split_part(ts_code, '.', 1)
                                WHEN ts_code LIKE '%%.BJ' THEN 'bj' || split_part(ts_code, '.', 1)
                                ELSE ts_code
                            END
                        ) IN (SELECT symbol FROM membership)
                ),
                base AS (
                    SELECT
                        m.ts_symbol,
                        o.symbol,
                        o.trade_date,
                        o.close,
                        o.adj_factor,
                        o.limit_up,
                        o.limit_down,
                        LAG(o.close) OVER (PARTITION BY o.symbol ORDER BY o.trade_date) AS prev_close,
                        LAG(o.adj_factor) OVER (PARTITION BY o.symbol ORDER BY o.trade_date) AS prev_adj_factor
                    FROM public.pams_ohlcv_daily AS o
                    JOIN membership AS m
                      ON m.symbol = o.symbol
                     AND o.trade_date >= m.start_date
                     AND o.trade_date <= m.end_date
                    WHERE o.market = 'CN_A'
                      AND o.trade_date >= %s
                      AND o.trade_date <= %s
                ),
                scored AS (
                    SELECT
                        b.*,
                        EXISTS (
                            SELECT 1
                            FROM st
                            WHERE st.symbol = b.symbol
                              AND st.start_date <= b.trade_date
                              AND (st.end_date IS NULL OR st.end_date >= b.trade_date)
                        ) AS is_st
                    FROM base AS b
                    WHERE b.prev_close IS NOT NULL
                ),
                checked AS (
                    SELECT
                        *,
                        CASE
                            WHEN prev_adj_factor IS NULL OR adj_factor IS NULL OR prev_adj_factor <= 0 OR adj_factor <= 0 THEN FALSE
                            WHEN ABS((adj_factor / prev_adj_factor) - 1.0) > 0.01 THEN TRUE
                            ELSE FALSE
                        END AS has_adj_jump,
                        CASE
                            WHEN symbol LIKE 'bj%%' AND trade_date >= DATE '2021-11-15' THEN 0.30
                            WHEN symbol LIKE 'sh688%%' AND trade_date >= DATE '2019-07-22' THEN 0.20
                            WHEN symbol LIKE 'sz301%%' THEN 0.20
                            WHEN symbol LIKE 'sz300%%' AND trade_date >= DATE '2020-08-24' THEN 0.20
                            WHEN is_st THEN 0.05
                            ELSE 0.10
                        END AS limit_pct
                    FROM scored
                ),
                suspect AS (
                    SELECT ts_symbol, trade_date
                    FROM checked
                    WHERE limit_up IS NULL
                       OR limit_down IS NULL
                       OR (
                            NOT has_adj_jump
                            AND (
                                    ABS(limit_up - ROUND(prev_close * (1.0 + limit_pct), 4)) > 0.011
                                 OR ABS(limit_down - ROUND(prev_close * (1.0 - limit_pct), 4)) > 0.011
                            )
                       )
                )
                SELECT
                    ts_symbol,
                    MIN(trade_date) AS start_date,
                    MAX(trade_date) AS end_date,
                    COUNT(*) AS suspect_rows
                FROM suspect
                GROUP BY ts_symbol
                ORDER BY ts_symbol
                """,
                (index_code, start, end),
            )
            return spans


def _fetch_db_rows(cur, ts_symbol: str, start: date, end: date) -> pd.DataFrame:
    symbol = _ts_to_internal(ts_symbol)
    return _fetchdf(
        cur,
        """
        SELECT symbol, trade_date, limit_up, limit_down
        FROM public.pams_ohlcv_daily
        WHERE market = 'CN_A'
          AND symbol = %s
          AND trade_date >= %s
          AND trade_date <= %s
        ORDER BY trade_date
        """,
        (symbol, start, end),
    )


def _fetch_source_rows(bs: Any, ts_symbol: str, start: date, end: date) -> pd.DataFrame:
    rs = bs.query_history_k_data_plus(
        _ts_to_bs(ts_symbol),
        SOURCE_FIELDS,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        frequency="d",
        adjustflag="3",
    )
    if rs.error_code != "0":
        raise RuntimeError(f"baostock query failed: {rs.error_code} {rs.error_msg}")
    frame = rs.get_data()
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["trade_date", "source_limit_up", "source_limit_down", "source_preclose", "source_is_st"])
    frame["trade_date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    frame["source_preclose"] = pd.to_numeric(frame["preclose"], errors="coerce")
    frame["source_is_st"] = pd.to_numeric(frame.get("isST"), errors="coerce").fillna(0).astype(int).eq(1)
    limit_pairs = [
        _compute_source_limits(_ts_to_internal(ts_symbol), row.trade_date, row.source_preclose, bool(row.source_is_st))
        for row in frame.itertuples(index=False)
    ]
    frame["source_limit_up"] = [pair[0] for pair in limit_pairs]
    frame["source_limit_down"] = [pair[1] for pair in limit_pairs]
    return (
        frame[["trade_date", "source_limit_up", "source_limit_down", "source_preclose", "source_is_st"]]
        .dropna(subset=["trade_date"])
        .drop_duplicates(subset=["trade_date"], keep="last")
        .sort_values("trade_date")
        .reset_index(drop=True)
    )


def _load_updates_into_temp(cur, updates: pd.DataFrame) -> None:
    cur.execute("TRUNCATE TABLE tmp_limit_updates")
    if updates.empty:
        return
    rows = [
        (
            str(row.symbol),
            row.trade_date,
            None if pd.isna(row.source_limit_up) else float(row.source_limit_up),
            None if pd.isna(row.source_limit_down) else float(row.source_limit_down),
        )
        for row in updates.itertuples(index=False)
    ]
    cur.executemany(
        """
        INSERT INTO tmp_limit_updates (
            symbol,
            trade_date,
            limit_up,
            limit_down
        )
        VALUES (%s, %s, %s, %s)
        """,
        rows,
    )


def run_rebuild(args: argparse.Namespace) -> dict[str, Any]:
    start = date.fromisoformat(str(args.start))
    end = date.fromisoformat(str(args.end))
    if start > end:
        raise ValueError("start must be <= end")

    explicit_symbols = _parse_symbol_list(str(args.symbols or ""))
    spans = _load_candidate_spans(start, end, str(args.index_code), explicit_symbols)
    symbol_offset = max(int(args.symbol_offset), 0)
    if symbol_offset > 0:
        spans = spans.iloc[symbol_offset:].reset_index(drop=True)
    max_symbols = max(int(args.max_symbols), 0)
    if max_symbols > 0:
        spans = spans.iloc[:max_symbols].reset_index(drop=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (DEFAULT_OUTPUT_ROOT / f"limit_price_rebuild_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "status": "ok",
        "apply": bool(args.apply),
        "index_code": str(args.index_code),
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "explicit_symbols": explicit_symbols,
        "symbol_offset": int(symbol_offset),
        "max_symbols": int(max_symbols),
        "candidate_symbol_count": int(len(spans)),
        "candidate_symbols_sample": spans["ts_symbol"].head(50).tolist() if not spans.empty else [],
        "candidate_rows_by_heuristic": int(pd.to_numeric(spans.get("suspect_rows"), errors="coerce").fillna(0).sum()) if not spans.empty else 0,
        "db_rows_scanned": 0,
        "source_rows_fetched": 0,
        "matched_rows": 0,
        "update_rows": 0,
        "unchanged_rows": 0,
        "source_missing_rows": 0,
        "failed_symbols": [],
    }

    spans_path = output_dir / "candidate_spans.csv"
    spans.to_csv(spans_path, index=False)
    summary["candidate_spans_csv"] = str(spans_path)

    bs = _load_baostock()

    def relogin() -> None:
        try:
            bs.logout()
        except Exception:
            pass
        login = bs.login()
        if login.error_code != "0":
            raise RuntimeError(f"baostock login failed: {login.error_msg}")

    relogin()

    compare_frames: list[pd.DataFrame] = []
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '1200000ms'")
                for idx, span in enumerate(spans.itertuples(index=False), start=1):
                    ts_symbol = str(span.ts_symbol)
                    symbol_start = span.start_date
                    symbol_end = span.end_date
                    try:
                        db_rows = _fetch_db_rows(cur, ts_symbol, symbol_start, symbol_end)
                        try:
                            source_rows = _fetch_source_rows(bs, ts_symbol, symbol_start, symbol_end)
                        except Exception as exc:
                            if not _is_login_error(exc):
                                raise
                            relogin()
                            source_rows = _fetch_source_rows(bs, ts_symbol, symbol_start, symbol_end)
                        if db_rows.empty:
                            continue
                        merged = db_rows.merge(source_rows, on="trade_date", how="left")
                        merged["ts_symbol"] = ts_symbol
                        merged["db_limit_up"] = pd.to_numeric(merged["limit_up"], errors="coerce")
                        merged["db_limit_down"] = pd.to_numeric(merged["limit_down"], errors="coerce")
                        merged["source_limit_up"] = pd.to_numeric(merged["source_limit_up"], errors="coerce")
                        merged["source_limit_down"] = pd.to_numeric(merged["source_limit_down"], errors="coerce")
                        merged["up_diff"] = (merged["db_limit_up"] - merged["source_limit_up"]).abs()
                        merged["down_diff"] = (merged["db_limit_down"] - merged["source_limit_down"]).abs()
                        merged["needs_update"] = (
                            merged["source_limit_up"].notna()
                            & merged["source_limit_down"].notna()
                            & (
                                merged["db_limit_up"].isna()
                                | merged["db_limit_down"].isna()
                                | (merged["up_diff"] > 0.011)
                                | (merged["down_diff"] > 0.011)
                            )
                        )
                        compare_frames.append(merged)
                        summary["db_rows_scanned"] += int(len(db_rows))
                        summary["source_rows_fetched"] += int(len(source_rows))
                    except Exception as exc:
                        summary["failed_symbols"].append({"ts_symbol": ts_symbol, "error": str(exc)})
                    if idx % 50 == 0:
                        print(f"[limit] {idx}/{len(spans)} symbols processed")
                    time.sleep(float(args.sleep_seconds))
    finally:
        try:
            bs.logout()
        except Exception:
            pass

    compare = pd.concat(compare_frames, ignore_index=True) if compare_frames else pd.DataFrame()
    if compare.empty:
        summary["status"] = "no_candidates"
        summary_path = output_dir / "summary.json"
        summary["summary_json"] = str(summary_path)
        _write_json(summary_path, summary)
        return summary

    summary["matched_rows"] = int(compare["source_limit_up"].notna().sum())
    summary["source_missing_rows"] = int(compare["source_limit_up"].isna().sum())
    summary["update_rows"] = int(compare["needs_update"].sum())
    summary["unchanged_rows"] = int((~compare["needs_update"] & compare["source_limit_up"].notna()).sum())

    sample_cols = [
        "ts_symbol",
        "symbol",
        "trade_date",
        "db_limit_up",
        "source_limit_up",
        "db_limit_down",
        "source_limit_down",
        "source_preclose",
        "source_is_st",
        "up_diff",
        "down_diff",
        "needs_update",
    ]
    compare_sample_path = output_dir / "compare_sample.csv"
    compare[sample_cols].head(1000).to_csv(compare_sample_path, index=False)
    summary["compare_sample_csv"] = str(compare_sample_path)

    updates = compare.loc[compare["needs_update"], ["symbol", "trade_date", "source_limit_up", "source_limit_down"]].copy()
    updates_path = output_dir / "limit_updates.csv"
    updates.to_csv(updates_path, index=False)
    summary["limit_updates_csv"] = str(updates_path)

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '1200000ms'")
            cur.execute(
                """
                CREATE TEMP TABLE IF NOT EXISTS tmp_limit_updates (
                    symbol text NOT NULL,
                    trade_date date NOT NULL,
                    limit_up numeric,
                    limit_down numeric
                ) ON COMMIT DROP
                """
            )
            _load_updates_into_temp(cur, updates)
            cur.execute(
                """
                UPDATE public.pams_ohlcv_daily AS target
                SET
                    limit_up = src.limit_up,
                    limit_down = src.limit_down
                FROM tmp_limit_updates AS src
                WHERE target.market = 'CN_A'
                  AND target.symbol = src.symbol
                  AND target.trade_date = src.trade_date
                """
            )
            summary["updated_rows_in_db"] = int(cur.rowcount or 0)
            if args.apply:
                conn.commit()
            else:
                conn.rollback()
                summary["status"] = "dry_run"

    summary_path = output_dir / "summary.json"
    summary["summary_json"] = str(summary_path)
    _write_json(summary_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and rebuild pams_ohlcv_daily limit_up/limit_down from baostock preclose")
    parser.add_argument("--start", default=DEFAULT_START, help="inclusive start date YYYY-MM-DD")
    parser.add_argument("--end", default=DEFAULT_END, help="inclusive end date YYYY-MM-DD")
    parser.add_argument("--index-code", default=DEFAULT_INDEX_CODE)
    parser.add_argument("--symbols", default="", help="optional comma-separated symbols in TS/internal format")
    parser.add_argument("--symbol-offset", type=int, default=0, help="skip this many candidate symbols before processing")
    parser.add_argument("--max-symbols", type=int, default=0, help="optional candidate symbol cap; 0 means no cap")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="sleep between baostock requests")
    parser.add_argument("--output-dir", default="", help="output directory for artifacts")
    parser.add_argument("--apply", action="store_true", help="commit DB writes; default is dry-run rollback")
    args = parser.parse_args()

    summary = run_rebuild(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_json={summary['summary_json']}")


if __name__ == "__main__":
    main()
