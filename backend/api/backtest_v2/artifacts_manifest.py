from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.api.backtest_v2.artifacts_io import _safe_float, _safe_int, _to_rel
from backend.api.backtest_v2.artifacts_stage_summary import (
    _extract_stage_pipeline_summary,
    _extract_stage_summary,
)
from backend.api.shared.json_utils import sanitize_json

MANIFEST_SCHEMA_VERSION = "backtest_v2_experiment_manifest@2"


def _manifest_config_snapshots(results_dir: Path, artifacts: dict[str, Any]) -> dict[str, str]:
    snapshots: dict[str, str] = {}
    for key, filename in (
        ("input_config", "input_config.json"),
        ("resolved_config", "resolved_config.json"),
        ("compiled_plan", "compiled_plan.json"),
    ):
        rel = str(artifacts.get(key) or "").strip()
        if rel:
            snapshots[key] = rel
            continue
        path = results_dir / filename
        if path.exists():
            snapshots[key] = _to_rel(path, results_dir)
    return snapshots


def _baseline_compare_status(results_dir: Path) -> str:
    path = results_dir / "baseline_compare.json"
    if not path.exists():
        return "NOT_RUN"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return "UNKNOWN"
    status = str(payload.get("status") or "").strip().upper()
    return status or "UNKNOWN"


def _generate_experiment_label(base_cfg: dict[str, Any], overrides: dict[str, Any]) -> str:
    wc = overrides.get("workbench_config") or {}
    strategy = str(wc.get("strategy") or base_cfg.get("signal", {}).get("strategy") or "UNKNOWN").upper()
    sig_gen = wc.get("signal_generation") or {}
    ma_key = "ema" if "EMA" in strategy else "sma"
    ma_cfg = sig_gen.get(ma_key) or wc.get(ma_key) or base_cfg.get("signal", {}).get(ma_key) or {}
    fast = ma_cfg.get("fast_ma") or ma_cfg.get("fast_period") or ""
    slow = ma_cfg.get("slow_ma") or ma_cfg.get("slow_period") or ""
    param_str = f" {fast}/{slow}" if fast and slow else ""

    u_mode = str(overrides.get("universe_mode") or wc.get("universe_mode") or "CUSTOM").upper()
    symbols = overrides.get("symbols") or []
    count_str = f" {len(symbols)}只" if symbols else ""
    price_adj = str(overrides.get("price_adj") or wc.get("price_adj") or "hfq").upper()

    start = str(overrides.get("start_date") or base_cfg.get("universe", {}).get("start") or "")
    end = str(overrides.get("end_date") or base_cfg.get("universe", {}).get("end") or "")
    start_short = start[:7] if len(start) >= 7 else start
    end_short = end[5:7] if len(end) >= 7 else end
    date_str = f"{start_short}~{end_short}" if start and end else ""

    parts = [f"{strategy}{param_str}", f"{u_mode}{count_str}", price_adj]
    if date_str:
        parts.append(date_str)
    return " | ".join(parts)


def write_manifest(results_dir: Path, result: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    artifacts = dict(result.get("artifacts") or {})
    baseline_compare_path = results_dir / "baseline_compare.json"
    if baseline_compare_path.exists():
        artifacts.setdefault("baseline_compare", _to_rel(baseline_compare_path, results_dir))
    config_snapshots = _manifest_config_snapshots(results_dir, artifacts)
    core_keys = (
        "perf",
        "nav",
        "funnel",
        "reason_codes",
        "config",
        "run_meta",
        "trades",
        "daily",
        "input_config",
        "resolved_config",
        "compiled_plan",
        "baseline_compare",
        "audit",
        "stage_summary",
        "execution_lineage_ledger",
        "regime_audit_summary",
        "regime_transition_debug",
        "regime_audit_report",
    )
    core_artifacts = {
        key: str(artifacts.get(key) or "")
        for key in core_keys
        if str(artifacts.get(key) or "").strip()
    }
    stage_summary = _extract_stage_summary(result)
    stage_pipeline = _extract_stage_pipeline_summary(result, stage_summary)
    manifest = {
        "exp_id": str(result.get("exp_id") or ""),
        "experiment_id": str(result.get("exp_id") or ""),
        "status": str(result.get("status") or "OK"),
        "created_at": datetime.now().isoformat(),
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "artifacts": artifacts,
        "config_snapshots": config_snapshots,
        "core_artifacts": core_artifacts,
        "baseline_compare_status": _baseline_compare_status(results_dir),
        "metrics": {
            "total_return": _safe_float(result.get("total_return")),
            "max_drawdown": _safe_float(result.get("max_drawdown")),
            "cagr": _safe_float(result.get("cagr")),
            "sharpe": _safe_float(result.get("sharpe")),
            "trades": _safe_int(result.get("trades")),
            "turnover": _safe_float(result.get("turnover")),
            "effective_execution_start_date": str(result.get("effective_execution_start_date") or ""),
            "metrics_from_effective_start": bool(result.get("metrics_from_effective_start", False)),
        },
    }
    if isinstance(result.get("asset_context"), dict) and result.get("asset_context"):
        asset_context = sanitize_json(dict(result["asset_context"]))
        manifest["asset_scope"] = str(asset_context.get("asset_scope") or "")
        manifest["asset_profile_id"] = str(asset_context.get("asset_profile_id") or "")
        manifest["market_profile_id"] = str(asset_context.get("market_profile_id") or "")
        manifest["execution_profile_id"] = str(asset_context.get("execution_profile_id") or "")
        manifest["asset_context"] = asset_context
    if isinstance(stage_pipeline, dict) and stage_pipeline:
        manifest["stage_pipeline"] = sanitize_json(stage_pipeline)
    if isinstance(stage_summary, dict) and stage_summary:
        manifest["stage_summary"] = sanitize_json(
            {
                "artifact": str(artifacts.get("stage_summary") or ""),
                "schema_version": stage_summary.get("schema_version"),
            }
        )
    path = results_dir / "manifest.json"
    path.write_text(json.dumps(sanitize_json(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return path, manifest


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "_baseline_compare_status",
    "_generate_experiment_label",
    "_manifest_config_snapshots",
    "write_manifest",
]
