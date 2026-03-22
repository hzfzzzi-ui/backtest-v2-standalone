from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.api.shared.paths import bt_root as _bt_root
from backend.api.backtest_v2.runner_config_helpers import _compile_semantic_config_bundle, _load_base_config
from backend.core.audit.regime_audit import build_regime_audit_summary, write_regime_audit_artifacts
from backend.core.audit.regime_compare import REGIME_COMPARE_WINDOWS
from backend.core.audit.regime_compare import build_regime_compare_delta
from backend.core.audit.regime_compare import build_regime_engine_compare_config
from backend.core.audit.regime_compare import load_json_file
from backend.core.audit.regime_compare import summarize_regime_experiment
from backend.core.config.loader import load_config
from backend.core.engine_vector.breakout_signal_provider import _coerce_regime_engine_cfg
from backend.core.engine_vector.breakout_signal_provider import _build_legacy_market_filter_state
from backend.core.engine_vector.data_matrix import build_ohlc_matrices_from_history
from backend.core.engine_vector.regime_engine_evaluator import evaluate_formal_regime_engine
from backend.core.engine_vector.regime_engine_inputs import build_formal_regime_feature_bundle
from backend.core.tools.data_bundle_builder import build_data_bundle
from backend.core.tools.experiment_runner import DEFAULT_EXPERIMENT_SYMBOLS
from backend.core.tools.experiment_runtime_access import run_experiment_sync

ROOT = Path(__file__).resolve().parents[3]
BASELINE_ROOT = ROOT / "outputs" / "baselines"
OPS_ROOT = ROOT / "outputs" / "ops"

BASELINE_V10_1_ID = "baseline_V10_1"
ASSET_SCOPE = "cn_a_equity"
OPS_DIR = OPS_ROOT / "compare_regime_engines_three_windows_20260320"


def _base_config() -> dict[str, Any]:
    return load_json_file(BASELINE_ROOT / BASELINE_V10_1_ID / "config.json")


def _run(cfg: dict[str, Any]) -> str:
    result = run_experiment_sync(
        {
            "preset": "single",
            "asset_scope": ASSET_SCOPE,
            "workbench_config": cfg,
        }
    )
    if not isinstance(result, dict):
        raise RuntimeError("runtime service returned non-dict result")
    exp_id = str(result.get("exp_id") or "").strip()
    status = str(result.get("status") or "").strip().upper()
    if not exp_id or status != "OK":
        raise RuntimeError(f"experiment run failed: {result!r}")
    return exp_id


def _exp_dir(exp_id: str) -> Path:
    path = ROOT / "outputs" / "experiments" / exp_id
    if not path.exists():
        raise RuntimeError(f"missing experiment dir: {path}")
    return path


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _fmt_num(value: Any, digits: int = 4) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return ""


def _selected_windows() -> list[dict[str, str]]:
    raw = str(os.environ.get("REGIME_COMPARE_WINDOW_KEYS") or "").strip()
    if not raw:
        return list(REGIME_COMPARE_WINDOWS)
    wanted = {item.strip() for item in raw.split(",") if item.strip()}
    out = [item for item in REGIME_COMPARE_WINDOWS if str(item.get("window_key") or "") in wanted]
    if not out:
        raise RuntimeError(f"no windows matched REGIME_COMPARE_WINDOW_KEYS={raw!r}")
    return out


def _state_only_window_keys() -> set[str]:
    raw = str(os.environ.get("REGIME_COMPARE_LIGHTWEIGHT_WINDOW_KEYS") or "").strip()
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def _ops_dir() -> Path:
    raw = str(os.environ.get("REGIME_COMPARE_OUTPUT_DIR") or "").strip()
    if not raw:
        return OPS_DIR
    path = Path(raw)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    return path


def _compile_runtime_bundle(semantic_cfg: dict[str, Any], *, config_source: str) -> tuple[dict[str, Any], dict[str, Any]]:
    compiled = _compile_semantic_config_bundle(
        base_cfg=_load_base_config(_bt_root()),
        body=None,
        semantic_cfg=semantic_cfg,
        config_source=config_source,
        use_body_universe_fields=False,
    )
    runtime_cfg = dict(compiled.get("runtime_config") or {})
    if not runtime_cfg:
        raise RuntimeError("semantic config compile returned empty runtime_config")
    compiled_plan = dict(compiled.get("compiled_plan") or {})
    execution_overrides = dict(compiled_plan.get("execution_overrides") or {})
    return runtime_cfg, execution_overrides


def _runtime_overrides(runtime_cfg: dict[str, Any], semantic_cfg: dict[str, Any]) -> dict[str, Any]:
    universe_mode = str(
        semantic_cfg.get("universe_mode")
        or runtime_cfg.get("universe_mode")
        or "CUSTOM"
    ).strip()
    universe = dict(runtime_cfg.get("universe") or {})
    data_source = dict(runtime_cfg.get("data_source") or {})
    return {
        "asset_scope": str(runtime_cfg.get("asset_scope") or ASSET_SCOPE),
        "universe_mode": universe_mode,
        "price_adj": str(universe.get("price_adj") or "hfq"),
        "data_role": str(data_source.get("data_role") or "").strip(),
        "asset_context": dict(runtime_cfg.get("asset_context") or {}),
    }


def _build_state_only_daily_frame(
    *,
    trading_days: list[Any],
    regime_engine: str,
    market_state: Any,
    trade_mode: Any,
    regime_confidence: Any,
    regime_duration_bars: Any,
    regime_transition_reason: Any,
    feature_availability: Any,
) -> pd.DataFrame:
    state_arr = market_state
    trade_mode_arr = trade_mode
    confidence_arr = regime_confidence
    duration_arr = regime_duration_bars
    reason_arr = regime_transition_reason
    feature_arr = feature_availability

    rows: list[dict[str, Any]] = []
    for idx, day in enumerate(list(trading_days or ())):
        state_code = int(state_arr[idx]) if state_arr is not None and idx < len(state_arr) else 0
        trade_mode_code = int(trade_mode_arr[idx]) if trade_mode_arr is not None and idx < len(trade_mode_arr) else 0
        feature_payload = feature_arr[idx] if feature_arr is not None and idx < len(feature_arr) else {}
        feature_map = dict(feature_payload) if isinstance(feature_payload, dict) else {}
        rows.append(
            {
                "date": pd.Timestamp(day).strftime("%Y-%m-%d"),
                "market_state": ("BULL", "TRANS_DOWN", "TRANS_UP", "BEAR")[state_code],
                "trade_mode": ("TREND_MAIN", "TREND_LIGHT", "NO_TRADE")[trade_mode_code],
                "regime_engine": str(regime_engine or "ma200_legacy"),
                "regime_confidence": float(confidence_arr[idx]) if confidence_arr is not None and idx < len(confidence_arr) else None,
                "regime_duration_bars": int(duration_arr[idx]) if duration_arr is not None and idx < len(duration_arr) else None,
                "regime_transition_reason": str(reason_arr[idx] or "") if reason_arr is not None and idx < len(reason_arr) else "",
                "feature_availability_json": json.dumps(feature_map, ensure_ascii=False),
            }
        )
    return pd.DataFrame(rows)


def _lightweight_run_meta(cfg_obj: Any) -> dict[str, Any]:
    return {
        "data": {
            "data_role": str(getattr(getattr(cfg_obj, "data_source", None), "data_role", "") or ""),
        },
        "regime": {
            "engine": str(getattr(getattr(cfg_obj, "regime_engine", None), "engine", "ma200_legacy") or "ma200_legacy"),
            "persistence": {
                "confidence_floor": float(
                    getattr(getattr(getattr(cfg_obj, "regime_engine", None), "persistence", None), "confidence_floor", 0.0)
                    or 0.0
                ),
            },
            "feature_availability_contract": {
                "required_blocks": list(
                    getattr(getattr(getattr(cfg_obj, "regime_engine", None), "fallback", None), "required_blocks", []) or []
                ),
            },
            "compare_mode": "state_only",
        },
    }


def _run_lightweight_regime_summary(
    *,
    semantic_cfg: dict[str, Any],
    window: dict[str, str],
    regime_engine: str,
    results_root: Path,
) -> dict[str, Any]:
    window_cfg = build_regime_engine_compare_config(
        semantic_cfg,
        start=window["start"],
        end=window["end"],
        regime_engine=regime_engine,
    )
    runtime_cfg, execution_overrides = _compile_runtime_bundle(
        window_cfg,
        config_source=f"{BASELINE_V10_1_ID}:{window['window_key']}:{regime_engine}:state_only",
    )
    overrides = _runtime_overrides(runtime_cfg, window_cfg)

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as fh:
        fh.write(json.dumps(runtime_cfg, ensure_ascii=False, indent=2))
        runtime_cfg_path = Path(fh.name).resolve()

    try:
        cfg_obj, _ = load_config(runtime_cfg_path)
        cfg_obj.regime_engine = _coerce_regime_engine_cfg(cfg_obj.regime_engine)
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
        if regime_engine == "market_regime_framework":
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
            market_state = formal_eval.market_state
            trade_mode = formal_eval.trade_mode
            regime_confidence = formal_eval.regime_confidence
            regime_duration_bars = formal_eval.regime_duration_bars
            regime_transition_reason = formal_eval.regime_transition_reason
            feature_availability = formal_eval.feature_availability
        else:
            market_state = legacy_market_state
            trade_mode = legacy_trade_mode
            regime_confidence = np.full(len(bundle.trading_days), np.nan, dtype=float)
            regime_duration_bars = [0] * len(bundle.trading_days)
            regime_transition_reason = [""] * len(bundle.trading_days)
            feature_availability = [{} for _ in bundle.trading_days]
        daily_df = _build_state_only_daily_frame(
            trading_days=bundle.trading_days,
            regime_engine=regime_engine,
            market_state=market_state,
            trade_mode=trade_mode,
            regime_confidence=regime_confidence,
            regime_duration_bars=regime_duration_bars,
            regime_transition_reason=regime_transition_reason,
            feature_availability=feature_availability,
        )
        run_meta = _lightweight_run_meta(cfg_obj)
        window_dir = results_root / f"{window['window_key']}_{regime_engine}_state_only"
        window_dir.mkdir(parents=True, exist_ok=True)
        write_regime_audit_artifacts(
            results_dir=window_dir,
            daily_df=daily_df,
            run_meta=run_meta,
        )
        audit_summary = build_regime_audit_summary(daily_df=daily_df, run_meta=run_meta)
        if audit_summary is None:
            raise RuntimeError(f"state-only audit summary is empty: {window['window_key']} / {regime_engine}")
        summary = dict(audit_summary.get("summary") or {})
        latest_state = dict(audit_summary.get("latest_state") or {})
        return {
            "window_key": window["window_key"],
            "window_label": window["label"],
            "exp_id": f"state_only:{window['window_key']}:{regime_engine}",
            "regime_engine": regime_engine,
            "compare_mode": "state_only",
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
    finally:
        try:
            runtime_cfg_path.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> None:
    results_dir = _ops_dir()
    results_dir.mkdir(parents=True, exist_ok=True)
    source_cfg = _base_config()
    rows: list[dict[str, Any]] = []
    delta_rows: list[dict[str, Any]] = []
    windows = _selected_windows()
    lightweight_windows = _state_only_window_keys()

    for window in windows:
        if window["window_key"] in lightweight_windows:
            legacy_row = _run_lightweight_regime_summary(
                semantic_cfg=source_cfg,
                window=window,
                regime_engine="ma200_legacy",
                results_root=results_dir,
            )
            formal_row = _run_lightweight_regime_summary(
                semantic_cfg=source_cfg,
                window=window,
                regime_engine="market_regime_framework",
                results_root=results_dir,
            )
        else:
            legacy_exp = _run(
                build_regime_engine_compare_config(
                    source_cfg,
                    start=window["start"],
                    end=window["end"],
                    regime_engine="ma200_legacy",
                )
            )
            formal_exp = _run(
                build_regime_engine_compare_config(
                    source_cfg,
                    start=window["start"],
                    end=window["end"],
                    regime_engine="market_regime_framework",
                )
            )
            legacy_row = summarize_regime_experiment(
                exp_dir=_exp_dir(legacy_exp),
                window_key=window["window_key"],
                window_label=window["label"],
                regime_engine="ma200_legacy",
            )
            formal_row = summarize_regime_experiment(
                exp_dir=_exp_dir(formal_exp),
                window_key=window["window_key"],
                window_label=window["label"],
                regime_engine="market_regime_framework",
            )
            legacy_row["compare_mode"] = "full_experiment"
            formal_row["compare_mode"] = "full_experiment"
        rows.extend([legacy_row, formal_row])
        delta_rows.append(build_regime_compare_delta(legacy_row=legacy_row, formal_row=formal_row))

    _write_csv(results_dir / "window_regime_comparison.csv", rows)
    _write_csv(results_dir / "window_regime_delta.csv", delta_rows)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "comparison_name": "compare_regime_engines_three_windows",
        "windows": windows,
        "rows": rows,
        "delta_rows": delta_rows,
        "lightweight_windows": sorted(lightweight_windows),
    }
    (results_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        "# Regime Engine Comparison (Three Windows)",
        "",
        "## Conclusion",
        "",
        "- This is a regime-engine comparison page, not a strategy-alpha replacement page.",
        "- Both sides reuse the same baseline strategy shell.",
        "- The only intended experimental difference is `regime_engine`.",
        "",
        "## Window Comparison",
        "",
        "| Window | Mode | Engine | Exp ID | Switch Count | Transition Events | Low Confidence Days | Feature Unavailable Days | Mean Confidence |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        report_lines.append(
            f"| {row['window_label']} | `{row.get('compare_mode') or 'full_experiment'}` | `{row['regime_engine']}` | `{row['exp_id']}` | "
            f"{row['switch_count']} | {row['transition_event_count']} | {row['low_confidence_days']} | "
            f"{row['feature_unavailable_days']} | {_fmt_num(row['regime_confidence_mean'])} |"
        )
    report_lines.extend(
        [
            "",
            "## Delta (formal - legacy)",
            "",
            "| Window | dSwitch | dTransitions | dLowConfidence | dFeatureUnavailable | dMeanConfidence |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in delta_rows:
        report_lines.append(
            f"| {row['window_label']} | {row['delta_switch_count']} | {row['delta_transition_event_count']} | "
            f"{row['delta_low_confidence_days']} | {row['delta_feature_unavailable_days']} | "
            f"{_fmt_num(row['delta_regime_confidence_mean'])} |"
        )

    (results_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
