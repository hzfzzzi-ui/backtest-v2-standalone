from __future__ import annotations

from pathlib import Path


def _read_repo_file(*parts: str) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root.joinpath(*parts)).read_text(encoding="utf-8", errors="ignore")


def test_multifactor_rank_helpers_are_shared_from_single_module() -> None:
    helper_source = _read_repo_file("backend", "core", "engine_vector", "multifactor_rank.py")
    sma_source = _read_repo_file("backend", "core", "engine_vector", "sma_signal_provider.py")
    strict_sources = [
        _read_repo_file("backend", "core", "engine_vector", "strict_runtime_default.py"),
        _read_repo_file("backend", "core", "engine_vector", "strict_runtime_breakout.py"),
        _read_repo_file("backend", "core", "engine_vector", "strict_runtime_generic.py"),
    ]

    assert "def cross_rank_pct(" in helper_source
    assert "def build_daily_multifactor_scores(" in helper_source
    assert "from backend.core.engine_vector.multifactor_rank import build_daily_multifactor_scores" in sma_source
    assert "def _build_daily_multifactor_scores(" not in sma_source
    assert "def _cross_rank_pct(" not in sma_source
    assert any(
        "from backend.core.engine_vector.multifactor_rank import build_daily_multifactor_scores" in source
        for source in strict_sources
    )
    for strict_source in strict_sources:
        assert "def _build_daily_multifactor_scores(" not in strict_source
        assert "def _cross_rank_pct(" not in strict_source
