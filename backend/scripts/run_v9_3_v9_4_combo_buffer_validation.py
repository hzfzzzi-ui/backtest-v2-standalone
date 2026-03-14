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
V93_ID = "baseline_V9_3"
V94_ID = "baseline_V9_4"
RESULT_PREFIX = "v9_3_v9_4_combo_buffer_validation"
BUFFER_VALUES: tuple[float, ...] = (0.7, 0.5)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _baseline_cfg_path(baseline_id: str) -> Path:
    path = ROOT / "outputs" / "baselines" / baseline_id / "config.json"
    if not path.exists():
        raise FileNotFoundError(f"missing baseline config: {path}")
    return path


def _baseline_meta_path(baseline_id: str) -> Path:
    path = ROOT / "outputs" / "baselines" / baseline_id / "baseline.json"
    if not path.exists():
        raise FileNotFoundError(f"missing baseline meta: {path}")
    return path


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
        if base != candidate:
            return [(path, base, candidate)]
        return []
    if base != candidate:
        return [(path, base, candidate)]
    return []


def _assert_allowed_diffs(
    *,
    base_cfg: dict[str, Any],
    candidate_cfg: dict[str, Any],
    allowed_paths: tuple[tuple[Any, ...], ...],
    ignored_paths: tuple[tuple[Any, ...], ...] = (),
    label: str,
) -> None:
    allowed = set(allowed_paths)
    ignored = set(ignored_paths)
    unexpected = [diff for diff in _collect_diffs(base_cfg, candidate_cfg) if diff[0] not in allowed and diff[0] not in ignored]
    if unexpected:
        lines = []
        for diff_path, base_value, candidate_value in unexpected[:10]:
            lines.append(f"{'.'.join(str(part) for part in diff_path)}: base={base_value!r}, candidate={candidate_value!r}")
        raise RuntimeError(f"{label} drifted beyond allowed paths:\n" + "\n".join(lines))


def _assert_v9_contract(cfg: dict[str, Any], *, baseline_id: str) -> None:
    strategy_name = str((cfg.get("signal_generation") or {}).get("strategy") or "").strip().upper()
    if strategy_name != "BREAKOUT_TREND":
        raise RuntimeError(f"{baseline_id}: expected BREAKOUT_TREND, got {strategy_name!r}")
    if str(cfg.get("universe_mode") or "") != "HS300_ZZ500":
        raise RuntimeError(f"{baseline_id}: universe_mode drifted")
    universe = cfg.get("universe") or {}
    if str(universe.get("benchmark") or "") != "000300.SH":
        raise RuntimeError(f"{baseline_id}: benchmark drifted")
    if str(universe.get("membership_mode") or "") != "PIT_DYNAMIC":
        raise RuntimeError(f"{baseline_id}: membership_mode drifted")
    breakout = (cfg.get("signal_generation") or {}).get("breakout") or {}
    ranking = (cfg.get("signal_generation") or {}).get("ranking") or {}
    trailing = (cfg.get("exit_rules") or {}).get("trailing") or {}
    if int(breakout.get("breakout_window", 0) or 0) != 45:
        raise RuntimeError(f"{baseline_id}: breakout_window drifted")
    if str(ranking.get("score_source_mode") or "").strip().lower() != "residual_only":
        raise RuntimeError(f"{baseline_id}: score_source_mode drifted")
    if abs(float(trailing.get("activate_profit_pct", 0.0) or 0.0) - 0.15) > 1e-12:
        raise RuntimeError(f"{baseline_id}: trailing.activate_profit_pct drifted")


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
            lots.setdefault(symbol, []).append({"qty": qty, "cost_ps": net_amount / float(qty), "date": trade_date})
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
        if remain > 0:
            continue

        closed_pnls.append(float(pnl))
        symbol_profit[symbol] = float(symbol_profit.get(symbol, 0.0) + pnl)
        month_key = pd.Timestamp(trade_date).strftime("%Y-%m")
        month_profit[month_key] = float(month_profit.get(month_key, 0.0) + pnl)

    if not closed_pnls:
        return {
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_hold_days": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "top1_symbol_profit_share": 0.0,
            "top3_month_profit_share": 0.0,
        }

    wins = [x for x in closed_pnls if x > 0]
    losses = [x for x in closed_pnls if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "win_rate": float(len(wins) / len(closed_pnls)),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 1e-12 else 0.0,
        "avg_hold_days": float(hold_qty_days / hold_qty_total) if hold_qty_total > 1e-12 else 0.0,
        "avg_win": float(gross_profit / len(wins)) if wins else 0.0,
        "avg_loss": float(sum(losses) / len(losses)) if losses else 0.0,
        "top1_symbol_profit_share": float(max(symbol_profit.values()) / gross_profit)
        if gross_profit > 1e-12 and symbol_profit
        else 0.0,
        "top3_month_profit_share": float(sum(sorted(month_profit.values(), reverse=True)[:3]) / gross_profit)
        if gross_profit > 1e-12 and month_profit
        else 0.0,
    }


def _load_audit_flags(results_dir: Path) -> dict[str, str]:
    audit_path = results_dir / "audit.json"
    if not audit_path.exists():
        return {"overall_status": "", "timing_alignment": "", "execution_realism": "", "result_sanity": ""}
    audit = _load_json(audit_path)
    research = audit.get("research_audit") if isinstance(audit, dict) and isinstance(audit.get("research_audit"), dict) else {}
    gates = research.get("gates") if isinstance(research.get("gates"), dict) else {}
    timing = gates.get("timing_alignment") if isinstance(gates.get("timing_alignment"), dict) else {}
    execution = gates.get("execution_realism") if isinstance(gates.get("execution_realism"), dict) else {}
    result_sanity = gates.get("result_sanity") if isinstance(gates.get("result_sanity"), dict) else {}
    return {
        "overall_status": str(research.get("overall_status") or ""),
        "timing_alignment": str(timing.get("status") or ""),
        "execution_realism": str(execution.get("status") or ""),
        "result_sanity": str(result_sanity.get("status") or ""),
    }


def _run_one(*, name: str, semantic_cfg: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    print(f"\n{'=' * 80}")
    print(name)
    print(f"{'=' * 80}")

    def progress(pct: int, message: str) -> None:
        print(f"  [{pct:3d}%] {message} ({time.perf_counter() - t0:.1f}s)")

    result = run_experiment_request({"preset": "single", "config_json": semantic_cfg, "fast_mode": True}, progress_hook=progress)
    results_dir = Path(str(result.get("results_dir") or ""))
    perf = _load_json(results_dir / "perf.json") if (results_dir / "perf.json").exists() else {}
    run_meta = _load_json(results_dir / "run_meta.json") if (results_dir / "run_meta.json").exists() else {}
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    trade_stats = _compute_trade_stats(results_dir / "portfolio_trades.csv")
    audit_flags = _load_audit_flags(results_dir)
    ranking = ((semantic_cfg.get("signal_generation") or {}).get("ranking") or {})
    trailing = ((semantic_cfg.get("exit_rules") or {}).get("trailing") or {})
    row = {
        "variant": name,
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
        "win_rate": float(trade_stats["win_rate"]),
        "profit_factor": float(trade_stats["profit_factor"]),
        "avg_hold_days": float(trade_stats["avg_hold_days"]),
        "avg_win": float(trade_stats["avg_win"]),
        "avg_loss": float(trade_stats["avg_loss"]),
        "top1_symbol_profit_share": float(trade_stats["top1_symbol_profit_share"]),
        "top3_month_profit_share": float(trade_stats["top3_month_profit_share"]),
        "audit_overall_status": str(audit_flags["overall_status"]),
        "timing_alignment": str(audit_flags["timing_alignment"]),
        "execution_realism": str(audit_flags["execution_realism"]),
        "result_sanity": str(audit_flags["result_sanity"]),
        "residual_window": int(ranking.get("residual_window", 60) or 60),
        "pre_profit_breakout_failure_enabled": bool(trailing.get("pre_profit_breakout_failure_enabled", False)),
        "pre_profit_breakout_failure_max_bars": int(trailing.get("pre_profit_breakout_failure_max_bars", 0) or 0),
        "pre_profit_breakout_failure_atr_buffer_k": float(trailing.get("pre_profit_breakout_failure_atr_buffer_k", 0.0) or 0.0),
    }
    print(
        "  CAGR={cagr:+.2%}  MaxDD={max_drawdown:.2%}  Sharpe={sharpe:.2f}  Trades={trades}  Audit={audit_overall_status}".format(
            **row
        )
    )
    return row


def _build_combo_cfg(base_cfg: dict[str, Any], *, atr_buffer_k: float) -> dict[str, Any]:
    combo = deepcopy(base_cfg)
    combo.setdefault("signal_generation", {}).setdefault("ranking", {})["residual_window"] = 40
    trailing = combo.setdefault("exit_rules", {}).setdefault("trailing", {})
    trailing["pre_profit_breakout_failure_enabled"] = True
    trailing["pre_profit_breakout_failure_max_bars"] = 5
    trailing["pre_profit_breakout_failure_atr_buffer_k"] = float(atr_buffer_k)
    combo.setdefault("flow_script", {})["description"] = (
        f"V9.3 residual_window=40 + pre-profit breakout failure exit max_bars=5 atr_buffer_k={atr_buffer_k:.1f}"
    )
    return combo


def _write_summary(
    *,
    out_dir: Path,
    base_meta: dict[str, Any],
    v93_meta: dict[str, Any],
    v94_meta: dict[str, Any],
    results: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(),
        "baseline_id": BASELINE_ID,
        "v93_id": V93_ID,
        "v94_id": V94_ID,
        "baseline_linked_exp_id": str(base_meta.get("linked_exp_id") or ""),
        "v93_linked_exp_id": str(v93_meta.get("linked_exp_id") or ""),
        "v94_linked_exp_id": str(v94_meta.get("linked_exp_id") or ""),
        "results": results,
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(results).to_csv(out_dir / "results.csv", index=False)


def main() -> None:
    base_cfg = _load_json(_baseline_cfg_path(BASELINE_ID))
    v93_cfg = _load_json(_baseline_cfg_path(V93_ID))
    v94_cfg = _load_json(_baseline_cfg_path(V94_ID))
    base_meta = _load_json(_baseline_meta_path(BASELINE_ID))
    v93_meta = _load_json(_baseline_meta_path(V93_ID))
    v94_meta = _load_json(_baseline_meta_path(V94_ID))

    _assert_v9_contract(base_cfg, baseline_id=BASELINE_ID)
    _assert_v9_contract(v93_cfg, baseline_id=V93_ID)
    _assert_v9_contract(v94_cfg, baseline_id=V94_ID)
    _assert_allowed_diffs(
        base_cfg=base_cfg,
        candidate_cfg=v93_cfg,
        allowed_paths=(("signal_generation", "ranking", "residual_window"),),
        label="V9.3 branch",
    )
    _assert_allowed_diffs(
        base_cfg=base_cfg,
        candidate_cfg=v94_cfg,
        allowed_paths=(
            ("exit_rules", "trailing", "pre_profit_breakout_failure_enabled"),
            ("exit_rules", "trailing", "pre_profit_breakout_failure_max_bars"),
            ("exit_rules", "trailing", "pre_profit_breakout_failure_atr_buffer_k"),
        ),
        ignored_paths=(("flow_script", "description"),),
        label="V9.4 branch",
    )

    combo_variants: list[tuple[str, dict[str, Any]]] = []
    for buffer_value in BUFFER_VALUES:
        cfg = _build_combo_cfg(base_cfg, atr_buffer_k=buffer_value)
        _assert_allowed_diffs(
            base_cfg=base_cfg,
            candidate_cfg=cfg,
            allowed_paths=(
                ("signal_generation", "ranking", "residual_window"),
                ("exit_rules", "trailing", "pre_profit_breakout_failure_enabled"),
                ("exit_rules", "trailing", "pre_profit_breakout_failure_max_bars"),
                ("exit_rules", "trailing", "pre_profit_breakout_failure_atr_buffer_k"),
            ),
            ignored_paths=(("flow_script", "description"),),
            label=f"combo buffer {buffer_value:.1f} branch",
        )
        combo_variants.append((f"V9_3_combo_atr_buffer_{buffer_value:.1f}", cfg))

    print("Audit: compare V9.1, frontend V9.3 fixed40, and combo branches with atr_buffer_k=0.7/0.5.")
    print("Audit: combo branches only add residual_window=40 plus pre-profit breakout failure exit on top of V9.1.")
    print("Audit: universe, PIT membership, benchmark, costs, execution, and all other contract items stay unchanged.")

    results = [
        _run_one(name="V9_1_baseline", semantic_cfg=base_cfg),
        _run_one(name="V9_3_fixed40", semantic_cfg=v93_cfg),
    ]
    for name, cfg in combo_variants:
        results.append(_run_one(name=name, semantic_cfg=cfg))

    out_dir = ROOT / "outputs" / "experiments" / f"{RESULT_PREFIX}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _write_summary(out_dir=out_dir, base_meta=base_meta, v93_meta=v93_meta, v94_meta=v94_meta, results=results)
    print(f"\nSummary written to: {out_dir}")


if __name__ == "__main__":
    main()
