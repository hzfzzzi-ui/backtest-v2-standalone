from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FinalScoreComponentSpec:
    factor_id: str
    provider_attr: str
    name_zh: str
    description: str
    role: str
    directly_in_final_score: bool
    direction: str = 'higher_is_better'
    frequency: str = 'daily'
    asof_policy: str = 'close_eod_same_day'
    interpretability_note: str = ''

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_CATALOG: tuple[FinalScoreComponentSpec, ...] = (
    FinalScoreComponentSpec('final_score', '_final_score', '综合总分', '当前主线真实使用的综合排序总分。', 'aggregate', False, interpretability_note='研究层仅用于解释，不替代正式 runtime 排序。'),
    FinalScoreComponentSpec('residual_strength_score', '_residual_strength_score', '残差强度', '主线 residual strength 组成项。', 'direct_component', True),
    FinalScoreComponentSpec('sector_strength_score', '_sector_strength_score', '行业强度', '主线 sector strength 组成项。', 'direct_component', True),
    FinalScoreComponentSpec('volume_price_quality_score', '_volume_price_quality_score', '量价质量', '主线 volume-price quality 组成项。', 'direct_component', True),
    FinalScoreComponentSpec('breakout_quality_score', '_breakout_quality_score', '突破质量', '主线 breakout quality 组成项。', 'quality_context', True),
    FinalScoreComponentSpec('breakout_margin_score', '_breakout_margin_score', '突破边际得分', '主线 breakout margin 组成项。', 'direct_component', True),
    FinalScoreComponentSpec('conditional_tiebreak_score', '_conditional_tiebreak_score', '条件加权平手分', '主线 conditional tiebreak 组成项。', 'conditional_context', True),
    FinalScoreComponentSpec('conditional_factor_leader_score', '_conditional_factor_leader_score', '条件龙头分', '主线 conditional factor leader 组成项。', 'conditional_context', True),
    FinalScoreComponentSpec('conditional_institution_proxy_score', '_conditional_institution_proxy_score', '条件机构代理分', '主线 conditional institution proxy 组成项。', 'conditional_context', True),
    FinalScoreComponentSpec('conditional_crowding_score', '_conditional_crowding_score', '条件拥挤分', '主线 conditional crowding 组成项。', 'conditional_context', True),
    FinalScoreComponentSpec('industry_second_stage_score', '_industry_second_stage_score', '行业二阶段总分', '主线行业二阶段组成项。', 'industry_second_stage', True),
    FinalScoreComponentSpec('industry_second_stage_not_hot_score', '_industry_second_stage_not_hot_score', '行业不热门分', '主线行业二阶段 not-hot 组成项。', 'industry_second_stage', True),
    FinalScoreComponentSpec('industry_second_stage_uncrowded_score', '_industry_second_stage_uncrowded_score', '行业不拥挤分', '主线行业二阶段 uncrowded 组成项。', 'industry_second_stage', True),
    FinalScoreComponentSpec('industry_second_stage_breadth_timing_score', '_industry_second_stage_breadth_timing_score', '行业广度时机分', '主线行业二阶段 breadth timing 组成项。', 'industry_second_stage', True),
    FinalScoreComponentSpec('industry_second_stage_persistence_10d', '_industry_second_stage_persistence_10d', '行业持续性10日分', '主线行业二阶段 persistence 组成项。', 'industry_second_stage', True),
)


def build_final_score_composition_catalog() -> list[dict[str, Any]]:
    return [item.as_dict() for item in _CATALOG]


def get_final_score_component_spec(factor_id: str) -> FinalScoreComponentSpec:
    key = str(factor_id or '').strip().lower()
    for item in _CATALOG:
        if item.factor_id == key:
            return item
    raise KeyError(f'unknown final score component: {factor_id}')


def list_final_score_component_ids(*, include_aggregate: bool = True) -> list[str]:
    return [item.factor_id for item in _CATALOG if include_aggregate or item.factor_id != 'final_score']
