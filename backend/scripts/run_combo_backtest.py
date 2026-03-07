"""双策略组合回测: EMA Cross Champion + Breakout P3-D Champion

测试不同配比的资金分配方案，验证组合能否:
1. 降低 MDD（两策略亏损期不完全重叠）
2. 提高 Sharpe（分散化效应）
3. 保持可接受的 CAGR

组合方式：各自独立回测 → 合并 NAV 曲线（等价于每日再平衡）

Usage:
  python backend/scripts/run_combo_backtest.py
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd

from backend.core.tools.experiment_runner import run_experiment

COMMON_OVERRIDES = {
    "universe_mode": "HS300_ZZ500", "start_date": "2016-03-01", "end_date": "2026-03-01",
    "benchmark": "000300.SH", "initial_capital": 1_000_000, "max_positions": 10,
    "base_order_value": 0, "fast_mode": True, "price_adj": "hfq",
    "enable_strength_rank": False, "enable_multifactor_rank": False, "momentum_top_pct": 0.0,
}


def _build_ema_config() -> str:
    """EMA Cross Champion: EMA(8,25) + TP30% + trail_k=6 + min5/cool5"""
    base_path = _root / "backend" / "configs" / "pams_cn_pg.json"
    base = json.loads(base_path.read_text(encoding="utf-8-sig"))
    base["universe"] = {
        **base.get("universe", {}),
        "start": "2016-03-01", "end": "2026-03-01",
        "benchmark": "000300.SH", "symbols": [],
    }
    base["initial_capital"] = 1_000_000
    base["strategy"] = {
        "name": "ema_cross", "order_size": 1000,
        "params": {
            "fast": 8, "slow": 25,
            "min_price": 5.0,
            "regime_ma": 120,
            "enable_v2_trend_filter": False,
            "enable_atr_stop": True, "atr_stop_k": 2.0,
            "enable_atr_trail": True, "atr_trail_k": 6.0,
            "enable_take_profit": True, "take_profit_mode": "pct", "take_profit_pct": 0.30,
            "enable_fixed_stop_loss": False,
            "enable_ma20_exit": False, "enable_low10_exit": False,
            "max_hold_days": 0,
            "min_hold_days": 5, "cooldown_days": 5,
            "momentum_top_pct": 0.0, "enable_sector_gate": False,
        },
    }
    base["exit"] = {
        "enable_atr_stop": True, "atr_stop_k": 2.0,
        "enable_atr_trail": True, "atr_trail_k": 6.0,
        "enable_take_profit": True, "take_profit_mode": "pct", "take_profit_pct": 0.30,
        "enable_fixed_stop_loss": False, "enable_low10_exit": False,
    }
    base["sizing"] = {"order_value": 0, "lot_size": 100, "weight_mode": "equal", "min_positions": 10}
    base["risk_budget"] = {"enabled": True, "dd_reduce_pct": 0.10, "dd_reduce_scale": 0.5, "atr_stop_k": 2.0}
    base["market_filter"] = {"enabled": False}
    base["benchmark_regime"] = {"enabled": False}
    base["breadth"] = {"enabled": False}
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(base, tmp, ensure_ascii=False, indent=2)
    tmp.close()
    return tmp.name


def _build_breakout_config() -> str:
    """Breakout P3-D Champion: bw=20, v2_trend=off, regime_ma=120, TP=20%, trail_k=3, atr_stop_k=1.5, LOW10, DD=10%/0.5"""
    base_path = _root / "backend" / "configs" / "pams_cn_pg.json"
    base = json.loads(base_path.read_text(encoding="utf-8-sig"))
    base["universe"] = {
        **base.get("universe", {}),
        "start": "2016-03-01", "end": "2026-03-01",
        "benchmark": "000300.SH", "symbols": [],
    }
    base["initial_capital"] = 1_000_000
    base["strategy"] = {
        "name": "breakout_trend", "order_size": 1000,
        "params": {
            "breakout_window": 20, "min_price": 5.0,
            "regime_ma": 120,
            "enable_v2_trend_filter": False,
            "v2_trend_short_ma": 20, "v2_trend_long_ma": 60,
            "enable_atr_stop": True, "atr_stop_k": 1.5,
            "enable_atr_trail": True, "atr_trail_k": 3.0,
            "enable_take_profit": True, "take_profit_mode": "pct", "take_profit_pct": 0.20,
            "enable_fixed_stop_loss": False,
            "enable_ma20_exit": False, "enable_low10_exit": True,
            "max_hold_days": 0,
            "min_hold_days": 5, "cooldown_days": 5,
            "momentum_top_pct": 0.0, "enable_sector_gate": False,
            "enable_risk_off_exit": False,
        },
    }
    base["exit"] = {
        "enable_atr_stop": True, "atr_stop_k": 1.5,
        "enable_atr_trail": True, "atr_trail_k": 3.0,
        "enable_take_profit": True, "take_profit_mode": "pct", "take_profit_pct": 0.20,
        "enable_fixed_stop_loss": False, "enable_low10_exit": True,
    }
    base["sizing"] = {"order_value": 0, "lot_size": 100, "weight_mode": "equal", "min_positions": 10}
    base["risk_budget"] = {"enabled": True, "dd_reduce_pct": 0.10, "dd_reduce_scale": 0.5, "atr_stop_k": 1.5}
    base["market_filter"] = {"enabled": False}
    base["benchmark_regime"] = {"enabled": False}
    base["breadth"] = {"enabled": False}
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(base, tmp, ensure_ascii=False, indent=2)
    tmp.close()
    return tmp.name


def _compute_metrics(nav: pd.Series, dates: pd.Series) -> dict:
    """从 NAV 序列计算核心指标"""
    if len(nav) < 2:
        return {"cagr": 0, "max_drawdown": 0, "sharpe": 0, "calmar": 0}
    nav_arr = nav.values.astype(float)
    total_ret = nav_arr[-1] / nav_arr[0] - 1.0

    d0 = pd.Timestamp(dates.iloc[0])
    d1 = pd.Timestamp(dates.iloc[-1])
    years = (d1 - d0).days / 365.25
    cagr = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0

    cummax = np.maximum.accumulate(nav_arr)
    dd = (nav_arr - cummax) / cummax
    max_dd = float(dd.min())

    daily_ret = np.diff(nav_arr) / nav_arr[:-1]
    sharpe = float(np.mean(daily_ret) / np.std(daily_ret) * np.sqrt(244)) if np.std(daily_ret) > 0 else 0

    calmar = cagr / abs(max_dd) if abs(max_dd) > 1e-8 else 0

    return {"cagr": cagr, "max_drawdown": max_dd, "sharpe": sharpe, "calmar": calmar, "total_return": total_ret}


def _subperiod_metrics(nav: pd.Series, dates: pd.Series) -> dict:
    """分子周期计算指标"""
    df = pd.DataFrame({"date": pd.to_datetime(dates), "nav": nav.values.astype(float)})
    periods = {
        "2016-2018": ("2016-01-01", "2018-12-31"),
        "2019-2021": ("2019-01-01", "2021-12-31"),
        "2022-2023": ("2022-01-01", "2023-12-31"),
        "2024-2026": ("2024-01-01", "2026-12-31"),
    }
    sub = {}
    for plabel, (start, end) in periods.items():
        mask = (df["date"] >= start) & (df["date"] <= end)
        grp = df[mask].sort_values("date")
        if len(grp) < 2:
            continue
        nav_s, nav_e = float(grp["nav"].iloc[0]), float(grp["nav"].iloc[-1])
        ret = nav_e / nav_s - 1.0 if nav_s > 0 else 0.0
        cummax = grp["nav"].cummax()
        max_dd = float(((grp["nav"] - cummax) / cummax).min())
        sub[plabel] = {"return": ret, "max_dd": max_dd}
    return sub


def _correlation_analysis(ema_daily: pd.DataFrame, bo_daily: pd.DataFrame) -> dict:
    """计算两策略日收益率相关性"""
    merged = pd.merge(
        ema_daily[["date", "nav"]].rename(columns={"nav": "ema_nav"}),
        bo_daily[["date", "nav"]].rename(columns={"nav": "bo_nav"}),
        on="date", how="inner",
    )
    if len(merged) < 10:
        return {"correlation": 0, "n_days": 0}

    ema_ret = merged["ema_nav"].pct_change().dropna()
    bo_ret = merged["bo_nav"].pct_change().dropna()
    corr = float(ema_ret.corr(bo_ret))

    # 滚动相关性（120日窗口）
    rolling_corr = ema_ret.rolling(120).corr(bo_ret).dropna()
    return {
        "correlation": corr,
        "n_days": len(merged),
        "rolling_corr_mean": float(rolling_corr.mean()) if len(rolling_corr) > 0 else 0,
        "rolling_corr_min": float(rolling_corr.min()) if len(rolling_corr) > 0 else 0,
        "rolling_corr_max": float(rolling_corr.max()) if len(rolling_corr) > 0 else 0,
    }


ALLOCATIONS = [
    {"id": "EMA_ONLY", "label": "EMA Cross Only", "ema_w": 1.0, "bo_w": 0.0},
    {"id": "BO_ONLY", "label": "Breakout Only", "ema_w": 0.0, "bo_w": 1.0},
    {"id": "COMBO_70_30", "label": "70% EMA + 30% BO", "ema_w": 0.7, "bo_w": 0.3},
    {"id": "COMBO_60_40", "label": "60% EMA + 40% BO", "ema_w": 0.6, "bo_w": 0.4},
    {"id": "COMBO_50_50", "label": "50% EMA + 50% BO", "ema_w": 0.5, "bo_w": 0.5},
    {"id": "COMBO_40_60", "label": "40% EMA + 60% BO", "ema_w": 0.4, "bo_w": 0.6},
    {"id": "COMBO_30_70", "label": "30% EMA + 70% BO", "ema_w": 0.3, "bo_w": 0.7},
]


def main() -> None:
    print(f"{'*' * 100}")
    print(f"  双策略组合回测: EMA Cross Champion + Breakout P3-D Champion")
    print(f"  Universe: CSI800 (HS300+ZZ500), 2016-03-01 ~ 2026-03-01")
    print(f"  资金: 100万，各配比独立测试")
    print(f"{'*' * 100}")

    # ── Step 1: 跑 EMA Cross Champion ──
    print(f"\n{'=' * 80}")
    print(f"  [1/2] EMA Cross Champion: EMA(8,25) + TP30% + trail_k=6 + min5/cool5")
    print(f"{'=' * 80}")
    ema_cfg = _build_ema_config()
    t0 = time.perf_counter()

    def ema_progress(pct: int, msg: str) -> None:
        print(f"  [{pct:3d}%] {msg}  ({time.perf_counter() - t0:.1f}s)")

    ema_result = run_experiment(ema_cfg, preset="single", overrides=COMMON_OVERRIDES, progress_hook=ema_progress)
    Path(ema_cfg).unlink(missing_ok=True)
    ema_elapsed = time.perf_counter() - t0
    print(f"  EMA Done: CAGR={ema_result['cagr']:+.2%}  MDD={ema_result['max_drawdown']:.2%}  "
          f"Sharpe={ema_result['sharpe']:.2f}  Trades={ema_result['trades']}  ({ema_elapsed:.1f}s)")

    # ── Step 2: 跑 Breakout P3-D Champion ──
    print(f"\n{'=' * 80}")
    print(f"  [2/2] Breakout P3-D Champion: bw=20, TP20%, trail_k=3, atr_stop=1.5, DD=10%/0.5")
    print(f"{'=' * 80}")
    bo_cfg = _build_breakout_config()
    t1 = time.perf_counter()

    def bo_progress(pct: int, msg: str) -> None:
        print(f"  [{pct:3d}%] {msg}  ({time.perf_counter() - t1:.1f}s)")

    bo_result = run_experiment(bo_cfg, preset="single", overrides=COMMON_OVERRIDES, progress_hook=bo_progress)
    Path(bo_cfg).unlink(missing_ok=True)
    bo_elapsed = time.perf_counter() - t1
    print(f"  BO Done: CAGR={bo_result['cagr']:+.2%}  MDD={bo_result['max_drawdown']:.2%}  "
          f"Sharpe={bo_result['sharpe']:.2f}  Trades={bo_result['trades']}  ({bo_elapsed:.1f}s)")

    # ── Step 3: 加载两条 NAV 曲线 ──
    ema_daily = pd.read_csv(Path(ema_result["results_dir"]) / "portfolio_daily.csv", parse_dates=["date"])
    bo_daily = pd.read_csv(Path(bo_result["results_dir"]) / "portfolio_daily.csv", parse_dates=["date"])

    # 对齐日期
    merged = pd.merge(
        ema_daily[["date", "nav"]].rename(columns={"nav": "ema_nav"}),
        bo_daily[["date", "nav"]].rename(columns={"nav": "bo_nav"}),
        on="date", how="inner",
    ).sort_values("date").reset_index(drop=True)

    print(f"\n  对齐后交易日数: {len(merged)}")

    # 归一化到 1.0 起始
    ema_nav_norm = merged["ema_nav"] / merged["ema_nav"].iloc[0]
    bo_nav_norm = merged["bo_nav"] / merged["bo_nav"].iloc[0]

    # ── Step 4: 相关性分析 ──
    corr_info = _correlation_analysis(ema_daily, bo_daily)
    print(f"\n{'=' * 80}")
    print(f"  相关性分析")
    print(f"{'=' * 80}")
    print(f"  全局日收益率相关系数:  {corr_info['correlation']:.4f}")
    print(f"  120日滚动相关系数均值: {corr_info['rolling_corr_mean']:.4f}")
    print(f"  120日滚动相关系数范围: [{corr_info['rolling_corr_min']:.4f}, {corr_info['rolling_corr_max']:.4f}]")
    if corr_info["correlation"] < 0.3:
        print(f"  → 低相关: 组合分散化效果极好")
    elif corr_info["correlation"] < 0.6:
        print(f"  → 中等相关: 组合有一定分散化效果")
    else:
        print(f"  → 高相关: 两策略走势相似，组合效果有限")

    # ── Step 5: 不同配比组合测算 ──
    all_results = []
    for alloc in ALLOCATIONS:
        w_ema, w_bo = alloc["ema_w"], alloc["bo_w"]
        if w_ema == 1.0:
            combo_nav = ema_nav_norm
        elif w_bo == 1.0:
            combo_nav = bo_nav_norm
        else:
            combo_nav = w_ema * ema_nav_norm + w_bo * bo_nav_norm

        m = _compute_metrics(combo_nav, merged["date"])
        sub = _subperiod_metrics(combo_nav, merged["date"])
        all_results.append({
            "id": alloc["id"], "label": alloc["label"],
            **m, "sub": sub,
        })

    # ── Step 6: 排名 ──
    print(f"\n\n{'#' * 100}")
    print(f"  OVERALL RANKING (by Calmar)")
    print(f"{'#' * 100}")
    print(f"  {'Rank':<5} {'Config':<30} {'CAGR':>8} {'MDD':>9} {'Sharpe':>8} {'Calmar':>8} {'TotalRet':>10}")
    print(f"  {'-' * 83}")
    sorted_r = sorted(all_results, key=lambda r: r.get("calmar", 0), reverse=True)
    for i, r in enumerate(sorted_r):
        marker = " ***" if i == 0 else ""
        print(f"  {i+1:<5} {r['label']:<30} {r['cagr']:>+7.2%} {r['max_drawdown']:>8.2%} "
              f"{r['sharpe']:>8.2f} {r['calmar']:>8.2f} {r['total_return']:>+9.2%}{marker}")

    # ── Sub-period returns ──
    print(f"\n  SUB-PERIOD RETURNS")
    print(f"  {'Config':<30} {'16-18':>9} {'19-21':>9} {'22-23':>9} {'24-26':>9}")
    print(f"  {'-' * 70}")
    for r in all_results:
        s = r["sub"]
        print(f"  {r['label']:<30} "
              f"{s.get('2016-2018', {}).get('return', 0):>+8.2%} "
              f"{s.get('2019-2021', {}).get('return', 0):>+8.2%} "
              f"{s.get('2022-2023', {}).get('return', 0):>+8.2%} "
              f"{s.get('2024-2026', {}).get('return', 0):>+8.2%}")

    # ── Sub-period MDD ──
    print(f"\n  SUB-PERIOD MDD")
    print(f"  {'Config':<30} {'16-18':>9} {'19-21':>9} {'22-23':>9} {'24-26':>9}")
    print(f"  {'-' * 70}")
    for r in all_results:
        s = r["sub"]
        print(f"  {r['label']:<30} "
              f"{s.get('2016-2018', {}).get('max_dd', 0):>8.2%} "
              f"{s.get('2019-2021', {}).get('max_dd', 0):>8.2%} "
              f"{s.get('2022-2023', {}).get('max_dd', 0):>8.2%} "
              f"{s.get('2024-2026', {}).get('max_dd', 0):>8.2%}")

    # ── 组合 vs 单策略改善幅度 ──
    ema_only = next(r for r in all_results if r["id"] == "EMA_ONLY")
    bo_only = next(r for r in all_results if r["id"] == "BO_ONLY")
    best_combo = sorted_r[0]

    print(f"\n{'#' * 100}")
    print(f"  组合 vs 单策略改善分析")
    print(f"{'#' * 100}")
    print(f"  {'指标':<20} {'EMA Only':>12} {'BO Only':>12} {'最优组合':>12} {'vs EMA':>10} {'vs BO':>10}")
    print(f"  {'-' * 78}")
    for metric in ["cagr", "max_drawdown", "sharpe", "calmar"]:
        ema_v = ema_only[metric]
        bo_v = bo_only[metric]
        best_v = best_combo[metric]
        delta_ema = best_v - ema_v
        delta_bo = best_v - bo_v
        if metric in ("cagr", "max_drawdown", "total_return"):
            print(f"  {metric:<20} {ema_v:>+11.2%} {bo_v:>+11.2%} {best_v:>+11.2%} {delta_ema:>+10.2%} {delta_bo:>+10.2%}")
        else:
            print(f"  {metric:<20} {ema_v:>+11.2f} {bo_v:>+11.2f} {best_v:>+11.2f} {delta_ema:>+10.2f} {delta_bo:>+10.2f}")
    print(f"\n  最优组合: {best_combo['label']}")
    print(f"  相关系数: {corr_info['correlation']:.4f}")

    # ── 逐年收益对比 ──
    print(f"\n  逐年收益对比")
    print(f"  {'Year':<8} {'EMA':>8} {'BO':>8} {'50/50':>8} {'Best Combo':>12}")
    print(f"  {'-' * 48}")
    combo_50 = next(r for r in all_results if r["id"] == "COMBO_50_50")
    for year in range(2016, 2027):
        yr_start = f"{year}-01-01"
        yr_end = f"{year}-12-31"
        mask = (merged["date"] >= yr_start) & (merged["date"] <= yr_end)
        yr_data = merged[mask]
        if len(yr_data) < 2:
            continue
        ema_yr_nav = yr_data["ema_nav"] / yr_data["ema_nav"].iloc[0]
        bo_yr_nav = yr_data["bo_nav"] / yr_data["bo_nav"].iloc[0]
        ema_yr_ret = float(ema_yr_nav.iloc[-1]) - 1.0
        bo_yr_ret = float(bo_yr_nav.iloc[-1]) - 1.0

        # 50/50 combo
        ema_norm_yr = ema_nav_norm.iloc[mask.values]
        bo_norm_yr = bo_nav_norm.iloc[mask.values]
        combo50_yr = 0.5 * ema_norm_yr + 0.5 * bo_norm_yr
        combo50_yr_ret = float(combo50_yr.iloc[-1] / combo50_yr.iloc[0]) - 1.0

        # Best combo
        w_ema_b = next(a["ema_w"] for a in ALLOCATIONS if a["id"] == best_combo["id"])
        w_bo_b = next(a["bo_w"] for a in ALLOCATIONS if a["id"] == best_combo["id"])
        if w_ema_b == 1.0:
            best_yr = ema_norm_yr
        elif w_bo_b == 1.0:
            best_yr = bo_norm_yr
        else:
            best_yr = w_ema_b * ema_norm_yr + w_bo_b * bo_norm_yr
        best_yr_ret = float(best_yr.iloc[-1] / best_yr.iloc[0]) - 1.0

        print(f"  {year:<8} {ema_yr_ret:>+7.2%} {bo_yr_ret:>+7.2%} {combo50_yr_ret:>+7.2%} {best_yr_ret:>+11.2%}")

    print(f"\n{'#' * 100}")
    print(f"  DONE")


if __name__ == "__main__":
    main()
