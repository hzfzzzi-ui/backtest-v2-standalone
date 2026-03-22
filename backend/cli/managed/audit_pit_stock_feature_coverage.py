from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import cn_side_table_common as common


DEFAULT_REFERENCE_TABLE = "pams_ohlcv_daily"
DEFAULT_DAILY_BASIC_TABLE = "pit_stock_daily_basic"
DEFAULT_MONEYFLOW_TABLE = "pit_stock_moneyflow"
DEFAULT_MARKET = "CN_A"


def _coerce_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _fetch_frame(cur, sql: str, params: tuple[Any, ...]) -> pd.DataFrame:
    cur.execute(sql, params)
    rows = cur.fetchall()
    columns = [item.name if hasattr(item, "name") else item[0] for item in (cur.description or [])]
    return pd.DataFrame(rows, columns=columns)


def _ensure_required_table(cur, table: str) -> None:
    table_name = common.safe_ident(table)
    cur.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
    if cur.fetchone()[0] is None:
        raise RuntimeError(f"required table does not exist: public.{table_name}")


def _resolve_reference_end_date(cur, reference_table: str, market: str) -> date | None:
    cur.execute(
        f"SELECT MAX(trade_date) FROM public.{common.safe_ident(reference_table)} WHERE market = %s",
        (market,),
    )
    row = cur.fetchone()
    return _coerce_date(row[0] if row else None)


def _fetch_coverage_frame(
    cur,
    *,
    start: date,
    end: date,
    market: str,
    reference_table: str,
    daily_basic_table: str,
    moneyflow_table: str,
) -> pd.DataFrame:
    sql = f"""
    WITH ref AS (
        SELECT trade_date, COUNT(*) AS reference_count
        FROM public.{common.safe_ident(reference_table)}
        WHERE market = %s
          AND trade_date BETWEEN %s AND %s
        GROUP BY trade_date
    ),
    daily_basic AS (
        SELECT trade_date, COUNT(*) AS daily_basic_count
        FROM public.{common.safe_ident(daily_basic_table)}
        WHERE trade_date BETWEEN %s AND %s
        GROUP BY trade_date
    ),
    moneyflow AS (
        SELECT trade_date, COUNT(*) AS moneyflow_count
        FROM public.{common.safe_ident(moneyflow_table)}
        WHERE trade_date BETWEEN %s AND %s
        GROUP BY trade_date
    )
    SELECT
        ref.trade_date,
        ref.reference_count,
        COALESCE(daily_basic.daily_basic_count, 0) AS daily_basic_count,
        COALESCE(moneyflow.moneyflow_count, 0) AS moneyflow_count
    FROM ref
    LEFT JOIN daily_basic USING (trade_date)
    LEFT JOIN moneyflow USING (trade_date)
    ORDER BY ref.trade_date
    """
    frame = _fetch_frame(
        cur,
        sql,
        (market, start, end, start, end, start, end),
    )
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "trade_date",
                "reference_count",
                "daily_basic_count",
                "moneyflow_count",
                "daily_basic_missing_count",
                "daily_basic_excess_count",
                "moneyflow_missing_count",
                "moneyflow_excess_count",
                "moneyflow_missing_vs_daily_basic_count",
                "daily_basic_coverage_ratio",
                "moneyflow_coverage_ratio",
                "moneyflow_vs_daily_basic_ratio",
            ]
        )

    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    for column in ["reference_count", "daily_basic_count", "moneyflow_count"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype(int)
    frame["daily_basic_missing_count"] = (frame["reference_count"] - frame["daily_basic_count"]).clip(lower=0)
    frame["daily_basic_excess_count"] = (frame["daily_basic_count"] - frame["reference_count"]).clip(lower=0)
    frame["moneyflow_missing_count"] = (frame["reference_count"] - frame["moneyflow_count"]).clip(lower=0)
    frame["moneyflow_excess_count"] = (frame["moneyflow_count"] - frame["reference_count"]).clip(lower=0)
    frame["moneyflow_missing_vs_daily_basic_count"] = (frame["daily_basic_count"] - frame["moneyflow_count"]).clip(lower=0)
    frame["daily_basic_coverage_ratio"] = (
        frame["daily_basic_count"] / frame["reference_count"].where(frame["reference_count"] > 0)
    ).round(6)
    frame["moneyflow_coverage_ratio"] = (
        frame["moneyflow_count"] / frame["reference_count"].where(frame["reference_count"] > 0)
    ).round(6)
    frame["moneyflow_vs_daily_basic_ratio"] = (
        frame["moneyflow_count"] / frame["daily_basic_count"].where(frame["daily_basic_count"] > 0)
    ).round(6)
    return frame


def _select_focus_trade_dates(frame: pd.DataFrame, missing_col: str, limit: int = 10) -> list[date]:
    if frame.empty:
        return []
    subset = frame[frame[missing_col] > 0].copy()
    if subset.empty:
        return []
    subset = subset.sort_values([missing_col, "trade_date"], ascending=[False, False]).head(limit)
    return [item for item in subset["trade_date"].tolist() if isinstance(item, date)]


def _fetch_gap_sample_frame(
    cur,
    *,
    market: str,
    reference_table: str,
    target_table: str,
    target_label: str,
    gap_kind: str,
    trade_dates: list[date],
    sample_per_trade_date: int = 25,
) -> pd.DataFrame:
    if not trade_dates:
        return pd.DataFrame(columns=["coverage_type", "trade_date", "symbol"])

    frames: list[pd.DataFrame] = []
    for trade_date in trade_dates:
        if gap_kind == "missing":
            sql = f"""
            SELECT ref.trade_date, ref.symbol
            FROM public.{common.safe_ident(reference_table)} AS ref
            LEFT JOIN public.{common.safe_ident(target_table)} AS tgt
              ON tgt.symbol = ref.symbol
             AND tgt.trade_date = ref.trade_date
            WHERE ref.market = %s
              AND ref.trade_date = %s
              AND tgt.symbol IS NULL
            ORDER BY ref.symbol
            LIMIT %s
            """
            params = (market, trade_date, int(sample_per_trade_date))
        elif gap_kind == "excess":
            sql = f"""
            SELECT tgt.trade_date, tgt.symbol
            FROM public.{common.safe_ident(target_table)} AS tgt
            LEFT JOIN public.{common.safe_ident(reference_table)} AS ref
              ON ref.symbol = tgt.symbol
             AND ref.trade_date = tgt.trade_date
             AND ref.market = %s
            WHERE tgt.trade_date = %s
              AND ref.symbol IS NULL
            ORDER BY tgt.symbol
            LIMIT %s
            """
            params = (market, trade_date, int(sample_per_trade_date))
        else:
            raise ValueError(f"unsupported gap_kind: {gap_kind}")
        frame = _fetch_frame(cur, sql, params)
        if frame.empty:
            continue
        frame["coverage_type"] = target_label
        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
        frames.append(frame[["coverage_type", "trade_date", "symbol"]].copy())
    if not frames:
        return pd.DataFrame(columns=["coverage_type", "trade_date", "symbol"])
    return pd.concat(frames, ignore_index=True)


def _build_worst_trade_dates(frame: pd.DataFrame, missing_col: str, ratio_col: str, count_col: str) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    subset = frame[frame[missing_col] > 0].copy()
    if subset.empty:
        return []
    subset = subset.sort_values([missing_col, ratio_col, "trade_date"], ascending=[False, True, False]).head(10)
    out: list[dict[str, Any]] = []
    for row in subset.itertuples(index=False):
        ratio_value = getattr(row, ratio_col)
        out.append(
            {
                "trade_date": row.trade_date.isoformat(),
                "reference_count": int(row.reference_count),
                "target_count": int(getattr(row, count_col)),
                "missing_count": int(getattr(row, missing_col)),
                "coverage_ratio": None if pd.isna(ratio_value) else float(ratio_value),
            }
        )
    return out


def build_audit_args(
    *,
    start: str = "",
    end: str = "",
    market: str = DEFAULT_MARKET,
    reference_table: str = DEFAULT_REFERENCE_TABLE,
    daily_basic_table: str = DEFAULT_DAILY_BASIC_TABLE,
    moneyflow_table: str = DEFAULT_MONEYFLOW_TABLE,
    output_dir: str = "",
) -> argparse.Namespace:
    return argparse.Namespace(
        start=str(start or ""),
        end=str(end or ""),
        market=str(market or DEFAULT_MARKET),
        reference_table=str(reference_table or DEFAULT_REFERENCE_TABLE),
        daily_basic_table=str(daily_basic_table or DEFAULT_DAILY_BASIC_TABLE),
        moneyflow_table=str(moneyflow_table or DEFAULT_MONEYFLOW_TABLE),
        output_dir=str(output_dir or ""),
    )


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    start = date.fromisoformat(str(args.start).strip()) if str(args.start or "").strip() else common.DEFAULT_BACKFILL_START
    ts_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (common.DEFAULT_OUTPUT_ROOT / f"pit_stock_feature_coverage_{ts_label}")
    output_dir.mkdir(parents=True, exist_ok=True)

    with common.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '1200000ms'")
            _ensure_required_table(cur, str(args.reference_table))
            _ensure_required_table(cur, str(args.daily_basic_table))
            _ensure_required_table(cur, str(args.moneyflow_table))
            end = (
                date.fromisoformat(str(args.end).strip())
                if str(args.end or "").strip()
                else _resolve_reference_end_date(cur, str(args.reference_table), str(args.market))
            )
            if end is None:
                raise RuntimeError("failed to resolve coverage audit end date from reference table")
            coverage_frame = _fetch_coverage_frame(
                cur,
                start=start,
                end=end,
                market=str(args.market),
                reference_table=str(args.reference_table),
                daily_basic_table=str(args.daily_basic_table),
                moneyflow_table=str(args.moneyflow_table),
            )
            daily_basic_focus_dates = _select_focus_trade_dates(coverage_frame, "daily_basic_missing_count")
            daily_basic_excess_focus_dates = _select_focus_trade_dates(coverage_frame, "daily_basic_excess_count")
            moneyflow_focus_dates = _select_focus_trade_dates(coverage_frame, "moneyflow_missing_count")
            moneyflow_excess_focus_dates = _select_focus_trade_dates(coverage_frame, "moneyflow_excess_count")
            daily_basic_missing_sample = _fetch_gap_sample_frame(
                cur,
                market=str(args.market),
                reference_table=str(args.reference_table),
                target_table=str(args.daily_basic_table),
                target_label="daily_basic_missing",
                gap_kind="missing",
                trade_dates=daily_basic_focus_dates,
            )
            daily_basic_excess_sample = _fetch_gap_sample_frame(
                cur,
                market=str(args.market),
                reference_table=str(args.reference_table),
                target_table=str(args.daily_basic_table),
                target_label="daily_basic_excess",
                gap_kind="excess",
                trade_dates=daily_basic_excess_focus_dates,
            )
            moneyflow_missing_sample = _fetch_gap_sample_frame(
                cur,
                market=str(args.market),
                reference_table=str(args.reference_table),
                target_table=str(args.moneyflow_table),
                target_label="moneyflow_missing",
                gap_kind="missing",
                trade_dates=moneyflow_focus_dates,
            )
            moneyflow_excess_sample = _fetch_gap_sample_frame(
                cur,
                market=str(args.market),
                reference_table=str(args.reference_table),
                target_table=str(args.moneyflow_table),
                target_label="moneyflow_excess",
                gap_kind="excess",
                trade_dates=moneyflow_excess_focus_dates,
            )

    coverage_path = output_dir / "pit_stock_feature_coverage_per_trade_date.csv"
    coverage_frame.to_csv(coverage_path, index=False)
    daily_basic_missing_path = output_dir / "pit_stock_daily_basic_missing_sample.csv"
    daily_basic_missing_sample.to_csv(daily_basic_missing_path, index=False)
    daily_basic_excess_path = output_dir / "pit_stock_daily_basic_excess_sample.csv"
    daily_basic_excess_sample.to_csv(daily_basic_excess_path, index=False)
    moneyflow_missing_path = output_dir / "pit_stock_moneyflow_missing_sample.csv"
    moneyflow_missing_sample.to_csv(moneyflow_missing_path, index=False)
    moneyflow_excess_path = output_dir / "pit_stock_moneyflow_excess_sample.csv"
    moneyflow_excess_sample.to_csv(moneyflow_excess_path, index=False)

    if coverage_frame.empty or start > end:
        return {
            "status": "noop",
            "market": str(args.market),
            "reference_table": str(args.reference_table),
            "daily_basic_table": str(args.daily_basic_table),
            "moneyflow_table": str(args.moneyflow_table),
            "date_range": {"start": start.isoformat(), "end": end.isoformat()},
            "trade_date_count": 0,
            "coverage_csv": str(coverage_path),
            "daily_basic_missing_sample_csv": str(daily_basic_missing_path),
            "daily_basic_excess_sample_csv": str(daily_basic_excess_path),
            "moneyflow_missing_sample_csv": str(moneyflow_missing_path),
            "moneyflow_excess_sample_csv": str(moneyflow_excess_path),
            "notes": [
                "No reference trade dates were found in the requested window.",
            ],
        }

    overall_reference_rows = int(coverage_frame["reference_count"].sum())
    overall_daily_basic_rows = int(coverage_frame["daily_basic_count"].sum())
    overall_moneyflow_rows = int(coverage_frame["moneyflow_count"].sum())
    overall_daily_basic_ratio = round(overall_daily_basic_rows / overall_reference_rows, 6) if overall_reference_rows else None
    overall_moneyflow_ratio = round(overall_moneyflow_rows / overall_reference_rows, 6) if overall_reference_rows else None
    overall_moneyflow_vs_daily_basic = (
        round(overall_moneyflow_rows / overall_daily_basic_rows, 6) if overall_daily_basic_rows else None
    )

    return {
        "status": "ok",
        "market": str(args.market),
        "reference_table": str(args.reference_table),
        "daily_basic_table": str(args.daily_basic_table),
        "moneyflow_table": str(args.moneyflow_table),
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "trade_date_count": int(len(coverage_frame)),
        "overall": {
            "reference_rows": overall_reference_rows,
            "daily_basic_rows": overall_daily_basic_rows,
            "moneyflow_rows": overall_moneyflow_rows,
            "daily_basic_missing_rows": int(coverage_frame["daily_basic_missing_count"].sum()),
            "daily_basic_excess_rows": int(coverage_frame["daily_basic_excess_count"].sum()),
            "moneyflow_missing_rows": int(coverage_frame["moneyflow_missing_count"].sum()),
            "moneyflow_excess_rows": int(coverage_frame["moneyflow_excess_count"].sum()),
            "daily_basic_coverage_ratio": overall_daily_basic_ratio,
            "moneyflow_coverage_ratio": overall_moneyflow_ratio,
            "moneyflow_vs_daily_basic_ratio": overall_moneyflow_vs_daily_basic,
        },
        "worst_trade_dates": {
            "daily_basic_missing": _build_worst_trade_dates(
                coverage_frame,
                "daily_basic_missing_count",
                "daily_basic_coverage_ratio",
                "daily_basic_count",
            ),
            "daily_basic_excess": _build_worst_trade_dates(
                coverage_frame,
                "daily_basic_excess_count",
                "daily_basic_coverage_ratio",
                "daily_basic_count",
            ),
            "moneyflow_missing": _build_worst_trade_dates(
                coverage_frame,
                "moneyflow_missing_count",
                "moneyflow_coverage_ratio",
                "moneyflow_count",
            ),
            "moneyflow_excess": _build_worst_trade_dates(
                coverage_frame,
                "moneyflow_excess_count",
                "moneyflow_coverage_ratio",
                "moneyflow_count",
            ),
        },
        "coverage_csv": str(coverage_path),
        "daily_basic_missing_sample_csv": str(daily_basic_missing_path),
        "daily_basic_excess_sample_csv": str(daily_basic_excess_path),
        "moneyflow_missing_sample_csv": str(moneyflow_missing_path),
        "moneyflow_excess_sample_csv": str(moneyflow_excess_path),
        "notes": [
            "Coverage is audited against pams_ohlcv_daily CN_A rows per trade_date.",
            "moneyflow coverage can be structurally lower than daily_basic coverage and must not be assumed to be full.",
            "Target rows can exceed the reference table if the side table contains symbols absent from the current pams_ohlcv_daily baseline.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit coverage of CN_A side tables against pams_ohlcv_daily")
    parser.add_argument("--start", default="", help="inclusive start date YYYY-MM-DD; default 2007-01-04")
    parser.add_argument("--end", default="", help="inclusive end date YYYY-MM-DD; default max trade_date in reference table")
    parser.add_argument("--market", default=DEFAULT_MARKET, help="reference market in pams_ohlcv_daily")
    parser.add_argument("--reference-table", default=DEFAULT_REFERENCE_TABLE, help="reference table for expected CN_A rows")
    parser.add_argument("--daily-basic-table", default=DEFAULT_DAILY_BASIC_TABLE, help="daily_basic side table")
    parser.add_argument("--moneyflow-table", default=DEFAULT_MONEYFLOW_TABLE, help="moneyflow side table")
    parser.add_argument("--output-dir", default="", help="output directory for summary and CSV artifacts")
    args = parser.parse_args()

    summary = run_audit(args)
    output_dir = Path(summary["coverage_csv"]).parent
    summary_path = output_dir / "summary.json"
    common.write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_json={summary_path}")


if __name__ == "__main__":
    main()
