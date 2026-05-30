from __future__ import annotations

from pathlib import Path


def test_architecture_closure_gates_doc_declares_p0_blockers() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    doc_path = repo_root / "docs" / "架构关闭门禁.md"
    text = doc_path.read_text(encoding="utf-8")

    assert "baseline_V10.1" in text
    assert "CN_STOCK_ETF_COMBO_BASELINE_V3" in text
    assert "backend/scripts/ops/v2_backend_refactor_baseline_contract.json" in text
    assert "exp_20260510_034302669_7790" in text
    assert "exp_20260426_005716047_8650" in text
    assert "exp_20260511_073506050_3d22" in text
    assert "exp_20260314_144548534_7db9" in text
    assert "exp_20260328_220801073_478b" in text
    assert "pytest -q --collect-only" in text
    assert "tests/unit/test_shared_helper_boundary.py" in text
    assert "tests/unit/test_script_surface_governance.py tests/unit/test_cli_main.py" in text
    assert "python -m backend.cli audit --target baseline_regression" in text
    assert "所有 P0 门禁变绿前，不得启动 P1 工作。" in text
    assert "`backend/cli/managed` 重新依赖 `backend.scripts`" in text
    assert "`backend/core/services/market_data_sync_records.py` 从纯同步运行记录存储退化" in text
    assert "`backend/core/services/market_data_sync_freshness.py`" in text
    assert "`backend/api` 在 `tests/unit/test_shared_helper_boundary.py` 显式 legacy allowlist 之外新增直接 DB/env owner" in text
    assert "display-only，或没有声明 canonical truth 归后端所有" in text
    assert "`backend/scripts/generated` 出现没有匹配 `research/studies/*.study.yaml` 的 wrapper" in text
    assert "allowed_drift_fields" in text
