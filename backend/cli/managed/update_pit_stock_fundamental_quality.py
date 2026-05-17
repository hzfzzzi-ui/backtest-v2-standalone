from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import cn_side_table_common as common


DEFAULT_TABLE = "pit_stock_fundamental_quality"
SOURCE_LABEL = "tushare_fina_indicator"
FIELDS = ["roe", "roa", "grossprofit_margin", "netprofit_margin", "debt_to_assets"]


def _to_ts_code(symbol: str) -> str:
    normalized = common.normalize_stock_symbol(symbol).lower()
    if len(normalized) == 8 and normalized[:2] in {"sh", "sz", "bj"}:
        suffix = {"sh": "SH", "sz": "SZ", "bj": "BJ"}[normalized[:2]]
        return f"{normalized[2:]}.{suffix}"
    return str(symbol or "").strip()


def _normalize_fina_indicator_frame(raw: pd.DataFrame, symbol_filter: set[str] | None = None) -> pd.DataFrame:
    columns = ["symbol", "ann_date", "end_date", "roe", "roa", "gross_margin", "net_margin", "debt_to_assets", "source"]
    if raw is None or raw.empty:
        return pd.DataFrame(columns=columns)
    df = raw.copy()
    keep_cols = [col for col in ["ts_code", "ann_date", "end_date", *FIELDS] if col in df.columns]
    df = df.loc[:, keep_cols].copy()
    if "ts_code" not in df.columns or "ann_date" not in df.columns or "end_date" not in df.columns:
        raise RuntimeError("tushare fina_indicator missing ts_code/ann_date/end_date")
    df["symbol"] = df["ts_code"].astype(str).map(common.normalize_stock_symbol).astype(str).str.lower()
    if symbol_filter:
        df = df[df["symbol"].isin(symbol_filter)].copy()
    df["ann_date"] = pd.to_datetime(df["ann_date"].astype(str), format="%Y%m%d", errors="coerce").dt.date
    df["end_date"] = pd.to_datetime(df["end_date"].astype(str), format="%Y%m%d", errors="coerce").dt.date
    df = df.dropna(subset=["symbol", "ann_date", "end_date"]).copy()
    rename = {
        "grossprofit_margin": "gross_margin",
        "netprofit_margin": "net_margin",
    }
    df = df.rename(columns=rename)
    for column in ["roe", "roa", "gross_margin", "net_margin", "debt_to_assets"]:
        if column not in df.columns:
            df[column] = pd.NA
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["source"] = SOURCE_LABEL
    return (
        df[columns]
        .drop_duplicates(subset=["symbol", "ann_date", "end_date"], keep="last")
        .sort_values(["ann_date", "symbol", "end_date"])
        .reset_index(drop=True)
    )


def _ensure_target_table(cur, table: str) -> None:
    table_name = common.safe_ident(table)
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.{table_name} (
            symbol TEXT NOT NULL,
            ann_date DATE NOT NULL,
            end_date DATE NOT NULL,
            roe DOUBLE PRECISION NULL,
            roa DOUBLE PRECISION NULL,
            gross_margin DOUBLE PRECISION NULL,
            net_margin DOUBLE PRECISION NULL,
            debt_to_assets DOUBLE PRECISION NULL,
            source TEXT NOT NULL DEFAULT '{SOURCE_LABEL}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (symbol, ann_date, end_date)
        )
        """
    )
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_ann_date ON public.{table_name} (ann_date DESC)")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol_ann_date ON public.{table_name} (symbol, ann_date DESC)")


def _init_temp_table(cur) -> None:
    cur.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS tmp_pit_stock_fundamental_quality (
            symbol TEXT NOT NULL,
            ann_date DATE NOT NULL,
            end_date DATE NOT NULL,
            roe DOUBLE PRECISION NULL,
            roa DOUBLE PRECISION NULL,
            gross_margin DOUBLE PRECISION NULL,
            net_margin DOUBLE PRECISION NULL,
            debt_to_assets DOUBLE PRECISION NULL,
            source TEXT NOT NULL
        ) ON COMMIT DROP
        """
    )


def _load_batch_into_temp(cur, batch: pd.DataFrame) -> None:
    cur.execute("TRUNCATE TABLE tmp_pit_stock_fundamental_quality")
    if batch.empty:
        return
    cur.executemany(
        """
        INSERT INTO tmp_pit_stock_fundamental_quality (
            symbol, ann_date, end_date, roe, roa, gross_margin, net_margin, debt_to_assets, source
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                str(row.symbol),
                row.ann_date,
                row.end_date,
                None if pd.isna(row.roe) else float(row.roe),
                None if pd.isna(row.roa) else float(row.roa),
                None if pd.isna(row.gross_margin) else float(row.gross_margin),
                None if pd.isna(row.net_margin) else float(row.net_margin),
                None if pd.isna(row.debt_to_assets) else float(row.debt_to_assets),
                str(row.source),
            )
            for row in batch.itertuples(index=False)
        ],
    )


def _upsert_batch(cur, table: str) -> int:
    table_name = common.safe_ident(table)
    cur.execute(
        f"""
        INSERT INTO public.{table_name} (
            symbol, ann_date, end_date, roe, roa, gross_margin, net_margin, debt_to_assets, source
        )
        SELECT
            symbol, ann_date, end_date, roe, roa, gross_margin, net_margin, debt_to_assets, source
        FROM tmp_pit_stock_fundamental_quality
        ON CONFLICT (symbol, ann_date, end_date) DO UPDATE SET
            roe = EXCLUDED.roe,
            roa = EXCLUDED.roa,
            gross_margin = EXCLUDED.gross_margin,
            net_margin = EXCLUDED.net_margin,
            debt_to_assets = EXCLUDED.debt_to_assets,
            source = EXCLUDED.source,
            updated_at = NOW()
        """
    )
    return int(cur.rowcount or 0)


def _count_batch_state(cur, table: str) -> tuple[int, int]:
    cur.execute(
        f"""
        SELECT
            COUNT(*) FILTER (WHERE dst.symbol IS NULL) AS insert_rows,
            COUNT(*) FILTER (WHERE dst.symbol IS NOT NULL) AS update_rows
        FROM tmp_pit_stock_fundamental_quality AS src
        LEFT JOIN public.{common.safe_ident(table)} AS dst
          ON dst.symbol = src.symbol
         AND dst.ann_date = src.ann_date
         AND dst.end_date = src.end_date
        """
    )
    row = cur.fetchone()
    return int(row[0] or 0), int(row[1] or 0)


def _fetch_fina_indicator(pro: Any, ts_code: str, start: date, end: date) -> pd.DataFrame:
    return pro.fina_indicator(
        ts_code=ts_code,
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        fields="ts_code,ann_date,end_date," + ",".join(FIELDS),
    )


def build_update_args(
    *,
    start: str,
    end: str,
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
    if not str(args.start or "").strip() or not str(args.end or "").strip():
        raise RuntimeError("--start and --end are required for fundamental quality updates")
    pro = common.load_tushare_client(token)
    start = date.fromisoformat(str(args.start).strip())
    end = date.fromisoformat(str(args.end).strip())
    symbol_filter = common.parse_symbols_csv(str(args.symbols_csv or ""))
    if not symbol_filter:
        raise RuntimeError("--symbols-csv is required to keep the first fundamental import bounded")
    ts_codes = sorted(_to_ts_code(symbol) for symbol in symbol_filter)
    ts_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (common.DEFAULT_OUTPUT_ROOT / f"pit_stock_fundamental_quality_update_{ts_label}")
    output_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "status": "ok",
        "apply": bool(args.apply),
        "table": str(args.table),
        "source": SOURCE_LABEL,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "symbol_filter_count": int(len(symbol_filter)),
        "fetched_rows": 0,
        "normalized_rows": 0,
        "insert_rows": 0,
        "update_rows": 0,
        "upserted_rows": 0,
        "per_symbol": [],
        "notes": [
            "First pass imports only plain quality fields from Tushare fina_indicator.",
            "ann_date is the PIT observation date; end_date is the financial reporting period.",
        ],
    }
    sample_frames: list[pd.DataFrame] = []
    with common.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '1200000ms'")
            _ensure_target_table(cur, str(args.table))
            _init_temp_table(cur)
            for ts_code in ts_codes:
                raw = _fetch_fina_indicator(pro, ts_code, start, end)
                normalized = _normalize_fina_indicator_frame(raw, symbol_filter)
                if not normalized.empty:
                    normalized = normalized.loc[
                        (normalized["ann_date"] >= start) & (normalized["ann_date"] <= end)
                    ].copy()
                raw_rows = 0 if raw is None else int(len(raw))
                summary["fetched_rows"] += raw_rows
                summary["normalized_rows"] += int(len(normalized))
                summary["per_symbol"].append({"ts_code": ts_code, "raw_rows": raw_rows, "rows": int(len(normalized))})
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

    sample_df = pd.concat(sample_frames, ignore_index=True) if sample_frames else pd.DataFrame()
    sample_path = output_dir / "pit_stock_fundamental_quality_sample.csv"
    sample_df.to_csv(sample_path, index=False)
    summary["sample_csv"] = str(sample_path)
    common.write_json(output_dir / "pit_stock_fundamental_quality_update_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Update PIT stock fundamental quality from Tushare fina_indicator")
    parser.add_argument("--start", required=True, help="inclusive announcement start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="inclusive announcement end date YYYY-MM-DD")
    parser.add_argument("--token", default=common.resolve_tushare_token())
    parser.add_argument("--table", default=DEFAULT_TABLE)
    parser.add_argument("--symbols-csv", required=True, help="comma-separated stock symbols")
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.apply = not bool(args.dry_run)
    summary = run_update(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
