from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.research.mainline_factor_surface_common import outputs_root
from backend.research.study_definition import StudyDefinition

REQUIRED_SOURCE_FILES = (
    "manifest.json",
    "b0_shadow_daily_plan.csv",
    "b01_shadow_daily_plan.csv",
    "b01_shadow_raw_triggers.csv",
    "b01_shadow_filtered.csv",
)

CORE_TECH_RE = re.compile(r"(?:\u7b97\u529b|CPO/\u5149\u6a21\u5757|\u5b58\u50a8|\u534a\u5bfc\u4f53)")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_repo_path(path_text: str) -> Path:
    raw = Path(str(path_text or "").strip())
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def _study_root(study: StudyDefinition) -> Path:
    parts = [part for part in str(study.study_id or "").replace("\\", "/").split("/") if part]
    return outputs_root().joinpath(*parts).resolve()


def _study_item_dir(study: StudyDefinition, *, window_key: str, variant_name: str) -> Path:
    return (_study_root(study) / str(window_key) / str(variant_name)).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    except FileNotFoundError:
        return pd.DataFrame()


def _date_filtered(df: pd.DataFrame, *, start: str, end: str) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return pd.DataFrame(columns=list(df.columns))
    out = df.copy()
    out["_date"] = pd.to_datetime(out["date"], errors="coerce")
    mask = (out["_date"] >= pd.to_datetime(start)) & (out["_date"] <= pd.to_datetime(end))
    return out.loc[mask].drop(columns=["_date"], errors="ignore").copy()


def _num_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def _sum(df: pd.DataFrame, column: str) -> float:
    values = _num_series(df, column)
    return float(values.fillna(0.0).sum()) if not values.empty else 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _join_examples(df: pd.DataFrame, *, symbol_col: str, name_col: str, limit: int = 8) -> str:
    if df.empty or symbol_col not in df.columns:
        return ""
    rows: list[str] = []
    seen: set[str] = set()
    for row in df[[symbol_col, name_col] if name_col in df.columns else [symbol_col]].itertuples(index=False):
        symbol = str(getattr(row, symbol_col) if hasattr(row, symbol_col) else row[0]).strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        name = ""
        if name_col in df.columns:
            try:
                name = str(getattr(row, name_col)).strip()
            except Exception:
                name = ""
        rows.append((symbol + (" " + name if name and name.lower() != "nan" else "")).strip())
        if len(rows) >= limit:
            break
    return "; ".join(rows)


def _top_values(series: pd.Series, *, limit: int = 8) -> str:
    if series.empty:
        return ""
    counts = series.fillna("").astype(str)
    counts = counts[counts.ne("")]
    if counts.empty:
        return ""
    return "; ".join(str(item) for item in counts.value_counts().head(limit).index.tolist())


def _filter_counts(filtered: pd.DataFrame) -> dict[str, int]:
    if filtered.empty:
        return {}
    counts: dict[str, int] = {}
    for column in sorted(col for col in filtered.columns if str(col).startswith("filter_")):
        total = _safe_int(_num_series(filtered, column).fillna(0).sum())
        if total:
            counts[column.replace("filter_", "")] = total
    return counts


def _theme_summary(plan: pd.DataFrame) -> pd.DataFrame:
    if plan.empty or "theme" not in plan.columns:
        return pd.DataFrame()
    work = plan.copy()
    return (
        work.groupby("theme", dropna=False)
        .agg(
            daily_plan_rows=("date", "size"),
            days=("date", "nunique"),
            unique_buy_symbols=("buy_symbol", "nunique"),
            unique_sell_symbols=("sell_symbol", "nunique"),
            potential_replace_amount_capped=("potential_replace_amount_capped", "sum"),
        )
        .reset_index()
        .sort_values(["daily_plan_rows", "potential_replace_amount_capped"], ascending=[False, False])
    )


def _source_audit(source_dir: Path, runner_params: dict[str, Any]) -> dict[str, Any]:
    missing = [name for name in REQUIRED_SOURCE_FILES if not (source_dir / name).exists()]
    manifest = _read_json(source_dir / "manifest.json")
    return sanitize_json(
        {
            "source_artifact_dir": str(source_dir),
            "required_files": list(REQUIRED_SOURCE_FILES),
            "missing_files": missing,
            "source_manifest": {
                "baseline_id": manifest.get("baseline_id"),
                "combo_baseline_dir": manifest.get("combo_baseline_dir"),
                "stock_component_exp_id": manifest.get("stock_component_exp_id"),
                "etf_component_exp_id": manifest.get("etf_component_exp_id"),
                "scope": manifest.get("scope"),
            },
            "source_coverage_start": str(runner_params.get("source_coverage_start") or ""),
            "source_coverage_end": str(runner_params.get("source_coverage_end") or ""),
        }
    )


def _coverage_complete(*, start: str, end: str, audit: dict[str, Any]) -> bool:
    source_start = str(audit.get("source_coverage_start") or "").strip()
    source_end = str(audit.get("source_coverage_end") or "").strip()
    if not source_start or not source_end:
        return False
    return pd.to_datetime(source_start) <= pd.to_datetime(start) and pd.to_datetime(source_end) >= pd.to_datetime(end)


def _window_summary(
    *,
    start: str,
    end: str,
    b0_plan: pd.DataFrame,
    b01_plan: pd.DataFrame,
    b01_raw: pd.DataFrame,
    b01_filtered: pd.DataFrame,
    audit: dict[str, Any],
) -> dict[str, Any]:
    b0_w = _date_filtered(b0_plan, start=start, end=end)
    plan_w = _date_filtered(b01_plan, start=start, end=end)
    raw_w = _date_filtered(b01_raw, start=start, end=end)
    filtered_w = _date_filtered(b01_filtered, start=start, end=end)
    sell_theme_tags = plan_w["sell_theme_tags"].fillna("").astype(str) if "sell_theme_tags" in plan_w.columns else pd.Series(dtype=str)
    core_tech_sell_rows = int(sell_theme_tags.str.contains(CORE_TECH_RE, regex=True).sum()) if not sell_theme_tags.empty else 0
    return sanitize_json(
        {
            "coverage_complete": _coverage_complete(start=start, end=end, audit=audit),
            "b0_daily_plan_rows": int(len(b0_w)),
            "b01_daily_plan_rows": int(len(plan_w)),
            "b01_daily_plan_days": int(plan_w["date"].nunique()) if "date" in plan_w.columns and not plan_w.empty else 0,
            "reduction_vs_b0_rows": int(len(b0_w) - len(plan_w)),
            "raw_trigger_rows": int(len(raw_w)),
            "pair_found_rows": int(raw_w["shadow_status"].astype(str).eq("PAIR_FOUND").sum()) if "shadow_status" in raw_w.columns else 0,
            "filtered_rows": int(len(filtered_w)),
            "unique_buy_symbols": int(plan_w["buy_symbol"].nunique()) if "buy_symbol" in plan_w.columns and not plan_w.empty else 0,
            "unique_sell_symbols": int(plan_w["sell_symbol"].nunique()) if "sell_symbol" in plan_w.columns and not plan_w.empty else 0,
            "potential_replace_amount_capped": _sum(plan_w, "potential_replace_amount_capped"),
            "top_buy_themes": _top_values(plan_w["theme"]) if "theme" in plan_w.columns else "",
            "buy_examples": _join_examples(plan_w, symbol_col="buy_symbol", name_col="buy_name"),
            "sell_examples": _join_examples(plan_w, symbol_col="sell_symbol", name_col="sell_name"),
            "core_tech_sell_rows": core_tech_sell_rows,
            "filter_counts": _filter_counts(filtered_w),
        }
    )


def _min_rows_for_window(runner_params: dict[str, Any], window_key: str) -> int:
    raw = runner_params.get("min_b01_plan_rows")
    if isinstance(raw, dict):
        if window_key in raw:
            return _safe_int(raw.get(window_key))
        if "default" in raw:
            return _safe_int(raw.get("default"))
    return 1


def _derive_verdict(summary: dict[str, Any], *, source_audit: dict[str, Any], min_rows: int) -> dict[str, Any]:
    missing = list(source_audit.get("missing_files") or [])
    if missing:
        return {
            "status": "inconclusive",
            "reason": "source artifact files are missing: " + ", ".join(str(item) for item in missing),
            "gate_status": "UNKNOWN",
            "verdict_source": "theme_protected_replacement_runner",
        }
    if not bool(summary.get("coverage_complete")):
        return {
            "status": "inconclusive",
            "reason": "source evidence does not fully cover this window; cannot use it as a baseline upgrade gate",
            "gate_status": "UNKNOWN",
            "verdict_source": "theme_protected_replacement_runner",
        }
    if int(summary.get("core_tech_sell_rows") or 0) > 0:
        return {
            "status": "falsified",
            "reason": "protected shadow still sells core tech themes; protection contract is not acceptable",
            "gate_status": "UNKNOWN",
            "verdict_source": "theme_protected_replacement_runner",
        }
    rows = int(summary.get("b01_daily_plan_rows") or 0)
    if rows < min_rows:
        return {
            "status": "inconclusive",
            "reason": f"protected shadow has only {rows} rows, below the review threshold {min_rows}",
            "gate_status": "UNKNOWN",
            "verdict_source": "theme_protected_replacement_runner",
        }
    return {
        "status": "confirmed",
        "reason": "B0.1 protected shadow remains active and has no core-tech sell breach; confirmed only for entering B1 AB, not for baseline promotion",
        "gate_status": "UNKNOWN",
        "verdict_source": "theme_protected_replacement_runner",
    }


def _write_human_report(
    *,
    path: Path,
    study: StudyDefinition,
    item: dict[str, Any],
    summary: dict[str, Any],
    verdict: dict[str, Any],
    source_audit: dict[str, Any],
) -> None:
    lines = [
        f"# {study.title}",
        "",
        "## 结论",
        "",
        f"- verdict: {verdict.get('status')}",
        f"- reason: {verdict.get('reason')}",
        "- 口径：research-only shadow，不成交、不重算 NAV、不代表真实收益改善。",
        "",
        "## 窗口摘要",
        "",
        f"- window: {item.get('window_key')} ({item.get('request_payload', {}).get('start_date')} 至 {item.get('request_payload', {}).get('end_date')})",
        f"- coverage_complete: {summary.get('coverage_complete')}",
        f"- B0 daily plan rows: {summary.get('b0_daily_plan_rows')}",
        f"- B0.1 daily plan rows: {summary.get('b01_daily_plan_rows')}",
        f"- reduction vs B0 rows: {summary.get('reduction_vs_b0_rows')}",
        f"- trigger rows / pair found rows: {summary.get('raw_trigger_rows')} / {summary.get('pair_found_rows')}",
        f"- unique buy/sell symbols: {summary.get('unique_buy_symbols')} / {summary.get('unique_sell_symbols')}",
        f"- capped potential replace amount: {summary.get('potential_replace_amount_capped')}",
        f"- top buy themes: {summary.get('top_buy_themes')}",
        f"- buy examples: {summary.get('buy_examples')}",
        f"- sell examples: {summary.get('sell_examples')}",
        "",
        "## 保护审计",
        "",
        f"- core tech sell rows: {summary.get('core_tech_sell_rows')}",
        f"- filter counts: {json.dumps(summary.get('filter_counts') or {}, ensure_ascii=False)}",
        "",
        "## 来源链路",
        "",
        f"- source artifact dir: {source_audit.get('source_artifact_dir')}",
        f"- baseline id: {(source_audit.get('source_manifest') or {}).get('baseline_id')}",
        f"- stock component exp id: {(source_audit.get('source_manifest') or {}).get('stock_component_exp_id')}",
        f"- ETF component exp id: {(source_audit.get('source_manifest') or {}).get('etf_component_exp_id')}",
        f"- missing files: {', '.join(source_audit.get('missing_files') or []) or 'none'}",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_matrix_summary(study: StudyDefinition, runs: list[dict[str, Any]]) -> dict[str, str]:
    root = _study_root(study)
    machine_dir = root / "machine"
    human_dir = root / "human"
    machine_dir.mkdir(parents=True, exist_ok=True)
    human_dir.mkdir(parents=True, exist_ok=True)
    machine_path = machine_dir / "theme_protected_replacement_matrix.json"
    human_path = human_dir / "theme_protected_replacement_matrix.md"
    machine_path.write_text(
        json.dumps(sanitize_json({"study_id": study.study_id, "runs": runs}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        f"# {study.title}",
        "",
        "| window | variant | verdict | coverage | B0 rows | B0.1 rows | core-tech sells | amount cap |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in runs:
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        verdict = row.get("verdict") if isinstance(row.get("verdict"), dict) else {}
        lines.append(
            "| {window} | {variant} | {verdict} | {coverage} | {b0} | {b01} | {core} | {amount} |".format(
                window=row.get("window_key") or "",
                variant=row.get("variant_name") or "",
                verdict=verdict.get("status") or "",
                coverage=summary.get("coverage_complete"),
                b0=summary.get("b0_daily_plan_rows"),
                b01=summary.get("b01_daily_plan_rows"),
                core=summary.get("core_tech_sell_rows"),
                amount=summary.get("potential_replace_amount_capped"),
            )
        )
    human_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"machine_summary": str(machine_path), "human_summary": str(human_path)}


def run_theme_protected_replacement_study(
    *,
    study: StudyDefinition,
    plan: list[dict[str, Any]],
    write_dual_output: bool = True,
    append_to_baseline: bool = False,
) -> dict[str, Any]:
    del append_to_baseline
    runs: list[dict[str, Any]] = []
    for item in plan:
        request_payload = dict(item.get("request_payload") or {})
        runner_params = request_payload.get("runner_params") if isinstance(request_payload.get("runner_params"), dict) else {}
        source_dir = _resolve_repo_path(str(runner_params.get("input_artifact_dir") or ""))
        source_audit = _source_audit(source_dir, runner_params)
        b0_plan = _read_csv(source_dir / "b0_shadow_daily_plan.csv")
        b01_plan = _read_csv(source_dir / "b01_shadow_daily_plan.csv")
        b01_raw = _read_csv(source_dir / "b01_shadow_raw_triggers.csv")
        b01_filtered = _read_csv(source_dir / "b01_shadow_filtered.csv")

        window_key = str(item.get("window_key") or "")
        variant_name = str(item.get("variant_name") or "")
        start = str(request_payload.get("start_date") or "")
        end = str(request_payload.get("end_date") or "")
        item_dir = _study_item_dir(study, window_key=window_key, variant_name=variant_name)
        machine_dir = item_dir / "machine"
        human_dir = item_dir / "human"
        machine_dir.mkdir(parents=True, exist_ok=True)
        human_dir.mkdir(parents=True, exist_ok=True)

        summary = _window_summary(
            start=start,
            end=end,
            b0_plan=b0_plan,
            b01_plan=b01_plan,
            b01_raw=b01_raw,
            b01_filtered=b01_filtered,
            audit=source_audit,
        )
        min_rows = _min_rows_for_window(runner_params, window_key)
        verdict = _derive_verdict(summary, source_audit=source_audit, min_rows=min_rows)
        plan_w = _date_filtered(b01_plan, start=start, end=end)
        raw_w = _date_filtered(b01_raw, start=start, end=end)
        filtered_w = _date_filtered(b01_filtered, start=start, end=end)
        theme_w = _theme_summary(plan_w)

        plan_w.to_csv(machine_dir / "b01_daily_plan_window.csv", index=False, encoding="utf-8-sig")
        raw_w.to_csv(machine_dir / "b01_raw_triggers_window.csv", index=False, encoding="utf-8-sig")
        filtered_w.to_csv(machine_dir / "b01_filtered_window.csv", index=False, encoding="utf-8-sig")
        theme_w.to_csv(machine_dir / "b01_theme_summary_window.csv", index=False, encoding="utf-8-sig")

        machine_payload = sanitize_json(
            {
                "study_id": study.study_id,
                "title": study.title,
                "window_key": window_key,
                "variant_name": variant_name,
                "generated_at": datetime.now().isoformat(),
                "research_only": True,
                "not_nav_backtest": True,
                "baseline_id": study.baseline_id,
                "summary": summary,
                "source_audit": source_audit,
                "verdict": verdict,
            }
        )
        (machine_dir / "summary.json").write_text(
            json.dumps(machine_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _write_human_report(
            path=human_dir / "summary.md",
            study=study,
            item=item,
            summary=summary,
            verdict=verdict,
            source_audit=source_audit,
        )

        run_row = sanitize_json(
            {
                "study_id": study.study_id,
                "window_key": window_key,
                "window_role": str(item.get("window_role") or ""),
                "variant_name": variant_name,
                "exp_id": "",
                "results_dir": str(item_dir),
                "research_only": True,
                "not_nav_backtest": True,
                "baseline_outputs": {},
                "summary": summary,
                "source_audit": source_audit,
                "verdict": verdict,
                "machine_outputs": {
                    "summary": str(machine_dir / "summary.json"),
                    "daily_plan": str(machine_dir / "b01_daily_plan_window.csv"),
                    "raw_triggers": str(machine_dir / "b01_raw_triggers_window.csv"),
                    "filtered": str(machine_dir / "b01_filtered_window.csv"),
                    "theme_summary": str(machine_dir / "b01_theme_summary_window.csv"),
                }
                if write_dual_output
                else {},
                "human_outputs": {"summary": str(human_dir / "summary.md")} if write_dual_output else {},
            }
        )
        runs.append(run_row)
    summary_refs = _write_matrix_summary(study, runs)
    return sanitize_json(
        {
            "study_id": study.study_id,
            "status": "OK",
            "research_only": True,
            "not_nav_backtest": True,
            "runs": runs,
            "summary_outputs": summary_refs,
        }
    )
