from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.research.study_definition import StudyDefinition


_CSV_REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "stock_alpha_factor_snapshot_csv": (
        "date",
        "symbol",
        "factor_id",
        "raw_value",
        "normalized_value",
        "rank_value",
        "availability_flag",
        "asof_timestamp",
    ),
    "stock_alpha_factor_score_snapshot_csv": (
        "date",
        "symbol",
        "score_id",
        "score_value",
        "availability_flag",
        "asof_timestamp",
    ),
    "account_state_score_snapshot_csv": (
        "date",
        "score_id",
        "scope",
        "raw_value",
        "normalized_value",
        "availability_flag",
        "asof_timestamp",
        "source_trace",
        "derived_state",
    ),
    "account_state_combo_score_snapshot_csv": (
        "date",
        "score_id",
        "scope",
        "raw_value",
        "normalized_value",
        "availability_flag",
        "asof_timestamp",
        "source_trace",
        "derived_state",
    ),
}

_SURFACE_REQUIRED_INPUTS: dict[str, tuple[str, ...]] = {
    "stock_alpha": (
        "stock_alpha_factor_catalog_json",
        "stock_alpha_factor_snapshot_csv",
        "stock_alpha_factor_score_snapshot_csv",
    ),
    "account_state": (
        "account_state_score_catalog_json",
        "account_state_score_snapshot_csv",
        "account_state_combo_score_snapshot_csv",
    ),
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _outputs_root() -> Path:
    return (_repo_root() / "outputs" / "studies").resolve()


def _study_run_dir(study: StudyDefinition, *, window_key: str, variant_name: str) -> Path:
    parts = [part for part in str(study.study_id or "").replace("\\", "/").split("/") if part]
    return (_outputs_root().joinpath(*parts, window_key, variant_name)).resolve()


def _resolve_path(path_text: str) -> Path:
    raw = Path(str(path_text or "").strip())
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def _parse_surface_kind(study: StudyDefinition, payload: dict[str, Any]) -> str:
    run_params = payload.get("run_params")
    run_params = run_params if isinstance(run_params, dict) else {}
    surface_kind = str(run_params.get("snapshot_surface_kind") or study.metadata.get("snapshot_surface_kind") or "").strip().lower()
    if not surface_kind:
        raise ValueError("snapshot-backed study requires snapshot_surface_kind")
    if surface_kind not in _SURFACE_REQUIRED_INPUTS:
        raise ValueError(f"unsupported snapshot_surface_kind: {surface_kind}")
    return surface_kind


def _parse_snapshot_inputs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    run_params = payload.get("run_params")
    run_params = run_params if isinstance(run_params, dict) else {}
    items = list(run_params.get("snapshot_inputs") or [])
    if not items:
        raise ValueError("snapshot-backed study requires run_params.snapshot_inputs")
    parsed: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("snapshot input entries must be objects")
        name = str(item.get("name") or "").strip()
        type_name = str(item.get("type") or "").strip().lower()
        path_text = str(item.get("path") or "").strip()
        if not name or not type_name or not path_text:
            raise ValueError("snapshot input must include name, type and path")
        parsed.append(
            {
                "name": name,
                "type": type_name,
                "path": path_text,
                "window_key": str(item.get("window_key") or ""),
                "variant_name": str(item.get("variant_name") or ""),
                "config_hash": str(item.get("config_hash") or ""),
                "source_trace": item.get("source_trace"),
            }
        )
    return parsed


def _load_snapshot_object(entry: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    path = _resolve_path(str(entry["path"]))
    if not path.exists():
        raise FileNotFoundError(f"snapshot input not found: {path}")
    type_name = str(entry["type"])
    if type_name.endswith("_json"):
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return (
            sanitize_json(
                {
                    **entry,
                    "resolved_path": str(path),
                    "row_count": None,
                    "date_range": None,
                }
            ),
            payload,
        )
    if type_name.endswith("_csv"):
        frame = pd.read_csv(path)
        required = _CSV_REQUIRED_COLUMNS.get(type_name)
        if required is None:
            raise ValueError(f"unsupported snapshot csv type: {type_name}")
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise ValueError(f"snapshot columns missing for {type_name}: {', '.join(missing)}")
        if "date" in frame.columns and not frame.empty:
            date_range = {
                "start": str(frame["date"].min()),
                "end": str(frame["date"].max()),
            }
        else:
            date_range = None
        return (
            sanitize_json(
                {
                    **entry,
                    "resolved_path": str(path),
                    "row_count": int(len(frame)),
                    "date_range": date_range,
                }
            ),
            frame,
        )
    raise ValueError(f"unsupported snapshot input type: {type_name}")


def _validate_surface_inputs(surface_kind: str, entries: list[dict[str, Any]]) -> None:
    present = {str(entry["type"]) for entry in entries}
    required = set(_SURFACE_REQUIRED_INPUTS[surface_kind])
    missing = sorted(required.difference(present))
    if missing:
        raise ValueError(f"snapshot inputs missing for surface {surface_kind}: {', '.join(missing)}")


def _build_stock_alpha_analysis(objects: dict[str, Any]) -> dict[str, Any]:
    catalog = list(objects["stock_alpha_factor_catalog_json"] or [])
    factor_snapshot = objects["stock_alpha_factor_snapshot_csv"].copy()
    factor_score = objects["stock_alpha_factor_score_snapshot_csv"].copy()
    return sanitize_json(
        {
            "surface_kind": "stock_alpha",
            "catalog_factor_count": len(catalog),
            "factor_ids": sorted({str(item.get("factor_id") or "") for item in catalog}),
            "factor_snapshot": {
                "row_count": int(len(factor_snapshot)),
                "symbol_count": int(factor_snapshot["symbol"].nunique()),
                "date_count": int(factor_snapshot["date"].nunique()),
                "availability_ratio": float(factor_snapshot["availability_flag"].mean()) if len(factor_snapshot) else 0.0,
            },
            "factor_score_snapshot": {
                "row_count": int(len(factor_score)),
                "symbol_count": int(factor_score["symbol"].nunique()),
                "date_count": int(factor_score["date"].nunique()),
                "availability_ratio": float(factor_score["availability_flag"].mean()) if len(factor_score) else 0.0,
            },
        }
    )


def _build_account_state_analysis(objects: dict[str, Any]) -> dict[str, Any]:
    catalog = list(objects["account_state_score_catalog_json"] or [])
    score_snapshot = objects["account_state_score_snapshot_csv"].copy()
    combo_snapshot = objects["account_state_combo_score_snapshot_csv"].copy()
    state_distribution = (
        combo_snapshot.loc[combo_snapshot["derived_state"].notna(), "derived_state"].value_counts(normalize=True).sort_index().to_dict()
        if len(combo_snapshot)
        else {}
    )
    return sanitize_json(
        {
            "surface_kind": "account_state",
            "catalog_score_count": len(catalog),
            "score_ids": sorted({str(item.get("score_id") or "") for item in catalog}),
            "score_snapshot": {
                "row_count": int(len(score_snapshot)),
                "score_count": int(score_snapshot["score_id"].nunique()),
                "date_count": int(score_snapshot["date"].nunique()),
                "availability_ratio": float(score_snapshot["availability_flag"].mean()) if len(score_snapshot) else 0.0,
            },
            "score_combo_snapshot": {
                "row_count": int(len(combo_snapshot)),
                "date_count": int(combo_snapshot["date"].nunique()),
                "availability_ratio": float(combo_snapshot["availability_flag"].mean()) if len(combo_snapshot) else 0.0,
            },
            "derived_state_distribution": state_distribution,
        }
    )


def _write_human_summary(path: Path, *, analysis: dict[str, Any], lineage: list[dict[str, Any]]) -> None:
    lines = [
        "# Snapshot Backed Research Runtime 摘要",
        "",
        f"- surface_kind: `{analysis.get('surface_kind')}`",
        f"- snapshot_inputs: `{len(lineage)}`",
        "",
        "## Snapshot Lineage",
        "",
    ]
    for item in lineage:
        lines.extend(
            [
                f"### `{item.get('name')}`",
                f"- type: `{item.get('type')}`",
                f"- path: `{item.get('resolved_path')}`",
                f"- window_key: `{item.get('window_key')}`",
                f"- variant_name: `{item.get('variant_name')}`",
                f"- config_hash: `{item.get('config_hash')}`",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_snapshot_backed_research_study(
    *,
    study: StudyDefinition,
    plan: list[dict[str, Any]],
    write_dual_output: bool = True,
    append_to_baseline: bool = True,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for item in list(plan or []):
        payload = dict(item.get("request_payload") or {})
        surface_kind = _parse_surface_kind(study, payload)
        parsed_inputs = _parse_snapshot_inputs(payload)

        lineage: list[dict[str, Any]] = []
        objects: dict[str, Any] = {}
        for entry in parsed_inputs:
            metadata, obj = _load_snapshot_object(entry)
            lineage.append(metadata)
            objects[str(entry["type"])] = obj
        _validate_surface_inputs(surface_kind, lineage)

        if surface_kind == "stock_alpha":
            analysis = _build_stock_alpha_analysis(objects)
        elif surface_kind == "account_state":
            analysis = _build_account_state_analysis(objects)
        else:
            raise ValueError(f"unsupported snapshot surface kind: {surface_kind}")

        run_dir = _study_run_dir(
            study,
            window_key=str(item.get("window_key") or ""),
            variant_name=str(item.get("variant_name") or ""),
        )
        machine_dir = (run_dir / "machine").resolve()
        human_dir = (run_dir / "human").resolve()
        machine_dir.mkdir(parents=True, exist_ok=True)
        human_dir.mkdir(parents=True, exist_ok=True)

        lineage_json = machine_dir / "snapshot_lineage.json"
        analysis_json = machine_dir / "analysis.json"
        summary_md = human_dir / "summary.md"

        lineage_json.write_text(json.dumps(sanitize_json(lineage), ensure_ascii=False, indent=2), encoding="utf-8")
        analysis_json.write_text(
            json.dumps(
                sanitize_json(
                    {
                        "study_id": study.study_id,
                        "title": study.title,
                        "baseline_id": study.baseline_id,
                        "analysis": analysis,
                        "snapshot_lineage": lineage,
                    }
                ),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        _write_human_summary(summary_md, analysis=analysis, lineage=lineage)

        runs.append(
            sanitize_json(
                {
                    "window_key": item.get("window_key"),
                    "variant_name": item.get("variant_name"),
                    "exp_id": "",
                    "results_dir": str(run_dir),
                    "verdict": {"status": "RESEARCH_ONLY"},
                    "machine_outputs": {
                        "snapshot_lineage": str(lineage_json),
                        "analysis": str(analysis_json),
                    },
                    "human_outputs": {"summary": str(summary_md)},
                    "diagnostic_outputs": {
                        "surface_kind": surface_kind,
                        "snapshot_count": len(lineage),
                    },
                    "baseline_outputs": {} if append_to_baseline else {},
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
