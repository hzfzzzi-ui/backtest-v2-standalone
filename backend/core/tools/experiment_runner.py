from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import pandas as pd

from backend.core.config.loader import load_config
from backend.core.engine_runtime.foundation_shell import (
    FoundationExecutionRequest,
    build_foundation_runtime_plan,
    run_foundation_execution_shell,
)
from backend.core.strategies.registry import build_strategy
from backend.core.tools.data_bundle_builder import build_data_bundle


DEFAULT_EXPERIMENT_SYMBOLS = ["600000.SH", "000001.SZ", "600519.SH"]
STANDARD_DAILY_COLUMNS = [
    "date",
    "nav",
    "cash",
    "positions_count",
    "positions_count_end_of_day",
    "daily_return",
    "drawdown",
    "gross_exposure",
    "turnover_pct",
    "top5_positions_json",
    "candidates_count",
    "selected_count",
    "top5_selected_strength_json",
    "top5_rejected_strength_json",
    "buy_slots_before_buy",
    "buy_slots_after_sell",
    "raw_buy_signal_count",
    "raw_alpha_signal_count",
    "composed_buy_signal_count",
    "composed_sell_signal_count",
    "buy_candidate_count",
    "after_held_filter_count",
    "after_slot_filter_count",
    "after_cash_lot_count",
    "diagnostics_input_json",
    "positions_before_sell",
    "sells_executed_count",
    "positions_after_sell",
    "buy_slots_calculated",
    "candidates_after_held_filter_count",
    "sorting_triggered",
    "mean_order_value_scale",
    "weak_trend_buy_rate",
    "strong_trend_buy_rate",
    "mf_rank_triggered",
    "mf_rank_applied",
    "mf_candidates_when_triggered",
    "mf_topk_reject_count",
    "mf_concentrated_selected_count",
    "mf_gate_on",
    "moneyflow_overlay_enabled",
    "moneyflow_overlay_mode",
    "moneyflow_overlay_gate_on",
    "moneyflow_overlay_observation_date",
    "moneyflow_overlay_score_source",
    "strong_risk_on",
    "mf_rank_suppressed_by_strong_gate",
    "same_symbol_conflict_count",
    "sleeve_budget_reject_count",
    "source_only_exit_count",
    "global_risk_override_count",
    "trend_slope_block_count",
    "trend_continuity_block_count",
    "base_trend_on_rate",
    "quality_trend_on_rate",
    "effective_max_positions",
    "dd_state",
    "market_state",
    "trade_mode",
    "benchmark_regime_on",
    "regime_engine",
    "regime_confidence",
    "regime_duration_bars",
    "regime_transition_reason",
    "feature_availability_json",
    "market_state_5",
    "base_state_5",
    "effective_state_5",
    "coarse_state",
    "effective_coarse_state",
    "market_state_score",
    "market_state_raw",
    "market_state_smoothed",
    "risk_budget_multiplier",
    "reason_codes_json",
    "block_scores_json",
    "subscores_json",
    "manual_override_json",
    "state_stability_metrics_json",
    "defense_bias",
    "weekly_observation_flag",
    "etf_target_exposure",
    "etf_min_deployable_exposure",
    "etf_target_exposure_source",
    "etf_min_deployable_exposure_source",
    "etf_actual_exposure",
    "etf_actual_risk_exposure",
    "etf_actual_fallback_exposure",
    "etf_actual_other_exposure",
    "etf_deployability_gap",
    "governor_budget_json",
]
STANDARD_TRADE_COLUMNS = [
    "date",
    "symbol",
    "side",
    "price",
    "fill_price",
    "qty",
    "value",
    "commission",
    "stamp_tax",
    "slippage",
    "net_amount",
    "reason_code",
    "triggered_rule",
    "break_streak",
    "exit_owner",
    "entry_alpha_id",
    "entry_sleeve_id",
    "entry_reason_code",
    "entry_date",
    "meta_json",
]


def _compute_st_buy_violations(trades: pd.DataFrame, st_history: pd.DataFrame) -> int:
    if trades is None or trades.empty or st_history is None or st_history.empty:
        return 0
    tdf = trades.copy()
    sdf = st_history.copy()
    side_col = "side" if "side" in tdf.columns else None
    if side_col is None:
        return 0
    tdf = tdf[tdf[side_col].astype(str).str.upper() == "BUY"].copy()
    if tdf.empty:
        return 0
    date_col = next((c for c in ("signal_date", "fill_date", "trade_date", "date") if c in tdf.columns), None)
    if date_col is None or "symbol" not in tdf.columns:
        return 0
    tdf["symbol"] = tdf["symbol"].astype(str).str.lower()
    tdf["trade_dt"] = pd.to_datetime(tdf[date_col], errors="coerce").dt.normalize()
    tdf = tdf.dropna(subset=["trade_dt"])
    if tdf.empty:
        return 0

    st_rows: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    for row in sdf.itertuples(index=False):
        ts_code = str(getattr(row, "ts_code", "")).strip()
        if not ts_code:
            continue
        if "." in ts_code:
            code, exch = ts_code.split(".", 1)
            symbol = f"{exch.lower()}{code}"
        else:
            symbol = ts_code.lower()
        start_dt = pd.to_datetime(getattr(row, "start_date", None), errors="coerce")
        end_dt = pd.to_datetime(getattr(row, "end_date", None), errors="coerce")
        if pd.isna(start_dt):
            continue
        if pd.isna(end_dt):
            end_dt = pd.Timestamp("2099-12-31")
        st_rows.append((symbol, pd.Timestamp(start_dt).normalize(), pd.Timestamp(end_dt).normalize()))
    if not st_rows:
        return 0

    by_symbol: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    for sym, sdt, edt in st_rows:
        by_symbol.setdefault(sym, []).append((sdt, edt))

    violations = 0
    for row in tdf.itertuples(index=False):
        sym = str(getattr(row, "symbol", "")).lower()
        dt = pd.Timestamp(getattr(row, "trade_dt"))
        for sdt, edt in by_symbol.get(sym, []):
            if sdt <= dt <= edt:
                violations += 1
                break
    return int(violations)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _results_root() -> Path:
    raw = os.environ.get("RESULTS_ROOT", "outputs").strip() or "outputs"
    p = Path(raw)
    if not p.is_absolute():
        p = (_repo_root() / p).resolve()
    return p


def _emit_progress(progress_hook: Callable[[int, str], None] | None, pct: int, message: str) -> None:
    if progress_hook is None:
        return
    try:
        progress_hook(int(max(0, min(100, pct))), str(message))
    except Exception:
        pass


def _coerce_bool_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any():
        return numeric.fillna(0.0).ne(0.0)
    text = series.astype(str).str.strip().str.lower()
    return text.isin({"1", "true", "t", "yes", "y", "on"})


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _matching_is_next_open(cfg_merged: dict[str, Any]) -> bool:
    execution = _as_dict(cfg_merged.get("execution"))
    cost_model = _as_dict(_as_dict(cfg_merged.get("position_risk")).get("cost_model"))
    matching = str(cost_model.get("matching") or execution.get("matching") or "next_open").strip().lower()
    return matching == "next_open"


def _compute_effective_warmup_analysis(
    cfg_merged: dict[str, Any],
    trading_days: list[date],
    daily_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    if not trading_days:
        return {}

    universe = _as_dict(cfg_merged.get("universe"))
    universe_filters = _as_dict(universe.get("filters"))
    signal_generation = _as_dict(cfg_merged.get("signal_generation"))
    breakout_cfg = _as_dict(signal_generation.get("breakout"))
    ranking_cfg = _as_dict(signal_generation.get("ranking"))
    benchmark_regime_cfg = _as_dict(cfg_merged.get("benchmark_regime"))

    candidate_offsets: dict[str, int] = {}

    min_list_days = _as_int(universe_filters.get("min_list_days"), 0)
    if min_list_days > 1:
        candidate_offsets["min_list_days"] = min_list_days - 1

    strategy_name = str(
        signal_generation.get("strategy") or cfg_merged.get("strategy_pack") or ""
    ).strip().upper()
    if "BREAKOUT" in strategy_name:
        strength_ma = _as_int(ranking_cfg.get("strength_ma"), 120)
        if strength_ma > 1:
            candidate_offsets["strength_ma"] = strength_ma - 1

        breakout_window = _as_int(breakout_cfg.get("breakout_window"), 0)
        if breakout_window > 1:
            candidate_offsets["breakout_window"] = breakout_window - 1

        entry_confirm_mode = str(breakout_cfg.get("entry_confirm_mode") or "").strip().lower()
        if entry_confirm_mode in {"volume_confirm", "volume_ratio_confirm"}:
            candidate_offsets["volume_ma20"] = 19

    candidate_offset = max(candidate_offsets.values()) if candidate_offsets else 0

    strategy_gate_offsets: dict[str, int] = {}
    if bool(benchmark_regime_cfg.get("enabled", False)):
        slow_period = max(_as_int(benchmark_regime_cfg.get("slow_period"), 0), 0)
        slope_window = max(_as_int(benchmark_regime_cfg.get("slope_window"), 1), 1)
        if slow_period > 0:
            strategy_gate_offsets["benchmark_regime"] = slow_period + slope_window - 1

    strategy_offset = max([candidate_offset, *strategy_gate_offsets.values()]) if strategy_gate_offsets else candidate_offset
    last_index = max(len(trading_days) - 1, 0)
    candidate_index = min(max(candidate_offset, 0), last_index)
    signal_index = min(max(strategy_offset, 0), last_index)
    execution_index = signal_index
    if _matching_is_next_open(cfg_merged) and signal_index < last_index:
        execution_index = signal_index + 1

    theoretical_execution_start_date = str(trading_days[execution_index])
    warmup = {
        "configured_start_date": str(trading_days[0]),
        "candidate_ready_date": str(trading_days[candidate_index]),
        "effective_signal_start_date": str(trading_days[signal_index]),
        "effective_execution_start_date": theoretical_execution_start_date,
        "theoretical_effective_execution_start_date": theoretical_execution_start_date,
        "candidate_warmup_trading_days": int(candidate_index),
        "signal_warmup_trading_days": int(signal_index),
        "execution_warmup_trading_days": int(execution_index),
        "candidate_component_offsets": candidate_offsets,
        "strategy_component_offsets": strategy_gate_offsets,
        "matching_mode": "next_open" if _matching_is_next_open(cfg_merged) else "same_bar",
    }

    if isinstance(daily_df, pd.DataFrame) and not daily_df.empty and "date" in daily_df.columns:
        observed = daily_df.copy()
        observed["date"] = pd.to_datetime(observed["date"], errors="coerce").dt.normalize()
        observed = observed.dropna(subset=["date"]).sort_values("date")
        if not observed.empty:
            raw_signal_dates = observed.loc[pd.to_numeric(observed.get("raw_buy_signal_count"), errors="coerce").fillna(0.0) > 0, "date"]
            if not raw_signal_dates.empty:
                warmup["observed_first_raw_signal_date"] = str(raw_signal_dates.iloc[0].date())
            if "benchmark_regime_on" in observed.columns:
                regime_on = _coerce_bool_series(observed["benchmark_regime_on"])
                regime_dates = observed.loc[regime_on, "date"]
                if not regime_dates.empty:
                    warmup["observed_first_regime_ready_date"] = str(regime_dates.iloc[0].date())
            if "positions_count_end_of_day" in observed.columns:
                position_dates = observed.loc[
                    pd.to_numeric(observed["positions_count_end_of_day"], errors="coerce").fillna(0.0) > 0,
                    "date",
                ]
                if not position_dates.empty:
                    warmup["observed_first_position_date"] = str(position_dates.iloc[0].date())

    metrics_start_date = theoretical_execution_start_date
    metrics_start_reason = "theoretical_effective_execution_start_date"
    observed_first_position_date = str(warmup.get("observed_first_position_date") or "").strip()
    if observed_first_position_date:
        try:
            observed_ts = pd.Timestamp(observed_first_position_date).normalize()
            theoretical_ts = pd.Timestamp(theoretical_execution_start_date).normalize()
            if observed_ts < theoretical_ts:
                metrics_start_date = str(observed_ts.date())
                metrics_start_reason = "observed_first_position_date"
        except Exception:
            pass

    warmup["metrics_start_date"] = metrics_start_date
    warmup["metrics_start_reason"] = metrics_start_reason
    warmup["effective_execution_start_date"] = metrics_start_date

    return warmup


def _recompute_perf_from_daily(
    daily_df: pd.DataFrame | None,
    effective_execution_start_date: str | None,
) -> dict[str, Any]:
    if not isinstance(daily_df, pd.DataFrame) or daily_df.empty or "date" not in daily_df.columns:
        return {}
    start_text = str(effective_execution_start_date or "").strip()
    if not start_text:
        return {}

    nav_col = next(
        (c for c in ("nav", "strategy_nav", "equity", "equity_curve", "portfolio_value") if c in daily_df.columns),
        None,
    )
    if nav_col is None:
        return {}

    df = daily_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date"]).sort_values("date")
    df = df.loc[df["date"] >= pd.Timestamp(start_text).normalize()].copy()
    if df.empty:
        return {}

    nav = pd.to_numeric(df[nav_col], errors="coerce")
    df["_nav"] = nav
    df = df.dropna(subset=["_nav"])
    if df.empty:
        return {}

    nav0 = float(df["_nav"].iloc[0])
    nav1 = float(df["_nav"].iloc[-1])
    total_return = (nav1 / nav0 - 1.0) if nav0 > 0 else 0.0
    n = int(len(df))
    years = max(n / 252.0, 1e-9)
    cagr = (nav1 / nav0) ** (1.0 / years) - 1.0 if nav0 > 0 and nav1 > 0 else 0.0

    nav_series = pd.to_numeric(df["_nav"], errors="coerce")
    peak = nav_series.cummax()
    dd = (nav_series / peak) - 1.0
    max_drawdown = float(dd.min())

    daily_ret = nav_series.pct_change().replace([math.inf, -math.inf], pd.NA).fillna(0.0)
    vol = float(daily_ret.std(ddof=0))
    sharpe = float((daily_ret.mean() / vol) * math.sqrt(252.0)) if vol > 0.0 else 0.0
    calmar = float(cagr / abs(max_drawdown)) if max_drawdown != 0 else 0.0

    return {
        "total_return": float(total_return),
        "cagr": float(cagr),
        "max_drawdown": float(max_drawdown),
        "sharpe": float(sharpe),
        "calmar": float(calmar),
        "effective_observation_days": int(n),
        "metrics_from_effective_start": True,
    }


def _project_trade_csv_schema(trades: pd.DataFrame) -> pd.DataFrame:
    if trades is None or trades.empty:
        return pd.DataFrame(columns=STANDARD_TRADE_COLUMNS)
    available = [column for column in STANDARD_TRADE_COLUMNS if column in trades.columns]
    projected = trades.loc[:, available].copy()
    for column in STANDARD_TRADE_COLUMNS:
        if column not in projected.columns:
            projected[column] = ""
    return projected.loc[:, STANDARD_TRADE_COLUMNS]


def _project_daily_csv_schema(daily: pd.DataFrame) -> pd.DataFrame:
    if daily is None or daily.empty:
        return pd.DataFrame(columns=STANDARD_DAILY_COLUMNS)
    available = [column for column in STANDARD_DAILY_COLUMNS if column in daily.columns]
    projected = daily.loc[:, available].copy()
    for column in STANDARD_DAILY_COLUMNS:
        if column not in projected.columns:
            projected[column] = ""
    return projected.loc[:, STANDARD_DAILY_COLUMNS]


def _inject_db_credentials_from_env(cfg: dict[str, Any]) -> None:
    cfg.setdefault("db", {})
    db = cfg["db"]
    db.setdefault("host", os.environ.get("PGHOST", os.environ.get("PAMS_PG_HOST", "pams-postgres")))
    db.setdefault("port", int(os.environ.get("PGPORT", os.environ.get("PAMS_PG_PORT", "5432"))))
    db.setdefault("dbname", os.environ.get("PGDATABASE", os.environ.get("PAMS_PG_DBNAME", "pams")))
    db.setdefault("user", os.environ.get("PGUSER", os.environ.get("PAMS_PG_USER", "pams")))
    db.setdefault("password", os.environ.get("PGPASSWORD", os.environ.get("PAMS_PG_PASSWORD", "")))


def _apply_overrides(raw_cfg: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    out = dict(raw_cfg)
    out.setdefault("universe", {})
    out.setdefault("execution", {})
    out.setdefault("sizing", {})
    out.setdefault("data_source", {})
    benchmark_written = False

    if overrides.get("symbols"):
        out["universe"]["symbols"] = list(overrides["symbols"])
    if overrides.get("start_date"):
        out["universe"]["start"] = str(overrides["start_date"])
    if overrides.get("end_date"):
        out["universe"]["end"] = str(overrides["end_date"])
    if "benchmark" in overrides and overrides.get("benchmark") is not None:
        out["universe"]["benchmark"] = str(overrides["benchmark"])
        benchmark_written = True
    if overrides.get("compare_symbol"):
        out["universe"]["benchmark_compare_symbol"] = str(overrides["compare_symbol"])
    if overrides.get("initial_capital") is not None:
        out["initial_capital"] = float(overrides["initial_capital"])
    if overrides.get("lot_size") is not None:
        out["execution"]["lot_size"] = int(overrides["lot_size"])
        out["sizing"]["lot_size"] = int(overrides["lot_size"])
    if overrides.get("base_order_value") is not None:
        out["sizing"]["order_value"] = float(overrides["base_order_value"])

    wb_cfg = overrides.get("workbench_config")
    if isinstance(wb_cfg, dict):
        # Some callers send a UI draft schema (no db/schema_mapping). Only treat workbench_config as
        # effective runtime config when it already looks like a full backend config.
        if isinstance(wb_cfg.get("schema_mapping"), dict) and isinstance(wb_cfg.get("db"), dict):
            out = dict(wb_cfg)
            out.setdefault("universe", {})
            out.setdefault("execution", {})
            out.setdefault("sizing", {})
        else:
            wb_uni = wb_cfg.get("universe") if isinstance(wb_cfg.get("universe"), dict) else {}
            if wb_uni.get("symbols"):
                out["universe"]["symbols"] = list(wb_uni["symbols"])
            if "start" in wb_uni and wb_uni.get("start") is not None:
                out["universe"]["start"] = str(wb_uni["start"])
            if "end" in wb_uni and wb_uni.get("end") is not None:
                out["universe"]["end"] = str(wb_uni["end"])
            if "benchmark" in wb_uni and wb_uni.get("benchmark") is not None:
                out["universe"]["benchmark"] = str(wb_uni["benchmark"])
                benchmark_written = True

    if overrides.get("universe_mode"):
        out["universe_mode"] = str(overrides["universe_mode"])
    if overrides.get("industries") is not None:
        out["industries"] = list(overrides["industries"] or [])
    if overrides.get("price_adj"):
        out.setdefault("universe", {})
        out["universe"]["price_adj"] = str(overrides["price_adj"])
    if isinstance(overrides.get("asset_context"), dict):
        out["asset_context"] = dict(overrides["asset_context"])
    if overrides.get("data_role"):
        out["data_source"]["data_role"] = str(overrides["data_role"])
    asset_context = out.get("asset_context") if isinstance(out.get("asset_context"), dict) else {}
    asset_scope = str(
        overrides.get("asset_scope")
        or asset_context.get("asset_scope")
        or ""
    ).strip().lower()
    if asset_scope == "cn_etf" and not benchmark_written:
        out["universe"]["benchmark"] = ""

    _inject_db_credentials_from_env(out)
    return out


def run_experiment(
    base_cfg_path: str,
    preset: str = "single",
    overrides: dict[str, Any] | None = None,
    progress_hook: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    _emit_progress(progress_hook, 5, "开始单次回测")
    ov = dict(overrides or {})

    base_path = Path(base_cfg_path).resolve()
    raw_cfg = json.loads(base_path.read_text(encoding="utf-8-sig"))
    cfg_merged = _apply_overrides(raw_cfg, ov)

    # Use millisecond timestamp + random suffix to avoid same-second collision
    # when async jobs start concurrently.
    exp_root = (_results_root() / "experiments").resolve()
    exp_root.mkdir(parents=True, exist_ok=True)
    for _ in range(10):
        now = datetime.now()
        exp_id = f"exp_{now.strftime('%Y%m%d_%H%M%S')}{int(now.microsecond / 1000):03d}_{uuid4().hex[:4]}"
        results_dir = (exp_root / exp_id).resolve()
        try:
            results_dir.mkdir(parents=False, exist_ok=False)
            break
        except FileExistsError:
            continue
    else:
        raise RuntimeError("failed to allocate unique exp_id after retries")

    tmp_cfg = results_dir / "run_config.json"
    tmp_cfg.write_text(json.dumps(cfg_merged, ensure_ascii=False, indent=2), encoding="utf-8")

    cfg_obj, _ = load_config(str(tmp_cfg))
    bundle = build_data_bundle(
        cfg_obj=cfg_obj,
        cfg_merged=cfg_merged,
        overrides=ov,
        rules_path=tmp_cfg.parent / "instrument_rules_cn.csv",
        progress_hook=progress_hook,
        default_experiment_symbols=DEFAULT_EXPERIMENT_SYMBOLS,
    )

    _emit_progress(progress_hook, 55, "执行组合回测")
    strategy = build_strategy(cfg_obj.strategy)
    strategy.set_context({"run_id": exp_id, "results_dir": str(results_dir)})
    strategy.state["universe_filters"] = {
        "min_price": float(bundle.universe_filters_raw.get("price_min", bundle.universe_filters_raw.get("min_price", 0.0)) or 0.0),
        "min_list_days": int(bundle.universe_filters_raw.get("min_list_days", 0) or 0),
        "min_avg_turnover_20d": float(bundle.universe_filters_raw.get("min_avg_turnover_20d", 0.0) or 0.0),
        "min_avg_turnover_rate_20d": float(bundle.universe_filters_raw.get("min_avg_turnover_rate_20d", 0.0) or 0.0),
        "turnover_rate_field": str(bundle.universe_filters_raw.get("turnover_rate_field", "turnover_rate_f") or "turnover_rate_f"),
        "exclude_star_market": bool(bundle.universe_filters_raw.get("exclude_star_market", False)),
        "dynamic_all_a_entry": bool(bundle.dynamic_all_a_entry),
    }
    strategy.state["membership_history"] = bundle.membership_history
    foundation_plan = build_foundation_runtime_plan(
        runtime_config=cfg_merged,
        overrides=ov,
    )
    bt_result = run_foundation_execution_shell(
        FoundationExecutionRequest(
            compiled_plan=foundation_plan,
            data_bundle=bundle,
            cfg_obj=cfg_obj,
            strategy=strategy,
        )
    )

    daily_projected = _project_daily_csv_schema(bt_result.daily)
    trade_projected = _project_trade_csv_schema(bt_result.trades)
    warmup_analysis = _compute_effective_warmup_analysis(
        cfg_merged=cfg_merged,
        trading_days=bundle.trading_days,
        daily_df=daily_projected,
    )

    _emit_progress(progress_hook, 85, "写出回测产物")
    daily_projected.to_csv(results_dir / "portfolio_daily.csv", index=False)
    trade_projected.to_csv(results_dir / "portfolio_trades.csv", index=False)
    bt_result.candidates.to_csv(results_dir / "portfolio_candidates.csv", index=False)
    st_buy_violation_count = _compute_st_buy_violations(bt_result.trades, bundle.st_history)

    m = dict(bt_result.metrics or {})
    perf_override = _recompute_perf_from_daily(
        daily_projected,
        warmup_analysis.get("effective_execution_start_date"),
    )
    if perf_override:
        m.update(perf_override)
    metrics_payload = {
        key: dict(m.get(key) or {})
        for key in ("audit", "stage_summary", "stage_pipeline")
        if isinstance(m.get(key), dict)
    }
    _emit_progress(progress_hook, 100, "单次回测完成")
    return {
        "exp_id": exp_id,
        "results_dir": str(results_dir),
        "status": "OK",
        "total_return": float(m.get("total_return", 0.0) or 0.0),
        "max_drawdown": float(m.get("max_drawdown", 0.0) or 0.0),
        "cagr": float(m.get("cagr", 0.0) or 0.0),
        "sharpe": float(m.get("sharpe", 0.0) or 0.0),
        "calmar": float(m.get("calmar", 0.0) or 0.0),
        "trades": int(m.get("trades", m.get("trades_count", 0)) or 0),
        "turnover": float(m.get("turnover", m.get("turnover_avg", 0.0)) or 0.0),
        "raw_signal": int(m.get("raw_signal", m.get("raw_signals_total", 0)) or 0),
        "blocked": int(m.get("blocked", m.get("blocked_signals_total", 0)) or 0),
        "orders": int(m.get("orders", m.get("orders_total", 0)) or 0),
        "skipped": int(m.get("skipped", m.get("skipped_orders_total", m.get("skipped_orders", 0)) or 0) or 0),
        "closed_trades": int(m.get("closed_trades", 0) or 0),
        # 透传引擎计数器字段，供 ensure_standard_artifacts 构建 run_meta.counters
        "avg_positions": float(m.get("avg_positions", 0.0) or 0.0),
        "max_positions": int(m.get("max_positions", 10) or 10),
        "trend_slope_block_count": int(m.get("trend_slope_block_count", 0) or 0),
        "mf_rank_applied_rate": float(m.get("mf_rank_applied_rate", 0.0) or 0.0),
        "mf_gate_on_rate": float(m.get("mf_gate_on_rate", m.get("gate_on_rate", 0.0)) or 0.0),
        "candidate_diag_reason_counts": dict(m.get("candidate_diag_reason_counts") or {}),
        # breadth / exit / regime / market filter 计数器
        "breadth_score_mean": float(m.get("breadth_score_mean", 0.0) or 0.0),
        "breadth_gate_block_count": int(m.get("breadth_gate_block_count", 0) or 0),
        "breadth_maxpos_mean": float(m.get("breadth_maxpos_mean", 0.0) or 0.0),
        "exit_take_profit_count": int(m.get("exit_take_profit_count", 0) or 0),
        "exit_fixed_stop_count": int(m.get("exit_fixed_stop_count", 0) or 0),
        "exit_atr_stop_count": int(m.get("exit_atr_stop_count", 0) or 0),
        "exit_atr_trail_count": int(m.get("exit_atr_trail_count", 0) or 0),
        "exit_time_exit_count": int(m.get("exit_time_exit_count", 0) or 0),
        "exit_signal_count": int(m.get("exit_signal_count", 0) or 0),
        "market_filter_bull_days": int(m.get("market_filter_bull_days", 0) or 0),
        "market_filter_bear_days": int(m.get("market_filter_bear_days", 0) or 0),
        "market_state_trans_down_days": int(m.get("market_state_trans_down_days", 0) or 0),
        "market_state_trans_up_days": int(m.get("market_state_trans_up_days", 0) or 0),
        "trade_mode_main_days": int(m.get("trade_mode_main_days", 0) or 0),
        "trade_mode_light_days": int(m.get("trade_mode_light_days", 0) or 0),
        "trade_mode_notrade_days": int(m.get("trade_mode_notrade_days", 0) or 0),
        "risk_budget_active_days": int(m.get("risk_budget_active_days", 0) or 0),
        "st_block_count": int(m.get("st_block_count", 0) or 0),
        "st_buy_violation_count": int(st_buy_violation_count),
        "run_profile_summary": {
            "engine_mode": "VECTOR_FAST_STRICT",
            "symbols_count": len(bundle.symbols),
            "trading_days": len(bundle.trading_days),
        },
        "universe_meta": bundle.universe_meta,
        "price_adj_mode": bundle.price_adj_mode,
        "adj_factor_stats": bundle.adj_factor_stats,
        "data_bundle": bundle.summary,
        "warmup_analysis": warmup_analysis,
        "candidate_ready_date": warmup_analysis.get("candidate_ready_date"),
        "effective_signal_start_date": warmup_analysis.get("effective_signal_start_date"),
        "effective_execution_start_date": warmup_analysis.get("effective_execution_start_date"),
        "metrics_from_effective_start": bool(m.get("metrics_from_effective_start", False)),
        "effective_observation_days": int(m.get("effective_observation_days", 0) or 0),
        "metrics": metrics_payload,
        "stage_summary": dict(metrics_payload.get("stage_summary") or {}),
        "stage_pipeline": dict(metrics_payload.get("stage_pipeline") or {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-run experiment runner")
    parser.add_argument("config", help="config path")
    parser.add_argument("--preset", default="single")
    args = parser.parse_args()
    out = run_experiment(args.config, args.preset, overrides={})
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
