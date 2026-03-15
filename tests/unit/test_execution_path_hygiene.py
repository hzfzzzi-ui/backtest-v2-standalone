from __future__ import annotations

import ast
from pathlib import Path


STRICT_PATH = Path("backend/core/engine_vector/portfolio_simulator_strict.py")
STRICT_IMPL_PATH = Path("backend/core/engine_vector/strict_runtime_impl.py")
BRIDGE_ADAPTER_PATH = Path("backend/core/stage_pipeline/adapters/bridge_adapter.py")
PORTFOLIO_BUILDER_PATH = Path("backend/core/portfolio/portfolio_builder.py")
FROZEN_LOOP_PATH = Path("backend/core/portfolio/frozen_loop.py")

FROZEN_PATHS = (
    STRICT_PATH,
    BRIDGE_ADAPTER_PATH,
    PORTFOLIO_BUILDER_PATH,
)


def _parse_module(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _import_targets(path: Path) -> set[str]:
    tree = _parse_module(path)
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            targets.add(node.module)
    return targets


def test_strict_shim_only_dispatches_known_compat_routes() -> None:
    imports = _import_targets(STRICT_PATH)
    assert "backend.core.engine_vector.strict_runtime_impl" in imports

    tree = _parse_module(STRICT_PATH)
    compat_routes: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not isinstance(node.left, ast.Name) or node.left.id != "route_id":
            continue
        if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
            continue
        if len(node.comparators) != 1:
            continue
        comparator = node.comparators[0]
        if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
            compat_routes.add(comparator.value)
    assert compat_routes == set()


def test_portfolio_builder_exports_frozen_loop_entrypoint() -> None:
    imports = _import_targets(PORTFOLIO_BUILDER_PATH)
    assert "backend.core.portfolio.frozen_loop" in imports


def test_frozen_paths_do_not_register_new_extension_points() -> None:
    forbidden_prefixes = (
        "backend.core.stage_pipeline.builtins",
        "backend.core.stage_pipeline.registry",
        "backend.core.stage_pipeline.resolver",
    )
    for rel_path in FROZEN_PATHS:
        imports = _import_targets(rel_path)
        assert not any(
            target == prefix or target.startswith(f"{prefix}.")
            for prefix in forbidden_prefixes
            for target in imports
        ), rel_path.as_posix()


def test_frozen_paths_declare_freeze_or_deletion_intent() -> None:
    expected_phrases = {
        STRICT_PATH: ("dispatch shim", "minimum golden set"),
        STRICT_IMPL_PATH: ("dispatch shim", "minimum golden set"),
        BRIDGE_ADAPTER_PATH: ("Frozen bridge adapter", "Deletion is allowed only"),
        PORTFOLIO_BUILDER_PATH: ("Frozen portfolio loop facade", "frozen_loop.py"),
        FROZEN_LOOP_PATH: ("Frozen portfolio loop implementation", "New execution"),
    }
    for rel_path, phrases in expected_phrases.items():
        docstring = ast.get_docstring(_parse_module(rel_path)) or ""
        for phrase in phrases:
            assert phrase in docstring, rel_path.as_posix()
