from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import pandas as pd

from backend.core.config.loader import load_config
from backend.core.engine_compat.foundation_shell import (
    FoundationCompatibilityRequest,
    build_foundation_compiled_plan,
    run_foundation_compatibility_shell,
)
from backend.core.strategies.registry import build_strategy
from backend.core.tools.data_bundle_builder import build_data_bundle


DEFAULT_EXPERIMENT_SYMBOLS = ["600000.SH", "000001.SZ", "600519.SH"]


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

    if overrides.get("symbols"):
        out["universe"]["symbols"] = list(overrides["symbols"])
    if overrides.get("start_date"):
        out["universe"]["start"] = str(overrides["start_date"])
    if overrides.get("end_date"):
        out["universe"]["end"] = str(overrides["end_date"])
    if overrides.get("benchmark"):
        out["universe"]["benchmark"] = str(overrides["benchmark"])
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
            if wb_uni.get("start"):
                out["universe"]["start"] = str(wb_uni["start"])
            if wb_uni.get("end"):
                out["universe"]["end"] = str(wb_uni["end"])
            if wb_uni.get("benchmark"):
                out["universe"]["benchmark"] = str(wb_uni["benchmark"])

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
        "dynamic_all_a_entry": bool(bundle.dynamic_all_a_entry),
    }
    foundation_plan = build_foundation_compiled_plan(
        runtime_config=cfg_merged,
        overrides=ov,
    )
    bt_result = run_foundation_compatibility_shell(
        FoundationCompatibilityRequest(
            compiled_plan=foundation_plan,
            data_bundle=bundle,
            cfg_obj=cfg_obj,
            strategy=strategy,
        )
    )

    _emit_progress(progress_hook, 85, "写出回测产物")
    bt_result.daily.to_csv(results_dir / "portfolio_daily.csv", index=False)
    bt_result.trades.to_csv(results_dir / "portfolio_trades.csv", index=False)
    bt_result.candidates.to_csv(results_dir / "portfolio_candidates.csv", index=False)
    st_buy_violation_count = _compute_st_buy_violations(bt_result.trades, bundle.st_history)

    m = dict(bt_result.metrics or {})
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
