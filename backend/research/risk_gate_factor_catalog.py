from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RiskGateFactorSpec:
    factor_id: str
    name_zh: str
    description: str
    factor_role: str
    direction: str = "higher_is_worse"
    frequency: str = "daily"
    asof_policy: str = "close_eod_same_day"
    interpretability_note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_CATALOG: tuple[RiskGateFactorSpec, ...] = (
    RiskGateFactorSpec("benchmark_regime_off_risk", "基准风控关闭风险", "基准 regime 未开启时的账户级风险暴露；研究层按日重复到所有候选。", "account_gate"),
    RiskGateFactorSpec("strong_risk_on_absence_risk", "强风险开缺失风险", "强风险开未成立时的账户级上下文风险；研究层按日重复到所有候选。", "account_context"),
    RiskGateFactorSpec("regime_blocked_breakout_risk", "基准关闭下突破阻断风险", "当 breakout/pullback-overlap 触发但 benchmark regime 关闭时的阻断风险。", "direct_gate"),
    RiskGateFactorSpec("breakout_quality_fail_risk", "突破质量失败风险", "处于 breakout quality scope 内且未通过 quality gate 时的直接失败风险。", "direct_veto"),
    RiskGateFactorSpec("breakout_quality_gate_shortfall_risk", "突破质量短板风险", "breakout quality score 低于 quality gate floor 的短板幅度。", "direct_veto"),
    RiskGateFactorSpec("bull_quality_residual_shortfall_risk", "牛市残差门槛短板风险", "在 BULL 且 bull breakout quality veto 生效时，residual score 低于门槛的短板幅度。", "bull_veto"),
    RiskGateFactorSpec("bull_quality_margin_shortfall_risk", "牛市突破边际短板风险", "在 BULL 且 bull breakout quality veto 生效时，breakout margin score 低于门槛的短板幅度。", "bull_veto"),
)


def build_risk_gate_factor_catalog() -> list[dict[str, Any]]:
    return [item.as_dict() for item in _CATALOG]


def get_risk_gate_factor_spec(factor_id: str) -> RiskGateFactorSpec:
    key = str(factor_id or "").strip().lower()
    for item in _CATALOG:
        if item.factor_id == key:
            return item
    raise KeyError(f"unknown risk gate factor: {factor_id}")


def list_risk_gate_factor_ids() -> list[str]:
    return [item.factor_id for item in _CATALOG]
