from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.core.tools.baseline_access import (
    baseline_dir,
    baseline_index_path,
    sanitize_json,
    write_baseline_record,
)
from backend.core.tools.experiment_runtime_access import run_experiment_sync

ROOT = Path(__file__).resolve().parents[3]
BASELINE_ROOT = ROOT / "outputs" / "baselines"
EXPERIMENT_ROOT = ROOT / "outputs" / "experiments"
OPS_ROOT = ROOT / "outputs" / "ops"

SOURCE_BASELINE_ID = "baseline_V10_1"
TARGET_BASELINE_ID = "baseline_V10_2"
TARGET_BASELINE_NAME = "baseline_V10.2"
TARGET_START = "2012-01-04"
TARGET_END = "2016-12-30"
TARGET_DATA_ROLE = "v2_canonical"
TARGET_MEMBERSHIP_MODE = "PIT_DYNAMIC"
ASSET_SCOPE = "cn_a_equity"
SUMMARY_PATH = OPS_ROOT / "baseline_v10_2_registration_2012_2016_v2_strict_pit.json"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - fatal path
        raise RuntimeError(f"failed to read json: {path} ({exc})") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"json root is not object: {path}")
    return payload


def _source_config_path() -> Path:
    return BASELINE_ROOT / SOURCE_BASELINE_ID / "config.json"


def _target_config(source_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(source_cfg)
    universe = dict(cfg.get("universe") or {})
    universe["start"] = TARGET_START
    universe["end"] = TARGET_END
    universe["membership_mode"] = TARGET_MEMBERSHIP_MODE
    cfg["universe"] = universe
    data_source = dict(cfg.get("data_source") or {})
    data_source["data_role"] = TARGET_DATA_ROLE
    cfg["data_source"] = data_source
    return sanitize_json(cfg)


def _diff_paths(before: Any, after: Any, prefix: str = "") -> dict[str, dict[str, Any]]:
    if isinstance(before, dict) or isinstance(after, dict):
        before_dict = before if isinstance(before, dict) else {}
        after_dict = after if isinstance(after, dict) else {}
        changed: dict[str, dict[str, Any]] = {}
        for key in sorted(set(before_dict.keys()) | set(after_dict.keys())):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            changed.update(_diff_paths(before_dict.get(key), after_dict.get(key), child_prefix))
        return changed
    if before != after:
        return {prefix: {"from": sanitize_json(before), "to": sanitize_json(after)}}
    return {}


def _assert_minimal_diff(diff_paths: dict[str, dict[str, Any]]) -> None:
    allowed = {
        "universe.start",
        "universe.end",
        "data_source.data_role",
    }
    unexpected = sorted(path for path in diff_paths.keys() if path not in allowed)
    if unexpected:
        raise RuntimeError(f"unexpected config drift: {unexpected}")


def _run_experiment(cfg: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "preset": "single",
        "asset_scope": ASSET_SCOPE,
        "workbench_config": cfg,
    }
    result = run_experiment_sync(payload)
    if not isinstance(result, dict):
        raise RuntimeError("runtime service returned non-dict result")
    exp_id = str(result.get("exp_id") or "").strip()
    status = str(result.get("status") or "").strip()
    if not exp_id:
        raise RuntimeError(f"missing exp_id in runtime result: status={status or 'unknown'}")
    if status.upper() != "OK":
        raise RuntimeError(f"experiment failed: status={status}")
    return result


def _experiment_dir(exp_id: str) -> Path:
    exp_dir = (EXPERIMENT_ROOT / exp_id).resolve()
    if not exp_dir.exists():
        raise RuntimeError(f"experiment directory missing: {exp_dir}")
    return exp_dir


def _register_baseline(cfg: dict[str, Any], exp_id: str) -> dict[str, Any]:
    payload = {
        "baseline_id": TARGET_BASELINE_ID,
        "name": TARGET_BASELINE_NAME,
        "display_name": TARGET_BASELINE_NAME,
        "owner": "manual",
        "locked": False,
        "linked_exp_id": exp_id,
        "config_json": cfg,
    }
    return write_baseline_record(payload)


def _write_summary(summary: dict[str, Any]) -> None:
    OPS_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    source_cfg = _load_json(_source_config_path())
    target_cfg = _target_config(source_cfg)
    diff_paths = _diff_paths(source_cfg, target_cfg)
    _assert_minimal_diff(diff_paths)

    runtime_result = _run_experiment(target_cfg)
    exp_id = str(runtime_result.get("exp_id") or "").strip()
    exp_dir = _experiment_dir(exp_id)
    perf = _load_json(exp_dir / "perf.json")
    run_meta = _load_json(exp_dir / "run_meta.json")
    compiled_plan = _load_json(exp_dir / "compiled_plan.json")
    baseline_record = _register_baseline(target_cfg, exp_id)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "source_baseline_id": SOURCE_BASELINE_ID,
        "target_baseline_id": TARGET_BASELINE_ID,
        "target_display_name": TARGET_BASELINE_NAME,
        "config_diff": diff_paths,
        "runtime_request": {
            "preset": "single",
            "asset_scope": ASSET_SCOPE,
            "workbench_config_source": str(_source_config_path()),
        },
        "runtime_result": {
            "exp_id": exp_id,
            "status": runtime_result.get("status"),
            "results_dir": runtime_result.get("results_dir"),
        },
        "baseline_record": baseline_record,
        "baseline_dir": str(baseline_dir(TARGET_BASELINE_ID)),
        "baseline_index_path": str(baseline_index_path()),
        "perf": {
            "total_return": perf.get("total_return"),
            "cagr": perf.get("cagr"),
            "sharpe": perf.get("sharpe"),
            "max_drawdown": perf.get("max_drawdown"),
            "trades": perf.get("trades"),
            "effective_execution_start_date": perf.get("effective_execution_start_date"),
        },
        "run_meta_checks": {
            "window_start": ((run_meta.get("data") or {}).get("start") if isinstance(run_meta.get("data"), dict) else None),
            "window_end": ((run_meta.get("data") or {}).get("end") if isinstance(run_meta.get("data"), dict) else None),
            "data_role": (
                (((run_meta.get("report_consistency") or {}).get("data_role")) if isinstance(run_meta.get("report_consistency"), dict) else None)
                or (((run_meta.get("data") or {}).get("data_role")) if isinstance(run_meta.get("data"), dict) else None)
            ),
            "membership_mode": (
                (((run_meta.get("universe") or {}).get("membership_mode")) if isinstance(run_meta.get("universe"), dict) else None)
            ),
            "historical_membership_dynamic": (
                (((run_meta.get("universe") or {}).get("historical_membership_dynamic")) if isinstance(run_meta.get("universe"), dict) else None)
            ),
            "linked_exp_status": run_meta.get("status"),
        },
        "compiled_plan_checks": {
            "price_adj": ((compiled_plan.get("execution_overrides") or {}).get("price_adj") if isinstance(compiled_plan.get("execution_overrides"), dict) else None),
            "asset_scope": ((compiled_plan.get("execution_overrides") or {}).get("asset_scope") if isinstance(compiled_plan.get("execution_overrides"), dict) else None),
            "enable_multifactor_rank": ((compiled_plan.get("execution_overrides") or {}).get("enable_multifactor_rank") if isinstance(compiled_plan.get("execution_overrides"), dict) else None),
        },
    }
    _write_summary(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
