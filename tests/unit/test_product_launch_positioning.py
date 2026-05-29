from __future__ import annotations

from pathlib import Path


FORMAL_CN_NAME = "个人多资产趋势配置系统"
FORMAL_EN_NAME = "OpenClaw Personal Multi-Asset Trend Allocation System"
DEPRECATED_FORMAL_NAMES = (
    "专业量化研究平台",
    "OpenClaw Quant Research Platform",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(*parts: str) -> str:
    return _repo_root().joinpath(*parts).read_text(encoding="utf-8", errors="ignore")


def test_root_readme_uses_formal_product_positioning() -> None:
    source = _read("README.md")

    assert source.startswith(f"# {FORMAL_EN_NAME}")
    assert f"**{FORMAL_CN_NAME}**" in source
    assert "受研究纪律约束" in source
    assert "不加杠杆" in source
    assert "不作为个人资产管理或记账系统" in source
    assert "PAMS 系统承接" in source
    assert "`outputs/` 运行产物" in source

    for deprecated_name in DEPRECATED_FORMAL_NAMES:
        assert deprecated_name not in source


def test_product_launch_docs_keep_formal_positioning_consistent() -> None:
    required_docs = (
        ("docs", "product_launch", "README.md"),
        ("docs", "product_launch", "FEATURES.md"),
        ("docs", "product_launch", "ARCHITECTURE.md"),
        ("docs", "product_launch", "MODULE_OWNERSHIP.md"),
        ("docs", "product_launch", "NAMING_AND_DEPRECATION.md"),
        ("docs", "product_launch", "RELEASE_CHECKLIST.md"),
    )

    for rel_parts in required_docs:
        source = _read(*rel_parts)
        assert FORMAL_CN_NAME in source, "/".join(rel_parts)
        for deprecated_name in DEPRECATED_FORMAL_NAMES:
            assert deprecated_name not in source, "/".join(rel_parts)

    product_readme = _read("docs", "product_launch", "README.md")
    naming_doc = _read("docs", "product_launch", "NAMING_AND_DEPRECATION.md")
    architecture_doc = _read("docs", "product_launch", "ARCHITECTURE.md")

    assert FORMAL_EN_NAME in product_readme
    assert FORMAL_EN_NAME in naming_doc
    assert FORMAL_EN_NAME in architecture_doc
    assert "openclaw-personal-multi-asset-trend-allocation" in product_readme
    assert "openclaw-personal-multi-asset-trend-allocation" in naming_doc


def test_pams_externalization_checklist_matches_boundary_registry() -> None:
    from backend.core.services.service_boundary_status import SERVICE_BOUNDARY_BY_MODULE

    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    contract_path = _repo_root().joinpath(
        "docs",
        "product_launch",
        "contracts",
        "daily_position_adjustment_package_v1.md",
    )

    assert SERVICE_BOUNDARY_BY_MODULE["backend.api.mobile"].target_system == "pams"
    assert SERVICE_BOUNDARY_BY_MODULE["backend.api.mobile"].launch_status == "externalize_to_pams"
    assert SERVICE_BOUNDARY_BY_MODULE["backend.core.services.mobile_ops_service"].target_system == "pams"
    assert SERVICE_BOUNDARY_BY_MODULE["backend.core.services.sim_account_service"].launch_status == "compat_audit_only"
    assert SERVICE_BOUNDARY_BY_MODULE["backend.core.services.transaction_lifecycle_service"].target_system == "pams"
    assert contract_path.exists()

    for checked_item in (
        "`api.mobile` 不属于正式研究平台主路径。",
        "`mobile_*` services 标记为 externalized_to_pams 或 deprecated。",
        "`sim_account` 不作为账户真值。",
        "`transaction_lifecycle_service` 不作为研究平台正式交易主表 owner。",
        "调仓包合同存在。",
        "PAMS 是正式通知、审批、执行状态 owner。",
    ):
        assert f"- [x] {checked_item}" in checklist


def test_naming_governance_checklist_matches_naming_doc() -> None:
    checklist = _read("docs", "product_launch", "RELEASE_CHECKLIST.md")
    naming_doc = _read("docs", "product_launch", "NAMING_AND_DEPRECATION.md")

    for marker in (
        FORMAL_EN_NAME,
        "个人多资产趋势配置系统",
        "`openclaw-personal-multi-asset-trend-allocation`",
        "当前名称废弃",
        "`pams_` 作为研究平台正式对象前缀",
        "`shadow` | `diagnostic_probe`",
        "`AB` | `controlled_experiment`",
    ):
        assert marker in naming_doc

    for checked_item in (
        "新增正式命名清单。",
        "新增废弃命名清单。",
        "`backtest_V2_standalone` 不再作为产品名。",
        "`PAMS/pams_` 不再作为研究平台正式命名前缀。",
        "`shadow` 和 `AB` 已映射到 `diagnostic_probe` 和 `controlled_experiment`。",
    ):
        assert f"- [x] {checked_item}" in checklist
