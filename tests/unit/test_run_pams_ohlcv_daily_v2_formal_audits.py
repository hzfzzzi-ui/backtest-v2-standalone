from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from backend.cli.managed import run_pams_ohlcv_daily_v2_formal_audits as formal_audits


def test_formal_audit_windows_use_2012_2017_not_2007_2017() -> None:
    assert [window.key for window in formal_audits.v2_common.FORMAL_AUDIT_WINDOWS] == [
        "2016_2026",
        "2012_2017",
        "2007_2026",
    ]
    assert list(formal_audits.v2_common.FORMAL_AUDIT_REQUIRED_WINDOW_KEYS) == [
        "2016_2026",
        "2012_2017",
    ]
    assert list(formal_audits.v2_common.FORMAL_AUDIT_ADVISORY_WINDOW_KEYS) == [
        "2007_2026",
    ]
    assert formal_audits.v2_common.FORMAL_AUDIT_WINDOWS[1].start_date.isoformat() == "2012-01-04"
    assert formal_audits.v2_common.FORMAL_AUDIT_WINDOWS[1].end_date.isoformat() == "2017-12-29"


def test_formal_audits_runner_executes_all_required_windows(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, str, str]] = []

    def _fake_build_update_args(**kwargs) -> Namespace:
        return Namespace(**kwargs)

    def _fake_run_update(args: Namespace) -> dict[str, object]:
        calls.append(
            (
                str(args.heartbeat_label),
                str(args.start),
                str(args.end),
                str(args.output_dir),
            )
        )
        output_dir = Path(str(args.output_dir))
        output_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "status": "completed",
            "gate": {
                "canonical": {
                    "eligible_no_source_rows": 0,
                    "hard_field_null_rows": 0,
                    "critical_exception_rows": 0,
                    "can_promote_shadow": True,
                },
                "runtime": {
                    "runtime_eligible_rows": 123,
                    "can_consume_v10_1": True,
                },
            },
        }
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return summary

    monkeypatch.setattr(formal_audits.audit_build, "build_update_args", _fake_build_update_args)
    monkeypatch.setattr(formal_audits.audit_build, "run_update", _fake_run_update)

    summary = formal_audits.run_update(
        formal_audits.build_update_args(
            output_dir=str(tmp_path),
            heartbeat_label="audit_formal_windows",
            apply=True,
        )
    )

    assert summary["status"] == "completed"
    assert summary["formal_windows_complete"] is True
    assert summary["all_windows_complete"] is True
    assert summary["required_windows"] == ["2016_2026", "2012_2017"]
    assert summary["advisory_windows"] == ["2007_2026"]
    assert [item["key"] for item in summary["windows"]] == ["2016_2026", "2012_2017", "2007_2026"]
    assert calls == [
        (
            "audit_formal_windows:2016_2026",
            "2016-03-01",
            "2026-03-20",
            str(tmp_path / "audit_2016_2026"),
        ),
        (
            "audit_formal_windows:2012_2017",
            "2012-01-04",
            "2017-12-29",
            str(tmp_path / "audit_2012_2017"),
        ),
        (
            "audit_formal_windows:2007_2026",
            "2007-01-04",
            "2026-03-20",
            str(tmp_path / "audit_2007_2026"),
        ),
    ]
    top_summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert top_summary["formal_windows_complete"] is True
    assert top_summary["all_windows_complete"] is True
    assert top_summary["windows"][1]["label"] == "2012-2017"
