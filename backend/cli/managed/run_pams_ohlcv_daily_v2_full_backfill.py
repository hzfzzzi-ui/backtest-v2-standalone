from __future__ import annotations

import argparse
import json
import traceback
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from . import audit_pams_ohlcv_daily_v2 as audit_build
from . import cn_side_table_common as common
from . import pams_ohlcv_daily_v2_common as v2_common
from . import refresh_security_master
from . import update_pams_ohlcv_daily_v2 as main_build
from . import update_pams_ohlcv_daily_v2_raw as raw_build
from . import update_pit_stock_moneyflow_v2 as moneyflow_build


@dataclass(frozen=True, slots=True)
class BackfillStep:
    name: str
    start: date | None
    end: date | None
    runner: Callable[[argparse.Namespace], dict[str, Any]]
    args_builder: Callable[..., argparse.Namespace] | None


DEFAULT_SEGMENTS = [
    (date(2007, 1, 4), date(2012, 12, 31)),
    (date(2013, 1, 1), date(2018, 12, 31)),
    (date(2019, 1, 1), v2_common.OFFICIAL_END_DATE),
]


def _clip_segments(start: date, end: date) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    for seg_start, seg_end in DEFAULT_SEGMENTS:
        clipped_start = max(start, seg_start)
        clipped_end = min(end, seg_end)
        if clipped_start <= clipped_end:
            out.append((clipped_start, clipped_end))
    return out


def _build_steps(start: date, end: date) -> list[BackfillStep]:
    steps: list[BackfillStep] = [
        BackfillStep(
            name="security_master",
            start=None,
            end=None,
            runner=refresh_security_master.run_refresh,
            args_builder=None,
        )
    ]
    for seg_start, seg_end in _clip_segments(start, end):
        label = f"{seg_start.year}_{seg_end.year}"
        steps.append(
            BackfillStep(
                name=f"raw_{label}",
                start=seg_start,
                end=seg_end,
                runner=raw_build.run_update,
                args_builder=raw_build.build_update_args,
            )
        )
    for seg_start, seg_end in _clip_segments(start, end):
        label = f"{seg_start.year}_{seg_end.year}"
        steps.append(
            BackfillStep(
                name=f"main_{label}",
                start=seg_start,
                end=seg_end,
                runner=main_build.run_update,
                args_builder=main_build.build_update_args,
            )
        )
    for seg_start, seg_end in _clip_segments(start, end):
        label = f"{seg_start.year}_{seg_end.year}"
        steps.append(
            BackfillStep(
                name=f"moneyflow_{label}",
                start=seg_start,
                end=seg_end,
                runner=moneyflow_build.run_update,
                args_builder=moneyflow_build.build_update_args,
            )
        )
    steps.append(
        BackfillStep(
            name="audit_full_window",
            start=start,
            end=end,
            runner=audit_build.run_update,
            args_builder=audit_build.build_update_args,
        )
    )
    return steps


def _status_payload(
    *,
    run_id: str,
    output_dir: Path,
    start: date,
    end: date,
    apply: bool,
    symbols_csv: str,
    steps: list[dict[str, Any]],
    status: str,
    current_step: str,
    started_at: str,
    finished_at: str | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "run_id": run_id,
        "apply": bool(apply),
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "symbols_csv": str(symbols_csv or ""),
        "output_dir": str(output_dir),
        "current_step": current_step,
        "heartbeat_path": str(output_dir / "heartbeat.json"),
        "started_at": started_at,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "steps": steps,
    }
    if finished_at:
        payload["finished_at"] = finished_at
    if error:
        payload["error"] = error
    return payload


def _write_status(path: Path, payload: dict[str, Any]) -> None:
    v2_common.write_json_atomic(path, payload)


def _step_status_rows(steps: list[BackfillStep], output_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in steps:
        rows.append(
            {
                "name": step.name,
                "start": None if step.start is None else step.start.isoformat(),
                "end": None if step.end is None else step.end.isoformat(),
                "status": "pending",
                "summary_json": str(output_dir / step.name / "summary.json"),
            }
        )
    return rows


def build_update_args(
    *,
    start: str = "",
    end: str = "",
    symbols_csv: str = "",
    output_dir: str = "",
    resume_from_step: str = "",
    resume_trade_date: str = "",
    apply: bool = True,
) -> argparse.Namespace:
    return argparse.Namespace(
        start=str(start or ""),
        end=str(end or ""),
        symbols_csv=str(symbols_csv or ""),
        output_dir=str(output_dir or ""),
        resume_from_step=str(resume_from_step or ""),
        resume_trade_date=str(resume_trade_date or ""),
        apply=bool(apply),
    )


def run_update(args: argparse.Namespace) -> dict[str, Any]:
    start = date.fromisoformat(str(args.start).strip()) if str(args.start or "").strip() else v2_common.DEFAULT_BACKFILL_START
    end = date.fromisoformat(str(args.end).strip()) if str(args.end or "").strip() else v2_common.OFFICIAL_END_DATE
    if start > end:
        raise ValueError("start must be <= end")
    resume_from_step = str(getattr(args, "resume_from_step", "") or "").strip()
    resume_trade_date_text = str(getattr(args, "resume_trade_date", "") or "").strip()
    resume_trade_date = date.fromisoformat(resume_trade_date_text) if resume_trade_date_text else None

    ts_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (v2_common.DEFAULT_OUTPUT_ROOT / f"pams_ohlcv_daily_v2_full_backfill_{ts_label}")
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "status.json"
    failure_path = output_dir / "failure.json"
    current_step_path = output_dir / "current_step.txt"
    heartbeat_path = output_dir / "heartbeat.json"
    run_id = v2_common.build_run_id("v2_full_backfill")
    started_at = datetime.now().isoformat(timespec="seconds")
    steps = _build_steps(start, end)
    if resume_from_step and resume_from_step not in {step.name for step in steps}:
        raise ValueError(f"resume_from_step not found in current plan: {resume_from_step}")
    step_rows = _step_status_rows(steps, output_dir)

    _write_status(
        status_path,
        _status_payload(
            run_id=run_id,
            output_dir=output_dir,
            start=start,
            end=end,
            apply=bool(args.apply),
            symbols_csv=str(args.symbols_csv or ""),
            steps=step_rows,
            status="running",
            current_step="pending",
            started_at=started_at,
        ),
    )
    v2_common.touch_heartbeat(
        heartbeat_path,
        step="bootstrap",
        status="running",
        extra={"run_id": run_id, "phase": "bootstrap"},
    )

    try:
        resume_reached = not bool(resume_from_step)
        for row, step in zip(step_rows, steps, strict=True):
            if not resume_reached:
                if step.name != resume_from_step:
                    row["status"] = "skipped"
                    row["skip_reason"] = "resumed_after_previous_run"
                    continue
                resume_reached = True
            row["status"] = "running"
            v2_common.write_text_atomic(current_step_path, step.name)
            _write_status(
                status_path,
                _status_payload(
                    run_id=run_id,
                    output_dir=output_dir,
                    start=start,
                    end=end,
                    apply=bool(args.apply),
                    symbols_csv=str(args.symbols_csv or ""),
                    steps=step_rows,
                    status="running",
                    current_step=step.name,
                    started_at=started_at,
                ),
            )
            v2_common.touch_heartbeat(
                heartbeat_path,
                step=step.name,
                status="running",
                extra={"run_id": run_id, "phase": "step_started"},
            )

            step_output_dir = output_dir / step.name
            step_output_dir.mkdir(parents=True, exist_ok=True)
            effective_step_start = step.start
            if (
                resume_trade_date is not None
                and step.name == resume_from_step
                and step.start is not None
                and step.end is not None
            ):
                if resume_trade_date > step.end:
                    raise ValueError(
                        f"resume_trade_date {resume_trade_date.isoformat()} exceeds step end {step.end.isoformat()} for {step.name}"
                    )
                effective_step_start = max(step.start, resume_trade_date)
            if step.args_builder is None:
                step_args = argparse.Namespace(
                    token="",
                    batch_size=2000,
                    output_dir=str(step_output_dir),
                    apply=bool(args.apply),
                )
            else:
                step_args = step.args_builder(
                    start="" if effective_step_start is None else effective_step_start.isoformat(),
                    end="" if step.end is None else step.end.isoformat(),
                    symbols_csv=str(args.symbols_csv or ""),
                    output_dir=str(step_output_dir),
                    heartbeat_path=str(heartbeat_path),
                    heartbeat_label=step.name,
                    apply=bool(args.apply),
                )
            if effective_step_start is not None and step.start is not None and effective_step_start != step.start:
                row["effective_start"] = effective_step_start.isoformat()
            step_summary = step.runner(step_args)
            step_summary_path = step_output_dir / "summary.json"
            common.write_json(step_summary_path, step_summary)
            row["status"] = str(step_summary.get("status") or "completed")
            row["finished_at"] = datetime.now().isoformat(timespec="seconds")
            v2_common.touch_heartbeat(
                heartbeat_path,
                step=step.name,
                status=row["status"],
                extra={"run_id": run_id, "phase": "step_completed"},
            )

        v2_common.write_text_atomic(current_step_path, "completed")
        final_summary = _status_payload(
            run_id=run_id,
            output_dir=output_dir,
            start=start,
            end=end,
            apply=bool(args.apply),
            symbols_csv=str(args.symbols_csv or ""),
            steps=step_rows,
            status="completed" if bool(args.apply) else "dry_run",
            current_step="completed",
            started_at=started_at,
            finished_at=datetime.now().isoformat(timespec="seconds"),
        )
        _write_status(status_path, final_summary)
        return final_summary
    except Exception as exc:
        error_payload = {
            "type": exc.__class__.__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        failure = _status_payload(
            run_id=run_id,
            output_dir=output_dir,
            start=start,
            end=end,
            apply=bool(args.apply),
            symbols_csv=str(args.symbols_csv or ""),
            steps=step_rows,
            status="failed",
            current_step=current_step_path.read_text(encoding="utf-8").strip() if current_step_path.exists() else "unknown",
            started_at=started_at,
            finished_at=datetime.now().isoformat(timespec="seconds"),
            error=error_payload,
        )
        _write_status(status_path, failure)
        v2_common.write_json_atomic(failure_path, failure)
        v2_common.touch_heartbeat(
            heartbeat_path,
            step=failure["current_step"],
            status="failed",
            extra={"run_id": run_id, "phase": "failed"},
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full pams_ohlcv_daily_v2 historical backfill workflow")
    parser.add_argument("--start", default="", help="inclusive start date YYYY-MM-DD; default 2007-01-04")
    parser.add_argument("--end", default="", help="inclusive end date YYYY-MM-DD; default 2026-03-16")
    parser.add_argument("--symbols-csv", default="", help="optional comma-separated symbols for smoke runs")
    parser.add_argument("--output-dir", default="", help="output directory for runner status and per-step summaries")
    parser.add_argument("--resume-from-step", default="", help="resume from a named step, skipping earlier completed steps")
    parser.add_argument("--resume-trade-date", default="", help="optional resume trade date applied only to the resumed step start")
    parser.add_argument("--apply", action="store_true", help="commit DB writes; default is dry-run rollback")
    args = parser.parse_args()

    summary = run_update(args)
    summary_path = Path(summary["output_dir"]) / "summary.json"
    common.write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_json={summary_path}")


if __name__ == "__main__":
    main()
