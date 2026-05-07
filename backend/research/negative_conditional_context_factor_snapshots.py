from __future__ import annotations

import numpy as np
import pandas as pd

from backend.research.mainline_breakout_runtime_context import MainlineBreakoutResearchContext
from backend.research.mainline_factor_surface_common import build_factor_score_snapshot, build_factor_snapshot, subset_columns
from backend.research.negative_conditional_context_factor_catalog import get_negative_conditional_context_factor_spec


def build_negative_conditional_context_factor_snapshots(context: MainlineBreakoutResearchContext, *, factor_ids: list[str], symbols: list[str] | None = None) -> pd.DataFrame:
    selected_symbols, selected_idx = subset_columns(context.symbols, symbols or [])
    factor_matrices: dict[str, np.ndarray] = {}
    for factor_id in factor_ids:
        spec = get_negative_conditional_context_factor_spec(factor_id)
        matrix = getattr(context.provider, spec.provider_attr)
        if factor_id in {"conditional_recent_limit_hit_3d", "conditional_near_limit_up"}:
            factor_matrices[factor_id] = np.asarray(matrix[:, selected_idx], dtype=bool).astype(float)
        else:
            factor_matrices[factor_id] = np.asarray(matrix[:, selected_idx], dtype=float)
    return build_factor_snapshot(dates=context.dates, symbols=selected_symbols, factor_matrices=factor_matrices, tradable_matrix=np.asarray(context.tradable_matrix[:, selected_idx], dtype=bool))


def build_negative_conditional_context_factor_score_snapshot(factor_snapshot: pd.DataFrame, *, factor_ids: list[str], factor_weights: dict[str, float]) -> pd.DataFrame:
    return build_factor_score_snapshot(factor_snapshot, factor_ids=factor_ids, factor_weights=factor_weights, score_id="negative_conditional_context_score")
