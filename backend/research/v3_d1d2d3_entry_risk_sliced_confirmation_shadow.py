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
    _fmt_money,
    _fmt_pct,
    _idx_at_or_after,
    _safe_float,
)
from backend.research.v3_d1_post_entry_confirmation_shadow import (
    VARIANTS,
    _build_detail,
    _load_base,
    _summary_group,
)


ROUND_ID = "sr_20260511_v3_d1d2d3_entry_risk_sliced_confirmation_shadow"
STUDY_ID = "cn_stock_etf/v3_d1d2d3_entry_risk_sliced_confirmation_shadow_v1"
VARIANT_NAME = "D1D2D3_ENTRY_RISK_SLICED_CONFIRMATION_SHADOW"
OUT_DIR = Path("outputs/studies/cn_stock_etf") / ROUND_ID
JOURNAL_PATH = Path("research/study_journal/rounds") / f"{ROUND_ID}.json"

SLICE_DEFS = [
    {
        "analysis_id": "D1_LOW_QUALITY_BREAKOUT",
        "analysis_name": "D1 低质量突破",
        "label_col": "low_quality_breakout_bool",
        "description": "confirmation failure only applies when breakout quality/fade/volume-price evidence is weak",
    },
    {
        "analysis_id": "D2_HIGH_CHASE",
        "analysis_name": "D2 高追涨",
        "label_col": "high_chase_bool",
        "description": "confirmation failure only applies when entry has chase-style extension/gap/margin evidence",
    },
    {
        "analysis_id": "D3_WEAK_LIQUIDITY",
        "analysis_name": "D3 弱流动性",
        "label_col": "weak_liquidity_bool",
        "description": "confirmation failure only applies when entry liquidity/participation evidence is weak",
    },
]


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"true", "1", "yes"}


def _prior_mean(series: pd.DataFrame, end_idx_exclusive: int, col: str, lookback: int) -> float | None:
    start = max(0, end_idx_exclusive - lookback)
    if col not in series.columns:
        return None
    part = pd.to_numeric(series.iloc[start:end_idx_exclusive][col], errors="coerce").dropna()
    if part.empty:
        return None
    return float(part.mean())


def _trade_key(row: pd.Series) -> str:
    return (
        str(row.get("symbol") or "").lower()
        + "|"
        + pd.Timestamp(row.get("entry_date")).strftime("%Y-%m-%d")
        + "|"
        + pd.Timestamp(row.get("exit_date")).strftime("%Y-%m-%d")
        + "|"
        + str(row.get("qty"))
    )


def _entry_liquidity_features(closed: pd.DataFrame, series_map: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in closed.iterrows():
        symbol = str(row.get("symbol") or "").lower()
        payload: dict[str, Any] = {"trade_key": row.get("trade_key") or _trade_key(row)}
        series = series_map.get(symbol)
        if series is None or series.empty:
            payload["entry_liquidity_available_bool"] = False
            rows.append(payload)
            continue
        entry_idx = _idx_at_or_after(series, row.get("entry_date"))
        if entry_idx is None:
            payload["entry_liquidity_available_bool"] = False
            rows.append(payload)
            continue
        amount20 = _prior_mean(series, entry_idx, "turnover", 20)
        amount60 = _prior_mean(series, entry_idx, "turnover", 60)
        turn20 = _prior_mean(series, entry_idx, "turnover_rate", 20)
        buy_net_cost = _safe_float(row.get("buy_net_cost"))
        payload.update(
            {
                "entry_liquidity_available_bool": amount20 is not None or amount60 is not None or turn20 is not None,
                "entry_amount20": amount20,
                "entry_amount60": amount60,
                "entry_turnover_rate20": turn20,
                "entry_order_participation20": None
                if amount20 is None or amount20 <= 0 or buy_net_cost is None
                else buy_net_cost / amount20,
            }
        )
        rows.append(payload)
    return pd.DataFrame(rows)


def _add_entry_risk_labels(detail: pd.DataFrame, liquidity: pd.DataFrame) -> pd.DataFrame:
    frame = detail.merge(liquidity, on="trade_key", how="left")
    for col in [
        "breakout_quality_score",
        "volume_price_quality_score",
        "breakout_fade_raw",
        "breakout_margin_raw",
        "breakout_open_gap_raw",
        "stock_pre_entry_20d_return",
        "entry_amount20",
        "entry_amount60",
        "entry_turnover_rate20",
        "entry_order_participation20",
    ]:
        frame[col] = pd.to_numeric(frame.get(col), errors="coerce")

    frame["low_quality_breakout_bool"] = (
        (frame["breakout_quality_score"] <= 0.60)
        | (frame["volume_price_quality_score"] <= 0.30)
        | (frame["breakout_fade_raw"] >= 0.020)
    ).fillna(False)
    frame["low_quality_breakout_reasons"] = ""
    frame.loc[frame["breakout_quality_score"] <= 0.60, "low_quality_breakout_reasons"] += "quality<=0.60;"
    frame.loc[frame["volume_price_quality_score"] <= 0.30, "low_quality_breakout_reasons"] += "vp_quality<=0.30;"
    frame.loc[frame["breakout_fade_raw"] >= 0.020, "low_quality_breakout_reasons"] += "fade>=2%;"

    chase_flags = (
        (frame["stock_pre_entry_20d_return"] >= 0.12).astype(int)
        + (frame["breakout_margin_raw"] >= 0.04).astype(int)
        + (frame["breakout_open_gap_raw"] >= 0.02).astype(int)
    )
    frame["high_chase_bool"] = (chase_flags >= 2).fillna(False)
    frame["high_chase_flag_count"] = chase_flags
    frame["high_chase_reasons"] = ""
    frame.loc[frame["stock_pre_entry_20d_return"] >= 0.12, "high_chase_reasons"] += "pre20>=12%;"
    frame.loc[frame["breakout_margin_raw"] >= 0.04, "high_chase_reasons"] += "margin>=4%;"
    frame.loc[frame["breakout_open_gap_raw"] >= 0.02, "high_chase_reasons"] += "gap>=2%;"

    frame["weak_liquidity_bool"] = (
        (frame["entry_amount20"] < 200_000_000.0)
        | (frame["entry_turnover_rate20"] < 1.0)
        | (frame["entry_order_participation20"] > 0.005)
    ).fillna(False)
    frame["weak_liquidity_reasons"] = ""
    frame.loc[frame["entry_amount20"] < 200_000_000.0, "weak_liquidity_reasons"] += "amount20<2e8;"
    frame.loc[frame["entry_turnover_rate20"] < 1.0, "weak_liquidity_reasons"] += "turnover20<1%;"
    frame.loc[frame["entry_order_participation20"] > 0.005, "weak_liquidity_reasons"] += "participation20>0.5%;"

    return frame


def _slice_detail(labeled: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for spec in SLICE_DEFS:
        frame = labeled.copy()
        label = frame[spec["label_col"]].fillna(False).astype(bool)
        base_active = frame["counterfactual_active_bool"].map(_safe_bool)
        sliced_active = base_active & label
        frame["analysis_id"] = spec["analysis_id"]
        frame["analysis_name"] = spec["analysis_name"]
        frame["analysis_description"] = spec["description"]
        frame["slice_label_col"] = spec["label_col"]
        frame["base_confirmation_active_bool"] = base_active
        frame["entry_risk_slice_match_bool"] = label
        frame["counterfactual_active_bool"] = sliced_active
        original_pnl = pd.to_numeric(frame["realized_pnl"], errors="coerce")
        frame.loc[~sliced_active, "delta_pnl"] = 0.0
        frame["delta_pnl"] = pd.to_numeric(frame["delta_pnl"], errors="coerce").fillna(0.0)
        frame["hypothetical_realized_pnl"] = original_pnl + frame["delta_pnl"]
        frame.loc[base_active & ~label, "shadow_reason"] = "confirmation_failed_but_slice_not_matched"
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _make_summaries(detail: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "analysis_variant_summary": _summary_group(detail, ["analysis_id", "analysis_name", "variant"]),
        "analysis_group_summary": _summary_group(detail, ["analysis_id", "analysis_name", "variant", "analysis_group"]),
        "analysis_exit_reason_summary": _summary_group(detail, ["analysis_id", "analysis_name", "variant", "exit_reason_code"]),
        "analysis_group_exit_reason_summary": _summary_group(
            detail, ["analysis_id", "analysis_name", "variant", "analysis_group", "exit_reason_code"]
        ),
        "label_coverage_summary": _summary_group(detail, ["analysis_id", "analysis_name", "entry_risk_slice_match_bool"]),
        "reason_summary": _summary_group(detail, ["analysis_id", "analysis_name", "variant", "shadow_reason"]),
    }


def _best_by_analysis(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    return (
        summary.sort_values(["analysis_id", "delta_pnl"], ascending=[True, False])
        .groupby(["analysis_id", "analysis_name"], as_index=False)
        .head(1)
        .reset_index(drop=True)
    )


def _write_outputs(detail: pd.DataFrame, summaries: dict[str, pd.DataFrame], audit: dict[str, Any]) -> dict[str, Any]:
    machine = OUT_DIR / "machine"
    human = OUT_DIR / "human"
    machine.mkdir(parents=True, exist_ok=True)
    human.mkdir(parents=True, exist_ok=True)

    detail.to_csv(machine / "d1d2d3_trade_detail.csv", index=False, encoding="utf-8-sig")
    for name, frame in summaries.items():
        frame.to_csv(machine / f"{name}.csv", index=False, encoding="utf-8-sig")

    best = _best_by_analysis(summaries["analysis_variant_summary"])
    best.to_csv(machine / "best_by_analysis.csv", index=False, encoding="utf-8-sig")

    lines: list[str] = []
    lines.append("# D1D2D3 Entry Risk Sliced Confirmation Shadow")
    lines.append("")
    lines.append("## 结论")
    lines.append("- 本轮是 read-only shadow，不改 V3 baseline、NAV、runtime、信号或成交。")
    lines.append("- 三个分析只是在上一轮“买入后确认失败”母规则上分别叠加一个入场风险标签。")
    lines.append("- 触发条件只使用入场前/入场当时可见字段和买入后确认窗口内价格路径，不使用卖后走势。")
    lines.append("")
    lines.append("## Best By Analysis")
    lines.append("|analysis|best_variant|active|delta_pnl|improved|worsened|avg_eval_ret|avg_mfe_until_eval|")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for row in best.itertuples(index=False):
        lines.append(
            f"|{row.analysis_name}|{row.variant}|{int(row.active_rows)}|{_fmt_money(row.delta_pnl)}|"
            f"{int(row.improved_rows)}|{int(row.worsened_rows)}|{_fmt_pct(row.avg_eval_return)}|"
            f"{_fmt_pct(row.avg_close_mfe_until_eval)}|"
        )

    lines.append("")
    lines.append("## TOP30 Split")
    focus = summaries["analysis_group_summary"].loc[
        summaries["analysis_group_summary"]["analysis_group"].isin(["loss_top30", "profit_top30"])
    ].copy()
    lines.append("|analysis|variant|group|active|delta_pnl|improved|worsened|")
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for row in focus.sort_values(["analysis_id", "variant", "analysis_group"]).itertuples(index=False):
        lines.append(
            f"|{row.analysis_name}|{row.variant}|{row.analysis_group}|{int(row.active_rows)}|"
            f"{_fmt_money(row.delta_pnl)}|{int(row.improved_rows)}|{int(row.worsened_rows)}|"
        )

    lines.append("")
    lines.append("## 口径")
    lines.append("- D1 低质量突破：`breakout_quality_score <= 0.60` 或 `volume_price_quality_score <= 0.30` 或 `breakout_fade_raw >= 2%`。")
    lines.append("- D2 高追涨：`stock_pre_entry_20d_return >= 12%`、`breakout_margin_raw >= 4%`、`breakout_open_gap_raw >= 2%` 三项至少命中两项。")
    lines.append("- D3 弱流动性：`entry_amount20 < 2e8` 或 `entry_turnover_rate20 < 1%` 或 `buy_net_cost / entry_amount20 > 0.5%`。")
    lines.append("")
    lines.append("## 数据审计")
    lines.append("```json")
    lines.append(json.dumps(audit, ensure_ascii=False, indent=2))
    lines.append("```")
    (human / "d1d2d3_entry_risk_sliced_confirmation_shadow.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    decision_status = "reject"
    positive = best.loc[pd.to_numeric(best["delta_pnl"], errors="coerce") > 0].copy()
    if not positive.empty:
        decision_status = "continue"

    journal = {
        "round_id": ROUND_ID,
        "title": "V3 D1D2D3 入场风险拆分确认失败 Shadow",
        "status": "audited",
        "study_id": STUDY_ID,
        "asset_scope": "cn_stock_etf",
        "baseline_id": BASELINE_ID,
        "primary_question": "买入后确认失败规则是否只应作用于低质量突破、高追涨、弱流动性三类入场风险？",
        "primary_variable": "entry risk slice applied to post-entry confirmation failure shadow",
        "fixed_assumptions": [
            "CN_STOCK_ETF_COMBO_BASELINE_V3 fixed",
            "stock closed trades only; ETF sleeve excluded",
            "no runtime, NAV, signal, pool, ranking, execution, or exit-rule changes",
            "one slice label per analysis; no bundled filter used for decision",
        ],
        "windows": ["2012-2026"],
        "variants": [item["variant"] for item in VARIANTS],
        "analyses": SLICE_DEFS,
        "evidence": [
            {
                "kind": "report",
                "study_id": STUDY_ID,
                "window_key": "1226",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "human" / "d1d2d3_entry_risk_sliced_confirmation_shadow.md"),
                "note": "human D1D2D3 sliced confirmation shadow report",
                "linked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            {
                "kind": "table",
                "study_id": STUDY_ID,
                "window_key": "1226",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "machine" / "d1d2d3_trade_detail.csv"),
                "note": "per-trade D1D2D3 sliced counterfactual detail",
                "linked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
        ],
        "key_findings": [
            f"{row.analysis_id}: best={row.variant}, delta={_fmt_money(row.delta_pnl)}, active={int(row.active_rows)}"
            for row in best.itertuples(index=False)
        ],
        "audit": audit,
        "decision": {
            "status": decision_status,
            "reason": "At least one sliced confirmation-failure analysis is positive." if decision_status == "continue" else "No sliced analysis is positive.",
        },
        "next_actions": [
            "If a sliced analysis is positive, inspect profit TOP30 damage before Docker AB.",
            "Do not combine D1/D2/D3 until each single slice has a stable reason.",
        ],
        "tags": ["cn_stock_etf", "V3", "D1D2D3", "confirmation-failure", "entry-risk", "shadow", "research-only"],
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
        "best_by_analysis": best.to_dict(orient="records"),
        "decision": journal["decision"],
        "outputs": {
            "report": str(OUT_DIR / "human" / "d1d2d3_entry_risk_sliced_confirmation_shadow.md"),
            "detail": str(OUT_DIR / "machine" / "d1d2d3_trade_detail.csv"),
            "best_by_analysis": str(OUT_DIR / "machine" / "best_by_analysis.csv"),
            "journal": str(JOURNAL_PATH),
        },
    }


def run() -> dict[str, Any]:
    closed, series_map, audit = _load_base()
    base_detail = _build_detail(closed, series_map)
    liquidity = _entry_liquidity_features(closed, series_map)
    labeled = _add_entry_risk_labels(base_detail, liquidity)
    detail = _slice_detail(labeled)
    summaries = _make_summaries(detail)
    audit = {
        **audit,
        "source_parent_shadow": "outputs/studies/cn_stock_etf/sr_20260511_v3_d1_post_entry_confirmation_shadow",
        "source_candidates": str(STOCK_EXP_DIR / "candidate_signals.csv"),
        "read_only_shadow": True,
        "liquidity_field": "public.pams_ohlcv_daily_v2.turnover as amount proxy",
    }
    return _write_outputs(detail, summaries, audit)


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
