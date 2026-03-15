from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import logging
import pandas as pd

from backend.core.audit.experiment_audit import merge_experiment_audit
from backend.core.audit.research_audit import build_research_audit
from backend.core.analytics.symbol_performance import build_symbol_performance
from backend.api.backtest_v2.protocol import ARTIFACT_FILENAMES, MISSING_FIELD_KEYS
from backend.api.shared.json_utils import sanitize_json
from backend.api.shared.paths import repo_root as _repo_root, results_root as _results_root
from backend.core.tools.runtime_data_access import (
    resolve_stock_names as resolve_runtime_stock_names,
    resolve_trade_st_flags as resolve_runtime_trade_st_flags,
)

logger = logging.getLogger(__name__)
MANIFEST_SCHEMA_VERSION = "backtest_v2_experiment_manifest@2"
_ST_NAME_PAT = re.compile(r"(^\*?ST)|(^ST)|退", re.IGNORECASE)


def _safe_float(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        n = float(v)
    except Exception:
        return None
    if math.isnan(n) or math.isinf(n):
        return None
    return n


def _safe_int(v: Any) -> int | None:
    if v in (None, ""):
        return None
    try:
        return int(float(v))
    except Exception:
        return None


def _to_rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _manifest_config_snapshots(results_dir: Path, artifacts: dict[str, Any]) -> dict[str, str]:
    snapshots: dict[str, str] = {}
    for key, filename in (
        ("input_config", "input_config.json"),
        ("resolved_config", "resolved_config.json"),
        ("compiled_plan", "compiled_plan.json"),
    ):
        rel = str(artifacts.get(key) or "").strip()
        if rel:
            snapshots[key] = rel
            continue
        path = results_dir / filename
        if path.exists():
            snapshots[key] = _to_rel(path, results_dir)
    return snapshots


def _baseline_compare_status(results_dir: Path) -> str:
    path = results_dir / "baseline_compare.json"
    if not path.exists():
        return "NOT_RUN"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return "UNKNOWN"
    status = str(payload.get("status") or "").strip().upper()
    return status or "UNKNOWN"


def _extract_stage_summary(result: dict[str, Any]) -> dict[str, Any] | None:
    direct = result.get("stage_summary")
    if isinstance(direct, dict) and direct:
        return sanitize_json(dict(direct))
    metrics = result.get("metrics")
    if isinstance(metrics, dict):
        nested = metrics.get("stage_summary")
        if isinstance(nested, dict) and nested:
            return sanitize_json(dict(nested))
    return None


def _extract_stage_pipeline_summary(
    result: dict[str, Any],
    stage_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    direct = result.get("stage_pipeline")
    if isinstance(direct, dict) and direct:
        return sanitize_json(dict(direct))
    metrics = result.get("metrics")
    if isinstance(metrics, dict):
        nested = metrics.get("stage_pipeline")
        if isinstance(nested, dict) and nested:
            return sanitize_json(dict(nested))
    if not isinstance(stage_summary, dict) or not stage_summary:
        return None
    return sanitize_json(
        {
            "schema_version": stage_summary.get("schema_version"),
            "execution_shell": stage_summary.get("execution_shell"),
            "daily_loop_mode": stage_summary.get("daily_loop_mode"),
            "route_id": stage_summary.get("route_id"),
            "stage_order": list(stage_summary.get("stage_order") or ()),
            "enabled_stages": list(stage_summary.get("enabled_stages") or ()),
            "warnings": list(stage_summary.get("warnings") or ()),
            "trading_days": _safe_int(stage_summary.get("trading_days")),
        }
    )


def _resolve_runtime_path(raw: str | None, bt_root: Path) -> Path | None:
    if not raw:
        return None
    p = Path(str(raw))
    if p.exists():
        return p.resolve()
    text = str(raw).strip()
    if text.startswith("/app/backend/core"):
        mapped = bt_root / text[len("/app/backend/core") :].lstrip("/\\")
        if mapped.exists():
            return mapped.resolve()
    return None


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


def _generate_experiment_label(base_cfg: dict[str, Any], overrides: dict[str, Any]) -> str:
    """Generate a human-readable label like 'SMA_CROSS 5/20 | CUSTOM 2只 | HFQ | 2024-01~06'."""
    wc = overrides.get("workbench_config") or {}

    strategy = str(wc.get("strategy") or base_cfg.get("signal", {}).get("strategy") or "UNKNOWN").upper()

    # Extract MA params — use ema config for EMA strategy, sma otherwise
    sig_gen = wc.get("signal_generation") or {}
    ma_key = "ema" if "EMA" in strategy else "sma"
    ma_cfg = sig_gen.get(ma_key) or wc.get(ma_key) or base_cfg.get("signal", {}).get(ma_key) or {}
    fast = ma_cfg.get("fast_ma") or ma_cfg.get("fast_period") or ""
    slow = ma_cfg.get("slow_ma") or ma_cfg.get("slow_period") or ""
    param_str = f" {fast}/{slow}" if fast and slow else ""

    # Universe mode + count
    u_mode = str(overrides.get("universe_mode") or wc.get("universe_mode") or "CUSTOM").upper()
    symbols = overrides.get("symbols") or []
    count_str = f" {len(symbols)}只" if symbols else ""

    # Price adj
    price_adj = str(overrides.get("price_adj") or wc.get("price_adj") or "hfq").upper()

    # Date range
    start = str(overrides.get("start_date") or base_cfg.get("universe", {}).get("start") or "")
    end = str(overrides.get("end_date") or base_cfg.get("universe", {}).get("end") or "")
    start_short = start[:7] if len(start) >= 7 else start
    end_short = end[5:7] if len(end) >= 7 else end
    date_str = f"{start_short}~{end_short}" if start and end else ""

    parts = [f"{strategy}{param_str}", f"{u_mode}{count_str}", price_adj]
    if date_str:
        parts.append(date_str)
    return " | ".join(parts)


def _write_nav_csv(results_dir: Path, result: dict[str, Any]) -> Path:
    out = results_dir / "nav.csv"
    if out.exists():
        return out
    effective_start = str(result.get("effective_execution_start_date") or "").strip()

    candidates = [results_dir / "portfolio_daily.csv", results_dir / "equity_curve.csv"]
    for src in candidates:
        if not src.exists():
            continue
        try:
            df = pd.read_csv(src)
            date_col = "date" if "date" in df.columns else ("dt" if "dt" in df.columns else None)
            nav_col = None
            for c in ["nav", "strategy_nav", "equity", "equity_curve", "portfolio_value"]:
                if c in df.columns:
                    nav_col = c
                    break
            if nav_col is None:
                continue
            if date_col is None:
                dates = pd.to_datetime(df.index, errors="coerce").strftime("%Y-%m-%d")
            else:
                dates = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
            nav = pd.to_numeric(df[nav_col], errors="coerce")
            out_df = pd.DataFrame({"date": dates, "nav": nav}).dropna(subset=["date", "nav"])
            if effective_start and not out_df.empty:
                date_ts = pd.to_datetime(out_df["date"], errors="coerce").dt.normalize()
                out_df = out_df.loc[date_ts >= pd.Timestamp(effective_start).normalize()].copy()
                if not out_df.empty:
                    nav0 = float(pd.to_numeric(out_df["nav"], errors="coerce").iloc[0])
                    if nav0 > 0:
                        out_df["nav"] = pd.to_numeric(out_df["nav"], errors="coerce") / nav0
            if not out_df.empty:
                out_df.to_csv(out, index=False)
                return out
        except Exception:
            pass

    start = str(result.get("start_date") or "")
    end = str(result.get("end_date") or "")
    total_ret = float(_safe_float(result.get("total_return")) or 0.0)
    if start and end:
        pd.DataFrame([
            {"date": start, "nav": 1.0},
            {"date": end, "nav": 1.0 + total_ret},
        ]).to_csv(out, index=False)
    else:
        pd.DataFrame(columns=["date", "nav"]).to_csv(out, index=False)
    return out


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return dict(payload) if isinstance(payload, dict) else None


def _write_csv_alias(src: Path, dst: Path, empty_columns: list[str] | None = None) -> Path:
    df = _safe_read_csv(src)
    if df.empty and empty_columns is not None:
        df = pd.DataFrame(columns=list(empty_columns))
    df.to_csv(dst, index=False)
    return dst


def _coerce_bool_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return not math.isnan(float(value)) and float(value) != 0.0
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"", "0", "false", "no", "n", "off", "nan", "none", "null"}:
        return False
    return bool(text)


def _bool_series(df: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in df.columns:
        return pd.Series([bool(default)] * len(df), index=df.index, dtype=bool)
    return df[column].map(_coerce_bool_value).astype(bool)


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
    values = pd.to_numeric(df[column], errors="coerce").fillna(0)
    return int(values.sum())


def _sum_reason_aliases(reason_counts: dict[str, Any], *aliases: str) -> int:
    total = 0
    for alias in aliases:
        total += int(reason_counts.get(str(alias), 0) or 0)
    return int(total)


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
    raw_buy_signal = _sum_int_column(daily_df, "raw_buy_signal_count")
    buy_candidates = _sum_int_column(daily_df, "buy_candidate_count")
    after_held = _sum_int_column(daily_df, "after_held_filter_count")
    after_slot = _sum_int_column(daily_df, "after_slot_filter_count")
    after_cash = _sum_int_column(daily_df, "after_cash_lot_count")
    after_slot_measured = after_slot is not None and (after_slot > 0 or buy_orders_count == 0)
    after_cash_measured = after_cash is not None and (after_cash > 0 or buy_orders_count == 0)

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
        available=buy_candidates is not None,
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
    """从 result dict 和 results_dir 下的产物文件中提取完整 counters。"""
    counters: dict[str, Any] = {}

    # --- 引擎 metrics 直接透传的字段 ---
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
            counters["mf_avg_candidates_when_triggered"] = (
                float(mfc[mtr > 0].mean()) if mf_rank_trigger_days > 0 else 0.0
            )
            counters["mf_topk_reject_count"] = int(mtk.sum())
            selected_sum = float(selected_count.sum())
            counters["mf_concentrated_buy_rate"] = (
                float(float(mcs.sum()) / selected_sum) if selected_sum > 0 else 0.0
            )
            counters["mf_gate_on_days"] = mf_gate_on_days
            counters["mf_gate_on_rate"] = float((mg > 0).mean()) if len(mg) > 0 else 0.0
            counters["gate_on_rate"] = float(counters["mf_gate_on_rate"])
            counters["strong_risk_on_days"] = strong_risk_on_days
            counters["strong_risk_on_rate"] = float((sro > 0).mean()) if len(sro) > 0 else 0.0
            counters["mf_rank_suppressed_by_strong_gate_days"] = mf_rank_suppressed_by_strong_gate_days

    # --- 从 portfolio_trades.csv 派生 exit 计数器 ---
    trades_path = results_dir / ARTIFACT_FILENAMES["trades"]
    atr_stop = 0
    atr_trail = 0
    atr_trail_update = 0
    reversal = 0
    time_exit = 0
    take_profit = 0
    fixed_stop_loss = 0
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
            # atr_trail_update_count: 从 triggered_rule 列推导
            if not tdf.empty and "triggered_rule" in tdf.columns:
                tr = tdf["triggered_rule"].astype(str).str.upper()
                atr_trail_update = int(
                    (
                        tr.str.contains("TRAIL", na=False)
                        & tr.str.contains("UPDATE|RAISE|ADJUST", regex=True, na=False)
                        & (~tr.str.contains("EXIT", na=False))
                    ).sum()
                )
        except Exception:
            pass
    buy_orders_count = 0
    sell_orders_count = 0
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

    # --- 从 candidate_diag_reason_counts 派生 constraint 计数器 ---
    diag = dict(result.get("candidate_diag_reason_counts") or {})
    counters["cash_skip_count"] = _sum_reason_aliases(diag, "SKIP_CASH_INSUFFICIENT", "SKIP_NO_CASH")
    counters["lot_skip_count"] = _sum_reason_aliases(diag, "SKIP_LOT_TOO_SMALL", "SKIP_QTY_ZERO")
    counters["cap_hit_single"] = int(diag.get("BLOCK_SINGLE_CAP", 0) or 0)
    counters["cap_hit_industry"] = int(diag.get("BLOCK_INDUSTRY_CAP", 0) or 0)
    counters["min_hold_block_count"] = int(diag.get("BLOCK_MIN_HOLD", 0) or 0)
    counters["cooldown_block_count"] = int(diag.get("BLOCK_COOLDOWN", 0) or 0)
    counters["entry_above_slow_ma_block_count"] = int(result.get("entry_above_slow_ma_block_count", 0) or 0)
    counters["entry_slope_block_count"] = int(result.get("entry_slope_block_count", 0) or 0)

    # --- regime router 计数器 ---
    counters["regime_trend_days"] = int(result.get("regime_trend_days", 0) or 0)
    counters["regime_mr_days"] = int(result.get("regime_mr_days", 0) or 0)
    counters["mr_rsi_oversold_buy_count"] = int(result.get("mr_rsi_oversold_buy_count", 0) or 0)
    counters["mr_rsi_overbought_sell_count"] = int(result.get("mr_rsi_overbought_sell_count", 0) or 0)
    counters["mr_stop_loss_count"] = int(result.get("mr_stop_loss_count", 0) or 0)
    counters["mr_time_exit_count"] = int(result.get("mr_time_exit_count", 0) or 0)
    counters["regime_filter_diagnostics"] = dict(result.get("regime_filter_diagnostics") or {})

    # --- MA200 市场过滤器计数器 ---
    counters["market_state_bull_days"] = int(result.get("market_state_bull_days", 0) or 0)
    counters["market_state_bear_days"] = int(result.get("market_state_bear_days", 0) or 0)
    counters["market_state_trans_down_days"] = int(result.get("market_state_trans_down_days", 0) or 0)
    counters["market_state_trans_up_days"] = int(result.get("market_state_trans_up_days", 0) or 0)
    counters["trade_mode_main_days"] = int(result.get("trade_mode_main_days", 0) or 0)
    counters["trade_mode_light_days"] = int(result.get("trade_mode_light_days", 0) or 0)
    counters["trade_mode_notrade_days"] = int(result.get("trade_mode_notrade_days", 0) or 0)

    # --- 派生字段 ---
    avg_pos = counters["avg_positions"]
    max_pos = counters["max_positions"]
    counters["slots_left"] = round(float(max_pos) - float(avg_pos), 1)
    counters["buy_orders_count"] = int(buy_orders_count)
    counters["sell_orders_count"] = int(sell_orders_count)
    buy_stage_funnel, buy_block_reason_counts = _build_buy_stage_funnel(result, results_dir, buy_orders_count)
    counters["buy_stage_funnel"] = buy_stage_funnel
    counters["buy_block_reason_counts"] = buy_block_reason_counts

    return sanitize_json(counters)


def _resolve_backtest_range(base_cfg: dict[str, Any], overrides: dict[str, Any]) -> tuple[str, str]:
    uni = dict(base_cfg.get("universe") or {})
    start = str(overrides.get("start_date") or uni.get("start") or "").strip()
    end = str(overrides.get("end_date") or uni.get("end") or "").strip()
    return start, end


def _load_runtime_universe(results_dir: Path) -> dict[str, Any]:
    """Load compiled runtime universe from run_config.json when available."""
    p = results_dir / "run_config.json"
    if not p.exists():
        return {}
    try:
        obj = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    u = obj.get("universe")
    return dict(u) if isinstance(u, dict) else {}


def _empty_close_history_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["symbol", "trade_date", "close"])


def _load_close_history_df(
    *,
    symbols: list[str],
    start_date: str,
    end_date: str,
    base_cfg: dict[str, Any],
) -> pd.DataFrame:
    if not symbols or not start_date or not end_date:
        return _empty_close_history_frame()
    try:
        import psycopg
        from backend.core.data.mapping import safe_ident

        ds = dict(base_cfg.get("data_source") or {})
        sm = dict(base_cfg.get("schema_mapping") or {})
        stocks_table = str(ds.get("stocks_table") or "pams_ohlcv_daily")
        mp = dict(sm.get(stocks_table) or {})
        date_col = str(mp.get("date") or "trade_date")
        symbol_col = str(mp.get("symbol") or "symbol")
        close_col = str(mp.get("close") or "close")

        q = (
            f"SELECT {safe_ident(symbol_col)} AS symbol, {safe_ident(date_col)} AS trade_date, {safe_ident(close_col)} AS close "
            f"FROM {safe_ident(stocks_table)} "
            f"WHERE {safe_ident(date_col)} >= %s AND {safe_ident(date_col)} <= %s "
            f"AND {safe_ident(symbol_col)} = ANY(%s) "
            f"ORDER BY {safe_ident(date_col)} ASC"
        )
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", os.environ.get("PAMS_PG_HOST", "pams-postgres")),
            port=int(os.environ.get("PGPORT", os.environ.get("PAMS_PG_PORT", "5432"))),
            dbname=os.environ.get("PGDATABASE", os.environ.get("PAMS_PG_DBNAME", "pams")),
            user=os.environ.get("PGUSER", os.environ.get("PAMS_PG_USER", "pams")),
            password=os.environ.get("PGPASSWORD", os.environ.get("PAMS_PG_PASSWORD", "")),
            autocommit=True,
        )
        with conn.cursor() as cur:
            cur.execute(q, (start_date, end_date, list({str(s).lower() for s in symbols})))
            rows = cur.fetchall()
        conn.close()
        if not rows:
            return _empty_close_history_frame()
        df = pd.DataFrame(rows, columns=["symbol", "trade_date", "close"])
        df["symbol"] = df["symbol"].astype(str).str.lower()
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        return df.dropna(subset=["trade_date", "close"]).sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    except Exception as exc:
        logger.warning("load_close_history_df failed: %s", exc)
        return _empty_close_history_frame()


def _last_close_map_from_history(df: pd.DataFrame | None) -> dict[str, float]:
    if df is None or df.empty:
        return {}
    last_close = df.groupby("symbol", as_index=False).tail(1)
    return {str(r.symbol): float(r.close) for r in last_close.itertuples(index=False)}


def _load_last_close_map(
    *,
    symbols: list[str],
    start_date: str,
    end_date: str,
    base_cfg: dict[str, Any],
) -> dict[str, float]:
    df = _load_close_history_df(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        base_cfg=base_cfg,
    )
    return _last_close_map_from_history(df)


def _empty_symbol_performance_frame() -> pd.DataFrame:
    return build_symbol_performance(
        trades_df=pd.DataFrame(),
        last_close_map={},
        last_date=None,
    )


def _resolve_validation_audit_ref(
    *,
    explicit_ref: dict[str, Any] | None,
    result: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any] | None:
    for candidate in (
        explicit_ref,
        result.get("validation_audit_ref"),
        overrides.get("validation_audit_ref"),
    ):
        if isinstance(candidate, dict) and candidate:
            return sanitize_json(dict(candidate))
    return None


def _finalize_research_audit(
    *,
    bt_root: Path,
    results_dir: Path,
    result: dict[str, Any],
    base_cfg: dict[str, Any],
    overrides: dict[str, Any],
    validation_audit_ref: dict[str, Any] | None,
) -> dict[str, Any] | None:
    audit_path = results_dir / "audit.json"
    audit_payload = _safe_read_json(audit_path)
    stage_summary_obj = _extract_stage_summary(result)
    stage_pipeline_obj = _extract_stage_pipeline_summary(result, stage_summary_obj)
    if not isinstance(audit_payload, dict):
        base_audit = (result.get("metrics") or {}).get("audit")
        if not isinstance(base_audit, dict):
            base_audit = {}
        audit_payload = merge_experiment_audit(
            base_audit,
            stage_pipeline=stage_pipeline_obj if isinstance(stage_pipeline_obj, dict) else None,
            stage_summary=stage_summary_obj if isinstance(stage_summary_obj, dict) else None,
            exp_id=str(result.get("exp_id") or ""),
        )
    if not isinstance(audit_payload, dict):
        audit_payload = {}

    research_audit = build_research_audit(
        results_dir=results_dir,
        result=result,
        manifest=result.get("manifest") if isinstance(result.get("manifest"), dict) else None,
        stage_summary=stage_summary_obj if isinstance(stage_summary_obj, dict) else None,
        stage_pipeline=stage_pipeline_obj if isinstance(stage_pipeline_obj, dict) else None,
        validation_audit_ref=_resolve_validation_audit_ref(
            explicit_ref=validation_audit_ref,
            result=result,
            overrides=overrides,
        ),
        bt_root=bt_root,
        artifact_presence={
            "run_meta": (results_dir / "run_meta.json").exists(),
            "manifest": (results_dir / "manifest.json").exists(),
            "audit": True,
        },
    )
    audit_payload["research_audit"] = sanitize_json(research_audit)
    audit_path.write_text(json.dumps(sanitize_json(audit_payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return audit_payload


def ensure_standard_artifacts(
    *,
    results_dir: Path,
    result: dict[str, Any],
    base_cfg: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    results_dir.mkdir(parents=True, exist_ok=True)
    missing_fields: list[str] = []

    perf_obj = {
        "total_return": _safe_float(result.get("total_return")),
        "max_drawdown": _safe_float(result.get("max_drawdown")),
        "cagr": _safe_float(result.get("cagr")),
        "sharpe": _safe_float(result.get("sharpe")),
        "calmar": _safe_float(result.get("calmar")),
        "top10_profit_concentration": _safe_float(result.get("top10_profit_concentration")),
        "tier": str(result.get("tier") or ""),
        "trades": _safe_int(result.get("trades")),
        "turnover": _safe_float(result.get("turnover")),
        "candidate_ready_date": str(result.get("candidate_ready_date") or ""),
        "effective_signal_start_date": str(result.get("effective_signal_start_date") or ""),
        "effective_execution_start_date": str(result.get("effective_execution_start_date") or ""),
        "metrics_from_effective_start": bool(result.get("metrics_from_effective_start", False)),
        "effective_observation_days": _safe_int(result.get("effective_observation_days")),
    }
    perf_path = results_dir / ARTIFACT_FILENAMES["perf"]
    perf_path.write_text(json.dumps(sanitize_json(perf_obj), ensure_ascii=False, indent=2), encoding="utf-8")

    nav_path = _write_nav_csv(results_dir, result)
    try:
        nav_df = pd.read_csv(nav_path)
    except Exception:
        nav_df = pd.DataFrame()
    if nav_df.empty:
        missing_fields.append(MISSING_FIELD_KEYS["nav"])

    # 从 result dict 取 funnel 数据；若为 0 则尝试从 portfolio_trades.csv 派生
    raw_signal = int(_safe_int(result.get("raw_signal")) or 0)
    blocked = int(_safe_int(result.get("blocked")) or 0)
    orders = int(_safe_int(result.get("orders")) or 0)
    skipped = int(_safe_int(result.get("skipped")) or 0)
    closed_trades = int(_safe_int(result.get("closed_trades")) or 0)

    trades_path = results_dir / "portfolio_trades.csv"
    reason_rows: list[dict[str, Any]] = []
    if trades_path.exists():
        try:
            tdf = pd.read_csv(trades_path)
            if not tdf.empty and "side" in tdf.columns:
                buy_df = tdf[tdf["side"].astype(str).str.upper() == "BUY"]
                sell_df = tdf[tdf["side"].astype(str).str.upper() == "SELL"]
                if raw_signal == 0:
                    raw_signal = int(len(buy_df))
                if orders == 0:
                    orders = int(len(tdf))
                if closed_trades == 0:
                    closed_trades = int(len(sell_df))
            # 从 trades 构建 reason_code 汇总
            if not tdf.empty and "reason_code" in tdf.columns:
                rc_counts = tdf["reason_code"].astype(str).value_counts()
                reason_rows = [
                    {"reason_code": str(code), "count": int(cnt)}
                    for code, cnt in rc_counts.items()
                    if str(code).strip()
                ]
        except Exception:
            pass

    funnel_obj = {
        "raw_signal": raw_signal,
        "blocked": blocked,
        "orders": orders,
        "skipped": skipped,
        "closed_trades": closed_trades,
    }
    funnel_path = results_dir / ARTIFACT_FILENAMES["funnel"]
    pd.DataFrame([funnel_obj]).to_csv(funnel_path, index=False)
    if not any(result.get(k) is not None for k in ("raw_signal", "blocked", "orders", "skipped", "closed_trades")):
        missing_fields.append(MISSING_FIELD_KEYS["funnel"])

    reason_path = results_dir / ARTIFACT_FILENAMES["reason_codes"]
    if reason_rows:
        pd.DataFrame(reason_rows).to_csv(reason_path, index=False)
    else:
        pd.DataFrame(columns=["reason_code", "count"]).to_csv(reason_path, index=False)
        missing_fields.append(MISSING_FIELD_KEYS["reason_codes"])

    # stock_names.json / trade_st_flags.json — 仅使用 PIT 安全 ST 信息修正历史展示名
    stock_names: dict[str, str] = {}
    trade_st_flags_path = results_dir / "trade_st_flags.json"
    trade_st_flags: dict[str, str] = {}
    stock_names_path = results_dir / "stock_names.json"
    if trades_path.exists():
        try:
            tdf_trades = pd.read_csv(trades_path)
            if not tdf_trades.empty and "symbol" in tdf_trades.columns:
                unique_symbols = list(tdf_trades["symbol"].dropna().unique())
                raw_stock_names = _resolve_stock_names(unique_symbols)
                trade_st_flags = _resolve_trade_st_flags(tdf_trades, raw_stock_names)
                stock_names = _sanitize_historical_stock_names(tdf_trades, raw_stock_names, trade_st_flags)
        except Exception as exc:
            logger.warning("build stock_names/trade_st_flags failed: %s", exc)
            stock_names = {}
            trade_st_flags = {}
    stock_names_path.write_text(json.dumps(stock_names, ensure_ascii=False, indent=2), encoding="utf-8")
    trade_st_flags_path.write_text(json.dumps(trade_st_flags, ensure_ascii=False, indent=2), encoding="utf-8")

    orders_path = _write_csv_alias(
        trades_path,
        results_dir / ARTIFACT_FILENAMES["orders"],
        empty_columns=[
            "date",
            "symbol",
            "side",
            "price",
            "qty",
            "reason_code",
            "exit_owner",
            "entry_alpha_id",
            "entry_sleeve_id",
            "entry_reason_code",
            "entry_date",
        ],
    )
    candidate_signals_path, candidate_signals_df = _build_candidate_signals(results_dir)
    alpha_funnel_path = _build_alpha_funnel(results_dir, candidate_signals_df)
    score_diagnostics_path = _build_score_diagnostics(results_dir, candidate_signals_df)

    symbol_perf_csv_path = results_dir / ARTIFACT_FILENAMES["symbol_performance"]
    symbol_perf_json_path = results_dir / "symbol_performance.json"
    try:
        if trades_path.exists():
            tdf_sp = pd.read_csv(trades_path)
            if not tdf_sp.empty and "symbol" in tdf_sp.columns:
                symbols = [str(x).lower() for x in tdf_sp["symbol"].dropna().unique().tolist()]
                last_date = None
                try:
                    nav_df = pd.read_csv(nav_path)
                    if not nav_df.empty and "date" in nav_df.columns:
                        ts = pd.to_datetime(nav_df["date"], errors="coerce").dropna().max()
                        last_date = ts.date() if pd.notna(ts) else None
                except Exception:
                    last_date = None
                history_start, history_end = _resolve_backtest_range(base_cfg, overrides)
                trade_date_col = "date" if "date" in tdf_sp.columns else ("trade_date" if "trade_date" in tdf_sp.columns else None)
                if trade_date_col is not None:
                    trade_dates = pd.to_datetime(tdf_sp[trade_date_col], errors="coerce").dropna()
                    if not trade_dates.empty:
                        history_start = trade_dates.min().date().isoformat()
                        history_end_date = trade_dates.max().date()
                        if last_date is not None:
                            history_end_date = max(history_end_date, last_date)
                        history_end = history_end_date.isoformat()
                close_history_df = _load_close_history_df(
                    symbols=symbols,
                    start_date=history_start,
                    end_date=history_end,
                    base_cfg=base_cfg,
                )
                last_close_map = _last_close_map_from_history(close_history_df)
                sp_df = build_symbol_performance(
                    trades_df=tdf_sp,
                    last_close_map=last_close_map,
                    last_date=last_date,
                    daily_close_df=close_history_df,
                )
            else:
                sp_df = pd.DataFrame()
        else:
            sp_df = _empty_symbol_performance_frame()
        if sp_df.empty and not list(sp_df.columns):
            sp_df = _empty_symbol_performance_frame()
        sp_df.to_csv(symbol_perf_csv_path, index=False)
        if sp_df.empty:
            missing_fields.append(MISSING_FIELD_KEYS["symbol_performance"])
        symbol_perf_json_path.write_text(
            json.dumps({"rows": sanitize_json(sp_df.to_dict(orient="records"))}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("build symbol_performance failed: %s", exc)
        _empty_symbol_performance_frame().to_csv(symbol_perf_csv_path, index=False)
        symbol_perf_json_path.write_text(json.dumps({"rows": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        missing_fields.append(MISSING_FIELD_KEYS["symbol_performance"])

    config_path = results_dir / ARTIFACT_FILENAMES["config"]
    config_path.write_text(
        json.dumps(
            sanitize_json({"base_config": base_cfg, "overrides": overrides}),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    runtime_uni = _load_runtime_universe(results_dir)
    original_wb = dict((overrides.get("original_workbench_config") or {})) if isinstance(overrides.get("original_workbench_config"), dict) else {}
    wb_uni = dict(original_wb.get("universe") or {}) if isinstance(original_wb.get("universe"), dict) else {}
    base_uni = dict(base_cfg.get("universe") or {})

    def _pick_with_source(candidates: list[tuple[Any, str]]) -> tuple[Any, str, bool]:
        if not candidates:
            return None, "missing", True
        primary = candidates[0][1]
        for value, source in candidates:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value, source, source != primary
        return None, "missing", True

    start_v, start_src, start_fallback = _pick_with_source([
        (runtime_uni.get("start"), "run_config.universe.start"),
        (wb_uni.get("start"), "original_workbench_config.universe.start"),
        (overrides.get("start_date"), "overrides.start_date"),
        (base_uni.get("start"), "base_config.universe.start"),
    ])
    end_v, end_src, end_fallback = _pick_with_source([
        (runtime_uni.get("end"), "run_config.universe.end"),
        (wb_uni.get("end"), "original_workbench_config.universe.end"),
        (overrides.get("end_date"), "overrides.end_date"),
        (base_uni.get("end"), "base_config.universe.end"),
    ])
    benchmark_v, benchmark_src, benchmark_fallback = _pick_with_source([
        (runtime_uni.get("benchmark"), "run_config.universe.benchmark"),
        (wb_uni.get("benchmark"), "original_workbench_config.universe.benchmark"),
        (overrides.get("benchmark"), "overrides.benchmark"),
        (base_uni.get("benchmark"), "base_config.universe.benchmark"),
    ])
    resolved_config_mode = str(
        overrides.get("resolved_config_mode") or result.get("resolved_config_mode") or "none"
    )
    resolved_config_id = overrides.get("resolved_config_id")
    if resolved_config_id in (None, ""):
        resolved_config_id = result.get("resolved_config_id")
    resolved_config_hash = str(
        overrides.get("resolved_config_hash") or result.get("resolved_config_hash") or ""
    ).strip()
    resolved_config_meta_raw = overrides.get("resolved_config_meta")
    if not isinstance(resolved_config_meta_raw, dict):
        resolved_config_meta_raw = result.get("resolved_config_meta")
    resolved_config_meta = (
        sanitize_json(dict(resolved_config_meta_raw)) if isinstance(resolved_config_meta_raw, dict) else None
    )
    resolved_universe_mode = str(
        (resolved_config_meta or {}).get("universe_mode")
        or runtime_uni.get("universe_mode")
        or wb_uni.get("universe_mode")
        or overrides.get("universe_mode")
        or (result.get("universe_meta") or {}).get("universe_mode")
        or ""
    ).strip()
    if resolved_config_meta is not None and resolved_universe_mode and not resolved_config_meta.get("universe_mode"):
        resolved_config_meta = dict(resolved_config_meta)
        resolved_config_meta["universe_mode"] = resolved_universe_mode
    stage_summary_obj = _extract_stage_summary(result)
    stage_pipeline_obj = _extract_stage_pipeline_summary(result, stage_summary_obj)
    stage_summary_rel = None
    if isinstance(stage_summary_obj, dict) and stage_summary_obj:
        stage_summary_path = results_dir / ARTIFACT_FILENAMES["stage_summary"]
        stage_summary_path.write_text(
            json.dumps(sanitize_json(stage_summary_obj), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        stage_summary_rel = _to_rel(stage_summary_path, results_dir)

    run_meta_obj = {
        "exp_id": str(result.get("exp_id") or ""),
        "tier": str(result.get("tier") or "T0"),
        "status": str(result.get("status") or "OK"),
        "created_at": datetime.now().isoformat(),
        "data": {
            "start": start_v,
            "end": end_v,
            "benchmark": benchmark_v,
            "compare_symbol": overrides.get("compare_symbol") or base_cfg.get("universe", {}).get("benchmark_compare_symbol"),
            "universe_limit": _safe_int(overrides.get("universe_limit")),
        },
        "code": {
            "engine_mode": str(overrides.get("engine_mode") or "VECTOR_FAST_STRICT"),
            "execution_profile": str(overrides.get("execution_profile") or "tradable"),
            "fast_mode": bool(overrides.get("fast_mode", True)),
        },
        "counters": _build_counters(result, results_dir, funnel_obj),
        "price_adj_mode": str(result.get("price_adj_mode") or "hfq"),
        "adj_factor_stats": sanitize_json(result.get("adj_factor_stats") or {}),
        "missing_fields": sorted(set(missing_fields)),
        "warmup": sanitize_json(result.get("warmup_analysis") or {}),
        "report_consistency": {
            "sources": {
                "start": start_src,
                "end": end_src,
                "benchmark": benchmark_src,
                "funnel": "funnel.csv",
            },
            "fallbacks": {
                "start": bool(start_fallback),
                "end": bool(end_fallback),
                "benchmark": bool(benchmark_fallback),
            },
            "config_source": str(overrides.get("config_source") or "unknown"),
            "config_conflict_policy": str(overrides.get("config_conflict_policy") or ""),
            "resolved_config_mode": resolved_config_mode,
            "resolved_config_id": str(resolved_config_id or "") or None,
            "resolved_config_hash": resolved_config_hash or None,
            "resolved_config_source_type": str((resolved_config_meta or {}).get("source_type") or ""),
            "resolved_config_owner": str((resolved_config_meta or {}).get("owner") or ""),
            "resolved_config_schema_version": str((resolved_config_meta or {}).get("schema_version") or ""),
            "resolved_config_source": str((resolved_config_meta or {}).get("config_source") or overrides.get("config_source") or ""),
            "resolved_config_compiler_hash": str((resolved_config_meta or {}).get("config_hash") or resolved_config_hash or ""),
            "resolved_config_meta": resolved_config_meta,
        },
    }
    # 注入 universe resolver 元数据（来自 experiment_runner）
    u_meta = result.get("universe_meta")
    if isinstance(u_meta, dict):
        run_meta_obj["universe"] = sanitize_json(u_meta)
        run_meta_obj["data"]["universe_mode"] = str(u_meta.get("universe_mode") or "CUSTOM")
    data_bundle = result.get("data_bundle")
    if isinstance(data_bundle, dict):
        run_meta_obj["data_bundle"] = sanitize_json(data_bundle)
    candidate_ctx = overrides.get("candidate_context")
    if isinstance(candidate_ctx, dict) and candidate_ctx:
        run_meta_obj["candidate"] = sanitize_json(candidate_ctx)
    if isinstance(stage_pipeline_obj, dict) and stage_pipeline_obj:
        run_meta_obj["stage_pipeline"] = sanitize_json(stage_pipeline_obj)
    run_meta_path = results_dir / ARTIFACT_FILENAMES["run_meta"]
    run_meta_path.write_text(json.dumps(sanitize_json(run_meta_obj), ensure_ascii=False, indent=2), encoding="utf-8")

    # 写入 audit.json（审计检查点数据）
    audit_data = (result.get("metrics") or {}).get("audit")
    if not isinstance(audit_data, dict):
        audit_data = {}
    audit_data = merge_experiment_audit(
        audit_data,
        stage_pipeline=stage_pipeline_obj if isinstance(stage_pipeline_obj, dict) else None,
        stage_summary=stage_summary_obj if isinstance(stage_summary_obj, dict) else None,
        exp_id=str(result.get("exp_id") or ""),
    )
    audit_rel = None
    if isinstance(audit_data, dict) and audit_data:
        try:
            audit_path = results_dir / "audit.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False, indent=2), encoding="utf-8")
            audit_rel = _to_rel(audit_path, results_dir)
        except Exception as exc:
            logger.warning("Failed to write audit.json: %s", exc)

    artifacts = {
        "perf": _to_rel(perf_path, results_dir),
        "nav": _to_rel(nav_path, results_dir),
        "funnel": _to_rel(funnel_path, results_dir),
        "reason_codes": _to_rel(reason_path, results_dir),
        "config": _to_rel(config_path, results_dir),
        "run_meta": _to_rel(run_meta_path, results_dir),
        "stock_names": _to_rel(stock_names_path, results_dir),
        "trade_st_flags": _to_rel(trade_st_flags_path, results_dir),
        "symbol_performance": _to_rel(symbol_perf_csv_path, results_dir),
        "orders": _to_rel(orders_path, results_dir),
        "candidate_signals": _to_rel(candidate_signals_path, results_dir),
        "alpha_funnel": _to_rel(alpha_funnel_path, results_dir),
        "score_diagnostics": _to_rel(score_diagnostics_path, results_dir),
        "audit": audit_rel,
        "stage_summary": stage_summary_rel,
    }
    # 如果引擎已写出 trades CSV，也加入 artifacts 映射
    if trades_path.exists():
        artifacts["trades"] = _to_rel(trades_path, results_dir)
    # 如果引擎已写出 daily CSV，也加入 artifacts 映射（供报告生成使用）
    daily_path = results_dir / ARTIFACT_FILENAMES["daily"]
    if daily_path.exists():
        artifacts["daily"] = _to_rel(daily_path, results_dir)
    for extra_name in ("input_config.json", "resolved_config.json", "compiled_plan.json", "baseline_compare.json"):
        extra_path = results_dir / extra_name
        if extra_path.exists():
            artifacts[extra_name.replace(".json", "")] = _to_rel(extra_path, results_dir)

    out = dict(result)
    out["status"] = str(out.get("status") or "OK")
    out["artifacts"] = artifacts
    return sanitize_json(out)


def write_manifest(results_dir: Path, result: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    artifacts = dict(result.get("artifacts") or {})
    baseline_compare_path = results_dir / "baseline_compare.json"
    if baseline_compare_path.exists():
        artifacts.setdefault("baseline_compare", _to_rel(baseline_compare_path, results_dir))
    config_snapshots = _manifest_config_snapshots(results_dir, artifacts)
    core_keys = (
        "perf",
        "nav",
        "funnel",
        "reason_codes",
        "config",
        "run_meta",
        "trades",
        "daily",
        "input_config",
        "resolved_config",
        "compiled_plan",
        "baseline_compare",
        "audit",
        "stage_summary",
    )
    core_artifacts = {
        key: str(artifacts.get(key) or "")
        for key in core_keys
        if str(artifacts.get(key) or "").strip()
    }
    stage_summary = _extract_stage_summary(result)
    stage_pipeline = _extract_stage_pipeline_summary(result, stage_summary)
    manifest = {
        "exp_id": str(result.get("exp_id") or ""),
        "experiment_id": str(result.get("exp_id") or ""),
        "status": str(result.get("status") or "OK"),
        "created_at": datetime.now().isoformat(),
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "artifacts": artifacts,
        "config_snapshots": config_snapshots,
        "core_artifacts": core_artifacts,
        "baseline_compare_status": _baseline_compare_status(results_dir),
        "metrics": {
            "total_return": _safe_float(result.get("total_return")),
            "max_drawdown": _safe_float(result.get("max_drawdown")),
            "cagr": _safe_float(result.get("cagr")),
            "sharpe": _safe_float(result.get("sharpe")),
            "trades": _safe_int(result.get("trades")),
            "turnover": _safe_float(result.get("turnover")),
            "effective_execution_start_date": str(result.get("effective_execution_start_date") or ""),
            "metrics_from_effective_start": bool(result.get("metrics_from_effective_start", False)),
        },
    }
    if isinstance(stage_pipeline, dict) and stage_pipeline:
        manifest["stage_pipeline"] = sanitize_json(stage_pipeline)
    if isinstance(stage_summary, dict) and stage_summary:
        manifest["stage_summary"] = sanitize_json(
            {
                "artifact": str(artifacts.get("stage_summary") or ""),
                "schema_version": stage_summary.get("schema_version"),
            }
        )
    path = results_dir / "manifest.json"
    path.write_text(json.dumps(sanitize_json(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return path, manifest


def _append_to_experiment_index(
    results_dir: Path,
    result: dict[str, Any],
    base_cfg: dict[str, Any],
    overrides: dict[str, Any],
) -> None:
    """Append an experiment summary to outputs/experiments/index.json."""
    experiments_root = results_dir.parent
    index_path = experiments_root / "index.json"

    # Read existing index
    entries: list[dict[str, Any]] = []
    if index_path.exists():
        try:
            entries = json.loads(index_path.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        except Exception:
            entries = []

    exp_id = str(result.get("exp_id") or "")
    label = _generate_experiment_label(base_cfg, overrides)
    entry = {
        "exp_id": exp_id,
        "label": label,
        "created_at": datetime.now().isoformat(),
        "status": str(result.get("status") or "OK"),
        "total_return": _safe_float(result.get("total_return")),
        "max_drawdown": _safe_float(result.get("max_drawdown")),
        "sharpe": _safe_float(result.get("sharpe")),
        "trades": _safe_int(result.get("trades")),
        "has_manifest": (results_dir / "manifest.json").exists(),
    }

    # Remove existing entry for same exp_id (re-run)
    entries = [e for e in entries if e.get("exp_id") != exp_id]
    entries.append(sanitize_json(entry))

    index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def stabilize_experiment_result(
    *,
    bt_root: Path,
    result: dict[str, Any],
    base_cfg: dict[str, Any],
    overrides: dict[str, Any],
    run_profile_summary: dict[str, Any] | None,
    validation_audit_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from backend.core.services.experiment_artifact_service import stabilize_experiment_output

    return stabilize_experiment_output(
        bt_root=bt_root,
        result=result,
        base_cfg=base_cfg,
        overrides=overrides,
        run_profile_summary=run_profile_summary,
        validation_audit_ref=validation_audit_ref,
    )
