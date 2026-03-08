"""Baseline regression gate for V2 cleanup changes.

Compare a candidate experiment against the locked March 7 baseline and
classify mismatches as blocking or diagnostic-only drift. When run with
``--rerun`` inside the backtest runtime container, the script reproduces the
baseline request through the current code and compares the new experiment
artifacts against the locked baseline contract.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from html import unescape
from pathlib import Path
from typing import Any

BASELINE_EXP_ID = "exp_20260307_051743747_77d8"
NON_BLOCKING_CATEGORIES = {
    "saved_config_resolution_drift",
    "report_diagnostic_drift",
}
REPORT_OVERVIEW_LABELS = ("回测区间", "基准指数", "对照指数", "股票池数量")
REPORT_KPI_LABELS = ("年化收益", "最大回撤", "夏普比率", "卡尔玛比率", "交易次数", "换手率", "累计收益", "评级")
REPORT_SOURCE_LABELS = ("区间开始", "区间结束", "基准", "标的数量", "漏斗", "配置冲突策略")
REPORT_SOURCE_CATEGORY = {
    "配置冲突策略": "saved_config_resolution_drift",
    "区间开始": "report_diagnostic_drift",
    "区间结束": "report_diagnostic_drift",
    "基准": "report_diagnostic_drift",
    "标的数量": "report_diagnostic_drift",
    "漏斗": "report_diagnostic_drift",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_repo_on_path() -> None:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _exp_dir(exp_id: str) -> Path:
    return _repo_root() / "outputs" / "experiments" / exp_id


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    return _sha256_bytes(path.read_bytes())


def _json_hash(obj: Any) -> str:
    data = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(data)


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_html_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return unescape(text).strip()


def _append_diff(diffs: list[dict[str, Any]], surface: str, expected: Any, actual: Any) -> None:
    if len(diffs) >= 12:
        return
    diffs.append(
        {
            "surface": surface or "$",
            "expected": expected,
            "actual": actual,
        }
    )


def _collect_diffs(expected: Any, actual: Any, surface: str = "") -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []

    def walk(lhs: Any, rhs: Any, path: str) -> None:
        if len(diffs) >= 12:
            return
        if type(lhs) is not type(rhs):
            _append_diff(diffs, path, lhs, rhs)
            return
        if isinstance(lhs, dict):
            for key in sorted(set(lhs.keys()) | set(rhs.keys())):
                next_path = f"{path}.{key}" if path else str(key)
                if key not in lhs:
                    _append_diff(diffs, next_path, "<missing>", rhs.get(key))
                    continue
                if key not in rhs:
                    _append_diff(diffs, next_path, lhs.get(key), "<missing>")
                    continue
                walk(lhs.get(key), rhs.get(key), next_path)
            return
        if isinstance(lhs, list):
            if len(lhs) != len(rhs):
                _append_diff(diffs, path, f"len={len(lhs)}", f"len={len(rhs)}")
                return
            for idx, (l_item, r_item) in enumerate(zip(lhs, rhs)):
                walk(l_item, r_item, f"{path}[{idx}]")
            return
        if lhs != rhs:
            _append_diff(diffs, path, lhs, rhs)

    walk(expected, actual, surface)
    return diffs


def _summarize_run_meta_core(meta: dict[str, Any]) -> dict[str, Any]:
    counters = meta.get("counters") if isinstance(meta.get("counters"), dict) else {}
    return {
        "status": meta.get("status"),
        "tier": meta.get("tier"),
        "data": meta.get("data") if isinstance(meta.get("data"), dict) else {},
        "code": meta.get("code") if isinstance(meta.get("code"), dict) else {},
        "price_adj_mode": meta.get("price_adj_mode"),
        "adj_factor_stats": meta.get("adj_factor_stats") if isinstance(meta.get("adj_factor_stats"), dict) else {},
        "missing_fields": meta.get("missing_fields") if isinstance(meta.get("missing_fields"), list) else [],
        "counters": {
            "avg_positions": counters.get("avg_positions"),
            "max_positions": counters.get("max_positions"),
            "raw_signal": counters.get("raw_signal"),
            "orders": counters.get("orders"),
            "closed_trades": counters.get("closed_trades"),
            "atr_stop_exit_count": counters.get("atr_stop_exit_count"),
            "atr_trail_exit_count": counters.get("atr_trail_exit_count"),
            "take_profit_exit_count": counters.get("take_profit_exit_count"),
            "fixed_stop_loss_exit_count": counters.get("fixed_stop_loss_exit_count"),
            "time_exit_count": counters.get("time_exit_count"),
        },
    }


def _summarize_run_meta_universe(meta: dict[str, Any]) -> dict[str, Any]:
    universe = meta.get("universe") if isinstance(meta.get("universe"), dict) else {}
    return {
        "universe_mode": universe.get("universe_mode"),
        "symbols_source": universe.get("symbols_source"),
        "raw_count": universe.get("raw_count"),
        "constituents_load_status": universe.get("constituents_load_status"),
        "load_table": universe.get("load_table"),
        "index_code": universe.get("index_code"),
        "as_of": universe.get("as_of"),
        "resolve_asof": universe.get("resolve_asof"),
        "dynamic_all_a_entry": universe.get("dynamic_all_a_entry"),
        "filters_config": universe.get("filters_config") if isinstance(universe.get("filters_config"), dict) else {},
        "excluded_counts": universe.get("excluded_counts") if isinstance(universe.get("excluded_counts"), dict) else {},
        "tradable_symbols": universe.get("tradable_symbols"),
        "after_filters_symbols": universe.get("after_filters_symbols"),
    }


def _extract_runtime_draft(config: dict[str, Any]) -> dict[str, Any] | None:
    overrides = config.get("overrides") if isinstance(config.get("overrides"), dict) else {}
    if isinstance(overrides.get("original_workbench_config"), dict):
        return overrides.get("original_workbench_config")
    if isinstance(overrides.get("workbench_config"), dict):
        return overrides.get("workbench_config")
    return None


def _normalized_conflict_policy(meta: dict[str, Any], config: dict[str, Any]) -> Any:
    overrides = config.get("overrides") if isinstance(config.get("overrides"), dict) else {}
    report_consistency = meta.get("report_consistency") if isinstance(meta.get("report_consistency"), dict) else {}
    config_id = str(overrides.get("config_id") or "").strip() or None
    draft = _extract_runtime_draft(config)
    if config_id or isinstance(draft, dict):
        _ensure_repo_on_path()
        from backend.api.endpoints._config_governance import resolve_runtime_config_source  # type: ignore

        try:
            resolution = resolve_runtime_config_source(config_id=config_id, draft_config=draft)
            policy = resolution.get("config_conflict_policy")
            if policy not in (None, ""):
                return policy
        except Exception:
            pass
    return overrides.get("config_conflict_policy") or report_consistency.get("config_conflict_policy")


def _summarize_resolution(meta: dict[str, Any], config: dict[str, Any], saved_record: dict[str, Any] | None) -> dict[str, Any]:
    overrides = config.get("overrides") if isinstance(config.get("overrides"), dict) else {}
    report_consistency = meta.get("report_consistency") if isinstance(meta.get("report_consistency"), dict) else {}
    return {
        "config_id": overrides.get("config_id"),
        "config_source": overrides.get("config_source"),
        "config_conflict_policy": _normalized_conflict_policy(meta, config),
        "report_config_source": report_consistency.get("config_source"),
        "saved_config_meta": {
            "config_hash": (saved_record or {}).get("config_hash"),
            "source_type": (saved_record or {}).get("source_type"),
            "owner": (saved_record or {}).get("owner"),
            "locked": (saved_record or {}).get("locked"),
            "baseline_of": (saved_record or {}).get("baseline_of"),
            "legacy_config_id": (saved_record or {}).get("legacy_config_id"),
        },
    }


def _summarize_perf(perf: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_return": perf.get("total_return"),
        "max_drawdown": perf.get("max_drawdown"),
        "cagr": perf.get("cagr"),
        "sharpe": perf.get("sharpe"),
        "calmar": perf.get("calmar"),
        "trades": perf.get("trades"),
        "turnover": perf.get("turnover"),
    }


def _summarize_nav(nav_rows: list[dict[str, Any]], nav_path: Path) -> dict[str, Any]:
    first = nav_rows[0] if nav_rows else {}
    last = nav_rows[-1] if nav_rows else {}
    return {
        "rows": len(nav_rows),
        "first_date": first.get("date"),
        "last_date": last.get("date"),
        "first_nav": _coerce_float(first.get("nav")),
        "terminal_nav": _coerce_float(last.get("nav")),
        "file_hash": _file_hash(nav_path),
    }


def _summarize_trades(trade_rows: list[dict[str, Any]], trades_path: Path) -> dict[str, Any]:
    reason_counts = Counter(str(row.get("reason_code") or "") for row in trade_rows)
    first = trade_rows[0] if trade_rows else {}
    last = trade_rows[-1] if trade_rows else {}
    return {
        "rows": len(trade_rows),
        "first_trade": {
            "date": first.get("date"),
            "symbol": first.get("symbol"),
            "side": first.get("side"),
            "reason_code": first.get("reason_code"),
        },
        "last_trade": {
            "date": last.get("date"),
            "symbol": last.get("symbol"),
            "side": last.get("side"),
            "reason_code": last.get("reason_code"),
        },
        "reason_counts": dict(sorted(reason_counts.items())),
        "file_hash": _file_hash(trades_path),
    }


def _extract_report_row(html: str, label: str) -> str | None:
    match = re.search(rf"<tr><td>{re.escape(label)}</td><td>(.*?)</td></tr>", html, flags=re.S)
    if not match:
        return None
    return _clean_html_text(match.group(1))


def _extract_report_kpis(html: str) -> dict[str, str]:
    pairs = re.findall(
        r'<div class="kpi-card"><div class="kpi-label">(.*?)</div><div class="kpi-value[^"]*">(.*?)</div></div>',
        html,
        flags=re.S,
    )
    out: dict[str, str] = {}
    for label, value in pairs:
        out[_clean_html_text(label)] = _clean_html_text(value)
    return out


def _extract_report_semantics(report_path: Path) -> dict[str, Any]:
    html = _read_text(report_path)
    kpis = _extract_report_kpis(html)
    overview = {label: _extract_report_row(html, label) for label in REPORT_OVERVIEW_LABELS}
    source_diag = {label: _extract_report_row(html, label) for label in REPORT_SOURCE_LABELS}
    appendix_total = None
    appendix_match = re.search(r"共\s*([0-9,]+)\s*条交易记录", html)
    if appendix_match:
        appendix_total = appendix_match.group(1)
    return {
        "overview": overview,
        "kpis": {label: kpis.get(label) for label in REPORT_KPI_LABELS},
        "source_diag": source_diag,
        "appendix_trade_total": appendix_total,
    }


def _normalize_report_semantics(report: dict[str, Any], meta: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    out = dict(report or {})
    source_diag = dict(out.get("source_diag") or {})
    source_diag["配置冲突策略"] = _normalized_conflict_policy(meta, config)
    out["source_diag"] = source_diag
    return out


def _saved_config_record(config_id: str | None) -> dict[str, Any] | None:
    if not config_id:
        return None
    _ensure_repo_on_path()
    from backend.api.endpoints._config_governance import load_saved_config_record  # type: ignore

    return load_saved_config_record(config_id)


def _baseline_input_bundle(exp_dir: Path) -> dict[str, Any]:
    config = _load_json(exp_dir / "config.json")
    run_config = _load_json(exp_dir / "run_config.json")
    run_meta = _load_json(exp_dir / "run_meta.json")
    perf = _load_json(exp_dir / "perf.json")
    overrides = config.get("overrides") if isinstance(config.get("overrides"), dict) else {}
    config_id = str(overrides.get("config_id") or "").strip() or None
    saved_record = _saved_config_record(config_id)
    draft = _extract_runtime_draft(config)
    return {
        "baseline_exp_id": exp_dir.name,
        "saved_config_id": config_id,
        "saved_config_hash": (saved_record or {}).get("config_hash"),
        "saved_config_source_type": (saved_record or {}).get("source_type"),
        "saved_config_owner": (saved_record or {}).get("owner"),
        "saved_config_locked": (saved_record or {}).get("locked"),
        "saved_config_baseline_of": (saved_record or {}).get("baseline_of"),
        "saved_config_legacy_id": (saved_record or {}).get("legacy_config_id"),
        "draft_hash": _json_hash(draft) if isinstance(draft, dict) else None,
        "config_conflict_policy": _normalized_conflict_policy(run_meta, config),
        "run_config_hash": _json_hash(run_config),
        "run_meta_core": _summarize_run_meta_core(run_meta),
        "run_meta_universe": _summarize_run_meta_universe(run_meta),
        "perf": _summarize_perf(perf),
    }


def _candidate_bundle(exp_dir: Path) -> dict[str, Any]:
    config = _load_json(exp_dir / "config.json")
    run_meta = _load_json(exp_dir / "run_meta.json")
    overrides = config.get("overrides") if isinstance(config.get("overrides"), dict) else {}
    saved_record = _saved_config_record(str(overrides.get("config_id") or "").strip() or None)
    report = _normalize_report_semantics(_extract_report_semantics(exp_dir / "report.html"), run_meta, config)
    return {
        "resolution": _summarize_resolution(run_meta, config, saved_record),
        "run_meta_core": _summarize_run_meta_core(run_meta),
        "run_meta_universe": _summarize_run_meta_universe(run_meta),
        "run_config": _load_json(exp_dir / "run_config.json"),
        "perf": _summarize_perf(_load_json(exp_dir / "perf.json")),
        "nav": _summarize_nav(_load_csv_rows(exp_dir / "nav.csv"), exp_dir / "nav.csv"),
        "trades": _summarize_trades(_load_csv_rows(exp_dir / "portfolio_trades.csv"), exp_dir / "portfolio_trades.csv"),
        "report": report,
    }


def _expected_bundle(exp_dir: Path) -> dict[str, Any]:
    config = _load_json(exp_dir / "config.json")
    run_meta = _load_json(exp_dir / "run_meta.json")
    overrides = config.get("overrides") if isinstance(config.get("overrides"), dict) else {}
    saved_record = _saved_config_record(str(overrides.get("config_id") or "").strip() or None)
    report = _normalize_report_semantics(_extract_report_semantics(exp_dir / "report.html"), run_meta, config)
    return {
        "resolution": _summarize_resolution(run_meta, config, saved_record),
        "run_meta_core": _summarize_run_meta_core(run_meta),
        "run_meta_universe": _summarize_run_meta_universe(run_meta),
        "run_config": _load_json(exp_dir / "run_config.json"),
        "perf": _summarize_perf(_load_json(exp_dir / "perf.json")),
        "nav": _summarize_nav(_load_csv_rows(exp_dir / "nav.csv"), exp_dir / "nav.csv"),
        "trades": _summarize_trades(_load_csv_rows(exp_dir / "portfolio_trades.csv"), exp_dir / "portfolio_trades.csv"),
        "report": report,
    }


def _record_mismatches(
    mismatches: list[dict[str, Any]],
    *,
    category: str,
    surface_prefix: str,
    expected: Any,
    actual: Any,
) -> None:
    blocking = category not in NON_BLOCKING_CATEGORIES
    for diff in _collect_diffs(expected, actual, surface_prefix):
        mismatches.append(
            {
                "category": category,
                "blocking": blocking,
                "surface": diff["surface"],
                "expected": diff["expected"],
                "actual": diff["actual"],
            }
        )


def _compare_report_source_diag(expected: dict[str, Any], actual: dict[str, Any], mismatches: list[dict[str, Any]]) -> None:
    for label in REPORT_SOURCE_LABELS:
        lhs = expected.get(label)
        rhs = actual.get(label)
        if lhs == rhs:
            continue
        category = REPORT_SOURCE_CATEGORY.get(label, "report_diagnostic_drift")
        mismatches.append(
            {
                "category": category,
                "blocking": category not in NON_BLOCKING_CATEGORIES,
                "surface": f"report.source_diag.{label}",
                "expected": lhs,
                "actual": rhs,
            }
        )


def compare_experiments(baseline_exp_id: str, candidate_exp_id: str) -> dict[str, Any]:
    baseline_dir = _exp_dir(baseline_exp_id)
    candidate_dir = _exp_dir(candidate_exp_id)
    if not baseline_dir.exists():
        raise FileNotFoundError(f"baseline experiment not found: {baseline_dir}")
    if not candidate_dir.exists():
        raise FileNotFoundError(f"candidate experiment not found: {candidate_dir}")

    input_bundle = _baseline_input_bundle(baseline_dir)
    expected = _expected_bundle(baseline_dir)
    actual = _candidate_bundle(candidate_dir)
    mismatches: list[dict[str, Any]] = []

    if expected["run_config"] != actual["run_config"]:
        _record_mismatches(
            mismatches,
            category="code_drift",
            surface_prefix="run_config",
            expected=expected["run_config"],
            actual=actual["run_config"],
        )

    if expected["perf"] != actual["perf"]:
        category = "database_universe_data_drift" if expected["run_meta_universe"] != actual["run_meta_universe"] else "code_drift"
        _record_mismatches(
            mismatches,
            category=category,
            surface_prefix="perf",
            expected=expected["perf"],
            actual=actual["perf"],
        )

    if expected["run_meta_core"] != actual["run_meta_core"]:
        _record_mismatches(
            mismatches,
            category="code_drift",
            surface_prefix="run_meta",
            expected=expected["run_meta_core"],
            actual=actual["run_meta_core"],
        )

    if expected["run_meta_universe"] != actual["run_meta_universe"]:
        _record_mismatches(
            mismatches,
            category="database_universe_data_drift",
            surface_prefix="run_meta.universe",
            expected=expected["run_meta_universe"],
            actual=actual["run_meta_universe"],
        )

    if expected["resolution"] != actual["resolution"]:
        _record_mismatches(
            mismatches,
            category="saved_config_resolution_drift",
            surface_prefix="resolution",
            expected=expected["resolution"],
            actual=actual["resolution"],
        )

    if expected["nav"] != actual["nav"]:
        category = "database_universe_data_drift" if expected["run_meta_universe"] != actual["run_meta_universe"] else "code_drift"
        _record_mismatches(
            mismatches,
            category=category,
            surface_prefix="nav",
            expected=expected["nav"],
            actual=actual["nav"],
        )

    if expected["trades"] != actual["trades"]:
        category = "database_universe_data_drift" if expected["run_meta_universe"] != actual["run_meta_universe"] else "code_drift"
        _record_mismatches(
            mismatches,
            category=category,
            surface_prefix="portfolio_trades",
            expected=expected["trades"],
            actual=actual["trades"],
        )

    expected_report = expected["report"]
    actual_report = actual["report"]
    expected_report_summary = {
        "overview": expected_report.get("overview"),
        "kpis": expected_report.get("kpis"),
        "appendix_trade_total": expected_report.get("appendix_trade_total"),
    }
    actual_report_summary = {
        "overview": actual_report.get("overview"),
        "kpis": actual_report.get("kpis"),
        "appendix_trade_total": actual_report.get("appendix_trade_total"),
    }
    if expected_report_summary != actual_report_summary:
        _record_mismatches(
            mismatches,
            category="report_rendering_drift",
            surface_prefix="report",
            expected=expected_report_summary,
            actual=actual_report_summary,
        )
    _compare_report_source_diag(
        expected=expected_report.get("source_diag") if isinstance(expected_report.get("source_diag"), dict) else {},
        actual=actual_report.get("source_diag") if isinstance(actual_report.get("source_diag"), dict) else {},
        mismatches=mismatches,
    )

    blocking = [m for m in mismatches if m.get("blocking")]
    warnings = [m for m in mismatches if not m.get("blocking")]
    status = "FAIL" if blocking else ("WARN" if warnings else "PASS")
    return {
        "status": status,
        "baseline_exp_id": baseline_exp_id,
        "candidate_exp_id": candidate_exp_id,
        "baseline_input_bundle": input_bundle,
        "mismatch_counts": {
            "blocking": len(blocking),
            "warning": len(warnings),
            "total": len(mismatches),
        },
        "mismatches": mismatches,
        "blocking_mismatches": blocking,
        "warning_mismatches": warnings,
    }


def _build_baseline_request(exp_dir: Path) -> dict[str, Any]:
    config = _load_json(exp_dir / "config.json")
    overrides = config.get("overrides") if isinstance(config.get("overrides"), dict) else {}
    original_wb = overrides.get("original_workbench_config") if isinstance(overrides.get("original_workbench_config"), dict) else None
    effective_wb = overrides.get("workbench_config") if isinstance(overrides.get("workbench_config"), dict) else None
    draft = original_wb or effective_wb or {}
    draft_universe = draft.get("universe") if isinstance(draft.get("universe"), dict) else {}
    flow_script = draft.get("flow_script") if isinstance(draft.get("flow_script"), dict) else {}
    return {
        "preset": str(flow_script.get("recommended_preset") or "single"),
        "config_path": "configs/pams_cn_pg.json",
        "config_id": overrides.get("config_id"),
        "workbench_mode": overrides.get("workbench_mode") or draft.get("mode") or "experiment",
        "workbench_config": draft,
        "universe_mode": draft.get("universe_mode") or "CUSTOM",
        "industries": draft.get("industries") or [],
        "price_adj": draft_universe.get("price_adj") or overrides.get("price_adj") or "hfq",
        "start_date": draft_universe.get("start"),
        "end_date": draft_universe.get("end"),
        "benchmark": draft_universe.get("benchmark"),
        "symbols": draft_universe.get("symbols"),
        "initial_capital": overrides.get("initial_capital"),
        "fast_mode": overrides.get("fast_mode"),
    }


def rerun_baseline(baseline_exp_id: str) -> str:
    _ensure_repo_on_path()
    from backend.api.endpoints._experiment_runner_api import (  # type: ignore
        BacktestV2ExperimentRequest,
        _run_backtest_v2_experiment_sync,
    )

    request_payload = _build_baseline_request(_exp_dir(baseline_exp_id))
    body = BacktestV2ExperimentRequest(**request_payload)
    result = _run_backtest_v2_experiment_sync(body)
    exp_id = str(result.get("exp_id") or "").strip()
    if not exp_id:
        raise RuntimeError("rerun did not produce exp_id")
    return exp_id


def _print_summary(result: dict[str, Any]) -> None:
    print(f"Baseline:  {result['baseline_exp_id']}")
    print(f"Candidate: {result['candidate_exp_id']}")
    print(f"Status:    {result['status']}")
    counts = result.get("mismatch_counts") or {}
    print(
        "Mismatches:"
        f" blocking={counts.get('blocking', 0)}"
        f" warning={counts.get('warning', 0)}"
        f" total={counts.get('total', 0)}"
    )
    bundle = result.get("baseline_input_bundle") if isinstance(result.get("baseline_input_bundle"), dict) else {}
    if bundle:
        print(
            "Baseline bundle:"
            f" config_id={bundle.get('saved_config_id') or '-'}"
            f" config_hash={bundle.get('saved_config_hash') or '-'}"
            f" conflict_policy={bundle.get('config_conflict_policy') or '-'}"
        )
    for mismatch in result.get("mismatches", [])[:16]:
        level = "FAIL" if mismatch.get("blocking") else "WARN"
        print(
            f"[{level}] {mismatch.get('category')}: {mismatch.get('surface')} | "
            f"expected={mismatch.get('expected')} | actual={mismatch.get('actual')}"
        )


def _write_json_output(result: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare experiments against the locked March 7 baseline.")
    parser.add_argument("--baseline-exp-id", default=BASELINE_EXP_ID)
    parser.add_argument("--candidate-exp-id", default=None)
    parser.add_argument("--rerun", action="store_true", help="rerun the locked baseline through current code before comparing")
    parser.add_argument("--output-json", default=None, help="write the comparison result to a JSON file")
    args = parser.parse_args()

    candidate_exp_id = str(args.candidate_exp_id or "").strip() or None
    if args.rerun:
        candidate_exp_id = rerun_baseline(args.baseline_exp_id)
        print(f"Rerun created candidate experiment: {candidate_exp_id}")
    if not candidate_exp_id:
        candidate_exp_id = args.baseline_exp_id

    result = compare_experiments(args.baseline_exp_id, candidate_exp_id)
    _print_summary(result)
    if args.output_json:
        _write_json_output(result, Path(args.output_json))

    if result["status"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
