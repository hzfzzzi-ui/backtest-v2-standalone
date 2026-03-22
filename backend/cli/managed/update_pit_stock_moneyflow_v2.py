from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import cn_side_table_common as common
from . import pams_ohlcv_daily_v2_common as v2_common


SIDE_COLUMNS = [
    "symbol",
    "trade_date",
    *v2_common.MONEYFLOW_VOLUME_FIELDS,
    *v2_common.MONEYFLOW_AMOUNT_FIELDS,
    "source_moneyflow_present",
    "net_fields_present",
    "source",
    "build_run_id",
]


def _table_exists(cur, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{common.safe_ident(table)}",))
    return cur.fetchone()[0] is not None


def _require_tables(cur) -> None:
    required = [
        v2_common.V2_MAIN_TABLE,
        v2_common.RAW_MONEYFLOW_TABLE,
        v2_common.V2_MONEYFLOW_TABLE,
        v2_common.V2_MONEYFLOW_WHITELIST_TABLE,
    ]
    missing = [table for table in required if not _table_exists(cur, table)]
    if missing:
        joined = ", ".join(sorted(missing))
        raise RuntimeError(
            f"missing v2 moneyflow dependencies: {joined}. Apply docs/db/pams_ohlcv_daily_v2_apply.sql and build v2 main table first."
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
    updates = ", ".join(f"{col} = EXCLUDED.{col}" for col in update_columns if col not in {"created_at", "updated_at"})
    if "updated_at" in safe_columns:
        on_conflict_sql = f"""
        ON CONFLICT ({", ".join(safe_pk_columns)}) DO UPDATE SET
            {updates},
            updated_at = NOW()
        """
    else:
        on_conflict_sql = f"""
        ON CONFLICT ({", ".join(safe_pk_columns)}) DO UPDATE SET
            {updates}
        """
    cur.executemany(
        f"""
        INSERT INTO public.{safe_table} ({", ".join(safe_columns)})
        VALUES ({placeholders})
        {on_conflict_sql}
        """,
        rows,
    )
    return int(len(rows))


def _load_open_trade_dates(conn, start: date, end: date) -> list[date]:
    frame = v2_common.df_from_query(
        conn,
        f"""
        SELECT DISTINCT trade_date
        FROM public.{common.safe_ident(v2_common.V2_MAIN_TABLE)}
        WHERE trade_date >= %s
          AND trade_date <= %s
        ORDER BY trade_date
        """,
        (start, end),
    )
    if frame.empty:
        return []
    return [item for item in pd.to_datetime(frame["trade_date"], errors="coerce").dt.date.tolist() if item is not None]


def _load_traded_main_rows(conn, trade_date: date, symbol_filter: set[str]) -> pd.DataFrame:
    query = f"""
        SELECT symbol, trade_date
        FROM public.{common.safe_ident(v2_common.V2_MAIN_TABLE)}
        WHERE trade_date = %s
          AND row_status = 'traded'
        ORDER BY symbol
    """
    params: tuple[Any, ...] = (trade_date,)
    if symbol_filter:
        query = f"""
            SELECT symbol, trade_date
            FROM public.{common.safe_ident(v2_common.V2_MAIN_TABLE)}
            WHERE trade_date = %s
              AND row_status = 'traded'
              AND symbol = ANY(%s)
            ORDER BY symbol
        """
        params = (trade_date, sorted(symbol_filter))
    frame = v2_common.df_from_query(conn, query, params)
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "trade_date"])
    frame["symbol"] = frame["symbol"].astype(str).map(v2_common.normalize_stock_symbol)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.date
    return frame


def _load_raw_moneyflow(conn, trade_date: date, symbol_filter: set[str]) -> pd.DataFrame:
    query = f"""
        SELECT ts_code, trade_date, {", ".join(v2_common.MONEYFLOW_VOLUME_FIELDS + v2_common.MONEYFLOW_AMOUNT_FIELDS)}
        FROM public.{common.safe_ident(v2_common.RAW_MONEYFLOW_TABLE)}
        WHERE trade_date = %s
        ORDER BY ts_code
    """
    params: tuple[Any, ...] = (trade_date,)
    if symbol_filter:
        ts_codes = [v2_common.symbol_to_tushare_code(symbol) for symbol in sorted(symbol_filter)]
        query = f"""
            SELECT ts_code, trade_date, {", ".join(v2_common.MONEYFLOW_VOLUME_FIELDS + v2_common.MONEYFLOW_AMOUNT_FIELDS)}
            FROM public.{common.safe_ident(v2_common.RAW_MONEYFLOW_TABLE)}
            WHERE trade_date = %s
              AND ts_code = ANY(%s)
            ORDER BY ts_code
        """
        params = (trade_date, ts_codes)
    frame = v2_common.df_from_query(conn, query, params)
    if frame.empty:
        columns = ["ts_code", "trade_date", *v2_common.MONEYFLOW_VOLUME_FIELDS, *v2_common.MONEYFLOW_AMOUNT_FIELDS]
        return pd.DataFrame(columns=columns)
    frame["symbol"] = frame["ts_code"].astype(str).map(v2_common.normalize_stock_symbol)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.date
    return frame


def _build_trade_date_frame(
    *,
    trade_date: date,
    main_frame: pd.DataFrame,
    raw_frame: pd.DataFrame,
    build_run_id: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if main_frame.empty:
        empty = pd.DataFrame(columns=SIDE_COLUMNS)
        return empty, {"trade_date": trade_date.isoformat(), "traded_rows": 0, "source_rows": 0, "net_rows": 0}
    raw_map = {
        str(row.symbol).lower(): row._asdict()
        for row in raw_frame.itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []
    source_rows = 0
    net_rows = 0
    for row in main_frame.itertuples(index=False):
        symbol = str(row.symbol).lower()
        raw_row = raw_map.get(symbol, {})
        source_present = bool(raw_row)
        if source_present:
            source_rows += 1
        net_fields_present = (
            v2_common.to_float_or_none(raw_row.get("net_mf_amount")) is not None
            and v2_common.to_int_or_none(raw_row.get("net_mf_vol")) is not None
        )
        if net_fields_present:
            net_rows += 1
        rows.append(
            {
                "symbol": symbol,
                "trade_date": trade_date,
                **{
                    field: (
                        v2_common.to_int_or_none(raw_row.get(field))
                        if field in v2_common.MONEYFLOW_VOLUME_FIELDS
                        else v2_common.to_float_or_none(raw_row.get(field))
                    )
                    for field in v2_common.MONEYFLOW_VOLUME_FIELDS + v2_common.MONEYFLOW_AMOUNT_FIELDS
                },
                "source_moneyflow_present": bool(source_present),
                "net_fields_present": bool(net_fields_present),
                "source": "tushare_moneyflow",
                "build_run_id": build_run_id,
            }
        )
    frame = pd.DataFrame(rows, columns=SIDE_COLUMNS)
    traded_rows = int(len(main_frame))
    stats = {
        "trade_date": trade_date.isoformat(),
        "traded_rows": traded_rows,
        "source_rows": int(source_rows),
        "net_rows": int(net_rows),
        "row_coverage_ratio": float(source_rows / traded_rows) if traded_rows else 0.0,
        "net_amount_coverage_ratio": float(net_rows / traded_rows) if traded_rows else 0.0,
    }
    return frame, stats


def _side_rows_to_tuples(frame: pd.DataFrame) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    if frame.empty:
        return rows
    now = datetime.now()
    for row in frame.itertuples(index=False):
        values: list[Any] = []
        for column in SIDE_COLUMNS:
            value = getattr(row, column)
            if pd.isna(value):
                value = None
            values.append(value)
        values.extend([now, now])
        rows.append(tuple(values))
    return rows


def _whitelist_rows(per_trade_date: list[dict[str, Any]], build_run_id: str) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    now = datetime.now()
    for item in per_trade_date:
        row_ratio = float(item["row_coverage_ratio"])
        net_ratio = float(item["net_amount_coverage_ratio"])
        allow = row_ratio >= v2_common.MONEYFLOW_ROW_COVERAGE_THRESHOLD and net_ratio >= v2_common.MONEYFLOW_NET_COVERAGE_THRESHOLD
        rows.append(
            (
                date.fromisoformat(str(item["trade_date"])),
                build_run_id,
                row_ratio,
                net_ratio,
                float(v2_common.MONEYFLOW_ROW_COVERAGE_THRESHOLD),
                float(v2_common.MONEYFLOW_NET_COVERAGE_THRESHOLD),
                bool(allow),
                now,
            )
        )
    return rows


def build_update_args(
    *,
    start: str = "",
    end: str = "",
    table: str = v2_common.V2_MONEYFLOW_TABLE,
    symbols_csv: str = "",
    output_dir: str = "",
    heartbeat_path: str = "",
    heartbeat_label: str = "",
    apply: bool = True,
) -> argparse.Namespace:
    return argparse.Namespace(
        start=str(start or ""),
        end=str(end or ""),
        table=str(table or v2_common.V2_MONEYFLOW_TABLE),
        symbols_csv=str(symbols_csv or ""),
        output_dir=str(output_dir or ""),
        heartbeat_path=str(heartbeat_path or ""),
        heartbeat_label=str(heartbeat_label or ""),
        apply=bool(apply),
    )


def run_update(args: argparse.Namespace) -> dict[str, Any]:
    latest_before = common.get_latest_trade_date(str(args.table))
    start, latest_before = common.infer_start_date(str(args.start or ""), str(args.table))
    run_id = v2_common.build_run_id("moneyflow_v2")
    ts_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (v2_common.DEFAULT_OUTPUT_ROOT / f"pit_stock_moneyflow_v2_{ts_label}")
    output_dir.mkdir(parents=True, exist_ok=True)
    heartbeat_path = str(getattr(args, "heartbeat_path", "") or "").strip()
    heartbeat_label = str(getattr(args, "heartbeat_label", "") or "").strip() or "pit_stock_moneyflow_v2"

    summary: dict[str, Any]
    sample_frames: list[pd.DataFrame] = []
    per_trade_date: list[dict[str, Any]] = []
    latest_after: date | None = latest_before

    v2_common.touch_heartbeat(
        heartbeat_path,
        step=heartbeat_label,
        status="running",
        extra={"build_run_id": run_id, "phase": "start"},
    )

    try:
        with common.connect() as conn:
            with conn.cursor() as cur:
                _require_tables(cur)
                cur.execute("SET statement_timeout = '1200000ms'")
                if str(args.end or "").strip():
                    end = date.fromisoformat(str(args.end).strip())
                else:
                    open_dates = _load_open_trade_dates(conn, start, date.today())
                    end = max(open_dates) if open_dates else start
                trade_dates = _load_open_trade_dates(conn, start, end)
                symbol_filter = common.parse_symbols_csv(str(args.symbols_csv or ""))

                summary = {
                    "status": "ok",
                    "apply": bool(args.apply),
                    "table": str(args.table),
                    "build_run_id": run_id,
                    "date_range": {"start": start.isoformat(), "end": end.isoformat()},
                    "latest_trade_date_before": latest_before.isoformat() if latest_before else None,
                    "latest_trade_date_after": latest_before.isoformat() if latest_before else None,
                    "open_trade_dates": [item.isoformat() for item in trade_dates],
                    "symbol_filter_count": int(len(symbol_filter)),
                    "rows": 0,
                    "per_trade_date": [],
                    "notes": [
                        "pit_stock_moneyflow_v2 aligns to traded rows in pams_ohlcv_daily_v2.",
                        "moneyflow nulls remain null and are not coerced to zero.",
                    ],
                }
                for trade_date in trade_dates:
                    try:
                        main_frame = _load_traded_main_rows(conn, trade_date, symbol_filter)
                        raw_frame = _load_raw_moneyflow(conn, trade_date, symbol_filter)
                        built_frame, stats = _build_trade_date_frame(
                            trade_date=trade_date,
                            main_frame=main_frame,
                            raw_frame=raw_frame,
                            build_run_id=run_id,
                        )
                        rows = _side_rows_to_tuples(built_frame)
                        affected_rows = _upsert_rows(
                            cur,
                            table=str(args.table),
                            columns=[*SIDE_COLUMNS, "created_at", "updated_at"],
                            pk_columns=["symbol", "trade_date"],
                            rows=rows,
                        )
                        whitelist_rows = _whitelist_rows([stats], run_id)
                        _upsert_rows(
                            cur,
                            table=v2_common.V2_MONEYFLOW_WHITELIST_TABLE,
                            columns=[
                                "trade_date",
                                "build_run_id",
                                "row_coverage_ratio",
                                "net_amount_coverage_ratio",
                                "required_row_coverage_ratio",
                                "required_net_coverage_ratio",
                                "allow_in_research",
                                "created_at",
                            ],
                            pk_columns=["trade_date", "build_run_id"],
                            rows=whitelist_rows,
                        )
                        stats["rows"] = affected_rows
                        summary["rows"] += affected_rows
                        per_trade_date.append(stats)
                        common.append_sample_rows(sample_frames, built_frame)
                        if args.apply:
                            conn.commit()
                        else:
                            conn.rollback()
                        v2_common.touch_heartbeat(
                            heartbeat_path,
                            step=heartbeat_label,
                            trade_date=trade_date,
                            status="running",
                            extra={"build_run_id": run_id, "phase": "trade_date_committed"},
                        )
                    except Exception:
                        if args.apply:
                            conn.rollback()
                        raise

                summary["per_trade_date"] = per_trade_date
                if args.apply:
                    latest_after = common.get_latest_trade_date(str(args.table))
                else:
                    summary["status"] = "dry_run"
    except Exception:
        v2_common.touch_heartbeat(
            heartbeat_path,
            step=heartbeat_label,
            status="failed",
            extra={"build_run_id": run_id, "phase": "failed"},
        )
        raise

    summary["latest_trade_date_after"] = latest_after.isoformat() if latest_after else None
    sample_df = pd.concat(sample_frames, ignore_index=True) if sample_frames else pd.DataFrame(columns=SIDE_COLUMNS)
    sample_path = output_dir / "pit_stock_moneyflow_v2_sample.csv"
    sample_df.to_csv(sample_path, index=False)
    whitelist_path = output_dir / "pit_stock_moneyflow_v2_whitelist_daily.csv"
    pd.DataFrame(per_trade_date).to_csv(whitelist_path, index=False)
    summary["sample_csv"] = str(sample_path)
    summary["whitelist_csv"] = str(whitelist_path)
    v2_common.touch_heartbeat(
        heartbeat_path,
        step=heartbeat_label,
        status=summary["status"],
        extra={"build_run_id": run_id, "phase": "completed"},
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build pit_stock_moneyflow_v2 aligned to pams_ohlcv_daily_v2")
    parser.add_argument("--start", default="", help="inclusive start date YYYY-MM-DD; default latest side-table date + 1 or 2007-01-04")
    parser.add_argument("--end", default="", help="inclusive end date YYYY-MM-DD; default latest open date from v2 main table")
    parser.add_argument("--table", default=v2_common.V2_MONEYFLOW_TABLE, help="target side table")
    parser.add_argument("--symbols-csv", default="", help="optional comma-separated symbols for smoke runs")
    parser.add_argument("--output-dir", default="", help="output directory for summary/sample artifacts")
    parser.add_argument("--heartbeat-path", default="", help="optional heartbeat JSON path updated during long-running side-table build")
    parser.add_argument("--heartbeat-label", default="", help="optional logical step name written to heartbeat JSON")
    parser.add_argument("--apply", action="store_true", help="commit DB writes; default is dry-run rollback")
    args = parser.parse_args()

    summary = run_update(args)
    output_dir = Path(summary["sample_csv"]).parent
    summary_path = output_dir / "summary.json"
    common.write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_json={summary_path}")


if __name__ == "__main__":
    main()
