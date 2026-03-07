"""验证三种改进方案对 Breakout 2016-2018 跟随度的影响。

E0: baseline (P3-D champion, 无 max_hold, 无 risk_off_exit)
E1: max_hold_days=90
E2: max_hold_days=60
E3: enable_risk_off_exit=True
E4: max_hold_days=90 + risk_off_exit
E5: max_hold_days=60 + risk_off_exit

Usage:
  python backend/scripts/run_breakout_fix_sweep.py
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


def _build_config(max_hold: int, risk_off_exit: bool) -> str:
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
            "max_hold_days": max_hold,
            "min_hold_days": 5, "cooldown_days": 5,
            "momentum_top_pct": 0.0, "enable_sector_gate": False,
            "enable_risk_off_exit": risk_off_exit,
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


EXPERIMENTS = [
    {"id": "E0", "label": "Baseline (P3-D champion)", "max_hold": 0, "risk_off": False},
    {"id": "E1", "label": "max_hold=90", "max_hold": 90, "risk_off": False},
    {"id": "E2", "label": "max_hold=60", "max_hold": 60, "risk_off": False},
    {"id": "E3", "label": "risk_off_exit=ON", "max_hold": 0, "risk_off": True},
    {"id": "E4", "label": "max_hold=90 + risk_off", "max_hold": 90, "risk_off": True},
    {"id": "E5", "label": "max_hold=60 + risk_off", "max_hold": 60, "risk_off": True},
]


def _analyze_subperiods(results_dir: str, label: str) -> dict:
    """Extract sub-period returns from portfolio_daily.csv."""
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
        nav_start = float(grp["nav"].iloc[0])
        nav_end = float(grp["nav"].iloc[-1])
        ret = nav_end / nav_start - 1.0 if nav_start > 0 else 0.0
        cummax = grp["nav"].cummax()
        dd = (grp["nav"] - cummax) / cummax
        max_dd = float(dd.min())
        avg_pos = float(grp["positions_count"].mean()) if "positions_count" in grp.columns else 0.0
        sub[plabel] = {"return": ret, "max_dd": max_dd, "avg_pos": avg_pos}
    return sub


def _analyze_trades_summary(results_dir: str) -> dict:
    """Extract trade stats from transaction log."""
    trades_csv = Path(results_dir) / "portfolio_trades.csv"
    if not trades_csv.exists():
        return {}
    df = pd.read_csv(trades_csv, parse_dates=["date"])
    buys = df[df["side"] == "BUY"]
    sells = df[df["side"] == "SELL"]

    # Match round-trips
    buy_records: dict[str, list] = {}
    for _, row in buys.iterrows():
        buy_records.setdefault(str(row["symbol"]), []).append(row)

    periods_trades: dict[str, list] = {"2016-2018": [], "2024-2026": []}
    for _, sell_row in sells.sort_values("date").iterrows():
        sym = str(sell_row["symbol"])
        if sym not in buy_records or not buy_records[sym]:
            continue
        buy_row = buy_records[sym].pop(0)
        buy_price = float(buy_row["fill_price"])
        sell_price = float(sell_row["fill_price"])
        pnl_pct = sell_price / buy_price - 1.0 if buy_price > 0 else 0.0
        hold_days = (sell_row["date"] - buy_row["date"]).days
        exit_reason = str(sell_row.get("reason_code", ""))
        buy_year = buy_row["date"].year

        if 2016 <= buy_year <= 2018:
            periods_trades["2016-2018"].append({"pnl_pct": pnl_pct, "hold": hold_days, "exit": exit_reason})
        elif 2024 <= buy_year <= 2026:
            periods_trades["2024-2026"].append({"pnl_pct": pnl_pct, "hold": hold_days, "exit": exit_reason})

    result = {}
    for period, trades in periods_trades.items():
        if not trades:
            result[period] = {"n": 0, "wr": 0, "avg_ret": 0, "avg_hold": 0}
            continue
        pnls = [t["pnl_pct"] for t in trades]
        holds = [t["hold"] for t in trades]
        n = len(trades)
        wins = sum(1 for p in pnls if p > 0)
        result[period] = {
            "n": n,
            "wr": wins / n if n > 0 else 0,
            "avg_ret": sum(pnls) / n,
            "avg_hold": sum(holds) / n,
            "exits": {},
        }
        for t in trades:
            result[period]["exits"][t["exit"]] = result[period]["exits"].get(t["exit"], 0) + 1
    return result


def main() -> None:
    print(f"{'*' * 90}")
    print(f"  BREAKOUT 改进方案验证实验")
    print(f"  Baseline = P3-D champion: bw=20, v2_trend=off, TP=20%, trail=3, stop=1.5, DD=10%/0.5")
    print(f"{'*' * 90}")

    all_results = []
    for exp in EXPERIMENTS:
        cfg_path = _build_config(exp["max_hold"], exp["risk_off"])
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

        # Sub-period analysis
        sub = _analyze_subperiods(result.get("results_dir", ""), label)
        trade_stats = _analyze_trades_summary(result.get("results_dir", ""))

        all_results.append({
            "id": exp["id"], "label": label,
            "cagr": cagr, "mdd": mdd, "sharpe": sharpe, "calmar": calmar, "trades": trades,
            "sub": sub, "trade_stats": trade_stats,
            "diag": result.get("candidate_diag_reason_counts", {}),
        })

    # ── Final ranking ──
    print(f"\n\n{'#' * 90}")
    print(f"  OVERALL RANKING (by Calmar)")
    print(f"{'#' * 90}")
    print(f"  {'Rank':<5} {'Config':<40} {'CAGR':>7} {'MDD':>8} {'Sharpe':>7} {'Calmar':>7} {'Trades':>7}")
    print(f"  {'-' * 83}")

    sorted_results = sorted(all_results, key=lambda r: r.get("calmar", 0), reverse=True)
    for i, r in enumerate(sorted_results):
        marker = " ***" if i == 0 else ""
        print(f"  {i+1:<5} {r['label']:<40} {r['cagr']:>+6.2%} {r['mdd']:>7.2%} {r['sharpe']:>7.2f} {r['calmar']:>7.2f} {r['trades']:>7}{marker}")

    # ── Sub-period comparison ──
    print(f"\n\n{'#' * 90}")
    print(f"  SUB-PERIOD RETURNS")
    print(f"{'#' * 90}")
    print(f"  {'Config':<40} {'16-18':>8} {'19-21':>8} {'22-23':>8} {'24-26':>8}")
    print(f"  {'-' * 76}")
    for r in all_results:
        s = r.get("sub", {})
        r1618 = s.get("2016-2018", {}).get("return", 0)
        r1921 = s.get("2019-2021", {}).get("return", 0)
        r2223 = s.get("2022-2023", {}).get("return", 0)
        r2426 = s.get("2024-2026", {}).get("return", 0)
        print(f"  {r['label']:<40} {r1618:>+7.2%} {r1921:>+7.2%} {r2223:>+7.2%} {r2426:>+7.2%}")

    # ── Sub-period MDD ──
    print(f"\n  {'Config':<40} {'16-18 MDD':>10} {'19-21 MDD':>10} {'22-23 MDD':>10} {'24-26 MDD':>10}")
    print(f"  {'-' * 84}")
    for r in all_results:
        s = r.get("sub", {})
        m1618 = s.get("2016-2018", {}).get("max_dd", 0)
        m1921 = s.get("2019-2021", {}).get("max_dd", 0)
        m2223 = s.get("2022-2023", {}).get("max_dd", 0)
        m2426 = s.get("2024-2026", {}).get("max_dd", 0)
        print(f"  {r['label']:<40} {m1618:>9.2%} {m1921:>9.2%} {m2223:>9.2%} {m2426:>9.2%}")

    # ── Trade quality in 2016-2018 ──
    print(f"\n\n{'#' * 90}")
    print(f"  2016-2018 TRADE QUALITY")
    print(f"{'#' * 90}")
    print(f"  {'Config':<40} {'Trades':>6} {'WR':>6} {'AvgRet':>8} {'AvgHold':>8} {'Exits':>30}")
    print(f"  {'-' * 100}")
    for r in all_results:
        ts = r.get("trade_stats", {}).get("2016-2018", {})
        n = ts.get("n", 0)
        wr = ts.get("wr", 0)
        avg_ret = ts.get("avg_ret", 0)
        avg_hold = ts.get("avg_hold", 0)
        exits = ts.get("exits", {})
        exit_str = ", ".join(f"{k}={v}" for k, v in sorted(exits.items()))
        print(f"  {r['label']:<40} {n:>6} {wr:>5.0%} {avg_ret:>+7.2%} {avg_hold:>7.0f}d {exit_str:>30}")

    # ── 2024-2026 trade quality for comparison ──
    print(f"\n  2024-2026 TRADE QUALITY")
    print(f"  {'Config':<40} {'Trades':>6} {'WR':>6} {'AvgRet':>8} {'AvgHold':>8}")
    print(f"  {'-' * 70}")
    for r in all_results:
        ts = r.get("trade_stats", {}).get("2024-2026", {})
        n = ts.get("n", 0)
        wr = ts.get("wr", 0)
        avg_ret = ts.get("avg_ret", 0)
        avg_hold = ts.get("avg_hold", 0)
        print(f"  {r['label']:<40} {n:>6} {wr:>5.0%} {avg_ret:>+7.2%} {avg_hold:>7.0f}d")

    print(f"\n{'#' * 90}")
    print(f"  DONE")
    print(f"{'#' * 90}")


if __name__ == "__main__":
    main()
