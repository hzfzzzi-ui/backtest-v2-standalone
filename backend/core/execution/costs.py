from __future__ import annotations

from dataclasses import dataclass

from backend.core.config.models import CostConfig
from backend.core.core.types import Side


@dataclass(slots=True)
class CostBreakdown:
    commission: float
    stamp_tax: float
    slippage: float


def compute_costs(
    side: Side,
    qty: int,
    price: float,
    cfg: CostConfig,
    stamp_tax_sell: bool = True,
    reference_price: float | None = None,
    fill_price: float | None = None,
) -> CostBreakdown:
    notional = float(qty) * float(price)
    commission = max(cfg.commission_min, notional * cfg.commission_rate)
    stamp_tax = notional * cfg.stamp_tax_rate if (side == Side.SELL and stamp_tax_sell) else 0.0
    if cfg.slippage_mode == "price_adjustment_only":
        ref_px = float(reference_price if reference_price is not None else price)
        fill_px = float(fill_price if fill_price is not None else price)
        slippage = abs(fill_px - ref_px) * float(qty)
    else:
        slippage = float(qty) * float(reference_price if reference_price is not None else price) * (cfg.slippage_bps / 10000.0)
    return CostBreakdown(commission=commission, stamp_tax=stamp_tax, slippage=slippage)
