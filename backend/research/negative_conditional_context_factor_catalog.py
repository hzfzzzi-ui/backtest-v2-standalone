from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class NegativeConditionalContextFactorSpec:
    factor_id: str
    provider_attr: str
    name_zh: str
    description: str
    direction: str = "higher_is_worse"
    role: str = "conditional_context"
    frequency: str = "daily"
    asof_policy: str = "close_eod_same_day"
    interpretability_note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_CATALOG: tuple[NegativeConditionalContextFactorSpec, ...] = (
    NegativeConditionalContextFactorSpec("conditional_tiebreak_score", "_conditional_tiebreak_score", "条件平手打破分", "主线 conditional tiebreak 组成项，当前更像负向条件上下文。"),
    NegativeConditionalContextFactorSpec("conditional_factor_leader_score", "_conditional_factor_leader_score", "条件龙头分", "主线 conditional factor leader 组成项，当前先按高分更脆弱的负向条件上下文研究。"),
    NegativeConditionalContextFactorSpec("conditional_institution_proxy_score", "_conditional_institution_proxy_score", "条件机构代理分", "主线 conditional institution proxy 组成项，当前三窗口更像负向条件项。"),
    NegativeConditionalContextFactorSpec("conditional_crowding_score", "_conditional_crowding_score", "条件拥挤分", "主线 conditional crowding 组成项，当前先按拥挤风险上下文研究。"),
    NegativeConditionalContextFactorSpec("conditional_recent_limit_hit_3d", "_conditional_recent_limit_hit_3d", "近期三日触板风险", "主线 conditional recent limit hit 3d 标记，研究其是否对应伪突破脆弱性。", role="event_risk"),
    NegativeConditionalContextFactorSpec("conditional_near_limit_up", "_conditional_near_limit_up", "临近涨停风险", "主线 conditional near limit up 标记，研究其是否对应高位脆弱性。", role="event_risk"),
)


def build_negative_conditional_context_factor_catalog() -> list[dict[str, Any]]:
    return [item.as_dict() for item in _CATALOG]


def get_negative_conditional_context_factor_spec(factor_id: str) -> NegativeConditionalContextFactorSpec:
    key = str(factor_id or "").strip().lower()
    for item in _CATALOG:
        if item.factor_id == key:
            return item
    raise KeyError(f"unknown negative conditional context factor: {factor_id}")


def list_negative_conditional_context_factor_ids() -> list[str]:
    return [item.factor_id for item in _CATALOG]
