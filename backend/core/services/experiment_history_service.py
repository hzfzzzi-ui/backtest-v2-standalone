from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from backend.api.shared.paths import experiments_root as _default_experiments_root
from backend.api.shared.json_utils import sanitize_json
from backend.core.config.asset_profiles import build_asset_context
from backend.core.tools.experiment_artifact_access import (
    experiment_surface_flags,
    load_manifest,
    manifest_artifact_rel,
)


def _resolve_experiments_root(experiments_root: Path | None = None) -> Path:
    return Path(experiments_root) if experiments_root is not None else _default_experiments_root()


def _read_index(*, experiments_root: Path | None = None) -> list[dict[str, Any]]:
    index_path = _resolve_experiments_root(experiments_root) / "index.json"
    if not index_path.exists():
        return []
    try:
        entries = json.loads(index_path.read_text(encoding="utf-8"))
        return entries if isinstance(entries, list) else []
    except Exception:
        return []


def _write_index(entries: list[dict[str, Any]], *, experiments_root: Path | None = None) -> None:
    index_path = _resolve_experiments_root(experiments_root) / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _extract_year(value: Any) -> int | None:
    text = str(value or "").strip()
    if len(text) < 4 or not text[:4].isdigit():
        return None
    try:
        return int(text[:4])
    except Exception:
        return None


def _experiment_surface_meta(exp_dir: Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = manifest if isinstance(manifest, dict) else load_manifest(exp_dir)
    artifacts = manifest.get("artifacts") if isinstance((manifest or {}).get("artifacts"), dict) else {}
    perf_rel = str(artifacts.get("perf") or "perf.json").strip()
    config_rel = str(artifacts.get("config") or "config.json").strip()
    perf = _read_json(exp_dir / perf_rel)
    cfg_payload = _read_json(exp_dir / config_rel)
    overrides = cfg_payload.get("overrides") if isinstance(cfg_payload.get("overrides"), dict) else {}
    workbench_cfg = None
    for candidate in (
        overrides.get("original_workbench_config"),
        overrides.get("workbench_config"),
        cfg_payload.get("workbench_config"),
    ):
        if isinstance(candidate, dict):
            workbench_cfg = candidate
            break
    universe_cfg = workbench_cfg.get("universe") if isinstance((workbench_cfg or {}).get("universe"), dict) else {}
    asset_context = build_asset_context(
        (manifest or {}).get("asset_scope"),
        config_json=workbench_cfg if isinstance(workbench_cfg, dict) else cfg_payload,
        metadata_scope=((manifest or {}).get("asset_context") or {}).get("asset_scope")
        if isinstance((manifest or {}).get("asset_context"), dict)
        else None,
    )
    return {
        "cagr": perf.get("cagr") if isinstance(perf, dict) else None,
        "max_drawdown": perf.get("max_drawdown") if isinstance(perf, dict) else None,
        "universe_mode": str((workbench_cfg or {}).get("universe_mode") or ""),
        "membership_mode": str(universe_cfg.get("membership_mode") or ""),
        "start_year": _extract_year(universe_cfg.get("start")),
        "end_year": _extract_year(universe_cfg.get("end")),
        "asset_scope": str(asset_context.get("asset_scope") or ""),
        "asset_profile_id": str(asset_context.get("asset_profile_id") or ""),
        "market_profile_id": str(asset_context.get("market_profile_id") or ""),
    }


def _compact_experiment_label(entry: dict[str, Any]) -> str:
    exp_id = str(entry.get("exp_id") or "").strip()
    label = str(entry.get("label") or exp_id).strip()
    upper = label.upper()
    if not label:
        return exp_id
    if (
        len(label) > 96
        or label.startswith("{")
        or "'PARAMS'" in upper
        or '"PARAMS"' in upper
        or "BREAKOUT_WINDOW" in upper
        or "REGIME_MA" in upper
        or "SECTOR_TOP_PCT" in upper
    ):
        return exp_id or label
    return label


def _read_nav_rows(path: Path, limit: int = 5000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        import pandas as pd

        frame = pd.read_csv(path)
    except Exception:
        return []
    if frame.empty or "date" not in frame.columns:
        return []
    nav_col = None
    for candidate in ("nav", "strategy_nav", "equity", "portfolio_value"):
        if candidate in frame.columns:
            nav_col = candidate
            break
    if nav_col is None:
        return []
    out: list[dict[str, Any]] = []
    for row in frame[["date", nav_col]].tail(int(limit)).itertuples(index=False):
        try:
            out.append({"date": str(row[0])[:10], "nav": float(row[1])})
        except Exception:
            continue
    return out


def list_experiments(*, experiments_root: Path | None = None) -> list[dict[str, Any]]:
    entries = _read_index(experiments_root=experiments_root)
    exp_root = _resolve_experiments_root(experiments_root)
    valid: list[dict[str, Any]] = []
    changed = False
    for entry in entries:
        exp_id = str(entry.get("exp_id", "")).strip()
        exp_dir = exp_root / exp_id
        if not exp_dir.is_dir():
            changed = True
            continue
        flags = experiment_surface_flags(exp_dir)
        if not bool(flags.get("has_manifest")) and not bool(flags.get("has_core_artifacts")):
            changed = True
            continue
        row = dict(entry)
        compact_label = _compact_experiment_label(row)
        if compact_label != str(row.get("label") or "").strip():
            row["label"] = compact_label
            changed = True
        row["has_manifest"] = bool(flags.get("has_manifest"))
        row["has_core_artifacts"] = bool(flags.get("has_core_artifacts"))
        row.update(_experiment_surface_meta(exp_dir))
        valid.append(row)
    if changed or len(valid) != len(entries):
        _write_index(valid, experiments_root=experiments_root)
    valid.sort(key=lambda e: str(e.get("created_at", "")), reverse=True)
    return valid


def delete_experiment(exp_id: str, *, experiments_root: Path | None = None) -> dict[str, Any]:
    import shutil

    exp_dir = _resolve_experiments_root(experiments_root) / exp_id
    if not exp_dir.is_dir():
        raise HTTPException(status_code=404, detail="experiment not found")
    shutil.rmtree(exp_dir, ignore_errors=True)
    entries = _read_index(experiments_root=experiments_root)
    entries = [entry for entry in entries if entry.get("exp_id") != exp_id]
    _write_index(entries, experiments_root=experiments_root)
    return {"status": "deleted"}


def clear_all_experiments(*, experiments_root: Path | None = None) -> dict[str, Any]:
    import shutil

    exp_root = _resolve_experiments_root(experiments_root)
    count = 0
    if exp_root.exists():
        for path in exp_root.iterdir():
            if path.is_dir() and path.name.startswith("exp_"):
                shutil.rmtree(path, ignore_errors=True)
                count += 1
    _write_index([], experiments_root=experiments_root)
    return {"status": "cleared", "count": count}


def compare_experiments(body: dict[str, Any], *, experiments_root: Path | None = None) -> dict[str, Any]:
    exp_ids = [str(value).strip() for value in (body or {}).get("exp_ids", []) if str(value).strip()]
    if len(exp_ids) < 2:
        raise HTTPException(status_code=400, detail="at least 2 exp_ids are required")
    if len(exp_ids) > 8:
        raise HTTPException(status_code=400, detail="at most 8 experiments can be compared at once")

    index_map = {str(item.get("exp_id") or ""): item for item in _read_index(experiments_root=experiments_root)}
    root = _resolve_experiments_root(experiments_root)
    items: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for exp_id in exp_ids:
        exp_dir = root / exp_id
        if not exp_dir.is_dir():
            skipped.append({"exp_id": exp_id, "reason": "experiment_not_found"})
            continue
        manifest = load_manifest(exp_dir)
        perf_rel = manifest_artifact_rel(manifest, "perf") if manifest else None
        nav_rel = manifest_artifact_rel(manifest, "nav") if manifest else None
        if not perf_rel or not nav_rel:
            skipped.append({"exp_id": exp_id, "reason": "missing_manifest_core_artifacts"})
            continue
        perf = _read_json(exp_dir / perf_rel)
        nav_rows = _read_nav_rows(exp_dir / nav_rel)
        if not perf or not nav_rows:
            skipped.append({"exp_id": exp_id, "reason": "unreadable_manifest_core_artifacts"})
            continue
        idx_row = dict(index_map.get(exp_id) or {})
        flags = experiment_surface_flags(exp_dir)
        items.append(
            {
                "exp_id": exp_id,
                "label": _compact_experiment_label(idx_row or {"exp_id": exp_id}),
                "created_at": str(idx_row.get("created_at") or ""),
                "has_manifest": bool(manifest),
                "has_core_artifacts": bool(flags.get("has_core_artifacts")),
                "perf": {
                    "total_return": perf.get("total_return"),
                    "cagr": perf.get("cagr"),
                    "sharpe": perf.get("sharpe"),
                    "max_drawdown": perf.get("max_drawdown"),
                    "trades": perf.get("trades"),
                },
                "nav": nav_rows,
            }
        )

    if len(items) < 2:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "not_comparable",
                "message": "not enough comparable experiments found",
                "skipped": skipped,
            },
        )
    return sanitize_json({"items": items, "skipped": skipped})
