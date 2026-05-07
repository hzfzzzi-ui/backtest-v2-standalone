from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StockAlphaFactorSpec:
    factor_id: str
    name_zh: str
    description: str
    dependencies: tuple[str, ...]
    frequency: str = "daily"
    asof_policy: str = "close_eod_same_day"
    normalization: str = "cross_sectional_zscore_and_pct_rank"
    interpretability_note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_CATALOG: tuple[StockAlphaFactorSpec, ...] = (
    StockAlphaFactorSpec(
        factor_id="breakout_distance",
        name_zh="突破距离",
        description="收盘价相对过去45日高点的距离，用于衡量右侧突破接近程度。",
        dependencies=("close", "high"),
        interpretability_note="值越高，表示越接近或越突破前高。",
    ),
    StockAlphaFactorSpec(
        factor_id="residual_strength",
        name_zh="残差强度",
        description="个股20日收益相对当日横截面中位数收益的偏离，用于刻画相对强弱。",
        dependencies=("close",),
        interpretability_note="值越高，表示相对市场横截面更强。",
    ),
    StockAlphaFactorSpec(
        factor_id="trend_quality",
        name_zh="趋势质量",
        description="20日收益相对20日波动的比值，用于衡量趋势平滑程度。",
        dependencies=("close",),
        interpretability_note="值越高，表示上涨更平滑、噪音更低。",
    ),
    StockAlphaFactorSpec(
        factor_id="volatility_penalty",
        name_zh="波动惩罚",
        description="20日收益波动率的相反数，用于惩罚高波动标的。",
        dependencies=("close",),
        interpretability_note="值越高，表示短期波动更低。",
    ),
    StockAlphaFactorSpec(
        factor_id="liquidity_quality",
        name_zh="流动性质量",
        description="过去20日成交额均值的对数，用于表征交易可实现性。",
        dependencies=("amount",),
        interpretability_note="值越高，表示成交额更充足、交易实现性更好。",
    ),
)


def build_stock_alpha_factor_catalog() -> list[dict[str, Any]]:
    return [item.as_dict() for item in _CATALOG]


def get_stock_alpha_factor_spec(factor_id: str) -> StockAlphaFactorSpec:
    key = str(factor_id or "").strip().lower()
    for item in _CATALOG:
        if item.factor_id == key:
            return item
    raise KeyError(f"unknown stock alpha factor: {factor_id}")


def list_stock_alpha_factor_ids() -> list[str]:
    return [item.factor_id for item in _CATALOG]
