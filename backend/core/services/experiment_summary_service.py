from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.api.shared.json_utils import sanitize_json
from backend.research import study_reports


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(content or ""), encoding="utf-8")


def build_machine_summary_bundle(
    *,
    exp_id: str,
    hypothesis: str,
    surface: dict[str, Any],
    audit: dict[str, Any] | None = None,
    baseline_id: str | None = None,
    study_id: str | None = None,
    change_scope: dict[str, Any] | None = None,
    compare: dict[str, Any] | None = None,
    verdict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": "experiment_nac@1",
        "exp_id": exp_id,
        "baseline_id": str(baseline_id or "").strip() or None,
        "study_id": str(study_id or "").strip() or None,
        "hypothesis": str(hypothesis or "").strip(),
        "change_scope": dict(change_scope or {}),
        "summary": surface.get("summary") if isinstance(surface.get("summary"), dict) else {},
        "perf": surface.get("perf") if isinstance(surface.get("perf"), dict) else {},
        "audit": audit if isinstance(audit, dict) else (surface.get("audit") if isinstance(surface.get("audit"), dict) else {}),
        "compare": dict(compare or {}),
        "verdict": {
            "status": str(((verdict or {}).get("status") or "UNKNOWN")).strip(),
            "reason": str(((verdict or {}).get("reason") or "")).strip(),
            "next_action": str(((verdict or {}).get("next_action") or "")).strip(),
        },
    }
    return sanitize_json(payload)


def build_human_summary_bundle(
    *,
    exp_id: str,
    title: str,
    verdict: str,
    reason: str,
    perf: dict[str, Any] | None = None,
) -> dict[str, Any]:
    perf_payload = perf if isinstance(perf, dict) else {}
    return sanitize_json(
        {
            "exp_id": exp_id,
            "title": str(title or exp_id),
            "verdict": str(verdict or "").strip(),
            "reason": str(reason or "").strip(),
            "perf": {
                "cagr": perf_payload.get("cagr"),
                "max_drawdown": perf_payload.get("max_drawdown"),
                "sharpe": perf_payload.get("sharpe"),
                "trades": perf_payload.get("trades"),
            },
        }
    )


def write_dual_output_bundle(
    *,
    exp_id: str,
    results_dir: str | Path,
    title: str,
    baseline_id: str,
    study_id: str,
    hypothesis: str,
    change_scope: dict[str, Any],
    surface: dict[str, Any],
    compare: dict[str, Any],
    audit: dict[str, Any],
    run_meta: dict[str, Any],
    config_snapshot: dict[str, Any],
    verdict: dict[str, Any],
    window_key: str,
    variant_name: str,
) -> dict[str, dict[str, str]]:
    root = Path(results_dir).resolve()
    machine_root = root / "machine"
    human_root = root / "human"
    perf = dict(surface.get("perf") or {})

    nac = build_machine_summary_bundle(
        exp_id=exp_id,
        baseline_id=baseline_id,
        study_id=study_id,
        hypothesis=hypothesis,
        change_scope=change_scope,
        surface=surface,
        audit=audit,
        compare=compare,
        verdict=verdict,
    )
    human_summary = build_human_summary_bundle(
        exp_id=exp_id,
        title=title,
        verdict=str(verdict.get("status") or "UNKNOWN"),
        reason=str(verdict.get("reason") or ""),
        perf=perf,
    )
    machine_manifest = {
        "schema_version": "experiment_machine_bundle@1",
        "exp_id": exp_id,
        "baseline_id": baseline_id,
        "study_id": study_id,
        "files": {
            "nac": "nac.json",
            "perf": "perf.json",
            "audit": "audit.json",
            "compare": "compare.json",
            "surface": "surface.json",
            "config_snapshot": "config_snapshot.json",
            "run_meta": "run_meta.json",
        },
        "verdict": dict(verdict or {}),
    }
    _write_json(machine_root / "manifest.json", machine_manifest)
    _write_json(machine_root / "nac.json", nac)
    _write_json(machine_root / "perf.json", perf)
    _write_json(machine_root / "audit.json", dict(audit or {}))
    _write_json(machine_root / "compare.json", dict(compare or {}))
    _write_json(machine_root / "surface.json", dict(surface or {}))
    _write_json(machine_root / "config_snapshot.json", dict(config_snapshot or {}))
    _write_json(machine_root / "run_meta.json", dict(run_meta or {}))

    conclusion = study_reports.render_conclusion_markdown(
        title=title,
        hypothesis=hypothesis,
        verdict=verdict,
        perf=perf,
        compare=compare,
        window_key=window_key,
        variant_name=variant_name,
    )
    summary_text = study_reports.render_summary_text(
        title=title,
        verdict=verdict,
        perf=perf,
        window_key=window_key,
        variant_name=variant_name,
    )
    _write_text(human_root / "conclusion.md", conclusion)
    _write_text(human_root / "summary.txt", summary_text + "\n")

    machine_refs = {
        path.stem: str(path.relative_to(root)).replace("\\", "/")
        for path in sorted(machine_root.glob("*"))
        if path.is_file()
    }
    human_refs = {
        path.stem: str(path.relative_to(root)).replace("\\", "/")
        for path in sorted(human_root.glob("*"))
        if path.is_file()
    }
    return {"machine": machine_refs, "human": human_refs}
