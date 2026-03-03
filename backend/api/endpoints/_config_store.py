from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ._paths import _configs_root
from ._utils import sanitize_json, _hash_json, _sanitize_for_json

router = APIRouter(tags=["backtest_v2"])

_FLOW_SCRIPT_CONFIG_ID = "cfg_flow_smoke_v1"


def _flow_script_config_json() -> dict[str, Any]:
    return {
        "mode": "experiment",
        "strategy_pack": "SMA_CROSS",
        "universe_mode": "CUSTOM",
        "universe": {
            "start": "2025-01-01",
            "end": "2025-03-31",
            "benchmark": "000300.SH",
            "symbols": ["600000.SH", "000001.SZ", "600519.SH"],
            "limit": 100,
            "filters": {
                "exclude_st": True,
                "exclude_suspended": True,
                "min_list_days": 120,
                "min_avg_turnover_20d": 100000000,
                "limit_rule": "skip",
            },
        },
        "signal_generation": {
            "enabled": True,
            "strategy": "SMA_CROSS",
            "sma": {"fast_ma": 5, "slow_ma": 20, "entry_buffer_pct": 1.0},
        },
        "signal_composition": {"enabled": True, "compose_mode": "WEIGHTED_SCORE"},
        "exit_rules": {
            "enabled": True,
            "signal_reverse": True,
            "atr_stop": {"enabled": True, "k": 0.8},
            "trailing": {"enabled": False, "k": 2.0},
        },
        "position_risk": {
            "enabled": True,
            "max_positions": 10,
            "single_stock_cap": 0.1,
            "industry_cap": 0.3,
            "lot": 100,
            "cash_shortage_policy": "skip",
        },
        "flow_script": {
            "script_id": "flow_smoke_v1",
            "description": "最小通流：validate -> experiment(run_async) -> group inspect -> execution preview",
            "recommended_preset": "G1-G4",
        },
    }


def _ensure_builtin_flow_script_config() -> None:
    root = _configs_root()
    p = root / f"{_FLOW_SCRIPT_CONFIG_ID}.json"
    cfg_obj = sanitize_json(_flow_script_config_json())
    cfg_hash = _hash_json(cfg_obj)
    saved_at = datetime.now().isoformat()
    payload = {
        "config_id": _FLOW_SCRIPT_CONFIG_ID,
        "config_hash": cfg_hash,
        "saved_at": saved_at,
        "name": "最小通流脚本",
        "tags": ["flow_script", "builtin"],
        "config_json": cfg_obj,
    }
    if p.exists():
        try:
            prev = json.loads(p.read_text(encoding="utf-8-sig"))
            if isinstance(prev, dict) and prev.get("config_hash") == cfg_hash:
                return
        except Exception:
            pass
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class BacktestV2ConfigSaveRequest(BaseModel):
    config_json: dict[str, Any]
    name: str | None = None
    tags: list[str] | None = None


@router.post("/api/backtest_v2/configs")
def save_backtest_v2_config(body: BacktestV2ConfigSaveRequest):
    cfg_obj = sanitize_json(dict(body.config_json or {}))
    cfg_hash = _hash_json(cfg_obj)
    config_id = f"cfg_{cfg_hash[:12]}"
    saved_at = datetime.now().isoformat()
    payload = {
        "config_id": config_id,
        "config_hash": cfg_hash,
        "saved_at": saved_at,
        "name": str(body.name or ""),
        "tags": [str(x) for x in (body.tags or [])],
        "config_json": cfg_obj,
    }
    p = _configs_root() / f"{config_id}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return _sanitize_for_json({"config_id": config_id, "saved_at": saved_at, "config_hash": cfg_hash})


@router.get("/api/backtest_v2/configs/{config_id}")
def get_backtest_v2_config(config_id: str):
    _ensure_builtin_flow_script_config()
    p = _configs_root() / f"{str(config_id)}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"config not found: {config_id}")
    try:
        obj = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"config load failed: {exc}")
    return _sanitize_for_json(obj)


@router.get("/api/backtest_v2/configs")
def list_backtest_v2_configs(latest: int = Query(20, ge=1, le=200)):
    _ensure_builtin_flow_script_config()
    root = _configs_root()
    rows: list[dict[str, Any]] = []
    for p in root.glob("cfg_*.json"):
        try:
            obj = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        rows.append(
            {
                "config_id": str(obj.get("config_id") or p.stem),
                "saved_at": str(obj.get("saved_at") or ""),
                "name": str(obj.get("name") or ""),
                "tags": [str(x) for x in (obj.get("tags") or [])],
                "config_hash": str(obj.get("config_hash") or ""),
            }
        )
    rows.sort(
        key=lambda x: (
            1 if "flow_script" in set(x.get("tags") or []) else 0,
            str(x.get("saved_at") or ""),
        ),
        reverse=True,
    )
    return _sanitize_for_json({"items": rows[: int(latest)]})
