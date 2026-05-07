from __future__ import annotations

import argparse
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

from backend.core.data.pg_env import connect as pg_connect
from backend.core.data.pg_env import load_db_settings as load_shared_db_settings
from backend.core.data.pg_env import read_env_file as read_shared_env_file

DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "ops"
DEFAULT_CONFIG_PATH = ROOT / "backend" / "configs" / "pams_cn_pg.json"
DEFAULT_TABLE = "pams_ohlcv_daily"
DEFAULT_INDEX_CODE = "000906.SH"
KCB_20PCT_START = date(2019, 7, 22)
GEM_20PCT_START = date(2020, 8, 24)
BSE_30PCT_START = date(2021, 11, 15)
RAW_FIELDS = "date,code,open,high,low,close,preclose,volume,amount,turn,tradestatus,isST"
HFQ_FIELDS = "date,close"
INDEX_FIELDS = "date,code,open,high,low,close,preclose,volume,amount"
UPSERT_COLUMNS = [
    "symbol",
    "market",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "turnover",
    "adj_factor",
    "limit_up",
    "limit_down",
    "is_suspended",
    "turnover_rate",
    "turnover_rate_f",
    "volume_ratio",
    "float_share",
    "free_share",
    "circ_mv",
]


@dataclass(slots=True)
class DbSettings:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def _load_env_file() -> dict[str, str]:
    return read_shared_env_file(ROOT)


def _load_db_settings() -> DbSettings:
    settings = load_shared_db_settings(config_path=DEFAULT_CONFIG_PATH, root=ROOT)
    return DbSettings(settings.host, settings.port, settings.dbname, settings.user, settings.password)


def _connect():
    if psycopg is None:  # pragma: no cover
        raise RuntimeError("psycopg is required")
    return pg_connect(config_path=DEFAULT_CONFIG_PATH, root=ROOT, autocommit=False)


def _internal_to_ts(symbol: str) -> str:
    text = str(symbol or "").strip().lower()
    if text.startswith(("sh", "sz", "bj")) and len(text) == 8:
        return f"{text[2:]}.{text[:2].upper()}"
    if "." in text:
        code, exch = text.split(".", 1)
        return f"{code.upper()}.{exch.upper()}"
    raise ValueError(f"unsupported symbol: {symbol}")


def _ts_to_internal(symbol: str) -> str:
    text = str(symbol or "").strip()
    if "." in text:
        code, exch = text.split(".", 1)
        exch_u = exch.upper()
        if exch_u == "SH":
            return f"sh{code}"
        if exch_u == "SZ":
            return f"sz{code}"
        if exch_u == "BJ":
            return f"bj{code}"
    lower = text.lower()
    if lower.startswith(("sh", "sz", "bj")):
        return lower
    raise ValueError(f"unsupported symbol: {symbol}")


def _internal_to_bs(symbol: str) -> str:
    text = str(symbol or "").strip().lower()
    if text.startswith(("sh", "sz", "bj")) and len(text) == 8:
        return f"{text[:2]}.{text[2:]}"
    if "." in text:
        code, exch = _internal_to_ts(text).split(".", 1)
        return f"{exch.lower()}.{code}"
    raise ValueError(f"unsupported symbol: {symbol}")


def _parse_symbol_list(raw: str) -> list[str]:
    tokens = [item.strip() for item in str(raw or "").replace(";", ",").split(",")]
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        if not token:
            continue
        normalized = _ts_to_internal(token)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _to_float_or_none(value: Any) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    return float(parsed)


def _to_int_or_none(value: Any) -> int | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    return int(round(float(parsed)))


def _limit_pct_for_symbol(symbol: str, trade_date: Any, *, is_st: bool) -> float:
    normalized = str(symbol or "").strip().lower()
    trade_day = pd.to_datetime(trade_date, errors="coerce")
    effective_date = None if pd.isna(trade_day) else trade_day.date()
    if normalized.startswith("bj"):
        if effective_date is not None and effective_date >= BSE_30PCT_START:
            return 0.30
        return 0.10
    if normalized.startswith("sh688"):
        if effective_date is not None and effective_date >= KCB_20PCT_START:
            return 0.20
        return 0.10
    if normalized.startswith("sz301"):
        return 0.20
    if normalized.startswith("sz300"):
        if effective_date is not None and effective_date >= GEM_20PCT_START:
            return 0.20
        return 0.10
    if is_st:
        return 0.05
    return 0.10


def _compute_limit_prices(prev_close: Any, symbol: str, trade_date: Any, *, is_st: bool) -> tuple[float | None, float | None]:
    previous = _to_float_or_none(prev_close)
    if previous is None or previous <= 0.0:
        return None, None
    pct = _limit_pct_for_symbol(symbol, trade_date, is_st=is_st)
    return round(previous * (1.0 + pct), 4), round(previous * (1.0 - pct), 4)


def _load_baostock():
    try:
        import baostock as bs
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("baostock is required") from exc
    return bs


def _load_csi800_symbols(index_code: str, start: date, end: date) -> list[str]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT symbol
                FROM public.pit_index_constituents
                WHERE index_code = %s
                  AND start_date <= %s
                  AND (end_date IS NULL OR end_date >= %s)
                ORDER BY symbol
                """,
                (index_code, end, start),
            )
            return [_ts_to_internal(str(row[0])) for row in cur.fetchall()]


def _load_cn_index_symbols() -> list[str]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT symbol
                FROM public.pams_ohlcv_daily
                WHERE market = 'CN_INDEX'
                ORDER BY symbol
                """
            )
            return [str(row[0]).strip().lower() for row in cur.fetchall()]


def _fetch_stock_history(bs: Any, symbol: str, start: date, end: date) -> pd.DataFrame:
    bs_code = _internal_to_bs(symbol)
    raw_rs = bs.query_history_k_data_plus(
        bs_code,
        RAW_FIELDS,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        frequency="d",
        adjustflag="3",
    )
    raw_df = raw_rs.get_data()
    if raw_df is None or raw_df.empty:
        return pd.DataFrame(columns=UPSERT_COLUMNS)
    hfq_rs = bs.query_history_k_data_plus(
        bs_code,
        HFQ_FIELDS,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        frequency="d",
        adjustflag="1",
    )
    hfq_df = hfq_rs.get_data()
    merged = raw_df.merge(hfq_df.rename(columns={"close": "hfq_close"}), on="date", how="left")
    merged["trade_date"] = pd.to_datetime(merged["date"], errors="coerce").dt.date
    for col in ["open", "high", "low", "close", "preclose", "volume", "amount", "turn", "hfq_close"]:
        merged[col] = pd.to_numeric(merged[col], errors="coerce")
    merged["symbol"] = symbol
    merged["market"] = "CN_A"
    merged["turnover"] = merged["amount"]
    merged["adj_factor"] = merged["hfq_close"] / merged["close"]
    merged["adj_factor"] = pd.to_numeric(merged["adj_factor"], errors="coerce")
    merged["is_st"] = pd.to_numeric(merged.get("isST"), errors="coerce").fillna(0).astype(int).eq(1)
    merged["is_suspended"] = ~pd.to_numeric(merged.get("tradestatus"), errors="coerce").fillna(0).astype(int).eq(1)
    limit_values = [
        _compute_limit_prices(prev_close=row.preclose, symbol=symbol, trade_date=row.trade_date, is_st=bool(row.is_st))
        for row in merged.itertuples(index=False)
    ]
    merged["limit_up"] = [item[0] for item in limit_values]
    merged["limit_down"] = [item[1] for item in limit_values]
    merged["turnover_rate"] = pd.to_numeric(merged["turn"], errors="coerce")
    merged["turnover_rate_f"] = pd.to_numeric(merged["turn"], errors="coerce")
    merged["volume_ratio"] = pd.NA
    merged["float_share"] = pd.NA
    merged["free_share"] = pd.NA
    merged["circ_mv"] = pd.NA
    out = merged[[
        "symbol",
        "market",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "turnover",
        "adj_factor",
        "limit_up",
        "limit_down",
        "is_suspended",
        "turnover_rate",
        "turnover_rate_f",
        "volume_ratio",
        "float_share",
        "free_share",
        "circ_mv",
    ]].copy()
    out = out.dropna(subset=["trade_date"]).drop_duplicates(subset=["symbol", "market", "trade_date"], keep="last")
    return out.sort_values("trade_date").reset_index(drop=True)


def _fetch_index_history(bs: Any, symbol: str, start: date, end: date) -> pd.DataFrame:
    bs_code = _internal_to_bs(symbol)
    rs = bs.query_history_k_data_plus(
        bs_code,
        INDEX_FIELDS,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        frequency="d",
        adjustflag="3",
    )
    raw = rs.get_data()
    if raw is None or raw.empty:
        return pd.DataFrame(columns=UPSERT_COLUMNS)
    raw["trade_date"] = pd.to_datetime(raw["date"], errors="coerce").dt.date
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    raw["symbol"] = symbol
    raw["market"] = "CN_INDEX"
    raw["turnover"] = raw["amount"]
    raw["adj_factor"] = pd.NA
    raw["limit_up"] = pd.NA
    raw["limit_down"] = pd.NA
    raw["is_suspended"] = False
    raw["turnover_rate"] = pd.NA
    raw["turnover_rate_f"] = pd.NA
    raw["volume_ratio"] = pd.NA
    raw["float_share"] = pd.NA
    raw["free_share"] = pd.NA
    raw["circ_mv"] = pd.NA
    out = raw[UPSERT_COLUMNS].copy()
    out = out.dropna(subset=["trade_date"]).drop_duplicates(subset=["symbol", "market", "trade_date"], keep="last")
    return out.sort_values("trade_date").reset_index(drop=True)


def _init_temp_table(cur) -> None:
    cur.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS tmp_csi800_baostock_backfill (
            symbol text NOT NULL,
            market text NOT NULL,
            trade_date date NOT NULL,
            open numeric,
            high numeric,
            low numeric,
            close numeric,
            volume bigint,
            turnover numeric,
            adj_factor numeric,
            limit_up numeric,
            limit_down numeric,
            is_suspended boolean,
            turnover_rate double precision,
            turnover_rate_f double precision,
            volume_ratio double precision,
            float_share double precision,
            free_share double precision,
            circ_mv double precision
        ) ON COMMIT DROP
        """
    )


def _load_batch_into_temp(cur, batch: pd.DataFrame) -> None:
    cur.execute("TRUNCATE TABLE tmp_csi800_baostock_backfill")
    rows = [
        (
            str(row.symbol),
            str(row.market),
            row.trade_date,
            _to_float_or_none(row.open),
            _to_float_or_none(row.high),
            _to_float_or_none(row.low),
            _to_float_or_none(row.close),
            _to_int_or_none(row.volume),
            _to_float_or_none(row.turnover),
            _to_float_or_none(row.adj_factor),
            _to_float_or_none(row.limit_up),
            _to_float_or_none(row.limit_down),
            bool(row.is_suspended),
            _to_float_or_none(row.turnover_rate),
            _to_float_or_none(row.turnover_rate_f),
            _to_float_or_none(row.volume_ratio),
            _to_float_or_none(row.float_share),
            _to_float_or_none(row.free_share),
            _to_float_or_none(row.circ_mv),
        )
        for row in batch.itertuples(index=False)
    ]
    if not rows:
        return
    cur.executemany(
        """
        INSERT INTO tmp_csi800_baostock_backfill (
            symbol,
            market,
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            turnover,
            adj_factor,
            limit_up,
            limit_down,
            is_suspended,
            turnover_rate,
            turnover_rate_f,
            volume_ratio,
            float_share,
            free_share,
            circ_mv
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )


def _count_batch_state(cur) -> tuple[int, int]:
    cur.execute(
        f"""
        SELECT
            COUNT(*) FILTER (WHERE target.symbol IS NULL) AS insert_rows,
            COUNT(*) FILTER (WHERE target.symbol IS NOT NULL) AS update_rows
        FROM tmp_csi800_baostock_backfill AS src
        LEFT JOIN public.{DEFAULT_TABLE} AS target
          ON target.symbol = src.symbol
         AND target.market = src.market
         AND target.trade_date = src.trade_date
        """
    )
    row = cur.fetchone()
    return int(row[0] or 0), int(row[1] or 0)


def _upsert_batch(cur) -> int:
    cur.execute(
        f"""
        INSERT INTO public.{DEFAULT_TABLE} (
            symbol,
            market,
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            turnover,
            adj_factor,
            limit_up,
            limit_down,
            is_suspended,
            turnover_rate,
            turnover_rate_f,
            volume_ratio,
            float_share,
            free_share,
            circ_mv
        )
        SELECT
            symbol,
            market,
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            turnover,
            adj_factor,
            limit_up,
            limit_down,
            is_suspended,
            turnover_rate,
            turnover_rate_f,
            volume_ratio,
            float_share,
            free_share,
            circ_mv
        FROM tmp_csi800_baostock_backfill
        ON CONFLICT (symbol, market, trade_date) DO UPDATE
        SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            turnover = EXCLUDED.turnover,
            adj_factor = COALESCE(EXCLUDED.adj_factor, {DEFAULT_TABLE}.adj_factor),
            limit_up = COALESCE(EXCLUDED.limit_up, {DEFAULT_TABLE}.limit_up),
            limit_down = COALESCE(EXCLUDED.limit_down, {DEFAULT_TABLE}.limit_down),
            is_suspended = EXCLUDED.is_suspended,
            turnover_rate = COALESCE(EXCLUDED.turnover_rate, {DEFAULT_TABLE}.turnover_rate),
            turnover_rate_f = COALESCE(EXCLUDED.turnover_rate_f, {DEFAULT_TABLE}.turnover_rate_f),
            volume_ratio = COALESCE(EXCLUDED.volume_ratio, {DEFAULT_TABLE}.volume_ratio),
            float_share = COALESCE(EXCLUDED.float_share, {DEFAULT_TABLE}.float_share),
            free_share = COALESCE(EXCLUDED.free_share, {DEFAULT_TABLE}.free_share),
            circ_mv = COALESCE(EXCLUDED.circ_mv, {DEFAULT_TABLE}.circ_mv)
        """
    )
    return int(cur.rowcount or 0)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_backfill(args: argparse.Namespace) -> dict[str, Any]:
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start > end:
        raise ValueError("start must be <= end")

    explicit_symbols = _parse_symbol_list(str(args.symbols or ""))
    stock_symbols = explicit_symbols or _load_csi800_symbols(str(args.index_code), start, end)
    index_symbols = [] if explicit_symbols else _load_cn_index_symbols()
    symbol_offset = max(int(args.symbol_offset), 0)
    if symbol_offset > 0:
        stock_symbols = stock_symbols[symbol_offset:]
    max_symbols = max(int(args.max_symbols), 0)
    if max_symbols > 0:
        stock_symbols = stock_symbols[:max_symbols]
    if args.skip_index_symbols:
        index_symbols = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (DEFAULT_OUTPUT_ROOT / f"csi800_baostock_backfill_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "status": "ok",
        "apply": bool(args.apply),
        "index_code": str(args.index_code),
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "explicit_symbols": [_internal_to_ts(symbol) for symbol in explicit_symbols],
        "stock_symbol_count": int(len(stock_symbols)),
        "index_symbol_count": int(len(index_symbols)),
        "stock_rows": 0,
        "index_rows": 0,
        "rows_total": 0,
        "insert_rows": 0,
        "update_rows": 0,
        "upserted_rows": 0,
        "failed_stock_symbols": [],
        "failed_index_symbols": [],
    }

    bs = _load_baostock()
    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"baostock login failed: {login.error_msg}")

    frames: list[pd.DataFrame] = []
    try:
        for idx, symbol in enumerate(stock_symbols, start=1):
            try:
                frame = _fetch_stock_history(bs, symbol, start, end)
                if not frame.empty:
                    frames.append(frame)
                    summary["stock_rows"] += int(len(frame))
            except Exception as exc:
                summary["failed_stock_symbols"].append({"symbol": symbol, "error": str(exc)})
            if idx % 25 == 0:
                print(f"[stock] {idx}/{len(stock_symbols)} symbols fetched")
            time.sleep(float(args.sleep_seconds))

        for idx, symbol in enumerate(index_symbols, start=1):
            try:
                frame = _fetch_index_history(bs, symbol, start, end)
                if not frame.empty:
                    frames.append(frame)
                    summary["index_rows"] += int(len(frame))
            except Exception as exc:
                summary["failed_index_symbols"].append({"symbol": symbol, "error": str(exc)})
            time.sleep(float(args.sleep_seconds))
    finally:
        bs.logout()

    combined = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=UPSERT_COLUMNS)
    )
    combined = combined.drop_duplicates(subset=["symbol", "market", "trade_date"], keep="last").sort_values(["trade_date", "market", "symbol"]).reset_index(drop=True)
    summary["rows_total"] = int(len(combined))

    sample_path = output_dir / "csi800_baostock_backfill_sample.csv"
    combined.head(500).to_csv(sample_path, index=False)
    summary["sample_csv"] = str(sample_path)

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '1200000ms'")
            _init_temp_table(cur)
            batch_size = max(int(args.batch_size), 1)
            for batch_start in range(0, len(combined), batch_size):
                batch = combined.iloc[batch_start : batch_start + batch_size].copy()
                _load_batch_into_temp(cur, batch)
                insert_rows, update_rows = _count_batch_state(cur)
                upserted_rows = _upsert_batch(cur)
                summary["insert_rows"] += insert_rows
                summary["update_rows"] += update_rows
                summary["upserted_rows"] += upserted_rows
            if args.apply:
                conn.commit()
            else:
                conn.rollback()
                summary["status"] = "dry_run"

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill CSI800-related CN_A/CN_INDEX OHLCV via baostock")
    parser.add_argument("--start", required=True, help="inclusive start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="inclusive end date YYYY-MM-DD")
    parser.add_argument("--index-code", default=DEFAULT_INDEX_CODE)
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--symbols", default="", help="optional comma-separated symbols in TS/internal format")
    parser.add_argument("--symbol-offset", type=int, default=0, help="skip this many stock symbols before backfill")
    parser.add_argument("--max-symbols", type=int, default=0, help="optional symbol cap for smoke tests; 0 means all symbols")
    parser.add_argument("--skip-index-symbols", action="store_true", help="do not backfill CN_INDEX rows in this run")
    parser.add_argument("--sleep-seconds", type=float, default=0.03, help="sleep between baostock requests")
    parser.add_argument("--output-dir", default="", help="output directory for summary/sample artifacts")
    parser.add_argument("--apply", action="store_true", help="commit DB writes; default is dry-run rollback")
    args = parser.parse_args()

    summary = run_backfill(args)
    output_dir = Path(summary["sample_csv"]).parent
    summary_path = output_dir / "summary.json"
    _write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_json={summary_path}")


if __name__ == "__main__":
    main()
