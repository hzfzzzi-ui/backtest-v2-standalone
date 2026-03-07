"""逐阶段信号漏斗诊断：分解每个过滤器的拦截量。

直接构建矩阵，逐阶段统计被拦截的信号数量。

Usage:
  python backend/scripts/run_funnel_diagnostic.py
"""
from __future__ import annotations

import io
import json
import sys
import time
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import numpy as np
import pandas as pd

from backend.core.config.loader import load_config
from backend.core.data.pg_provider import PostgresDataProvider
from backend.core.data.price_adjust import apply_price_adjustment
from backend.core.engine_vector.data_matrix import build_ohlc_matrices_from_history
from backend.core.engine_vector.features import compute_feature_matrices
from backend.core.universe.universe_resolver import resolve_universe_by_mode


def main() -> None:
    print(f"{'*' * 90}")
    print(f"  BREAKOUT 信号漏斗逐阶段诊断")
    print(f"{'*' * 90}")

    # ── Load config & data ──
    t0 = time.perf_counter()
    base_path = _root / "backend" / "configs" / "pams_cn_pg.json"
    raw_cfg = json.loads(base_path.read_text(encoding="utf-8-sig"))
    raw_cfg["universe"] = {
        **raw_cfg.get("universe", {}),
        "start": "2016-03-01", "end": "2026-03-01",
        "benchmark": "000300.SH", "symbols": [],
    }
    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(raw_cfg, tmp, ensure_ascii=False, indent=2)
    tmp.close()

    cfg_obj, _ = load_config(tmp.name)
    pg = PostgresDataProvider(
        db=cfg_obj.db, runtime=cfg_obj.db_runtime,
        data_source=cfg_obj.data_source, schema_mapping=cfg_obj.schema_mapping,
        rules_path=base_path.parent / "instrument_rules_cn.csv",
    )
    try:
        from backend.core.data.cached_provider import CachedDataProvider
        provider = CachedDataProvider(pg)
    except ImportError:
        provider = pg

    print(f"  [{time.perf_counter() - t0:.1f}s] Resolving universe...")
    symbols, _ = resolve_universe_by_mode(
        mode="HS300_ZZ500", as_of=cfg_obj.universe.start,
        db=cfg_obj.db, runtime=cfg_obj.db_runtime, symbols=[],
    )
    print(f"  [{time.perf_counter() - t0:.1f}s] Loading {len(symbols)} symbols...")
    history = provider.load_ohlcv_daily(symbols, cfg_obj.universe.start, cfg_obj.universe.end, source="stocks")
    benchmark = provider.load_benchmark_daily("000300.SH", cfg_obj.universe.start, cfg_obj.universe.end)
    calendar = provider.load_trading_calendar_cn(cfg_obj.universe.start, cfg_obj.universe.end)
    trading_days = [d.date() for d in calendar]
    st_history = provider.load_st_history(symbols, cfg_obj.universe.start, cfg_obj.universe.end)

    signal_history = apply_price_adjustment(history, "hfq")
    Path(tmp.name).unlink(missing_ok=True)

    # ── Build matrices ──
    print(f"  [{time.perf_counter() - t0:.1f}s] Building matrices...")
    hist = signal_history.copy()
    hist["date"] = pd.to_datetime(hist["date"])
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

    mx = build_ohlc_matrices_from_history(hist, trading_days, st_history=st_history, min_price=5.0)
    T, N = mx.close.shape
    print(f"  [{time.perf_counter() - t0:.1f}s] Matrix: {T} days x {N} symbols")

    feats = compute_feature_matrices(
        close=mx.close, high=mx.high, low=mx.low,
        fast=5, slow=20, trend_fast=120, trend_slow=200,
        atr_n=14, strength_ma=120,
        v2_trend_short_ma=20, v2_trend_long_ma=60,
        breakout_window=20,
    )

    # ── Benchmark regime ──
    bench = benchmark.copy()
    bench["date"] = pd.to_datetime(bench["date"])
    bench = bench.sort_values("date")
    bench_close_s = pd.to_numeric(bench["close"], errors="coerce")
    bench_ma120 = bench_close_s.rolling(120, min_periods=120).mean()
    bench_ma60 = bench_close_s.rolling(60, min_periods=60).mean()
    bmap_close = {pd.Timestamp(d).normalize(): float(v) for d, v in zip(bench["date"], bench_close_s)}
    bmap_ma120 = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma120)}
    bmap_ma60 = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma60)}

    bench_close_arr = np.array([bmap_close.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
    bench_ma120_arr = np.array([bmap_ma120.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
    bench_ma60_arr = np.array([bmap_ma60.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)

    risk_on_120 = np.ones(T, dtype=bool)
    valid_120 = ~np.isnan(bench_close_arr) & ~np.isnan(bench_ma120_arr)
    risk_on_120[valid_120] = bench_close_arr[valid_120] > bench_ma120_arr[valid_120]

    risk_on_60 = np.ones(T, dtype=bool)
    valid_60 = ~np.isnan(bench_close_arr) & ~np.isnan(bench_ma60_arr)
    risk_on_60[valid_60] = bench_close_arr[valid_60] > bench_ma60_arr[valid_60]

    # ── Breakout signal: close[t] > high_max20[t-1] ──
    breakout_up = np.zeros((T, N), dtype=bool)
    if T > 1:
        prev_hmax = feats.high_max20[:-1, :]
        curr_close = mx.close[1:, :]
        valid = ~np.isnan(curr_close) & ~np.isnan(prev_hmax)
        breakout_up[1:, :] = (curr_close > prev_hmax) & valid

    # ── V2 trend filter ──
    v2_trend_ok = (
        ~np.isnan(mx.close)
        & ~np.isnan(feats.sma20)
        & ~np.isnan(feats.sma60)
        & (mx.close > feats.sma60)
        & (feats.sma20 > feats.sma60)
    )

    # ── Composite buy_base matrices ──
    risk_on_120_m = np.repeat(risk_on_120.reshape(-1, 1), N, axis=1)
    risk_on_60_m = np.repeat(risk_on_60.reshape(-1, 1), N, axis=1)

    # Champion config: v2_trend=OFF, regime_ma=120
    buy_base_champion = breakout_up & risk_on_120_m & mx.tradable

    # Alternative: v2_trend=ON
    buy_base_with_v2 = breakout_up & v2_trend_ok & risk_on_120_m & mx.tradable

    # Alternative: regime_ma=60
    buy_base_rma60 = breakout_up & risk_on_60_m & mx.tradable

    # No regime filter at all
    buy_base_no_regime = breakout_up & mx.tradable

    print(f"  [{time.perf_counter() - t0:.1f}s] Computing funnel stats...")

    # ── Per-quarter funnel ──
    dates_pd = pd.DatetimeIndex(mx.dates)
    yq = dates_pd.to_period("Q")

    print(f"\n{'=' * 120}")
    print(f"  ENTRY FUNNEL: 每日信号经过各阶段后的存活量")
    print(f"{'=' * 120}")
    print(f"  {'Quarter':<10} {'universe':>8} {'breakout':>9} {'tradable':>9} {'regime120':>10} {'CHAMPION':>10} {'|':>2} {'no_regime':>10} {'regime60':>10} {'+v2trend':>10}")
    print(f"  {'-' * 100}")

    for q in sorted(yq.unique()):
        mask = yq == q
        days_in_q = int(mask.sum())
        # Per-day averages
        universe_per_day = float(np.mean(np.sum(~np.isnan(mx.close[mask]), axis=1)))
        breakout_per_day = float(np.mean(np.sum(breakout_up[mask], axis=1)))
        tradable_breakout_per_day = float(np.mean(np.sum(breakout_up[mask] & mx.tradable[mask], axis=1)))
        regime120_per_day = float(np.mean(risk_on_120[mask]))  # fraction of days risk_on
        champion_per_day = float(np.mean(np.sum(buy_base_champion[mask], axis=1)))

        no_regime_per_day = float(np.mean(np.sum(buy_base_no_regime[mask], axis=1)))
        rma60_per_day = float(np.mean(np.sum(buy_base_rma60[mask], axis=1)))
        with_v2_per_day = float(np.mean(np.sum(buy_base_with_v2[mask], axis=1)))

        regime_pct = f"({regime120_per_day:.0%})"
        print(f"  {str(q):<10} {universe_per_day:>8.0f} {breakout_per_day:>9.1f} {tradable_breakout_per_day:>9.1f} {regime_pct:>10s} {champion_per_day:>10.1f} {'|':>2} {no_regime_per_day:>10.1f} {rma60_per_day:>10.1f} {with_v2_per_day:>10.1f}")

    # ── Yearly summary ──
    yy = dates_pd.year
    print(f"\n  YEARLY BLOCKING RATE SUMMARY")
    print(f"  {'Year':<6} {'Days':>5} {'Risk120ON%':>10} {'Risk60ON%':>10} {'BreakoutSig':>12} {'RegimeBlk%':>10} {'TradBlk%':>10} {'V2Blk%':>10} {'ChampionSig':>12}")
    print(f"  {'-' * 89}")

    for year in sorted(yy.unique()):
        mask = yy == year
        days_in_y = int(mask.sum())
        regime120_on = float(np.mean(risk_on_120[mask]))
        regime60_on = float(np.mean(risk_on_60[mask]))

        total_breakout = int(np.sum(breakout_up[mask]))
        total_tradable_breakout = int(np.sum(breakout_up[mask] & mx.tradable[mask]))
        total_champion = int(np.sum(buy_base_champion[mask]))
        total_no_regime = int(np.sum(buy_base_no_regime[mask]))
        total_with_v2 = int(np.sum(buy_base_with_v2[mask]))

        regime_block_pct = 1.0 - total_champion / total_no_regime if total_no_regime > 0 else 0.0
        trad_block_pct = 1.0 - total_tradable_breakout / total_breakout if total_breakout > 0 else 0.0
        v2_block_pct = 1.0 - total_with_v2 / total_champion if total_champion > 0 else 0.0

        print(f"  {year:<6} {days_in_y:>5} {regime120_on:>9.0%} {regime60_on:>9.0%} {total_breakout:>12,} {regime_block_pct:>9.0%} {trad_block_pct:>9.0%} {v2_block_pct:>9.0%} {total_champion:>12,}")

    # ── EXIT FUNNEL: 从最新回测的 trades 文件分析 ──
    # Run the actual backtest to get trade data
    print(f"\n{'=' * 120}")
    print(f"  EXIT FUNNEL: ATR Stop 拦截分析")
    print(f"{'=' * 120}")

    # Analyze ATR values at entry time for 2016-2018 vs 2024-2026
    # ATR relative to price (ATR%)
    atr_pct = feats.atr14 / mx.close * 100  # as percentage of close

    print(f"\n  ATR% 分布 (ATR14 / Close * 100)")
    print(f"  {'Quarter':<10} {'Mean':>8} {'Median':>8} {'P75':>8} {'P90':>8} {'Max':>8}")
    print(f"  {'-' * 48}")

    for q in sorted(yq.unique()):
        mask = yq == q
        vals = atr_pct[mask]
        vals_flat = vals[~np.isnan(vals) & mx.tradable[mask]]
        if len(vals_flat) == 0:
            continue
        print(f"  {str(q):<10} {np.mean(vals_flat):>7.2f}% {np.median(vals_flat):>7.2f}% {np.percentile(vals_flat, 75):>7.2f}% {np.percentile(vals_flat, 90):>7.2f}% {np.max(vals_flat):>7.2f}%")

    # Stop distance analysis: ATR_stop_k * ATR as % of price
    stop_k = 1.5
    stop_dist_pct = stop_k * atr_pct  # stop loss distance as % of price

    print(f"\n  止损距离 (k={stop_k} × ATR14 / Close × 100)")
    print(f"  {'Year':<6} {'Mean':>8} {'Median':>8} {'P25':>8} {'P75':>8}")
    print(f"  {'-' * 36}")

    for year in sorted(yy.unique()):
        mask = yy == year
        vals = stop_dist_pct[mask]
        vals_flat = vals[~np.isnan(vals) & mx.tradable[mask]]
        if len(vals_flat) == 0:
            continue
        print(f"  {year:<6} {np.mean(vals_flat):>7.2f}% {np.median(vals_flat):>7.2f}% {np.percentile(vals_flat, 25):>7.2f}% {np.percentile(vals_flat, 75):>7.2f}%")

    # ── SLOT blocking analysis: how often are slots full? ──
    print(f"\n{'=' * 120}")
    print(f"  SLOT BLOCKING: buy_sigs 到实际成交的拦截")
    print(f"{'=' * 120}")
    print(f"  champion config: max_positions=10, lot_size=100")
    print(f"  从 portfolio_daily.csv 分析:")

    # We need the latest run's portfolio_daily for slot analysis
    # Look for the most recent experiment output
    import glob
    exp_dirs = sorted(glob.glob("outputs/experiments/exp_*/portfolio_daily.csv"))
    if exp_dirs:
        latest_daily = exp_dirs[-1]
        df = pd.read_csv(latest_daily, parse_dates=["date"])
        df["year"] = df["date"].dt.year

        print(f"\n  {'Year':<6} {'SigDays':>8} {'AvgRawSig':>10} {'AvgBuyCand':>11} {'AvgSlots':>9} {'SlotsBlk%':>10} {'AvgPos':>7} {'FullDays%':>10}")
        print(f"  {'-' * 73}")

        for year, grp in df.groupby("year"):
            sig_days = grp[grp["raw_buy_signal_count"] > 0]
            if len(sig_days) == 0:
                print(f"  {year:<6} {'0':>8}")
                continue
            avg_raw = sig_days["raw_buy_signal_count"].mean()
            avg_cand = sig_days["buy_candidate_count"].mean()
            avg_slots = sig_days["buy_slots_calculated"].mean()
            avg_pos = grp["positions_count"].mean()
            full_days = (grp["positions_count"] >= 10).sum() / len(grp)
            # slot blocking: how many candidates couldn't get in
            slot_blocked = sig_days["buy_candidate_count"].sum() - sig_days["after_cash_lot_count"].sum()
            total_cands = sig_days["buy_candidate_count"].sum()
            slot_block_rate = slot_blocked / total_cands if total_cands > 0 else 0

            print(f"  {year:<6} {len(sig_days):>8} {avg_raw:>10.1f} {avg_cand:>11.1f} {avg_slots:>9.1f} {slot_block_rate:>9.0%} {avg_pos:>7.1f} {full_days:>9.0%}")
    else:
        print(f"  (no experiment data found)")

    elapsed = time.perf_counter() - t0
    print(f"\n  Total elapsed: {elapsed:.1f}s")
    print(f"{'*' * 90}")


if __name__ == "__main__":
    main()
