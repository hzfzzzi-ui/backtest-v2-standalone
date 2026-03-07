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
from backend.core.data.pg_provider import PostgresDataProvider
from backend.core.data.price_adjust import apply_price_adjustment
from backend.core.portfolio.portfolio_builder import run_portfolio_backtest
from backend.core.strategies.registry import build_strategy
from backend.core.universe.universe_resolver import resolve_universe_by_mode
from backend.core.universe.hs300_csi500 import UniverseFilterConfig, apply_universe_filters, build_candidates_from_ohlcv


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
    universe_filters_raw = {}
    try:
        universe_filters_raw = dict((cfg_merged.get("universe") or {}).get("filters") or {})
    except Exception:
        universe_filters_raw = {}
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

    dynamic_all_a_entry = bool(universe_mode == "ALL_A")
    resolve_asof = cfg_obj.universe.end if dynamic_all_a_entry else cfg_obj.universe.start

    _emit_progress(progress_hook, 10, f"解析 Universe ({universe_mode})")
    symbols, universe_meta = resolve_universe_by_mode(
        mode=universe_mode,
        as_of=resolve_asof,
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
        industries=universe_industries,
        symbols=user_symbols,
        universe_limit=int(ov.get("universe_limit") or 0) or None,
    )
    universe_meta["resolve_asof"] = str(resolve_asof)
    universe_meta["dynamic_all_a_entry"] = bool(dynamic_all_a_entry)
    _emit_progress(progress_hook, 20, f"加载行情数据: {len(symbols)} 标的 ({universe_mode})")
    history = provider.load_ohlcv_daily(symbols, cfg_obj.universe.start, cfg_obj.universe.end, source="stocks")

    # ── Universe filters (from workbench/universe.filters) ──
    if universe_filters_raw and not dynamic_all_a_entry:
        _emit_progress(progress_hook, 30, "应用 Universe 过滤器")
        uf_cfg = UniverseFilterConfig(
            exclude_st=bool(universe_filters_raw.get("exclude_st", True)),
            exclude_delisted=bool(universe_filters_raw.get("exclude_delisted", True)),
            exclude_suspended=bool(universe_filters_raw.get("exclude_suspended", True)),
            min_list_days=int(universe_filters_raw.get("min_list_days", 120)),
            min_avg_turnover_20d=float(universe_filters_raw.get("min_avg_turnover_20d", 1e8)),
            exclude_limit_lock=str(universe_filters_raw.get("limit_rule", "ignore")).strip().lower() in {"forbid", "skip"},
            min_price=float(
                universe_filters_raw.get(
                    "price_min",
                    universe_filters_raw.get("min_price", 0.0),
                ) or 0.0
            ),
        )
        # Build filter candidates using a lookback window before backtest start.
        # Without lookback, list_days/avg_turnover_20d may collapse to near-zero
        # when history starts exactly at start_date.
        filter_asof = pd.Timestamp(cfg_obj.universe.start)
        history_for_filter = history
        need_lookback = bool(
            int(universe_filters_raw.get("min_list_days", 120) or 0) > 1
            or float(universe_filters_raw.get("min_avg_turnover_20d", 0.0) or 0.0) > 0.0
        )
        if need_lookback:
            lookback_days = max(260, int(universe_filters_raw.get("min_list_days", 120) or 120) * 3)
            filter_start = (filter_asof - pd.Timedelta(days=lookback_days)).date().isoformat()
            history_for_filter = provider.load_ohlcv_daily(
                symbols,
                filter_start,
                cfg_obj.universe.start,
                source="stocks",
            )
        filter_asof_date = pd.Timestamp(filter_asof).date()
        try:
            st_history_for_filter = provider.load_st_history(symbols, filter_asof_date, filter_asof_date)
        except Exception:
            st_history_for_filter = pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type"])
        try:
            security_master = provider.load_security_master(symbols)
        except Exception:
            security_master = pd.DataFrame(columns=["symbol", "list_date", "delist_date"])

        candidates = build_candidates_from_ohlcv(
            history_for_filter,
            filter_asof,
            st_history=st_history_for_filter,
            security_master=security_master,
        )
        filtered_candidates, _snapshot, excluded_counts = apply_universe_filters(candidates, uf_cfg)
        filtered_symbols = sorted(
            {str(s).strip().lower() for s in filtered_candidates.get("symbol", pd.Series(dtype=str)).tolist() if str(s).strip()}
        )
        before_count = int(len(symbols))
        after_count = int(len(filtered_symbols))
        universe_meta["filters_config"] = dict(universe_filters_raw)
        universe_meta["excluded_counts"] = excluded_counts
        universe_meta["tradable_symbols"] = after_count
        universe_meta["after_filters_symbols"] = after_count
        if after_count > 0:
            symbols = filtered_symbols
            history = history[history["symbol"].astype(str).str.lower().isin(set(filtered_symbols))].copy()
        else:
            # Keep previous universe if filter removes all symbols; preserve runability with observability.
            universe_meta["filter_warning"] = "all symbols filtered out; fallback to pre-filter universe"
            universe_meta["after_filters_symbols"] = before_count
    elif universe_filters_raw and dynamic_all_a_entry:
        # ALL_A 动态入池：不在起始日做一次性静态裁剪，后续由矩阵逐日过滤控制可交易性。
        universe_meta["filters_config"] = dict(universe_filters_raw)
        universe_meta["excluded_counts"] = {}
        universe_meta["tradable_symbols"] = int(len(symbols))
        universe_meta["after_filters_symbols"] = int(len(symbols))
        universe_meta["filter_mode"] = "dynamic_daily_gate"

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
        _sec_col = "index_code" if "index_code" in sec_df.columns else "symbol"
        if not sec_df.empty and _sec_col in sec_df.columns:
            for sym, grp in sec_df.groupby(_sec_col):
                sector_data[str(sym)] = grp.reset_index(drop=True)
    except Exception:
        pass
    industry_map = provider.load_industry_mapping(symbols)

    _emit_progress(progress_hook, 55, "执行组合回测")
    strategy = build_strategy(cfg_obj.strategy)
    strategy.set_context({"run_id": exp_id, "results_dir": str(results_dir)})
    strategy.state["universe_filters"] = {
        "min_price": float(universe_filters_raw.get("price_min", universe_filters_raw.get("min_price", 0.0)) or 0.0),
        "min_list_days": int(universe_filters_raw.get("min_list_days", 0) or 0),
        "min_avg_turnover_20d": float(universe_filters_raw.get("min_avg_turnover_20d", 0.0) or 0.0),
        "dynamic_all_a_entry": bool(dynamic_all_a_entry),
    }
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
        momentum_top_pct=float(ov.get("momentum_top_pct", 0.0)),
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
    st_buy_violation_count = _compute_st_buy_violations(bt_result.trades, st_history)

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
