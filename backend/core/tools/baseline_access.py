from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.core.tools.experiment_artifact_access import load_manifest


DEFAULT_BASELINE_ID = "baseline_V1"
DEFAULT_BASELINE_EXP_ID = "exp_20260308_021045840_cde0"


def baselines_root() -> Path:
    root = _results_root() / "baselines"
    root.mkdir(parents=True, exist_ok=True)
    return root


def baseline_index_path() -> Path:
    return baselines_root() / "index.json"


def baseline_dir(baseline_id: str) -> Path:
    return baselines_root() / str(baseline_id or "").strip()


def _slugify_baseline_id(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return DEFAULT_BASELINE_ID
    text = re.sub(r"[^0-9A-Za-z_\-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or DEFAULT_BASELINE_ID


def _extract_experiment_workbench_config(exp_id: str) -> dict[str, Any] | None:
    exp_dir = _experiments_root() / str(exp_id or "").strip()
    cfg_path = exp_dir / "config.json"
    if not cfg_path.exists():
        return None
    try:
        payload = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    overrides = payload.get("overrides") if isinstance(payload.get("overrides"), dict) else {}
    for candidate in (
        overrides.get("original_workbench_config"),
        overrides.get("workbench_config"),
        payload.get("workbench_config"),
    ):
        if isinstance(candidate, dict):
            return sanitize_json(candidate)
    return None


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _has_experiment_result(exp_id: str | None) -> bool:
    if not exp_id:
        return False
    exp_dir = _experiments_root() / str(exp_id).strip()
    if not exp_dir.is_dir():
        return False
    manifest = load_manifest(exp_dir)
    return bool(manifest and isinstance(manifest.get("artifacts"), dict))


def _extract_year(value: Any) -> int | None:
    text = str(value or "").strip()
    if len(text) < 4 or not text[:4].isdigit():
        return None
    try:
        return int(text[:4])
    except Exception:
        return None


def _linked_experiment_metrics(exp_id: str | None) -> dict[str, Any]:
    if not exp_id:
        return {}
    exp_dir = _experiments_root() / str(exp_id).strip()
    if not exp_dir.is_dir():
        return {}
    manifest = load_manifest(exp_dir) or {}
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    perf_rel = str(artifacts.get("perf") or "perf.json").strip()
    perf = _read_json(exp_dir / perf_rel) or {}
    return {
        "cagr": perf.get("cagr"),
        "max_drawdown": perf.get("max_drawdown"),
    }


def _record_meta_view(record: dict[str, Any]) -> dict[str, Any]:
    cfg = record.get("config_json") if isinstance(record.get("config_json"), dict) else {}
    universe = cfg.get("universe") if isinstance(cfg.get("universe"), dict) else {}
    linked_metrics = _linked_experiment_metrics(str(record.get("linked_exp_id") or "").strip() or None)
    return {
        "baseline_id": str(record.get("baseline_id") or ""),
        "config_id": str(record.get("baseline_id") or ""),
        "name": str(record.get("name") or record.get("display_name") or record.get("baseline_id") or ""),
        "display_name": str(record.get("display_name") or record.get("name") or record.get("baseline_id") or ""),
        "created_at": str(record.get("created_at") or ""),
        "updated_at": str(record.get("updated_at") or ""),
        "source_type": "baseline",
        "owner": str(record.get("owner") or "manual"),
        "locked": bool(record.get("locked", True)),
        "universe_mode": str(cfg.get("universe_mode") or ""),
        "start_year": _extract_year(universe.get("start")),
        "end_year": _extract_year(universe.get("end")),
        "linked_exp_id": str(record.get("linked_exp_id") or ""),
        "has_result": bool(record.get("has_result")),
        "cagr": linked_metrics.get("cagr"),
        "max_drawdown": linked_metrics.get("max_drawdown"),
        "config_hash": str(record.get("config_hash") or ""),
    }


def normalize_baseline_record(
    record: dict[str, Any] | None,
    *,
    baseline_id_hint: str | None = None,
) -> dict[str, Any]:
    raw = dict(record or {})
    cfg = raw.get("config_json")
    config_json = sanitize_json(dict(cfg)) if isinstance(cfg, dict) else {}
    baseline_id = _slugify_baseline_id(str(raw.get("baseline_id") or baseline_id_hint or raw.get("name") or raw.get("display_name") or DEFAULT_BASELINE_ID))
    now = datetime.now().isoformat()
    created_at = str(raw.get("created_at") or "").strip() or now
    updated_at = str(raw.get("updated_at") or "").strip() or now
    linked_exp_id = str(raw.get("linked_exp_id") or "").strip() or None
    config_hash = json.dumps(config_json, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    config_hash = hashlib.sha1(config_hash.encode("utf-8")).hexdigest()
    normalized = {
        "baseline_id": baseline_id,
        "name": str(raw.get("name") or raw.get("display_name") or baseline_id),
        "display_name": str(raw.get("display_name") or raw.get("name") or baseline_id),
        "created_at": created_at,
        "updated_at": updated_at,
        "owner": str(raw.get("owner") or "manual"),
        "locked": bool(raw.get("locked", True)),
        "linked_exp_id": linked_exp_id,
        "has_result": _has_experiment_result(linked_exp_id),
        "config_hash": config_hash,
        "config_json": config_json,
    }
    return normalized


def load_baseline_record(baseline_id: str) -> dict[str, Any] | None:
    bid = _slugify_baseline_id(baseline_id)
    folder = baseline_dir(bid)
    meta = _read_json(folder / "baseline.json")
    cfg = _read_json(folder / "config.json")
    if not meta or not cfg:
        return None
    return normalize_baseline_record({**meta, "config_json": cfg}, baseline_id_hint=bid)


def write_baseline_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_baseline_record(record)
    folder = baseline_dir(str(normalized.get("baseline_id") or ""))
    folder.mkdir(parents=True, exist_ok=True)

    existing = load_baseline_record(str(normalized.get("baseline_id") or ""))
    if existing:
        normalized["created_at"] = str(existing.get("created_at") or normalized.get("created_at") or "")
    normalized["updated_at"] = datetime.now().isoformat()

    meta = {
        "baseline_id": normalized["baseline_id"],
        "name": normalized["name"],
        "display_name": normalized["display_name"],
        "created_at": normalized["created_at"],
        "updated_at": normalized["updated_at"],
        "owner": normalized["owner"],
        "locked": normalized["locked"],
        "linked_exp_id": normalized.get("linked_exp_id"),
        "has_result": normalized.get("has_result"),
        "config_hash": normalized["config_hash"],
    }
    (folder / "baseline.json").write_text(json.dumps(sanitize_json(meta), ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "config.json").write_text(json.dumps(sanitize_json(normalized["config_json"]), ensure_ascii=False, indent=2), encoding="utf-8")
    write_baseline_index()
    return normalize_baseline_record(normalized)


def list_baseline_records() -> list[dict[str, Any]]:
    ensure_default_baseline_v1()
    rows: list[dict[str, Any]] = []
    for folder in baselines_root().iterdir():
        if not folder.is_dir():
            continue
        record = load_baseline_record(folder.name)
        if not record:
            continue
        rows.append(_record_meta_view(record))
    rows.sort(key=lambda x: (str(x.get("updated_at") or ""), str(x.get("baseline_id") or "")), reverse=True)
    return rows


def write_baseline_index() -> Path:
    rows = list_baseline_records()
    path = baseline_index_path()
    path.write_text(json.dumps(sanitize_json(rows), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def ensure_default_baseline_v1() -> dict[str, Any] | None:
    existing = load_baseline_record(DEFAULT_BASELINE_ID)
    if existing:
        return existing
    cfg = _extract_experiment_workbench_config(DEFAULT_BASELINE_EXP_ID)
    if not isinstance(cfg, dict):
        return None
    return write_baseline_record(
        {
            "baseline_id": DEFAULT_BASELINE_ID,
            "name": DEFAULT_BASELINE_ID,
            "display_name": DEFAULT_BASELINE_ID,
            "owner": "manual",
            "locked": True,
            "linked_exp_id": DEFAULT_BASELINE_EXP_ID,
            "config_json": cfg,
        }
    )


def baseline_meta_view(baseline_id: str) -> dict[str, Any] | None:
    record = load_baseline_record(baseline_id)
    if not record:
        return None
    return _record_meta_view(record)
def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _results_root() -> Path:
    raw = os.environ.get("RESULTS_ROOT", "outputs").strip() or "outputs"
    path = Path(raw)
    if not path.is_absolute():
        path = (_repo_root() / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _experiments_root() -> Path:
    root = _results_root() / "experiments"
    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_json(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
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
