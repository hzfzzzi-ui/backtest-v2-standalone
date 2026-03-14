from __future__ import annotations

import io
import json
import sys
import time
from copy import deepcopy
from dataclasses import dataclass
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
CANDIDATE_ID = "baseline_V9_3"
RESULT_PREFIX = "v9_3_conditional_short_cycle_validation"


@dataclass(frozen=True, slots=True)
class WindowSpec:
    label: str
    start: str
    end: str


@dataclass(frozen=True, slots=True)
class VariantSpec:
    name: str
    semantic_cfg: dict[str, Any]


WINDOWS: tuple[WindowSpec, ...] = (
    WindowSpec(label="2022_2026", start="2022-01-01", end="2026-03-01"),
    WindowSpec(label="2024_2026", start="2024-01-01", end="2026-03-01"),
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(dict(out[key]), value)
        else:
            out[key] = deepcopy(value)
    return out


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
        if len(base) != len(candidate):
            return [(path, base, candidate)]
        diffs: list[tuple[tuple[Any, ...], Any, Any]] = []
        for idx, (base_item, candidate_item) in enumerate(zip(base, candidate)):
            diffs.extend(_collect_diffs(base_item, candidate_item, path + (idx,)))
        return diffs
    if base != candidate:
        return [(path, base, candidate)]
    return []


def _assert_allowed_diffs(
    *,
    base_cfg: dict[str, Any],
    candidate_cfg: dict[str, Any],
    allowed_paths: tuple[tuple[Any, ...], ...],
    label: str,
) -> None:
    allowed = set(allowed_paths)
    unexpected = [diff for diff in _collect_diffs(base_cfg, candidate_cfg) if diff[0] not in allowed]
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


def _apply_window(cfg: dict[str, Any], window: WindowSpec) -> dict[str, Any]:
    out = deepcopy(cfg)
    out.setdefault("universe", {})["start"] = window.start
    out.setdefault("universe", {})["end"] = window.end
    return out


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
        return {"overall_status": "", "timing_alignment": "", "execution_realism": ""}
    audit = _load_json(audit_path)
    research = audit.get("research_audit") if isinstance(audit, dict) and isinstance(audit.get("research_audit"), dict) else {}
    gates = research.get("gates") if isinstance(research.get("gates"), dict) else {}
    timing = gates.get("timing_alignment") if isinstance(gates.get("timing_alignment"), dict) else {}
    execution = gates.get("execution_realism") if isinstance(gates.get("execution_realism"), dict) else {}
    return {
        "overall_status": str(research.get("overall_status") or ""),
        "timing_alignment": str(timing.get("status") or ""),
        "execution_realism": str(execution.get("status") or ""),
    }


def _run_one(*, variant: VariantSpec, window: WindowSpec) -> dict[str, Any]:
    t0 = time.perf_counter()
    print(f"\n{'=' * 80}")
    print(f"{variant.name} :: {window.label}")
    print(f"{'=' * 80}")

    def progress(pct: int, message: str) -> None:
        print(f"  [{pct:3d}%] {message} ({time.perf_counter() - t0:.1f}s)")

    semantic_cfg = _apply_window(variant.semantic_cfg, window)
    result = run_experiment_request({"preset": "single", "config_json": semantic_cfg, "fast_mode": True}, progress_hook=progress)
    results_dir = Path(str(result.get("results_dir") or ""))
    perf = _load_json(results_dir / "perf.json") if (results_dir / "perf.json").exists() else {}
    run_meta = _load_json(results_dir / "run_meta.json") if (results_dir / "run_meta.json").exists() else {}
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    trade_stats = _compute_trade_stats(results_dir / "portfolio_trades.csv")
    audit_flags = _load_audit_flags(results_dir)
    ranking = ((semantic_cfg.get("signal_generation") or {}).get("ranking") or {})
    metrics = {
        "variant": variant.name,
        "baseline_id": BASELINE_ID if variant.name == "V9_1_baseline" else CANDIDATE_ID,
        "window_label": window.label,
        "window_start": window.start,
        "window_end": window.end,
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
        "audit_overall_status": str(audit_flags["overall_status"]),
        "timing_alignment": str(audit_flags["timing_alignment"]),
        "execution_realism": str(audit_flags["execution_realism"]),
        "residual_window": int(ranking.get("residual_window", 60) or 60),
        "residual_window_regime_mode": str(ranking.get("residual_window_regime_mode", "OFF") or "OFF"),
        "residual_window_fallback": int(ranking.get("residual_window_fallback", ranking.get("residual_window", 60)) or ranking.get("residual_window", 60)),
        "residual_window_regime_fast_ma": int(ranking.get("residual_window_regime_fast_ma", 120) or 120),
        "residual_window_regime_slow_ma": int(ranking.get("residual_window_regime_slow_ma", 200) or 200),
    }
    print(
        "  CAGR={cagr:+.2%}  MaxDD={max_drawdown:.2%}  Sharpe={sharpe:.2f}  Trades={trades}  Audit={audit_overall_status}".format(
            **metrics
        )
    )
    return metrics


def _build_variants() -> tuple[list[VariantSpec], dict[str, Any], dict[str, Any]]:
    base_cfg = _load_json(_baseline_cfg_path(BASELINE_ID))
    candidate_cfg = _load_json(_baseline_cfg_path(CANDIDATE_ID))
    base_meta = _load_json(_baseline_meta_path(BASELINE_ID))
    candidate_meta = _load_json(_baseline_meta_path(CANDIDATE_ID))
    _assert_v9_contract(base_cfg, baseline_id=BASELINE_ID)
    _assert_v9_contract(candidate_cfg, baseline_id=CANDIDATE_ID)
    _assert_allowed_diffs(
        base_cfg=base_cfg,
        candidate_cfg=candidate_cfg,
        allowed_paths=(("signal_generation", "ranking", "residual_window"),),
        label="V9.3 candidate branch",
    )

    conditional_120_200 = _deep_merge(
        candidate_cfg,
        {
            "signal_generation": {
                "ranking": {
                    "residual_window_regime_mode": "STRONG_RISK_ON",
                    "residual_window_fallback": 60,
                }
            }
        },
    )
    _assert_allowed_diffs(
        base_cfg=candidate_cfg,
        candidate_cfg=conditional_120_200,
        allowed_paths=(
            ("signal_generation", "ranking", "residual_window_regime_mode"),
            ("signal_generation", "ranking", "residual_window_fallback"),
        ),
        label="V9.3 conditional 120/200 branch",
    )

    conditional_20_60 = _deep_merge(
        conditional_120_200,
        {
            "signal_generation": {
                "ranking": {
                    "residual_window_regime_fast_ma": 20,
                    "residual_window_regime_slow_ma": 60,
                }
            }
        },
    )
    _assert_allowed_diffs(
        base_cfg=conditional_120_200,
        candidate_cfg=conditional_20_60,
        allowed_paths=(
            ("signal_generation", "ranking", "residual_window_regime_fast_ma"),
            ("signal_generation", "ranking", "residual_window_regime_slow_ma"),
        ),
        label="V9.3 conditional 20/60 branch",
    )

    variants = [
        VariantSpec(name="V9_1_baseline", semantic_cfg=base_cfg),
        VariantSpec(name="V9_3_conditional_120_200", semantic_cfg=conditional_120_200),
        VariantSpec(name="V9_3_conditional_20_60", semantic_cfg=conditional_20_60),
    ]
    return variants, base_meta, candidate_meta


def _write_summary(
    *,
    out_dir: Path,
    base_meta: dict[str, Any],
    candidate_meta: dict[str, Any],
    results: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": datetime.now().isoformat(),
        "baseline_id": BASELINE_ID,
        "candidate_id": CANDIDATE_ID,
        "baseline_linked_exp_id": str(base_meta.get("linked_exp_id") or ""),
        "candidate_linked_exp_id": str(candidate_meta.get("linked_exp_id") or ""),
        "results": results,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(results).to_csv(out_dir / "results.csv", index=False)


def main() -> None:
    variants, base_meta, candidate_meta = _build_variants()
    print("Audit: short-cycle windows are rerun independently by overwriting universe.start/end.")
    print("Audit: the only A/B main change inside conditional V9.3 is regime MA definition: 120/200 vs 20/60.")
    print("Audit: universe, PIT membership, benchmark, costs, execution, and exits stay unchanged.")

    results: list[dict[str, Any]] = []
    for window in WINDOWS:
        for variant in variants:
            results.append(_run_one(variant=variant, window=window))

    results.sort(key=lambda item: (str(item["window_label"]), str(item["variant"])))
    out_dir = ROOT / "outputs" / "experiments" / f"{RESULT_PREFIX}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _write_summary(out_dir=out_dir, base_meta=base_meta, candidate_meta=candidate_meta, results=results)
    print(f"\nSummary written to: {out_dir}")


if __name__ == "__main__":
    main()
