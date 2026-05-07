from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StockLifecycleFragilityFactorSpec:
    factor_id: str
    name_zh: str
    description: str
    lifecycle_group: str
    direction: str = 'higher_is_worse'
    scope: str = 'stock_lifecycle'
    frequency: str = 'daily'
    asof_policy: str = 'close_eod_same_day'
    interpretability_note: str = ''

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_CATALOG: tuple[StockLifecycleFragilityFactorSpec, ...] = (
    StockLifecycleFragilityFactorSpec(
        'early_fade_risk',
        '早期衰减风险',
        '最近一次主线 entry 之后 1-5 bar 内，从持有期高点向下回落的脆弱性。',
        'early_fade',
    ),
    StockLifecycleFragilityFactorSpec(
        'weak_carry_risk',
        '弱持续性风险',
        '最近一次主线 entry 之后 5-20 bar 内，持有收益缺乏延续性的风险。',
        'weak_carry',
    ),
    StockLifecycleFragilityFactorSpec(
        'break_floor_risk',
        '破位风险',
        '持有期内价格向近期 low10 floor 靠近或跌破时的脆弱性。',
        'break_floor',
    ),
    StockLifecycleFragilityFactorSpec(
        'pre_profit_failure_context_risk',
        '预盈利失败上下文风险',
        'entry 早期尚未形成盈利、同时价格回落时，对 pre-profit breakout failure 的上下文风险。',
        'exit_conditional',
    ),
    StockLifecycleFragilityFactorSpec(
        'low10_exit_context_risk',
        'low10 退出上下文风险',
        '持有期内价格向 low10 退出条件靠近时的上下文风险。',
        'exit_conditional',
    ),
    StockLifecycleFragilityFactorSpec(
        'risk_off_exit_context_risk',
        '风险退出上下文风险',
        '持有期暴露落入 TRANS_DOWN / RISK_OFF 等弱状态时，对 risk-off exit 的上下文风险。',
        'exit_conditional',
    ),
)


def build_stock_lifecycle_fragility_catalog() -> list[dict[str, Any]]:
    return [item.as_dict() for item in _CATALOG]


def list_stock_lifecycle_fragility_factor_ids() -> list[str]:
    return [item.factor_id for item in _CATALOG]


def get_stock_lifecycle_fragility_factor_spec(factor_id: str) -> StockLifecycleFragilityFactorSpec:
    key = str(factor_id or '').strip().lower()
    for item in _CATALOG:
        if item.factor_id == key:
            return item
    raise KeyError(f'unknown stock lifecycle fragility factor: {factor_id}')
