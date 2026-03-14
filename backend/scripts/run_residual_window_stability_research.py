from __future__ import annotations

import argparse
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
from backend.core.tools.experiment_runner import _recompute_perf_from_daily  # noqa: E402


BASELINE_ID = "baseline_V9_1"
BASELINE_INDEX_PATH = ROOT / "outputs" / "baselines" / "index.json"
RESULT_PREFIX = "residual_window_stability_research"
ALLOWED_DIFF_PATHS = (("signal_generation", "ranking", "residual_window"),)


@dataclass(frozen=True, slots=True)
class VariantSpec:
    name: str
    patch: dict[str, Any]


DEFAULT_WINDOWS: tuple[int, ...] = (60, 50, 40)


def _parse_windows(argv: list[str]) -> tuple[int, ...]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--windows", default="60,50,40")
    args, _ = parser.parse_known_args(argv[1:])
    raw_items = [item.strip() for item in str(args.windows or "").split(",")]
    windows: list[int] = []
    for item in raw_items:
        if not item:
            continue
        value = int(item)
        if value < 2:
            raise ValueError(f"invalid residual_window: {value}")
        if value not in windows:
            windows.append(value)
    if not windows:
        return DEFAULT_WINDOWS
    return tuple(windows)


def _build_variants(windows: tuple[int, ...]) -> tuple[VariantSpec, ...]:
    variants: list[VariantSpec] = []
    for window in windows:
        if int(window) == 60:
            variants.append(VariantSpec(name="baseline", patch={}))
            continue
        variants.append(
            VariantSpec(
                name=f"residual_window_{int(window)}",
                patch={"signal_generation": {"ranking": {"residual_window": int(window)}}},
            )
        )
    return tuple(variants)


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


def _build_variant_cfg(base_cfg: dict[str, Any], variant: VariantSpec) -> dict[str, Any]:
    candidate_cfg = _deep_merge(base_cfg, variant.patch)
    _assert_allowed_diffs(base_cfg, candidate_cfg, allowed_paths=ALLOWED_DIFF_PATHS)
    return candidate_cfg


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


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
    win_rate = len(wins) / len(closed_pnls) if closed_pnls else 0.0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 1e-12 else 0.0
    avg_hold_days = hold_qty_days / hold_qty_total if hold_qty_total > 1e-12 else 0.0
    avg_win = gross_profit / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    top1_symbol_profit_share = (
        max(symbol_profit.values()) / gross_profit if gross_profit > 1e-12 and symbol_profit else 0.0
    )
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


def _load_audit_flags(results_dir: Path) -> dict[str, str]:
    audit_path = results_dir / "audit.json"
    if not audit_path.exists():
        return {"overall_status": "", "timing_alignment": "", "execution_realism": ""}
    audit = _load_json(audit_path)
    if not isinstance(audit, dict):
        return {"overall_status": "", "timing_alignment": "", "execution_realism": ""}
    checks = audit.get("checks") if isinstance(audit.get("checks"), dict) else {}
    timing = checks.get("timing_alignment") if isinstance(checks.get("timing_alignment"), dict) else {}
    execution = checks.get("execution_realism") if isinstance(checks.get("execution_realism"), dict) else {}
    research = audit.get("research_audit") if isinstance(audit.get("research_audit"), dict) else {}
    return {
        "overall_status": str(research.get("overall_status") or ""),
        "timing_alignment": str(timing.get("status") or ""),
        "execution_realism": str(execution.get("status") or ""),
    }


def _normalize_daily(results_dir: Path) -> pd.DataFrame:
    daily = _safe_read_csv(results_dir / "portfolio_daily.csv")
    if daily.empty or "date" not in daily.columns:
        return pd.DataFrame()
    df = daily.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date"]).sort_values("date")
    return df.reset_index(drop=True)


def _load_effective_execution_start(results_dir: Path) -> str:
    perf_path = results_dir / "perf.json"
    if perf_path.exists():
        perf = _load_json(perf_path)
        if isinstance(perf, dict):
            text = str(perf.get("effective_execution_start_date") or "").strip()
            if text:
                return text
    run_meta_path = results_dir / "run_meta.json"
    if run_meta_path.exists():
        run_meta = _load_json(run_meta_path)
        warmup = run_meta.get("warmup") if isinstance(run_meta, dict) and isinstance(run_meta.get("warmup"), dict) else {}
        text = str(warmup.get("effective_execution_start_date") or "").strip()
        if text:
            return text
    return ""


def _recompute_aligned_metrics(results_dir: Path, effective_start: str) -> dict[str, Any]:
    df = _normalize_daily(results_dir)
    if df.empty or not effective_start:
        return {
            "aligned_total_return": 0.0,
            "aligned_cagr": 0.0,
            "aligned_max_drawdown": 0.0,
            "aligned_sharpe": 0.0,
            "aligned_calmar": 0.0,
            "aligned_observation_days": 0,
        }
    metrics = _recompute_perf_from_daily(df, effective_start)
    return {
        "aligned_total_return": float(metrics.get("total_return", 0.0) or 0.0),
        "aligned_cagr": float(metrics.get("cagr", 0.0) or 0.0),
        "aligned_max_drawdown": float(metrics.get("max_drawdown", 0.0) or 0.0),
        "aligned_sharpe": float(metrics.get("sharpe", 0.0) or 0.0),
        "aligned_calmar": float(metrics.get("calmar", 0.0) or 0.0),
        "aligned_observation_days": int(metrics.get("effective_observation_days", 0) or 0),
    }


def _compute_period_metrics(results_dir: Path, start_date: str, end_date: str) -> dict[str, Any]:
    df = _normalize_daily(results_dir)
    if df.empty:
        return {
            "period_total_return": 0.0,
            "period_cagr": 0.0,
            "period_max_drawdown": 0.0,
            "period_sharpe": 0.0,
            "period_calmar": 0.0,
            "period_observation_days": 0,
            "avg_positions": 0.0,
            "avg_turnover_pct": 0.0,
        }

    start_ts = pd.Timestamp(start_date).normalize()
    end_ts = pd.Timestamp(end_date).normalize()
    window = df.loc[(df["date"] >= start_ts) & (df["date"] <= end_ts)].copy()
    if window.empty:
        return {
            "period_total_return": 0.0,
            "period_cagr": 0.0,
            "period_max_drawdown": 0.0,
            "period_sharpe": 0.0,
            "period_calmar": 0.0,
            "period_observation_days": 0,
            "avg_positions": 0.0,
            "avg_turnover_pct": 0.0,
        }

    metrics = _recompute_perf_from_daily(window, start_ts.strftime("%Y-%m-%d"))
    positions_col = "positions_count_end_of_day" if "positions_count_end_of_day" in window.columns else "positions_count"
    avg_positions = (
        float(pd.to_numeric(window[positions_col], errors="coerce").fillna(0.0).mean()) if positions_col in window.columns else 0.0
    )
    avg_turnover_pct = (
        float(pd.to_numeric(window["turnover_pct"], errors="coerce").fillna(0.0).mean()) if "turnover_pct" in window.columns else 0.0
    )
    return {
        "period_total_return": float(metrics.get("total_return", 0.0) or 0.0),
        "period_cagr": float(metrics.get("cagr", 0.0) or 0.0),
        "period_max_drawdown": float(metrics.get("max_drawdown", 0.0) or 0.0),
        "period_sharpe": float(metrics.get("sharpe", 0.0) or 0.0),
        "period_calmar": float(metrics.get("calmar", 0.0) or 0.0),
        "period_observation_days": int(metrics.get("effective_observation_days", 0) or 0),
        "avg_positions": float(avg_positions),
        "avg_turnover_pct": float(avg_turnover_pct),
    }


def _compute_calendar_year_returns(results_dir: Path, effective_start: str) -> list[dict[str, Any]]:
    df = _normalize_daily(results_dir)
    if df.empty or not effective_start:
        return []
    start_ts = pd.Timestamp(effective_start).normalize()
    df = df.loc[df["date"] >= start_ts].copy()
    if df.empty or "nav" not in df.columns:
        return []
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df = df.dropna(subset=["nav"])
    if df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for year, year_df in df.groupby(df["date"].dt.year):
        year_df = year_df.sort_values("date")
        nav0 = float(year_df["nav"].iloc[0])
        nav1 = float(year_df["nav"].iloc[-1])
        year_ret = (nav1 / nav0 - 1.0) if nav0 > 0 else 0.0
        peak = year_df["nav"].cummax()
        year_dd = float((year_df["nav"] / peak - 1.0).min()) if not year_df.empty else 0.0
        rows.append(
            {
                "year": int(year),
                "year_total_return": float(year_ret),
                "year_max_drawdown": float(year_dd),
                "year_days": int(len(year_df)),
            }
        )
    return rows


def _compute_year_stability(year_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not year_rows:
        return {
            "positive_years": 0,
            "negative_years": 0,
            "top3_positive_year_share": 0.0,
            "worst_year_return": 0.0,
            "best_year_return": 0.0,
        }
    returns = [float(row.get("year_total_return", 0.0) or 0.0) for row in year_rows]
    positive = [x for x in returns if x > 0]
    negative = [x for x in returns if x < 0]
    top3_share = sum(sorted(positive, reverse=True)[:3]) / sum(positive) if positive and sum(positive) > 1e-12 else 0.0
    return {
        "positive_years": int(len(positive)),
        "negative_years": int(len(negative)),
        "top3_positive_year_share": float(top3_share),
        "worst_year_return": float(min(returns)),
        "best_year_return": float(max(returns)),
    }


def _run_one(*, variant: VariantSpec, semantic_cfg: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    print(f"\n{'=' * 80}")
    print(f"residual_window_stability :: {variant.name}")
    print(f"{'=' * 80}")

    def progress(pct: int, message: str) -> None:
        elapsed = time.perf_counter() - t0
        print(f"  [{pct:3d}%] {message} ({elapsed:.1f}s)")

    result = run_experiment_request({"preset": "single", "config_json": semantic_cfg, "fast_mode": True}, progress_hook=progress)
    results_dir = Path(str(result.get("results_dir") or ""))
    perf = _load_json(results_dir / "perf.json") if (results_dir / "perf.json").exists() else {}
    run_meta = _load_json(results_dir / "run_meta.json") if (results_dir / "run_meta.json").exists() else {}
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    trade_stats = _compute_trade_stats(results_dir / "portfolio_trades.csv")
    audit_flags = _load_audit_flags(results_dir)
    effective_execution_start_date = _load_effective_execution_start(results_dir)

    metrics = {
        "variant": variant.name,
        "exp_id": str(result.get("exp_id") or ""),
        "results_dir": str(results_dir),
        "residual_window": (
            int(((semantic_cfg.get("signal_generation") or {}).get("ranking") or {}).get("residual_window", 60) or 60)
        ),
        "raw_total_return": float(perf.get("total_return", result.get("total_return", 0.0)) or 0.0),
        "raw_cagr": float(perf.get("cagr", result.get("cagr", 0.0)) or 0.0),
        "raw_max_drawdown": float(perf.get("max_drawdown", result.get("max_drawdown", 0.0)) or 0.0),
        "raw_sharpe": float(perf.get("sharpe", result.get("sharpe", 0.0)) or 0.0),
        "raw_calmar": float(perf.get("calmar", result.get("calmar", 0.0)) or 0.0),
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
        "effective_execution_start_date": effective_execution_start_date,
        "audit_overall_status": str(audit_flags["overall_status"]),
        "timing_alignment": str(audit_flags["timing_alignment"]),
        "execution_realism": str(audit_flags["execution_realism"]),
    }
    print(
        "  raw_CAGR={raw_cagr:+.2%}  raw_MaxDD={raw_max_drawdown:.2%}  raw_Sharpe={raw_sharpe:.2f}  "
        "Trades={trades}  Audit={audit_overall_status}/{timing_alignment}/{execution_realism}".format(**metrics)
    )
    return metrics


def _period_specs(common_start: str, end_date: str) -> list[tuple[str, str, str]]:
    return [
        ("2016_2018", max(common_start, "2016-01-01"), "2018-12-31"),
        ("2019_2021", "2019-01-01", "2021-12-31"),
        ("2022_2026", "2022-01-01", end_date),
    ]


def _write_summary(
    *,
    out_dir: Path,
    baseline_entry: dict[str, Any],
    semantic_cfg_path: Path,
    base_cfg: dict[str, Any],
    results: list[dict[str, Any]],
    period_rows: list[dict[str, Any]],
    year_rows: list[dict[str, Any]],
    common_effective_start_date: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "baseline_id": str(baseline_entry.get("baseline_id") or BASELINE_ID),
        "baseline_linked_exp_id": str(baseline_entry.get("linked_exp_id") or ""),
        "baseline_semantic_config_path": str(semantic_cfg_path),
        "common_effective_start_date": common_effective_start_date,
        "main_change_path": "signal_generation.ranking.residual_window",
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
        "period_results": period_rows,
        "calendar_year_results": year_rows,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(results).to_csv(out_dir / "overall_results.csv", index=False)
    pd.DataFrame(period_rows).to_csv(out_dir / "period_results.csv", index=False)
    pd.DataFrame(year_rows).to_csv(out_dir / "calendar_year_results.csv", index=False)

    lines = [
        "# V9.1 Residual Window Stability Research",
        "",
        f"- baseline_id: `{summary['baseline_id']}`",
        f"- baseline_linked_exp_id: `{summary['baseline_linked_exp_id']}`",
        f"- common_effective_start_date: `{common_effective_start_date}`",
        "- anchor_note: `V9.1 remains the formal baseline; this study checks only residual_window local stability.`",
        "",
        "## Overall",
        "",
        "| variant | residual_window | aligned_CAGR | aligned_MaxDD | aligned_Sharpe | aligned_Calmar | trades | win_rate | top1_stock_profit | top3_month_profit | audit | exp_id |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in results:
        lines.append(
            "| {variant} | {residual_window} | {aligned_cagr:.2%} | {aligned_max_drawdown:.2%} | {aligned_sharpe:.2f} | "
            "{aligned_calmar:.2f} | {trades} | {win_rate:.2%} | {top1_symbol_profit_share:.2%} | {top3_month_profit_share:.2%} | "
            "{audit_overall_status}/{timing_alignment}/{execution_realism} | `{exp_id}` |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Subperiods",
            "",
            "| variant | period | total_return | CAGR | MaxDD | Sharpe | Calmar | obs_days | avg_positions | avg_turnover_pct |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in period_rows:
        lines.append(
            "| {variant} | {period} | {period_total_return:.2%} | {period_cagr:.2%} | {period_max_drawdown:.2%} | "
            "{period_sharpe:.2f} | {period_calmar:.2f} | {period_observation_days} | {avg_positions:.2f} | {avg_turnover_pct:.2%} |".format(
                **row
            )
        )
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    variants = _build_variants(_parse_windows(sys.argv))
    baseline_entry, semantic_cfg_path = _baseline_paths()
    base_cfg = _load_json(semantic_cfg_path)
    _assert_baseline_contract(base_cfg, baseline_entry)

    print("Audit: anchor baseline is V9.1 by the report; only residual_window is allowed to change.")
    print("Audit: universe, benchmark, costs, execution, and exit rules remain untouched in every variant.")
    print("Audit: all variants still use day-t close features and next-trading-day open execution.")
    print("Run windows: " + ", ".join(str(int(((variant.patch.get('signal_generation') or {}).get('ranking') or {}).get('residual_window', 60))) for variant in variants))

    results: list[dict[str, Any]] = []
    for variant in variants:
        semantic_cfg = _build_variant_cfg(base_cfg, variant)
        results.append(_run_one(variant=variant, semantic_cfg=semantic_cfg))

    effective_starts = [
        pd.Timestamp(str(row["effective_execution_start_date"])).normalize()
        for row in results
        if str(row.get("effective_execution_start_date") or "").strip()
    ]
    common_effective_start_date = max(effective_starts).strftime("%Y-%m-%d") if effective_starts else ""
    if common_effective_start_date:
        print(f"\nAligned comparison start date: {common_effective_start_date}")
    else:
        print("\nAligned comparison start date: <missing>")

    for row in results:
        row.update(_recompute_aligned_metrics(Path(str(row["results_dir"])), common_effective_start_date))

    end_date = str((base_cfg.get("universe") or {}).get("end") or "")
    period_rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    for row in results:
        result_dir = Path(str(row["results_dir"]))
        for period_name, period_start, period_end in _period_specs(common_effective_start_date, end_date):
            metrics = _compute_period_metrics(result_dir, period_start, period_end)
            period_rows.append(
                {
                    "variant": str(row["variant"]),
                    "residual_window": int(row["residual_window"]),
                    "period": period_name,
                    "period_start": period_start,
                    "period_end": period_end,
                    **metrics,
                }
            )
        year_values = _compute_calendar_year_returns(result_dir, common_effective_start_date)
        year_rows.extend(
            {
                "variant": str(row["variant"]),
                "residual_window": int(row["residual_window"]),
                **item,
            }
            for item in year_values
        )
        row.update(_compute_year_stability(year_values))

    results = sorted(results, key=lambda item: int(item["residual_window"]))
    period_rows = sorted(period_rows, key=lambda item: (int(item["residual_window"]), str(item["period"])))
    year_rows = sorted(year_rows, key=lambda item: (int(item["residual_window"]), int(item["year"])))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "outputs" / "experiments" / f"{RESULT_PREFIX}_{stamp}"
    _write_summary(
        out_dir=out_dir,
        baseline_entry=baseline_entry,
        semantic_cfg_path=semantic_cfg_path,
        base_cfg=base_cfg,
        results=results,
        period_rows=period_rows,
        year_rows=year_rows,
        common_effective_start_date=common_effective_start_date,
    )
    print(f"\nSummary written to: {out_dir}")


if __name__ == "__main__":
    main()
