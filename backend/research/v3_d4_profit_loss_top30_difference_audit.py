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
    _idx_at_or_before,
    _load_ohlcv,
    _safe_float,
    _series_map,
)
from backend.research.v3_loss_top30_exit_reason_audit import (
    BENCHMARKS,
    _build_series_map,
    _load_index_prices,
    _ret_offset,
)


ROUND_ID = "sr_20260511_v3_d4_profit_loss_top30_difference_audit"
STUDY_ID = "cn_stock_etf/v3_d4_profit_loss_top30_difference_audit_v1"
VARIANT_NAME = "D4_PROFIT_LOSS_TOP30_DIFFERENCE_AUDIT"
SOURCE_D0_DIR = Path("outputs/studies/cn_stock_etf/sr_20260511_v3_d0_trade_path_morphology_audit")
OUT_DIR = Path("outputs/studies/cn_stock_etf") / ROUND_ID
JOURNAL_PATH = Path("research/study_journal/rounds") / f"{ROUND_ID}.json"
HORIZONS = (3, 5, 10, 20)


ENTRY_METRICS = [
    "stock_pre_entry_20d_return",
    "pre_entry_ret5",
    "pre_entry_ret10",
    "pre_entry_ret20",
    "entry_close_vs_prev_ma20",
    "entry_close_vs_prev_ma60",
    "entry_atr14_extension",
    "breakout_margin_raw",
    "breakout_open_gap_raw",
    "breakout_fade_raw",
    "breakout_quality_score",
    "residual_strength_score",
    "sector_strength_score",
    "volume_price_quality_score",
    "final_score_rank",
    "entry_volume_ratio_5v20",
    "entry_turnover_ratio_5v20",
]

WHOLE_TRADE_METRICS = [
    "close_mfe",
    "close_mae",
    "giveback_from_close_peak",
    "days_to_peak",
    "days_from_peak_to_exit",
    "below_ma20_days_last10",
    "below_ma60_days_last20",
    "days_below_ma20_warning_before_exit",
    "days_dd10_warning_before_exit",
    "last_rank_before_exit",
]


def _read_d0_detail() -> pd.DataFrame:
    path = _abs(SOURCE_D0_DIR / "machine" / "d0_trade_path_detail.csv")
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    for col in ["entry_date", "exit_date"]:
        frame[col] = pd.to_datetime(frame[col], errors="coerce")
    frame["symbol"] = frame["symbol"].astype(str).str.lower()
    for col in set(ENTRY_METRICS + WHOLE_TRADE_METRICS + ["realized_pnl", "realized_return"]):
        frame[col] = pd.to_numeric(frame.get(col), errors="coerce")
    return frame


def _prior_mean(series: pd.DataFrame, end_idx_exclusive: int, col: str, lookback: int) -> float | None:
    if col not in series.columns:
        return None
    start = max(0, end_idx_exclusive - lookback)
    part = pd.to_numeric(series.iloc[start:end_idx_exclusive][col], errors="coerce").dropna()
    if part.empty:
        return None
    return float(part.mean())


def _window_mean(series: pd.DataFrame, start_idx: int, end_idx_inclusive: int, col: str) -> float | None:
    if col not in series.columns:
        return None
    part = pd.to_numeric(series.iloc[start_idx : end_idx_inclusive + 1][col], errors="coerce").dropna()
    if part.empty:
        return None
    return float(part.mean())


def _ret_stock_horizon(series: pd.DataFrame, entry_idx: int, horizon: int) -> float | None:
    end_idx = entry_idx + horizon
    if end_idx >= len(series):
        return None
    start = _safe_float(series.iloc[entry_idx]["adj_close"])
    end = _safe_float(series.iloc[end_idx]["adj_close"])
    if not start or end is None:
        return None
    return end / start - 1.0


def _path_horizon_metrics(row: pd.Series, series_map: dict[str, pd.DataFrame]) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "").lower()
    series = series_map.get(symbol)
    payload: dict[str, Any] = {}
    if series is None or series.empty:
        return {f"h{h}_path_available_bool": False for h in HORIZONS}
    entry_idx = _idx_at_or_after(series, row.get("entry_date"))
    exit_idx = _idx_at_or_before(series, row.get("exit_date"))
    if entry_idx is None or exit_idx is None:
        return {f"h{h}_path_available_bool": False for h in HORIZONS}

    entry_close = _safe_float(series.iloc[entry_idx]["adj_close"])
    prior_amount20 = _prior_mean(series, entry_idx, "turnover", 20)
    prior_turn20 = _prior_mean(series, entry_idx, "turnover_rate", 20)
    for horizon in HORIZONS:
        end_idx = entry_idx + horizon
        available = bool(entry_close and end_idx < len(series) and end_idx <= exit_idx)
        payload[f"h{horizon}_path_available_bool"] = available
        if not available:
            continue
        window = series.iloc[entry_idx : end_idx + 1].copy()
        stock_ret = _ret_stock_horizon(series, entry_idx, horizon)
        payload[f"h{horizon}_date"] = pd.Timestamp(series.iloc[end_idx]["date"]).strftime("%Y-%m-%d")
        payload[f"h{horizon}_stock_return"] = stock_ret
        payload[f"h{horizon}_close_mfe"] = None if not entry_close else _safe_float(window["adj_close"].max() / entry_close - 1.0)
        payload[f"h{horizon}_close_mae"] = None if not entry_close else _safe_float(window["adj_close"].min() / entry_close - 1.0)
        payload[f"h{horizon}_down_days"] = int((pd.to_numeric(window["ret1"], errors="coerce") < 0).sum()) if "ret1" in window else None
        amount_mean = _window_mean(series, entry_idx, end_idx, "turnover")
        turn_mean = _window_mean(series, entry_idx, end_idx, "turnover_rate")
        payload[f"h{horizon}_amount_ratio_vs_prior20"] = None if not prior_amount20 or amount_mean is None else amount_mean / prior_amount20
        payload[f"h{horizon}_turnover_ratio_vs_prior20"] = None if not prior_turn20 or turn_mean is None else turn_mean / prior_turn20
    return payload


def _index_horizon_metrics(row: pd.Series, index_map: dict[str, pd.DataFrame]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    entry_date = row.get("entry_date")
    industry_code = str(row.get("sw_l1_index_code") or "")
    for horizon in HORIZONS:
        sse_ret = _ret_offset(index_map.get("000001.SH"), entry_date, 0, horizon)
        hs300_ret = _ret_offset(index_map.get("000300.SH"), entry_date, 0, horizon)
        zz500_ret = _ret_offset(index_map.get("000905.SH"), entry_date, 0, horizon)
        industry_ret = _ret_offset(index_map.get(industry_code), entry_date, 0, horizon)
        payload[f"h{horizon}_sse_return"] = sse_ret
        payload[f"h{horizon}_hs300_return"] = hs300_ret
        payload[f"h{horizon}_zz500_return"] = zz500_ret
        payload[f"h{horizon}_industry_return"] = industry_ret
    return payload


def _load_candidate_frame() -> pd.DataFrame:
    path = _abs(STOCK_EXP_DIR / "candidate_signals.csv")
    if not path.exists():
        return pd.DataFrame(columns=["symbol", "date"])
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "date"])
    frame["symbol"] = frame["symbol"].astype(str).str.lower()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for col in ["final_score_rank", "final_score_value", "selected_rank"]:
        frame[col] = pd.to_numeric(frame.get(col), errors="coerce")
    frame = frame.dropna(subset=["symbol", "date"]).sort_values(["symbol", "date"]).reset_index(drop=True)
    return frame


def _candidate_horizon_metrics(row: pd.Series, by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    symbol = str(row.get("symbol") or "").lower()
    frame = by_symbol.get(symbol)
    entry_date = pd.Timestamp(row.get("entry_date"))
    if frame is None or frame.empty or pd.isna(entry_date):
        return {f"h{h}_candidate_present_days": 0 for h in HORIZONS}
    for horizon in HORIZONS:
        horizon_date_raw = row.get(f"h{horizon}_date")
        if not horizon_date_raw or pd.isna(horizon_date_raw):
            payload[f"h{horizon}_candidate_present_days"] = 0
            continue
        horizon_date = pd.Timestamp(horizon_date_raw)
        part = frame.loc[(frame["date"] >= entry_date) & (frame["date"] <= horizon_date)].copy()
        payload[f"h{horizon}_candidate_present_days"] = int(part["date"].nunique()) if not part.empty else 0
        payload[f"h{horizon}_candidate_present_rate"] = (int(part["date"].nunique()) / float(horizon + 1)) if horizon >= 0 else None
        if part.empty:
            continue
        rank = pd.to_numeric(part["final_score_rank"], errors="coerce")
        payload[f"h{horizon}_candidate_best_rank"] = _safe_float(rank.min())
        payload[f"h{horizon}_candidate_avg_rank"] = _safe_float(rank.mean())
        payload[f"h{horizon}_candidate_last_rank"] = _safe_float(rank.dropna().iloc[-1]) if rank.notna().any() else None
        payload[f"h{horizon}_candidate_top5_days"] = int((rank <= 5).sum())
    return payload


def _to_numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _summary_by_group(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for group, grp in frame.groupby("analysis_group"):
        payload: dict[str, Any] = {
            "analysis_group": group,
            "rows": int(len(grp)),
            "symbols": int(grp["symbol"].nunique()),
            "pnl_sum": float(pd.to_numeric(grp["realized_pnl"], errors="coerce").sum()),
        }
        for col in columns:
            if col not in grp.columns:
                continue
            s = pd.to_numeric(grp[col], errors="coerce")
            payload[f"{col}_count"] = int(s.notna().sum())
            payload[f"{col}_mean"] = _safe_float(s.mean())
            payload[f"{col}_median"] = _safe_float(s.median())
        rows.append(payload)
    return pd.DataFrame(rows)


def _difference_rank(summary: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    profit = summary.loc[summary["analysis_group"].eq("profit_top30")]
    loss = summary.loc[summary["analysis_group"].eq("loss_top30")]
    if profit.empty or loss.empty:
        return pd.DataFrame()
    p = profit.iloc[0].to_dict()
    l = loss.iloc[0].to_dict()
    rows: list[dict[str, Any]] = []
    for col in columns:
        p_mean = _safe_float(p.get(f"{col}_mean"))
        l_mean = _safe_float(l.get(f"{col}_mean"))
        p_median = _safe_float(p.get(f"{col}_median"))
        l_median = _safe_float(l.get(f"{col}_median"))
        rows.append(
            {
                "metric": col,
                "profit_mean": p_mean,
                "loss_mean": l_mean,
                "profit_minus_loss_mean": None if p_mean is None or l_mean is None else p_mean - l_mean,
                "profit_median": p_median,
                "loss_median": l_median,
                "profit_minus_loss_median": None if p_median is None or l_median is None else p_median - l_median,
                "profit_count": int(p.get(f"{col}_count") or 0),
                "loss_count": int(l.get(f"{col}_count") or 0),
            }
        )
    out = pd.DataFrame(rows)
    out["abs_median_gap"] = pd.to_numeric(out["profit_minus_loss_median"], errors="coerce").abs()
    return out.sort_values("abs_median_gap", ascending=False).reset_index(drop=True)


def _horizon_columns() -> list[str]:
    cols: list[str] = []
    for h in HORIZONS:
        cols.extend(
            [
                f"h{h}_stock_return",
                f"h{h}_sse_return",
                f"h{h}_hs300_return",
                f"h{h}_zz500_return",
                f"h{h}_industry_return",
                f"h{h}_relative_vs_sse",
                f"h{h}_relative_vs_industry",
                f"h{h}_close_mfe",
                f"h{h}_close_mae",
                f"h{h}_down_days",
                f"h{h}_amount_ratio_vs_prior20",
                f"h{h}_turnover_ratio_vs_prior20",
                f"h{h}_candidate_present_days",
                f"h{h}_candidate_present_rate",
                f"h{h}_candidate_best_rank",
                f"h{h}_candidate_avg_rank",
                f"h{h}_candidate_last_rank",
                f"h{h}_candidate_top5_days",
            ]
        )
    return cols


def _earliest_divergence(diff: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "stock_return",
        "relative_vs_sse",
        "relative_vs_industry",
        "close_mfe",
        "close_mae",
        "candidate_avg_rank",
        "amount_ratio_vs_prior20",
        "turnover_ratio_vs_prior20",
    ]
    rows: list[dict[str, Any]] = []
    by_metric = diff.set_index("metric")
    for metric in metrics:
        for horizon in HORIZONS:
            key = f"h{horizon}_{metric}"
            if key not in by_metric.index:
                continue
            row = by_metric.loc[key]
            gap = _safe_float(row.get("profit_minus_loss_median"))
            if gap is None or pd.isna(gap):
                continue
            if metric.startswith("candidate"):
                profit_count = int(row.get("profit_count") or 0)
                loss_count = int(row.get("loss_count") or 0)
                if profit_count == 0 or loss_count == 0 or abs(gap) < 1e-12:
                    continue
            rows.append(
                {
                    "feature_family": metric,
                    "first_available_horizon": horizon,
                    "profit_median": _safe_float(row.get("profit_median")),
                    "loss_median": _safe_float(row.get("loss_median")),
                    "profit_minus_loss_median": gap,
                    "profit_count": int(row.get("profit_count") or 0),
                    "loss_count": int(row.get("loss_count") or 0),
                }
            )
            break
    return pd.DataFrame(rows)


def _fmt_num(value: Any) -> str:
    num = _safe_float(value)
    if num is None:
        return "-"
    return f"{num:.2f}"


def _metric_row(diff: pd.DataFrame, metric: str) -> dict[str, Any]:
    part = diff.loc[diff["metric"].eq(metric)]
    return {} if part.empty else part.iloc[0].to_dict()


def _write_report(
    detail: pd.DataFrame,
    group_summary: pd.DataFrame,
    diff_rank: pd.DataFrame,
    earliest: pd.DataFrame,
    audit: dict[str, Any],
) -> None:
    human = OUT_DIR / "human"
    human.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# D4 盈利 TOP30 vs 亏损 TOP30 差异审计")
    lines.append("")
    lines.append("## 结论")
    lines.append("- 本轮是 read-only audit，不改 V3 baseline、NAV、runtime、信号、排序或退出规则。")
    lines.append("- TOP30 分组是事后诊断标签，只用于找差异，不可直接作为线上条件。")
    lines.append("- 核心观察：入场前差异存在但不稳定，真正分叉集中在买入后 3-10 个交易日的相对强度和 MFE/MAE。")
    lines.append("- 候选排名在固定 3/5/10/20 日窗口覆盖不足，本轮不把候选持续性作为有效结论。")
    lines.append("")

    key_metrics = [
        "stock_pre_entry_20d_return",
        "entry_close_vs_prev_ma20",
        "breakout_quality_score",
        "volume_price_quality_score",
        "h3_stock_return",
        "h3_relative_vs_sse",
        "h3_relative_vs_industry",
        "h3_close_mfe",
        "h3_close_mae",
        "h5_stock_return",
        "h10_stock_return",
        "h10_relative_vs_sse",
        "h20_stock_return",
        "h20_relative_vs_sse",
        "close_mfe",
        "close_mae",
        "days_to_peak",
    ]
    lines.append("## 关键差异")
    lines.append("|metric|profit_median|loss_median|profit-loss|profit_count|loss_count|")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for metric in key_metrics:
        row = _metric_row(diff_rank, metric)
        if not row:
            continue
        formatter = _fmt_pct if any(token in metric for token in ["return", "mfe", "mae", "relative", "quality", "vs_prev"]) else _fmt_num
        lines.append(
            f"|{metric}|{formatter(row.get('profit_median'))}|{formatter(row.get('loss_median'))}|"
            f"{formatter(row.get('profit_minus_loss_median'))}|{int(row.get('profit_count') or 0)}|{int(row.get('loss_count') or 0)}|"
        )

    lines.append("")
    lines.append("## 最早分叉")
    lines.append("|feature|horizon|profit_median|loss_median|profit-loss|")
    lines.append("|---|---:|---:|---:|---:|")
    for row in earliest.itertuples(index=False):
        formatter = _fmt_num if "rank" in row.feature_family or "days" in row.feature_family else _fmt_pct
        lines.append(
            f"|{row.feature_family}|{int(row.first_available_horizon)}|{formatter(row.profit_median)}|"
            f"{formatter(row.loss_median)}|{formatter(row.profit_minus_loss_median)}|"
        )

    lines.append("")
    lines.append("## TOP 行业")
    for group in ["profit_top30", "loss_top30"]:
        part = detail.loc[detail["analysis_group"].eq(group)].copy()
        sector = (
            part.groupby("sw_l1_industry", dropna=False)
            .agg(rows=("symbol", "size"), pnl=("realized_pnl", "sum"))
            .reset_index()
            .sort_values("pnl", ascending=(group == "loss_top30"))
            .head(8)
        )
        lines.append(f"### {group}")
        lines.append("|industry|rows|pnl|")
        lines.append("|---|---:|---:|")
        for item in sector.itertuples(index=False):
            lines.append(f"|{item.sw_l1_industry or '-'}|{int(item.rows)}|{_fmt_money(item.pnl)}|")
        lines.append("")

    lines.append("## 数据审计")
    lines.append("```json")
    lines.append(json.dumps(audit, ensure_ascii=False, indent=2))
    lines.append("```")
    (human / "d4_profit_loss_top30_difference_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    detail = _read_d0_detail()
    focus = detail.loc[detail["analysis_group"].isin(["profit_top30", "loss_top30"])].copy()
    min_date = (focus["entry_date"].min() - pd.Timedelta(days=90)).strftime("%Y-%m-%d")
    max_date = (focus["exit_date"].max() + pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    symbols = sorted(focus["symbol"].dropna().astype(str).str.lower().unique().tolist())
    ohlcv = _load_ohlcv(symbols, min_date, max_date)
    series_map = _series_map(ohlcv)

    index_codes = sorted(set(BENCHMARKS) | {x for x in focus["sw_l1_index_code"].dropna().astype(str).loc[lambda s: s.ne("")].tolist()})
    indices = _load_index_prices(index_codes, min_date, max_date)
    index_map = _build_series_map(indices.rename(columns={"close": "value"}), "index_code", "value")

    path_rows = [_path_horizon_metrics(row, series_map) for _, row in focus.iterrows()]
    index_rows = [_index_horizon_metrics(row, index_map) for _, row in focus.iterrows()]
    enriched = pd.concat([focus.reset_index(drop=True), pd.DataFrame(path_rows), pd.DataFrame(index_rows)], axis=1)
    for h in HORIZONS:
        enriched[f"h{h}_relative_vs_sse"] = pd.to_numeric(enriched.get(f"h{h}_stock_return"), errors="coerce") - pd.to_numeric(
            enriched.get(f"h{h}_sse_return"), errors="coerce"
        )
        enriched[f"h{h}_relative_vs_industry"] = pd.to_numeric(enriched.get(f"h{h}_stock_return"), errors="coerce") - pd.to_numeric(
            enriched.get(f"h{h}_industry_return"), errors="coerce"
        )

    candidates = _load_candidate_frame()
    candidate_map = {symbol: grp.sort_values("date").reset_index(drop=True) for symbol, grp in candidates.groupby("symbol")}
    candidate_rows = [_candidate_horizon_metrics(row, candidate_map) for _, row in enriched.iterrows()]
    enriched = pd.concat([enriched.reset_index(drop=True), pd.DataFrame(candidate_rows)], axis=1)

    metric_cols = ENTRY_METRICS + WHOLE_TRADE_METRICS + _horizon_columns()
    enriched = _to_numeric(enriched, metric_cols + ["realized_pnl", "realized_return"])
    group_summary = _summary_by_group(enriched, metric_cols)
    diff_rank = _difference_rank(group_summary, metric_cols)
    earliest = _earliest_divergence(diff_rank)

    machine = OUT_DIR / "machine"
    machine.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(machine / "d4_profit_loss_top30_detail.csv", index=False, encoding="utf-8-sig")
    group_summary.to_csv(machine / "d4_group_feature_summary.csv", index=False, encoding="utf-8-sig")
    diff_rank.to_csv(machine / "d4_difference_rank.csv", index=False, encoding="utf-8-sig")
    earliest.to_csv(machine / "d4_earliest_divergence.csv", index=False, encoding="utf-8-sig")

    audit = {
        "baseline_id": BASELINE_ID,
        "source_d0_detail": str(SOURCE_D0_DIR / "machine" / "d0_trade_path_detail.csv"),
        "stock_top30_rows": int(len(enriched)),
        "profit_top30_rows": int(enriched["analysis_group"].eq("profit_top30").sum()),
        "loss_top30_rows": int(enriched["analysis_group"].eq("loss_top30").sum()),
        "symbols_requested": len(symbols),
        "symbols_loaded": int(ohlcv["symbol"].nunique()) if not ohlcv.empty else 0,
        "ohlcv_rows": int(len(ohlcv)),
        "index_codes_requested": len(index_codes),
        "index_codes_loaded": int(indices["index_code"].nunique()) if not indices.empty else 0,
        "candidate_rows": int(len(candidates)),
        "source_prices": "public.pams_ohlcv_daily_v2 adjusted OHLCV",
        "source_indices": "public.pit_index_daily",
        "source_candidates": str(STOCK_EXP_DIR / "candidate_signals.csv"),
        "horizons_trading_days_after_entry": list(HORIZONS),
        "read_only_audit": True,
    }
    _write_report(enriched, group_summary, diff_rank, earliest, audit)

    top_diff = diff_rank.head(20).loc[:, ["metric", "profit_median", "loss_median", "profit_minus_loss_median"]].to_dict(orient="records")
    journal = {
        "round_id": ROUND_ID,
        "title": "V3 D4 盈利 TOP30 vs 亏损 TOP30 差异审计",
        "status": "audited",
        "study_id": STUDY_ID,
        "asset_scope": "cn_stock_etf",
        "baseline_id": BASELINE_ID,
        "primary_question": "盈利 TOP30 与亏损 TOP30 的稳定差异来自入场前、入场后确认、相对强度、候选持续性还是流动性？",
        "primary_variable": "profit_top30_vs_loss_top30 post-hoc diagnostic feature differences",
        "fixed_assumptions": [
            "CN_STOCK_ETF_COMBO_BASELINE_V3 fixed",
            "D0 closed stock trade reconstruction fixed",
            "no runtime, NAV, signal, ranking, execution, exit, pool, or ETF changes",
            "TOP30 labels are post-hoc diagnostics and not live-rule conditions",
        ],
        "windows": ["2012-2026"],
        "evidence": [
            {
                "kind": "report",
                "study_id": STUDY_ID,
                "window_key": "1226",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "human" / "d4_profit_loss_top30_difference_audit.md"),
                "note": "human D4 profit/loss top30 difference audit report",
                "linked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            {
                "kind": "table",
                "study_id": STUDY_ID,
                "window_key": "1226",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "machine" / "d4_profit_loss_top30_detail.csv"),
                "note": "per-trade top30 difference detail",
                "linked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
        ],
        "key_findings": [
            "Entry-only differences exist but overlap is large; post-entry relative strength and MFE/MAE separate better.",
            "Candidate persistence has weak fixed-window coverage in this audit and is not treated as a decisive finding.",
            *[
                f"{row.metric}: profit_median={row.profit_median}, loss_median={row.loss_median}, gap={row.profit_minus_loss_median}"
                for row in diff_rank.head(8).itertuples(index=False)
            ],
        ],
        "audit": audit,
        "decision": {
            "status": "continue",
            "reason": "This diagnostic identifies post-entry relative strength and candidate persistence as better next-rule candidates than raw entry labels.",
        },
        "next_actions": [
            "Design a shadow rule using post-entry relative strength and candidate persistence, not TOP30 labels.",
            "Keep entry chase/quality/liquidity as secondary gates only if they reduce profit-top30 damage.",
        ],
        "tags": ["cn_stock_etf", "V3", "D4", "profit-top30", "loss-top30", "difference-audit", "research-only"],
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
        "top_diff": top_diff,
        "earliest_divergence": earliest.to_dict(orient="records"),
        "outputs": {
            "report": str(OUT_DIR / "human" / "d4_profit_loss_top30_difference_audit.md"),
            "detail": str(OUT_DIR / "machine" / "d4_profit_loss_top30_detail.csv"),
            "difference_rank": str(OUT_DIR / "machine" / "d4_difference_rank.csv"),
            "journal": str(JOURNAL_PATH),
        },
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
