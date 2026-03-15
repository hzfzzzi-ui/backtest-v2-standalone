from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.api.shared.json_utils import sanitize_json
from backend.core.tools import baseline_access


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def build_baseline_ledger_entry(
    *,
    baseline_id: str,
    exp_id: str,
    verdict: str,
    summary: dict[str, Any],
) -> dict[str, Any]:
    return sanitize_json(
        {
            "baseline_id": str(baseline_id or "").strip(),
            "exp_id": str(exp_id or "").strip(),
            "verdict": str(verdict or "").strip(),
            "summary": dict(summary or {}),
        }
    )


def build_baseline_report_append(
    *,
    baseline_id: str,
    exp_id: str,
    human_summary: dict[str, Any],
) -> dict[str, Any]:
    return sanitize_json(
        {
            "baseline_id": str(baseline_id or "").strip(),
            "exp_id": str(exp_id or "").strip(),
            "human_summary": dict(human_summary or {}),
        }
    )


def append_experiment_to_baseline(
    *,
    baseline_id: str,
    exp_id: str,
    study_id: str,
    title: str,
    verdict: dict[str, Any],
    perf: dict[str, Any],
    compare: dict[str, Any],
    human_output_refs: dict[str, Any],
    window_key: str,
    variant_name: str,
) -> dict[str, Any]:
    record = baseline_access.load_baseline_record(baseline_id) or {}
    baseline_dir = baseline_access.baseline_dir(baseline_id)
    machine_root = baseline_dir / "machine"
    human_root = baseline_dir / "human"
    machine_root.mkdir(parents=True, exist_ok=True)
    human_root.mkdir(parents=True, exist_ok=True)

    status = str(verdict.get("status") or "UNKNOWN")
    human_summary = {
        "title": title,
        "study_id": study_id,
        "window_key": window_key,
        "variant_name": variant_name,
        "verdict": status,
        "reason": str(verdict.get("reason") or ""),
        "human_output_refs": dict(human_output_refs or {}),
        "perf": {
            "cagr": perf.get("cagr"),
            "max_drawdown": perf.get("max_drawdown"),
            "sharpe": perf.get("sharpe"),
            "trades": perf.get("trades"),
        },
        "compare": dict(compare or {}),
    }
    ledger_entry = build_baseline_ledger_entry(
        baseline_id=baseline_id,
        exp_id=exp_id,
        verdict=status,
        summary=human_summary,
    )
    report_append = build_baseline_report_append(
        baseline_id=baseline_id,
        exp_id=exp_id,
        human_summary=human_summary,
    )

    ledger_path = machine_root / "experiment_ledger.jsonl"
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ledger_entry, ensure_ascii=False) + "\n")

    report_index_path = machine_root / "report_index.json"
    report_index: list[dict[str, Any]] = []
    if report_index_path.exists():
        try:
            payload = json.loads(report_index_path.read_text(encoding="utf-8-sig"))
            if isinstance(payload, list):
                report_index = payload
            elif isinstance(payload, dict) and isinstance(payload.get("rows"), list):
                report_index = list(payload.get("rows") or [])
        except Exception:
            report_index = []
    report_index.append(
        sanitize_json(
            {
                "exp_id": exp_id,
                "study_id": study_id,
                "window_key": window_key,
                "variant_name": variant_name,
                "verdict": status,
                "created_at": datetime.now().isoformat(),
            }
        )
    )
    _write_json(report_index_path, {"rows": report_index})

    champion_path = machine_root / "latest_champion.json"
    champion_updated = False
    if status == "PASS":
        champion_payload = sanitize_json(
            {
                "baseline_id": baseline_id,
                "exp_id": exp_id,
                "study_id": study_id,
                "window_key": window_key,
                "variant_name": variant_name,
                "updated_at": datetime.now().isoformat(),
                "linked_exp_id": str(record.get("linked_exp_id") or ""),
                "perf": {
                    "cagr": perf.get("cagr"),
                    "max_drawdown": perf.get("max_drawdown"),
                    "sharpe": perf.get("sharpe"),
                    "trades": perf.get("trades"),
                },
            }
        )
        _write_json(champion_path, champion_payload)
        champion_updated = True

    baseline_report_path = human_root / "baseline_report.md"
    existing_report = baseline_report_path.read_text(encoding="utf-8-sig") if baseline_report_path.exists() else ""
    section = "\n".join(
        [
            f"## {title}",
            f"- exp_id: {exp_id}",
            f"- study_id: {study_id}",
            f"- window/variant: {window_key}/{variant_name}",
            f"- verdict: {status}",
            f"- reason: {str(verdict.get('reason') or '').strip() or '暂无'}",
            f"- cagr: {perf.get('cagr')}",
            f"- max_drawdown: {perf.get('max_drawdown')}",
            f"- sharpe: {perf.get('sharpe')}",
            f"- trades: {perf.get('trades')}",
            "",
        ]
    )
    baseline_report_path.write_text((existing_report + ("\n" if existing_report else "") + section).strip() + "\n", encoding="utf-8")

    digest_path = human_root / "baseline_digest.md"
    digest_existing = digest_path.read_text(encoding="utf-8-sig").splitlines() if digest_path.exists() else []
    digest_line = f"- {datetime.now().date().isoformat()} | {exp_id} | {window_key}/{variant_name} | {status} | CAGR={perf.get('cagr')} | MDD={perf.get('max_drawdown')}"
    digest_lines = [line for line in digest_existing if line.strip()]
    digest_lines.append(digest_line)
    digest_path.write_text("\n".join(digest_lines[-20:]) + "\n", encoding="utf-8")

    return sanitize_json(
        {
            "ledger": str(ledger_path.relative_to(baseline_dir)).replace("\\", "/"),
            "report_index": str(report_index_path.relative_to(baseline_dir)).replace("\\", "/"),
            "baseline_report": str(baseline_report_path.relative_to(baseline_dir)).replace("\\", "/"),
            "baseline_digest": str(digest_path.relative_to(baseline_dir)).replace("\\", "/"),
            "champion_updated": champion_updated,
            "report_append": report_append,
        }
    )
