from __future__ import annotations

from pathlib import Path


def test_architecture_closure_gates_doc_declares_p0_blockers() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    doc_path = repo_root / "docs" / "architecture_closure_gates.md"
    text = doc_path.read_text(encoding="utf-8")

    assert "baseline_V10.1" in text
    assert "backend/scripts/ops/v2_backend_refactor_baseline_contract.json" in text
    assert "exp_20260426_005716047_8650" in text
    assert "exp_20260314_144548534_7db9" in text
    assert "exp_20260328_220801073_478b" in text
    assert "pytest -q --collect-only" in text
    assert "tests/unit/test_script_surface_governance.py tests/unit/test_cli_main.py" in text
    assert "python -m backend.cli audit --target baseline_regression" in text
    assert "`P1` work must not start until every `P0` gate below is green." in text
    assert "allowed_drift_fields" in text
