from __future__ import annotations

from pathlib import Path

from backend.cli.commands import audit
from backend.cli.managed import product_launch_report
from backend.core.services.product_launch_report_service import (
    build_launch_readiness_report,
    parse_release_checklist,
    write_launch_readiness_report,
)


SAMPLE_CHECKLIST = """# Release Checklist

## 1. Docs

- [x] Root README uses formal product name.
- [ ] Launch report can be generated.

## 10. Blocking Rules

The product cannot launch if any rule is active:

- Unexplained baseline behavior drift
- Research-only module enters live publishing
"""


def test_parse_release_checklist_counts_items_and_blocking_rules() -> None:
    status = parse_release_checklist(SAMPLE_CHECKLIST)

    assert status.title == "Release Checklist"
    assert len(status.checked_items) == 1
    assert len(status.unchecked_items) == 1
    assert status.unchecked_items[0].section == "1. Docs"
    assert status.blocking_rules == (
        "Unexplained baseline behavior drift",
        "Research-only module enters live publishing",
    )
    assert status.ready_for_launch is False


def test_build_launch_readiness_report_marks_unfinished_items_not_ready() -> None:
    report = build_launch_readiness_report(
        SAMPLE_CHECKLIST,
        source_path="docs/product_launch/RELEASE_CHECKLIST.md",
        generated_at="2026-05-30T15:00:00Z",
    )

    assert "# 正式上线验收报告" in report
    assert "- readiness: `NOT_READY`" in report
    assert "- unchecked_items: `1`" in report
    assert "[1. Docs] Launch report can be generated." in report
    assert "本报告只读取上线验收清单，不重算研究指标。" in report


def test_write_launch_readiness_report_writes_markdown(tmp_path: Path) -> None:
    checklist_path = tmp_path / "RELEASE_CHECKLIST.md"
    output_path = tmp_path / "launch_readiness_report.md"
    checklist_path.write_text(SAMPLE_CHECKLIST, encoding="utf-8")

    written = write_launch_readiness_report(
        checklist_path,
        output_path,
        generated_at="2026-05-30T15:00:00Z",
    )

    assert written == output_path
    assert output_path.read_text(encoding="utf-8").startswith("# 正式上线验收报告")


def test_launch_readiness_report_is_managed_audit_target() -> None:
    assert audit._TARGETS["launch_readiness_report"] == "backend.cli.managed.product_launch_report"


def test_product_launch_report_cli_writes_report(tmp_path: Path, capsys) -> None:
    checklist_path = tmp_path / "RELEASE_CHECKLIST.md"
    output_path = tmp_path / "report.md"
    checklist_path.write_text(SAMPLE_CHECKLIST, encoding="utf-8")

    product_launch_report.main(
        [
            "--checklist",
            str(checklist_path),
            "--output",
            str(output_path),
            "--generated-at",
            "2026-05-30T15:00:00Z",
        ]
    )

    captured = capsys.readouterr()
    assert f"launch_report={output_path}" in captured.out
    assert "- readiness: `NOT_READY`" in output_path.read_text(encoding="utf-8")
