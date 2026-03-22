from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from . import cn_side_table_common as common
from . import pams_ohlcv_daily_v2_common as v2_common


SOURCE_TABLES = {
    "stock_basic": v2_common.RAW_STOCK_BASIC_TABLE,
    "trade_cal": v2_common.RAW_TRADE_CAL_TABLE,
    "daily": v2_common.RAW_DAILY_TABLE,
    "adj_factor": v2_common.RAW_ADJ_FACTOR_TABLE,
    "daily_basic": v2_common.RAW_DAILY_BASIC_TABLE,
    "suspend_d": v2_common.RAW_SUSPEND_TABLE,
    "stk_limit": v2_common.RAW_STK_LIMIT_TABLE,
    "moneyflow": v2_common.RAW_MONEYFLOW_TABLE,
}

_NETWORK_FAILURE_TOKENS = (
    "temporary failure in name resolution",
    "failed to resolve",
    "max retries exceeded",
    "connectionerror",
    "connection error",
    "read timed out",
    "connect timeout",
    "connecttimeout",
    "name resolution",
    "name or service not known",
    "remote disconnected",
    "connection aborted",
    "connection reset",
    "timed out",
)


def _iter_dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current = current + pd.Timedelta(days=1).to_pytimedelta()


def _table_exists(cur, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{common.safe_ident(table)}",))
    return cur.fetchone()[0] is not None


def _require_tables(cur) -> None:
    missing = [table for table in SOURCE_TABLES.values() if not _table_exists(cur, table)]
    if missing:
        joined = ", ".join(sorted(missing))
        raise RuntimeError(
            f"missing raw tables: {joined}. Apply docs/db/pams_ohlcv_daily_v2_apply.sql first."
        )


def _upsert_rows(
    cur,
    *,
    table: str,
    columns: list[str],
    pk_columns: list[str],
    rows: list[tuple[Any, ...]],
) -> int:
    if not rows:
        return 0
    safe_table = common.safe_ident(table)
    safe_columns = [common.safe_ident(col) for col in columns]
    safe_pk_columns = [common.safe_ident(col) for col in pk_columns]
    update_columns = [col for col in safe_columns if col not in safe_pk_columns]
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(f"{col} = EXCLUDED.{col}" for col in update_columns)
    cur.executemany(
        f"""
        INSERT INTO public.{safe_table} ({", ".join(safe_columns)})
        VALUES ({placeholders})
        ON CONFLICT ({", ".join(safe_pk_columns)}) DO UPDATE SET
            {updates}
        """,
        rows,
    )
    return int(len(rows))


def _normalize_stock_basic(pro: Any) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for status in ("L", "D", "P"):
        raw = pro.stock_basic(
            exchange="",
            list_status=status,
            fields="ts_code,symbol,name,exchange,market,list_status,list_date,delist_date,industry",
        )
        if raw is None or raw.empty:
            continue
        frame = raw.copy()
        frame["ts_code"] = frame["ts_code"].astype(str).str.upper().str.strip()
        frame["symbol"] = frame["ts_code"].map(v2_common.normalize_stock_symbol)
        frame["name"] = frame["name"].astype(str).str.strip()
        frame["exchange"] = frame["exchange"].astype(str).str.strip()
        frame["market"] = frame["market"].astype(str).str.strip()
        frame["list_status"] = frame.get("list_status", status)
        frame["list_date"] = pd.to_datetime(frame["list_date"], errors="coerce").dt.date
        frame["delist_date"] = pd.to_datetime(frame["delist_date"], errors="coerce").dt.date
        frame["industry"] = frame["industry"].astype(str).str.strip()
        frames.append(
            frame[
                [
                    "ts_code",
                    "symbol",
                    "name",
                    "exchange",
                    "market",
                    "list_status",
                    "list_date",
                    "delist_date",
                    "industry",
                ]
            ].copy()
        )
    if not frames:
        return pd.DataFrame(
            columns=[
                "ts_code",
                "symbol",
                "name",
                "exchange",
                "market",
                "list_status",
                "list_date",
                "delist_date",
                "industry",
            ]
        )
    return (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset=["ts_code"], keep="last")
        .sort_values("ts_code")
        .reset_index(drop=True)
    )


def _normalize_trade_cal(pro: Any, start: date, end: date) -> pd.DataFrame:
    raw = pro.trade_cal(exchange="SSE", start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"))
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["exchange", "cal_date", "is_open", "pretrade_date"])
    frame = raw.copy()
    frame["exchange"] = frame["exchange"].astype(str).str.strip()
    frame["cal_date"] = pd.to_datetime(frame["cal_date"], errors="coerce").dt.date
    frame["pretrade_date"] = pd.to_datetime(frame["pretrade_date"], errors="coerce").dt.date
    frame["is_open"] = frame["is_open"].astype(str).str.strip().isin({"1", "true", "True", "t", "T"})
    return (
        frame[["exchange", "cal_date", "is_open", "pretrade_date"]]
        .dropna(subset=["exchange", "cal_date"])
        .drop_duplicates(subset=["exchange", "cal_date"], keep="last")
        .sort_values(["exchange", "cal_date"])
        .reset_index(drop=True)
    )


def _normalize_trade_date_frame(raw: pd.DataFrame, *, source: str, symbol_filter: set[str] | None) -> pd.DataFrame:
    if raw is None or raw.empty:
        if source == "daily":
            cols = ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"]
        elif source == "adj_factor":
            cols = ["ts_code", "trade_date", "adj_factor"]
        elif source == "daily_basic":
            cols = ["ts_code", "trade_date", *v2_common.DAILY_BASIC_FIELDS]
        elif source == "suspend_d":
            cols = ["ts_code", "trade_date", "suspend_timing", "suspend_type"]
        elif source == "stk_limit":
            cols = ["ts_code", "trade_date", "up_limit", "down_limit"]
        else:
            cols = ["ts_code", "trade_date", *v2_common.MONEYFLOW_VOLUME_FIELDS, *v2_common.MONEYFLOW_AMOUNT_FIELDS]
        return pd.DataFrame(columns=cols)
    frame = raw.copy()
    frame["ts_code"] = frame["ts_code"].astype(str).str.upper().str.strip()
    if symbol_filter:
        allowed = {v2_common.symbol_to_tushare_code(symbol) for symbol in symbol_filter}
        frame = frame[frame["ts_code"].isin(allowed)].copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.date
    if source == "daily":
        keep = ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"]
    elif source == "adj_factor":
        keep = ["ts_code", "trade_date", "adj_factor"]
    elif source == "daily_basic":
        keep = ["ts_code", "trade_date", *v2_common.DAILY_BASIC_FIELDS]
    elif source == "suspend_d":
        keep = ["ts_code", "trade_date", "suspend_timing", "suspend_type"]
    elif source == "stk_limit":
        keep = ["ts_code", "trade_date", "up_limit", "down_limit"]
    elif source == "moneyflow":
        keep = ["ts_code", "trade_date", *v2_common.MONEYFLOW_VOLUME_FIELDS, *v2_common.MONEYFLOW_AMOUNT_FIELDS]
    else:  # pragma: no cover
        raise ValueError(f"unsupported source: {source}")
    for column in keep:
        if column not in frame.columns:
            frame[column] = pd.NA
    numeric_columns = [col for col in keep if col not in {"ts_code", "trade_date", "suspend_timing", "suspend_type"}]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return (
        frame[keep]
        .dropna(subset=["ts_code", "trade_date"])
        .drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
        .sort_values(["trade_date", "ts_code"])
        .reset_index(drop=True)
    )


def _fetch_trade_date_sources(
    pro: Any,
    trade_date: date,
    symbol_filter: set[str],
    *,
    soft_fail_events: list[dict[str, Any]] | None = None,
) -> dict[str, pd.DataFrame]:
    trade_date_text = trade_date.strftime("%Y%m%d")
    raw_daily = _query_with_retry(
        lambda: pro.daily(trade_date=trade_date_text),
        label="daily",
        trade_date=trade_date,
    )
    raw_adj = _query_with_retry(
        lambda: pro.adj_factor(trade_date=trade_date_text),
        label="adj_factor",
        trade_date=trade_date,
    )
    raw_basic = _query_with_retry(
        lambda: pro.daily_basic(trade_date=trade_date_text),
        label="daily_basic",
        trade_date=trade_date,
    )
    raw_suspend = _query_with_retry(
        lambda: pro.suspend_d(start_date=trade_date_text, end_date=trade_date_text),
        label="suspend_d",
        trade_date=trade_date,
    )
    raw_limit = _query_with_retry(
        lambda: pro.stk_limit(start_date=trade_date_text, end_date=trade_date_text),
        label="stk_limit",
        trade_date=trade_date,
        max_attempts=8,
        sleep_seconds=5,
        allow_soft_fail=True,
        soft_fail_events=soft_fail_events,
    )
    raw_moneyflow = _query_with_retry(
        lambda: pro.moneyflow(trade_date=trade_date_text),
        label="moneyflow",
        trade_date=trade_date,
        max_attempts=8,
        sleep_seconds=5,
        allow_soft_fail=True,
        soft_fail_events=soft_fail_events,
    )
    return {
        "daily": _normalize_trade_date_frame(raw_daily, source="daily", symbol_filter=symbol_filter),
        "adj_factor": _normalize_trade_date_frame(raw_adj, source="adj_factor", symbol_filter=symbol_filter),
        "daily_basic": _normalize_trade_date_frame(raw_basic, source="daily_basic", symbol_filter=symbol_filter),
        "suspend_d": _normalize_trade_date_frame(raw_suspend, source="suspend_d", symbol_filter=symbol_filter),
        "stk_limit": _normalize_trade_date_frame(raw_limit, source="stk_limit", symbol_filter=symbol_filter),
        "moneyflow": _normalize_trade_date_frame(raw_moneyflow, source="moneyflow", symbol_filter=symbol_filter),
    }


def _rows_from_frame(frame: pd.DataFrame, columns: list[str], source_run_id: str) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    if frame.empty:
        return rows
    for row in frame.itertuples(index=False):
        values: list[Any] = []
        for column in columns:
            value = getattr(row, column)
            if pd.isna(value):
                value = None
            values.append(value)
        values.append(source_run_id)
        values.append(datetime.now())
        rows.append(tuple(values))
    return rows


def _exception_chain(exc: Exception | None) -> Iterable[Exception]:
    current = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        next_exc = current.__cause__ or current.__context__
        current = next_exc if isinstance(next_exc, Exception) else None


def _is_retryable_network_failure(exc: Exception | None) -> bool:
    if exc is None:
        return False
    texts: list[str] = []
    for item in _exception_chain(exc):
        texts.append(f"{item.__class__.__module__}.{item.__class__.__name__}: {item}")
    joined = " ".join(texts).lower()
    return any(token in joined for token in _NETWORK_FAILURE_TOKENS)


def _query_with_retry(
    fetcher,
    *,
    label: str,
    trade_date: date,
    max_attempts: int = 5,
    sleep_seconds: int = 3,
    allow_soft_fail: bool = False,
    soft_fail_events: list[dict[str, Any]] | None = None,
):
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fetcher()
        except Exception as exc:  # pragma: no cover - exercised by integration runs
            last_error = exc
            if attempt >= max_attempts:
                break
            time.sleep(float(sleep_seconds * attempt))
    if allow_soft_fail and _is_retryable_network_failure(last_error):
        if soft_fail_events is not None:
            soft_fail_events.append(
                {
                    "label": str(label),
                    "trade_date": trade_date.isoformat(),
                    "attempts": int(max_attempts),
                    "error_type": last_error.__class__.__name__ if last_error is not None else "UnknownError",
                    "error_message": str(last_error or ""),
                }
            )
        return None
    raise RuntimeError(
        f"tushare source `{label}` failed after {max_attempts} attempts on trade_date={trade_date.isoformat()}"
    ) from last_error


def build_update_args(
    *,
    start: str = "",
    end: str = "",
    token: str = "",
    symbols_csv: str = "",
    output_dir: str = "",
    heartbeat_path: str = "",
    heartbeat_label: str = "",
    apply: bool = True,
) -> argparse.Namespace:
    return argparse.Namespace(
        start=str(start or ""),
        end=str(end or ""),
        token=common.resolve_tushare_token(str(token or "")),
        symbols_csv=str(symbols_csv or ""),
        output_dir=str(output_dir or ""),
        heartbeat_path=str(heartbeat_path or ""),
        heartbeat_label=str(heartbeat_label or ""),
        apply=bool(apply),
    )


def run_update(args: argparse.Namespace) -> dict[str, Any]:
    token = common.resolve_tushare_token(str(args.token or ""))
    pro = common.load_tushare_client(token)
    end = date.fromisoformat(str(args.end).strip()) if str(args.end or "").strip() else common.resolve_latest_trade_date(pro)
    if end is None:
        raise RuntimeError("failed to resolve target end date from Tushare trade calendar")
    start, _latest_before = common.infer_start_date(str(args.start or ""), v2_common.RAW_DAILY_TABLE)
    symbol_filter = common.parse_symbols_csv(str(args.symbols_csv or ""))
    ts_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (v2_common.DEFAULT_OUTPUT_ROOT / f"pams_ohlcv_daily_v2_raw_{ts_label}")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = v2_common.build_run_id("raw_sync")
    heartbeat_path = str(getattr(args, "heartbeat_path", "") or "").strip()
    heartbeat_label = str(getattr(args, "heartbeat_label", "") or "").strip() or "pams_ohlcv_daily_v2_raw"

    trade_cal_frame = _normalize_trade_cal(pro, start, end)
    open_trade_dates = sorted(
        {
            trade_date
            for trade_date, is_open in zip(trade_cal_frame["cal_date"], trade_cal_frame["is_open"], strict=False)
            if bool(is_open)
        }
    )
    stock_basic_frame = _normalize_stock_basic(pro)

    summary: dict[str, Any] = {
        "status": "ok",
        "apply": bool(args.apply),
        "run_id": run_id,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "symbol_filter_count": int(len(symbol_filter)),
        "sources": {name: {"rows": 0, "soft_failures": 0} for name in SOURCE_TABLES},
        "open_trade_dates": [item.isoformat() for item in open_trade_dates],
        "soft_failures": [],
        "notes": [
            "v2 raw sync stores Tushare source rows before canonical build.",
            "AkShare is not used in raw sync and is reserved for canonical turnover_rate fallback only.",
        ],
    }

    source_samples: dict[str, pd.DataFrame] = {
        "stock_basic": stock_basic_frame.head(100).copy(),
        "trade_cal": trade_cal_frame.head(100).copy(),
    }

    v2_common.touch_heartbeat(
        heartbeat_path,
        step=heartbeat_label,
        status="running",
        extra={"run_id": run_id, "phase": "start", "date_range": summary["date_range"]},
    )

    try:
        with common.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = '1200000ms'")
                _require_tables(cur)
                stock_basic_rows = _rows_from_frame(
                    stock_basic_frame,
                    ["ts_code", "symbol", "name", "exchange", "market", "list_status", "list_date", "delist_date", "industry"],
                    run_id,
                )
                summary["sources"]["stock_basic"]["rows"] = _upsert_rows(
                    cur,
                    table=v2_common.RAW_STOCK_BASIC_TABLE,
                    columns=["ts_code", "symbol", "name", "exchange", "market", "list_status", "list_date", "delist_date", "industry", "source_run_id", "ingested_at"],
                    pk_columns=["ts_code"],
                    rows=stock_basic_rows,
                )
                trade_cal_rows = _rows_from_frame(
                    trade_cal_frame,
                    ["exchange", "cal_date", "is_open", "pretrade_date"],
                    run_id,
                )
                summary["sources"]["trade_cal"]["rows"] = _upsert_rows(
                    cur,
                    table=v2_common.RAW_TRADE_CAL_TABLE,
                    columns=["exchange", "cal_date", "is_open", "pretrade_date", "source_run_id", "ingested_at"],
                    pk_columns=["exchange", "cal_date"],
                    rows=trade_cal_rows,
                )
                if args.apply:
                    conn.commit()

                per_trade_date: list[dict[str, Any]] = []
                for trade_date in open_trade_dates:
                    try:
                        trade_soft_failures: list[dict[str, Any]] = []
                        fetched = _fetch_trade_date_sources(
                            pro,
                            trade_date,
                            symbol_filter,
                            soft_fail_events=trade_soft_failures,
                        )
                        trade_stats: dict[str, Any] = {"trade_date": trade_date.isoformat()}
                        if trade_soft_failures:
                            trade_stats["soft_failures"] = list(trade_soft_failures)
                            summary["soft_failures"].extend(trade_soft_failures)
                            for event in trade_soft_failures:
                                source_name = str(event.get("label") or "").strip()
                                if source_name in summary["sources"]:
                                    summary["sources"][source_name]["soft_failures"] += 1
                        for source_name, frame in fetched.items():
                            if source_name not in source_samples:
                                source_samples[source_name] = frame.head(100).copy()
                            columns: list[str]
                            pk_columns = ["ts_code", "trade_date"]
                            if source_name == "daily":
                                columns = ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount", "source_run_id", "ingested_at"]
                            elif source_name == "adj_factor":
                                columns = ["ts_code", "trade_date", "adj_factor", "source_run_id", "ingested_at"]
                            elif source_name == "daily_basic":
                                columns = ["ts_code", "trade_date", *v2_common.DAILY_BASIC_FIELDS, "source_run_id", "ingested_at"]
                            elif source_name == "suspend_d":
                                columns = ["ts_code", "trade_date", "suspend_timing", "suspend_type", "source_run_id", "ingested_at"]
                            elif source_name == "stk_limit":
                                columns = ["ts_code", "trade_date", "up_limit", "down_limit", "source_run_id", "ingested_at"]
                            elif source_name == "moneyflow":
                                columns = [
                                    "ts_code",
                                    "trade_date",
                                    *v2_common.MONEYFLOW_VOLUME_FIELDS,
                                    *v2_common.MONEYFLOW_AMOUNT_FIELDS,
                                    "source_run_id",
                                    "ingested_at",
                                ]
                            else:  # pragma: no cover
                                raise ValueError(f"unsupported source: {source_name}")
                            raw_columns = [col for col in columns if col not in {"source_run_id", "ingested_at"}]
                            rows = _rows_from_frame(frame, raw_columns, run_id)
                            affected_rows = _upsert_rows(
                                cur,
                                table=SOURCE_TABLES[source_name],
                                columns=columns,
                                pk_columns=pk_columns,
                                rows=rows,
                            )
                            summary["sources"][source_name]["rows"] += affected_rows
                            trade_stats[source_name] = int(affected_rows)
                        per_trade_date.append(trade_stats)
                        if args.apply:
                            conn.commit()
                        v2_common.touch_heartbeat(
                            heartbeat_path,
                            step=heartbeat_label,
                            trade_date=trade_date,
                            status="running",
                            extra={"run_id": run_id, "phase": "trade_date_committed"},
                        )
                    except Exception:
                        if args.apply:
                            conn.rollback()
                        raise

                summary["per_trade_date"] = per_trade_date
                if args.apply:
                    pass
                else:
                    conn.rollback()
                    summary["status"] = "dry_run"
    except Exception:
        v2_common.touch_heartbeat(
            heartbeat_path,
            step=heartbeat_label,
            status="failed",
            extra={"run_id": run_id, "phase": "failed"},
        )
        raise

    sample_paths: dict[str, str] = {}
    for source_name, frame in source_samples.items():
        sample_path = output_dir / f"{source_name}_sample.csv"
        frame.to_csv(sample_path, index=False)
        sample_paths[source_name] = str(sample_path)
    summary["sample_csv"] = sample_paths
    v2_common.touch_heartbeat(
        heartbeat_path,
        step=heartbeat_label,
        status=summary["status"],
        extra={"run_id": run_id, "phase": "completed"},
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync raw Tushare source tables for pams_ohlcv_daily_v2")
    parser.add_argument("--start", default="", help="inclusive start date YYYY-MM-DD; default latest raw daily + 1 or 2007-01-04")
    parser.add_argument("--end", default="", help="inclusive end date YYYY-MM-DD; default latest available trade date")
    parser.add_argument("--token", default=common.resolve_tushare_token(), help="Tushare token")
    parser.add_argument("--symbols-csv", default="", help="optional comma-separated symbols to narrow smoke runs")
    parser.add_argument("--output-dir", default="", help="output directory for summary/sample artifacts")
    parser.add_argument("--heartbeat-path", default="", help="optional heartbeat JSON path updated during long-running sync")
    parser.add_argument("--heartbeat-label", default="", help="optional logical step name written to heartbeat JSON")
    parser.add_argument("--apply", action="store_true", help="commit DB writes; default is dry-run rollback")
    args = parser.parse_args()

    summary = run_update(args)
    output_dir = Path(next(iter(summary["sample_csv"].values()))).parent if summary["sample_csv"] else Path(args.output_dir or ".")
    summary_path = output_dir / "summary.json"
    common.write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_json={summary_path}")


if __name__ == "__main__":
    main()
