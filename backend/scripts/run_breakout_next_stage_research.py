from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api.endpoints._experiment_runner_api import (  # noqa: E402
    BacktestV2ExperimentRequest,
    _build_runtime_cfg_from_workbench,
)
from backend.core.tools.experiment_runner import run_experiment  # noqa: E402


WINDOWS = {
    "FULL": ("2016-03-01", "2026-03-01"),
    "W1": ("2016-03-01", "2019-12-31"),
    "W2": ("2020-01-01", "2022-12-31"),
    "W3": ("2023-01-01", "2026-03-01"),
}


EXPERIMENTS = [
    {"experiment_id": "A1", "entry_confirm_mode": "none", "entry_delay_mode": "none", "portfolio_mode": "equal_10"},
    {"experiment_id": "A2", "entry_confirm_mode": "close_strength", "entry_delay_mode": "none", "portfolio_mode": "equal_10"},
    {"experiment_id": "A3", "entry_confirm_mode": "volume_confirm", "entry_delay_mode": "none", "portfolio_mode": "equal_10"},
    {"experiment_id": "A4", "entry_confirm_mode": "volatility_confirm", "entry_delay_mode": "none", "portfolio_mode": "equal_10"},
    {"experiment_id": "B1", "entry_confirm_mode": "none", "entry_delay_mode": "none", "portfolio_mode": "equal_10"},
    {"experiment_id": "B2", "entry_confirm_mode": "none", "entry_delay_mode": "t1_confirm", "portfolio_mode": "equal_10"},
    {"experiment_id": "B3", "entry_confirm_mode": "none", "entry_delay_mode": "t2_confirm", "portfolio_mode": "equal_10"},
    {"experiment_id": "B4", "entry_confirm_mode": "none", "entry_delay_mode": "pullback_confirm", "portfolio_mode": "equal_10"},
    {"experiment_id": "C1", "entry_confirm_mode": "none", "entry_delay_mode": "none", "portfolio_mode": "equal_10"},
    {"experiment_id": "C2", "entry_confirm_mode": "none", "entry_delay_mode": "none", "portfolio_mode": "equal_8"},
    {"experiment_id": "C3", "entry_confirm_mode": "none", "entry_delay_mode": "none", "portfolio_mode": "equal_6"},
    {"experiment_id": "C4", "entry_confirm_mode": "none", "entry_delay_mode": "none", "portfolio_mode": "profit_release"},
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _build_runtime_from_wb(base_cfg: dict[str, Any], wb_cfg: dict[str, Any]) -> dict[str, Any]:
    body = BacktestV2ExperimentRequest(
        preset="single",
        universe_mode=str(wb_cfg.get("universe_mode", "ALL_A")),
        start_date=str((wb_cfg.get("universe") or {}).get("start", "2016-03-01")),
        end_date=str((wb_cfg.get("universe") or {}).get("end", "2026-03-01")),
        benchmark=str((wb_cfg.get("universe") or {}).get("benchmark", "000300.SH")),
        max_positions=int(((wb_cfg.get("position_risk") or {}).get("max_positions", 10))),
        fast_mode=True,
        price_adj=str((wb_cfg.get("universe") or {}).get("price_adj", "hfq")),
    )
    return _build_runtime_cfg_from_workbench(base_cfg, body, wb_cfg)


def _apply_experiment_to_wb(base_wb: dict[str, Any], e: dict[str, Any], start: str, end: str) -> dict[str, Any]:
    wb = deepcopy(base_wb)
    wb.setdefault("signal_generation", {}).setdefault("breakout", {})
    wb.setdefault("position_risk", {})
    wb.setdefault("exit_rules", {}).setdefault("atr_stop", {})
    wb.setdefault("universe", {})

    # Keep fixed anchors for this research.
    wb["signal_generation"]["strategy"] = "BREAKOUT_TREND"
    wb["signal_generation"]["breakout"]["breakout_window"] = 55
    wb["signal_generation"]["breakout"]["entry_confirm_mode"] = str(e["entry_confirm_mode"])
    wb["signal_generation"]["breakout"]["entry_delay_mode"] = str(e["entry_delay_mode"])
    wb["exit_rules"]["atr_stop"]["enabled"] = True
    wb["exit_rules"]["atr_stop"]["k"] = 1.2
    wb["position_risk"]["portfolio_mode"] = str(e["portfolio_mode"])

    wb["universe"]["start"] = start
    wb["universe"]["end"] = end
    return wb


def _compute_trade_stats(trades_csv: Path) -> dict[str, float]:
    if not trades_csv.exists():
        return {"win_rate": 0.0, "profit_factor": 0.0, "avg_hold_days": 0.0}
    import pandas as pd

    df = pd.read_csv(trades_csv)
    if df.empty:
        return {"win_rate": 0.0, "profit_factor": 0.0, "avg_hold_days": 0.0}
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["side"] = df["side"].astype(str).str.upper()
    df = df.sort_values(["date"]).reset_index(drop=True)

    lots: dict[str, list[dict[str, Any]]] = {}
    closed_pnls: list[float] = []
    hold_qty_days = 0.0
    hold_qty_total = 0.0

    for r in df.itertuples(index=False):
        sym = str(r.symbol).lower()
        side = str(r.side).upper()
        qty = int(getattr(r, "qty", 0) or 0)
        net_amount = float(getattr(r, "net_amount", 0.0) or 0.0)
        d = r.date
        if qty <= 0 or d is None:
            continue
        if side == "BUY":
            ps_cost = net_amount / float(qty)
            lots.setdefault(sym, []).append({"qty": qty, "cost_ps": ps_cost, "date": d})
        elif side == "SELL":
            ps_recv = net_amount / float(qty)
            remain = qty
            pnl = 0.0
            sym_lots = lots.setdefault(sym, [])
            while remain > 0 and sym_lots:
                lot = sym_lots[0]
                take = min(remain, int(lot["qty"]))
                pnl += float(take) * (ps_recv - float(lot["cost_ps"]))
                hd = max((d - lot["date"]).days, 0)
                hold_qty_days += float(hd) * float(take)
                hold_qty_total += float(take)
                lot["qty"] = int(lot["qty"]) - int(take)
                remain -= int(take)
                if int(lot["qty"]) <= 0:
                    sym_lots.pop(0)
            if qty > remain:
                closed_pnls.append(float(pnl))

    wins = [p for p in closed_pnls if p > 0]
    losses = [p for p in closed_pnls if p < 0]
    win_rate = (len(wins) / len(closed_pnls)) if closed_pnls else 0.0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 1e-12 else (999.0 if gross_profit > 0 else 0.0)
    avg_hold_days = (hold_qty_days / hold_qty_total) if hold_qty_total > 0 else 0.0
    return {"win_rate": float(win_rate), "profit_factor": float(profit_factor), "avg_hold_days": float(avg_hold_days)}


def _run_one(base_cfg: dict[str, Any], wb_cfg: dict[str, Any], exp: dict[str, Any], window_name: str) -> dict[str, Any]:
    start, end = WINDOWS[window_name]
    wb_variant = _apply_experiment_to_wb(wb_cfg, exp, start=start, end=end)
    runtime_cfg = _build_runtime_from_wb(base_cfg, wb_variant)

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(runtime_cfg, tmp, ensure_ascii=False, indent=2)
    tmp.close()
    tmp_path = tmp.name

    universe = wb_variant.get("universe") or {}
    overrides: dict[str, Any] = {
        "universe_mode": str(wb_variant.get("universe_mode", "ALL_A")),
        "start_date": str(universe.get("start", start)),
        "end_date": str(universe.get("end", end)),
        "benchmark": str(universe.get("benchmark", "000300.SH")),
        "initial_capital": float(wb_variant.get("initial_capital", 1_000_000)),
        "max_positions": int((wb_variant.get("position_risk") or {}).get("max_positions", 10)),
        "base_order_value": 0,
        "fast_mode": True,
        "price_adj": str(universe.get("price_adj", "hfq")),
    }
    try:
        result = run_experiment(tmp_path, preset="single", overrides=overrides)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    results_dir = Path(str(result.get("results_dir", "")))
    trades_csv = results_dir / "portfolio_trades.csv"
    tstats = _compute_trade_stats(trades_csv)
    return {
        "experiment_id": str(exp["experiment_id"]),
        "window": window_name,
        "entry_confirm_mode": str(exp["entry_confirm_mode"]),
        "entry_delay_mode": str(exp["entry_delay_mode"]),
        "portfolio_mode": str(exp["portfolio_mode"]),
        "breakout_window": 55,
        "atr_stop_k": 1.2,
        "exp_id": str(result.get("exp_id", "")),
        "results_dir": str(results_dir),
        "CAGR": float(result.get("cagr", 0.0) or 0.0),
        "Sharpe": float(result.get("sharpe", 0.0) or 0.0),
        "MaxDrawdown": float(result.get("max_drawdown", 0.0) or 0.0),
        "Trades": int(result.get("trades", 0) or 0),
        "AvgPositions": float(result.get("avg_positions", 0.0) or 0.0),
        "AvgHoldDays": float(tstats["avg_hold_days"]),
        "WinRate": float(tstats["win_rate"]),
        "ProfitFactor": float(tstats["profit_factor"]),
    }


def _mk_key(exp: dict[str, Any], window: str) -> tuple[str, str, str, str]:
    return (
        str(exp["entry_confirm_mode"]),
        str(exp["entry_delay_mode"]),
        str(exp["portfolio_mode"]),
        window,
    )


def main() -> None:
    t0 = time.perf_counter()
    base_cfg = _load_json(ROOT / "backend" / "configs" / "pams_cn_pg.json")
    base_cfg.setdefault("db", {})
    if str(base_cfg["db"].get("host") or "").strip() == "pams-postgres":
        base_cfg["db"]["host"] = "localhost"
    if not str(base_cfg["db"].get("password") or "").strip():
        env_pwd = str(os.environ.get("PGPASSWORD") or os.environ.get("PAMS_PG_PASSWORD") or "").strip()
        if env_pwd:
            base_cfg["db"]["password"] = env_pwd

    wb_payload = _load_json(ROOT / "outputs" / "configs" / "cfg_da4a2be7f3b7.json")
    wb_cfg = dict(wb_payload.get("config_json") or {})

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "outputs" / "experiments" / f"next_stage_research_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cache: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    full_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []

    for exp in EXPERIMENTS:
        for w in ("FULL", "W1", "W2", "W3"):
            k = _mk_key(exp, w)
            if k not in cache:
                print(f"[RUN] {exp['experiment_id']} {w} {k[0]}/{k[1]}/{k[2]}")
                cache[k] = _run_one(base_cfg=base_cfg, wb_cfg=wb_cfg, exp=exp, window_name=w)
                r = cache[k]
                print(f"  -> {r['exp_id']} CAGR={r['CAGR']:.2%} Sharpe={r['Sharpe']:.2f} MDD={r['MaxDrawdown']:.2%}")
            row = dict(cache[k])
            row["experiment_id"] = str(exp["experiment_id"])
            if w == "FULL":
                full_rows.append(row)
            else:
                rolling_rows.append(row)

    # Baseline window refs for pass criteria.
    baseline_ref: dict[str, dict[str, float]] = {}
    for r in rolling_rows:
        if str(r["experiment_id"]) == "A1":
            baseline_ref[str(r["window"])] = {
                "CAGR": float(r["CAGR"]),
                "MaxDrawdown": float(r["MaxDrawdown"]),
            }

    # Build summary rows with rolling metrics and pass count.
    summary_rows: list[dict[str, Any]] = []
    by_exp_roll: dict[str, dict[str, dict[str, Any]]] = {}
    for r in rolling_rows:
        by_exp_roll.setdefault(str(r["experiment_id"]), {})[str(r["window"])] = r

    for fr in full_rows:
        eid = str(fr["experiment_id"])
        rw = by_exp_roll.get(eid, {})
        sw1 = float((rw.get("W1") or {}).get("Sharpe", 0.0))
        sw2 = float((rw.get("W2") or {}).get("Sharpe", 0.0))
        sw3 = float((rw.get("W3") or {}).get("Sharpe", 0.0))
        pass_windows = 0
        for w in ("W1", "W2", "W3"):
            rr = rw.get(w)
            if not rr or w not in baseline_ref:
                continue
            base_cagr = float(baseline_ref[w]["CAGR"])
            base_mdd = float(baseline_ref[w]["MaxDrawdown"])
            c1 = float(rr["Sharpe"]) >= 0.30
            c2 = float(rr["CAGR"]) >= (0.8 * base_cagr)
            c3 = float(rr["MaxDrawdown"]) >= (base_mdd - 0.05)
            if c1 and c2 and c3:
                pass_windows += 1
        srow = {
            **fr,
            "Sharpe_W1": sw1,
            "Sharpe_W2": sw2,
            "Sharpe_W3": sw3,
            "pass_windows": int(pass_windows),
            "pass_criteria": bool(pass_windows >= 2),
        }
        summary_rows.append(srow)

    # Pick best config: pass_criteria first, then Sharpe, then CAGR.
    ranked = sorted(
        summary_rows,
        key=lambda x: (1 if bool(x["pass_criteria"]) else 0, float(x["Sharpe"]), float(x["CAGR"])),
        reverse=True,
    )
    best = ranked[0] if ranked else {}

    # Save rolling CSV.
    rolling_csv = out_dir / "rolling_window_results.csv"
    with rolling_csv.open("w", newline="", encoding="utf-8") as f:
        fields = [
            "experiment_id", "window", "entry_confirm_mode", "entry_delay_mode", "portfolio_mode",
            "breakout_window", "atr_stop_k", "exp_id", "CAGR", "Sharpe", "MaxDrawdown",
            "Trades", "AvgPositions", "AvgHoldDays", "WinRate", "ProfitFactor",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rolling_rows:
            w.writerow({k: r.get(k) for k in fields})

    # Save best_config.json (workbench-oriented).
    best_cfg = _apply_experiment_to_wb(
        base_wb=wb_cfg,
        e={
            "entry_confirm_mode": str(best.get("entry_confirm_mode", "none")),
            "entry_delay_mode": str(best.get("entry_delay_mode", "none")),
            "portfolio_mode": str(best.get("portfolio_mode", "equal_10")),
            "experiment_id": str(best.get("experiment_id", "")),
        },
        start="2016-03-01",
        end="2026-03-01",
    )
    (out_dir / "best_config.json").write_text(json.dumps(best_cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    # Save machine-readable full summary.
    (out_dir / "results_table.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(),
                "elapsed_seconds": float(time.perf_counter() - t0),
                "summary_rows": summary_rows,
                "rolling_rows": rolling_rows,
                "best": best,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Markdown report.
    md = []
    md.append("# Breakout Next-Stage Research Summary")
    md.append("")
    md.append("- Baseline anchor: 3月6日冠军配置")
    md.append("- Fixed: breakout_window=55, atr_stop_k=1.2")
    md.append("")
    md.append("## Full-Period Results (2016-03-01 ~ 2026-03-01)")
    md.append("")
    md.append("| experiment_id | entry_confirm_mode | entry_delay_mode | portfolio_mode | CAGR | Sharpe | MaxDrawdown | Trades | AvgHoldDays | WinRate | ProfitFactor | Sharpe_W1 | Sharpe_W2 | Sharpe_W3 | pass_windows | pass_criteria |")
    md.append("|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for r in sorted(summary_rows, key=lambda x: str(x["experiment_id"])):
        md.append(
            f"| {r['experiment_id']} | {r['entry_confirm_mode']} | {r['entry_delay_mode']} | {r['portfolio_mode']} | "
            f"{float(r['CAGR']):.2%} | {float(r['Sharpe']):.2f} | {float(r['MaxDrawdown']):.2%} | {int(r['Trades'])} | "
            f"{float(r['AvgHoldDays']):.2f} | {float(r['WinRate']):.2%} | {float(r['ProfitFactor']):.2f} | "
            f"{float(r['Sharpe_W1']):.2f} | {float(r['Sharpe_W2']):.2f} | {float(r['Sharpe_W3']):.2f} | "
            f"{int(r['pass_windows'])} | {bool(r['pass_criteria'])} |"
        )
    md.append("")
    md.append("## Best Configuration")
    md.append("")
    if best:
        md.append(f"- experiment_id: `{best['experiment_id']}`")
        md.append(f"- entry_confirm_mode: `{best['entry_confirm_mode']}`")
        md.append(f"- entry_delay_mode: `{best['entry_delay_mode']}`")
        md.append(f"- portfolio_mode: `{best['portfolio_mode']}`")
        md.append(f"- CAGR: `{float(best['CAGR']):.2%}`")
        md.append(f"- Sharpe: `{float(best['Sharpe']):.2f}`")
        md.append(f"- MaxDrawdown: `{float(best['MaxDrawdown']):.2%}`")
        md.append(f"- pass_windows: `{int(best['pass_windows'])}`")
    (out_dir / "experiment_summary.md").write_text("\n".join(md), encoding="utf-8")

    print(f"[DONE] {out_dir}")


if __name__ == "__main__":
    main()

