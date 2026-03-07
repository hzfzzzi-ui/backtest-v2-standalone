"""Breakout Trend 3-phase parameter sweep on true-PIT CSI800.

Phase 1: Exit optimization  (TP + trail width + LOW10)
Phase 2: Entry relaxation   (breakout window + trend filter + regime MA)
Phase 3: Risk control        (ATR stop + DD circuit breaker)

Usage (in Docker):
  python backend/scripts/run_breakout_sweep.py --phase 1
  python backend/scripts/run_breakout_sweep.py --phase 2 --best-exit P1-C
  python backend/scripts/run_breakout_sweep.py --phase 3 --best-exit P1-C --best-entry P2-B
  python backend/scripts/run_breakout_sweep.py --phase all
"""
from __future__ import annotations

import argparse
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

# ---------------------------------------------------------------------------
# Common overrides (shared across all configs)
# ---------------------------------------------------------------------------
COMMON_OVERRIDES = {
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

# ---------------------------------------------------------------------------
# Config builder
# ---------------------------------------------------------------------------

def _build_config(strategy_params: dict, exit_block: dict, risk_budget: dict) -> str:
    """Build a temp config file from base + strategy/exit overrides."""
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
    base["strategy"] = {
        "name": "breakout_trend",
        "order_size": 1000,
        "params": strategy_params,
    }
    base["exit"] = exit_block
    base["sizing"] = {"order_value": 0, "lot_size": 100, "weight_mode": "equal", "min_positions": 10}
    base["risk_budget"] = risk_budget
    base["market_filter"] = {"enabled": False}
    base["benchmark_regime"] = {"enabled": False}
    base["breadth"] = {"enabled": False}
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(base, tmp, ensure_ascii=False, indent=2)
    tmp.close()
    return tmp.name


def _run_one(label: str, config_path: str) -> dict:
    """Run a single backtest and return metrics."""
    t0 = time.perf_counter()
    print(f"\n{'=' * 72}")
    print(f"  {label}")
    print(f"{'=' * 72}")

    def progress(pct: int, msg: str) -> None:
        elapsed = time.perf_counter() - t0
        print(f"  [{pct:3d}%] {msg}  ({elapsed:.1f}s)")

    try:
        result = run_experiment(config_path, preset="single", overrides=COMMON_OVERRIDES, progress_hook=progress)
    except Exception as e:
        print(f"\n  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"label": label}
    finally:
        Path(config_path).unlink(missing_ok=True)

    elapsed = time.perf_counter() - t0
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
        "trades": trades, "avg_positions": avg_pos, "elapsed": elapsed,
    }


# ---------------------------------------------------------------------------
# Phase definitions
# ---------------------------------------------------------------------------

def _base_strategy_params(
    breakout_window: int = 20,
    regime_ma: int = 120,
    v2_trend: bool = True,
    atr_stop_k: float = 2.0,
    atr_trail_k: float = 3.0,
    enable_tp: bool = False,
    tp_pct: float = 0.0,
    enable_low10: bool = True,
    min_hold: int = 5,
    cooldown: int = 5,
) -> dict:
    return {
        "breakout_window": breakout_window,
        "min_price": 5.0,
        "regime_ma": regime_ma,
        "enable_v2_trend_filter": v2_trend,
        "v2_trend_short_ma": 20,
        "v2_trend_long_ma": 60,
        "enable_atr_stop": True,
        "atr_stop_k": atr_stop_k,
        "enable_atr_trail": True,
        "atr_trail_k": atr_trail_k,
        "enable_take_profit": enable_tp,
        "take_profit_mode": "pct",
        "take_profit_pct": tp_pct,
        "enable_fixed_stop_loss": False,
        "enable_ma20_exit": False,
        "enable_low10_exit": enable_low10,
        "max_hold_days": 0,
        "min_hold_days": min_hold,
        "cooldown_days": cooldown,
        "momentum_top_pct": 0.0,
        "enable_sector_gate": False,
    }


def _exit_block(
    atr_stop_k: float = 2.0,
    atr_trail_k: float = 3.0,
    enable_tp: bool = False,
    tp_pct: float = 0.0,
    enable_low10: bool = True,
) -> dict:
    return {
        "enable_atr_stop": True,
        "atr_stop_k": atr_stop_k,
        "enable_atr_trail": True,
        "atr_trail_k": atr_trail_k,
        "enable_take_profit": enable_tp,
        "take_profit_mode": "pct",
        "take_profit_pct": tp_pct,
        "enable_fixed_stop_loss": False,
        "enable_low10_exit": enable_low10,
    }


# ── Phase 1: Exit optimization ──

PHASE1_CONFIGS = {
    "P1-A": {"label": "P1-A: baseline (no TP, trail=3, LOW10)",
             "tp": False, "tp_pct": 0.0, "trail_k": 3.0, "low10": True},
    "P1-B": {"label": "P1-B: TP=20%, trail=3, LOW10",
             "tp": True, "tp_pct": 0.20, "trail_k": 3.0, "low10": True},
    "P1-C": {"label": "P1-C: TP=30%, trail=3, LOW10",
             "tp": True, "tp_pct": 0.30, "trail_k": 3.0, "low10": True},
    "P1-D": {"label": "P1-D: no TP, trail=5, LOW10",
             "tp": False, "tp_pct": 0.0, "trail_k": 5.0, "low10": True},
    "P1-E": {"label": "P1-E: TP=30%, trail=5, LOW10",
             "tp": True, "tp_pct": 0.30, "trail_k": 5.0, "low10": True},
    "P1-F": {"label": "P1-F: TP=30%, trail=6, no LOW10 (champion style)",
             "tp": True, "tp_pct": 0.30, "trail_k": 6.0, "low10": False},
}


def build_phase1() -> list[tuple[str, str]]:
    """Return [(label, config_path), ...] for Phase 1."""
    configs = []
    for cid, p in PHASE1_CONFIGS.items():
        sp = _base_strategy_params(
            atr_trail_k=p["trail_k"],
            enable_tp=p["tp"], tp_pct=p["tp_pct"],
            enable_low10=p["low10"],
        )
        eb = _exit_block(
            atr_trail_k=p["trail_k"],
            enable_tp=p["tp"], tp_pct=p["tp_pct"],
            enable_low10=p["low10"],
        )
        configs.append((p["label"], _build_config(sp, eb, {"enabled": False})))
    return configs


# ── Phase 2: Entry relaxation (uses best exit from Phase 1) ──

def _get_exit_params(best_exit_id: str) -> dict:
    """Get the exit params from a Phase 1 config ID."""
    p = PHASE1_CONFIGS[best_exit_id]
    return {
        "trail_k": p["trail_k"], "tp": p["tp"],
        "tp_pct": p["tp_pct"], "low10": p["low10"],
    }


PHASE2_GRID = [
    {"id": "P2-A", "bw": 20, "v2": True,  "rma": 120, "note": "Phase 1 winner (baseline)"},
    {"id": "P2-B", "bw": 15, "v2": True,  "rma": 120, "note": "shorter window"},
    {"id": "P2-C", "bw": 10, "v2": True,  "rma": 120, "note": "aggressive short window"},
    {"id": "P2-D", "bw": 20, "v2": False, "rma": 120, "note": "no trend filter"},
    {"id": "P2-E", "bw": 15, "v2": False, "rma": 120, "note": "short + no trend"},
    {"id": "P2-F", "bw": 15, "v2": False, "rma": 60,  "note": "full relax"},
]


def build_phase2(best_exit_id: str) -> list[tuple[str, str]]:
    ep = _get_exit_params(best_exit_id)
    configs = []
    for g in PHASE2_GRID:
        label = f"{g['id']}: bw={g['bw']}, v2={'on' if g['v2'] else 'off'}, rma={g['rma']} ({g['note']})"
        sp = _base_strategy_params(
            breakout_window=g["bw"], regime_ma=g["rma"], v2_trend=g["v2"],
            atr_trail_k=ep["trail_k"],
            enable_tp=ep["tp"], tp_pct=ep["tp_pct"],
            enable_low10=ep["low10"],
        )
        eb = _exit_block(
            atr_trail_k=ep["trail_k"],
            enable_tp=ep["tp"], tp_pct=ep["tp_pct"],
            enable_low10=ep["low10"],
        )
        configs.append((label, _build_config(sp, eb, {"enabled": False})))
    return configs


# ── Phase 3: Risk control (uses best exit + best entry) ──

PHASE3_GRID = [
    {"id": "P3-A", "stop_k": 2.0, "dd": False, "dd_pct": 0,    "dd_scale": 0,   "note": "Phase 2 winner"},
    {"id": "P3-B", "stop_k": 1.5, "dd": False, "dd_pct": 0,    "dd_scale": 0,   "note": "tighter stop"},
    {"id": "P3-C", "stop_k": 2.0, "dd": True,  "dd_pct": 0.10, "dd_scale": 0.5, "note": "DD breaker 10%/0.5"},
    {"id": "P3-D", "stop_k": 1.5, "dd": True,  "dd_pct": 0.10, "dd_scale": 0.5, "note": "tight stop + DD"},
    {"id": "P3-E", "stop_k": 2.0, "dd": True,  "dd_pct": 0.15, "dd_scale": 0.3, "note": "aggressive DD 15%/0.3"},
    {"id": "P3-F", "stop_k": 1.5, "dd": True,  "dd_pct": 0.15, "dd_scale": 0.3, "note": "tight + aggressive DD"},
]


def build_phase3(best_exit_id: str, best_entry: dict) -> list[tuple[str, str]]:
    ep = _get_exit_params(best_exit_id)
    configs = []
    for g in PHASE3_GRID:
        dd_detail = f" {g['dd_pct']:.0%}/{g['dd_scale']}" if g["dd"] else ""
        label = (f"{g['id']}: stop_k={g['stop_k']}, "
                 f"DD={'on' if g['dd'] else 'off'}{dd_detail} "
                 f"({g['note']})")
        sp = _base_strategy_params(
            breakout_window=best_entry["bw"],
            regime_ma=best_entry["rma"],
            v2_trend=best_entry["v2"],
            atr_stop_k=g["stop_k"],
            atr_trail_k=ep["trail_k"],
            enable_tp=ep["tp"], tp_pct=ep["tp_pct"],
            enable_low10=ep["low10"],
        )
        eb = _exit_block(
            atr_stop_k=g["stop_k"],
            atr_trail_k=ep["trail_k"],
            enable_tp=ep["tp"], tp_pct=ep["tp_pct"],
            enable_low10=ep["low10"],
        )
        rb = {"enabled": False}
        if g["dd"]:
            rb = {
                "enabled": True,
                "dd_reduce_pct": g["dd_pct"],
                "dd_reduce_scale": g["dd_scale"],
                "atr_stop_k": g["stop_k"],
            }
        configs.append((label, _build_config(sp, eb, rb)))
    return configs


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def print_ranking(results: list[dict], phase_label: str) -> None:
    """Print ranking table sorted by Calmar ratio."""
    valid = [r for r in results if "cagr" in r]
    valid.sort(key=lambda r: r.get("calmar", 0), reverse=True)

    print(f"\n{'#' * 72}")
    print(f"  {phase_label} RANKING (by Calmar ratio)")
    print(f"{'#' * 72}")
    print(f"  {'Rank':<5} {'Config':<55} {'CAGR':>8} {'MDD':>8} {'Sharpe':>7} {'Calmar':>8} {'Trades':>7}")
    print(f"  {'-' * 98}")

    for i, r in enumerate(valid):
        cagr = r.get("cagr", 0)
        mdd = r.get("max_drawdown", 0)
        sharpe = r.get("sharpe", 0)
        calmar = r.get("calmar", 0)
        trades = r.get("trades", 0)
        marker = " ***" if i == 0 else ""
        print(f"  {i + 1:<5} {r['label']:<55} {cagr:>+7.2%} {mdd:>7.2%} {sharpe:>7.2f} {calmar:>8.2f} {trades:>7}{marker}")

    if valid:
        best = valid[0]
        cagr = best.get("cagr", 0)
        mdd = best.get("max_drawdown", 0)
        print(f"\n  WINNER: {best['label']}")
        print(f"  CAGR={cagr:+.2%}  MDD={mdd:.2%}  Calmar={best.get('calmar', 0):.2f}")

        # Judgment
        if cagr > 0.05 and mdd < 0.30:
            print(f"  VERDICT: Promising — worth deep-dive")
        elif cagr > 0.03 and mdd < 0.40:
            print(f"  VERDICT: Acceptable — diversification candidate")
        elif cagr < 0.02:
            print(f"  VERDICT: Weak — breakout may not work on CSI800")
        else:
            print(f"  VERDICT: Marginal — needs further tuning")

    print(f"{'#' * 72}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Breakout Trend parameter sweep")
    parser.add_argument("--phase", type=str, default="1", help="Phase: 1, 2, 3, or all")
    parser.add_argument("--best-exit", type=str, default="P1-A",
                        help="Best exit config from Phase 1 (e.g. P1-C)")
    parser.add_argument("--best-entry", type=str, default="P2-A",
                        help="Best entry config from Phase 2 (e.g. P2-B)")
    args = parser.parse_args()

    # Look up best entry params from P2 grid
    best_entry_map = {g["id"]: g for g in PHASE2_GRID}

    phases_to_run = []
    if args.phase == "all":
        phases_to_run = [1, 2, 3]
    else:
        phases_to_run = [int(args.phase)]

    all_results = {}

    for phase in phases_to_run:
        if phase == 1:
            configs = build_phase1()
            label = "PHASE 1: EXIT OPTIMIZATION"
        elif phase == 2:
            configs = build_phase2(args.best_exit)
            label = f"PHASE 2: ENTRY RELAXATION (exit={args.best_exit})"
        elif phase == 3:
            entry = best_entry_map.get(args.best_entry, PHASE2_GRID[0])
            configs = build_phase3(args.best_exit, entry)
            label = f"PHASE 3: RISK CONTROL (exit={args.best_exit}, entry={args.best_entry})"
        else:
            print(f"Unknown phase: {phase}")
            continue

        print(f"\n{'*' * 72}")
        print(f"  {label}")
        print(f"  {len(configs)} configurations")
        print(f"{'*' * 72}")

        results = []
        for config_label, config_path in configs:
            r = _run_one(config_label, config_path)
            results.append(r)

        print_ranking(results, label)
        all_results[phase] = results

        # In 'all' mode, auto-pick winner for next phase
        if args.phase == "all" and phase == 1:
            valid = [r for r in results if "calmar" in r]
            if valid:
                valid.sort(key=lambda r: r.get("calmar", 0), reverse=True)
                winner_label = valid[0]["label"]
                # Extract P1-X from label
                for pid in PHASE1_CONFIGS:
                    if pid in winner_label:
                        args.best_exit = pid
                        print(f"\n  Auto-selected best exit: {pid}")
                        break

        if args.phase == "all" and phase == 2:
            valid = [r for r in results if "calmar" in r]
            if valid:
                valid.sort(key=lambda r: r.get("calmar", 0), reverse=True)
                winner_label = valid[0]["label"]
                for g in PHASE2_GRID:
                    if g["id"] in winner_label:
                        args.best_entry = g["id"]
                        print(f"\n  Auto-selected best entry: {g['id']}")
                        break

    # Final summary if multiple phases
    if len(all_results) > 1:
        print(f"\n{'*' * 72}")
        print(f"  SWEEP COMPLETE — ALL PHASES")
        print(f"{'*' * 72}")
        for phase, results in all_results.items():
            valid = [r for r in results if "calmar" in r]
            if valid:
                valid.sort(key=lambda r: r.get("calmar", 0), reverse=True)
                best = valid[0]
                print(f"  Phase {phase} winner: {best['label']}")
                print(f"    CAGR={best.get('cagr', 0):+.2%}  MDD={best.get('max_drawdown', 0):.2%}  Calmar={best.get('calmar', 0):.2f}")
        print(f"{'*' * 72}")


if __name__ == "__main__":
    main()
