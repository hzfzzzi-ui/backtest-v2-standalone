"""Breakout 策略分期诊断：2016-2018 vs 2024+ 为什么跟随度不同？

Usage:
  python backend/scripts/run_breakout_diagnostic.py
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import numpy as np
import pandas as pd

from backend.core.tools.experiment_runner import run_experiment


def _build_champion_config() -> str:
    import tempfile
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
            "max_hold_days": 0, "min_hold_days": 5, "cooldown_days": 5,
            "momentum_top_pct": 0.0, "enable_sector_gate": False,
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


COMMON_OVERRIDES = {
    "universe_mode": "HS300_ZZ500", "start_date": "2016-03-01", "end_date": "2026-03-01",
    "benchmark": "000300.SH", "initial_capital": 1_000_000, "max_positions": 10,
    "base_order_value": 0, "fast_mode": True, "price_adj": "hfq",
    "enable_strength_rank": False, "enable_multifactor_rank": False, "momentum_top_pct": 0.0,
}


def _run_full() -> dict:
    cfg_path = _build_champion_config()
    t0 = time.perf_counter()
    def progress(pct: int, msg: str) -> None:
        print(f"  [{pct:3d}%] {msg}  ({time.perf_counter() - t0:.1f}s)")
    result = run_experiment(cfg_path, preset="single", overrides=COMMON_OVERRIDES, progress_hook=progress)
    Path(cfg_path).unlink(missing_ok=True)
    print(f"\n  Full run: CAGR={result['cagr']:+.2%}, MDD={result['max_drawdown']:.2%}, Trades={result['trades']}")
    return result


# ── Analysis ──

def _analyze_daily(daily_csv: str) -> None:
    df = pd.read_csv(daily_csv, parse_dates=["date"])
    df["year"] = df["date"].dt.year

    print(f"\n{'=' * 90}")
    print(f"  DAILY PORTFOLIO ANALYSIS")
    print(f"{'=' * 90}")

    # Yearly NAV performance
    print(f"\n  {'Year':<6} {'Days':>5} {'Return':>8} {'MaxDD':>8} {'AvgPos':>7} {'SignalDays':>10} {'AvgSignals':>10} {'DDState':>8}")
    print(f"  {'-' * 68}")

    for year, grp in df.groupby("year"):
        grp = grp.sort_values("date").reset_index(drop=True)
        nav_start = float(grp["nav"].iloc[0])
        nav_end = float(grp["nav"].iloc[-1])
        ret = nav_end / nav_start - 1.0 if nav_start > 0 else 0.0
        cummax = grp["nav"].cummax()
        dd = (grp["nav"] - cummax) / cummax
        max_dd = float(dd.min())
        avg_pos = float(grp["positions_count"].mean()) if "positions_count" in grp.columns else 0.0

        # Signal funnel
        raw_sig_col = "raw_buy_signal_count"
        if raw_sig_col in grp.columns:
            sig_days = int((grp[raw_sig_col] > 0).sum())
            avg_sig = float(grp[raw_sig_col].mean())
        else:
            sig_days = 0
            avg_sig = 0.0

        # DD state distribution
        dd_state_col = "dd_state"
        dd_reduced = ""
        if dd_state_col in grp.columns:
            dd_counts = grp[dd_state_col].value_counts()
            reduced = int(dd_counts.get("REDUCED", 0))
            dd_reduced = f"{reduced}d" if reduced > 0 else "0d"

        print(f"  {year:<6} {len(grp):>5} {ret:>+7.2%} {max_dd:>7.2%} {avg_pos:>7.1f} {sig_days:>10} {avg_sig:>9.2f} {dd_reduced:>8}")

    # Signal funnel deep dive
    funnel_cols = ["raw_buy_signal_count", "buy_candidate_count", "after_held_filter_count",
                   "after_slot_filter_count", "after_cash_lot_count"]
    available_funnel = [c for c in funnel_cols if c in df.columns]

    if available_funnel:
        print(f"\n  SIGNAL FUNNEL BY PERIOD")
        periods = [
            ("2016-2018", "2016-01-01", "2018-12-31"),
            ("2019-2021", "2019-01-01", "2021-12-31"),
            ("2022-2023", "2022-01-01", "2023-12-31"),
            ("2024-2026", "2024-01-01", "2026-12-31"),
        ]
        header = f"  {'Period':<12}"
        for c in available_funnel:
            short = c.replace("_count", "").replace("raw_buy_signal", "raw_sig").replace("buy_candidate", "cand").replace("after_held_filter", "post_held").replace("after_slot_filter", "post_slot").replace("after_cash_lot", "filled")
            header += f" {short:>10}"
        header += f" {'sig_days':>9} {'avg_pos':>8}"
        print(header)
        print(f"  {'-' * (12 + 10 * len(available_funnel) + 20)}")

        for label, start, end in periods:
            mask = (df["date"] >= start) & (df["date"] <= end)
            grp = df[mask]
            if grp.empty:
                continue
            row = f"  {label:<12}"
            for c in available_funnel:
                row += f" {int(grp[c].sum()):>10}"
            sig_days = int((grp["raw_buy_signal_count"] > 0).sum()) if "raw_buy_signal_count" in grp.columns else 0
            avg_pos = float(grp["positions_count"].mean()) if "positions_count" in grp.columns else 0.0
            row += f" {sig_days:>9} {avg_pos:>7.1f}"
            print(row)


def _reconstruct_roundtrips(trades_csv: str) -> pd.DataFrame:
    """Reconstruct round-trip trades from BUY/SELL transaction log."""
    df = pd.read_csv(trades_csv, parse_dates=["date"])
    buys = df[df["side"] == "BUY"].copy()
    sells = df[df["side"] == "SELL"].copy()

    # Match: for each SELL, find the most recent preceding BUY of the same symbol
    roundtrips = []
    buy_records: dict[str, list] = {}
    for _, row in buys.iterrows():
        sym = str(row["symbol"])
        buy_records.setdefault(sym, []).append(row)

    for _, sell_row in sells.sort_values("date").iterrows():
        sym = str(sell_row["symbol"])
        if sym not in buy_records or not buy_records[sym]:
            continue
        buy_row = buy_records[sym].pop(0)
        buy_price = float(buy_row["fill_price"])
        sell_price = float(sell_row["fill_price"])
        qty = int(sell_row["qty"])
        pnl = (sell_price - buy_price) * qty
        pnl_pct = (sell_price / buy_price - 1.0) if buy_price > 0 else 0.0
        hold_days = (sell_row["date"] - buy_row["date"]).days

        # Parse meta for regime_on
        meta = {}
        try:
            meta = json.loads(str(buy_row.get("meta_json", "{}")))
        except Exception:
            pass

        roundtrips.append({
            "symbol": sym,
            "buy_date": buy_row["date"],
            "sell_date": sell_row["date"],
            "buy_price": buy_price,
            "sell_price": sell_price,
            "qty": qty,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "hold_days": hold_days,
            "exit_reason": str(sell_row.get("reason_code", "")),
            "regime_on": bool(meta.get("regime_on", True)),
        })

    return pd.DataFrame(roundtrips)


def _analyze_trades(trades_csv: str) -> None:
    rt = _reconstruct_roundtrips(trades_csv)
    if rt.empty:
        print(f"\n  No round-trip trades reconstructed")
        return

    rt["buy_year"] = rt["buy_date"].dt.year

    print(f"\n{'=' * 90}")
    print(f"  ROUND-TRIP TRADE ANALYSIS ({len(rt)} trades)")
    print(f"{'=' * 90}")

    # Per-year
    print(f"\n  {'Year':<6} {'Trades':>6} {'WinRate':>8} {'AvgPnL':>10} {'AvgPnL%':>9} {'AvgHold':>8} {'TotalPnL':>12}")
    print(f"  {'-' * 63}")
    for year, grp in rt.groupby("buy_year"):
        n = len(grp)
        wins = int((grp["pnl"] > 0).sum())
        wr = wins / n if n > 0 else 0.0
        print(f"  {year:<6} {n:>6} {wr:>7.1%} {grp['pnl'].mean():>10,.0f} {grp['pnl_pct'].mean():>+8.2%} {grp['hold_days'].mean():>7.1f}d {grp['pnl'].sum():>12,.0f}")

    # Exit reason by period
    print(f"\n  EXIT REASON DISTRIBUTION BY PERIOD")
    periods = [
        ("2016-2018", "2016-01-01", "2018-12-31"),
        ("2019-2021", "2019-01-01", "2021-12-31"),
        ("2022-2023", "2022-01-01", "2023-12-31"),
        ("2024-2026", "2024-01-01", "2026-12-31"),
    ]
    for label, start, end in periods:
        mask = (rt["buy_date"] >= start) & (rt["buy_date"] <= end)
        grp = rt[mask]
        if grp.empty:
            continue
        print(f"\n  {label} ({len(grp)} trades, WR={int((grp['pnl'] > 0).sum()) / len(grp):.0%}, avgPnL%={grp['pnl_pct'].mean():+.2%}):")
        for reason, sub in grp.groupby("exit_reason"):
            n = len(sub)
            pct = n / len(grp)
            avg_pnl = sub["pnl_pct"].mean()
            wr = int((sub["pnl"] > 0).sum()) / n if n > 0 else 0.0
            avg_hold = sub["hold_days"].mean()
            print(f"    {str(reason):<35s} {n:>4} ({pct:>5.1%})  avgRet={avg_pnl:>+7.2%}  WR={wr:.0%}  hold={avg_hold:.0f}d")

    # Direct comparison 2016-2018 vs 2024-2026
    print(f"\n  TRADE QUALITY COMPARISON")
    print(f"  {'Metric':<25} {'2016-2018':>12} {'2024-2026':>12}")
    print(f"  {'-' * 52}")

    for label, start, end in [("2016-2018", "2016-01-01", "2018-12-31"), ("2024-2026", "2024-01-01", "2026-12-31")]:
        mask = (rt["buy_date"] >= start) & (rt["buy_date"] <= end)
        grp = rt[mask]
        if grp.empty:
            continue
        n = len(grp)
        wins = int((grp["pnl"] > 0).sum())
        wr = wins / n if n > 0 else 0.0
        print(f"\n  --- {label} ---")
        print(f"  {'Trades':<25} {n:>12}")
        print(f"  {'Win Rate':<25} {wr:>11.1%}")
        print(f"  {'Avg Return':<25} {grp['pnl_pct'].mean():>+11.2%}")
        print(f"  {'Median Return':<25} {grp['pnl_pct'].median():>+11.2%}")
        print(f"  {'Best Trade':<25} {grp['pnl_pct'].max():>+11.2%}")
        print(f"  {'Worst Trade':<25} {grp['pnl_pct'].min():>+11.2%}")
        print(f"  {'Avg Hold Days':<25} {grp['hold_days'].mean():>10.1f}d")
        print(f"  {'Total PnL':<25} {grp['pnl'].sum():>12,.0f}")
        # Regime distribution
        regime_on = int(grp["regime_on"].sum())
        print(f"  {'Regime ON trades':<25} {regime_on:>12} ({regime_on / n:.0%})")

    # Top winners and losers in each period
    for label, start, end in [("2016-2018", "2016-01-01", "2018-12-31"), ("2024-2026", "2024-01-01", "2026-12-31")]:
        mask = (rt["buy_date"] >= start) & (rt["buy_date"] <= end)
        grp = rt[mask].copy()
        if grp.empty:
            continue
        print(f"\n  TOP 5 WINNERS {label}:")
        top5 = grp.nlargest(5, "pnl_pct")
        for _, row in top5.iterrows():
            print(f"    {row['symbol']:<15s} {row['buy_date'].strftime('%Y-%m-%d')} -> {row['sell_date'].strftime('%Y-%m-%d')} ret={row['pnl_pct']:+.1%} hold={row['hold_days']}d exit={row['exit_reason']}")
        print(f"\n  TOP 5 LOSERS {label}:")
        bot5 = grp.nsmallest(5, "pnl_pct")
        for _, row in bot5.iterrows():
            print(f"    {row['symbol']:<15s} {row['buy_date'].strftime('%Y-%m-%d')} -> {row['sell_date'].strftime('%Y-%m-%d')} ret={row['pnl_pct']:+.1%} hold={row['hold_days']}d exit={row['exit_reason']}")


def _analyze_benchmark_regime(daily_csv: str) -> None:
    """Load benchmark data separately to compare regimes."""
    # We can infer regime from the daily data and the benchmark
    # For now, analyze positions and DD state
    df = pd.read_csv(daily_csv, parse_dates=["date"])

    print(f"\n{'=' * 90}")
    print(f"  POSITION & REGIME ANALYSIS")
    print(f"{'=' * 90}")

    # Monthly position count and DD state
    df["ym"] = df["date"].dt.to_period("M")
    monthly = df.groupby("ym").agg(
        avg_pos=("positions_count", "mean"),
        max_pos=("positions_count", "max"),
        avg_raw_sig=("raw_buy_signal_count", "mean") if "raw_buy_signal_count" in df.columns else ("positions_count", "mean"),
        days=("date", "count"),
    ).reset_index()

    # Show quarters with no positions
    print(f"\n  QUARTERS WITH ZERO POSITIONS:")
    df["yq"] = df["date"].dt.to_period("Q")
    quarterly = df.groupby("yq").agg(
        avg_pos=("positions_count", "mean"),
        max_pos=("positions_count", "max"),
        days=("date", "count"),
    ).reset_index()
    zero_quarters = quarterly[quarterly["max_pos"] == 0]
    for _, row in zero_quarters.iterrows():
        print(f"    {row['yq']}  (max_pos=0, {row['days']} days)")

    # Signal density heatmap (quarterly)
    if "raw_buy_signal_count" in df.columns:
        print(f"\n  QUARTERLY SIGNAL DENSITY:")
        print(f"  {'Quarter':<10} {'Days':>5} {'SigDays':>8} {'TotalSig':>9} {'AvgSig':>8} {'AvgPos':>7} {'MaxPos':>7}")
        print(f"  {'-' * 58}")
        for yq, grp in df.groupby("yq"):
            sig_days = int((grp["raw_buy_signal_count"] > 0).sum())
            total_sig = int(grp["raw_buy_signal_count"].sum())
            avg_sig = grp["raw_buy_signal_count"].mean()
            avg_pos = grp["positions_count"].mean()
            max_pos = int(grp["positions_count"].max())
            print(f"  {str(yq):<10} {len(grp):>5} {sig_days:>8} {total_sig:>9} {avg_sig:>7.2f} {avg_pos:>7.1f} {max_pos:>7}")

    # DD state timeline
    if "dd_state" in df.columns:
        print(f"\n  DD STATE DISTRIBUTION BY YEAR:")
        for year, grp in df.groupby(df["date"].dt.year):
            counts = grp["dd_state"].value_counts()
            parts = ", ".join(f"{k}={v}" for k, v in counts.items())
            print(f"    {year}: {parts}")


def main() -> None:
    print(f"{'*' * 90}")
    print(f"  BREAKOUT P3-D 分期诊断")
    print(f"  配置: bw=20, v2_trend=off, regime_ma=120")
    print(f"  退出: TP=20%, trail=3, stop=1.5, LOW10=on, DD=10%/0.5")
    print(f"  期间: 2016-03-01 ~ 2026-03-01, CSI800")
    print(f"{'*' * 90}")

    t0 = time.perf_counter()
    result = _run_full()
    elapsed = time.perf_counter() - t0
    print(f"\n  Run elapsed: {elapsed:.1f}s")

    results_dir = result.get("results_dir", "")
    if not results_dir:
        print("  ERROR: no results_dir")
        return
    rdir = Path(results_dir)

    # 1. Daily analysis
    daily_csv = rdir / "portfolio_daily.csv"
    if daily_csv.exists():
        _analyze_daily(str(daily_csv))
        _analyze_benchmark_regime(str(daily_csv))

    # 2. Trade analysis
    trades_csv = rdir / "portfolio_trades.csv"
    if trades_csv.exists():
        _analyze_trades(str(trades_csv))

    # 3. Engine counters
    print(f"\n{'=' * 90}")
    print(f"  ENGINE COUNTERS")
    print(f"{'=' * 90}")
    diag = result.get("candidate_diag_reason_counts", {})
    if diag:
        for k, v in sorted(diag.items(), key=lambda x: -int(x[1])):
            print(f"    {k:<40s} {v:>6}")
    print(f"\n  exit_take_profit:  {result.get('exit_take_profit_count', 0)}")
    print(f"  exit_atr_stop:     {result.get('exit_atr_stop_count', 0)}")
    print(f"  exit_atr_trail:    {result.get('exit_atr_trail_count', 0)}")
    print(f"  exit_signal:       {result.get('exit_signal_count', 0)}")
    print(f"\n  DONE. Results in: {results_dir}")


if __name__ == "__main__":
    main()
