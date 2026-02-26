from __future__ import annotations

import numpy as np


def build_daily_candidate_index(buy_base: np.ndarray) -> list[np.ndarray]:
    return [np.where(buy_base[i])[0] for i in range(buy_base.shape[0])]

