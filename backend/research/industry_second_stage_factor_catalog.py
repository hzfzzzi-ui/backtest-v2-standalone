from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class IndustrySecondStageFactorSpec:
    factor_id: str
    provider_attr: str
    name_zh: str
    description: str
    direction: str = "higher_is_better"
    role: str = "industry_second_stage"
    frequency: str = "daily"
    asof_policy: str = "close_eod_same_day"
    interpretability_note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_CATALOG: tuple[IndustrySecondStageFactorSpec, ...] = (
    IndustrySecondStageFactorSpec("industry_second_stage_score", "_industry_second_stage_score", "行业二阶段总分", "主线行业二阶段总分。"),
    IndustrySecondStageFactorSpec("industry_second_stage_not_hot_score", "_industry_second_stage_not_hot_score", "行业不热门分", "主线行业二阶段 not-hot 组成项。"),
    IndustrySecondStageFactorSpec("industry_second_stage_uncrowded_score", "_industry_second_stage_uncrowded_score", "行业不拥挤分", "主线行业二阶段 uncrowded 组成项。"),
    IndustrySecondStageFactorSpec("industry_second_stage_breadth_timing_score", "_industry_second_stage_breadth_timing_score", "行业广度时机分", "主线行业二阶段 breadth timing 组成项。"),
    IndustrySecondStageFactorSpec("industry_second_stage_persistence_10d", "_industry_second_stage_persistence_10d", "行业持续性10日分", "主线行业二阶段 persistence 组成项。"),
)


def build_industry_second_stage_factor_catalog() -> list[dict[str, Any]]:
    return [item.as_dict() for item in _CATALOG]


def get_industry_second_stage_factor_spec(factor_id: str) -> IndustrySecondStageFactorSpec:
    key = str(factor_id or "").strip().lower()
    for item in _CATALOG:
        if item.factor_id == key:
            return item
    raise KeyError(f"unknown industry second stage factor: {factor_id}")


def list_industry_second_stage_factor_ids() -> list[str]:
    return [item.factor_id for item in _CATALOG]
