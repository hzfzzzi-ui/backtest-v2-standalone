"""A/B Compare: EMA Cross Champion vs Breakout Trend on CSI800, 10yr."""
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

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from backend.core.tools.experiment_runner import run_experiment


def _build_config(strategy_block: dict, exit_block: dict, risk_budget: dict, sizing: dict) -> str:
    """Load base config, merge strategy/exit, write to temp file, return path."""
    base_path = _root / "backend" / "configs" / "pams_cn_pg.json"
    base = json.loads(base_path.read_text(encoding="utf-8-sig"))
    base["universe"] = {
        **base.get("universe", {}),
        "start": "2016-03-01",
        "end": "2026-03-01",
        "benchmark": "000300.SH",
        "symbols": [],
    }
    base["initial_capital"] = 1_000_000
    base["strategy"] = strategy_block
    base["exit"] = exit_block
    base["sizing"] = sizing
    base["risk_budget"] = risk_budget
    base["market_filter"] = {"enabled": False}
    base["benchmark_regime"] = {"enabled": False}
    base["breadth"] = {"enabled": False}
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(base, tmp, ensure_ascii=False, indent=2)
    tmp.close()
    return tmp.name


def _run_one(label: str, config_path: str, overrides: dict) -> dict:
    t0 = time.perf_counter()
    print(f"\n{'=' * 72}")
    print(f"  {label}")
    print(f"{'=' * 72}")
    for k, v in sorted(overrides.items()):
        print(f"    {k}: {v}")
    print()

    def progress(pct: int, msg: str) -> None:
        elapsed = time.perf_counter() - t0
        print(f"  [{pct:3d}%] {msg}  ({elapsed:.1f}s)")

    try:
        result = run_experiment(config_path, preset="single", overrides=overrides, progress_hook=progress)
    except Exception as e:
        print(f"\n  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {}
    finally:
        Path(config_path).unlink(missing_ok=True)

    elapsed = time.perf_counter() - t0

    # Print summary
    cagr = result.get("cagr", 0)
    total_ret = result.get("total_return", 0)
    mdd = result.get("max_drawdown", 0)
    sharpe = result.get("sharpe", 0)
    calmar = result.get("calmar", 0)
    trades = result.get("trades", 0)
    avg_pos = result.get("avg_positions", 0)
    diag = result.get("candidate_diag_reason_counts", {})

    print(f"\n  CAGR:            {cagr:+.2%}")
    print(f"  Total Return:    {total_ret:+.2%}")
    print(f"  Max Drawdown:    {mdd:.2%}")
    print(f"  Sharpe:          {sharpe:.2f}")
    print(f"  Calmar:          {calmar:.2f}")
    print(f"  Trades:          {trades}")
    print(f"  Avg Positions:   {avg_pos:.1f}")
    print(f"  Elapsed:         {elapsed:.1f}s")
    if diag:
        print(f"  Exit breakdown:")
        for k, v in sorted(diag.items(), key=lambda x: -int(x[1])):
            print(f"    {k:35s} {v:>6}")
    print(f"{'=' * 72}")

    return {
        "label": label, "cagr": cagr, "total_return": total_ret,
        "max_drawdown": mdd, "sharpe": sharpe, "calmar": calmar,
        "trades": trades, "avg_positions": avg_pos, "diag": diag,
    }


def main() -> None:
    results = []

    # ── A: EMA Cross Champion (G5) on CSI800 ──
    cfg_a = _build_config(
        strategy_block={
            "name": "ema_cross",
            "fast": 8,
            "slow": 25,
            "order_size": 1000,
            "params": {
                "fast": 8,
                "slow": 25,
                "regime_ma": 60,
                "enable_atr_stop": True,
                "atr_stop_k": 2.0,
                "enable_atr_trail": True,
                "atr_trail_k": 6.0,
                "enable_take_profit": True,
                "take_profit_mode": "pct",
                "take_profit_pct": 0.30,
                "enable_fixed_stop_loss": False,
                "enable_ma20_exit": False,
                "enable_low10_exit": False,
                "max_hold_days": 0,
                "min_hold_days": 5,
                "cooldown_days": 5,
            },
        },
        exit_block={
            "enable_atr_stop": True,
            "atr_stop_k": 2.0,
            "enable_atr_trail": True,
            "atr_trail_k": 6.0,
            "enable_take_profit": True,
            "take_profit_mode": "pct",
            "take_profit_pct": 0.30,
            "enable_fixed_stop_loss": False,
        },
        risk_budget={"enabled": False},
        sizing={"order_value": 0, "lot_size": 100, "weight_mode": "equal", "min_positions": 10},
    )
    ov_a = {
        "universe_mode": "HS300_ZZ500",
        "start_date": "2016-03-01",
        "end_date": "2026-03-01",
        "benchmark": "000300.SH",
        "initial_capital": 1_000_000,
        "max_positions": 10,
        "base_order_value": 0,
        "fast_mode": True,
        "price_adj": "hfq",
        "enable_strength_rank": False,
        "enable_multifactor_rank": False,
        "momentum_top_pct": 0.0,
    }
    results.append(_run_one("A: EMA Cross Champion (8/25) — CSI800", cfg_a, ov_a))

    # ── B: Breakout Trend on CSI800 (Turtle exits, no TP cap) ──
    cfg_b = _build_config(
        strategy_block={
            "name": "breakout_trend",
            "order_size": 1000,
            "params": {
                "breakout_window": 20,
                "min_price": 5.0,
                "regime_ma": 120,
                "enable_v2_trend_filter": True,
                "v2_trend_short_ma": 20,
                "v2_trend_long_ma": 60,
                "enable_atr_stop": True,
                "atr_stop_k": 2.0,
                "enable_atr_trail": True,
                "atr_trail_k": 3.0,
                "enable_take_profit": False,
                "enable_fixed_stop_loss": False,
                "enable_ma20_exit": False,
                "enable_low10_exit": True,
                "max_hold_days": 0,
                "min_hold_days": 5,
                "cooldown_days": 5,
                "momentum_top_pct": 0.0,
                "enable_sector_gate": False,
            },
        },
        exit_block={
            "enable_atr_stop": True,
            "atr_stop_k": 2.0,
            "enable_atr_trail": True,
            "atr_trail_k": 3.0,
            "enable_take_profit": False,
            "enable_fixed_stop_loss": False,
            "enable_low10_exit": True,
        },
        risk_budget={"enabled": False},
        sizing={"order_value": 0, "lot_size": 100, "weight_mode": "equal", "min_positions": 10},
    )
    ov_b = {
        "universe_mode": "HS300_ZZ500",
        "start_date": "2016-03-01",
        "end_date": "2026-03-01",
        "benchmark": "000300.SH",
        "initial_capital": 1_000_000,
        "max_positions": 10,
        "base_order_value": 0,
        "fast_mode": True,
        "price_adj": "hfq",
        "enable_strength_rank": False,
        "enable_multifactor_rank": False,
        "momentum_top_pct": 0.0,
    }
    results.append(_run_one("B: Breakout 20d (Turtle) — CSI800", cfg_b, ov_b))

    # ── Comparison ──
    print(f"\n{'=' * 72}")
    print("  A/B COMPARISON")
    print(f"{'=' * 72}")
    header = f"  {'Metric':<20}"
    for r in results:
        header += f" {'[' + r.get('label', '?')[:30] + ']':>35}"
    print(header)
    print("  " + "-" * 70)
    for key, fmt in [
        ("cagr", "{:+.2%}"), ("total_return", "{:+.2%}"), ("max_drawdown", "{:.2%}"),
        ("sharpe", "{:.2f}"), ("calmar", "{:.2f}"), ("trades", "{}"), ("avg_positions", "{:.1f}"),
    ]:
        row = f"  {key:<20}"
        for r in results:
            row += f" {fmt.format(r.get(key, 0)):>35}"
        print(row)
    print(f"{'=' * 72}")


if __name__ == "__main__":
    main()
