from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import cn_side_table_common as common


DEFAULT_TABLE = "pit_stock_daily_basic"
SOURCE_LABEL = "tushare_daily_basic"
FIELDS = ["turnover_rate", "turnover_rate_f"]


def _normalize_daily_basic_frame(raw: pd.DataFrame, symbol_filter: set[str] | None = None) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["symbol", "trade_date", *FIELDS, "source"])
    df = raw.copy()
    keep_cols = [c for c in ["ts_code", "trade_date", *FIELDS] if c in df.columns]
    df = df.loc[:, keep_cols].copy()
    if "ts_code" not in df.columns or "trade_date" not in df.columns:
        raise RuntimeError("tushare daily_basic missing ts_code/trade_date")
    df["symbol"] = df["ts_code"].astype(str).map(common.normalize_stock_symbol).astype(str).str.lower()
    df["trade_date"] = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d", errors="coerce").dt.date
    df = df.dropna(subset=["symbol", "trade_date"]).reset_index(drop=True)
    if symbol_filter:
        df = df[df["symbol"].isin(symbol_filter)].copy()
    for column in FIELDS:
        if column not in df.columns:
            df[column] = pd.NA
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["source"] = SOURCE_LABEL
    return (
        df[["symbol", "trade_date", *FIELDS, "source"]]
        .drop_duplicates(subset=["symbol", "trade_date"], keep="last")
        .sort_values(["trade_date", "symbol"])
        .reset_index(drop=True)
    )


def _ensure_target_table(cur, table: str) -> None:
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.{common.safe_ident(table)} (
            symbol TEXT NOT NULL,
            trade_date DATE NOT NULL,
            turnover_rate DOUBLE PRECISION NULL,
            turnover_rate_f DOUBLE PRECISION NULL,
            source TEXT NOT NULL DEFAULT '{SOURCE_LABEL}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (symbol, trade_date)
        )
        """
    )
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{common.safe_ident(table)}_trade_date ON public.{common.safe_ident(table)} (trade_date DESC)"
    )


def _init_temp_table(cur) -> None:
    cur.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS tmp_pit_stock_daily_basic (
            symbol TEXT NOT NULL,
            trade_date DATE NOT NULL,
            turnover_rate DOUBLE PRECISION NULL,
            turnover_rate_f DOUBLE PRECISION NULL,
            source TEXT NOT NULL
        ) ON COMMIT DROP
        """
    )


def _load_batch_into_temp(cur, batch: pd.DataFrame) -> None:
    cur.execute("TRUNCATE TABLE tmp_pit_stock_daily_basic")
    if batch.empty:
        return
    cur.executemany(
        """
        INSERT INTO tmp_pit_stock_daily_basic (
            symbol, trade_date, turnover_rate, turnover_rate_f, source
        ) VALUES (%s, %s, %s, %s, %s)
        """,
        [
            (
                str(row.symbol),
                row.trade_date,
                None if pd.isna(row.turnover_rate) else float(row.turnover_rate),
                None if pd.isna(row.turnover_rate_f) else float(row.turnover_rate_f),
                str(row.source),
            )
            for row in batch.itertuples(index=False)
        ],
    )


def _count_batch_state(cur, table: str) -> tuple[int, int]:
    cur.execute(
        f"""
        SELECT
            COUNT(*) FILTER (WHERE dst.symbol IS NULL) AS insert_rows,
            COUNT(*) FILTER (WHERE dst.symbol IS NOT NULL) AS update_rows
        FROM tmp_pit_stock_daily_basic AS src
        LEFT JOIN public.{common.safe_ident(table)} AS dst
          ON dst.symbol = src.symbol
         AND dst.trade_date = src.trade_date
        """
    )
    row = cur.fetchone()
    return int(row[0] or 0), int(row[1] or 0)


def _upsert_batch(cur, table: str) -> int:
    cur.execute(
        f"""
        INSERT INTO public.{common.safe_ident(table)} (
            symbol, trade_date, turnover_rate, turnover_rate_f, source
        )
        SELECT
            symbol, trade_date, turnover_rate, turnover_rate_f, source
        FROM tmp_pit_stock_daily_basic
        ON CONFLICT (symbol, trade_date) DO UPDATE SET
            turnover_rate = EXCLUDED.turnover_rate,
            turnover_rate_f = EXCLUDED.turnover_rate_f,
            source = EXCLUDED.source,
            updated_at = NOW()
        """
    )
    return int(cur.rowcount or 0)


def _fetch_daily_basic_by_trade_date(pro: Any, trade_date: date, symbol_filter: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pro.daily_basic(
        trade_date=trade_date.strftime("%Y%m%d"),
        fields="ts_code,trade_date," + ",".join(FIELDS),
    )
    normalized = _normalize_daily_basic_frame(raw, symbol_filter)
    return raw if raw is not None else pd.DataFrame(), normalized


def build_update_args(
    *,
    start: str = "",
    end: str = "",
    token: str = "",
    table: str = DEFAULT_TABLE,
    symbols_csv: str = "",
    batch_size: int = 5000,
    output_dir: str = "",
    apply: bool = True,
) -> argparse.Namespace:
    return argparse.Namespace(
        start=str(start or ""),
        end=str(end or ""),
        token=common.resolve_tushare_token(str(token or "")),
        table=str(table or DEFAULT_TABLE),
        symbols_csv=str(symbols_csv or ""),
        batch_size=int(batch_size),
        output_dir=str(output_dir or ""),
        apply=bool(apply),
    )


def run_update(args: argparse.Namespace) -> dict[str, Any]:
    token = common.resolve_tushare_token(str(args.token or ""))
    pro = common.load_tushare_client(token)
    end = date.fromisoformat(str(args.end).strip()) if str(args.end or "").strip() else common.resolve_latest_trade_date(pro)
    if end is None:
        raise RuntimeError("failed to resolve target end date from Tushare trade calendar")
    start, latest_before = common.infer_start_date(str(args.start or ""), str(args.table))
    ts_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (common.DEFAULT_OUTPUT_ROOT / f"pit_stock_daily_basic_update_{ts_label}")
    output_dir.mkdir(parents=True, exist_ok=True)
    symbol_filter = common.parse_symbols_csv(str(args.symbols_csv or ""))
    open_trade_dates = common.load_open_trade_dates(pro, start, end)

    summary: dict[str, Any] = {
        "status": "ok",
        "apply": bool(args.apply),
        "table": str(args.table),
        "source": SOURCE_LABEL,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "latest_trade_date_before": latest_before.isoformat() if latest_before else None,
        "latest_trade_date_after": latest_before.isoformat() if latest_before else None,
        "symbol_filter_count": int(len(symbol_filter)),
        "open_trade_dates": [item.isoformat() for item in open_trade_dates],
        "fetched_rows": 0,
        "normalized_rows": 0,
        "insert_rows": 0,
        "update_rows": 0,
        "upserted_rows": 0,
        "per_trade_date": [],
        "notes": [
            "pit_stock_daily_basic stores explicit turnover fields from Tushare daily_basic.",
            "turnover_rate and turnover_rate_f are stored as source-of-truth values and are not derived from成交额.",
        ],
    }

    sample_frames: list[pd.DataFrame] = []
    with common.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '1200000ms'")
            _ensure_target_table(cur, str(args.table))
            _init_temp_table(cur)

            for trade_date in open_trade_dates:
                raw, normalized = _fetch_daily_basic_by_trade_date(pro, trade_date, symbol_filter)
                raw_rows = 0 if raw is None else int(len(raw))
                summary["fetched_rows"] += raw_rows
                summary["normalized_rows"] += int(len(normalized))
                summary["per_trade_date"].append(
                    {
                        "trade_date": trade_date.isoformat(),
                        "raw_rows": raw_rows,
                        "rows": int(len(normalized)),
                    }
                )
                common.append_sample_rows(sample_frames, normalized)
                if normalized.empty:
                    continue
                for batch_start in range(0, len(normalized), int(args.batch_size)):
                    batch = normalized.iloc[batch_start : batch_start + int(args.batch_size)].copy()
                    _load_batch_into_temp(cur, batch)
                    insert_rows, update_rows = _count_batch_state(cur, str(args.table))
                    upserted_rows = _upsert_batch(cur, str(args.table))
                    summary["insert_rows"] += insert_rows
                    summary["update_rows"] += update_rows
                    summary["upserted_rows"] += upserted_rows

            if args.apply:
                conn.commit()
            else:
                conn.rollback()
                summary["status"] = "dry_run"

    latest_after = common.get_latest_trade_date(str(args.table)) if args.apply else latest_before
    summary["latest_trade_date_after"] = latest_after.isoformat() if latest_after else None
    if start > end or not open_trade_dates:
        summary["status"] = "noop" if args.apply else "dry_run"
    sample_df = pd.concat(sample_frames, ignore_index=True) if sample_frames else pd.DataFrame(columns=["symbol", "trade_date", *FIELDS, "source"])
    sample_path = output_dir / "pit_stock_daily_basic_sample.csv"
    sample_df.to_csv(sample_path, index=False)
    summary["sample_csv"] = str(sample_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Update pit_stock_daily_basic from Tushare daily_basic")
    parser.add_argument("--start", default="", help="inclusive start date YYYY-MM-DD; default is latest target date + 1 or 2007-01-04")
    parser.add_argument("--end", default="", help="inclusive end date YYYY-MM-DD; default is latest available trade date")
    parser.add_argument("--token", default=common.resolve_tushare_token())
    parser.add_argument("--table", default=DEFAULT_TABLE, help="target PostgreSQL table")
    parser.add_argument("--symbols-csv", default="", help="optional comma-separated symbols, e.g. 600000.SH,000001.SZ")
    parser.add_argument("--batch-size", type=int, default=5000, help="DB upsert batch size")
    parser.add_argument("--output-dir", default="", help="output directory for summary/sample artifacts")
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
