from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from backend.core.tools.experiment_artifact_access import experiments_root
from backend.core.tools.saved_config_access import _hash_json, sanitize_json

BREAKOUT_ATR_STOP_K10_CANDIDATE = "v2-breakout-atr-stop-k10-candidate"
BREAKOUT_BR35_ATR10_CANDIDATE = "v2-breakout-br35-atr10-candidate"

_EXPERIMENTS_ROOT = experiments_root()

_CANDIDATE_DEFS: dict[str, dict[str, Any]] = {
    BREAKOUT_ATR_STOP_K10_CANDIDATE: {
        "candidate_name": BREAKOUT_ATR_STOP_K10_CANDIDATE,
        "candidate_kind": "locked_baseline_candidate",
        "locked_baseline_exp_id": "exp_20260307_051743747_77d8",
        "locked_baseline_cfg_path": _EXPERIMENTS_ROOT / "exp_20260307_051743747_77d8" / "run_config.json",
        "locked_baseline_perf_path": _EXPERIMENTS_ROOT / "exp_20260307_051743747_77d8" / "perf.json",
        "locked_baseline_meta_path": _EXPERIMENTS_ROOT / "exp_20260307_051743747_77d8" / "run_meta.json",
        "main_change_path": "strategy.params.atr_stop_k",
        "allowed_diff_paths": ["strategy.params.atr_stop_k"],
        "allowed_diff_path_tuple": ("strategy", "params", "atr_stop_k"),
        "change_label": "atr_stop_k",
        "candidate_value": 1.0,
        "summary_title": "Breakout ATR Stop K10 Candidate Summary",
        "evidence_bundle": (
            ("full_sample", _EXPERIMENTS_ROOT / "atr_stop_research_20260307_161615" / "summary.json"),
            ("local_robustness", _EXPERIMENTS_ROOT / "atr_stop_local_robustness_20260307_161712" / "summary.json"),
            ("window_check", _EXPERIMENTS_ROOT / "atr_stop_window_check_20260307_161756" / "summary.json"),
            ("terminal_sensitivity", _EXPERIMENTS_ROOT / "atr_stop_terminal_sensitivity_20260307_162729" / "summary.json"),
        ),
    },
    BREAKOUT_BR35_ATR10_CANDIDATE: {
        "candidate_name": BREAKOUT_BR35_ATR10_CANDIDATE,
        "candidate_kind": "locked_formal_candidate",
        "locked_baseline_exp_id": "exp_20260307_171750033_eb7b",
        "locked_baseline_cfg_path": _EXPERIMENTS_ROOT / "exp_20260307_171750033_eb7b" / "run_config.json",
        "locked_baseline_perf_path": _EXPERIMENTS_ROOT / "exp_20260307_171750033_eb7b" / "perf.json",
        "locked_baseline_meta_path": _EXPERIMENTS_ROOT / "exp_20260307_171750033_eb7b" / "run_meta.json",
        "main_change_path": "strategy.params.breakout_window",
        "allowed_diff_paths": ["strategy.params.breakout_window"],
        "allowed_diff_path_tuple": ("strategy", "params", "breakout_window"),
        "change_label": "breakout_window",
        "candidate_value": 35,
        "summary_title": "Breakout BR35 ATR10 Candidate Summary",
        "evidence_bundle": (
            ("full_sample", _EXPERIMENTS_ROOT / "breakout_window_research_20260307_190247" / "summary.json"),
            ("formal_robustness", _EXPERIMENTS_ROOT / "breakout_window35_robustness_20260307_191748" / "summary.json"),
        ),
    },
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _candidate_def(candidate_name: str) -> dict[str, Any]:
    definition = _CANDIDATE_DEFS.get(str(candidate_name or "").strip().lower())
    if definition is None:
        raise ValueError(f"unknown locked candidate preset: {candidate_name!r}")
    return definition


def is_locked_candidate_preset(preset: str | None) -> bool:
    return str(preset or "").strip().lower() in _CANDIDATE_DEFS


def is_breakout_atr_stop_k10_candidate(preset: str | None) -> bool:
    return str(preset or "").strip().lower() == BREAKOUT_ATR_STOP_K10_CANDIDATE


def is_breakout_br35_atr10_candidate(preset: str | None) -> bool:
    return str(preset or "").strip().lower() == BREAKOUT_BR35_ATR10_CANDIDATE


def _load_json(path: Path, *, missing_label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing {missing_label}: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_locked_baseline_config(candidate_name: str = BREAKOUT_ATR_STOP_K10_CANDIDATE) -> dict[str, Any]:
    definition = _candidate_def(candidate_name)
    return _load_json(Path(definition["locked_baseline_cfg_path"]), missing_label="locked baseline config")


def load_locked_baseline_meta(candidate_name: str = BREAKOUT_ATR_STOP_K10_CANDIDATE) -> dict[str, Any]:
    definition = _candidate_def(candidate_name)
    return _load_json(Path(definition["locked_baseline_meta_path"]), missing_label="locked baseline meta")


def _path_text(path: tuple[Any, ...]) -> str:
    return ".".join(str(part) for part in path)


def _collect_diffs(base: Any, candidate: Any, path: tuple[Any, ...] = ()) -> list[tuple[tuple[Any, ...], Any, Any]]:
    if isinstance(base, dict) and isinstance(candidate, dict):
        diffs: list[tuple[tuple[Any, ...], Any, Any]] = []
        for key in sorted(set(base.keys()) | set(candidate.keys())):
            if key not in base:
                diffs.append((path + (key,), "<missing>", candidate[key]))
                continue
            if key not in candidate:
                diffs.append((path + (key,), base[key], "<missing>"))
                continue
            diffs.extend(_collect_diffs(base[key], candidate[key], path + (key,)))
        return diffs
    if isinstance(base, list) and isinstance(candidate, list):
        if len(base) != len(candidate):
            return [(path, base, candidate)]
        diffs: list[tuple[tuple[Any, ...], Any, Any]] = []
        for idx, (base_item, candidate_item) in enumerate(zip(base, candidate)):
            diffs.extend(_collect_diffs(base_item, candidate_item, path + (idx,)))
        return diffs
    if base != candidate:
        return [(path, base, candidate)]
    return []


def _format_diff_list(diffs: list[tuple[tuple[Any, ...], Any, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "path": _path_text(diff_path),
            "baseline": sanitize_json(base_value),
            "candidate": sanitize_json(candidate_value),
        }
        for diff_path, base_value, candidate_value in diffs
    ]


def _get_nested_value(obj: dict[str, Any], path: tuple[Any, ...], default: Any = None) -> Any:
    current: Any = obj
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _set_nested_value(obj: dict[str, Any], path: tuple[Any, ...], value: Any) -> None:
    current: dict[str, Any] = obj
    for key in path[:-1]:
        if not isinstance(current.get(key), dict):
            current[key] = {}
        current = current[key]
    current[path[-1]] = value


def _build_static_t1_guard() -> dict[str, Any]:
    sim_path = _repo_root() / "backend" / "core" / "engine_vector" / "strict_runtime_breakout.py"
    provider_path = _repo_root() / "backend" / "core" / "engine_vector" / "breakout_signal_provider.py"
    sim_text = sim_path.read_text(encoding="utf-8")
    sim_guard_path = sim_path
    required_sim_patterns = (
        "ds = provider.day_signals(day, i, ctx)",
        "pending[next_day] = [",
    )
    provider_text = provider_path.read_text(encoding="utf-8")

    missing_sim = [pattern for pattern in required_sim_patterns if pattern not in sim_text]
    if missing_sim:
        raise RuntimeError(f"time-alignment guard failed in {sim_guard_path}: missing {missing_sim!r}")

    required_provider_patterns = (
        "bench_close_s.rolling(regime_ma, min_periods=regime_ma).mean()",
        "self._risk_on = np.ones(t, dtype=bool)",
        "self._risk_on[valid_bench] = self._bench_close[valid_bench] > bench_ma[valid_bench]",
    )
    missing_provider = [pattern for pattern in required_provider_patterns if pattern not in provider_text]
    if missing_provider:
        raise RuntimeError(f"provider audit failed in {provider_path}: missing {missing_provider!r}")

    return sanitize_json(
        {
            "provider_signal_ref": f"{sim_guard_path}:469",
            "next_day_queue_ref": f"{sim_guard_path}:595",
            "provider_regime_ref": f"{provider_path}:176",
            "audit_mode": "static_code_contract",
            "t1_execution_confirmed": True,
        }
    )


def load_candidate_evidence_bundle(candidate_name: str) -> list[dict[str, Any]]:
    definition = _candidate_def(candidate_name)
    evidence: list[dict[str, Any]] = []
    missing: list[str] = []
    for label, path in definition["evidence_bundle"]:
        summary_path = Path(path)
        if not summary_path.exists():
            missing.append(f"{label}: {summary_path}")
            continue
        obj = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        baseline_exp_id = (
            str(obj.get("baseline_exp_id") or "")
            or str(obj.get("base_exp_id") or "")
            or str(obj.get("source_baseline_exp_id") or "")
        )
        evidence.append(
            {
                "label": label,
                "summary_json_path": str(summary_path),
                "summary_md_path": str(summary_path.with_suffix(".md")),
                "generated_at": str(obj.get("generated_at") or ""),
                "baseline_exp_id": baseline_exp_id,
            }
        )
    if missing:
        raise FileNotFoundError("candidate evidence bundle is incomplete:\n" + "\n".join(missing))
    return evidence


def build_locked_candidate_cfg(candidate_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    definition = _candidate_def(candidate_name)
    base_cfg = load_locked_baseline_config(candidate_name)
    baseline_meta = load_locked_baseline_meta(candidate_name)
    strategy_name = str((base_cfg.get("strategy") or {}).get("name") or "").strip().lower()
    if strategy_name != "breakout_trend":
        raise ValueError(f"locked baseline strategy is not breakout_trend: {strategy_name!r}")

    allowed_path = tuple(definition["allowed_diff_path_tuple"])
    candidate_cfg = deepcopy(base_cfg)
    baseline_value = _get_nested_value(candidate_cfg, allowed_path)
    _set_nested_value(candidate_cfg, allowed_path, definition["candidate_value"])

    diffs = _collect_diffs(base_cfg, candidate_cfg)
    unexpected = [diff for diff in diffs if diff[0] != allowed_path]
    if unexpected:
        lines = []
        for diff_path, base_value, candidate_value in unexpected[:10]:
            lines.append(f"{_path_text(diff_path)}: baseline={base_value!r}, candidate={candidate_value!r}")
        raise ValueError("candidate drifted beyond allowed path before execution:\n" + "\n".join(lines))

    evidence_bundle = load_candidate_evidence_bundle(candidate_name)
    baseline_data = dict(baseline_meta.get("data") or {})
    baseline_code = dict(baseline_meta.get("code") or {})
    locked_runtime_overrides = {
        "universe_mode": str(baseline_data.get("universe_mode") or "").strip(),
        "price_adj": str(baseline_meta.get("price_adj_mode") or "hfq").strip() or "hfq",
        "fast_mode": bool(baseline_code.get("fast_mode", True)),
    }
    meta = {
        "candidate_name": definition["candidate_name"],
        "candidate_kind": definition["candidate_kind"],
        "source_baseline_exp_id": definition["locked_baseline_exp_id"],
        "source_baseline_config_path": str(definition["locked_baseline_cfg_path"]),
        "source_baseline_meta_path": str(definition["locked_baseline_meta_path"]),
        "source_baseline_perf_path": str(definition["locked_baseline_perf_path"]),
        "source_baseline_config_hash": _hash_json(base_cfg),
        "candidate_config_hash": _hash_json(candidate_cfg),
        "main_change_path": definition["main_change_path"],
        "allowed_diff_paths": list(definition["allowed_diff_paths"]),
        "baseline_value": baseline_value,
        "candidate_value": definition["candidate_value"],
        "enabled_by_default": False,
        "rollback_value": baseline_value,
        "locked_runtime_overrides": locked_runtime_overrides,
        "preflight_diffs": _format_diff_list(diffs),
        "evidence_bundle": evidence_bundle,
    }
    return candidate_cfg, sanitize_json(meta)


def build_breakout_atr_stop_k10_candidate_cfg() -> tuple[dict[str, Any], dict[str, Any]]:
    return build_locked_candidate_cfg(BREAKOUT_ATR_STOP_K10_CANDIDATE)


def build_breakout_br35_atr10_candidate_cfg() -> tuple[dict[str, Any], dict[str, Any]]:
    return build_locked_candidate_cfg(BREAKOUT_BR35_ATR10_CANDIDATE)


def assess_locked_candidate_results(candidate_name: str, results_dir: Path) -> dict[str, Any]:
    definition = _candidate_def(candidate_name)
    baseline_cfg = load_locked_baseline_config(candidate_name)
    runtime_cfg_path = results_dir / "run_config.json"
    if not runtime_cfg_path.exists():
        raise FileNotFoundError(f"missing candidate runtime config: {runtime_cfg_path}")
    runtime_cfg = json.loads(runtime_cfg_path.read_text(encoding="utf-8-sig"))

    allowed_path = tuple(definition["allowed_diff_path_tuple"])
    diffs = _collect_diffs(baseline_cfg, runtime_cfg)
    unexpected = [diff for diff in diffs if diff[0] != allowed_path]

    audit_path = results_dir / "audit.json"
    audit_summary: dict[str, Any] = {}
    time_alignment_guard: dict[str, Any] | None = None
    blockers: list[str] = []
    if audit_path.exists():
        audit_obj = json.loads(audit_path.read_text(encoding="utf-8-sig"))
        if isinstance(audit_obj.get("summary"), dict):
            audit_summary = dict(audit_obj.get("summary") or {})
        time_alignment_guard = sanitize_json(audit_obj.get("summary") or {})
    else:
        try:
            time_alignment_guard = _build_static_t1_guard()
        except Exception as exc:
            blockers.append(f"t1_static_guard_failed: {exc}")

    if unexpected:
        blockers.append("non_target_config_drift: " + ", ".join(_path_text(diff_path) for diff_path, _, _ in unexpected[:10]))
    if int(audit_summary.get("t1_check_fail", 0) or 0) > 0:
        blockers.append(f"t1_check_fail={int(audit_summary.get('t1_check_fail', 0) or 0)}")

    return sanitize_json(
        {
            "status": "blocked" if blockers else "ready",
            "runtime_config_path": str(runtime_cfg_path),
            "audit_path": str(audit_path) if audit_path.exists() else None,
            "diffs": _format_diff_list(diffs),
            "unexpected_diffs": _format_diff_list(unexpected),
            "audit_summary": audit_summary,
            "time_alignment_guard": time_alignment_guard,
            "blockers": blockers,
        }
    )


def assess_breakout_atr_stop_k10_candidate_results(results_dir: Path) -> dict[str, Any]:
    return assess_locked_candidate_results(BREAKOUT_ATR_STOP_K10_CANDIDATE, results_dir)


def assess_breakout_br35_atr10_candidate_results(results_dir: Path) -> dict[str, Any]:
    return assess_locked_candidate_results(BREAKOUT_BR35_ATR10_CANDIDATE, results_dir)


def write_locked_candidate_artifacts(
    *,
    candidate_name: str,
    results_dir: Path,
    result: dict[str, Any],
    candidate_meta: dict[str, Any],
) -> dict[str, Any]:
    definition = _candidate_def(candidate_name)
    assessment = assess_locked_candidate_results(candidate_name, results_dir)
    summary_obj = {
        "candidate_name": candidate_name,
        "status": str(assessment.get("status") or "blocked"),
        "current_exp_id": str(result.get("exp_id") or ""),
        "current_results_dir": str(results_dir),
        "current_metrics": {
            "cagr": float(result.get("cagr", 0.0) or 0.0),
            "max_drawdown": float(result.get("max_drawdown", 0.0) or 0.0),
            "sharpe": float(result.get("sharpe", 0.0) or 0.0),
            "calmar": float(result.get("calmar", 0.0) or 0.0),
            "total_return": float(result.get("total_return", 0.0) or 0.0),
            "trades": int(result.get("trades", 0) or 0),
        },
        "provenance": candidate_meta,
        "assessment": assessment,
        "notes": [
            "This result marks a formal candidate, not a promoted baseline.",
            "Rollback: stop using the candidate preset and return to the previous explicit candidate or baseline entry.",
        ],
    }

    provenance_path = results_dir / "candidate_provenance.json"
    provenance_path.write_text(json.dumps(candidate_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_json_path = results_dir / "candidate_summary.json"
    summary_json_path.write_text(json.dumps(summary_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    blockers = list(assessment.get("blockers") or [])
    evidence_bundle = list(candidate_meta.get("evidence_bundle") or [])
    lines = [
        f"# {definition['summary_title']}",
        "",
        f"- candidate_name: `{candidate_name}`",
        f"- status: `{summary_obj['status']}`",
        f"- current_exp_id: `{summary_obj['current_exp_id']}`",
        f"- source_baseline_exp_id: `{candidate_meta.get('source_baseline_exp_id')}`",
        f"- main_change_path: `{candidate_meta.get('main_change_path')}`",
        f"- {definition['change_label']}: `{candidate_meta.get('baseline_value')} -> {candidate_meta.get('candidate_value')}`",
        "",
        "## Current Result",
        "",
        "| CAGR | MaxDD | Sharpe | Calmar | Total Return | Trades |",
        "|---:|---:|---:|---:|---:|---:|",
        "| {cagr:.2%} | {max_drawdown:.2%} | {sharpe:.2f} | {calmar:.2f} | {total_return:.2%} | {trades} |".format(
            **summary_obj["current_metrics"]
        ),
        "",
        "## Audit",
        "",
        f"- config drift status: `{summary_obj['status']}`",
        f"- audit t1_check_fail: `{int((assessment.get('audit_summary') or {}).get('t1_check_fail', 0) or 0)}`",
        f"- audit mode: `{str((assessment.get('time_alignment_guard') or {}).get('audit_mode') or ('audit_json' if assessment.get('audit_path') else 'unknown'))}`",
    ]
    if blockers:
        lines.extend(["", "## Blockers", ""])
        for item in blockers:
            lines.append(f"- `{item}`")
    else:
        lines.extend(
            [
                "",
                "## Conclusion",
                "",
                "- The runtime artifact passes the single-path drift check and the T+1 audit guard.",
                "- This remains a formal candidate, not a promoted baseline default.",
                "- Rollback: stop using the candidate preset and return to the previous explicit candidate or baseline entry.",
            ]
        )
    lines.extend(["", "## Evidence Bundle", ""])
    for item in evidence_bundle:
        lines.append(
            "- `{label}`: `{summary_json_path}`".format(
                label=str(item.get("label") or ""),
                summary_json_path=str(item.get("summary_json_path") or ""),
            )
        )
    summary_md_path = results_dir / "candidate_summary.md"
    summary_md_path.write_text("\n".join(lines), encoding="utf-8")

    return sanitize_json(
        {
            "status": summary_obj["status"],
            "blockers": blockers,
            "candidate_provenance_path": str(provenance_path),
            "candidate_summary_json_path": str(summary_json_path),
            "candidate_summary_path": str(summary_md_path),
            "assessment": assessment,
        }
    )


def write_breakout_atr_stop_k10_candidate_artifacts(
    *,
    results_dir: Path,
    result: dict[str, Any],
    candidate_meta: dict[str, Any],
) -> dict[str, Any]:
    return write_locked_candidate_artifacts(
        candidate_name=BREAKOUT_ATR_STOP_K10_CANDIDATE,
        results_dir=results_dir,
        result=result,
        candidate_meta=candidate_meta,
    )


def write_breakout_br35_atr10_candidate_artifacts(
    *,
    results_dir: Path,
    result: dict[str, Any],
    candidate_meta: dict[str, Any],
) -> dict[str, Any]:
    return write_locked_candidate_artifacts(
        candidate_name=BREAKOUT_BR35_ATR10_CANDIDATE,
        results_dir=results_dir,
        result=result,
        candidate_meta=candidate_meta,
    )
