from __future__ import annotations

from pathlib import Path

from backend.research.account_state_score_catalog import build_account_state_score_catalog
from backend.research.execution_pressure_factor_catalog import build_execution_pressure_factor_catalog
from backend.research.exit_fragility_factor_catalog import build_exit_fragility_factor_catalog
from backend.research.final_score_composition_catalog import build_final_score_composition_catalog
from backend.research.industry_second_stage_factor_catalog import build_industry_second_stage_factor_catalog
from backend.research.moneyflow_factor_catalog import build_moneyflow_factor_catalog
from backend.research.negative_conditional_context_factor_catalog import (
    build_negative_conditional_context_factor_catalog,
)
from backend.research.positive_quality_factor_catalog import build_positive_quality_factor_catalog
from backend.research.risk_gate_factor_catalog import build_risk_gate_factor_catalog
from backend.research.stock_alpha_factor_catalog import build_stock_alpha_factor_catalog
from backend.research.stock_lifecycle_fragility_catalog import build_stock_lifecycle_fragility_catalog


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(*parts: str) -> str:
    return _repo_root().joinpath(*parts).read_text(encoding="utf-8", errors="ignore")


def test_docs_readme_declares_human_machine_research_layers() -> None:
    readme = _read("docs", "README.md")
    governance = _read("docs", "DOCS_GOVERNANCE.md")

    for marker in (
        "人读说明",
        "合同/准机器文档",
        "机器执行材料",
        "研究记录",
        "历史/重构材料",
        "05_研究记录",
        "product_launch",
        "outputs/` 属于运行产物路径",
    ):
        assert marker in readme

    for marker in (
        "| H | 人读说明",
        "| C | 合同/准机器文档",
        "| M | 机器执行材料",
        "| R | 研究记录",
        "| A | 历史/重构材料",
        "没有进入登记表的因子",
    ):
        assert marker in governance


def test_factor_research_registry_covers_catalog_ids_and_study_paths() -> None:
    registry = _read("docs", "05_研究记录", "因子研究登记.md")

    catalog_builders = (
        ("backend/research/stock_alpha_factor_catalog.py", build_stock_alpha_factor_catalog),
        ("backend/research/moneyflow_factor_catalog.py", build_moneyflow_factor_catalog),
        ("backend/research/risk_gate_factor_catalog.py", build_risk_gate_factor_catalog),
        ("backend/research/execution_pressure_factor_catalog.py", build_execution_pressure_factor_catalog),
        ("backend/research/exit_fragility_factor_catalog.py", build_exit_fragility_factor_catalog),
        ("backend/research/positive_quality_factor_catalog.py", build_positive_quality_factor_catalog),
        (
            "backend/research/negative_conditional_context_factor_catalog.py",
            build_negative_conditional_context_factor_catalog,
        ),
        ("backend/research/final_score_composition_catalog.py", build_final_score_composition_catalog),
        ("backend/research/industry_second_stage_factor_catalog.py", build_industry_second_stage_factor_catalog),
        ("backend/research/stock_lifecycle_fragility_catalog.py", build_stock_lifecycle_fragility_catalog),
        ("backend/research/account_state_score_catalog.py", build_account_state_score_catalog),
    )

    for catalog_path, build_catalog in catalog_builders:
        assert catalog_path in registry
        for item in build_catalog():
            factor_or_score_id = item.get("factor_id") or item.get("score_id")
            assert factor_or_score_id in registry

    for rel_path in _repo_root().joinpath("research", "studies", "factors").glob("*.study.yaml"):
        rel = rel_path.relative_to(_repo_root()).as_posix()
        assert rel in registry

    assert "research/studies/state_scores/account_state_score_real_mainline_s1.study.yaml" in registry
    assert "needs_journal_link" in registry
    assert "不得直接修改出场时点" in registry
