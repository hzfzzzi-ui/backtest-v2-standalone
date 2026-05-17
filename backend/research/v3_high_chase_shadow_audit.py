from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from backend.research.v3_d0_trade_path_morphology_audit import (
    BASELINE_ID,
    _abs,
    _fmt_money,
    _fmt_pct,
    _safe_float,
)


ROUND_ID = "sr_20260511_v3_high_chase_shadow_audit"
STUDY_ID = "cn_stock_etf/v3_high_chase_shadow_audit_v1"
VARIANT_NAME = "HIGH_CHASE_SHADOW_AUDIT"
SOURCE_D0_DIR = Path("outputs/studies/cn_stock_etf/sr_20260511_v3_d0_trade_path_morphology_audit")
SOURCE_D5_DIR = Path("outputs/studies/cn_stock_etf/sr_20260511_v3_d5_mfe_mae_confirmation_shadow")
OUT_DIR = Path("outputs/studies/cn_stock_etf") / ROUND_ID
JOURNAL_PATH = Path("research/study_journal/rounds") / f"{ROUND_ID}.json"

HIGHER_WORSE_Q80_COLS = [
    "pre_entry_ret5",
    "pre_entry_ret10",
    "stock_pre_entry_20d_return",
    "entry_close_vs_prev_ma20",
    "entry_close_vs_prev_ma60",
    "entry_atr14_extension",
    "breakout_margin_raw",
    "breakout_open_gap_raw",
    "breakout_fade_raw",
]
LOWER_WORSE_Q20_COLS = ["breakout_quality_score", "volume_price_quality_score"]
NUMERIC_COLS = sorted(
    set(
        HIGHER_WORSE_Q80_COLS
        + LOWER_WORSE_Q20_COLS
        + [
            "realized_pnl",
            "realized_return",
            "buy_net_cost",
            "sell_net_proceeds",
            "close_mfe",
            "close_mae",
            "high_mfe",
            "low_mae",
            "entry_volume_ratio_5v20",
            "entry_turnover_ratio_5v20",
            "breakout_quality_score",
            "volume_price_quality_score",
            "final_score_rank",
            "hold_calendar_days",
        ]
    )
)


def _read_d0_detail() -> pd.DataFrame:
    path = _abs(SOURCE_D0_DIR / "machine" / "d0_trade_path_detail.csv")
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    for col in ["entry_date", "exit_date"]:
        frame[col] = pd.to_datetime(frame[col], errors="coerce")
    frame["symbol"] = frame["symbol"].astype(str).str.lower()
    for col in NUMERIC_COLS:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def _read_d5_3d() -> pd.DataFrame:
    path = _abs(SOURCE_D5_DIR / "machine" / "d5_trade_detail.csv")
    if not path.exists():
        return pd.DataFrame(columns=["trade_key"])
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    if frame.empty:
        return pd.DataFrame(columns=["trade_key"])
    frame = frame.loc[frame["variant"].eq("D5_3D_MFE2_MAE5_HALF")].copy()
    keep = [
        "trade_key",
        "counterfactual_active_bool",
        "eval_return",
        "close_mfe_until_eval",
        "close_mae_until_eval",
        "delta_pnl",
    ]
    frame = frame.loc[:, [col for col in keep if col in frame.columns]].copy()
    frame = frame.rename(
        columns={
            "counterfactual_active_bool": "d5_3d_fail_bool",
            "eval_return": "d5_3d_eval_return",
            "close_mfe_until_eval": "d5_3d_close_mfe",
            "close_mae_until_eval": "d5_3d_close_mae",
            "delta_pnl": "d5_3d_shadow_delta_pnl",
        }
    )
    for col in ["d5_3d_eval_return", "d5_3d_close_mfe", "d5_3d_close_mae", "d5_3d_shadow_delta_pnl"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["d5_3d_fail_bool"] = frame["d5_3d_fail_bool"].map(_safe_bool)
    return frame


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"true", "1", "yes"}


def _thresholds(frame: pd.DataFrame) -> dict[str, float | None]:
    values: dict[str, float | None] = {}
    for col in HIGHER_WORSE_Q80_COLS:
        values[f"{col}_q80"] = _safe_float(pd.to_numeric(frame.get(col), errors="coerce").quantile(0.80))
    for col in LOWER_WORSE_Q20_COLS:
        values[f"{col}_q20"] = _safe_float(pd.to_numeric(frame.get(col), errors="coerce").quantile(0.20))
    return values


def _ge(frame: pd.DataFrame, col: str, threshold: float | None) -> pd.Series:
    if threshold is None or col not in frame.columns:
        return pd.Series(False, index=frame.index)
    return pd.to_numeric(frame[col], errors="coerce").ge(threshold).fillna(False)


def _le(frame: pd.DataFrame, col: str, threshold: float | None) -> pd.Series:
    if threshold is None or col not in frame.columns:
        return pd.Series(False, index=frame.index)
    return pd.to_numeric(frame[col], errors="coerce").le(threshold).fillna(False)


def _reason_join(parts: list[str]) -> str:
    return ";".join([p for p in parts if p])


def _add_high_chase_labels(frame: pd.DataFrame, thresholds: dict[str, float | None]) -> pd.DataFrame:
    out = frame.copy()
    out["short_heat_bool"] = (
        _ge(out, "pre_entry_ret5", thresholds["pre_entry_ret5_q80"])
        | _ge(out, "pre_entry_ret10", thresholds["pre_entry_ret10_q80"])
        | _ge(out, "stock_pre_entry_20d_return", thresholds["stock_pre_entry_20d_return_q80"])
    )
    out["extension_heat_bool"] = (
        _ge(out, "entry_close_vs_prev_ma20", thresholds["entry_close_vs_prev_ma20_q80"])
        | _ge(out, "entry_close_vs_prev_ma60", thresholds["entry_close_vs_prev_ma60_q80"])
        | _ge(out, "entry_atr14_extension", thresholds["entry_atr14_extension_q80"])
    )
    out["breakout_stretch_bool"] = (
        _ge(out, "breakout_margin_raw", thresholds["breakout_margin_raw_q80"])
        | _ge(out, "breakout_open_gap_raw", thresholds["breakout_open_gap_raw_q80"])
    )
    out["weak_breakout_quality_bool"] = (
        _le(out, "breakout_quality_score", thresholds["breakout_quality_score_q20"])
        | _le(out, "volume_price_quality_score", thresholds["volume_price_quality_score_q20"])
        | _ge(out, "breakout_fade_raw", thresholds["breakout_fade_raw_q80"])
    )
    out["high_chase_core_count"] = (
        out["short_heat_bool"].astype(int)
        + out["extension_heat_bool"].astype(int)
        + out["breakout_stretch_bool"].astype(int)
    )
    out["high_chase_bool"] = out["high_chase_core_count"].ge(2)
    out["fragile_high_chase_bool"] = out["high_chase_bool"] & out["weak_breakout_quality_bool"]
    out["high_chase_label"] = "normal"
    out.loc[out["high_chase_core_count"].eq(1), "high_chase_label"] = "mild_chase"
    out.loc[out["high_chase_core_count"].ge(2), "high_chase_label"] = "high_chase"
    out.loc[
        out["high_chase_core_count"].eq(3) | (out["high_chase_bool"] & out["weak_breakout_quality_bool"]),
        "high_chase_label",
    ] = "extreme_chase"
    out["high_chase_d5_label"] = "non_high_no_d5_fail"
    d5_fail = out["d5_3d_fail_bool"].fillna(False).astype(bool)
    out.loc[out["high_chase_bool"] & d5_fail, "high_chase_d5_label"] = "high_chase_and_d5_fail"
    out.loc[out["high_chase_bool"] & ~d5_fail, "high_chase_d5_label"] = "high_chase_no_d5_fail"
    out.loc[~out["high_chase_bool"] & d5_fail, "high_chase_d5_label"] = "non_high_d5_fail"

    reason_rows: list[str] = []
    for row in out.itertuples(index=False):
        reason_rows.append(
            _reason_join(
                [
                    "short_heat" if bool(getattr(row, "short_heat_bool")) else "",
                    "extension_heat" if bool(getattr(row, "extension_heat_bool")) else "",
                    "breakout_stretch" if bool(getattr(row, "breakout_stretch_bool")) else "",
                    "weak_breakout_quality" if bool(getattr(row, "weak_breakout_quality_bool")) else "",
                    "d5_3d_fail" if bool(getattr(row, "d5_3d_fail_bool", False)) else "",
                ]
            )
        )
    out["high_chase_reasons"] = reason_rows
    return out


def _summary(frame: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    total_rows = float(len(frame))
    total_pnl = _safe_float(pd.to_numeric(frame["realized_pnl"], errors="coerce").sum()) or 0.0

    def _rate(mask: pd.Series) -> float:
        return float(mask.mean()) if len(mask) else 0.0

    grouped = frame.groupby(by, dropna=False)
    rows: list[dict[str, Any]] = []
    for keys, grp in grouped:
        if not isinstance(keys, tuple):
            keys = (keys,)
        payload = {col: value for col, value in zip(by, keys)}
        pnl = pd.to_numeric(grp["realized_pnl"], errors="coerce")
        realized_return = pd.to_numeric(grp["realized_return"], errors="coerce")
        payload.update(
            {
                "rows": int(len(grp)),
                "row_share": len(grp) / total_rows if total_rows else 0.0,
                "symbols": int(grp["symbol"].nunique()),
                "pnl_sum": float(pnl.sum()),
                "pnl_share": float(pnl.sum() / total_pnl) if total_pnl else None,
                "win_rate": _rate(grp["winner_bool"].astype(bool)),
                "median_realized_return": _safe_float(realized_return.median()),
                "avg_realized_return": _safe_float(realized_return.mean()),
                "median_close_mfe": _safe_float(pd.to_numeric(grp["close_mfe"], errors="coerce").median()),
                "median_close_mae": _safe_float(pd.to_numeric(grp["close_mae"], errors="coerce").median()),
                "median_pre_entry_ret5": _safe_float(pd.to_numeric(grp["pre_entry_ret5"], errors="coerce").median()),
                "median_pre_entry_ret10": _safe_float(pd.to_numeric(grp["pre_entry_ret10"], errors="coerce").median()),
                "median_pre_entry_ret20": _safe_float(pd.to_numeric(grp["stock_pre_entry_20d_return"], errors="coerce").median()),
                "median_entry_vs_ma20": _safe_float(pd.to_numeric(grp["entry_close_vs_prev_ma20"], errors="coerce").median()),
                "median_atr_extension": _safe_float(pd.to_numeric(grp["entry_atr14_extension"], errors="coerce").median()),
                "median_breakout_margin": _safe_float(pd.to_numeric(grp["breakout_margin_raw"], errors="coerce").median()),
                "median_breakout_gap": _safe_float(pd.to_numeric(grp["breakout_open_gap_raw"], errors="coerce").median()),
                "median_breakout_fade": _safe_float(pd.to_numeric(grp["breakout_fade_raw"], errors="coerce").median()),
                "median_breakout_quality": _safe_float(pd.to_numeric(grp["breakout_quality_score"], errors="coerce").median()),
                "median_volume_price_quality": _safe_float(pd.to_numeric(grp["volume_price_quality_score"], errors="coerce").median()),
                "d5_3d_fail_count": int(grp["d5_3d_fail_bool"].fillna(False).astype(bool).sum()),
                "d5_3d_fail_rate": _rate(grp["d5_3d_fail_bool"].fillna(False).astype(bool)),
                "loss_top30_count": int(grp["analysis_group"].eq("loss_top30").sum()),
                "profit_top30_count": int(grp["analysis_group"].eq("profit_top30").sum()),
            }
        )
        rows.append(payload)
    return pd.DataFrame(rows)


def _flag_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for flag in [
        "short_heat_bool",
        "extension_heat_bool",
        "breakout_stretch_bool",
        "weak_breakout_quality_bool",
        "high_chase_bool",
        "fragile_high_chase_bool",
        "d5_3d_fail_bool",
    ]:
        if flag not in frame.columns:
            continue
        for value, grp in frame.groupby(frame[flag].fillna(False).astype(bool)):
            pnl = pd.to_numeric(grp["realized_pnl"], errors="coerce")
            rows.append(
                {
                    "flag": flag,
                    "flag_value": bool(value),
                    "rows": int(len(grp)),
                    "pnl_sum": float(pnl.sum()),
                    "win_rate": float(grp["winner_bool"].astype(bool).mean()) if len(grp) else 0.0,
                    "loss_top30_count": int(grp["analysis_group"].eq("loss_top30").sum()),
                    "profit_top30_count": int(grp["analysis_group"].eq("profit_top30").sum()),
                    "d5_3d_fail_rate": float(grp["d5_3d_fail_bool"].fillna(False).astype(bool).mean()) if len(grp) else 0.0,
                    "median_close_mfe": _safe_float(pd.to_numeric(grp["close_mfe"], errors="coerce").median()),
                    "median_close_mae": _safe_float(pd.to_numeric(grp["close_mae"], errors="coerce").median()),
                }
            )
    return pd.DataFrame(rows)


def _coverage_payload(detail: pd.DataFrame) -> dict[str, Any]:
    loss = detail.loc[detail["analysis_group"].eq("loss_top30")].copy()
    profit = detail.loc[detail["analysis_group"].eq("profit_top30")].copy()

    def _share(frame: pd.DataFrame, mask_col: str) -> float:
        return float(frame[mask_col].fillna(False).astype(bool).mean()) if len(frame) else 0.0

    def _pnl(frame: pd.DataFrame, mask_col: str) -> float:
        return float(pd.to_numeric(frame.loc[frame[mask_col].fillna(False).astype(bool), "realized_pnl"], errors="coerce").sum())

    return {
        "loss_top30_high_chase_count": int(loss["high_chase_bool"].fillna(False).astype(bool).sum()),
        "loss_top30_high_chase_share": _share(loss, "high_chase_bool"),
        "profit_top30_high_chase_count": int(profit["high_chase_bool"].fillna(False).astype(bool).sum()),
        "profit_top30_high_chase_share": _share(profit, "high_chase_bool"),
        "loss_top30_fragile_high_chase_count": int(loss["fragile_high_chase_bool"].fillna(False).astype(bool).sum()),
        "loss_top30_fragile_high_chase_share": _share(loss, "fragile_high_chase_bool"),
        "profit_top30_fragile_high_chase_count": int(profit["fragile_high_chase_bool"].fillna(False).astype(bool).sum()),
        "profit_top30_fragile_high_chase_share": _share(profit, "fragile_high_chase_bool"),
        "loss_top30_high_chase_pnl": _pnl(loss, "high_chase_bool"),
        "profit_top30_high_chase_pnl": _pnl(profit, "high_chase_bool"),
        "loss_top30_high_chase_and_d5_fail_count": int(
            (loss["high_chase_bool"].fillna(False).astype(bool) & loss["d5_3d_fail_bool"].fillna(False).astype(bool)).sum()
        ),
        "profit_top30_high_chase_and_d5_fail_count": int(
            (profit["high_chase_bool"].fillna(False).astype(bool) & profit["d5_3d_fail_bool"].fillna(False).astype(bool)).sum()
        ),
    }


def _write_outputs(
    detail: pd.DataFrame,
    summaries: dict[str, pd.DataFrame],
    thresholds: dict[str, float | None],
    audit: dict[str, Any],
    coverage: dict[str, Any],
) -> dict[str, Any]:
    machine = OUT_DIR / "machine"
    human = OUT_DIR / "human"
    machine.mkdir(parents=True, exist_ok=True)
    human.mkdir(parents=True, exist_ok=True)

    detail.to_csv(machine / "high_chase_trade_detail.csv", index=False, encoding="utf-8-sig")
    for name, frame in summaries.items():
        frame.to_csv(machine / f"{name}.csv", index=False, encoding="utf-8-sig")
    (machine / "thresholds.json").write_text(json.dumps(thresholds, ensure_ascii=False, indent=2), encoding="utf-8")
    (machine / "coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")

    label_summary = summaries["label_summary"].sort_values("pnl_sum")
    group_label = summaries["group_label_summary"]
    d5_label = summaries["high_chase_d5_summary"].sort_values("pnl_sum")
    top30 = detail.loc[detail["analysis_group"].isin(["loss_top30", "profit_top30"])].copy()

    lines: list[str] = []
    lines.append("# High Chase Shadow Audit")
    lines.append("")
    lines.append("## 结论")
    lines.append("- 本轮是 read-only shadow audit，不改 V3 baseline、NAV、runtime、信号、排序、买入或卖出规则。")
    lines.append("- 追高本身不是稳定主因：loss TOP30 的 high_chase 占比为 "
                 f"{_fmt_pct(coverage['loss_top30_high_chase_share'])}，profit TOP30 为 "
                 f"{_fmt_pct(coverage['profit_top30_high_chase_share'])}，两边都高。")
    lines.append("- 更像风险主因的是“高追 + 买入后三日确认失败”：loss TOP30 命中 "
                 f"{coverage['loss_top30_high_chase_and_d5_fail_count']} 笔，profit TOP30 只命中 "
                 f"{coverage['profit_top30_high_chase_and_d5_fail_count']} 笔。")
    lines.append("- 不能把 high_chase 直接做禁买条件；它会同时挡掉大量盈利 TOP30。后续更适合研究降仓、watch 或延迟确认。")
    lines.append("")

    lines.append("## 标签定义")
    lines.append("- `short_heat`: pre-entry 5/10/20 日涨幅任一进入全样本 top20%。")
    lines.append("- `extension_heat`: 入场价相对 MA20/MA60 或 ATR extension 任一进入 top20%。")
    lines.append("- `breakout_stretch`: 突破幅度或跳空幅度任一进入 top20%。")
    lines.append("- `high_chase`: 上面三类至少命中两类。")
    lines.append("- `extreme_chase`: 三类全命中，或 high_chase 同时伴随弱突破质量。")
    lines.append("")

    lines.append("## 全部已闭合个股交易按追高标签拆分")
    lines.append("|label|rows|row_share|PnL|win_rate|median_ret|median_MFE|median_MAE|D5_fail_rate|loss_TOP30|profit_TOP30|")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in label_summary.itertuples(index=False):
        lines.append(
            f"|{row.high_chase_label}|{int(row.rows)}|{_fmt_pct(row.row_share)}|{_fmt_money(row.pnl_sum)}|"
            f"{_fmt_pct(row.win_rate)}|{_fmt_pct(row.median_realized_return)}|{_fmt_pct(row.median_close_mfe)}|"
            f"{_fmt_pct(row.median_close_mae)}|{_fmt_pct(row.d5_3d_fail_rate)}|"
            f"{int(row.loss_top30_count)}|{int(row.profit_top30_count)}|"
        )

    lines.append("")
    lines.append("## TOP30 标签覆盖")
    focus = group_label.loc[group_label["analysis_group"].isin(["loss_top30", "profit_top30"])].copy()
    lines.append("|group|label|rows|PnL|median_ret|median_MFE|median_MAE|D5_fail_rate|")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for row in focus.sort_values(["analysis_group", "high_chase_label"]).itertuples(index=False):
        lines.append(
            f"|{row.analysis_group}|{row.high_chase_label}|{int(row.rows)}|{_fmt_money(row.pnl_sum)}|"
            f"{_fmt_pct(row.median_realized_return)}|{_fmt_pct(row.median_close_mfe)}|"
            f"{_fmt_pct(row.median_close_mae)}|{_fmt_pct(row.d5_3d_fail_rate)}|"
        )

    lines.append("")
    lines.append("## 高追与 D5 失败交叉")
    lines.append("|label|rows|PnL|win_rate|median_MFE|median_MAE|loss_TOP30|profit_TOP30|")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in d5_label.itertuples(index=False):
        lines.append(
            f"|{row.high_chase_d5_label}|{int(row.rows)}|{_fmt_money(row.pnl_sum)}|{_fmt_pct(row.win_rate)}|"
            f"{_fmt_pct(row.median_close_mfe)}|{_fmt_pct(row.median_close_mae)}|"
            f"{int(row.loss_top30_count)}|{int(row.profit_top30_count)}|"
        )

    lines.append("")
    lines.append("## TOP30 明细")
    lines.append("|group|symbol|name|entry|exit|PnL|label|reasons|MFE|MAE|D5_fail|")
    lines.append("|---|---|---|---|---|---:|---|---|---:|---:|---|")
    for row in top30.sort_values(["analysis_group", "realized_pnl"]).itertuples(index=False):
        entry = pd.Timestamp(row.entry_date).strftime("%Y-%m-%d")
        exit_date = pd.Timestamp(row.exit_date).strftime("%Y-%m-%d")
        lines.append(
            f"|{row.analysis_group}|{row.symbol}|{getattr(row, 'name', '')}|{entry}|{exit_date}|"
            f"{_fmt_money(row.realized_pnl)}|{row.high_chase_label}|{row.high_chase_reasons or '-'}|"
            f"{_fmt_pct(row.close_mfe)}|{_fmt_pct(row.close_mae)}|{bool(row.d5_3d_fail_bool)}|"
        )

    lines.append("")
    lines.append("## 阈值审计")
    lines.append("```json")
    lines.append(json.dumps(thresholds, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## 数据审计")
    lines.append("```json")
    lines.append(json.dumps(audit, ensure_ascii=False, indent=2))
    lines.append("```")
    (human / "high_chase_shadow_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "report": str(OUT_DIR / "human" / "high_chase_shadow_audit.md"),
        "detail": str(OUT_DIR / "machine" / "high_chase_trade_detail.csv"),
        "label_summary": str(OUT_DIR / "machine" / "label_summary.csv"),
        "group_label_summary": str(OUT_DIR / "machine" / "group_label_summary.csv"),
        "high_chase_d5_summary": str(OUT_DIR / "machine" / "high_chase_d5_summary.csv"),
        "flag_summary": str(OUT_DIR / "machine" / "flag_summary.csv"),
        "thresholds": str(OUT_DIR / "machine" / "thresholds.json"),
        "coverage": str(OUT_DIR / "machine" / "coverage.json"),
    }


def _write_journal(audit: dict[str, Any], coverage: dict[str, Any], outputs: dict[str, Any]) -> None:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    journal = {
        "round_id": ROUND_ID,
        "title": "V3 High Chase 追高标签 Shadow Audit",
        "status": "audited",
        "study_id": STUDY_ID,
        "asset_scope": "cn_stock_etf",
        "baseline_id": BASELINE_ID,
        "primary_question": "追高标签是否能解释 V3 个股腿盈利 TOP30、亏损 TOP30 和全部已闭合买入样本的差异？",
        "primary_variable": "read-only high_chase labels over closed stock trades",
        "fixed_assumptions": [
            "CN_STOCK_ETF_COMBO_BASELINE_V3 fixed",
            "D0 closed stock trade reconstruction fixed",
            "D5 3D shadow output fixed for confirmation-failure cross split",
            "no runtime, NAV, signal, ranking, execution, exit, pool, stock, or ETF changes",
            "global quantile labels are post-hoc diagnostics and not deployable live thresholds",
        ],
        "windows": ["2012-2026"],
        "evidence": [
            {
                "kind": "report",
                "study_id": STUDY_ID,
                "window_key": "1226",
                "variant_name": VARIANT_NAME,
                "path": outputs["report"],
                "note": "human high chase shadow audit report",
                "linked_at": now,
            },
            {
                "kind": "table",
                "study_id": STUDY_ID,
                "window_key": "1226",
                "variant_name": VARIANT_NAME,
                "path": outputs["detail"],
                "note": "per-trade high chase label detail",
                "linked_at": now,
            },
        ],
        "key_findings": [
            (
                "High chase alone is not a clean loss cause: "
                f"loss TOP30 high_chase share={coverage['loss_top30_high_chase_share']:.4f}, "
                f"profit TOP30 high_chase share={coverage['profit_top30_high_chase_share']:.4f}."
            ),
            (
                "High chase plus D5 3D confirmation failure is more discriminative: "
                f"loss TOP30 count={coverage['loss_top30_high_chase_and_d5_fail_count']}, "
                f"profit TOP30 count={coverage['profit_top30_high_chase_and_d5_fail_count']}."
            ),
            "Do not use high_chase as a hard no-buy filter; study position sizing/watch/delayed confirmation instead.",
        ],
        "audit": audit,
        "decision": {
            "status": "continue",
            "reason": "追高不是单独主因，但追高叠加入场后确认失败值得进入下一轮 AB 设计。",
        },
        "next_actions": [
            "Design a High Chase + D5 failure watch/size-down AB, not a hard no-buy rule.",
            "Keep high_chase labels read-only until rolling/live-safe thresholds are specified.",
        ],
        "tags": ["cn_stock_etf", "V3", "high-chase", "shadow-audit", "profit-top30", "loss-top30", "research-only"],
        "schema_version": "openclaw_study_round@1",
        "created_at": now,
        "updated_at": now,
    }
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL_PATH.write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")


def run() -> dict[str, Any]:
    base = _read_d0_detail()
    d5 = _read_d5_3d()
    d5_keys = set(d5["trade_key"].dropna().astype(str).tolist()) if "trade_key" in d5.columns else set()
    detail = base.merge(d5, on="trade_key", how="left")
    detail["d5_3d_fail_bool"] = detail["d5_3d_fail_bool"].fillna(False).astype(bool)
    thresholds = _thresholds(detail)
    detail = _add_high_chase_labels(detail, thresholds)

    summaries = {
        "label_summary": _summary(detail, ["high_chase_label"]),
        "group_label_summary": _summary(detail, ["analysis_group", "high_chase_label"]),
        "high_chase_d5_summary": _summary(detail, ["high_chase_d5_label"]),
        "group_high_chase_d5_summary": _summary(detail, ["analysis_group", "high_chase_d5_label"]),
        "flag_summary": _flag_summary(detail),
    }
    coverage = _coverage_payload(detail)
    audit = {
        "baseline_id": BASELINE_ID,
        "source_d0_detail": str(SOURCE_D0_DIR / "machine" / "d0_trade_path_detail.csv"),
        "source_d5_detail": str(SOURCE_D5_DIR / "machine" / "d5_trade_detail.csv"),
        "closed_stock_trades": int(len(detail)),
        "symbols": int(detail["symbol"].nunique()),
        "profit_top30_rows": int(detail["analysis_group"].eq("profit_top30").sum()),
        "loss_top30_rows": int(detail["analysis_group"].eq("loss_top30").sum()),
        "d5_trade_keys_matched": int(detail["trade_key"].astype(str).isin(d5_keys).sum()),
        "d5_rows_with_eval_return": int(detail["d5_3d_eval_return"].notna().sum()) if "d5_3d_eval_return" in detail.columns else 0,
        "label_threshold_policy": "global closed-trade quantile, diagnostic-only",
        "high_chase_definition": "at least two of short_heat, extension_heat, breakout_stretch",
        "extreme_chase_definition": "all three high-chase families, or high_chase with weak breakout quality",
        "read_only_audit": True,
    }
    outputs = _write_outputs(detail, summaries, thresholds, audit, coverage)
    _write_journal(audit, coverage, outputs)
    return {
        "round_id": ROUND_ID,
        "study_id": STUDY_ID,
        "baseline_id": BASELINE_ID,
        "coverage": coverage,
        "outputs": {**outputs, "journal": str(JOURNAL_PATH)},
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
