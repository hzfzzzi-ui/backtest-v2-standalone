from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.tools.experiment_runner import (
    _compute_effective_warmup_analysis,
    _recompute_perf_from_daily,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _results_root() -> Path:
    return (_repo_root() / "outputs").resolve()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _rewrite_nav_csv(exp_dir: Path, effective_execution_start_date: str) -> None:
    daily_path = exp_dir / "portfolio_daily.csv"
    if not daily_path.exists():
        return
    df = pd.read_csv(daily_path)
    if df.empty or "date" not in df.columns or "nav" not in df.columns:
        return
    dates = pd.to_datetime(df["date"], errors="coerce")
    nav = pd.to_numeric(df["nav"], errors="coerce")
    out_df = pd.DataFrame({"date": dates.dt.strftime("%Y-%m-%d"), "nav": nav}).dropna(subset=["date", "nav"])
    if effective_execution_start_date:
        cutoff = pd.Timestamp(effective_execution_start_date).normalize()
        out_df = out_df.loc[pd.to_datetime(out_df["date"], errors="coerce").dt.normalize() >= cutoff].copy()
    if out_df.empty:
        return
    nav0 = float(pd.to_numeric(out_df["nav"], errors="coerce").iloc[0])
    if nav0 > 0:
        out_df["nav"] = pd.to_numeric(out_df["nav"], errors="coerce") / nav0
    out_df.to_csv(exp_dir / "nav.csv", index=False)


def _rewrite_experiment(exp_dir: Path) -> dict[str, Any] | None:
    run_cfg_path = exp_dir / "run_config.json"
    daily_path = exp_dir / "portfolio_daily.csv"
    perf_path = exp_dir / "perf.json"
    run_meta_path = exp_dir / "run_meta.json"
    manifest_path = exp_dir / "manifest.json"
    if not run_cfg_path.exists() or not daily_path.exists():
        return None

    cfg = _load_json(run_cfg_path)
    daily_df = pd.read_csv(daily_path)
    if daily_df.empty or "date" not in daily_df.columns:
        return None

    trading_days = [d.date() for d in pd.to_datetime(daily_df["date"], errors="coerce").dropna()]
    if not trading_days:
        return None

    warmup = _compute_effective_warmup_analysis(cfg, trading_days, daily_df)
    effective_execution_start_date = str(warmup.get("effective_execution_start_date") or "")
    perf_metrics = _recompute_perf_from_daily(daily_df, effective_execution_start_date)

    perf_payload = _load_json(perf_path) if perf_path.exists() else {}
    perf_payload.update(
        {
            "total_return": perf_metrics.get("total_return"),
            "max_drawdown": perf_metrics.get("max_drawdown"),
            "cagr": perf_metrics.get("cagr"),
            "sharpe": perf_metrics.get("sharpe"),
            "calmar": perf_metrics.get("calmar"),
            "candidate_ready_date": warmup.get("candidate_ready_date"),
            "effective_signal_start_date": warmup.get("effective_signal_start_date"),
            "effective_execution_start_date": effective_execution_start_date,
            "metrics_from_effective_start": True,
            "effective_observation_days": perf_metrics.get("effective_observation_days"),
        }
    )
    _write_json(perf_path, perf_payload)

    if run_meta_path.exists():
        run_meta = _load_json(run_meta_path)
        run_meta["warmup"] = warmup
        _write_json(run_meta_path, run_meta)

    if manifest_path.exists():
        manifest = _load_json(manifest_path)
        metrics = dict(manifest.get("metrics") or {})
        metrics.update(
            {
                "total_return": perf_metrics.get("total_return"),
                "max_drawdown": perf_metrics.get("max_drawdown"),
                "cagr": perf_metrics.get("cagr"),
                "sharpe": perf_metrics.get("sharpe"),
                "calmar": perf_metrics.get("calmar"),
                "effective_execution_start_date": effective_execution_start_date,
                "metrics_from_effective_start": True,
            }
        )
        manifest["metrics"] = metrics
        _write_json(manifest_path, manifest)

    _rewrite_nav_csv(exp_dir, effective_execution_start_date)

    return {
        "exp_id": exp_dir.name,
        "candidate_ready_date": warmup.get("candidate_ready_date"),
        "effective_signal_start_date": warmup.get("effective_signal_start_date"),
        "effective_execution_start_date": effective_execution_start_date,
        "cagr": perf_metrics.get("cagr"),
        "max_drawdown": perf_metrics.get("max_drawdown"),
    }


def _rewrite_baseline_index(results_root: Path) -> int:
    index_path = results_root / "baselines" / "index.json"
    if not index_path.exists():
        return 0
    rows = _load_json(index_path)
    if not isinstance(rows, list):
        return 0
    changed = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        exp_id = str(row.get("linked_exp_id") or "").strip()
        if not exp_id:
            continue
        perf_path = results_root / "experiments" / exp_id / "perf.json"
        if not perf_path.exists():
            continue
        perf = _load_json(perf_path)
        new_cagr = perf.get("cagr")
        new_mdd = perf.get("max_drawdown")
        if row.get("cagr") != new_cagr or row.get("max_drawdown") != new_mdd:
            row["cagr"] = new_cagr
            row["max_drawdown"] = new_mdd
            row["has_result"] = True
            changed += 1
    if changed:
        _write_json(index_path, rows)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Rewrite experiment artifacts using effective execution start date.")
    parser.add_argument("--exp-id", action="append", default=[], help="Specific experiment id(s) to rewrite.")
    parser.add_argument("--all", action="store_true", help="Rewrite all experiment dirs with run_config + portfolio_daily.")
    args = parser.parse_args()

    results_root = _results_root()
    exp_root = results_root / "experiments"

    exp_dirs: list[Path] = []
    if args.exp_id:
        exp_dirs.extend((exp_root / str(exp_id).strip()) for exp_id in args.exp_id if str(exp_id).strip())
    elif args.all:
        for child in sorted(exp_root.iterdir()):
            if child.is_dir() and (child / "run_config.json").exists() and (child / "portfolio_daily.csv").exists():
                exp_dirs.append(child)
    else:
        raise SystemExit("specify --exp-id or --all")

    rewritten: list[dict[str, Any]] = []
    for exp_dir in exp_dirs:
        item = _rewrite_experiment(exp_dir.resolve())
        if item is not None:
            rewritten.append(item)

    baseline_updates = _rewrite_baseline_index(results_root)

    summary = {
        "rewritten_count": len(rewritten),
        "baseline_index_updates": baseline_updates,
        "experiments": rewritten,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
