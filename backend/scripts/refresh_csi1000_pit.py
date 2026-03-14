from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CALENDAR_PATH = REPO_ROOT / "data_cache" / "csi1000_rebalance_calendar.csv"
DEFAULT_MANUAL_MANIFEST = REPO_ROOT / "data_cache" / "csi1000_manual" / "manifest.csv"
DEFAULT_OUT_DIR = REPO_ROOT / "data_cache"
DEFAULT_OPS_DIR = REPO_ROOT / "outputs" / "ops"


def _load_env_file() -> dict[str, str]:
    env_path = REPO_ROOT / ".env"
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


def _resolve_tushare_token(explicit: str | None = None) -> str:
    file_env = _load_env_file()
    return str(explicit or os.environ.get("TUSHARE_TOKEN") or file_env.get("TUSHARE_TOKEN") or "").strip()


def build_fetch_command(
    *,
    calendar: Path,
    provider: str,
    out_dir: Path,
    summary_out: Path,
    expected_count: int,
    lookahead_days: int,
    allow_count_mismatch: bool,
    allow_static_fallback: bool,
) -> list[str]:
    cmd = [
        sys.executable,
        str(REPO_ROOT / "backend" / "scripts" / "fetch_csi1000_pit_by_calendar.py"),
        "--calendar",
        str(calendar),
        "--provider",
        str(provider),
        "--out-dir",
        str(out_dir),
        "--summary-out",
        str(summary_out),
        "--expected-count",
        str(int(expected_count)),
        "--lookahead-days",
        str(int(lookahead_days)),
    ]
    if allow_count_mismatch:
        cmd.append("--allow-count-mismatch")
    if allow_static_fallback:
        cmd.append("--allow-static-fallback")
    return cmd


def build_manual_command(
    *,
    manifest: Path,
    out_dir: Path,
    summary_out: Path,
    expected_count: int,
    allow_count_mismatch: bool,
) -> list[str]:
    cmd = [
        sys.executable,
        str(REPO_ROOT / "backend" / "scripts" / "build_csi1000_pit_from_manual_snapshots.py"),
        "--manifest",
        str(manifest),
        "--out-dir",
        str(out_dir),
        "--summary-out",
        str(summary_out),
        "--expected-count",
        str(int(expected_count)),
    ]
    if allow_count_mismatch:
        cmd.append("--allow-count-mismatch")
    return cmd


def build_import_command(
    *,
    changes_csv: Path,
    summary_out: Path,
    source_label: str = "",
) -> list[str]:
    cmd = [
        sys.executable,
        str(REPO_ROOT / "backend" / "scripts" / "import_csi1000_pit.py"),
        "--from-csv",
        str(changes_csv),
        "--summary-out",
        str(summary_out),
    ]
    if str(source_label or "").strip():
        cmd.extend(["--source-label", str(source_label).strip()])
    return cmd


def _run_command(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=str(REPO_ROOT), env=os.environ.copy())


def _run_command_with_env(cmd: list[str], extra_env: dict[str, str] | None = None) -> None:
    env = os.environ.copy()
    if extra_env:
        env.update({key: value for key, value in extra_env.items() if value is not None})
    subprocess.run(cmd, check=True, cwd=str(REPO_ROOT), env=env)


def run_refresh(
    *,
    calendar: Path,
    provider: str,
    out_dir: Path,
    ops_dir: Path,
    expected_count: int,
    lookahead_days: int,
    allow_count_mismatch: bool,
    allow_static_fallback: bool,
    manual_manifest: Path | None = None,
    source_label: str = "",
    skip_import: bool = False,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ops_dir.mkdir(parents=True, exist_ok=True)
    token = _resolve_tushare_token()
    resolved_provider = str(provider)
    if resolved_provider == "auto":
        resolved_provider = "tushare" if token else "akshare_static"

    fetch_summary = ops_dir / "csi1000_pit_fetch_summary.json"
    manual_summary = ops_dir / "csi1000_pit_manual_build_summary.json"
    import_summary = ops_dir / "csi1000_pit_import_summary.json"
    combined_summary = ops_dir / "csi1000_pit_refresh_summary.json"
    changes_csv = out_dir / "csi1000_pit_calendar_changes.csv"

    fetch_cmd: list[str] | None = None
    manual_cmd: list[str] | None = None
    if resolved_provider == "manual_manifest":
        manifest_path = Path(manual_manifest or DEFAULT_MANUAL_MANIFEST).resolve()
        changes_csv = out_dir / "csi1000_pit_manual_changes.csv"
        manual_cmd = build_manual_command(
            manifest=manifest_path,
            out_dir=out_dir,
            summary_out=manual_summary,
            expected_count=expected_count,
            allow_count_mismatch=allow_count_mismatch,
        )
        _run_command(manual_cmd)
    else:
        fetch_cmd = build_fetch_command(
            calendar=calendar,
            provider=resolved_provider,
            out_dir=out_dir,
            summary_out=fetch_summary,
            expected_count=expected_count,
            lookahead_days=lookahead_days,
            allow_count_mismatch=allow_count_mismatch,
            allow_static_fallback=allow_static_fallback,
        )
        _run_command_with_env(fetch_cmd, {"TUSHARE_TOKEN": token} if token else None)

    import_cmd: list[str] | None = None
    if not skip_import:
        import_cmd = build_import_command(
            changes_csv=changes_csv,
            summary_out=import_summary,
            source_label=source_label,
        )
        _run_command(import_cmd)

    payload = {
        "calendar": str(calendar),
        "provider": resolved_provider,
        "token_available": bool(token),
        "allow_static_fallback": bool(allow_static_fallback),
        "allow_count_mismatch": bool(allow_count_mismatch),
        "manual_manifest": str(Path(manual_manifest).resolve()) if manual_manifest else None,
        "skip_import": bool(skip_import),
        "commands": {
            "fetch": fetch_cmd,
            "manual_build": manual_cmd,
            "import": import_cmd,
        },
        "outputs": {
            "changes_csv": str(changes_csv),
            "fetch_summary": str(fetch_summary) if fetch_cmd is not None else None,
            "manual_build_summary": str(manual_summary) if manual_cmd is not None else None,
            "import_summary": str(import_summary) if not skip_import else None,
        },
    }
    combined_summary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["outputs"]["refresh_summary"] = str(combined_summary)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh CSI1000 PIT by running fetch and import in one command")
    parser.add_argument("--calendar", default=str(DEFAULT_CALENDAR_PATH), help="rebalance calendar csv path")
    parser.add_argument(
        "--provider",
        choices=["auto", "tushare", "akshare_static", "manual_manifest"],
        default="auto",
    )
    parser.add_argument(
        "--manual-manifest",
        default=str(DEFAULT_MANUAL_MANIFEST),
        help="manual official snapshot manifest path; used when provider=manual_manifest",
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="directory for generated CSV files")
    parser.add_argument("--ops-dir", default=str(DEFAULT_OPS_DIR), help="directory for structured summaries")
    parser.add_argument("--expected-count", type=int, default=1000, help="expected constituent count per snapshot")
    parser.add_argument("--lookahead-days", type=int, default=10, help="days to look ahead for tushare trade_date")
    parser.add_argument("--allow-count-mismatch", action="store_true", help="allow snapshot count mismatches")
    parser.add_argument(
        "--allow-static-fallback",
        action="store_true",
        help="allow low-fidelity akshare static fallback during refresh",
    )
    parser.add_argument("--source-label", default="", help="override source label during import")
    parser.add_argument("--skip-import", action="store_true", help="only run fetch stage without DB import")
    args = parser.parse_args()

    summary = run_refresh(
        calendar=Path(args.calendar).resolve(),
        provider=str(args.provider),
        out_dir=Path(args.out_dir).resolve(),
        ops_dir=Path(args.ops_dir).resolve(),
        expected_count=int(args.expected_count),
        lookahead_days=int(args.lookahead_days),
        allow_count_mismatch=bool(args.allow_count_mismatch),
        allow_static_fallback=bool(args.allow_static_fallback),
        manual_manifest=Path(args.manual_manifest).resolve() if str(args.manual_manifest or "").strip() else None,
        source_label=str(args.source_label or ""),
        skip_import=bool(args.skip_import),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
