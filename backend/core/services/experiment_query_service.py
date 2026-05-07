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
from backend.api.shared.json_utils import sanitize_json
from backend.core.config.asset_profiles import build_asset_context
from backend.core.services.experiment_surface_sections import (
    SIMPLE_SURFACE_SECTIONS,
    is_simple_surface_section_available,
    load_simple_surface_section_data,
    surface_config as _surface_config,
    surface_daily as _surface_daily,
    surface_nav as _surface_nav,
    surface_reason_codes as _surface_reason_codes,
    surface_run_meta as _surface_run_meta,
    surface_stage_funnel as _surface_stage_funnel,
    surface_stock_names as _surface_stock_names,
    surface_symbol_stats as _surface_symbol_stats,
    surface_trades as _surface_trades,
)
from backend.core.services import experiment_history_service
from backend.core.tools import baseline_access
from backend.core.tools.experiment_artifact_access import (
    load_manifest,
    manifest_artifact_rel,
    resolve_experiment_dir_by_id,
)

_ALLOWED_SURFACE_SECTIONS = set(SIMPLE_SURFACE_SECTIONS) | {"combo_truth"}


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
    for candidate in ("date", "trade_date", "order_date", "as_of_date", "signal_date", "scheduled_date", "fill_date"):
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
    rows = experiment_history_service.list_experiments()
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
    return sanitize_json(experiment_history_service.delete_experiment(exp_id))


def clear_all_experiments() -> dict[str, Any]:
    return sanitize_json(experiment_history_service.clear_all_experiments())


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


def _format_pct_text(value: Any) -> str:
    num = _to_finite_float(value)
    return f"{num * 100:.2f}%" if num is not None else "-"


def _join_non_empty(parts: list[str]) -> str:
    values = [str(part or "").strip() for part in parts if str(part or "").strip()]
    return " | ".join(values) if values else "-"


def _summarize_reason_codes(values: Any) -> str:
    items = [str(item or "").strip() for item in list(values or ()) if str(item or "").strip()]
    return ", ".join(items[:3]) if items else "-"


def _summarize_manual_override(payload: Any) -> str:
    override_payload = payload if isinstance(payload, dict) else {}
    if not override_payload.get("active"):
        return "无"
    parts = [
        str(override_payload.get("scope") or "override").strip(),
        str(override_payload.get("target_state_5") or "").strip(),
        str(override_payload.get("reason") or "").strip(),
    ]
    return _join_non_empty(parts)


def _surface_component_snapshot(exp_id: str) -> dict[str, Any] | None:
    component_dir = resolve_experiment_dir_by_id(exp_id)
    if component_dir is None:
        return None
    manifest = load_manifest(component_dir)
    if not isinstance(manifest, dict) or not manifest:
        return None
    summary = sanitize_json(_surface_summary(exp_id, manifest, component_dir).model_dump())
    nav_rows = _surface_nav(component_dir, manifest)
    payload = {
        "active": True,
        "source": {"kind": "experiment", "id": exp_id},
        "assetContext": dict(summary.get("asset_context") or {}),
        "result": {
            "exp_id": exp_id,
            "status": str(manifest.get("status") or ""),
        },
        "manifest": sanitize_json(manifest),
        "artifacts": {
            "perf": _surface_perf_payload(component_dir, manifest),
            "run_meta": _surface_run_meta(component_dir, manifest),
            "config": _surface_config(component_dir, manifest),
            "nav": nav_rows,
            "navSeries": [{"date": row.get("date"), "value": row.get("nav")} for row in nav_rows],
            "symbolPerformanceRows": _surface_symbol_stats(component_dir, manifest),
            "tradesRows": _surface_trades(component_dir, manifest),
            "funnelRows": _surface_stage_funnel(component_dir, manifest),
            "dailyRows": _surface_daily(component_dir, manifest),
            "reasonRows": _surface_reason_codes(component_dir, manifest),
            "stockNames": _surface_stock_names(component_dir, manifest),
            "surfaceSummary": summary,
            "surfaceLazySections": {},
            "machineOutputs": dict(manifest.get("machine_outputs") or {}),
            "humanOutputs": dict(manifest.get("human_outputs") or {}),
        },
        "view": {},
        "updatedAt": None,
    }
    return sanitize_json(payload)


def _build_research_combo_display(
    stock_snapshot: dict[str, Any] | None,
    etf_snapshot: dict[str, Any] | None,
    combo_run_meta: dict[str, Any] | None,
) -> dict[str, Any]:
    stock_run_meta = (
        ((stock_snapshot or {}).get("artifacts") or {}).get("run_meta")
        if isinstance(((stock_snapshot or {}).get("artifacts") or {}), dict)
        else {}
    )
    etf_run_meta = (
        ((etf_snapshot or {}).get("artifacts") or {}).get("run_meta")
        if isinstance(((etf_snapshot or {}).get("artifacts") or {}), dict)
        else {}
    )
    stock_run_meta = stock_run_meta if isinstance(stock_run_meta, dict) else {}
    etf_run_meta = etf_run_meta if isinstance(etf_run_meta, dict) else {}
    combo_meta = combo_run_meta if isinstance(combo_run_meta, dict) else {}
    stock_latest = dict(((stock_run_meta.get("regime") or {}).get("latest_state") or {}))
    etf_latest = dict(((etf_run_meta.get("regime") or {}).get("latest_state") or {}))
    stock_governor = dict(stock_run_meta.get("governed_snapshot") or {})
    etf_governor = dict(etf_run_meta.get("governed_snapshot") or {})
    combo_runtime = dict(combo_meta.get("combo_runtime") or {})
    combo_mode = str(combo_runtime.get("mode") or "").strip()
    if not combo_mode:
        execution_contract = (
            dict(combo_meta.get("execution_contract") or {})
            if isinstance(combo_meta.get("execution_contract"), dict)
            else {}
        )
        combo_policy = (
            dict(execution_contract.get("combo_policy") or {})
            if isinstance(execution_contract.get("combo_policy"), dict)
            else {}
        )
        combo_mode = str(combo_policy.get("mode") or "").strip()
    account_allocator_runtime = (
        dict(combo_meta.get("account_allocator_runtime") or {})
        if isinstance(combo_meta.get("account_allocator_runtime"), dict)
        else {}
    )
    account_budget_roles = (
        dict(account_allocator_runtime.get("budget_roles") or {})
        if isinstance(account_allocator_runtime.get("budget_roles"), dict)
        else {}
    )
    account_target = dict(account_budget_roles.get("target") or {})
    account_actual = dict(account_budget_roles.get("actual") or {})
    account_deviation = dict(account_budget_roles.get("deviation") or {})
    account_state_source = str(account_allocator_runtime.get("state_source") or "").strip()
    account_state_resolution = dict(account_allocator_runtime.get("state_resolution") or {})
    account_state_transition_policy = dict(account_allocator_runtime.get("state_transition_policy") or {})
    account_state_transition_runtime = dict(account_allocator_runtime.get("state_transition_runtime") or {})
    account_transition_action_handoff = dict(account_allocator_runtime.get("transition_action_handoff") or {})
    account_riskoff_left_side = dict(account_allocator_runtime.get("riskoff_left_side_accumulation_budget") or {})
    account_riskoff_materialization = dict(
        account_allocator_runtime.get("riskoff_budget_execution_materialization") or {}
    )
    etf_formal_view = (
        dict(((etf_run_meta.get("etf_beta") or {}).get("formal_view") or {}))
        if isinstance((etf_run_meta.get("etf_beta") or {}), dict)
        else {}
    )
    account_transition_execution = dict(account_allocator_runtime.get("transition_execution") or {})
    account_transition_execution_reference = dict(
        account_allocator_runtime.get("transition_execution_reference") or {}
    )
    account_transition_kind = str(account_state_transition_runtime.get("transition_kind") or "").strip()
    account_transition_from = str(account_state_transition_runtime.get("previous_state_5") or "").strip()
    account_transition_to = str(account_state_transition_runtime.get("effective_state_5") or "").strip()
    account_transition_carry = str(((account_state_transition_runtime.get("carry_rules") or {}).get("mode")) or "").strip()
    account_transition_derisk = str(((account_state_transition_runtime.get("de_risk_rules") or {}).get("mode")) or "").strip()
    account_transition_cash = str(((account_state_transition_runtime.get("cash_release_rules") or {}).get("mode")) or "").strip()
    account_transition_handoff = str(((account_state_transition_runtime.get("budget_handoff_rules") or {}).get("mode")) or "").strip()
    account_riskoff_left_side_active = bool(account_riskoff_left_side.get("active"))
    account_riskoff_materialization_active = bool(account_riskoff_materialization.get("active"))
    left_side_defense_assets = ", ".join(
        [str(symbol).strip() for symbol in (account_riskoff_left_side.get("defense_assets") or []) if str(symbol).strip()]
    )
    left_side_core_assets = ", ".join(
        [str(symbol).strip() for symbol in (account_riskoff_left_side.get("core_beta_assets") or []) if str(symbol).strip()]
    )
    left_side_budget_text = account_riskoff_left_side_active and _join_non_empty([
        "RISK_OFF 左侧累积",
        left_side_defense_assets and f"债 {left_side_defense_assets}" or "",
        left_side_core_assets and f"核心宽基 {left_side_core_assets}" or "",
        account_riskoff_left_side.get("core_beta_weight") is not None
        and f"core {_format_pct_text(account_riskoff_left_side.get('core_beta_weight'))}" or "",
    ]) or ""
    materialization_budget_text = account_riskoff_materialization_active and _join_non_empty([
        "RISK_OFF 执行落地",
        str(account_riskoff_materialization.get("execution_activated") or "").strip().lower() == "true"
        and "已激活" or "",
        str(account_riskoff_materialization.get("execution_rejected") or "").strip().lower() == "true"
        and f"拒绝 {account_riskoff_materialization.get('reject_reason')}" or "",
        account_riskoff_materialization.get("release_destination")
        and f"destination {account_riskoff_materialization.get('release_destination')}" or "",
    ]) or ""
    transition_runtime_text = bool(account_allocator_runtime) and _join_non_empty([
        account_transition_kind and f"transition {account_transition_kind}" or "",
        account_transition_from and account_transition_to and f"{account_transition_from} -> {account_transition_to}" or "",
        account_transition_carry and f"carry {account_transition_carry}" or "",
        account_transition_derisk and f"de-risk {account_transition_derisk}" or "",
        account_transition_cash and f"cash {account_transition_cash}" or "",
        account_transition_handoff and f"handoff {account_transition_handoff}" or "",
    ]) or ""
    transition_action_handoff_text = bool(account_transition_action_handoff) and _join_non_empty([
        str(account_transition_action_handoff.get("transition_kind") or "").strip()
        and f"handoff {account_transition_action_handoff.get('transition_kind')}" or "",
        str(account_transition_action_handoff.get("consumption_mode") or "").strip()
        and f"mode {account_transition_action_handoff.get('consumption_mode')}" or "",
        bool(account_transition_action_handoff.get("implemented_for_execution"))
        and "implemented" or "reference_only",
    ]) or ""
    transition_execution_text = bool(account_transition_execution) and _join_non_empty([
        str(account_transition_execution.get("owner") or "").strip()
        and f"owner {account_transition_execution.get('owner')}" or "",
        str(account_transition_execution.get("status") or "").strip()
        and f"status {account_transition_execution.get('status')}" or "",
        str(account_transition_execution.get("reason_code") or "").strip()
        and f"reason {account_transition_execution.get('reason_code')}" or "",
        str(account_transition_execution.get("reject_reason") or "").strip()
        and f"reject {account_transition_execution.get('reject_reason')}" or "",
    ]) or ""
    account_effective_state = str(account_allocator_runtime.get("effective_state_5") or "").strip()
    regime_summary = {
        "available": bool(
            stock_latest.get("base_state")
            or stock_latest.get("effective_state")
            or etf_latest.get("base_state")
            or etf_latest.get("effective_state")
        ),
        "base_state": str(stock_latest.get("base_state") or "").strip() and f"stock {stock_latest.get('base_state')}" or "-",
        "effective_state": str(etf_latest.get("effective_state") or "").strip() and f"ETF {etf_latest.get('effective_state')}" or "-",
        "coarse_state": _join_non_empty([
            str(stock_latest.get("effective_coarse_state") or "").strip() and f"stock {stock_latest.get('effective_coarse_state')}" or "",
            str(etf_latest.get("effective_coarse_state") or "").strip() and f"ETF {etf_latest.get('effective_coarse_state')}" or "",
        ]),
        "risk_budget_multiplier_text": _join_non_empty([
            stock_governor.get("total_risk_budget") is not None and f"stock {_format_pct_text(stock_governor.get('total_risk_budget'))}" or "",
            etf_governor.get("total_risk_budget") is not None and f"ETF {_format_pct_text(etf_governor.get('total_risk_budget'))}" or "",
        ]),
        "reason_text": _join_non_empty([
            str(stock_latest.get("effective_state") or "").strip() and f"stock {stock_latest.get('effective_state')}" or "",
            str(etf_latest.get("effective_state") or "").strip() and f"ETF {etf_latest.get('effective_state')}" or "",
            account_effective_state and f"allocator {account_effective_state}" or "",
            account_state_source and f"source {account_state_source}" or "",
        ]),
        "manual_override_text": (
            _join_non_empty([
                stock_latest.get("manual_override", {}).get("active") and f"stock {_summarize_manual_override(stock_latest.get('manual_override'))}" or "",
                etf_latest.get("manual_override", {}).get("active") and f"ETF {_summarize_manual_override(etf_latest.get('manual_override'))}" or "",
            ])
            if bool((stock_latest.get("manual_override") or {}).get("active")) or bool((etf_latest.get("manual_override") or {}).get("active"))
            else "无"
        ),
    }
    governor_summary = {
        "available": bool(
            stock_governor.get("total_risk_budget") is not None
            or etf_governor.get("total_risk_budget") is not None
            or stock_governor.get("budget_consumer_sleeve_id")
            or etf_governor.get("budget_consumer_sleeve_id")
            or bool(account_allocator_runtime)
        ),
        "total_risk_budget_text": bool(account_allocator_runtime) and _join_non_empty([
            account_target and (
                f"target defense {_format_pct_text(account_target.get('defense'))}, "
                f"core {_format_pct_text(account_target.get('core_beta'))}, "
                f"alpha {_format_pct_text(account_target.get('alpha'))}"
            ) or "",
            account_actual and (
                f"actual defense {_format_pct_text(account_actual.get('defense'))}, "
                f"core {_format_pct_text(account_actual.get('core_beta'))}, "
                f"alpha {_format_pct_text(account_actual.get('alpha'))}"
            ) or "",
        ]) or _join_non_empty([
            stock_governor.get("total_risk_budget") is not None and f"stock {_format_pct_text(stock_governor.get('total_risk_budget'))}" or "",
            etf_governor.get("total_risk_budget") is not None and f"ETF {_format_pct_text(etf_governor.get('total_risk_budget'))}" or "",
        ]),
        "total_exposure_cap_text": bool(account_allocator_runtime)
        and _join_non_empty([
            "账户层主叙事",
            account_effective_state and f"state {account_effective_state}" or "",
            account_transition_kind and f"transition {account_transition_kind}" or "",
            str(account_allocator_runtime.get("runtime_truth_source") or "").strip(),
        ])
        or combo_mode and f"研究组合 {combo_mode}" or "研究组合 50/50",
        "budget_consumer_text": bool(account_allocator_runtime) and "defense + core_beta + alpha" or "cn_stock_trend_alpha_core + cn_etf_beta",
        "budget_reason_text": bool(account_allocator_runtime) and _join_non_empty([
            (account_budget_roles.get("reason_codes") or []) and _summarize_reason_codes(account_budget_roles.get("reason_codes")) or "",
            account_deviation and (
                f"gap defense {_format_pct_text(account_deviation.get('defense_gap'))}, "
                f"core {_format_pct_text(account_deviation.get('core_beta_gap'))}, "
                f"alpha {_format_pct_text(account_deviation.get('alpha_gap'))}"
            ) or "",
            transition_action_handoff_text,
            transition_execution_text,
            transition_runtime_text,
        ]) or _join_non_empty([
            (stock_governor.get("budget_reason_codes") or []) and f"stock {_summarize_reason_codes(stock_governor.get('budget_reason_codes'))}" or "",
            (etf_governor.get("budget_reason_codes") or []) and f"ETF {_summarize_reason_codes(etf_governor.get('budget_reason_codes'))}" or "",
        ]),
    }
    return sanitize_json(
        {
            "contract_version": "research_combo_truth_display@1",
            "regime": regime_summary,
            "governor": governor_summary,
            "account_allocator": bool(account_allocator_runtime) and {
                "available": True,
                "runtime_truth_source": str(account_allocator_runtime.get("runtime_truth_source") or "account_allocator"),
                "budget_owner": str(account_allocator_runtime.get("budget_owner") or "account_allocator"),
                "effective_state_5": account_effective_state or None,
                "state_source": account_state_source or None,
                "state_resolution": account_state_resolution or None,
                "state_transition_policy": account_state_transition_policy or None,
                "state_transition_runtime": account_state_transition_runtime or None,
                "transition_action_handoff": account_transition_action_handoff or None,
                "transition_execution": account_transition_execution or None,
                "target": account_target,
                "actual": account_actual,
                "deviation": account_deviation,
                "riskoff_left_side_accumulation_budget": account_riskoff_left_side or None,
                "riskoff_budget_execution_materialization": account_riskoff_materialization or None,
                "diagnostics_reference": {
                    "transition_execution_reference": account_transition_execution_reference or None,
                    "reference_combo": dict(account_allocator_runtime.get("reference_combo") or {}),
                },
            } or {"available": False},
        }
    )


def _surface_combo_truth(exp_dir: Path, manifest: dict[str, Any]) -> dict[str, Any] | None:
    run_meta = _surface_run_meta(exp_dir, manifest)
    asset_role = str(((run_meta.get("data") or {}).get("asset_role")) or "").strip().lower()
    execution_shell = str(((manifest.get("stage_pipeline") or {}).get("execution_shell")) or "").strip().lower()
    if asset_role not in {"research_combo", "unified_multi_sleeve_combo"} and execution_shell not in {
        "read_only_combo",
        "unified_combo_phase1",
    }:
        return None
    config_payload = _surface_config(exp_dir, manifest)
    dependencies = dict((run_meta.get("dependencies") or {})) if isinstance(run_meta, dict) else {}
    component_runs = dict(dependencies.get("component_runs") or {})
    component_experiments = dict(config_payload.get("component_experiments") or {}) if isinstance(config_payload, dict) else {}
    sleeves = dict((run_meta.get("sleeves") or {})) if isinstance(run_meta, dict) else {}
    stock_exp_id = str(
        ((component_runs.get("stock_alpha_core") or {}).get("exp_id"))
        or ((sleeves.get("stock_alpha_core") or {}).get("exp_id"))
        or ((component_experiments.get("stock_alpha_core") or {}).get("exp_id"))
        or ""
    ).strip()
    etf_exp_id = str(
        ((component_runs.get("etf_beta") or {}).get("exp_id"))
        or ((sleeves.get("etf_beta") or {}).get("exp_id"))
        or ((component_experiments.get("etf_beta") or {}).get("exp_id"))
        or ""
    ).strip()
    stock_snapshot = _surface_component_snapshot(stock_exp_id) if stock_exp_id else None
    etf_snapshot = _surface_component_snapshot(etf_exp_id) if etf_exp_id else None
    return sanitize_json(
        {
            "contract_version": "research_combo_truth@1",
            "display": _build_research_combo_display(stock_snapshot, etf_snapshot, run_meta),
            "components": {
                "stock": {
                    "exp_id": stock_exp_id or None,
                    "asset_scope": "cn_a_equity",
                    "snapshot": stock_snapshot,
                },
                "etf": {
                    "exp_id": etf_exp_id or None,
                    "asset_scope": "cn_etf",
                    "snapshot": etf_snapshot,
                },
            },
        }
    )


def _surface_section_data(exp_dir: Path, manifest: dict[str, Any], section: str) -> Any:
    if section == "combo_truth":
        return _surface_combo_truth(exp_dir, manifest)
    return load_simple_surface_section_data(exp_dir, manifest, section)


def _surface_section_available(exp_dir: Path, manifest: dict[str, Any], section: str) -> bool:
    data = _surface_combo_truth(exp_dir, manifest) if section == "combo_truth" else None
    if section != "combo_truth":
        return is_simple_surface_section_available(exp_dir, manifest, section)
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
                "execution_lineage_ledger": _artifact_regression_summary(
                    exp_dir,
                    manifest,
                    "execution_lineage_ledger",
                    ARTIFACT_FILENAMES["execution_lineage_ledger"],
                ),
            },
            "lineage": (
                ((audit.get("execution_lineage") or {}) if isinstance(audit.get("execution_lineage"), dict) else {})
                if isinstance((audit := _read_json(exp_dir / (manifest_artifact_rel(manifest, "audit") or "audit.json"))), dict)
                else {}
            ),
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

