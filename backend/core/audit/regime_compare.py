from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.audit.regime_audit import build_regime_audit_summary

REGIME_COMPARE_WINDOWS: list[dict[str, str]] = [
    {
        "window_key": "2016_2026",
        "label": "2016-2026",
        "start": "2016-03-01",
        "end": "2026-03-01",
    },
    {
        "window_key": "2012_2017",
        "label": "2012-2017",
        "start": "2012-01-04",
        "end": "2017-12-29",
    },
    {
        "window_key": "2012_2026",
        "label": "2012-2026",
        "start": "2012-01-04",
        "end": "2026-03-16",
    },
]


def load_json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid json root: {path}")
    return payload


def build_regime_engine_compare_config(
    source_cfg: dict[str, Any],
    *,
    start: str,
    end: str,
    regime_engine: str,
) -> dict[str, Any]:
    cfg = copy.deepcopy(source_cfg)
    universe = dict(cfg.get("universe") or {})
    universe["start"] = start
    universe["end"] = end
    cfg["universe"] = universe

    regime_cfg = dict(cfg.get("regime_engine") or {})
    regime_cfg["engine"] = str(regime_engine or "ma200_legacy")
    cfg["regime_engine"] = regime_cfg
    return cfg


def summarize_regime_experiment(
    *,
    exp_dir: Path,
    window_key: str,
    window_label: str,
    regime_engine: str,
) -> dict[str, Any]:
    run_meta = load_json_file(exp_dir / "run_meta.json")
    daily_df = pd.read_csv(exp_dir / "portfolio_daily.csv")
    audit_summary = build_regime_audit_summary(daily_df=daily_df, run_meta=run_meta)
    if audit_summary is None:
        raise RuntimeError(f"missing regime audit inputs: {exp_dir}")

    summary = dict(audit_summary.get("summary") or {})
    latest_state = dict(audit_summary.get("latest_state") or {})
    return {
        "window_key": window_key,
        "window_label": window_label,
        "exp_id": exp_dir.name,
        "regime_engine": regime_engine,
        "data_role": str(((run_meta.get("data") or {}) if isinstance(run_meta.get("data"), dict) else {}).get("data_role") or ""),
        "switch_count": int(summary.get("switch_count") or 0),
        "transition_event_count": int(summary.get("transition_event_count") or 0),
        "low_confidence_days": int(summary.get("low_confidence_days") or 0),
        "low_confidence_ratio": float(summary.get("low_confidence_ratio") or 0.0),
        "feature_unavailable_days": int(summary.get("feature_unavailable_days") or 0),
        "regime_confidence_mean": float(summary.get("regime_confidence_mean") or 0.0),
        "state_day_counts_json": json.dumps(summary.get("state_day_counts") or {}, ensure_ascii=False),
        "trade_mode_day_counts_json": json.dumps(summary.get("trade_mode_day_counts") or {}, ensure_ascii=False),
        "transition_reason_counts_json": json.dumps(summary.get("transition_reason_counts") or {}, ensure_ascii=False),
        "latest_state": str(latest_state.get("market_state") or ""),
        "latest_trade_mode": str(latest_state.get("trade_mode") or ""),
    }


def build_regime_compare_delta(
    *,
    legacy_row: dict[str, Any],
    formal_row: dict[str, Any],
) -> dict[str, Any]:
    return {
        "window_key": legacy_row["window_key"],
        "window_label": legacy_row["window_label"],
        "legacy_exp_id": legacy_row["exp_id"],
        "formal_exp_id": formal_row["exp_id"],
        "delta_switch_count": int(formal_row["switch_count"]) - int(legacy_row["switch_count"]),
        "delta_transition_event_count": int(formal_row["transition_event_count"]) - int(legacy_row["transition_event_count"]),
        "delta_low_confidence_days": int(formal_row["low_confidence_days"]) - int(legacy_row["low_confidence_days"]),
        "delta_feature_unavailable_days": int(formal_row["feature_unavailable_days"]) - int(legacy_row["feature_unavailable_days"]),
        "delta_regime_confidence_mean": float(formal_row["regime_confidence_mean"]) - float(legacy_row["regime_confidence_mean"]),
    }


__all__ = [
    "REGIME_COMPARE_WINDOWS",
    "build_regime_compare_delta",
    "build_regime_engine_compare_config",
    "load_json_file",
    "summarize_regime_experiment",
]
