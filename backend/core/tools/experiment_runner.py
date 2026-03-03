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
from backend.core.data.price_adjust import apply_price_adjustment
from backend.core.portfolio.portfolio_builder import run_portfolio_backtest
from backend.core.strategies.registry import build_strategy
from backend.core.universe.universe_resolver import resolve_universe_by_mode


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
    _pg = PostgresDataProvider(
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
        data_source=cfg_obj.data_source,
        schema_mapping=cfg_obj.schema_mapping,
        rules_path=tmp_cfg.parent / "instrument_rules_cn.csv",
    )
    try:
        from backend.core.data.cached_provider import CachedDataProvider
        provider = CachedDataProvider(_pg)
    except ImportError:
        provider = _pg

    # ── Universe 解析: 根据 mode 从 DB 查询 PIT-safe 的 symbols ──
    universe_mode = str(ov.get("universe_mode", "CUSTOM")).strip().upper()
    universe_industries = list(ov.get("industries") or [])
    user_symbols = list(cfg_obj.universe.symbols or [])

    if universe_mode == "CUSTOM" and not user_symbols:
        user_symbols = list(DEFAULT_EXPERIMENT_SYMBOLS)

    _emit_progress(progress_hook, 10, f"解析 Universe ({universe_mode})")
    symbols, universe_meta = resolve_universe_by_mode(
        mode=universe_mode,
        as_of=cfg_obj.universe.start,
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
        industries=universe_industries,
        symbols=user_symbols,
        universe_limit=int(ov.get("universe_limit") or 0) or None,
    )
    _emit_progress(progress_hook, 20, f"加载行情数据: {len(symbols)} 标的 ({universe_mode})")
    history = provider.load_ohlcv_daily(symbols, cfg_obj.universe.start, cfg_obj.universe.end, source="stocks")
    benchmark = provider.load_benchmark_daily(cfg_obj.universe.benchmark, cfg_obj.universe.start, cfg_obj.universe.end)
    calendar = provider.load_trading_calendar_cn(cfg_obj.universe.start, cfg_obj.universe.end)
    trading_days = [d.date() for d in calendar]

    # ── 价格复权: 信号计算用复权价，成交执行用不复权价 ──
    price_adj_mode = str(ov.get("price_adj", "hfq")).strip().lower()
    if price_adj_mode not in ("hfq", "qfq", "none"):
        price_adj_mode = "hfq"
    raw_history = history
    adj_factor_stats: dict[str, Any] = {}
    if "adj_factor" in history.columns:
        af = history["adj_factor"]
        adj_factor_stats = {
            "min": float(af.min()),
            "max": float(af.max()),
            "null_count": int(af.isna().sum()),
        }
    if price_adj_mode != "none":
        signal_history = apply_price_adjustment(history, price_adj_mode)
    else:
        signal_history = history

    # ── 辅助数据: ST 历史、行业指数、行业映射 ──
    _emit_progress(progress_hook, 40, "加载辅助数据 (ST/行业)")
    st_history = provider.load_st_history(symbols, cfg_obj.universe.start, cfg_obj.universe.end)
    sector_data: dict[str, pd.DataFrame] = {}
    try:
        sec_df = provider.load_sector_indices(cfg_obj.universe.start, cfg_obj.universe.end)
        if not sec_df.empty and "symbol" in sec_df.columns:
            for sym, grp in sec_df.groupby("symbol"):
                sector_data[str(sym)] = grp.reset_index(drop=True)
    except Exception:
        pass
    industry_map = provider.load_industry_mapping(symbols)

    _emit_progress(progress_hook, 55, "执行组合回测")
    strategy = build_strategy(cfg_obj.strategy)
    strategy.set_context({"run_id": exp_id, "results_dir": str(results_dir)})
    bt_result = run_portfolio_backtest(
        strategy=strategy,
        history=signal_history,
        raw_history=raw_history,
        benchmark=benchmark,
        trading_days=trading_days,
        benchmark_symbol=cfg_obj.universe.benchmark,
        initial_cash=float(cfg_obj.initial_capital),
        max_positions=int(ov.get("max_positions", 10)),
        lot_size=int(cfg_obj.execution.lot_size),
        base_order_value=float(cfg_obj.sizing.order_value),
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
        cost_cfg=cfg_obj.costs,
        exit_cfg=cfg_obj.exit,
        risk_cfg=cfg_obj.risk,
        sizing_cfg=cfg_obj.sizing,
        st_history=st_history,
        sector_data=sector_data,
        industry_map=industry_map,
        risk_budget_cfg=cfg_obj.risk_budget,
        market_filter_cfg=cfg_obj.market_filter,
        benchmark_regime_cfg=cfg_obj.benchmark_regime,
        breadth_cfg=cfg_obj.breadth,
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
        "risk_budget_active_days": int(m.get("risk_budget_active_days", 0) or 0),
        "st_block_count": int(m.get("st_block_count", 0) or 0),
        "run_profile_summary": {
            "engine_mode": "VECTOR_FAST_STRICT",
            "symbols_count": len(symbols),
            "trading_days": len(trading_days),
        },
        "universe_meta": universe_meta,
        "price_adj_mode": price_adj_mode,
        "adj_factor_stats": adj_factor_stats,
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
