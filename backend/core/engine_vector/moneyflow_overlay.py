from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
from backend.core.engine_vector.factor_insertion_contracts import resolve_moneyflow_overlay_contract


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


def _as_positive_int(value: Any, *, default: int = 0) -> int:
    try:
        parsed = int(value)
    except Exception:
        return int(default)
    return parsed if parsed > 0 else int(default)


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    try:
        ts = pd.Timestamp(value)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    return ts.date()


def _score_map_from_series(series: pd.Series, *, lower_is_better: bool) -> dict[str, float]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return {}
    grouped = clean.groupby(clean.index).last()
    if grouped.empty:
        return {}
    if len(grouped) == 1:
        symbol = str(grouped.index[0]).lower()
        return {symbol: 0.5}
    ranks = grouped.rank(method="average", ascending=bool(lower_is_better))
    scaled = 1.0 - ((ranks - 1.0) / float(len(grouped) - 1))
    return {
        str(symbol).lower(): float(value)
        for symbol, value in scaled.items()
    }


@dataclass(frozen=True, slots=True)
class MoneyflowOverlaySnapshot:
    enabled: bool = False
    mode: str = "off"
    gate_on: bool = False
    observation_date: date | None = None
    execution_date: date | None = None
    gate_status: str = ""
    gate_reason: str = ""
    score_field: str = ""
    score_source: str = ""
    band_limit: int = 0
    score_map: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _OverlayMonth:
    observation_date: date
    execution_date: date | None
    gate_on: bool
    gate_status: str
    gate_reason: str
    score_map: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class _OverlayRuntime:
    mode: str
    score_field: str
    score_source: str
    months: tuple[_OverlayMonth, ...]

    def snapshot_for_day(self, day: date) -> MoneyflowOverlaySnapshot:
        if not self.months:
            return MoneyflowOverlaySnapshot(
                enabled=True,
                mode=self.mode,
                gate_on=False,
                score_field=self.score_field,
                score_source=self.score_source,
            )
        observation_days = [month.observation_date for month in self.months]
        idx = bisect_right(observation_days, day) - 1
        if idx < 0:
            return MoneyflowOverlaySnapshot(
                enabled=True,
                mode=self.mode,
                gate_on=False,
                score_field=self.score_field,
                score_source=self.score_source,
                gate_status="pending_first_observation",
                gate_reason="no_observation_available_yet",
            )
        month = self.months[idx]
        return MoneyflowOverlaySnapshot(
            enabled=True,
            mode=self.mode,
            gate_on=bool(month.gate_on),
            observation_date=month.observation_date,
            execution_date=month.execution_date,
            gate_status=month.gate_status,
            gate_reason=month.gate_reason,
            score_field=self.score_field,
            score_source=self.score_source,
            score_map=dict(month.score_map),
        )


@lru_cache(maxsize=16)
def _load_overlay_runtime_cached(
    *,
    factor_panel_path: str,
    factor_panel_mtime_ns: int,
    coverage_ledger_path: str,
    coverage_ledger_mtime_ns: int,
    score_field: str,
    lower_is_better: bool,
    mode: str,
    score_source: str,
) -> _OverlayRuntime:
    del factor_panel_mtime_ns, coverage_ledger_mtime_ns
    factor_df = pd.read_csv(factor_panel_path)
    ledger_df = pd.read_csv(coverage_ledger_path)

    if score_field not in factor_df.columns:
        raise ValueError(f"moneyflow overlay missing score field: {score_field}")
    if "symbol" not in factor_df.columns or "observation_date" not in factor_df.columns:
        raise ValueError("moneyflow overlay factor panel missing required columns")

    factor_df = factor_df.copy()
    factor_df["symbol"] = factor_df["symbol"].astype(str).str.lower()
    factor_df["observation_date"] = pd.to_datetime(factor_df["observation_date"], errors="coerce").dt.date
    if "execution_date" in factor_df.columns:
        factor_df["execution_date"] = pd.to_datetime(factor_df["execution_date"], errors="coerce").dt.date
    else:
        factor_df["execution_date"] = pd.Series([None] * len(factor_df), index=factor_df.index, dtype=object)
    factor_df = factor_df.dropna(subset=["symbol", "observation_date"])
    if "monthly_factor_valid" in factor_df.columns:
        factor_df = factor_df.loc[factor_df["monthly_factor_valid"].map(lambda value: _as_bool(value, default=True))]
    if "month_end_valid" in factor_df.columns:
        factor_df = factor_df.loc[factor_df["month_end_valid"].map(lambda value: _as_bool(value, default=True))]

    ledger_df = ledger_df.copy()
    trade_date_col = "trade_date" if "trade_date" in ledger_df.columns else "observation_date"
    if trade_date_col not in ledger_df.columns:
        raise ValueError("moneyflow overlay coverage ledger missing trade_date")
    ledger_df["trade_date"] = pd.to_datetime(ledger_df[trade_date_col], errors="coerce").dt.date
    ledger_df = ledger_df.dropna(subset=["trade_date"])

    gate_by_observation: dict[date, tuple[bool, str, str]] = {}
    for row in ledger_df.itertuples(index=False):
        obs_date = _as_date(getattr(row, "trade_date", None))
        if obs_date is None:
            continue
        gate_on = _as_bool(getattr(row, "allow_in_research", None), default=False)
        gate_status = str(getattr(row, "gate_status", "") or "").strip().lower()
        gate_reason = str(getattr(row, "gate_reason", "") or "").strip()
        gate_by_observation[obs_date] = (gate_on, gate_status, gate_reason)

    months: list[_OverlayMonth] = []
    for observation_date, month_df in factor_df.groupby("observation_date", sort=True):
        score_map = _score_map_from_series(
            month_df.set_index("symbol")[score_field],
            lower_is_better=bool(lower_is_better),
        )
        if not score_map:
            continue
        execution_date = _as_date(month_df["execution_date"].dropna().iloc[0]) if "execution_date" in month_df.columns and month_df["execution_date"].notna().any() else None
        gate_on, gate_status, gate_reason = gate_by_observation.get(
            observation_date,
            (
                False,
                str(month_df["gate_status"].iloc[0]).strip().lower() if "gate_status" in month_df.columns else "missing_coverage_gate",
                str(month_df["gate_reason"].iloc[0]).strip() if "gate_reason" in month_df.columns else "missing_coverage_gate",
            ),
        )
        months.append(
            _OverlayMonth(
                observation_date=observation_date,
                execution_date=execution_date,
                gate_on=bool(gate_on),
                gate_status=str(gate_status or ""),
                gate_reason=str(gate_reason or ""),
                score_map=score_map,
            )
        )
    return _OverlayRuntime(
        mode=str(mode or "off").strip().lower() or "off",
        score_field=str(score_field or "").strip(),
        score_source=str(score_source or "").strip(),
        months=tuple(months),
    )


@lru_cache(maxsize=16)
def _load_daily_factor_snapshot_runtime_cached(
    *,
    factor_snapshot_path: str,
    factor_snapshot_mtime_ns: int,
    factor_id: str,
    score_field: str,
    available_column: str,
    lower_is_better: bool,
    mode: str,
    score_source: str,
    date_column: str,
    symbol_column: str,
) -> _OverlayRuntime:
    del factor_snapshot_mtime_ns
    factor_df = pd.read_csv(factor_snapshot_path)

    if date_column not in factor_df.columns or symbol_column not in factor_df.columns:
        raise ValueError("moneyflow overlay daily factor snapshot missing required columns")
    if score_field not in factor_df.columns:
        raise ValueError(f"moneyflow overlay missing score field: {score_field}")
    if factor_id and "factor_id" not in factor_df.columns:
        raise ValueError("moneyflow overlay daily factor snapshot missing factor_id column")

    factor_df = factor_df.copy()
    if factor_id:
        factor_df = factor_df.loc[factor_df["factor_id"].astype(str).str.strip() == factor_id]
    factor_df[symbol_column] = factor_df[symbol_column].astype(str).str.lower()
    factor_df[date_column] = pd.to_datetime(factor_df[date_column], errors="coerce").dt.date
    factor_df = factor_df.dropna(subset=[symbol_column, date_column])
    if available_column in factor_df.columns:
        factor_df["__available"] = factor_df[available_column].map(lambda value: _as_bool(value, default=True))
    else:
        factor_df["__available"] = True

    months: list[_OverlayMonth] = []
    for observation_date, day_df in factor_df.groupby(date_column, sort=True):
        usable_df = day_df.loc[day_df["__available"]]
        if usable_df.empty:
            score_map: Mapping[str, float] = {}
            gate_on = False
            gate_status = "no_available_scores"
            gate_reason = "daily_factor_snapshot_unavailable"
        else:
            score_map = _score_map_from_series(
                usable_df.set_index(symbol_column)[score_field],
                lower_is_better=bool(lower_is_better),
            )
            gate_on = bool(score_map)
            gate_status = "tradable" if gate_on else "empty_score_map"
            gate_reason = "" if gate_on else "daily_factor_snapshot_empty"
        months.append(
            _OverlayMonth(
                observation_date=observation_date,
                execution_date=observation_date,
                gate_on=bool(gate_on),
                gate_status=str(gate_status or ""),
                gate_reason=str(gate_reason or ""),
                score_map=score_map,
            )
        )
    return _OverlayRuntime(
        mode=str(mode or "off").strip().lower() or "off",
        score_field=str(score_field or "").strip(),
        score_source=str(score_source or "").strip(),
        months=tuple(months),
    )


def resolve_moneyflow_overlay_snapshot(
    asset_context: Mapping[str, Any] | None,
    *,
    day: date,
) -> MoneyflowOverlaySnapshot:
    context = dict(asset_context or {})
    raw_cfg = context.get("moneyflow_overlay")
    cfg = dict(raw_cfg or {}) if isinstance(raw_cfg, Mapping) else {}
    enabled = _as_bool(cfg.get("enabled"), default=False)
    mode = str(cfg.get("mode") or "off").strip().lower() or "off"
    band_limit = _as_positive_int(cfg.get("band_limit"), default=0)
    if not enabled or mode in {"", "off"}:
        return MoneyflowOverlaySnapshot(enabled=False, mode="off")
    contract = resolve_moneyflow_overlay_contract(cfg)
    if not contract.valid:
        return MoneyflowOverlaySnapshot(
            enabled=True,
            mode=str(contract.action or mode or "off"),
            gate_on=False,
            gate_status=str(contract.status or "invalid_contract"),
            gate_reason=str(contract.reason or "invalid_factor_insertion_contract"),
            score_field=str(cfg.get("score_field") or "monthly_divergence_rate").strip(),
            score_source=str(cfg.get("score_source") or "").strip(),
            band_limit=int(band_limit),
        )

    source_kind = str(cfg.get("source_kind") or "monthly_factor_panel").strip().lower() or "monthly_factor_panel"
    if source_kind in {"daily_factor_snapshot", "factor_snapshot"}:
        factor_snapshot = _resolve_path(cfg.get("factor_snapshot_path"))
        factor_id = str(cfg.get("factor_id") or "").strip()
        score_field = str(cfg.get("score_field") or "rank_value").strip()
        score_source = str(cfg.get("score_source") or "").strip()
        lower_is_better = _as_bool(cfg.get("lower_is_better"), default=True)
        date_column = str(cfg.get("date_column") or "date").strip()
        symbol_column = str(cfg.get("symbol_column") or "symbol").strip()
        available_column = str(cfg.get("available_column") or "available").strip()
        if factor_snapshot is None:
            return MoneyflowOverlaySnapshot(
                enabled=True,
                mode=mode,
                gate_on=False,
                gate_status="missing_paths",
                gate_reason="moneyflow_overlay_paths_missing",
                score_field=score_field,
                score_source=score_source,
                band_limit=int(band_limit),
            )
        if not factor_snapshot.exists():
            return MoneyflowOverlaySnapshot(
                enabled=True,
                mode=mode,
                gate_on=False,
                gate_status="missing_files",
                gate_reason="moneyflow_overlay_files_missing",
                score_field=score_field,
                score_source=score_source,
                band_limit=int(band_limit),
            )
        runtime = _load_daily_factor_snapshot_runtime_cached(
            factor_snapshot_path=str(factor_snapshot),
            factor_snapshot_mtime_ns=factor_snapshot.stat().st_mtime_ns,
            factor_id=factor_id,
            score_field=score_field,
            available_column=available_column,
            lower_is_better=bool(lower_is_better),
            mode=mode,
            score_source=score_source or f"{factor_snapshot.parent.name}:{factor_id or score_field}",
            date_column=date_column,
            symbol_column=symbol_column,
        )
        snapshot = runtime.snapshot_for_day(day)
        return MoneyflowOverlaySnapshot(
            enabled=bool(snapshot.enabled),
            mode=str(snapshot.mode or "off"),
            gate_on=bool(snapshot.gate_on),
            observation_date=snapshot.observation_date,
            execution_date=snapshot.execution_date,
            gate_status=str(snapshot.gate_status or ""),
            gate_reason=str(snapshot.gate_reason or ""),
            score_field=str(snapshot.score_field or ""),
            score_source=str(snapshot.score_source or ""),
            band_limit=int(band_limit),
            score_map=dict(snapshot.score_map or {}),
        )

    factor_panel = _resolve_path(cfg.get("factor_panel_path"))
    coverage_ledger = _resolve_path(cfg.get("coverage_ledger_path"))
    score_field = str(cfg.get("score_field") or "monthly_divergence_rate").strip()
    score_source = str(cfg.get("score_source") or "").strip()
    lower_is_better = _as_bool(cfg.get("lower_is_better"), default=True)
    if factor_panel is None or coverage_ledger is None:
        return MoneyflowOverlaySnapshot(
            enabled=True,
            mode=mode,
            gate_on=False,
            gate_status="missing_paths",
            gate_reason="moneyflow_overlay_paths_missing",
            score_field=score_field,
            score_source=score_source,
            band_limit=int(band_limit),
        )
    if not factor_panel.exists() or not coverage_ledger.exists():
        return MoneyflowOverlaySnapshot(
            enabled=True,
            mode=mode,
            gate_on=False,
            gate_status="missing_files",
            gate_reason="moneyflow_overlay_files_missing",
            score_field=score_field,
            score_source=score_source,
            band_limit=int(band_limit),
        )

    runtime = _load_overlay_runtime_cached(
        factor_panel_path=str(factor_panel),
        factor_panel_mtime_ns=factor_panel.stat().st_mtime_ns,
        coverage_ledger_path=str(coverage_ledger),
        coverage_ledger_mtime_ns=coverage_ledger.stat().st_mtime_ns,
        score_field=score_field,
        lower_is_better=bool(lower_is_better),
        mode=mode,
        score_source=score_source or factor_panel.parent.name,
    )
    snapshot = runtime.snapshot_for_day(day)
    return MoneyflowOverlaySnapshot(
        enabled=bool(snapshot.enabled),
        mode=str(snapshot.mode or "off"),
        gate_on=bool(snapshot.gate_on),
        observation_date=snapshot.observation_date,
        execution_date=snapshot.execution_date,
        gate_status=str(snapshot.gate_status or ""),
        gate_reason=str(snapshot.gate_reason or ""),
        score_field=str(snapshot.score_field or ""),
        score_source=str(snapshot.score_source or ""),
        band_limit=int(band_limit),
        score_map=dict(snapshot.score_map or {}),
    )
