"""RegimeFilter 诊断分析脚本。

不运行完整回测，仅加载数据 + 计算 RegimeFilter，输出信号分布统计。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# ── 项目根 ──
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.core.config.loader import load_config
from backend.core.data.cached_provider import CachedDataProvider
from backend.core.data.pg_provider import PostgresDataProvider
from backend.core.data.price_adjust import apply_price_adjustment
from backend.core.engine_vector.data_matrix import OhlcMatrices, build_ohlc_matrices_from_history
from backend.core.engine_vector.regime_filter import RegimeFilter, RegimeFilterConfig
from backend.core.universe.universe_resolver import resolve_universe_by_mode


def main():
    cfg_path = ROOT / "backend" / "configs" / "sweep" / "r3_regime_filter_csi800.json"
    cfg_obj, _ = load_config(str(cfg_path))

    provider = CachedDataProvider(
        inner=PostgresDataProvider(
            db=cfg_obj.db,
            runtime=cfg_obj.db_runtime,
            data_source=cfg_obj.data_source,
            schema_mapping=cfg_obj.schema_mapping,
            rules_path=cfg_path.parent / "instrument_rules_cn.csv",
        )
    )

    # ── Universe ──
    symbols, _ = resolve_universe_by_mode(
        mode="HS300_ZZ500",
        as_of=cfg_obj.universe.start,
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
    )
    print(f"Universe: {len(symbols)} stocks")

    # ── 数据 ──
    history = provider.load_ohlcv_daily(symbols, cfg_obj.universe.start, cfg_obj.universe.end, source="stocks")
    benchmark = provider.load_benchmark_daily(cfg_obj.universe.benchmark, cfg_obj.universe.start, cfg_obj.universe.end)
    calendar = provider.load_trading_calendar_cn(cfg_obj.universe.start, cfg_obj.universe.end)
    trading_days = [d.date() for d in calendar]

    signal_history = apply_price_adjustment(history, "hfq") if "adj_factor" in history.columns else history

    sector_indices_raw = provider.load_sector_indices(cfg_obj.universe.start, cfg_obj.universe.end)
    industry_map = provider.load_industry_mapping(symbols)
    sector_data: dict[str, pd.DataFrame] = {}
    if not sector_indices_raw.empty and "index_code" in sector_indices_raw.columns:
        for code, grp in sector_indices_raw.groupby("index_code"):
            sector_data[str(code)] = grp.reset_index(drop=True)

    # ── OhlcMatrices ──
    mx = build_ohlc_matrices_from_history(signal_history, trading_days)
    sym_to_col = {s: i for i, s in enumerate(mx.symbols)}

    # ── Benchmark arrays ──
    bench_map = {}
    for _, row in benchmark.iterrows():
        d = row["date"]
        if hasattr(d, "date"):
            d = d.date()
        bench_map[d] = row

    bench_close = np.array([float(bench_map[d]["close"]) if d in bench_map else np.nan for d in trading_days])
    bench_high = np.array([float(bench_map[d]["high"]) if d in bench_map else np.nan for d in trading_days])
    bench_low = np.array([float(bench_map[d]["low"]) if d in bench_map else np.nan for d in trading_days])

    T, N = mx.close.shape
    print(f"DataMatrix: T={T}, N={N}")
    print(f"Trading days: {trading_days[0]} → {trading_days[-1]}")
    print(f"Sector data: {len(sector_data)} indices")
    print(f"Industry map coverage: {len(industry_map)}/{len(symbols)} stocks")

    # ── RegimeFilter ──
    rf_cfg = RegimeFilterConfig(
        ema_slope_span=50, slope_lookback=10,
        ema_short_span=20, ema_long_span=60,
        adx_period=14,
        w_slope=0.4, w_spread=0.3, w_adx=0.3,
        zscore_window=120, ema_smooth_span=10,
        alpha_m=2.0, alpha_sec=2.0, alpha_i=2.0,
        regime_threshold=0.3,
    )

    t0 = time.perf_counter()
    rf = RegimeFilter(rf_cfg)
    rf.precompute(
        benchmark_close=bench_close,
        benchmark_high=bench_high,
        benchmark_low=bench_low,
        stock_close=mx.close,
        stock_high=mx.high,
        stock_low=mx.low,
        sector_data=sector_data,
        industry_map=industry_map,
        sym_to_col=sym_to_col,
        trading_days=trading_days,
    )
    elapsed = time.perf_counter() - t0
    print(f"\nRegimeFilter precompute: {elapsed:.2f}s")

    # ── 诊断 ──
    print("\n" + "=" * 60)
    print("REGIME FILTER DIAGNOSTICS")
    print("=" * 60)

    diag = rf.diagnostics
    for k, v in diag.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    # ── 各层 gate 分布 ──
    gate_m = rf._gate_m
    gate_sec = rf._gate_sec
    gate_stock = rf._gate_stock
    rs = rf.regime_signals

    print(f"\n--- Layer 1: Market Gate (T,) ---")
    valid_m = gate_m[~np.isnan(gate_m)]
    print(f"  shape: {gate_m.shape}")
    print(f"  mean={np.mean(valid_m):.4f}, std={np.std(valid_m):.4f}")
    print(f"  min={np.min(valid_m):.4f}, p25={np.percentile(valid_m,25):.4f}, median={np.median(valid_m):.4f}, p75={np.percentile(valid_m,75):.4f}, max={np.max(valid_m):.4f}")
    print(f"  >0.3: {np.mean(valid_m >= 0.3)*100:.1f}%  >0.5: {np.mean(valid_m >= 0.5)*100:.1f}%  >0.7: {np.mean(valid_m >= 0.7)*100:.1f}%")

    print(f"\n--- Layer 2: Sector Gate (T, N) ---")
    valid_sec = gate_sec[~np.isnan(gate_sec)]
    print(f"  shape: {gate_sec.shape}")
    print(f"  mean={np.mean(valid_sec):.4f}, std={np.std(valid_sec):.4f}")
    print(f"  min={np.min(valid_sec):.4f}, median={np.median(valid_sec):.4f}, max={np.max(valid_sec):.4f}")
    print(f"  >0.3: {np.mean(valid_sec >= 0.3)*100:.1f}%  >0.5: {np.mean(valid_sec >= 0.5)*100:.1f}%  >0.7: {np.mean(valid_sec >= 0.7)*100:.1f}%")

    print(f"\n--- Layer 3: Stock Gate (T, N) ---")
    valid_stock = gate_stock[~np.isnan(gate_stock)]
    print(f"  shape: {gate_stock.shape}")
    print(f"  mean={np.mean(valid_stock):.4f}, std={np.std(valid_stock):.4f}")
    print(f"  min={np.min(valid_stock):.4f}, median={np.median(valid_stock):.4f}, max={np.max(valid_stock):.4f}")
    print(f"  >0.3: {np.mean(valid_stock >= 0.3)*100:.1f}%  >0.5: {np.mean(valid_stock >= 0.5)*100:.1f}%  >0.7: {np.mean(valid_stock >= 0.7)*100:.1f}%")

    print(f"\n--- Final Regime Signal = G_m × G_sec × G_stock (T, N) ---")
    valid_rs = rs[~np.isnan(rs)]
    print(f"  shape: {rs.shape}")
    print(f"  mean={np.mean(valid_rs):.4f}, std={np.std(valid_rs):.4f}")
    print(f"  min={np.min(valid_rs):.4f}, p10={np.percentile(valid_rs,10):.4f}, median={np.median(valid_rs):.4f}, p90={np.percentile(valid_rs,90):.4f}, max={np.max(valid_rs):.4f}")

    for thr in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        pct = np.mean(valid_rs >= thr) * 100
        print(f"  regime_on (threshold={thr}): {pct:.1f}% of stock-days")

    # ── 逐日 regime_on 统计 ──
    print(f"\n--- Per-day regime_on breakdown (threshold=0.3) ---")
    regime_on = rs >= 0.3
    daily_trend_pct = np.nanmean(regime_on, axis=1) * 100  # (T,) pct of stocks in trend per day

    print(f"  Daily trend%: mean={np.nanmean(daily_trend_pct):.1f}%, std={np.nanstd(daily_trend_pct):.1f}%")
    print(f"  Days where >80% stocks in trend: {np.sum(daily_trend_pct > 80)}/{T} ({np.sum(daily_trend_pct > 80)/T*100:.1f}%)")
    print(f"  Days where <20% stocks in trend: {np.sum(daily_trend_pct < 20)}/{T} ({np.sum(daily_trend_pct < 20)/T*100:.1f}%)")
    print(f"  Days where 20-80% stocks (MIXED): {np.sum((daily_trend_pct >= 20) & (daily_trend_pct <= 80))}/{T}")

    # ── 对比: 旧 regime (bench_close > MA60) ──
    from backend.core.engine_vector.features import _ewm_mean_matrix
    bench_ma60 = _ewm_mean_matrix(bench_close[:, np.newaxis], 60)[:, 0]
    old_regime = bench_close > bench_ma60
    old_trend_days = np.sum(old_regime[~np.isnan(bench_ma60)])
    old_total = np.sum(~np.isnan(bench_ma60))
    print(f"\n--- Old regime (bench > MA60): {old_trend_days}/{old_total} trend days ({old_trend_days/old_total*100:.1f}%) ---")

    # ── 新旧 regime 一致性 ──
    # 旧: 全局binary; 新: 逐股票, 按 majority 统计
    new_global_trend = daily_trend_pct > 50  # majority of stocks in trend
    valid_mask = ~np.isnan(bench_ma60)
    agree = np.sum(new_global_trend[valid_mask] == old_regime[valid_mask])
    print(f"  Agreement (new majority vs old): {agree}/{np.sum(valid_mask)} ({agree/np.sum(valid_mask)*100:.1f}%)")

    # ── Gate_m 与旧 regime 对比 ──
    print(f"\n--- Market gate vs old regime ---")
    gm_trend = gate_m >= 0.5  # market layer says trend
    agree_m = np.sum(gm_trend[valid_mask] == old_regime[valid_mask])
    print(f"  Market gate>0.5 vs bench>MA60: {agree_m}/{np.sum(valid_mask)} agreement ({agree_m/np.sum(valid_mask)*100:.1f}%)")

    # ── Regime signal 时序变化：regime flipping frequency ──
    print(f"\n--- Regime flipping frequency (threshold=0.3) ---")
    regime_on_f = regime_on.astype(float)
    flips = np.abs(np.diff(regime_on_f, axis=0))  # (T-1, N)
    daily_flip_rate = np.nanmean(flips, axis=1) * 100  # pct of stocks that flip per day
    print(f"  Daily flip rate: mean={np.nanmean(daily_flip_rate):.2f}%, max={np.nanmax(daily_flip_rate):.2f}%")
    total_flips = np.nansum(flips)
    print(f"  Total stock-day flips: {int(total_flips)}")


if __name__ == "__main__":
    main()
