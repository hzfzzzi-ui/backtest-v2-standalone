from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.core.config.asset_profiles import build_asset_context, canonical_asset_scope

try:
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover
    _np = None

_VALID_SOURCE_TYPES = {"baseline", "search", "template", "derived"}
_VALID_OWNERS = {"manual", "claude", "script", "builtin"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _results_root() -> Path:
    raw = os.environ.get("RESULTS_ROOT", "outputs").strip() or "outputs"
    path = Path(raw)
    if not path.is_absolute():
        path = (_repo_root() / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def configs_root() -> Path:
    root = _results_root() / "configs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_json(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if _np is not None and isinstance(obj, _np.generic):
        return sanitize_json(obj.item())
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, tuple):
        return [sanitize_json(v) for v in obj]
    if isinstance(obj, list):
        return [sanitize_json(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): sanitize_json(v) for k, v in obj.items()}
    return str(obj)


def _hash_json(obj: Any) -> str:
    payload = json.dumps(sanitize_json(obj), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def _normalized_tags(value: Any) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in _as_str_list(value):
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _tag_set(value: Any) -> set[str]:
    return {str(item).strip().lower() for item in _as_str_list(value) if str(item).strip()}


def _new_saved_config_id() -> str:
    return f"cfg_{uuid4().hex[:12]}"


def _coerce_source_type(value: Any, *, tags: list[str], config_id: str) -> str:
    text = str(value or "").strip().lower()
    if text in _VALID_SOURCE_TYPES:
        return text
    tag_set = _tag_set(tags)
    if "builtin" in tag_set or "template" in tag_set:
        return "template"
    if "baseline" in tag_set or "champion" in tag_set:
        return "baseline"
    if tag_set.intersection({"search", "matrix", "sweep", "grid", "optimizer"}):
        return "search"
    if config_id.startswith("cfg_flow_"):
        return "template"
    return "derived"


def _coerce_owner(value: Any, *, tags: list[str], source_type: str) -> str:
    text = str(value or "").strip().lower()
    if text in _VALID_OWNERS:
        return text
    tag_set = _tag_set(tags)
    if "builtin" in tag_set:
        return "builtin"
    if "claude" in tag_set:
        return "claude"
    if source_type == "search" or tag_set.intersection({"script", "recent", "backtest_named"}):
        return "script"
    return "manual"


def _coerce_locked(value: Any, *, owner: str, source_type: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return owner == "builtin" or source_type == "baseline"


def _config_meta_view(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    config_json = dict(record.get("config_json") or {})
    asset_context = build_asset_context(config_json=config_json)
    return {
        "config_id": str(record.get("config_id") or ""),
        "config_hash": str(record.get("config_hash") or ""),
        "saved_at": str(record.get("saved_at") or ""),
        "name": str(record.get("name") or record.get("display_name") or ""),
        "display_name": str(record.get("display_name") or record.get("name") or ""),
        "tags": list(record.get("tags") or []),
        "source_type": str(record.get("source_type") or "derived"),
        "owner": str(record.get("owner") or "manual"),
        "locked": bool(record.get("locked")),
        "baseline_of": record.get("baseline_of"),
        "universe_mode": str(config_json.get("universe_mode") or ""),
        "asset_scope": canonical_asset_scope(asset_context.get("asset_scope")),
        "asset_profile_id": str(asset_context.get("asset_profile_id") or ""),
        "market_profile_id": str(asset_context.get("market_profile_id") or ""),
    }


def normalize_saved_config_record(obj: dict[str, Any] | None, *, config_id_hint: str | None = None) -> dict[str, Any]:
    raw = dict(obj or {})
    cfg_json_raw = raw.get("config_json")
    cfg_json = sanitize_json(dict(cfg_json_raw)) if isinstance(cfg_json_raw, dict) else {}
    cfg_hash = _hash_json(cfg_json)
    config_id = str(raw.get("config_id") or config_id_hint or _new_saved_config_id()).strip()
    tags = _normalized_tags(raw.get("tags"))
    source_type = _coerce_source_type(raw.get("source_type"), tags=tags, config_id=config_id)
    owner = _coerce_owner(raw.get("owner"), tags=tags, source_type=source_type)
    locked = _coerce_locked(raw.get("locked"), owner=owner, source_type=source_type)
    display_name = str(raw.get("display_name") or raw.get("name") or "").strip()
    baseline_of = str(raw.get("baseline_of") or "").strip() or None
    saved_at = str(raw.get("saved_at") or "").strip() or datetime.now().isoformat()

    passthrough = {
        k: v
        for k, v in raw.items()
        if k
        not in {
            "config_id",
            "config_hash",
            "saved_at",
            "name",
            "display_name",
            "tags",
            "source_type",
            "owner",
            "locked",
            "baseline_of",
            "config_json",
        }
    }

    normalized = {
        **passthrough,
        "config_id": config_id,
        "config_hash": cfg_hash,
        "saved_at": saved_at,
        "name": display_name,
        "display_name": display_name,
        "tags": tags,
        "source_type": source_type,
        "owner": owner,
        "locked": locked,
        "baseline_of": baseline_of,
        "config_json": cfg_json,
    }
    return normalized


def create_saved_config_record(
    config_json: dict[str, Any] | None,
    *,
    config_id: str | None = None,
    name: str | None = None,
    display_name: str | None = None,
    tags: list[str] | None = None,
    source_type: str | None = None,
    owner: str | None = None,
    locked: bool | None = None,
    baseline_of: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg_obj = sanitize_json(dict(config_json or {}))
    cfg_obj.setdefault("asset_scope", "cn_a_equity")
    cfg_hash = _hash_json(cfg_obj)
    record = {
        **dict(extra or {}),
        "config_id": str(config_id or _new_saved_config_id()),
        "config_hash": cfg_hash,
        "saved_at": datetime.now().isoformat(),
        "name": str(display_name or name or ""),
        "display_name": str(display_name or name or ""),
        "tags": _normalized_tags(tags or []),
        "source_type": source_type,
        "owner": owner,
        "locked": locked,
        "baseline_of": str(baseline_of or "").strip() or None,
        "config_json": cfg_obj,
    }
    return normalize_saved_config_record(record)


def write_saved_config_record(
    record: dict[str, Any],
    *,
    preserve_existing_nonbuiltin: bool = False,
) -> dict[str, Any]:
    normalized = normalize_saved_config_record(record)
    root = configs_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{normalized['config_id']}.json"
    if path.exists() and preserve_existing_nonbuiltin:
        existing = load_saved_config_record(str(normalized.get("config_id") or ""))
        if existing and str(existing.get("owner") or "") != "builtin":
            return existing
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


def load_saved_config_record(config_id: str | None) -> dict[str, Any] | None:
    cfg_id = str(config_id or "").strip()
    if not cfg_id:
        return None
    path = configs_root() / f"{cfg_id}.json"
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return normalize_saved_config_record(obj, config_id_hint=path.stem)


def resolve_runtime_config_source(
    *,
    config_id: str | None,
    runtime_config: dict[str, Any] | None = None,
    draft_config: dict[str, Any] | None,
) -> dict[str, Any]:
    saved_record = load_saved_config_record(config_id)
    runtime_cfg = sanitize_json(dict(runtime_config)) if isinstance(runtime_config, dict) else None
    runtime_hash = _hash_json(runtime_cfg) if isinstance(runtime_cfg, dict) else None
    draft_cfg = sanitize_json(dict(draft_config)) if isinstance(draft_config, dict) else None
    draft_hash = _hash_json(draft_cfg) if isinstance(draft_cfg, dict) else None

    if runtime_cfg is not None:
        resolved_meta = _config_meta_view(saved_record)
        if saved_record is not None:
            saved_hash = str(saved_record.get("config_hash") or "")
            if runtime_hash and runtime_hash == saved_hash:
                return {
                    "config_source": "runtime_config_json",
                    "resolved_config_mode": "loaded_config_runtime",
                    "resolved_config_id": str(saved_record.get("config_id") or ""),
                    "resolved_config_hash": runtime_hash,
                    "resolved_config_meta": resolved_meta,
                    "effective_config_json": runtime_cfg,
                    "runtime_config_hash": runtime_hash,
                    "draft_config_hash": draft_hash,
                    "draft_config_present": draft_cfg is not None,
                    "config_conflict_policy": "runtime_matches_config_id",
                }
            return {
                "config_source": "runtime_config_json",
                "resolved_config_mode": "loaded_dirty_runtime",
                "resolved_config_id": str(saved_record.get("config_id") or ""),
                "resolved_config_hash": runtime_hash,
                "resolved_config_meta": resolved_meta,
                "effective_config_json": runtime_cfg,
                "runtime_config_hash": runtime_hash,
                "draft_config_hash": draft_hash,
                "draft_config_present": draft_cfg is not None,
                "config_conflict_policy": "config_id_provenance_only",
            }
        return {
            "config_source": "runtime_config_json",
            "resolved_config_mode": "draft_runtime",
            "resolved_config_id": None,
            "resolved_config_hash": runtime_hash,
            "resolved_config_meta": None,
            "effective_config_json": runtime_cfg,
            "runtime_config_hash": runtime_hash,
            "draft_config_hash": draft_hash,
            "draft_config_present": draft_cfg is not None,
            "config_conflict_policy": "runtime_only",
        }

    if saved_record is not None:
        conflict_policy = "saved_config_only"
        if draft_cfg is not None:
            if draft_hash and draft_hash == str(saved_record.get("config_hash") or ""):
                conflict_policy = "saved_matches_draft"
            else:
                conflict_policy = "config_id_overrides_workbench"
        return {
            "config_source": "config_id",
            "resolved_config_mode": "saved_config_run",
            "resolved_config_id": str(saved_record.get("config_id") or ""),
            "resolved_config_hash": str(saved_record.get("config_hash") or ""),
            "resolved_config_meta": _config_meta_view(saved_record),
            "effective_config_json": dict(saved_record.get("config_json") or {}),
            "draft_config_hash": draft_hash,
            "draft_config_present": draft_cfg is not None,
            "config_conflict_policy": conflict_policy,
        }

    if draft_cfg is not None:
        return {
            "config_source": "workbench_config",
            "resolved_config_mode": "draft_run",
            "resolved_config_id": None,
            "resolved_config_hash": draft_hash,
            "resolved_config_meta": None,
            "effective_config_json": draft_cfg,
            "draft_config_hash": draft_hash,
            "draft_config_present": True,
            "config_conflict_policy": "draft_only",
        }

    return {
        "config_source": "none",
        "resolved_config_mode": "none",
        "resolved_config_id": None,
        "resolved_config_hash": None,
        "resolved_config_meta": None,
        "effective_config_json": None,
        "draft_config_hash": None,
        "draft_config_present": False,
        "config_conflict_policy": "none",
    }


def saved_config_meta_view(record: dict[str, Any] | None) -> dict[str, Any] | None:
    return _config_meta_view(record)
