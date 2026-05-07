from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.core.data.mapping import normalize_index_symbol, ts_to_cn_index_symbol
from backend.research.a_share_moneyflow_divergence import _create_provider_from_payload
from backend.research.account_state_score_catalog import (
    build_account_state_score_catalog,
    list_account_state_score_ids,
)
from backend.research.account_state_score_snapshots import (
    build_account_state_combo_score_snapshot,
    build_account_state_score_snapshots,
)
from backend.research.study_definition import StudyDefinition


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _outputs_root() -> Path:
    return (_repo_root() / "outputs" / "studies").resolve()


def _study_run_dir(study: StudyDefinition, *, window_key: str, variant_name: str) -> Path:
    parts = [part for part in str(study.study_id or "").replace("\\", "/").split("/") if part]
    return (_outputs_root().joinpath(*parts, window_key, variant_name)).resolve()


def _parse_benchmark_symbol(payload: dict[str, Any]) -> str:
    run_params = payload.get("run_params")
    run_params = run_params if isinstance(run_params, dict) else {}
    return normalize_index_symbol(str(run_params.get("benchmark_symbol") or "000300.SH").strip())


def _parse_score_ids(payload: dict[str, Any]) -> list[str]:
    run_params = payload.get("run_params")
    run_params = run_params if isinstance(run_params, dict) else {}
    score_ids = [str(item).strip().lower() for item in list(run_params.get("score_ids") or []) if str(item).strip()]
    return score_ids or list_account_state_score_ids()


def _parse_score_weights(payload: dict[str, Any], *, score_ids: list[str]) -> dict[str, float]:
    run_params = payload.get("run_params")
    run_params = run_params if isinstance(run_params, dict) else {}
    raw = run_params.get("score_weights")
    if not isinstance(raw, dict) or not raw:
        return {score_id: 1.0 for score_id in score_ids}
    out: dict[str, float] = {}
    for score_id in score_ids:
        value = raw.get(score_id)
        out[score_id] = float(value) if value is not None else 0.0
    return out


def _load_benchmark_history(
    payload: dict[str, Any],
    *,
    start: str,
    end: str,
    benchmark_symbol: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    provider, config_snapshot, config_hash = _create_provider_from_payload(payload)
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    preload_start = start_date - timedelta(days=180)
    load_end = end_date + timedelta(days=10)
    if hasattr(provider, "load_benchmark_daily"):
        history = provider.load_benchmark_daily(benchmark_symbol, preload_start, load_end)
    else:
        history = provider.load_ohlcv_daily(
            [ts_to_cn_index_symbol(benchmark_symbol)],
            preload_start,
            load_end,
            source="account_state_score_surface",
        )
    history = history.copy()
    history["date"] = pd.to_datetime(history["date"])
    return history, {
        "config_snapshot": dict(config_snapshot or {}),
        "config_hash": str(config_hash or ""),
        "preload_start": preload_start.isoformat(),
        "window_start": start,
        "window_end": end,
        "benchmark_symbol": benchmark_symbol,
    }


def _attach_forward_return(benchmark_history: pd.DataFrame, *, benchmark_symbol: str) -> pd.DataFrame:
    frame = benchmark_history.copy()
    target_symbol = normalize_index_symbol(str(benchmark_symbol or "").strip())
    frame["symbol"] = frame["symbol"].astype(str).map(lambda value: normalize_index_symbol(str(value).strip()))
    frame = frame.loc[frame["symbol"] == target_symbol].copy()
    frame = frame.sort_values("date").reset_index(drop=True)
    frame["forward_return_5d"] = frame["close"].shift(-5) / frame["close"] - 1.0
    frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
    return frame.loc[:, ["date", "forward_return_5d"]]


def _safe_spearman(frame: pd.DataFrame, *, value_col: str) -> float | None:
    subset = frame.loc[frame[value_col].notna() & frame["forward_return_5d"].notna(), [value_col, "forward_return_5d"]]
    if len(subset) < 5:
        return None
    if subset[value_col].nunique() <= 1 or subset["forward_return_5d"].nunique() <= 1:
        return None
    value_ranks = subset[value_col].rank(method="average")
    forward_ranks = subset["forward_return_5d"].rank(method="average")
    value = value_ranks.corr(forward_ranks, method="pearson")
    if pd.isna(value):
        return None
    return float(value)


def _safe_top_bottom_spread(frame: pd.DataFrame, *, value_col: str) -> float | None:
    subset = frame.loc[frame[value_col].notna() & frame["forward_return_5d"].notna(), [value_col, "forward_return_5d"]].copy()
    if len(subset) < 10:
        return None
    upper = float(subset[value_col].quantile(0.8))
    lower = float(subset[value_col].quantile(0.2))
    top = subset.loc[subset[value_col] >= upper, "forward_return_5d"]
    bottom = subset.loc[subset[value_col] <= lower, "forward_return_5d"]
    if top.empty or bottom.empty:
        return None
    return float(top.mean() - bottom.mean())


def _summarize_score(frame: pd.DataFrame, *, value_col: str) -> dict[str, Any]:
    coverage_ratio = float(frame["availability_flag"].mean()) if len(frame) else 0.0
    usable = frame.loc[frame["availability_flag"] & frame[value_col].notna() & frame["forward_return_5d"].notna()].copy()
    corr = _safe_spearman(usable, value_col=value_col)
    spread = _safe_top_bottom_spread(usable, value_col=value_col)
    if usable.empty:
        top_mean = None
        bottom_mean = None
    else:
        upper = float(usable[value_col].quantile(0.8))
        lower = float(usable[value_col].quantile(0.2))
        top_mean = float(usable.loc[usable[value_col] >= upper, "forward_return_5d"].mean()) if len(usable) else None
        bottom_mean = float(usable.loc[usable[value_col] <= lower, "forward_return_5d"].mean()) if len(usable) else None
    return sanitize_json(
        {
            "coverage_ratio": coverage_ratio,
            "usable_days": int(usable["date"].nunique()) if len(usable) else 0,
            "mean_score": float(usable[value_col].mean()) if len(usable) else None,
            "score_forward_corr_5d": corr,
            "top_quintile_mean_forward_return_5d": top_mean,
            "bottom_quintile_mean_forward_return_5d": bottom_mean,
            "top_bottom_spread_5d": spread,
        }
    )


def _build_analysis(
    score_snapshot: pd.DataFrame,
    combo_snapshot: pd.DataFrame,
    benchmark_history: pd.DataFrame,
    *,
    score_ids: list[str],
    score_weights: dict[str, float],
    benchmark_symbol: str,
    window_key: str,
    variant_name: str,
) -> dict[str, Any]:
    forward = _attach_forward_return(benchmark_history, benchmark_symbol=benchmark_symbol)
    merged_score = score_snapshot.merge(forward, on="date", how="left")
    single_score = {
        score_id: _summarize_score(
            merged_score.loc[merged_score["score_id"] == score_id].copy(),
            value_col="normalized_value",
        )
        for score_id in score_ids
    }
    merged_combo = combo_snapshot.merge(forward, on="date", how="left")
    combo_analysis = _summarize_score(merged_combo.copy(), value_col="normalized_value")
    state_distribution = (
        combo_snapshot.loc[combo_snapshot["derived_state"].notna(), "derived_state"].value_counts(normalize=True).sort_index().to_dict()
    )
    return sanitize_json(
        {
            "window_key": window_key,
            "variant_name": variant_name,
            "benchmark_symbol": benchmark_symbol,
            "score_ids": list(score_ids),
            "score_weights": dict(score_weights),
            "catalog": build_account_state_score_catalog(),
            "single_score": single_score,
            "combo_score": combo_analysis,
            "derived_state_distribution": state_distribution,
        }
    )


def _write_human_summary(path: Path, analysis: dict[str, Any]) -> None:
    lines = [
        "# Account State Score 研究摘要",
        "",
        f"- window: `{analysis['window_key']}`",
        f"- variant: `{analysis['variant_name']}`",
        f"- benchmark_symbol: `{analysis['benchmark_symbol']}`",
        f"- scores: `{', '.join(analysis['score_ids'])}`",
        "",
        "## 单分数结果",
        "",
    ]
    for score_id, summary in dict(analysis.get("single_score") or {}).items():
        lines.extend(
            [
                f"### `{score_id}`",
                f"- coverage_ratio: `{summary.get('coverage_ratio')}`",
                f"- score_forward_corr_5d: `{summary.get('score_forward_corr_5d')}`",
                f"- top_bottom_spread_5d: `{summary.get('top_bottom_spread_5d')}`",
                "",
            ]
        )
    combo = dict(analysis.get("combo_score") or {})
    lines.extend(
        [
            "## 组合分数结果",
            "",
            f"- coverage_ratio: `{combo.get('coverage_ratio')}`",
            f"- score_forward_corr_5d: `{combo.get('score_forward_corr_5d')}`",
            f"- top_bottom_spread_5d: `{combo.get('top_bottom_spread_5d')}`",
            "",
            "## 派生状态分布",
            "",
        ]
    )
    for state, ratio in dict(analysis.get("derived_state_distribution") or {}).items():
        lines.append(f"- `{state}`: `{ratio}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_account_state_score_study(
    *,
    study: StudyDefinition,
    plan: list[dict[str, Any]],
    write_dual_output: bool = True,
    append_to_baseline: bool = True,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for item in list(plan or []):
        payload = dict(item.get("request_payload") or {})
        benchmark_symbol = _parse_benchmark_symbol(payload)
        score_ids = _parse_score_ids(payload)
        score_weights = _parse_score_weights(payload, score_ids=score_ids)
        start = str(payload.get("start_date") or "")
        end = str(payload.get("end_date") or "")
        benchmark_history, provider_meta = _load_benchmark_history(
            payload,
            start=start,
            end=end,
            benchmark_symbol=benchmark_symbol,
        )
        score_snapshot = build_account_state_score_snapshots(
            benchmark_history,
            benchmark_symbol=benchmark_symbol,
            score_ids=score_ids,
        )
        window_snapshot = score_snapshot.loc[
            (score_snapshot["date"] >= start) & (score_snapshot["date"] <= end)
        ].reset_index(drop=True)
        combo_snapshot = build_account_state_combo_score_snapshot(
            window_snapshot,
            score_ids=score_ids,
            score_weights=score_weights,
        )
        analysis = _build_analysis(
            window_snapshot,
            combo_snapshot,
            benchmark_history.loc[
                (benchmark_history["date"] >= pd.Timestamp(start)) & (benchmark_history["date"] <= pd.Timestamp(end) + pd.Timedelta(days=10))
            ].copy(),
            score_ids=score_ids,
            score_weights=score_weights,
            benchmark_symbol=benchmark_symbol,
            window_key=str(item.get("window_key") or ""),
            variant_name=str(item.get("variant_name") or ""),
        )

        run_dir = _study_run_dir(
            study,
            window_key=str(item.get("window_key") or ""),
            variant_name=str(item.get("variant_name") or ""),
        )
        machine_dir = (run_dir / "machine").resolve()
        human_dir = (run_dir / "human").resolve()
        machine_dir.mkdir(parents=True, exist_ok=True)
        human_dir.mkdir(parents=True, exist_ok=True)

        catalog_json = machine_dir / "score_catalog.json"
        snapshot_csv = machine_dir / "score_snapshot.csv"
        combo_csv = machine_dir / "score_combo_snapshot.csv"
        analysis_json = machine_dir / "analysis.json"
        summary_md = human_dir / "summary.md"

        catalog_json.write_text(
            json.dumps(build_account_state_score_catalog(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        window_snapshot.to_csv(snapshot_csv, index=False, encoding="utf-8-sig")
        combo_snapshot.to_csv(combo_csv, index=False, encoding="utf-8-sig")
        analysis_json.write_text(
            json.dumps(
                sanitize_json(
                    {
                        "study_id": study.study_id,
                        "title": study.title,
                        "baseline_id": study.baseline_id,
                        "provider_meta": provider_meta,
                        "analysis": analysis,
                    }
                ),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        _write_human_summary(summary_md, analysis)

        runs.append(
            sanitize_json(
                {
                    "window_key": item.get("window_key"),
                    "variant_name": item.get("variant_name"),
                    "exp_id": "",
                    "results_dir": str(run_dir),
                    "verdict": {"status": "RESEARCH_ONLY"},
                    "machine_outputs": {
                        "score_catalog": str(catalog_json),
                        "score_snapshot": str(snapshot_csv),
                        "score_combo_snapshot": str(combo_csv),
                        "analysis": str(analysis_json),
                    },
                    "human_outputs": {"summary": str(summary_md)},
                    "diagnostic_outputs": {
                        "benchmark_symbol": benchmark_symbol,
                        "score_ids": list(score_ids),
                    },
                    "baseline_outputs": {} if append_to_baseline else {},
                }
            )
        )

    return sanitize_json(
        {
            "study_id": study.study_id,
            "title": study.title,
            "baseline_id": study.baseline_id,
            "required_outputs": list(study.required_outputs),
            "runs": runs,
        }
    )
