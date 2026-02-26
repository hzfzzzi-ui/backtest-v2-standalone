from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any, Dict


@dataclass(slots=True)
class DBConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str


@dataclass(slots=True)
class DBRuntimeConfig:
    statement_timeout_ms: int = 60000


@dataclass(slots=True)
class UniverseConfig:
    symbols: list[str]
    benchmark: str
    start: date
    end: date
    benchmark_compare_symbol: str = "000001.SH"


@dataclass(slots=True)
class DataSourceConfig:
    stocks_table: str = "pams_ohlcv_daily"
    index_table: str = "pit_index_daily"
    prefer_index_table: bool = True
    allow_cn_index_in_stocks_table: bool = False
    cn_index_filter_column: str = "market"
    cn_index_filter_value: str = "CN_INDEX"


@dataclass(slots=True)
class ExecutionConfig:
    engine_mode: str = "SLOW_AUDIT"
    profile: str = "basic"
    lot_size: int = 100
    tick_size: float = 0.01
    limit_pct_default: float = 0.10
    limit_pct_star: float = 0.05
    limit_pct_kcb_gem: float = 0.20
    liquidity_cap_pct: float = 0.10
    allow_liquidity_without_volume: bool = False
    t_plus_one: bool = True
    t_plus_one_cash: bool = False
    limit_price_epsilon_mode: str = "tick_or_default"
    limit_price_epsilon_default: float = 0.01
    dedup_same_day: bool = True
    block_buy_if_holding: bool = True
    allow_pyramiding: bool = False
    skip_if_no_cash: bool = True


@dataclass(slots=True)
class SizingConfig:
    mode: str = "fixed_qty"
    order_value: float = 10000.0
    reserve_cash_ratio: float = 0.02
    lot_size: int = 100
    # "OFF" keeps legacy sizing behavior.
    # "LOT100_MIN1LOT": dynamic order_value ensures at least 1 lot purchasable when cash allows.
    # "ODDLOT_1": research-only odd-lot mode.
    univote_lot_mode: str = "OFF"


@dataclass(slots=True)
class CostConfig:
    commission_rate: float = 0.0003
    commission_min: float = 5.0
    stamp_tax_rate: float = 0.001
    slippage_bps: float = 2.0
    slippage_mode: str = "price_adjustment_only"


@dataclass(slots=True)
class DataScopeConfig:
    extend_prev_close: bool = True
    prev_close_missing_policy: str = "disable_limit_check"


@dataclass(slots=True)
class StrategyConfig:
    name: str = "sma_cross"
    fast: int = 5
    slow: int = 20
    order_size: int = 1000
    trend_ma: int = 200
    use_benchmark_regime: bool = False
    atr_n: int = 14
    atr_k: float = 2.5
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BacktestConfig:
    db: DBConfig
    db_runtime: DBRuntimeConfig
    universe: UniverseConfig
    data_source: DataSourceConfig
    schema_mapping: Dict[str, Dict[str, str]]
    data_scope: DataScopeConfig = field(default_factory=DataScopeConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    sizing: SizingConfig = field(default_factory=SizingConfig)
    costs: CostConfig = field(default_factory=CostConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    initial_capital: float = 100000.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
