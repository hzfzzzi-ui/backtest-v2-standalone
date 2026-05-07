from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MoneyflowFactorSpec:
    factor_id: str
    name_zh: str
    description: str
    dependencies: tuple[str, ...]
    frequency: str = "monthly_observation"
    asof_policy: str = "month_end_close_with_required_coverage"
    normalization: str = "cross_sectional_zscore_and_pct_rank"
    interpretability_note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_CATALOG: tuple[MoneyflowFactorSpec, ...] = (
    MoneyflowFactorSpec(
        factor_id="monthly_divergence_rate",
        name_zh="月度资金流偏离率",
        description="月末观测的月度资金流偏离率，基于日度 abs(net_mf_amount) 相对 20 日规模基准汇总而成。",
        dependencies=("net_mf_amount", "circ_mv", "amount"),
        interpretability_note="值越高表示当月资金流偏离越大，首版仅作为研究因子使用。",
    ),
)


def build_moneyflow_factor_catalog() -> list[dict[str, Any]]:
    return [item.as_dict() for item in _CATALOG]


def get_moneyflow_factor_spec(factor_id: str) -> MoneyflowFactorSpec:
    key = str(factor_id or "").strip().lower()
    for item in _CATALOG:
        if item.factor_id == key:
            return item
    raise KeyError(f"unknown moneyflow factor: {factor_id}")


def list_moneyflow_factor_ids() -> list[str]:
    return [item.factor_id for item in _CATALOG]
