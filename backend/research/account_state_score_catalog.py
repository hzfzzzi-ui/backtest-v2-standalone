from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AccountStateScoreSpec:
    score_id: str
    name_zh: str
    description: str
    scope: str = "account"
    frequency: str = "daily"
    asof_policy: str = "close_eod_same_day"
    normalization: str = "sigmoid_to_0_1"
    interpretability_note: str = ""
    derived_state_role: str = "derived_runtime_state"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_CATALOG: tuple[AccountStateScoreSpec, ...] = (
    AccountStateScoreSpec(
        score_id="risk_on_score",
        name_zh="风险开启分数",
        description="基于基准长中短趋势共同刻画账户层风险偏好开启强度。",
        interpretability_note="值越高，表示更接近持续性风险开启环境。",
    ),
    AccountStateScoreSpec(
        score_id="recovery_score",
        name_zh="恢复分数",
        description="基于短中期修复强度与长期趋势偏弱并存的特征刻画恢复阶段强度。",
        interpretability_note="值越高，表示更接近恢复而未完全转入强势的环境。",
    ),
    AccountStateScoreSpec(
        score_id="defense_score",
        name_zh="防守分数",
        description="基于长期趋势走弱、回撤压力和中期斜率转差刻画防守需求强度。",
        interpretability_note="值越高，表示更接近防守优先环境。",
    ),
)


def build_account_state_score_catalog() -> list[dict[str, Any]]:
    return [item.as_dict() for item in _CATALOG]


def get_account_state_score_spec(score_id: str) -> AccountStateScoreSpec:
    key = str(score_id or "").strip().lower()
    for item in _CATALOG:
        if item.score_id == key:
            return item
    raise KeyError(f"unknown account state score: {score_id}")


def list_account_state_score_ids() -> list[str]:
    return [item.score_id for item in _CATALOG]
