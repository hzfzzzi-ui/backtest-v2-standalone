"""Import CSI1000 PIT CSV into pit_index_constituents.

Usage:
  python backend/scripts/import_csi1000_pit.py --from-csv data_cache/csi1000_pit_calendar_changes.csv

Behavior:
- Deletes existing rows for index_code='000852.SH' only.
- Inserts rows from CSV.
- Extends `pit_index_constituents` with optional calendar metadata columns when needed.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg


INDEX_CODE = "000852.SH"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "backend" / "configs" / "pams_cn_pg.json"
OPTIONAL_COLUMNS = (
    ("event_type", "TEXT"),
    ("rebalance_calendar_version", "TEXT"),
    ("rebalance_calendar_source", "TEXT"),
    ("rebalance_calendar_generated_at", "TEXT"),
)


@dataclass(frozen=True, slots=True)
class PITRow:
    index_code: str
    symbol: str
    in_date: str
    out_date: str | None
    source: str
    event_type: str | None = None
    rebalance_calendar_version: str | None = None
    rebalance_calendar_source: str | None = None
    rebalance_calendar_generated_at: str | None = None


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


def _get_conn():
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


def _default_source_label(csv_path: Path, explicit: str | None) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    name = csv_path.name.lower()
    if "calendar" in name:
        return "tushare_csi1000_calendar"
    if "monthly" in name:
        return "tushare_csi1000_monthly"
    if "manual" in name:
        return "csindex_official_manual"
    return "akshare_csi1000_static"


def _normalize_nullable_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _read_csv(csv_path: Path, source_label: str | None = None) -> list[PITRow]:
    rows_out: list[PITRow] = []
    fallback_source = _default_source_label(csv_path, source_label)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx = str(row.get("index_code") or "").strip().upper()
            sym = str(row.get("symbol") or "").strip().upper()
            in_date = str(row.get("in_date") or "").strip()
            out_date = _normalize_nullable_text(row.get("out_date"))
            source = str(row.get("source") or "").strip() or fallback_source
            if idx != INDEX_CODE or not sym or not in_date:
                continue
            rows_out.append(
                PITRow(
                    index_code=idx,
                    symbol=sym,
                    in_date=in_date,
                    out_date=out_date,
                    source=source,
                    event_type=_normalize_nullable_text(row.get("event_type")),
                    rebalance_calendar_version=_normalize_nullable_text(row.get("rebalance_calendar_version")),
                    rebalance_calendar_source=_normalize_nullable_text(row.get("rebalance_calendar_source")),
                    rebalance_calendar_generated_at=_normalize_nullable_text(row.get("rebalance_calendar_generated_at")),
                )
            )
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
            "membership_source": "unknown",
            "rebalance_calendar_version": None,
            "rebalance_calendar_source": None,
            "rebalance_calendar_generated_at": None,
        }

    start_dates = sorted({row.in_date for row in rows if row.in_date})
    end_dates = sorted({row.out_date for row in rows if row.out_date})
    sources = sorted({row.source for row in rows if row.source})
    versions = sorted({row.rebalance_calendar_version for row in rows if row.rebalance_calendar_version})
    calendar_sources = sorted({row.rebalance_calendar_source for row in rows if row.rebalance_calendar_source})
    generated_values = sorted(
        {row.rebalance_calendar_generated_at for row in rows if row.rebalance_calendar_generated_at}
    )
    return {
        "rows": int(len(rows)),
        "distinct_symbols": int(len({row.symbol for row in rows})),
        "distinct_start_dates": int(len(start_dates)),
        "open_rows": int(sum(1 for row in rows if not row.out_date)),
        "closed_rows": int(sum(1 for row in rows if row.out_date)),
        "min_start_date": start_dates[0] if start_dates else None,
        "max_start_date": start_dates[-1] if start_dates else None,
        "min_end_date": end_dates[0] if end_dates else None,
        "max_end_date": end_dates[-1] if end_dates else None,
        "membership_source": sources[0] if len(sources) == 1 else "mixed",
        "membership_sources": sources,
        "rebalance_calendar_version": versions[0] if len(versions) == 1 else ("mixed" if versions else None),
        "rebalance_calendar_source": (
            calendar_sources[0] if len(calendar_sources) == 1 else ("mixed" if calendar_sources else None)
        ),
        "rebalance_calendar_generated_at": (
            generated_values[0] if len(generated_values) == 1 else ("mixed" if generated_values else None)
        ),
    }


def _ensure_optional_columns(cur) -> None:
    for name, ddl_type in OPTIONAL_COLUMNS:
        cur.execute(f"ALTER TABLE public.pit_index_constituents ADD COLUMN IF NOT EXISTS {name} {ddl_type}")


def _rows_to_params(rows: list[PITRow]) -> list[tuple[Any, ...]]:
    return [
        (
            row.index_code,
            row.symbol,
            row.in_date,
            row.out_date,
            row.source,
            row.event_type,
            row.rebalance_calendar_version,
            row.rebalance_calendar_source,
            row.rebalance_calendar_generated_at,
        )
        for row in rows
    ]


def _query_db_summary(cur) -> dict[str, Any]:
    cur.execute(
        """
        SELECT
            COUNT(*)::bigint AS rows,
            COUNT(DISTINCT symbol)::bigint AS distinct_symbols,
            COUNT(DISTINCT start_date)::bigint AS distinct_start_dates,
            COUNT(*) FILTER (WHERE end_date IS NULL)::bigint AS open_rows,
            COUNT(*) FILTER (WHERE end_date IS NOT NULL)::bigint AS closed_rows,
            MIN(start_date)::text AS min_start_date,
            MAX(start_date)::text AS max_start_date,
            MIN(end_date)::text AS min_end_date,
            MAX(end_date)::text AS max_end_date,
            COUNT(DISTINCT source)::bigint AS distinct_sources,
            MIN(source)::text AS min_source,
            MAX(source)::text AS max_source,
            COUNT(DISTINCT rebalance_calendar_version)::bigint AS distinct_calendar_versions,
            MIN(rebalance_calendar_version)::text AS min_calendar_version,
            MAX(rebalance_calendar_version)::text AS max_calendar_version,
            COUNT(DISTINCT rebalance_calendar_source)::bigint AS distinct_calendar_sources,
            MIN(rebalance_calendar_source)::text AS min_calendar_source,
            MAX(rebalance_calendar_source)::text AS max_calendar_source,
            COUNT(DISTINCT rebalance_calendar_generated_at)::bigint AS distinct_calendar_generated_values,
            MIN(rebalance_calendar_generated_at)::text AS min_calendar_generated_at,
            MAX(rebalance_calendar_generated_at)::text AS max_calendar_generated_at
        FROM public.pit_index_constituents
        WHERE index_code = %s
        """,
        (INDEX_CODE,),
    )
    row = cur.fetchone()
    if row is None:
        return {}
    return {
        "rows": int(row[0] or 0),
        "distinct_symbols": int(row[1] or 0),
        "distinct_start_dates": int(row[2] or 0),
        "open_rows": int(row[3] or 0),
        "closed_rows": int(row[4] or 0),
        "min_start_date": row[5],
        "max_start_date": row[6],
        "min_end_date": row[7],
        "max_end_date": row[8],
        "membership_source": (
            row[10]
            if int(row[9] or 0) == 1
            else ("mixed" if int(row[9] or 0) > 1 else None)
        ),
        "rebalance_calendar_version": (
            row[13]
            if int(row[12] or 0) == 1
            else ("mixed" if int(row[12] or 0) > 1 else None)
        ),
        "rebalance_calendar_source": (
            row[16]
            if int(row[15] or 0) == 1
            else ("mixed" if int(row[15] or 0) > 1 else None)
        ),
        "rebalance_calendar_generated_at": (
            row[19]
            if int(row[18] or 0) == 1
            else ("mixed" if int(row[18] or 0) > 1 else None)
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CSI1000 PIT CSV")
    parser.add_argument("--from-csv", required=True, help="path to csi1000 PIT changes csv")
    parser.add_argument("--source-label", default="", help="override source label when CSV has no source column")
    parser.add_argument("--summary-out", default="", help="optional output path for structured import summary")
    args = parser.parse_args()

    csv_path = Path(args.from_csv).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"csv not found: {csv_path}")

    rows = _read_csv(csv_path, source_label=args.source_label)
    if not rows:
        raise RuntimeError(f"no valid {INDEX_CODE} rows found in csv")

    csv_summary = summarize_rows(rows)
    with _get_conn() as conn:
        with conn.cursor() as cur:
            _ensure_optional_columns(cur)
            cur.execute("SELECT COUNT(*) FROM public.pit_index_constituents WHERE index_code = %s", (INDEX_CODE,))
            old_cnt = int(cur.fetchone()[0] or 0)

            cur.execute("DELETE FROM public.pit_index_constituents WHERE index_code = %s", (INDEX_CODE,))
            cur.executemany(
                """
                INSERT INTO public.pit_index_constituents
                    (
                        index_code,
                        symbol,
                        start_date,
                        end_date,
                        source,
                        event_type,
                        rebalance_calendar_version,
                        rebalance_calendar_source,
                        rebalance_calendar_generated_at,
                        created_at
                    )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                _rows_to_params(rows),
            )
            db_summary = _query_db_summary(cur)
        conn.commit()

    summary = {
        "index_code": INDEX_CODE,
        "csv_path": str(csv_path),
        "csv": csv_summary,
        "db": db_summary,
        "old_rows": old_cnt,
        "new_rows": int(db_summary.get("rows") or 0),
    }
    summary_json = json.dumps(summary, ensure_ascii=False, indent=2)
    print(summary_json)

    if args.summary_out:
        summary_path = Path(args.summary_out).resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary_json, encoding="utf-8")


if __name__ == "__main__":
    main()
