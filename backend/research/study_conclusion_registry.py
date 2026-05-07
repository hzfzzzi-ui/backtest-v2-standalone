from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.api.shared.json_utils import sanitize_json


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_outputs_root() -> Path:
    return (_repo_root() / "outputs").resolve()


def _infer_outputs_root(results_dir: str | Path | None) -> Path:
    if results_dir:
        candidate = Path(results_dir).resolve()
        for path in [candidate, *candidate.parents]:
            if path.name == "outputs":
                return path
    return _default_outputs_root()


def _conclusions_root(results_dir: str | Path | None) -> Path:
    root = (_infer_outputs_root(results_dir) / "studies" / "conclusions").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _study_registry_path(study_id: str, *, results_dir: str | Path | None) -> Path:
    parts = [part for part in str(study_id or "").replace("\\", "/").split("/") if part]
    if not parts:
        parts = ["unknown_study"]
    return (_conclusions_root(results_dir) / Path(*parts) / "registry.jsonl").resolve()


def _extract_key_metrics(compare: dict[str, Any] | None) -> dict[str, Any]:
    metrics = compare.get("metrics") if isinstance(compare, dict) else {}
    if not isinstance(metrics, dict):
        return {}
    out: dict[str, Any] = {}
    for key in ("cagr", "sharpe", "max_drawdown", "trades", "turnover", "calmar"):
        row = metrics.get(key)
        if not isinstance(row, dict):
            continue
        out[key] = {
            "candidate": row.get("candidate"),
            "baseline": row.get("baseline"),
            "delta": row.get("delta"),
        }
    return sanitize_json(out)


def _build_summary_short(
    *,
    verdict_status: str,
    verdict_reason: str,
    window_key: str,
    variant_name: str,
) -> str:
    parts = [str(verdict_status or "").strip() or "UNKNOWN"]
    if window_key:
        parts.append(f"window={window_key}")
    if variant_name:
        parts.append(f"variant={variant_name}")
    reason = str(verdict_reason or "").strip()
    if reason:
        parts.append(reason)
    return " | ".join(parts)


def append_study_conclusion(
    *,
    study_id: str,
    compared_baseline_id: str,
    verdict: dict[str, Any] | None,
    exp_id: str | None,
    window_key: str,
    variant_name: str,
    compare: dict[str, Any] | None,
    results_dir: str | Path | None,
) -> dict[str, Any]:
    verdict_payload = dict(verdict or {})
    verdict_status = str(verdict_payload.get("status") or "UNKNOWN").strip() or "UNKNOWN"
    verdict_reason = str(verdict_payload.get("reason") or "").strip()
    baseline_source = (
        sanitize_json(dict(compare.get("baseline_source_of_truth") or {}))
        if isinstance(compare, dict) and isinstance(compare.get("baseline_source_of_truth"), dict)
        else None
    )
    entry = sanitize_json(
        {
            "recorded_at": datetime.now().isoformat(),
            "study_id": str(study_id or "").strip(),
            "compared_baseline_id": str(compared_baseline_id or "").strip(),
            "verdict": verdict_status,
            "summary_short": _build_summary_short(
                verdict_status=verdict_status,
                verdict_reason=verdict_reason,
                window_key=str(window_key or "").strip(),
                variant_name=str(variant_name or "").strip(),
            ),
            "exp_id": str(exp_id or "").strip(),
            "window_key": str(window_key or "").strip(),
            "variant_name": str(variant_name or "").strip(),
            "key_metrics": _extract_key_metrics(compare),
            "baseline_source_of_truth": baseline_source,
        }
    )
    path = _study_registry_path(str(study_id or "").strip(), results_dir=results_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return sanitize_json(
        {
            "registry": str(path.relative_to(_infer_outputs_root(results_dir))).replace("\\", "/"),
            "entry": entry,
        }
    )
