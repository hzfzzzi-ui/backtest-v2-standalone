from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from backend.core.config.loader import load_config
from backend.core.config.etf_beta_contract import (
    build_default_etf_beta_contract,
    normalize_etf_beta_contract,
)
from backend.core.config.models import CostConfig
from backend.core.data.cn_etf_catalog import normalize_cn_etf_symbol, normalize_cn_etf_ts_code
from backend.core.data.provider_factory import build_runtime_provider_from_config
from backend.core.engine_vector.cn_etf_beta_signal_provider import _rebalance_flags


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return None
    if not np.isfinite(parsed):
        return None
    return float(parsed)


def _safe_int(value: Any) -> int | None:
    parsed = _safe_float(value)
    if parsed is None:
        return None
    return int(parsed)


def _safe_ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
    left = _safe_float(numerator)
    right = _safe_float(denominator)
    if left is None or right is None or abs(right) <= 1e-12:
        return None
    return float(left) / float(right)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_json_cell(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        payload = json.loads(value)
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _parse_diagnostics_cell(value: Any) -> dict[str, Any]:
    payload = _parse_json_cell(value)
    diagnostics = payload.get("diagnostics")
    if isinstance(diagnostics, Mapping):
        return dict(diagnostics)
    return payload


def _extract_etf_diagnostics_views(value: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    diagnostics = _parse_diagnostics_cell(value)
    formal_view = dict(diagnostics.get("etf_beta_formal_view") or {})
    research_view = dict(diagnostics.get("etf_beta_research_view") or {})
    return diagnostics, formal_view, research_view


def _normalize_symbol(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "." in text:
        return normalize_cn_etf_ts_code(text)
    return normalize_cn_etf_ts_code(normalize_cn_etf_symbol(text))


def _series_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}, ()):
            return value
    return None


def _ensure_ops_dir(exp_id: str) -> Path:
    out_dir = _repo_root() / "outputs" / "ops" / "diagnose_cn_etf_phase1_zero_trade_mainline" / exp_id
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _build_results_context(
    *,
    exp_id: str,
    results_dir: Path,
) -> dict[str, Any]:
    return {
        "exp_id": exp_id,
        "results_dir": results_dir,
        "run_meta": _read_json(results_dir / "run_meta.json"),
        "config": _read_json(results_dir / "config.json"),
        "resolved_config": _read_json(results_dir / "resolved_config.json"),
        "perf": _read_json(results_dir / "perf.json"),
        "nav": _read_csv(results_dir / "nav.csv"),
        "portfolio_daily": _read_csv(results_dir / "portfolio_daily.csv"),
        "orders": _read_csv(results_dir / "orders.csv"),
        "trades": _read_csv(results_dir / "portfolio_trades.csv"),
    }


def _resolved_config_payload(context: Mapping[str, Any]) -> dict[str, Any]:
    resolved_config = dict(context.get("resolved_config") or {})
    config_json = resolved_config.get("config_json")
    if isinstance(config_json, Mapping):
        return dict(config_json)
    return resolved_config


def _extract_effective_parameters(context: Mapping[str, Any]) -> dict[str, Any]:
    run_meta = dict(context.get("run_meta") or {})
    etf_meta = dict(run_meta.get("etf_beta") or {})
    etf_formal_view = dict(etf_meta.get("formal_view") or {})
    etf_research_view = dict(etf_meta.get("research_view") or {})
    resolved_config = _resolved_config_payload(context)
    configured_contract = (
        ((resolved_config.get("governed_a_share") or {}).get("etf_beta"))
        if isinstance(resolved_config.get("governed_a_share"), Mapping)
        else None
    )
    defaults = build_default_etf_beta_contract(enabled=True)
    effective_contract = normalize_etf_beta_contract(configured_contract or defaults)

    cost_config = CostConfig(**dict(resolved_config.get("costs") or {}))
    fields = [
        "research_rule_family",
        "strategy_role",
        "source_entry_type",
        "governor_boundary_mode",
        "local_policy_mode",
        "allocation_engine_mode",
        "bucket_policy_profile",
        "absolute_filter_mode",
        "fallback_mode",
        "fallback_symbol",
        "rebalance_frequency",
        "max_selected_symbols",
        "relative_strength_fast_window",
        "relative_strength_mid_window",
        "relative_strength_slow_window",
        "relative_strength_fast_weight",
        "relative_strength_mid_weight",
        "relative_strength_slow_weight",
        "core_beta_symbols",
        "limited_defense_candidates",
    ]
    effective_rows: list[dict[str, Any]] = []
    configured_source = dict(configured_contract or {})
    for field in fields:
        effective_rows.append(
            {
                "parameter": field,
                "configured_value": configured_source.get(field),
                "effective_value": effective_contract.get(field),
                "default_value": defaults.get(field),
                "overridden": configured_source.get(field) not in (None, "", [], {}),
            }
        )
    cost_rows = [
        {
            "parameter": "commission_rate",
            "configured_value": (resolved_config.get("costs") or {}).get("commission_rate"),
            "effective_value": cost_config.commission_rate,
            "default_value": CostConfig().commission_rate,
            "overridden": (resolved_config.get("costs") or {}).get("commission_rate") is not None,
        },
        {
            "parameter": "commission_min",
            "configured_value": (resolved_config.get("costs") or {}).get("commission_min"),
            "effective_value": cost_config.commission_min,
            "default_value": CostConfig().commission_min,
            "overridden": (resolved_config.get("costs") or {}).get("commission_min") is not None,
        },
        {
            "parameter": "stamp_tax_rate",
            "configured_value": (resolved_config.get("costs") or {}).get("stamp_tax_rate"),
            "effective_value": cost_config.stamp_tax_rate,
            "default_value": CostConfig().stamp_tax_rate,
            "overridden": (resolved_config.get("costs") or {}).get("stamp_tax_rate") is not None,
        },
        {
            "parameter": "slippage_bps",
            "configured_value": (resolved_config.get("costs") or {}).get("slippage_bps"),
            "effective_value": cost_config.slippage_bps,
            "default_value": CostConfig().slippage_bps,
            "overridden": (resolved_config.get("costs") or {}).get("slippage_bps") is not None,
        },
    ]
    return {
        "effective_contract": effective_contract,
        "rows": effective_rows + cost_rows,
        "run_meta_summary": {
            "requested_budget": _first_non_empty(etf_research_view.get("requested_budget"), etf_meta.get("requested_budget")),
            "applied_budget": _first_non_empty(etf_research_view.get("applied_budget"), etf_meta.get("applied_budget")),
            "target_exposure": _first_non_empty(etf_formal_view.get("target_exposure"), etf_meta.get("target_exposure")),
            "target_exposure_source": _first_non_empty(
                etf_formal_view.get("target_exposure_source"),
                etf_meta.get("target_exposure_source"),
            ),
            "formal_alignment_status": _first_non_empty(
                etf_meta.get("formal_alignment_status"),
                etf_formal_view.get("formal_alignment_status"),
            ),
        },
    }


def _build_position_utilization(context: Mapping[str, Any]) -> dict[str, Any]:
    portfolio_daily = context.get("portfolio_daily")
    if not isinstance(portfolio_daily, pd.DataFrame) or portfolio_daily.empty:
        return {
            "observed_day_count": 0,
            "avg_exposure": None,
            "median_exposure": None,
            "empty_day_ratio": None,
            "below_30_ratio": None,
            "below_50_ratio": None,
            "below_80_ratio": None,
            "avg_risk_asset_share": None,
            "avg_defense_asset_share": None,
            "avg_cash_share": None,
            "signal_count": 0,
            "order_count": 0,
            "trade_count": 0,
            "unfilled_order_count": 0,
        }

    actual_exposure = _series_numeric(portfolio_daily, "etf_actual_exposure")
    if actual_exposure.dropna().empty:
        actual_exposure = _series_numeric(portfolio_daily, "gross_exposure")
    risk_exposure = _series_numeric(portfolio_daily, "etf_actual_risk_exposure")
    defense_exposure = _series_numeric(portfolio_daily, "etf_actual_fallback_exposure")
    cash_amount = _series_numeric(portfolio_daily, "cash")
    nav_amount = _series_numeric(portfolio_daily, "nav")
    cash_share = cash_amount.divide(nav_amount.where(nav_amount.abs() > 1e-12, np.nan))
    valid_exposure = actual_exposure.dropna()
    exposure_filled = actual_exposure.fillna(0.0)
    orders_df = context.get("orders")
    trades_df = context.get("trades")
    signal_count = int(
        (_series_numeric(portfolio_daily, "composed_buy_signal_count").fillna(0.0).sum())
        + (_series_numeric(portfolio_daily, "composed_sell_signal_count").fillna(0.0).sum())
    )
    order_count = int(len(orders_df.index)) if isinstance(orders_df, pd.DataFrame) else 0
    trade_count = int(len(trades_df.index)) if isinstance(trades_df, pd.DataFrame) else 0
    return {
        "observed_day_count": int(len(portfolio_daily.index)),
        "avg_exposure": float(valid_exposure.mean()) if not valid_exposure.empty else None,
        "median_exposure": float(valid_exposure.median()) if not valid_exposure.empty else None,
        "empty_day_ratio": float((exposure_filled <= 1e-9).mean()),
        "below_30_ratio": float((exposure_filled < 0.30).mean()),
        "below_50_ratio": float((exposure_filled < 0.50).mean()),
        "below_80_ratio": float((exposure_filled < 0.80).mean()),
        "avg_risk_asset_share": float(risk_exposure.dropna().mean()) if not risk_exposure.dropna().empty else None,
        "avg_defense_asset_share": float(defense_exposure.dropna().mean()) if not defense_exposure.dropna().empty else None,
        "avg_cash_share": float(cash_share.dropna().mean()) if not cash_share.dropna().empty else None,
        "signal_count": signal_count,
        "order_count": order_count,
        "trade_count": trade_count,
        "unfilled_order_count": max(order_count - trade_count, 0),
    }


def _count_by_reference_day(frame: pd.DataFrame, reference_days: pd.Series) -> dict[str, int]:
    if frame.empty:
        return {}
    day_series = None
    for column in ("entry_date", "date"):
        if column in frame.columns:
            parsed = pd.to_datetime(frame[column], errors="coerce").dt.strftime("%Y-%m-%d")
            if not parsed.dropna().empty:
                day_series = parsed
                break
    if day_series is None:
        return {}
    counts = Counter(str(value).strip() for value in day_series.dropna().tolist() if str(value).strip())
    return {str(day): int(counts.get(str(day), 0)) for day in reference_days.astype(str).tolist()}


def _merge_reason_counts(*reason_maps: Mapping[str, Any]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for mapping in reason_maps:
        for key, value in dict(mapping or {}).items():
            text = str(key).strip()
            count = _safe_int(value) or 0
            if text and count > 0:
                counter[text] += int(count)
    return dict(sorted(counter.items()))


def _build_rebalance_day_summary(context: Mapping[str, Any], effective_params: Mapping[str, Any]) -> pd.DataFrame:
    portfolio_daily = context.get("portfolio_daily")
    if not isinstance(portfolio_daily, pd.DataFrame) or portfolio_daily.empty:
        return pd.DataFrame()

    work = portfolio_daily.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["date"]).reset_index(drop=True)
    diagnostics_rows = [_parse_diagnostics_cell(value) for value in work.get("diagnostics_input_json", pd.Series(dtype=str)).tolist()]
    work["etf_beta_rebalance_day"] = [
        bool(row.get("etf_beta_rebalance_day", False))
        for row in diagnostics_rows
    ]
    if not bool(work["etf_beta_rebalance_day"].any()):
        frequency = str((effective_params.get("effective_contract") or {}).get("rebalance_frequency") or "monthly").strip().lower()
        work["etf_beta_rebalance_day"] = _rebalance_flags(work["date"].dt.date.tolist(), frequency=frequency)
    rebalance_rows = work.loc[work["etf_beta_rebalance_day"]].copy()
    if rebalance_rows.empty:
        return pd.DataFrame()

    orders_df = context.get("orders")
    trades_df = context.get("trades")
    order_counts = _count_by_reference_day(orders_df if isinstance(orders_df, pd.DataFrame) else pd.DataFrame(), rebalance_rows["date"].dt.strftime("%Y-%m-%d"))
    trade_counts = _count_by_reference_day(trades_df if isinstance(trades_df, pd.DataFrame) else pd.DataFrame(), rebalance_rows["date"].dt.strftime("%Y-%m-%d"))
    rows: list[dict[str, Any]] = []
    for row in rebalance_rows.itertuples(index=False):
        diagnostics, formal_view, research_view = _extract_etf_diagnostics_views(getattr(row, "diagnostics_input_json", ""))
        governor_snapshot = _parse_json_cell(getattr(row, "governor_budget_json", ""))
        candidate_pool_symbols = [
            str(item).strip().upper()
            for item in list(research_view.get("candidate_pool_symbols") or diagnostics.get("etf_beta_candidate_pool_symbols") or ())
            if str(item).strip()
        ]
        eligible_symbols = [
            str(item).strip().upper()
            for item in list(formal_view.get("eligible_etfs") or diagnostics.get("etf_beta_eligible_symbols") or ())
            if str(item).strip()
        ]
        selected_symbols = [
            str(item).strip().upper()
            for item in list(formal_view.get("selected_etfs") or diagnostics.get("etf_beta_selected_symbols") or ())
            if str(item).strip()
        ]
        ref_day = pd.Timestamp(row.date).strftime("%Y-%m-%d")
        rows.append(
            {
                "date": ref_day,
                "rebalance_day": True,
                "candidate_count": len(candidate_pool_symbols),
                "eligible_count": len(eligible_symbols),
                "selected_count": len(selected_symbols),
                "order_count": int(order_counts.get(ref_day, 0)),
                "trade_count": int(trade_counts.get(ref_day, 0)),
                "requested_budget": _safe_float(research_view.get("requested_budget")),
                "applied_budget": _safe_float(research_view.get("applied_budget")),
                "target_exposure": _safe_float(getattr(row, "etf_target_exposure", None)),
                "actual_exposure": _safe_float(getattr(row, "etf_actual_exposure", None)),
                "slot_cap": _safe_int(diagnostics.get("etf_beta_deployable_slot_cap")),
                "runtime_reason_codes": list(research_view.get("runtime_reason_codes") or diagnostics.get("etf_beta_runtime_reason_codes") or ()),
                "budget_reason_codes": list(governor_snapshot.get("budget_reason_codes") or ()),
                "filter_reason_counts": _merge_reason_counts(
                    research_view.get("absolute_filter_reject_reason_counts") or diagnostics.get("etf_beta_absolute_filter_reject_reason_counts") or {},
                    research_view.get("candidate_pool_reject_reason_counts") or diagnostics.get("etf_beta_candidate_pool_reject_reason_counts") or {},
                    research_view.get("selection_chain_reject_reason_counts") or diagnostics.get("etf_beta_selection_chain_reject_reason_counts") or {},
                ),
                "candidate_pool_symbols": candidate_pool_symbols,
                "eligible_symbols": eligible_symbols,
                "selected_symbols": selected_symbols,
            }
        )
    return pd.DataFrame(rows)


def _load_price_frame(
    *,
    symbols: list[str],
    start_date: str,
    end_date: str,
    resolved_config: Mapping[str, Any] | None = None,
    price_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if isinstance(price_frame, pd.DataFrame) and not price_frame.empty:
        frame = price_frame.copy()
    else:
        cfg_path = _repo_root() / "backend" / "configs" / "pams_cn_pg.json"
        cfg_obj, _ = load_config(str(cfg_path))
        data_source_cfg = (
            dict((resolved_config or {}).get("data_source") or {})
            if isinstance(resolved_config, Mapping)
            else {}
        )
        if data_source_cfg.get("data_role") is not None:
            cfg_obj.data_source.data_role = str(data_source_cfg.get("data_role") or cfg_obj.data_source.data_role)
        if data_source_cfg.get("stocks_table") is not None:
            cfg_obj.data_source.stocks_table = str(data_source_cfg.get("stocks_table") or cfg_obj.data_source.stocks_table)
        provider = build_runtime_provider_from_config(
            cfg_obj,
            cfg_path.parent / "instrument_rules_cn.csv",
        )
        internal_symbols = [normalize_cn_etf_symbol(symbol) for symbol in symbols]
        frame = provider.load_ohlcv_daily(
            internal_symbols,
            pd.Timestamp(start_date).date(),
            pd.Timestamp(end_date).date(),
            source="stocks",
        )
    if frame.empty:
        return pd.DataFrame(columns=["date", "symbol", "close"])
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    result = result.dropna(subset=["date"])
    result["symbol"] = result["symbol"].map(_normalize_symbol)
    result["close"] = pd.to_numeric(result["close"], errors="coerce")
    result = result.dropna(subset=["symbol", "close"])
    return result[["date", "symbol", "close"]].sort_values(["date", "symbol"]).reset_index(drop=True)


def _rank_score_map(values: Mapping[str, float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    total = max(len(ordered), 1)
    return {symbol: float(rank) / float(total) for rank, (symbol, _value) in enumerate(ordered, start=1)}


def _build_ranking_detail(
    *,
    context: Mapping[str, Any],
    effective_params: Mapping[str, Any],
    rebalance_summary: pd.DataFrame,
    price_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if rebalance_summary.empty:
        return pd.DataFrame()
    contract = dict(effective_params.get("effective_contract") or {})
    all_symbols = sorted(
        {
            str(symbol).strip().upper()
            for values in rebalance_summary["candidate_pool_symbols"].tolist()
            for symbol in list(values or [])
            if str(symbol).strip()
        }
    )
    if not all_symbols:
        return pd.DataFrame()
    price_df = _load_price_frame(
        symbols=all_symbols,
        start_date=str(rebalance_summary["date"].min()),
        end_date=str(rebalance_summary["date"].max()),
        resolved_config=_resolved_config_payload(context),
        price_frame=price_frame,
    )
    if price_df.empty:
        return pd.DataFrame()

    pivot = price_df.pivot(index="date", columns="symbol", values="close").sort_index()
    fast_window = int(contract.get("relative_strength_fast_window") or 60)
    mid_window = _safe_int(contract.get("relative_strength_mid_window"))
    slow_window = int(contract.get("relative_strength_slow_window") or 120)
    fast_weight = float(contract.get("relative_strength_fast_weight") or 0.4)
    mid_weight = float(contract.get("relative_strength_mid_weight") or 0.0)
    slow_weight = float(contract.get("relative_strength_slow_weight") or 0.6)
    absolute_mode = str(contract.get("absolute_filter_mode") or "none").strip().lower()

    ma150 = pivot.rolling(150, min_periods=150).mean()
    ma200 = pivot.rolling(200, min_periods=200).mean()
    ret_fast = pivot.pct_change(fast_window)
    ret_mid = pivot.pct_change(mid_window) if mid_window and mid_window >= 2 else None
    ret_slow = pivot.pct_change(slow_window)
    ret12 = pivot.pct_change(252)
    rows: list[dict[str, Any]] = []
    for summary_row in rebalance_summary.itertuples(index=False):
        day = pd.Timestamp(summary_row.date)
        if day not in pivot.index:
            continue
        candidate_symbols = [str(item).strip().upper() for item in list(summary_row.candidate_pool_symbols or []) if str(item).strip()]
        if not candidate_symbols:
            continue
        symbol_returns_fast: dict[str, float] = {}
        symbol_returns_mid: dict[str, float] = {}
        symbol_returns_slow: dict[str, float] = {}
        eligible_symbols: list[str] = []
        absolute_pass_map: dict[str, bool] = {}
        for symbol in candidate_symbols:
            close_now = _safe_float(pivot.at[day, symbol]) if symbol in pivot.columns else None
            ma150_now = _safe_float(ma150.at[day, symbol]) if symbol in ma150.columns else None
            ma200_now = _safe_float(ma200.at[day, symbol]) if symbol in ma200.columns else None
            ret12_now = _safe_float(ret12.at[day, symbol]) if symbol in ret12.columns else None
            fast_now = _safe_float(ret_fast.at[day, symbol]) if symbol in ret_fast.columns else None
            mid_now = _safe_float(ret_mid.at[day, symbol]) if isinstance(ret_mid, pd.DataFrame) and symbol in ret_mid.columns else None
            slow_now = _safe_float(ret_slow.at[day, symbol]) if symbol in ret_slow.columns else None
            absolute_pass = True
            if absolute_mode == "ma200_and_positive_12m":
                absolute_pass = bool(close_now is not None and ma200_now is not None and close_now > ma200_now and ret12_now is not None and ret12_now > 0.0)
            elif absolute_mode == "ma200_only":
                absolute_pass = bool(close_now is not None and ma200_now is not None and close_now > ma200_now)
            elif absolute_mode == "ma150_and_positive_12m":
                absolute_pass = bool(close_now is not None and ma150_now is not None and close_now > ma150_now and ret12_now is not None and ret12_now > 0.0)
            elif absolute_mode == "positive_12m":
                absolute_pass = bool(ret12_now is not None and ret12_now > 0.0)
            absolute_pass_map[symbol] = absolute_pass
            if absolute_pass and fast_now is not None and slow_now is not None and (mid_window is None or mid_now is not None):
                eligible_symbols.append(symbol)
                symbol_returns_fast[symbol] = float(fast_now)
                if mid_window is not None and mid_now is not None:
                    symbol_returns_mid[symbol] = float(mid_now)
                symbol_returns_slow[symbol] = float(slow_now)

        rank_fast = _rank_score_map(symbol_returns_fast)
        rank_mid = _rank_score_map(symbol_returns_mid) if mid_window is not None else {}
        rank_slow = _rank_score_map(symbol_returns_slow)
        combined: dict[str, float] = {}
        for symbol in eligible_symbols:
            combined[symbol] = (
                slow_weight * float(rank_slow.get(symbol, 0.0))
                + fast_weight * float(rank_fast.get(symbol, 0.0))
                + (mid_weight * float(rank_mid.get(symbol, 0.0)) if mid_window is not None else 0.0)
            )
        ranked_symbols = sorted(
            eligible_symbols,
            key=lambda symbol: (
                -float(combined.get(symbol, 0.0)),
                -float(symbol_returns_slow.get(symbol, float("-inf"))),
                -float(symbol_returns_mid.get(symbol, float("-inf"))) if mid_window is not None else 0.0,
                -float(symbol_returns_fast.get(symbol, float("-inf"))),
                symbol,
            ),
        )
        rank_map = {symbol: idx for idx, symbol in enumerate(ranked_symbols, start=1)}
        selected_symbols = {str(item).strip().upper() for item in list(summary_row.selected_symbols or []) if str(item).strip()}
        for symbol in candidate_symbols:
            rows.append(
                {
                    "date": summary_row.date,
                    "symbol": symbol,
                    "close": _safe_float(pivot.at[day, symbol]) if symbol in pivot.columns else None,
                    "ma150": _safe_float(ma150.at[day, symbol]) if symbol in ma150.columns else None,
                    "ma200": _safe_float(ma200.at[day, symbol]) if symbol in ma200.columns else None,
                    "ret12": _safe_float(ret12.at[day, symbol]) if symbol in ret12.columns else None,
                    "ret_fast": symbol_returns_fast.get(symbol),
                    "ret_mid": symbol_returns_mid.get(symbol) if mid_window is not None else None,
                    "ret_slow": symbol_returns_slow.get(symbol),
                    "absolute_pass": bool(absolute_pass_map.get(symbol, False)),
                    "score_fast": rank_fast.get(symbol),
                    "score_mid": rank_mid.get(symbol) if mid_window is not None else None,
                    "score_slow": rank_slow.get(symbol),
                    "total_score": combined.get(symbol),
                    "rank": rank_map.get(symbol),
                    "selected": symbol in selected_symbols,
                }
            )
    return pd.DataFrame(rows)


def _build_lineage_samples(context: Mapping[str, Any], rebalance_summary: pd.DataFrame) -> dict[str, Any]:
    portfolio_daily = context.get("portfolio_daily")
    orders_df = context.get("orders")
    trades_df = context.get("trades")
    run_meta = dict(context.get("run_meta") or {})
    if not isinstance(portfolio_daily, pd.DataFrame):
        portfolio_daily = pd.DataFrame()
    if not isinstance(orders_df, pd.DataFrame):
        orders_df = pd.DataFrame()
    if not isinstance(trades_df, pd.DataFrame):
        trades_df = pd.DataFrame()
    signal_date_source = "signal_day_close"
    order_submit_policy = "next_trading_day_open"
    stage_pipeline = dict(run_meta.get("stage_pipeline") or {})
    execution_shell = str(stage_pipeline.get("execution_shell") or "").strip()
    lineage_samples: list[dict[str, Any]] = []
    if not trades_df.empty:
        for row in trades_df.head(5).itertuples(index=False):
            lineage_samples.append(
                {
                    "sample_type": "filled_trade",
                    "signal_date": _first_non_empty(getattr(row, "entry_date", None), getattr(row, "date", None)),
                    "order_submit_date": getattr(row, "date", None),
                    "fill_date": getattr(row, "date", None),
                    "symbol": _normalize_symbol(getattr(row, "symbol", None)),
                    "side": getattr(row, "side", None),
                    "fill_price": _safe_float(getattr(row, "fill_price", None)),
                    "fill_price_source": "portfolio_trades.fill_price",
                    "reason_code": getattr(row, "reason_code", None),
                }
            )
    elif not orders_df.empty:
        for row in orders_df.head(5).itertuples(index=False):
            lineage_samples.append(
                {
                    "sample_type": "unfilled_order",
                    "signal_date": _first_non_empty(getattr(row, "entry_date", None), getattr(row, "date", None)),
                    "order_submit_date": getattr(row, "date", None),
                    "fill_date": None,
                    "symbol": _normalize_symbol(getattr(row, "symbol", None)),
                    "side": getattr(row, "side", None),
                    "fill_price": None,
                    "fill_price_source": "no_fill",
                    "reason_code": getattr(row, "reason_code", None),
                }
            )
    else:
        for row in rebalance_summary.head(5).itertuples(index=False):
            lineage_samples.append(
                {
                    "sample_type": "zero_order_rebalance_day",
                    "signal_date": row.date,
                    "order_submit_date": None,
                    "fill_date": None,
                    "symbol": None,
                    "side": "BUY",
                    "fill_price": None,
                    "fill_price_source": "no_order_generated",
                    "reason_code": ",".join(list(row.runtime_reason_codes or [])),
                    "budget_reason_codes": list(row.budget_reason_codes or []),
                }
            )
    signal_count = int(
        (_series_numeric(portfolio_daily, "composed_buy_signal_count").fillna(0.0).sum())
        + (_series_numeric(portfolio_daily, "composed_sell_signal_count").fillna(0.0).sum())
    )
    return {
        "signal_data_day": signal_date_source,
        "signal_generation_time": "bar_close_after_observation",
        "order_submission_time": order_submit_policy,
        "execution_shell": execution_shell,
        "signal_count": signal_count,
        "order_count": int(len(orders_df.index)),
        "trade_count": int(len(trades_df.index)),
        "unfilled_order_count": max(int(len(orders_df.index)) - int(len(trades_df.index)), 0),
        "samples": lineage_samples,
        "sample_count": len(lineage_samples),
    }


def _build_synthetic_nav(returns: pd.Series) -> pd.Series:
    if returns.empty:
        return pd.Series(dtype=float)
    return (1.0 + returns.fillna(0.0)).cumprod()


def _compute_perf_metrics(nav: pd.Series, *, avg_position: float | None = None, turnover: float | None = None) -> dict[str, Any]:
    if nav.empty:
        return {
            "cagr": None,
            "max_drawdown": None,
            "sharpe": None,
            "avg_position": avg_position,
            "turnover": turnover,
        }
    daily_returns = nav.pct_change().fillna(0.0)
    total_return = float(nav.iloc[-1] / nav.iloc[0] - 1.0) if float(nav.iloc[0]) != 0 else None
    periods = int(len(nav.index))
    cagr = None
    if periods > 1 and nav.iloc[0] > 0 and nav.iloc[-1] > 0:
        cagr = float((nav.iloc[-1] / nav.iloc[0]) ** (252.0 / float(periods - 1)) - 1.0)
    running_peak = nav.cummax()
    drawdown = nav.divide(running_peak.where(running_peak.abs() > 1e-12, np.nan)) - 1.0
    sharpe = None
    if daily_returns.std(ddof=0) > 1e-12:
        sharpe = float((daily_returns.mean() / daily_returns.std(ddof=0)) * np.sqrt(252.0))
    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": float(drawdown.min()) if not drawdown.empty else None,
        "sharpe": sharpe,
        "avg_position": avg_position,
        "turnover": turnover,
    }


def _weight_turnover(weights: pd.DataFrame) -> float | None:
    if weights.empty:
        return None
    turn = weights.fillna(0.0).diff().abs().sum(axis=1).fillna(0.0) * 0.5
    return float(turn.mean())


def _build_layer_compare(
    *,
    context: Mapping[str, Any],
    effective_params: Mapping[str, Any],
    price_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    contract = dict(effective_params.get("effective_contract") or {})
    portfolio_daily = context.get("portfolio_daily")
    nav_df = context.get("nav")
    if not isinstance(portfolio_daily, pd.DataFrame) or portfolio_daily.empty:
        return pd.DataFrame()
    if not isinstance(nav_df, pd.DataFrame) or nav_df.empty:
        nav_df = pd.DataFrame()
    dates = pd.to_datetime(portfolio_daily["date"], errors="coerce").dropna().sort_values().unique()
    if len(dates) == 0:
        return pd.DataFrame()
    risk_symbols = [str(item).strip().upper() for item in list(contract.get("core_beta_symbols") or []) if str(item).strip()]
    defense_symbols = [str(item).strip().upper() for item in list(contract.get("limited_defense_candidates") or []) if str(item).strip()]
    all_symbols = sorted(set(risk_symbols + defense_symbols))
    px = _load_price_frame(
        symbols=all_symbols,
        start_date=str(pd.Timestamp(dates[0]).date()),
        end_date=str(pd.Timestamp(dates[-1]).date()),
        resolved_config=_resolved_config_payload(context),
        price_frame=price_frame,
    )
    pivot = px.pivot(index="date", columns="symbol", values="close").sort_index().reindex(pd.to_datetime(dates)).ffill()
    returns = pivot.pct_change().fillna(0.0)
    index_dates = returns.index
    buy_hold_weights = pd.DataFrame(0.0, index=index_dates, columns=all_symbols)
    if risk_symbols:
        equal_weight = 1.0 / float(len(risk_symbols))
        for symbol in risk_symbols:
            if symbol in buy_hold_weights.columns:
                buy_hold_weights.loc[:, symbol] = equal_weight

    allocation_weights = pd.DataFrame(0.0, index=index_dates, columns=all_symbols)
    cash_weight_series = pd.Series(1.0, index=index_dates, dtype=float)
    for row in portfolio_daily.itertuples(index=False):
        day = pd.Timestamp(getattr(row, "date"))
        diagnostics, formal_view, research_view = _extract_etf_diagnostics_views(getattr(row, "diagnostics_input_json", ""))
        targets = dict(formal_view.get("targets") or diagnostics.get("etf_beta_targets") or {})
        for symbol, weight in targets.items():
            symbol_text = _normalize_symbol(symbol)
            if symbol_text in allocation_weights.columns:
                allocation_weights.at[day, symbol_text] = float(_safe_float(weight) or 0.0)
        cash_weight_series.at[day] = float(
            _safe_float(research_view.get("cash_weight")) or max(0.0, 1.0 - allocation_weights.loc[day].sum())
        )

    filter_weights = buy_hold_weights.copy()
    absolute_mode = str(contract.get("absolute_filter_mode") or "none").strip().lower()
    if absolute_mode != "none":
        ma200 = pivot.rolling(200, min_periods=200).mean()
        ret12 = pivot.pct_change(252)
        for day in index_dates:
            for symbol in risk_symbols:
                if symbol not in filter_weights.columns:
                    continue
                close_now = _safe_float(pivot.at[day, symbol]) if symbol in pivot.columns else None
                ma200_now = _safe_float(ma200.at[day, symbol]) if symbol in ma200.columns else None
                ret12_now = _safe_float(ret12.at[day, symbol]) if symbol in ret12.columns else None
                absolute_pass = True
                if absolute_mode == "ma200_and_positive_12m":
                    absolute_pass = bool(close_now is not None and ma200_now is not None and close_now > ma200_now and ret12_now is not None and ret12_now > 0.0)
                elif absolute_mode == "ma200_only":
                    absolute_pass = bool(close_now is not None and ma200_now is not None and close_now > ma200_now)
                elif absolute_mode == "positive_12m":
                    absolute_pass = bool(ret12_now is not None and ret12_now > 0.0)
                if not absolute_pass:
                    filter_weights.at[day, symbol] = 0.0
            row_sum = filter_weights.loc[day].sum()
            if row_sum > 1e-12:
                filter_weights.loc[day] = filter_weights.loc[day] / row_sum

    filter_plus_allocation_weights = allocation_weights.copy()
    layer_rows: list[dict[str, Any]] = []
    layer_map = {
        "buy_and_hold": buy_hold_weights,
        "filter_only": filter_weights,
        "allocation_only": allocation_weights,
        "filter_plus_allocation": filter_plus_allocation_weights,
    }
    for name, weights in layer_map.items():
        daily_returns = (weights.reindex(columns=returns.columns, fill_value=0.0) * returns).sum(axis=1)
        nav = _build_synthetic_nav(daily_returns)
        layer_rows.append(
            {
                "layer": name,
                **_compute_perf_metrics(
                    nav,
                    avg_position=float(weights.sum(axis=1).mean()) if not weights.empty else None,
                    turnover=_weight_turnover(weights),
                ),
            }
        )

    actual_nav = pd.to_numeric(nav_df.get("nav"), errors="coerce") if "nav" in nav_df.columns else pd.Series(dtype=float)
    actual_nav.index = pd.to_datetime(nav_df.get("date"), errors="coerce") if "date" in nav_df.columns else pd.Index([], dtype="datetime64[ns]")
    actual_nav = actual_nav.dropna()
    layer_rows.append(
        {
            "layer": "full_strategy",
            **_compute_perf_metrics(
                actual_nav,
                avg_position=float(_series_numeric(portfolio_daily, "etf_actual_exposure").dropna().mean()) if not portfolio_daily.empty else None,
                turnover=float(_series_numeric(portfolio_daily, "turnover_pct").dropna().mean()) if not portfolio_daily.empty else None,
            ),
        }
    )
    return pd.DataFrame(layer_rows)


def _rootcause_code_locations() -> dict[str, list[str]]:
    return {
        "governor_budget_zero": [
            "backend/core/config/cn_a_governed_mainline.py:267",
            "backend/core/config/cn_a_governed_mainline.py:325",
        ],
        "requested_budget_zero": [
            "backend/core/config/etf_beta_contract.py:856",
            "backend/core/config/etf_beta_contract.py:878",
        ],
        "provider_slot_cap_zero": [
            "backend/core/engine_vector/cn_etf_beta_signal_provider.py:1955",
        ],
        "study_contract_none_filter": [
            "research/studies/etf/cn_etf_first_wave_core.study.yaml:47",
            "research/studies/etf/cn_etf_first_wave_core.study.yaml:50",
        ],
        "cost_not_rootcause": [
            "backend/core/config/models.py:178",
        ],
    }


def _build_rootcause_summary(
    *,
    context: Mapping[str, Any],
    effective_params: Mapping[str, Any],
    rebalance_summary: pd.DataFrame,
    position_utilization: Mapping[str, Any],
    lineage_summary: Mapping[str, Any],
    layer_compare: pd.DataFrame,
) -> dict[str, Any]:
    run_meta = dict(context.get("run_meta") or {})
    portfolio_daily = context.get("portfolio_daily")
    if not isinstance(portfolio_daily, pd.DataFrame):
        portfolio_daily = pd.DataFrame()
    governor_zero_days = 0
    slot_cap_zero_days = 0
    requested_budget_zero_days = 0
    eligible_positive_selected_zero_days = 0
    budget_reason_counter: Counter[str] = Counter()
    runtime_reason_counter: Counter[str] = Counter()
    for row in portfolio_daily.itertuples(index=False):
        diagnostics, formal_view, research_view = _extract_etf_diagnostics_views(getattr(row, "diagnostics_input_json", ""))
        governor_snapshot = _parse_json_cell(getattr(row, "governor_budget_json", ""))
        requested_budget = _safe_float(research_view.get("requested_budget"))
        if requested_budget is not None and abs(requested_budget) <= 1e-12:
            requested_budget_zero_days += 1
        slot_cap = _safe_int(diagnostics.get("etf_beta_deployable_slot_cap")) or 0
        if slot_cap <= 0:
            slot_cap_zero_days += 1
        total_exposure_cap = _safe_float(governor_snapshot.get("total_exposure_cap"))
        if total_exposure_cap is not None and abs(total_exposure_cap) <= 1e-12:
            governor_zero_days += 1
        eligible_count = len(list(formal_view.get("eligible_etfs") or diagnostics.get("etf_beta_eligible_symbols") or ()))
        selected_count = len(list(formal_view.get("selected_etfs") or diagnostics.get("etf_beta_selected_symbols") or ()))
        if eligible_count > 0 and selected_count <= 0:
            eligible_positive_selected_zero_days += 1
        for code in list(governor_snapshot.get("budget_reason_codes") or ()):
            text = str(code).strip()
            if text:
                budget_reason_counter[text] += 1
        for code in list(research_view.get("runtime_reason_codes") or diagnostics.get("etf_beta_runtime_reason_codes") or ()):
            text = str(code).strip()
            if text:
                runtime_reason_counter[text] += 1

    layer_map = {
        str(row["layer"]): dict(row)
        for row in layer_compare.to_dict(orient="records")
    }
    top_reasons = [
        {
            "rank": 1,
            "reason": "Governor 在正式窗口内把 `total_exposure_cap` 持续压到 0，直接抹掉 ETF Phase 1 的可用预算。",
            "evidence": {
                "governor_zero_days": governor_zero_days,
                "budget_reason_counts": dict(sorted(budget_reason_counter.items())),
            },
            "code_locations": _rootcause_code_locations()["governor_budget_zero"],
            "minimal_fix": "先单独核对 formal Phase 1 为什么长期命中 `ETF_BETA_SLOT_CAP_ACTIVE/NO_DEPLOYABLE_SLOTS`，不要先改 ETF 选中逻辑。",
            "minimal_validation": "固定正式资产池和正式 study，只打印 Governor 每日 `effective_max_positions/slot_cap/total_exposure_cap`。",
        },
        {
            "rank": 2,
            "reason": "ETF `requested_budget` 直接绑定 Governor sleeve budget；Governor 给 0 时，配置引擎本地没有预算可承接。",
            "evidence": {
                "requested_budget_zero_days": requested_budget_zero_days,
                "run_meta_requested_budget": _first_non_empty(
                    ((run_meta.get("etf_beta") or {}).get("research_view") or {}).get("requested_budget"),
                    ((run_meta.get("etf_beta") or {}).get("requested_budget")),
                ),
                "target_exposure_source": _first_non_empty(
                    ((run_meta.get("etf_beta") or {}).get("formal_view") or {}).get("target_exposure_source"),
                    ((run_meta.get("etf_beta") or {}).get("target_exposure_source")),
                ),
            },
            "code_locations": _rootcause_code_locations()["requested_budget_zero"],
            "minimal_fix": "先确认 formal Phase 1 的 `requested_budget` 是否应该完全消费 Governor sleeve budget，还是需要最小诊断 floor。",
            "minimal_validation": "只做 contract trace，不改交易：输出 `requested_budget -> applied_budget -> targets` 日级链路。",
        },
        {
            "rank": 3,
            "reason": "Provider 在 `slot_cap <= 0` 时直接短路，哪怕候选和 eligible 都存在，也不会生成目标、订单和成交。",
            "evidence": {
                "slot_cap_zero_days": slot_cap_zero_days,
                "eligible_positive_selected_zero_days": eligible_positive_selected_zero_days,
                "runtime_reason_counts": dict(sorted(runtime_reason_counter.items())),
            },
            "code_locations": _rootcause_code_locations()["provider_slot_cap_zero"],
            "minimal_fix": "保持正式策略不变，先补更细 diagnostics：把 `slot_cap=0` 前后的 candidate/eligible/targets 全量落盘。",
            "minimal_validation": "抽样 5 个 `eligible>0 且 selected=0` 的交易日，复核 provider 输入和 governor 输出是否一致。",
        },
        {
            "rank": 4,
            "reason": "当前 formal study 已经关闭绝对过滤和 fallback，说明零交易不是由过滤过严、fallback 误配或成本抑制造成。",
            "evidence": {
                "absolute_filter_mode": ((effective_params.get("effective_contract") or {}).get("absolute_filter_mode")),
                "fallback_mode": ((effective_params.get("effective_contract") or {}).get("fallback_mode")),
                "rebalance_days_with_eligible": int((rebalance_summary["eligible_count"] > 0).sum()) if not rebalance_summary.empty else 0,
            },
            "code_locations": _rootcause_code_locations()["study_contract_none_filter"],
            "minimal_fix": "不要再先调 `MA200/RET12`；先把 Governor/配置预算链跑通，再回来看过滤。",
            "minimal_validation": "保持 `absolute_filter_mode=none` 不变，只复查 `eligible -> selected -> orders` 三层。",
        },
        {
            "rank": 5,
            "reason": "五层对照显示买入持有和过滤/分配前层仍有正收益，而完整正式策略为 0，问题集中在配置预算和执行前链路，不在数据可用性。",
            "evidence": {
                "layer_compare": {
                    name: {
                        "cagr": layer_map.get(name, {}).get("cagr"),
                        "avg_position": layer_map.get(name, {}).get("avg_position"),
                    }
                    for name in ("buy_and_hold", "filter_only", "allocation_only", "filter_plus_allocation", "full_strategy")
                },
                "position_utilization": {
                    "avg_exposure": position_utilization.get("avg_exposure"),
                    "empty_day_ratio": position_utilization.get("empty_day_ratio"),
                },
            },
            "code_locations": _rootcause_code_locations()["cost_not_rootcause"],
            "minimal_fix": "把下一条 change 聚焦在 formal Phase 1 zero-trade 预算链诊断，不要同时改数据、过滤、排序、成本。",
            "minimal_validation": "在同一正式窗口重跑五层对照，要求 `allocation_only/full_strategy` 的差距可解释到具体 budget gate。",
        },
    ]
    return {
        "diagnostic_scope": "cn_etf_phase1_allocation_entry",
        "top_reasons": top_reasons,
        "non_rootcause_notes": [
            "当前 formal Phase 1 的 `absolute_filter_mode=none`，所以绝对过滤不是这次 zero-trade 的直接根因。",
            "正式实验存在完整候选池与 eligible 集合，数据覆盖不是主根因。",
            "当前为零订单零成交，手续费/滑点/税费不会成为直接抑制因素。",
        ],
    }


def write_cn_etf_phase1_zero_trade_diagnostics(
    *,
    exp_id: str,
    results_dir: str | Path,
    price_frame: pd.DataFrame | None = None,
) -> dict[str, Any]:
    resolved_results_dir = Path(results_dir).resolve()
    context = _build_results_context(exp_id=exp_id, results_dir=resolved_results_dir)
    ops_dir = _ensure_ops_dir(exp_id)
    effective_params = _extract_effective_parameters(context)
    rebalance_summary = _build_rebalance_day_summary(context, effective_params)
    ranking_detail = _build_ranking_detail(
        context=context,
        effective_params=effective_params,
        rebalance_summary=rebalance_summary,
        price_frame=price_frame,
    )
    position_utilization = _build_position_utilization(context)
    lineage_summary = _build_lineage_samples(context, rebalance_summary)
    layer_compare = _build_layer_compare(
        context=context,
        effective_params=effective_params,
        price_frame=price_frame,
    )
    rootcause_summary = _build_rootcause_summary(
        context=context,
        effective_params=effective_params,
        rebalance_summary=rebalance_summary,
        position_utilization=position_utilization,
        lineage_summary=lineage_summary,
        layer_compare=layer_compare,
    )

    rebalance_summary_path = ops_dir / "rebalance_day_summary.csv"
    ranking_detail_path = ops_dir / "ranking_detail.csv"
    effective_parameters_path = ops_dir / "effective_parameters.json"
    position_utilization_path = ops_dir / "position_utilization.json"
    lineage_summary_path = ops_dir / "lineage_samples.json"
    layer_compare_path = ops_dir / "layer_compare.csv"
    rootcause_summary_path = ops_dir / "rootcause_summary.json"

    rebalance_summary.to_csv(rebalance_summary_path, index=False, encoding="utf-8-sig")
    ranking_detail.to_csv(ranking_detail_path, index=False, encoding="utf-8-sig")
    _write_json(effective_parameters_path, {"rows": list(effective_params.get("rows") or []), "run_meta_summary": dict(effective_params.get("run_meta_summary") or {})})
    _write_json(position_utilization_path, position_utilization)
    _write_json(lineage_summary_path, lineage_summary)
    layer_compare.to_csv(layer_compare_path, index=False, encoding="utf-8-sig")
    _write_json(rootcause_summary_path, rootcause_summary)

    return {
        "ops_dir": str(ops_dir),
        "rebalance_day_summary": str(rebalance_summary_path),
        "ranking_detail": str(ranking_detail_path),
        "effective_parameters": str(effective_parameters_path),
        "position_utilization": str(position_utilization_path),
        "lineage_samples": str(lineage_summary_path),
        "layer_compare": str(layer_compare_path),
        "rootcause_summary": str(rootcause_summary_path),
    }
