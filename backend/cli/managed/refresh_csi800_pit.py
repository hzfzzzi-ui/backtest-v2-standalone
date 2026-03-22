from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from backend.scripts.import_csi800_pit import _get_db_conn, _load_existing_rows, summarize_rows


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR = REPO_ROOT / "data_cache"
DEFAULT_OPS_DIR = REPO_ROOT / "outputs" / "ops"
DEFAULT_REQUIRED_START = "2007-01-01"
AUTO_SEED_FILENAME = "csi800_formal_history_seed_auto.csv"
AUTO_SEED_SUMMARY_FILENAME = "csi800_auto_seed_summary.json"


def build_fetch_command(*, out_dir: Path, summary_out: Path) -> list[str]:
    return [
        sys.executable,
        str(REPO_ROOT / "backend" / "scripts" / "fetch_csi800_pit_history.py"),
        "--out-dir",
        str(out_dir),
        "--summary-out",
        str(summary_out),
    ]


def build_materialize_command(
    *,
    seed_csv: Path,
    patch_csv: Path,
    out_dir: Path,
    summary_out: Path,
    required_start: str,
    required_end: str,
) -> list[str]:
    return [
        sys.executable,
        str(REPO_ROOT / "backend" / "scripts" / "build_csi800_formal_history.py"),
        "--seed-csv",
        str(seed_csv),
        "--patch-csv",
        str(patch_csv),
        "--out-csv",
        str(out_dir / "csi800_formal_history_changes.csv"),
        "--summary-out",
        str(summary_out),
        "--required-start",
        str(required_start),
        "--required-end",
        str(required_end),
    ]


def build_import_command(*, changes_csv: Path, summary_out: Path) -> list[str]:
    return [
        sys.executable,
        str(REPO_ROOT / "backend" / "scripts" / "import_csi800_pit.py"),
        "--from-csv",
        str(changes_csv),
        "--replace-existing",
        "--summary-out",
        str(summary_out),
    ]


def _run_command(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=str(REPO_ROOT), env=os.environ.copy())


def _load_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fetch_covers_required_start(summary: dict[str, Any], required_start: str) -> bool:
    first_usable = str(summary.get("first_usable_trade_date") or "").strip()
    return bool(first_usable) and first_usable <= str(required_start)


def _rows_cover_date(rows: list[Any], target_date: str) -> bool:
    date_text = str(target_date or "").strip()
    if not date_text:
        return False
    for row in rows:
        if row.start_date <= date_text and (row.end_date is None or row.end_date > date_text):
            return True
    return False


def _write_seed_csv(path: Path, rows: list[Any]) -> None:
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


def _bootstrap_seed_csv_from_existing_db(
    *,
    out_dir: Path,
    ops_dir: Path,
    required_start: str,
) -> tuple[Path | None, dict[str, Any]]:
    summary_path = ops_dir / AUTO_SEED_SUMMARY_FILENAME
    with _get_db_conn() as conn:
        existing_rows = _load_existing_rows(conn)
    existing_summary = summarize_rows(existing_rows)
    covers_required_start = _rows_cover_date(existing_rows, required_start)
    payload: dict[str, Any] = {
        "status": "unavailable",
        "source": "db_existing_rows",
        "required_start": required_start,
        "covers_required_start": covers_required_start,
        "seed_csv": None,
        "existing_summary": existing_summary,
    }
    if not existing_rows or not covers_required_start:
        _write_refresh_summary(summary_path, payload)
        return None, payload

    seed_csv = out_dir / AUTO_SEED_FILENAME
    _write_seed_csv(seed_csv, existing_rows)
    payload.update({"status": "ok", "seed_csv": str(seed_csv)})
    _write_refresh_summary(summary_path, payload)
    return seed_csv, payload


def _write_refresh_summary(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_refresh(
    *,
    out_dir: Path,
    ops_dir: Path,
    skip_import: bool = False,
    seed_csv: Path | None = None,
    required_start: str = DEFAULT_REQUIRED_START,
    required_end: str | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ops_dir.mkdir(parents=True, exist_ok=True)

    required_end_value = str(required_end or dt.date.today().isoformat())
    history_changes_csv = out_dir / "csi800_pit_history_changes.csv"
    changes_csv = history_changes_csv
    fetch_summary = ops_dir / "csi800_pit_fetch_summary.json"
    materialize_summary = ops_dir / "csi800_pit_materialize_summary.json"
    import_summary = ops_dir / "csi800_pit_import_summary.json"
    refresh_summary = ops_dir / "csi800_pit_refresh_summary.json"
    auto_seed_summary = ops_dir / AUTO_SEED_SUMMARY_FILENAME
    fetch_cmd = build_fetch_command(out_dir=out_dir, summary_out=fetch_summary)
    materialize_cmd: list[str] | None = None
    import_cmd: list[str] | None = None
    effective_seed_csv = seed_csv
    seed_mode = "explicit" if seed_csv is not None else None
    auto_seed_payload: dict[str, Any] | None = None

    _run_command(fetch_cmd)
    fetch_payload = _load_summary(fetch_summary)

    if not skip_import:
        if effective_seed_csv is None and not _fetch_covers_required_start(fetch_payload, required_start):
            effective_seed_csv, auto_seed_payload = _bootstrap_seed_csv_from_existing_db(
                out_dir=out_dir,
                ops_dir=ops_dir,
                required_start=required_start,
            )
            if effective_seed_csv is not None:
                seed_mode = "auto_db_export"
        if effective_seed_csv is not None:
            materialize_cmd = build_materialize_command(
                seed_csv=effective_seed_csv,
                patch_csv=history_changes_csv,
                out_dir=out_dir,
                summary_out=materialize_summary,
                required_start=required_start,
                required_end=required_end_value,
            )
            _run_command(materialize_cmd)
            materialize_payload = _load_summary(materialize_summary)
            if materialize_payload.get("covers_required_start") is False:
                payload = {
                    "status": "blocked",
                    "reason": "formal_chain_missing_required_start",
                    "required_start": required_start,
                    "seed_csv": str(effective_seed_csv),
                    "seed_mode": seed_mode,
                    "commands": {
                        "fetch": fetch_cmd,
                        "materialize": materialize_cmd,
                        "import": None,
                    },
                    "outputs": {
                        "changes_csv": str(history_changes_csv),
                        "formal_changes_csv": str(out_dir / "csi800_formal_history_changes.csv"),
                        "fetch_summary": str(fetch_summary),
                        "auto_seed_summary": str(auto_seed_summary) if auto_seed_payload is not None else None,
                        "materialize_summary": str(materialize_summary),
                        "import_summary": None,
                        "refresh_summary": str(refresh_summary),
                    },
                }
                _write_refresh_summary(refresh_summary, payload)
                raise RuntimeError(f"formal CSI800 history still missing required_start={required_start}")
            changes_csv = out_dir / "csi800_formal_history_changes.csv"
        elif not _fetch_covers_required_start(fetch_payload, required_start):
            payload = {
                "status": "blocked",
                "reason": "fetch_missing_required_start",
                "required_start": required_start,
                "suggestion": "provide --seed-csv with a trusted long-history chain before replace import",
                "commands": {
                    "fetch": fetch_cmd,
                    "materialize": None,
                    "import": None,
                },
                "outputs": {
                    "changes_csv": str(history_changes_csv),
                    "formal_changes_csv": None,
                    "fetch_summary": str(fetch_summary),
                    "auto_seed_summary": str(auto_seed_summary) if auto_seed_summary.exists() else None,
                    "materialize_summary": None,
                    "import_summary": None,
                    "refresh_summary": str(refresh_summary),
                },
            }
            _write_refresh_summary(refresh_summary, payload)
            raise RuntimeError(
                f"formal CSI800 fetch cannot cover required_start={required_start}; "
                "provide --seed-csv before replace import"
            )

        import_cmd = build_import_command(changes_csv=changes_csv, summary_out=import_summary)
        _run_command(import_cmd)

    payload = {
        "status": "ok",
        "skip_import": bool(skip_import),
        "required_start": required_start,
        "required_end": required_end_value,
        "seed_csv": None if effective_seed_csv is None else str(effective_seed_csv),
        "seed_mode": seed_mode,
        "auto_seed": auto_seed_payload,
        "commands": {
            "fetch": fetch_cmd,
            "materialize": materialize_cmd,
            "import": import_cmd,
        },
        "outputs": {
            "changes_csv": str(changes_csv),
            "history_changes_csv": str(history_changes_csv),
            "fetch_summary": str(fetch_summary),
            "auto_seed_summary": str(auto_seed_summary) if auto_seed_payload is not None else None,
            "materialize_summary": None if materialize_cmd is None else str(materialize_summary),
            "import_summary": None if skip_import else str(import_summary),
            "refresh_summary": str(refresh_summary),
        },
    }
    _write_refresh_summary(refresh_summary, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh CSI800/000906 PIT by running fetch and import in one command")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="directory for generated CSV files")
    parser.add_argument("--ops-dir", default=str(DEFAULT_OPS_DIR), help="directory for structured summaries")
    parser.add_argument("--skip-import", action="store_true", help="only run fetch stage without DB import")
    parser.add_argument("--seed-csv", default="", help="trusted long-history seed CSV used to materialize formal history")
    parser.add_argument("--required-start", default=DEFAULT_REQUIRED_START, help="required earliest coverage for formal import")
    parser.add_argument("--required-end", default=dt.date.today().isoformat(), help="required latest coverage for formal import")
    args = parser.parse_args()

    summary = run_refresh(
        out_dir=Path(args.out_dir).resolve(),
        ops_dir=Path(args.ops_dir).resolve(),
        skip_import=bool(args.skip_import),
        seed_csv=(Path(args.seed_csv).resolve() if str(args.seed_csv or "").strip() else None),
        required_start=str(args.required_start),
        required_end=str(args.required_end),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
