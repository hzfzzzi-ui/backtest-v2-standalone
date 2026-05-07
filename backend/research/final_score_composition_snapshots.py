from __future__ import annotations

import numpy as np
import pandas as pd

from backend.research.final_score_composition_catalog import get_final_score_component_spec
from backend.research.mainline_breakout_runtime_context import MainlineBreakoutResearchContext
from backend.research.mainline_factor_surface_common import build_factor_score_snapshot, build_factor_snapshot, subset_columns


def build_final_score_composition_snapshots(context: MainlineBreakoutResearchContext, *, factor_ids: list[str], symbols: list[str] | None = None) -> pd.DataFrame:
    selected_symbols, selected_idx = subset_columns(context.symbols, symbols or [])
    factor_matrices: dict[str, np.ndarray] = {}
    for factor_id in factor_ids:
        spec = get_final_score_component_spec(factor_id)
        matrix = getattr(context.provider, spec.provider_attr)
        factor_matrices[factor_id] = np.asarray(matrix[:, selected_idx], dtype=float)
    return build_factor_snapshot(
        dates=context.dates,
        symbols=selected_symbols,
        factor_matrices=factor_matrices,
        tradable_matrix=np.asarray(context.tradable_matrix[:, selected_idx], dtype=bool),
    )


def build_final_score_factor_score_snapshot(factor_snapshot: pd.DataFrame, *, factor_ids: list[str], factor_weights: dict[str, float]) -> pd.DataFrame:
    selected = [factor_id for factor_id in factor_ids if factor_id != 'final_score']
    return build_factor_score_snapshot(
        factor_snapshot,
        factor_ids=selected,
        factor_weights=factor_weights,
        score_id='final_score_component_score',
    )
