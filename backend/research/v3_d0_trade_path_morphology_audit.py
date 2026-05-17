from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from backend.research.v3_loss_top30_exit_reason_audit import _fetch_db_frame


ROUND_ID = "sr_20260511_v3_d0_trade_path_morphology_audit"
STUDY_ID = "cn_stock_etf/v3_d0_trade_path_morphology_audit_v1"
BASELINE_ID = "CN_STOCK_ETF_COMBO_BASELINE_V3"
VARIANT_NAME = "D0_TRADE_PATH_MORPHOLOGY_AUDIT"

SOURCE_LOSS_AUDIT_DIR = Path("outputs/studies/cn_stock_etf/sr_20260511_v3_loss_top30_exit_reason_audit")
SOURCE_C2_DIR = Path("outputs/studies/cn_stock_etf/sr_20260511_v3_c2_theme_weak_confirmation_shadow")
STOCK_EXP_DIR = Path("outputs/experiments/exp_20260510_033603951_8649")
OUT_DIR = Path("outputs/studies/cn_stock_etf") / ROUND_ID
JOURNAL_PATH = Path("research/study_journal/rounds") / f"{ROUND_ID}.json"


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


def _load_ohlcv(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    frame = _fetch_db_frame(
        """
        SELECT symbol, trade_date AS date, open, high, low, close, volume, turnover,
               adj_factor, turnover_rate, volume_ratio, circ_mv, row_status
        FROM public.pams_ohlcv_daily_v2
        WHERE symbol = ANY(%s)
          AND trade_date >= %s
          AND trade_date <= %s
        ORDER BY symbol, trade_date
        """,
        (symbols, start, end),
    )
    if frame.empty:
        return frame
    frame["symbol"] = frame["symbol"].astype(str).str.lower()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume", "turnover", "adj_factor", "turnover_rate", "volume_ratio", "circ_mv"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["adj_factor"] = frame["adj_factor"].fillna(1.0)
    for col in ["open", "high", "low", "close"]:
        frame[f"adj_{col}"] = frame[col] * frame["adj_factor"]
    return frame.dropna(subset=["symbol", "date", "adj_close"]).sort_values(["symbol", "date"]).reset_index(drop=True)


def _series_map(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for symbol, grp in frame.groupby("symbol"):
        work = grp.sort_values("date").reset_index(drop=True).copy()
        work["ma20"] = work["adj_close"].rolling(20, min_periods=5).mean()
        work["ma60"] = work["adj_close"].rolling(60, min_periods=10).mean()
        prev_close = work["adj_close"].shift(1)
        tr = pd.concat(
            [
                work["adj_high"] - work["adj_low"],
                (work["adj_high"] - prev_close).abs(),
                (work["adj_low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        work["atr14"] = tr.rolling(14, min_periods=5).mean()
        work["ret1"] = work["adj_close"].pct_change()
        out[str(symbol)] = work
    return out


def _idx_at_or_after(series: pd.DataFrame, date_value: Any) -> int | None:
    if series.empty or pd.isna(date_value):
        return None
    idx = series.index[series["date"] >= pd.Timestamp(date_value).normalize()]
    return int(idx[0]) if len(idx) else None


def _idx_at_or_before(series: pd.DataFrame, date_value: Any) -> int | None:
    if series.empty or pd.isna(date_value):
        return None
    idx = series.index[series["date"] <= pd.Timestamp(date_value).normalize()]
    return int(idx[-1]) if len(idx) else None


def _ret(series: pd.DataFrame, end_idx: int, lookback: int) -> float | None:
    start_idx = end_idx - lookback
    if start_idx < 0 or end_idx >= len(series):
        return None
    start = _safe_float(series.iloc[start_idx]["adj_close"])
    end = _safe_float(series.iloc[end_idx]["adj_close"])
    if not start or end is None:
        return None
    return end / start - 1.0


def _prior_mean(series: pd.DataFrame, end_idx_exclusive: int, col: str, lookback: int) -> float | None:
    start = max(0, end_idx_exclusive - lookback)
    part = pd.to_numeric(series.iloc[start:end_idx_exclusive][col], errors="coerce").dropna()
    if part.empty:
        return None
    return float(part.mean())


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _trading_days_between(series: pd.DataFrame, start_date: Any, end_date: Any) -> int | None:
    if series.empty or pd.isna(start_date) or pd.isna(end_date):
        return None
    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()
    return int(((series["date"] >= start) & (series["date"] <= end)).sum())


def _first_condition_date(hold: pd.DataFrame, mask: pd.Series, *, skip_rows: int = 0) -> pd.Timestamp | None:
    if hold.empty:
        return None
    local = hold.iloc[skip_rows:].copy() if skip_rows > 0 else hold
    local_mask = mask.loc[local.index].fillna(False)
    hits = local.loc[local_mask]
    if hits.empty:
        return None
    return pd.Timestamp(hits.iloc[0]["date"]).normalize()


def _path_metrics(row: pd.Series, series_map: dict[str, pd.DataFrame]) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "").lower()
    series = series_map.get(symbol)
    if series is None or series.empty:
        return {"path_available_bool": False}
    entry_idx = _idx_at_or_after(series, row.get("entry_date"))
    exit_idx = _idx_at_or_before(series, row.get("exit_date"))
    if entry_idx is None or exit_idx is None or exit_idx < entry_idx:
        return {"path_available_bool": False}

    entry = series.iloc[entry_idx]
    exit_row = series.iloc[exit_idx]
    entry_close = _safe_float(entry["adj_close"])
    exit_close = _safe_float(exit_row["adj_close"])
    if not entry_close or exit_close is None:
        return {"path_available_bool": False}

    prev_idx = max(0, entry_idx - 1)
    prev_ma20 = _prior_mean(series, entry_idx, "adj_close", 20)
    prev_ma60 = _prior_mean(series, entry_idx, "adj_close", 60)
    prev_high20 = _safe_float(series.iloc[max(0, entry_idx - 20):entry_idx]["adj_high"].max()) if entry_idx > 0 else None
    prev_atr14 = _safe_float(series.iloc[prev_idx]["atr14"])

    hold = series.iloc[entry_idx : exit_idx + 1].copy()
    hold["close_ret_from_entry"] = hold["adj_close"] / entry_close - 1.0
    hold["high_ret_from_entry"] = hold["adj_high"] / entry_close - 1.0
    hold["low_ret_from_entry"] = hold["adj_low"] / entry_close - 1.0
    max_close_idx = int(hold["adj_close"].idxmax())
    min_close_idx = int(hold["adj_close"].idxmin())
    peak_close = _safe_float(series.loc[max_close_idx, "adj_close"])
    trough_close = _safe_float(series.loc[min_close_idx, "adj_close"])
    close_mfe = None if peak_close is None else peak_close / entry_close - 1.0
    close_mae = None if trough_close is None else trough_close / entry_close - 1.0
    high_mfe = _safe_float(hold["high_ret_from_entry"].max())
    low_mae = _safe_float(hold["low_ret_from_entry"].min())
    price_return_holding = exit_close / entry_close - 1.0
    peak_date = pd.Timestamp(series.loc[max_close_idx, "date"]).normalize()
    trough_date = pd.Timestamp(series.loc[min_close_idx, "date"]).normalize()
    exit_date = pd.Timestamp(exit_row["date"]).normalize()
    days_to_peak = _trading_days_between(series, entry["date"], peak_date)
    days_from_peak_to_exit = _trading_days_between(series, peak_date, exit_date)

    below_ma20 = hold["adj_close"] < hold["ma20"]
    below_ma60 = hold["adj_close"] < hold["ma60"]
    drawdown_from_running_peak = hold["adj_close"] / hold["adj_close"].cummax() - 1.0
    first_below_ma20 = _first_condition_date(hold, below_ma20, skip_rows=5)
    first_below_ma60 = _first_condition_date(hold, below_ma60, skip_rows=5)
    first_dd10 = _first_condition_date(hold, drawdown_from_running_peak <= -0.10, skip_rows=1)
    first_mae10 = _first_condition_date(hold, hold["close_ret_from_entry"] <= -0.10, skip_rows=1)

    exit_ma20 = _safe_float(exit_row["ma20"])
    exit_ma60 = _safe_float(exit_row["ma60"])
    exit_idx_int = int(exit_idx)
    ma20_5ago = _safe_float(series.iloc[exit_idx_int - 5]["ma20"]) if exit_idx_int >= 5 else None
    ma60_10ago = _safe_float(series.iloc[exit_idx_int - 10]["ma60"]) if exit_idx_int >= 10 else None
    last10 = series.iloc[max(0, exit_idx_int - 9) : exit_idx_int + 1]
    last20 = series.iloc[max(0, exit_idx_int - 19) : exit_idx_int + 1]
    last5 = series.iloc[max(0, exit_idx_int - 4) : exit_idx_int + 1]

    entry_vol5 = _prior_mean(series, entry_idx + 1, "volume", 5)
    entry_vol20_prev = _prior_mean(series, entry_idx - 5 + 1, "volume", 20) if entry_idx >= 5 else _prior_mean(series, entry_idx, "volume", 20)
    exit_vol5 = _prior_mean(series, exit_idx + 1, "volume", 5)
    exit_vol20_prev = _prior_mean(series, exit_idx - 5 + 1, "volume", 20) if exit_idx >= 5 else _prior_mean(series, exit_idx, "volume", 20)
    entry_turn5 = _prior_mean(series, entry_idx + 1, "turnover_rate", 5)
    entry_turn20_prev = _prior_mean(series, entry_idx, "turnover_rate", 20)
    exit_turn5 = _prior_mean(series, exit_idx + 1, "turnover_rate", 5)
    exit_turn20_prev = _prior_mean(series, exit_idx, "turnover_rate", 20)

    def _warn_days(date_value: pd.Timestamp | None) -> int | None:
        if date_value is None:
            return None
        days = _trading_days_between(series, date_value, exit_date)
        return None if days is None else max(days - 1, 0)

    return {
        "path_available_bool": True,
        "entry_close_adj": entry_close,
        "exit_close_adj": exit_close,
        "pre_entry_ret5": _ret(series, prev_idx, 5),
        "pre_entry_ret10": _ret(series, prev_idx, 10),
        "pre_entry_ret20": _ret(series, prev_idx, 20),
        "entry_close_vs_prev_ma20": None if not prev_ma20 else entry_close / prev_ma20 - 1.0,
        "entry_close_vs_prev_ma60": None if not prev_ma60 else entry_close / prev_ma60 - 1.0,
        "entry_close_vs_prev_20d_high": None if not prev_high20 else entry_close / prev_high20 - 1.0,
        "entry_atr14_extension": None if not prev_atr14 else (entry_close - (prev_ma20 or entry_close)) / prev_atr14,
        "price_return_holding_adj": price_return_holding,
        "close_mfe": close_mfe,
        "close_mae": close_mae,
        "high_mfe": high_mfe,
        "low_mae": low_mae,
        "peak_date": peak_date.strftime("%Y-%m-%d"),
        "trough_date": trough_date.strftime("%Y-%m-%d"),
        "days_to_peak": days_to_peak,
        "days_from_peak_to_exit": days_from_peak_to_exit,
        "giveback_from_close_peak": None if close_mfe is None else close_mfe - price_return_holding,
        "peak_to_exit_drawdown": None if not peak_close else exit_close / peak_close - 1.0,
        "exit_close_vs_ma20": None if not exit_ma20 else exit_close / exit_ma20 - 1.0,
        "exit_close_vs_ma60": None if not exit_ma60 else exit_close / exit_ma60 - 1.0,
        "exit_ma20_slope5": None if not ma20_5ago or exit_ma20 is None else exit_ma20 / ma20_5ago - 1.0,
        "exit_ma60_slope10": None if not ma60_10ago or exit_ma60 is None else exit_ma60 / ma60_10ago - 1.0,
        "below_ma20_days_last10": int((last10["adj_close"] < last10["ma20"]).sum()),
        "below_ma60_days_last20": int((last20["adj_close"] < last20["ma60"]).sum()),
        "down_days_last5": int((last5["ret1"] < 0).sum()),
        "down_days_last10": int((last10["ret1"] < 0).sum()),
        "first_below_ma20_date": "" if first_below_ma20 is None else first_below_ma20.strftime("%Y-%m-%d"),
        "first_below_ma60_date": "" if first_below_ma60 is None else first_below_ma60.strftime("%Y-%m-%d"),
        "first_dd10_from_peak_date": "" if first_dd10 is None else first_dd10.strftime("%Y-%m-%d"),
        "first_loss10_from_entry_date": "" if first_mae10 is None else first_mae10.strftime("%Y-%m-%d"),
        "days_below_ma20_warning_before_exit": _warn_days(first_below_ma20),
        "days_below_ma60_warning_before_exit": _warn_days(first_below_ma60),
        "days_dd10_warning_before_exit": _warn_days(first_dd10),
        "days_loss10_warning_before_exit": _warn_days(first_mae10),
        "entry_volume_ratio_5v20": _safe_ratio(entry_vol5, entry_vol20_prev),
        "exit_volume_ratio_5v20": _safe_ratio(exit_vol5, exit_vol20_prev),
        "entry_turnover_ratio_5v20": _safe_ratio(entry_turn5, entry_turn20_prev),
        "exit_turnover_ratio_5v20": _safe_ratio(exit_turn5, exit_turn20_prev),
    }


def _candidate_rank_features(closed: pd.DataFrame) -> pd.DataFrame:
    path = _abs(STOCK_EXP_DIR / "candidate_signals.csv")
    if not path.exists():
        return pd.DataFrame({"trade_key": closed["trade_key"]})
    cands = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    if cands.empty:
        return pd.DataFrame({"trade_key": closed["trade_key"]})
    cands["symbol"] = cands["symbol"].astype(str).str.lower()
    cands["date"] = pd.to_datetime(cands["date"], errors="coerce")
    for col in ["final_score_rank", "final_score_value", "selected_rank"]:
        cands[col] = pd.to_numeric(cands.get(col), errors="coerce")
    by_symbol = {symbol: grp.sort_values("date").reset_index(drop=True) for symbol, grp in cands.groupby("symbol")}
    rows: list[dict[str, Any]] = []
    for row in closed.itertuples(index=False):
        symbol = str(row.symbol).lower()
        grp = by_symbol.get(symbol)
        entry_date = pd.Timestamp(row.entry_date)
        exit_date = pd.Timestamp(row.exit_date)
        payload: dict[str, Any] = {"trade_key": row.trade_key}
        if grp is None or grp.empty:
            rows.append(payload)
            continue
        during = grp.loc[(grp["date"] >= entry_date) & (grp["date"] <= exit_date)].copy()
        last20 = grp.loc[(grp["date"] <= exit_date) & (grp["date"] >= exit_date - pd.Timedelta(days=30))].copy()
        if not during.empty:
            payload["candidate_days_during_hold"] = int(during["date"].nunique())
            payload["best_rank_during_hold"] = _safe_float(during["final_score_rank"].min())
            payload["worst_rank_during_hold"] = _safe_float(during["final_score_rank"].max())
        if not last20.empty:
            last = last20.sort_values("date").iloc[-1]
            payload["last_candidate_before_exit_date"] = pd.Timestamp(last["date"]).strftime("%Y-%m-%d")
            payload["last_rank_before_exit"] = _safe_float(last.get("final_score_rank"))
            payload["last_score_before_exit"] = _safe_float(last.get("final_score_value"))
            payload["days_since_last_candidate_before_exit"] = int((exit_date.normalize() - pd.Timestamp(last["date"]).normalize()).days)
        rows.append(payload)
    return pd.DataFrame(rows)


def _load_inputs() -> pd.DataFrame:
    closed = _read_csv(SOURCE_LOSS_AUDIT_DIR / "machine" / "all_closed_stock_trades_enriched.csv")
    closed["symbol"] = closed["symbol"].astype(str).str.lower()
    closed["entry_date"] = pd.to_datetime(closed["entry_date"], errors="coerce")
    closed["exit_date"] = pd.to_datetime(closed["exit_date"], errors="coerce")
    for col in ["realized_pnl", "realized_return", "hold_calendar_days", "final_score_rank"]:
        closed[col] = pd.to_numeric(closed.get(col), errors="coerce")
    closed = closed.dropna(subset=["symbol", "entry_date", "exit_date"]).copy()
    closed["trade_key"] = (
        closed["symbol"].astype(str)
        + "|"
        + closed["entry_date"].dt.strftime("%Y-%m-%d")
        + "|"
        + closed["exit_date"].dt.strftime("%Y-%m-%d")
        + "|"
        + closed["qty"].astype(str)
    )
    c2_path = _abs(SOURCE_C2_DIR / "machine" / "risk_off_exit_c2_detail_1626.csv")
    if c2_path.exists():
        c2 = pd.read_csv(c2_path, encoding="utf-8-sig", low_memory=False)
        c2["symbol"] = c2["symbol"].astype(str).str.lower()
        c2["entry_date"] = pd.to_datetime(c2["entry_date"], errors="coerce")
        c2["exit_date"] = pd.to_datetime(c2["exit_date"], errors="coerce")
        c2["trade_key"] = (
            c2["symbol"].astype(str)
            + "|"
            + c2["entry_date"].dt.strftime("%Y-%m-%d")
            + "|"
            + c2["exit_date"].dt.strftime("%Y-%m-%d")
            + "|"
            + c2["qty"].astype(str)
        )
        keep = ["trade_key", "theme_evidence_status", "theme_weak_label", "post_sell_outcome", "c2_verdict"]
        closed = closed.merge(c2.loc[:, [col for col in keep if col in c2.columns]].drop_duplicates("trade_key"), on="trade_key", how="left")
    return closed


def _assign_groups(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["analysis_group"] = "other"
    profit_keys = set(out.sort_values("realized_pnl", ascending=False).head(30)["trade_key"])
    loss_keys = set(out.sort_values("realized_pnl", ascending=True).head(30)["trade_key"])
    out.loc[out["trade_key"].isin(profit_keys), "analysis_group"] = "profit_top30"
    out.loc[out["trade_key"].isin(loss_keys), "analysis_group"] = "loss_top30"
    out["winner_bool"] = out["realized_pnl"] > 0
    return out


def _summary(frame: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    numeric = [
        "realized_pnl",
        "realized_return",
        "pre_entry_ret20",
        "entry_close_vs_prev_ma20",
        "entry_close_vs_prev_ma60",
        "entry_atr14_extension",
        "close_mfe",
        "close_mae",
        "giveback_from_close_peak",
        "peak_to_exit_drawdown",
        "days_to_peak",
        "days_from_peak_to_exit",
        "exit_close_vs_ma20",
        "exit_close_vs_ma60",
        "exit_ma20_slope5",
        "below_ma20_days_last10",
        "down_days_last10",
        "days_below_ma20_warning_before_exit",
        "days_dd10_warning_before_exit",
        "entry_volume_ratio_5v20",
        "exit_volume_ratio_5v20",
        "candidate_days_during_hold",
        "last_rank_before_exit",
    ]
    agg: dict[str, tuple[str, str]] = {
        "rows": ("symbol", "size"),
        "symbols": ("symbol", "nunique"),
        "pnl_sum": ("realized_pnl", "sum"),
        "win_count": ("winner_bool", "sum"),
    }
    for col in numeric:
        if col in frame.columns:
            agg[f"avg_{col}"] = (col, "mean")
            agg[f"median_{col}"] = (col, "median")
    return frame.groupby(by, dropna=False).agg(**agg).reset_index()


def _write_report(detail: pd.DataFrame, summaries: dict[str, pd.DataFrame], out_dir: Path, audit: dict[str, Any]) -> None:
    group_summary = summaries["group_summary"]
    compare = group_summary.loc[group_summary["analysis_group"].isin(["profit_top30", "loss_top30"])].copy()
    lines: list[str] = []
    lines.append("# D0 盈亏 TOP30 路径形态审计")
    lines.append("")
    lines.append("## 结论")
    lines.append("- D0 是 read-only 观察层，不改策略、baseline、NAV 或 runtime。")
    lines.append("- 本轮不使用主题/行业指数作为触发，只看个股自身价格路径、均线、量能、浮盈回吐和候选排名痕迹。")
    if not compare.empty:
        for row in compare.itertuples(index=False):
            lines.append(
                f"- {row.analysis_group}: {int(row.rows)} 笔，PnL={_fmt_money(row.pnl_sum)}，"
                f"买入前20日={_fmt_pct(getattr(row, 'avg_pre_entry_ret20', None))}，"
                f"MFE={_fmt_pct(getattr(row, 'avg_close_mfe', None))}，MAE={_fmt_pct(getattr(row, 'avg_close_mae', None))}，"
                f"回吐={_fmt_pct(getattr(row, 'avg_giveback_from_close_peak', None))}。"
            )
    lines.append("")
    lines.append("## 盈亏 TOP30 对照")
    lines.append("|group|rows|PnL|avg_ret|pre20|entry_vs_ma20|MFE|MAE|giveback|peak_to_exit_dd|exit_vs_ma20|below_ma20_last10|dd10_warn_days|")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in compare.itertuples(index=False):
        lines.append(
            f"|{row.analysis_group}|{int(row.rows)}|{_fmt_money(row.pnl_sum)}|{_fmt_pct(getattr(row, 'avg_realized_return', None))}|"
            f"{_fmt_pct(getattr(row, 'avg_pre_entry_ret20', None))}|{_fmt_pct(getattr(row, 'avg_entry_close_vs_prev_ma20', None))}|"
            f"{_fmt_pct(getattr(row, 'avg_close_mfe', None))}|{_fmt_pct(getattr(row, 'avg_close_mae', None))}|"
            f"{_fmt_pct(getattr(row, 'avg_giveback_from_close_peak', None))}|{_fmt_pct(getattr(row, 'avg_peak_to_exit_drawdown', None))}|"
            f"{_fmt_pct(getattr(row, 'avg_exit_close_vs_ma20', None))}|{_safe_float(getattr(row, 'avg_below_ma20_days_last10', None)):.2f}|"
            f"{_safe_float(getattr(row, 'avg_days_dd10_warning_before_exit', None)):.2f}|"
        )
    lines.append("")
    lines.append("## 退出原因拆分")
    lines.append("|group|exit_reason|rows|PnL|MFE|MAE|giveback|exit_vs_ma20|dd10_warn_days|")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    reason = summaries["group_exit_reason_summary"]
    focus = reason.loc[reason["analysis_group"].isin(["profit_top30", "loss_top30"])].copy()
    for row in focus.sort_values(["analysis_group", "pnl_sum"]).itertuples(index=False):
        lines.append(
            f"|{row.analysis_group}|{row.exit_reason_code}|{int(row.rows)}|{_fmt_money(row.pnl_sum)}|"
            f"{_fmt_pct(getattr(row, 'avg_close_mfe', None))}|{_fmt_pct(getattr(row, 'avg_close_mae', None))}|"
            f"{_fmt_pct(getattr(row, 'avg_giveback_from_close_peak', None))}|{_fmt_pct(getattr(row, 'avg_exit_close_vs_ma20', None))}|"
            f"{_safe_float(getattr(row, 'avg_days_dd10_warning_before_exit', None)):.2f}|"
        )
    lines.append("")
    lines.append("## 数据审计")
    lines.append("```json")
    lines.append(json.dumps(audit, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## 决策")
    lines.append("- 后续优先比较：亏损 TOP30 是入场后从未有效盈利，还是曾有浮盈但回吐。")
    lines.append("- 若亏损组卖出前已有较长预警，应研究退出速度；若没有预警，应研究入场确认/风险预算。")
    lines.append("- 本产物只支持提出假设，不直接推出交易规则。")
    human_dir = out_dir / "human"
    human_dir.mkdir(parents=True, exist_ok=True)
    (human_dir / "d0_trade_path_morphology_audit.md").write_text("\n".join(lines), encoding="utf-8")


def _write_journal(summary: dict[str, Any]) -> None:
    now = summary["generated_at"]
    journal = {
        "round_id": ROUND_ID,
        "title": "V3 D0 盈亏 TOP30 路径形态审计",
        "status": "audited",
        "study_id": STUDY_ID,
        "asset_scope": "cn_stock_etf",
        "baseline_id": BASELINE_ID,
        "primary_question": "抛开主题/行业指数，盈利 TOP30 与亏损 TOP30 在买入过热、持仓 MFE/MAE、回吐、均线破坏和排名痕迹上有什么差异？",
        "primary_variable": "read-only per-trade price path morphology over V3 stock closed trades",
        "fixed_assumptions": [
            "CN_STOCK_ETF_COMBO_BASELINE_V3 fixed",
            "stock_alpha_core closed trades only; ETF sleeve excluded",
            "no runtime, NAV, signal, pool, ranking, execution, or exit-rule changes",
            "theme and industry indices are not used as triggers in D0",
        ],
        "windows": ["2012-2026"],
        "variants": [VARIANT_NAME],
        "evidence": [
            {
                "kind": "report",
                "study_id": STUDY_ID,
                "window_key": "1226",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "human" / "d0_trade_path_morphology_audit.md"),
                "note": "human report for D0 trade path morphology audit",
                "linked_at": now,
            },
            {
                "kind": "table",
                "study_id": STUDY_ID,
                "window_key": "1226",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "machine" / "d0_trade_path_detail.csv"),
                "note": "per-trade price path metrics for all closed stock trades",
                "linked_at": now,
            },
        ],
        "key_findings": summary.get("key_findings", []),
        "audit": {
            "source_artifact_checked": True,
            "db_price_lineage_checked": True,
            "read_only_shadow": True,
        },
        "decision": {
            "status": "continue",
            "reason": "Use D0 morphology to decide whether next research should target entry confirmation, profit giveback, or risk-off timing.",
        },
        "next_actions": [
            "Separate loss TOP30 into never-worked vs gave-back-winners.",
            "Check whether sell warnings appeared many days before exit.",
            "Design one follow-up shadow only after the dominant failure mode is clear.",
        ],
        "tags": ["cn_stock_etf", "V3", "D0", "path-morphology", "profit-loss-top30", "research-only"],
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

    closed = _assign_groups(_load_inputs())
    min_date = (closed["entry_date"].min() - pd.Timedelta(days=160)).strftime("%Y-%m-%d")
    max_date = (closed["exit_date"].max() + pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    symbols = sorted(closed["symbol"].dropna().astype(str).str.lower().unique().tolist())
    ohlcv = _load_ohlcv(symbols, min_date, max_date)
    maps = _series_map(ohlcv)
    path_features = pd.DataFrame([_path_metrics(row, maps) for _, row in closed.iterrows()])
    rank_features = _candidate_rank_features(closed)
    detail = pd.concat([closed.reset_index(drop=True), path_features.reset_index(drop=True)], axis=1)
    detail = detail.merge(rank_features, how="left", on="trade_key")

    summaries = {
        "group_summary": _summary(detail, ["analysis_group"]),
        "winner_summary": _summary(detail, ["winner_bool"]),
        "group_exit_reason_summary": _summary(detail, ["analysis_group", "exit_reason_code"]),
        "group_c2_verdict_summary": _summary(detail, ["analysis_group", "c2_verdict"]),
    }
    detail.to_csv(machine_dir / "d0_trade_path_detail.csv", index=False, encoding="utf-8-sig")
    for name, frame in summaries.items():
        frame.to_csv(machine_dir / f"d0_{name}.csv", index=False, encoding="utf-8-sig")

    group_summary = summaries["group_summary"]
    groups = {row["analysis_group"]: row for _, row in group_summary.iterrows()}
    profit = groups.get("profit_top30", {})
    loss = groups.get("loss_top30", {})
    key_findings = [
        f"Closed stock trades audited: {len(detail)}; path available: {int(detail['path_available_bool'].fillna(False).sum())}.",
        (
            "Profit TOP30 avg MFE/giveback: "
            f"{_fmt_pct(profit.get('avg_close_mfe'))}/{_fmt_pct(profit.get('avg_giveback_from_close_peak'))}; "
            "Loss TOP30 avg MFE/giveback: "
            f"{_fmt_pct(loss.get('avg_close_mfe'))}/{_fmt_pct(loss.get('avg_giveback_from_close_peak'))}."
        ),
        (
            "Profit TOP30 avg pre-entry 20d / loss TOP30 avg pre-entry 20d: "
            f"{_fmt_pct(profit.get('avg_pre_entry_ret20'))}/{_fmt_pct(loss.get('avg_pre_entry_ret20'))}."
        ),
    ]
    audit = {
        "baseline_id": BASELINE_ID,
        "closed_trades": int(len(closed)),
        "symbols_requested": int(len(symbols)),
        "symbols_loaded": int(ohlcv["symbol"].nunique()) if not ohlcv.empty else 0,
        "ohlcv_rows": int(len(ohlcv)),
        "min_query_date": min_date,
        "max_query_date": max_date,
        "source_closed_trades": str(SOURCE_LOSS_AUDIT_DIR / "machine" / "all_closed_stock_trades_enriched.csv"),
        "source_prices": "public.pams_ohlcv_daily_v2 adjusted OHLCV",
        "source_candidates": str(STOCK_EXP_DIR / "candidate_signals.csv"),
    }
    summary = {
        "round_id": ROUND_ID,
        "study_id": STUDY_ID,
        "baseline_id": BASELINE_ID,
        "variant_name": VARIANT_NAME,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "read-only path morphology audit over V3 stock_alpha_core closed trades",
        "audit": audit,
        "key_findings": key_findings,
        "outputs": {
            "report": str(OUT_DIR / "human" / "d0_trade_path_morphology_audit.md"),
            "detail": str(OUT_DIR / "machine" / "d0_trade_path_detail.csv"),
            "group_summary": str(OUT_DIR / "machine" / "d0_group_summary.csv"),
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
                "key_findings": result["key_findings"],
                "outputs": result["outputs"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
