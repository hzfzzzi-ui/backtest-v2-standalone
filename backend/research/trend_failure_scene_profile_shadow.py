from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_POSITION_ROOT = Path("outputs/studies/cn_stock_etf/position_risk_state_shadow_v1")
DEFAULT_STATE_ROOT = Path("outputs/studies/cn_stock_etf/cn_stock_style_industry_state_switch_shadow_v1")
DEFAULT_OUTPUT_ROOT = Path("outputs/studies/cn_stock_etf/trend_failure_scene_profile_shadow_v1")
DEFAULT_VARIANT = "M1_STYLE_STATE"
DEFAULT_WINDOWS = ("1626", "1217", "1226", "recent_2526", "turn_202512_202604")


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
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        frame = frame.loc[frame["date"].notna()].copy()
    return frame


def load_scene_inputs(position_root: Path, state_root: Path, *, window_key: str, variant: str) -> pd.DataFrame:
    positions = _read_csv(position_root / window_key / "position_risk_detail.csv")
    if positions.empty:
        return pd.DataFrame()
    machine = state_root / window_key / variant / "machine"
    style = _read_csv(machine / "style_state_daily.csv")
    industry = _read_csv(machine / "industry_health_daily.csv")
    rotation = _read_csv(machine / "rotation_pressure_daily.csv")
    keep_style = [c for c in ["date", "style_state_label", "avg_ret20", "avg_ret60", "worst_drawdown60"] if c in style.columns]
    keep_industry = [
        c
        for c in [
            "date",
            "industry_market_health_label",
            "healthy_industry_count",
            "weak_industry_count",
            "industry_breadth_healthy",
            "industry_breadth_weak",
        ]
        if c in industry.columns
    ]
    keep_rotation = [
        c
        for c in [
            "date",
            "held_stock_count",
            "held_weak_ratio",
            "held_healthy_ratio",
            "rotation_pressure_label",
        ]
        if c in rotation.columns
    ]
    out = positions.copy()
    if keep_style:
        out = out.merge(style[keep_style], on="date", how="left")
    if keep_industry:
        out = out.merge(industry[keep_industry], on="date", how="left")
    if keep_rotation:
        out = out.merge(rotation[keep_rotation], on="date", how="left")
    out["year"] = out["date"].astype(str).str.slice(0, 4)
    out["year_month"] = out["date"].astype(str).str.slice(0, 7)
    for col in [
        "forward_ret5",
        "forward_ret20",
        "mfe20",
        "mae20",
        "ret5",
        "ret20",
        "close_vs_ma20",
        "drawdown20",
        "industry_ret20",
        "held_weak_ratio",
        "industry_breadth_weak",
    ]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out["bad_fwd20_flag"] = out["forward_ret20"].lt(-0.05)
    out["deep_mae20_flag"] = out["mae20"].lt(-0.12)
    out["low_mfe20_flag"] = out["mfe20"].lt(0.05)
    out["failure_outcome_flag"] = out["bad_fwd20_flag"] | (out["deep_mae20_flag"] & out["low_mfe20_flag"])
    return out


def summarize_scene(frame: pd.DataFrame, group_cols: list[str], *, min_rows: int = 20) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    missing = [col for col in group_cols if col not in frame.columns]
    if missing:
        return pd.DataFrame()
    work = frame.copy()
    for col in group_cols:
        work[col] = work[col].fillna("unknown").astype(str)
    grouped = (
        work.groupby(group_cols, dropna=False)
        .agg(
            rows=("symbol", "count"),
            unique_symbols=("symbol", "nunique"),
            unique_days=("date", "nunique"),
            avg_forward_ret20=("forward_ret20", "mean"),
            median_forward_ret20=("forward_ret20", "median"),
            avg_mfe20=("mfe20", "mean"),
            avg_mae20=("mae20", "mean"),
            bad_fwd20_ratio=("bad_fwd20_flag", "mean"),
            deep_mae20_ratio=("deep_mae20_flag", "mean"),
            low_mfe20_ratio=("low_mfe20_flag", "mean"),
            failure_outcome_ratio=("failure_outcome_flag", "mean"),
            avg_ret20=("ret20", "mean"),
            avg_close_vs_ma20=("close_vs_ma20", "mean"),
            avg_drawdown20=("drawdown20", "mean"),
        )
        .reset_index()
    )
    grouped = grouped.loc[grouped["rows"].ge(min_rows)].copy()
    if grouped.empty:
        return grouped
    grouped["scene_key"] = grouped[group_cols].astype(str).agg("|".join, axis=1)
    grouped["dimension"] = "+".join(group_cols)
    grouped.sort_values(["avg_forward_ret20", "failure_outcome_ratio", "rows"], ascending=[True, False, False], inplace=True)
    return grouped.reset_index(drop=True)


def _records(frame: pd.DataFrame, limit: int = 16) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return json.loads(frame.head(limit).to_json(orient="records", force_ascii=False))


def _write_csv(path: Path, frame: pd.DataFrame) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Trend Failure Scene Profile Shadow V1",
        "",
        "## Scope",
        "",
        "- research_only: true",
        "- baseline_mutation: false",
        "- nav_recompute: false",
        "- goal: profile where the current trend framework is structurally weak",
        "",
    ]
    for window in summary["windows"]:
        lines.extend([f"## {window['window_key']}", ""])
        lines.append(f"- rows: {window['rows']}")
        lines.append(f"- failure_outcome_ratio: {window['failure_outcome_ratio']}")
        lines.append("")
        lines.append("Worst single scenes:")
        for row in window["worst_single_scenes"]:
            lines.append(
                "- {dimension}={scene_key}: rows={rows}, avg_fwd20={avg_forward_ret20}, failure_ratio={failure_outcome_ratio}".format(
                    **{k: row.get(k) for k in row}
                )
            )
        lines.append("")
        lines.append("Worst combo scenes:")
        for row in window["worst_combo_scenes"]:
            lines.append(
                "- {scene_key}: rows={rows}, avg_fwd20={avg_forward_ret20}, failure_ratio={failure_outcome_ratio}".format(
                    **{k: row.get(k) for k in row}
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Guardrails",
            "",
            "- This is a scene profile, not a rule.",
            "- Bad outcomes use forward_ret20/MFE/MAE only for evaluation.",
            "- Any future rule must be designed per scene and validated against concentration risk.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_trend_failure_scene_profile(
    *,
    position_root: Path = DEFAULT_POSITION_ROOT,
    state_root: Path = DEFAULT_STATE_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    windows: tuple[str, ...] = DEFAULT_WINDOWS,
    variant: str = DEFAULT_VARIANT,
) -> dict[str, Any]:
    position_root = _resolve(position_root)
    state_root = _resolve(state_root)
    output_root = _resolve(output_root)
    single_dims = [
        ["year"],
        ["industry_name"],
        ["style_state_label"],
        ["industry_market_health_label"],
        ["rotation_pressure_label"],
        ["position_risk_state"],
    ]
    combo_dims = [
        ["style_state_label", "industry_market_health_label", "position_risk_state"],
        ["industry_market_health_label", "position_risk_state", "industry_name"],
        ["style_state_label", "position_risk_state", "industry_name"],
        ["year", "industry_name"],
    ]
    summary: dict[str, Any] = {
        "research_only": True,
        "baseline_mutation": False,
        "nav_recompute": False,
        "position_root": str(position_root),
        "state_root": str(state_root),
        "variant": variant,
        "windows": [],
        "outputs": {},
    }
    for window_key in windows:
        scene = load_scene_inputs(position_root, state_root, window_key=window_key, variant=variant)
        window_dir = output_root / window_key
        summary["outputs"][f"{window_key}/scene_detail"] = _write_csv(window_dir / "scene_detail.csv", scene)
        single_tables: list[pd.DataFrame] = []
        combo_tables: list[pd.DataFrame] = []
        for dims in single_dims:
            table = summarize_scene(scene, dims, min_rows=20)
            single_tables.append(table)
            summary["outputs"][f"{window_key}/single_{'_'.join(dims)}"] = _write_csv(window_dir / f"single_{'_'.join(dims)}.csv", table)
        for dims in combo_dims:
            table = summarize_scene(scene, dims, min_rows=20)
            combo_tables.append(table)
            summary["outputs"][f"{window_key}/combo_{'_'.join(dims)}"] = _write_csv(window_dir / f"combo_{'_'.join(dims)}.csv", table)
        single_matrix = pd.concat(single_tables, ignore_index=True) if single_tables else pd.DataFrame()
        combo_matrix = pd.concat(combo_tables, ignore_index=True) if combo_tables else pd.DataFrame()
        single_matrix.sort_values(["avg_forward_ret20", "failure_outcome_ratio", "rows"], ascending=[True, False, False], inplace=True)
        combo_matrix.sort_values(["avg_forward_ret20", "failure_outcome_ratio", "rows"], ascending=[True, False, False], inplace=True)
        summary["outputs"][f"{window_key}/single_scene_matrix"] = _write_csv(window_dir / "single_scene_matrix.csv", single_matrix)
        summary["outputs"][f"{window_key}/combo_scene_matrix"] = _write_csv(window_dir / "combo_scene_matrix.csv", combo_matrix)
        fail_ratio = float(scene["failure_outcome_flag"].mean()) if "failure_outcome_flag" in scene and len(scene) else None
        summary["windows"].append(
            {
                "window_key": window_key,
                "rows": int(len(scene)),
                "failure_outcome_ratio": fail_ratio,
                "worst_single_scenes": _records(single_matrix, 12),
                "worst_combo_scenes": _records(combo_matrix, 12),
            }
        )
    output_root.mkdir(parents=True, exist_ok=True)
    summary_path = output_root / "summary.json"
    report_path = output_root / "summary.md"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_render_report(summary), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    summary["report_path"] = str(report_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Trend failure scene profile shadow")
    parser.add_argument("--position-root", default=str(DEFAULT_POSITION_ROOT))
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    parser.add_argument("--windows", default=",".join(DEFAULT_WINDOWS))
    args = parser.parse_args()
    result = run_trend_failure_scene_profile(
        position_root=Path(args.position_root),
        state_root=Path(args.state_root),
        output_root=Path(args.output_root),
        variant=args.variant,
        windows=tuple(item.strip() for item in args.windows.split(",") if item.strip()),
    )
    print(json.dumps({"summary_path": result["summary_path"], "report_path": result["report_path"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
