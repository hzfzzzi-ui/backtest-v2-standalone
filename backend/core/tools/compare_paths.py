"""Research-only parity harness for provider experiments.

Compares RegimeRouterSignalProvider and GenericSignalProvider paths during
matrix-search or engine cleanup work. This script is not part of the product
runtime contract.

Usage: python -m backend.core.tools.compare_paths <config_name>
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

from backend.core.config.loader import load_config
from backend.core.data.cached_provider import CachedDataProvider
from backend.core.data.pg_provider import PostgresDataProvider
from backend.core.data.price_adjust import apply_price_adjustment
from backend.core.strategies.registry import build_strategy
from backend.core.universe.universe_resolver import resolve_universe_by_mode


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _inject_db(cfg: dict) -> None:
    cfg.setdefault("db", {})
    db = cfg["db"]
    db.setdefault("host", os.environ.get("PGHOST", os.environ.get("PAMS_PG_HOST", "pams-postgres")))
    db.setdefault("port", int(os.environ.get("PGPORT", os.environ.get("PAMS_PG_PORT", "5432"))))
    db.setdefault("dbname", os.environ.get("PGDATABASE", os.environ.get("PAMS_PG_DBNAME", "pams")))
    db.setdefault("user", os.environ.get("PGUSER", os.environ.get("PAMS_PG_USER", "pams")))
    db.setdefault("password", os.environ.get("PGPASSWORD", os.environ.get("PAMS_PG_PASSWORD", "")))


def main() -> None:
    config_name = sys.argv[1] if len(sys.argv) > 1 else "r1_rsi_default_csi800"
    universe_mode = sys.argv[2] if len(sys.argv) > 2 else "HS300_ZZ500"

    cfg_path = _repo_root() / "backend" / "configs" / f"{config_name}.json"
    if not cfg_path.exists():
        cfg_path = _repo_root() / "backend" / "configs" / "sweep" / f"{config_name}.json"
    if not cfg_path.exists():
        print(f"Config not found: {config_name}")
        sys.exit(1)

    raw_cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    _inject_db(raw_cfg)
    tmp_dir = Path("/tmp/compare_paths")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_cfg = tmp_dir / "run_config.json"
    tmp_cfg.write_text(json.dumps(raw_cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    cfg_obj, _ = load_config(str(tmp_cfg))
    provider = CachedDataProvider(inner=PostgresDataProvider(
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
        data_source=cfg_obj.data_source,
        schema_mapping=cfg_obj.schema_mapping,
        rules_path=tmp_cfg.parent / "instrument_rules_cn.csv",
    ))

    symbols, _ = resolve_universe_by_mode(
        mode=universe_mode,
        as_of=cfg_obj.universe.start,
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
        industries=[],
        symbols=list(cfg_obj.universe.symbols or []),
    )
    print(f"Universe: {len(symbols)} symbols ({universe_mode})")

    history = provider.load_ohlcv_daily(symbols, cfg_obj.universe.start, cfg_obj.universe.end, source="stocks")
    benchmark = provider.load_benchmark_daily(cfg_obj.universe.benchmark, cfg_obj.universe.start, cfg_obj.universe.end)
    calendar = provider.load_trading_calendar_cn(cfg_obj.universe.start, cfg_obj.universe.end)
    trading_days = [d.date() for d in calendar]
    try:
        st_history = provider.load_st_history(symbols, cfg_obj.universe.start, cfg_obj.universe.end)
    except Exception:
        st_history = None

    raw_history = history
    signal_history = apply_price_adjustment(history, "hfq") if "adj_factor" in history.columns else history

    from backend.core.engine_vector.portfolio_simulator_strict import (
        _build_price_indices,
        _run_generic_path,
        _run_regime_router_path,
    )

    _raw = raw_history if raw_history is not None else signal_history
    open_idx, close_idx, hfq_close_idx, adj_factor_idx = _build_price_indices(_raw, hfq_df=signal_history)

    common_kwargs = dict(
        history=signal_history,
        benchmark=benchmark,
        trading_days=trading_days,
        initial_cash=float(cfg_obj.initial_capital),
        max_positions=10,
        lot_size=int(cfg_obj.execution.lot_size),
        open_idx=open_idx,
        close_idx=close_idx,
        hfq_close_idx=hfq_close_idx,
        adj_factor_idx=adj_factor_idx,
        cost_cfg=cfg_obj.costs,
        exit_cfg=cfg_obj.exit,
        risk_cfg=cfg_obj.risk,
        enable_strength_rank=False,
        strength_ma=120,
        strength_top_k_mode="FILL_TO_MAX",
        fast_mode=True,
        debug_first_divergence=False,
        enable_multifactor_rank=False,
        mf_topk=10,
        mf_concentrate_topn=3,
        mf_concentrate_scale=1.5,
        mf_rank_gate_mode="ALWAYS_ON",
        base_order_value=float(cfg_obj.sizing.order_value),
        sizing_cfg=cfg_obj.sizing,
        raw_history=raw_history,
        st_history=st_history,
    )

    # ── Run NEW path (RegimeRouterSignalProvider) ──
    print("\n=== Running NEW path (RegimeRouterSignalProvider) ===")
    strategy_new = build_strategy(cfg_obj.strategy)
    t0 = time.perf_counter()
    result_new = _run_regime_router_path(strategy=strategy_new, **common_kwargs)
    t_new = time.perf_counter() - t0
    print(f"  Time: {t_new:.1f}s")
    print(f"  Trades: {len(result_new.trades)}")
    print(f"  Final NAV: {result_new.daily['nav'].iloc[-1]:.2f}")

    # ── Run OLD path (GenericSignalProvider) ──
    print("\n=== Running OLD path (GenericSignalProvider) ===")
    strategy_old = build_strategy(cfg_obj.strategy)
    t0 = time.perf_counter()
    result_old = _run_generic_path(strategy=strategy_old, history_lookback_days=None, **common_kwargs)
    t_old = time.perf_counter() - t0
    print(f"  Time: {t_old:.1f}s")
    print(f"  Trades: {len(result_old.trades)}")
    print(f"  Final NAV: {result_old.daily['nav'].iloc[-1]:.2f}")

    # ── Compare ──
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)

    trades_new = result_new.trades.copy()
    trades_old = result_old.trades.copy()

    print(f"\nTrades count: NEW={len(trades_new)}, OLD={len(trades_old)}")

    # reason_code distribution
    rc_new = trades_new["reason_code"].value_counts().to_dict() if "reason_code" in trades_new.columns else {}
    rc_old = trades_old["reason_code"].value_counts().to_dict() if "reason_code" in trades_old.columns else {}
    all_reasons = sorted(set(list(rc_new.keys()) + list(rc_old.keys())))
    print("\nReason code distribution:")
    print(f"  {'reason':<30s} {'NEW':>8s} {'OLD':>8s} {'DIFF':>8s}")
    for r in all_reasons:
        n = rc_new.get(r, 0)
        o = rc_old.get(r, 0)
        d = n - o
        marker = " ***" if d != 0 else ""
        print(f"  {r:<30s} {n:>8d} {o:>8d} {d:>+8d}{marker}")

    # NAV comparison
    daily_new = result_new.daily.copy()
    daily_old = result_old.daily.copy()
    if len(daily_new) == len(daily_old):
        nav_diff = (daily_new["nav"] - daily_old["nav"]).abs()
        max_diff = nav_diff.max()
        mean_diff = nav_diff.mean()
        first_diverge_idx = -1
        for idx in range(len(nav_diff)):
            if nav_diff.iloc[idx] > 0.01:
                first_diverge_idx = idx
                break
        print(f"\nDaily NAV comparison ({len(daily_new)} days):")
        print(f"  Max absolute diff:  {max_diff:.6f}")
        print(f"  Mean absolute diff: {mean_diff:.6f}")
        if first_diverge_idx >= 0:
            d = daily_new.iloc[first_diverge_idx]
            d_old = daily_old.iloc[first_diverge_idx]
            print(f"  First divergence at day {first_diverge_idx}: date={d.get('date', 'N/A')}")
            print(f"    NEW NAV={d['nav']:.4f}, OLD NAV={d_old['nav']:.4f}, diff={d['nav']-d_old['nav']:.4f}")
        else:
            print("  No divergence found (< 0.01)")
    else:
        print(f"\nDaily length mismatch: NEW={len(daily_new)}, OLD={len(daily_old)}")

    # Side-by-side trade comparison (first divergence)
    if len(trades_new) > 0 and len(trades_old) > 0:
        cols = ["date", "symbol", "side", "reason_code", "qty"]
        cols_n = [c for c in cols if c in trades_new.columns]
        cols_o = [c for c in cols if c in trades_old.columns]
        tn = trades_new[cols_n].reset_index(drop=True)
        to = trades_old[cols_o].reset_index(drop=True)
        max_rows = min(len(tn), len(to))
        first_diff = -1
        for i in range(max_rows):
            if any(str(tn.iloc[i][c]) != str(to.iloc[i][c]) for c in cols_n if c in cols_o):
                first_diff = i
                break
        if first_diff == -1 and len(tn) != len(to):
            first_diff = max_rows
        if first_diff >= 0:
            start = max(0, first_diff - 2)
            end = min(max_rows, first_diff + 5)
            print(f"\nFirst trade divergence at row {first_diff}:")
            print(f"  NEW trades[{start}:{end}]:")
            for j in range(start, min(end, len(tn))):
                print(f"    {j}: {dict(tn.iloc[j])}")
            print(f"  OLD trades[{start}:{end}]:")
            for j in range(start, min(end, len(to))):
                print(f"    {j}: {dict(to.iloc[j])}")
        else:
            print("\nAll trades match row-by-row!")

    # Save results
    trades_new.to_csv(tmp_dir / "trades_new.csv", index=False)
    trades_old.to_csv(tmp_dir / "trades_old.csv", index=False)
    daily_new.to_csv(tmp_dir / "daily_new.csv", index=False)
    daily_old.to_csv(tmp_dir / "daily_old.csv", index=False)
    print(f"\nResults saved to {tmp_dir}/")

    # Speedup
    print(f"\nSpeedup: {t_old/t_new:.1f}x ({t_old:.1f}s → {t_new:.1f}s)")


if __name__ == "__main__":
    main()
