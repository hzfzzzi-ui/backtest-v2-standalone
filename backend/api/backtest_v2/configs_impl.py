from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.api.shared.json_utils import sanitize_json, sanitize_for_json as _sanitize_for_json
from backend.api.backtest_v2.builtin_config_library import (
    _configs_root,
    _ensure_builtin_champion_configs,
    _ensure_builtin_flow_script_config,
)
from backend.core.tools.saved_config_access import (
    create_saved_config_record,
    load_saved_config_record,
    normalize_saved_config_record,
    write_saved_config_record,
)
from backend.core.tools.baseline_access import (
    list_baseline_records,
    load_baseline_record,
    write_baseline_record,
)

router = APIRouter(tags=["backtest_v2"])

class BacktestV2ConfigSaveRequest(BaseModel):
    config_json: dict[str, Any]
    name: str | None = None
    display_name: str | None = None
    tags: list[str] | None = None
    source_type: str | None = None
    owner: str | None = None
    locked: bool | None = None
    baseline_of: str | None = None


class BacktestV2BaselineSaveRequest(BaseModel):
    baseline_id: str | None = None
    name: str | None = None
    display_name: str | None = None
    config_json: dict[str, Any]
    linked_exp_id: str | None = None
    execution_contract_ref: dict[str, Any] | None = None
    status: str | None = None
    effective_period: str | None = None
    superseded_by: str | None = None
    owner: str | None = None
    locked: bool | None = None


@router.post("/api/backtest_v2/configs")
def save_backtest_v2_config(body: BacktestV2ConfigSaveRequest):
    record = create_saved_config_record(
        body.config_json,
        name=str(body.display_name or body.name or ""),
        display_name=str(body.display_name or body.name or ""),
        tags=[str(x) for x in (body.tags or [])],
        source_type=body.source_type,
        owner=body.owner,
        locked=body.locked,
        baseline_of=body.baseline_of,
    )
    stored = write_saved_config_record(record)
    return _sanitize_for_json(stored)


@router.get("/api/backtest_v2/configs/{config_id}")
def get_backtest_v2_config(config_id: str):
    _ensure_builtin_flow_script_config()
    _ensure_builtin_champion_configs()
    obj = load_saved_config_record(config_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"config not found: {config_id}")
    return _sanitize_for_json(obj)


@router.get("/api/backtest_v2/configs")
def list_backtest_v2_configs(latest: int = Query(20, ge=1, le=200)):
    _ensure_builtin_flow_script_config()
    _ensure_builtin_champion_configs()
    root = _configs_root()
    rows: list[dict[str, Any]] = []
    for p in root.glob("*.json"):
        try:
            obj = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        row = normalize_saved_config_record(obj, config_id_hint=p.stem)
        rows.append(
            {
                "config_id": str(row.get("config_id") or p.stem),
                "saved_at": str(row.get("saved_at") or ""),
                "name": str(row.get("name") or row.get("display_name") or ""),
                "display_name": str(row.get("display_name") or row.get("name") or ""),
                "tags": [str(x) for x in (row.get("tags") or [])],
                "config_hash": str(row.get("config_hash") or ""),
                "source_type": str(row.get("source_type") or "derived"),
                "owner": str(row.get("owner") or "manual"),
                "locked": bool(row.get("locked")),
                "baseline_of": row.get("baseline_of"),
                "universe_mode": str((row.get("config_json") or {}).get("universe_mode") or ""),
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


@router.get("/api/backtest_v2/baselines")
def list_backtest_v2_baselines():
    return _sanitize_for_json({"items": list_baseline_records()})


@router.get("/api/backtest_v2/baselines/{baseline_id}")
def get_backtest_v2_baseline(baseline_id: str):
    record = load_baseline_record(baseline_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"baseline not found: {baseline_id}")
    return _sanitize_for_json(record)


@router.post("/api/backtest_v2/baselines")
def save_backtest_v2_baseline(body: BacktestV2BaselineSaveRequest):
    record = write_baseline_record(
        {
            "baseline_id": str(body.baseline_id or body.display_name or body.name or "").strip(),
            "name": str(body.name or body.display_name or body.baseline_id or "").strip(),
            "display_name": str(body.display_name or body.name or body.baseline_id or "").strip(),
            "config_json": sanitize_json(body.config_json),
            "linked_exp_id": str(body.linked_exp_id or "").strip() or None,
            "execution_contract_ref": sanitize_json(body.execution_contract_ref) if isinstance(body.execution_contract_ref, dict) else None,
            "status": str(body.status or "").strip() or None,
            "effective_period": str(body.effective_period or "").strip() or None,
            "superseded_by": str(body.superseded_by or "").strip() or None,
            "owner": str(body.owner or "manual"),
            "locked": True if body.locked is None else bool(body.locked),
        }
    )
    return _sanitize_for_json(record)
