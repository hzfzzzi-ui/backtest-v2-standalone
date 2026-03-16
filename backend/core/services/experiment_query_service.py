from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException

from backend.api.backtest_v2.contracts.manifest import ExperimentManifest
from backend.api.backtest_v2.contracts.responses import HistoryListItem, MobileExperimentSummary
from backend.api.backtest_v2.contracts.surface import ExperimentLazySurfaceSection, ExperimentSurface, ExperimentSurfaceSummary
from backend.api.backtest_v2.protocol import ARTIFACT_FILENAMES
from backend.api.backtest_v2 import history_impl
from backend.api.shared.json_utils import sanitize_json
from backend.core.config.asset_profiles import build_asset_context
from backend.core.tools import baseline_access
from backend.core.tools.experiment_artifact_access import (
    load_manifest,
    manifest_artifact_rel,
    resolve_experiment_dir_by_id,
)

_ALLOWED_SURFACE_SECTIONS = {
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


def _to_finite_float(value: Any) -> float | None:
    try:
        num = float(value)
    except Exception:
        return None
    return num if math.isfinite(num) else None


def _first_finite_float(*values: Any) -> float | None:
    for value in values:
        num = _to_finite_float(value)
        if num is not None:
            return num
    return None


def _surface_initial_capital(config_payload: dict[str, Any]) -> float | None:
    config = config_payload if isinstance(config_payload, dict) else {}
    overrides = config.get("overrides") if isinstance(config.get("overrides"), dict) else {}
    workbench_cfg = overrides.get("original_workbench_config")
    if not isinstance(workbench_cfg, dict):
        workbench_cfg = overrides.get("workbench_config")
    base_cfg = config.get("base_config") if isinstance(config.get("base_config"), dict) else {}
    return _first_finite_float(
        workbench_cfg.get("initial_capital") if isinstance(workbench_cfg, dict) else None,
        overrides.get("initial_capital"),
        base_cfg.get("initial_capital"),
    )


def _safe_meta_json(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _surface_trade_stats(exp_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    trades_rel = manifest_artifact_rel(manifest, "trades") or "portfolio_trades.csv"
    frame = _read_csv(exp_dir / trades_rel)
    if frame.empty:
        return {}

    rows = frame.to_dict(orient="records")
    indexed_rows = sorted(
        enumerate(rows),
        key=lambda item: (
            str((item[1] or {}).get("date") or ""),
            item[0],
        ),
    )
    books: dict[str, dict[str, float]] = {}
    realized_pnls: list[float] = []

    for _, row in indexed_rows:
        side = str((row or {}).get("side") or "").strip().upper()
        symbol = str((row or {}).get("symbol") or "").strip().lower()
        qty = _to_finite_float((row or {}).get("qty"))
        if not symbol or qty is None or qty <= 0:
            continue

        book = books.get(symbol, {"qty": 0.0, "cost": 0.0})
        if side == "BUY":
            gross_cost = _to_finite_float((row or {}).get("net_amount"))
            fill_price = _to_finite_float((row or {}).get("fill_price"))
            cost = gross_cost if gross_cost is not None else (fill_price * qty if fill_price is not None else None)
            if cost is not None and cost > 0:
                book["qty"] += qty
                book["cost"] += cost
                books[symbol] = book
            continue

        if side != "SELL":
            continue

        matched_qty = min(qty, book["qty"] if book["qty"] > 0 else qty)
        if not (matched_qty > 0):
            continue

        avg_cost = (book["cost"] / book["qty"]) if book["qty"] > 0 else None
        if avg_cost is None or avg_cost <= 0:
            avg_cost = _to_finite_float(_safe_meta_json((row or {}).get("meta_json")).get("avg_cost"))
        proceeds = _to_finite_float((row or {}).get("net_amount"))
        if avg_cost is None or avg_cost <= 0 or proceeds is None:
            continue

        realized_pnls.append(proceeds - (avg_cost * matched_qty))

        if book["qty"] > 0:
            book["qty"] -= matched_qty
            book["cost"] -= avg_cost * matched_qty
            if book["qty"] <= 1e-8 or book["cost"] <= 1e-8:
                books.pop(symbol, None)
            else:
                books[symbol] = book

    wins = [value for value in realized_pnls if value > 0]
    losses = [value for value in realized_pnls if value < 0]
    gross_profit = sum(wins)
    gross_loss = sum(abs(value) for value in losses)
    profit_factor = None
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    elif gross_profit > 0:
        profit_factor = math.inf

    expectancy = (sum(realized_pnls) / len(realized_pnls)) if realized_pnls else None
    win_rate = (len(wins) / len(realized_pnls)) if realized_pnls else None
    return sanitize_json(
        {
            "closed_trades": int(len(realized_pnls)),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "expectancy_per_trade": expectancy,
        }
    )


def _surface_perf_payload(exp_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    perf_rel = manifest_artifact_rel(manifest, "perf") or "perf.json"
    perf = sanitize_json(_read_json(exp_dir / perf_rel))
    config_payload = _surface_config(exp_dir, manifest)
    initial_capital = _surface_initial_capital(config_payload)
    total_return = _to_finite_float(perf.get("total_return"))
    final_capital = _first_finite_float(perf.get("final_capital"))

    if final_capital is None and initial_capital is not None:
        if total_return is not None:
            final_capital = initial_capital * (1.0 + total_return)
        else:
            nav_rows = _surface_nav(exp_dir, manifest)
            if nav_rows:
                last_nav = _to_finite_float(nav_rows[-1].get("nav"))
                if last_nav is not None:
                    final_capital = initial_capital * last_nav

    trade_stats = _surface_trade_stats(exp_dir, manifest)

    if initial_capital is not None and perf.get("initial_capital") is None:
        perf["initial_capital"] = initial_capital
    if final_capital is not None and perf.get("final_capital") is None:
        perf["final_capital"] = final_capital
    for key, value in trade_stats.items():
        if perf.get(key) is None and value is not None:
            perf[key] = value

    return sanitize_json(perf)


def _load_experiment_dir_or_404(exp_id: str) -> Path:
    exp_dir = resolve_experiment_dir_by_id(exp_id)
    if exp_dir is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return exp_dir


def _surface_output_refs(exp_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    machine: dict[str, str] = {}
    human: dict[str, str] = {}
    for kind, target in (("machine", machine), ("human", human)):
        root = exp_dir / kind
        if not root.exists():
            continue
        for path in sorted(root.glob("*")):
            if path.is_file():
                target[path.stem] = str(path.relative_to(exp_dir)).replace("\\", "/")
    return machine, human


def _artifact_date_bounds(frame: pd.DataFrame) -> tuple[str | None, str | None]:
    if frame.empty:
        return None, None
    date_col = None
    for candidate in ("date", "trade_date", "order_date", "as_of_date"):
        if candidate in frame.columns:
            date_col = candidate
            break
    if date_col is None and len(frame.columns) > 0:
        date_col = str(frame.columns[0])
    if not date_col:
        return None, None
    try:
        first_date = str(frame[date_col].iloc[0])[:10]
        last_date = str(frame[date_col].iloc[-1])[:10]
    except Exception:
        return None, None
    return first_date or None, last_date or None


def _artifact_regression_summary(exp_dir: Path, manifest: dict[str, Any], artifact_key: str, default_rel: str) -> dict[str, Any]:
    frame = _read_csv(exp_dir / (manifest_artifact_rel(manifest, artifact_key) or default_rel))
    first_date, last_date = _artifact_date_bounds(frame)
    return sanitize_json(
        {
            "rows": int(len(frame.index)),
            "first_date": first_date,
            "last_date": last_date,
        }
    )


def load_experiment_manifest(exp_id: str) -> ExperimentManifest:
    exp_dir = _load_experiment_dir_or_404(exp_id)
    manifest = load_manifest(exp_dir)
    if not manifest:
        raise HTTPException(status_code=404, detail="manifest not found")
    machine_outputs, human_outputs = _surface_output_refs(exp_dir)
    payload = {
        **manifest,
        "machine_outputs": machine_outputs,
        "human_outputs": human_outputs,
    }
    return ExperimentManifest.model_validate(payload)


def _history_perf_summary(entry: dict[str, Any]) -> dict[str, Any]:
    return sanitize_json(
        {
            "cagr": entry.get("cagr"),
            "max_drawdown": entry.get("max_drawdown"),
            "sharpe": entry.get("sharpe"),
            "total_return": entry.get("total_return"),
            "trades": entry.get("trades"),
        }
    )


def list_experiments() -> list[dict[str, Any]]:
    rows = history_impl.list_experiments()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = HistoryListItem(
            exp_id=str(row.get("exp_id") or ""),
            label=str(row.get("label") or row.get("exp_id") or ""),
            created_at=str(row.get("created_at") or ""),
            has_manifest=bool(row.get("has_manifest")),
            has_core_artifacts=bool(row.get("has_core_artifacts")),
            asset_scope=str(row.get("asset_scope") or "") or None,
            asset_profile_id=str(row.get("asset_profile_id") or "") or None,
            market_profile_id=str(row.get("market_profile_id") or "") or None,
            perf=_history_perf_summary(row),
        ).model_dump()
        items.append(sanitize_json({**dict(row), **item}))
    return items


def delete_experiment(exp_id: str) -> dict[str, Any]:
    return sanitize_json(history_impl.delete_experiment(exp_id))


def clear_all_experiments() -> dict[str, Any]:
    return sanitize_json(history_impl.clear_all_experiments())


def _surface_summary(exp_id: str, manifest: dict[str, Any], exp_dir: Path) -> ExperimentSurfaceSummary:
    perf = _read_json(exp_dir / (manifest_artifact_rel(manifest, "perf") or "perf.json"))
    stage_pipeline = manifest.get("stage_pipeline") if isinstance(manifest.get("stage_pipeline"), dict) else {}
    manifest_asset_context = manifest.get("asset_context") if isinstance(manifest.get("asset_context"), dict) else {}
    asset_context = sanitize_json(
        build_asset_context(
            manifest.get("asset_scope"),
            metadata_scope=manifest_asset_context.get("asset_scope"),
        )
    )
    return ExperimentSurfaceSummary(
        exp_id=exp_id,
        label=str(manifest.get("experiment_id") or exp_id),
        status=str(manifest.get("status") or "unknown"),
        created_at=str(manifest.get("created_at") or ""),
        baseline_compare_status=str(manifest.get("baseline_compare_status") or ""),
        runtime_route=str(stage_pipeline.get("route_id") or ""),
        execution_shell=str(stage_pipeline.get("execution_shell") or ""),
        effective_execution_start_date=str(
            perf.get("effective_execution_start_date")
            or ((manifest.get("metrics") or {}) if isinstance(manifest.get("metrics"), dict) else {}).get("effective_execution_start_date")
            or ""
        )
        or None,
        asset_scope=str(asset_context.get("asset_scope") or ""),
        asset_profile_id=str(asset_context.get("asset_profile_id") or ""),
        market_profile_id=str(asset_context.get("market_profile_id") or ""),
        execution_profile_id=str(asset_context.get("execution_profile_id") or ""),
        asset_context=asset_context,
    )


def _surface_nav(exp_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
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
    for row in frame[["date", nav_col]].itertuples(index=False):
        try:
            rows.append({"date": str(row[0])[:10], "nav": float(row[1])})
        except Exception:
            continue
    return rows


def _surface_drawdown(nav_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _surface_symbol_stats(exp_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
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


def _surface_stage_funnel(exp_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    run_meta_rel = manifest_artifact_rel(manifest, "run_meta") or "run_meta.json"
    run_meta = _read_json(exp_dir / run_meta_rel)
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    funnel = counters.get("buy_stage_funnel") if isinstance(counters.get("buy_stage_funnel"), list) else []
    return sanitize_json(funnel)


def _surface_run_meta(exp_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    rel = manifest_artifact_rel(manifest, "run_meta") or "run_meta.json"
    return sanitize_json(_read_json(exp_dir / rel))


def _surface_config(exp_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    rel = manifest_artifact_rel(manifest, "config") or "config.json"
    return sanitize_json(_read_json(exp_dir / rel))


def _surface_trades(exp_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rel = manifest_artifact_rel(manifest, "trades") or "portfolio_trades.csv"
    frame = _read_csv(exp_dir / rel)
    return sanitize_json(frame.to_dict(orient="records")) if not frame.empty else []


def _surface_daily(exp_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rel = manifest_artifact_rel(manifest, "daily") or "portfolio_daily.csv"
    frame = _read_csv(exp_dir / rel)
    return sanitize_json(frame.to_dict(orient="records")) if not frame.empty else []


def _surface_reason_codes(exp_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rel = manifest_artifact_rel(manifest, "reason_codes") or "reason_codes.csv"
    frame = _read_csv(exp_dir / rel)
    return sanitize_json(frame.to_dict(orient="records")) if not frame.empty else []


def _surface_cash_blocked_buys_recent(exp_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rel = manifest_artifact_rel(manifest, "cash_blocked_buys_recent") or ARTIFACT_FILENAMES["cash_blocked_buys_recent"]
    frame = _read_csv(exp_dir / rel)
    return sanitize_json(frame.to_dict(orient="records")) if not frame.empty else []


def _surface_stock_names(exp_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    rel = manifest_artifact_rel(manifest, "stock_names") or "stock_names.json"
    return sanitize_json(_read_json(exp_dir / rel))


def _surface_section_data(exp_dir: Path, manifest: dict[str, Any], section: str) -> Any:
    if section == "nav":
        return _surface_nav(exp_dir, manifest)
    if section == "drawdown":
        return _surface_drawdown(_surface_nav(exp_dir, manifest))
    if section == "symbol_stats":
        return _surface_symbol_stats(exp_dir, manifest)
    if section == "stage_funnel":
        return _surface_stage_funnel(exp_dir, manifest)
    if section == "run_meta":
        return _surface_run_meta(exp_dir, manifest)
    if section == "config":
        return _surface_config(exp_dir, manifest)
    if section == "trades":
        return _surface_trades(exp_dir, manifest)
    if section == "daily":
        return _surface_daily(exp_dir, manifest)
    if section == "reason_codes":
        return _surface_reason_codes(exp_dir, manifest)
    if section == "cash_blocked_buys_recent":
        return _surface_cash_blocked_buys_recent(exp_dir, manifest)
    if section == "stock_names":
        return _surface_stock_names(exp_dir, manifest)
    return None


def _surface_section_available(exp_dir: Path, manifest: dict[str, Any], section: str) -> bool:
    if section == "cash_blocked_buys_recent":
        rel = manifest_artifact_rel(manifest, "cash_blocked_buys_recent") or ARTIFACT_FILENAMES["cash_blocked_buys_recent"]
        return (exp_dir / rel).exists()
    data = _surface_section_data(exp_dir, manifest, section)
    if isinstance(data, dict):
        return bool(data)
    if isinstance(data, list):
        return bool(data)
    return data is not None


def get_experiment_surface(exp_id: str) -> dict[str, Any]:
    exp_dir = _load_experiment_dir_or_404(exp_id)
    manifest = load_experiment_manifest(exp_id).model_dump()
    perf = _surface_perf_payload(exp_dir, manifest)
    audit = _read_json(exp_dir / (manifest_artifact_rel(manifest, "audit") or "audit.json"))
    summary = _surface_summary(exp_id, manifest, exp_dir)
    lazy_sections = {
        key: ExperimentLazySurfaceSection(
            section=key,
            available=_surface_section_available(exp_dir, manifest, key),
            inline=False,
            endpoint=f"/api/backtest_v2/experiments/{exp_id}/surface/{key}",
        )
        for key in sorted(_ALLOWED_SURFACE_SECTIONS)
    }
    surface = ExperimentSurface(
        summary=summary,
        perf=sanitize_json(perf),
        audit=sanitize_json(audit),
        asset_context=sanitize_json(dict(manifest.get("asset_context") or summary.asset_context or {})),
        machine_outputs=dict(manifest.get("machine_outputs") or {}),
        human_outputs=dict(manifest.get("human_outputs") or {}),
        lazy_sections=lazy_sections,
    )
    return sanitize_json(surface.model_dump())


def get_experiment_surface_section(exp_id: str, section: str) -> dict[str, Any] | None:
    if section not in _ALLOWED_SURFACE_SECTIONS:
        return None
    exp_dir = _load_experiment_dir_or_404(exp_id)
    manifest = load_experiment_manifest(exp_id).model_dump()
    data = _surface_section_data(exp_dir, manifest, section)
    return sanitize_json({"section": section, "data": data})


def get_execution_regression_contract(exp_id: str) -> dict[str, Any]:
    exp_dir = _load_experiment_dir_or_404(exp_id)
    manifest = load_experiment_manifest(exp_id).model_dump()
    perf = _read_json(exp_dir / (manifest_artifact_rel(manifest, "perf") or "perf.json"))
    run_meta = _read_json(exp_dir / (manifest_artifact_rel(manifest, "run_meta") or "run_meta.json"))
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    stage_pipeline = manifest.get("stage_pipeline") if isinstance(manifest.get("stage_pipeline"), dict) else {}
    return sanitize_json(
        {
            "exp_id": exp_id,
            "manifest": {
                "schema_version": manifest.get("schema_version"),
                "status": manifest.get("status"),
                "baseline_compare_status": manifest.get("baseline_compare_status"),
                "route_id": stage_pipeline.get("route_id"),
                "execution_shell": stage_pipeline.get("execution_shell"),
            },
            "perf": {
                "total_return": perf.get("total_return"),
                "max_drawdown": perf.get("max_drawdown"),
                "cagr": perf.get("cagr"),
                "sharpe": perf.get("sharpe"),
                "calmar": perf.get("calmar"),
                "trades": perf.get("trades"),
                "turnover": perf.get("turnover"),
                "effective_execution_start_date": perf.get("effective_execution_start_date"),
            },
            "counters": {
                "orders": counters.get("orders"),
                "closed_trades": counters.get("closed_trades"),
                "buy_orders_count": counters.get("buy_orders_count"),
                "sell_orders_count": counters.get("sell_orders_count"),
            },
            "artifacts": {
                "orders": _artifact_regression_summary(exp_dir, manifest, "orders", "orders.csv"),
                "trades": _artifact_regression_summary(exp_dir, manifest, "trades", "portfolio_trades.csv"),
                "nav": _artifact_regression_summary(exp_dir, manifest, "nav", "nav.csv"),
            },
        }
    )


def get_baseline_regression_snapshot(baseline_id: str) -> dict[str, Any]:
    record = baseline_access.load_baseline_record(baseline_id) or {}
    linked_exp_id = str(record.get("linked_exp_id") or "").strip()
    if not linked_exp_id:
        return {}
    regression = get_execution_regression_contract(linked_exp_id)
    regression.pop("exp_id", None)
    return sanitize_json(
        {
            "baseline_id": baseline_id,
            "linked_exp_id": linked_exp_id,
            **regression,
        }
    )


def get_v10_1_regression_snapshot() -> dict[str, Any]:
    return get_baseline_regression_snapshot("baseline_V10_1")


def build_mobile_experiment_summary(exp_id: str) -> dict[str, Any]:
    manifest = load_experiment_manifest(exp_id).model_dump()
    surface = get_experiment_surface(exp_id)
    exp_dir = _load_experiment_dir_or_404(exp_id)
    perf = _read_json(exp_dir / (manifest_artifact_rel(manifest, "perf") or "perf.json"))
    summary = surface.get("summary") if isinstance(surface.get("summary"), dict) else {}
    machine_outputs = dict(surface.get("machine_outputs") or {})
    human_outputs = dict(surface.get("human_outputs") or {})
    tags: list[str] = []
    if machine_outputs:
        tags.append("machine")
    if human_outputs:
        tags.append("human")
    payload = MobileExperimentSummary(
        exp_id=exp_id,
        title=str(summary.get("label") or exp_id),
        subtitle=str(summary.get("runtime_route") or ""),
        tags=tags,
        status=str(summary.get("status") or ""),
        cagr=perf.get("cagr"),
        sharpe=perf.get("sharpe"),
        max_drawdown=perf.get("max_drawdown"),
        total_return=perf.get("total_return"),
        trades=perf.get("trades"),
        signal_date=perf.get("effective_signal_start_date"),
    )
    return sanitize_json(payload.model_dump())
