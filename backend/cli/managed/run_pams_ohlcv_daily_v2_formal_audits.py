from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from . import audit_pams_ohlcv_daily_v2 as audit_build
from . import cn_side_table_common as common
from . import pams_ohlcv_daily_v2_common as v2_common


def build_update_args(
    *,
    output_dir: str = "",
    symbols_csv: str = "",
    heartbeat_path: str = "",
    heartbeat_label: str = "",
    apply: bool = True,
) -> argparse.Namespace:
    return argparse.Namespace(
        output_dir=str(output_dir or ""),
        symbols_csv=str(symbols_csv or ""),
        heartbeat_path=str(heartbeat_path or ""),
        heartbeat_label=str(heartbeat_label or ""),
        apply=bool(apply),
    )


def _window_payload(
    *,
    window: v2_common.FormalAuditWindow,
    output_dir: Path,
    summary: dict[str, Any],
) -> dict[str, Any]:
    gate = dict(summary.get("gate") or {})
    canonical = dict(gate.get("canonical") or {})
    runtime = dict(gate.get("runtime") or {})
    return {
        "key": window.key,
        "label": window.label,
        "start": window.start_date.isoformat(),
        "end": window.end_date.isoformat(),
        "status": str(summary.get("status") or "unknown"),
        "summary_json": str(output_dir / "summary.json"),
        "eligible_no_source_rows": int(canonical.get("eligible_no_source_rows") or 0),
        "hard_field_null_rows": int(canonical.get("hard_field_null_rows") or 0),
        "critical_exception_rows": int(canonical.get("critical_exception_rows") or 0),
        "runtime_eligible_rows": int(runtime.get("runtime_eligible_rows") or 0),
        "can_promote_shadow": bool(canonical.get("can_promote_shadow")),
        "can_consume_v10_1": bool(runtime.get("can_consume_v10_1")),
    }


def run_update(args: argparse.Namespace) -> dict[str, Any]:
    ts_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir or "").strip() else (
        v2_common.DEFAULT_OUTPUT_ROOT / f"pams_ohlcv_daily_v2_formal_audits_{ts_label}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    heartbeat_path = Path(str(args.heartbeat_path or "").strip()) if str(args.heartbeat_path or "").strip() else None
    heartbeat_label = str(args.heartbeat_label or "").strip() or "formal_audits"
    run_id = v2_common.build_run_id("v2_formal_audits")
    started_at = datetime.now().isoformat(timespec="seconds")
    window_rows: list[dict[str, Any]] = []

    for window in v2_common.FORMAL_AUDIT_WINDOWS:
        window_output_dir = output_dir / f"audit_{window.key}"
        window_output_dir.mkdir(parents=True, exist_ok=True)
        if heartbeat_path is not None:
            v2_common.touch_heartbeat(
                heartbeat_path,
                step=heartbeat_label,
                status="running",
                extra={
                    "run_id": run_id,
                    "phase": "window_started",
                    "window_key": window.key,
                },
            )
        summary = audit_build.run_update(
            audit_build.build_update_args(
                start=window.start_date.isoformat(),
                end=window.end_date.isoformat(),
                symbols_csv=str(args.symbols_csv or ""),
                output_dir=str(window_output_dir),
                heartbeat_path="" if heartbeat_path is None else str(heartbeat_path),
                heartbeat_label=f"{heartbeat_label}:{window.key}",
                apply=bool(args.apply),
            )
        )
        window_rows.append(
            _window_payload(
                window=window,
                output_dir=window_output_dir,
                summary=summary,
            )
        )

    final_status = "completed" if bool(args.apply) else "dry_run"
    summary = {
        "status": final_status,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "output_dir": str(output_dir),
        "symbols_csv": str(args.symbols_csv or ""),
        "required_windows": list(v2_common.FORMAL_AUDIT_REQUIRED_WINDOW_KEYS),
        "advisory_windows": list(v2_common.FORMAL_AUDIT_ADVISORY_WINDOW_KEYS),
        "formal_windows_complete": all(
            any(item["key"] == key for item in window_rows)
            for key in v2_common.FORMAL_AUDIT_REQUIRED_WINDOW_KEYS
        ),
        "all_windows_complete": len(window_rows) == len(v2_common.FORMAL_AUDIT_WINDOWS),
        "windows": window_rows,
    }
    summary_path = output_dir / "summary.json"
    common.write_json(summary_path, summary)
    if heartbeat_path is not None:
        v2_common.touch_heartbeat(
            heartbeat_path,
            step=heartbeat_label,
            status=final_status,
            extra={"run_id": run_id, "phase": "completed"},
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the three formal pams_ohlcv_daily_v2 audit windows")
    parser.add_argument("--output-dir", default="", help="output directory for consolidated formal audit artifacts")
    parser.add_argument("--symbols-csv", default="", help="optional comma-separated symbols for smoke runs")
    parser.add_argument("--heartbeat-path", default="", help="optional heartbeat JSON path updated during execution")
    parser.add_argument("--heartbeat-label", default="", help="optional logical step name written to heartbeat JSON")
    parser.add_argument("--apply", action="store_true", help="commit DB writes; default is dry-run rollback")
    args = parser.parse_args()

    summary = run_update(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_json={Path(summary['output_dir']) / 'summary.json'}")


if __name__ == "__main__":
    main()
