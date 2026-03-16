from __future__ import annotations

import ast
from pathlib import Path


STRICT_RUNTIME_PATH = Path("backend/core/engine_vector/strict_runtime.py")
BRIDGE_ADAPTER_PATH = Path("backend/core/stage_pipeline/adapters/bridge_adapter.py")
PORTFOLIO_RUNTIME_PATH = Path("backend/core/portfolio/portfolio_runtime.py")
PORTFOLIO_LOOP_PATH = Path("backend/core/portfolio/portfolio_loop.py")

RETIRED_PATHS = (
    Path("backend/core/engine_vector/portfolio_simulator_strict.py"),
    Path("backend/core/engine_vector/strict_runtime_impl.py"),
    Path("backend/core/portfolio/portfolio_builder.py"),
    Path("backend/core/portfolio/frozen_loop.py"),
)


def _parse_module(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8-sig"))


def _import_targets(path: Path) -> set[str]:
    targets: set[str] = set()
    for node in ast.walk(_parse_module(path)):
        if isinstance(node, ast.ImportFrom) and node.module:
            targets.add(node.module)
    return targets


def test_retired_execution_paths_are_removed() -> None:
    for rel_path in RETIRED_PATHS:
        assert not rel_path.exists(), rel_path.as_posix()


def test_runtime_modules_point_at_final_execution_paths() -> None:
    runtime_imports = _import_targets(PORTFOLIO_RUNTIME_PATH)
    loop_imports = _import_targets(PORTFOLIO_LOOP_PATH)

    assert "backend.core.portfolio.portfolio_loop" in runtime_imports
    assert "backend.core.engine_vector.strict_runtime" in loop_imports
    assert "backend.core.portfolio.portfolio_runtime" in loop_imports


def test_active_backend_core_sources_no_longer_reference_retired_execution_paths() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    core_root = repo_root / "backend" / "core"
    retired_tokens = (
        "portfolio_simulator_strict.py",
        "strict_runtime_impl.py",
        "backend.core.portfolio.portfolio_builder",
        "backend.core.portfolio.frozen_loop",
    )
    matches: list[str] = []
    for path in core_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(token in text for token in retired_tokens):
            matches.append(str(path.relative_to(repo_root)).replace("\\", "/"))
    assert matches == []


def test_final_execution_modules_drop_transitional_docstrings() -> None:
    expected = {
        STRICT_RUNTIME_PATH: ("Vector runtime entrypoint",),
        BRIDGE_ADAPTER_PATH: ("Stage-pipeline bridge",),
        PORTFOLIO_RUNTIME_PATH: ("Portfolio runtime helpers",),
        PORTFOLIO_LOOP_PATH: ("Portfolio loop implementation",),
    }
    forbidden = ("Frozen", "Transitional", "deletion is allowed only")
    for rel_path, required_phrases in expected.items():
        docstring = ast.get_docstring(_parse_module(rel_path)) or ""
        for phrase in required_phrases:
            assert phrase in docstring, rel_path.as_posix()
        lowered = docstring.lower()
        assert all(token.lower() not in lowered for token in forbidden), rel_path.as_posix()
