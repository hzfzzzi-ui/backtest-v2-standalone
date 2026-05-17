from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from backend.api.shared.json_utils import sanitize_json
from backend.core.services import (
    experiment_compare_service,
    experiment_query_service,
    experiment_summary_service,
)
from backend.core.tools import experiment_runtime_access
from backend.research import study_gates, study_loader
from backend.research.mainline_factor_surface_common import outputs_root
from backend.research.study_definition import StudyDefinition, StudyVariant, StudyWindow


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_repo_path(path_text: str) -> Path:
    raw = Path(str(path_text or "").strip())
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"json payload must be an object: {path}")
    return payload


def _study_root(study: StudyDefinition) -> Path:
    parts = [part for part in str(study.study_id or "").replace("\\", "/").split("/") if part]
    return outputs_root().joinpath(*parts).resolve()


def _study_item_dir(study: StudyDefinition, *, window_key: str, variant_name: str) -> Path:
    return (_study_root(study) / str(window_key) / str(variant_name)).resolve()


def _set_universe_bounds(config: dict[str, Any], *, start: str, end: str) -> None:
    universe = config.get("universe")
    if not isinstance(universe, dict):
        universe = {}
        config["universe"] = universe
    universe["start"] = start
    universe["end"] = end


def _source_contract_from_config(combo_config: dict[str, Any]) -> dict[str, Any]:
    unified_runtime = combo_config.get("unified_runtime")
    if not isinstance(unified_runtime, dict):
        raise ValueError("combo template is missing unified_runtime")
    source_contract = unified_runtime.get("component_source_contract")
    if not isinstance(source_contract, dict):
        combo_context = unified_runtime.get("combo_context") if isinstance(unified_runtime.get("combo_context"), dict) else {}
        source_contract = combo_context.get("component_source_contract")
    if not isinstance(source_contract, dict):
        raise ValueError("combo template is missing component_source_contract")
    components = source_contract.get("components")
    if not isinstance(components, dict):
        raise ValueError("component_source_contract is missing components")
    return deepcopy(source_contract)


def _component_semantic_config(source_contract: dict[str, Any], component_key: str) -> dict[str, Any]:
    components = source_contract.get("components") if isinstance(source_contract.get("components"), dict) else {}
    component = components.get(component_key) if isinstance(components.get(component_key), dict) else {}
    compile_input = component.get("compile_input") if isinstance(component.get("compile_input"), dict) else {}
    semantic_config = compile_input.get("semantic_config") if isinstance(compile_input.get("semantic_config"), dict) else None
    if not isinstance(semantic_config, dict):
        raise ValueError(f"{component_key} is missing compile_input.semantic_config")
    return deepcopy(semantic_config)


def _find_variant(study: StudyDefinition, variant_name: str) -> StudyVariant:
    for variant in study.variants:
        if variant.name == variant_name:
            return variant
    raise ValueError(f"variant not found in {study.study_id}: {variant_name}")


def _build_etf_study_semantic_config(
    *,
    source: dict[str, Any],
    window_key: str,
    window_role: str,
    start: str,
    end: str,
) -> dict[str, Any]:
    source_study_id = str(source.get("study_id") or "").strip()
    source_variant_name = str(source.get("variant_name") or "").strip()
    if not source_study_id or not source_variant_name:
        raise ValueError("etf_source requires study_id and variant_name")
    etf_study = study_loader.load_study_definition(source_study_id)
    etf_variant = _find_variant(etf_study, source_variant_name)
    etf_window = StudyWindow(key=window_key, role=window_role, start=start, end=end)
    from backend.research import study_runner

    etf_payload = study_runner.build_request_payload(etf_study, etf_window, etf_variant)
    semantic_config = etf_payload.get("config_json")
    if not isinstance(semantic_config, dict):
        raise ValueError(f"ETF study payload is missing config_json: {source_study_id}/{source_variant_name}")
    return sanitize_json(dict(semantic_config))


def _build_etf_semantic_config(
    *,
    template_source_contract: dict[str, Any],
    source: dict[str, Any],
    window_key: str,
    window_role: str,
    start: str,
    end: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    mode = str(source.get("mode") or "").strip()
    pool_version = str(source.get("pool_version") or mode or "").strip()
    if mode == "current_formal_combo_template":
        semantic_config = _component_semantic_config(template_source_contract, "etf_component")
        source_meta = {
            "source_kind": "combo_template_replay",
            "baseline_id": "CN_STOCK_ETF_FORMAL_V1",
            "window_key": window_key,
            "variant_name": "CURRENT_FORMAL_COMBO_REPLAY",
            "pool_version": pool_version,
        }
    elif mode == "etf_study_variant":
        semantic_config = _build_etf_study_semantic_config(
            source=source,
            window_key=window_key,
            window_role=window_role,
            start=start,
            end=end,
        )
        source_meta = {
            "source_kind": "study_shadow",
            "study_id": str(source.get("study_id") or "").strip(),
            "window_key": window_key,
            "variant_name": str(source.get("variant_name") or "").strip(),
            "pool_version": pool_version,
        }
    else:
        raise ValueError(f"unsupported etf_source mode: {mode}")
    _set_universe_bounds(semantic_config, start=start, end=end)
    return sanitize_json(semantic_config), sanitize_json(source_meta)


def _replace_component_semantic(
    source_contract: dict[str, Any],
    *,
    component_key: str,
    semantic_config: dict[str, Any],
    source_meta: dict[str, Any] | None = None,
) -> None:
    components = source_contract.setdefault("components", {})
    if not isinstance(components, dict):
        raise ValueError("component_source_contract.components must be an object")
    component = components.get(component_key)
    if not isinstance(component, dict):
        raise ValueError(f"component_source_contract is missing {component_key}")
    updated = deepcopy(component)
    updated["compile_input"] = {"semantic_config": sanitize_json(deepcopy(semantic_config))}
    if source_meta is not None:
        updated["source"] = sanitize_json(dict(source_meta))
    components[component_key] = updated


def build_combo_shadow_request_payload(study: StudyDefinition, item: dict[str, Any]) -> dict[str, Any]:
    request_payload = dict(item.get("request_payload") or {})
    runner_params = request_payload.get("runner_params") if isinstance(request_payload.get("runner_params"), dict) else {}
    template_path = _resolve_repo_path(str(runner_params.get("combo_template_path") or ""))
    if not template_path.exists():
        raise FileNotFoundError(f"combo template not found: {template_path}")
    template_payload = _read_json(template_path)
    combo_config = deepcopy(template_payload.get("workbench_config") if isinstance(template_payload.get("workbench_config"), dict) else template_payload)
    template_source_contract = _source_contract_from_config(combo_config)
    source_contract = deepcopy(template_source_contract)

    window_key = str(item.get("window_key") or (request_payload.get("study_meta") or {}).get("window_key") or "").strip()
    window_role = str(item.get("window_role") or "").strip() or "main"
    variant_name = str(item.get("variant_name") or (request_payload.get("study_meta") or {}).get("variant_name") or "").strip()
    start = str(request_payload.get("start_date") or "").strip()
    end = str(request_payload.get("end_date") or "").strip()
    if not window_key or not variant_name or not start or not end:
        raise ValueError("combo shadow item is missing window, variant, start, or end")

    stock_semantic_config = _component_semantic_config(source_contract, "stock_component")
    _set_universe_bounds(stock_semantic_config, start=start, end=end)
    _replace_component_semantic(
        source_contract,
        component_key="stock_component",
        semantic_config=stock_semantic_config,
    )

    etf_source = runner_params.get("etf_source") if isinstance(runner_params.get("etf_source"), dict) else {}
    etf_semantic_config, etf_source_meta = _build_etf_semantic_config(
        template_source_contract=template_source_contract,
        source=etf_source,
        window_key=window_key,
        window_role=window_role,
        start=start,
        end=end,
    )
    _replace_component_semantic(
        source_contract,
        component_key="etf_component",
        semantic_config=etf_semantic_config,
        source_meta=etf_source_meta,
    )

    _set_universe_bounds(combo_config, start=start, end=end)
    combo_config.setdefault("universe", {})["benchmark"] = "CN_STOCK_ETF_50_50"
    unified_runtime = combo_config.get("unified_runtime")
    if not isinstance(unified_runtime, dict):
        raise ValueError("combo template is missing unified_runtime")
    unified_runtime.pop("execution_contract", None)
    unified_runtime["component_source_contract"] = sanitize_json(deepcopy(source_contract))
    unified_runtime["etf_component_promotion_mode"] = "research_only_no_formal_migration"
    combo_context = unified_runtime.get("combo_context")
    if not isinstance(combo_context, dict):
        combo_context = {}
        unified_runtime["combo_context"] = combo_context
    combo_context.pop("execution_contract", None)
    combo_context["component_source_contract"] = sanitize_json(deepcopy(source_contract))
    combo_context["research_only"] = True
    combo_context["shadow_study_id"] = study.study_id
    combo_context["shadow_variant_name"] = variant_name
    combo_context["shadow_window_key"] = window_key

    study_meta = dict(request_payload.get("study_meta") or {})
    study_meta.update(
        {
            "research_only": True,
            "runner_mode": "cn_stock_etf_expanded_pool_shadow",
            "combo_template_path": str(template_path),
            "etf_source": etf_source_meta,
        }
    )
    return sanitize_json(
        {
            "preset": request_payload.get("preset") or "single",
            "asset_scope": "cn_a_equity",
            "config_path": request_payload.get("config_path") or str(_resolve_repo_path("backend/configs/pams_cn_pg.json")),
            "config_json": combo_config,
            "fast_mode": bool(request_payload.get("fast_mode")) if request_payload.get("fast_mode") is not None else True,
            "start_date": start,
            "end_date": end,
            "study_meta": study_meta,
        }
    )


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


def _component_result_refs(run_meta: dict[str, Any], config_snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    dependencies = run_meta.get("dependencies") if isinstance(run_meta.get("dependencies"), dict) else {}
    component_runs = dependencies.get("component_runs") if isinstance(dependencies.get("component_runs"), dict) else {}
    sleeves = run_meta.get("sleeves") if isinstance(run_meta.get("sleeves"), dict) else {}
    component_experiments = (
        config_snapshot.get("component_experiments")
        if isinstance(config_snapshot.get("component_experiments"), dict)
        else {}
    )
    def _first_ref(key: str) -> dict[str, Any]:
        for source in (component_runs, sleeves, component_experiments):
            value = source.get(key) if isinstance(source.get(key), dict) else None
            if isinstance(value, dict) and (value.get("exp_id") or value.get("results_dir")):
                return sanitize_json(dict(value))
        return {}

    return {
        "stock_alpha_core": _first_ref("stock_alpha_core"),
        "etf_beta": _first_ref("etf_beta"),
    }


def _component_exp_ids(run_meta: dict[str, Any], config_snapshot: dict[str, Any]) -> dict[str, str | None]:
    refs = _component_result_refs(run_meta, config_snapshot)
    stock_exp_id = refs["stock_alpha_core"].get("exp_id")
    etf_exp_id = refs["etf_beta"].get("exp_id")
    return {
        "stock_exp_id": str(stock_exp_id or "").strip() or None,
        "etf_exp_id": str(etf_exp_id or "").strip() or None,
    }


def _key_perf(perf: dict[str, Any]) -> dict[str, Any]:
    return {
        key: perf.get(key)
        for key in (
            "total_return",
            "cagr",
            "max_drawdown",
            "sharpe",
            "calmar",
            "trades",
            "turnover",
            "effective_execution_start_date",
        )
        if key in perf
    }


def _write_matrix_summary(study: StudyDefinition, runs: list[dict[str, Any]]) -> dict[str, str]:
    root = _study_root(study)
    machine_dir = root / "machine"
    human_dir = root / "human"
    machine_dir.mkdir(parents=True, exist_ok=True)
    human_dir.mkdir(parents=True, exist_ok=True)
    machine_path = machine_dir / "combo_shadow_matrix.json"
    human_path = human_dir / "combo_shadow_matrix.md"
    machine_path.write_text(json.dumps(sanitize_json({"study_id": study.study_id, "runs": runs}), ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# {study.title}",
        "",
        "| window | variant | combo exp_id | stock exp_id | ETF exp_id | cagr | maxDD | sharpe |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in runs:
        perf = row.get("perf") if isinstance(row.get("perf"), dict) else {}
        components = row.get("component_exp_ids") if isinstance(row.get("component_exp_ids"), dict) else {}
        lines.append(
            "| {window} | {variant} | `{combo}` | `{stock}` | `{etf}` | {cagr} | {mdd} | {sharpe} |".format(
                window=row.get("window_key") or "",
                variant=row.get("variant_name") or "",
                combo=row.get("exp_id") or "",
                stock=components.get("stock_exp_id") or "",
                etf=components.get("etf_exp_id") or "",
                cagr=perf.get("cagr"),
                mdd=perf.get("max_drawdown"),
                sharpe=perf.get("sharpe"),
            )
        )
    human_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"machine_summary": str(machine_path), "human_summary": str(human_path)}


def run_cn_stock_etf_expanded_pool_shadow_study(
    *,
    study: StudyDefinition,
    plan: list[dict[str, Any]],
    write_dual_output: bool = True,
    append_to_baseline: bool = False,
) -> dict[str, Any]:
    del append_to_baseline
    runs: list[dict[str, Any]] = []
    for item in plan:
        window_key = str(item.get("window_key") or "")
        combo_payload = build_combo_shadow_request_payload(study, item)
        runtime_result = experiment_runtime_access.run_experiment_sync(combo_payload)
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
        component_ids = _component_exp_ids(run_meta, config_snapshot)
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
        run_row = sanitize_json(
            {
                "study_id": study.study_id,
                "window_key": window_key,
                "window_role": str(item.get("window_role") or ""),
                "variant_name": str(item.get("variant_name") or ""),
                "exp_id": exp_id,
                "results_dir": str(results_dir),
                "component_exp_ids": component_ids,
                "etf_source": ((combo_payload.get("study_meta") or {}).get("etf_source") or {}),
                "perf": _key_perf(perf),
                "compare": compare,
                "verdict": verdict,
                "research_only": True,
                "baseline_outputs": {},
                "machine_outputs": output_refs.get("machine") if isinstance(output_refs.get("machine"), dict) else {},
                "human_outputs": output_refs.get("human") if isinstance(output_refs.get("human"), dict) else {},
            }
        )
        item_dir = _study_item_dir(
            study,
            window_key=str(item.get("window_key") or ""),
            variant_name=str(item.get("variant_name") or ""),
        )
        machine_dir = item_dir / "machine"
        machine_dir.mkdir(parents=True, exist_ok=True)
        (machine_dir / "combo_shadow_run.json").write_text(
            json.dumps(run_row, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        runs.append(run_row)
    summary_refs = _write_matrix_summary(study, runs)
    return sanitize_json(
        {
            "study_id": study.study_id,
            "status": "OK",
            "research_only": True,
            "runs": runs,
            "summary_outputs": summary_refs,
        }
    )
