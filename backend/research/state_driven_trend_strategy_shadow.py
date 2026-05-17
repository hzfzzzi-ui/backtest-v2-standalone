from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


DEFAULT_STATE_ROOT = Path("outputs/studies/cn_stock_etf/cn_stock_style_industry_state_switch_shadow_v1")
DEFAULT_TRADE_DETAIL = Path(
    "outputs/studies/cn_stock_etf/sr_20260511_v3_d0_trade_path_morphology_audit/machine/d0_trade_path_detail.csv"
)
DEFAULT_OUTPUT_ROOT = Path("outputs/studies/cn_stock_etf/cn_stock_state_driven_trend_strategy_shadow_v1")
DEFAULT_VARIANT = "M1_STYLE_STATE"
DEFAULT_WINDOWS = ("1626", "1217", "1226", "recent_2526", "turn_202512_202604")


MARKET_PERMISSION_BY_STYLE = {
    "broad_bull": "risk_on",
    "mid_small_beta": "risk_on",
    "split_rotation": "neutral",
    "large_cap_defense": "neutral",
    "risk_off": "risk_off",
}

INDUSTRY_PERMISSION_BY_HEALTH = {
    "healthy": "allow",
    "watch": "watch",
    "weak": "block",
}


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


def _write_csv(path: Path, frame: pd.DataFrame) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def _records(frame: pd.DataFrame, limit: int = 20) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return json.loads(frame.head(limit).to_json(orient="records", force_ascii=False, date_format="iso"))


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(pd.NA, index=frame.index, dtype="Float64")
    return pd.to_numeric(frame[column], errors="coerce")


def market_permission_from_style(style_state_label: object) -> str:
    return MARKET_PERMISSION_BY_STYLE.get(_text(style_state_label), "unknown")


def industry_permission_from_health(industry_health_label: object) -> str:
    return INDUSTRY_PERMISSION_BY_HEALTH.get(_text(industry_health_label), "unknown")


def derive_stock_eligibility(market_permission: object, industry_permission: object) -> tuple[str, str]:
    market = _text(market_permission)
    industry = _text(industry_permission)
    if market == "risk_off":
        return "blocked", "block_market"
    if industry == "block":
        return "blocked", "block_industry"
    if market == "unknown" or industry == "unknown":
        return "unknown", "unknown"
    if market == "neutral" or industry == "watch":
        return "reduced", "reduce_state"
    if market == "risk_on" and industry == "allow":
        return "eligible", "allow"
    return "unknown", "unknown"


def prepare_market_states(style_daily: pd.DataFrame) -> pd.DataFrame:
    if style_daily.empty:
        return pd.DataFrame()
    required = {"date", "style_state_label"}
    missing = required - set(style_daily.columns)
    if missing:
        raise ValueError("style state daily is missing required columns: " + ", ".join(sorted(missing)))
    out = style_daily.copy()
    out["market_state_date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out = out.loc[out["market_state_date"].notna()].copy()
    out["style_state_label"] = out["style_state_label"].map(_text)
    out["market_permission"] = out["style_state_label"].map(market_permission_from_style)
    cols = [
        "market_state_date",
        "style_state_label",
        "style_state_reason",
        "market_permission",
        "avg_ret20",
        "avg_ret60",
        "worst_drawdown60",
        "hs300_ret20",
        "zz500_ret20",
        "csi1000_ret20",
    ]
    present = [col for col in cols if col in out.columns]
    return out[present].sort_values("market_state_date").reset_index(drop=True)


def prepare_industry_states(industry_daily: pd.DataFrame) -> pd.DataFrame:
    if industry_daily.empty:
        return pd.DataFrame()
    required = {"date", "industry_name", "industry_health_label"}
    missing = required - set(industry_daily.columns)
    if missing:
        raise ValueError("industry health daily is missing required columns: " + ", ".join(sorted(missing)))
    out = industry_daily.copy()
    out["industry_state_date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out = out.loc[out["industry_state_date"].notna()].copy()
    out["industry_key"] = out["industry_name"].map(_text)
    out["industry_health_label"] = out["industry_health_label"].map(_text)
    out["industry_permission"] = out["industry_health_label"].map(industry_permission_from_health)
    cols = [
        "industry_state_date",
        "industry_key",
        "industry_index_code",
        "industry_name",
        "industry_health_label",
        "industry_health_reason",
        "industry_permission",
        "ret20",
        "ret60",
        "drawdown60",
        "trend_score",
    ]
    present = [col for col in cols if col in out.columns]
    return out[present].sort_values(["industry_key", "industry_state_date"]).reset_index(drop=True)


def prepare_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    out = trades.copy()
    out["trade_row_id"] = range(len(out))
    out["entry_date_ts"] = pd.to_datetime(out.get("entry_date"), errors="coerce").dt.normalize()
    signal = pd.to_datetime(out.get("entry_signal_date"), errors="coerce").dt.normalize()
    out["observation_date"] = signal.fillna(out["entry_date_ts"])
    out["exit_date_ts"] = pd.to_datetime(out.get("exit_date"), errors="coerce").dt.normalize()
    out["industry_key"] = out.get("sw_l1_industry", pd.Series("", index=out.index)).map(_text)
    for column in ["realized_pnl", "realized_return", "stock_pre_entry_20d_return", "close_mfe", "close_mae"]:
        out[column] = _num(out, column)
    out["loser_flag"] = out["realized_return"].lt(0).fillna(False)
    out["winner_flag"] = out["realized_return"].gt(0).fillna(False)
    return out.loc[out["observation_date"].notna()].copy()


def _merge_market_asof(trades: pd.DataFrame, market_states: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    if market_states.empty:
        out = trades.copy()
        out["market_permission"] = "unknown"
        out["style_state_label"] = ""
        out["market_state_date"] = pd.NaT
        return out
    return pd.merge_asof(
        trades.sort_values("observation_date"),
        market_states.sort_values("market_state_date"),
        left_on="observation_date",
        right_on="market_state_date",
        direction="backward",
    ).sort_values("trade_row_id")


def _merge_industry_asof(trades: pd.DataFrame, industry_states: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    if industry_states.empty:
        out = trades.copy()
        out["industry_permission"] = "unknown"
        out["industry_health_label"] = ""
        out["industry_state_date"] = pd.NaT
        return out
    pieces: list[pd.DataFrame] = []
    state_by_key = {
        key: grp.sort_values("industry_state_date").reset_index(drop=True)
        for key, grp in industry_states.groupby("industry_key", dropna=False)
    }
    for industry_key, grp in trades.groupby("industry_key", dropna=False, sort=False):
        state = state_by_key.get(industry_key)
        if state is None or state.empty:
            missing = grp.copy()
            missing["industry_permission"] = "unknown"
            missing["industry_health_label"] = ""
            missing["industry_state_date"] = pd.NaT
            pieces.append(missing)
            continue
        pieces.append(
            pd.merge_asof(
                grp.sort_values("observation_date"),
                state,
                left_on="observation_date",
                right_on="industry_state_date",
                direction="backward",
            )
        )
    if not pieces:
        return trades.copy()
    return pd.concat(pieces, ignore_index=True).sort_values("trade_row_id")


def build_trade_state_audit(
    *,
    trades: pd.DataFrame,
    market_states: pd.DataFrame,
    industry_states: pd.DataFrame,
) -> pd.DataFrame:
    trade_frame = prepare_trades(trades)
    if trade_frame.empty:
        return pd.DataFrame()
    joined = _merge_market_asof(trade_frame, market_states)
    joined = _merge_industry_asof(joined, industry_states)
    joined["market_permission"] = joined.get("market_permission", pd.Series("unknown", index=joined.index)).fillna("unknown").map(_text)
    joined["industry_permission"] = joined.get("industry_permission", pd.Series("unknown", index=joined.index)).fillna("unknown").map(_text)
    labels = [derive_stock_eligibility(row.market_permission, row.industry_permission) for row in joined.itertuples(index=False)]
    joined["stock_eligibility"] = [item[0] for item in labels]
    joined["shadow_action"] = [item[1] for item in labels]
    joined["filtered_or_reduced_flag"] = joined["shadow_action"].isin({"block_market", "block_industry", "reduce_state"})
    joined["loser_filtered_or_reduced_flag"] = joined["loser_flag"] & joined["filtered_or_reduced_flag"]
    joined["winner_filtered_or_reduced_flag"] = joined["winner_flag"] & joined["filtered_or_reduced_flag"]
    joined["loser_allowed_flag"] = joined["loser_flag"] & joined["shadow_action"].eq("allow")
    joined["winner_allowed_flag"] = joined["winner_flag"] & joined["shadow_action"].eq("allow")
    joined["audit_bucket"] = "flat_or_unknown"
    joined.loc[joined["loser_filtered_or_reduced_flag"], "audit_bucket"] = "loss_filtered_or_reduced"
    joined.loc[joined["winner_filtered_or_reduced_flag"], "audit_bucket"] = "winner_filtered_or_reduced"
    joined.loc[joined["loser_allowed_flag"], "audit_bucket"] = "loss_allowed"
    joined.loc[joined["winner_allowed_flag"], "audit_bucket"] = "winner_allowed"

    wanted = [
        "trade_row_id",
        "symbol",
        "name",
        "entry_date",
        "entry_signal_date",
        "observation_date",
        "exit_date",
        "sw_l1_industry",
        "industry_key",
        "realized_pnl",
        "realized_return",
        "stock_pre_entry_20d_return",
        "close_mfe",
        "close_mae",
        "market_state_date",
        "style_state_label",
        "style_state_reason",
        "market_permission",
        "industry_state_date",
        "industry_health_label",
        "industry_health_reason",
        "industry_permission",
        "stock_eligibility",
        "shadow_action",
        "loser_flag",
        "winner_flag",
        "filtered_or_reduced_flag",
        "loser_filtered_or_reduced_flag",
        "winner_filtered_or_reduced_flag",
        "loser_allowed_flag",
        "winner_allowed_flag",
        "audit_bucket",
        "entry_reason_code",
        "exit_reason_code",
        "triggered_rule",
        "analysis_group",
    ]
    present = [col for col in wanted if col in joined.columns]
    return joined[present].sort_values(["observation_date", "trade_row_id"]).reset_index(drop=True)


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return float(numerator / denominator)


def summarize_trade_audit(audit: pd.DataFrame) -> dict[str, Any]:
    if audit.empty:
        return {
            "trade_rows": 0,
            "loser_rows": 0,
            "winner_rows": 0,
            "loser_filtered_or_reduced_rows": 0,
            "winner_filtered_or_reduced_rows": 0,
            "loser_allowed_rows": 0,
            "winner_allowed_rows": 0,
            "loss_filtered_or_reduced_pnl": 0.0,
            "winner_filtered_or_reduced_pnl": 0.0,
            "filtered_winner_gain_to_loss_abs_ratio": None,
            "loss_capture_rate": None,
            "winner_overblock_rate": None,
            "decision": "hold",
        }
    loser_rows = int(audit["loser_flag"].sum())
    winner_rows = int(audit["winner_flag"].sum())
    loss_filtered = int((audit["loser_flag"] & audit["filtered_or_reduced_flag"]).sum())
    winner_filtered = int((audit["winner_flag"] & audit["filtered_or_reduced_flag"]).sum())
    loser_allowed = int((audit["loser_flag"] & audit["shadow_action"].eq("allow")).sum())
    winner_allowed = int((audit["winner_flag"] & audit["shadow_action"].eq("allow")).sum())
    loss_filtered_pnl = float(audit.loc[audit["loser_flag"] & audit["filtered_or_reduced_flag"], "realized_pnl"].sum())
    winner_filtered_pnl = float(audit.loc[audit["winner_flag"] & audit["filtered_or_reduced_flag"], "realized_pnl"].sum())
    loss_abs = abs(loss_filtered_pnl)
    winner_to_loss_ratio = None if loss_abs <= 0 else float(winner_filtered_pnl / loss_abs)
    loss_capture_rate = _rate(loss_filtered, loser_rows)
    winner_overblock_rate = _rate(winner_filtered, winner_rows)
    decision = "hold"
    if loss_capture_rate is not None and winner_overblock_rate is not None:
        if winner_overblock_rate >= loss_capture_rate:
            decision = "reject"
        elif winner_to_loss_ratio is not None and winner_to_loss_ratio > 1.0:
            decision = "hold"
        elif loss_capture_rate >= 0.45 and loss_capture_rate > winner_overblock_rate + 0.10:
            decision = "continue"
    return {
        "trade_rows": int(len(audit)),
        "date_min": str(pd.to_datetime(audit["observation_date"]).min().date()),
        "date_max": str(pd.to_datetime(audit["observation_date"]).max().date()),
        "loser_rows": loser_rows,
        "winner_rows": winner_rows,
        "loser_filtered_or_reduced_rows": loss_filtered,
        "winner_filtered_or_reduced_rows": winner_filtered,
        "loser_allowed_rows": loser_allowed,
        "winner_allowed_rows": winner_allowed,
        "loss_filtered_or_reduced_pnl": loss_filtered_pnl,
        "winner_filtered_or_reduced_pnl": winner_filtered_pnl,
        "filtered_winner_gain_to_loss_abs_ratio": winner_to_loss_ratio,
        "loss_capture_rate": loss_capture_rate,
        "winner_overblock_rate": winner_overblock_rate,
        "net_loss_filter_count": int(loss_filtered - winner_filtered),
        "decision": decision,
    }


def _summary_by(frame: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    grouped = frame.groupby(by, dropna=False)
    out = grouped.agg(
        trades=("symbol", "count"),
        symbols=("symbol", "nunique"),
        pnl_sum=("realized_pnl", "sum"),
        avg_realized_return=("realized_return", "mean"),
        median_realized_return=("realized_return", "median"),
        loser_rows=("loser_flag", "sum"),
        winner_rows=("winner_flag", "sum"),
        filtered_or_reduced_rows=("filtered_or_reduced_flag", "sum"),
        loser_filtered_or_reduced_rows=("loser_filtered_or_reduced_flag", "sum"),
        winner_filtered_or_reduced_rows=("winner_filtered_or_reduced_flag", "sum"),
        loser_allowed_rows=("loser_allowed_flag", "sum"),
        winner_allowed_rows=("winner_allowed_flag", "sum"),
    ).reset_index()
    out["loss_capture_rate"] = out.apply(lambda row: _rate(int(row["loser_filtered_or_reduced_rows"]), int(row["loser_rows"])), axis=1)
    out["winner_overblock_rate"] = out.apply(lambda row: _rate(int(row["winner_filtered_or_reduced_rows"]), int(row["winner_rows"])), axis=1)
    return out.sort_values(["trades", "loser_filtered_or_reduced_rows"], ascending=[False, False]).reset_index(drop=True)


def build_window_outputs(
    *,
    state_root: Path,
    trade_detail: pd.DataFrame,
    output_root: Path,
    window: str,
    variant: str = DEFAULT_VARIANT,
) -> dict[str, Any]:
    machine_source = state_root / window / variant / "machine"
    style_path = machine_source / "style_state_daily.csv"
    industry_path = machine_source / "industry_health_by_industry_daily.csv"
    style_daily = _read_csv(style_path)
    industry_daily = _read_csv(industry_path)
    if style_daily.empty and industry_daily.empty:
        raise FileNotFoundError(f"missing state inputs for {window}: {machine_source}")

    market_states = prepare_market_states(style_daily)
    industry_states = prepare_industry_states(industry_daily)
    start = market_states["market_state_date"].min() if not market_states.empty else pd.NaT
    end = market_states["market_state_date"].max() if not market_states.empty else pd.NaT
    trades = prepare_trades(trade_detail)
    if pd.notna(start) and pd.notna(end):
        trades = trades.loc[trades["observation_date"].between(start, end)].copy()
    audit = build_trade_state_audit(trades=trades, market_states=market_states, industry_states=industry_states)

    machine_dir = output_root / window / "machine"
    human_dir = output_root / window / "human"
    machine_dir.mkdir(parents=True, exist_ok=True)
    human_dir.mkdir(parents=True, exist_ok=True)

    action_summary = _summary_by(audit, ["shadow_action", "stock_eligibility"])
    layer_summary = _summary_by(audit, ["market_permission", "industry_permission", "stock_eligibility", "shadow_action"])
    industry_summary = _summary_by(audit, ["sw_l1_industry", "shadow_action"]) if "sw_l1_industry" in audit.columns else pd.DataFrame()
    bucket_summary = _summary_by(audit, ["audit_bucket"])
    recent = audit.loc[pd.to_datetime(audit.get("observation_date"), errors="coerce").ge(pd.Timestamp("2025-01-01"))].copy() if not audit.empty else pd.DataFrame()
    recent_summary = _summary_by(recent, ["shadow_action", "stock_eligibility"]) if not recent.empty else pd.DataFrame()

    paths = {
        "trade_state_audit": _write_csv(machine_dir / "trade_state_audit.csv", audit),
        "state_action_summary": _write_csv(machine_dir / "state_action_summary.csv", action_summary),
        "layer_summary": _write_csv(machine_dir / "layer_summary.csv", layer_summary),
        "industry_action_summary": _write_csv(machine_dir / "industry_action_summary.csv", industry_summary),
        "audit_bucket_summary": _write_csv(machine_dir / "audit_bucket_summary.csv", bucket_summary),
        "recent_2025_2026_summary": _write_csv(machine_dir / "recent_2025_2026_summary.csv", recent_summary),
    }
    summary = {
        "window": window,
        "variant": variant,
        "research_only": True,
        "baseline_mutation": False,
        "nav_recompute": False,
        "runtime_orders_emitted": False,
        "state_source_dir": str(machine_source),
        "style_state_path": str(style_path),
        "industry_health_path": str(industry_path),
        "input_state_date_min": None if pd.isna(start) else str(pd.Timestamp(start).date()),
        "input_state_date_max": None if pd.isna(end) else str(pd.Timestamp(end).date()),
        "label_policy": {
            "market_permission": MARKET_PERMISSION_BY_STYLE,
            "industry_permission": INDUSTRY_PERMISSION_BY_HEALTH,
            "asof_join": "entry_signal_date if available else entry_date; latest state date <= observation date",
            "evaluation_only_fields": ["realized_return", "realized_pnl", "close_mfe", "close_mae"],
        },
        "summary": summarize_trade_audit(audit),
        "action_summary": _records(action_summary, 50),
        "bucket_summary": _records(bucket_summary, 20),
        "recent_2025_2026_summary": _records(recent_summary, 20),
        "outputs": paths,
    }
    summary_path = machine_dir / "summary.json"
    report_path = human_dir / "summary.md"
    summary["outputs"]["summary_json"] = str(summary_path)
    summary["outputs"]["summary_md"] = str(report_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_render_report(summary), encoding="utf-8")
    return summary


def _render_report(summary: dict[str, Any]) -> str:
    core = summary["summary"]
    lines = [
        "# State Driven Trend Strategy Shadow V1",
        "",
        "## Scope",
        "",
        "- research_only: true",
        "- baseline_mutation: false",
        "- nav_recompute: false",
        f"- window: {summary['window']}",
        f"- state_range: {summary.get('input_state_date_min')} -> {summary.get('input_state_date_max')}",
        "",
        "## Conclusion",
        "",
        f"- decision: {core.get('decision')}",
        f"- trades: {core.get('trade_rows')}",
        f"- losers filtered/reduced: {core.get('loser_filtered_or_reduced_rows')} / {core.get('loser_rows')} ({core.get('loss_capture_rate')})",
        f"- winners filtered/reduced: {core.get('winner_filtered_or_reduced_rows')} / {core.get('winner_rows')} ({core.get('winner_overblock_rate')})",
        f"- filtered winner gain / filtered loss abs: {core.get('filtered_winner_gain_to_loss_abs_ratio')}",
        f"- losers still allowed: {core.get('loser_allowed_rows')}",
        "",
        "## Layer Summary",
        "",
        "| action | eligibility | trades | losers filtered/reduced | winners filtered/reduced | avg return |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in summary.get("action_summary") or []:
        lines.append(
            "| {shadow_action} | {stock_eligibility} | {trades} | {loser_filtered_or_reduced_rows} | {winner_filtered_or_reduced_rows} | {avg_realized_return} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- This is a shadow audit, not a PnL counterfactual.",
            "- Realized return, MFE, and MAE are used only after labels are built.",
            "- A continue decision only means the architecture deserves a narrower AB design; it is not baseline promotion evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_state_driven_trend_strategy_shadow(
    *,
    state_root: str | Path = DEFAULT_STATE_ROOT,
    trade_detail_path: str | Path = DEFAULT_TRADE_DETAIL,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    windows: Iterable[str] = DEFAULT_WINDOWS,
    variant: str = DEFAULT_VARIANT,
) -> dict[str, Any]:
    state_root_path = _resolve(state_root)
    trade_path = _resolve(trade_detail_path)
    output_root_path = _resolve(output_root)
    trades = _read_csv(trade_path)
    if trades.empty:
        raise FileNotFoundError(f"trade detail not found or empty: {trade_path}")

    runs: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for window in windows:
        try:
            runs.append(
                build_window_outputs(
                    state_root=state_root_path,
                    trade_detail=trades,
                    output_root=output_root_path,
                    window=str(window),
                    variant=variant,
                )
            )
        except FileNotFoundError as exc:
            skipped.append({"window": str(window), "reason": str(exc)})

    output_root_path.mkdir(parents=True, exist_ok=True)
    payload = {
        "study_id": "cn_stock_etf/cn_stock_state_driven_trend_strategy_shadow_v1",
        "research_only": True,
        "baseline_mutation": False,
        "nav_recompute": False,
        "runtime_orders_emitted": False,
        "windows": [run["window"] for run in runs],
        "skipped": skipped,
        "runs": [
            {
                "window": run["window"],
                "summary": run["summary"],
                "outputs": run["outputs"],
            }
            for run in runs
        ],
    }
    matrix_path = output_root_path / "matrix_summary.json"
    matrix_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["outputs"] = {"matrix_summary": str(matrix_path)}
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
    parser.add_argument("--trade-detail-path", default=str(DEFAULT_TRADE_DETAIL))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--windows", default=",".join(DEFAULT_WINDOWS))
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    args = parser.parse_args()
    windows = tuple(item.strip() for item in args.windows.split(",") if item.strip())
    summary = run_state_driven_trend_strategy_shadow(
        state_root=args.state_root,
        trade_detail_path=args.trade_detail_path,
        output_root=args.output_root,
        windows=windows,
        variant=args.variant,
    )
    print(json.dumps(summary["outputs"], ensure_ascii=False))


if __name__ == "__main__":
    main()
