from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from backend.api.shared.json_utils import sanitize_json
from backend.core.services import experiment_history_service, experiment_query_service
from backend.core.tools import baseline_access


def compare_experiments(body: dict[str, Any]) -> dict[str, Any]:
    return sanitize_json(experiment_history_service.compare_experiments(body))


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _detect_display_layer_conflicts(
    *,
    baseline_id: str,
    baseline_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    perf = baseline_snapshot.get("perf") if isinstance(baseline_snapshot.get("perf"), dict) else {}
    baseline_dir = baseline_access.baseline_dir(baseline_id)
    champion = _read_json(baseline_dir / "machine" / "latest_champion.json") or {}
    champion_perf = champion.get("perf") if isinstance(champion.get("perf"), dict) else {}
    if not champion_perf:
        return []
    mismatched_fields: list[dict[str, Any]] = []
    for key in ("cagr", "max_drawdown", "sharpe", "trades", "turnover", "calmar"):
        canonical_value = perf.get(key)
        display_value = champion_perf.get(key)
        if canonical_value is None and display_value is None:
            continue
        if canonical_value != display_value:
            mismatched_fields.append(
                {
                    "field": key,
                    "linked_exp_value": canonical_value,
                    "display_value": display_value,
                }
            )
    if not mismatched_fields:
        return []
    return sanitize_json(
        [
            {
                "artifact": f"outputs/baselines/{baseline_id}/machine/latest_champion.json",
                "kind": "display_layer_conflict",
                "fields": mismatched_fields,
            }
        ]
    )


def _baseline_perf_from_ledger(*, baseline_id: str, linked_exp_id: str) -> dict[str, Any] | None:
    ledger_path = baseline_access.baseline_dir(baseline_id) / "machine" / "experiment_ledger.jsonl"
    if not ledger_path.exists():
        return None
    for raw in ledger_path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if str(payload.get("exp_id") or "").strip() != linked_exp_id:
            continue
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        perf = summary.get("perf") if isinstance(summary.get("perf"), dict) else {}
        if perf:
            return sanitize_json(dict(perf))
    return None


def compare_experiment_to_baseline(*, exp_id: str, baseline_id: str) -> dict[str, Any]:
    baseline = baseline_access.load_baseline_record(baseline_id) or {}
    baseline_exp_id = str(baseline.get("linked_exp_id") or "").strip()
    if not baseline_exp_id:
        return sanitize_json(
            {
                "baseline_id": str(baseline_id or "").strip(),
                "candidate_exp_id": str(exp_id or "").strip(),
                "baseline_exp_id": None,
                "status": "baseline_missing_linked_exp",
                "baseline_source_of_truth": {
                    "kind": "missing_linked_exp",
                    "baseline_id": str(baseline_id or "").strip(),
                    "linked_exp_id": None,
                    "display_layers_are_non_canonical": True,
                },
                "metrics": {},
            }
        )
    candidate = experiment_query_service.get_execution_regression_contract(str(exp_id or "").strip())
    baseline_snapshot: dict[str, Any] | None = None
    baseline_status = "ok"
    baseline_source_of_truth = {
        "kind": "linked_experiment",
        "baseline_id": str(baseline_id or "").strip(),
        "linked_exp_id": baseline_exp_id,
        "display_layers_are_non_canonical": True,
        "display_layer_conflicts": [],
    }
    try:
        baseline_snapshot = experiment_query_service.get_execution_regression_contract(baseline_exp_id)
        baseline_source_of_truth["display_layer_conflicts"] = _detect_display_layer_conflicts(
            baseline_id=str(baseline_id or "").strip(),
            baseline_snapshot=baseline_snapshot,
        )
    except HTTPException as exc:
        if int(getattr(exc, "status_code", 0) or 0) != 404:
            raise
        fallback_perf = _baseline_perf_from_ledger(
            baseline_id=str(baseline_id or "").strip(),
            linked_exp_id=baseline_exp_id,
        )
        if not fallback_perf:
            raise
        baseline_snapshot = {"perf": fallback_perf}
        baseline_status = "baseline_ledger_fallback"
        baseline_source_of_truth = {
            "kind": "baseline_ledger_fallback",
            "baseline_id": str(baseline_id or "").strip(),
            "linked_exp_id": baseline_exp_id,
            "artifact": f"outputs/baselines/{baseline_id}/machine/experiment_ledger.jsonl",
            "display_layers_are_non_canonical": True,
            "display_layer_conflicts": [],
        }
    metrics: dict[str, Any] = {}
    for key in ("total_return", "cagr", "sharpe", "calmar", "max_drawdown", "trades", "turnover"):
        cand_value = (candidate.get("perf") or {}).get(key) if isinstance(candidate.get("perf"), dict) else None
        base_value = (baseline_snapshot.get("perf") or {}).get(key) if isinstance(baseline_snapshot.get("perf"), dict) else None
        try:
            delta = float(cand_value) - float(base_value)
        except Exception:
            delta = None
        metrics[key] = {
            "candidate": cand_value,
            "baseline": base_value,
            "delta": delta,
        }
    return sanitize_json(
        {
            "baseline_id": str(baseline_id or "").strip(),
            "candidate_exp_id": str(exp_id or "").strip(),
            "baseline_exp_id": baseline_exp_id,
            "status": baseline_status,
            "baseline_source_of_truth": baseline_source_of_truth,
            "metrics": metrics,
        }
    )
