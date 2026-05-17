from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_STUDY_MACHINE_DIR = (
    Path("outputs")
    / "studies"
    / "cn_stock_etf"
    / "cn_stock_style_industry_state_switch_shadow_v1"
    / "1626"
    / "M1_STYLE_STATE"
    / "machine"
)
DEFAULT_OUTPUT_DIR = (
    Path("outputs")
    / "studies"
    / "cn_stock_etf"
    / "holding_health_dashboard_v1"
    / "1626"
)

HEALTH_RANK = {
    "unknown": 0,
    "weak": 1,
    "watch": 2,
    "healthy": 3,
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_path(path: str | Path) -> Path:
    raw = Path(path)
    return raw if raw.is_absolute() else (_repo_root() / raw).resolve()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _to_date(frame: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    out = frame.copy()
    if column in out.columns:
        out[column] = pd.to_datetime(out[column], errors="coerce")
        out = out.loc[out[column].notna()].copy()
    return out


def _health_rank(label: Any) -> int:
    return int(HEALTH_RANK.get(str(label or "unknown").strip().lower(), 0))


def explode_held_industry_daily(held_industry: pd.DataFrame) -> pd.DataFrame:
    """Expand R1 industry-level held rows into symbol-level health rows."""
    if held_industry.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "industry_index_code",
                "industry_name",
                "industry_health_label",
                "industry_ret20",
                "industry_ret60",
            ]
        )
    work = _to_date(held_industry)
    rows: list[dict[str, Any]] = []
    for row in work.itertuples(index=False):
        symbols = [
            str(item).strip().lower()
            for item in str(getattr(row, "held_symbols", "") or "").split(";")
            if str(item).strip()
        ]
        for symbol in symbols:
            rows.append(
                {
                    "date": getattr(row, "date"),
                    "symbol": symbol,
                    "industry_index_code": str(getattr(row, "industry_index_code", "") or ""),
                    "industry_name": str(getattr(row, "industry_name", "") or "unknown"),
                    "industry_health_label": str(getattr(row, "industry_health_label", "") or "unknown"),
                    "industry_ret20": getattr(row, "ret20", None),
                    "industry_ret60": getattr(row, "ret60", None),
                }
            )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["health_rank"] = out["industry_health_label"].map(_health_rank).astype(int)
    out = out.sort_values(["symbol", "date"]).reset_index(drop=True)
    out["prev_industry_health_label"] = out.groupby("symbol")["industry_health_label"].shift(1).fillna("")
    out["prev_health_rank"] = out.groupby("symbol")["health_rank"].shift(1)
    out["health_rank_delta"] = out["health_rank"] - out["prev_health_rank"]
    out["health_downgrade_flag"] = out["health_rank_delta"].lt(0).fillna(False)
    out["new_weak_flag"] = (
        out["industry_health_label"].eq("weak")
        & out["prev_industry_health_label"].ne("weak")
        & out["prev_industry_health_label"].ne("")
    )
    out["transition_label"] = out.apply(
        lambda r: (
            f"{r['prev_industry_health_label']}_to_{r['industry_health_label']}"
            if bool(r["health_downgrade_flag"])
            else ""
        ),
        axis=1,
    )
    return out


def _candidate_daily(candidate_industry: pd.DataFrame) -> pd.DataFrame:
    if candidate_industry.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "cash_blocked_candidate_count",
                "cash_blocked_candidate_industries",
                "cash_blocked_candidate_symbols",
            ]
        )
    work = _to_date(candidate_industry)
    if work.empty:
        return pd.DataFrame()
    work["industry_name"] = work.get("industry_name", "unknown").fillna("unknown").astype(str)
    work["cash_blocked_symbol_count"] = pd.to_numeric(
        work.get("cash_blocked_symbol_count", 0), errors="coerce"
    ).fillna(0)
    grouped = (
        work.groupby("date")
        .agg(
            cash_blocked_candidate_count=("cash_blocked_symbol_count", "sum"),
            cash_blocked_candidate_industries=(
                "industry_name",
                lambda s: ";".join(sorted({str(v) for v in s if str(v) and str(v) != "nan"})[:12]),
            ),
            cash_blocked_candidate_symbols=(
                "cash_blocked_symbols",
                lambda s: ";".join(
                    sorted(
                        {
                            item.strip().lower()
                            for value in s.fillna("").astype(str)
                            for item in value.split(";")
                            if item.strip()
                        }
                    )[:30]
                ),
            ),
        )
        .reset_index()
    )
    grouped["cash_blocked_candidate_count"] = grouped["cash_blocked_candidate_count"].astype(int)
    return grouped


def build_holding_health_dashboard(
    *,
    study_machine_dir: str | Path = DEFAULT_STUDY_MACHINE_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    machine_dir = _resolve_path(study_machine_dir)
    out_dir = _resolve_path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    r1_daily = _to_date(_read_csv(machine_dir / "rotation_pressure_daily.csv"))
    held_industry = _to_date(_read_csv(machine_dir / "rotation_pressure_held_industry_daily.csv"))
    candidate_industry = _to_date(_read_csv(machine_dir / "candidate_pool_industry_daily.csv"))
    source_audit_path = machine_dir / "candidate_signals_source_audit.json"
    source_audit = json.loads(source_audit_path.read_text(encoding="utf-8")) if source_audit_path.exists() else {}

    positions = explode_held_industry_daily(held_industry)
    candidates = _candidate_daily(candidate_industry)

    daily = r1_daily.copy()
    if daily.empty:
        daily = pd.DataFrame(columns=["date"])
    for column in [
        "held_stock_count",
        "held_healthy_count",
        "held_watch_count",
        "held_weak_count",
        "held_unknown_count",
    ]:
        if column in daily.columns:
            daily[column] = pd.to_numeric(daily[column], errors="coerce").fillna(0).astype(int)
    if not positions.empty:
        flags = (
            positions.groupby("date")
            .agg(
                downgraded_holding_count=("health_downgrade_flag", "sum"),
                new_weak_holding_count=("new_weak_flag", "sum"),
                downgraded_symbols=("symbol", lambda s: ""),
            )
            .reset_index()
        )
        downgraded = (
            positions.loc[positions["health_downgrade_flag"]]
            .groupby("date")
            .agg(
                downgraded_symbols=(
                    "symbol",
                    lambda s: ";".join(sorted({str(v) for v in s})[:30]),
                )
            )
            .reset_index()
        )
        flags = flags.drop(columns=["downgraded_symbols"], errors="ignore").merge(
            downgraded, on="date", how="left"
        )
        weak_symbols = (
            positions.loc[positions["industry_health_label"].eq("weak")]
            .groupby("date")
            .agg(weak_symbols=("symbol", lambda s: ";".join(sorted({str(v) for v in s})[:30])))
            .reset_index()
        )
        daily = daily.merge(flags, on="date", how="left").merge(weak_symbols, on="date", how="left")
    else:
        daily["downgraded_holding_count"] = 0
        daily["new_weak_holding_count"] = 0
        daily["downgraded_symbols"] = ""
        daily["weak_symbols"] = ""
    if not candidates.empty:
        daily = daily.merge(candidates, on="date", how="left")
    for column in ["downgraded_holding_count", "new_weak_holding_count", "cash_blocked_candidate_count"]:
        if column not in daily.columns:
            daily[column] = 0
        daily[column] = pd.to_numeric(daily[column], errors="coerce").fillna(0).astype(int)
    for column in [
        "downgraded_symbols",
        "weak_symbols",
        "cash_blocked_candidate_industries",
        "cash_blocked_candidate_symbols",
    ]:
        if column not in daily.columns:
            daily[column] = ""
        daily[column] = daily[column].fillna("").astype(str)

    daily["dashboard_alert_level"] = daily.apply(_alert_level, axis=1)
    daily["dashboard_alert_reason"] = daily.apply(_alert_reason, axis=1)
    daily = daily.sort_values("date").reset_index(drop=True)

    summary = _build_summary(daily, positions, source_audit)
    daily_path = out_dir / "holding_health_daily.csv"
    positions_path = out_dir / "holding_health_positions.csv"
    summary_path = out_dir / "holding_health_summary.json"
    report_path = out_dir / "holding_health_summary.md"

    daily.to_csv(daily_path, index=False, encoding="utf-8-sig")
    positions.to_csv(positions_path, index=False, encoding="utf-8-sig")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_render_report(summary, daily, positions), encoding="utf-8")

    return {
        "status": "OK",
        "output_dir": str(out_dir),
        "daily_path": str(daily_path),
        "positions_path": str(positions_path),
        "summary_path": str(summary_path),
        "report_path": str(report_path),
        "summary": summary,
    }


def _alert_level(row: pd.Series) -> str:
    weak = int(row.get("held_weak_count") or 0)
    watch = int(row.get("held_watch_count") or 0)
    healthy = int(row.get("held_healthy_count") or 0)
    downgraded = int(row.get("downgraded_holding_count") or 0)
    cash_blocked = int(row.get("cash_blocked_candidate_count") or 0)
    if weak >= 3 or downgraded >= 3:
        return "red"
    if weak > 0 or watch >= healthy or cash_blocked > 0:
        return "yellow"
    if healthy > 0:
        return "green"
    return "neutral"


def _alert_reason(row: pd.Series) -> str:
    parts: list[str] = []
    weak = int(row.get("held_weak_count") or 0)
    watch = int(row.get("held_watch_count") or 0)
    healthy = int(row.get("held_healthy_count") or 0)
    downgraded = int(row.get("downgraded_holding_count") or 0)
    cash_blocked = int(row.get("cash_blocked_candidate_count") or 0)
    if weak:
        parts.append(f"{weak} weak holdings")
    if watch:
        parts.append(f"{watch} watch holdings")
    if downgraded:
        parts.append(f"{downgraded} health downgrades")
    if cash_blocked:
        parts.append(f"{cash_blocked} cash-blocked candidates")
    if not parts and healthy:
        parts.append("held book is mainly healthy")
    return "; ".join(parts)


def _build_summary(daily: pd.DataFrame, positions: pd.DataFrame, source_audit: dict[str, Any]) -> dict[str, Any]:
    latest = daily.iloc[-1].to_dict() if not daily.empty else {}
    latest_date = latest.get("date")
    if hasattr(latest_date, "date"):
        latest_date = latest_date.date().isoformat()
    by_alert = daily["dashboard_alert_level"].value_counts().to_dict() if "dashboard_alert_level" in daily else {}
    by_r1 = daily["rotation_pressure_label"].value_counts().to_dict() if "rotation_pressure_label" in daily else {}
    latest_positions = positions.loc[positions["date"].eq(pd.to_datetime(latest_date))] if latest_date and not positions.empty else pd.DataFrame()
    latest_weak = latest_positions.loc[latest_positions["industry_health_label"].eq("weak")] if not latest_positions.empty else pd.DataFrame()
    latest_watch = latest_positions.loc[latest_positions["industry_health_label"].eq("watch")] if not latest_positions.empty else pd.DataFrame()
    return {
        "dashboard_id": "holding_health_dashboard_v1",
        "window_key": "1626",
        "research_only": True,
        "not_nav_backtest": True,
        "row_count": int(len(daily)),
        "position_row_count": int(len(positions)),
        "first_date": str(daily["date"].iloc[0].date()) if not daily.empty else "",
        "last_date": str(daily["date"].iloc[-1].date()) if not daily.empty else "",
        "latest": {
            "date": latest_date or "",
            "alert_level": str(latest.get("dashboard_alert_level") or ""),
            "alert_reason": str(latest.get("dashboard_alert_reason") or ""),
            "rotation_pressure_label": str(latest.get("rotation_pressure_label") or ""),
            "held_stock_count": int(latest.get("held_stock_count") or 0),
            "held_healthy_count": int(latest.get("held_healthy_count") or 0),
            "held_watch_count": int(latest.get("held_watch_count") or 0),
            "held_weak_count": int(latest.get("held_weak_count") or 0),
            "downgraded_holding_count": int(latest.get("downgraded_holding_count") or 0),
            "new_weak_holding_count": int(latest.get("new_weak_holding_count") or 0),
            "weak_symbols": str(latest.get("weak_symbols") or ""),
            "downgraded_symbols": str(latest.get("downgraded_symbols") or ""),
            "cash_blocked_candidate_count": int(latest.get("cash_blocked_candidate_count") or 0),
            "cash_blocked_candidate_industries": str(latest.get("cash_blocked_candidate_industries") or ""),
        },
        "latest_weak_positions": latest_weak[
            ["symbol", "industry_name", "industry_health_label", "industry_ret20", "industry_ret60"]
        ].to_dict("records") if not latest_weak.empty else [],
        "latest_watch_positions": latest_watch[
            ["symbol", "industry_name", "industry_health_label", "industry_ret20", "industry_ret60"]
        ].to_dict("records") if not latest_watch.empty else [],
        "alert_level_counts": {str(k): int(v) for k, v in by_alert.items()},
        "rotation_pressure_counts": {str(k): int(v) for k, v in by_r1.items()},
        "source_limitations": {
            "candidate_source_scope": str(source_audit.get("source_scope") or ""),
            "candidate_selected_row_count": int(source_audit.get("selected_row_count") or 0),
            "candidate_reject_reason_counts": source_audit.get("reject_reason_counts") or {},
            "note": "R3 is rejected/diagnostic cash-blocked candidates only, not a full candidate pool.",
        },
    }


def _render_report(summary: dict[str, Any], daily: pd.DataFrame, positions: pd.DataFrame) -> str:
    latest = summary.get("latest", {})
    lines = [
        "# Holding Health Dashboard V1",
        "",
        "## Conclusion",
        "",
        "- research_only: true",
        "- scope: R1 holding health dashboard; no trades, no NAV recomputation, no baseline change.",
        f"- latest date: {latest.get('date')}",
        f"- latest alert: {latest.get('alert_level')} ({latest.get('alert_reason')})",
        f"- latest R1: {latest.get('rotation_pressure_label')}",
        f"- latest held healthy/watch/weak: {latest.get('held_healthy_count')}/{latest.get('held_watch_count')}/{latest.get('held_weak_count')}",
        f"- latest weak symbols: {latest.get('weak_symbols')}",
        f"- latest downgraded symbols: {latest.get('downgraded_symbols')}",
        f"- latest cash-blocked candidates: {latest.get('cash_blocked_candidate_count')} ({latest.get('cash_blocked_candidate_industries')})",
        "",
        "## Source Limitations",
        "",
        f"- candidate source scope: {summary.get('source_limitations', {}).get('candidate_source_scope')}",
        "- R3 cash-blocked candidates are not a full candidate pool.",
        "",
        "## Recent Daily",
        "",
        "| date | alert | R1 | healthy | watch | weak | downgraded | cash blocked | reason |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    recent = daily.tail(20) if not daily.empty else pd.DataFrame()
    for row in recent.itertuples(index=False):
        lines.append(
            "| {date} | {alert} | {r1} | {healthy} | {watch} | {weak} | {down} | {cash} | {reason} |".format(
                date=getattr(row, "date").date().isoformat() if hasattr(getattr(row, "date"), "date") else "",
                alert=getattr(row, "dashboard_alert_level", ""),
                r1=getattr(row, "rotation_pressure_label", ""),
                healthy=int(getattr(row, "held_healthy_count", 0) or 0),
                watch=int(getattr(row, "held_watch_count", 0) or 0),
                weak=int(getattr(row, "held_weak_count", 0) or 0),
                down=int(getattr(row, "downgraded_holding_count", 0) or 0),
                cash=int(getattr(row, "cash_blocked_candidate_count", 0) or 0),
                reason=str(getattr(row, "dashboard_alert_reason", "")),
            )
        )
    lines.extend(["", "## Latest Weak Positions", ""])
    weak_positions = summary.get("latest_weak_positions") or []
    if weak_positions:
        lines.extend(["| symbol | industry | ret20 | ret60 |", "|---|---|---:|---:|"])
        for item in weak_positions:
            lines.append(
                f"| {item.get('symbol')} | {item.get('industry_name')} | {item.get('industry_ret20')} | {item.get('industry_ret60')} |"
            )
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build holding health dashboard from R1/I1 shadow outputs.")
    parser.add_argument("--study-machine-dir", default=str(DEFAULT_STUDY_MACHINE_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    result = build_holding_health_dashboard(
        study_machine_dir=args.study_machine_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
