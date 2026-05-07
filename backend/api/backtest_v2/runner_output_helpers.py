"""Runner output snapshot and profile helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.api.shared.json_utils import sanitize_json


def _canonical_contract_hash(payload: dict[str, Any]) -> str:
    body = json.dumps(sanitize_json(dict(payload or {})), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def build_single_execution_contract(
    *,
    runtime_config: dict[str, Any] | None,
    asset_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime_payload = sanitize_json(dict(runtime_config or {}))
    asset_ctx = sanitize_json(
        dict(
            asset_context
            or (runtime_payload.get("asset_context") if isinstance(runtime_payload.get("asset_context"), dict) else {})
            or {}
        )
    )
    asset_scope = str(
        asset_ctx.get("asset_scope")
        or runtime_payload.get("asset_scope")
        or ""
    ).strip()
    return sanitize_json(
        {
            "contract_version": "backtest_execution_contract@1",
            "contract_type": "single_run",
            "asset_scope": asset_scope,
            "runtime_config": runtime_payload,
        }
    )


def build_unified_combo_execution_contract(
    *,
    combo_mode: str,
    benchmark: str,
    weights: dict[str, Any] | None,
    stock_runtime_config: dict[str, Any] | None,
    etf_runtime_config: dict[str, Any] | None,
    stock_execution_overrides: dict[str, Any] | None = None,
    etf_execution_overrides: dict[str, Any] | None = None,
    account_budget_control: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stock_runtime = sanitize_json(dict(stock_runtime_config or {}))
    etf_runtime = sanitize_json(dict(etf_runtime_config or {}))
    stock_overrides = sanitize_json(dict(stock_execution_overrides or {}))
    etf_overrides = sanitize_json(dict(etf_execution_overrides or {}))
    resolved_weights = sanitize_json(dict(weights or {}))
    control = sanitize_json(dict(account_budget_control or {}))
    return sanitize_json(
        {
            "contract_version": "backtest_execution_contract@1",
            "contract_type": "unified_combo",
            "asset_scope": "cn_a_multi_sleeve",
            "combo_policy": {
                "mode": str(combo_mode or "").strip() or "account_budget_controlled_dynamic_mix",
                "benchmark": str(benchmark or "").strip() or "CN_STOCK_ETF_50_50",
                "weights": resolved_weights,
                "account_budget_control": control,
            },
            "components": {
                "stock_component": {
                    "sleeve_id": "cn_stock_trend_alpha_core",
                    "asset_scope": "cn_a_equity",
                    "weight": resolved_weights.get("cn_stock_trend_alpha_core"),
                    "runtime_config": stock_runtime,
                    "execution_overrides": stock_overrides,
                },
                "etf_component": {
                    "sleeve_id": "cn_etf_beta",
                    "asset_scope": "cn_etf",
                    "weight": resolved_weights.get("cn_etf_beta"),
                    "runtime_config": etf_runtime,
                    "execution_overrides": etf_overrides,
                },
            },
        }
    )


def write_execution_contract_snapshot(
    *,
    results_dir: Path,
    execution_contract: dict[str, Any] | None,
    filename: str = "execution_contract.json",
) -> Path | None:
    payload = sanitize_json(dict(execution_contract or {}))
    if not payload:
        return None
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / filename
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def build_execution_contract_ref(
    *,
    execution_contract: dict[str, Any] | None,
    artifact_rel: str | None,
) -> dict[str, Any]:
    payload = sanitize_json(dict(execution_contract or {}))
    return sanitize_json(
        {
            "artifact": str(artifact_rel or "").strip() or None,
            "contract_version": str(payload.get("contract_version") or "").strip() or None,
            "contract_type": str(payload.get("contract_type") or "").strip() or None,
            "asset_scope": str(payload.get("asset_scope") or "").strip() or None,
            "hash": _canonical_contract_hash(payload) if payload else None,
        }
    )


def _write_config_snapshots(
    *,
    result: dict[str, Any],
    input_config: dict[str, Any] | None,
    resolved_config: dict[str, Any] | None,
    compiled_plan: dict[str, Any] | None,
) -> None:
    results_dir_raw = str(result.get("results_dir") or "").strip()
    if not results_dir_raw:
        return
    results_dir = Path(results_dir_raw)
    results_dir.mkdir(parents=True, exist_ok=True)

    snapshots = {
        "input_config.json": sanitize_json(dict(input_config or {})),
        "resolved_config.json": sanitize_json(dict(resolved_config or {})),
        "compiled_plan.json": sanitize_json(dict(compiled_plan or {})),
    }
    for filename, payload in snapshots.items():
        (results_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

def _attach_run_profile_summary(result: dict[str, Any]) -> None:
    if not isinstance(result, dict):
        return
    results_dir_raw = str(result.get("results_dir") or "").strip()
    if not results_dir_raw:
        return
    rp = Path(results_dir_raw) / "run_profile.json"
    if not rp.exists():
        return
    try:
        obj = json.loads(rp.read_text(encoding="utf-8-sig"))
    except Exception:
        return
    stages = obj.get("stage_seconds") if isinstance(obj.get("stage_seconds"), dict) else {}
    summary: dict[str, Any] = {
        "run_profile_path": str(rp),
        "total_wall_seconds": float(obj.get("total_wall_seconds", 0.0) or 0.0),
        "stage_seconds": {str(k): float(v or 0.0) for k, v in stages.items()},
        "symbols_count": int(obj.get("symbols_count", 0) or 0),
        "trading_days": int(obj.get("trading_days", 0) or 0),
        "variant_count": int(obj.get("variant_count", 0) or 0),
        "row_count": int(obj.get("row_count", 0) or 0),
        "rows_per_second": float(obj.get("rows_per_second", 0.0) or 0.0),
        "bottleneck_stage": str(obj.get("bottleneck_stage") or ""),
        "bottleneck_label": str(obj.get("bottleneck_label") or "BOTTLENECK_UNKNOWN"),
    }
    perf = obj.get("perf") if isinstance(obj.get("perf"), dict) else {}
    if perf:
        summary["perf"] = {
            "db_load_seconds": float(perf.get("db_load_seconds", 0.0) or 0.0),
            "precompute_seconds": float(perf.get("precompute_seconds", 0.0) or 0.0),
            "simulation_seconds": float(perf.get("simulation_seconds", 0.0) or 0.0),
            "io_write_seconds": float(perf.get("io_write_seconds", 0.0) or 0.0),
            "db_queries": int(perf.get("db_queries", 0) or 0),
            "cache_hit_rate": float(perf.get("cache_hit_rate", 0.0) or 0.0),
        }
    tips: list[str] = []
    b = summary["bottleneck_label"]
    if b == "BOTTLENECK_DATA_LOAD":
        tips.append("数据加载是主要瓶颈：建议减少 universe_limit 或缩短回测区间。")
    elif b == "BOTTLENECK_SIMULATION":
        tips.append("仿真执行是主要瓶颈：建议启用 fast_mode 并关闭非必要明细写盘。")
    elif b == "BOTTLENECK_PRECOMPUTE":
        tips.append("预计算是主要瓶颈：建议缩短 lookback 或减少因子维度。")
    elif b == "BOTTLENECK_IO":
        tips.append("写盘是主要瓶颈：建议关闭 trades/candidates 明细输出。")
    if float(summary.get("rows_per_second", 0.0) or 0.0) <= 0.0:
        tips.append("当前 rows_per_second=0，建议检查实验是否无有效分组输出。")
    summary["optimization_tips"] = tips
    result["run_profile_summary"] = summary

