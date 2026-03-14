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
BASELINE_INDEX_PATH = ROOT / "outputs" / "baselines" / "index.json"
RESULT_PREFIX = "residual_alpha_refinement_research"


@dataclass(frozen=True, slots=True)
class VariantSpec:
    name: str
    patch: dict[str, Any]


@dataclass(frozen=True, slots=True)
class StudySpec:
    study_id: str
    hypothesis: str
    allowed_diff_paths: tuple[tuple[Any, ...], ...]
    variants: tuple[VariantSpec, ...]


STUDIES: tuple[StudySpec, ...] = (
    StudySpec(
        study_id="direction1_residual_tail_breakout_margin",
        hypothesis=(
            "在 residual_only 主排序不变的前提下，仅对同日 breakout 候选加入小权重 breakout_margin 次级排序，"
            "检验 residual 顶部尾部是否存在可被突破质量进一步分辨的空间。"
        ),
        allowed_diff_paths=(
            ("signal_generation", "ranking", "residual_refine_mode"),
            ("signal_generation", "ranking", "residual_refine_weight"),
        ),
        variants=(
            VariantSpec(name="baseline", patch={}),
            VariantSpec(
                name="breakout_margin_refine_w15",
                patch={
                    "signal_generation": {
                        "ranking": {
                            "residual_refine_mode": "breakout_margin",
                            "residual_refine_weight": 0.15,
                        }
                    }
                },
            ),
        ),
    ),
    StudySpec(
        study_id="direction2_residual_window_40",
        hypothesis=(
            "A 股主线切换较快时，60 日 residual 可能偏慢；将 residual lookback 缩短到 40 日，"
            "检验更快的 alpha 记忆是否改善排序效率。"
        ),
        allowed_diff_paths=(("signal_generation", "ranking", "residual_window"),),
        variants=(
            VariantSpec(name="baseline", patch={}),
            VariantSpec(
                name="residual_window_40",
                patch={"signal_generation": {"ranking": {"residual_window": 40}}},
            ),
        ),
    ),
)


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


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = deepcopy(value)
    return merged


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


def _assert_allowed_diffs(
    base_cfg: dict[str, Any],
    candidate_cfg: dict[str, Any],
    *,
    allowed_paths: tuple[tuple[Any, ...], ...],
) -> None:
    diffs = _collect_diffs(base_cfg, candidate_cfg)
    allowed = set(allowed_paths)
    unexpected = [diff for diff in diffs if diff[0] not in allowed]
    if unexpected:
        lines = []
        for diff_path, base_value, candidate_value in unexpected[:10]:
            lines.append(f"{_path_text(diff_path)}: baseline={base_value!r}, candidate={candidate_value!r}")
        raise RuntimeError("variant drifted beyond the allowed main change:\n" + "\n".join(lines))


def _build_variant_cfg(base_cfg: dict[str, Any], study: StudySpec, variant: VariantSpec) -> dict[str, Any]:
    candidate_cfg = _deep_merge(base_cfg, variant.patch)
    _assert_allowed_diffs(base_cfg, candidate_cfg, allowed_paths=study.allowed_diff_paths)
    return candidate_cfg


def _assert_baseline_contract(base_cfg: dict[str, Any], baseline_entry: dict[str, Any]) -> None:
    strategy_name = str((base_cfg.get("signal_generation") or {}).get("strategy") or "").strip().upper()
    if strategy_name != "BREAKOUT_TREND":
        raise RuntimeError(f"expected BREAKOUT_TREND baseline, got {strategy_name!r}")
    if str(baseline_entry.get("universe_mode") or "") != "HS300_ZZ500":
        raise RuntimeError("baseline universe_mode is not HS300_ZZ500")
    if str((base_cfg.get("universe") or {}).get("benchmark") or "") != "000300.SH":
        raise RuntimeError("baseline benchmark is not 000300.SH")
    if str((base_cfg.get("universe") or {}).get("membership_mode") or "") != "PIT_DYNAMIC":
        raise RuntimeError("baseline membership_mode is not PIT_DYNAMIC")

    breakout = (base_cfg.get("signal_generation") or {}).get("breakout") or {}
    ranking = (base_cfg.get("signal_generation") or {}).get("ranking") or {}
    trailing = (base_cfg.get("exit_rules") or {}).get("trailing") or {}
    if int(breakout.get("breakout_window", 0) or 0) != 45:
        raise RuntimeError("expected V9.1 baseline breakout_window=45")
    if abs(float(breakout.get("breakout_entry_buffer_pct", 0.0) or 0.0)) > 1e-12:
        raise RuntimeError("expected V9.1 baseline breakout_entry_buffer_pct=0.0")
    if str(ranking.get("score_source_mode") or "").strip().lower() != "residual_only":
        raise RuntimeError("expected V9.1 baseline score_source_mode=residual_only")
    if "residual_window" in ranking:
        raise RuntimeError("expected V9.1 baseline to omit ranking.residual_window override")
    if "residual_refine_mode" in ranking or "residual_refine_weight" in ranking:
        raise RuntimeError("expected V9.1 baseline to omit residual refine controls")
    if abs(float(trailing.get("activate_profit_pct", 0.0) or 0.0) - 0.15) > 1e-12:
        raise RuntimeError("expected V9.1 baseline trailing.activate_profit_pct=0.15")
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


def _compute_candidate_stats(results_dir: Path) -> dict[str, float]:
    path = results_dir / "portfolio_candidates.csv"
    if not path.exists():
        return {
            "candidate_rows": 0.0,
            "selected_rows": 0.0,
            "selected_residual_median": 0.0,
            "selected_breakout_margin_median": 0.0,
        }
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return {
            "candidate_rows": 0.0,
            "selected_rows": 0.0,
            "selected_residual_median": 0.0,
            "selected_breakout_margin_median": 0.0,
        }
    if df.empty:
        return {
            "candidate_rows": 0.0,
            "selected_rows": 0.0,
            "selected_residual_median": 0.0,
            "selected_breakout_margin_median": 0.0,
        }
    selected = df.copy()
    if "selected_flag" in selected.columns:
        selected = selected[selected["selected_flag"].astype(bool)]
    elif "selected" in selected.columns:
        selected = selected[selected["selected"].astype(bool)]
    residual_median = 0.0
    breakout_margin_median = 0.0
    if not selected.empty and "residual_strength_score" in selected.columns:
        residual_series = pd.to_numeric(selected["residual_strength_score"], errors="coerce").dropna()
        if not residual_series.empty:
            residual_median = float(residual_series.median())
    if not selected.empty and "breakout_margin_raw" in selected.columns:
        breakout_series = pd.to_numeric(selected["breakout_margin_raw"], errors="coerce").dropna()
        if not breakout_series.empty:
            breakout_margin_median = float(breakout_series.median())
    return {
        "candidate_rows": float(len(df)),
        "selected_rows": float(len(selected)),
        "selected_residual_median": float(residual_median),
        "selected_breakout_margin_median": float(breakout_margin_median),
    }


def _load_audit_flags(results_dir: Path) -> dict[str, str]:
    audit_path = results_dir / "audit.json"
    if not audit_path.exists():
        return {"timing_alignment": "", "execution_realism": ""}
    audit = _load_json(audit_path)
    if not isinstance(audit, dict):
        return {"timing_alignment": "", "execution_realism": ""}
    checks = audit.get("checks") if isinstance(audit.get("checks"), dict) else {}
    timing = checks.get("timing_alignment") if isinstance(checks.get("timing_alignment"), dict) else {}
    execution = checks.get("execution_realism") if isinstance(checks.get("execution_realism"), dict) else {}
    return {
        "timing_alignment": str(timing.get("status") or ""),
        "execution_realism": str(execution.get("status") or ""),
    }


def _run_one(*, study: StudySpec, variant: VariantSpec, semantic_cfg: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    print(f"\n{'=' * 80}")
    print(f"{study.study_id} :: {variant.name}")
    print(f"{'=' * 80}")

    def progress(pct: int, message: str) -> None:
        elapsed = time.perf_counter() - t0
        print(f"  [{pct:3d}%] {message} ({elapsed:.1f}s)")

    result = run_experiment_request({"preset": "single", "config_json": semantic_cfg, "fast_mode": True}, progress_hook=progress)
    results_dir = Path(str(result.get("results_dir") or ""))
    perf = _load_json(results_dir / "perf.json") if (results_dir / "perf.json").exists() else {}
    run_meta = _load_json(results_dir / "run_meta.json") if (results_dir / "run_meta.json").exists() else {}
    trade_stats = _compute_trade_stats(results_dir / "portfolio_trades.csv")
    candidate_stats = _compute_candidate_stats(results_dir)
    audit_flags = _load_audit_flags(results_dir)
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}

    metrics = {
        "study_id": study.study_id,
        "hypothesis": study.hypothesis,
        "variant": variant.name,
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
        "candidate_rows": float(candidate_stats["candidate_rows"]),
        "selected_rows": float(candidate_stats["selected_rows"]),
        "selected_residual_median": float(candidate_stats["selected_residual_median"]),
        "selected_breakout_margin_median": float(candidate_stats["selected_breakout_margin_median"]),
        "timing_alignment": str(audit_flags["timing_alignment"]),
        "execution_realism": str(audit_flags["execution_realism"]),
    }
    print(
        "  CAGR={cagr:+.2%}  MaxDD={max_drawdown:.2%}  Sharpe={sharpe:.2f}  "
        "Trades={trades}  AvgPos={avg_positions:.2f}  Audit={timing_alignment}/{execution_realism}".format(**metrics)
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
        "unchanged_contract": {
            "benchmark": str((base_cfg.get("universe") or {}).get("benchmark") or ""),
            "start": str((base_cfg.get("universe") or {}).get("start") or ""),
            "end": str((base_cfg.get("universe") or {}).get("end") or ""),
            "membership_mode": str((base_cfg.get("universe") or {}).get("membership_mode") or ""),
            "costs": base_cfg.get("costs") or {},
            "execution": base_cfg.get("execution") or {},
            "benchmark_regime": base_cfg.get("benchmark_regime") or {},
        },
        "results": results,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# V9.1 Residual Alpha Refinement Research",
        "",
        f"- baseline_id: `{summary['baseline_id']}`",
        f"- baseline_linked_exp_id: `{summary['baseline_linked_exp_id']}`",
        "- anchor_note: `V9.2 exists only as extended validation; V9.1 remains the formal baseline in the report.`",
        "",
        "| study | variant | CAGR | MaxDD | Sharpe | Calmar | Trades | WinRate | Top1StockProfit | Top3MonthProfit | Audit | exp_id |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in results:
        lines.append(
            "| {study_id} | {variant} | {cagr:.2%} | {max_drawdown:.2%} | {sharpe:.2f} | {calmar:.2f} | "
            "{trades} | {win_rate:.2%} | {top1_symbol_profit_share:.2%} | {top3_month_profit_share:.2%} | "
            "{timing_alignment}/{execution_realism} | `{exp_id}` |".format(**row)
        )
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    baseline_entry, semantic_cfg_path = _baseline_paths()
    base_cfg = _load_json(semantic_cfg_path)
    _assert_baseline_contract(base_cfg, baseline_entry)

    print("Audit: anchor baseline is V9.1 by the report; V9.2 is treated only as extended validation.")
    print("Audit: universe, costs, benchmark_regime, execution, and exit rules remain untouched in every variant.")
    print("Audit: all variants still use day-t close features and next-trading-day open execution.")

    results: list[dict[str, Any]] = []
    baseline_cache: dict[str, Any] | None = None
    for study in STUDIES:
        print(f"\nStudy: {study.study_id}")
        print(f"Hypothesis: {study.hypothesis}")
        for variant in study.variants:
            if variant.name == "baseline":
                if baseline_cache is None:
                    baseline_cfg = _build_variant_cfg(base_cfg, study, variant)
                    baseline_cache = _run_one(study=study, variant=variant, semantic_cfg=baseline_cfg)
                results.append(dict(baseline_cache, study_id=study.study_id, hypothesis=study.hypothesis))
                continue
            semantic_cfg = _build_variant_cfg(base_cfg, study, variant)
            results.append(_run_one(study=study, variant=variant, semantic_cfg=semantic_cfg))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "outputs" / "experiments" / f"{RESULT_PREFIX}_{stamp}"
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
