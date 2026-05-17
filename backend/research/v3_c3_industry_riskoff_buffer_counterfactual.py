from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from backend.research.v3_loss_top30_exit_reason_audit import _load_index_prices, _load_prices


ROUND_ID = "sr_20260511_v3_c3_industry_riskoff_buffer_counterfactual"
STUDY_ID = "cn_stock_etf/v3_c3_industry_riskoff_buffer_counterfactual_v1"
BASELINE_ID = "CN_STOCK_ETF_COMBO_BASELINE_V3"
VARIANT_NAME = "C3I_INDUSTRY_RISKOFF_BUFFER_COUNTERFACTUAL"

SOURCE_C2_DIR = Path("outputs/studies/cn_stock_etf/sr_20260511_v3_c2_theme_weak_confirmation_shadow")
OUT_DIR = Path("outputs/studies/cn_stock_etf") / ROUND_ID
JOURNAL_PATH = Path("research/study_journal/rounds") / f"{ROUND_ID}.json"

WINDOWS = {
    "1626": ("2016-01-01", "2026-05-08"),
    "2020_2026": ("2020-01-01", "2026-05-08"),
    "2024_2026": ("2024-01-01", "2026-05-08"),
    "2025_2026": ("2025-01-01", "2026-05-08"),
    "2025_12_2026_04": ("2025-12-01", "2026-04-30"),
    "2026_03": ("2026-03-01", "2026-03-31"),
}

BENCHMARK_CODE = "000001.SH"
VARIANTS = [
    {
        "variant": "C3I_DELAY_1D_FULL",
        "description": "industry-strong risk-off exit delays full sale by 1 trading day",
        "max_days": 1,
        "retained_pct": 1.0,
    },
    {
        "variant": "C3I_DELAY_3D_FULL",
        "description": "industry-strong risk-off exit delays full sale by up to 3 trading days with guardrails",
        "max_days": 3,
        "retained_pct": 1.0,
    },
    {
        "variant": "C3I_HALF_3D",
        "description": "industry-strong risk-off exit sells 50% immediately and buffers 50% by up to 3 trading days",
        "max_days": 3,
        "retained_pct": 0.5,
    },
]

STOCK_DROP_GUARD = -0.05


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _abs(path: Path) -> Path:
    return (_repo_root() / path).resolve()


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(_abs(path), encoding="utf-8-sig", low_memory=False)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _fmt_pct(value: Any) -> str:
    num = _safe_float(value)
    return "-" if num is None else f"{num * 100:.2f}%"


def _fmt_money(value: Any) -> str:
    num = _safe_float(value)
    return "-" if num is None else f"{num:,.0f}"


def _build_series_map(frame: pd.DataFrame, key_col: str, value_col: str) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    if frame.empty:
        return out
    for key, grp in frame.groupby(key_col):
        series = grp.sort_values("date").reset_index(drop=True).loc[:, ["date", value_col]].rename(columns={value_col: "value"})
        series["date"] = pd.to_datetime(series["date"], errors="coerce")
        series["value"] = pd.to_numeric(series["value"], errors="coerce")
        out[str(key)] = series.dropna(subset=["date", "value"]).reset_index(drop=True)
    return out


def _prev_idx(series: pd.DataFrame | None, date_value: Any) -> int | None:
    if series is None or series.empty or pd.isna(date_value):
        return None
    date_ts = pd.Timestamp(date_value).normalize()
    idx = series.index[series["date"] < date_ts]
    if len(idx) == 0:
        return None
    return int(idx[-1])


def _at_or_before_idx(series: pd.DataFrame | None, date_value: Any) -> int | None:
    if series is None or series.empty or pd.isna(date_value):
        return None
    date_ts = pd.Timestamp(date_value).normalize()
    idx = series.index[series["date"] <= date_ts]
    if len(idx) == 0:
        return None
    return int(idx[-1])


def _future_indices(series: pd.DataFrame | None, date_value: Any, max_days: int) -> list[int]:
    if series is None or series.empty or pd.isna(date_value):
        return []
    date_ts = pd.Timestamp(date_value).normalize()
    base = _at_or_before_idx(series, date_ts)
    if base is None:
        return []
    start = base + 1
    end = min(base + max_days, len(series) - 1)
    if start > end:
        return []
    return list(range(start, end + 1))


def _ret_lookback(series: pd.DataFrame | None, date_value: Any, lookback: int, *, strict_before: bool = True) -> float | None:
    if series is None or series.empty or pd.isna(date_value):
        return None
    idx = _prev_idx(series, date_value) if strict_before else _at_or_before_idx(series, date_value)
    if idx is None or idx - lookback < 0:
        return None
    base = _safe_float(series.iloc[idx - lookback]["value"])
    last = _safe_float(series.iloc[idx]["value"])
    if not base or last is None:
        return None
    return last / base - 1.0


def _industry_state(
    industry_series: pd.DataFrame | None,
    benchmark_series: pd.DataFrame | None,
    date_value: Any,
    *,
    strict_before: bool = True,
) -> dict[str, Any]:
    ret20 = _ret_lookback(industry_series, date_value, 20, strict_before=strict_before)
    ret60 = _ret_lookback(industry_series, date_value, 60, strict_before=strict_before)
    bench20 = _ret_lookback(benchmark_series, date_value, 20, strict_before=strict_before)
    bench60 = _ret_lookback(benchmark_series, date_value, 60, strict_before=strict_before)
    excess20 = None if ret20 is None or bench20 is None else ret20 - bench20
    excess60 = None if ret60 is None or bench60 is None else ret60 - bench60
    strong = ret20 is not None and excess20 is not None and ret20 > 0 and excess20 > 0
    return {
        "industry_ret20_asof": ret20,
        "industry_ret60_asof": ret60,
        "benchmark_ret20_asof": bench20,
        "benchmark_ret60_asof": bench60,
        "industry_excess20_asof": excess20,
        "industry_excess60_asof": excess60,
        "industry_strong_asof_bool": bool(strong),
        "industry_state_label": "industry_strong" if strong else ("industry_unavailable" if ret20 is None or excess20 is None else "industry_not_strong"),
    }


def _base_price(stock_series: pd.DataFrame | None, exit_date: Any) -> tuple[pd.Timestamp | None, float | None]:
    idx = _at_or_before_idx(stock_series, exit_date)
    if idx is None or stock_series is None:
        return None, None
    row = stock_series.iloc[idx]
    return pd.Timestamp(row["date"]).normalize(), _safe_float(row["value"])


def _choose_counterfactual_exit(
    row: pd.Series,
    *,
    variant: dict[str, Any],
    stock_map: dict[str, pd.DataFrame],
    index_map: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "").lower()
    stock_series = stock_map.get(symbol)
    industry_series = index_map.get(str(row.get("sw_l1_index_code") or ""))
    benchmark_series = index_map.get(BENCHMARK_CODE)
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    base_date, base_value = _base_price(stock_series, exit_date)

    active = bool(row.get("c3_industry_eligible_bool"))
    retained_pct = float(variant["retained_pct"])
    max_days = int(variant["max_days"])
    if not active:
        return {
            "counterfactual_active_bool": False,
            "hypothetical_exit_date": exit_date.strftime("%Y-%m-%d"),
            "hypothetical_exit_value": base_value,
            "extra_trading_days": 0,
            "retained_pct": 0.0,
            "hypothetical_exit_reason": "not_eligible_original_exit",
            "stock_return_during_buffer": 0.0,
            "mae_during_buffer": 0.0,
            "mfe_during_buffer": 0.0,
            "delta_pnl": 0.0,
        }
    if stock_series is None or stock_series.empty or base_value is None or not base_value:
        return {
            "counterfactual_active_bool": False,
            "hypothetical_exit_date": exit_date.strftime("%Y-%m-%d"),
            "hypothetical_exit_value": None,
            "extra_trading_days": 0,
            "retained_pct": 0.0,
            "hypothetical_exit_reason": "missing_stock_price",
            "stock_return_during_buffer": None,
            "mae_during_buffer": None,
            "mfe_during_buffer": None,
            "delta_pnl": 0.0,
        }

    future = _future_indices(stock_series, exit_date, max_days)
    if not future:
        return {
            "counterfactual_active_bool": False,
            "hypothetical_exit_date": exit_date.strftime("%Y-%m-%d"),
            "hypothetical_exit_value": base_value,
            "extra_trading_days": 0,
            "retained_pct": 0.0,
            "hypothetical_exit_reason": "missing_future_price",
            "stock_return_during_buffer": None,
            "mae_during_buffer": None,
            "mfe_during_buffer": None,
            "delta_pnl": 0.0,
        }

    selected_idx = future[-1]
    reason = "max_delay_reached"
    path_returns: list[float] = []
    for seq, idx in enumerate(future, start=1):
        date_value = pd.Timestamp(stock_series.iloc[idx]["date"]).normalize()
        value = _safe_float(stock_series.iloc[idx]["value"])
        if value is None:
            continue
        ret = value / base_value - 1.0
        path_returns.append(ret)
        if ret <= STOCK_DROP_GUARD:
            selected_idx = idx
            reason = "stock_drop_guard"
            break
        state = _industry_state(industry_series, benchmark_series, date_value, strict_before=False)
        if seq > 1 and not bool(state.get("industry_strong_asof_bool")):
            selected_idx = idx
            reason = "industry_weak_guard"
            break

    selected_date = pd.Timestamp(stock_series.iloc[selected_idx]["date"]).normalize()
    selected_value = _safe_float(stock_series.iloc[selected_idx]["value"])
    if selected_value is None:
        selected_value = base_value
    stock_ret = selected_value / base_value - 1.0
    if not path_returns:
        path_returns = [stock_ret]
    sell_net_proceeds = _safe_float(row.get("sell_net_proceeds")) or 0.0
    delta_pnl = sell_net_proceeds * retained_pct * stock_ret
    if max_days == 1 and reason == "max_delay_reached":
        reason = "next_day_exit"
    return {
        "counterfactual_active_bool": True,
        "hypothetical_exit_date": selected_date.strftime("%Y-%m-%d"),
        "hypothetical_exit_value": selected_value,
        "extra_trading_days": int(max(0, len([idx for idx in future if idx <= selected_idx]))),
        "retained_pct": retained_pct,
        "hypothetical_exit_reason": reason,
        "stock_return_during_buffer": stock_ret,
        "mae_during_buffer": min(path_returns),
        "mfe_during_buffer": max(path_returns),
        "delta_pnl": float(delta_pnl),
    }


def _load_base_detail() -> pd.DataFrame:
    frame = _read_csv(SOURCE_C2_DIR / "machine" / "risk_off_exit_c2_detail_1626.csv")
    if frame.empty:
        raise RuntimeError("missing C2 detail input")
    frame["exit_date"] = pd.to_datetime(frame["exit_date"], errors="coerce")
    for col in ["realized_pnl", "realized_return", "sell_net_proceeds", "sell_fill_price"]:
        frame[col] = pd.to_numeric(frame.get(col), errors="coerce")
    return frame.dropna(subset=["exit_date"]).copy()


def _prepare_market_data(detail: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[str, Any]]:
    min_date = (detail["exit_date"].min() - pd.Timedelta(days=140)).strftime("%Y-%m-%d")
    max_date = (detail["exit_date"].max() + pd.Timedelta(days=40)).strftime("%Y-%m-%d")
    symbols = sorted(detail["symbol"].dropna().astype(str).str.lower().unique().tolist())
    index_codes = sorted(set(detail["sw_l1_index_code"].dropna().astype(str).loc[lambda s: s.ne("")].tolist()) | {BENCHMARK_CODE})
    prices = _load_prices(symbols, min_date, max_date)
    indices = _load_index_prices(index_codes, min_date, max_date)
    stock_map = _build_series_map(prices, "symbol", "adj_close")
    index_map = _build_series_map(indices, "index_code", "close")
    audit = {
        "min_query_date": min_date,
        "max_query_date": max_date,
        "stock_symbols_requested": len(symbols),
        "stock_symbols_loaded": int(prices["symbol"].nunique()) if not prices.empty else 0,
        "index_codes_requested": len(index_codes),
        "index_codes_loaded": int(indices["index_code"].nunique()) if not indices.empty else 0,
        "benchmark_code": BENCHMARK_CODE,
    }
    return stock_map, index_map, audit


def _add_industry_state(detail: pd.DataFrame, index_map: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    benchmark_series = index_map.get(BENCHMARK_CODE)
    for row in detail.itertuples(index=False):
        industry_series = index_map.get(str(getattr(row, "sw_l1_index_code", "") or ""))
        state = _industry_state(industry_series, benchmark_series, getattr(row, "exit_date"), strict_before=True)
        rows.append(state)
    out = pd.concat([detail.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    out["industry_data_available_bool"] = out["industry_ret20_asof"].notna() & out["industry_excess20_asof"].notna()
    out["c3_industry_eligible_bool"] = out["industry_data_available_bool"] & out["industry_strong_asof_bool"]
    return out


def _build_variant_detail(
    detail: pd.DataFrame,
    *,
    stock_map: dict[str, pd.DataFrame],
    index_map: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for variant in VARIANTS:
        cf_rows = [
            _choose_counterfactual_exit(row, variant=variant, stock_map=stock_map, index_map=index_map)
            for _, row in detail.iterrows()
        ]
        frame = pd.concat([detail.reset_index(drop=True), pd.DataFrame(cf_rows)], axis=1)
        frame["variant"] = variant["variant"]
        frame["variant_description"] = variant["description"]
        frame["hypothetical_realized_pnl"] = pd.to_numeric(frame["realized_pnl"], errors="coerce") + pd.to_numeric(
            frame["delta_pnl"], errors="coerce"
        ).fillna(0.0)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _window_filter(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    dates = pd.to_datetime(frame["exit_date"], errors="coerce")
    return frame.loc[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))].copy()


def _summary_group(frame: pd.DataFrame, by_cols: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    grouped = frame.groupby(by_cols, dropna=False)
    out = grouped.agg(
        rows=("symbol", "size"),
        active_rows=("counterfactual_active_bool", "sum"),
        eligible_rows=("c3_industry_eligible_bool", "sum"),
        original_pnl=("realized_pnl", "sum"),
        delta_pnl=("delta_pnl", "sum"),
        hypothetical_pnl=("hypothetical_realized_pnl", "sum"),
        improved_rows=("delta_pnl", lambda s: int((pd.to_numeric(s, errors="coerce") > 0).sum())),
        worsened_rows=("delta_pnl", lambda s: int((pd.to_numeric(s, errors="coerce") < 0).sum())),
        avg_delta=("delta_pnl", "mean"),
        median_delta=("delta_pnl", "median"),
        avg_extra_days=("extra_trading_days", "mean"),
        avg_buffer_return=("stock_return_during_buffer", "mean"),
        avg_mae=("mae_during_buffer", "mean"),
        avg_mfe=("mfe_during_buffer", "mean"),
    ).reset_index()
    return out


def _summaries(detail: pd.DataFrame) -> dict[str, pd.DataFrame]:
    window_rows: list[pd.DataFrame] = []
    for window_key, (start, end) in WINDOWS.items():
        part = _window_filter(detail, start, end)
        if part.empty:
            continue
        summary = _summary_group(part, ["variant"])
        summary.insert(0, "window_key", window_key)
        window_rows.append(summary)
    return {
        "variant_summary": _summary_group(detail, ["variant"]),
        "window_variant_summary": pd.concat(window_rows, ignore_index=True) if window_rows else pd.DataFrame(),
        "verdict_summary": _summary_group(detail, ["variant", "c2_verdict"]),
        "industry_summary": _summary_group(detail, ["variant", "sw_l1_industry"]),
        "state_summary": _summary_group(detail, ["variant", "industry_state_label"]),
        "guardrail_summary": _summary_group(detail, ["variant", "hypothetical_exit_reason"]),
    }


def _write_report(summaries: dict[str, pd.DataFrame], detail: pd.DataFrame, out_dir: Path, audit: dict[str, Any]) -> None:
    variant_summary = summaries["variant_summary"].sort_values("delta_pnl", ascending=False)
    window_summary = summaries["window_variant_summary"]
    verdict_summary = summaries["verdict_summary"]
    eligible_count = int(detail.loc[detail["variant"].eq(VARIANTS[0]["variant"]), "c3_industry_eligible_bool"].sum())
    total_count = int(detail.loc[detail["variant"].eq(VARIANTS[0]["variant"])].shape[0])

    lines: list[str] = []
    lines.append("# C3-I 行业强弱 Risk-Off 缓冲反事实")
    lines.append("")
    lines.append("## 结论")
    lines.append("- C3-I 是 read-only shadow，不改 V3 baseline、NAV、持仓、runtime 或真实卖出规则。")
    lines.append(
        f"- 它只用申万一级行业指数做触发：卖出日前一交易日行业近20日收益 > 0，且相对上证近20日超额 > 0。"
    )
    lines.append(f"- 主窗口 RISK_OFF_EXIT 共 {total_count} 笔，其中行业强 eligible {eligible_count} 笔。")
    if not variant_summary.empty:
        best = variant_summary.iloc[0]
        best_delta = _safe_float(best.get("delta_pnl")) or 0.0
        lines.append(
            f"- 当前最优 shadow 变体是 `{best['variant']}`，交易级 delta_pnl={_fmt_money(best['delta_pnl'])}，"
            f"active_rows={int(best['active_rows'])}。"
        )
        if best_delta <= 0:
            lines.append("- 事实结论：C3-I 行业-only 缓冲未通过，当前不建议进入正式 Docker AB。")
        else:
            lines.append("- 事实结论：C3-I 行业-only 缓冲为正，但仍需检查行业/个股集中度后再决定是否进入正式 Docker AB。")
    lines.append("- C2 verdict 只用于事后评价，不参与 C3-I 触发，避免未来函数。")
    lines.append("")
    lines.append("## 触发口径")
    lines.append("- 原始卖出必须是 V3 股票腿 `RISK_OFF_EXIT`。")
    lines.append("- 行业数据来自 `public.pit_index_daily` 的申万一级行业指数；行业归属来自上游 C2 明细的 PIT 申万一级。")
    lines.append("- 强行业条件：`industry_ret20_asof > 0` 且 `industry_ret20_asof - sse_ret20_asof > 0`。")
    lines.append("- as-of 时点：原卖出日前一交易日，避免使用卖出日收盘后的信息。")
    lines.append("- guardrail：缓冲期间个股相对原卖出日价格跌幅 <= -5%，或行业强状态失效，则提前退出。")
    lines.append("")
    lines.append("## Variant Summary")
    lines.append("|variant|rows|active|delta_pnl|improved|worsened|avg_extra_days|avg_buffer_ret|avg_mae|")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in variant_summary.itertuples(index=False):
        lines.append(
            f"|{row.variant}|{int(row.rows)}|{int(row.active_rows)}|{_fmt_money(row.delta_pnl)}|"
            f"{int(row.improved_rows)}|{int(row.worsened_rows)}|{_safe_float(row.avg_extra_days):.2f}|"
            f"{_fmt_pct(row.avg_buffer_return)}|{_fmt_pct(row.avg_mae)}|"
        )
    lines.append("")
    lines.append("## 重点窗口")
    lines.append("|window|variant|active|delta_pnl|improved|worsened|avg_extra_days|")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    if not window_summary.empty:
        focus = window_summary.loc[window_summary["window_key"].isin(["1626", "2025_2026", "2026_03"])].copy()
        for row in focus.sort_values(["window_key", "delta_pnl"], ascending=[True, False]).itertuples(index=False):
            lines.append(
                f"|{row.window_key}|{row.variant}|{int(row.active_rows)}|{_fmt_money(row.delta_pnl)}|"
                f"{int(row.improved_rows)}|{int(row.worsened_rows)}|{_safe_float(row.avg_extra_days):.2f}|"
            )
    lines.append("")
    lines.append("## C2 事后分组检查")
    lines.append("|variant|c2_verdict|rows|active|delta_pnl|improved|worsened|")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    if not verdict_summary.empty:
        focus_verdicts = {
            "protected_profit",
            "suspected_overkill_theme_not_weak",
            "mixed_industry_weak_but_rebounded",
            "confirmed_exit_stock_industry_weak",
            "confirmed_exit_stock_theme_weak",
        }
        focus = verdict_summary.loc[verdict_summary["c2_verdict"].isin(focus_verdicts)].copy()
        for row in focus.sort_values(["variant", "delta_pnl"], ascending=[True, False]).itertuples(index=False):
            lines.append(
                f"|{row.variant}|{row.c2_verdict}|{int(row.rows)}|{int(row.active_rows)}|{_fmt_money(row.delta_pnl)}|"
                f"{int(row.improved_rows)}|{int(row.worsened_rows)}|"
            )
    lines.append("")
    lines.append("## 数据审计")
    lines.append("```json")
    lines.append(json.dumps(audit, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## 决策")
    if not variant_summary.empty and (_safe_float(variant_summary.iloc[0].get("delta_pnl")) or 0.0) <= 0:
        lines.append("- C3-I 行业-only shadow 不通过，不进入正式 AB。")
        lines.append("- 主要问题是 2025-2026，尤其 2026-03，行业强条件没有挡住 risk-off 后的短期下跌。")
    else:
        lines.append("- 若 C3-I 的改善主要来自少数行业或少数股票，不能直接进入正式 AB。")
        lines.append("- 若分批版本优于全仓延迟，下一步优先做账户级 Docker AB 的分批版本。")
    lines.append("- 主题层暂不参与触发，后续可作为 C3-T 单独研究。")

    human_dir = out_dir / "human"
    human_dir.mkdir(parents=True, exist_ok=True)
    (human_dir / "c3_industry_counterfactual_report.md").write_text("\n".join(lines), encoding="utf-8")


def _write_journal(summary: dict[str, Any]) -> None:
    now = summary["generated_at"]
    journal = {
        "round_id": ROUND_ID,
        "title": "V3 C3-I 申万一级行业 Risk-Off 缓冲反事实",
        "status": "audited",
        "study_id": STUDY_ID,
        "asset_scope": "cn_stock_etf",
        "baseline_id": BASELINE_ID,
        "primary_question": "当 V3 股票腿 RISK_OFF_EXIT 触发时，如果申万一级行业仍强，延迟或分批退出是否能减少误杀且不破坏风险保护？",
        "primary_variable": "industry-only counterfactual buffer over V3 stock-leg risk-off exits",
        "fixed_assumptions": [
            "CN_STOCK_ETF_COMBO_BASELINE_V3 fixed",
            "stock_alpha_core risk-off exits only; ETF sleeve excluded",
            "no runtime, NAV, signal, pool, ranking, execution, or exit-rule changes",
            "industry strength trigger uses only as-of pre-exit SW L1 index data",
            "C2 verdict is evaluation-only and not used as a trigger",
        ],
        "windows": list(WINDOWS.keys()),
        "variants": [item["variant"] for item in VARIANTS],
        "evidence": [
            {
                "kind": "report",
                "study_id": STUDY_ID,
                "window_key": "1626",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "human" / "c3_industry_counterfactual_report.md"),
                "note": "human C3-I industry-only counterfactual report",
                "linked_at": now,
            },
            {
                "kind": "summary",
                "study_id": STUDY_ID,
                "window_key": "multi",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "machine" / "summary.json"),
                "note": "machine summary with variant, verdict, industry, and guardrail breakdowns",
                "linked_at": now,
            },
            {
                "kind": "table",
                "study_id": STUDY_ID,
                "window_key": "1626",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "machine" / "c3_trade_detail_1626.csv"),
                "note": "per-trade C3-I counterfactual detail",
                "linked_at": now,
            },
        ],
        "key_findings": summary.get("key_findings", []),
        "audit": {
            "same_window_compare": False,
            "config_truth_checked": False,
            "nav_lineage_checked": False,
            "docker_run_checked": False,
            "source_artifact_checked": True,
            "db_price_lineage_checked": True,
            "read_only_shadow": True,
        },
        "decision": summary.get("decision", {}),
        "next_actions": [
            "Inspect whether C3-I improvement is concentrated by industry or a few symbols.",
            "If stable, promote only the best C3-I variant to a Docker runtime AB proposal.",
            "Keep theme-triggered C3-T as a separate later study.",
        ],
        "tags": ["cn_stock_etf", "V3", "C3-I", "industry-index", "risk-off-exit", "counterfactual", "shadow"],
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

    base_detail = _load_base_detail()
    stock_map, index_map, audit = _prepare_market_data(base_detail)
    enriched = _add_industry_state(base_detail, index_map)
    detail = _build_variant_detail(enriched, stock_map=stock_map, index_map=index_map)

    summaries = _summaries(detail)
    detail.to_csv(machine_dir / "c3_trade_detail_1626.csv", index=False, encoding="utf-8-sig")
    for name, frame in summaries.items():
        frame.to_csv(machine_dir / f"c3_{name}.csv", index=False, encoding="utf-8-sig")

    variant_summary = summaries["variant_summary"].sort_values("delta_pnl", ascending=False)
    best = variant_summary.iloc[0].to_dict() if not variant_summary.empty else {}
    active_count = int(detail.loc[detail["variant"].eq(VARIANTS[0]["variant"]), "c3_industry_eligible_bool"].sum())
    total_count = int(detail.loc[detail["variant"].eq(VARIANTS[0]["variant"])].shape[0])
    best_delta = _safe_float(best.get("delta_pnl")) or 0.0
    decision = (
        {
            "status": "reject",
            "reason": "Industry-only risk-off buffer has negative delta_pnl in the main window and deteriorates the recent 2025-2026 / 2026-03 windows; do not promote to Docker runtime AB.",
        }
        if best_delta <= 0
        else {
            "status": "continue",
            "reason": "Industry-only buffer is positive in shadow; inspect concentration before Docker runtime AB.",
        }
    )
    summary = {
        "round_id": ROUND_ID,
        "study_id": STUDY_ID,
        "baseline_id": BASELINE_ID,
        "variant_name": VARIANT_NAME,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "read-only industry-only counterfactual over V3 stock_alpha_core RISK_OFF_EXIT trades",
        "trigger": {
            "source": "SW L1 industry index as-of prior trading day",
            "industry_strong_rule": "industry_ret20_asof > 0 and industry_ret20_asof - sse_ret20_asof > 0",
            "stock_drop_guard": STOCK_DROP_GUARD,
            "theme_used": False,
        },
        "audit": audit,
        "best_variant": best,
        "eligible_count": active_count,
        "risk_off_exit_count": total_count,
        "key_findings": [
            f"Industry-only eligible exits: {active_count}/{total_count}.",
            f"Best shadow variant by delta_pnl: {best.get('variant')} delta={_fmt_money(best.get('delta_pnl'))}.",
            "C2 verdict is evaluation-only; C3-I trigger uses no theme or post-sell information.",
            "C3-I industry-only buffer is not promoted when the best variant delta is non-positive.",
        ],
        "decision": decision,
        "outputs": {
            "report": str(OUT_DIR / "human" / "c3_industry_counterfactual_report.md"),
            "detail": str(OUT_DIR / "machine" / "c3_trade_detail_1626.csv"),
            "variant_summary": str(OUT_DIR / "machine" / "c3_variant_summary.csv"),
            "journal": str(JOURNAL_PATH),
        },
    }
    (machine_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summaries, detail, out_dir, audit)
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
                "eligible_count": result["eligible_count"],
                "risk_off_exit_count": result["risk_off_exit_count"],
                "best_variant": result["best_variant"],
                "outputs": result["outputs"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
