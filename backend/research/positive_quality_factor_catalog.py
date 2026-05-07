from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PositiveQualityFactorSpec:
    factor_id: str
    provider_attr: str
    name_zh: str
    description: str
    direction: str = "higher_is_better"
    frequency: str = "daily"
    asof_policy: str = "close_eod_same_day"
    interpretability_note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_CATALOG: tuple[PositiveQualityFactorSpec, ...] = (
    PositiveQualityFactorSpec("volume_price_quality_score", "_volume_price_quality_score", "量价质量分", "主线 final_score 组成中最稳定偏正的量价质量项。"),
    PositiveQualityFactorSpec("breakout_quality_score", "_breakout_quality_score", "突破质量分", "主线 final_score 组成中偏正的突破质量项。"),
)


def build_positive_quality_factor_catalog() -> list[dict[str, Any]]:
    return [item.as_dict() for item in _CATALOG]


def get_positive_quality_factor_spec(factor_id: str) -> PositiveQualityFactorSpec:
    key = str(factor_id or "").strip().lower()
    for item in _CATALOG:
        if item.factor_id == key:
            return item
    raise KeyError(f"unknown positive quality factor: {factor_id}")


def list_positive_quality_factor_ids() -> list[str]:
    return [item.factor_id for item in _CATALOG]
