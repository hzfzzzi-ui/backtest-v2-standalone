from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_INPUT_ROOT = Path("outputs/studies/cn_stock_etf/position_risk_state_shadow_v1")
DEFAULT_OUTPUT_ROOT = Path("outputs/studies/cn_stock_etf/watch_lagging_deep_dive_shadow_v1")
DEFAULT_WINDOWS = ("1626", "1217", "1226", "recent_2526", "turn_202512_202604")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(path: str | Path) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def _read_detail(input_root: Path, window_key: str) -> pd.DataFrame:
    path = input_root / window_key / "position_risk_detail.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return frame


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(pd.NA, index=frame.index, dtype="Float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _bucket_ret5(value: Any) -> str:
    if pd.isna(value):
        return "unknown"
    value = float(value)
    if value <= -0.10:
        return "ret5_deep_drop"
    if value <= -0.03:
        return "ret5_pullback"
    if value < 0.0:
        return "ret5_small_down"
    return "ret5_non_negative"


def _bucket_ret20(value: Any) -> str:
    if pd.isna(value):
        return "unknown"
    value = float(value)
    if value <= -0.05:
        return "ret20_negative_deep"
    if value < 0.0:
        return "ret20_negative_mild"
    if value < 0.08:
        return "ret20_positive_weak"
    return "ret20_positive_strong"


def _bucket_close_vs_ma20(value: Any) -> str:
    if pd.isna(value):
        return "unknown"
    value = float(value)
    if value >= 0.0:
        return "above_ma20"
    if value >= -0.03:
        return "near_below_ma20"
    if value >= -0.08:
        return "below_ma20"
    return "deep_below_ma20"


def _bucket_drawdown20(value: Any) -> str:
    if pd.isna(value):
        return "unknown"
    value = float(value)
    if value >= -0.05:
        return "dd20_shallow"
    if value >= -0.10:
        return "dd20_medium"
    return "dd20_deep"


def _bucket_duration(value: Any) -> str:
    if pd.isna(value):
        return "unknown"
    value = float(value)
    if value <= 3:
        return "weak_just_1_3d"
    if value <= 9:
        return "weak_early_4_9d"
    return "weak_persistent_10d_plus"


def _bucket_industry_ret20(value: Any) -> str:
    if pd.isna(value):
        return "unknown"
    value = float(value)
    if value <= -0.08:
        return "industry_ret20_deep_negative"
    if value < -0.03:
        return "industry_ret20_negative"
    if value < 0.0:
        return "industry_ret20_slight_negative"
    return "industry_ret20_non_negative"


def build_watch_lagging_features(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return detail.copy()
    out = detail.loc[detail.get("position_risk_state", pd.Series(dtype=str)).astype(str).eq("watch_lagging")].copy()
    if out.empty:
        return out
    for col in [
        "ret5",
        "ret10",
        "ret20",
        "close_vs_ma20",
        "drawdown20",
        "industry_weak_duration",
        "industry_ret20",
        "forward_ret5",
        "forward_ret20",
        "mfe20",
        "mae20",
    ]:
        out[col] = _num(out, col)
    out["ret5_bucket"] = out["ret5"].map(_bucket_ret5)
    out["ret20_bucket"] = out["ret20"].map(_bucket_ret20)
    out["close_vs_ma20_bucket"] = out["close_vs_ma20"].map(_bucket_close_vs_ma20)
    out["drawdown20_bucket"] = out["drawdown20"].map(_bucket_drawdown20)
    out["industry_weak_duration_bucket"] = out["industry_weak_duration"].map(_bucket_duration)
    out["industry_ret20_bucket"] = out["industry_ret20"].map(_bucket_industry_ret20)
    out["year_month"] = out["date"].astype(str).str.slice(0, 7)
    out["year"] = out["date"].astype(str).str.slice(0, 4)
    out["setup_key"] = (
        out["ret20_bucket"].astype(str)
        + "|"
        + out["close_vs_ma20_bucket"].astype(str)
        + "|"
        + out["drawdown20_bucket"].astype(str)
        + "|"
        + out["industry_weak_duration_bucket"].astype(str)
    )
    return out


def summarize_group(frame: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if frame.empty or group_col not in frame.columns:
        return pd.DataFrame()
    work = frame.copy()
    agg = (
        work.groupby(group_col, dropna=False)
        .agg(
            rows=("symbol", "count"),
            unique_symbols=("symbol", "nunique"),
            unique_industries=("industry_name", "nunique"),
            avg_ret5=("ret5", "mean"),
            avg_ret20=("ret20", "mean"),
            avg_close_vs_ma20=("close_vs_ma20", "mean"),
            avg_drawdown20=("drawdown20", "mean"),
            avg_forward_ret5=("forward_ret5", "mean"),
            avg_forward_ret20=("forward_ret20", "mean"),
            median_forward_ret20=("forward_ret20", "median"),
            avg_mfe20=("mfe20", "mean"),
            avg_mae20=("mae20", "mean"),
        )
        .reset_index()
        .rename(columns={group_col: "bucket"})
    )
    return agg.sort_values(["avg_forward_ret20", "rows"], ascending=[True, False]).reset_index(drop=True)


def summarize_concentration(frame: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if frame.empty or group_col not in frame.columns:
        return pd.DataFrame()
    out = (
        frame.groupby(group_col, dropna=False)
        .agg(
            rows=("symbol", "count"),
            unique_symbols=("symbol", "nunique"),
            avg_forward_ret20=("forward_ret20", "mean"),
            avg_mfe20=("mfe20", "mean"),
            avg_mae20=("mae20", "mean"),
        )
        .reset_index()
        .rename(columns={group_col: "bucket"})
    )
    return out.sort_values(["rows", "avg_forward_ret20"], ascending=[False, True]).reset_index(drop=True)


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
        "# Watch Lagging Deep Dive Shadow V1",
        "",
        "## Scope",
        "",
        "- research_only: true",
        "- baseline_mutation: false",
        "- nav_recompute: false",
        "- target_state: watch_lagging",
        "",
    ]
    for window in summary["windows"]:
        lines.extend([f"## {window['window_key']}", ""])
        lines.append(f"- rows: {window['rows']}")
        lines.append(f"- unique_symbols: {window['unique_symbols']}")
        lines.append(f"- unique_industries: {window['unique_industries']}")
        lines.append("")
        lines.append("Worst setup buckets:")
        for row in window["worst_setups"]:
            lines.append(
                "- {bucket}: rows={rows}, avg_fwd20={avg_forward_ret20}, avg_mfe20={avg_mfe20}, avg_mae20={avg_mae20}".format(
                    **{k: row.get(k) for k in row}
                )
            )
        lines.append("")
        lines.append("Worst simple buckets:")
        for row in window["worst_simple_buckets"]:
            lines.append(
                "- {dimension}={bucket}: rows={rows}, avg_fwd20={avg_forward_ret20}, avg_mfe20={avg_mfe20}, avg_mae20={avg_mae20}".format(
                    **{k: row.get(k) for k in row}
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Guardrails",
            "",
            "- This analysis explains watch_lagging; it is not an executable rule.",
            "- Future returns, MFE, and MAE are evaluation outputs only.",
            "- A candidate rule must survive concentration checks across years, industries, and windows.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_watch_lagging_deep_dive(
    *,
    input_root: Path = DEFAULT_INPUT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    windows: tuple[str, ...] = DEFAULT_WINDOWS,
) -> dict[str, Any]:
    input_root = _resolve(input_root)
    output_root = _resolve(output_root)
    dimensions = [
        "ret5_bucket",
        "ret20_bucket",
        "close_vs_ma20_bucket",
        "drawdown20_bucket",
        "industry_weak_duration_bucket",
        "industry_ret20_bucket",
    ]
    concentration_dims = ["year", "year_month", "industry_name", "symbol"]
    summary: dict[str, Any] = {
        "research_only": True,
        "baseline_mutation": False,
        "nav_recompute": False,
        "target_state": "watch_lagging",
        "input_root": str(input_root),
        "windows": [],
        "outputs": {},
    }
    for window_key in windows:
        detail = _read_detail(input_root, window_key)
        watch = build_watch_lagging_features(detail)
        window_dir = output_root / window_key
        summary["outputs"][f"{window_key}/watch_lagging_detail"] = _write_csv(window_dir / "watch_lagging_detail.csv", watch)
        simple_rows: list[pd.DataFrame] = []
        for dim in dimensions:
            grouped = summarize_group(watch, dim)
            grouped.insert(0, "dimension", dim)
            simple_rows.append(grouped)
            summary["outputs"][f"{window_key}/{dim}_summary"] = _write_csv(window_dir / f"{dim}_summary.csv", grouped)
        simple_summary = pd.concat(simple_rows, ignore_index=True) if simple_rows else pd.DataFrame()
        setup_summary = summarize_group(watch, "setup_key")
        summary["outputs"][f"{window_key}/simple_bucket_summary"] = _write_csv(window_dir / "simple_bucket_summary.csv", simple_summary)
        summary["outputs"][f"{window_key}/setup_summary"] = _write_csv(window_dir / "setup_summary.csv", setup_summary)
        for dim in concentration_dims:
            conc = summarize_concentration(watch, dim)
            summary["outputs"][f"{window_key}/{dim}_concentration"] = _write_csv(window_dir / f"{dim}_concentration.csv", conc)
        worst_simple = simple_summary.loc[simple_summary["rows"].ge(5)].sort_values(["avg_forward_ret20", "rows"], ascending=[True, False]) if not simple_summary.empty else pd.DataFrame()
        worst_setup = setup_summary.loc[setup_summary["rows"].ge(5)].sort_values(["avg_forward_ret20", "rows"], ascending=[True, False]) if not setup_summary.empty else pd.DataFrame()
        summary["windows"].append(
            {
                "window_key": window_key,
                "rows": int(len(watch)),
                "unique_symbols": int(watch["symbol"].nunique()) if "symbol" in watch else 0,
                "unique_industries": int(watch["industry_name"].nunique()) if "industry_name" in watch else 0,
                "worst_simple_buckets": _records(worst_simple, 10),
                "worst_setups": _records(worst_setup, 10),
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
    parser = argparse.ArgumentParser(description="Watch lagging deep dive shadow")
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--windows", default=",".join(DEFAULT_WINDOWS))
    args = parser.parse_args()
    result = run_watch_lagging_deep_dive(
        input_root=Path(args.input_root),
        output_root=Path(args.output_root),
        windows=tuple(item.strip() for item in args.windows.split(",") if item.strip()),
    )
    print(json.dumps({"summary_path": result["summary_path"], "report_path": result["report_path"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
