from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from backend.research.v3_d0_trade_path_morphology_audit import (
    BASELINE_ID,
    STOCK_EXP_DIR,
    _fmt_money,
    _fmt_pct,
    _idx_at_or_after,
    _idx_at_or_before,
    _safe_float,
)
from backend.research.v3_d1_post_entry_confirmation_shadow import _load_base


ROUND_ID = "sr_20260511_v3_d5_mfe_mae_confirmation_shadow"
STUDY_ID = "cn_stock_etf/v3_d5_mfe_mae_confirmation_shadow_v1"
VARIANT_NAME = "D5_MFE_MAE_CONFIRMATION_SHADOW"
OUT_DIR = Path("outputs/studies/cn_stock_etf") / ROUND_ID
JOURNAL_PATH = Path("research/study_journal/rounds") / f"{ROUND_ID}.json"

VARIANTS = [
    {
        "variant": "D5_3D_MFE2_MAE5_HALF",
        "lookahead_days": 3,
        "min_close_mfe": 0.02,
        "max_close_mae": -0.05,
        "exit_pct": 0.5,
        "description": "after 3 trading days, if close MFE < +2% and close MAE <= -5%, exit half",
    },
    {
        "variant": "D5_5D_MFE3_MAE6_HALF",
        "lookahead_days": 5,
        "min_close_mfe": 0.03,
        "max_close_mae": -0.06,
        "exit_pct": 0.5,
        "description": "after 5 trading days, if close MFE < +3% and close MAE <= -6%, exit half",
    },
    {
        "variant": "D5_10D_MFE5_MAE8_HALF",
        "lookahead_days": 10,
        "min_close_mfe": 0.05,
        "max_close_mae": -0.08,
        "exit_pct": 0.5,
        "description": "after 10 trading days, if close MFE < +5% and close MAE <= -8%, exit half",
    },
]


def _counterfactual(row: pd.Series, series_map: dict[str, pd.DataFrame], variant: dict[str, Any]) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "").lower()
    series = series_map.get(symbol)
    if series is None or series.empty:
        return {"counterfactual_active_bool": False, "shadow_reason": "missing_price"}

    entry_idx = _idx_at_or_after(series, row.get("entry_date"))
    exit_idx = _idx_at_or_before(series, row.get("exit_date"))
    if entry_idx is None or exit_idx is None or exit_idx <= entry_idx:
        return {"counterfactual_active_bool": False, "shadow_reason": "bad_entry_exit_index"}

    lookahead = int(variant["lookahead_days"])
    eval_idx = entry_idx + lookahead
    if eval_idx >= exit_idx:
        return {
            "counterfactual_active_bool": False,
            "shadow_reason": "original_exit_before_or_on_eval",
            "eval_trading_day": lookahead,
        }
    if eval_idx >= len(series):
        return {"counterfactual_active_bool": False, "shadow_reason": "missing_eval_price", "eval_trading_day": lookahead}

    entry_close = _safe_float(series.iloc[entry_idx]["adj_close"])
    eval_close = _safe_float(series.iloc[eval_idx]["adj_close"])
    original_exit_close = _safe_float(series.iloc[exit_idx]["adj_close"])
    if not entry_close or eval_close is None or original_exit_close is None or original_exit_close == 0:
        return {"counterfactual_active_bool": False, "shadow_reason": "bad_price", "eval_trading_day": lookahead}

    window = series.iloc[entry_idx : eval_idx + 1].copy()
    close_mfe_until_eval = _safe_float(window["adj_close"].max() / entry_close - 1.0)
    close_mae_until_eval = _safe_float(window["adj_close"].min() / entry_close - 1.0)
    eval_return = eval_close / entry_close - 1.0
    failed = (
        close_mfe_until_eval is not None
        and close_mae_until_eval is not None
        and close_mfe_until_eval < float(variant["min_close_mfe"])
        and close_mae_until_eval <= float(variant["max_close_mae"])
    )
    if not failed:
        return {
            "counterfactual_active_bool": False,
            "shadow_reason": "mfe_mae_confirmation_passed",
            "eval_trading_day": lookahead,
            "eval_date": pd.Timestamp(series.iloc[eval_idx]["date"]).strftime("%Y-%m-%d"),
            "eval_return": eval_return,
            "close_mfe_until_eval": close_mfe_until_eval,
            "close_mae_until_eval": close_mae_until_eval,
        }

    exit_pct = float(variant["exit_pct"])
    sell_net_proceeds = _safe_float(row.get("sell_net_proceeds")) or 0.0
    early_vs_original_exit_ret = eval_close / original_exit_close - 1.0
    delta_pnl = sell_net_proceeds * exit_pct * early_vs_original_exit_ret
    return {
        "counterfactual_active_bool": True,
        "shadow_reason": "mfe_insufficient_mae_expanded_exit",
        "eval_trading_day": lookahead,
        "eval_date": pd.Timestamp(series.iloc[eval_idx]["date"]).strftime("%Y-%m-%d"),
        "eval_return": eval_return,
        "close_mfe_until_eval": close_mfe_until_eval,
        "close_mae_until_eval": close_mae_until_eval,
        "early_vs_original_exit_ret": early_vs_original_exit_ret,
        "exit_pct": exit_pct,
        "delta_pnl": float(delta_pnl),
        "hypothetical_realized_pnl": (_safe_float(row.get("realized_pnl")) or 0.0) + float(delta_pnl),
        "original_exit_date": pd.Timestamp(series.iloc[exit_idx]["date"]).strftime("%Y-%m-%d"),
        "original_exit_return_from_entry_adj": original_exit_close / entry_close - 1.0,
    }


def _build_detail(closed: pd.DataFrame, series_map: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for variant in VARIANTS:
        rows = [_counterfactual(row, series_map, variant) for _, row in closed.iterrows()]
        frame = pd.concat([closed.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
        frame["variant"] = variant["variant"]
        frame["variant_description"] = variant["description"]
        frame["lookahead_days"] = int(variant["lookahead_days"])
        frame["min_close_mfe_threshold"] = float(variant["min_close_mfe"])
        frame["max_close_mae_threshold"] = float(variant["max_close_mae"])
        frame["exit_pct"] = pd.to_numeric(frame.get("exit_pct"), errors="coerce").fillna(0.0)
        frame["delta_pnl"] = pd.to_numeric(frame.get("delta_pnl"), errors="coerce").fillna(0.0)
        frame["hypothetical_realized_pnl"] = pd.to_numeric(frame.get("hypothetical_realized_pnl"), errors="coerce").fillna(
            pd.to_numeric(frame["realized_pnl"], errors="coerce")
        )
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _summary_group(frame: pd.DataFrame, by_cols: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    grouped = frame.groupby(by_cols, dropna=False)
    return grouped.agg(
        rows=("symbol", "size"),
        active_rows=("counterfactual_active_bool", "sum"),
        original_pnl=("realized_pnl", "sum"),
        delta_pnl=("delta_pnl", "sum"),
        hypothetical_pnl=("hypothetical_realized_pnl", "sum"),
        improved_rows=("delta_pnl", lambda s: int((pd.to_numeric(s, errors="coerce") > 0).sum())),
        worsened_rows=("delta_pnl", lambda s: int((pd.to_numeric(s, errors="coerce") < 0).sum())),
        avg_delta=("delta_pnl", "mean"),
        median_delta=("delta_pnl", "median"),
        avg_eval_return=("eval_return", "mean"),
        avg_close_mfe_until_eval=("close_mfe_until_eval", "mean"),
        avg_close_mae_until_eval=("close_mae_until_eval", "mean"),
        avg_early_vs_original_exit_ret=("early_vs_original_exit_ret", "mean"),
    ).reset_index()


def _make_summaries(detail: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "variant_summary": _summary_group(detail, ["variant"]),
        "group_summary": _summary_group(detail, ["variant", "analysis_group"]),
        "exit_reason_summary": _summary_group(detail, ["variant", "exit_reason_code"]),
        "group_exit_reason_summary": _summary_group(detail, ["variant", "analysis_group", "exit_reason_code"]),
        "reason_summary": _summary_group(detail, ["variant", "shadow_reason"]),
    }


def _write_report(detail: pd.DataFrame, summaries: dict[str, pd.DataFrame], audit: dict[str, Any]) -> None:
    human = OUT_DIR / "human"
    human.mkdir(parents=True, exist_ok=True)
    variant_summary = summaries["variant_summary"].sort_values("delta_pnl", ascending=False)
    group_summary = summaries["group_summary"]
    best = variant_summary.iloc[0] if not variant_summary.empty else None

    lines: list[str] = []
    lines.append("# D5 MFE 不足 + MAE 扩大 Shadow")
    lines.append("")
    lines.append("## 结论")
    lines.append("- 本轮是 read-only shadow，不改 V3 baseline、NAV、runtime、信号、排序或退出规则。")
    lines.append("- 触发只使用买入后自身复权收盘价路径：close MFE 和 close MAE。")
    lines.append("- 本轮不使用行业、主题、大盘、候选排名、流动性或入场追高标签。")
    if best is not None:
        lines.append(
            f"- 当前最优变体 `{best['variant']}`：active={int(best['active_rows'])}，"
            f"delta_pnl={_fmt_money(best['delta_pnl'])}，improved={int(best['improved_rows'])}，"
            f"worsened={int(best['worsened_rows'])}。"
        )
    lines.append("")

    lines.append("## Variant Summary")
    lines.append("|variant|active|delta_pnl|improved|worsened|avg_mfe|avg_mae|avg_eval_ret|")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in variant_summary.itertuples(index=False):
        lines.append(
            f"|{row.variant}|{int(row.active_rows)}|{_fmt_money(row.delta_pnl)}|{int(row.improved_rows)}|"
            f"{int(row.worsened_rows)}|{_fmt_pct(row.avg_close_mfe_until_eval)}|"
            f"{_fmt_pct(row.avg_close_mae_until_eval)}|{_fmt_pct(row.avg_eval_return)}|"
        )

    lines.append("")
    lines.append("## TOP30 Split")
    lines.append("|variant|group|active|delta_pnl|improved|worsened|")
    lines.append("|---|---|---:|---:|---:|---:|")
    focus = group_summary.loc[group_summary["analysis_group"].isin(["loss_top30", "profit_top30"])].copy()
    for row in focus.sort_values(["variant", "analysis_group"]).itertuples(index=False):
        lines.append(
            f"|{row.variant}|{row.analysis_group}|{int(row.active_rows)}|{_fmt_money(row.delta_pnl)}|"
            f"{int(row.improved_rows)}|{int(row.worsened_rows)}|"
        )

    lines.append("")
    lines.append("## 口径")
    for variant in VARIANTS:
        lines.append(
            f"- `{variant['variant']}`：观察 {variant['lookahead_days']} 个交易日，"
            f"close MFE < {_fmt_pct(variant['min_close_mfe'])} 且 close MAE <= {_fmt_pct(variant['max_close_mae'])}，半卖。"
        )

    active = detail.loc[detail["counterfactual_active_bool"].astype(bool)].copy()
    if not active.empty:
        lines.append("")
        lines.append("## 最大误伤")
        worst = active.sort_values("delta_pnl").head(8)
        lines.append("|variant|symbol|name|entry|exit|group|pnl|mfe|mae|delta|")
        lines.append("|---|---|---|---|---|---|---:|---:|---:|---:|")
        for row in worst.itertuples(index=False):
            lines.append(
                f"|{row.variant}|{row.symbol}|{getattr(row, 'name', '')}|{pd.Timestamp(row.entry_date).strftime('%Y-%m-%d')}|"
                f"{pd.Timestamp(row.exit_date).strftime('%Y-%m-%d')}|{row.analysis_group}|{_fmt_money(row.realized_pnl)}|"
                f"{_fmt_pct(row.close_mfe_until_eval)}|{_fmt_pct(row.close_mae_until_eval)}|{_fmt_money(row.delta_pnl)}|"
            )
        lines.append("")
        lines.append("## 最大改善")
        best_rows = active.sort_values("delta_pnl", ascending=False).head(8)
        lines.append("|variant|symbol|name|entry|exit|group|pnl|mfe|mae|delta|")
        lines.append("|---|---|---|---|---|---|---:|---:|---:|---:|")
        for row in best_rows.itertuples(index=False):
            lines.append(
                f"|{row.variant}|{row.symbol}|{getattr(row, 'name', '')}|{pd.Timestamp(row.entry_date).strftime('%Y-%m-%d')}|"
                f"{pd.Timestamp(row.exit_date).strftime('%Y-%m-%d')}|{row.analysis_group}|{_fmt_money(row.realized_pnl)}|"
                f"{_fmt_pct(row.close_mfe_until_eval)}|{_fmt_pct(row.close_mae_until_eval)}|{_fmt_money(row.delta_pnl)}|"
            )

    lines.append("")
    lines.append("## 数据审计")
    lines.append("```json")
    lines.append(json.dumps(audit, ensure_ascii=False, indent=2))
    lines.append("```")
    (human / "d5_mfe_mae_confirmation_shadow.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_outputs(detail: pd.DataFrame, summaries: dict[str, pd.DataFrame], audit: dict[str, Any]) -> dict[str, Any]:
    machine = OUT_DIR / "machine"
    machine.mkdir(parents=True, exist_ok=True)
    detail.to_csv(machine / "d5_trade_detail.csv", index=False, encoding="utf-8-sig")
    for name, frame in summaries.items():
        frame.to_csv(machine / f"d5_{name}.csv", index=False, encoding="utf-8-sig")
    _write_report(detail, summaries, audit)

    variant_summary = summaries["variant_summary"].sort_values("delta_pnl", ascending=False)
    best = variant_summary.iloc[0].to_dict() if not variant_summary.empty else {}
    group_summary = summaries["group_summary"]
    focus = group_summary.loc[
        group_summary["variant"].eq(best.get("variant"))
        & group_summary["analysis_group"].isin(["loss_top30", "profit_top30"])
    ].copy()
    focus_payload = focus.to_dict(orient="records")
    decision_status = "continue" if _safe_float(best.get("delta_pnl")) and float(best.get("delta_pnl")) > 0 else "reject"

    journal = {
        "round_id": ROUND_ID,
        "title": "V3 D5 MFE不足 + MAE扩大确认失败 Shadow",
        "status": "audited",
        "study_id": STUDY_ID,
        "asset_scope": "cn_stock_etf",
        "baseline_id": BASELINE_ID,
        "primary_question": "只用买入后自身价格路径的 MFE 不足 + MAE 扩大，是否能更干净识别假突破？",
        "primary_variable": "close MFE/MAE post-entry confirmation failure",
        "fixed_assumptions": [
            "CN_STOCK_ETF_COMBO_BASELINE_V3 fixed",
            "stock closed trades only; ETF sleeve excluded",
            "no runtime, NAV, signal, ranking, execution, exit, pool, industry, theme, or benchmark changes",
            "trigger uses only adjusted close path visible at evaluation date",
            "half exit only",
        ],
        "windows": ["2012-2026"],
        "variants": [item["variant"] for item in VARIANTS],
        "evidence": [
            {
                "kind": "report",
                "study_id": STUDY_ID,
                "window_key": "1226",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "human" / "d5_mfe_mae_confirmation_shadow.md"),
                "note": "human D5 MFE/MAE confirmation shadow report",
                "linked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            {
                "kind": "table",
                "study_id": STUDY_ID,
                "window_key": "1226",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "machine" / "d5_trade_detail.csv"),
                "note": "per-trade D5 counterfactual detail",
                "linked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
        ],
        "key_findings": [
            f"Best variant: {best.get('variant')} delta={_fmt_money(best.get('delta_pnl'))}, active={int(best.get('active_rows') or 0)}.",
            "No industry/theme/benchmark/candidate/liquidity fields are used by the trigger.",
        ],
        "audit": audit,
        "decision": {
            "status": decision_status,
            "reason": "Best D5 variant is positive at trade-level shadow." if decision_status == "continue" else "Best D5 variant is non-positive at trade-level shadow.",
        },
        "next_actions": [
            "If positive, inspect profit TOP30 damage before Docker AB.",
            "If non-positive, do not tune thresholds blindly; add an explicit profit-runner protection condition.",
        ],
        "tags": ["cn_stock_etf", "V3", "D5", "mfe", "mae", "confirmation-failure", "shadow", "research-only"],
        "schema_version": "openclaw_study_round@1",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL_PATH.write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "round_id": ROUND_ID,
        "study_id": STUDY_ID,
        "baseline_id": BASELINE_ID,
        "best_variant": best,
        "best_top30_split": focus_payload,
        "decision": journal["decision"],
        "outputs": {
            "report": str(OUT_DIR / "human" / "d5_mfe_mae_confirmation_shadow.md"),
            "detail": str(OUT_DIR / "machine" / "d5_trade_detail.csv"),
            "variant_summary": str(OUT_DIR / "machine" / "d5_variant_summary.csv"),
            "journal": str(JOURNAL_PATH),
        },
    }


def run() -> dict[str, Any]:
    closed, series_map, audit = _load_base()
    detail = _build_detail(closed, series_map)
    summaries = _make_summaries(detail)
    audit = {
        **audit,
        "read_only_shadow": True,
        "trigger_scope": "stock adjusted close path only",
        "excluded_from_trigger": ["industry", "theme", "benchmark", "candidate_rank", "liquidity", "entry_chase"],
        "source_parent_audit": "outputs/studies/cn_stock_etf/sr_20260511_v3_d4_profit_loss_top30_difference_audit",
    }
    return _write_outputs(detail, summaries, audit)


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
