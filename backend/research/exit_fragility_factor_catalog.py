from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ExitFragilityFactorSpec:
    factor_id: str
    provider_attr: str
    name_zh: str
    description: str
    relation_to_exit: str
    direction: str
    frequency: str = 'daily'
    asof_policy: str = 'close_eod_same_day'
    interpretability_note: str = ''

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_CATALOG: tuple[ExitFragilityFactorSpec, ...] = (
    ExitFragilityFactorSpec('breakout_margin_raw', '_breakout_margin_raw', '突破原始边际', '突破当日离前高的原始超额幅度。', 'pre_profit_breakout_failure', 'higher_is_worse'),
    ExitFragilityFactorSpec('breakout_margin_score', '_breakout_margin_score', '突破边际得分', '主线 breakout margin score。', 'pre_profit_breakout_failure', 'higher_is_worse'),
    ExitFragilityFactorSpec('breakout_fade_raw', '_breakout_fade_raw', '突破回落幅度', '突破当日从高点回落的原始幅度。', 'pre_profit_breakout_failure', 'higher_is_worse'),
    ExitFragilityFactorSpec('breakout_open_gap_raw', '_breakout_open_gap_raw', '突破跳空幅度', '突破当日跳空缺口的原始幅度。', 'pre_profit_breakout_failure', 'higher_is_worse'),
    ExitFragilityFactorSpec('breakout_quality_score', '_breakout_quality_score', '突破质量得分', '主线 breakout quality score。', 'pre_profit_breakout_failure', 'lower_is_worse', interpretability_note='该因子在 fragility score 中会反向使用。'),
)


def build_exit_fragility_factor_catalog() -> list[dict[str, Any]]:
    return [item.as_dict() for item in _CATALOG]


def get_exit_fragility_factor_spec(factor_id: str) -> ExitFragilityFactorSpec:
    key = str(factor_id or '').strip().lower()
    for item in _CATALOG:
        if item.factor_id == key:
            return item
    raise KeyError(f'unknown exit fragility factor: {factor_id}')


def list_exit_fragility_factor_ids() -> list[str]:
    return [item.factor_id for item in _CATALOG]
