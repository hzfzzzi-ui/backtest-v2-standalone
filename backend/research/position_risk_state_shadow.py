from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_INPUT_ROOT = Path("outputs/studies/cn_stock_etf/weak_industry_stock_state_shadow_v1")
DEFAULT_OUTPUT_ROOT = Path("outputs/studies/cn_stock_etf/position_risk_state_shadow_v1")
DEFAULT_WINDOWS = ("1626", "1217", "1226", "recent_2526", "turn_202512_202604")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(path: str | Path) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def _read_position_detail(input_root: Path, window_key: str) -> pd.DataFrame:
    path = input_root / window_key / "position_state_detail.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return frame


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def _bool(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    raw = frame[column]
    if raw.dtype == bool:
        return raw.fillna(False)
    return raw.astype(str).str.lower().isin({"true", "1", "yes"})


def assign_position_risk_state(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    industry_weak = _bool(out, "industry_is_weak")
    stock_strong = _bool(out, "stock_strong_flag")
    stock_weak = _bool(out, "stock_weak_confirmed_flag")
    ret5 = _num(out, "ret5")
    ret10 = _num(out, "ret10")
    ret20 = _num(out, "ret20")
    close_vs_ma20 = _num(out, "close_vs_ma20")
    drawdown20 = _num(out, "drawdown20")

    risk_confirmed = (
        industry_weak
        & stock_weak
        & ret5.lt(0.0)
        & ret10.lt(0.0)
        & (ret20.lt(-0.03) | close_vs_ma20.lt(-0.03) | drawdown20.lt(-0.08))
    )
    repairing = industry_weak & ret5.gt(0.0) & close_vs_ma20.gt(-0.03) & ~risk_confirmed
    watch_lagging = industry_weak & ~stock_strong & ~stock_weak & ~repairing & ~risk_confirmed
    weak_but_strong_stock = industry_weak & stock_strong & ~repairing & ~risk_confirmed
    watch_pullback = ~industry_weak & stock_strong & (ret5.lt(0.0) | drawdown20.lt(-0.05))
    healthy_continue = ~industry_weak & stock_strong & ~watch_pullback

    out["position_risk_state"] = "neutral_hold"
    out.loc[healthy_continue, "position_risk_state"] = "healthy_continue"
    out.loc[watch_pullback, "position_risk_state"] = "watch_pullback"
    out.loc[weak_but_strong_stock, "position_risk_state"] = "industry_weak_stock_strong"
    out.loc[watch_lagging, "position_risk_state"] = "watch_lagging"
    out.loc[repairing, "position_risk_state"] = "repairing"
    out.loc[risk_confirmed, "position_risk_state"] = "risk_confirmed"

    out["position_risk_reason"] = ""
    out.loc[healthy_continue, "position_risk_reason"] = "stock trend remains strong outside weak industry"
    out.loc[watch_pullback, "position_risk_reason"] = "strong stock is pulling back outside weak industry"
    out.loc[weak_but_strong_stock, "position_risk_reason"] = "industry is weak but stock remains strong"
    out.loc[watch_lagging, "position_risk_reason"] = "industry is weak and stock is neither strong nor confirmed weak"
    out.loc[repairing, "position_risk_reason"] = "industry is weak but stock shows short-term repair"
    out.loc[risk_confirmed, "position_risk_reason"] = "industry is weak and stock weakness is confirmed by price state"
    out.loc[out["position_risk_state"].eq("neutral_hold"), "position_risk_reason"] = "no clear risk-state trigger"

    out["exit_candidate_flag"] = out["position_risk_state"].eq("risk_confirmed")
    out["watch_candidate_flag"] = out["position_risk_state"].isin(
        {"watch_lagging", "watch_pullback", "industry_weak_stock_strong", "repairing"}
    )
    return out


def summarize_by_state(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty or "position_risk_state" not in detail.columns:
        return pd.DataFrame()
    work = detail.copy()
    metrics = ["ret5", "ret10", "ret20", "close_vs_ma20", "drawdown20", "forward_ret5", "forward_ret20", "mfe20", "mae20"]
    for col in metrics:
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")
    agg: dict[str, tuple[str, str]] = {
        "rows": ("symbol", "count"),
        "unique_symbols": ("symbol", "nunique"),
        "exit_candidate_rows": ("exit_candidate_flag", "sum"),
        "watch_candidate_rows": ("watch_candidate_flag", "sum"),
    }
    for col in metrics:
        if col in work.columns:
            agg[f"avg_{col}"] = (col, "mean")
            agg[f"median_{col}"] = (col, "median")
    out = work.groupby("position_risk_state", dropna=False).agg(**agg).reset_index().rename(columns={"position_risk_state": "state"})
    if "avg_forward_ret20" in out.columns:
        out.sort_values(["avg_forward_ret20", "rows"], ascending=[True, False], inplace=True)
    return out.reset_index(drop=True)


def summarize_by_window_day(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty or "position_risk_state" not in detail.columns:
        return pd.DataFrame()
    pivot = (
        detail.pivot_table(index="date", columns="position_risk_state", values="symbol", aggfunc="count", fill_value=0)
        .reset_index()
        .rename_axis(None, axis=1)
    )
    total = detail.groupby("date")["symbol"].count().rename("total_positions").reset_index()
    out = total.merge(pivot, on="date", how="left")
    if "risk_confirmed" not in out.columns:
        out["risk_confirmed"] = 0
    if "watch_lagging" not in out.columns:
        out["watch_lagging"] = 0
    out["risk_confirmed_ratio"] = out["risk_confirmed"] / out["total_positions"].where(out["total_positions"].ne(0), 1)
    out["watch_lagging_ratio"] = out["watch_lagging"] / out["total_positions"].where(out["total_positions"].ne(0), 1)
    return out.sort_values("date").reset_index(drop=True)


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
        "# Position Risk State Shadow V1",
        "",
        "## Scope",
        "",
        "- research_only: true",
        "- baseline_mutation: false",
        "- nav_recompute: false",
        "- current_info_only_for_state: true",
        "",
    ]
    for window in summary["windows"]:
        lines.extend([f"## {window['window_key']}", ""])
        lines.append(f"- rows: {window['rows']}")
        lines.append(f"- exit_candidate_rows: {window['exit_candidate_rows']}")
        lines.append(f"- watch_candidate_rows: {window['watch_candidate_rows']}")
        lines.append("")
        for row in window["state_summary"]:
            lines.append(
                "- {state}: rows={rows}, avg_fwd20={avg_forward_ret20}, avg_mfe20={avg_mfe20}, avg_mae20={avg_mae20}".format(
                    **{k: row.get(k) for k in row}
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Guardrails",
            "",
            "- State labels are diagnostic only.",
            "- Forward return, MFE, and MAE are evaluation fields, not classification inputs.",
            "- A runtime AB requires risk_confirmed to be consistently worse across 1626, 1217, and 1226.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_position_risk_state_shadow(
    *,
    input_root: Path = DEFAULT_INPUT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    windows: tuple[str, ...] = DEFAULT_WINDOWS,
) -> dict[str, Any]:
    input_root = _resolve(input_root)
    output_root = _resolve(output_root)
    summary: dict[str, Any] = {
        "research_only": True,
        "baseline_mutation": False,
        "nav_recompute": False,
        "current_info_only_for_state": True,
        "input_root": str(input_root),
        "windows": [],
        "outputs": {},
    }
    for window_key in windows:
        raw = _read_position_detail(input_root, window_key)
        detail = assign_position_risk_state(raw)
        state_summary = summarize_by_state(detail)
        daily_summary = summarize_by_window_day(detail)
        window_dir = output_root / window_key
        summary["outputs"][f"{window_key}/position_risk_detail"] = _write_csv(window_dir / "position_risk_detail.csv", detail)
        summary["outputs"][f"{window_key}/state_summary"] = _write_csv(window_dir / "state_summary.csv", state_summary)
        summary["outputs"][f"{window_key}/daily_summary"] = _write_csv(window_dir / "daily_summary.csv", daily_summary)
        summary["windows"].append(
            {
                "window_key": window_key,
                "rows": int(len(detail)),
                "exit_candidate_rows": int(detail["exit_candidate_flag"].sum()) if "exit_candidate_flag" in detail else 0,
                "watch_candidate_rows": int(detail["watch_candidate_flag"].sum()) if "watch_candidate_flag" in detail else 0,
                "state_summary": _records(state_summary),
                "latest_daily": _records(daily_summary.tail(1), 1),
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
    parser = argparse.ArgumentParser(description="Position risk state shadow")
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--windows", default=",".join(DEFAULT_WINDOWS))
    args = parser.parse_args()
    result = run_position_risk_state_shadow(
        input_root=Path(args.input_root),
        output_root=Path(args.output_root),
        windows=tuple(item.strip() for item in args.windows.split(",") if item.strip()),
    )
    print(json.dumps({"summary_path": result["summary_path"], "report_path": result["report_path"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
