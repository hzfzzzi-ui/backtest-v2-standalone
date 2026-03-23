"""Build CSI1000 PIT records from manually curated official snapshots.

This script is intended for the "official announcement / manual ETL" path when
commercial data entitlements are not available.

Expected workflow:
1. Download official CSI1000 constituent snapshots or adjustment attachments.
2. Convert each snapshot to CSV/XLS/XLSX with one symbol/code column.
3. Prepare a manifest CSV listing effective_date -> snapshot file mapping.
4. Run this script to reconstruct PIT changes and flattened snapshots.
5. Import the generated changes CSV with `import_csi1000_pit.py`.

Manifest columns:
- effective_date (required, YYYY-MM-DD)
- snapshot_path (required, relative to manifest file or absolute path)
- source (optional, default: csindex_official_manual)
- event_type (optional, default: scheduled)
- version (optional, default: manual-v1)
- snapshot_trade_date (optional, structured lineage field)
- rebalance_calendar_source (optional, default: source)
- rebalance_calendar_generated_at (optional, ISO-8601 timestamp)
- source_url (optional, metadata only)
- source_note (optional, metadata only)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


INDEX_CODE = "000852.SH"
DEFAULT_SOURCE = "csindex_official_manual"


@dataclass(frozen=True)
class SnapshotSpec:
    effective_date: str
    snapshot_path: Path
    source: str
    event_type: str = "scheduled"
    version: str = "manual-v1"
    snapshot_trade_date: str = ""
    rebalance_calendar_source: str = DEFAULT_SOURCE
    rebalance_calendar_generated_at: str = ""
    source_url: str = ""
    source_note: str = ""


def _to_local_symbol(code: str) -> str:
    text = str(code or "").strip().upper()
    if not text or text in {"NAN", "NONE"}:
        return ""
    if "." in text:
        left, right = text.split(".", 1)
        right = right.upper()
        if right in {"SH", "SZ"}:
            return f"{left.zfill(6)}.{right}"
        if left in {"SH", "SZ"}:
            return f"{right.zfill(6)}.{left}"
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return ""
    if len(digits) < 6:
        digits = digits.zfill(6)
    if len(digits) != 6:
        return ""
    if digits.startswith(("6", "9")):
        return f"{digits}.SH"
    return f"{digits}.SZ"


def _looks_like_symbol_series(series: pd.Series) -> float:
    total = 0
    ok = 0
    for value in series.dropna().tolist():
        total += 1
        if _to_local_symbol(str(value)):
            ok += 1
    if total == 0:
        return 0.0
    return ok / total


def _detect_symbol_column(df: pd.DataFrame) -> str:
    preferred = [
        "symbol",
        "code",
        "con_code",
        "constituent_code",
        "secu_code",
        "证券代码",
        "股票代码",
        "样本代码",
        "成分券代码",
        "成分股代码",
    ]
    lowered = {str(col).strip().lower(): str(col) for col in df.columns}
    for key in preferred:
        match = lowered.get(key.lower())
        if match:
            return match

    best_col = None
    best_score = 0.0
    for col in df.columns:
        score = _looks_like_symbol_series(df[col])
        if score > best_score:
            best_score = score
            best_col = str(col)
    if best_col and best_score >= 0.8:
        return best_col
    raise RuntimeError(f"unable to detect symbol column from columns={list(df.columns)}")


def _read_snapshot_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise RuntimeError(f"unsupported snapshot file type: {path}")


def _load_snapshot_symbols(path: Path) -> list[str]:
    df = _read_snapshot_table(path)
    if df is None or df.empty:
        raise RuntimeError(f"snapshot is empty: {path}")
    col = _detect_symbol_column(df)
    symbols = sorted({_to_local_symbol(v) for v in df[col].tolist() if _to_local_symbol(v)})
    if not symbols:
        raise RuntimeError(f"no valid symbols parsed from snapshot: {path}")
    return symbols


def _read_manifest(manifest_path: Path) -> list[SnapshotSpec]:
    rows: list[SnapshotSpec] = []
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            effective_date = str(raw.get("effective_date") or "").strip()
            snapshot_rel = str(raw.get("snapshot_path") or "").strip()
            if not effective_date or not snapshot_rel:
                continue
            dt.date.fromisoformat(effective_date)
            snapshot_path = Path(snapshot_rel)
            if not snapshot_path.is_absolute():
                snapshot_path = (manifest_path.parent / snapshot_path).resolve()
            rows.append(
                SnapshotSpec(
                    effective_date=effective_date,
                    snapshot_path=snapshot_path,
                    source=str(raw.get("source") or "").strip() or DEFAULT_SOURCE,
                    event_type=str(raw.get("event_type") or "scheduled").strip().lower() or "scheduled",
                    version=str(raw.get("version") or "manual-v1").strip() or "manual-v1",
                    snapshot_trade_date=str(raw.get("snapshot_trade_date") or "").strip(),
                    rebalance_calendar_source=(
                        str(raw.get("rebalance_calendar_source") or "").strip()
                        or str(raw.get("source") or "").strip()
                        or DEFAULT_SOURCE
                    ),
                    rebalance_calendar_generated_at=str(raw.get("rebalance_calendar_generated_at") or "").strip(),
                    source_url=str(raw.get("source_url") or "").strip(),
                    source_note=str(raw.get("source_note") or "").strip(),
                )
            )
    if not rows:
        raise RuntimeError(f"no valid rows found in manifest: {manifest_path}")
    rows.sort(key=lambda r: r.effective_date)
    dates = [r.effective_date for r in rows]
    if len(dates) != len(set(dates)):
        raise RuntimeError("manifest contains duplicate effective_date rows")
    return rows


def build_snapshots_from_manifest(
    manifest_path: Path,
    *,
    expected_count: int = 1000,
    strict_count: bool = True,
) -> list[tuple[SnapshotSpec, list[str]]]:
    specs = _read_manifest(manifest_path)
    out: list[tuple[SnapshotSpec, list[str]]] = []
    for spec in specs:
        if not spec.snapshot_path.exists():
            raise FileNotFoundError(f"snapshot file not found: {spec.snapshot_path}")
        symbols = _load_snapshot_symbols(spec.snapshot_path)
        if strict_count and len(symbols) != expected_count:
            raise RuntimeError(
                f"snapshot count mismatch at {spec.effective_date}: "
                f"expected={expected_count} actual={len(symbols)} file={spec.snapshot_path}"
            )
        out.append((spec, symbols))
    return out


def reconstruct_changes(
    snapshots: list[tuple[SnapshotSpec, list[str]]],
    *,
    index_code: str = INDEX_CODE,
) -> list[dict[str, str]]:
    active: dict[str, dict[str, str]] = {}
    changes: list[dict[str, str]] = []
    for spec, symbols in snapshots:
        current = set(symbols)
        prev = set(active.keys())
        added = current - prev
        removed = prev - current
        for sym in added:
            active[sym] = {
                "in_date": spec.effective_date,
                "source": spec.source,
                "event_type": spec.event_type,
                "rebalance_calendar_version": spec.version,
                "rebalance_calendar_source": spec.rebalance_calendar_source,
                "rebalance_calendar_generated_at": spec.rebalance_calendar_generated_at,
            }
        for sym in removed:
            row_meta = active[sym]
            changes.append(
                {
                    "index_code": index_code,
                    "symbol": sym,
                    "in_date": row_meta["in_date"],
                    "out_date": spec.effective_date,
                    "source": row_meta["source"],
                    "event_type": row_meta["event_type"],
                    "rebalance_calendar_version": row_meta["rebalance_calendar_version"],
                    "rebalance_calendar_source": row_meta["rebalance_calendar_source"],
                    "rebalance_calendar_generated_at": row_meta["rebalance_calendar_generated_at"],
                }
            )
            del active[sym]
    for sym, row_meta in active.items():
        changes.append(
            {
                "index_code": index_code,
                "symbol": sym,
                "in_date": row_meta["in_date"],
                "out_date": "",
                "source": row_meta["source"],
                "event_type": row_meta["event_type"],
                "rebalance_calendar_version": row_meta["rebalance_calendar_version"],
                "rebalance_calendar_source": row_meta["rebalance_calendar_source"],
                "rebalance_calendar_generated_at": row_meta["rebalance_calendar_generated_at"],
            }
        )
    changes.sort(key=lambda row: (row["symbol"], row["in_date"]))
    return changes


def save_flat_snapshots(path: Path, snapshots: Iterable[tuple[SnapshotSpec, list[str]]]) -> int:
    rows = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "effective_date",
                "symbol",
                "source",
                "event_type",
                "rebalance_calendar_version",
                "rebalance_calendar_source",
                "rebalance_calendar_generated_at",
                "snapshot_trade_date",
                "source_url",
                "source_note",
            ]
        )
        for spec, symbols in snapshots:
            for symbol in symbols:
                writer.writerow(
                    [
                        spec.effective_date,
                        symbol,
                        spec.source,
                        spec.event_type,
                        spec.version,
                        spec.rebalance_calendar_source,
                        spec.rebalance_calendar_generated_at,
                        spec.snapshot_trade_date,
                        spec.source_url,
                        spec.source_note,
                    ]
                )
                rows += 1
    return rows


def save_changes(path: Path, changes: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "index_code",
                "symbol",
                "in_date",
                "out_date",
                "source",
                "event_type",
                "rebalance_calendar_version",
                "rebalance_calendar_source",
                "rebalance_calendar_generated_at",
            ],
        )
        writer.writeheader()
        writer.writerows(changes)


def summarize_build(
    manifest_path: Path,
    snapshots: list[tuple[SnapshotSpec, list[str]]],
    changes: list[dict[str, str]],
    *,
    expected_count: int,
    strict_count: bool,
    snapshots_csv: Path,
    changes_csv: Path,
) -> dict[str, Any]:
    effective_dates = [spec.effective_date for spec, _ in snapshots]
    provider_floor_candidates = sorted(
        {
            spec.snapshot_trade_date or spec.effective_date
            for spec, _ in snapshots
            if spec.source and "static" not in spec.source.lower()
        }
    )
    sources = sorted({spec.source for spec, _ in snapshots if spec.source})
    versions = sorted({spec.version for spec, _ in snapshots if spec.version})
    calendar_sources = sorted({spec.rebalance_calendar_source for spec, _ in snapshots if spec.rebalance_calendar_source})
    generated_values = sorted(
        {spec.rebalance_calendar_generated_at for spec, _ in snapshots if spec.rebalance_calendar_generated_at}
    )
    source_urls = [spec.source_url for spec, _ in snapshots if spec.source_url]
    return {
        "index_code": INDEX_CODE,
        "manifest_path": str(manifest_path),
        "snapshot_count": int(len(snapshots)),
        "snapshot_rows": int(sum(len(symbols) for _, symbols in snapshots)),
        "change_rows": int(len(changes)),
        "open_rows": int(sum(1 for row in changes if not row["out_date"])),
        "closed_rows": int(sum(1 for row in changes if row["out_date"])),
        "expected_count": int(expected_count),
        "strict_count": bool(strict_count),
        "first_effective_date": effective_dates[0] if effective_dates else None,
        "last_effective_date": effective_dates[-1] if effective_dates else None,
        "provider_floor_date": provider_floor_candidates[0] if provider_floor_candidates else None,
        "source": sources[0] if len(sources) == 1 else ("mixed" if sources else None),
        "source_values": sources,
        "rebalance_calendar_version": versions[0] if len(versions) == 1 else ("mixed" if versions else None),
        "rebalance_calendar_source": (
            calendar_sources[0] if len(calendar_sources) == 1 else ("mixed" if calendar_sources else None)
        ),
        "rebalance_calendar_generated_at": (
            generated_values[0] if len(generated_values) == 1 else ("mixed" if generated_values else None)
        ),
        "source_url_count": int(len(source_urls)),
        "outputs": {
            "snapshots_csv": str(snapshots_csv),
            "changes_csv": str(changes_csv),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CSI1000 PIT from manually curated official snapshots")
    parser.add_argument("--manifest", required=True, help="CSV manifest path")
    parser.add_argument("--out-dir", default="data_cache", help="output directory")
    parser.add_argument("--summary-out", default="", help="optional summary json path")
    parser.add_argument("--expected-count", type=int, default=1000, help="expected constituent count per snapshot")
    parser.add_argument(
        "--allow-count-mismatch",
        action="store_true",
        help="allow snapshots with constituent count != expected-count",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    snapshots = build_snapshots_from_manifest(
        manifest_path,
        expected_count=int(args.expected_count),
        strict_count=not bool(args.allow_count_mismatch),
    )
    changes = reconstruct_changes(snapshots)

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshots_csv = out_dir / "csi1000_pit_manual_snapshots.csv"
    changes_csv = out_dir / "csi1000_pit_manual_changes.csv"
    snap_rows = save_flat_snapshots(snapshots_csv, snapshots)
    save_changes(changes_csv, changes)
    summary_payload = summarize_build(
        manifest_path,
        snapshots,
        changes,
        expected_count=int(args.expected_count),
        strict_count=not bool(args.allow_count_mismatch),
        snapshots_csv=snapshots_csv,
        changes_csv=changes_csv,
    )
    summary_path = (
        Path(args.summary_out).resolve()
        if str(args.summary_out or "").strip()
        else out_dir / "csi1000_pit_manual_summary.json"
    )
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    active = sum(1 for row in changes if not row["out_date"])
    removed = sum(1 for row in changes if row["out_date"])
    print(
        f"manifest={manifest_path} snapshots={len(snapshots)} snapshot_rows={snap_rows} "
        f"changes={len(changes)} active={active} removed={removed}"
    )
    print(f"snapshots_csv={snapshots_csv}")
    print(f"changes_csv={changes_csv}")
    print(f"summary_json={summary_path}")


if __name__ == "__main__":
    main()
