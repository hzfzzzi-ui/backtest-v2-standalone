from __future__ import annotations

from copy import deepcopy
import csv
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
from backend.research import study_gates
from backend.research.mainline_factor_surface_common import outputs_root
from backend.research.study_definition import StudyDefinition


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


def _run_sort_key(study: StudyDefinition, row: dict[str, Any]) -> tuple[int, int, str, str]:
    window_order = {window.key: idx for idx, window in enumerate(study.windows)}
    variant_order = {variant.name: idx for idx, variant in enumerate(study.variants)}
    window = str(row.get("window_key") or "")
    variant = str(row.get("variant_name") or "")
    return (
        window_order.get(window, 10_000),
        variant_order.get(variant, 10_000),
        window,
        variant,
    )


def _load_existing_runs(study: StudyDefinition) -> list[dict[str, Any]]:
    root = _study_root(study)
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in root.glob("*/*/machine/stock_rule_combo_ab_run.json"):
        try:
            payload = _read_json(path)
        except Exception:
            continue
        if str(payload.get("study_id") or "") != study.study_id:
            continue
        if not payload.get("window_key") or not payload.get("variant_name"):
            continue
        rows.append(sanitize_json(payload))
    return rows


def _merge_runs(study: StudyDefinition, existing: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for row in existing + current:
        key = (str(row.get("window_key") or ""), str(row.get("variant_name") or ""))
        if not key[0] or not key[1]:
            continue
        merged[key] = row
    return sorted(merged.values(), key=lambda row: _run_sort_key(study, row))


def _set_universe_bounds(config: dict[str, Any], *, start: str, end: str) -> None:
    universe = config.get("universe")
    if not isinstance(universe, dict):
        universe = {}
        config["universe"] = universe
    universe["start"] = start
    universe["end"] = end


def _deep_merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in dict(patch or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(dict(merged.get(key) or {}), value)
        else:
            merged[key] = deepcopy(value)
    return merged


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


def _replace_component_compile_input(
    source_contract: dict[str, Any],
    *,
    component_key: str,
    semantic_config: dict[str, Any],
    runtime_config: dict[str, Any],
    source_meta: dict[str, Any] | None = None,
) -> None:
    components = source_contract.setdefault("components", {})
    if not isinstance(components, dict):
        raise ValueError("component_source_contract.components must be an object")
    component = components.get(component_key)
    if not isinstance(component, dict):
        raise ValueError(f"component_source_contract is missing {component_key}")
    updated = deepcopy(component)
    updated["compile_input"] = {
        "semantic_config": sanitize_json(deepcopy(semantic_config)),
        "runtime_config": sanitize_json(deepcopy(runtime_config)),
    }
    if source_meta is not None:
        updated["source"] = sanitize_json(dict(source_meta))
    components[component_key] = updated


def _apply_stock_runtime_patches(runtime_config: dict[str, Any], runner_params: dict[str, Any]) -> None:
    config_patch = runner_params.get("stock_runtime_config_patch")
    if isinstance(config_patch, dict) and config_patch:
        runtime_config.update(_deep_merge_dict(runtime_config, config_patch))

    param_patch = runner_params.get("stock_runtime_param_patch")
    if not isinstance(param_patch, dict) or not param_patch:
        return
    strategy = runtime_config.get("strategy")
    if not isinstance(strategy, dict):
        strategy = {}
        runtime_config["strategy"] = strategy
    params = strategy.get("params")
    if not isinstance(params, dict):
        params = {}
    strategy["params"] = _deep_merge_dict(params, param_patch)


def build_stock_rule_combo_request_payload(study: StudyDefinition, item: dict[str, Any]) -> dict[str, Any]:
    request_payload = dict(item.get("request_payload") or {})
    runner_params = request_payload.get("runner_params") if isinstance(request_payload.get("runner_params"), dict) else {}
    template_path = _resolve_repo_path(str(runner_params.get("combo_template_path") or ""))
    stock_runtime_path = _resolve_repo_path(str(runner_params.get("stock_runtime_config_path") or ""))
    etf_runtime_path = _resolve_repo_path(str(runner_params.get("etf_runtime_config_path") or ""))
    for label, path in (
        ("combo template", template_path),
        ("stock runtime config", stock_runtime_path),
        ("ETF runtime config", etf_runtime_path),
    ):
        if not path.exists():
            raise FileNotFoundError(f"{label} not found: {path}")

    template_payload = _read_json(template_path)
    combo_config = deepcopy(
        template_payload.get("workbench_config")
        if isinstance(template_payload.get("workbench_config"), dict)
        else template_payload
    )
    source_contract = _source_contract_from_config(combo_config)

    window_key = str(item.get("window_key") or (request_payload.get("study_meta") or {}).get("window_key") or "").strip()
    window_role = str(item.get("window_role") or "").strip() or "main"
    variant_name = str(item.get("variant_name") or (request_payload.get("study_meta") or {}).get("variant_name") or "").strip()
    start = str(request_payload.get("start_date") or "").strip()
    end = str(request_payload.get("end_date") or "").strip()
    if not window_key or not variant_name or not start or not end:
        raise ValueError("combo stock-rule item is missing window, variant, start, or end")

    stock_semantic_config = _component_semantic_config(source_contract, "stock_component")
    etf_semantic_config = _component_semantic_config(source_contract, "etf_component")
    stock_runtime_config = _read_json(stock_runtime_path)
    etf_runtime_config = _read_json(etf_runtime_path)

    for cfg in (stock_semantic_config, etf_semantic_config, stock_runtime_config, etf_runtime_config):
        _set_universe_bounds(cfg, start=start, end=end)
    _apply_stock_runtime_patches(stock_runtime_config, runner_params)

    _replace_component_compile_input(
        source_contract,
        component_key="stock_component",
        semantic_config=stock_semantic_config,
        runtime_config=stock_runtime_config,
        source_meta={
            "source_kind": "combo_stock_rule_ab",
            "source_stock_component_runtime_path": str(stock_runtime_path),
            "source_stock_component_exp_id": str(runner_params.get("source_stock_component_exp_id") or "").strip()
            or None,
            "rule_variant": variant_name,
            "stock_runtime_param_patch": runner_params.get("stock_runtime_param_patch")
            if isinstance(runner_params.get("stock_runtime_param_patch"), dict)
            else {},
        },
    )
    _replace_component_compile_input(
        source_contract,
        component_key="etf_component",
        semantic_config=etf_semantic_config,
        runtime_config=etf_runtime_config,
    )

    _set_universe_bounds(combo_config, start=start, end=end)
    combo_config.setdefault("universe", {})["benchmark"] = "CN_STOCK_ETF_50_50"
    unified_runtime = combo_config.get("unified_runtime")
    if not isinstance(unified_runtime, dict):
        raise ValueError("combo template is missing unified_runtime")
    unified_runtime.pop("execution_contract", None)
    unified_runtime["component_source_contract"] = sanitize_json(deepcopy(source_contract))
    unified_runtime["stock_component_rule_ab_mode"] = "research_only_no_formal_migration"
    combo_context = unified_runtime.get("combo_context")
    if not isinstance(combo_context, dict):
        combo_context = {}
        unified_runtime["combo_context"] = combo_context
    combo_context.pop("execution_contract", None)
    combo_context["component_source_contract"] = sanitize_json(deepcopy(source_contract))
    combo_context["research_only"] = True
    combo_context["stock_rule_ab_study_id"] = study.study_id
    combo_context["stock_rule_ab_variant_name"] = variant_name
    combo_context["stock_rule_ab_window_key"] = window_key

    study_meta = dict(request_payload.get("study_meta") or {})
    study_meta.update(
        {
            "research_only": True,
            "runner_mode": "cn_stock_etf_stock_rule_combo_ab",
            "combo_template_path": str(template_path),
            "stock_runtime_config_path": str(stock_runtime_path),
            "etf_runtime_config_path": str(etf_runtime_path),
            "stock_runtime_param_patch": runner_params.get("stock_runtime_param_patch")
            if isinstance(runner_params.get("stock_runtime_param_patch"), dict)
            else {},
            "window_role": window_role,
        }
    )
    return sanitize_json(
        {
            "preset": request_payload.get("preset") or "single",
            "asset_scope": "cn_a_equity",
            "config_path": request_payload.get("config_path")
            or str(_resolve_repo_path("backend/configs/pams_cn_pg.json")),
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


def _coalesce_run_trades(perf: dict[str, Any], run_meta: dict[str, Any], runtime_result: dict[str, Any]) -> None:
    if perf.get("trades") is not None:
        return
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    for value in (runtime_result.get("trades"), counters.get("orders"), counters.get("closed_trades")):
        try:
            perf["trades"] = int(float(value))
            return
        except Exception:
            continue


def _reason_code_count(exp_id: str | None, reason_code: str) -> int:
    if not exp_id:
        return 0
    try:
        results_dir = experiment_runtime_access.resolve_results_dir(exp_id=exp_id)
    except Exception:
        return 0
    path = results_dir / "reason_codes.csv"
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if str(row.get("reason_code") or "").strip() == reason_code:
                    return int(float(row.get("count") or 0))
    except Exception:
        return 0
    return 0


def _stock_d5_reason_counts(exp_id: str | None) -> dict[str, int]:
    immediate = _reason_code_count(exp_id, "MFE_MAE_CONFIRMATION_EXIT")
    watch = _reason_code_count(exp_id, "MFE_MAE_CONFIRMATION_WATCH_EXIT")
    return {
        "MFE_MAE_CONFIRMATION_EXIT": int(immediate),
        "MFE_MAE_CONFIRMATION_WATCH_EXIT": int(watch),
        "total": int(immediate + watch),
    }


def _delta(candidate: Any, baseline: Any) -> float | None:
    try:
        return float(candidate) - float(baseline)
    except Exception:
        return None


def _same_window_comparisons(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_window: dict[str, dict[str, dict[str, Any]]] = {}
    for row in runs:
        by_window.setdefault(str(row.get("window_key") or ""), {})[str(row.get("variant_name") or "")] = row
    out: list[dict[str, Any]] = []
    for window_key, rows in sorted(by_window.items()):
        b0 = rows.get("B0_COMBO_V3_REPLAY")
        if not b0:
            continue
        b0_perf = b0.get("perf") if isinstance(b0.get("perf"), dict) else {}
        for variant_name, candidate in sorted(rows.items()):
            if variant_name == "B0_COMBO_V3_REPLAY":
                continue
            cand_perf = candidate.get("perf") if isinstance(candidate.get("perf"), dict) else {}
            out.append(
                sanitize_json(
                    {
                        "window_key": window_key,
                        "variant_name": variant_name,
                        "b0_exp_id": b0.get("exp_id"),
                        "candidate_exp_id": candidate.get("exp_id"),
                        "metrics_delta": {
                            key: _delta(cand_perf.get(key), b0_perf.get(key))
                            for key in ("total_return", "cagr", "sharpe", "max_drawdown", "calmar", "trades")
                        },
                        "b0_d5_trigger_count": b0.get("stock_d5_trigger_count"),
                        "candidate_d5_trigger_count": candidate.get("stock_d5_trigger_count"),
                        "b0_d5_reason_counts": b0.get("stock_d5_reason_counts"),
                        "candidate_d5_reason_counts": candidate.get("stock_d5_reason_counts"),
                        "stock_component_exp_ids": {
                            "b0": (b0.get("component_exp_ids") or {}).get("stock_exp_id")
                            if isinstance(b0.get("component_exp_ids"), dict)
                            else None,
                            "candidate": (candidate.get("component_exp_ids") or {}).get("stock_exp_id")
                            if isinstance(candidate.get("component_exp_ids"), dict)
                            else None,
                        },
                        "etf_component_exp_ids": {
                            "b0": (b0.get("component_exp_ids") or {}).get("etf_exp_id")
                            if isinstance(b0.get("component_exp_ids"), dict)
                            else None,
                            "candidate": (candidate.get("component_exp_ids") or {}).get("etf_exp_id")
                            if isinstance(candidate.get("component_exp_ids"), dict)
                            else None,
                        },
                    }
                )
            )
    return out


def _write_matrix_summary(study: StudyDefinition, runs: list[dict[str, Any]]) -> dict[str, str]:
    root = _study_root(study)
    machine_dir = root / "machine"
    human_dir = root / "human"
    machine_dir.mkdir(parents=True, exist_ok=True)
    human_dir.mkdir(parents=True, exist_ok=True)
    comparisons = _same_window_comparisons(runs)
    machine_path = machine_dir / "stock_rule_combo_ab_matrix.json"
    human_path = human_dir / "stock_rule_combo_ab_matrix.md"
    machine_path.write_text(
        json.dumps(
            sanitize_json({"study_id": study.study_id, "runs": runs, "same_window_comparisons": comparisons}),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    lines = [
        f"# {study.title}",
        "",
        "| window | variant | combo exp_id | stock exp id | ETF exp id | cagr | maxDD | sharpe | trades | D5 immediate | D5 watch | D5 total |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in runs:
        perf = row.get("perf") if isinstance(row.get("perf"), dict) else {}
        components = row.get("component_exp_ids") if isinstance(row.get("component_exp_ids"), dict) else {}
        d5_counts = row.get("stock_d5_reason_counts") if isinstance(row.get("stock_d5_reason_counts"), dict) else {}
        if "total" not in d5_counts and row.get("stock_d5_trigger_count") is not None:
            d5_counts = {**d5_counts, "total": row.get("stock_d5_trigger_count")}
        lines.append(
            "| {window} | {variant} | `{combo}` | `{stock}` | `{etf}` | {cagr} | {mdd} | {sharpe} | {trades} | {d5_immediate} | {d5_watch} | {d5_total} |".format(
                window=row.get("window_key") or "",
                variant=row.get("variant_name") or "",
                combo=row.get("exp_id") or "",
                stock=components.get("stock_exp_id") or "",
                etf=components.get("etf_exp_id") or "",
                cagr=perf.get("cagr"),
                mdd=perf.get("max_drawdown"),
                sharpe=perf.get("sharpe"),
                trades=perf.get("trades"),
                d5_immediate=d5_counts.get("MFE_MAE_CONFIRMATION_EXIT"),
                d5_watch=d5_counts.get("MFE_MAE_CONFIRMATION_WATCH_EXIT"),
                d5_total=d5_counts.get("total", row.get("stock_d5_trigger_count")),
            )
        )
    if comparisons:
        lines.extend(
            [
                "",
                "## Same-window deltas",
                "",
                "| window | variant | cagr delta | sharpe delta | maxDD delta | calmar delta | trades delta | D5 exits |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in comparisons:
            deltas = row.get("metrics_delta") if isinstance(row.get("metrics_delta"), dict) else {}
            lines.append(
                "| {window} | {variant} | {cagr} | {sharpe} | {mdd} | {calmar} | {trades} | {d5} |".format(
                    window=row.get("window_key") or "",
                    variant=row.get("variant_name") or "",
                    cagr=deltas.get("cagr"),
                    sharpe=deltas.get("sharpe"),
                    mdd=deltas.get("max_drawdown"),
                    calmar=deltas.get("calmar"),
                    trades=deltas.get("trades"),
                    d5=row.get("candidate_d5_trigger_count"),
                )
            )
    human_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"machine_summary": str(machine_path), "human_summary": str(human_path)}


def run_cn_stock_etf_stock_rule_combo_ab_study(
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
        variant_name = str(item.get("variant_name") or "")
        combo_payload = build_stock_rule_combo_request_payload(study, item)
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
        run_meta = _load_run_meta(exp_id, results_dir)
        config_snapshot = _load_config_snapshot(exp_id, results_dir)
        _coalesce_run_trades(perf, run_meta, runtime_result)
        verdict = study_gates.evaluate_hard_gates(
            hard_gates=study.hard_gates,
            perf=perf,
            compare=compare,
        )
        component_ids = _component_exp_ids(run_meta, config_snapshot)
        stock_d5_reason_counts = _stock_d5_reason_counts(component_ids.get("stock_exp_id"))
        stock_d5_trigger_count = int(stock_d5_reason_counts.get("total") or 0)
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
                window_key=window_key,
                variant_name=variant_name,
            )
        run_row = sanitize_json(
            {
                "study_id": study.study_id,
                "window_key": window_key,
                "window_role": str(item.get("window_role") or ""),
                "variant_name": variant_name,
                "exp_id": exp_id,
                "results_dir": str(results_dir),
                "component_exp_ids": component_ids,
                "stock_d5_trigger_count": stock_d5_trigger_count,
                "stock_d5_reason_counts": stock_d5_reason_counts,
                "perf": _key_perf(perf),
                "compare": compare,
                "verdict": verdict,
                "research_only": True,
                "baseline_outputs": {},
                "machine_outputs": output_refs.get("machine") if isinstance(output_refs.get("machine"), dict) else {},
                "human_outputs": output_refs.get("human") if isinstance(output_refs.get("human"), dict) else {},
            }
        )
        item_dir = _study_item_dir(study, window_key=window_key, variant_name=variant_name)
        machine_dir = item_dir / "machine"
        machine_dir.mkdir(parents=True, exist_ok=True)
        (machine_dir / "stock_rule_combo_ab_run.json").write_text(
            json.dumps(run_row, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        runs.append(run_row)
    all_runs = _merge_runs(study, _load_existing_runs(study), runs)
    summary_refs = _write_matrix_summary(study, all_runs)
    return sanitize_json(
        {
            "study_id": study.study_id,
            "status": "OK",
            "research_only": True,
            "runs": runs,
            "all_runs": all_runs,
            "same_window_comparisons": _same_window_comparisons(all_runs),
            "summary_outputs": summary_refs,
        }
    )
