from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from backend.core.config.loader import load_config
from backend.core.data.pg_provider import PostgresDataProvider
from backend.core.portfolio.portfolio_builder import run_portfolio_backtest
from backend.core.strategies.registry import build_strategy


DEFAULT_EXPERIMENT_SYMBOLS = ["600000.SH", "000001.SZ", "600519.SH"]


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

    exp_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    results_dir = (_results_root() / "experiments" / exp_id).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    tmp_cfg = results_dir / "run_config.json"
    tmp_cfg.write_text(json.dumps(cfg_merged, ensure_ascii=False, indent=2), encoding="utf-8")

    cfg_obj, _ = load_config(str(tmp_cfg))
    provider = PostgresDataProvider(
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
        data_source=cfg_obj.data_source,
        schema_mapping=cfg_obj.schema_mapping,
        rules_path=tmp_cfg.parent / "instrument_rules_cn.csv",
    )

    symbols = list(cfg_obj.universe.symbols or DEFAULT_EXPERIMENT_SYMBOLS)
    _emit_progress(progress_hook, 20, f"加载行情数据: {len(symbols)} 标的")
    history = provider.load_ohlcv_daily(symbols, cfg_obj.universe.start, cfg_obj.universe.end, source="stocks")
    benchmark = provider.load_benchmark_daily(cfg_obj.universe.benchmark, cfg_obj.universe.start, cfg_obj.universe.end)
    calendar = provider.load_trading_calendar_cn(cfg_obj.universe.start, cfg_obj.universe.end)
    trading_days = [d.date() for d in calendar]

    _emit_progress(progress_hook, 55, "执行组合回测")
    strategy = build_strategy(cfg_obj.strategy)
    strategy.set_context({"run_id": exp_id, "results_dir": str(results_dir)})
    bt_result = run_portfolio_backtest(
        strategy=strategy,
        history=history,
        benchmark=benchmark,
        trading_days=trading_days,
        benchmark_symbol=cfg_obj.universe.benchmark,
        initial_cash=float(cfg_obj.initial_capital),
        max_positions=int(ov.get("max_positions", 10)),
        lot_size=int(cfg_obj.execution.lot_size),
        enable_strength_rank=bool(ov.get("enable_strength_rank", False)),
        strength_ma=int(ov.get("strength_ma", 120)),
        strength_top_k_mode=str(ov.get("strength_top_k_mode", "FILL_TO_MAX")),
        engine_mode="VECTOR_FAST_STRICT",
        fast_mode=bool(ov.get("fast_mode", True)),
        enable_multifactor_rank=bool(ov.get("enable_multifactor_rank", False)),
        mf_topk=int(ov.get("mf_topk", 10)),
        mf_concentrate_topn=int(ov.get("mf_concentrate_topn", 3)),
        mf_concentrate_scale=float(ov.get("mf_concentrate_scale", 1.5)),
        mf_rank_gate_mode=str(ov.get("mf_rank_gate_mode", "ALWAYS_ON")),
    )

    _emit_progress(progress_hook, 85, "写出回测产物")
    bt_result.daily.to_csv(results_dir / "portfolio_daily.csv", index=False)
    bt_result.trades.to_csv(results_dir / "portfolio_trades.csv", index=False)
    bt_result.candidates.to_csv(results_dir / "portfolio_candidates.csv", index=False)

    m = dict(bt_result.metrics or {})
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
        "run_profile_summary": {
            "engine_mode": "VECTOR_FAST_STRICT",
            "symbols_count": len(symbols),
            "trading_days": len(trading_days),
        },
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
