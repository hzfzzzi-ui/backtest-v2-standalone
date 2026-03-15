from __future__ import annotations

from typing import Any

from backend.api.shared.json_utils import sanitize_json


def evaluate_hard_gates(*, hard_gates: dict[str, Any], perf: dict[str, Any], compare: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    checks: dict[str, Any] = {}

    def _num(value: Any) -> float | None:
        try:
            return float(value)
        except Exception:
            return None

    for key in ("min_cagr", "min_sharpe", "min_calmar", "min_total_return"):
        if key in hard_gates:
            metric_name = key.replace("min_", "")
            actual = _num(perf.get(metric_name))
            required = _num(hard_gates.get(key))
            passed = actual is not None and required is not None and actual >= required
            checks[key] = {"required": required, "actual": actual, "passed": passed}
            if not passed:
                failures.append(f"{metric_name}<{required}")

    if "max_drawdown_floor" in hard_gates:
        actual = _num(perf.get("max_drawdown"))
        floor = _num(hard_gates.get("max_drawdown_floor"))
        passed = actual is not None and floor is not None and actual >= floor
        checks["max_drawdown_floor"] = {"required": floor, "actual": actual, "passed": passed}
        if not passed:
            failures.append(f"max_drawdown<{floor}")

    if "min_trades" in hard_gates:
        actual = perf.get("trades")
        try:
            actual_int = int(actual)
        except Exception:
            actual_int = None
        required = int(hard_gates.get("min_trades"))
        passed = actual_int is not None and actual_int >= required
        checks["min_trades"] = {"required": required, "actual": actual_int, "passed": passed}
        if not passed:
            failures.append(f"trades<{required}")

    if "min_cagr_delta" in hard_gates:
        metric = ((compare.get("metrics") or {}).get("cagr") or {}) if isinstance(compare.get("metrics"), dict) else {}
        actual = _num(metric.get("delta"))
        required = _num(hard_gates.get("min_cagr_delta"))
        passed = actual is not None and required is not None and actual >= required
        checks["min_cagr_delta"] = {"required": required, "actual": actual, "passed": passed}
        if not passed:
            failures.append(f"cagr_delta<{required}")

    if "max_drawdown_delta_floor" in hard_gates:
        metric = ((compare.get("metrics") or {}).get("max_drawdown") or {}) if isinstance(compare.get("metrics"), dict) else {}
        actual = _num(metric.get("delta"))
        required = _num(hard_gates.get("max_drawdown_delta_floor"))
        passed = actual is not None and required is not None and actual >= required
        checks["max_drawdown_delta_floor"] = {"required": required, "actual": actual, "passed": passed}
        if not passed:
            failures.append(f"max_drawdown_delta<{required}")

    status = "PASS" if not failures else "FAIL"
    reason = "" if not failures else "; ".join(failures)
    next_action = "promote_candidate" if status == "PASS" else "review_or_archive"
    return sanitize_json(
        {
            "status": status,
            "reason": reason,
            "next_action": next_action,
            "checks": checks,
        }
    )
