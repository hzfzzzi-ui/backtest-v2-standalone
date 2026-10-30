from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from backend.core.services.mobile_briefing_service import build_mobile_daily_briefing
from backend.core.services.mobile_execution_service import list_execution_tickets
from backend.core.services.mobile_notification_service import build_mobile_notification_feed
from backend.core.services.ops_domain_pg import OpsDomainSchemaMissing
from backend.core.services.mobile_ops_service import (
    build_suggestion_id,
    load_mobile_control_state,
    signal_staleness_threshold_days,
)
from backend.core.services.experiment_query_service import build_mobile_experiment_summary

PreviewLoader = Callable[[dict[str, Any], str, str | None], dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_index(results_root: Path) -> list[dict[str, Any]]:
    index_path = results_root / "experiments" / "index.json"
    if not index_path.exists():
        return []
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _looks_like_config_dump(label: str, exp_id: str) -> bool:
    normalized = _clean_text(label)
    if not normalized or normalized == _clean_text(exp_id):
        return False
    if len(normalized) >= 120:
        return True
    upper = normalized.upper()
    return upper.startswith("{'NAME':") or '"NAME":' in upper or "'PARAMS':" in upper


def _format_short_pct(value: Any) -> str:
    number = _safe_number(value)
    if number is None:
        return ""
    return f"{number * 100:.0f}%"


def _format_short_number(value: Any) -> str:
    number = _safe_number(value)
    if number is None:
        return ""
    if float(number).is_integer():
        return str(int(number))
    return f"{number:.1f}"


def _strategy_title(code: str) -> str:
    mapping = {
        "BREAKOUT_TREND": "突破趋势",
        "EMA_CROSS": "EMA 趋势",
        "SMA_CROSS": "SMA 趋势",
        "REGIME_ROUTER": "环境路由",
        "COMPOSITE": "组合策略",
        "RSI_REVERSAL": "RSI 反转",
    }
    normalized = _clean_text(code).upper()
    return mapping.get(normalized, normalized or "最新实验")


def _score_mode_title(code: str) -> str:
    mapping = {
        "RESIDUAL_ONLY": "残差排序",
        "RESIDUAL_SECTOR_QUALITY": "残差+行业质量",
        "MOMENTUM_ONLY": "动量排序",
    }
    normalized = _clean_text(code).upper()
    return mapping.get(normalized, normalized)


def _portfolio_mode_title(code: str) -> str:
    mapping = {
        "PROFIT_RELEASE": "利润释放",
        "EQUAL_10": "等权 10 持仓",
        "HARD_SLEEVE_BUDGET": "硬预算",
    }
    normalized = _clean_text(code).upper()
    return mapping.get(normalized, _clean_text(code))


def _matching_mode_title(code: str) -> str:
    mapping = {
        "NEXT_OPEN": "次日开盘",
        "CLOSE": "当日收盘",
    }
    normalized = _clean_text(code).upper()
    return mapping.get(normalized, _clean_text(code))


def _experiment_display(exp_id: str, raw_label: str, config_json: dict[str, Any] | None) -> dict[str, Any]:
    cfg = config_json if isinstance(config_json, dict) else {}
    universe = cfg.get("universe") if isinstance(cfg.get("universe"), dict) else {}
    signal_generation = cfg.get("signal_generation") if isinstance(cfg.get("signal_generation"), dict) else {}
    breakout = signal_generation.get("breakout") if isinstance(signal_generation.get("breakout"), dict) else {}
    ranking = signal_generation.get("ranking") if isinstance(signal_generation.get("ranking"), dict) else {}
    position_risk = cfg.get("position_risk") if isinstance(cfg.get("position_risk"), dict) else {}
    cost_model = position_risk.get("cost_model") if isinstance(position_risk.get("cost_model"), dict) else {}
    exit_rules = cfg.get("exit_rules") if isinstance(cfg.get("exit_rules"), dict) else {}
    atr_stop = exit_rules.get("atr_stop") if isinstance(exit_rules.get("atr_stop"), dict) else {}
    trailing = exit_rules.get("trailing") if isinstance(exit_rules.get("trailing"), dict) else {}
    risk_off_exit = exit_rules.get("risk_off_exit") if isinstance(exit_rules.get("risk_off_exit"), dict) else {}
    low10_exit = exit_rules.get("low10_exit") if isinstance(exit_rules.get("low10_exit"), dict) else {}

    explicit_title = _clean_text(cfg.get("display_name") or cfg.get("name"))
    fallback_label = _clean_text(raw_label)
    strategy_title = _strategy_title(_clean_text(cfg.get("strategy_pack") or signal_generation.get("strategy")))
    breakout_window = _format_short_number(breakout.get("breakout_window"))
    ranking_mode = _score_mode_title(_clean_text(ranking.get("score_source_mode")))
    residual_window = _format_short_number(ranking.get("residual_window"))

    title_parts = []
    if explicit_title and not _looks_like_config_dump(explicit_title, exp_id):
        title_parts.append(explicit_title)
    elif fallback_label and not _looks_like_config_dump(fallback_label, exp_id):
        title_parts.append(fallback_label)
    else:
        title_parts.append(strategy_title)
        if breakout_window:
            title_parts.append(f"BR{breakout_window}")
        if ranking_mode:
            title_parts.append(
                f"{ranking_mode}{residual_window}" if ranking_mode == "残差排序" and residual_window else ranking_mode
            )

    title = " · ".join([part for part in title_parts if part]) or exp_id
    if _looks_like_config_dump(raw_label, exp_id):
        raw_label = ""
    if not title and fallback_label:
        title = fallback_label

    date_start = _clean_text(universe.get("start"))[:7]
    date_end = _clean_text(universe.get("end"))[:7]
    subtitle_parts = [
        _clean_text(cfg.get("universe_mode")),
        _clean_text(universe.get("benchmark")),
        f"{date_start} ~ {date_end}" if date_start and date_end else "",
        _portfolio_mode_title(position_risk.get("portfolio_mode")),
    ]
    subtitle = " · ".join([part for part in subtitle_parts if part])

    tags: list[str] = []
    if _safe_number(position_risk.get("max_positions"), integer=True) is not None:
        tags.append(f"{int(position_risk.get('max_positions') or 0)}持仓")
    single_stock_cap = _format_short_pct(position_risk.get("single_stock_cap"))
    if single_stock_cap:
        tags.append(f"单票上限 {single_stock_cap}")
    matching_mode = _matching_mode_title(cost_model.get("matching"))
    if matching_mode:
        tags.append(matching_mode)
    atr_stop_k = _format_short_number(atr_stop.get("k")) if atr_stop.get("enabled") else ""
    if atr_stop_k:
        tags.append(f"ATR止损 {atr_stop_k}")
    trailing_k = _format_short_number(trailing.get("k")) if trailing.get("enabled") else ""
    if trailing_k:
        tags.append(f"ATR跟踪 {trailing_k}")
    activate_profit_pct = _format_short_pct(trailing.get("activate_profit_pct"))
    if activate_profit_pct:
        tags.append(f"启盈 {activate_profit_pct}")
    if bool(trailing.get("pre_profit_breakout_failure_enabled")):
        tags.append("前利润突破失败退出")
    if bool(low10_exit.get("enabled")):
        tags.append("Low10 退出")
    if bool(risk_off_exit.get("enabled")):
        tags.append("风险关机退出")

    return {
        "title": title or exp_id,
        "subtitle": subtitle,
        "tags": tags[:6],
        "raw_label": fallback_label or exp_id,
    }


def _safe_number(value: Any, *, integer: bool = False) -> int | float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if integer:
        return int(number)
    return float(number)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _daily_nav_change(daily_frame: pd.DataFrame) -> tuple[float | None, float | None]:
    if daily_frame.empty or "nav" not in daily_frame.columns:
        return None, None
    frame = daily_frame.copy()
    frame["date"] = pd.to_datetime(frame.get("date"), errors="coerce")
    frame["nav"] = pd.to_numeric(frame.get("nav"), errors="coerce")
    frame = frame.dropna(subset=["nav"]).sort_values("date")
    if len(frame.index) < 2:
        return None, None
    latest_nav = _safe_number(frame.iloc[-1]["nav"])
    previous_nav = _safe_number(frame.iloc[-2]["nav"])
    if latest_nav is None or previous_nav is None:
        return None, None
    change = float(latest_nav) - float(previous_nav)
    if float(previous_nav) == 0:
        return round(change, 6), None
    return round(change, 6), round(change / float(previous_nav), 10)


def _read_latest_market_snapshot(results_root: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    snapshot_root = results_root / "market_snapshots"
    if not snapshot_root.exists():
        return {"status": "missing", "summary": None, "warnings": ["暂无市场快照产物"]}, None

    candidates = sorted((path for path in snapshot_root.iterdir() if path.is_dir()), key=lambda p: p.name, reverse=True)
    for directory in candidates:
        snapshot = _read_json(directory / "market_snapshot.json")
        if not snapshot:
            continue
        sentiment_layer = snapshot.get("sentiment_layer") if isinstance(snapshot.get("sentiment_layer"), dict) else {}
        liquidity_layer = snapshot.get("liquidity_layer") if isinstance(snapshot.get("liquidity_layer"), dict) else {}
        risk_layer = snapshot.get("risk_layer") if isinstance(snapshot.get("risk_layer"), dict) else {}
        warnings = snapshot.get("warnings") if isinstance(snapshot.get("warnings"), list) else []
        top_warnings = [str(item.get("message") or item.get("code") or "") for item in warnings[:3] if isinstance(item, dict)]
        summary = {
            "trade_date": str(snapshot.get("trade_date") or directory.name),
            "build_status": str(snapshot.get("build_status") or "unknown"),
            "generated_at": str(snapshot.get("generated_at") or ""),
            "sentiment_regime": str(sentiment_layer.get("sentiment_regime") or "-"),
            "sentiment_score": _safe_number(sentiment_layer.get("sentiment_score")),
            "turnover_heat": _safe_number(liquidity_layer.get("market_amount_heat")),
            "risk_drawdown_from_60d_high": _safe_number(risk_layer.get("drawdown_from_60d_high")),
            "warning_count": len(warnings),
            "warnings": top_warnings,
        }
        return {"status": "ok", "summary": summary, "warnings": top_warnings}, snapshot

    return {"status": "missing", "summary": None, "warnings": ["市场快照目录存在，但没有可读快照"]}, None


def _load_stock_names(exp_dir: Path, manifest: dict[str, Any]) -> dict[str, str]:
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    rel_path = str(artifacts.get("stock_names") or "stock_names.json").strip()
    if not rel_path:
        return {}
    payload = _read_json(exp_dir / rel_path)
    return {str(k).lower(): str(v) for k, v in payload.items()}


def _rebuild_positions(trades_frame: pd.DataFrame, stock_names: dict[str, str]) -> list[dict[str, Any]]:
    if trades_frame.empty or "symbol" not in trades_frame.columns:
        return []

    frame = trades_frame.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.lower()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["qty"] = pd.to_numeric(frame["qty"], errors="coerce").fillna(0).astype(int)
    frame["fill_price"] = pd.to_numeric(frame.get("fill_price"), errors="coerce")
    frame = frame.sort_values(["date", "symbol"]).reset_index(drop=True)

    positions: dict[str, dict[str, Any]] = {}
    for row in frame.itertuples(index=False):
        symbol = str(getattr(row, "symbol", "") or "").lower()
        if not symbol:
            continue
        side = str(getattr(row, "side", "") or "").upper()
        qty = int(getattr(row, "qty", 0) or 0)
        fill_price = _safe_number(getattr(row, "fill_price", None))
        position = positions.get(symbol) or {
            "symbol": symbol,
            "name": stock_names.get(symbol, symbol.upper()),
            "qty": 0,
            "avg_fill_price": None,
            "entry_date": None,
            "last_trade_date": None,
            "last_reason_code": "",
        }
        if side == "BUY":
            previous_qty = int(position["qty"])
            previous_cost = float(position["avg_fill_price"] or 0.0) * previous_qty
            next_qty = previous_qty + qty
            if next_qty <= 0:
                continue
            next_cost = previous_cost + float(fill_price or 0.0) * qty
            position["qty"] = next_qty
            position["avg_fill_price"] = round(next_cost / next_qty, 4) if next_qty > 0 else None
            position["entry_date"] = position["entry_date"] or (str(getattr(row, "date", "") or "")[:10] if getattr(row, "date", None) is not None else None)
        elif side == "SELL":
            next_qty = int(position["qty"]) - qty
            if next_qty <= 0:
                positions.pop(symbol, None)
                continue
            position["qty"] = next_qty
        else:
            continue
        position["last_trade_date"] = str(getattr(row, "date", "") or "")[:10] if getattr(row, "date", None) is not None else position["last_trade_date"]
        position["last_reason_code"] = str(getattr(row, "reason_code", "") or "")
        positions[symbol] = position

    out = list(positions.values())
    out.sort(key=lambda item: str(item.get("symbol") or ""))
    return out


def _load_latest_experiment(results_root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    entries = _read_index(results_root)
    if not entries:
        return None, ["暂无实验记录"]
    valid_entries = [entry for entry in entries if isinstance(entry, dict) and str(entry.get("exp_id") or "").strip()]
    if not valid_entries:
        return None, ["实验索引存在，但没有有效记录"]
    valid_entries.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    exp_entry = valid_entries[0]
    exp_id = str(exp_entry.get("exp_id") or "").strip()
    exp_dir = results_root / "experiments" / exp_id
    if not exp_dir.exists():
        return None, [f"最新实验目录不存在: {exp_id}"]

    manifest = _read_json(exp_dir / "manifest.json")
    perf = _read_json(exp_dir / "perf.json")
    run_meta = _read_json(exp_dir / "run_meta.json")
    resolved_config = _read_json(exp_dir / "resolved_config.json")
    input_config = _read_json(exp_dir / "input_config.json")
    daily_frame = _read_csv(exp_dir / "portfolio_daily.csv")
    trades_frame = _read_csv(exp_dir / "portfolio_trades.csv")
    stock_names = _load_stock_names(exp_dir, manifest)

    latest_daily = daily_frame.tail(1).to_dict(orient="records")[0] if not daily_frame.empty else {}
    daily_pnl, daily_return = _daily_nav_change(daily_frame)
    current_positions = _rebuild_positions(trades_frame, stock_names)
    config_json = resolved_config.get("config_json") if isinstance(resolved_config.get("config_json"), dict) else None
    if config_json is None and input_config:
        config_json = input_config
    experiment_display = _experiment_display(
        exp_id,
        _clean_text(exp_entry.get("label")),
        config_json,
    )

    experiment_summary = {
        "exp_id": exp_id,
        "label": str(exp_entry.get("label") or exp_id),
        "title": experiment_display["title"],
        "subtitle": experiment_display["subtitle"],
        "tags": experiment_display["tags"],
        "raw_label": experiment_display["raw_label"],
        "created_at": str(exp_entry.get("created_at") or ""),
        "status": str(exp_entry.get("status") or manifest.get("status") or "unknown"),
        "cagr": _safe_number(exp_entry.get("cagr", perf.get("cagr"))),
        "sharpe": _safe_number(exp_entry.get("sharpe", perf.get("sharpe"))),
        "max_drawdown": _safe_number(exp_entry.get("max_drawdown", perf.get("max_drawdown"))),
        "total_return": _safe_number(exp_entry.get("total_return", perf.get("total_return"))),
        "trades": _safe_number(exp_entry.get("trades", perf.get("trades")), integer=True),
        "universe_mode": str(exp_entry.get("universe_mode") or run_meta.get("data", {}).get("universe_mode") or ""),
        "latest_trade_date": str(latest_daily.get("date") or ""),
        "nav": _safe_number(latest_daily.get("nav")),
        "cash": _safe_number(latest_daily.get("cash")),
        "daily_pnl": _safe_number(daily_pnl),
        "daily_return": _safe_number(daily_return),
        "position_count": len(current_positions),
        "market_state": str(latest_daily.get("market_state") or ""),
        "trade_mode": str(latest_daily.get("trade_mode") or ""),
        "benchmark_regime_on": str(latest_daily.get("benchmark_regime_on") or ""),
    }
    try:
        surface_summary = build_mobile_experiment_summary(exp_id)
    except Exception:
        surface_summary = {}
    if isinstance(surface_summary, dict) and surface_summary:
        for key in ("status", "cagr", "sharpe", "max_drawdown", "total_return", "trades"):
            if surface_summary.get(key) is not None:
                experiment_summary[key] = surface_summary.get(key)
        experiment_summary["surface_summary"] = surface_summary

    return (
        {
            "entry": exp_entry,
            "exp_dir": exp_dir,
            "manifest": manifest,
            "perf": perf,
            "run_meta": run_meta,
            "resolved_config": resolved_config,
            "input_config": input_config,
            "config_json": config_json,
            "latest_daily": latest_daily,
            "current_positions": current_positions,
            "stock_names": stock_names,
            "summary": experiment_summary,
        },
        [],
    )


def _preview_reason_map(preview: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for item in preview.get("candidates") or []:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").lower()
        if not symbol:
            continue
        reasons = [str(reason) for reason in item.get("reasons") or [] if str(reason).strip()]
        out[symbol] = reasons
    return out


def _build_guidance(
    *,
    current_positions: list[dict[str, Any]],
    preview_payload: dict[str, Any] | None,
    stock_names: dict[str, str],
) -> dict[str, Any]:
    if not preview_payload:
        return {
            "status": "unavailable",
            "as_of_date_used": None,
            "buy": [],
            "sell": [],
            "hold": [],
            "warnings": ["执行预览不可用，未生成买卖指引"],
        }

    target_positions = [
        item for item in (preview_payload.get("target_positions") or [])
        if isinstance(item, dict) and str(item.get("symbol") or "").strip()
    ]
    target_symbols = {str(item.get("symbol") or "").lower() for item in target_positions}
    current_map = {str(item.get("symbol") or "").lower(): item for item in current_positions}
    reason_map = _preview_reason_map(preview_payload)

    buy: list[dict[str, Any]] = []
    hold: list[dict[str, Any]] = []
    for item in target_positions:
        symbol = str(item.get("symbol") or "").lower()
        guidance_item = {
            "symbol": symbol,
            "name": stock_names.get(symbol, symbol.upper()),
            "target_weight": _safe_number(item.get("target_weight")),
            "cap_reason": str(item.get("cap_reason") or ""),
            "reasons": reason_map.get(symbol, []),
        }
        if symbol in current_map:
            hold.append(guidance_item)
        else:
            buy.append(guidance_item)

    sell: list[dict[str, Any]] = []
    for symbol, position in current_map.items():
        if symbol in target_symbols:
            continue
        sell.append(
            {
                "symbol": symbol,
                "name": stock_names.get(symbol, str(position.get("name") or symbol.upper())),
                "qty": int(position.get("qty") or 0),
                "action": "exit_all",
                "reason": "not_in_target_positions",
            }
        )

    return {
        "status": "ok",
        "as_of_date_used": str(preview_payload.get("as_of_date_used") or ""),
        "buy": buy,
        "sell": sell,
        "hold": hold,
        "warnings": [],
    }


def _parse_iso_date(value: Any):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:10]).date()
    except Exception:
        return None


def _build_freshness(signal_date: str, market_summary: dict[str, Any]) -> dict[str, Any]:
    signal_day = _parse_iso_date(signal_date)
    market_day = _parse_iso_date((market_summary.get("summary") or {}).get("trade_date"))
    anchor_day = market_day or datetime.now(UTC).date()
    if signal_day is None:
        return {
            "status": "unknown",
            "signal_date": str(signal_date or ""),
            "anchor_date": str(anchor_day),
            "data_age_days": None,
            "label": "unknown",
        }
    age_days = max((anchor_day - signal_day).days, 0)
    stale = age_days > signal_staleness_threshold_days()
    return {
        "status": "stale" if stale else "fresh",
        "signal_date": str(signal_day),
        "anchor_date": str(anchor_day),
        "data_age_days": age_days,
        "label": "stale" if stale else "fresh",
    }


def _extract_exit_tags(experiment_summary: dict[str, Any]) -> list[str]:
    tags = [str(tag) for tag in experiment_summary.get("tags") or [] if str(tag).strip()]
    out = [
        tag
        for tag in tags
        if ("ATR" in tag.upper()) or ("\u6b62\u635f" in tag) or ("\u9000\u51fa" in tag) or ("\u542f\u76c8" in tag)
    ]
    return out[:4]


def _unique_warnings(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out






def _build_risk_flags(ops_snapshot: dict[str, Any], holding_sync: dict[str, Any]) -> dict[str, Any]:
    risk_lock = ops_snapshot.get("risk_lock") if isinstance(ops_snapshot.get("risk_lock"), dict) else {}
    executor = ops_snapshot.get("executor") if isinstance(ops_snapshot.get("executor"), dict) else {}
    drift_summary = holding_sync.get("drift_summary") if isinstance(holding_sync.get("drift_summary"), dict) else {}
    return {
        "holding_sync_status": str(holding_sync.get("status") or ""),
        "pending_ticket_drift": bool(drift_summary.get("pending_ticket_drift")),
        "risk_locked": bool(risk_lock.get("locked")),
        "risk_lock_reason": str(risk_lock.get("reason") or ""),
        "executor_declared": bool(executor.get("declared")),
        "executor_available": bool(executor.get("available", True)),
        "executor_reason": str(executor.get("reason") or ""),
    }


def _annotate_pending_tickets(
    items: list[dict[str, Any]],
    *,
    source_mode: str,
    snapshot_id: str,
    reconcile_id: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in list(items or []):
        if not isinstance(item, dict):
            continue
        is_current_surface = True
        surface_status = "current"
        if str(source_mode or "").strip().lower() == "position_aware_reconcile":
            is_current_surface = (
                str(item.get("snapshot_id") or "").strip() == str(snapshot_id or "").strip()
                and str(item.get("reconcile_id") or "").strip() == str(reconcile_id or "").strip()
            )
            surface_status = "current" if is_current_surface else "stale_surface"
        out.append(
            {
                **item,
                "is_current_surface": is_current_surface,
                "surface_status": surface_status,
            }
        )
    return out


def _build_reconcile_surface(*, results_root: Path, market_summary: dict[str, Any],
                             experiment_summary: dict[str, Any] | None,
                             ops_snapshot: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Account data is unavailable after removal; research output remains read-only."""
    del results_root, experiment_summary
    warning = "simulation account removed; account data is unavailable"
    holding_sync = {"status": "unavailable", "warnings": [warning]}
    surface = {
        "status": "unavailable", "source_mode": "experiment_fallback",
        "account_id": "", "holding_sync": holding_sync, "cash": None,
        "snapshot_id": "", "reconcile_id": "", "as_of_date": "",
        "positions": None, "action_sheet": [], "actions": {"buy": [], "sell": [], "hold": []},
        "freshness": _build_freshness("", market_summary),
        "risk_flags": _build_risk_flags(ops_snapshot, holding_sync),
        "warnings": [warning], "strategy_source": {}, "generated_at": "", "summary": None,
    }
    return surface, holding_sync, []












def _build_fallback_guidance(
    *,
    experiment_summary: dict[str, Any] | None,
    reconcile_surface: dict[str, Any],
) -> dict[str, Any]:
    warnings = list(reconcile_surface.get("warnings") or [])
    if not experiment_summary:
        warnings.append("latest experiment is missing")
    return {
        "status": "fallback_read_only",
        "source_mode": "experiment_fallback",
        "as_of_date_used": str(reconcile_surface.get("as_of_date") or ""),
        "buy": [],
        "sell": [],
        "hold": [],
        "warnings": _unique_warnings(warnings),
        "freshness": dict(reconcile_surface.get("freshness") or {}),
        "approval_cards": [],
    }


def _decision_label(status: str) -> str:
    mapping = {
        "approved_pending": "\u5df2\u786e\u8ba4\u5f85\u6267\u884c",
        "rejected": "\u5df2\u9a73\u56de",
        "revoked": "\u5df2\u64a4\u56de",
        "expired": "\u5df2\u8fc7\u671f",
        "none": "\u672a\u786e\u8ba4",
    }
    return mapping.get(str(status or "").strip().lower(), "\u672a\u786e\u8ba4")


def _build_blockers(
    *,
    suggestion_id: str,
    freshness: dict[str, Any],
    ops_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if str(freshness.get("status") or "") == "stale":
        blockers.append(
            {
                "code": "stale_data",
                "message": "\u6570\u636e\u5df2\u8fc7\u65f6\uff0c\u8bf7\u5148\u5237\u65b0\u7814\u7a76\u4ea7\u7269\u6216\u6267\u884c\u9884\u89c8",
            }
        )
    active_pending = ((ops_snapshot.get("active_pending_by_suggestion") or {}) if isinstance(ops_snapshot, dict) else {}).get(suggestion_id)
    if isinstance(active_pending, dict) and str(active_pending.get("ticket_id") or "").strip():
        blockers.append(
            {
                "code": "duplicate_submission",
                "message": f"\u5df2\u6709\u5f85\u6267\u884c ticket: {active_pending.get('ticket_id')}",
                "ticket_id": str(active_pending.get("ticket_id") or ""),
            }
        )
    risk_lock = ops_snapshot.get("risk_lock") if isinstance(ops_snapshot.get("risk_lock"), dict) else {}
    if bool(risk_lock.get("locked")):
        blockers.append(
            {
                "code": "risk_locked",
                "message": str(risk_lock.get("reason") or "\u98ce\u63a7\u9501\u5b9a\u751f\u6548\uff0c\u6682\u4e0d\u5141\u8bb8\u786e\u8ba4"),
            }
        )
    executor = ops_snapshot.get("executor") if isinstance(ops_snapshot.get("executor"), dict) else {}
    if bool(executor.get("declared")) and not bool(executor.get("available", True)):
        blockers.append(
            {
                "code": "executor_unavailable",
                "message": str(executor.get("reason") or "\u684c\u9762\u6267\u884c\u5668\u4e0d\u53ef\u7528"),
            }
        )
    return blockers


def _build_user_decision(suggestion_id: str, ops_snapshot: dict[str, Any]) -> dict[str, Any]:
    latest = ((ops_snapshot.get("latest_by_suggestion") or {}) if isinstance(ops_snapshot, dict) else {}).get(suggestion_id)
    if not isinstance(latest, dict):
        return {
            "status": "none",
            "status_label": _decision_label("none"),
            "ticket_id": "",
            "manual_adjusted": False,
            "updated_at": "",
            "final_qty": None,
            "final_target_weight": None,
            "reason": "",
        }
    reason = str(latest.get("reject_reason") or latest.get("revoke_reason") or "")
    status = str(latest.get("status") or "none")
    return {
        "status": status,
        "status_label": _decision_label(status),
        "ticket_id": str(latest.get("ticket_id") or ""),
        "manual_adjusted": bool(latest.get("manual_adjusted")),
        "updated_at": str(latest.get("updated_at") or ""),
        "final_qty": latest.get("final_qty"),
        "final_target_weight": latest.get("final_target_weight"),
        "reason": reason,
    }


def _build_approval_cards(
    *,
    experiment_summary: dict[str, Any],
    guidance: dict[str, Any],
    ops_snapshot: dict[str, Any],
    market_summary: dict[str, Any],
    positions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    signal_date = str(guidance.get("as_of_date_used") or experiment_summary.get("latest_trade_date") or "")
    freshness = _build_freshness(signal_date, market_summary)
    exit_tags = _extract_exit_tags(experiment_summary)
    current_qty_map = {
        str(item.get("symbol") or "").lower(): int(item.get("qty") or 0)
        for item in positions
        if isinstance(item, dict)
    }
    cards: list[dict[str, Any]] = []
    source_groups = [
        ("buy", "buy"),
        ("sell", "sell"),
        ("hold", "hold"),
    ]
    for bucket, field_name in source_groups:
        for item in guidance.get(field_name) or []:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol") or "").lower()
            action_type = "buy" if bucket == "buy" else "sell" if bucket == "sell" else "hold"
            suggestion_id = build_suggestion_id(
                exp_id=str(experiment_summary.get("exp_id") or ""),
                signal_date=signal_date,
                symbol=symbol,
                action_type=action_type,
            )
            system_suggestion = {
                "target_weight": _safe_number(item.get("target_weight")),
                "suggested_qty": int(item.get("qty") or 0) if bucket == "sell" else None,
                "current_qty": current_qty_map.get(symbol),
                "cap_reason": str(item.get("cap_reason") or ""),
            }
            card_freshness = dict(freshness)
            blockers = _build_blockers(
                suggestion_id=suggestion_id,
                freshness=card_freshness,
                ops_snapshot=ops_snapshot,
            )
            user_decision = _build_user_decision(suggestion_id, ops_snapshot)
            can_confirm = bucket in {"buy", "sell"} and not blockers
            can_reject = bucket in {"buy", "sell"} and str(user_decision.get("status") or "") != "approved_pending"
            cards.append(
                {
                    "suggestion_id": suggestion_id,
                    "exp_id": str(experiment_summary.get("exp_id") or ""),
                    "signal_date": signal_date,
                    "symbol": symbol,
                    "name": str(item.get("name") or symbol.upper()),
                    "bucket": bucket,
                    "action_type": action_type,
                    "system_suggestion": system_suggestion,
                    "reason_tags": list(item.get("reasons") or ([] if not item.get("reason") else [item.get("reason")])),
                    "exit_tags": exit_tags,
                    "freshness": card_freshness,
                    "blockers": blockers,
                    "user_decision": user_decision,
                    "can_confirm": can_confirm,
                    "can_reject": can_reject,
                    "can_edit": can_confirm,
                }
            )
    cards.sort(key=lambda item: (str(item.get("bucket") or ""), str(item.get("symbol") or "")))
    return cards


def build_mobile_dashboard(results_root: Path, preview_loader: PreviewLoader | None = None) -> dict[str, Any]:
    errors: list[str] = []
    experiment_context, experiment_errors = _load_latest_experiment(results_root)
    errors.extend(experiment_errors)
    market_summary, _market_snapshot = _read_latest_market_snapshot(results_root)

    if experiment_context is None:
        return {
            "status": "empty",
            "updated_at": _now_iso(),
            "experiment": None,
            "guidance": {
                "status": "empty",
                "as_of_date_used": None,
                "buy": [],
                "sell": [],
                "hold": [],
                "warnings": ["暂无可用实验，无法生成手机端指引"],
            },
            "market": market_summary,
            "positions": [],
            "warnings": errors + list(market_summary.get("warnings") or []),
            "errors": errors,
        }

    preview_payload: dict[str, Any] | None = None
    preview_error = ""
    config_json = experiment_context.get("config_json")
    if preview_loader is not None and isinstance(config_json, dict):
        try:
            preview_payload = preview_loader(
                config_json,
                str(experiment_context["summary"]["exp_id"]),
                str(experiment_context["summary"]["latest_trade_date"] or "") or None,
            )
        except Exception as exc:
            preview_error = str(exc)
    elif preview_loader is not None:
        preview_error = "latest experiment is missing config_json"

    if preview_error:
        errors.append(preview_error)

    guidance = _build_guidance(
        current_positions=list(experiment_context.get("current_positions") or []),
        preview_payload=preview_payload,
        stock_names=dict(experiment_context.get("stock_names") or {}),
    )
    if preview_error and guidance.get("status") != "ok":
        guidance_warnings = list(guidance.get("warnings") or [])
        guidance_warnings.insert(0, preview_error)
        guidance["warnings"] = guidance_warnings
    ops_snapshot = load_mobile_control_state(results_root)
    signal_date = str(guidance.get("as_of_date_used") or experiment_context["summary"].get("latest_trade_date") or "")
    guidance["freshness"] = _build_freshness(signal_date, market_summary)
    guidance["approval_cards"] = _build_approval_cards(
        experiment_summary=dict(experiment_context.get("summary") or {}),
        guidance=guidance,
        ops_snapshot=ops_snapshot,
        market_summary=market_summary,
        positions=list(experiment_context.get("current_positions") or []),
    )
    guidance["pending_tickets"] = list(ops_snapshot.get("pending_tickets") or [])
    guidance["pending_count"] = len(guidance["pending_tickets"])
    if str(guidance.get("freshness", {}).get("status") or "") == "stale":
        guidance_warnings = list(guidance.get("warnings") or [])
        guidance_warnings.insert(0, "mobile dashboard signal snapshot is stale")
        guidance["warnings"] = guidance_warnings

    return {
        "status": "ok",
        "updated_at": _now_iso(),
        "experiment": experiment_context.get("summary"),
        "guidance": guidance,
        "market": market_summary,
        "positions": experiment_context.get("current_positions") or [],
        "warnings": errors + list(market_summary.get("warnings") or []) + list(guidance.get("warnings") or []),
        "errors": errors,
    }


def _build_mobile_dashboard_v2(results_root: Path, preview_loader: PreviewLoader | None = None) -> dict[str, Any]:
    del preview_loader
    errors: list[str] = []
    experiment_context, experiment_errors = _load_latest_experiment(results_root)
    errors.extend(experiment_errors)
    market_summary, _market_snapshot = _read_latest_market_snapshot(results_root)
    lifecycle_missing = False
    try:
        ops_snapshot = load_mobile_control_state(results_root)
        execution_tickets = list_execution_tickets(results_root)
    except OpsDomainSchemaMissing:
        lifecycle_missing = True
        ops_snapshot = {}
        execution_tickets = None
        errors.append("transaction lifecycle storage is unavailable")
    experiment_summary = dict(experiment_context.get("summary") or {}) if isinstance(experiment_context, dict) else None
    reconcile_surface, holding_sync, positions = _build_reconcile_surface(
        results_root=results_root,
        market_summary=market_summary,
        experiment_summary=experiment_summary,
        ops_snapshot=ops_snapshot,
    )
    if lifecycle_missing:
        reconcile_surface["risk_flags"].update({
            "pending_ticket_drift": None, "risk_locked": None, "risk_lock_reason": "transaction_lifecycle_schema_missing",
            "executor_declared": None, "executor_available": None, "executor_reason": "transaction_lifecycle_schema_missing",
        })
    refresh_status = {"status": "unavailable", "reason": "simulation_account_removed"}

    guidance = _build_fallback_guidance(experiment_summary=experiment_summary, reconcile_surface=reconcile_surface)

    if lifecycle_missing:
        guidance["pending_tickets"] = None
        guidance["pending_count"] = None
        guidance["execution_tickets"] = None
        guidance["execution_count"] = None
    else:
        guidance["pending_tickets"] = _annotate_pending_tickets(
            list(ops_snapshot.get("pending_tickets") or []),
            source_mode=str(reconcile_surface.get("source_mode") or ""),
            snapshot_id=str(reconcile_surface.get("snapshot_id") or ""),
            reconcile_id=str(reconcile_surface.get("reconcile_id") or ""),
        )
        guidance["pending_count"] = len(guidance["pending_tickets"])
        guidance["execution_tickets"] = _annotate_pending_tickets(
            execution_tickets,
            source_mode=str(reconcile_surface.get("source_mode") or ""),
            snapshot_id=str(reconcile_surface.get("snapshot_id") or ""),
            reconcile_id=str(reconcile_surface.get("reconcile_id") or ""),
        )
        guidance["execution_count"] = len(guidance["execution_tickets"])
    warnings = _unique_warnings(
        errors
        + list(market_summary.get("warnings") or [])
        + list(guidance.get("warnings") or [])
        + list(holding_sync.get("warnings") or [])
        + list(reconcile_surface.get("warnings") or [])
    )
    status = "degraded" if lifecycle_missing else ("ok" if experiment_context is not None else "empty")
    if lifecycle_missing:
        briefing = {"status": "unavailable", "reason": "transaction_lifecycle_schema_missing"}
        notifications = {"status": "unavailable", "reason": "transaction_lifecycle_schema_missing", "items": None, "count": None}
    else:
        briefing = build_mobile_daily_briefing(
            results_root,
            experiment_summary=experiment_summary,
            guidance=guidance,
            holding_sync=holding_sync,
            reconcile_surface=reconcile_surface,
            market_summary=market_summary,
        )
        notifications = build_mobile_notification_feed(results_root, briefing=briefing)

    return {
        "status": status,
        "updated_at": _now_iso(),
        "lifecycle_status": {"status": "unavailable", "reason": "transaction_lifecycle_schema_missing"} if lifecycle_missing else None,
        "source_mode": str(reconcile_surface.get("source_mode") or ""),
        "experiment": experiment_summary,
        "holding_sync": holding_sync,
        "reconcile": reconcile_surface,
        "guidance": guidance,
        "market": market_summary,
        "positions": None,
        "briefing": briefing,
        "notifications": notifications,
        "reconcile_refresh": refresh_status,
        "freshness": dict(reconcile_surface.get("freshness") or {}),
        "risk_flags": dict(reconcile_surface.get("risk_flags") or {}),
        "warnings": warnings,
        "errors": errors,
    }


build_mobile_dashboard = _build_mobile_dashboard_v2
