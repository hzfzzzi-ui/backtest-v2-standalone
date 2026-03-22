from __future__ import annotations

import json
from argparse import Namespace
from datetime import date
from pathlib import Path

import pytest

from backend.cli.managed import run_pams_ohlcv_daily_v2_full_backfill as full_backfill


def test_full_backfill_builds_expected_default_steps() -> None:
    steps = full_backfill._build_steps(date(2007, 1, 4), date(2026, 3, 20))
    assert [step.name for step in steps] == [
        "security_master",
        "raw_2007_2012",
        "raw_2013_2018",
        "raw_2019_2026",
        "main_2007_2012",
        "main_2013_2018",
        "main_2019_2026",
        "moneyflow_2007_2012",
        "moneyflow_2013_2018",
        "moneyflow_2019_2026",
        "audit_full_window",
        "audit_formal_windows",
    ]


def test_full_backfill_skips_formal_audits_for_symbol_smoke() -> None:
    steps = full_backfill._build_steps(
        date(2007, 1, 4),
        date(2026, 3, 20),
        symbols_csv="sh600000,sz000001",
    )
    assert [step.name for step in steps] == [
        "security_master",
        "raw_2007_2012",
        "raw_2013_2018",
        "raw_2019_2026",
        "main_2007_2012",
        "main_2013_2018",
        "main_2019_2026",
        "moneyflow_2007_2012",
        "moneyflow_2013_2018",
        "moneyflow_2019_2026",
        "audit_full_window",
    ]


def test_full_backfill_defaults_to_official_window_end(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, date] = {}

    def _ok_runner(_args: Namespace) -> dict[str, str]:
        return {"status": "ok"}

    def _build_steps(start: date, end: date, *, symbols_csv: str = "") -> list[full_backfill.BackfillStep]:
        captured["start"] = start
        captured["end"] = end
        captured["symbols_csv"] = symbols_csv
        return [full_backfill.BackfillStep("security_master", None, None, _ok_runner, None)]

    monkeypatch.setattr(full_backfill, "_build_steps", _build_steps)

    summary = full_backfill.run_update(
        full_backfill.build_update_args(
            output_dir=str(tmp_path),
            apply=False,
        )
    )

    assert summary["status"] == "dry_run"
    assert captured == {
        "start": full_backfill.v2_common.DEFAULT_BACKFILL_START,
        "end": full_backfill.v2_common.OFFICIAL_END_DATE,
        "symbols_csv": "",
    }


def test_full_backfill_runner_writes_failure_status_on_step_error(monkeypatch, tmp_path: Path) -> None:
    def _ok_runner(_args: Namespace) -> dict[str, str]:
        return {"status": "ok"}

    def _boom_runner(_args: Namespace) -> dict[str, str]:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        full_backfill,
        "_build_steps",
        lambda _start, _end, symbols_csv="": [
            full_backfill.BackfillStep("step_ok", None, None, _ok_runner, None),
            full_backfill.BackfillStep("step_boom", None, None, _boom_runner, None),
        ],
    )

    args = full_backfill.build_update_args(
        start="2007-01-04",
        end="2007-01-31",
        output_dir=str(tmp_path),
        apply=False,
    )

    with pytest.raises(RuntimeError, match="boom"):
        full_backfill.run_update(args)

    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    failure = json.loads((tmp_path / "failure.json").read_text(encoding="utf-8"))
    heartbeat = json.loads((tmp_path / "heartbeat.json").read_text(encoding="utf-8"))

    assert status["status"] == "failed"
    assert status["current_step"] == "step_boom"
    assert failure["error"]["message"] == "boom"
    assert heartbeat["status"] == "failed"
    assert heartbeat["step"] == "step_boom"


def test_full_backfill_runner_can_resume_from_raw_step(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str | None, str | None]] = []

    def _runner(_args: Namespace) -> dict[str, str]:
        calls.append(
            (
                str(getattr(_args, "heartbeat_label", "")),
                str(getattr(_args, "start", "")) or None,
                str(getattr(_args, "end", "")) or None,
            )
        )
        return {"status": "ok"}

    def _builder(**kwargs) -> Namespace:
        return Namespace(**kwargs)

    monkeypatch.setattr(
        full_backfill,
        "_build_steps",
        lambda _start, _end, symbols_csv="": [
            full_backfill.BackfillStep("security_master", None, None, _runner, None),
            full_backfill.BackfillStep("raw_2007_2012", date(2007, 1, 4), date(2012, 12, 31), _runner, _builder),
            full_backfill.BackfillStep("main_2007_2012", date(2007, 1, 4), date(2012, 12, 31), _runner, _builder),
        ],
    )

    args = full_backfill.build_update_args(
        start="2007-01-04",
        end="2026-03-20",
        output_dir=str(tmp_path),
        resume_from_step="raw_2007_2012",
        resume_trade_date="2011-04-21",
        apply=False,
    )

    summary = full_backfill.run_update(args)
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))

    assert summary["status"] == "dry_run"
    assert status["steps"][0]["status"] == "skipped"
    assert status["steps"][1]["status"] == "ok"
    assert status["steps"][1]["effective_start"] == "2011-04-21"
    assert calls == [
        ("raw_2007_2012", "2011-04-21", "2012-12-31"),
        ("main_2007_2012", "2007-01-04", "2012-12-31"),
    ]
