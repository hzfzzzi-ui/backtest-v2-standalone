from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.api.backtest_v2.protocol import ARTIFACT_FILENAMES
from backend.api.shared.json_utils import sanitize_json
from backend.core.tools.experiment_artifact_access import manifest_artifact_rel

SIMPLE_SURFACE_SECTIONS = frozenset(
    {
        "nav",
        "drawdown",
        "symbol_stats",
        "stage_funnel",
        "run_meta",
        "config",
        "trades",
        "daily",
        "reason_codes",
        "cash_blocked_buys_recent",
        "stock_names",
    }
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def surface_nav(exp_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    nav_rel = manifest_artifact_rel(manifest, "nav") or "nav.csv"
    frame = _read_csv(exp_dir / nav_rel)
    if frame.empty or "date" not in frame.columns:
        return []
    nav_col = None
    for candidate in ("nav", "strategy_nav", "equity", "portfolio_value"):
        if candidate in frame.columns:
            nav_col = candidate
            break
    if nav_col is None:
        return []
    rows: list[dict[str, Any]] = []
    extra_columns = [name for name in ("stock_nav", "etf_nav") if name in frame.columns]
    wanted_columns = ["date", nav_col, *extra_columns]
    for row in frame[wanted_columns].itertuples(index=False, name=None):
        try:
            payload: dict[str, Any] = {"date": str(row[0])[:10], "nav": float(row[1])}
            for index, key in enumerate(extra_columns, start=2):
                try:
                    value = float(row[index])
                except Exception:
                    continue
                if value > 0:
                    payload[key] = value
            rows.append(payload)
        except Exception:
            continue
    return rows


def surface_drawdown(nav_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    peak = None
    rows: list[dict[str, Any]] = []
    for item in nav_rows:
        try:
            nav = float(item.get("nav"))
        except Exception:
            continue
        peak = nav if peak is None else max(peak, nav)
        rows.append({"date": str(item.get("date") or "")[:10], "drawdown": ((nav - peak) / peak) if peak else 0.0})
    return rows


def surface_symbol_stats(exp_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rel = manifest_artifact_rel(manifest, "symbol_performance") or "symbol_performance.csv"
    path = exp_dir / rel
    if path.suffix.lower() == ".json":
        payload = _read_json(path)
        rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
        return sanitize_json(rows)
    frame = _read_csv(path)
    if frame.empty:
        return []
    wanted = [name for name in ("symbol", "return_pct", "max_drawdown", "trades", "net_pnl") if name in frame.columns]
    if not wanted:
        return []
    return sanitize_json(frame[wanted].to_dict(orient="records"))


def surface_stage_funnel(exp_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    run_meta_rel = manifest_artifact_rel(manifest, "run_meta") or "run_meta.json"
    run_meta = _read_json(exp_dir / run_meta_rel)
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    funnel = counters.get("buy_stage_funnel") if isinstance(counters.get("buy_stage_funnel"), list) else []
    return sanitize_json(funnel)


def surface_run_meta(exp_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    rel = manifest_artifact_rel(manifest, "run_meta") or "run_meta.json"
    return sanitize_json(_read_json(exp_dir / rel))


def surface_config(exp_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    rel = manifest_artifact_rel(manifest, "config") or "config.json"
    return sanitize_json(_read_json(exp_dir / rel))


def surface_trades(exp_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rel = manifest_artifact_rel(manifest, "trades") or "portfolio_trades.csv"
    frame = _read_csv(exp_dir / rel)
    return sanitize_json(frame.to_dict(orient="records")) if not frame.empty else []


def surface_daily(exp_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rel = manifest_artifact_rel(manifest, "daily") or "portfolio_daily.csv"
    frame = _read_csv(exp_dir / rel)
    return sanitize_json(frame.to_dict(orient="records")) if not frame.empty else []


def surface_reason_codes(exp_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rel = manifest_artifact_rel(manifest, "reason_codes") or "reason_codes.csv"
    frame = _read_csv(exp_dir / rel)
    return sanitize_json(frame.to_dict(orient="records")) if not frame.empty else []


def surface_cash_blocked_buys_recent(exp_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rel = manifest_artifact_rel(manifest, "cash_blocked_buys_recent") or ARTIFACT_FILENAMES["cash_blocked_buys_recent"]
    frame = _read_csv(exp_dir / rel)
    return sanitize_json(frame.to_dict(orient="records")) if not frame.empty else []


def surface_stock_names(exp_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    rel = manifest_artifact_rel(manifest, "stock_names") or "stock_names.json"
    return sanitize_json(_read_json(exp_dir / rel))


def load_simple_surface_section_data(exp_dir: Path, manifest: dict[str, Any], section: str) -> Any:
    if section == "nav":
        return surface_nav(exp_dir, manifest)
    if section == "drawdown":
        return surface_drawdown(surface_nav(exp_dir, manifest))
    if section == "symbol_stats":
        return surface_symbol_stats(exp_dir, manifest)
    if section == "stage_funnel":
        return surface_stage_funnel(exp_dir, manifest)
    if section == "run_meta":
        return surface_run_meta(exp_dir, manifest)
    if section == "config":
        return surface_config(exp_dir, manifest)
    if section == "trades":
        return surface_trades(exp_dir, manifest)
    if section == "daily":
        return surface_daily(exp_dir, manifest)
    if section == "reason_codes":
        return surface_reason_codes(exp_dir, manifest)
    if section == "cash_blocked_buys_recent":
        return surface_cash_blocked_buys_recent(exp_dir, manifest)
    if section == "stock_names":
        return surface_stock_names(exp_dir, manifest)
    return None


def is_simple_surface_section_available(exp_dir: Path, manifest: dict[str, Any], section: str) -> bool:
    if section == "cash_blocked_buys_recent":
        rel = manifest_artifact_rel(manifest, "cash_blocked_buys_recent") or ARTIFACT_FILENAMES["cash_blocked_buys_recent"]
        return (exp_dir / rel).exists()
    data = load_simple_surface_section_data(exp_dir, manifest, section)
    if isinstance(data, dict):
        return bool(data)
    if isinstance(data, list):
        return bool(data)
    return data is not None
