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


DEFAULT_BASELINE_ID = "baseline"
DEFAULT_BASELINE_STATUS = "active"
DEFAULT_BASELINE_SOURCE_OF_TRUTH = "baseline.json.linked_exp_id"
BASELINE_CONFIG_SNAPSHOT_FILENAME = "baseline_config_snapshot.json"
BASELINE_CONFIG_ALIAS_FILENAME = "config.json"


def baselines_root() -> Path:
    root = _results_root() / "baselines"
    root.mkdir(parents=True, exist_ok=True)
    return root


def baseline_index_path() -> Path:
    return baselines_root() / "index.json"


def baseline_dir(baseline_id: str) -> Path:
    return baselines_root() / str(baseline_id or "").strip()


def baseline_config_snapshot_path(baseline_id: str) -> Path:
    return baseline_dir(baseline_id) / BASELINE_CONFIG_SNAPSHOT_FILENAME


def baseline_config_alias_path(baseline_id: str) -> Path:
    return baseline_dir(baseline_id) / BASELINE_CONFIG_ALIAS_FILENAME


def _slugify_baseline_id(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return DEFAULT_BASELINE_ID
    text = re.sub(r"[^0-9A-Za-z_\-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or DEFAULT_BASELINE_ID


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _canonical_contract_hash(payload: dict[str, Any]) -> str:
    body = json.dumps(sanitize_json(dict(payload or {})), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _execution_contract_ref_from_payload(payload: dict[str, Any], *, artifact_rel: str) -> dict[str, Any]:
    return sanitize_json(
        {
            "artifact": str(artifact_rel or "").strip() or None,
            "contract_version": str(payload.get("contract_version") or "").strip() or None,
            "contract_type": str(payload.get("contract_type") or "").strip() or None,
            "asset_scope": str(payload.get("asset_scope") or "").strip() or None,
            "hash": _canonical_contract_hash(payload) if payload else None,
        }
    )


def _resolve_execution_contract_ref(exp_id: str | None) -> dict[str, Any] | None:
    text = str(exp_id or "").strip()
    if not text:
        return None
    exp_dir = _experiments_root() / text
    if not exp_dir.is_dir():
        return None

    run_meta = _read_json(exp_dir / "run_meta.json") or {}
    ref = run_meta.get("execution_contract_ref")
    if isinstance(ref, dict) and ref:
        return sanitize_json(ref)

    manifest = load_manifest(exp_dir) or {}
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    artifact_rel = str(artifacts.get("execution_contract") or "execution_contract.json").strip() or "execution_contract.json"
    exec_payload = _read_json(exp_dir / artifact_rel)
    if not isinstance(exec_payload, dict) or not exec_payload:
        return None
    return _execution_contract_ref_from_payload(exec_payload, artifact_rel=artifact_rel)


def load_baseline_execution_contract(
    baseline_id: str,
    *,
    verify_hash: bool = True,
) -> dict[str, Any]:
    record = load_baseline_record(baseline_id)
    if not isinstance(record, dict) or not record:
        raise FileNotFoundError(f"baseline not found: {baseline_id}")
    linked_exp_id = str(record.get("linked_exp_id") or "").strip()
    if not linked_exp_id:
        raise FileNotFoundError(f"baseline missing linked_exp_id: {baseline_id}")
    ref = record.get("execution_contract_ref") if isinstance(record.get("execution_contract_ref"), dict) else {}
    artifact_rel = str(ref.get("artifact") or "execution_contract.json").strip() or "execution_contract.json"
    artifact_path = Path(artifact_rel)
    if artifact_path.is_absolute():
        path = artifact_path.resolve()
    else:
        path = (_experiments_root() / linked_exp_id / artifact_rel).resolve()
    payload = _read_json(path)
    if not isinstance(payload, dict) or not payload:
        raise FileNotFoundError(f"baseline execution contract not found: {baseline_id} -> {path}")
    expected_hash = str(ref.get("hash") or "").strip()
    actual_hash = _canonical_contract_hash(payload)
    if verify_hash and expected_hash and expected_hash != actual_hash:
        raise ValueError(
            f"baseline execution contract hash mismatch: {baseline_id} expected={expected_hash} actual={actual_hash}"
        )
    return sanitize_json(payload)


def _has_experiment_result(exp_id: str | None) -> bool:
    if not exp_id:
        return False
    exp_dir = _experiments_root() / str(exp_id).strip()
    if not exp_dir.is_dir():
        return False
    manifest = load_manifest(exp_dir)
    return bool(manifest and isinstance(manifest.get("artifacts"), dict))


def _linked_experiment_missing(exp_id: str | None) -> bool:
    text = str(exp_id or "").strip()
    return bool(text) and not (_experiments_root() / text).is_dir()


def _extract_year(value: Any) -> int | None:
    text = str(value or "").strip()
    if len(text) < 4 or not text[:4].isdigit():
        return None
    try:
        return int(text[:4])
    except Exception:
        return None


def _derive_asset_scope(raw: dict[str, Any], config_json: dict[str, Any], execution_contract_ref: dict[str, Any] | None) -> str:
    text = str(raw.get("asset_scope") or config_json.get("asset_scope") or "").strip()
    if text:
        return text
    if isinstance(execution_contract_ref, dict):
        text = str(execution_contract_ref.get("asset_scope") or "").strip()
        if text:
            return text
    if bool(config_json.get("unified_runtime")):
        return "cn_a_multi_sleeve"
    return "cn_a_equity"


def _derive_effective_period(raw: dict[str, Any], config_json: dict[str, Any], execution_contract_ref: dict[str, Any] | None) -> str:
    explicit = str(raw.get("effective_period") or "").strip()
    if explicit:
        return explicit
    universe = config_json.get("universe") if isinstance(config_json.get("universe"), dict) else {}
    start_year = _extract_year(universe.get("start"))
    end_year = _extract_year(universe.get("end"))
    asset_scope = _derive_asset_scope(raw, config_json, execution_contract_ref)
    return f"{asset_scope}:{start_year or 'na'}-{end_year or 'na'}"


def _validate_single_active_baseline(normalized: dict[str, Any]) -> None:
    if str(normalized.get("status") or "").strip() != "active":
        return
    target_period = str(normalized.get("effective_period") or "").strip()
    if not target_period:
        return
    baseline_id = str(normalized.get("baseline_id") or "").strip()
    for folder in baselines_root().iterdir():
        if not folder.is_dir() or folder.name == baseline_id:
            continue
        existing = load_baseline_record(folder.name)
        if not existing:
            continue
        if str(existing.get("status") or "").strip() != "active":
            continue
        if str(existing.get("effective_period") or "").strip() != target_period:
            continue
        raise ValueError(
            f"active baseline already exists for effective_period={target_period}: {existing.get('baseline_id')}"
        )


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


def _baseline_ledger_metrics(*, baseline_id: str, linked_exp_id: str | None) -> dict[str, Any]:
    exp_id = str(linked_exp_id or "").strip()
    if not exp_id:
        return {}
    path = baseline_dir(baseline_id) / "machine" / "experiment_ledger.jsonl"
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except Exception:
        return {}
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if str(payload.get("exp_id") or "").strip() != exp_id:
            continue
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        perf = summary.get("perf") if isinstance(summary.get("perf"), dict) else {}
        if perf:
            return sanitize_json(dict(perf))
    return {}


def _record_meta_view(record: dict[str, Any]) -> dict[str, Any]:
    cfg = record.get("config_json") if isinstance(record.get("config_json"), dict) else {}
    universe = cfg.get("universe") if isinstance(cfg.get("universe"), dict) else {}
    baseline_id = str(record.get("baseline_id") or "")
    linked_exp_id = str(record.get("linked_exp_id") or "").strip()
    linked_metrics = _linked_experiment_metrics(linked_exp_id or None)
    linked_missing = _linked_experiment_missing(linked_exp_id or None)
    ledger_metrics = (
        _baseline_ledger_metrics(baseline_id=baseline_id, linked_exp_id=linked_exp_id)
        if linked_missing
        else {}
    )
    metric_view = linked_metrics or ledger_metrics
    result_source = "linked_experiment" if linked_metrics else "baseline_ledger_snapshot" if ledger_metrics else "none"
    return {
        "baseline_id": baseline_id,
        "config_id": baseline_id,
        "name": str(record.get("name") or record.get("display_name") or record.get("baseline_id") or ""),
        "display_name": str(record.get("display_name") or record.get("name") or record.get("baseline_id") or ""),
        "created_at": str(record.get("created_at") or ""),
        "updated_at": str(record.get("updated_at") or ""),
        "source_type": "baseline",
        "owner": str(record.get("owner") or "manual"),
        "locked": bool(record.get("locked", True)),
        "status": str(record.get("status") or DEFAULT_BASELINE_STATUS),
        "effective_period": str(record.get("effective_period") or ""),
        "superseded_by": str(record.get("superseded_by") or "") or None,
        "baseline_source_of_truth": str(record.get("baseline_source_of_truth") or DEFAULT_BASELINE_SOURCE_OF_TRUTH),
        "universe_mode": str(cfg.get("universe_mode") or ""),
        "membership_mode": str(universe.get("membership_mode") or ""),
        "start_year": _extract_year(universe.get("start")),
        "end_year": _extract_year(universe.get("end")),
        "linked_exp_id": str(record.get("linked_exp_id") or ""),
        "execution_contract_ref": sanitize_json(dict(record.get("execution_contract_ref") or {}))
        if isinstance(record.get("execution_contract_ref"), dict)
        else None,
        "has_result": bool(record.get("has_result")),
        "linked_exp_missing": linked_missing,
        "metric_snapshot_available": bool(metric_view),
        "result_source": result_source,
        "cagr": metric_view.get("cagr"),
        "max_drawdown": metric_view.get("max_drawdown"),
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
    execution_contract_ref_raw = raw.get("execution_contract_ref")
    execution_contract_ref = (
        sanitize_json(dict(execution_contract_ref_raw))
        if isinstance(execution_contract_ref_raw, dict) and execution_contract_ref_raw
        else None
    )
    if execution_contract_ref is None:
        execution_contract_ref = _resolve_execution_contract_ref(linked_exp_id)
    config_hash = json.dumps(config_json, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    config_hash = hashlib.sha1(config_hash.encode("utf-8")).hexdigest()
    status = str(raw.get("status") or DEFAULT_BASELINE_STATUS).strip() or DEFAULT_BASELINE_STATUS
    effective_period = _derive_effective_period(raw, config_json, execution_contract_ref)
    normalized = {
        "baseline_id": baseline_id,
        "name": str(raw.get("name") or raw.get("display_name") or baseline_id),
        "display_name": str(raw.get("display_name") or raw.get("name") or baseline_id),
        "created_at": created_at,
        "updated_at": updated_at,
        "owner": str(raw.get("owner") or "manual"),
        "locked": bool(raw.get("locked", True)),
        "status": status,
        "effective_period": effective_period,
        "superseded_by": str(raw.get("superseded_by") or "").strip() or None,
        "baseline_source_of_truth": DEFAULT_BASELINE_SOURCE_OF_TRUTH,
        "asset_scope": _derive_asset_scope(raw, config_json, execution_contract_ref),
        "linked_exp_id": linked_exp_id,
        "execution_contract_ref": execution_contract_ref,
        "has_result": _has_experiment_result(linked_exp_id),
        "linked_exp_missing": _linked_experiment_missing(linked_exp_id),
        "config_hash": config_hash,
        "config_json": config_json,
    }
    return normalized


def load_baseline_record(baseline_id: str) -> dict[str, Any] | None:
    bid = _slugify_baseline_id(baseline_id)
    folder = baseline_dir(bid)
    meta = _read_json(folder / "baseline.json")
    cfg = _read_json(folder / BASELINE_CONFIG_SNAPSHOT_FILENAME) or _read_json(folder / BASELINE_CONFIG_ALIAS_FILENAME)
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
        if not normalized.get("linked_exp_id") and existing.get("linked_exp_id"):
            normalized["linked_exp_id"] = existing.get("linked_exp_id")
        if not normalized.get("execution_contract_ref") and existing.get("execution_contract_ref"):
            normalized["execution_contract_ref"] = existing.get("execution_contract_ref")
        if not normalized.get("superseded_by") and existing.get("superseded_by"):
            normalized["superseded_by"] = existing.get("superseded_by")
    normalized["updated_at"] = datetime.now().isoformat()
    _validate_single_active_baseline(normalized)

    meta = {
        "baseline_id": normalized["baseline_id"],
        "name": normalized["name"],
        "display_name": normalized["display_name"],
        "created_at": normalized["created_at"],
        "updated_at": normalized["updated_at"],
        "owner": normalized["owner"],
        "locked": normalized["locked"],
        "status": normalized["status"],
        "effective_period": normalized["effective_period"],
        "superseded_by": normalized.get("superseded_by"),
        "baseline_source_of_truth": normalized["baseline_source_of_truth"],
        "asset_scope": normalized.get("asset_scope"),
        "linked_exp_id": normalized.get("linked_exp_id"),
        "execution_contract_ref": normalized.get("execution_contract_ref"),
        "has_result": normalized.get("has_result"),
        "config_hash": normalized["config_hash"],
    }
    (folder / "baseline.json").write_text(json.dumps(sanitize_json(meta), ensure_ascii=False, indent=2), encoding="utf-8")
    config_payload = json.dumps(sanitize_json(normalized["config_json"]), ensure_ascii=False, indent=2)
    (folder / BASELINE_CONFIG_SNAPSHOT_FILENAME).write_text(config_payload, encoding="utf-8")
    (folder / BASELINE_CONFIG_ALIAS_FILENAME).write_text(config_payload, encoding="utf-8")
    write_baseline_index()
    return normalize_baseline_record(normalized)


def list_baseline_records() -> list[dict[str, Any]]:
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
