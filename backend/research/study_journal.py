from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.api.shared.json_utils import sanitize_json
from backend.api.shared.paths import results_root

ROUND_SCHEMA_VERSION = "openclaw_study_round@1"
SUMMARY_SCHEMA_VERSION = "openclaw_study_auto_summary@1"

_ROUND_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
_WINDOW_BUCKETS = {
    "1626": "2016-2026",
    "2016-2026": "2016-2026",
    "2016_2026": "2016-2026",
    "1217": "2012-2017",
    "2012-2017": "2012-2017",
    "2012_2017": "2012-2017",
    "1226": "2012-2026",
    "2012-2026": "2012-2026",
    "2012_2026": "2012-2026",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _json_clone(value: Any) -> Any:
    return json.loads(json.dumps(sanitize_json(value), ensure_ascii=False))


def journal_root() -> Path:
    raw = os.environ.get("STUDY_JOURNAL_ROOT", "").strip()
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            path = (_repo_root() / path).resolve()
        return path
    return (_repo_root() / "research" / "study_journal").resolve()


def rounds_root() -> Path:
    root = journal_root() / "rounds"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _conclusions_root() -> Path:
    return (results_root() / "studies" / "conclusions").resolve()


def validate_round_id(round_id: str) -> str:
    value = str(round_id or "").strip()
    if not value or not _ROUND_ID_RE.match(value):
        raise ValueError("round_id must be a safe slug")
    return value


def round_path(round_id: str) -> Path:
    safe_id = validate_round_id(round_id)
    root = rounds_root().resolve()
    path = (root / f"{safe_id}.json").resolve()
    if root not in path.parents:
        raise ValueError("round path escaped journal root")
    return path


def _generate_round_id() -> str:
    base = "sr_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = base
    suffix = 2
    while round_path(candidate).exists():
        candidate = f"{base}_{suffix:02d}"
        suffix += 1
    return candidate


def _read_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise ValueError(f"invalid study round json: {path}") from exc
    if not isinstance(obj, dict):
        raise ValueError(f"study round json must be an object: {path}")
    return obj


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_json(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _unique_texts(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _normalize_evidence(item: dict[str, Any]) -> dict[str, Any]:
    kind = str(item.get("kind") or "experiment").strip() or "experiment"
    evidence = {
        "kind": kind,
        "exp_id": str(item.get("exp_id") or "").strip(),
        "study_id": str(item.get("study_id") or "").strip(),
        "window_key": str(item.get("window_key") or "").strip(),
        "variant_name": str(item.get("variant_name") or "").strip(),
        "path": str(item.get("path") or "").strip(),
        "note": str(item.get("note") or "").strip(),
        "linked_at": str(item.get("linked_at") or "").strip(),
    }
    for key, value in item.items():
        if key not in evidence:
            evidence[str(key)] = sanitize_json(value)
    return evidence


def _normalize_round(
    payload: dict[str, Any],
    *,
    existing: dict[str, Any] | None = None,
    touch: bool = True,
) -> dict[str, Any]:
    base = _json_clone(existing or {})
    for key, value in payload.items():
        if key in {"created_at", "auto_summary"}:
            continue
        base[str(key)] = sanitize_json(value)

    now = _now_iso()
    round_id = validate_round_id(str(base.get("round_id") or _generate_round_id()))
    base["schema_version"] = ROUND_SCHEMA_VERSION
    base["round_id"] = round_id
    if existing is None and payload.get("created_at"):
        base["created_at"] = str(payload.get("created_at") or "").strip()
    if existing is None and isinstance(payload.get("auto_summary"), dict):
        base["auto_summary"] = sanitize_json(payload.get("auto_summary"))
    base["created_at"] = str(base.get("created_at") or now)
    base["updated_at"] = now if touch else str(base.get("updated_at") or now)
    base["title"] = str(base.get("title") or "未命名研究轮次").strip() or "未命名研究轮次"
    base["status"] = str(base.get("status") or "draft").strip() or "draft"
    base["study_id"] = str(base.get("study_id") or "").strip()
    base["asset_scope"] = str(base.get("asset_scope") or "").strip()
    base["baseline_id"] = str(base.get("baseline_id") or "").strip()
    base["primary_question"] = str(base.get("primary_question") or "").strip()
    base["primary_variable"] = str(base.get("primary_variable") or "").strip()
    base["fixed_assumptions"] = _unique_texts(_as_list(base.get("fixed_assumptions")))
    base["windows"] = _unique_texts(_as_list(base.get("windows")))
    base["variants"] = _unique_texts(_as_list(base.get("variants")))
    base["evidence"] = [
        _normalize_evidence(item)
        for item in _as_list(base.get("evidence"))
        if isinstance(item, dict)
    ]
    base["key_findings"] = _unique_texts(_as_list(base.get("key_findings")))
    base["audit"] = _as_dict(base.get("audit"))
    base["decision"] = _as_dict(base.get("decision")) or {"status": "draft", "reason": ""}
    base["next_actions"] = _unique_texts(_as_list(base.get("next_actions")))
    base["tags"] = _unique_texts(_as_list(base.get("tags")))
    base["notes"] = [
        note
        for note in _as_list(base.get("notes"))
        if isinstance(note, dict) and str(note.get("body") or "").strip()
    ]
    return sanitize_json(base)


def _conclusion_matches_round(record: dict[str, Any], round_payload: dict[str, Any]) -> bool:
    exp_id = str(record.get("exp_id") or "").strip()
    study_id = str(record.get("study_id") or "").strip()
    window_key = str(record.get("window_key") or "").strip()
    variant_name = str(record.get("variant_name") or "").strip()
    evidence = _as_list(round_payload.get("evidence"))
    evidence_exp_ids = {str(item.get("exp_id") or "").strip() for item in evidence if isinstance(item, dict)}
    if exp_id and exp_id in evidence_exp_ids:
        return True
    if study_id and study_id == str(round_payload.get("study_id") or "").strip():
        windows = {str(item or "").strip() for item in _as_list(round_payload.get("windows"))}
        variants = {str(item or "").strip() for item in _as_list(round_payload.get("variants"))}
        return (not windows or window_key in windows) and (not variants or variant_name in variants)
    return False


def list_conclusion_records(
    *,
    study_id: str | None = None,
    exp_id: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    root = _conclusions_root()
    if not root.exists():
        return []
    safe_limit = max(1, min(int(limit or 200), 1000))
    study_filter = str(study_id or "").strip()
    exp_filter = str(exp_id or "").strip()
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("registry.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except Exception:
            continue
        for line in lines:
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            if study_filter and str(payload.get("study_id") or "").strip() != study_filter:
                continue
            if exp_filter and str(payload.get("exp_id") or "").strip() != exp_filter:
                continue
            item = sanitize_json(dict(payload))
            item["registry_path"] = str(path.relative_to(results_root())).replace("\\", "/")
            records.append(item)
    records.sort(key=lambda item: str(item.get("recorded_at") or ""), reverse=True)
    return records[:safe_limit]


def _window_bucket(window_key: str) -> str | None:
    value = str(window_key or "").strip()
    if value in _WINDOW_BUCKETS:
        return _WINDOW_BUCKETS[value]
    lowered = value.lower()
    for token, bucket in _WINDOW_BUCKETS.items():
        if token.lower() in lowered:
            return bucket
    return None


def _metric_highlights(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    highlights: list[dict[str, Any]] = []
    for record in records:
        metrics = _as_dict(record.get("key_metrics"))
        if not metrics:
            continue
        row: dict[str, Any] = {
            "exp_id": str(record.get("exp_id") or "").strip(),
            "window_key": str(record.get("window_key") or "").strip(),
            "variant_name": str(record.get("variant_name") or "").strip(),
        }
        for metric in ("cagr", "sharpe", "max_drawdown", "calmar"):
            metric_row = _as_dict(metrics.get(metric))
            if metric_row:
                row[metric] = {
                    "candidate": metric_row.get("candidate"),
                    "baseline": metric_row.get("baseline"),
                    "delta": metric_row.get("delta"),
                }
        if len(row) > 3:
            highlights.append(row)
    return highlights[:8]


def _research_verdict_key(value: Any) -> str:
    raw = str(value or "").strip()
    lowered = raw.lower()
    if lowered in {"confirmed", "falsified", "inconclusive"}:
        return lowered.upper()
    upper = raw.upper()
    if upper in {"PASS", "FAIL"}:
        return f"LEGACY_{upper}"
    return upper or "UNKNOWN"


def _gate_status_key(record: dict[str, Any]) -> str:
    gate = str(record.get("gate_status") or "").strip().upper()
    if gate in {"PASS", "FAIL", "UNKNOWN"}:
        return gate
    verdict = str(record.get("verdict") or "").strip().upper()
    if verdict in {"PASS", "FAIL"}:
        return verdict
    return "UNKNOWN"


def build_auto_summary(round_payload: dict[str, Any]) -> dict[str, Any]:
    evidence = [
        item
        for item in _as_list(round_payload.get("evidence"))
        if isinstance(item, dict)
    ]
    conclusion_records = [
        record
        for record in list_conclusion_records(study_id=str(round_payload.get("study_id") or "").strip(), limit=1000)
        if _conclusion_matches_round(record, round_payload)
    ]
    verdicts = Counter(_research_verdict_key(record.get("verdict")) for record in conclusion_records)
    gate_statuses = Counter(_gate_status_key(record) for record in conclusion_records)
    evidence_windows = [
        str(item.get("window_key") or "").strip()
        for item in evidence
        if isinstance(item, dict) and str(item.get("window_key") or "").strip()
    ]
    record_windows = [
        str(record.get("window_key") or "").strip()
        for record in conclusion_records
        if str(record.get("window_key") or "").strip()
    ]
    buckets = sorted({bucket for window in [*evidence_windows, *record_windows] if (bucket := _window_bucket(window))})
    three_window_ready = {"2016-2026", "2012-2017", "2012-2026"}.issubset(set(buckets))

    facts = [
        f"已关联 {len(evidence)} 条证据。",
        f"匹配到 {len(conclusion_records)} 条 study conclusion registry 记录。",
    ]
    if buckets:
        facts.append("窗口覆盖：" + "、".join(buckets) + "。")
    if verdicts:
        verdict_text = "、".join(f"{key}={value}" for key, value in sorted(verdicts.items()))
        facts.append(f"verdict 分布：{verdict_text}。")

    if gate_statuses:
        gate_text = ", ".join(f"{key}={value}" for key, value in sorted(gate_statuses.items()))
        facts.append(f"gate status distribution: {gate_text}.")

    audit = _as_dict(round_payload.get("audit"))
    risks: list[str] = []
    if not evidence:
        risks.append("尚未关联实验或报告证据，不能形成研究结论。")
    if evidence and not conclusion_records:
        risks.append("关联证据未匹配到 conclusion registry，指标和 verdict 需要人工核对。")
    if any(str(key).startswith("LEGACY_") for key in verdicts):
        risks.append("legacy PASS/FAIL verdict records are gate status only and cannot be treated as study acceptance.")
    if not three_window_ready:
        risks.append("三窗口证据尚不完整，不能作为 baseline 升级依据。")
    if not audit.get("same_window_compare"):
        risks.append("尚未确认 same-window compare。")
    if not audit.get("config_truth_checked"):
        risks.append("尚未确认 config truth。")
    if not audit.get("nav_lineage_checked"):
        risks.append("尚未确认 NAV/account lineage。")

    next_actions = list(_as_list(round_payload.get("next_actions")))
    if not evidence:
        next_actions.append("先关联至少一个实验或报告证据。")
    if not three_window_ready:
        next_actions.append("补齐 2016-2026、2012-2017、2012-2026 三窗口证据。")
    if not audit.get("config_truth_checked") or not audit.get("nav_lineage_checked"):
        next_actions.append("补做 config truth 与 NAV lineage 审计。")
    next_actions = _unique_texts(next_actions)

    if not evidence:
        reliability = "low"
        conclusion = "尚无可接受证据，当前只能记录研究意图，不能形成结论。"
    elif not conclusion_records:
        reliability = "low"
        conclusion = "已有证据链接但缺少可解析 conclusion registry，结论需要人工补证。"
    elif three_window_ready and not risks:
        reliability = "reviewable"
        conclusion = "证据、三窗口和审计项已基本齐备，可以进入人工审阅和决策。"
    else:
        reliability = "partial"
        pass_count = verdicts.get("CONFIRMED", 0)
        fail_count = verdicts.get("FALSIFIED", 0)
        if pass_count > fail_count:
            conclusion = "已有正向证据，但仍需补齐风险、窗口或审计项后再判断。"
        elif fail_count > pass_count:
            conclusion = "已有负向证据，建议先定位失败来源再决定是否继续。"
        else:
            conclusion = "证据尚不充分或方向混合，当前结论不应升级为 baseline 判断。"

    title = str(round_payload.get("title") or "未命名研究轮次").strip()
    primary_variable = str(round_payload.get("primary_variable") or "").strip()
    headline = title if not primary_variable else f"{title}：主变量={primary_variable}"

    return sanitize_json(
        {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "headline": headline,
            "conclusion_draft": conclusion,
            "reliability": reliability,
            "facts": facts,
            "risks": risks,
            "next_actions": next_actions,
            "evidence_counts": {
                "linked": len(evidence),
                "matched_conclusions": len(conclusion_records),
            },
            "window_coverage": buckets,
            "verdict_counts": dict(sorted(verdicts.items())),
            "gate_status_counts": dict(sorted(gate_statuses.items())),
            "metric_highlights": _metric_highlights(conclusion_records),
        }
    )


def save_round(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_round(payload)
    path = round_path(str(normalized["round_id"]))
    if path.exists():
        raise FileExistsError(f"study round already exists: {normalized['round_id']}")
    normalized["auto_summary"] = build_auto_summary(normalized)
    normalized["reliability"] = str(normalized["auto_summary"].get("reliability") or "low")
    _write_json(path, normalized)
    return normalized


def get_round(round_id: str) -> dict[str, Any]:
    path = round_path(round_id)
    if not path.exists():
        raise FileNotFoundError(f"study round not found: {round_id}")
    payload = _normalize_round(_read_json(path), existing=None, touch=False)
    if not isinstance(payload.get("auto_summary"), dict):
        payload["auto_summary"] = build_auto_summary(payload)
    return sanitize_json(payload)


def list_rounds() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(rounds_root().glob("*.json")):
        try:
            item = get_round(path.stem)
        except Exception:
            continue
        summary = _as_dict(item.get("auto_summary"))
        items.append(
            sanitize_json(
                {
                    "round_id": item.get("round_id"),
                    "title": item.get("title"),
                    "status": item.get("status"),
                    "reliability": item.get("reliability") or summary.get("reliability"),
                    "study_id": item.get("study_id"),
                    "baseline_id": item.get("baseline_id"),
                    "updated_at": item.get("updated_at"),
                    "auto_summary_headline": summary.get("headline"),
                    "evidence_count": len(_as_list(item.get("evidence"))),
                    "tags": _as_list(item.get("tags")),
                }
            )
        )
    items.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return items


def update_round(round_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    current = get_round(round_id)
    patch = dict(patch or {})
    patch["round_id"] = current["round_id"]
    updated = _normalize_round(patch, existing=current)
    updated["auto_summary"] = build_auto_summary(updated)
    updated["reliability"] = str(updated["auto_summary"].get("reliability") or "low")
    _write_json(round_path(round_id), updated)
    return updated


def append_note(round_id: str, note: dict[str, Any]) -> dict[str, Any]:
    current = get_round(round_id)
    notes = _as_list(current.get("notes"))
    now = _now_iso()
    body = str(note.get("body") or "").strip()
    if not body:
        raise ValueError("note body is required")
    notes.append(
        sanitize_json(
            {
                "note_id": str(note.get("note_id") or f"note_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                "kind": str(note.get("kind") or "note").strip() or "note",
                "body": body,
                "created_at": now,
            }
        )
    )
    return update_round(round_id, {"notes": notes})


def link_experiment(round_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
    current = get_round(round_id)
    exp_id = str(evidence.get("exp_id") or "").strip()
    if not exp_id:
        raise ValueError("exp_id is required")
    item = _normalize_evidence({**evidence, "kind": "experiment", "linked_at": _now_iso()})
    items = [
        _normalize_evidence(existing)
        for existing in _as_list(current.get("evidence"))
        if isinstance(existing, dict)
    ]
    dedupe_key = (
        item.get("kind"),
        item.get("exp_id"),
        item.get("window_key"),
        item.get("variant_name"),
    )
    filtered = [
        existing
        for existing in items
        if (
            existing.get("kind"),
            existing.get("exp_id"),
            existing.get("window_key"),
            existing.get("variant_name"),
        )
        != dedupe_key
    ]
    filtered.append(item)
    return update_round(round_id, {"evidence": filtered})


def refresh_auto_summary(round_id: str) -> dict[str, Any]:
    current = get_round(round_id)
    current["auto_summary"] = build_auto_summary(current)
    current["reliability"] = str(current["auto_summary"].get("reliability") or "low")
    current["updated_at"] = _now_iso()
    _write_json(round_path(round_id), current)
    return current
