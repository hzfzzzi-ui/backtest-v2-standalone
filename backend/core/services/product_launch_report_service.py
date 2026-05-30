from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence


_CHECKLIST_RE = re.compile(r"^- \[(?P<mark>[ xX])\]\s+(?P<text>.+?)\s*$")
_BULLET_RE = re.compile(r"^-\s+(?P<text>.+?)\s*$")
_SECTION_RE = re.compile(r"^##\s+(?P<number>\d+)\.\s+(?P<title>.+?)\s*$")


@dataclass(frozen=True)
class LaunchChecklistItem:
    section: str
    text: str
    checked: bool


@dataclass(frozen=True)
class LaunchChecklistStatus:
    title: str
    items: tuple[LaunchChecklistItem, ...]
    blocking_rules: tuple[str, ...]

    @property
    def checked_items(self) -> tuple[LaunchChecklistItem, ...]:
        return tuple(item for item in self.items if item.checked)

    @property
    def unchecked_items(self) -> tuple[LaunchChecklistItem, ...]:
        return tuple(item for item in self.items if not item.checked)

    @property
    def ready_for_launch(self) -> bool:
        return not self.unchecked_items


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_release_checklist(text: str) -> LaunchChecklistStatus:
    title = ""
    current_section = "未分组"
    in_blocking_rules = False
    items: list[LaunchChecklistItem] = []
    blocking_rules: list[str] = []

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue

        section_match = _SECTION_RE.match(line)
        if section_match:
            number = section_match.group("number")
            current_section = f'{number}. {section_match.group("title").strip()}'
            in_blocking_rules = number == "10"
            continue

        checklist_match = _CHECKLIST_RE.match(line)
        if checklist_match:
            mark = checklist_match.group("mark").strip().lower()
            items.append(
                LaunchChecklistItem(
                    section=current_section,
                    text=checklist_match.group("text").strip(),
                    checked=mark == "x",
                )
            )
            continue

        if in_blocking_rules:
            bullet_match = _BULLET_RE.match(line)
            if bullet_match:
                blocking_rules.append(bullet_match.group("text").strip())

    if not items:
        raise ValueError("release checklist has no '- [ ]' or '- [x]' items")

    return LaunchChecklistStatus(
        title=title or "上线差距清单",
        items=tuple(items),
        blocking_rules=tuple(blocking_rules),
    )


def build_launch_readiness_report(
    checklist_text: str,
    *,
    source_path: str | Path = "docs/上线准备/上线差距清单.md",
    generated_at: str | None = None,
) -> str:
    status = parse_release_checklist(checklist_text)
    checked_count = len(status.checked_items)
    unchecked_items = status.unchecked_items
    readiness = "READY" if status.ready_for_launch else "NOT_READY"

    lines: list[str] = [
        "# 正式上线验收报告",
        "",
        f"- source: `{Path(source_path).as_posix()}`",
        f"- generated_at: `{generated_at or _now_iso()}`",
        f"- checklist_title: `{status.title}`",
        f"- checked_items: `{checked_count}`",
        f"- unchecked_items: `{len(unchecked_items)}`",
        f"- blocking_rules: `{len(status.blocking_rules)}`",
        f"- readiness: `{readiness}`",
        "",
        "## 未完成清单",
        "",
    ]

    if unchecked_items:
        lines.extend(f"- [{item.section}] {item.text}" for item in unchecked_items)
    else:
        lines.append("- 无")

    lines.extend(["", "## 阻断规则", ""])
    if status.blocking_rules:
        lines.extend(f"- {rule}" for rule in status.blocking_rules)
    else:
        lines.append("- 无")

    lines.extend(
        [
            "",
            "## 生成边界",
            "",
            "- 本报告只读取上线验收清单，不重算研究指标。",
            "- 存在未完成清单项时，readiness 必须保持 NOT_READY。",
            "",
        ]
    )
    return "\n".join(lines)


def write_launch_readiness_report(
    checklist_path: str | Path,
    output_path: str | Path,
    *,
    generated_at: str | None = None,
) -> Path:
    source = Path(checklist_path)
    output = Path(output_path)
    report = build_launch_readiness_report(
        source.read_text(encoding="utf-8-sig"),
        source_path=source,
        generated_at=generated_at,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    return output


__all__: Sequence[str] = (
    "LaunchChecklistItem",
    "LaunchChecklistStatus",
    "parse_release_checklist",
    "build_launch_readiness_report",
    "write_launch_readiness_report",
)
