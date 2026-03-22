"""Import CSI800 PIT CSV into pit_index_constituents.

Usage:
  python backend/scripts/import_csi800_pit.py --from-csv data_cache/csi800_pit_history_changes.csv --replace-existing

Behavior:
- Formal mode can replace all 000906.SH rows with a single-source history chain.
- Legacy patch mode preserves older history and trims overlap at the patch boundary.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError:
    psycopg = None


INDEX_CODE = "000906.SH"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "backend" / "configs" / "pams_cn_pg.json"


@dataclass(frozen=True, slots=True)
class PITRow:
    index_code: str
    symbol: str
    start_date: str
    end_date: str | None
    source: str


def _load_env_file() -> dict[str, str]:
    env_path = ROOT / ".env"
    out: dict[str, str] = {}
    if not env_path.exists():
        return out
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def _get_db_conn():
    if psycopg is None:
        raise RuntimeError("psycopg is not installed")
    file_env = _load_env_file()
    cfg = {}
    if DEFAULT_CONFIG_PATH.exists():
        cfg = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    db_cfg = dict(cfg.get("db") or {})
    return psycopg.connect(
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
        autocommit=False,
    )


def _normalize_nullable_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _default_source_label(csv_path: Path, explicit: str | None) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    name = csv_path.name.lower()
    if "history" in name or "trade_date" in name:
        return "tushare_csi800_history"
    if "monthly" in name:
        return "tushare_csi800_monthly"
    return "tushare_csi800_monthly"


def _read_csv(csv_path: Path, source_label: str | None = None) -> list[PITRow]:
    rows_out: list[PITRow] = []
    fallback_source = _default_source_label(csv_path, source_label)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            idx = str(row.get("index_code") or "").strip().upper()
            symbol = str(row.get("symbol") or "").strip().upper()
            start_date = str(row.get("in_date") or row.get("start_date") or "").strip()
            end_date = _normalize_nullable_text(row.get("out_date") or row.get("end_date"))
            source = str(row.get("source") or "").strip() or fallback_source
            if idx != INDEX_CODE or not symbol or not start_date:
                continue
            rows_out.append(
                PITRow(
                    index_code=idx,
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    source=source,
                )
            )
    rows_out.sort(key=lambda row: (row.symbol, row.start_date, row.end_date or ""))
    return rows_out


def summarize_rows(rows: list[PITRow]) -> dict[str, Any]:
    if not rows:
        return {
            "rows": 0,
            "distinct_symbols": 0,
            "distinct_start_dates": 0,
            "open_rows": 0,
            "closed_rows": 0,
            "min_start_date": None,
            "max_start_date": None,
            "min_end_date": None,
            "max_end_date": None,
            "membership_source": None,
            "membership_sources": [],
        }
    start_dates = sorted({row.start_date for row in rows if row.start_date})
    end_dates = sorted({row.end_date for row in rows if row.end_date})
    sources = sorted({row.source for row in rows if row.source})
    return {
        "rows": int(len(rows)),
        "distinct_symbols": int(len({row.symbol for row in rows})),
        "distinct_start_dates": int(len(start_dates)),
        "open_rows": int(sum(1 for row in rows if not row.end_date)),
        "closed_rows": int(sum(1 for row in rows if row.end_date)),
        "min_start_date": start_dates[0] if start_dates else None,
        "max_start_date": start_dates[-1] if start_dates else None,
        "min_end_date": end_dates[0] if end_dates else None,
        "max_end_date": end_dates[-1] if end_dates else None,
        "membership_source": sources[0] if len(sources) == 1 else ("mixed" if sources else None),
        "membership_sources": sources,
    }


def _load_existing_rows(conn) -> list[PITRow]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT index_code, symbol, start_date::text, end_date::text, COALESCE(source, '')
            FROM public.pit_index_constituents
            WHERE index_code = %s
            ORDER BY symbol, start_date, end_date NULLS LAST
            """,
            (INDEX_CODE,),
        )
        fetched = cur.fetchall()
    return [
        PITRow(
            index_code=str(row[0]),
            symbol=str(row[1]),
            start_date=str(row[2]),
            end_date=_normalize_nullable_text(row[3]),
            source=str(row[4] or "").strip() or "unknown",
        )
        for row in fetched
    ]


def _merge_rows(existing_rows: list[PITRow], patch_rows: list[PITRow]) -> tuple[list[PITRow], str | None]:
    if not patch_rows:
        return sorted(existing_rows, key=lambda row: (row.symbol, row.start_date, row.end_date or "")), None

    patch_start = min(row.start_date for row in patch_rows)
    merged: list[PITRow] = []
    for row in existing_rows:
        if row.start_date >= patch_start:
            continue
        if row.end_date is None or row.end_date > patch_start:
            merged.append(replace(row, end_date=patch_start))
        else:
            merged.append(row)
    merged.extend(patch_rows)
    merged.sort(key=lambda row: (row.symbol, row.start_date, row.end_date or ""))
    return merged, patch_start


def _select_rows_for_write(
    existing_rows: list[PITRow],
    patch_rows: list[PITRow],
    *,
    replace_existing: bool,
) -> tuple[list[PITRow], str | None, str]:
    if replace_existing:
        rows = sorted(patch_rows, key=lambda row: (row.symbol, row.start_date, row.end_date or ""))
        patch_start = min((row.start_date for row in rows), default=None)
        return rows, patch_start, "replace_existing"
    merged_rows, patch_start = _merge_rows(existing_rows, patch_rows)
    return merged_rows, patch_start, "merge_patch"


def _replace_rows(conn, rows: list[PITRow]) -> int:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM public.pit_index_constituents WHERE index_code = %s", (INDEX_CODE,))
        cur.executemany(
            """
            INSERT INTO public.pit_index_constituents
                (index_code, symbol, start_date, end_date, source, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            [
                (row.index_code, row.symbol, row.start_date, row.end_date, row.source)
                for row in rows
            ],
        )
    conn.commit()
    return len(rows)


def _query_pit_check(conn, check_date: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(DISTINCT symbol)
            FROM public.pit_index_constituents
            WHERE index_code = %s
              AND start_date <= %s
              AND (end_date IS NULL OR end_date > %s)
            """,
            (INDEX_CODE, check_date, check_date),
        )
        row = cur.fetchone()
    return int(row[0] or 0) if row else 0


def _write_summary(summary_out: Path, payload: dict[str, Any]) -> None:
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CSI800 PIT CSV")
    parser.add_argument("--from-csv", required=True, help="path to csi800 PIT changes csv")
    parser.add_argument("--source-label", default="", help="override source label when CSV has no source column")
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="replace all existing 000906.SH rows instead of merge-patching from the earliest start date",
    )
    parser.add_argument("--summary-out", default="", help="optional JSON summary output path")
    args = parser.parse_args()

    csv_path = Path(args.from_csv).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"csv not found: {csv_path}")

    patch_rows = _read_csv(csv_path, source_label=args.source_label)
    if not patch_rows:
        raise RuntimeError(f"no valid {INDEX_CODE} rows found in csv")

    patch_summary = summarize_rows(patch_rows)
    summary_payload: dict[str, Any] | None = None
    with _get_db_conn() as conn:
        existing_rows = _load_existing_rows(conn)
        old_summary = summarize_rows(existing_rows)
        rows_to_write, patch_start, mode = _select_rows_for_write(
            existing_rows,
            patch_rows,
            replace_existing=bool(args.replace_existing),
        )
        final_summary = summarize_rows(rows_to_write)

        print("=" * 60)
        print("  CSI800 PIT 数据导入")
        print("=" * 60)
        print(f"\n  输入文件: {csv_path}")
        print(f"    记录数:       {patch_summary['rows']}")
        print(f"    当前成分:     {patch_summary['open_rows']}")
        print(f"    历史移出记录: {patch_summary['closed_rows']}")
        print(f"    source:       {patch_summary['membership_source']}")
        print(f"    patch_start:  {patch_start}")
        print(f"    mode:         {mode}")

        print("\n  导入前数据库摘要:")
        print(f"    记录数:       {old_summary['rows']}")
        print(f"    当前成分:     {old_summary['open_rows']}")
        print(f"    历史移出记录: {old_summary['closed_rows']}")
        print(f"    source:       {old_summary['membership_source']}")

        check_dates = ["2010-01-01", "2016-03-01", "2020-01-01", "2025-01-01", "2025-08-01", "2026-03-01"]
        pre_counts: dict[str, int] = {}
        print("\n  PIT 对比（导入前）:")
        for check_date in check_dates:
            count = _query_pit_check(conn, check_date)
            pre_counts[check_date] = count
            print(f"    {check_date}: {count} 只")

        print("\n  正在写入...")
        count = _replace_rows(conn, rows_to_write)
        print(f"  写入 {count} 条记录")

        post_counts: dict[str, int] = {}
        print("\n  PIT 对比（导入后）:")
        for check_date in check_dates:
            checked = _query_pit_check(conn, check_date)
            post_counts[check_date] = checked
            print(f"    {check_date}: {checked} 只")

        summary_payload = {
            "status": "ok",
            "mode": mode,
            "csv_path": str(csv_path),
            "patch_start": patch_start,
            "input_summary": patch_summary,
            "existing_summary": old_summary,
            "final_summary": final_summary,
            "pit_check_before": pre_counts,
            "pit_check_after": post_counts,
        }

    print(f"\n{'=' * 60}")
    print("  导入完成")
    print(f"  导入模式: {summary_payload['mode'] if summary_payload else 'unknown'}")
    print(f"{'=' * 60}")

    if summary_payload is not None and str(args.summary_out or "").strip():
        _write_summary(Path(args.summary_out).resolve(), summary_payload)


if __name__ == "__main__":
    main()
