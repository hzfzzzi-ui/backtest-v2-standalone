from __future__ import annotations

import io
import json
import sys
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.services.experiment_runtime_service import run_experiment_request  # noqa: E402


BASELINE_ID = "baseline_V9_1"
BASELINE_INDEX_PATH = ROOT / "outputs" / "baselines" / "index.json"
ALLOWED_DIFF_PATH = ("signal_generation", "breakout", "breakout_entry_buffer_pct")
BUFFER_VARIANTS: list[tuple[str, float]] = [
    ("baseline", 0.0),
    ("buffer_0p5pct", 0.005),
    ("buffer_1p0pct", 0.01),
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _path_text(path: tuple[Any, ...]) -> str:
    return ".".join(str(part) for part in path)


def _collect_diffs(base: Any, candidate: Any, path: tuple[Any, ...] = ()) -> list[tuple[tuple[Any, ...], Any, Any]]:
    if isinstance(base, dict) and isinstance(candidate, dict):
        diffs: list[tuple[tuple[Any, ...], Any, Any]] = []
        for key in sorted(set(base.keys()) | set(candidate.keys())):
            if key not in base:
                diffs.append((path + (key,), "<missing>", candidate[key]))
                continue
            if key not in candidate:
                diffs.append((path + (key,), base[key], "<missing>"))
                continue
            diffs.extend(_collect_diffs(base[key], candidate[key], path + (key,)))
        return diffs
    if isinstance(base, list) and isinstance(candidate, list):
        if len(base) != len(candidate):
            return [(path, base, candidate)]
        diffs: list[tuple[tuple[Any, ...], Any, Any]] = []
        for idx, (base_item, candidate_item) in enumerate(zip(base, candidate)):
            diffs.extend(_collect_diffs(base_item, candidate_item, path + (idx,)))
        return diffs
    if base != candidate:
        return [(path, base, candidate)]
    return []


def _find_baseline_entry() -> dict[str, Any]:
    entries = _load_json(BASELINE_INDEX_PATH)
    if not isinstance(entries, list):
        raise RuntimeError(f"unexpected baseline index format: {type(entries)!r}")
    for item in entries:
        if not isinstance(item, dict):
            continue
        if str(item.get("baseline_id") or "") == BASELINE_ID:
            return dict(item)
    raise RuntimeError(f"missing baseline entry: {BASELINE_ID}")


def _baseline_paths() -> tuple[dict[str, Any], Path]:
    baseline_entry = _find_baseline_entry()
    semantic_cfg_path = ROOT / "outputs" / "baselines" / BASELINE_ID / "config.json"
    if not semantic_cfg_path.exists():
        raise FileNotFoundError(f"missing baseline semantic config: {semantic_cfg_path}")
    return baseline_entry, semantic_cfg_path


def _assert_single_main_change(base_cfg: dict[str, Any], candidate_cfg: dict[str, Any]) -> None:
    diffs = _collect_diffs(base_cfg, candidate_cfg)
    unexpected = [diff for diff in diffs if diff[0] != ALLOWED_DIFF_PATH]
    if unexpected:
        lines = []
        for diff_path, base_value, candidate_value in unexpected[:10]:
            lines.append(f"{_path_text(diff_path)}: baseline={base_value!r}, candidate={candidate_value!r}")
        raise RuntimeError(
            "variant drifted beyond the allowed main change:\n" + "\n".join(lines)
        )


def _build_variant_cfg(base_cfg: dict[str, Any], *, breakout_buffer_pct: float) -> dict[str, Any]:
    candidate_cfg = deepcopy(base_cfg)
    candidate_cfg.setdefault("signal_generation", {}).setdefault("breakout", {})["breakout_entry_buffer_pct"] = float(
        breakout_buffer_pct
    )
    _assert_single_main_change(base_cfg, candidate_cfg)
    return candidate_cfg


def _assert_baseline_contract(base_cfg: dict[str, Any], baseline_entry: dict[str, Any]) -> None:
    strategy_name = str((base_cfg.get("signal_generation") or {}).get("strategy") or "").strip().upper()
    if strategy_name != "BREAKOUT_TREND":
        raise RuntimeError(f"expected BREAKOUT_TREND baseline, got {strategy_name!r}")
    if str(baseline_entry.get("universe_mode") or "") != "HS300_ZZ500":
        raise RuntimeError("baseline universe_mode is not HS300_ZZ500")
    if str((base_cfg.get("universe") or {}).get("benchmark") or "") != "000300.SH":
        raise RuntimeError("baseline benchmark is not 000300.SH")
    params = (base_cfg.get("signal_generation") or {}).get("breakout") or {}
    if abs(float(params.get("breakout_entry_buffer_pct", 0.0) or 0.0)) > 1e-12:
        raise RuntimeError("expected V9.1 baseline breakout_entry_buffer_pct=0.0")
    if int(params.get("breakout_window", 0) or 0) != 45:
        raise RuntimeError("expected V9.1 baseline breakout_window=45")
    if not bool((base_cfg.get("benchmark_regime") or {}).get("enabled")):
        raise RuntimeError("expected benchmark_regime.enabled=true")


def _compute_trade_stats(trades_csv: Path) -> dict[str, float]:
    if not trades_csv.exists():
        return {
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_hold_days": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "top1_symbol_profit_share": 0.0,
            "top3_month_profit_share": 0.0,
        }
    df = pd.read_csv(trades_csv)
    if df.empty:
        return {
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_hold_days": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "top1_symbol_profit_share": 0.0,
            "top3_month_profit_share": 0.0,
        }
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["side"] = df["side"].astype(str).str.upper()
    df = df.sort_values(["date"]).reset_index(drop=True)

    lots: dict[str, list[dict[str, Any]]] = {}
    closed_pnls: list[float] = []
    hold_qty_days = 0.0
    hold_qty_total = 0.0
    symbol_profit: dict[str, float] = {}
    month_profit: dict[str, float] = {}

    for row in df.itertuples(index=False):
        symbol = str(row.symbol).lower()
        side = str(row.side).upper()
        qty = int(getattr(row, "qty", 0) or 0)
        net_amount = float(getattr(row, "net_amount", 0.0) or 0.0)
        trade_date = getattr(row, "date", None)
        if qty <= 0 or trade_date is None or pd.isna(trade_date):
            continue
        if side == "BUY":
            cost_per_share = net_amount / float(qty)
            lots.setdefault(symbol, []).append({"qty": qty, "cost_ps": cost_per_share, "date": trade_date})
            continue
        if side != "SELL":
            continue

        recv_per_share = net_amount / float(qty)
        remain = qty
        pnl = 0.0
        symbol_lots = lots.setdefault(symbol, [])
        while remain > 0 and symbol_lots:
            lot = symbol_lots[0]
            take = min(remain, int(lot["qty"]))
            pnl += float(take) * (recv_per_share - float(lot["cost_ps"]))
            held_days = max((trade_date - lot["date"]).days, 0)
            hold_qty_days += float(held_days) * float(take)
            hold_qty_total += float(take)
            lot["qty"] = int(lot["qty"]) - int(take)
            remain -= int(take)
            if int(lot["qty"]) <= 0:
                symbol_lots.pop(0)
        if qty > remain:
            closed_pnls.append(float(pnl))
            if pnl > 0:
                symbol_profit[symbol] = float(symbol_profit.get(symbol, 0.0)) + float(pnl)
                month_key = pd.Timestamp(trade_date).strftime("%Y-%m")
                month_profit[month_key] = float(month_profit.get(month_key, 0.0)) + float(pnl)

    wins = [value for value in closed_pnls if value > 0]
    losses = [value for value in closed_pnls if value < 0]
    win_rate = (len(wins) / len(closed_pnls)) if closed_pnls else 0.0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 1e-12 else (999.0 if gross_profit > 0 else 0.0)
    avg_hold_days = (hold_qty_days / hold_qty_total) if hold_qty_total > 0 else 0.0
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0
    top1_symbol_profit_share = (max(symbol_profit.values()) / gross_profit) if gross_profit > 1e-12 and symbol_profit else 0.0
    top3_month_profit_share = (
        sum(sorted(month_profit.values(), reverse=True)[:3]) / gross_profit
        if gross_profit > 1e-12 and month_profit
        else 0.0
    )
    return {
        "win_rate": float(win_rate),
        "profit_factor": float(profit_factor),
        "avg_hold_days": float(avg_hold_days),
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
        "top1_symbol_profit_share": float(top1_symbol_profit_share),
        "top3_month_profit_share": float(top3_month_profit_share),
    }


def _run_one(
    *,
    variant_name: str,
    breakout_buffer_pct: float,
    base_cfg: dict[str, Any],
) -> dict[str, Any]:
    semantic_cfg = _build_variant_cfg(base_cfg, breakout_buffer_pct=breakout_buffer_pct)
    t0 = time.perf_counter()
    print(f"\n{'=' * 72}")
    print(f"{variant_name}: signal_generation.breakout.breakout_entry_buffer_pct={breakout_buffer_pct:.4f}")
    print(f"{'=' * 72}")

    def progress(pct: int, message: str) -> None:
        elapsed = time.perf_counter() - t0
        print(f"  [{pct:3d}%] {message} ({elapsed:.1f}s)")

    result = run_experiment_request({"preset": "single", "config_json": semantic_cfg, "fast_mode": True}, progress_hook=progress)
    results_dir = Path(str(result.get("results_dir") or ""))
    perf = _load_json(results_dir / "perf.json") if (results_dir / "perf.json").exists() else {}
    run_meta = _load_json(results_dir / "run_meta.json") if (results_dir / "run_meta.json").exists() else {}
    trade_stats = _compute_trade_stats(results_dir / "portfolio_trades.csv")
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}

    metrics = {
        "variant": variant_name,
        "breakout_entry_buffer_pct": float(breakout_buffer_pct),
        "exp_id": str(result.get("exp_id") or ""),
        "results_dir": str(results_dir),
        "cagr": float(perf.get("cagr", result.get("cagr", 0.0)) or 0.0),
        "max_drawdown": float(perf.get("max_drawdown", result.get("max_drawdown", 0.0)) or 0.0),
        "sharpe": float(perf.get("sharpe", result.get("sharpe", 0.0)) or 0.0),
        "calmar": float(perf.get("calmar", result.get("calmar", 0.0)) or 0.0),
        "total_return": float(perf.get("total_return", result.get("total_return", 0.0)) or 0.0),
        "trades": int(perf.get("trades", result.get("trades", 0)) or 0),
        "turnover": float(perf.get("turnover", result.get("turnover", 0.0)) or 0.0),
        "avg_positions": float(counters.get("avg_positions", result.get("avg_positions", 0.0)) or 0.0),
        "raw_signal": int(counters.get("raw_signal", 0) or 0),
        "buy_orders_count": int(counters.get("buy_orders_count", 0) or 0),
        "win_rate": float(trade_stats["win_rate"]),
        "profit_factor": float(trade_stats["profit_factor"]),
        "avg_hold_days": float(trade_stats["avg_hold_days"]),
        "avg_win": float(trade_stats["avg_win"]),
        "avg_loss": float(trade_stats["avg_loss"]),
        "top1_symbol_profit_share": float(trade_stats["top1_symbol_profit_share"]),
        "top3_month_profit_share": float(trade_stats["top3_month_profit_share"]),
        "audit_only_changed": _path_text(ALLOWED_DIFF_PATH),
    }
    print(
        "  CAGR={cagr:+.2%}  MaxDD={max_drawdown:.2%}  Sharpe={sharpe:.2f}  "
        "Trades={trades}  AvgPos={avg_positions:.2f}".format(**metrics)
    )
    return metrics


def _write_summary(
    *,
    out_dir: Path,
    baseline_entry: dict[str, Any],
    semantic_cfg_path: Path,
    base_cfg: dict[str, Any],
    results: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": datetime.now().isoformat(),
        "baseline_id": str(baseline_entry.get("baseline_id") or BASELINE_ID),
        "baseline_linked_exp_id": str(baseline_entry.get("linked_exp_id") or ""),
        "baseline_semantic_config_path": str(semantic_cfg_path),
        "main_change_path": _path_text(ALLOWED_DIFF_PATH),
        "unchanged_contract": {
            "benchmark": str((base_cfg.get("universe") or {}).get("benchmark") or ""),
            "start": str((base_cfg.get("universe") or {}).get("start") or ""),
            "end": str((base_cfg.get("universe") or {}).get("end") or ""),
            "costs": base_cfg.get("costs") or {},
            "execution": base_cfg.get("execution") or {},
            "benchmark_regime": base_cfg.get("benchmark_regime") or {},
        },
        "results": results,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# V9.1 Breakout Buffer Research",
        "",
        f"- baseline_id: `{summary['baseline_id']}`",
        f"- baseline_linked_exp_id: `{summary['baseline_linked_exp_id']}`",
        f"- main_change: `{summary['main_change_path']}`",
        "",
        "| variant | buffer | CAGR | MaxDD | Sharpe | Calmar | Trades | AvgPos | WinRate | Top1StockProfit | Top3MonthProfit | exp_id |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in results:
        lines.append(
            "| {variant} | {breakout_entry_buffer_pct:.2%} | {cagr:.2%} | {max_drawdown:.2%} | {sharpe:.2f} | "
            "{calmar:.2f} | {trades} | {avg_positions:.2f} | {win_rate:.2%} | {top1_symbol_profit_share:.2%} | "
            "{top3_month_profit_share:.2%} | `{exp_id}` |".format(**row)
        )
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    baseline_entry, semantic_cfg_path = _baseline_paths()
    base_cfg = _load_json(semantic_cfg_path)
    _assert_baseline_contract(base_cfg, baseline_entry)

    print("Audit: only signal_generation.breakout.breakout_entry_buffer_pct will change.")
    print("Audit: universe, costs, execution, benchmark_regime, exits, and ranking stay untouched.")
    print("Audit: existing engine still generates signals on day t and queues orders for next-day open.")

    results: list[dict[str, Any]] = []
    for variant_name, breakout_buffer_pct in BUFFER_VARIANTS:
        results.append(
            _run_one(
                variant_name=variant_name,
                breakout_buffer_pct=breakout_buffer_pct,
                base_cfg=base_cfg,
            )
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "outputs" / "experiments" / f"breakout_buffer_research_{stamp}"
    _write_summary(
        out_dir=out_dir,
        baseline_entry=baseline_entry,
        semantic_cfg_path=semantic_cfg_path,
        base_cfg=base_cfg,
        results=results,
    )
    print(f"\nSummary written to: {out_dir}")


if __name__ == "__main__":
    main()
