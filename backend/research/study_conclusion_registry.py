from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.api.shared.json_utils import sanitize_json

FORMAL_VERDICTS = {"confirmed", "falsified", "inconclusive"}
LEGACY_GATE_STATUSES = {"PASS", "FAIL", "UNKNOWN"}


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


def _normalize_gate_status(value: Any) -> str:
    status = str(value or "").strip().upper()
    return status if status in LEGACY_GATE_STATUSES else "UNKNOWN"


def _normalize_formal_verdict(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in FORMAL_VERDICTS:
        return status
    return "inconclusive"


def _normalize_verdict_payload(verdict: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(verdict or {})
    raw_status = str(payload.get("status") or "").strip()
    raw_status_upper = raw_status.upper()
    explicit_formal = payload.get("study_verdict") or payload.get("formal_verdict")
    if explicit_formal is not None:
        formal_status = _normalize_formal_verdict(explicit_formal)
    else:
        formal_status = _normalize_formal_verdict(raw_status)
    gate_status = _normalize_gate_status(payload.get("gate_status") or raw_status_upper)
    reason = str(payload.get("reason") or "").strip()
    gate_reason = str(payload.get("gate_reason") or ("reason" in payload and raw_status_upper in LEGACY_GATE_STATUSES and reason) or "").strip()
    source = str(payload.get("verdict_source") or "").strip()
    if not source:
        source = "formal_input" if raw_status.lower() in FORMAL_VERDICTS else "normalized_legacy_gate_status"
    return sanitize_json(
        {
            "status": formal_status,
            "reason": reason,
            "gate_status": gate_status,
            "gate_reason": gate_reason,
            "gate_checks": (
                payload.get("gate_checks")
                if isinstance(payload.get("gate_checks"), dict)
                else payload.get("checks")
                if isinstance(payload.get("checks"), dict)
                else {}
            ),
            "verdict_source": source,
        }
    )


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
    verdict_payload = _normalize_verdict_payload(verdict)
    verdict_status = str(verdict_payload.get("status") or "inconclusive").strip() or "inconclusive"
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
            "gate_status": verdict_payload.get("gate_status"),
            "gate_reason": verdict_payload.get("gate_reason"),
            "gate_checks": verdict_payload.get("gate_checks"),
            "verdict_source": verdict_payload.get("verdict_source"),
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
