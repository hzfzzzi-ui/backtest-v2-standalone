"""Transitional dispatch shim for the strict runtime.

New route branches and execution logic must not be introduced here. Route
selection belongs in `route_registry.py`, and formal execution flow belongs in
`foundation_shell.py` plus `stage_pipeline/*`. This module remains only until
the minimum golden set passes and the runtime cleanup path can continue.
"""

from __future__ import annotations

from backend.core.engine_vector.strict_runtime_impl import run_vector_portfolio_backtest_strict

__all__ = ["run_vector_portfolio_backtest_strict"]
