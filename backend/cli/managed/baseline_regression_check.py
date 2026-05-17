"""Foundation baseline regression gate for backend refactor work.

This script compares a candidate experiment against the locked baseline
contract defined in ``backend/scripts/ops/v2_backend_refactor_baseline_contract.json``.
It can also rerun the baseline request through the current code and write a
``baseline_compare.json`` report into the candidate experiment directory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import os
import subprocess
from pathlib import Path
from typing import Any

from backend.core.tools import experiment_runtime_access


DEFAULT_CONTRACT_PATH = Path("backend/scripts/ops/v2_backend_refactor_baseline_contract.json")
DEFAULT_RUNTIME_CONTAINER = "backtest-v2-standalone"
APPROVED_ASSET_BOUNDARY_KEYS = {
    "asset_scope",
    "asset_context",
    "asset_profile_id",
    "market_profile_id",
    "execution_profile_id",
}
TRADE_SEMANTIC_IGNORE_FIELDS = {
    "component_exp_id",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ensure_repo_on_path() -> None:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    return _sha256_bytes(path.read_bytes())


def _json_hash(obj: Any) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(payload)


def _strip_keys_recursive(obj: Any, forbidden_keys: set[str]) -> Any:
    if isinstance(obj, dict):
        return {
            key: _strip_keys_recursive(value, forbidden_keys)
            for key, value in obj.items()
            if key not in forbidden_keys
        }
    if isinstance(obj, list):
        return [_strip_keys_recursive(item, forbidden_keys) for item in obj]
    return obj


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _exp_dir(exp_id: str) -> Path:
    return _repo_root() / "outputs" / "experiments" / exp_id


def _load_contract(contract_path: Path) -> dict[str, Any]:
    path = contract_path if contract_path.is_absolute() else (_repo_root() / contract_path).resolve()
    obj = _load_json(path)
    if not obj:
        raise FileNotFoundError(f"baseline contract not found: {path}")
    obj["_contract_path"] = str(path)
    return obj


def _running_inside_runtime_container() -> bool:
    if os.environ.get("BASELINE_REGRESSION_IN_CONTAINER") == "1":
        return True
    return Path("/.dockerenv").exists() and Path("/app").exists()


def _runtime_container_is_available(container_name: str = DEFAULT_RUNTIME_CONTAINER) -> bool:
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def _delegate_rerun_to_runtime_container(argv: list[str], container_name: str = DEFAULT_RUNTIME_CONTAINER) -> int:
    cmd = [
        "docker",
        "exec",
        "-e",
        "BASELINE_REGRESSION_IN_CONTAINER=1",
        container_name,
        "python",
        "backend/scripts/baseline_regression_check.py",
        *argv,
    ]
    print(f"Delegating rerun to Docker container: {container_name}")
    completed = subprocess.run(cmd, check=False)
    return int(completed.returncode)


def _remove_path(obj: Any, path: str) -> None:
    parts = [part for part in str(path or "").split(".") if part]
    if not parts:
        return
    current = obj
    for key in parts[:-1]:
        if not isinstance(current, dict) or key not in current:
            return
        current = current[key]
    if isinstance(current, dict):
        current.pop(parts[-1], None)


def _strip_paths(obj: Any, paths: list[str]) -> Any:
    cloned = json.loads(json.dumps(obj, ensure_ascii=False))
    for path in paths:
        _remove_path(cloned, path)
    return cloned


def _collect_diffs(expected: Any, actual: Any, surface: str = "") -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []

    def walk(lhs: Any, rhs: Any, path: str) -> None:
        if len(diffs) >= 20:
            return
        if type(lhs) is not type(rhs):
            diffs.append({"surface": path or "$", "expected": lhs, "actual": rhs})
            return
        if isinstance(lhs, dict):
            for key in sorted(set(lhs.keys()) | set(rhs.keys())):
                next_path = f"{path}.{key}" if path else str(key)
                if key not in lhs:
                    diffs.append({"surface": next_path, "expected": "<missing>", "actual": rhs.get(key)})
                    continue
                if key not in rhs:
                    diffs.append({"surface": next_path, "expected": lhs.get(key), "actual": "<missing>"})
                    continue
                walk(lhs.get(key), rhs.get(key), next_path)
            return
        if isinstance(lhs, list):
            if len(lhs) != len(rhs):
                diffs.append({"surface": path or "$", "expected": f"len={len(lhs)}", "actual": f"len={len(rhs)}"})
                return
            for idx, (l_item, r_item) in enumerate(zip(lhs, rhs)):
                walk(l_item, r_item, f"{path}[{idx}]")
            return
        if lhs != rhs:
            diffs.append({"surface": path or "$", "expected": lhs, "actual": rhs})

    walk(expected, actual, surface)
    return diffs


def _saved_config_record(config_id: str | None) -> dict[str, Any] | None:
    text = str(config_id or "").strip()
    if not text:
        return None
    return experiment_runtime_access.load_saved_config_record(text)


def _extract_runtime_draft(config: dict[str, Any]) -> dict[str, Any] | None:
    overrides = config.get("overrides") if isinstance(config.get("overrides"), dict) else {}
    if isinstance(overrides.get("original_workbench_config"), dict):
        return overrides.get("original_workbench_config")
    if isinstance(overrides.get("workbench_config"), dict):
        return overrides.get("workbench_config")
    return None


def _normalized_conflict_policy(run_meta: dict[str, Any], config: dict[str, Any]) -> Any:
    overrides = config.get("overrides") if isinstance(config.get("overrides"), dict) else {}
    report_consistency = run_meta.get("report_consistency") if isinstance(run_meta.get("report_consistency"), dict) else {}
    return (
        overrides.get("config_conflict_policy")
        or report_consistency.get("config_conflict_policy")
        or None
    )


def _summarize_run_meta_core(meta: dict[str, Any]) -> dict[str, Any]:
    counters = meta.get("counters") if isinstance(meta.get("counters"), dict) else {}
    return {
        "tier": meta.get("tier"),
        "status": meta.get("status"),
        "data": meta.get("data") if isinstance(meta.get("data"), dict) else {},
        "code": meta.get("code") if isinstance(meta.get("code"), dict) else {},
        "price_adj_mode": meta.get("price_adj_mode"),
        "adj_factor_stats": meta.get("adj_factor_stats") if isinstance(meta.get("adj_factor_stats"), dict) else {},
        "missing_fields": meta.get("missing_fields") if isinstance(meta.get("missing_fields"), list) else [],
        "counters": {
            "avg_positions": counters.get("avg_positions"),
            "max_positions": counters.get("max_positions"),
            "raw_signal": counters.get("raw_signal"),
            "blocked": counters.get("blocked"),
            "orders": counters.get("orders"),
            "skipped": counters.get("skipped"),
            "closed_trades": counters.get("closed_trades"),
            "atr_stop_exit_count": counters.get("atr_stop_exit_count"),
            "atr_trail_exit_count": counters.get("atr_trail_exit_count"),
            "time_exit_count": counters.get("time_exit_count"),
            "take_profit_exit_count": counters.get("take_profit_exit_count"),
            "fixed_stop_loss_exit_count": counters.get("fixed_stop_loss_exit_count"),
            "buy_stage_funnel": counters.get("buy_stage_funnel") if isinstance(counters.get("buy_stage_funnel"), list) else [],
        },
    }


def _summarize_run_meta_universe(meta: dict[str, Any]) -> dict[str, Any]:
    universe = meta.get("universe") if isinstance(meta.get("universe"), dict) else {}
    return {
        "universe_mode": universe.get("universe_mode"),
        "symbols_source": universe.get("symbols_source"),
        "raw_count": universe.get("raw_count"),
        "constituents_load_status": universe.get("constituents_load_status"),
        "load_table": universe.get("load_table"),
        "index_code": universe.get("index_code"),
        "as_of": universe.get("as_of"),
        "resolve_asof": universe.get("resolve_asof"),
        "dynamic_all_a_entry": universe.get("dynamic_all_a_entry"),
        "filters_config": universe.get("filters_config") if isinstance(universe.get("filters_config"), dict) else {},
        "excluded_counts": universe.get("excluded_counts") if isinstance(universe.get("excluded_counts"), dict) else {},
        "tradable_symbols": universe.get("tradable_symbols"),
        "after_filters_symbols": universe.get("after_filters_symbols"),
    }


def _summarize_manifest(manifest: dict[str, Any], ignore_paths: list[str]) -> dict[str, Any]:
    cleaned = _strip_paths(manifest, ignore_paths)
    artifacts = cleaned.get("artifacts") if isinstance(cleaned.get("artifacts"), dict) else {}
    if isinstance(artifacts, dict):
        artifacts = dict(artifacts)
        artifacts.pop("report", None)
    return {
        "status": cleaned.get("status"),
        "schema_version": cleaned.get("schema_version"),
        "asset_scope": cleaned.get("asset_scope"),
        "asset_profile_id": cleaned.get("asset_profile_id"),
        "market_profile_id": cleaned.get("market_profile_id"),
        "execution_profile_id": cleaned.get("execution_profile_id"),
        "artifacts": artifacts,
        "config_snapshots": cleaned.get("config_snapshots") if isinstance(cleaned.get("config_snapshots"), dict) else {},
        "baseline_compare_status": cleaned.get("baseline_compare_status"),
        "metrics": cleaned.get("metrics") if isinstance(cleaned.get("metrics"), dict) else {},
    }


def _summarize_perf(perf: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    return {field: perf.get(field) for field in fields}


def _summarize_nav(nav_rows: list[dict[str, Any]], nav_path: Path) -> dict[str, Any]:
    first = nav_rows[0] if nav_rows else {}
    last = nav_rows[-1] if nav_rows else {}
    return {
        "rows": len(nav_rows),
        "first_date": first.get("date"),
        "last_date": last.get("date"),
        "first_nav": _coerce_float(first.get("nav")),
        "terminal_nav": _coerce_float(last.get("nav")),
        "file_hash": _file_hash(nav_path),
    }


def _summarize_trades(trade_rows: list[dict[str, Any]], trades_path: Path) -> dict[str, Any]:
    reason_counts: dict[str, int] = {}
    semantic_rows: list[dict[str, str]] = []
    for row in trade_rows:
        code = str(row.get("reason_code") or "")
        reason_counts[code] = int(reason_counts.get(code, 0)) + 1
        semantic_rows.append(
            {
                str(key): str(value or "")
                for key, value in sorted(row.items())
                if str(key) not in TRADE_SEMANTIC_IGNORE_FIELDS
            }
        )
    return {
        "rows": len(trade_rows),
        "reason_counts": dict(sorted(reason_counts.items())),
        "semantic_hash": _json_hash(semantic_rows),
        "ignored_fields": sorted(TRADE_SEMANTIC_IGNORE_FIELDS),
    }


def _summarize_config_truth(
    config: dict[str, Any],
    run_config: dict[str, Any],
    run_meta: dict[str, Any],
    ignore_paths: list[str],
) -> dict[str, Any]:
    overrides = config.get("overrides") if isinstance(config.get("overrides"), dict) else {}
    report_consistency = run_meta.get("report_consistency") if isinstance(run_meta.get("report_consistency"), dict) else {}
    saved_record = _saved_config_record(str(overrides.get("config_id") or "").strip() or None) or {}
    draft = _extract_runtime_draft(config)
    summary = {
        "config_source": overrides.get("config_source"),
        "config_conflict_policy": _normalized_conflict_policy(run_meta, config),
        "resolved_config_mode": report_consistency.get("resolved_config_mode") or overrides.get("resolved_config_mode"),
        "resolved_config_id": report_consistency.get("resolved_config_id") or overrides.get("resolved_config_id"),
        "resolved_config_hash": report_consistency.get("resolved_config_hash") or overrides.get("resolved_config_hash"),
        "saved_config_meta": {
            "config_id": saved_record.get("config_id"),
            "config_hash": saved_record.get("config_hash"),
            "source_type": saved_record.get("source_type"),
            "owner": saved_record.get("owner"),
            "locked": saved_record.get("locked"),
            "baseline_of": saved_record.get("baseline_of"),
            "saved_at": saved_record.get("saved_at"),
        },
        "draft_hash": _json_hash(draft) if isinstance(draft, dict) else None,
        "run_config_hash": _json_hash(run_config),
        "run_config_behavior_hash": _json_hash(_strip_keys_recursive(run_config, APPROVED_ASSET_BOUNDARY_KEYS)),
    }
    return _strip_paths(summary, ignore_paths)


def _summarize_portfolio_daily(
    daily_rows: list[dict[str, Any]],
    daily_path: Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    semantic_csv = ((contract.get("protected_artifacts") or {}).get("semantic_csv") or {}).get("portfolio_daily.csv") or {}
    stable_fields = [
        str(field)
        for field in semantic_csv.get("stable_fields") or []
        if str(field).strip()
    ]
    aggregate_sum_fields = [
        str(field)
        for field in semantic_csv.get("aggregate_sum_fields") or []
        if str(field).strip()
    ]
    first = daily_rows[0] if daily_rows else {}
    last = daily_rows[-1] if daily_rows else {}
    present_fields = [field for field in stable_fields if daily_rows and field in first]
    summary: dict[str, Any] = {
        "rows": len(daily_rows),
        "first_date": first.get("date"),
        "last_date": last.get("date"),
        "first_nav": _coerce_float(first.get("nav")),
        "terminal_nav": _coerce_float(last.get("nav")),
        "stable_fields": present_fields,
    }
    for field in aggregate_sum_fields:
        if not daily_rows or field not in first:
            continue
        summary[f"{field}_sum"] = sum(_coerce_float(row.get(field)) or 0.0 for row in daily_rows)
    if present_fields:
        semantic_rows = [
            {field: str(row.get(field) or "") for field in present_fields}
            for row in daily_rows
        ]
        summary["semantic_hash"] = _json_hash(semantic_rows)
    else:
        summary["semantic_hash"] = _file_hash(daily_path)
    return summary


def _bundle_from_dir(exp_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
    config = _load_json(exp_dir / "config.json")
    run_meta = _load_json(exp_dir / "run_meta.json")
    run_config = _load_json(exp_dir / "run_config.json")
    manifest = _load_json(exp_dir / "manifest.json")
    perf = _load_json(exp_dir / "perf.json")
    nav_rows = _load_csv_rows(exp_dir / "nav.csv")
    daily_rows = _load_csv_rows(exp_dir / "portfolio_daily.csv")
    trade_rows = _load_csv_rows(exp_dir / "portfolio_trades.csv")
    candidates_rows = _load_csv_rows(exp_dir / "portfolio_candidates.csv")
    daily_path = exp_dir / "portfolio_daily.csv"
    trades_path = exp_dir / "portfolio_trades.csv"
    candidates_path = exp_dir / "portfolio_candidates.csv"
    allowed = dict(contract.get("allowed_drift_fields") or {})
    return {
        "run_meta_core": _strip_paths(_summarize_run_meta_core(run_meta), list(allowed.get("run_meta.json") or [])),
        "run_meta_universe": _summarize_run_meta_universe(run_meta),
        "config_truth": _summarize_config_truth(
            config=config,
            run_config=run_config,
            run_meta=run_meta,
            ignore_paths=list(allowed.get("config_truth") or []),
        ),
        "manifest": _summarize_manifest(manifest, list(allowed.get("manifest.json") or [])),
        "perf": _summarize_perf(
            perf,
            list((((contract.get("protected_artifacts") or {}).get("summary_json") or {}).get("perf.json") or [])),
        ),
        "nav": _summarize_nav(nav_rows, exp_dir / "nav.csv"),
        "portfolio_daily": _summarize_portfolio_daily(daily_rows, daily_path, contract),
        "portfolio_trades": _summarize_trades(trade_rows, trades_path),
        "portfolio_candidates": {
            "rows": len(candidates_rows),
            "file_hash": _file_hash(candidates_path),
        },
    }


def _artifact_result(
    *,
    artifact: str,
    category: str,
    expected: Any,
    actual: Any,
    non_blocking_categories: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    diffs = _collect_diffs(expected, actual, artifact)
    blocking = category not in non_blocking_categories
    status = "PASS" if not diffs else ("WARN" if not blocking else "FAIL")
    mismatches = [
        {
            "artifact": artifact,
            "category": category,
            "blocking": blocking,
            "surface": diff["surface"],
            "expected": diff["expected"],
            "actual": diff["actual"],
        }
        for diff in diffs
    ]
    return (
        {
            "artifact": artifact,
            "category": category,
            "status": status,
            "blocking": blocking,
            "diff_count": len(diffs),
        },
        mismatches,
    )


def compare_experiment_dirs(
    *,
    baseline_dir: Path,
    candidate_dir: Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    if not baseline_dir.exists():
        raise FileNotFoundError(f"baseline experiment not found: {baseline_dir}")
    if not candidate_dir.exists():
        raise FileNotFoundError(f"candidate experiment not found: {candidate_dir}")

    expected = _bundle_from_dir(baseline_dir, contract)
    actual = _bundle_from_dir(candidate_dir, contract)
    non_blocking_categories = set(str(x) for x in contract.get("non_blocking_categories") or [])
    artifact_results: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    universe_drift = expected["run_meta_universe"] != actual["run_meta_universe"]
    perf_category = "data_drift" if universe_drift else "code_drift"

    for artifact_name in ["portfolio_daily", "portfolio_trades", "portfolio_candidates"]:
        result, diffs = _artifact_result(
            artifact=artifact_name,
            category=perf_category,
            expected=expected[artifact_name],
            actual=actual[artifact_name],
            non_blocking_categories=non_blocking_categories,
        )
        artifact_results.append(result)
        mismatches.extend(diffs)

    for artifact_name in ["perf", "nav"]:
        result, diffs = _artifact_result(
            artifact=artifact_name,
            category=perf_category,
            expected=expected[artifact_name],
            actual=actual[artifact_name],
            non_blocking_categories=non_blocking_categories,
        )
        artifact_results.append(result)
        mismatches.extend(diffs)

    result, diffs = _artifact_result(
        artifact="run_meta_core",
        category="code_drift",
        expected=expected["run_meta_core"],
        actual=actual["run_meta_core"],
        non_blocking_categories=non_blocking_categories,
    )
    artifact_results.append(result)
    mismatches.extend(diffs)

    result, diffs = _artifact_result(
        artifact="run_meta_universe",
        category="data_drift",
        expected=expected["run_meta_universe"],
        actual=actual["run_meta_universe"],
        non_blocking_categories=non_blocking_categories,
    )
    artifact_results.append(result)
    mismatches.extend(diffs)

    result, diffs = _artifact_result(
        artifact="config_truth",
        category="config_truth_drift",
        expected=expected["config_truth"],
        actual=actual["config_truth"],
        non_blocking_categories=non_blocking_categories,
    )
    artifact_results.append(result)
    mismatches.extend(diffs)

    result, diffs = _artifact_result(
        artifact="manifest",
        category="artifact_drift",
        expected=expected["manifest"],
        actual=actual["manifest"],
        non_blocking_categories=non_blocking_categories,
    )
    artifact_results.append(result)
    mismatches.extend(diffs)

    blocking = [item for item in mismatches if bool(item.get("blocking"))]
    warnings = [item for item in mismatches if not bool(item.get("blocking"))]
    status = "FAIL" if blocking else ("WARN" if warnings else "PASS")
    return {
        "status": status,
        "contract_name": contract.get("contract_name"),
        "contract_version": contract.get("version"),
        "contract_path": contract.get("_contract_path"),
        "baseline_exp_id": baseline_dir.name,
        "candidate_exp_id": candidate_dir.name,
        "artifact_results": artifact_results,
        "mismatch_counts": {
            "blocking": len(blocking),
            "warning": len(warnings),
            "total": len(mismatches),
        },
        "allowed_drift_fields": contract.get("allowed_drift_fields") or {},
        "verification_command": contract.get("verification_command"),
        "blocking_diffs": blocking,
        "warning_diffs": warnings,
        "mismatches": mismatches,
        "summary": {
            "baseline_dir": str(baseline_dir),
            "candidate_dir": str(candidate_dir),
            "universe_drift_detected": universe_drift,
        },
    }


def compare_experiments(
    baseline_exp_id: str,
    candidate_exp_id: str,
    *,
    contract_path: Path,
) -> dict[str, Any]:
    contract = _load_contract(contract_path)
    return compare_experiment_dirs(
        baseline_dir=_exp_dir(baseline_exp_id),
        candidate_dir=_exp_dir(candidate_exp_id),
        contract=contract,
    )


def _build_baseline_request(exp_dir: Path) -> dict[str, Any]:
    config = _load_json(exp_dir / "config.json")
    overrides = config.get("overrides") if isinstance(config.get("overrides"), dict) else {}
    original_wb = overrides.get("original_workbench_config") if isinstance(overrides.get("original_workbench_config"), dict) else None
    effective_wb = overrides.get("workbench_config") if isinstance(overrides.get("workbench_config"), dict) else None
    input_config = _load_json(exp_dir / "input_config.json")
    compiled_plan = _load_json(exp_dir / "compiled_plan.json")
    compiled_runtime = (
        compiled_plan.get("runtime_config")
        if isinstance(compiled_plan.get("runtime_config"), dict)
        else None
    )
    draft = original_wb or effective_wb or {}
    draft_universe = draft.get("universe") if isinstance(draft.get("universe"), dict) else {}
    flow_script = draft.get("flow_script") if isinstance(draft.get("flow_script"), dict) else {}
    request_payload = {
        "preset": str(flow_script.get("recommended_preset") or "single"),
        "config_path": "configs/pams_cn_pg.json",
        "config_id": overrides.get("config_id"),
        "workbench_mode": overrides.get("workbench_mode") or draft.get("mode") or "experiment",
        "universe_mode": draft.get("universe_mode") or "CUSTOM",
        "industries": draft.get("industries") or [],
        "price_adj": draft_universe.get("price_adj") or overrides.get("price_adj") or "hfq",
        "start_date": draft_universe.get("start"),
        "end_date": draft_universe.get("end"),
        "benchmark": draft_universe.get("benchmark"),
        "symbols": draft_universe.get("symbols"),
        "initial_capital": overrides.get("initial_capital"),
        "fast_mode": overrides.get("fast_mode"),
    }
    requested_source = str(overrides.get("config_source") or "").strip().lower()
    if requested_source == "config_json" and isinstance(input_config, dict) and input_config:
        request_payload["config_json"] = input_config
        return request_payload
    if requested_source == "runtime_config_json" and isinstance(original_wb, dict) and original_wb:
        request_payload["runtime_config_json"] = original_wb
        return request_payload
    if requested_source == "workbench_config" and isinstance(original_wb, dict) and original_wb:
        request_payload["workbench_config"] = original_wb
        return request_payload
    if isinstance(compiled_runtime, dict) and compiled_runtime.get("db") and compiled_runtime.get("schema_mapping"):
        request_payload["runtime_config_json"] = compiled_runtime
        return request_payload
    if isinstance(effective_wb, dict) and effective_wb.get("db") and effective_wb.get("schema_mapping"):
        request_payload["runtime_config_json"] = effective_wb
        return request_payload
    if isinstance(input_config, dict) and input_config:
        request_payload["config_json"] = input_config
        return request_payload
    if isinstance(original_wb, dict) and original_wb:
        request_payload["workbench_config"] = original_wb
        return request_payload
    request_payload["workbench_config"] = draft
    return request_payload


def _ensure_rerun_saved_config(exp_dir: Path) -> Path | None:
    config = _load_json(exp_dir / "config.json")
    overrides = config.get("overrides") if isinstance(config.get("overrides"), dict) else {}
    config_id = str(overrides.get("config_id") or "").strip()
    if not config_id or _saved_config_record(config_id):
        return None

    effective_wb = overrides.get("workbench_config") if isinstance(overrides.get("workbench_config"), dict) else None
    if not isinstance(effective_wb, dict) or not effective_wb:
        return None

    resolved_meta = overrides.get("resolved_config_meta") if isinstance(overrides.get("resolved_config_meta"), dict) else {}
    _ensure_repo_on_path()
    from backend.core.tools.saved_config_access import create_saved_config_record  # type: ignore

    record = create_saved_config_record(
        effective_wb,
        config_id=config_id,
        name=str(resolved_meta.get("name") or config_id),
        display_name=str(resolved_meta.get("display_name") or resolved_meta.get("name") or config_id),
        tags=list(resolved_meta.get("tags") or []),
        source_type=str(resolved_meta.get("source_type") or "template"),
        owner=str(resolved_meta.get("owner") or "builtin"),
        locked=bool(resolved_meta.get("locked", True)),
        baseline_of=resolved_meta.get("baseline_of"),
        extra={"saved_at": str(resolved_meta.get("saved_at") or "")},
    )
    cfg_root = _repo_root() / "outputs" / "configs"
    cfg_root.mkdir(parents=True, exist_ok=True)
    path = cfg_root / f"{config_id}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def rerun_baseline(baseline_exp_id: str) -> str:
    exp_dir = _exp_dir(baseline_exp_id)
    temp_saved_config = _ensure_rerun_saved_config(exp_dir)
    try:
        request_payload = _build_baseline_request(exp_dir)
        result = experiment_runtime_access.run_experiment_sync(request_payload)
    finally:
        if temp_saved_config is not None:
            temp_saved_config.unlink(missing_ok=True)
    exp_id = str(result.get("exp_id") or "").strip()
    if not exp_id:
        raise RuntimeError("rerun did not produce exp_id")
    return exp_id


def _write_json_output(result: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_path.name != "baseline_compare.json":
        return
    manifest_path = output_path.parent / "manifest.json"
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict) or not manifest:
        return
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    artifacts["baseline_compare"] = output_path.name
    manifest["artifacts"] = artifacts
    manifest.setdefault("exp_id", str(manifest.get("experiment_id") or output_path.parent.name))
    manifest.setdefault("experiment_id", str(manifest.get("exp_id") or output_path.parent.name))
    manifest.setdefault("schema_version", "backtest_v2_experiment_manifest@2")
    config_snapshots = manifest.get("config_snapshots") if isinstance(manifest.get("config_snapshots"), dict) else {}
    for key, filename in (
        ("input_config", "input_config.json"),
        ("resolved_config", "resolved_config.json"),
        ("compiled_plan", "compiled_plan.json"),
    ):
        if key in config_snapshots:
            continue
        if (output_path.parent / filename).exists():
            config_snapshots[key] = filename
    manifest["config_snapshots"] = config_snapshots
    manifest["baseline_compare_status"] = str(result.get("status") or "UNKNOWN").strip().upper() or "UNKNOWN"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_summary(result: dict[str, Any]) -> None:
    print(f"Contract:  {result.get('contract_name')}@{result.get('contract_version')}")
    print(f"Baseline:  {result.get('baseline_exp_id')}")
    print(f"Candidate: {result.get('candidate_exp_id')}")
    print(f"Status:    {result.get('status')}")
    counts = result.get("mismatch_counts") if isinstance(result.get("mismatch_counts"), dict) else {}
    print(
        "Mismatches:"
        f" blocking={counts.get('blocking', 0)}"
        f" warning={counts.get('warning', 0)}"
        f" total={counts.get('total', 0)}"
    )
    for artifact_result in result.get("artifact_results", [])[:12]:
        print(
            f"- {artifact_result.get('artifact')}: "
            f"{artifact_result.get('status')} ({artifact_result.get('category')}, diffs={artifact_result.get('diff_count')})"
        )
    for mismatch in result.get("mismatches", [])[:16]:
        level = "FAIL" if mismatch.get("blocking") else "WARN"
        print(
            f"[{level}] {mismatch.get('artifact')}::{mismatch.get('surface')} | "
            f"expected={mismatch.get('expected')} | actual={mismatch.get('actual')}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare experiments against the backend refactor baseline contract.")
    parser.add_argument("--contract-path", default=str(DEFAULT_CONTRACT_PATH))
    parser.add_argument("--baseline-exp-id", default=None)
    parser.add_argument("--candidate-exp-id", default=None)
    parser.add_argument("--rerun", action="store_true", help="rerun the baseline request through current code before comparing")
    parser.add_argument("--output-json", default=None, help="write the comparison result to a JSON file")
    parser.add_argument("--write-to-candidate", action="store_true", help="write baseline_compare.json into the candidate experiment directory")
    args = parser.parse_args()

    if args.rerun and not _running_inside_runtime_container() and _runtime_container_is_available():
        raise SystemExit(_delegate_rerun_to_runtime_container(sys.argv[1:]))

    contract = _load_contract(Path(args.contract_path))
    baseline_exp_id = str(args.baseline_exp_id or contract.get("baseline_exp_id") or "").strip()
    if not baseline_exp_id:
        raise RuntimeError("baseline_exp_id is missing from arguments and contract")

    candidate_exp_id = str(args.candidate_exp_id or "").strip() or None
    if args.rerun:
        candidate_exp_id = rerun_baseline(baseline_exp_id)
        print(f"Rerun created candidate experiment: {candidate_exp_id}")
    if not candidate_exp_id:
        candidate_exp_id = baseline_exp_id

    result = compare_experiment_dirs(
        baseline_dir=_exp_dir(baseline_exp_id),
        candidate_dir=_exp_dir(candidate_exp_id),
        contract=contract,
    )
    _print_summary(result)

    output_json = Path(args.output_json).resolve() if args.output_json else None
    if output_json is not None:
        _write_json_output(result, output_json)

    if args.write_to_candidate:
        _write_json_output(result, _exp_dir(candidate_exp_id) / "baseline_compare.json")

    if result.get("status") == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
