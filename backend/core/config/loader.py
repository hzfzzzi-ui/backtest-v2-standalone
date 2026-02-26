from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from .models import (
    BacktestConfig,
    CostConfig,
    DataScopeConfig,
    DataSourceConfig,
    DBConfig,
    DBRuntimeConfig,
    ExecutionConfig,
    SizingConfig,
    StrategyConfig,
    UniverseConfig,
)


def _env(key: str, fallback: Any) -> Any:
    value = os.getenv(key)
    return fallback if value is None else value


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def load_config(path: str | Path) -> tuple[BacktestConfig, str]:
    raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))

    db_raw = raw["db"]
    db = DBConfig(
        host=str(_env("PAMS_PG_HOST", db_raw["host"])),
        port=int(_env("PAMS_PG_PORT", db_raw.get("port", 5432))),
        dbname=str(_env("PAMS_PG_DBNAME", db_raw["dbname"])),
        user=str(_env("PAMS_PG_USER", db_raw["user"])),
        password=str(_env("PAMS_PG_PASSWORD", db_raw.get("password", ""))),
    )

    runtime = DBRuntimeConfig(**raw.get("db_runtime", {}))

    uni_raw = raw["universe"]
    universe = UniverseConfig(
        symbols=list(uni_raw["symbols"]),
        benchmark=str(uni_raw["benchmark"]),
        start=_parse_date(uni_raw["start"]),
        end=_parse_date(uni_raw["end"]),
        benchmark_compare_symbol=str(uni_raw.get("benchmark_compare_symbol", "000001.SH")),
    )

    cfg = BacktestConfig(
        db=db,
        db_runtime=runtime,
        universe=universe,
        data_source=DataSourceConfig(**raw.get("data_source", {})),
        schema_mapping=raw["schema_mapping"],
        data_scope=DataScopeConfig(**raw.get("data_scope", {})),
        execution=ExecutionConfig(**raw.get("execution", {})),
        sizing=SizingConfig(**raw.get("sizing", {})),
        costs=CostConfig(**raw.get("costs", {})),
        strategy=StrategyConfig(**raw.get("strategy", {})),
        initial_capital=float(raw.get("initial_capital", 100000.0)),
    )

    config_hash = hashlib.sha256(
        json.dumps(cfg.to_dict(), sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return cfg, config_hash
