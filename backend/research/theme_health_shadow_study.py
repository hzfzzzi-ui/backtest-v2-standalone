from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.research.mainline_factor_surface_common import outputs_root
from backend.research.study_definition import StudyDefinition

REQUIRED_SOURCE_FILES = (
    "manifest.json",
    "long_daily_theme_alignment.csv",
)

DEFAULT_THRESHOLDS = {
    "proxy_ret20_weak_threshold": 0.0,
    "proxy_ret60_weak_threshold": 0.0,
    "rank_pct_weak_threshold": 0.60,
    "candidate_collapse_days": 10,
    "watch_min_flags": 2,
    "confirmed_min_flags": 3,
    "min_proxy_coverage_ratio": 0.35,
}


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


def _num_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def _bool_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(False, index=df.index)
    raw = df[column]
    if raw.dtype == bool:
        return raw.fillna(False)
    return raw.fillna("").astype(str).str.lower().isin({"true", "1", "yes"})


def _source_audit(source_dir: Path) -> dict[str, Any]:
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
        }
    )


def _thresholds(runner_params: dict[str, Any]) -> dict[str, float | int]:
    out: dict[str, float | int] = dict(DEFAULT_THRESHOLDS)
    custom = runner_params.get("thresholds") if isinstance(runner_params.get("thresholds"), dict) else {}
    for key in out:
        if key not in custom:
            continue
        try:
            if isinstance(out[key], int):
                out[key] = int(custom[key])
            else:
                out[key] = float(custom[key])
        except Exception:
            continue
    return out


def _date_filtered(df: pd.DataFrame, *, start: str, end: str) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return pd.DataFrame(columns=list(df.columns))
    out = df.copy()
    out["_date"] = pd.to_datetime(out["date"], errors="coerce")
    mask = (out["_date"] >= pd.to_datetime(start)) & (out["_date"] <= pd.to_datetime(end))
    return out.loc[mask].drop(columns=["_date"], errors="ignore").copy()


def _add_daily_proxy_rank(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["proxy_available_bool"] = _bool_series(out, "proxy_available")
    out["proxy_max_ret20_num"] = _num_series(out, "proxy_max_ret20")
    out["proxy_max_ret60_num"] = _num_series(out, "proxy_max_ret60")
    available = out["proxy_available_bool"] & out["proxy_max_ret20_num"].notna()
    out["proxy_rank_pct"] = pd.NA
    if not available.any():
        return out
    ranked = out.loc[available, ["date", "proxy_max_ret20_num"]].copy()
    ranked["_rank"] = ranked.groupby("date")["proxy_max_ret20_num"].rank(method="min", ascending=False)
    ranked["_count"] = ranked.groupby("date")["proxy_max_ret20_num"].transform("count")
    denom = (ranked["_count"] - 1).replace(0, 1)
    out.loc[ranked.index, "proxy_rank_pct"] = ((ranked["_rank"] - 1) / denom).astype(float)
    return out


def compute_theme_health_daily(alignment: pd.DataFrame, thresholds: dict[str, float | int]) -> pd.DataFrame:
    if alignment.empty:
        return pd.DataFrame()
    work = _add_daily_proxy_rank(alignment)
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["stock_theme_exposure_pct_num"] = _num_series(work, "stock_theme_exposure_pct").fillna(0.0)
    work["stock_theme_position_count_num"] = _num_series(work, "stock_theme_position_count").fillna(0.0)
    work["candidate_rows_num"] = _num_series(work, "candidate_rows").fillna(0.0)
    work["selected_rows_num"] = _num_series(work, "selected_rows").fillna(0.0)
    work["held_theme"] = (work["stock_theme_exposure_pct_num"] > 0) | (work["stock_theme_position_count_num"] > 0)
    work = work.loc[work["held_theme"]].copy()
    if work.empty:
        return work

    work.sort_values(["theme", "date"], inplace=True)
    visible = (work["candidate_rows_num"] + work["selected_rows_num"]).gt(0).astype(int)
    collapse_days = max(int(thresholds["candidate_collapse_days"]), 1)
    work["candidate_visible_trailing_days"] = (
        visible.groupby(work["theme"]).rolling(collapse_days, min_periods=1).sum().reset_index(level=0, drop=True)
    )
    work["flag_ret20_weak"] = work["proxy_available_bool"] & (
        work["proxy_max_ret20_num"] <= float(thresholds["proxy_ret20_weak_threshold"])
    )
    work["flag_ret60_weak"] = work["proxy_available_bool"] & (
        work["proxy_max_ret60_num"] <= float(thresholds["proxy_ret60_weak_threshold"])
    )
    work["flag_rank_weak"] = work["proxy_available_bool"] & (
        pd.to_numeric(work["proxy_rank_pct"], errors="coerce") >= float(thresholds["rank_pct_weak_threshold"])
    )
    work["flag_candidate_collapse"] = work["candidate_visible_trailing_days"].fillna(0).le(0)
    work["flag_held_proxy_weak"] = _bool_series(work, "stock_overweight_proxy_weak") | work["flag_ret20_weak"]
    flag_cols = [
        "flag_ret20_weak",
        "flag_ret60_weak",
        "flag_rank_weak",
        "flag_candidate_collapse",
        "flag_held_proxy_weak",
    ]
    work["weak_flag_count"] = work[flag_cols].fillna(False).astype(int).sum(axis=1)
    confirmed_min = int(thresholds["confirmed_min_flags"])
    watch_min = int(thresholds["watch_min_flags"])
    work["theme_health_label"] = "healthy"
    work.loc[work["weak_flag_count"] >= watch_min, "theme_health_label"] = "watch"
    work.loc[work["weak_flag_count"] >= confirmed_min, "theme_health_label"] = "confirmed_weak"
    work["theme_health_score"] = (100 - work["weak_flag_count"] * 20).clip(lower=0, upper=100)
    work["date"] = work["date"].dt.strftime("%Y-%m-%d")
    ordered = [
        "date",
        "theme",
        "theme_health_label",
        "theme_health_score",
        "weak_flag_count",
        "stock_theme_exposure_pct",
        "stock_theme_position_count",
        "held_examples",
        "proxy_available_bool",
        "theme_proxy",
        "proxy_max_ret20",
        "proxy_max_ret60",
        "proxy_max_ret5",
        "proxy_rank_pct",
        "candidate_rows",
        "selected_rows",
        "cash_blocked_rows",
        "candidate_visible_trailing_days",
        "candidate_examples",
        *flag_cols,
    ]
    cols = [col for col in ordered if col in work.columns]
    return work[cols].copy()


def _first_non_empty(series: pd.Series, limit: int = 160) -> str:
    for value in series.fillna("").astype(str):
        text = value.strip()
        if text:
            return text[:limit]
    return ""


def _theme_summary(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    work = daily.copy()
    work["is_watch"] = work["theme_health_label"].astype(str).isin(["watch", "confirmed_weak"])
    work["is_confirmed"] = work["theme_health_label"].astype(str).eq("confirmed_weak")
    work["proxy_available_int"] = _bool_series(work, "proxy_available_bool").astype(int)
    work["stock_theme_exposure_pct_num"] = _num_series(work, "stock_theme_exposure_pct").fillna(0.0)
    grouped = work.groupby("theme", dropna=False)
    out = grouped.agg(
        held_days=("date", "size"),
        watch_days=("is_watch", "sum"),
        confirmed_weak_days=("is_confirmed", "sum"),
        proxy_available_days=("proxy_available_int", "sum"),
        avg_exposure_pct=("stock_theme_exposure_pct_num", "mean"),
        max_exposure_pct=("stock_theme_exposure_pct_num", "max"),
        avg_health_score=("theme_health_score", "mean"),
        min_health_score=("theme_health_score", "min"),
        ret20_weak_days=("flag_ret20_weak", "sum"),
        ret60_weak_days=("flag_ret60_weak", "sum"),
        rank_weak_days=("flag_rank_weak", "sum"),
        candidate_collapse_days=("flag_candidate_collapse", "sum"),
    ).reset_index()
    confirmed = work.loc[work["is_confirmed"]].groupby("theme")["date"].agg(["min", "max"]).reset_index()
    confirmed.rename(columns={"min": "first_confirmed_weak_date", "max": "last_confirmed_weak_date"}, inplace=True)
    out = out.merge(confirmed, how="left", on="theme")
    examples = grouped.agg(
        held_examples=("held_examples", _first_non_empty),
        candidate_examples=("candidate_examples", _first_non_empty),
    ).reset_index()
    out = out.merge(examples, how="left", on="theme")
    out["proxy_coverage_ratio"] = out["proxy_available_days"] / out["held_days"].replace(0, pd.NA)
    return out.sort_values(["confirmed_weak_days", "watch_days", "held_days"], ascending=[False, False, False])


def _window_summary(daily: pd.DataFrame, theme_summary: pd.DataFrame) -> dict[str, Any]:
    if daily.empty:
        return {
            "held_theme_days": 0,
            "watch_days": 0,
            "confirmed_weak_days": 0,
            "proxy_coverage_ratio": 0.0,
            "themes_with_confirmed_weak": 0,
            "top_confirmed_weak_themes": "",
        }
    watch = daily["theme_health_label"].astype(str).isin(["watch", "confirmed_weak"])
    confirmed = daily["theme_health_label"].astype(str).eq("confirmed_weak")
    proxy_available = _bool_series(daily, "proxy_available_bool")
    top = ""
    if not theme_summary.empty:
        top_rows = theme_summary.loc[pd.to_numeric(theme_summary["confirmed_weak_days"], errors="coerce").fillna(0) > 0]
        top = "; ".join(
            f"{row.theme}:{int(row.confirmed_weak_days)}"
            for row in top_rows.head(8).itertuples(index=False)
        )
    return sanitize_json(
        {
            "held_theme_days": int(len(daily)),
            "watch_days": int(watch.sum()),
            "confirmed_weak_days": int(confirmed.sum()),
            "watch_day_ratio": float(watch.sum() / len(daily)),
            "confirmed_weak_day_ratio": float(confirmed.sum() / len(daily)),
            "proxy_available_days": int(proxy_available.sum()),
            "proxy_coverage_ratio": float(proxy_available.sum() / len(daily)),
            "themes_held": int(daily["theme"].nunique()) if "theme" in daily.columns else 0,
            "themes_with_confirmed_weak": int(
                (pd.to_numeric(theme_summary.get("confirmed_weak_days"), errors="coerce").fillna(0) > 0).sum()
            )
            if not theme_summary.empty
            else 0,
            "top_confirmed_weak_themes": top,
        }
    )


def _derive_verdict(
    summary: dict[str, Any],
    *,
    source_audit: dict[str, Any],
    thresholds: dict[str, float | int],
) -> dict[str, Any]:
    missing = list(source_audit.get("missing_files") or [])
    if missing:
        return {
            "status": "inconclusive",
            "reason": "source artifact files are missing: " + ", ".join(str(item) for item in missing),
            "gate_status": "UNKNOWN",
            "verdict_source": "theme_health_shadow_runner",
        }
    if int(summary.get("held_theme_days") or 0) == 0:
        return {
            "status": "inconclusive",
            "reason": "no held stock theme rows in this window",
            "gate_status": "UNKNOWN",
            "verdict_source": "theme_health_shadow_runner",
        }
    coverage = float(summary.get("proxy_coverage_ratio") or 0.0)
    if coverage < float(thresholds["min_proxy_coverage_ratio"]):
        return {
            "status": "inconclusive",
            "reason": f"ETF theme proxy coverage is only {coverage:.2%}; diagnostic only, not enough for an AB gate",
            "gate_status": "UNKNOWN",
            "verdict_source": "theme_health_shadow_runner",
        }
    confirmed = int(summary.get("confirmed_weak_days") or 0)
    if confirmed > 0:
        return {
            "status": "confirmed",
            "reason": f"C1 found {confirmed} confirmed weak held-theme days; evidence is suitable for designing a later runtime AB, not for baseline promotion",
            "gate_status": "UNKNOWN",
            "verdict_source": "theme_health_shadow_runner",
        }
    return {
        "status": "inconclusive",
        "reason": "C1 did not find confirmed weak held-theme days under current thresholds",
        "gate_status": "UNKNOWN",
        "verdict_source": "theme_health_shadow_runner",
    }


def _write_human_report(
    *,
    path: Path,
    study: StudyDefinition,
    item: dict[str, Any],
    summary: dict[str, Any],
    verdict: dict[str, Any],
    source_audit: dict[str, Any],
    thresholds: dict[str, float | int],
    theme_summary: pd.DataFrame,
) -> None:
    lines = [
        f"# {study.title}",
        "",
        "## Conclusion",
        "",
        f"- verdict: {verdict.get('status')}",
        f"- reason: {verdict.get('reason')}",
        "- scope: research-only theme health shadow; no trades, no NAV recomputation, no baseline change.",
        "",
        "## Window",
        "",
        f"- window: {item.get('window_key')} ({item.get('request_payload', {}).get('start_date')} to {item.get('request_payload', {}).get('end_date')})",
        f"- held theme days: {summary.get('held_theme_days')}",
        f"- watch days: {summary.get('watch_days')} ({summary.get('watch_day_ratio')})",
        f"- confirmed weak days: {summary.get('confirmed_weak_days')} ({summary.get('confirmed_weak_day_ratio')})",
        f"- proxy coverage ratio: {summary.get('proxy_coverage_ratio')}",
        f"- themes held / themes with confirmed weak: {summary.get('themes_held')} / {summary.get('themes_with_confirmed_weak')}",
        f"- top confirmed weak themes: {summary.get('top_confirmed_weak_themes')}",
        "",
        "## Thresholds",
        "",
        "```json",
        json.dumps(thresholds, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Top Theme Summary",
        "",
        "| theme | held_days | watch_days | confirmed_weak_days | proxy_coverage | avg_exposure | first_confirmed | last_confirmed |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    if not theme_summary.empty:
        for row in theme_summary.head(12).itertuples(index=False):
            lines.append(
                "| {theme} | {held} | {watch} | {confirmed} | {coverage} | {exposure} | {first} | {last} |".format(
                    theme=getattr(row, "theme", ""),
                    held=getattr(row, "held_days", ""),
                    watch=getattr(row, "watch_days", ""),
                    confirmed=getattr(row, "confirmed_weak_days", ""),
                    coverage=getattr(row, "proxy_coverage_ratio", ""),
                    exposure=getattr(row, "avg_exposure_pct", ""),
                    first=getattr(row, "first_confirmed_weak_date", ""),
                    last=getattr(row, "last_confirmed_weak_date", ""),
                )
            )
    lines.extend(
        [
            "",
            "## Source Lineage",
            "",
            f"- source artifact dir: {source_audit.get('source_artifact_dir')}",
            f"- baseline id: {(source_audit.get('source_manifest') or {}).get('baseline_id')}",
            f"- stock component exp id: {(source_audit.get('source_manifest') or {}).get('stock_component_exp_id')}",
            f"- ETF component exp id: {(source_audit.get('source_manifest') or {}).get('etf_component_exp_id')}",
            f"- missing files: {', '.join(source_audit.get('missing_files') or []) or 'none'}",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_matrix_summary(study: StudyDefinition, runs: list[dict[str, Any]]) -> dict[str, str]:
    root = _study_root(study)
    machine_dir = root / "machine"
    human_dir = root / "human"
    machine_dir.mkdir(parents=True, exist_ok=True)
    human_dir.mkdir(parents=True, exist_ok=True)
    machine_path = machine_dir / "theme_health_shadow_matrix.json"
    human_path = human_dir / "theme_health_shadow_matrix.md"
    machine_path.write_text(
        json.dumps(sanitize_json({"study_id": study.study_id, "runs": runs}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        f"# {study.title}",
        "",
        "| window | variant | verdict | held days | watch days | confirmed weak days | proxy coverage | top weak themes |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in runs:
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        verdict = row.get("verdict") if isinstance(row.get("verdict"), dict) else {}
        lines.append(
            "| {window} | {variant} | {verdict} | {held} | {watch} | {confirmed} | {coverage} | {themes} |".format(
                window=row.get("window_key") or "",
                variant=row.get("variant_name") or "",
                verdict=verdict.get("status") or "",
                held=summary.get("held_theme_days"),
                watch=summary.get("watch_days"),
                confirmed=summary.get("confirmed_weak_days"),
                coverage=summary.get("proxy_coverage_ratio"),
                themes=summary.get("top_confirmed_weak_themes") or "",
            )
        )
    human_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"machine_summary": str(machine_path), "human_summary": str(human_path)}


def run_theme_health_shadow_study(
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
        source_audit = _source_audit(source_dir)
        thresholds = _thresholds(runner_params)
        alignment = _read_csv(source_dir / "long_daily_theme_alignment.csv")

        window_key = str(item.get("window_key") or "")
        variant_name = str(item.get("variant_name") or "")
        start = str(request_payload.get("start_date") or "")
        end = str(request_payload.get("end_date") or "")
        item_dir = _study_item_dir(study, window_key=window_key, variant_name=variant_name)
        machine_dir = item_dir / "machine"
        human_dir = item_dir / "human"
        machine_dir.mkdir(parents=True, exist_ok=True)
        human_dir.mkdir(parents=True, exist_ok=True)

        window_alignment = _date_filtered(alignment, start=start, end=end)
        daily = compute_theme_health_daily(window_alignment, thresholds)
        theme_summary = _theme_summary(daily)
        summary = _window_summary(daily, theme_summary)
        verdict = _derive_verdict(summary, source_audit=source_audit, thresholds=thresholds)

        daily_path = machine_dir / "theme_health_daily.csv"
        theme_summary_path = machine_dir / "theme_health_by_theme.csv"
        window_summary_path = machine_dir / "theme_health_window_summary.json"
        daily.to_csv(daily_path, index=False, encoding="utf-8-sig")
        theme_summary.to_csv(theme_summary_path, index=False, encoding="utf-8-sig")
        window_summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

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
                "thresholds": thresholds,
                "summary": summary,
                "source_audit": source_audit,
                "verdict": verdict,
            }
        )
        summary_path = machine_dir / "summary.json"
        summary_path.write_text(json.dumps(machine_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        human_path = human_dir / "summary.md"
        if write_dual_output:
            _write_human_report(
                path=human_path,
                study=study,
                item=item,
                summary=summary,
                verdict=verdict,
                source_audit=source_audit,
                thresholds=thresholds,
                theme_summary=theme_summary,
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
                "thresholds": thresholds,
                "verdict": verdict,
                "machine_outputs": {
                    "summary": str(summary_path),
                    "daily": str(daily_path),
                    "theme_summary": str(theme_summary_path),
                    "window_summary": str(window_summary_path),
                },
                "human_outputs": {"summary": str(human_path)} if write_dual_output else {},
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
