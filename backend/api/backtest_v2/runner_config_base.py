"""Shared base helpers for runtime config compilation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from backend.api.shared.json_utils import sanitize_json
from backend.core.tools.locked_candidate_presets import build_locked_candidate_cfg


def load_base_config(bt_root: Path) -> dict[str, Any]:
    cfg_path = bt_root / "configs" / "pams_cn_pg.json"
    if not cfg_path.exists():
        cfg_path_alt = bt_root.parent / "configs" / "pams_cn_pg.json"
        if cfg_path_alt.exists():
            cfg_path = cfg_path_alt
        else:
            raise HTTPException(status_code=500, detail=f"missing config template: {cfg_path}")
    return json.loads(cfg_path.read_text(encoding="utf-8-sig"))


def assert_locked_candidate_request_supported(body: Any) -> None:
    forbidden: list[str] = []
    if getattr(body, "symbols", None):
        forbidden.append("symbols")
    if getattr(body, "start_date", None):
        forbidden.append("start_date")
    if getattr(body, "end_date", None):
        forbidden.append("end_date")
    if getattr(body, "benchmark", None):
        forbidden.append("benchmark")
    if getattr(body, "compare_symbol", None):
        forbidden.append("compare_symbol")
    if getattr(body, "initial_capital", None) is not None:
        forbidden.append("initial_capital")
    if getattr(body, "max_positions", None) is not None:
        forbidden.append("max_positions")
    if getattr(body, "base_order_value", None) is not None:
        forbidden.append("base_order_value")
    if getattr(body, "univote_lot_mode", None) is not None:
        forbidden.append("univote_lot_mode")
    if getattr(body, "lot_size", None) is not None:
        forbidden.append("lot_size")
    if getattr(body, "universe_limit", None) is not None:
        forbidden.append("universe_limit")
    if str(getattr(body, "config_path", "") or "").strip():
        forbidden.append("config_path")
    if str(getattr(body, "config_id", "") or "").strip():
        forbidden.append("config_id")
    if getattr(body, "runtime_config_json", None) is not None:
        forbidden.append("runtime_config_json")
    if getattr(body, "config_json", None) is not None:
        forbidden.append("config_json")
    if getattr(body, "workbench_config", None) is not None:
        forbidden.append("workbench_config")
    if getattr(body, "signal_generation", None) is not None:
        forbidden.append("signal_generation")
    if getattr(body, "signal_composition", None) is not None:
        forbidden.append("signal_composition")
    if getattr(body, "enable_strength_rank", None) is not None:
        forbidden.append("enable_strength_rank")
    if getattr(body, "strength_ma", None) is not None:
        forbidden.append("strength_ma")
    if getattr(body, "strength_top_k_mode", None) is not None:
        forbidden.append("strength_top_k_mode")
    if getattr(body, "enable_multifactor_rank", None) is not None:
        forbidden.append("enable_multifactor_rank")
    if getattr(body, "mf_topk", None) is not None:
        forbidden.append("mf_topk")
    if getattr(body, "momentum_top_pct", None) is not None:
        forbidden.append("momentum_top_pct")
    if forbidden:
        raise HTTPException(
            status_code=400,
            detail=(
                "locked baseline candidate does not accept config-mutating request fields: "
                + ", ".join(forbidden)
            ),
        )


def build_locked_candidate_execution_context(
    body: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str, dict[str, Any]]:
    assert_locked_candidate_request_supported(body)
    candidate_name = str(getattr(body, "preset", "") or "").strip().lower()
    try:
        candidate_cfg, candidate_meta = build_locked_candidate_cfg(candidate_name)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"failed to build locked candidate config: {exc}")

    runtime_overrides = dict(candidate_meta.get("locked_runtime_overrides") or {})
    universe_mode = str(runtime_overrides.get("universe_mode") or "").strip()
    if not universe_mode:
        raise HTTPException(status_code=500, detail="locked candidate is missing baseline universe_mode")

    price_adj = str(runtime_overrides.get("price_adj") or "hfq").strip() or "hfq"
    resolved_config_hash = str(candidate_meta.get("candidate_config_hash") or "").strip()
    resolved_config_meta = sanitize_json(
        {
            "candidate_name": str(candidate_meta.get("candidate_name") or ""),
            "source_baseline_exp_id": str(candidate_meta.get("source_baseline_exp_id") or ""),
            "main_change_path": str(candidate_meta.get("main_change_path") or ""),
            "enabled_by_default": bool(candidate_meta.get("enabled_by_default", False)),
        }
    )
    overrides: dict[str, Any] = {
        "config_source": "locked_candidate",
        "resolved_config_mode": "locked_candidate",
        "config_conflict_policy": "locked_candidate",
        "universe_mode": universe_mode,
        "price_adj": price_adj,
        "candidate_context": sanitize_json(candidate_meta),
    }
    if resolved_config_hash:
        overrides["resolved_config_hash"] = resolved_config_hash
    if resolved_config_meta:
        overrides["resolved_config_meta"] = resolved_config_meta
    if getattr(body, "fast_mode", None) is not None:
        overrides["fast_mode"] = bool(getattr(body, "fast_mode"))
    elif "fast_mode" in runtime_overrides:
        overrides["fast_mode"] = bool(runtime_overrides.get("fast_mode"))
    if getattr(body, "workbench_mode", None):
        overrides["workbench_mode"] = str(getattr(body, "workbench_mode"))

    return candidate_cfg, sanitize_json(candidate_meta), overrides, resolved_config_hash, resolved_config_meta
