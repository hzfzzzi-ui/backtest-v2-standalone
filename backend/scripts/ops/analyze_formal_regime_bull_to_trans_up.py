from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.api.shared.paths import bt_root as _bt_root
from backend.api.backtest_v2.runner_config_helpers import _compile_semantic_config_bundle, _load_base_config
from backend.core.config.loader import load_config
from backend.core.engine_vector.breakout_signal_provider import _coerce_regime_engine_cfg
from backend.core.engine_vector.breakout_signal_provider import _build_legacy_market_filter_state
from backend.core.engine_vector.data_matrix import build_ohlc_matrices_from_history
from backend.core.engine_vector.regime_engine_evaluator import _compute_breadth_scores
from backend.core.engine_vector.regime_engine_evaluator import _compute_participation_scores
from backend.core.engine_vector.regime_engine_evaluator import _compute_risk_scores
from backend.core.engine_vector.regime_engine_evaluator import _compute_trend_scores
from backend.core.engine_vector.regime_engine_evaluator import _weighted_score
from backend.core.engine_vector.regime_engine_evaluator import evaluate_formal_regime_engine
from backend.core.engine_vector.regime_engine_inputs import build_formal_regime_feature_bundle
from backend.core.tools.data_bundle_builder import build_data_bundle
from backend.core.tools.experiment_runner import DEFAULT_EXPERIMENT_SYMBOLS

ROOT = Path(__file__).resolve().parents[3]
OPS_ROOT = ROOT / "outputs" / "ops"

LEGACY_EXP_ID = "exp_20260320_124758017_a2de"
FORMAL_EXP_ID = "exp_20260320_125317256_782c"
OUT_DIR = OPS_ROOT / "formal_regime_bull_to_trans_up_drag_20260320"


def _load_resolved_experiment_config(exp_id: str) -> dict[str, Any]:
    path = ROOT / "outputs" / "experiments" / exp_id / "resolved_config.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    config_json = payload.get("config_json")
    if not isinstance(config_json, dict):
        raise RuntimeError(f"missing config_json in {path}")
    return config_json


def _compile_runtime_bundle(semantic_cfg: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    compiled = _compile_semantic_config_bundle(
        base_cfg=_load_base_config(_bt_root()),
        body=None,
        semantic_cfg=semantic_cfg,
        config_source=f"{FORMAL_EXP_ID}:drag_analysis",
        use_body_universe_fields=False,
    )
    runtime_cfg = dict(compiled.get("runtime_config") or {})
    if not runtime_cfg:
        raise RuntimeError("semantic config compile returned empty runtime_config")
    execution_overrides = dict((compiled.get("compiled_plan") or {}).get("execution_overrides") or {})
    return runtime_cfg, execution_overrides


def _runtime_overrides(runtime_cfg: dict[str, Any], semantic_cfg: dict[str, Any]) -> dict[str, Any]:
    universe = dict(runtime_cfg.get("universe") or {})
    data_source = dict(runtime_cfg.get("data_source") or {})
    return {
        "asset_scope": str(runtime_cfg.get("asset_scope") or "cn_a_equity"),
        "universe_mode": str(semantic_cfg.get("universe_mode") or "CUSTOM"),
        "price_adj": str(universe.get("price_adj") or "hfq"),
        "data_role": str(data_source.get("data_role") or "").strip(),
        "asset_context": dict(runtime_cfg.get("asset_context") or {}),
    }


def _load_daily(exp_id: str) -> pd.DataFrame:
    path = ROOT / "outputs" / "experiments" / exp_id / "portfolio_daily.csv"
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _mean_or_none(series: pd.Series) -> float | None:
    valid = pd.to_numeric(series, errors="coerce")
    if not valid.notna().any():
        return None
    return float(valid.mean())


def _sum_int(series: pd.Series) -> int:
    return int(pd.to_numeric(series, errors="coerce").fillna(0).sum())


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    semantic_cfg = _load_resolved_experiment_config(FORMAL_EXP_ID)
    runtime_cfg, _ = _compile_runtime_bundle(semantic_cfg)
    overrides = _runtime_overrides(runtime_cfg, semantic_cfg)

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as fh:
        fh.write(json.dumps(runtime_cfg, ensure_ascii=False, indent=2))
        runtime_cfg_path = Path(fh.name).resolve()

    try:
        cfg_obj, _ = load_config(runtime_cfg_path)
        cfg_obj.regime_engine = _coerce_regime_engine_cfg(getattr(cfg_obj, "regime_engine", None))
        bundle = build_data_bundle(
            cfg_obj=cfg_obj,
            cfg_merged=runtime_cfg,
            overrides=overrides,
            rules_path=runtime_cfg_path.parent / "instrument_rules_cn.csv",
            default_experiment_symbols=DEFAULT_EXPERIMENT_SYMBOLS,
        )
        mx = build_ohlc_matrices_from_history(
            bundle.signal_history,
            bundle.trading_days,
            st_history=bundle.st_history,
            membership_history=bundle.membership_history,
            min_price=float(bundle.universe_filters_raw.get("price_min", bundle.universe_filters_raw.get("min_price", 0.0)) or 0.0),
            min_list_days=int(bundle.universe_filters_raw.get("min_list_days", 0) or 0),
            min_avg_turnover_20d=float(bundle.universe_filters_raw.get("min_avg_turnover_20d", 0.0) or 0.0),
        )

        legacy_market_state, legacy_trade_mode = _build_legacy_market_filter_state(
            benchmark=bundle.benchmark,
            dates=mx.dates,
            market_filter_cfg=cfg_obj.market_filter,
        )
        formal_bundle = build_formal_regime_feature_bundle(
            benchmark=bundle.benchmark,
            history=bundle.signal_history,
            mx=mx,
            trading_days=bundle.trading_days,
            regime_engine_cfg=cfg_obj.regime_engine,
            membership_history=bundle.membership_history,
        )
        formal_eval = evaluate_formal_regime_engine(
            bundle=formal_bundle,
            regime_engine_cfg=cfg_obj.regime_engine,
            legacy_market_state=legacy_market_state,
            legacy_trade_mode=legacy_trade_mode,
        )
    finally:
        try:
            runtime_cfg_path.unlink(missing_ok=True)
        except Exception:
            pass

    availability = {
        "trend_block": np.asarray(formal_bundle.feature_availability.trend_block, dtype=bool),
        "risk_block": np.asarray(formal_bundle.feature_availability.risk_block, dtype=bool),
        "breadth_block": np.asarray(formal_bundle.feature_availability.breadth_block, dtype=bool),
        "participation_block": np.asarray(formal_bundle.feature_availability.participation_block, dtype=bool),
    }
    trend_bull, trend_bear = _compute_trend_scores(formal_bundle)
    risk_bull, risk_bear = _compute_risk_scores(formal_bundle)
    breadth_bull, breadth_bear = _compute_breadth_scores(formal_bundle)
    participation_bull, participation_bear = _compute_participation_scores(formal_bundle)
    bull_score = _weighted_score(
        {
            "trend_block": trend_bull,
            "risk_block": risk_bull,
            "breadth_block": breadth_bull,
            "participation_block": participation_bull,
        },
        availability,
    )
    bear_score = _weighted_score(
        {
            "trend_block": trend_bear,
            "risk_block": risk_bear,
            "breadth_block": breadth_bear,
            "participation_block": participation_bear,
        },
        availability,
    )

    legacy_daily = _load_daily(LEGACY_EXP_ID)[["date", "market_state", "trade_mode", "selected_count", "raw_buy_signal_count", "candidates_count"]]
    formal_daily = _load_daily(FORMAL_EXP_ID)[[
        "date",
        "market_state",
        "trade_mode",
        "selected_count",
        "raw_buy_signal_count",
        "candidates_count",
        "regime_confidence",
        "regime_duration_bars",
        "regime_transition_reason",
        "feature_availability_json",
    ]]

    feature_df = pd.DataFrame(
        {
            "date": pd.to_datetime(bundle.trading_days),
            "trend_bull": trend_bull,
            "trend_bear": trend_bear,
            "risk_bull": risk_bull,
            "risk_bear": risk_bear,
            "breadth_bull": breadth_bull,
            "breadth_bear": breadth_bear,
            "participation_bull": participation_bull,
            "participation_bear": participation_bear,
            "bull_score": bull_score,
            "bear_score": bear_score,
            "score_diff": bull_score - bear_score,
            "formal_state_code": formal_eval.market_state,
            "formal_trade_mode_code": formal_eval.trade_mode,
            "fallback_active": formal_eval.fallback_active,
            "required_trend_ready": formal_bundle.feature_availability.trend_block,
            "required_risk_ready": formal_bundle.feature_availability.risk_block,
            "breadth_ready": formal_bundle.feature_availability.breadth_block,
            "participation_ready": formal_bundle.feature_availability.participation_block,
        }
    )

    merged = legacy_daily.merge(
        formal_daily.rename(
            columns={
                "market_state": "formal_market_state",
                "trade_mode": "formal_trade_mode",
                "selected_count": "formal_selected_count",
                "raw_buy_signal_count": "formal_raw_buy_signal_count",
                "candidates_count": "formal_candidates_count",
            }
        ),
        on="date",
        how="inner",
    ).rename(
        columns={
            "market_state": "legacy_market_state",
            "trade_mode": "legacy_trade_mode",
            "selected_count": "legacy_selected_count",
            "raw_buy_signal_count": "legacy_raw_buy_signal_count",
            "candidates_count": "legacy_candidates_count",
        }
    )
    merged = merged.merge(feature_df, on="date", how="inner")
    merged["selected_loss"] = pd.to_numeric(merged["legacy_selected_count"], errors="coerce").fillna(0) - pd.to_numeric(merged["formal_selected_count"], errors="coerce").fillna(0)

    bull_to_trans_up = merged[
        (merged["legacy_market_state"] == "BULL") & (merged["formal_market_state"] == "TRANS_UP")
    ].copy()
    bull_to_bull = merged[
        (merged["legacy_market_state"] == "BULL") & (merged["formal_market_state"] == "BULL")
    ].copy()
    ready = bull_to_trans_up[~bull_to_trans_up["fallback_active"].astype(bool)].copy()
    fallback = bull_to_trans_up[bull_to_trans_up["fallback_active"].astype(bool)].copy()
    loss_days = ready[ready["selected_loss"] > 0].copy()
    loss_by_formal_mode = (
        loss_days.groupby("formal_trade_mode", dropna=False)
        .agg(
            days=("date", "count"),
            selected_loss_total=("selected_loss", "sum"),
            bull_score_mean=("bull_score", "mean"),
            bear_score_mean=("bear_score", "mean"),
            score_diff_mean=("score_diff", "mean"),
            regime_confidence_mean=("regime_confidence", "mean"),
            trend_bull_mean=("trend_bull", "mean"),
            risk_bull_mean=("risk_bull", "mean"),
            breadth_bull_mean=("breadth_bull", "mean"),
            participation_bull_mean=("participation_bull", "mean"),
        )
        .reset_index()
    )

    def _block_summary(sample: pd.DataFrame, name: str) -> dict[str, Any]:
        return {
            "days": int(len(sample)),
            "bull_score_mean": _mean_or_none(sample["bull_score"]),
            "bear_score_mean": _mean_or_none(sample["bear_score"]),
            "score_diff_mean": _mean_or_none(sample["score_diff"]),
            "regime_confidence_mean": _mean_or_none(sample["regime_confidence"]),
            "selected_loss_total": _sum_int(sample["selected_loss"]) if "selected_loss" in sample.columns else 0,
            "trend_bull_mean": _mean_or_none(sample["trend_bull"]),
            "risk_bull_mean": _mean_or_none(sample["risk_bull"]),
            "breadth_bull_mean": _mean_or_none(sample["breadth_bull"]),
            "participation_bull_mean": _mean_or_none(sample["participation_bull"]),
            "trend_bear_mean": _mean_or_none(sample["trend_bear"]),
            "risk_bear_mean": _mean_or_none(sample["risk_bear"]),
            "breadth_bear_mean": _mean_or_none(sample["breadth_bear"]),
            "participation_bear_mean": _mean_or_none(sample["participation_bear"]),
            "regime_transition_reason_counts": sample["regime_transition_reason"].astype(str).value_counts().head(10).to_dict(),
        }

    reference = _block_summary(bull_to_bull, "bull_to_bull")
    ready_summary = _block_summary(ready, "bull_to_trans_up_ready")
    fallback_summary = _block_summary(fallback, "bull_to_trans_up_fallback")
    loss_summary = _block_summary(loss_days, "bull_to_trans_up_selected_loss")

    comparison_rows: list[dict[str, Any]] = []
    for block in ("trend", "risk", "breadth", "participation"):
        comparison_rows.append(
            {
                "block": block,
                "bull_to_bull_bull_mean": reference.get(f"{block}_bull_mean"),
                "bull_to_trans_up_ready_bull_mean": ready_summary.get(f"{block}_bull_mean"),
                "delta_bull_mean": (ready_summary.get(f"{block}_bull_mean") or 0.0) - (reference.get(f"{block}_bull_mean") or 0.0),
                "bull_to_bull_bear_mean": reference.get(f"{block}_bear_mean"),
                "bull_to_trans_up_ready_bear_mean": ready_summary.get(f"{block}_bear_mean"),
                "delta_bear_mean": (ready_summary.get(f"{block}_bear_mean") or 0.0) - (reference.get(f"{block}_bear_mean") or 0.0),
                "selected_loss_day_bull_mean": loss_summary.get(f"{block}_bull_mean"),
                "selected_loss_day_bear_mean": loss_summary.get(f"{block}_bear_mean"),
            }
        )
    comparison_df = pd.DataFrame(comparison_rows)
    comparison_df["drag_rank_bull"] = comparison_df["delta_bull_mean"].rank(method="dense")
    comparison_df["drag_rank_bear"] = (-comparison_df["delta_bear_mean"]).rank(method="dense")

    ready_top = ready[
        [
            "date",
            "legacy_trade_mode",
            "formal_trade_mode",
            "legacy_selected_count",
            "formal_selected_count",
            "selected_loss",
            "regime_confidence",
            "regime_duration_bars",
            "regime_transition_reason",
            "bull_score",
            "bear_score",
            "score_diff",
            "trend_bull",
            "risk_bull",
            "breadth_bull",
            "participation_bull",
            "trend_bear",
            "risk_bear",
            "breadth_bear",
            "participation_bear",
        ]
    ].sort_values(["selected_loss", "bull_score"], ascending=[False, True])

    summary = {
        "generated_at": datetime.now().isoformat(),
        "legacy_exp_id": LEGACY_EXP_ID,
        "formal_exp_id": FORMAL_EXP_ID,
        "window": {"start": str(semantic_cfg["universe"]["start"]), "end": str(semantic_cfg["universe"]["end"])},
        "bull_to_trans_up_total_days": int(len(bull_to_trans_up)),
        "bull_to_trans_up_ready_days": int(len(ready)),
        "bull_to_trans_up_fallback_days": int(len(fallback)),
        "bull_to_bull_days": int(len(bull_to_bull)),
        "bull_to_trans_up_selected_loss_days": int(len(loss_days)),
        "bull_to_trans_up_selected_loss_total": _sum_int(loss_days["selected_loss"]),
        "reference_bull_to_bull": reference,
        "bull_to_trans_up_ready": ready_summary,
        "bull_to_trans_up_fallback": fallback_summary,
        "bull_to_trans_up_selected_loss": loss_summary,
        "drag_blocks": comparison_rows,
    }

    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    comparison_df.to_csv(OUT_DIR / "block_score_comparison.csv", index=False, encoding="utf-8-sig")
    ready_top.head(120).to_csv(OUT_DIR / "bull_to_trans_up_ready_top_days.csv", index=False, encoding="utf-8-sig")
    loss_by_formal_mode.to_csv(OUT_DIR / "selected_loss_by_formal_mode.csv", index=False, encoding="utf-8-sig")
    ready[["date", "regime_transition_reason"]].astype({"date": "string"}).groupby("regime_transition_reason").size().reset_index(name="days").sort_values("days", ascending=False).to_csv(
        OUT_DIR / "bull_to_trans_up_ready_reason_counts.csv",
        index=False,
        encoding="utf-8-sig",
    )

    report_lines = [
        "# Formal Regime BULL->TRANS_UP Block Drag Analysis",
        "",
        f"- `legacy_exp_id`: `{LEGACY_EXP_ID}`",
        f"- `formal_exp_id`: `{FORMAL_EXP_ID}`",
        f"- `BULL -> TRANS_UP total_days`: `{len(bull_to_trans_up)}`",
        f"- `ready_days(no fallback)`: `{len(ready)}`",
        f"- `fallback_days`: `{len(fallback)}`",
        f"- `selected_loss_days`: `{len(loss_days)}`",
        f"- `selected_loss_total`: `{_sum_int(ready['selected_loss'])}`",
        "",
        "## Means",
        "",
        f"- `BULL->BULL bull_score_mean`: `{reference['bull_score_mean']}`",
        f"- `BULL->TRANS_UP ready bull_score_mean`: `{ready_summary['bull_score_mean']}`",
        f"- `BULL->BULL bear_score_mean`: `{reference['bear_score_mean']}`",
        f"- `BULL->TRANS_UP ready bear_score_mean`: `{ready_summary['bear_score_mean']}`",
        "",
        "## Block Deltas",
        "",
    ]
    for row in comparison_rows:
        report_lines.append(
            f"- `{row['block']}`: bull `{row['bull_to_bull_bull_mean']:.4f} -> {row['bull_to_trans_up_ready_bull_mean']:.4f}`, "
            f"delta `{row['delta_bull_mean']:.4f}`; bear `{row['bull_to_bull_bear_mean']:.4f} -> {row['bull_to_trans_up_ready_bear_mean']:.4f}`, "
            f"delta `{row['delta_bear_mean']:.4f}`"
        )
    report_lines.extend(
        [
            "",
            "## Top Ready Reasons",
            "",
        ]
    )
    for key, value in ready_summary["regime_transition_reason_counts"].items():
        report_lines.append(f"- `{key}`: `{value}`")
    (OUT_DIR / "report.md").write_text("\n".join(report_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
