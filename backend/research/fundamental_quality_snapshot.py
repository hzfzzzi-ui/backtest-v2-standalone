from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from psycopg.rows import dict_row

from backend.api.shared.json_utils import sanitize_json
from backend.core.data import pg_env
from backend.research.csi1000_negative_attribution import normalize_symbol
from backend.research.v4_fundamental_quality_shadow import compute_quality_score


FACTOR_ID = "fundamental_quality_v1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_path(path: str | Path) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        return raw
    return (_repo_root() / raw).resolve()


def load_symbols_from_csv(path: str | Path, *, column: str = "symbol") -> list[str]:
    frame = pd.read_csv(_resolve_path(path))
    if column not in frame.columns:
        raise ValueError(f"symbol source missing column: {column}")
    return sorted({normalize_symbol(value) for value in frame[column].dropna().tolist() if normalize_symbol(value)})


def _query_frame(conn: Any, sql: str, params: tuple[Any, ...]) -> pd.DataFrame:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return pd.DataFrame(rows)


def load_trade_dates(conn: Any, *, start: str, end: str) -> pd.DataFrame:
    frame = _query_frame(
        conn,
        """
        SELECT DISTINCT trade_date
        FROM public.pams_ohlcv_daily_v2
        WHERE trade_date BETWEEN %s AND %s
          AND row_status = 'traded'
        ORDER BY trade_date
        """,
        (start, end),
    )
    if frame.empty:
        return pd.DataFrame(columns=["date"])
    frame["date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    return frame.dropna(subset=["date"]).loc[:, ["date"]].drop_duplicates().sort_values("date").reset_index(drop=True)


def load_quality_rows(conn: Any, *, symbols: list[str], start: str, end: str) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    frame = _query_frame(
        conn,
        """
        SELECT symbol, ann_date, end_date, roe, roa, gross_margin, net_margin, debt_to_assets AS leverage
        FROM public.pit_stock_fundamental_quality
        WHERE symbol = ANY(%s)
          AND ann_date <= %s
          AND ann_date >= %s
        ORDER BY symbol, ann_date, end_date
        """,
        (symbols, end, start),
    )
    if frame.empty:
        return pd.DataFrame()
    frame["symbol"] = frame["symbol"].map(normalize_symbol)
    frame["ann_date"] = pd.to_datetime(frame["ann_date"], errors="coerce")
    frame["end_date"] = pd.to_datetime(frame["end_date"], errors="coerce")
    return compute_quality_score(frame.dropna(subset=["symbol", "ann_date"]))


def build_daily_quality_snapshot(
    *,
    symbols: list[str],
    start: str,
    end: str,
    min_ann_start: str = "2007-01-01",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    normalized_symbols = sorted({normalize_symbol(symbol) for symbol in symbols if normalize_symbol(symbol)})
    with pg_env.connect(autocommit=True) as conn:
        trade_dates = load_trade_dates(conn, start=start, end=end)
        quality = load_quality_rows(conn, symbols=normalized_symbols, start=min_ann_start, end=end)
    if trade_dates.empty or quality.empty or not normalized_symbols:
        empty = pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "factor_id",
                "quality_score",
                "available",
                "source_ann_date",
                "source_end_date",
                "quality_component_count",
            ]
        )
        return empty, {
            "status": "empty",
            "symbol_count": len(normalized_symbols),
            "trade_dates": int(len(trade_dates)),
            "quality_rows": int(len(quality)),
        }

    grid = pd.MultiIndex.from_product(
        [trade_dates["date"].tolist(), normalized_symbols],
        names=["date", "symbol"],
    ).to_frame(index=False)
    quality = quality.sort_values(["symbol", "ann_date", "end_date"]).reset_index(drop=True)
    chunks: list[pd.DataFrame] = []
    for symbol, grid_group in grid.groupby("symbol", sort=False):
        quality_group = quality.loc[quality["symbol"].eq(symbol)].sort_values("ann_date")
        if quality_group.empty:
            group = grid_group.copy()
            group["quality_score"] = np.nan
            group["source_ann_date"] = pd.NaT
            group["source_end_date"] = pd.NaT
            group["quality_component_count"] = 0
            chunks.append(group)
            continue
        merged = pd.merge_asof(
            grid_group.sort_values("date"),
            quality_group,
            left_on="date",
            right_on="ann_date",
            by="symbol",
            direction="backward",
        )
        merged = merged.rename(columns={"ann_date": "source_ann_date", "end_date": "source_end_date"})
        chunks.append(merged)
    snapshot = pd.concat(chunks, ignore_index=True)
    snapshot["factor_id"] = FACTOR_ID
    snapshot["available"] = snapshot["quality_score"].notna() & (pd.to_numeric(snapshot["quality_component_count"], errors="coerce") >= 2)
    keep = [
        "date",
        "symbol",
        "factor_id",
        "quality_score",
        "available",
        "source_ann_date",
        "source_end_date",
        "quality_component_count",
        "roe",
        "roa",
        "gross_margin",
        "net_margin",
        "leverage",
    ]
    snapshot = snapshot.loc[:, [col for col in keep if col in snapshot.columns]].sort_values(["date", "symbol"]).reset_index(drop=True)
    available = snapshot.loc[snapshot["available"]]
    audit = {
        "status": "ok",
        "factor_id": FACTOR_ID,
        "symbol_count": len(normalized_symbols),
        "trade_dates": int(trade_dates["date"].nunique()),
        "quality_rows": int(len(quality)),
        "snapshot_rows": int(len(snapshot)),
        "available_rows": int(len(available)),
        "coverage_rate": float(len(available) / len(snapshot)) if len(snapshot) else 0.0,
        "min_date": str(snapshot["date"].min().date()) if not snapshot.empty else None,
        "max_date": str(snapshot["date"].max().date()) if not snapshot.empty else None,
        "min_source_ann_date": str(available["source_ann_date"].min().date()) if not available.empty else None,
        "max_source_ann_date": str(available["source_ann_date"].max().date()) if not available.empty else None,
    }
    return snapshot, audit


def write_daily_quality_snapshot(
    *,
    symbols_csv: str | Path,
    output_dir: str | Path,
    start: str,
    end: str,
    symbol_column: str = "symbol",
    min_ann_start: str = "2007-01-01",
) -> dict[str, Any]:
    output = _resolve_path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    symbols = load_symbols_from_csv(symbols_csv, column=symbol_column)
    snapshot, audit = build_daily_quality_snapshot(
        symbols=symbols,
        start=start,
        end=end,
        min_ann_start=min_ann_start,
    )
    snapshot_path = output / "fundamental_quality_daily_snapshot.csv"
    audit_path = output / "fundamental_quality_daily_snapshot_audit.json"
    snapshot.to_csv(snapshot_path, index=False, encoding="utf-8")
    payload = {**audit, "snapshot_path": str(snapshot_path), "symbol_source": str(_resolve_path(symbols_csv))}
    audit_path.write_text(json.dumps(sanitize_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return sanitize_json(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build PIT daily fundamental quality snapshot for ranking overlay research.")
    parser.add_argument("--symbols-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--symbol-column", default="symbol")
    parser.add_argument("--min-ann-start", default="2007-01-01")
    args = parser.parse_args()
    payload = write_daily_quality_snapshot(
        symbols_csv=args.symbols_csv,
        output_dir=args.output_dir,
        start=args.start,
        end=args.end,
        symbol_column=args.symbol_column,
        min_ann_start=args.min_ann_start,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
