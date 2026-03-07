"""DD 熔断参数对 Breakout 策略的影响实验。

E0: Baseline (DD=10%/0.5)
E1: DD 关闭
E2: DD=15%/0.5 (更宽松触发)
E3: DD=10%/0.7 (降幅更小: 10→7 slots)
E4: DD=20%/0.5 (很宽松)
E5: DD=10%/0.5 + regime_ma=90 (适度放松 regime)

Usage:
  python backend/scripts/run_dd_breaker_sweep.py
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import time
from pathlib import Path

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


def _build_config(dd_enabled: bool, dd_pct: float, dd_scale: float, regime_ma: int = 120) -> str:
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
            "regime_ma": regime_ma,
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
    base["risk_budget"] = {
        "enabled": dd_enabled,
        "dd_reduce_pct": dd_pct,
        "dd_reduce_scale": dd_scale,
        "atr_stop_k": 1.5,
    }
    base["market_filter"] = {"enabled": False}
    base["benchmark_regime"] = {"enabled": False}
    base["breadth"] = {"enabled": False}
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(base, tmp, ensure_ascii=False, indent=2)
    tmp.close()
    return tmp.name


EXPERIMENTS = [
    {"id": "E0", "label": "Baseline DD=10%/0.5", "dd": True, "pct": 0.10, "scale": 0.5, "rma": 120},
    {"id": "E1", "label": "DD OFF", "dd": False, "pct": 0.10, "scale": 0.5, "rma": 120},
    {"id": "E2", "label": "DD=15%/0.5 (宽松)", "dd": True, "pct": 0.15, "scale": 0.5, "rma": 120},
    {"id": "E3", "label": "DD=10%/0.7 (轻度降仓)", "dd": True, "pct": 0.10, "scale": 0.7, "rma": 120},
    {"id": "E4", "label": "DD=20%/0.5 (很宽松)", "dd": True, "pct": 0.20, "scale": 0.5, "rma": 120},
    {"id": "E5", "label": "DD=10%/0.5 + rma=90", "dd": True, "pct": 0.10, "scale": 0.5, "rma": 90},
]


def _subperiod_analysis(results_dir: str) -> dict:
    daily_csv = Path(results_dir) / "portfolio_daily.csv"
    if not daily_csv.exists():
        return {}
    df = pd.read_csv(daily_csv, parse_dates=["date"])
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
        if grp.empty:
            continue
        nav_s, nav_e = float(grp["nav"].iloc[0]), float(grp["nav"].iloc[-1])
        ret = nav_e / nav_s - 1.0 if nav_s > 0 else 0.0
        cummax = grp["nav"].cummax()
        max_dd = float(((grp["nav"] - cummax) / cummax).min())
        avg_pos = float(grp["positions_count"].mean()) if "positions_count" in grp.columns else 0.0
        # DD state
        dd_reduced_pct = 0.0
        if "dd_state" in grp.columns:
            dd_reduced_pct = float((grp["dd_state"] == "REDUCED").sum()) / len(grp)
        sub[plabel] = {"return": ret, "max_dd": max_dd, "avg_pos": avg_pos, "dd_reduced_pct": dd_reduced_pct}
    return sub


def main() -> None:
    print(f"{'*' * 100}")
    print(f"  DD 熔断参数实验")
    print(f"  Baseline = P3-D champion + DD=10%/0.5")
    print(f"{'*' * 100}")

    all_results = []
    for exp in EXPERIMENTS:
        cfg_path = _build_config(exp["dd"], exp["pct"], exp["scale"], exp["rma"])
        t0 = time.perf_counter()
        label = f"{exp['id']}: {exp['label']}"
        print(f"\n{'=' * 80}")
        print(f"  {label}")
        print(f"{'=' * 80}")

        def progress(pct: int, msg: str) -> None:
            print(f"  [{pct:3d}%] {msg}  ({time.perf_counter() - t0:.1f}s)")

        result = run_experiment(cfg_path, preset="single", overrides=COMMON_OVERRIDES, progress_hook=progress)
        Path(cfg_path).unlink(missing_ok=True)
        elapsed = time.perf_counter() - t0

        cagr = result.get("cagr", 0)
        mdd = result.get("max_drawdown", 0)
        sharpe = result.get("sharpe", 0)
        calmar = result.get("calmar", 0)
        trades = result.get("trades", 0)

        print(f"\n  CAGR={cagr:+.2%}  MDD={mdd:.2%}  Sharpe={sharpe:.2f}  Calmar={calmar:.2f}  Trades={trades}  ({elapsed:.1f}s)")

        sub = _subperiod_analysis(result.get("results_dir", ""))
        all_results.append({
            "id": exp["id"], "label": label,
            "cagr": cagr, "mdd": mdd, "sharpe": sharpe, "calmar": calmar, "trades": trades,
            "sub": sub,
        })

    # ── Rankings ──
    print(f"\n\n{'#' * 100}")
    print(f"  OVERALL RANKING (by Calmar)")
    print(f"{'#' * 100}")
    print(f"  {'Rank':<5} {'Config':<40} {'CAGR':>7} {'MDD':>8} {'Sharpe':>7} {'Calmar':>7} {'Trades':>7}")
    print(f"  {'-' * 83}")
    sorted_r = sorted(all_results, key=lambda r: r.get("calmar", 0), reverse=True)
    for i, r in enumerate(sorted_r):
        marker = " ***" if i == 0 else ""
        print(f"  {i+1:<5} {r['label']:<40} {r['cagr']:>+6.2%} {r['mdd']:>7.2%} {r['sharpe']:>7.2f} {r['calmar']:>7.2f} {r['trades']:>7}{marker}")

    # ── Sub-period returns ──
    print(f"\n  SUB-PERIOD RETURNS")
    print(f"  {'Config':<40} {'16-18':>8} {'19-21':>8} {'22-23':>8} {'24-26':>8}")
    print(f"  {'-' * 76}")
    for r in all_results:
        s = r["sub"]
        print(f"  {r['label']:<40} {s.get('2016-2018', {}).get('return', 0):>+7.2%} {s.get('2019-2021', {}).get('return', 0):>+7.2%} {s.get('2022-2023', {}).get('return', 0):>+7.2%} {s.get('2024-2026', {}).get('return', 0):>+7.2%}")

    # ── Sub-period MDD ──
    print(f"\n  SUB-PERIOD MDD")
    print(f"  {'Config':<40} {'16-18':>8} {'19-21':>8} {'22-23':>8} {'24-26':>8}")
    print(f"  {'-' * 76}")
    for r in all_results:
        s = r["sub"]
        print(f"  {r['label']:<40} {s.get('2016-2018', {}).get('max_dd', 0):>7.2%} {s.get('2019-2021', {}).get('max_dd', 0):>7.2%} {s.get('2022-2023', {}).get('max_dd', 0):>7.2%} {s.get('2024-2026', {}).get('max_dd', 0):>7.2%}")

    # ── Average positions ──
    print(f"\n  AVERAGE POSITIONS")
    print(f"  {'Config':<40} {'16-18':>8} {'19-21':>8} {'22-23':>8} {'24-26':>8}")
    print(f"  {'-' * 76}")
    for r in all_results:
        s = r["sub"]
        print(f"  {r['label']:<40} {s.get('2016-2018', {}).get('avg_pos', 0):>7.1f} {s.get('2019-2021', {}).get('avg_pos', 0):>7.1f} {s.get('2022-2023', {}).get('avg_pos', 0):>7.1f} {s.get('2024-2026', {}).get('avg_pos', 0):>7.1f}")

    # ── DD Reduced % ──
    print(f"\n  DD REDUCED DAYS %")
    print(f"  {'Config':<40} {'16-18':>8} {'19-21':>8} {'22-23':>8} {'24-26':>8}")
    print(f"  {'-' * 76}")
    for r in all_results:
        s = r["sub"]
        print(f"  {r['label']:<40} {s.get('2016-2018', {}).get('dd_reduced_pct', 0):>7.0%} {s.get('2019-2021', {}).get('dd_reduced_pct', 0):>7.0%} {s.get('2022-2023', {}).get('dd_reduced_pct', 0):>7.0%} {s.get('2024-2026', {}).get('dd_reduced_pct', 0):>7.0%}")

    print(f"\n{'#' * 100}")
    print(f"  DONE")


if __name__ == "__main__":
    main()
