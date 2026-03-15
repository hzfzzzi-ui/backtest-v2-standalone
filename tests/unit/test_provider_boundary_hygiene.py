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


def test_signal_providers_do_not_import_portfolio_builder_directly() -> None:
    for rel_path in PROVIDER_FILES:
        imports = _import_targets(rel_path)
        assert "backend.core.portfolio.portfolio_builder" not in imports, rel_path.as_posix()
