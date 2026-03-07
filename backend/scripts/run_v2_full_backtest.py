"""V2 Alpha Strategy full pipeline backtest - ALL_A, 10yr, all stages enabled."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import time
from pathlib import Path

# Fix Windows GBK encoding
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure repo root is on sys.path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from backend.core.tools.experiment_runner import run_experiment


def main() -> None:
    # Load base config (has db, schema_mapping, data_source, etc.)
    base_path = _root / "backend" / "configs" / "pams_cn_pg.json"
    base = json.loads(base_path.read_text(encoding="utf-8-sig"))

    # Override all V2 settings directly into the config dict
    base["universe"] = {
        **base.get("universe", {}),
        "start": "2016-03-01",
        "end": "2026-03-01",
        "benchmark": "000300.SH",
        "symbols": [],  # will be resolved by universe_mode
    }
    base["initial_capital"] = 1_000_000
    base["strategy"] = {
        "name": "breakout_trend",
        "order_size": 1000,
        "params": {
            # S4: Breakout Entry
            "breakout_window": 20,
            # S1: Universe Price Filter
            "min_price": 5.0,
            # S2: Market Regime
            "regime_ma": 120,
            # S3: Stock Trend Filter
            "enable_v2_trend_filter": True,
            "v2_trend_short_ma": 20,
            "v2_trend_long_ma": 60,
            # S7: Exit Rules
            "enable_atr_stop": True,
            "atr_stop_k": 2.0,
            "enable_atr_trail": True,
            "atr_trail_k": 3.0,
            "enable_take_profit": True,
            "take_profit_mode": "pct",
            "take_profit_pct": 0.30,
            "enable_fixed_stop_loss": False,
            "fixed_stop_loss_pct": 0.05,
            "enable_ma20_exit": False,
            "enable_low10_exit": True,
            # Hold/Cooldown
            "max_hold_days": 0,
            "min_hold_days": 5,
            "cooldown_days": 5,
            # S5: Momentum Ranking
            "momentum_top_pct": 0.10,
            # S6: Sector Gate
            "enable_sector_gate": True,
            "sector_rank_window": 60,
            "sector_top_pct": 0.30,
        },
    }
    base["exit"] = {
        "enable_atr_stop": True,
        "atr_stop_k": 2.0,
        "enable_atr_trail": True,
        "atr_trail_k": 3.0,
        "enable_take_profit": True,
        "take_profit_mode": "pct",
        "take_profit_pct": 0.30,
        "enable_fixed_stop_loss": False,
        "fixed_stop_loss_pct": 0.05,
        "enable_ma20_exit": False,
        "enable_low10_exit": True,
    }
    base["sizing"] = {
        "order_value": 0,
        "lot_size": 100,
        "weight_mode": "equal",
        "min_positions": 10,
    }
    # S8: DD Risk Control (DD>10% → reduce positions)
    base["risk_budget"] = {
        "enabled": True,
        "dd_reduce_pct": 0.10,
        "dd_reduce_scale": 0.5,
        "atr_stop_k": 2.0,
    }
    base["market_filter"] = {"enabled": False}
    base["benchmark_regime"] = {"enabled": False}
    base["breadth"] = {"enabled": False}

    # Write merged config to temp file
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(base, tmp, ensure_ascii=False, indent=2)
    tmp.close()
    tmp_path = tmp.name

    overrides: dict = {
        "universe_mode": "ALL_A",
        "start_date": "2016-03-01",
        "end_date": "2026-03-01",
        "benchmark": "000300.SH",
        "initial_capital": 1_000_000,
        "max_positions": 15,
        "base_order_value": 0,
        "fast_mode": True,
        "price_adj": "hfq",
        "enable_strength_rank": False,
        "enable_multifactor_rank": False,
        "momentum_top_pct": 0.0,
    }

    t0 = time.perf_counter()
    print("=" * 72)
    print("  V2 Alpha Strategy - Full Pipeline Backtest")
    print("=" * 72)
    print(f"  Universe:   ALL_A")
    print(f"  Period:     2016-03-01 -> 2026-03-01 (10 yr)")
    print(f"  Strategy:   breakout_trend (20-day high breakout)")
    print(f"  Capital:    1,000,000")
    print(f"  MaxPos:     15")
    print()
    print("  V2 Stages enabled:")
    print("    S1 min_price=5       S2 regime_ma=120       S3 trend_filter(20/60)")
    print("    S4 breakout(20)      S5 momentum_top=10%    S6 sector_gate(30%)")
    print("    S7 ATR+trail+TP30%+LOW10exit+min5/cool5  (Turtle style)")
    print("    S8 DD>10% reduce 50%")
    print("    S9 equal weight, min_pos=10")
    print("=" * 72)
    print()

    def progress(pct: int, msg: str) -> None:
        elapsed = time.perf_counter() - t0
        print(f"  [{pct:3d}%] {msg}  ({elapsed:.1f}s)")

    try:
        result = run_experiment(tmp_path, preset="single", overrides=overrides, progress_hook=progress)
    except Exception as e:
        print(f"\n  ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    elapsed = time.perf_counter() - t0

    # ── Stage-by-stage diagnostics ──
    print()
    print("=" * 72)
    print("  STAGE-BY-STAGE DIAGNOSTICS")
    print("=" * 72)

    diag = result.get("candidate_diag_reason_counts", {})
    uni_meta = result.get("universe_meta", {})

    # S1: Universe
    print(f"\n  S1 Universe Price Filter")
    print(f"     Symbols loaded:       {uni_meta.get('resolved_count', '?')}")
    print(f"     Universe mode:        {uni_meta.get('mode', '?')}")
    print(f"     Min price block:      {diag.get('BLOCK_MIN_PRICE', 0)}")

    # S2: Market Regime
    print(f"\n  S2 Market Regime (MA120)")
    print(f"     Risk-off block:       {diag.get('BLOCK_RISK_OFF', diag.get('BLOCK_REGIME_OFF', 0))}")
    mf_bull = result.get("market_filter_bull_days", 0)
    mf_bear = result.get("market_filter_bear_days", 0)
    print(f"     Market filter bull:   {mf_bull} days")
    print(f"     Market filter bear:   {mf_bear} days")

    # S3: Stock Trend Filter
    print(f"\n  S3 Stock Trend Filter (MA20>MA60)")
    trend_block = diag.get("BLOCK_TREND_FILTER", diag.get("BLOCK_V2_TREND", diag.get("BLOCK_TREND", 0)))
    print(f"     Trend block:          {trend_block}")
    print(f"     Slope block:          {result.get('trend_slope_block_count', 0)}")

    # S4: Breakout Entry
    print(f"\n  S4 Breakout Entry (20-day high)")
    cross_not_met = diag.get("BLOCK_CROSS_NOT_MET", 0)
    print(f"     Cross not met:        {cross_not_met}")
    print(f"     Entry buffer block:   {diag.get('BLOCK_ENTRY_BUFFER', 0)}")
    print(f"     No slots:             {diag.get('BLOCK_NO_SLOTS', 0)}")

    # S5: Momentum Ranking
    print(f"\n  S5 Momentum Ranking (top 10%)")
    print(f"     NOT_IN_TOPK reject:   {diag.get('NOT_IN_TOPK', 0)}")

    # S6: Industry Trend Gate
    print(f"\n  S6 Industry Trend Gate (top 30%)")
    print(f"     Sector cold block:    {diag.get('BLOCK_SECTOR_COLD', 0)}")

    # S7: Exit Rules
    print(f"\n  S7 Exit Rules")
    print(f"     ATR Stop Loss:        {result.get('exit_atr_stop_count', diag.get('ATR_STOP_LOSS', 0))}")
    print(f"     ATR Trail Exit:       {result.get('exit_atr_trail_count', diag.get('ATR_TRAIL_EXIT', 0))}")
    print(f"     Take Profit (30%):    {result.get('exit_take_profit_count', diag.get('TAKE_PROFIT', 0))}")
    print(f"     Fixed Stop (5%):      {result.get('exit_fixed_stop_count', diag.get('FIXED_STOP_LOSS', 0))}")
    print(f"     Time Exit:            {result.get('exit_time_exit_count', diag.get('TIME_EXIT', 0))}")
    print(f"     Signal Exit:          {result.get('exit_signal_count', diag.get('SIGNAL_EXIT', 0))}")
    print(f"     MA20 Exit:            {diag.get('TREND_EXIT_MA20', 0)}")
    print(f"     LOW10 Exit:           {diag.get('TREND_EXIT_LOW10', 0)}")
    print(f"     ST block:             {result.get('st_block_count', 0)}")

    # S8: DD Risk Control
    print(f"\n  S8 DD Risk Control (DD>10% -> reduce 50%)")
    print(f"     DD reduced days:      {diag.get('REDUCED', 0)}")

    # S9: Portfolio Sizing
    print(f"\n  S9 Portfolio Sizing")
    print(f"     Weight mode:          equal")
    print(f"     Min positions:        10")
    print(f"     Avg positions:        {result.get('avg_positions', 0):.1f}")
    print(f"     Lot reject:           {diag.get('SKIP_LOT_TOO_SMALL', 0)}")
    print(f"     Cash reject:          {diag.get('SKIP_CASH_INSUFFICIENT', 0)}")

    # ── Final Summary ──
    print()
    print("=" * 72)
    print("  BACKTEST SUMMARY")
    print("=" * 72)
    cagr = result.get("cagr", 0)
    total_ret = result.get("total_return", 0)
    mdd = result.get("max_drawdown", 0)
    sharpe = result.get("sharpe", 0)
    calmar = result.get("calmar", 0)
    trades = result.get("trades", 0)
    turnover = result.get("turnover", 0)

    print(f"     CAGR:                 {cagr:+.2%}")
    print(f"     Total Return:         {total_ret:+.2%}")
    print(f"     Max Drawdown:         {mdd:.2%}")
    print(f"     Sharpe:               {sharpe:.2f}")
    print(f"     Calmar:               {calmar:.2f}")
    print(f"     Trades:               {trades}")
    print(f"     Avg Turnover:         {turnover:.4f}")
    print(f"     Avg Positions:        {result.get('avg_positions', 0):.1f}")
    print(f"     Elapsed:              {elapsed:.1f}s")
    print(f"     Results:              {result.get('results_dir', '')}")
    print("=" * 72)

    # Dump full diag counts
    if diag:
        print("\n  Full diag_reason_counts:")
        for k, v in sorted(diag.items(), key=lambda x: -int(x[1])):
            print(f"     {k:40s} {v:>8}")

    print()


if __name__ == "__main__":
    main()
