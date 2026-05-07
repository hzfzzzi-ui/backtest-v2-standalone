"""Import CSI1000 PIT CSV into pit_index_constituents and refresh sidecar.

Usage:
  python backend/scripts/import_csi1000_pit.py --from-csv data_cache/csi1000_pit_calendar_changes.csv \
      --snapshots-csv data_cache/csi1000_pit_calendar_snapshots.csv

Behavior:
- Deletes existing rows for index_code='000852.SH' only.
- Inserts PIT interval rows from changes CSV.
- Rebuilds refresh sidecar rows from snapshots CSV in the same transaction.
- Extends `pit_index_constituents` with optional calendar metadata columns when needed.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg


INDEX_CODE = "000852.SH"
REFRESH_SIDECAR_TABLE = "pit_index_constituent_refresh_membership"
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.data.pg_env import connect as pg_connect
from backend.core.data.pg_env import read_env_file as read_shared_env_file

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


@dataclass(frozen=True, slots=True)
class SnapshotRow:
    index_code: str
    refresh_date: str
    symbol: str
    source: str
    event_type: str | None = None
    rebalance_calendar_version: str | None = None
    rebalance_calendar_source: str | None = None
    rebalance_calendar_generated_at: str | None = None
    snapshot_trade_date: str | None = None
    source_url: str | None = None
    source_note: str | None = None


@dataclass(frozen=True, slots=True)
class RefreshMembershipRow:
    index_code: str
    refresh_date: str
    symbol: str
    constituent_start_date: str
    source: str
    event_type: str | None = None
    snapshot_trade_date: str | None = None
    rebalance_calendar_version: str | None = None
    rebalance_calendar_source: str | None = None
    rebalance_calendar_generated_at: str | None = None
    source_url: str | None = None
    source_note: str | None = None


def _load_env_file() -> dict[str, str]:
    return read_shared_env_file(ROOT)


def _get_conn():
    return pg_connect(config_path=DEFAULT_CONFIG_PATH, root=ROOT, autocommit=False)


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


def _read_snapshots_csv(csv_path: Path, source_label: str | None = None) -> list[SnapshotRow]:
    rows_out: list[SnapshotRow] = []
    fallback_source = _default_source_label(csv_path, source_label)
    seen_keys: set[tuple[str, str, str]] = set()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            refresh_date = str(row.get("effective_date") or row.get("refresh_date") or "").strip()
            symbol = str(row.get("symbol") or "").strip().upper()
            if not refresh_date or not symbol:
                continue
            key = (INDEX_CODE, refresh_date, symbol)
            if key in seen_keys:
                raise RuntimeError(
                    f"duplicate snapshot row for index_code={INDEX_CODE} refresh_date={refresh_date} symbol={symbol}"
                )
            seen_keys.add(key)
            rows_out.append(
                SnapshotRow(
                    index_code=INDEX_CODE,
                    refresh_date=refresh_date,
                    symbol=symbol,
                    source=str(row.get("source") or "").strip() or fallback_source,
                    event_type=_normalize_nullable_text(row.get("event_type")),
                    rebalance_calendar_version=_normalize_nullable_text(row.get("rebalance_calendar_version")),
                    rebalance_calendar_source=_normalize_nullable_text(row.get("rebalance_calendar_source")),
                    rebalance_calendar_generated_at=_normalize_nullable_text(row.get("rebalance_calendar_generated_at")),
                    snapshot_trade_date=_normalize_nullable_text(row.get("snapshot_trade_date")),
                    source_url=_normalize_nullable_text(row.get("source_url")),
                    source_note=_normalize_nullable_text(row.get("source_note")),
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


def summarize_snapshot_rows(rows: list[SnapshotRow]) -> dict[str, Any]:
    if not rows:
        return {
            "rows": 0,
            "refresh_event_count": 0,
            "distinct_symbols": 0,
            "min_refresh_date": None,
            "max_refresh_date": None,
            "provider_floor_date": None,
        }
    refresh_dates = sorted({row.refresh_date for row in rows if row.refresh_date})
    provider_floor_candidates = sorted(
        {
            row.snapshot_trade_date or row.refresh_date
            for row in rows
            if row.source and "static" not in row.source.lower()
        }
    )
    sources = sorted({row.source for row in rows if row.source})
    event_types = sorted({row.event_type for row in rows if row.event_type})
    return {
        "rows": int(len(rows)),
        "refresh_event_count": int(len(refresh_dates)),
        "distinct_symbols": int(len({row.symbol for row in rows})),
        "min_refresh_date": refresh_dates[0] if refresh_dates else None,
        "max_refresh_date": refresh_dates[-1] if refresh_dates else None,
        "provider_floor_date": provider_floor_candidates[0] if provider_floor_candidates else None,
        "membership_source": sources[0] if len(sources) == 1 else ("mixed" if sources else None),
        "membership_sources": sources,
        "event_types": event_types,
        "snapshot_trade_date_rows": int(sum(1 for row in rows if row.snapshot_trade_date)),
    }


def _ensure_optional_columns(cur) -> None:
    for name, ddl_type in OPTIONAL_COLUMNS:
        cur.execute(f"ALTER TABLE public.pit_index_constituents ADD COLUMN IF NOT EXISTS {name} {ddl_type}")


def _ensure_refresh_sidecar_table(cur) -> None:
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.{REFRESH_SIDECAR_TABLE} (
            index_code VARCHAR NOT NULL,
            refresh_date DATE NOT NULL,
            symbol VARCHAR NOT NULL,
            constituent_start_date DATE NOT NULL,
            source TEXT,
            event_type TEXT,
            snapshot_trade_date DATE,
            rebalance_calendar_version TEXT,
            rebalance_calendar_source TEXT,
            rebalance_calendar_generated_at TEXT,
            source_url TEXT,
            source_note TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (index_code, refresh_date, symbol)
        )
        """
    )
    cur.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{REFRESH_SIDECAR_TABLE}_mapping
        ON public.{REFRESH_SIDECAR_TABLE} (index_code, symbol, constituent_start_date)
        """
    )


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


def _refresh_rows_to_params(rows: list[RefreshMembershipRow]) -> list[tuple[Any, ...]]:
    return [
        (
            row.index_code,
            row.refresh_date,
            row.symbol,
            row.constituent_start_date,
            row.source,
            row.event_type,
            row.snapshot_trade_date,
            row.rebalance_calendar_version,
            row.rebalance_calendar_source,
            row.rebalance_calendar_generated_at,
            row.source_url,
            row.source_note,
        )
        for row in rows
    ]


def _row_covers_refresh(row: PITRow, refresh_date: str) -> bool:
    if row.in_date > refresh_date:
        return False
    if row.out_date is None:
        return True
    return row.out_date > refresh_date


def _build_refresh_sidecar_rows(
    pit_rows: list[PITRow],
    snapshot_rows: list[SnapshotRow],
) -> list[RefreshMembershipRow]:
    pit_rows_by_symbol: dict[str, list[PITRow]] = {}
    for row in pit_rows:
        pit_rows_by_symbol.setdefault(row.symbol, []).append(row)
    for rows in pit_rows_by_symbol.values():
        rows.sort(key=lambda item: item.in_date)

    sidecar_rows: list[RefreshMembershipRow] = []
    for snapshot in snapshot_rows:
        candidates = [
            row
            for row in pit_rows_by_symbol.get(snapshot.symbol, [])
            if _row_covers_refresh(row, snapshot.refresh_date)
        ]
        if len(candidates) != 1:
            raise RuntimeError(
                "snapshot row could not be mapped to a unique PIT interval: "
                f"refresh_date={snapshot.refresh_date} symbol={snapshot.symbol} candidates={len(candidates)}"
            )
        matched = candidates[0]
        sidecar_rows.append(
            RefreshMembershipRow(
                index_code=INDEX_CODE,
                refresh_date=snapshot.refresh_date,
                symbol=snapshot.symbol,
                constituent_start_date=matched.in_date,
                source=snapshot.source,
                event_type=snapshot.event_type,
                snapshot_trade_date=snapshot.snapshot_trade_date,
                rebalance_calendar_version=snapshot.rebalance_calendar_version,
                rebalance_calendar_source=snapshot.rebalance_calendar_source,
                rebalance_calendar_generated_at=snapshot.rebalance_calendar_generated_at,
                source_url=snapshot.source_url,
                source_note=snapshot.source_note,
            )
        )
    return sidecar_rows


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
        "membership_source": row[10] if int(row[9] or 0) == 1 else ("mixed" if int(row[9] or 0) > 1 else None),
        "rebalance_calendar_version": (
            row[13] if int(row[12] or 0) == 1 else ("mixed" if int(row[12] or 0) > 1 else None)
        ),
        "rebalance_calendar_source": (
            row[16] if int(row[15] or 0) == 1 else ("mixed" if int(row[15] or 0) > 1 else None)
        ),
        "rebalance_calendar_generated_at": (
            row[19] if int(row[18] or 0) == 1 else ("mixed" if int(row[18] or 0) > 1 else None)
        ),
    }


def _query_sidecar_summary(cur) -> dict[str, Any]:
    cur.execute(
        f"""
        SELECT
            COUNT(*)::bigint AS rows,
            COUNT(DISTINCT refresh_date)::bigint AS refresh_event_count,
            COUNT(DISTINCT symbol)::bigint AS distinct_symbols,
            MIN(refresh_date)::text AS min_refresh_date,
            MAX(refresh_date)::text AS max_refresh_date,
            MIN(COALESCE(snapshot_trade_date, refresh_date))
                FILTER (WHERE source IS NULL OR source NOT ILIKE '%%static%%')::text AS provider_floor_date,
            COUNT(*) FILTER (WHERE snapshot_trade_date IS NOT NULL)::bigint AS snapshot_trade_date_rows
        FROM public.{REFRESH_SIDECAR_TABLE}
        WHERE index_code = %s
        """,
        (INDEX_CODE,),
    )
    row = cur.fetchone()
    if row is None:
        return {}
    return {
        "rows": int(row[0] or 0),
        "refresh_event_count": int(row[1] or 0),
        "distinct_symbols": int(row[2] or 0),
        "min_refresh_date": row[3],
        "max_refresh_date": row[4],
        "provider_floor_date": row[5],
        "snapshot_trade_date_rows": int(row[6] or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CSI1000 PIT CSV")
    parser.add_argument("--from-csv", required=True, help="path to csi1000 PIT changes csv")
    parser.add_argument("--snapshots-csv", default="", help="optional snapshots csv used to rebuild refresh sidecar")
    parser.add_argument("--source-label", default="", help="override source label when CSV has no source column")
    parser.add_argument("--summary-out", default="", help="optional output path for structured import summary")
    args = parser.parse_args()

    csv_path = Path(args.from_csv).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"csv not found: {csv_path}")

    snapshots_path = Path(args.snapshots_csv).resolve() if str(args.snapshots_csv or "").strip() else None
    if snapshots_path is not None and not snapshots_path.exists():
        raise FileNotFoundError(f"snapshots csv not found: {snapshots_path}")

    rows = _read_csv(csv_path, source_label=args.source_label)
    if not rows:
        raise RuntimeError(f"no valid {INDEX_CODE} rows found in csv")

    snapshot_rows = _read_snapshots_csv(snapshots_path, source_label=args.source_label) if snapshots_path else []
    refresh_rows = _build_refresh_sidecar_rows(rows, snapshot_rows) if snapshot_rows else []
    warnings: list[str] = []
    if snapshots_path is None:
        warnings.append("missing_snapshots_csv_sidecar_not_rebuilt")

    csv_summary = summarize_rows(rows)
    snapshot_summary = summarize_snapshot_rows(snapshot_rows)
    with _get_conn() as conn:
        with conn.cursor() as cur:
            _ensure_optional_columns(cur)
            _ensure_refresh_sidecar_table(cur)
            cur.execute("SELECT COUNT(*) FROM public.pit_index_constituents WHERE index_code = %s", (INDEX_CODE,))
            old_cnt = int(cur.fetchone()[0] or 0)
            cur.execute(f"SELECT COUNT(*) FROM public.{REFRESH_SIDECAR_TABLE} WHERE index_code = %s", (INDEX_CODE,))
            old_sidecar_cnt = int(cur.fetchone()[0] or 0)

            cur.execute(f"DELETE FROM public.{REFRESH_SIDECAR_TABLE} WHERE index_code = %s", (INDEX_CODE,))
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
            if refresh_rows:
                cur.executemany(
                    f"""
                    INSERT INTO public.{REFRESH_SIDECAR_TABLE}
                        (
                            index_code,
                            refresh_date,
                            symbol,
                            constituent_start_date,
                            source,
                            event_type,
                            snapshot_trade_date,
                            rebalance_calendar_version,
                            rebalance_calendar_source,
                            rebalance_calendar_generated_at,
                            source_url,
                            source_note,
                            created_at
                        )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    _refresh_rows_to_params(refresh_rows),
                )
            db_summary = _query_db_summary(cur)
            sidecar_summary = _query_sidecar_summary(cur)
        conn.commit()

    summary = {
        "index_code": INDEX_CODE,
        "csv_path": str(csv_path),
        "snapshots_csv": str(snapshots_path) if snapshots_path is not None else None,
        "csv": csv_summary,
        "snapshots": snapshot_summary,
        "db": db_summary,
        "sidecar": sidecar_summary,
        "old_rows": old_cnt,
        "new_rows": int(db_summary.get("rows") or 0),
        "old_sidecar_rows": old_sidecar_cnt,
        "new_sidecar_rows": int(sidecar_summary.get("rows") or 0),
        "warnings": warnings,
    }
    summary_json = json.dumps(summary, ensure_ascii=False, indent=2)
    print(summary_json)

    if args.summary_out:
        summary_path = Path(args.summary_out).resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary_json, encoding="utf-8")


if __name__ == "__main__":
    main()
