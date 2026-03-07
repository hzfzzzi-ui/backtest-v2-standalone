"""Import CSI1000 PIT CSV into pit_index_constituents.

Usage:
  python backend/scripts/import_csi1000_pit.py --from-csv /app/data_cache/csi1000_pit_changes.csv

Behavior:
- Deletes existing rows for index_code='000852.SH' only.
- Inserts records from CSV.
- Does NOT truncate the whole table.
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import psycopg


def _get_conn():
    return psycopg.connect(
        host=os.environ.get("PGHOST", os.environ.get("PAMS_PG_HOST", "pams-postgres")),
        port=int(os.environ.get("PGPORT", os.environ.get("PAMS_PG_PORT", "5432"))),
        dbname=os.environ.get("PGDATABASE", os.environ.get("PAMS_PG_DBNAME", "pams")),
        user=os.environ.get("PGUSER", os.environ.get("PAMS_PG_USER", "pams")),
        password=os.environ.get("PGPASSWORD", os.environ.get("PAMS_PG_PASSWORD", "")),
        autocommit=False,
    )


def _read_csv(csv_path: Path) -> list[tuple[str, str, str, str | None, str]]:
    rows_out: list[tuple[str, str, str, str | None, str]] = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx = str(row.get("index_code") or "").strip().upper()
            sym = str(row.get("symbol") or "").strip().upper()
            in_date = str(row.get("in_date") or "").strip()
            out_date_raw = str(row.get("out_date") or "").strip()
            out_date = out_date_raw if out_date_raw else None
            if idx != "000852.SH" or not sym or not in_date:
                continue
            rows_out.append((idx, sym, in_date, out_date, "akshare_csi1000_static"))
    return rows_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CSI1000 PIT CSV")
    parser.add_argument("--from-csv", required=True, help="path to csi1000_pit_changes.csv")
    args = parser.parse_args()

    csv_path = Path(args.from_csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"csv not found: {csv_path}")

    rows = _read_csv(csv_path)
    if not rows:
        raise RuntimeError("no valid 000852.SH rows found in csv")

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.pit_index_constituents WHERE index_code='000852.SH'")
            old_cnt = int(cur.fetchone()[0] or 0)

            cur.execute("DELETE FROM public.pit_index_constituents WHERE index_code='000852.SH'")
            cur.executemany(
                """
                INSERT INTO public.pit_index_constituents
                    (index_code, symbol, start_date, end_date, source, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                rows,
            )
            cur.execute("SELECT COUNT(*) FROM public.pit_index_constituents WHERE index_code='000852.SH'")
            new_cnt = int(cur.fetchone()[0] or 0)
        conn.commit()

    print(f"import done: index_code=000852.SH old={old_cnt} new={new_cnt}")


if __name__ == "__main__":
    main()

