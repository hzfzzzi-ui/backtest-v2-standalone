from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_research_workbench_frontend_slimming_audit_exists() -> None:
    path = _repo_root().joinpath(
        "docs",
        "02_系统架构设计",
        "研究工作台前端瘦身审计.md",
    )
    source = path.read_text(encoding="utf-8")

    for marker in (
        "resultsFormatting.js",
        "前端 helper 不得成为",
        "displayFormatPrimitives.js",
        "comboContractFormatting.js",
    ):
        assert marker in source
