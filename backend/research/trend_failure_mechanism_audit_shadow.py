from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_INPUT_ROOT = Path("outputs/studies/cn_stock_etf/trend_failure_scene_profile_shadow_v1")
DEFAULT_OUTPUT_ROOT = Path("outputs/studies/cn_stock_etf/trend_failure_mechanism_audit_shadow_v1")

NUMERIC_COLUMNS = [
    "ret5",
    "ret10",
    "ret20",
    "close_vs_ma20",
    "drawdown20",
    "forward_ret5",
    "forward_ret20",
    "mfe20",
    "mae20",
    "industry_ret20",
    "industry_ret60",
    "industry_weak_duration",
    "industry_breadth_weak",
    "industry_breadth_healthy",
]

MECHANISM_COLUMNS = [
    "high_chase_like_flag",
    "trend_exhaustion_after_flag",
    "industry_breakdown_flag",
    "market_breadth_weak_flag",
    "rotation_pressure_flag",
    "delayed_exit_like_flag",
    "healthy_state_misread_flag",
    "style_adverse_flag",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(path: str | Path) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def _as_bool(series: pd.Series) -> pd.Series:
    if series.empty:
        return pd.Series(dtype=bool)
    text = series.fillna(False).astype(str).str.lower()
    return text.isin({"true", "1", "yes"})


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(pd.NA, index=frame.index, dtype="Float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _thresholds(frame: pd.DataFrame) -> dict[str, float | None]:
    thresholds: dict[str, float | None] = {}
    for column, quantile in [
        ("ret5", 0.75),
        ("ret10", 0.75),
        ("ret20", 0.75),
        ("close_vs_ma20", 0.75),
        ("drawdown20", 0.25),
        ("industry_ret20", 0.25),
        ("industry_ret60", 0.25),
        ("industry_weak_duration", 0.75),
        ("industry_breadth_weak", 0.75),
    ]:
        values = _num(frame, column)
        value = values.quantile(quantile) if values.notna().any() else None
        thresholds[f"{column}_q{int(quantile * 100)}"] = None if pd.isna(value) else float(value)
    return thresholds


def _ge(frame: pd.DataFrame, column: str, threshold: float | None) -> pd.Series:
    if threshold is None:
        return pd.Series(False, index=frame.index)
    return _num(frame, column).ge(threshold).fillna(False)


def _le(frame: pd.DataFrame, column: str, threshold: float | None) -> pd.Series:
    if threshold is None:
        return pd.Series(False, index=frame.index)
    return _num(frame, column).le(threshold).fillna(False)


def add_mechanism_flags(frame: pd.DataFrame, thresholds: dict[str, float | None] | None = None) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    for column in NUMERIC_COLUMNS:
        out[column] = _num(out, column)
    thresholds = thresholds or _thresholds(out)

    bad_fwd20 = _as_bool(out.get("bad_fwd20_flag", pd.Series(False, index=out.index)))
    deep_mae20 = _as_bool(out.get("deep_mae20_flag", pd.Series(False, index=out.index)))
    low_mfe20 = _as_bool(out.get("low_mfe20_flag", pd.Series(False, index=out.index)))
    failure = _as_bool(out.get("failure_outcome_flag", pd.Series(False, index=out.index)))

    high_ret = _ge(out, "ret20", thresholds.get("ret20_q75")) | _ge(out, "ret10", thresholds.get("ret10_q75"))
    extended = _ge(out, "close_vs_ma20", thresholds.get("close_vs_ma20_q75"))
    out["high_chase_like_flag"] = high_ret & extended
    out["trend_exhaustion_after_flag"] = (high_ret | out["ret20"].ge(0.08).fillna(False)) & low_mfe20 & bad_fwd20

    industry_label = out.get("industry_health_label", pd.Series("", index=out.index)).fillna("").astype(str)
    out["industry_breakdown_flag"] = (
        industry_label.isin({"weak", "watch"})
        | _as_bool(out.get("industry_is_weak", pd.Series(False, index=out.index)))
        | _le(out, "industry_ret20", thresholds.get("industry_ret20_q25"))
    )

    market_label = out.get("industry_market_health_label", pd.Series("", index=out.index)).fillna("").astype(str)
    out["market_breadth_weak_flag"] = market_label.eq("industry_broad_weak") | _ge(
        out, "industry_breadth_weak", thresholds.get("industry_breadth_weak_q75")
    )

    rotation_label = out.get("rotation_pressure_label", pd.Series("", index=out.index)).fillna("").astype(str)
    out["rotation_pressure_flag"] = rotation_label.isin({"rotation_pressure", "held_broad_weak", "held_mixed"})

    position_state = out.get("position_risk_state", pd.Series("", index=out.index)).fillna("").astype(str)
    weak_position = position_state.isin({"watch_lagging", "risk_confirmed", "watch_pullback"})
    already_damaged = (
        out["close_vs_ma20"].lt(0.0).fillna(False)
        | out["ret20"].lt(0.0).fillna(False)
        | _le(out, "drawdown20", thresholds.get("drawdown20_q25"))
    )
    out["delayed_exit_like_flag"] = weak_position & already_damaged
    out["healthy_state_misread_flag"] = position_state.eq("healthy_continue") & failure & (bad_fwd20 | deep_mae20)

    style_label = out.get("style_state_label", pd.Series("", index=out.index)).fillna("").astype(str)
    out["style_adverse_flag"] = style_label.isin({"risk_off", "split_rotation", "large_cap_defense"})
    out["any_mechanism_flag"] = out[MECHANISM_COLUMNS].any(axis=1)

    reasons: list[str] = []
    for row in out[MECHANISM_COLUMNS].itertuples(index=False):
        names = [name.removesuffix("_flag") for name, value in zip(MECHANISM_COLUMNS, row) if bool(value)]
        reasons.append(";".join(names))
    out["mechanism_reasons"] = reasons
    return out


def _scene_filter(frame: pd.DataFrame, scene: dict[str, Any]) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for column in str(scene.get("dimension", "")).split("+"):
        column = column.strip()
        if not column or column not in frame.columns:
            continue
        value = scene.get(column)
        if value is None:
            value = scene.get("scene_key") if "+" not in str(scene.get("dimension", "")) else None
        if value is None:
            continue
        mask &= frame[column].fillna("").astype(str).eq(str(value))
    return mask


def _records(frame: pd.DataFrame, limit: int = 16) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return json.loads(frame.head(limit).to_json(orient="records", force_ascii=False))


def summarize_scene_mechanism(frame: pd.DataFrame, scene: dict[str, Any]) -> dict[str, Any]:
    if frame.empty:
        return {
            "scene_key": scene.get("scene_key"),
            "dimension": scene.get("dimension"),
            "rows": 0,
        }
    failure = _as_bool(frame.get("failure_outcome_flag", pd.Series(False, index=frame.index)))
    failed = frame.loc[failure].copy()

    payload: dict[str, Any] = {
        "scene_key": scene.get("scene_key"),
        "dimension": scene.get("dimension"),
        "rows": int(len(frame)),
        "unique_symbols": int(frame["symbol"].nunique()) if "symbol" in frame.columns else 0,
        "unique_days": int(frame["date"].nunique()) if "date" in frame.columns else 0,
        "failure_rows": int(len(failed)),
        "failure_outcome_ratio": float(failure.mean()) if len(frame) else 0.0,
        "avg_forward_ret20": float(_num(frame, "forward_ret20").mean()) if len(frame) else None,
        "avg_mfe20": float(_num(frame, "mfe20").mean()) if len(frame) else None,
        "avg_mae20": float(_num(frame, "mae20").mean()) if len(frame) else None,
        "avg_ret20": float(_num(frame, "ret20").mean()) if len(frame) else None,
        "avg_close_vs_ma20": float(_num(frame, "close_vs_ma20").mean()) if len(frame) else None,
        "top_industries": ",".join(frame.get("industry_name", pd.Series(dtype=str)).dropna().astype(str).value_counts().head(5).index),
        "top_years": ",".join(frame.get("year", pd.Series(dtype=str)).dropna().astype(str).value_counts().head(5).index),
    }

    for column in MECHANISM_COLUMNS:
        values = _as_bool(frame[column]) if column in frame.columns else pd.Series(False, index=frame.index)
        failed_values = _as_bool(failed[column]) if column in failed.columns else pd.Series(dtype=bool)
        name = column.removesuffix("_flag")
        payload[f"{name}_rate"] = float(values.mean()) if len(values) else 0.0
        payload[f"{name}_failure_rate"] = float(failed_values.mean()) if len(failed_values) else 0.0
    any_failed = _as_bool(failed.get("any_mechanism_flag", pd.Series(dtype=bool)))
    payload["failure_mechanism_coverage"] = float(any_failed.mean()) if len(any_failed) else 0.0

    failure_rates = {
        column.removesuffix("_flag"): payload.get(f"{column.removesuffix('_flag')}_failure_rate", 0.0)
        for column in MECHANISM_COLUMNS
    }
    payload["dominant_failure_mechanism"] = max(failure_rates, key=failure_rates.get) if failure_rates else ""
    payload["dominant_failure_mechanism_rate"] = failure_rates.get(payload["dominant_failure_mechanism"], 0.0)
    return payload


def _write_csv(path: Path, frame: pd.DataFrame) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Trend Failure Mechanism Audit Shadow V1",
        "",
        "## Scope",
        "",
        "- research_only: true",
        "- baseline_mutation: false",
        "- nav_recompute: false",
        "- source: trend_failure_scene_profile_shadow_v1",
        "",
        "## Mechanism Labels",
        "",
        "- high_chase_like: snapshot already has high recent return and high extension versus MA20.",
        "- trend_exhaustion_after: strong-looking snapshot later shows low MFE and bad 20d forward return.",
        "- industry_breakdown: own industry is weak/watch or in the lower tail of 20d industry return.",
        "- market_breadth_weak: broad industry health is weak or weak-industry breadth is high.",
        "- rotation_pressure: held book is mixed/weak or under rotation pressure.",
        "- delayed_exit_like: weak position state and already damaged price structure.",
        "- healthy_state_misread: state says healthy_continue but the following path fails.",
        "- style_adverse: market style is risk_off, split_rotation, or large_cap_defense.",
        "",
    ]
    for window in summary["windows"]:
        lines.extend([f"## {window['window_key']}", ""])
        lines.append(f"- rows: {window['rows']}")
        lines.append(f"- audited_scenes: {window['audited_scenes']}")
        lines.append("")
        lines.append("Worst audited scenes:")
        for row in window["worst_scenes"]:
            lines.append(
                "- {scene_key}: rows={rows}, fail={failure_outcome_ratio}, avg_fwd20={avg_forward_ret20}, dominant={dominant_failure_mechanism}({dominant_failure_mechanism_rate})".format(
                    **{k: row.get(k) for k in row}
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Guardrails",
            "",
            "- This is an explanatory shadow audit, not an executable rule.",
            "- Future return, MFE, and MAE are evaluation fields and must not be used in runtime decisions.",
            "- Mechanism labels can overlap; dominant mechanism is a summary, not a causal proof.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_trend_failure_mechanism_audit(
    *,
    input_root: str | Path = DEFAULT_INPUT_ROOT,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    top_single: int = 8,
    top_combo: int = 12,
) -> dict[str, Any]:
    input_dir = _resolve(input_root)
    output_dir = _resolve(output_root)
    source_summary_path = input_dir / "summary.json"
    source_summary = json.loads(source_summary_path.read_text(encoding="utf-8"))
    summary: dict[str, Any] = {
        "research_only": True,
        "baseline_mutation": False,
        "nav_recompute": False,
        "input_root": str(input_dir),
        "outputs": {},
        "windows": [],
    }

    for window in source_summary.get("windows", []):
        window_key = str(window.get("window_key"))
        detail = _read_csv(input_dir / window_key / "scene_detail.csv")
        if detail.empty:
            continue
        labeled = add_mechanism_flags(detail)
        window_dir = output_dir / window_key
        detail_path = _write_csv(window_dir / "mechanism_detail.csv", labeled)

        scenes = []
        for scene in window.get("worst_single_scenes", [])[:top_single]:
            scenes.append(scene)
        for scene in window.get("worst_combo_scenes", [])[:top_combo]:
            scenes.append(scene)

        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for scene in scenes:
            key = str(scene.get("scene_key"))
            if key in seen:
                continue
            seen.add(key)
            subset = labeled.loc[_scene_filter(labeled, scene)].copy()
            rows.append(summarize_scene_mechanism(subset, scene))

        scene_summary = pd.DataFrame(rows).sort_values(
            ["avg_forward_ret20", "rows"], ascending=[True, False], na_position="last"
        )
        scene_summary_path = _write_csv(window_dir / "scene_mechanism_summary.csv", scene_summary)
        summary["windows"].append(
            {
                "window_key": window_key,
                "rows": int(len(labeled)),
                "audited_scenes": int(len(scene_summary)),
                "detail_path": detail_path,
                "scene_mechanism_summary_path": scene_summary_path,
                "worst_scenes": _records(scene_summary, 10),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "summary.md"
    summary["outputs"] = {"summary_json": str(summary_path), "summary_md": str(report_path)}
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_render_report(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--top-single", type=int, default=8)
    parser.add_argument("--top-combo", type=int, default=12)
    args = parser.parse_args()
    summary = run_trend_failure_mechanism_audit(
        input_root=args.input_root,
        output_root=args.output_root,
        top_single=args.top_single,
        top_combo=args.top_combo,
    )
    print(json.dumps(summary["outputs"], ensure_ascii=False))


if __name__ == "__main__":
    main()
