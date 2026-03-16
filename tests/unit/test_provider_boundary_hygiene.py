from __future__ import annotations

import ast
from pathlib import Path


PROVIDER_FILES = [
    Path("backend/core/engine_vector/generic_signal_provider.py"),
    Path("backend/core/engine_vector/regime_router_signal_provider.py"),
    Path("backend/core/engine_vector/sma_signal_provider.py"),
]


def _import_targets(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            targets.add(node.module)
    return targets


def test_signal_providers_do_not_import_portfolio_runtime_directly() -> None:
    for rel_path in PROVIDER_FILES:
        imports = _import_targets(rel_path)
        assert "backend.core.portfolio.portfolio_runtime" not in imports, rel_path.as_posix()


def test_regime_router_provider_delegates_to_split_modules() -> None:
    imports = _import_targets(Path("backend/core/engine_vector/regime_router_signal_provider.py"))

    assert "backend.core.engine_vector.regime_router_precompute" in imports
    assert "backend.core.engine_vector.regime_router_day_routes" in imports
    assert "backend.core.engine_vector.features" not in imports
    assert "backend.core.engine_vector.data_matrix" not in imports


def test_strict_runtime_default_is_a_stage_orchestration_facade() -> None:
    imports = _import_targets(Path("backend/core/engine_vector/strict_runtime_default.py"))

    assert "backend.core.engine_vector.strict_runtime_input_stage" in imports
    assert "backend.core.engine_vector.strict_runtime_benchmark_stage" in imports
    assert "backend.core.engine_vector.strict_runtime_signal_stage" in imports
    assert "backend.core.engine_vector.strict_runtime_daily_loop" in imports
    assert "backend.core.engine_vector.strict_runtime_result_stage" in imports
    assert "backend.core.engine_vector.features" not in imports
    assert "backend.core.engine_vector.signal_matrix" not in imports
    assert "backend.core.portfolio.metrics" not in imports
    assert "backend.core.portfolio.nav_snapshot" not in imports
