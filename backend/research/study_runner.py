from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from backend.api.shared.json_utils import sanitize_json
from backend.core.services import (
    baseline_report_service,
    experiment_compare_service,
    experiment_query_service,
    experiment_summary_service,
)
from backend.core.tools import experiment_runtime_access
from backend.research import study_gates
from backend.research.study_definition import StudyDefinition, StudyPatch, StudyVariant, StudyWindow


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_config_path(path_text: str) -> Path:
    raw = Path(str(path_text or "").strip())
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def _ensure_patchable_config_json(request_payload: dict[str, Any]) -> dict[str, Any]:
    existing = request_payload.get("config_json")
    if isinstance(existing, dict):
        return dict(existing)
    config_path = str(request_payload.get("config_path") or "").strip()
    if not config_path:
        return {}
    resolved = _resolve_config_path(config_path)
    if not resolved.exists():
        return {}
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _set_path(payload: dict[str, Any], path: str, value: Any) -> None:
    tokens = [token.strip() for token in str(path or "").split(".") if token.strip()]
    if not tokens:
        raise ValueError("study patch path cannot be empty")
    cursor: Any = payload
    for token in tokens[:-1]:
        if not isinstance(cursor.get(token), dict):
            cursor[token] = {}
        cursor = cursor[token]
    cursor[tokens[-1]] = deepcopy(value)


def _apply_config_patches(request_payload: dict[str, Any], patches: tuple[StudyPatch, ...]) -> None:
    if not patches:
        return
    config_json = _ensure_patchable_config_json(request_payload)
    request_payload["config_json"] = config_json
    for patch in patches:
        _set_path(config_json, patch.path, patch.value)


def _merge_request_overrides(request_payload: dict[str, Any], overrides: dict[str, Any]) -> None:
    for key, value in dict(overrides or {}).items():
        if isinstance(value, dict) and isinstance(request_payload.get(key), dict):
            merged = dict(request_payload.get(key) or {})
            merged.update(deepcopy(value))
            request_payload[key] = merged
        else:
            request_payload[key] = deepcopy(value)


def _requires_materialized_config_json(study: StudyDefinition) -> bool:
    value = study.metadata.get("materialize_config_json")
    if value is None:
        return False
    return bool(value)


def build_request_payload(study: StudyDefinition, window: StudyWindow, variant: StudyVariant) -> dict[str, Any]:
    payload = deepcopy(study.request_template)
    payload.setdefault("preset", "single")
    payload["asset_scope"] = study.asset_scope
    _merge_request_overrides(payload, window.request_overrides)
    _merge_request_overrides(payload, variant.request_overrides)
    if _requires_materialized_config_json(study):
        payload["config_json"] = _ensure_patchable_config_json(payload)
    payload["start_date"] = window.start
    payload["end_date"] = window.end
    _apply_config_patches(payload, variant.config_patches)
    config_json = payload.get("config_json")
    if isinstance(config_json, dict):
        universe = config_json.get("universe")
        if not isinstance(universe, dict):
            universe = {}
            config_json["universe"] = universe
        universe["start"] = window.start
        universe["end"] = window.end
    payload["study_meta"] = sanitize_json(
        {
            "study_id": study.study_id,
            "title": study.title,
            "baseline_id": study.baseline_id,
            "asset_scope": study.asset_scope,
            "window_key": window.key,
            "variant_name": variant.name,
            "required_outputs": list(study.required_outputs),
        }
    )
    return sanitize_json(payload)


def build_execution_plan(
    study: StudyDefinition,
    *,
    only_variant_names: list[str] | None = None,
    only_window_keys: list[str] | None = None,
) -> list[dict[str, Any]]:
    allowed_variants = {str(item).strip() for item in list(only_variant_names or []) if str(item).strip()}
    allowed_windows = {str(item).strip() for item in list(only_window_keys or []) if str(item).strip()}
    plan: list[dict[str, Any]] = []
    for window in study.windows:
        if allowed_windows and window.key not in allowed_windows:
            continue
        for variant in study.variants:
            if allowed_variants and variant.name not in allowed_variants:
                continue
            plan.append(
                sanitize_json(
                    {
                        "study_id": study.study_id,
                        "title": study.title,
                        "baseline_id": study.baseline_id,
                        "window_key": window.key,
                        "window_role": window.role,
                        "variant_name": variant.name,
                        "request_payload": build_request_payload(study, window, variant),
                    }
                )
            )
    return plan


def _load_run_meta(exp_id: str, results_dir: str | Path | None) -> dict[str, Any]:
    return experiment_runtime_access.read_json_artifact(
        exp_id=exp_id,
        results_dir=results_dir,
        artifact_key="run_meta",
        fallback_rel_path="run_meta.json",
    )


def _load_config_snapshot(exp_id: str, results_dir: str | Path | None) -> dict[str, Any]:
    resolved = experiment_runtime_access.read_json_artifact(
        exp_id=exp_id,
        results_dir=results_dir,
        artifact_key="resolved_config",
        fallback_rel_path="resolved_config.json",
    )
    if resolved:
        return resolved
    return experiment_runtime_access.read_json_artifact(
        exp_id=exp_id,
        results_dir=results_dir,
        artifact_key="config",
        fallback_rel_path="config.json",
    )


def run_study(
    study: StudyDefinition,
    *,
    only_variant_names: list[str] | None = None,
    only_window_keys: list[str] | None = None,
    write_dual_output: bool = True,
    append_to_baseline: bool = True,
) -> dict[str, Any]:
    plan = build_execution_plan(
        study,
        only_variant_names=only_variant_names,
        only_window_keys=only_window_keys,
    )
    runs: list[dict[str, Any]] = []
    for item in plan:
        payload = dict(item.get("request_payload") or {})
        runtime_result = experiment_runtime_access.run_experiment_sync(payload)
        exp_id = str(runtime_result.get("exp_id") or runtime_result.get("experiment_id") or "").strip()
        results_dir = experiment_runtime_access.resolve_results_dir(
            exp_id=exp_id or None,
            results_dir=runtime_result.get("results_dir"),
        )
        surface = experiment_query_service.get_experiment_surface(exp_id)
        compare = experiment_compare_service.compare_experiment_to_baseline(
            exp_id=exp_id,
            baseline_id=study.baseline_id,
        )
        perf = dict(surface.get("perf") or {})
        verdict = study_gates.evaluate_hard_gates(
            hard_gates=study.hard_gates,
            perf=perf,
            compare=compare,
        )
        run_meta = _load_run_meta(exp_id, results_dir)
        config_snapshot = _load_config_snapshot(exp_id, results_dir)
        output_refs = {"machine": {}, "human": {}}
        if write_dual_output:
            output_refs = experiment_summary_service.write_dual_output_bundle(
                exp_id=exp_id,
                results_dir=results_dir,
                title=study.title,
                baseline_id=study.baseline_id,
                study_id=study.study_id,
                hypothesis=study.hypothesis,
                change_scope=study.change_scope,
                surface=surface,
                compare=compare,
                audit=dict(surface.get("audit") or {}),
                run_meta=run_meta,
                config_snapshot=config_snapshot,
                verdict=verdict,
                window_key=str(item.get("window_key") or ""),
                variant_name=str(item.get("variant_name") or ""),
            )
        baseline_outputs: dict[str, Any] = {}
        if append_to_baseline:
            baseline_outputs = baseline_report_service.append_experiment_to_baseline(
                baseline_id=study.baseline_id,
                exp_id=exp_id,
                study_id=study.study_id,
                title=study.title,
                verdict=verdict,
                perf=perf,
                compare=compare,
                human_output_refs=dict(output_refs.get("human") or {}),
                window_key=str(item.get("window_key") or ""),
                variant_name=str(item.get("variant_name") or ""),
            )
        runs.append(
            sanitize_json(
                {
                    "window_key": item.get("window_key"),
                    "variant_name": item.get("variant_name"),
                    "exp_id": exp_id,
                    "results_dir": str(results_dir),
                    "verdict": verdict,
                    "machine_outputs": dict(output_refs.get("machine") or {}),
                    "human_outputs": dict(output_refs.get("human") or {}),
                    "baseline_outputs": baseline_outputs,
                }
            )
        )
    return sanitize_json(
        {
            "study_id": study.study_id,
            "title": study.title,
            "baseline_id": study.baseline_id,
            "required_outputs": list(study.required_outputs),
            "runs": runs,
        }
    )
