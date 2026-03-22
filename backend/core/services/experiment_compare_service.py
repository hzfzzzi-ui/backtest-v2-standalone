from __future__ import annotations

from typing import Any

from backend.api.shared.json_utils import sanitize_json
from backend.core.services import experiment_history_service, experiment_query_service
from backend.core.tools import baseline_access


def compare_experiments(body: dict[str, Any]) -> dict[str, Any]:
    return sanitize_json(experiment_history_service.compare_experiments(body))


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
                "metrics": {},
            }
        )
    candidate = experiment_query_service.get_execution_regression_contract(str(exp_id or "").strip())
    baseline_snapshot = experiment_query_service.get_execution_regression_contract(baseline_exp_id)
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
            "status": "ok",
            "metrics": metrics,
        }
    )
