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
from backend.research.cn_etf_phase1_zero_trade_diagnostics import (
    write_cn_etf_phase1_zero_trade_diagnostics,
)
from backend.research.a_share_moneyflow_divergence import run_a_share_moneyflow_divergence_study
from backend.research.account_state_score_study import run_account_state_score_study
from backend.research.execution_pressure_factor_study import run_execution_pressure_factor_study
from backend.research.risk_gate_factor_study import run_risk_gate_factor_study
from backend.research.exit_fragility_factor_study import run_exit_fragility_factor_study
from backend.research.final_score_composition_study import run_final_score_composition_study
from backend.research.industry_second_stage_factor_study import run_industry_second_stage_factor_study
from backend.research.moneyflow_factor_study import run_moneyflow_factor_study
from backend.research.negative_conditional_context_factor_study import run_negative_conditional_context_factor_study
from backend.research.positive_quality_factor_study import run_positive_quality_factor_study
from backend.research.snapshot_backed_study import run_snapshot_backed_research_study
from backend.research.stock_lifecycle_fragility_study import run_stock_lifecycle_fragility_study
from backend.research.stock_alpha_factor_study import run_stock_alpha_factor_study
from backend.research import study_conclusion_registry
from backend.research import study_gates
from backend.research.study_definition import StudyDefinition, StudyPatch, StudyVariant, StudyWindow


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_config_path(path_text: str) -> Path:
    raw = Path(str(path_text or "").strip())
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def _default_runtime_config_path() -> Path:
    return (_repo_root() / "backend" / "configs" / "pams_cn_pg.json").resolve()


def _looks_like_backend_runtime_config(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    return isinstance(payload.get("db"), dict) and isinstance(payload.get("schema_mapping"), dict)


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


def _ensure_patchable_mapping_payload(
    request_payload: dict[str, Any],
    *,
    payload_key: str,
    path_key: str,
) -> dict[str, Any]:
    existing = request_payload.get(payload_key)
    if isinstance(existing, dict):
        return dict(existing)
    config_path = str(request_payload.get(path_key) or "").strip()
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


def _materialize_mapping_payload(
    request_payload: dict[str, Any],
    *,
    payload_key: str,
    path_key: str,
) -> dict[str, Any]:
    explicit = request_payload.get(payload_key)
    explicit_dict = dict(explicit) if isinstance(explicit, dict) else {}
    config_path = str(request_payload.get(path_key) or "").strip()
    if not config_path:
        return explicit_dict
    resolved = _resolve_config_path(config_path)
    if not resolved.exists():
        return explicit_dict
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8-sig"))
    except Exception:
        return explicit_dict
    base_dict = dict(payload) if isinstance(payload, dict) else {}
    if explicit_dict:
        return _deep_merge_dict(base_dict, explicit_dict)
    return base_dict


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


def _deep_merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in dict(patch or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(dict(merged.get(key) or {}), value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _apply_config_patches(request_payload: dict[str, Any], patches: tuple[StudyPatch, ...]) -> None:
    if not patches:
        return
    config_json = _ensure_patchable_config_json(request_payload)
    request_payload["config_json"] = config_json
    for patch in patches:
        _set_path(config_json, patch.path, patch.value)


def _apply_window_bounds_to_mapping(mapping_payload: dict[str, Any], *, start: str, end: str) -> None:
    universe = mapping_payload.get("universe")
    if not isinstance(universe, dict):
        universe = {}
        mapping_payload["universe"] = universe
    universe["start"] = start
    universe["end"] = end


def _merge_request_overrides(request_payload: dict[str, Any], overrides: dict[str, Any]) -> None:
    for key, value in dict(overrides or {}).items():
        if isinstance(value, dict) and isinstance(request_payload.get(key), dict):
            request_payload[key] = _deep_merge_dict(
                dict(request_payload.get(key) or {}),
                value,
            )
        else:
            request_payload[key] = deepcopy(value)


def _resolve_payload_paths(request_payload: dict[str, Any]) -> None:
    for key in ("config_path", "workbench_config_path", "runtime_config_path"):
        raw = str(request_payload.get(key) or "").strip()
        if raw:
            request_payload[key] = str(_resolve_config_path(raw))


def _requires_materialized_config_json(study: StudyDefinition) -> bool:
    value = study.metadata.get("materialize_config_json")
    if value is None:
        return False
    return bool(value)


def build_request_payload(study: StudyDefinition, window: StudyWindow, variant: StudyVariant) -> dict[str, Any]:
    payload = deepcopy(study.request_template)
    payload.setdefault("preset", "single")
    payload["asset_scope"] = study.asset_scope
    _resolve_payload_paths(payload)
    _merge_request_overrides(payload, window.request_overrides)
    _merge_request_overrides(payload, variant.request_overrides)
    _resolve_payload_paths(payload)
    workbench_config = _materialize_mapping_payload(
        payload,
        payload_key="workbench_config",
        path_key="workbench_config_path",
    )
    if workbench_config:
        payload["workbench_config"] = workbench_config
    runtime_config_json = _materialize_mapping_payload(
        payload,
        payload_key="runtime_config_json",
        path_key="runtime_config_path",
    )
    if runtime_config_json:
        payload["runtime_config_json"] = runtime_config_json
    if _requires_materialized_config_json(study):
        payload["config_json"] = _ensure_patchable_config_json(payload)
    payload["start_date"] = window.start
    payload["end_date"] = window.end
    _apply_config_patches(payload, variant.config_patches)
    config_json = payload.get("config_json")
    if isinstance(config_json, dict):
        _apply_window_bounds_to_mapping(config_json, start=window.start, end=window.end)
        if not _looks_like_backend_runtime_config(config_json):
            payload["config_path"] = str(_default_runtime_config_path())
    workbench_config = payload.get("workbench_config")
    if isinstance(workbench_config, dict) and _looks_like_backend_runtime_config(workbench_config):
        _apply_window_bounds_to_mapping(workbench_config, start=window.start, end=window.end)
    runtime_config_json = payload.get("runtime_config_json")
    if isinstance(runtime_config_json, dict) and _looks_like_backend_runtime_config(runtime_config_json):
        _apply_window_bounds_to_mapping(runtime_config_json, start=window.start, end=window.end)
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


def _append_study_conclusions(study: StudyDefinition, result: dict[str, Any]) -> dict[str, Any]:
    runs = result.get("runs")
    if not isinstance(runs, list):
        return sanitize_json(result)
    updated_runs: list[dict[str, Any]] = []
    for row in runs:
        run_row = dict(row or {})
        exp_id = str(run_row.get("exp_id") or "").strip()
        compare: dict[str, Any] | None = None
        if exp_id:
            compare = experiment_compare_service.compare_experiment_to_baseline(
                exp_id=exp_id,
                baseline_id=study.baseline_id,
            )
        conclusion_outputs = study_conclusion_registry.append_study_conclusion(
            study_id=study.study_id,
            compared_baseline_id=study.baseline_id,
            verdict=run_row.get("verdict") if isinstance(run_row.get("verdict"), dict) else {},
            exp_id=exp_id or None,
            window_key=str(run_row.get("window_key") or "").strip(),
            variant_name=str(run_row.get("variant_name") or "").strip(),
            compare=compare,
            results_dir=run_row.get("results_dir"),
        )
        run_row["conclusion_outputs"] = conclusion_outputs
        updated_runs.append(sanitize_json(run_row))
    out = dict(result)
    out["runs"] = updated_runs
    return sanitize_json(out)


def run_study(
    study: StudyDefinition,
    *,
    only_variant_names: list[str] | None = None,
    only_window_keys: list[str] | None = None,
    write_dual_output: bool = True,
    append_to_baseline: bool = False,
) -> dict[str, Any]:
    plan = build_execution_plan(
        study,
        only_variant_names=only_variant_names,
        only_window_keys=only_window_keys,
    )
    runner_mode = str(study.metadata.get("runner_mode") or "").strip().lower()
    if runner_mode == "a_share_moneyflow_divergence":
        return _append_study_conclusions(study, run_a_share_moneyflow_divergence_study(
            study=study,
            plan=plan,
            write_dual_output=write_dual_output,
            append_to_baseline=append_to_baseline,
        ))
    if runner_mode == "stock_alpha_factor_surface":
        return _append_study_conclusions(study, run_stock_alpha_factor_study(
            study=study,
            plan=plan,
            write_dual_output=write_dual_output,
            append_to_baseline=append_to_baseline,
        ))
    if runner_mode == "stock_lifecycle_fragility_surface":
        return _append_study_conclusions(study, run_stock_lifecycle_fragility_study(
            study=study,
            plan=plan,
            write_dual_output=write_dual_output,
            append_to_baseline=append_to_baseline,
        ))
    if runner_mode == "account_state_score_surface":
        return _append_study_conclusions(study, run_account_state_score_study(
            study=study,
            plan=plan,
            write_dual_output=write_dual_output,
            append_to_baseline=append_to_baseline,
        ))
    if runner_mode == "moneyflow_factor_surface":
        return _append_study_conclusions(study, run_moneyflow_factor_study(
            study=study,
            plan=plan,
            write_dual_output=write_dual_output,
            append_to_baseline=append_to_baseline,
        ))
    if runner_mode == "negative_conditional_context_factor_surface":
        return _append_study_conclusions(study, run_negative_conditional_context_factor_study(
            study=study,
            plan=plan,
            write_dual_output=write_dual_output,
            append_to_baseline=append_to_baseline,
        ))
    if runner_mode == "risk_gate_factor_surface":
        return _append_study_conclusions(study, run_risk_gate_factor_study(
            study=study,
            plan=plan,
            write_dual_output=write_dual_output,
            append_to_baseline=append_to_baseline,
        ))
    if runner_mode == "industry_second_stage_factor_surface":
        return _append_study_conclusions(study, run_industry_second_stage_factor_study(
            study=study,
            plan=plan,
            write_dual_output=write_dual_output,
            append_to_baseline=append_to_baseline,
        ))
    if runner_mode == "positive_quality_factor_surface":
        return _append_study_conclusions(study, run_positive_quality_factor_study(
            study=study,
            plan=plan,
            write_dual_output=write_dual_output,
            append_to_baseline=append_to_baseline,
        ))
    if runner_mode == "final_score_composition_surface":
        return _append_study_conclusions(study, run_final_score_composition_study(
            study=study,
            plan=plan,
            write_dual_output=write_dual_output,
            append_to_baseline=append_to_baseline,
        ))
    if runner_mode == "exit_fragility_factor_surface":
        return _append_study_conclusions(study, run_exit_fragility_factor_study(
            study=study,
            plan=plan,
            write_dual_output=write_dual_output,
            append_to_baseline=append_to_baseline,
        ))
    if runner_mode == "execution_pressure_factor_surface":
        return _append_study_conclusions(study, run_execution_pressure_factor_study(
            study=study,
            plan=plan,
            write_dual_output=write_dual_output,
            append_to_baseline=append_to_baseline,
        ))
    if runner_mode == "snapshot_backed_research_runtime":
        return _append_study_conclusions(study, run_snapshot_backed_research_study(
            study=study,
            plan=plan,
            write_dual_output=write_dual_output,
            append_to_baseline=append_to_baseline,
        ))
    diagnostic_mode = str(study.metadata.get("diagnostic_mode") or "").strip().lower()
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
        diagnostic_outputs: dict[str, Any] = {}
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
        if diagnostic_mode == "cn_etf_phase1_zero_trade_mainline":
            diagnostic_outputs = write_cn_etf_phase1_zero_trade_diagnostics(
                exp_id=exp_id,
                results_dir=results_dir,
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
                    "diagnostic_outputs": diagnostic_outputs,
                    "baseline_outputs": baseline_outputs,
                }
            )
        )
    return _append_study_conclusions(
        study,
        sanitize_json(
            {
                "study_id": study.study_id,
                "title": study.title,
                "baseline_id": study.baseline_id,
                "required_outputs": list(study.required_outputs),
                "runs": runs,
            }
        ),
    )
