from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    name: str
    alpha_id: str
    family: str
    sleeve_id: str
    params: dict[str, Any]


def normalized_symbol(value: Any) -> str:
    return str(value or "").strip().lower()


def normalized_name(value: Any) -> str:
    return str(value or "").strip().lower()


def safe_score(value: Any, *, fallback: float = 0.5) -> float:
    try:
        score = float(value)
    except Exception:
        return float(fallback)
    if np.isnan(score):
        return float(fallback)
    return float(score)
