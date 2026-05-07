from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import pandas as pd
from backend.core.engine_vector.factor_insertion_contracts import resolve_holding_exit_fragility_contract


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_path(value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = (_repo_root() / path).resolve()
    return path.resolve()


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True, slots=True)
class HoldingExitFragilitySnapshot:
    enabled: bool = False
    valid: bool = False
    gate_on: bool = False
    observation_date: date | None = None
    source_kind: str = "off"
    factor_id: str = ""
    action: str = ""
    risk_bucket_top_pct: float = 0.2
    risk_threshold: float = 0.8
    gate_status: str = ""
    gate_reason: str = ""
    score_source: str = ""
    score_map: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "score_map", MappingProxyType(dict(self.score_map or {})))


@dataclass(frozen=True, slots=True)
class _FragilityDay:
    observation_date: date
    gate_on: bool
    gate_status: str
    gate_reason: str
    score_map: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "score_map", MappingProxyType(dict(self.score_map or {})))


@dataclass(frozen=True, slots=True)
class _FragilityRuntime:
    factor_id: str
    action: str
    risk_bucket_top_pct: float
    risk_threshold: float
    score_source: str
    day_map: Mapping[date, _FragilityDay]

    def __post_init__(self) -> None:
        object.__setattr__(self, "day_map", MappingProxyType(dict(self.day_map or {})))

    def snapshot_for_day(self, day: date) -> HoldingExitFragilitySnapshot:
        fragility_day = self.day_map.get(day)
        if fragility_day is None:
            return HoldingExitFragilitySnapshot(
                enabled=True,
                valid=True,
                gate_on=False,
                observation_date=day,
                source_kind="daily_factor_snapshot",
                factor_id=self.factor_id,
                action=self.action,
                risk_bucket_top_pct=self.risk_bucket_top_pct,
                risk_threshold=self.risk_threshold,
                gate_status="no_observation_for_day",
                gate_reason="daily_factor_snapshot_unavailable",
                score_source=self.score_source,
            )
        return HoldingExitFragilitySnapshot(
            enabled=True,
            valid=True,
            gate_on=bool(fragility_day.gate_on),
            observation_date=fragility_day.observation_date,
            source_kind="daily_factor_snapshot",
            factor_id=self.factor_id,
            action=self.action,
            risk_bucket_top_pct=self.risk_bucket_top_pct,
            risk_threshold=self.risk_threshold,
            gate_status=str(fragility_day.gate_status or ""),
            gate_reason=str(fragility_day.gate_reason or ""),
            score_source=self.score_source,
            score_map=dict(fragility_day.score_map),
        )


@lru_cache(maxsize=16)
def _load_daily_factor_runtime_cached(
    *,
    factor_snapshot_path: str,
    factor_snapshot_mtime_ns: int,
    factor_id: str,
    score_field: str,
    available_column: str,
    date_column: str,
    symbol_column: str,
    action: str,
    risk_bucket_top_pct: float,
    score_source: str,
) -> _FragilityRuntime:
    del factor_snapshot_mtime_ns
    factor_df = pd.read_csv(factor_snapshot_path)
    if date_column not in factor_df.columns or symbol_column not in factor_df.columns:
        raise ValueError("holding_exit_fragility daily factor snapshot missing required columns")
    if score_field not in factor_df.columns:
        raise ValueError(f"holding_exit_fragility missing score field: {score_field}")
    if factor_id and "factor_id" not in factor_df.columns:
        raise ValueError("holding_exit_fragility daily factor snapshot missing factor_id column")

    factor_df = factor_df.copy()
    if factor_id:
        factor_df = factor_df.loc[factor_df["factor_id"].astype(str).str.strip() == factor_id]
    factor_df[symbol_column] = factor_df[symbol_column].astype(str).str.lower()
    factor_df[date_column] = pd.to_datetime(factor_df[date_column], errors="coerce").dt.date
    factor_df = factor_df.dropna(subset=[date_column, symbol_column])
    factor_df["__score"] = pd.to_numeric(factor_df[score_field], errors="coerce")
    factor_df["__available"] = (
        factor_df[available_column].map(lambda value: _as_bool(value, default=True))
        if available_column in factor_df.columns
        else True
    )

    day_map: dict[date, _FragilityDay] = {}
    for observation_date, day_df in factor_df.groupby(date_column, sort=True):
        usable_df = day_df.loc[day_df["__available"] & day_df["__score"].notna()].copy()
        if usable_df.empty:
            day_map[observation_date] = _FragilityDay(
                observation_date=observation_date,
                gate_on=False,
                gate_status="no_available_scores",
                gate_reason="daily_factor_snapshot_unavailable",
                score_map={},
            )
            continue
        grouped = usable_df.groupby(symbol_column)["__score"].last()
        day_map[observation_date] = _FragilityDay(
            observation_date=observation_date,
            gate_on=True,
            gate_status="ready",
            gate_reason="",
            score_map={str(symbol).lower(): float(value) for symbol, value in grouped.items()},
        )

    return _FragilityRuntime(
        factor_id=str(factor_id or "").strip(),
        action=str(action or "").strip(),
        risk_bucket_top_pct=float(risk_bucket_top_pct),
        risk_threshold=max(0.0, min(1.0, 1.0 - float(risk_bucket_top_pct))),
        score_source=str(score_source or "").strip(),
        day_map=day_map,
    )


def resolve_holding_exit_fragility_snapshot(
    asset_context: Mapping[str, Any] | None,
    *,
    day: date,
) -> HoldingExitFragilitySnapshot:
    context = dict(asset_context or {})
    raw_cfg = context.get("holding_exit_fragility")
    if not isinstance(raw_cfg, Mapping):
        return HoldingExitFragilitySnapshot()

    enabled = _as_bool(raw_cfg.get("enabled"), default=False)
    if not enabled:
        return HoldingExitFragilitySnapshot()
    contract = resolve_holding_exit_fragility_contract(raw_cfg)
    if not contract.valid:
        return HoldingExitFragilitySnapshot(
            enabled=True,
            valid=False,
            gate_on=False,
            observation_date=day,
            source_kind=str(raw_cfg.get("source_kind") or "").strip().lower() or "off",
            factor_id=str(raw_cfg.get("factor_id") or "").strip(),
            action=str(contract.action or ""),
            gate_status=str(contract.status or "invalid_contract"),
            gate_reason=str(contract.reason or "invalid_factor_insertion_contract"),
            score_source=str(raw_cfg.get("score_source") or "").strip(),
        )

    apply_layer = str(raw_cfg.get("apply_layer") or "holding_exit").strip().lower()
    if apply_layer not in {"holding_exit", "holding", "exit"}:
        return HoldingExitFragilitySnapshot(
            enabled=True,
            valid=False,
            gate_on=False,
            observation_date=day,
            source_kind=str(raw_cfg.get("source_kind") or "").strip().lower() or "off",
            factor_id=str(raw_cfg.get("factor_id") or "").strip(),
            action=str(contract.action or ""),
            gate_status="invalid_layer",
            gate_reason=f"unsupported_apply_layer:{apply_layer}",
            score_source=str(raw_cfg.get("score_source") or "").strip(),
        )

    source_kind = str(raw_cfg.get("source_kind") or "daily_factor_snapshot").strip().lower()
    if source_kind != "daily_factor_snapshot":
        return HoldingExitFragilitySnapshot(
            enabled=True,
            valid=False,
            gate_on=False,
            observation_date=day,
            source_kind=source_kind,
            factor_id=str(raw_cfg.get("factor_id") or "").strip(),
            action=str(contract.action or ""),
            gate_status="invalid_source_kind",
            gate_reason=f"unsupported_source_kind:{source_kind}",
            score_source=str(raw_cfg.get("score_source") or "").strip(),
        )

    action = str(contract.action or "")
    if not action:
        return HoldingExitFragilitySnapshot(
            enabled=True,
            valid=False,
            gate_on=False,
            observation_date=day,
            source_kind=source_kind,
            factor_id=str(raw_cfg.get("factor_id") or "").strip(),
            action="",
            gate_status="invalid_action",
            gate_reason="unsupported_action",
            score_source=str(raw_cfg.get("score_source") or "").strip(),
        )

    factor_snapshot_path = _resolve_path(raw_cfg.get("factor_snapshot_path") or raw_cfg.get("snapshot_path"))
    if factor_snapshot_path is None:
        return HoldingExitFragilitySnapshot(
            enabled=True,
            valid=False,
            gate_on=False,
            observation_date=day,
            source_kind=source_kind,
            factor_id=str(raw_cfg.get("factor_id") or "").strip(),
            action=action,
            gate_status="missing_factor_snapshot_path",
            gate_reason="holding_exit_fragility_paths_missing",
            score_source=str(raw_cfg.get("score_source") or "").strip(),
        )
    if not factor_snapshot_path.exists():
        return HoldingExitFragilitySnapshot(
            enabled=True,
            valid=False,
            gate_on=False,
            observation_date=day,
            source_kind=source_kind,
            factor_id=str(raw_cfg.get("factor_id") or "").strip(),
            action=action,
            gate_status="missing_factor_snapshot_file",
            gate_reason="holding_exit_fragility_files_missing",
            score_source=str(raw_cfg.get("score_source") or "").strip(),
        )

    factor_id = str(raw_cfg.get("factor_id") or "").strip()
    score_field = str(raw_cfg.get("score_field") or "rank_value").strip()
    available_column = str(raw_cfg.get("available_column") or "available").strip()
    date_column = str(raw_cfg.get("date_column") or "date").strip()
    symbol_column = str(raw_cfg.get("symbol_column") or "symbol").strip()
    risk_bucket_top_pct = float(raw_cfg.get("risk_bucket_top_pct", raw_cfg.get("top_pct", 0.2)) or 0.2)
    score_source = str(raw_cfg.get("score_source") or f"{factor_snapshot_path.stem}:{factor_id}").strip()

    runtime = _load_daily_factor_runtime_cached(
        factor_snapshot_path=str(factor_snapshot_path),
        factor_snapshot_mtime_ns=factor_snapshot_path.stat().st_mtime_ns,
        factor_id=factor_id,
        score_field=score_field,
        available_column=available_column,
        date_column=date_column,
        symbol_column=symbol_column,
        action=action,
        risk_bucket_top_pct=risk_bucket_top_pct,
        score_source=score_source,
    )
    return runtime.snapshot_for_day(day)
