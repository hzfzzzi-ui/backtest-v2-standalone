from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from backend.core.data.pg_env import env_or_file
from .models import (
    BacktestConfig,
    BenchmarkRegimeConfig,
    BreadthConfig,
    CostConfig,
    DataScopeConfig,
    DataSourceConfig,
    DBConfig,
    DBRuntimeConfig,
    ExecutionConfig,
    ExitConfig,
    MarketFilterConfig,
    RegimeEngineConfig,
    RiskBudgetConfig,
    RiskConfig,
    SizingConfig,
    StrategyConfig,
    UniverseConfig,
)


def _env(key: str, fallback: Any) -> Any:
    value = env_or_file(key)
    return fallback if value is None else value


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


_STRATEGY_CONFIG_FIELDS = frozenset(f.name for f in __import__("dataclasses").fields(StrategyConfig))


def _build_strategy_config(raw: dict[str, Any]) -> StrategyConfig:
    known = {k: v for k, v in raw.items() if k in _STRATEGY_CONFIG_FIELDS}
    extra = {k: v for k, v in raw.items() if k not in _STRATEGY_CONFIG_FIELDS}
    cfg = StrategyConfig(**known)
    cfg.params = {**cfg.params, **extra}
    return cfg


def load_config(path: str | Path) -> tuple[BacktestConfig, str]:
    raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))

    db_raw = raw["db"]
    db = DBConfig(
        host=str(_env("PAMS_PG_HOST", db_raw["host"])),
        port=int(_env("PAMS_PG_PORT", db_raw.get("port", 5432))),
        dbname=str(_env("PAMS_PG_DBNAME", db_raw["dbname"])),
        user=str(_env("PAMS_PG_USER", db_raw["user"])),
        password=str(_env("PAMS_PG_PASSWORD", _env("POSTGRES_PASSWORD", db_raw.get("password", "")))),
    )

    runtime = DBRuntimeConfig(**raw.get("db_runtime", {}))

    uni_raw = raw["universe"]
    universe = UniverseConfig(
        symbols=list(uni_raw["symbols"]),
        benchmark=str(uni_raw["benchmark"]),
        start=_parse_date(uni_raw["start"]),
        end=_parse_date(uni_raw["end"]),
        benchmark_compare_symbol=str(uni_raw.get("benchmark_compare_symbol", "000001.SH")),
        allow_low_fidelity_history=bool(uni_raw.get("allow_low_fidelity_history", False)),
    )

    # 旧字段静默忽略（向后兼容）
    _sizing_raw = {k: v for k, v in raw.get("sizing", {}).items()
                   if k not in ("enable_volatility_sizing", "vol_target_risk_pct")}
    _risk_raw = {k: v for k, v in raw.get("risk", {}).items()
                 if k not in ("enable_drawdown_breaker", "drawdown_breaker_pct", "drawdown_breaker_recover_pct")}
    _exit_raw = raw.get("exit", {})

    cfg = BacktestConfig(
        db=db,
        db_runtime=runtime,
        universe=universe,
        data_source=DataSourceConfig(**raw.get("data_source", {})),
        schema_mapping=raw["schema_mapping"],
        data_scope=DataScopeConfig(**raw.get("data_scope", {})),
        execution=ExecutionConfig(**raw.get("execution", {})),
        sizing=SizingConfig(**_sizing_raw),
        costs=CostConfig(**raw.get("costs", {})),
        exit=ExitConfig(**_exit_raw),
        risk=RiskConfig(**_risk_raw),
        risk_budget=RiskBudgetConfig(**raw.get("risk_budget", {})),
        regime_engine=RegimeEngineConfig(**raw.get("regime_engine", {})),
        market_filter=MarketFilterConfig(**raw.get("market_filter", {})),
        benchmark_regime=BenchmarkRegimeConfig(**raw.get("benchmark_regime", {})),
        breadth=BreadthConfig(**raw.get("breadth", {})),
        strategy=_build_strategy_config(raw.get("strategy", {})),
        initial_capital=float(raw.get("initial_capital", 100000.0)),
    )

    config_hash = hashlib.sha256(
        json.dumps(cfg.to_dict(), sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return cfg, config_hash
