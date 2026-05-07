from __future__ import annotations

import pandas as pd
import numpy as np

from backend.research.exit_fragility_factor_catalog import get_exit_fragility_factor_spec
from backend.research.mainline_breakout_runtime_context import MainlineBreakoutResearchContext
from backend.research.mainline_factor_surface_common import build_factor_score_snapshot, build_factor_snapshot, subset_columns


def build_exit_fragility_factor_snapshots(context: MainlineBreakoutResearchContext, *, factor_ids: list[str], symbols: list[str] | None = None) -> pd.DataFrame:
    selected_symbols, selected_idx = subset_columns(context.symbols, symbols or [])
    factor_matrices: dict[str, np.ndarray] = {}
    for factor_id in factor_ids:
        spec = get_exit_fragility_factor_spec(factor_id)
        matrix = getattr(context.provider, spec.provider_attr)
        factor_matrices[factor_id] = np.asarray(matrix[:, selected_idx], dtype=float)
    return build_factor_snapshot(
        dates=context.dates,
        symbols=selected_symbols,
        factor_matrices=factor_matrices,
        tradable_matrix=np.asarray(context.tradable_matrix[:, selected_idx], dtype=bool),
    )


def build_exit_fragility_factor_score_snapshot(factor_snapshot: pd.DataFrame, *, factor_ids: list[str], factor_weights: dict[str, float]) -> pd.DataFrame:
    invert_for_score = {factor_id for factor_id in factor_ids if get_exit_fragility_factor_spec(factor_id).direction == 'lower_is_worse'}
    return build_factor_score_snapshot(
        factor_snapshot,
        factor_ids=factor_ids,
        factor_weights=factor_weights,
        invert_for_score=invert_for_score,
        score_id='exit_fragility_score',
    )
