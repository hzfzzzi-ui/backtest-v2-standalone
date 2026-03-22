"""Materialize formal CSI800/000906 history from a long-history seed and optional patch.

This script builds a single formal chain that can be safely replace-imported into
`pit_index_constituents` for `000906.SH`.

Inputs:
- seed CSV: long-history changes file, typically recovered from a trusted backup
- patch CSV: optional tail updates, typically from Tushare trade_date history

Outputs:
- data_cache/csi800_formal_history_changes.csv
- data_cache/csi800_formal_history_summary.json
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scripts.import_csi800_pit import PITRow, _merge_rows, _read_csv, summarize_rows


FORMAL_SOURCE = "csi800_formal_history"


def _covers_date(rows: list[PITRow], target: str | None) -> bool | None:
    date_str = str(target or "").strip()
    if not date_str:
        return None
    for row in rows:
        if row.start_date <= date_str and (row.end_date is None or row.end_date > date_str):
            return True
    return False


def materialize_formal_rows(
    seed_rows: list[PITRow],
    *,
    patch_rows: list[PITRow] | None = None,
    source_label: str = FORMAL_SOURCE,
) -> tuple[list[PITRow], str | None, list[str]]:
    if not seed_rows:
        raise RuntimeError("seed_rows is empty")
    normalized_patch = list(patch_rows or [])
    component_sources = sorted(
        {
            str(row.source or "").strip()
            for row in [*seed_rows, *normalized_patch]
            if str(row.source or "").strip()
        }
    )
    if normalized_patch:
        merged_rows, patch_start = _merge_rows(seed_rows, normalized_patch)
    else:
        merged_rows = sorted(seed_rows, key=lambda row: (row.symbol, row.start_date, row.end_date or ""))
        patch_start = None
    final_rows = [replace(row, source=source_label) for row in merged_rows]
    return final_rows, patch_start, component_sources


def _write_changes_csv(path: Path, rows: list[PITRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["index_code", "symbol", "in_date", "out_date", "source"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "index_code": row.index_code,
                    "symbol": row.symbol,
                    "in_date": row.start_date,
                    "out_date": row.end_date or "",
                    "source": row.source,
                }
            )


def _build_summary(
    *,
    seed_csv: Path,
    patch_csv: Path | None,
    output_csv: Path,
    source_label: str,
    seed_rows: list[PITRow],
    patch_rows: list[PITRow],
    final_rows: list[PITRow],
    patch_start: str | None,
    required_start: str | None,
    required_end: str | None,
    component_sources: list[str],
) -> dict[str, Any]:
    return {
        "status": "ok",
        "source_label": source_label,
        "seed_csv": str(seed_csv),
        "patch_csv": None if patch_csv is None else str(patch_csv),
        "output_csv": str(output_csv),
        "mode": "seed_plus_patch" if patch_rows else "seed_only",
        "patch_start": patch_start,
        "required_start": required_start,
        "required_end": required_end,
        "covers_required_start": _covers_date(final_rows, required_start),
        "covers_required_end": _covers_date(final_rows, required_end),
        "component_sources": component_sources,
        "seed_summary": summarize_rows(seed_rows),
        "patch_summary": summarize_rows(patch_rows),
        "final_summary": summarize_rows(final_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize formal CSI800 history from seed and optional patch")
    parser.add_argument("--seed-csv", required=True)
    parser.add_argument("--patch-csv", default="")
    parser.add_argument("--out-csv", default="data_cache/csi800_formal_history_changes.csv")
    parser.add_argument("--summary-out", default="")
    parser.add_argument("--source-label", default=FORMAL_SOURCE)
    parser.add_argument("--required-start", default="2007-01-01")
    parser.add_argument("--required-end", default=dt.date.today().isoformat())
    args = parser.parse_args()

    seed_csv = Path(args.seed_csv).resolve()
    if not seed_csv.exists():
        raise FileNotFoundError(f"seed csv not found: {seed_csv}")
    patch_csv = Path(args.patch_csv).resolve() if str(args.patch_csv or "").strip() else None
    if patch_csv is not None and not patch_csv.exists():
        raise FileNotFoundError(f"patch csv not found: {patch_csv}")

    seed_rows = _read_csv(seed_csv)
    patch_rows = _read_csv(patch_csv) if patch_csv is not None else []
    final_rows, patch_start, component_sources = materialize_formal_rows(
        seed_rows,
        patch_rows=patch_rows,
        source_label=str(args.source_label or FORMAL_SOURCE).strip() or FORMAL_SOURCE,
    )
    required_start = str(args.required_start or "").strip() or None
    required_end = str(args.required_end or "").strip() or None
    if _covers_date(final_rows, required_start) is False:
        raise RuntimeError(f"formal CSI800 history does not cover required_start={required_start}")
    if _covers_date(final_rows, required_end) is False:
        raise RuntimeError(f"formal CSI800 history does not cover required_end={required_end}")

    out_csv = Path(args.out_csv).resolve()
    summary_out = Path(args.summary_out).resolve() if str(args.summary_out or "").strip() else (
        out_csv.parent / "csi800_formal_history_summary.json"
    )
    _write_changes_csv(out_csv, final_rows)
    summary = _build_summary(
        seed_csv=seed_csv,
        patch_csv=patch_csv,
        output_csv=out_csv,
        source_label=str(args.source_label or FORMAL_SOURCE).strip() or FORMAL_SOURCE,
        seed_rows=seed_rows,
        patch_rows=patch_rows,
        final_rows=final_rows,
        patch_start=patch_start,
        required_start=required_start,
        required_end=required_end,
        component_sources=component_sources,
    )
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
