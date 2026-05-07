from __future__ import annotations

import re

from .models import BacktestConfig

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_config(cfg: BacktestConfig) -> None:
    if cfg.universe.start > cfg.universe.end:
        raise ValueError("universe.start must be <= universe.end")
    if not cfg.universe.symbols:
        raise ValueError("universe.symbols must not be empty")
    for table, mapping in cfg.schema_mapping.items():
        if not _IDENT.match(table):
            raise ValueError(f"invalid table name: {table}")
        required = ["date", "symbol", "open", "high", "low", "close"]
        for key in required:
            if key not in mapping or not mapping[key]:
                raise ValueError(f"schema_mapping[{table}] missing required key: {key}")
            if not _IDENT.match(mapping[key]):
                raise ValueError(f"invalid column name: {mapping[key]}")
    if cfg.execution.tick_size <= 0:
        raise ValueError("execution.tick_size must be > 0")
    if cfg.execution.lot_size <= 0:
        raise ValueError("execution.lot_size must be > 0")
    allowed_prev_close_policies = {"disable_limit_check", "reject_all_trades_on_missing_prev_close"}
    if cfg.data_scope.prev_close_missing_policy not in allowed_prev_close_policies:
        raise ValueError(
            "data_scope.prev_close_missing_policy must be one of "
            f"{sorted(allowed_prev_close_policies)}"
        )
    if cfg.costs.slippage_mode not in {"price_adjustment_only", "cost_only"}:
        raise ValueError("costs.slippage_mode must be 'price_adjustment_only' or 'cost_only'")
    if cfg.execution.dividend_cash_timing_mode not in {"ex_date", "pay_date"}:
        raise ValueError("execution.dividend_cash_timing_mode must be 'ex_date' or 'pay_date'")
