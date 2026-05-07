from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.research.a_share_moneyflow_divergence import (
    _create_provider_from_payload,
    build_daily_divergence_frame,
    build_monthly_divergence_panel,
)
from backend.research.moneyflow_factor_catalog import (
    build_moneyflow_factor_catalog,
    list_moneyflow_factor_ids,
)
from backend.research.moneyflow_factor_snapshots import (
    build_moneyflow_factor_score_snapshot,
    build_moneyflow_factor_snapshots,
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
        raise ValueError("moneyflow factor study requires run_params.symbols")
    return sorted(dict.fromkeys(symbols))


def _parse_factor_ids(payload: dict[str, Any]) -> list[str]:
    run_params = payload.get("run_params")
    run_params = run_params if isinstance(run_params, dict) else {}
    factor_ids = [str(item).strip().lower() for item in list(run_params.get("factor_ids") or []) if str(item).strip()]
    return factor_ids or list_moneyflow_factor_ids()


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


def _parse_moneyflow_table(payload: dict[str, Any]) -> str:
    run_params = payload.get("run_params")
    run_params = run_params if isinstance(run_params, dict) else {}
    return str(run_params.get("moneyflow_table") or "pit_stock_moneyflow_v2").strip()


def _parse_horizon_days(payload: dict[str, Any]) -> int:
    run_params = payload.get("run_params")
    run_params = run_params if isinstance(run_params, dict) else {}
    return int(run_params.get("horizon_days") or 20)


def _load_histories(
    payload: dict[str, Any],
    *,
    start: str,
    end: str,
    symbols: list[str],
    moneyflow_table: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    provider, config_snapshot, config_hash = _create_provider_from_payload(payload)
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    preload_start = start_date - timedelta(days=120)
    load_end = end_date + timedelta(days=45)
    price_history = provider.load_ohlcv_daily(symbols, preload_start, load_end, source="moneyflow_factor_surface")
    moneyflow = provider.load_stock_moneyflow(symbols, preload_start, end_date, table=moneyflow_table)
    price_history = price_history.copy()
    price_history["date"] = pd.to_datetime(price_history["date"])
    return price_history, moneyflow.copy(), {
        "config_snapshot": dict(config_snapshot or {}),
        "config_hash": str(config_hash or ""),
        "preload_start": preload_start.isoformat(),
        "window_start": start,
        "window_end": end,
        "moneyflow_table": moneyflow_table,
    }


def _attach_forward_return(price_history: pd.DataFrame, *, horizon_days: int) -> pd.DataFrame:
    frame = price_history.copy().sort_values(["symbol", "date"]).reset_index(drop=True)
    frame["symbol"] = frame["symbol"].astype(str).str.lower()
    frame[f"forward_return_{horizon_days}d"] = frame.groupby("symbol")["close"].shift(-horizon_days) / frame["close"] - 1.0
    frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
    return frame.loc[:, ["date", "symbol", f"forward_return_{horizon_days}d"]]


def _safe_spearman(frame: pd.DataFrame, *, value_col: str, forward_col: str) -> float | None:
    subset = frame.loc[frame[value_col].notna() & frame[forward_col].notna(), [value_col, forward_col]]
    if len(subset) < 3:
        return None
    if subset[value_col].nunique() <= 1 or subset[forward_col].nunique() <= 1:
        return None
    value_ranks = subset[value_col].rank(method="average")
    forward_ranks = subset[forward_col].rank(method="average")
    value = value_ranks.corr(forward_ranks, method="pearson")
    if pd.isna(value):
        return None
    return float(value)


def _safe_top_bottom_spread(frame: pd.DataFrame, *, value_col: str, forward_col: str) -> float | None:
    subset = frame.loc[frame[value_col].notna() & frame[forward_col].notna(), [value_col, forward_col]].copy()
    if len(subset) < 4:
        return None
    subset = subset.sort_values(value_col).reset_index(drop=True)
    half = len(subset) // 2
    if half <= 0:
        return None
    bottom = float(subset.iloc[:half][forward_col].mean())
    top = float(subset.iloc[-half:][forward_col].mean())
    return top - bottom


def _summarize_signal(frame: pd.DataFrame, *, value_col: str, horizon_days: int) -> dict[str, Any]:
    forward_col = f"forward_return_{horizon_days}d"
    coverage_ratio = float(frame["availability_flag"].mean()) if len(frame) else 0.0
    usable = frame.loc[frame[value_col].notna() & frame[forward_col].notna() & frame["availability_flag"]].copy()
    observation_ic = [
        value
        for _, group in usable.groupby("date")
        if (value := _safe_spearman(group, value_col=value_col, forward_col=forward_col)) is not None
    ]
    spreads = [
        value
        for _, group in usable.groupby("date")
        if (value := _safe_top_bottom_spread(group, value_col=value_col, forward_col=forward_col)) is not None
    ]
    ic_mean = float(np.mean(observation_ic)) if observation_ic else None
    ic_std = float(np.std(observation_ic, ddof=0)) if observation_ic else None
    ic_ir = float(ic_mean / ic_std) if observation_ic and ic_std and ic_std > 0 else None
    spread_mean = float(np.mean(spreads)) if spreads else None
    return sanitize_json(
        {
            "coverage_ratio": coverage_ratio,
            "usable_rows": int(len(usable)),
            "usable_observations": int(usable["date"].nunique()) if len(usable) else 0,
            f"mean_observation_ic_{horizon_days}d": ic_mean,
            "ic_ir": ic_ir,
            f"mean_top_bottom_spread_{horizon_days}d": spread_mean,
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
    horizon_days: int,
) -> dict[str, Any]:
    forward = _attach_forward_return(price_history, horizon_days=horizon_days)
    merged_factor = factor_snapshot.merge(forward, on=["date", "symbol"], how="left")
    factor_analysis = {
        factor_id: _summarize_signal(
            merged_factor.loc[merged_factor["factor_id"] == factor_id].copy(),
            value_col="rank_value",
            horizon_days=horizon_days,
        )
        for factor_id in factor_ids
    }
    merged_score = factor_score_snapshot.merge(forward, on=["date", "symbol"], how="left")
    score_analysis = _summarize_signal(
        merged_score.copy(),
        value_col="score_value",
        horizon_days=horizon_days,
    )
    return sanitize_json(
        {
            "window_key": window_key,
            "variant_name": variant_name,
            "symbol_count": len(symbols),
            "factor_ids": list(factor_ids),
            "factor_weights": dict(factor_weights),
            "horizon_days": int(horizon_days),
            "catalog": build_moneyflow_factor_catalog(),
            "single_factor": factor_analysis,
            "factor_score": score_analysis,
        }
    )


def _write_human_summary(path: Path, analysis: dict[str, Any]) -> None:
    horizon_days = int(analysis.get("horizon_days") or 20)
    lines = [
        "# Moneyflow factor study summary",
        "",
        f"- window: `{analysis['window_key']}`",
        f"- variant: `{analysis['variant_name']}`",
        f"- symbols: `{analysis['symbol_count']}`",
        f"- horizon_days: `{horizon_days}`",
        f"- factors: `{', '.join(analysis['factor_ids'])}`",
        "",
        "## Single factor results",
        "",
    ]
    for factor_id, summary in dict(analysis.get("single_factor") or {}).items():
        lines.extend(
            [
                f"### `{factor_id}`",
                f"- coverage_ratio: `{summary.get('coverage_ratio')}`",
                f"- mean_observation_ic_{horizon_days}d: `{summary.get(f'mean_observation_ic_{horizon_days}d')}`",
                f"- ic_ir: `{summary.get('ic_ir')}`",
                f"- mean_top_bottom_spread_{horizon_days}d: `{summary.get(f'mean_top_bottom_spread_{horizon_days}d')}`",
                "",
            ]
        )
    score = dict(analysis.get("factor_score") or {})
    lines.extend(
        [
            "## Factor score result",
            "",
            f"- coverage_ratio: `{score.get('coverage_ratio')}`",
            f"- mean_observation_ic_{horizon_days}d: `{score.get(f'mean_observation_ic_{horizon_days}d')}`",
            f"- ic_ir: `{score.get('ic_ir')}`",
            f"- mean_top_bottom_spread_{horizon_days}d: `{score.get(f'mean_top_bottom_spread_{horizon_days}d')}`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_moneyflow_factor_study(
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
        moneyflow_table = _parse_moneyflow_table(payload)
        horizon_days = _parse_horizon_days(payload)
        start = str(payload.get("start_date") or "")
        end = str(payload.get("end_date") or "")
        price_history, moneyflow, provider_meta = _load_histories(
            payload,
            start=start,
            end=end,
            symbols=symbols,
            moneyflow_table=moneyflow_table,
        )
        daily_divergence = build_daily_divergence_frame(price_history, moneyflow)
        monthly_panel = build_monthly_divergence_panel(daily_divergence)
        factor_snapshot = build_moneyflow_factor_snapshots(monthly_panel, factor_ids=factor_ids)
        window_snapshot = factor_snapshot.loc[
            (factor_snapshot["date"] >= start) & (factor_snapshot["date"] <= end)
        ].reset_index(drop=True)
        factor_score_snapshot = build_moneyflow_factor_score_snapshot(
            window_snapshot,
            factor_ids=factor_ids,
            factor_weights=factor_weights,
        )
        analysis = _build_analysis(
            window_snapshot,
            factor_score_snapshot,
            price_history.loc[
                (price_history["date"] >= pd.Timestamp(start))
                & (price_history["date"] <= pd.Timestamp(end) + pd.Timedelta(days=45))
            ].copy(),
            factor_ids=factor_ids,
            factor_weights=factor_weights,
            symbols=symbols,
            window_key=str(item.get("window_key") or ""),
            variant_name=str(item.get("variant_name") or ""),
            horizon_days=horizon_days,
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
            json.dumps(build_moneyflow_factor_catalog(), ensure_ascii=False, indent=2),
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
                        "moneyflow_table": moneyflow_table,
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
