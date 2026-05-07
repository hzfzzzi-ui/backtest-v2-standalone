from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.research.a_share_moneyflow_divergence import _create_provider_from_payload
from backend.research.stock_alpha_factor_catalog import (
    build_stock_alpha_factor_catalog,
    list_stock_alpha_factor_ids,
)
from backend.research.stock_alpha_factor_snapshots import (
    build_stock_alpha_factor_score_snapshot,
    build_stock_alpha_factor_snapshots,
)
from backend.research.study_definition import StudyDefinition


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _outputs_root() -> Path:
    return (_repo_root() / "outputs" / "studies").resolve()


def _study_run_dir(study: StudyDefinition, *, window_key: str, variant_name: str) -> Path:
    parts = [part for part in str(study.study_id or "").replace("\\", "/").split("/") if part]
    return (_outputs_root().joinpath(*parts, window_key, variant_name)).resolve()


def _parse_symbols(payload: dict[str, Any]) -> list[str]:
    run_params = payload.get("run_params")
    run_params = run_params if isinstance(run_params, dict) else {}
    symbols = [str(item).strip().lower() for item in list(run_params.get("symbols") or []) if str(item).strip()]
    if not symbols:
        raise ValueError("stock alpha factor study requires run_params.symbols")
    return sorted(dict.fromkeys(symbols))


def _parse_factor_ids(payload: dict[str, Any]) -> list[str]:
    run_params = payload.get("run_params")
    run_params = run_params if isinstance(run_params, dict) else {}
    factor_ids = [str(item).strip().lower() for item in list(run_params.get("factor_ids") or []) if str(item).strip()]
    return factor_ids or list_stock_alpha_factor_ids()


def _parse_factor_weights(payload: dict[str, Any], *, factor_ids: list[str]) -> dict[str, float]:
    run_params = payload.get("run_params")
    run_params = run_params if isinstance(run_params, dict) else {}
    raw = run_params.get("factor_weights")
    if not isinstance(raw, dict) or not raw:
        return {factor_id: 1.0 for factor_id in factor_ids}
    out: dict[str, float] = {}
    for factor_id in factor_ids:
        value = raw.get(factor_id)
        out[factor_id] = float(value) if value is not None else 0.0
    return out


def _load_price_history(payload: dict[str, Any], *, start: str, end: str, symbols: list[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    provider, config_snapshot, config_hash = _create_provider_from_payload(payload)
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    preload_start = start_date - timedelta(days=120)
    history = provider.load_ohlcv_daily(symbols, preload_start, end_date, source="stock_alpha_factor_surface")
    history = history.copy()
    history["date"] = pd.to_datetime(history["date"])
    return history, {
        "config_snapshot": dict(config_snapshot or {}),
        "config_hash": str(config_hash or ""),
        "preload_start": preload_start.isoformat(),
        "window_start": start,
        "window_end": end,
    }


def _attach_forward_return(price_history: pd.DataFrame) -> pd.DataFrame:
    frame = price_history.copy().sort_values(["symbol", "date"]).reset_index(drop=True)
    frame["forward_return_1d"] = frame.groupby("symbol")["close"].shift(-1) / frame["close"] - 1.0
    frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
    frame["symbol"] = frame["symbol"].astype(str).str.lower()
    return frame.loc[:, ["date", "symbol", "forward_return_1d"]]


def _safe_spearman(frame: pd.DataFrame, *, value_col: str) -> float | None:
    subset = frame.loc[frame[value_col].notna() & frame["forward_return_1d"].notna(), [value_col, "forward_return_1d"]]
    if len(subset) < 3:
        return None
    if subset[value_col].nunique() <= 1 or subset["forward_return_1d"].nunique() <= 1:
        return None
    value_ranks = subset[value_col].rank(method="average")
    forward_ranks = subset["forward_return_1d"].rank(method="average")
    value = value_ranks.corr(forward_ranks, method="pearson")
    if pd.isna(value):
        return None
    return float(value)


def _safe_top_bottom_spread(frame: pd.DataFrame, *, value_col: str) -> float | None:
    subset = frame.loc[frame[value_col].notna() & frame["forward_return_1d"].notna(), [value_col, "forward_return_1d"]].copy()
    if len(subset) < 4:
        return None
    subset = subset.sort_values(value_col).reset_index(drop=True)
    half = len(subset) // 2
    if half <= 0:
        return None
    bottom = float(subset.iloc[:half]["forward_return_1d"].mean())
    top = float(subset.iloc[-half:]["forward_return_1d"].mean())
    return top - bottom


def _summarize_signal(frame: pd.DataFrame, *, value_col: str) -> dict[str, Any]:
    coverage_ratio = float(frame["availability_flag"].mean()) if len(frame) else 0.0
    usable = frame.loc[frame[value_col].notna() & frame["forward_return_1d"].notna()].copy()
    daily_ic = [
        value
        for _, group in usable.groupby("date")
        if (value := _safe_spearman(group, value_col=value_col)) is not None
    ]
    spreads = [
        value
        for _, group in usable.groupby("date")
        if (value := _safe_top_bottom_spread(group, value_col=value_col)) is not None
    ]
    ic_mean = float(np.mean(daily_ic)) if daily_ic else None
    ic_std = float(np.std(daily_ic, ddof=0)) if daily_ic else None
    ic_ir = float(ic_mean / ic_std) if daily_ic and ic_std and ic_std > 0 else None
    spread_mean = float(np.mean(spreads)) if spreads else None
    return sanitize_json(
        {
            "coverage_ratio": coverage_ratio,
            "usable_rows": int(len(usable)),
            "usable_days": int(usable["date"].nunique()),
            "mean_daily_ic": ic_mean,
            "ic_ir": ic_ir,
            "mean_top_bottom_spread_1d": spread_mean,
        }
    )


def _build_analysis(
    factor_snapshot: pd.DataFrame,
    factor_score_snapshot: pd.DataFrame,
    price_history: pd.DataFrame,
    *,
    factor_ids: list[str],
    factor_weights: dict[str, float],
    symbols: list[str],
    window_key: str,
    variant_name: str,
) -> dict[str, Any]:
    forward = _attach_forward_return(price_history)
    merged_factor = factor_snapshot.merge(forward, on=["date", "symbol"], how="left")
    factor_analysis = {
        factor_id: _summarize_signal(
            merged_factor.loc[merged_factor["factor_id"] == factor_id].copy(),
            value_col="rank_value",
        )
        for factor_id in factor_ids
    }
    merged_score = factor_score_snapshot.merge(forward, on=["date", "symbol"], how="left")
    score_analysis = _summarize_signal(merged_score.copy(), value_col="score_value")
    return sanitize_json(
        {
            "window_key": window_key,
            "variant_name": variant_name,
            "symbol_count": len(symbols),
            "factor_ids": list(factor_ids),
            "factor_weights": dict(factor_weights),
            "catalog": build_stock_alpha_factor_catalog(),
            "single_factor": factor_analysis,
            "factor_score": score_analysis,
        }
    )


def _write_human_summary(path: Path, analysis: dict[str, Any]) -> None:
    lines = [
        "# Stock Alpha 因子研究摘要",
        "",
        f"- window: `{analysis['window_key']}`",
        f"- variant: `{analysis['variant_name']}`",
        f"- symbols: `{analysis['symbol_count']}`",
        f"- factors: `{', '.join(analysis['factor_ids'])}`",
        "",
        "## 单因子结果",
        "",
    ]
    for factor_id, summary in dict(analysis.get("single_factor") or {}).items():
        lines.extend(
            [
                f"### `{factor_id}`",
                f"- coverage_ratio: `{summary.get('coverage_ratio')}`",
                f"- mean_daily_ic: `{summary.get('mean_daily_ic')}`",
                f"- ic_ir: `{summary.get('ic_ir')}`",
                f"- mean_top_bottom_spread_1d: `{summary.get('mean_top_bottom_spread_1d')}`",
                "",
            ]
        )
    score = dict(analysis.get("factor_score") or {})
    lines.extend(
        [
            "## 因子组合结果",
            "",
            f"- coverage_ratio: `{score.get('coverage_ratio')}`",
            f"- mean_daily_ic: `{score.get('mean_daily_ic')}`",
            f"- ic_ir: `{score.get('ic_ir')}`",
            f"- mean_top_bottom_spread_1d: `{score.get('mean_top_bottom_spread_1d')}`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_stock_alpha_factor_study(
    *,
    study: StudyDefinition,
    plan: list[dict[str, Any]],
    write_dual_output: bool = True,
    append_to_baseline: bool = True,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for item in list(plan or []):
        payload = dict(item.get("request_payload") or {})
        symbols = _parse_symbols(payload)
        factor_ids = _parse_factor_ids(payload)
        factor_weights = _parse_factor_weights(payload, factor_ids=factor_ids)
        start = str(payload.get("start_date") or "")
        end = str(payload.get("end_date") or "")
        price_history, provider_meta = _load_price_history(payload, start=start, end=end, symbols=symbols)
        factor_snapshot = build_stock_alpha_factor_snapshots(price_history, factor_ids=factor_ids)
        window_snapshot = factor_snapshot.loc[
            (factor_snapshot["date"] >= start) & (factor_snapshot["date"] <= end)
        ].reset_index(drop=True)
        factor_score_snapshot = build_stock_alpha_factor_score_snapshot(
            window_snapshot,
            factor_ids=factor_ids,
            factor_weights=factor_weights,
        )
        analysis = _build_analysis(
            window_snapshot,
            factor_score_snapshot,
            price_history.loc[(price_history["date"] >= pd.Timestamp(start)) & (price_history["date"] <= pd.Timestamp(end))].copy(),
            factor_ids=factor_ids,
            factor_weights=factor_weights,
            symbols=symbols,
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

        catalog_json = machine_dir / "factor_catalog.json"
        snapshot_csv = machine_dir / "factor_snapshot.csv"
        score_csv = machine_dir / "factor_score_snapshot.csv"
        analysis_json = machine_dir / "analysis.json"
        summary_md = human_dir / "summary.md"

        catalog_json.write_text(
            json.dumps(build_stock_alpha_factor_catalog(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        window_snapshot.to_csv(snapshot_csv, index=False, encoding="utf-8-sig")
        factor_score_snapshot.to_csv(score_csv, index=False, encoding="utf-8-sig")
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
                        "factor_catalog": str(catalog_json),
                        "factor_snapshot": str(snapshot_csv),
                        "factor_score_snapshot": str(score_csv),
                        "analysis": str(analysis_json),
                    },
                    "human_outputs": {"summary": str(summary_md)},
                    "diagnostic_outputs": {
                        "symbol_count": len(symbols),
                        "factor_ids": list(factor_ids),
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
