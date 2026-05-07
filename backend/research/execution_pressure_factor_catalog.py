from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ExecutionPressureFactorSpec:
    factor_id: str
    name_zh: str
    description: str
    direction: str = "higher_is_worse"
    scope: str = "stock_sleeve_account"
    frequency: str = "daily"
    asof_policy: str = "close_eod_same_day"
    interpretability_note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_CATALOG: tuple[ExecutionPressureFactorSpec, ...] = (
    ExecutionPressureFactorSpec("slot_overhang_pressure", "槽位过滤压力", "候选在 slot filter 后被压缩的比例，刻画候选过多相对槽位不足的压力。"),
    ExecutionPressureFactorSpec("cash_lot_pressure", "现金手数压力", "slot filter 后因现金/整手约束继续掉队的比例。"),
    ExecutionPressureFactorSpec("budget_reject_pressure", "预算拒单压力", "由 sleeve budget reject 造成的候选压缩比例。"),
    ExecutionPressureFactorSpec("deployment_gap_pressure", "部署缺口压力", "计划 buy slots 与实际 selected 之间的缺口比例。"),
    ExecutionPressureFactorSpec("underexposure_pressure", "欠部署压力", "stock sleeve 当日 gross exposure 未能部署到位的程度。"),
    ExecutionPressureFactorSpec("cash_drag_pressure", "现金拖累压力", "cash/nav 比例，刻画持仓部署不足导致的现金拖累。"),
)


def build_execution_pressure_factor_catalog() -> list[dict[str, Any]]:
    return [item.as_dict() for item in _CATALOG]


def list_execution_pressure_factor_ids() -> list[str]:
    return [item.factor_id for item in _CATALOG]
