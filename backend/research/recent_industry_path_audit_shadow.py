from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_MECHANISM_ROOT = Path("outputs/studies/cn_stock_etf/trend_failure_mechanism_audit_shadow_v1")
DEFAULT_TRADE_DETAIL = Path(
    "outputs/studies/cn_stock_etf/sr_20260511_v3_d0_trade_path_morphology_audit/machine/d0_trade_path_detail.csv"
)
DEFAULT_OUTPUT_ROOT = Path("outputs/studies/cn_stock_etf/recent_industry_path_audit_shadow_v1")
DEFAULT_WINDOW = "1226"
TARGET_INDUSTRIES = ("基础化工", "计算机")
TARGET_START = "2025-01-01"

TRADE_NUMERIC_COLUMNS = [
    "realized_pnl",
    "realized_return",
    "stock_pre_entry_20d_return",
    "pre_entry_ret5",
    "pre_entry_ret10",
    "entry_close_vs_prev_ma20",
    "close_mfe",
    "close_mae",
    "giveback_from_close_peak",
    "peak_to_exit_drawdown",
    "industry_index_return_holding",
    "relative_vs_industry_holding",
    "days_below_ma20_warning_before_exit",
    "days_dd10_warning_before_exit",
    "days_since_last_candidate_before_exit",
    "hold_calendar_days",
]

SNAPSHOT_NUMERIC_COLUMNS = [
    "ret5",
    "ret10",
    "ret20",
    "close_vs_ma20",
    "drawdown20",
    "forward_ret20",
    "mfe20",
    "mae20",
    "industry_ret20",
    "industry_ret60",
    "industry_breadth_weak",
    "industry_breadth_healthy",
]

MECHANISM_FLAGS = [
    "high_chase_like_flag",
    "trend_exhaustion_after_flag",
    "industry_breakdown_flag",
    "market_breadth_weak_flag",
    "rotation_pressure_flag",
    "delayed_exit_like_flag",
    "healthy_state_misread_flag",
    "style_adverse_flag",
    "failure_outcome_flag",
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


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(pd.NA, index=frame.index, dtype="Float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _bool(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)
    return frame[column].fillna(False).astype(str).str.lower().isin({"true", "1", "yes"})


def _thresholds(frame: pd.DataFrame, columns: list[str]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for column in columns:
        values = _num(frame, column)
        for q in (0.25, 0.75):
            value = values.quantile(q) if values.notna().any() else None
            out[f"{column}_q{int(q * 100)}"] = None if value is None or pd.isna(value) else float(value)
    return out


def _ge(frame: pd.DataFrame, column: str, threshold: float | None) -> pd.Series:
    if threshold is None:
        return pd.Series(False, index=frame.index)
    return _num(frame, column).ge(threshold).fillna(False)


def _le(frame: pd.DataFrame, column: str, threshold: float | None) -> pd.Series:
    if threshold is None:
        return pd.Series(False, index=frame.index)
    return _num(frame, column).le(threshold).fillna(False)


def label_target_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    out = trades.copy()
    for column in TRADE_NUMERIC_COLUMNS:
        out[column] = _num(out, column)
    for column in ["entry_date", "exit_date"]:
        if column in out.columns:
            out[column] = pd.to_datetime(out[column], errors="coerce")

    thresholds = _thresholds(out, TRADE_NUMERIC_COLUMNS)
    out["trade_high_chase_flag"] = (
        _ge(out, "stock_pre_entry_20d_return", thresholds.get("stock_pre_entry_20d_return_q75"))
        | _ge(out, "pre_entry_ret10", thresholds.get("pre_entry_ret10_q75"))
        | _ge(out, "entry_close_vs_prev_ma20", thresholds.get("entry_close_vs_prev_ma20_q75"))
    )
    out["trade_early_failure_flag"] = (
        _le(out, "close_mfe", thresholds.get("close_mfe_q25"))
        & _le(out, "close_mae", thresholds.get("close_mae_q25"))
        & out["realized_return"].lt(0).fillna(False)
    )
    out["trade_peak_giveback_flag"] = (
        _ge(out, "close_mfe", thresholds.get("close_mfe_q75"))
        & _ge(out, "giveback_from_close_peak", thresholds.get("giveback_from_close_peak_q75"))
    )
    out["trade_delayed_exit_flag"] = (
        out["days_below_ma20_warning_before_exit"].ge(10).fillna(False)
        | out["days_dd10_warning_before_exit"].ge(10).fillna(False)
    )
    out["trade_industry_drag_flag"] = out["industry_index_return_holding"].lt(0).fillna(False)
    out["trade_risk_off_exit_flag"] = out.get("exit_reason_code", pd.Series("", index=out.index)).astype(str).eq(
        "RISK_OFF_EXIT"
    )
    out["trade_candidate_gap_flag"] = out["days_since_last_candidate_before_exit"].ge(5).fillna(False)

    reasons: list[str] = []
    reason_columns = [
        "trade_high_chase_flag",
        "trade_early_failure_flag",
        "trade_peak_giveback_flag",
        "trade_delayed_exit_flag",
        "trade_industry_drag_flag",
        "trade_risk_off_exit_flag",
        "trade_candidate_gap_flag",
    ]
    for row in out[reason_columns].itertuples(index=False):
        reasons.append(";".join(name.removeprefix("trade_").removesuffix("_flag") for name, value in zip(reason_columns, row) if bool(value)))
    out["trade_path_reasons"] = reasons
    return out


def _path_label(row: pd.Series) -> str:
    if row.get("market_breadth_weak_rate", 0.0) >= 0.6:
        return "market_breadth_break"
    if row.get("industry_breakdown_rate", 0.0) >= 0.6:
        return "industry_breakdown"
    if row.get("high_chase_like_rate", 0.0) >= 0.3 and row.get("trend_exhaustion_after_rate", 0.0) >= 0.2:
        return "high_chase_then_exhaustion"
    if row.get("healthy_state_misread_rate", 0.0) >= 0.5:
        return "healthy_state_misread"
    if row.get("delayed_exit_like_rate", 0.0) >= 0.3:
        return "delayed_exit_like"
    if row.get("failure_outcome_rate", 0.0) >= 0.5:
        return "unexplained_failure_cluster"
    return "mixed_or_non_failure"


def build_snapshot_segments(snapshots: pd.DataFrame) -> pd.DataFrame:
    if snapshots.empty:
        return pd.DataFrame()
    work = snapshots.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["date", "symbol"]).sort_values(["symbol", "date"]).reset_index(drop=True)
    for column in SNAPSHOT_NUMERIC_COLUMNS:
        work[column] = _num(work, column)
    for column in MECHANISM_FLAGS:
        work[column] = _bool(work, column)
    work["date_gap"] = work.groupby("symbol")["date"].diff().dt.days.fillna(1)
    work["segment_id"] = work.groupby("symbol")["date_gap"].transform(lambda s: s.gt(7).cumsum())

    rows: list[dict[str, Any]] = []
    for (symbol, segment_id), grp in work.groupby(["symbol", "segment_id"], sort=False):
        payload: dict[str, Any] = {
            "symbol": symbol,
            "segment_id": int(segment_id),
            "start_date": grp["date"].min().strftime("%Y-%m-%d"),
            "end_date": grp["date"].max().strftime("%Y-%m-%d"),
            "rows": int(len(grp)),
            "industry_name": ",".join(grp["industry_name"].dropna().astype(str).value_counts().head(2).index),
            "year_months": ",".join(grp["date"].dt.strftime("%Y-%m").drop_duplicates().tolist()),
            "avg_forward_ret20": float(grp["forward_ret20"].mean()),
            "min_forward_ret20": float(grp["forward_ret20"].min()),
            "avg_mfe20": float(grp["mfe20"].mean()),
            "avg_mae20": float(grp["mae20"].mean()),
            "avg_ret20": float(grp["ret20"].mean()),
            "avg_close_vs_ma20": float(grp["close_vs_ma20"].mean()),
            "avg_industry_ret20": float(grp["industry_ret20"].mean()),
            "avg_industry_breadth_weak": float(grp["industry_breadth_weak"].mean()),
            "first_failure_date": _first_date(grp, "failure_outcome_flag"),
            "first_industry_breakdown_date": _first_date(grp, "industry_breakdown_flag"),
            "first_market_breadth_weak_date": _first_date(grp, "market_breadth_weak_flag"),
            "first_high_chase_like_date": _first_date(grp, "high_chase_like_flag"),
            "dominant_position_state": _mode(grp, "position_risk_state"),
            "dominant_style_state": _mode(grp, "style_state_label"),
            "dominant_industry_market_health": _mode(grp, "industry_market_health_label"),
        }
        for column in MECHANISM_FLAGS:
            payload[column.removesuffix("_flag") + "_rate"] = float(grp[column].mean())
        rows.append(payload)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["path_label"] = out.apply(_path_label, axis=1)
    return out.sort_values(["avg_forward_ret20", "rows"], ascending=[True, False]).reset_index(drop=True)


def _first_date(frame: pd.DataFrame, flag: str) -> str | None:
    if flag not in frame.columns:
        return None
    hit = frame.loc[frame[flag].fillna(False).astype(bool), "date"]
    if hit.empty:
        return None
    return hit.min().strftime("%Y-%m-%d")


def _mode(frame: pd.DataFrame, column: str) -> str:
    if column not in frame.columns:
        return ""
    values = frame[column].dropna().astype(str).value_counts()
    return "" if values.empty else str(values.index[0])


def _summary_by(frame: pd.DataFrame, by: list[str], value_col: str = "realized_return") -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    if value_col == "segment":
        grouped = frame.groupby(by, dropna=False)
        return (
            grouped.agg(
                rows=("symbol", "count"),
                symbols=("symbol", "nunique"),
                avg_forward_ret20=("avg_forward_ret20", "mean"),
                min_forward_ret20=("min_forward_ret20", "min"),
                avg_failure_rate=("failure_outcome_rate", "mean"),
                avg_industry_breakdown_rate=("industry_breakdown_rate", "mean"),
                avg_market_breadth_weak_rate=("market_breadth_weak_rate", "mean"),
                avg_high_chase_like_rate=("high_chase_like_rate", "mean"),
            )
            .reset_index()
            .sort_values(["avg_forward_ret20", "rows"], ascending=[True, False])
        )
    grouped = frame.groupby(by, dropna=False)
    return (
        grouped.agg(
            rows=("symbol", "count"),
            symbols=("symbol", "nunique"),
            pnl_sum=("realized_pnl", "sum"),
            avg_realized_return=("realized_return", "mean"),
            median_realized_return=("realized_return", "median"),
            avg_pre_entry_20d=("stock_pre_entry_20d_return", "mean"),
            avg_close_mfe=("close_mfe", "mean"),
            avg_close_mae=("close_mae", "mean"),
            high_chase_rate=("trade_high_chase_flag", "mean"),
            peak_giveback_rate=("trade_peak_giveback_flag", "mean"),
            delayed_exit_rate=("trade_delayed_exit_flag", "mean"),
            risk_off_exit_rate=("trade_risk_off_exit_flag", "mean"),
        )
        .reset_index()
        .sort_values(["avg_realized_return", "rows"], ascending=[True, False])
    )


def _write_csv(path: Path, frame: pd.DataFrame) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def _records(frame: pd.DataFrame, limit: int = 12) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return json.loads(frame.head(limit).to_json(orient="records", force_ascii=False, date_format="iso"))


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Recent Industry Path Audit Shadow V1",
        "",
        "## Scope",
        "",
        "- research_only: true",
        "- baseline_mutation: false",
        "- nav_recompute: false",
        f"- target_start: {summary['target_start']}",
        f"- target_industries: {', '.join(summary['target_industries'])}",
        "",
        "## Findings",
        "",
    ]
    lines.append(f"- target_trades: {summary['target_trade_rows']}")
    lines.append(f"- target_segments: {summary['target_segment_rows']}")
    lines.append("")
    lines.append("Trade summary:")
    for row in summary["trade_summary"]:
        lines.append(
            "- {sw_l1_industry}: rows={rows}, avg_ret={avg_realized_return}, high_chase={high_chase_rate}, delayed_exit={delayed_exit_rate}, risk_off_exit={risk_off_exit_rate}".format(
                **{k: row.get(k) for k in row}
            )
        )
    lines.append("")
    lines.append("Worst snapshot segments:")
    for row in summary["worst_segments"]:
        lines.append(
            "- {symbol} {industry_name} {start_date}->{end_date}: avg_fwd20={avg_forward_ret20}, label={path_label}".format(
                **{k: row.get(k) for k in row}
            )
        )
    lines.append("")
    lines.extend(
        [
            "## Guardrails",
            "",
            "- Snapshot segments are explanatory position-day paths, not independent trades.",
            "- Future returns, MFE, and MAE are evaluation fields and must not enter runtime rules.",
            "- Trade count is small after 2025, so conclusions must rely on path consistency rather than trade-only statistics.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_recent_industry_path_audit(
    *,
    mechanism_root: str | Path = DEFAULT_MECHANISM_ROOT,
    trade_detail_path: str | Path = DEFAULT_TRADE_DETAIL,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    window: str = DEFAULT_WINDOW,
    target_start: str = TARGET_START,
    target_industries: tuple[str, ...] = TARGET_INDUSTRIES,
) -> dict[str, Any]:
    mechanism_dir = _resolve(mechanism_root)
    trade_path = _resolve(trade_detail_path)
    output_dir = _resolve(output_root)
    snapshots = _read_csv(mechanism_dir / window / "mechanism_detail.csv")
    trades = _read_csv(trade_path)

    target_start_ts = pd.Timestamp(target_start)
    if not snapshots.empty:
        snapshots["date"] = pd.to_datetime(snapshots["date"], errors="coerce")
        snapshots = snapshots.loc[
            snapshots["date"].ge(target_start_ts) & snapshots["industry_name"].isin(target_industries)
        ].copy()
    if not trades.empty:
        trades["entry_date"] = pd.to_datetime(trades["entry_date"], errors="coerce")
        trades = trades.loc[
            trades["entry_date"].ge(target_start_ts) & trades["sw_l1_industry"].isin(target_industries)
        ].copy()

    trade_detail = label_target_trades(trades)
    segments = build_snapshot_segments(snapshots)
    trade_summary = _summary_by(trade_detail, ["sw_l1_industry"])
    segment_summary = _summary_by(segments, ["industry_name", "path_label"], value_col="segment")

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "target_trade_detail": _write_csv(output_dir / "target_trade_detail.csv", trade_detail),
        "target_trade_summary": _write_csv(output_dir / "target_trade_summary.csv", trade_summary),
        "target_snapshot_segments": _write_csv(output_dir / "target_snapshot_segments.csv", segments),
        "target_segment_summary": _write_csv(output_dir / "target_segment_summary.csv", segment_summary),
    }
    summary: dict[str, Any] = {
        "research_only": True,
        "baseline_mutation": False,
        "nav_recompute": False,
        "window": window,
        "target_start": target_start,
        "target_industries": list(target_industries),
        "target_trade_rows": int(len(trade_detail)),
        "target_segment_rows": int(len(segments)),
        "trade_summary": _records(trade_summary),
        "segment_summary": _records(segment_summary, 20),
        "worst_trades": _records(trade_detail.sort_values("realized_return"), 12) if not trade_detail.empty else [],
        "worst_segments": _records(segments, 16),
        "outputs": paths,
    }
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "summary.md"
    summary["outputs"]["summary_json"] = str(summary_path)
    summary["outputs"]["summary_md"] = str(report_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_render_report(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mechanism-root", default=str(DEFAULT_MECHANISM_ROOT))
    parser.add_argument("--trade-detail-path", default=str(DEFAULT_TRADE_DETAIL))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--window", default=DEFAULT_WINDOW)
    parser.add_argument("--target-start", default=TARGET_START)
    parser.add_argument("--target-industries", default=",".join(TARGET_INDUSTRIES))
    args = parser.parse_args()
    summary = run_recent_industry_path_audit(
        mechanism_root=args.mechanism_root,
        trade_detail_path=args.trade_detail_path,
        output_root=args.output_root,
        window=args.window,
        target_start=args.target_start,
        target_industries=tuple(item.strip() for item in args.target_industries.split(",") if item.strip()),
    )
    print(json.dumps(summary["outputs"], ensure_ascii=False))


if __name__ == "__main__":
    main()
