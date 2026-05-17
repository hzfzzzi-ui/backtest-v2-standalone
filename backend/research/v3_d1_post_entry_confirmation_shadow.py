from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from backend.research.v3_d0_trade_path_morphology_audit import (
    BASELINE_ID,
    STOCK_EXP_DIR,
    _abs,
    _assign_groups,
    _fmt_money,
    _fmt_pct,
    _idx_at_or_after,
    _idx_at_or_before,
    _load_inputs,
    _load_ohlcv,
    _safe_float,
    _series_map,
)


ROUND_ID = "sr_20260511_v3_d1_post_entry_confirmation_shadow"
STUDY_ID = "cn_stock_etf/v3_d1_post_entry_confirmation_shadow_v1"
VARIANT_NAME = "D1_POST_ENTRY_CONFIRMATION_FAILURE_SHADOW"
OUT_DIR = Path("outputs/studies/cn_stock_etf") / ROUND_ID
JOURNAL_PATH = Path("research/study_journal/rounds") / f"{ROUND_ID}.json"

VARIANTS = [
    {
        "variant": "D1_3D_FAIL_FULL",
        "lookahead_days": 3,
        "min_close_mfe": 0.03,
        "max_eval_return": 0.00,
        "exit_pct": 1.0,
        "description": "after 3 trading days, if no +3% close MFE and eval close <= entry, exit full",
    },
    {
        "variant": "D1_3D_FAIL_HALF",
        "lookahead_days": 3,
        "min_close_mfe": 0.03,
        "max_eval_return": 0.00,
        "exit_pct": 0.5,
        "description": "after 3 trading days, if no +3% close MFE and eval close <= entry, exit half",
    },
    {
        "variant": "D1_5D_FAIL_FULL",
        "lookahead_days": 5,
        "min_close_mfe": 0.05,
        "max_eval_return": 0.00,
        "exit_pct": 1.0,
        "description": "after 5 trading days, if no +5% close MFE and eval close <= entry, exit full",
    },
    {
        "variant": "D1_5D_FAIL_HALF",
        "lookahead_days": 5,
        "min_close_mfe": 0.05,
        "max_eval_return": 0.00,
        "exit_pct": 0.5,
        "description": "after 5 trading days, if no +5% close MFE and eval close <= entry, exit half",
    },
    {
        "variant": "D1_10D_WEAK_FULL",
        "lookahead_days": 10,
        "min_close_mfe": 0.08,
        "max_eval_return": 0.02,
        "exit_pct": 1.0,
        "description": "after 10 trading days, if no +8% close MFE and eval close <= +2%, exit full",
    },
    {
        "variant": "D1_10D_WEAK_HALF",
        "lookahead_days": 10,
        "min_close_mfe": 0.08,
        "max_eval_return": 0.02,
        "exit_pct": 0.5,
        "description": "after 10 trading days, if no +8% close MFE and eval close <= +2%, exit half",
    },
]


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


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
    eval_return = eval_close / entry_close - 1.0
    failed = (
        close_mfe_until_eval is not None
        and close_mfe_until_eval < float(variant["min_close_mfe"])
        and eval_return <= float(variant["max_eval_return"])
    )
    if not failed:
        return {
            "counterfactual_active_bool": False,
            "shadow_reason": "confirmation_passed",
            "eval_trading_day": lookahead,
            "eval_date": pd.Timestamp(series.iloc[eval_idx]["date"]).strftime("%Y-%m-%d"),
            "eval_return": eval_return,
            "close_mfe_until_eval": close_mfe_until_eval,
        }

    exit_pct = float(variant["exit_pct"])
    sell_net_proceeds = _safe_float(row.get("sell_net_proceeds")) or 0.0
    early_vs_original_exit_ret = eval_close / original_exit_close - 1.0
    delta_pnl = sell_net_proceeds * exit_pct * early_vs_original_exit_ret
    return {
        "counterfactual_active_bool": True,
        "shadow_reason": "confirmation_failed_exit",
        "eval_trading_day": lookahead,
        "eval_date": pd.Timestamp(series.iloc[eval_idx]["date"]).strftime("%Y-%m-%d"),
        "eval_return": eval_return,
        "close_mfe_until_eval": close_mfe_until_eval,
        "early_vs_original_exit_ret": early_vs_original_exit_ret,
        "exit_pct": exit_pct,
        "delta_pnl": float(delta_pnl),
        "hypothetical_realized_pnl": (_safe_float(row.get("realized_pnl")) or 0.0) + float(delta_pnl),
        "original_exit_date": pd.Timestamp(series.iloc[exit_idx]["date"]).strftime("%Y-%m-%d"),
        "original_exit_return_from_entry_adj": original_exit_close / entry_close - 1.0,
    }


def _load_base() -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, Any]]:
    closed = _assign_groups(_load_inputs())
    min_date = (closed["entry_date"].min() - pd.Timedelta(days=80)).strftime("%Y-%m-%d")
    max_date = (closed["exit_date"].max() + pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    symbols = sorted(closed["symbol"].dropna().astype(str).str.lower().unique().tolist())
    ohlcv = _load_ohlcv(symbols, min_date, max_date)
    audit = {
        "baseline_id": BASELINE_ID,
        "closed_trades": int(len(closed)),
        "symbols_requested": int(len(symbols)),
        "symbols_loaded": int(ohlcv["symbol"].nunique()) if not ohlcv.empty else 0,
        "ohlcv_rows": int(len(ohlcv)),
        "min_query_date": min_date,
        "max_query_date": max_date,
        "source_prices": "public.pams_ohlcv_daily_v2 adjusted OHLCV",
        "source_candidates": str(STOCK_EXP_DIR / "candidate_signals.csv"),
    }
    return closed, _series_map(ohlcv), audit


def _build_detail(closed: pd.DataFrame, series_map: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for variant in VARIANTS:
        rows = [_counterfactual(row, series_map, variant) for _, row in closed.iterrows()]
        frame = pd.concat([closed.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
        frame["variant"] = variant["variant"]
        frame["variant_description"] = variant["description"]
        frame["lookahead_days"] = int(variant["lookahead_days"])
        frame["min_close_mfe_threshold"] = float(variant["min_close_mfe"])
        frame["max_eval_return_threshold"] = float(variant["max_eval_return"])
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
        avg_early_vs_original_exit_ret=("early_vs_original_exit_ret", "mean"),
    ).reset_index()


def _make_summaries(detail: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "variant_summary": _summary_group(detail, ["variant"]),
        "group_summary": _summary_group(detail, ["variant", "analysis_group"]),
        "exit_reason_summary": _summary_group(detail, ["variant", "exit_reason_code"]),
        "group_exit_reason_summary": _summary_group(detail, ["variant", "analysis_group", "exit_reason_code"]),
        "c2_verdict_summary": _summary_group(detail, ["variant", "c2_verdict"]),
        "reason_summary": _summary_group(detail, ["variant", "shadow_reason"]),
    }


def _write_report(detail: pd.DataFrame, summaries: dict[str, pd.DataFrame], out_dir: Path, audit: dict[str, Any]) -> None:
    variant_summary = summaries["variant_summary"].sort_values("delta_pnl", ascending=False)
    group_summary = summaries["group_summary"]
    best = variant_summary.iloc[0] if not variant_summary.empty else None
    lines: list[str] = []
    lines.append("# D1 买入后确认失败 Shadow")
    lines.append("")
    lines.append("## 结论")
    lines.append("- D1 是 read-only shadow，不改 V3 baseline、NAV、买卖规则或 runtime。")
    lines.append("- 触发只使用买入后 3/5/10 个交易日内已经可见的个股收盘路径，不使用主题、行业指数或卖后结果。")
    if best is not None:
        lines.append(
            f"- 当前最优变体 `{best['variant']}`：active={int(best['active_rows'])}，"
            f"delta_pnl={_fmt_money(best['delta_pnl'])}，improved={int(best['improved_rows'])}，worsened={int(best['worsened_rows'])}。"
        )
    lines.append("")
    lines.append("## Variant Summary")
    lines.append("|variant|active|delta_pnl|improved|worsened|avg_eval_ret|avg_mfe_until_eval|avg_early_vs_original_exit|")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in variant_summary.itertuples(index=False):
        lines.append(
            f"|{row.variant}|{int(row.active_rows)}|{_fmt_money(row.delta_pnl)}|{int(row.improved_rows)}|"
            f"{int(row.worsened_rows)}|{_fmt_pct(row.avg_eval_return)}|{_fmt_pct(row.avg_close_mfe_until_eval)}|"
            f"{_fmt_pct(row.avg_early_vs_original_exit_ret)}|"
        )
    lines.append("")
    lines.append("## TOP30 分组")
    lines.append("|variant|group|active|delta_pnl|improved|worsened|avg_early_vs_original_exit|")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    focus = group_summary.loc[group_summary["analysis_group"].isin(["profit_top30", "loss_top30"])].copy()
    for row in focus.sort_values(["variant", "analysis_group"]).itertuples(index=False):
        lines.append(
            f"|{row.variant}|{row.analysis_group}|{int(row.active_rows)}|{_fmt_money(row.delta_pnl)}|"
            f"{int(row.improved_rows)}|{int(row.worsened_rows)}|{_fmt_pct(row.avg_early_vs_original_exit_ret)}|"
        )
    lines.append("")
    lines.append("## 退出原因分组")
    lines.append("|variant|group|exit_reason|active|delta_pnl|improved|worsened|")
    lines.append("|---|---|---|---:|---:|---:|---:|")
    ge = summaries["group_exit_reason_summary"]
    focus_ge = ge.loc[ge["analysis_group"].isin(["profit_top30", "loss_top30"])].copy()
    for row in focus_ge.sort_values(["variant", "analysis_group", "delta_pnl"]).itertuples(index=False):
        lines.append(
            f"|{row.variant}|{row.analysis_group}|{row.exit_reason_code}|{int(row.active_rows)}|{_fmt_money(row.delta_pnl)}|"
            f"{int(row.improved_rows)}|{int(row.worsened_rows)}|"
        )
    lines.append("")
    lines.append("## 数据审计")
    lines.append("```json")
    lines.append(json.dumps(audit, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## 决策")
    lines.append("- 若 D1 改善亏损 TOP30 但明显伤害盈利 TOP30，应优先考虑半仓/预算缩减，不做全卖。")
    lines.append("- 若 D1 全局为正且盈利 TOP30 损伤可控，再设计 Docker runtime AB。")
    lines.append("- 这轮仍是交易级反事实，没有模拟现金再投资。")
    human_dir = out_dir / "human"
    human_dir.mkdir(parents=True, exist_ok=True)
    (human_dir / "d1_post_entry_confirmation_shadow.md").write_text("\n".join(lines), encoding="utf-8")


def _write_journal(summary: dict[str, Any]) -> None:
    now = summary["generated_at"]
    journal = {
        "round_id": ROUND_ID,
        "title": "V3 D1 买入后确认失败 Shadow",
        "status": "audited",
        "study_id": STUDY_ID,
        "asset_scope": "cn_stock_etf",
        "baseline_id": BASELINE_ID,
        "primary_question": "突破买入后 3/5/10 日没有确认时，提前退出或减半是否能降低亏损且不显著伤害盈利 TOP30？",
        "primary_variable": "post-entry confirmation failure trade-level counterfactual",
        "fixed_assumptions": [
            "CN_STOCK_ETF_COMBO_BASELINE_V3 fixed",
            "stock_alpha_core closed trades only; ETF sleeve excluded",
            "no runtime, NAV, signal, pool, ranking, execution, or exit-rule changes",
            "trigger uses only post-entry individual stock path available at the evaluation date",
        ],
        "windows": ["2012-2026"],
        "variants": [item["variant"] for item in VARIANTS],
        "evidence": [
            {
                "kind": "report",
                "study_id": STUDY_ID,
                "window_key": "1226",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "human" / "d1_post_entry_confirmation_shadow.md"),
                "note": "human D1 post-entry confirmation shadow report",
                "linked_at": now,
            },
            {
                "kind": "table",
                "study_id": STUDY_ID,
                "window_key": "1226",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "machine" / "d1_trade_detail.csv"),
                "note": "per-trade D1 counterfactual detail",
                "linked_at": now,
            },
        ],
        "key_findings": summary.get("key_findings", []),
        "audit": {
            "source_artifact_checked": True,
            "db_price_lineage_checked": True,
            "read_only_shadow": True,
        },
        "decision": summary.get("decision", {}),
        "next_actions": [
            "Inspect active rows that damage profit TOP30.",
            "If half-exit is robust, convert only the best variant to a Docker AB proposal.",
            "Keep D1 separate from theme/industry research.",
        ],
        "tags": ["cn_stock_etf", "V3", "D1", "post-entry-confirmation", "shadow", "research-only"],
        "schema_version": "openclaw_study_round@1",
        "created_at": now,
        "updated_at": now,
    }
    path = _abs(JOURNAL_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")


def run() -> dict[str, Any]:
    out_dir = _abs(OUT_DIR)
    machine_dir = out_dir / "machine"
    machine_dir.mkdir(parents=True, exist_ok=True)

    closed, maps, audit = _load_base()
    detail = _build_detail(closed, maps)
    summaries = _make_summaries(detail)
    detail.to_csv(machine_dir / "d1_trade_detail.csv", index=False, encoding="utf-8-sig")
    for name, frame in summaries.items():
        frame.to_csv(machine_dir / f"d1_{name}.csv", index=False, encoding="utf-8-sig")

    variant_summary = summaries["variant_summary"].sort_values("delta_pnl", ascending=False)
    best = variant_summary.iloc[0].to_dict() if not variant_summary.empty else {}
    best_delta = _safe_float(best.get("delta_pnl")) or 0.0
    decision = (
        {
            "status": "continue",
            "reason": "Best D1 shadow variant is positive at trade level; inspect concentration and profit TOP30 damage before Docker AB.",
        }
        if best_delta > 0
        else {
            "status": "reject",
            "reason": "Best D1 shadow variant is non-positive at trade level; do not promote.",
        }
    )
    summary = {
        "round_id": ROUND_ID,
        "study_id": STUDY_ID,
        "baseline_id": BASELINE_ID,
        "variant_name": VARIANT_NAME,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "read-only post-entry confirmation failure shadow over V3 stock closed trades",
        "best_variant": best,
        "decision": decision,
        "audit": audit,
        "key_findings": [
            f"Best variant: {best.get('variant')} delta={_fmt_money(best.get('delta_pnl'))}, active={best.get('active_rows')}.",
            "D1 trigger uses no theme, no industry index, and no post-exit future information.",
            "Trade-level counterfactual does not model cash redeployment.",
        ],
        "outputs": {
            "report": str(OUT_DIR / "human" / "d1_post_entry_confirmation_shadow.md"),
            "detail": str(OUT_DIR / "machine" / "d1_trade_detail.csv"),
            "variant_summary": str(OUT_DIR / "machine" / "d1_variant_summary.csv"),
            "journal": str(JOURNAL_PATH),
        },
    }
    (machine_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(detail, summaries, out_dir, audit)
    _write_journal(summary)
    return summary


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "round_id": result["round_id"],
                "study_id": result["study_id"],
                "baseline_id": result["baseline_id"],
                "best_variant": result["best_variant"],
                "decision": result["decision"],
                "outputs": result["outputs"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
