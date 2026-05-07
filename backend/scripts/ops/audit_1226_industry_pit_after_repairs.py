from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from backend.core.config.loader import load_config
from backend.core.data.provider_factory import build_runtime_provider_from_config
from backend.core.engine_vector.breakout_signal_provider import _build_industry_assignment_matrices


def _membership_mask(
    membership_history: pd.DataFrame,
    *,
    symbols: list[str],
    date_index: pd.DatetimeIndex,
) -> np.ndarray:
    mask = np.zeros((len(date_index), len(symbols)), dtype=bool)
    if membership_history.empty or not symbols or date_index.empty:
        return mask
    symbol_to_col = {str(sym).lower(): idx for idx, sym in enumerate(symbols)}
    hist = membership_history.copy()
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    hist["start_date"] = pd.to_datetime(hist["start_date"], errors="coerce").dt.normalize()
    hist["end_date"] = pd.to_datetime(hist["end_date"], errors="coerce").dt.normalize()
    hist = hist.dropna(subset=["symbol", "start_date"]).reset_index(drop=True)
    for row in hist.itertuples(index=False):
        col_idx = symbol_to_col.get(str(row.symbol).lower())
        if col_idx is None:
            continue
        start_idx = int(date_index.searchsorted(pd.Timestamp(row.start_date).normalize(), side="left"))
        end_idx = (
            int(date_index.searchsorted(pd.Timestamp(row.end_date).normalize(), side="left"))
            if not pd.isna(row.end_date)
            else len(date_index)
        )
        if start_idx >= len(date_index) or start_idx >= end_idx:
            continue
        mask[start_idx:end_idx, col_idx] = True
    return mask


def _active_price_mask(
    provider: object,
    *,
    symbols: list[str],
    start: date,
    end: date,
    date_index: pd.DatetimeIndex,
) -> np.ndarray:
    if not symbols or date_index.empty:
        return np.zeros((len(date_index), len(symbols)), dtype=bool)
    q = (
        "SELECT trade_date, symbol "
        "FROM pams_ohlcv_daily "
        "WHERE trade_date >= %s AND trade_date <= %s "
        "AND symbol = ANY(%s) "
        "ORDER BY trade_date, symbol"
    )
    exec_df = getattr(provider, "_exec_df", None)
    if not callable(exec_df):
        raise TypeError("ops industry PIT audit requires a provider with _exec_df support")
    raw = exec_df(
        q,
        (start, end, symbols),
        {
            "provider": "postgres",
            "source": "industry_pit_audit_price_presence",
            "table": "pams_ohlcv_daily",
            "symbols": [f"{len(symbols)} symbols"],
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
    )
    if raw.empty:
        return np.zeros((len(date_index), len(symbols)), dtype=bool)
    dates = pd.to_datetime(raw["trade_date"], errors="coerce").dt.normalize()
    date_pos = date_index.get_indexer(dates)
    symbol_to_col = {str(sym).lower(): idx for idx, sym in enumerate(symbols)}
    symbol_pos = raw["symbol"].astype(str).str.lower().map(symbol_to_col).to_numpy(dtype=float)
    valid = (date_pos >= 0) & ~np.isnan(symbol_pos)
    mask = np.zeros((len(date_index), len(symbols)), dtype=bool)
    mask[date_pos[valid], symbol_pos[valid].astype(int)] = True
    return mask


def _resolve_output_dir(base: Path | None) -> Path:
    if base is not None:
        return base.resolve()
    return (
        Path("outputs")
        / "ops"
        / "audit_1226_industry_pit_after_repairs_20260314"
    ).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit 12-26 PIT industry mapping after repairs.")
    parser.add_argument("--config", default="backend/configs/pams_cn_pg.json")
    parser.add_argument("--start", default="2012-01-04")
    parser.add_argument("--end", default="2026-03-01")
    parser.add_argument("--index-code", default="000906.SH")
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    start = date.fromisoformat(str(args.start))
    end = date.fromisoformat(str(args.end))
    output_dir = _resolve_output_dir(Path(args.output_dir) if str(args.output_dir).strip() else None)
    output_dir.mkdir(parents=True, exist_ok=True)

    cfg_obj, _ = load_config(args.config)
    provider = build_runtime_provider_from_config(
        cfg_obj,
        "backend/core/data/rules.csv",
        use_cache=False,
    )

    membership_history = provider.load_index_constituent_history(args.index_code, start, end)
    membership_history = membership_history.copy()
    membership_history["symbol"] = membership_history["symbol"].astype(str).str.lower()
    symbols = sorted(membership_history["symbol"].dropna().astype(str).unique().tolist())
    date_index = provider.load_trading_calendar_cn(start, end).normalize()

    active_mask = _active_price_mask(provider, symbols=symbols, start=start, end=end, date_index=date_index)
    member_mask = _membership_mask(membership_history, symbols=symbols, date_index=date_index)
    relevant_mask = active_mask & member_mask

    industry_map = provider.load_industry_mapping(symbols)
    industry_history = provider.load_industry_history(symbols, start, end)
    sec_df = provider.load_sector_indices(start, end)
    sector_data: dict[str, pd.DataFrame] = {}
    if not sec_df.empty:
        for code, grp in sec_df.groupby("index_code"):
            sector_data[str(code).upper()] = grp.reset_index(drop=True)

    name_matrix, code_matrix = _build_industry_assignment_matrices(
        industry_map=industry_map,
        industry_history=industry_history,
        sector_data=sector_data,
        symbols=symbols,
        dates=date_index.to_numpy(),
    )
    if name_matrix is None or code_matrix is None:
        raise RuntimeError("industry assignment matrices unexpectedly returned None")

    name_arr = np.asarray(name_matrix, dtype=object)
    code_arr = np.asarray(code_matrix, dtype=object)
    if name_arr.ndim != 2 or code_arr.ndim != 2:
        raise RuntimeError(
            f"unexpected matrix shape: name={name_arr.shape!r} code={code_arr.shape!r}"
        )

    name_missing = pd.isna(name_arr)
    code_missing = pd.isna(code_arr)
    pit_gap_mask = relevant_mask & name_missing
    crosswalk_gap_mask = relevant_mask & (~name_missing) & code_missing

    static_map_available = np.array([str(sym).lower() in industry_map for sym in symbols], dtype=bool)
    pit_gap_static_map_available_mask = pit_gap_mask & static_map_available.reshape(1, -1)

    standard_df = provider._exec_df(
        "SELECT standard, COUNT(*) AS rows FROM pit_industry_history GROUP BY standard ORDER BY standard",
        tuple(),
        {
            "provider": "postgres",
            "source": "industry_pit_audit_standard_counts",
            "table": "pit_industry_history",
            "symbols": [],
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
    )
    standard_counts = {
        str(row["standard"]): int(row["rows"])
        for _, row in standard_df.iterrows()
    }

    pit_gap_days_by_symbol = pit_gap_mask.sum(axis=0).astype(int)
    crosswalk_gap_days_by_symbol = crosswalk_gap_mask.sum(axis=0).astype(int)
    relevant_days_by_symbol = relevant_mask.sum(axis=0).astype(int)
    coverage_rows = []
    for idx, sym in enumerate(symbols):
        coverage_rows.append(
            {
                "symbol": sym,
                "relevant_days": int(relevant_days_by_symbol[idx]),
                "pit_gap_days": int(pit_gap_days_by_symbol[idx]),
                "crosswalk_gap_days": int(crosswalk_gap_days_by_symbol[idx]),
            }
        )
    coverage_df = pd.DataFrame(coverage_rows).sort_values(
        ["pit_gap_days", "crosswalk_gap_days", "relevant_days", "symbol"],
        ascending=[False, False, False, True],
    )
    coverage_df.to_csv(output_dir / "pit_coverage_by_symbol.csv", index=False, encoding="utf-8-sig")

    crosswalk_rows = []
    pit_rows = []
    row_idx, col_idx = np.where(crosswalk_gap_mask)
    for r, c in zip(row_idx.tolist(), col_idx.tolist()):
        crosswalk_rows.append(
            {
                "trade_date": str(date_index[r].date()),
                "symbol": symbols[c],
                "industry_l1": None if pd.isna(name_arr[r, c]) else str(name_arr[r, c]),
            }
        )
    row_idx, col_idx = np.where(pit_gap_mask)
    for r, c in zip(row_idx.tolist(), col_idx.tolist()):
        pit_rows.append(
            {
                "trade_date": str(date_index[r].date()),
                "symbol": symbols[c],
            }
        )
    pd.DataFrame(crosswalk_rows).to_csv(
        output_dir / "sw_contemporaneous_crosswalk_rows.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(pit_rows).to_csv(
        output_dir / "pit_gap_rows.csv", index=False, encoding="utf-8-sig"
    )

    summary = {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "index_code": str(args.index_code),
        "union_symbol_count": int(len(symbols)),
        "membership_history_rows": int(len(membership_history)),
        "relevant_stock_days": int(relevant_mask.sum()),
        "standard_counts": standard_counts,
        "pit_gap_symbols": int((pit_gap_days_by_symbol > 0).sum()),
        "pit_gap_days": int(pit_gap_mask.sum()),
        "crosswalk_gap_symbols": int((crosswalk_gap_days_by_symbol > 0).sum()),
        "crosswalk_gap_days": int(crosswalk_gap_mask.sum()),
        "latest_mapping_fallback_removed": bool(pit_gap_static_map_available_mask.sum() > 0 or int(pit_gap_mask.sum()) == 0),
        "pit_gap_days_with_static_mapping_available": int(pit_gap_static_map_available_mask.sum()),
        "pit_safe_runtime_industry_labels": bool(int(pit_gap_mask.sum()) == 0 and int(crosswalk_gap_mask.sum()) == 0),
        "sector_index_code_count": int(len(sector_data)),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
