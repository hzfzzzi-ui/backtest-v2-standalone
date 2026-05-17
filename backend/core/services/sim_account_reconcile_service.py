from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Mapping

from backend.api.backtest_v2.runner_config_helpers import (
    _compile_semantic_config_bundle,
    _load_base_config,
    _looks_like_backend_runtime_config,
)
from backend.api.backtest_v2.runner_impl import BacktestV2ExperimentRequest
from backend.api.shared.paths import bt_root as _bt_root
from backend.core.config.loader import load_config
from backend.core.core.models import Signal
from backend.core.engine_vector.signal_provider import DayContext as ProviderDayContext
from backend.core.services.sim_account_service import (
    default_sim_account_id,
    load_latest_holdings_snapshot,
)
from backend.core.services import sim_account_domain_service as sim_account_domain
from backend.core.stage_pipeline.adapters.bridge_adapter import (
    StagePipelineBridgeRequest,
    StagePipelineBridgeRuntime,
)
from backend.core.stage_pipeline.adapters.candidate_boundary import build_candidate_boundary_result
from backend.core.stage_pipeline.adapters.candidate_plan import build_candidate_plan_result
from backend.core.stage_pipeline.adapters.daily_accounting import prepare_daily_snapshot
from backend.core.stage_pipeline.contracts import StageOutputs
from backend.core.strategies.registry import build_strategy
from backend.core.tools.data_bundle_builder import build_data_bundle

_ACCOUNT_ID_RE = re.compile(r"[^a-z0-9_-]+")
_RECONCILE_SCHEMA_VERSION = "sim_account_reconcile_run@1"
_REFERENCE_PRICE_BASIS = "latest_close"


def _normalize_account_id(value: str) -> str:
    normalized = _ACCOUNT_ID_RE.sub("_", str(value or "").strip().lower()).strip("_")
    if not normalized:
        raise ValueError("account_id is required")
    return normalized


def _now_ts(now_ts: int | None = None) -> int:
    return int(now_ts if now_ts is not None else time.time())


def _now_iso(now_ts: int | None = None) -> str:
    return datetime.fromtimestamp(_now_ts(now_ts), tz=UTC).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_index(results_root: Path) -> list[dict[str, Any]]:
    path = results_root / "experiments" / "index.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False, dir=str(path.parent)) as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
        tmp_path = Path(fh.name)
    os.replace(str(tmp_path), str(path))


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        fh.write("\n")


def _sim_account_root(results_root: Path, account_id: str) -> Path:
    root = results_root / "ops" / "sim_account" / _normalize_account_id(account_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _reconcile_root(results_root: Path, account_id: str) -> Path:
    root = _sim_account_root(results_root, account_id) / "reconcile"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _reconcile_history_root(results_root: Path, account_id: str) -> Path:
    root = _reconcile_root(results_root, account_id) / "history"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _latest_reconcile_path(results_root: Path, account_id: str) -> Path:
    return _reconcile_root(results_root, account_id) / "latest.json"


def _audit_log_path(results_root: Path, account_id: str) -> Path:
    return _sim_account_root(results_root, account_id) / "audit_log.jsonl"


def _normalize_symbol(value: Any) -> str:
    return str(value or "").strip().lower()


def _parse_trade_date(value: Any) -> date:
    text = str(value or "").strip()
    if not text:
        raise ValueError("trade_date is required")
    try:
        return date.fromisoformat(text[:10])
    except Exception as exc:
        raise ValueError(f"invalid trade_date: {value}") from exc


def _stable_hash(payload: Any) -> str:
    return hashlib.sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()[:16]


def _pick_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _pick_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _extract_stock_names(exp_dir: Path, manifest: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, str]:
    stock_names: dict[str, str] = {}
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    rel_path = str(artifacts.get("stock_names") or "").strip()
    if rel_path:
        payload = _read_json(exp_dir / rel_path)
        stock_names.update(
            {
                _normalize_symbol(symbol): str(name)
                for symbol, name in payload.items()
                if _normalize_symbol(symbol) and str(name).strip()
            }
        )
    for item in list(snapshot.get("positions") or []):
        if not isinstance(item, Mapping):
            continue
        symbol = _normalize_symbol(item.get("symbol"))
        name = str(item.get("name") or "").strip()
        if symbol and name and symbol not in stock_names:
            stock_names[symbol] = name
    return stock_names


def _load_latest_experiment_context(results_root: Path, strategy_as_of_date: str) -> dict[str, Any]:
    entries = [item for item in _read_index(results_root) if str(item.get("exp_id") or "").strip()]
    if not entries:
        raise FileNotFoundError("latest experiment index is missing")
    entries.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    entry = entries[0]
    exp_id = str(entry.get("exp_id") or "").strip()
    if not exp_id:
        raise FileNotFoundError("latest experiment exp_id is missing")

    exp_dir = results_root / "experiments" / exp_id
    if not exp_dir.exists():
        raise FileNotFoundError(f"latest experiment directory is missing: {exp_id}")

    manifest = _read_json(exp_dir / "manifest.json")
    resolved_config = _read_json(exp_dir / "resolved_config.json")
    input_config = _read_json(exp_dir / "input_config.json")
    compiled_plan = _read_json(exp_dir / "compiled_plan.json")

    config_json = resolved_config.get("config_json") if isinstance(resolved_config.get("config_json"), dict) else None
    if config_json is None and input_config:
        config_json = input_config
    if not isinstance(config_json, dict):
        raise ValueError(f"latest experiment is missing config_json: {exp_id}")

    request_body = BacktestV2ExperimentRequest(
        config_json=config_json,
        asset_scope=str(config_json.get("asset_scope") or "cn_a_equity"),
        end_date=str(strategy_as_of_date or ""),
    )

    config_hash = str(
        resolved_config.get("config_hash")
        or compiled_plan.get("config_hash")
        or entry.get("resolved_config_hash")
        or ""
    ).strip()

    runtime_config = compiled_plan.get("runtime_config") if isinstance(compiled_plan.get("runtime_config"), dict) else None
    execution_overrides = (
        compiled_plan.get("execution_overrides")
        if isinstance(compiled_plan.get("execution_overrides"), dict)
        else {}
    )
    if not runtime_config:
        if _looks_like_backend_runtime_config(config_json):
            runtime_config = dict(config_json)
        else:
            semantic_compile = _compile_semantic_config_bundle(
                base_cfg=_load_base_config(_bt_root()),
                body=request_body,
                semantic_cfg=config_json,
                config_source=f"latest_experiment:{exp_id}",
                use_body_universe_fields=True,
            )
            runtime_config = semantic_compile.get("runtime_config") if isinstance(semantic_compile.get("runtime_config"), dict) else {}
            compiled_payload = semantic_compile.get("compiled_plan") if isinstance(semantic_compile.get("compiled_plan"), dict) else {}
            execution_overrides = (
                compiled_payload.get("execution_overrides")
                if isinstance(compiled_payload.get("execution_overrides"), dict)
                else {}
            )
            config_hash = config_hash or str(semantic_compile.get("config_hash") or "").strip()

    if not runtime_config:
        raise ValueError(f"failed to resolve runtime_config from latest experiment: {exp_id}")

    if not config_hash:
        config_hash = _stable_hash(config_json)

    return {
        "exp_id": exp_id,
        "entry": entry,
        "exp_dir": exp_dir,
        "manifest": manifest,
        "config_json": config_json,
        "runtime_config": runtime_config,
        "execution_overrides": dict(execution_overrides or {}),
        "config_hash": config_hash,
    }


def _write_runtime_config_tmp(runtime_config: dict[str, Any]) -> Path:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as fh:
        fh.write(json.dumps(runtime_config, ensure_ascii=False, indent=2))
        return Path(fh.name).resolve()


def _resolve_runtime_inputs(
    strategy_context: dict[str, Any],
    *,
    snapshot_trade_date: str,
    strategy_as_of_date: str,
) -> dict[str, Any]:
    runtime_config = dict(strategy_context.get("runtime_config") or {})
    runtime_config.setdefault("initial_capital", 100000.0)
    if isinstance(runtime_config.get("universe"), dict):
        runtime_config["universe"] = dict(runtime_config.get("universe") or {})
        runtime_config["universe"]["end"] = strategy_as_of_date or snapshot_trade_date

    tmp_cfg_path = _write_runtime_config_tmp(runtime_config)
    try:
        cfg_obj, runtime_hash = load_config(tmp_cfg_path)
    finally:
        try:
            tmp_cfg_path.unlink(missing_ok=True)
        except Exception:
            pass

    config_json = strategy_context.get("config_json") if isinstance(strategy_context.get("config_json"), dict) else {}
    universe_cfg = config_json.get("universe") if isinstance(config_json.get("universe"), dict) else {}
    position_risk = config_json.get("position_risk") if isinstance(config_json.get("position_risk"), dict) else {}
    execution_overrides = dict(strategy_context.get("execution_overrides") or {})
    asset_scope = str(
        runtime_config.get("asset_scope")
        or config_json.get("asset_scope")
        or "cn_a_equity"
    )
    overrides = {
        "asset_scope": asset_scope,
        "universe_mode": str(config_json.get("universe_mode") or "CUSTOM"),
        "industries": _string_list(config_json.get("industries")),
        "price_adj": str(universe_cfg.get("price_adj") or "hfq"),
        **execution_overrides,
    }
    rules_path = (_bt_root().parent / "configs" / "instrument_rules_cn.csv").resolve()
    bundle = build_data_bundle(
        cfg_obj=cfg_obj,
        cfg_merged=runtime_config,
        overrides=overrides,
        rules_path=rules_path,
    )
    strategy = build_strategy(cfg_obj.strategy)
    if hasattr(strategy, "state") and isinstance(strategy.state, dict):
        strategy.state["universe_filters"] = {
            "min_price": float(bundle.universe_filters_raw.get("price_min", bundle.universe_filters_raw.get("min_price", 0.0)) or 0.0),
            "min_list_days": int(bundle.universe_filters_raw.get("min_list_days", 0) or 0),
            "min_avg_turnover_20d": float(bundle.universe_filters_raw.get("min_avg_turnover_20d", 0.0) or 0.0),
            "min_avg_turnover_rate_20d": float(bundle.universe_filters_raw.get("min_avg_turnover_rate_20d", 0.0) or 0.0),
            "turnover_rate_field": str(bundle.universe_filters_raw.get("turnover_rate_field", "turnover_rate_f") or "turnover_rate_f"),
            "exclude_star_market": bool(bundle.universe_filters_raw.get("exclude_star_market", False)),
            "csi1000_new_min_circ_mv_yi": float(bundle.universe_filters_raw.get("csi1000_new_min_circ_mv_yi", 0.0) or 0.0),
            "dynamic_all_a_entry": bool(bundle.dynamic_all_a_entry),
        }
        strategy.state["membership_history"] = bundle.membership_history

    max_positions = _pick_int(
        execution_overrides.get("max_positions"),
        _pick_int(position_risk.get("max_positions"), 10),
    )
    runtime_execution = runtime_config.get("execution") if isinstance(runtime_config.get("execution"), dict) else {}
    runtime_sizing = runtime_config.get("sizing") if isinstance(runtime_config.get("sizing"), dict) else {}

    return {
        "cfg_obj": cfg_obj,
        "bundle": bundle,
        "strategy": strategy,
        "runtime_config": runtime_config,
        "execution_overrides": execution_overrides,
        "asset_scope": asset_scope,
        "runtime_hash": runtime_hash,
        "max_positions": max_positions,
        "lot_size": _pick_int(runtime_execution.get("lot_size"), int(cfg_obj.execution.lot_size)),
        "base_order_value": _pick_float(runtime_sizing.get("order_value"), float(cfg_obj.sizing.order_value)),
    }


def _build_runtime(
    runtime_inputs: dict[str, Any],
    snapshot: dict[str, Any],
) -> StagePipelineBridgeRuntime:
    bundle = runtime_inputs["bundle"]
    cfg_obj = runtime_inputs["cfg_obj"]
    strategy = runtime_inputs["strategy"]
    runtime_config = runtime_inputs["runtime_config"]
    execution_overrides = runtime_inputs["execution_overrides"]
    snapshot_cost_nav = float(snapshot.get("cash") or 0.0) + sum(
        int(item.get("qty") or 0) * float(item.get("avg_cost") or 0.0)
        for item in list(snapshot.get("positions") or [])
        if isinstance(item, Mapping)
    )
    request = StagePipelineBridgeRequest(
        data_bundle=bundle,
        strategy=strategy,
        initial_cash=max(snapshot_cost_nav, 1.0),
        max_positions=int(runtime_inputs["max_positions"]),
        lot_size=int(runtime_inputs["lot_size"]),
        enable_strength_rank=bool(execution_overrides.get("enable_strength_rank", False)),
        strength_ma=_pick_int(execution_overrides.get("strength_ma"), 120),
        strength_top_k_mode=str(execution_overrides.get("strength_top_k_mode") or "FILL_TO_MAX"),
        fast_mode=bool(execution_overrides.get("fast_mode", True)),
        enable_multifactor_rank=bool(execution_overrides.get("enable_multifactor_rank", False)),
        mf_topk=_pick_int(execution_overrides.get("mf_topk"), 10),
        mf_concentrate_topn=_pick_int(execution_overrides.get("mf_concentrate_topn"), 3),
        mf_concentrate_scale=_pick_float(execution_overrides.get("mf_concentrate_scale"), 1.5),
        mf_rank_gate_mode=str(execution_overrides.get("mf_rank_gate_mode") or "ALWAYS_ON"),
        momentum_top_pct=_pick_float(execution_overrides.get("momentum_top_pct"), 0.0),
        cost_cfg=cfg_obj.costs,
        exit_cfg=cfg_obj.exit,
        sizing_cfg=cfg_obj.sizing,
        base_order_value=float(runtime_inputs["base_order_value"]),
        risk_budget_cfg=cfg_obj.risk_budget,
        market_filter_cfg=cfg_obj.market_filter,
        benchmark_regime_cfg=cfg_obj.benchmark_regime,
        breadth_cfg=cfg_obj.breadth,
        asset_context=runtime_config.get("asset_context") if isinstance(runtime_config.get("asset_context"), dict) else {},
    )
    return StagePipelineBridgeRuntime(request)


def _snapshot_position_maps(snapshot: dict[str, Any]) -> tuple[dict[str, int], dict[str, int], dict[str, float]]:
    qty_map: dict[str, int] = {}
    sellable_map: dict[str, int] = {}
    avg_cost_map: dict[str, float] = {}
    for item in list(snapshot.get("positions") or []):
        if not isinstance(item, Mapping):
            continue
        symbol = _normalize_symbol(item.get("symbol"))
        if not symbol:
            continue
        qty_map[symbol] = int(item.get("qty") or 0)
        sellable_map[symbol] = int(item.get("sellable_qty") or 0)
        avg_cost_map[symbol] = float(item.get("avg_cost") or 0.0)
    return qty_map, sellable_map, avg_cost_map


def _estimate_market_value(
    qty_map: Mapping[str, int],
    *,
    close_idx: Mapping[tuple[date, str], float],
    avg_cost_map: Mapping[str, float],
    as_of_day: date,
) -> float:
    market_value = 0.0
    for symbol, qty in qty_map.items():
        close_price = float(close_idx.get((as_of_day, symbol), 0.0) or 0.0)
        if close_price > 0.0:
            market_value += float(qty) * close_price
        else:
            market_value += float(qty) * float(avg_cost_map.get(symbol, 0.0) or 0.0)
    return market_value


def _reset_runtime_ledger(runtime: StagePipelineBridgeRuntime, snapshot: dict[str, Any], *, as_of_day: date) -> None:
    qty_map, _sellable_map, avg_cost_map = _snapshot_position_maps(snapshot)
    runtime.cash = float(snapshot.get("cash") or 0.0)
    runtime.positions = dict(qty_map)
    runtime.position_avg_cost = dict(avg_cost_map)
    runtime.holding_sources = {}
    nav = float(runtime.cash) + _estimate_market_value(
        qty_map,
        close_idx=runtime.close_idx,
        avg_cost_map=avg_cost_map,
        as_of_day=as_of_day,
    )
    runtime.peak_nav = float(nav)
    runtime.prev_nav = float(nav)
    runtime.trade_rows = []
    runtime.candidate_rows = []
    runtime.daily_rows = []
    runtime.deferred_sell_orders = []
    runtime._prepared_day_index = None
    runtime._current_day = None
    runtime._traded_value_today = 0.0


def _close_reference_map(
    runtime: StagePipelineBridgeRuntime,
    *,
    as_of_day: date,
    day_signals: Any,
) -> dict[str, float]:
    symbols = set(_normalize_symbol(symbol) for symbol in runtime.positions)
    for signal in list(day_signals.sell_signals) + list(day_signals.buy_signals):
        symbols.add(_normalize_symbol(getattr(signal, "symbol", "")))
    reference_prices: dict[str, float] = {}
    for symbol in sorted(sym for sym in symbols if sym):
        price = float(runtime.close_idx.get((as_of_day, symbol), 0.0) or 0.0)
        if price > 0.0:
            reference_prices[symbol] = price
    return reference_prices


def _cap_sell_signals(
    day_signals: Any,
    *,
    snapshot: dict[str, Any],
    close_idx: Mapping[tuple[date, str], float],
    as_of_day: date,
) -> tuple[Any, list[dict[str, Any]]]:
    current_qty_map, sellable_map, _avg_cost_map = _snapshot_position_maps(snapshot)
    capped_signals: list[Signal] = []
    blocked_rows: list[dict[str, Any]] = []
    for signal in list(day_signals.sell_signals or []):
        symbol = _normalize_symbol(getattr(signal, "symbol", ""))
        held_qty = int(current_qty_map.get(symbol, 0))
        if held_qty <= 0:
            continue
        requested_qty = held_qty if int(getattr(signal, "qty", 0) or 0) <= 0 else min(held_qty, int(getattr(signal, "qty", 0) or 0))
        sellable_qty = int(sellable_map.get(symbol, held_qty))
        reference_price = float(close_idx.get((as_of_day, symbol), 0.0) or 0.0)
        if sellable_qty <= 0:
            blocked_rows.append(
                {
                    "symbol": symbol,
                    "action_type": "hold",
                    "current_qty": held_qty,
                    "sellable_qty": 0,
                    "suggested_qty": 0,
                    "target_qty": held_qty,
                    "delta_qty": 0,
                    "reference_price": reference_price,
                    "reference_price_basis": _REFERENCE_PRICE_BASIS if reference_price > 0 else "missing_price",
                    "reason_code": "SELL_BLOCKED_NOT_SELLABLE",
                    "reason_tags": [
                        str(getattr(signal, "reason_code", "") or getattr(signal, "reason", "") or "SELL"),
                        "sellable_qty_zero",
                    ],
                    "blocked": True,
                    "blocked_reason": "sellable_qty_zero",
                }
            )
            continue
        capped_qty = min(requested_qty, sellable_qty)
        signal_meta = dict(getattr(signal, "meta", {}) or {})
        if capped_qty < requested_qty:
            signal_meta["sellable_cap_applied"] = True
            signal_meta["requested_qty"] = int(requested_qty)
            signal_meta["sellable_qty"] = int(sellable_qty)
        capped_signals.append(
            Signal(
                signal_date=signal.signal_date,
                symbol=symbol,
                side=signal.side,
                qty=int(capped_qty),
                action=getattr(signal, "action", ""),
                reason=getattr(signal, "reason", ""),
                reason_code=getattr(signal, "reason_code", ""),
                meta=signal_meta,
            )
        )
    return replace(day_signals, sell_signals=capped_signals), blocked_rows


def _prepare_runtime_day(
    runtime: StagePipelineBridgeRuntime,
    *,
    as_of_day: date,
    snapshot: dict[str, Any],
) -> tuple[list[dict[str, Any]], StageOutputs]:
    trading_days = list(runtime.request.data_bundle.trading_days or [])
    if as_of_day not in trading_days:
        raise ValueError(f"snapshot trade_date is outside runtime calendar: {as_of_day}")
    day_index = trading_days.index(as_of_day)
    snapshot_day = prepare_daily_snapshot(runtime, day_index=day_index, day=as_of_day)
    controls = dict(snapshot_day.controls)
    next_day = trading_days[day_index + 1] if day_index + 1 < len(trading_days) else as_of_day
    provider_ctx = ProviderDayContext(
        positions=runtime.positions,
        position_avg_cost=runtime.position_avg_cost,
        cash=runtime.cash,
        nav=float(snapshot_day.nav),
        base_order_value=runtime._provider_base_order_value(float(snapshot_day.nav), int(controls["effective_max_positions"])),
        max_positions=int(controls["effective_max_positions"]),
        close_idx=runtime.close_idx,
        open_idx=runtime.open_idx,
        next_day=next_day,
        holding_sources=runtime.holding_sources,
        asset_context=runtime.request.asset_context,
        risk_on=bool(controls["risk_on_today"]),
        market_state=str(controls.get("market_state", "") or ""),
    )
    day_signals = runtime.provider.day_signals(as_of_day, day_index, provider_ctx)
    day_signals = runtime._postprocess_day_signals(day_index, day_signals, controls)
    day_signals, blocked_rows = _cap_sell_signals(
        day_signals,
        snapshot=snapshot,
        close_idx=runtime.close_idx,
        as_of_day=as_of_day,
    )
    if not getattr(runtime, "_current_day", None) or not isinstance(runtime._current_day, dict):
        runtime._current_day = {}
    candidate_boundary = build_candidate_boundary_result(
        runtime,
        day=as_of_day,
        controls=controls,
        day_signals=day_signals,
    )
    next_open = _close_reference_map(runtime, as_of_day=as_of_day, day_signals=day_signals)
    candidate_plan = build_candidate_plan_result(
        runtime,
        day=as_of_day,
        controls=controls,
        day_signals=day_signals,
        candidate_boundary=candidate_boundary,
        next_open=next_open,
        nav=float(snapshot_day.nav),
    )
    runtime._current_day = {
        "day": as_of_day,
        "nav": float(snapshot_day.nav),
        "market_value": float(snapshot_day.market_value),
        "controls": controls,
        "accounting_snapshot": getattr(snapshot_day, "accounting_snapshot", None),
        "day_signals": day_signals,
        "candidate_boundary": candidate_boundary,
        "candidate_plan": candidate_plan,
        "next_open": next_open,
        "holding_symbols": tuple(sorted(symbol for symbol, qty in runtime.positions.items() if int(qty) > 0)),
    }
    runtime._prepared_day_index = int(day_index)
    stage_output = runtime.plan_orders()
    return blocked_rows, stage_output


def _extract_reason_tags(raw_order: Mapping[str, Any]) -> list[str]:
    reason_tags: list[str] = []
    reason_code = str(raw_order.get("reason_code") or "").strip()
    if reason_code:
        reason_tags.append(reason_code)
    meta = raw_order.get("meta") if isinstance(raw_order.get("meta"), dict) else {}
    for key in (
        "triggered_rule",
        "trend_tier",
        "alpha_id",
        "entry_alpha_id",
        "entry_sleeve_id",
        "rotation_candidate_symbol",
        "rotation_held_symbol",
    ):
        value = str(meta.get(key) or "").strip()
        if value and value not in reason_tags:
            reason_tags.append(value)
    return reason_tags


def _name_for_symbol(symbol: str, stock_names: Mapping[str, str]) -> str:
    return str(stock_names.get(symbol) or symbol.upper())


def _future_position_projection(
    snapshot: dict[str, Any],
    *,
    orders: list[dict[str, Any]],
) -> tuple[dict[str, int], float]:
    current_qty_map, _sellable_map, _avg_cost_map = _snapshot_position_maps(snapshot)
    future_qty_map = dict(current_qty_map)
    future_cash = float(snapshot.get("cash") or 0.0)
    for order in list(orders or []):
        symbol = _normalize_symbol(order.get("symbol"))
        qty = int(order.get("qty") or 0)
        price = float(order.get("reference_price") or 0.0)
        side = str(order.get("action_type") or "").strip().lower()
        if side == "sell":
            current_qty = int(future_qty_map.get(symbol, 0))
            remain = max(current_qty - qty, 0)
            if remain > 0:
                future_qty_map[symbol] = remain
            else:
                future_qty_map.pop(symbol, None)
            future_cash += float(qty) * float(price)
        elif side == "buy":
            future_qty_map[symbol] = int(future_qty_map.get(symbol, 0)) + qty
            future_cash -= float(qty) * float(price)
    return future_qty_map, float(future_cash)


def _weight_map(
    qty_map: Mapping[str, int],
    *,
    future_cash: float,
    reference_price_map: Mapping[str, float],
    avg_cost_map: Mapping[str, float],
) -> dict[str, float]:
    total_nav = float(future_cash)
    value_map: dict[str, float] = {}
    for symbol, qty in qty_map.items():
        price = float(reference_price_map.get(symbol, 0.0) or 0.0)
        if price <= 0.0:
            price = float(avg_cost_map.get(symbol, 0.0) or 0.0)
        value = float(qty) * float(price)
        value_map[symbol] = float(value)
        total_nav += float(value)
    if total_nav <= 0.0:
        return {symbol: 0.0 for symbol in qty_map}
    return {symbol: float(value_map.get(symbol, 0.0)) / float(total_nav) for symbol in qty_map}


def _bucket_order_rank(action_type: str) -> int:
    return {"buy": 0, "sell": 1, "hold": 2}.get(str(action_type or "").strip().lower(), 9)


def _build_action_sheet(
    snapshot: dict[str, Any],
    *,
    stage_output: StageOutputs,
    blocked_rows: list[dict[str, Any]],
    stock_names: Mapping[str, str],
    runtime: StagePipelineBridgeRuntime,
    as_of_day: date,
) -> dict[str, Any]:
    current_qty_map, sellable_map, avg_cost_map = _snapshot_position_maps(snapshot)
    reference_price_map = {
        symbol: float(runtime.close_idx.get((as_of_day, symbol), 0.0) or 0.0)
        for symbol in set(current_qty_map) | {
            _normalize_symbol(order.get("symbol"))
            for order in list((stage_output.payload or {}).get("next_day_orders") or [])
            if isinstance(order, Mapping)
        }
    }

    order_rows: list[dict[str, Any]] = []
    touched_symbols: set[str] = set()
    for raw_order in list((stage_output.payload or {}).get("next_day_orders") or []):
        if not isinstance(raw_order, Mapping):
            continue
        symbol = _normalize_symbol(raw_order.get("symbol"))
        action_type = "buy" if str(raw_order.get("side") or "").strip().upper() == "BUY" else "sell"
        current_qty = int(current_qty_map.get(symbol, 0))
        suggested_qty = int(raw_order.get("qty") or 0)
        target_qty = current_qty + suggested_qty if action_type == "buy" else max(current_qty - suggested_qty, 0)
        reference_price = float(reference_price_map.get(symbol, 0.0) or 0.0)
        order_rows.append(
            {
                "symbol": symbol,
                "name": _name_for_symbol(symbol, stock_names),
                "action_type": action_type,
                "current_qty": current_qty,
                "sellable_qty": int(sellable_map.get(symbol, current_qty)),
                "suggested_qty": suggested_qty,
                "target_qty": target_qty,
                "delta_qty": target_qty - current_qty,
                "reference_price": reference_price,
                "reference_price_basis": _REFERENCE_PRICE_BASIS if reference_price > 0 else "missing_price",
                "reason_code": str(raw_order.get("reason_code") or ""),
                "reason_tags": _extract_reason_tags(raw_order),
                "blocked": False,
                "blocked_reason": "",
                "qty": suggested_qty,
            }
        )
        touched_symbols.add(symbol)

    order_rows.extend({**dict(item), "qty": int(item.get("suggested_qty") or 0)} for item in blocked_rows)
    touched_symbols.update(_normalize_symbol(item.get("symbol")) for item in blocked_rows if _normalize_symbol(item.get("symbol")))

    future_qty_map, future_cash = _future_position_projection(snapshot, orders=order_rows)
    future_weight_map = _weight_map(
        future_qty_map,
        future_cash=future_cash,
        reference_price_map=reference_price_map,
        avg_cost_map=avg_cost_map,
    )

    for row in order_rows:
        row["target_weight"] = float(future_weight_map.get(str(row.get("symbol") or ""), 0.0))
        row.pop("qty", None)

    hold_rows: list[dict[str, Any]] = []
    for symbol, current_qty in sorted(current_qty_map.items()):
        if symbol in touched_symbols:
            continue
        reference_price = float(reference_price_map.get(symbol, 0.0) or 0.0)
        hold_rows.append(
            {
                "symbol": symbol,
                "name": _name_for_symbol(symbol, stock_names),
                "action_type": "hold",
                "current_qty": int(current_qty),
                "sellable_qty": int(sellable_map.get(symbol, current_qty)),
                "suggested_qty": 0,
                "target_qty": int(current_qty),
                "delta_qty": 0,
                "reference_price": reference_price,
                "reference_price_basis": _REFERENCE_PRICE_BASIS if reference_price > 0 else "missing_price",
                "reason_code": "HOLD",
                "reason_tags": ["currently_held"],
                "blocked": False,
                "blocked_reason": "",
                "target_weight": float(future_weight_map.get(symbol, 0.0)),
            }
        )

    rows = order_rows + hold_rows
    rows.sort(key=lambda item: (_bucket_order_rank(str(item.get("action_type") or "")), str(item.get("symbol") or "")))
    return {
        "action_sheet": rows,
        "buy": [row for row in rows if str(row.get("action_type") or "") == "buy"],
        "sell": [row for row in rows if str(row.get("action_type") or "") == "sell"],
        "hold": [row for row in rows if str(row.get("action_type") or "") == "hold"],
    }


def load_latest_reconcile_run(results_root: Path, account_id: str | None = None) -> dict[str, Any] | None:
    normalized_account_id = _normalize_account_id(str(account_id or default_sim_account_id()))
    payload = _read_json(_latest_reconcile_path(results_root, normalized_account_id))
    return payload or None


def run_position_aware_reconcile(
    results_root: Path,
    account_id: str | None = None,
    *,
    strategy_as_of_date: str | None = None,
    now_ts: int | None = None,
) -> dict[str, Any]:
    normalized_account_id = _normalize_account_id(str(account_id or default_sim_account_id()))
    snapshot = load_latest_holdings_snapshot(results_root, normalized_account_id)
    if not isinstance(snapshot, dict) or not snapshot:
        raise FileNotFoundError(f"latest holdings snapshot is missing: {normalized_account_id}")

    snapshot_trade_date = str(snapshot.get("trade_date") or "").strip()
    if not snapshot_trade_date:
        raise ValueError("latest holdings snapshot is missing trade_date")

    resolved_as_of_date = str(strategy_as_of_date or snapshot_trade_date).strip() or snapshot_trade_date

    strategy_context = _load_latest_experiment_context(results_root, resolved_as_of_date)
    stock_names = _extract_stock_names(
        Path(strategy_context["exp_dir"]),
        dict(strategy_context.get("manifest") or {}),
        snapshot,
    )
    runtime_inputs = _resolve_runtime_inputs(
        strategy_context,
        snapshot_trade_date=snapshot_trade_date,
        strategy_as_of_date=resolved_as_of_date,
    )
    runtime = _build_runtime(runtime_inputs, snapshot)
    as_of_day = _parse_trade_date(resolved_as_of_date)
    _reset_runtime_ledger(runtime, snapshot, as_of_day=as_of_day)
    blocked_rows, stage_output = _prepare_runtime_day(runtime, as_of_day=as_of_day, snapshot=snapshot)
    stage_payload = dict(stage_output.payload or {})
    candidate_plan_payload = dict(stage_payload.get("candidate_plan") or {})
    execution_kernel_payload = dict(stage_payload.get("execution_kernel") or {})
    candidate_plan_reject_reason_counts = dict(candidate_plan_payload.get("reject_reason_counts") or {})
    execution_kernel_reject_reason_counts = dict(execution_kernel_payload.get("reject_reason_counts") or {})
    merged_reason_counts = dict(stage_output.reason_counts or {})
    for reason, count in candidate_plan_reject_reason_counts.items():
        key = str(reason or "").strip()
        if not key:
            continue
        merged_reason_counts[key] = int(merged_reason_counts.get(key, 0)) + int(count or 0)
    merged_order_reject_counts = dict(runtime.order_reject_reason_counts or {})
    for reason, count in execution_kernel_reject_reason_counts.items():
        key = str(reason or "").strip()
        if not key:
            continue
        merged_order_reject_counts[key] = int(merged_order_reject_counts.get(key, 0)) + int(count or 0)
    action_sheet_payload = _build_action_sheet(
        snapshot,
        stage_output=stage_output,
        blocked_rows=blocked_rows,
        stock_names=stock_names,
        runtime=runtime,
        as_of_day=as_of_day,
    )
    diagnostics = {
        "reason_counts": merged_reason_counts,
        "order_reject_reason_counts": merged_order_reject_counts,
        "blocked_count": len(blocked_rows),
        "market_state": str(((runtime._current_day or {}).get("controls") or {}).get("market_state") or ""),
        "trade_mode": str(((runtime._current_day or {}).get("controls") or {}).get("trade_mode") or ""),
        "effective_max_positions": int((((runtime._current_day or {}).get("controls") or {}).get("effective_max_positions") or runtime.request.max_positions)),
    }
    reconcile_seed = {
        "account_id": normalized_account_id,
        "snapshot_id": str(snapshot.get("snapshot_id") or ""),
        "trade_date": snapshot_trade_date,
        "as_of_date": resolved_as_of_date,
        "config_hash": str(strategy_context.get("config_hash") or runtime_inputs.get("runtime_hash") or ""),
        "action_sheet": [
            {
                "symbol": row.get("symbol"),
                "action_type": row.get("action_type"),
                "suggested_qty": row.get("suggested_qty"),
                "target_qty": row.get("target_qty"),
                "reference_price": row.get("reference_price"),
            "reason_code": row.get("reason_code"),
            }
            for row in list(action_sheet_payload.get("action_sheet") or [])
        ],
    }
    reconcile_id = f"rc_{_stable_hash(reconcile_seed)}"
    payload = {
        "schema_version": _RECONCILE_SCHEMA_VERSION,
        "account_id": normalized_account_id,
        "reconcile_id": reconcile_id,
        "generated_at": _now_iso(now_ts),
        "snapshot_id": str(snapshot.get("snapshot_id") or ""),
        "snapshot_trade_date": snapshot_trade_date,
        "snapshot_synced_at": str(snapshot.get("synced_at") or ""),
        "as_of_date": resolved_as_of_date,
        "source_mode": "position_aware_reconcile",
        "strategy_source": {
            "exp_id": str(strategy_context.get("exp_id") or ""),
            "created_at": str((strategy_context.get("entry") or {}).get("created_at") or ""),
            "config_hash": str(strategy_context.get("config_hash") or runtime_inputs.get("runtime_hash") or ""),
            "asset_scope": str(runtime_inputs.get("asset_scope") or ""),
        },
        "execution_assumptions": {
            "signal_clock": "POST_CLOSE",
            "execution_clock": "NEXT_OPEN",
            "reference_price_basis": _REFERENCE_PRICE_BASIS,
        },
        "summary": {
            "action_count": len(action_sheet_payload["action_sheet"]),
            "buy_count": len(action_sheet_payload["buy"]),
            "sell_count": len(action_sheet_payload["sell"]),
            "hold_count": len(action_sheet_payload["hold"]),
            "blocked_count": len(blocked_rows),
        },
        "actions": {
            "buy": action_sheet_payload["buy"],
            "sell": action_sheet_payload["sell"],
            "hold": action_sheet_payload["hold"],
        },
        "action_sheet": action_sheet_payload["action_sheet"],
        "diagnostics": diagnostics,
    }

    latest_path = _latest_reconcile_path(results_root, normalized_account_id)
    history_path = _reconcile_history_root(results_root, normalized_account_id) / f"{reconcile_id}.json"
    _atomic_write_json(history_path, payload)
    _atomic_write_json(latest_path, payload)
    sim_account_domain.write_reconcile_summary(results_root, payload)
    _append_jsonl(
        _audit_log_path(results_root, normalized_account_id),
            {
                "event_type": "reconcile_generated",
                "account_id": normalized_account_id,
                "reconcile_id": reconcile_id,
                "snapshot_id": payload["snapshot_id"],
                "trade_date": snapshot_trade_date,
                "as_of_date": resolved_as_of_date,
                "exp_id": payload["strategy_source"]["exp_id"],
            "config_hash": payload["strategy_source"]["config_hash"],
            "buy_count": payload["summary"]["buy_count"],
            "sell_count": payload["summary"]["sell_count"],
            "hold_count": payload["summary"]["hold_count"],
            "blocked_count": payload["summary"]["blocked_count"],
            "at": payload["generated_at"],
        },
    )
    return payload


def load_latest_reconcile_summary(results_root: Path, account_id: str | None = None) -> dict[str, Any] | None:
    normalized_account_id = _normalize_account_id(str(account_id or default_sim_account_id()))
    payload = sim_account_domain.load_latest_reconcile_summary(results_root, normalized_account_id)
    return payload or None


__all__ = [
    "load_latest_reconcile_run",
    "load_latest_reconcile_summary",
    "run_position_aware_reconcile",
]
