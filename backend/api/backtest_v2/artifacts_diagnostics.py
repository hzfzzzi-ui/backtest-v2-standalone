from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd

from backend.api.backtest_v2.artifacts_io import _bool_series, _coerce_bool_value, _safe_int, _safe_read_csv
from backend.api.backtest_v2.protocol import ARTIFACT_FILENAMES
from backend.api.shared.json_utils import sanitize_json
from backend.core.stage_pipeline.contracts import RuntimeDiagnosticsInput
from backend.core.tools.runtime_data_access import (
    resolve_stock_names as resolve_runtime_stock_names,
    resolve_trade_st_flags as resolve_runtime_trade_st_flags,
)

logger = logging.getLogger(__name__)
_ST_NAME_PAT = re.compile(r"(^\*?ST)|(^ST)|退", re.IGNORECASE)


def _resolve_stock_names(symbols: list[str]) -> dict[str, str]:
    try:
        return resolve_runtime_stock_names(symbols)
    except Exception as exc:
        logger.warning("resolve_stock_names failed: %s", exc)
        return {}


def _resolve_trade_st_flags(trades_df: pd.DataFrame, stock_names: dict[str, str]) -> dict[str, str]:
    try:
        return resolve_runtime_trade_st_flags(trades_df, stock_names)
    except Exception as exc:
        logger.warning("resolve_trade_st_flags failed: %s", exc)
        return {}


def _sanitize_historical_stock_names(
    trades_df: pd.DataFrame,
    stock_names: dict[str, str],
    trade_st_flags: dict[str, str],
) -> dict[str, str]:
    if not stock_names:
        return {}
    symbols_with_pit_st = {
        str(key).split("|", 1)[1].lower()
        for key, value in (trade_st_flags or {}).items()
        if str(key).count("|") == 1 and str(value).upper() == "PIT_ST"
    }
    out: dict[str, str] = {}
    for symbol, name in stock_names.items():
        sym = str(symbol or "").strip()
        display_name = str(name or "").strip()
        if not sym or not display_name:
            continue
        if _ST_NAME_PAT.search(display_name) and sym.lower() not in symbols_with_pit_st:
            continue
        out[sym] = display_name
    return out


def _build_candidate_signals(results_dir: Path) -> tuple[Path, pd.DataFrame]:
    src = results_dir / "portfolio_candidates.csv"
    out = results_dir / ARTIFACT_FILENAMES["candidate_signals"]
    required_cols = [
        "date",
        "symbol",
        "alpha_source",
        "residual_strength_score",
        "sector_strength_score",
        "volume_price_quality_score",
        "final_score",
        "selected_flag",
    ]
    df = _safe_read_csv(src)
    if df.empty:
        empty_df = pd.DataFrame(columns=required_cols)
        empty_df.to_csv(out, index=False)
        return out, empty_df

    if "selected_flag" not in df.columns:
        if "selected" in df.columns:
            df["selected_flag"] = _bool_series(df, "selected")
        else:
            df["selected_flag"] = False
    if "final_score" not in df.columns and "mf_score" in df.columns:
        df["final_score"] = pd.to_numeric(df["mf_score"], errors="coerce")
    for col in required_cols:
        if col not in df.columns:
            df[col] = None
    df["selected_flag"] = _bool_series(df, "selected_flag")
    df.to_csv(out, index=False)
    return out, df


def _recent_trading_dates(results_dir: Path, candidate_df: pd.DataFrame, limit: int = 5) -> list[str]:
    def _collect_dates(frame: pd.DataFrame) -> list[str]:
        if frame.empty or "date" not in frame.columns:
            return []
        values: list[str] = []
        seen: set[str] = set()
        for raw in frame["date"].tolist():
            text = str(raw or "").strip()[:10]
            if not text or text in seen:
                continue
            seen.add(text)
            values.append(text)
        return values

    daily_df = _safe_read_csv(results_dir / ARTIFACT_FILENAMES["daily"])
    dates = _collect_dates(daily_df) or _collect_dates(candidate_df)
    if not dates:
        return []
    return dates[-max(1, int(limit)) :]


def _build_recent_cash_blocked_buys(results_dir: Path, candidate_df: pd.DataFrame) -> Path:
    out = results_dir / ARTIFACT_FILENAMES["cash_blocked_buys_recent"]
    columns = [
        "date",
        "symbol",
        "reject_reason",
        "cash_available",
        "estimated_qty",
        "estimated_amount",
        "estimated_price",
        "alpha_source",
        "cash_blocked_reason",
    ]
    if candidate_df.empty or "date" not in candidate_df.columns or "symbol" not in candidate_df.columns:
        pd.DataFrame(columns=columns).to_csv(out, index=False)
        return out

    df = candidate_df.copy()
    if "reject_reason" in df.columns:
        reject_series = df["reject_reason"].fillna("").astype(str).str.upper()
    else:
        reject_series = pd.Series([""] * len(df.index), index=df.index, dtype="object")
    if "cash_blocked_flag" in df.columns:
        blocked_mask = _bool_series(df, "cash_blocked_flag")
    else:
        blocked_mask = pd.Series([False] * len(df.index), index=df.index, dtype="bool")
    blocked_mask = blocked_mask | reject_series.eq("SKIP_NO_CASH")
    if not bool(blocked_mask.any()):
        pd.DataFrame(columns=columns).to_csv(out, index=False)
        return out

    recent_dates = _recent_trading_dates(results_dir, df, limit=5)
    if recent_dates:
        df = df[df["date"].astype(str).str[:10].isin(recent_dates)].copy()
        reject_series = reject_series.loc[df.index]
        blocked_mask = blocked_mask.loc[df.index]
    df = df[blocked_mask].copy()
    if df.empty:
        pd.DataFrame(columns=columns).to_csv(out, index=False)
        return out

    if "alpha_source" not in df.columns:
        df["alpha_source"] = ""
    if "cash_blocked_reason" not in df.columns:
        df["cash_blocked_reason"] = reject_series
    for col in ("cash_available", "estimated_amount", "estimated_price"):
        if col not in df.columns:
            df[col] = None
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "estimated_qty" not in df.columns:
        df["estimated_qty"] = None
    else:
        df["estimated_qty"] = pd.to_numeric(df["estimated_qty"], errors="coerce").astype("Int64")
    df["date"] = df["date"].astype(str).str[:10]
    df["symbol"] = df["symbol"].astype(str).str.lower()
    df["reject_reason"] = reject_series.loc[df.index]
    df["cash_blocked_reason"] = df["cash_blocked_reason"].fillna("").astype(str)
    df = df[columns]
    df = df.sort_values(["date", "estimated_amount", "symbol"], ascending=[False, False, True]).reset_index(drop=True)
    df.to_csv(out, index=False)
    return out


def _build_alpha_funnel(results_dir: Path, candidate_df: pd.DataFrame) -> Path:
    out = results_dir / ARTIFACT_FILENAMES["alpha_funnel"]
    columns = ["date", "alpha_source", "candidate_count", "selected_count", "rejected_count"]
    if candidate_df.empty:
        pd.DataFrame(columns=columns).to_csv(out, index=False)
        return out

    df = candidate_df.copy()
    if "is_candidate" in df.columns:
        try:
            df = df[df["is_candidate"].astype(bool)]
        except Exception:
            pass
    if df.empty:
        pd.DataFrame(columns=columns).to_csv(out, index=False)
        return out
    if "selected_flag" not in df.columns:
        df["selected_flag"] = False
    if "alpha_source" not in df.columns:
        df["alpha_source"] = "unknown"
    df["selected_flag"] = _bool_series(df, "selected_flag")
    df["alpha_source"] = df["alpha_source"].fillna("unknown").astype(str)

    grouped = (
        df.groupby(["date", "alpha_source"], dropna=False)
        .agg(
            candidate_count=("symbol", "count"),
            selected_count=("selected_flag", lambda s: int(pd.Series(s).sum())),
        )
        .reset_index()
    )
    grouped["rejected_count"] = grouped["candidate_count"] - grouped["selected_count"]
    grouped = grouped[columns]
    grouped = grouped.sort_values(["date", "alpha_source"], ascending=[True, True]).reset_index(drop=True)
    grouped.to_csv(out, index=False)
    return out


def _build_score_diagnostics(results_dir: Path, candidate_df: pd.DataFrame) -> Path:
    out = results_dir / ARTIFACT_FILENAMES["score_diagnostics"]
    columns = [
        "date",
        "candidate_rank",
        "symbol",
        "alpha_source",
        "final_score",
        "residual_strength_score",
        "sector_strength_score",
        "volume_price_quality_score",
        "selected_flag",
    ]
    if candidate_df.empty:
        pd.DataFrame(columns=columns).to_csv(out, index=False)
        return out

    df = candidate_df.copy()
    if "is_candidate" in df.columns:
        try:
            df = df[df["is_candidate"].astype(bool)]
        except Exception:
            pass
    if df.empty or "date" not in df.columns or "symbol" not in df.columns:
        pd.DataFrame(columns=columns).to_csv(out, index=False)
        return out

    if "selected_flag" not in df.columns:
        df["selected_flag"] = False
    if "alpha_source" not in df.columns:
        df["alpha_source"] = "unknown"
    if "final_score" not in df.columns and "mf_score" in df.columns:
        df["final_score"] = pd.to_numeric(df["mf_score"], errors="coerce")
    for score_col in ("final_score", "residual_strength_score", "sector_strength_score", "volume_price_quality_score"):
        if score_col not in df.columns:
            df[score_col] = None
        else:
            df[score_col] = pd.to_numeric(df[score_col], errors="coerce")
    df["selected_flag"] = _bool_series(df, "selected_flag")
    df["alpha_source"] = df["alpha_source"].fillna("unknown").astype(str)

    df = df.sort_values(["date", "final_score", "symbol"], ascending=[True, False, True]).copy()
    df["candidate_rank"] = df.groupby("date").cumcount() + 1
    df = df[df["candidate_rank"] <= 10]
    df = df[columns]
    df.to_csv(out, index=False)
    return out


def _sum_int_column(df: pd.DataFrame, column: str) -> int | None:
    if df.empty or column not in df.columns:
        return None
    values = pd.to_numeric(df[column], errors="coerce")
    if not bool(values.notna().any()):
        return None
    return int(values.fillna(0).sum())


def _sum_reason_aliases(reason_counts: dict[str, Any], *aliases: str) -> int:
    total = 0
    for alias in aliases:
        total += int(reason_counts.get(str(alias), 0) or 0)
    return int(total)


def _runtime_diagnostics_from_daily_row(row: dict[str, Any]) -> RuntimeDiagnosticsInput:
    parsed = RuntimeDiagnosticsInput.from_json(row.get("diagnostics_input_json"))
    if parsed is not None:
        return parsed
    return RuntimeDiagnosticsInput(
        route_id=str(row.get("route_id") or ""),
        candidates_count=int(_safe_int(row.get("candidates_count")) or 0),
        selected_count=int(_safe_int(row.get("selected_count")) or 0),
        positions_before_sell=int(_safe_int(row.get("positions_before_sell")) or 0),
        positions_after_sell=int(_safe_int(row.get("positions_after_sell")) or 0),
        buy_slots=int(_safe_int(row.get("buy_slots_after_sell")) or _safe_int(row.get("buy_slots_before_buy")) or 0),
        raw_buy_signal_count=int(_safe_int(row.get("raw_buy_signal_count")) or 0),
        raw_alpha_signal_count=int(_safe_int(row.get("raw_alpha_signal_count")) or 0),
        composed_buy_signal_count=int(_safe_int(row.get("composed_buy_signal_count")) or 0),
        composed_sell_signal_count=int(_safe_int(row.get("composed_sell_signal_count")) or 0),
        raw_buy_candidate_count=int(_safe_int(row.get("buy_candidate_count")) or 0),
        raw_after_held_filter_count=int(_safe_int(row.get("after_held_filter_count")) or 0),
        raw_after_slot_filter_count=_safe_int(row.get("after_slot_filter_count")),
        raw_after_cash_lot_count=_safe_int(row.get("after_cash_lot_count")),
        benchmark_regime_on=_coerce_bool_value(row.get("benchmark_regime_on")),
        strong_risk_on=_coerce_bool_value(row.get("strong_risk_on")),
    )


def _normalize_buy_stage_counts(diag: RuntimeDiagnosticsInput) -> dict[str, Any]:
    raw_buy_candidate_count = int(diag.raw_buy_candidate_count or 0)
    raw_after_held_filter_count = int(diag.raw_after_held_filter_count or 0)
    after_slot_filter_count = diag.raw_after_slot_filter_count
    after_cash_lot_count = diag.raw_after_cash_lot_count

    if diag.route_id == "provider_breakout_runtime":
        stage_mid_count = (
            int(raw_after_held_filter_count)
            if (int(diag.candidates_count) > 0 or bool(diag.benchmark_regime_on))
            else 0
        )
        return {
            "buy_candidate_count": int(stage_mid_count),
            "after_held_filter_count": int(stage_mid_count),
            "after_slot_filter_count": int(stage_mid_count),
            "after_cash_lot_count": int(diag.selected_count),
            "after_slot_measured": True,
            "after_cash_measured": True,
        }

    return {
        "buy_candidate_count": int(raw_buy_candidate_count),
        "after_held_filter_count": int(raw_after_held_filter_count),
        "after_slot_filter_count": after_slot_filter_count,
        "after_cash_lot_count": after_cash_lot_count,
        "after_slot_measured": after_slot_filter_count is not None,
        "after_cash_measured": after_cash_lot_count is not None,
    }


def _build_buy_stage_funnel(
    result: dict[str, Any],
    results_dir: Path,
    buy_orders_count: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    daily_path = results_dir / ARTIFACT_FILENAMES["daily"]
    daily_df = _safe_read_csv(daily_path)
    universe_meta = dict(result.get("universe_meta") or {})
    diag_raw = {
        str(k): int(v or 0)
        for k, v in dict(result.get("candidate_diag_reason_counts") or {}).items()
        if str(k).strip()
    }
    diag = {
        k: v for k, v in diag_raw.items()
        if k.startswith("BLOCK_") or k.startswith("SKIP_") or k.startswith("ENTRY_")
    }

    raw_universe = _safe_int(universe_meta.get("raw_count"))
    tradable_universe = _safe_int(
        universe_meta.get("tradable_symbols")
        or universe_meta.get("after_filters_symbols")
    )
    trading_days = int(len(daily_df)) if not daily_df.empty else None
    tradable_symbol_days = None
    if tradable_universe is not None and trading_days is not None:
        tradable_symbol_days = int(tradable_universe) * int(trading_days)
    diag_inputs = [
        _runtime_diagnostics_from_daily_row(record)
        for record in daily_df.to_dict(orient="records")
    ] if not daily_df.empty else []
    normalized_rows = [_normalize_buy_stage_counts(diag) for diag in diag_inputs]
    raw_buy_signal = (
        int(sum(int(diag.raw_buy_signal_count or 0) for diag in diag_inputs))
        if diag_inputs
        else _sum_int_column(daily_df, "raw_buy_signal_count")
    )
    buy_candidates = (
        int(sum(int(row["buy_candidate_count"]) for row in normalized_rows))
        if normalized_rows
        else _sum_int_column(daily_df, "buy_candidate_count")
    )
    after_held = (
        int(sum(int(row["after_held_filter_count"]) for row in normalized_rows))
        if normalized_rows
        else _sum_int_column(daily_df, "after_held_filter_count")
    )
    after_slot_values = [
        int(row["after_slot_filter_count"])
        for row in normalized_rows
        if row["after_slot_measured"] and row["after_slot_filter_count"] is not None
    ]
    after_cash_values = [
        int(row["after_cash_lot_count"])
        for row in normalized_rows
        if row["after_cash_measured"] and row["after_cash_lot_count"] is not None
    ]
    after_slot = int(sum(after_slot_values)) if after_slot_values else None
    after_cash = int(sum(after_cash_values)) if after_cash_values else None
    after_slot_measured = bool(after_slot_values) and (after_slot > 0 or buy_orders_count == 0)
    after_cash_measured = bool(after_cash_values) and (after_cash > 0 or buy_orders_count == 0)

    def stage_row(
        stage_key: str,
        stage_label: str,
        input_count: int | None,
        output_count: int | None,
        note: str,
        *,
        available: bool = True,
    ) -> dict[str, Any]:
        filtered_count = None
        if input_count is not None and output_count is not None:
            filtered_count = max(int(input_count) - int(output_count), 0)
        return {
            "stage_key": stage_key,
            "stage_label": stage_label,
            "input_count": input_count,
            "output_count": output_count,
            "filtered_count": filtered_count,
            "available": bool(available),
            "note": note,
        }

    rows: list[dict[str, Any]] = []
    rows.append(stage_row(
        "s1",
        "S1 股票池",
        raw_universe,
        tradable_universe,
        "指数成分载入与基础可交易过滤后的标的数",
        available=raw_universe is not None and tradable_universe is not None,
    ))
    rows.append(stage_row(
        "s2",
        "S2 大盘环境",
        None,
        None,
        "当前产物未按候选维度单独计数；大盘环境已并入信号生成或交易模式",
        available=False,
    ))
    rows.append(stage_row(
        "s3",
        "S3 行业趋势",
        None,
        None,
        "当前策略未启用或未单独输出行业级买入过滤计数",
        available=False,
    ))
    rows.append(stage_row(
        "s4",
        "S4 个股趋势",
        tradable_symbol_days,
        raw_buy_signal,
        "从全回测期可交易标的日频事件收缩到原始买入信号",
        available=tradable_symbol_days is not None and raw_buy_signal is not None,
    ))
    rows.append(stage_row(
        "s5",
        "S5 个股排序",
        raw_buy_signal,
        buy_candidates,
        "候选排序与可交易预筛后的保留数量",
        available=raw_buy_signal is not None and buy_candidates is not None,
    ))
    rows.append(stage_row(
        "s6",
        "S6 入场信号",
        buy_candidates,
        after_held,
        "去除已持仓/重复信号后的可入场候选",
        available=buy_candidates is not None and after_held is not None,
    ))
    rows.append(stage_row(
        "s7",
        "S7 组合构建",
        after_held,
        after_slot if after_slot_measured else buy_orders_count,
        "仓位槽位与组合容量约束后的保留数量"
        if after_slot_measured
        else "当前引擎未稳定输出 slot stage，直接落到实际 BUY orders",
        available=after_held is not None,
    ))
    rows.append(stage_row(
        "s8",
        "S8 风险控制",
        after_slot if after_slot_measured else None,
        after_cash if after_cash_measured else None,
        "现金、整手与下单金额约束后的候选数量"
        if (after_slot_measured and after_cash_measured)
        else "当前引擎未单独输出 cash/lot stage 计数",
        available=after_slot_measured and after_cash_measured,
    ))
    rows.append(stage_row(
        "s9",
        "S9 退出",
        None,
        None,
        "买入漏斗不适用；退出统计请查看卖出漏斗",
        available=False,
    ))

    return rows, diag


def _build_counters(
    result: dict[str, Any],
    results_dir: Path,
    funnel_obj: dict[str, Any] | None = None,
) -> dict[str, Any]:
    counters: dict[str, Any] = {}
    counters["avg_positions"] = float(result.get("avg_positions", 0.0) or 0.0)
    counters["max_positions"] = int(result.get("max_positions", 10) or 10)
    counters["trend_slope_block_count"] = int(result.get("trend_slope_block_count", 0) or 0)
    counters["mf_rank_applied_rate"] = float(result.get("mf_rank_applied_rate", 0.0) or 0.0)
    counters["gate_on_rate"] = float(result.get("mf_gate_on_rate", result.get("gate_on_rate", 0.0)) or 0.0)
    _f = dict(funnel_obj or {})
    counters["raw_signal"] = int(_f.get("raw_signal", result.get("raw_signal", 0)) or 0)
    counters["blocked"] = int(_f.get("blocked", result.get("blocked", 0)) or 0)
    counters["orders"] = int(_f.get("orders", result.get("orders", 0)) or 0)
    counters["skipped"] = int(_f.get("skipped", result.get("skipped", 0)) or 0)
    counters["closed_trades"] = int(_f.get("closed_trades", result.get("closed_trades", 0)) or 0)

    daily_path = results_dir / ARTIFACT_FILENAMES["daily"]
    if daily_path.exists():
        try:
            ddf = pd.read_csv(daily_path)
        except Exception:
            ddf = pd.DataFrame()
        if not ddf.empty:
            def _num_series(name: str) -> pd.Series:
                if name not in ddf.columns:
                    return pd.Series(0.0, index=ddf.index, dtype=float)
                return pd.to_numeric(ddf[name], errors="coerce").fillna(0.0)

            mtr = _num_series("mf_rank_triggered")
            mra = _num_series("mf_rank_applied")
            mfc = _num_series("mf_candidates_when_triggered")
            mtk = _num_series("mf_topk_reject_count")
            mcs = _num_series("mf_concentrated_selected_count")
            mg = _num_series("mf_gate_on")
            sro = _num_series("strong_risk_on")
            mssg = _num_series("mf_rank_suppressed_by_strong_gate")
            selected_count = _num_series("selected_count")

            mf_rank_trigger_days = int((mtr > 0).sum())
            mf_rank_applied_days = int((mra > 0).sum())
            mf_gate_on_days = int((mg > 0).sum())
            strong_risk_on_days = int((sro > 0).sum())
            mf_rank_suppressed_by_strong_gate_days = int((mssg > 0).sum())

            counters["mf_rank_trigger_days"] = mf_rank_trigger_days
            counters["mf_rank_trigger_rate"] = float((mtr > 0).mean()) if len(mtr) > 0 else 0.0
            counters["mf_rank_applied_days"] = mf_rank_applied_days
            counters["mf_rank_applied_rate"] = float((mra > 0).mean()) if len(mra) > 0 else counters["mf_rank_applied_rate"]
            counters["mf_avg_candidates_when_triggered"] = float(mfc[mtr > 0].mean()) if mf_rank_trigger_days > 0 else 0.0
            counters["mf_topk_reject_count"] = int(mtk.sum())
            selected_sum = float(selected_count.sum())
            counters["mf_concentrated_buy_rate"] = float(float(mcs.sum()) / selected_sum) if selected_sum > 0 else 0.0
            counters["mf_gate_on_days"] = mf_gate_on_days
            counters["mf_gate_on_rate"] = float((mg > 0).mean()) if len(mg) > 0 else 0.0
            counters["gate_on_rate"] = float(counters["mf_gate_on_rate"])
            counters["strong_risk_on_days"] = strong_risk_on_days
            counters["strong_risk_on_rate"] = float((sro > 0).mean()) if len(sro) > 0 else 0.0
            counters["mf_rank_suppressed_by_strong_gate_days"] = mf_rank_suppressed_by_strong_gate_days

    trades_path = results_dir / ARTIFACT_FILENAMES["trades"]
    atr_stop = atr_trail = atr_trail_update = reversal = time_exit = take_profit = fixed_stop_loss = 0
    if trades_path.exists():
        try:
            tdf = pd.read_csv(trades_path)
            if not tdf.empty and "reason_code" in tdf.columns:
                rc = tdf["reason_code"].astype(str).str.upper()
                atr_stop = int(rc.eq("ATR_STOP_LOSS").sum())
                atr_trail = int(rc.eq("ATR_TRAIL_EXIT").sum())
                reversal = int(rc.isin(["SIGNAL_REVERSE", "SMA_CROSS_DOWN", "EMA_CROSS_DOWN"]).sum())
                time_exit = int(rc.eq("TIME_EXIT").sum())
                take_profit = int(rc.eq("TAKE_PROFIT").sum())
                fixed_stop_loss = int(rc.eq("FIXED_STOP_LOSS").sum())
            if not tdf.empty and "triggered_rule" in tdf.columns:
                tr = tdf["triggered_rule"].astype(str).str.upper()
                atr_trail_update = int(((tr.str.contains("TRAIL", na=False) & tr.str.contains("UPDATE|RAISE|ADJUST", regex=True, na=False) & (~tr.str.contains("EXIT", na=False)))).sum())
        except Exception:
            pass
    buy_orders_count = sell_orders_count = 0
    if trades_path.exists():
        try:
            tdf_orders = pd.read_csv(trades_path)
            if not tdf_orders.empty and "side" in tdf_orders.columns:
                side = tdf_orders["side"].astype(str).str.upper()
                buy_orders_count = int(side.eq("BUY").sum())
                sell_orders_count = int(side.eq("SELL").sum())
        except Exception:
            pass
    counters["atr_stop_exit_count"] = atr_stop
    counters["atr_trail_exit_count"] = atr_trail
    counters["atr_trail_update_count"] = int(result.get("atr_trail_update_count", 0) or 0) or atr_trail_update
    counters["reversal_exit_count"] = reversal
    counters["time_exit_count"] = time_exit
    counters["take_profit_exit_count"] = int(result.get("take_profit_exit_count", 0) or 0) or take_profit
    counters["fixed_stop_loss_exit_count"] = int(result.get("fixed_stop_loss_exit_count", 0) or 0) or fixed_stop_loss
    counters["dd_reduced_count"] = int(result.get("dd_reduced_count", 0) or 0)

    diag = dict(result.get("candidate_diag_reason_counts") or {})
    counters["cash_skip_count"] = _sum_reason_aliases(diag, "SKIP_CASH_INSUFFICIENT", "SKIP_NO_CASH")
    counters["lot_skip_count"] = _sum_reason_aliases(diag, "SKIP_LOT_TOO_SMALL", "SKIP_QTY_ZERO")
    counters["cap_hit_single"] = int(diag.get("BLOCK_SINGLE_CAP", 0) or 0)
    counters["cap_hit_industry"] = int(diag.get("BLOCK_INDUSTRY_CAP", 0) or 0)
    counters["min_hold_block_count"] = int(diag.get("BLOCK_MIN_HOLD", 0) or 0)
    counters["cooldown_block_count"] = int(diag.get("BLOCK_COOLDOWN", 0) or 0)
    counters["entry_above_slow_ma_block_count"] = int(result.get("entry_above_slow_ma_block_count", 0) or 0)
    counters["entry_slope_block_count"] = int(result.get("entry_slope_block_count", 0) or 0)
    counters["regime_trend_days"] = int(result.get("regime_trend_days", 0) or 0)
    counters["regime_mr_days"] = int(result.get("regime_mr_days", 0) or 0)
    counters["mr_rsi_oversold_buy_count"] = int(result.get("mr_rsi_oversold_buy_count", 0) or 0)
    counters["mr_rsi_overbought_sell_count"] = int(result.get("mr_rsi_overbought_sell_count", 0) or 0)
    counters["mr_stop_loss_count"] = int(result.get("mr_stop_loss_count", 0) or 0)
    counters["mr_time_exit_count"] = int(result.get("mr_time_exit_count", 0) or 0)
    counters["regime_filter_diagnostics"] = dict(result.get("regime_filter_diagnostics") or {})
    counters["market_state_bull_days"] = int(result.get("market_state_bull_days", 0) or 0)
    counters["market_state_bear_days"] = int(result.get("market_state_bear_days", 0) or 0)
    counters["market_state_trans_down_days"] = int(result.get("market_state_trans_down_days", 0) or 0)
    counters["market_state_trans_up_days"] = int(result.get("market_state_trans_up_days", 0) or 0)
    counters["trade_mode_main_days"] = int(result.get("trade_mode_main_days", 0) or 0)
    counters["trade_mode_light_days"] = int(result.get("trade_mode_light_days", 0) or 0)
    counters["trade_mode_notrade_days"] = int(result.get("trade_mode_notrade_days", 0) or 0)

    avg_pos = counters["avg_positions"]
    max_pos = counters["max_positions"]
    counters["slots_left"] = round(float(max_pos) - float(avg_pos), 1)
    counters["buy_orders_count"] = int(buy_orders_count)
    counters["sell_orders_count"] = int(sell_orders_count)
    buy_stage_funnel, buy_block_reason_counts = _build_buy_stage_funnel(result, results_dir, buy_orders_count)
    counters["buy_stage_funnel"] = buy_stage_funnel
    counters["buy_block_reason_counts"] = buy_block_reason_counts
    return sanitize_json(counters)


__all__ = [
    "_build_alpha_funnel",
    "_build_buy_stage_funnel",
    "_build_candidate_signals",
    "_build_recent_cash_blocked_buys",
    "_build_counters",
    "_build_score_diagnostics",
    "_resolve_stock_names",
    "_resolve_trade_st_flags",
    "_sanitize_historical_stock_names",
]
