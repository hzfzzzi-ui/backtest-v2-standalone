from __future__ import annotations

from datetime import date
from datetime import timedelta
import math
import json
import os
import re
from pathlib import Path
import tempfile
from typing import Any

import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.core.config.loader import load_config
from backend.core.data.provider import DataProvider
from backend.core.data.provider_factory import build_runtime_provider_from_config
from backend.core.portfolio.metrics import compute_backtest_metrics
from backend.core.universe.hs300_csi500 import UniverseFilterConfig, apply_universe_filters
from backend.core.universe.universe_resolver import resolve_universe_by_mode


def required_valid_days(trading_days_in_month: int) -> int:
    count = max(int(trading_days_in_month or 0), 0)
    return max(15, int(math.ceil(count * 0.8))) if count > 0 else 15


def _normalize_industry_label(value: Any) -> str:
    return str(value or "").strip()


def _resolve_allowed_industry_l1(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = [item for item in re.split(r"[,，;；|/]+", value) if str(item).strip()]
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = [value]
    out: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        label = _normalize_industry_label(item)
        if not label or label in seen:
            continue
        out.append(label)
        seen.add(label)
    return out


def _to_internal_symbol_local(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    if not text:
        return ""
    if text.startswith(("sh", "sz")) and len(text) == 8:
        return text
    if "." in text:
        code, exch = text.split(".", 1)
        if exch in {"sh", "sz"} and len(code) == 6:
            return f"{exch}{code}"
    return text


def _build_active_industry_l1_map(industry_history: pd.DataFrame, as_of: date) -> dict[str, str]:
    if industry_history is None or industry_history.empty:
        return {}
    frame = industry_history.copy()
    frame["symbol"] = frame.get("ts_code", frame.get("symbol", pd.Series(dtype=str))).astype(str).map(_to_internal_symbol_local)
    frame["start_date"] = pd.to_datetime(frame.get("start_date"), errors="coerce").dt.normalize()
    frame["end_date"] = pd.to_datetime(frame.get("end_date"), errors="coerce").dt.normalize()
    frame["industry_l1"] = frame.get("industry_l1", pd.Series(dtype=str)).map(_normalize_industry_label)
    as_of_ts = pd.Timestamp(as_of).normalize()
    frame = frame[frame["symbol"].astype(bool)]
    frame = frame[frame["industry_l1"].astype(bool)]
    frame = frame[frame["start_date"].isna() | (frame["start_date"] <= as_of_ts)]
    frame = frame[frame["end_date"].isna() | (frame["end_date"] >= as_of_ts)]
    if frame.empty:
        return {}
    frame = frame.sort_values(["symbol", "start_date", "end_date"], na_position="last")
    latest = frame.groupby("symbol", as_index=False).tail(1)
    return {
        str(row.symbol): str(row.industry_l1)
        for row in latest.itertuples(index=False)
        if str(row.symbol).strip() and str(row.industry_l1).strip()
    }


def _apply_allowed_industry_filter(
    candidates: pd.DataFrame,
    allowed_industry_l1: list[str] | None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    allowed = {_normalize_industry_label(item) for item in (allowed_industry_l1 or []) if _normalize_industry_label(item)}
    if not allowed or candidates is None or candidates.empty:
        return candidates.copy() if isinstance(candidates, pd.DataFrame) else pd.DataFrame(), {}
    frame = candidates.copy()
    if "industry_l1" not in frame.columns:
        frame["industry_l1"] = ""
    frame["industry_l1"] = frame["industry_l1"].map(_normalize_industry_label)
    mask = frame["industry_l1"].isin(allowed)
    excluded = int((~mask).sum())
    return frame.loc[mask].copy(), ({"EXCLUDE_INDUSTRY_NOT_ALLOWED": excluded} if excluded > 0 else {})


def _apply_repair_screen_filters(
    candidates: pd.DataFrame,
    *,
    liquidity_bottom_quantile: float = 0.0,
    price_repair_min_ma20_ratio: float = 0.0,
) -> tuple[pd.DataFrame, dict[str, int], dict[str, float | None]]:
    frame = candidates.copy() if isinstance(candidates, pd.DataFrame) else pd.DataFrame()
    if frame.empty:
        return frame, {}, {
            "liquidity_threshold_avg_turnover_20d": None,
            "price_repair_min_ma20_ratio": None,
        }

    frame["avg_turnover_20d"] = pd.to_numeric(frame.get("avg_turnover_20d"), errors="coerce")
    frame["last_close"] = pd.to_numeric(frame.get("last_close"), errors="coerce")
    frame["ma20_close"] = pd.to_numeric(frame.get("ma20_close"), errors="coerce")

    excluded_counts: dict[str, int] = {}
    audit_meta: dict[str, float | None] = {
        "liquidity_threshold_avg_turnover_20d": None,
        "price_repair_min_ma20_ratio": None,
    }

    quantile = float(liquidity_bottom_quantile or 0.0)
    if quantile > 0.0:
        valid_turnover = frame["avg_turnover_20d"].dropna()
        if not valid_turnover.empty:
            threshold = float(valid_turnover.quantile(min(max(quantile, 0.0), 1.0)))
            audit_meta["liquidity_threshold_avg_turnover_20d"] = threshold
            liquidity_mask = frame["avg_turnover_20d"].notna() & frame["avg_turnover_20d"].ge(threshold)
            excluded = int((~liquidity_mask).sum())
            if excluded > 0:
                excluded_counts["EXCLUDE_LIQUIDITY_BOTTOM_QUANTILE"] = excluded
            frame = frame.loc[liquidity_mask].copy()

    min_ma_ratio = float(price_repair_min_ma20_ratio or 0.0)
    if min_ma_ratio > 0.0 and not frame.empty:
        audit_meta["price_repair_min_ma20_ratio"] = min_ma_ratio
        price_mask = (
            frame["last_close"].notna()
            & frame["ma20_close"].notna()
            & frame["ma20_close"].gt(0.0)
            & frame["last_close"].ge(frame["ma20_close"] * min_ma_ratio)
        )
        excluded = int((~price_mask).sum())
        if excluded > 0:
            excluded_counts["EXCLUDE_PRICE_REPAIR_BELOW_MA20"] = excluded
        frame = frame.loc[price_mask].copy()

    return frame, excluded_counts, audit_meta


def assess_moneyflow_gate(
    observation_dates: list[date],
    whitelist: pd.DataFrame,
    *,
    required_row_coverage_ratio: float = 0.95,
    required_net_coverage_ratio: float = 0.90,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    gate_frame = whitelist.copy() if whitelist is not None else pd.DataFrame()
    if not gate_frame.empty and "trade_date" in gate_frame.columns:
        gate_frame["trade_date"] = pd.to_datetime(gate_frame["trade_date"], errors="coerce").dt.normalize()
        gate_frame = gate_frame.dropna(subset=["trade_date"]).sort_values("trade_date")
        gate_frame = gate_frame.drop_duplicates(subset=["trade_date"], keep="last")
        gate_map = {
            pd.Timestamp(row.trade_date).date(): row._asdict()
            for row in gate_frame.itertuples(index=False)
        }
    else:
        gate_map = {}

    for observation_date in observation_dates:
        raw = gate_map.get(observation_date)
        if raw is None:
            rows.append(
                {
                    "trade_date": pd.Timestamp(observation_date),
                    "row_coverage_ratio": pd.NA,
                    "net_amount_coverage_ratio": pd.NA,
                    "required_row_coverage_ratio": float(required_row_coverage_ratio),
                    "required_net_coverage_ratio": float(required_net_coverage_ratio),
                    "allow_in_research": False,
                    "gate_status": "blocked_missing_gate",
                    "gate_reason": "MISSING_WHITELIST_ENTRY",
                }
            )
            continue

        row_ratio = pd.to_numeric(pd.Series([raw.get("row_coverage_ratio")]), errors="coerce").iloc[0]
        net_ratio = pd.to_numeric(pd.Series([raw.get("net_amount_coverage_ratio")]), errors="coerce").iloc[0]
        allow_raw = raw.get("allow_in_research")
        allow = bool(allow_raw) if allow_raw is not None and not pd.isna(allow_raw) else False
        allow = allow and pd.notna(row_ratio) and pd.notna(net_ratio)
        allow = allow and float(row_ratio) >= float(required_row_coverage_ratio)
        allow = allow and float(net_ratio) >= float(required_net_coverage_ratio)
        rows.append(
            {
                "trade_date": pd.Timestamp(observation_date),
                "row_coverage_ratio": None if pd.isna(row_ratio) else float(row_ratio),
                "net_amount_coverage_ratio": None if pd.isna(net_ratio) else float(net_ratio),
                "required_row_coverage_ratio": float(required_row_coverage_ratio),
                "required_net_coverage_ratio": float(required_net_coverage_ratio),
                "allow_in_research": bool(allow),
                "gate_status": "tradable" if allow else "skipped_low_coverage",
                "gate_reason": "" if allow else "LOW_MONEYFLOW_COVERAGE",
            }
        )

    return pd.DataFrame(rows)


def synthesize_moneyflow_gate_from_daily_coverage(
    provider: DataProvider,
    symbols: list[str],
    observation_dates: list[date],
    *,
    moneyflow_table: str,
    required_row_coverage_ratio: float = 0.95,
    required_net_coverage_ratio: float = 0.90,
) -> pd.DataFrame:
    expected_symbols = len({str(symbol).lower() for symbol in symbols if str(symbol).strip()})
    rows: list[dict[str, Any]] = []
    for observation_date in observation_dates:
        if expected_symbols <= 0:
            row_ratio = 0.0
            net_ratio = 0.0
        else:
            daily = provider.load_stock_moneyflow(symbols, observation_date, observation_date, table=moneyflow_table)
            if daily is None or daily.empty:
                row_ratio = 0.0
                net_ratio = 0.0
            else:
                daily = daily.copy()
                daily["symbol"] = daily.get("symbol", pd.Series(dtype=str)).astype(str).str.lower()
                daily["trade_date"] = pd.to_datetime(
                    daily.get("trade_date", daily.get("date")),
                    errors="coerce",
                ).dt.normalize()
                daily["net_mf_amount"] = pd.to_numeric(daily.get("net_mf_amount"), errors="coerce")
                daily = daily[daily["trade_date"] == pd.Timestamp(observation_date)]
                daily = daily.dropna(subset=["symbol"]).drop_duplicates(subset=["symbol"], keep="last")
                row_ratio = float(daily["symbol"].nunique() / expected_symbols)
                net_ratio = float(daily.loc[daily["net_mf_amount"].notna(), "symbol"].nunique() / expected_symbols)
        allow = row_ratio >= float(required_row_coverage_ratio) and net_ratio >= float(required_net_coverage_ratio)
        rows.append(
            {
                "trade_date": pd.Timestamp(observation_date),
                "row_coverage_ratio": float(row_ratio),
                "net_amount_coverage_ratio": float(net_ratio),
                "required_row_coverage_ratio": float(required_row_coverage_ratio),
                "required_net_coverage_ratio": float(required_net_coverage_ratio),
                "allow_in_research": bool(allow),
                "gate_status": "tradable" if allow else "skipped_low_coverage",
                "gate_reason": "" if allow else "LOW_MONEYFLOW_COVERAGE",
            }
        )
    return pd.DataFrame(rows)


def _has_whitelist_coverage(whitelist: pd.DataFrame, observation_dates: list[date]) -> bool:
    if whitelist is None or whitelist.empty or "trade_date" not in whitelist.columns:
        return False
    frame = whitelist.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    available = {pd.Timestamp(value).date() for value in frame["trade_date"].dropna().tolist()}
    return any(observation_date in available for observation_date in observation_dates)


def build_daily_divergence_frame(
    price_history: pd.DataFrame,
    moneyflow: pd.DataFrame,
    *,
    denominator_mode: str = "avg20_circ_mv",
) -> pd.DataFrame:
    if price_history is None or price_history.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "circ_mv",
                "avg20_circ_mv",
                "amount",
                "avg20_amount",
                "net_mf_amount",
                "daily_divergence_rate",
                "factor_valid",
            ]
        )

    price = price_history.copy()
    price["date"] = pd.to_datetime(price["date"], errors="coerce").dt.normalize()
    price["symbol"] = price["symbol"].astype(str).str.lower()
    price["circ_mv"] = pd.to_numeric(price.get("circ_mv"), errors="coerce")
    price["amount"] = pd.to_numeric(price.get("amount"), errors="coerce")
    price = price.sort_values(["symbol", "date"]).reset_index(drop=True)

    if moneyflow is None or moneyflow.empty:
        merged = price[["date", "symbol", "circ_mv", "amount"]].copy()
        merged["trade_date"] = merged["date"]
        merged["net_mf_amount"] = pd.NA
    else:
        mf = moneyflow.copy()
        mf_date_col = "trade_date" if "trade_date" in mf.columns else "date"
        mf["trade_date"] = pd.to_datetime(mf[mf_date_col], errors="coerce").dt.normalize()
        mf["symbol"] = mf["symbol"].astype(str).str.lower()
        mf["net_mf_amount"] = pd.to_numeric(mf.get("net_mf_amount"), errors="coerce")
        merged = price.merge(
            mf[["trade_date", "symbol", "net_mf_amount"]],
            left_on=["date", "symbol"],
            right_on=["trade_date", "symbol"],
            how="left",
        )

    merged["circ_mv_window_count"] = (
        merged.groupby("symbol")["circ_mv"].transform(lambda series: series.rolling(20, min_periods=20).count())
    )
    merged["avg20_circ_mv"] = (
        merged.groupby("symbol")["circ_mv"].transform(lambda series: series.rolling(20, min_periods=20).mean())
    )
    merged["amount_window_count"] = (
        merged.groupby("symbol")["amount"].transform(lambda series: series.rolling(20, min_periods=20).count())
    )
    merged["avg20_amount"] = (
        merged.groupby("symbol")["amount"].transform(lambda series: series.rolling(20, min_periods=20).mean())
    )
    denominator = str(denominator_mode or "avg20_circ_mv").strip().lower() or "avg20_circ_mv"
    if denominator == "avg20_amount":
        merged["factor_valid"] = (
            merged["net_mf_amount"].notna()
            & merged["amount"].notna()
            & merged["avg20_amount"].notna()
            & merged["amount_window_count"].eq(20.0)
            & merged["avg20_amount"].gt(0.0)
        )
    else:
        merged["factor_valid"] = (
            merged["net_mf_amount"].notna()
            & merged["circ_mv"].notna()
            & merged["avg20_circ_mv"].notna()
            & merged["circ_mv_window_count"].eq(20.0)
            & merged["avg20_circ_mv"].gt(0.0)
        )
    merged["daily_divergence_rate"] = pd.NA
    valid_mask = merged["factor_valid"]
    base_series = merged["avg20_amount"] if denominator == "avg20_amount" else merged["avg20_circ_mv"]
    merged.loc[valid_mask, "daily_divergence_rate"] = merged.loc[valid_mask, "net_mf_amount"].abs() / base_series.loc[valid_mask]
    return merged[
        [
            "date",
            "symbol",
            "circ_mv",
            "avg20_circ_mv",
            "amount",
            "avg20_amount",
            "net_mf_amount",
            "daily_divergence_rate",
            "factor_valid",
        ]
    ].copy()


def build_monthly_divergence_panel(daily_divergence: pd.DataFrame) -> pd.DataFrame:
    if daily_divergence is None or daily_divergence.empty:
        return pd.DataFrame(
            columns=[
                "month",
                "symbol",
                "monthly_divergence_rate",
                "valid_days",
                "month_trading_days",
                "required_valid_days",
                "month_end_valid",
                "monthly_factor_valid",
            ]
        )

    frame = daily_divergence.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["month"] = frame["date"].dt.to_period("M").dt.to_timestamp()
    frame["daily_divergence_rate"] = pd.to_numeric(frame["daily_divergence_rate"], errors="coerce")
    frame["factor_valid"] = frame["factor_valid"].fillna(False).astype(bool)

    month_sizes = (
        frame.groupby(["month", "symbol"], dropna=False)["date"]
        .count()
        .rename("month_trading_days")
        .reset_index()
    )
    grouped = (
        frame.groupby(["month", "symbol"], dropna=False)
        .agg(
            monthly_divergence_rate=("daily_divergence_rate", "mean"),
            valid_days=("factor_valid", "sum"),
            month_end_valid=("factor_valid", "last"),
        )
        .reset_index()
    )
    grouped = grouped.merge(month_sizes, on=["month", "symbol"], how="left")
    grouped["required_valid_days"] = grouped["month_trading_days"].astype(int).map(required_valid_days)
    grouped["monthly_factor_valid"] = (
        grouped["month_end_valid"].fillna(False).astype(bool)
        & grouped["valid_days"].astype(int).ge(grouped["required_valid_days"].astype(int))
        & grouped["monthly_divergence_rate"].notna()
    )
    return grouped[
        [
            "month",
            "symbol",
            "monthly_divergence_rate",
            "valid_days",
            "month_trading_days",
            "required_valid_days",
            "month_end_valid",
            "monthly_factor_valid",
        ]
    ].copy()


def build_month_end_candidate_snapshot(
    price_history: pd.DataFrame,
    observation_dates: list[date],
    *,
    security_master: pd.DataFrame | None = None,
    st_history: pd.DataFrame | None = None,
    turnover_rate_field: str = "turnover_rate_f",
) -> pd.DataFrame:
    if price_history is None or price_history.empty or not observation_dates:
        return pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "in_hs300",
                "in_csi500",
                "is_st",
                "is_delisted",
                "is_star_market",
                "is_chinext",
                "security_name",
                "is_suspended",
                "list_days",
                "avg_turnover_20d",
                "avg_turnover_rate_20d",
                "last_close",
                "ma20_close",
                "circ_mv",
                "limit_lock",
            ]
        )

    from backend.core.universe.hs300_csi500 import is_chinext_symbol, is_star_market_symbol

    df = price_history.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.lower()
    df["amount"] = pd.to_numeric(df.get("amount"), errors="coerce")
    df["volume"] = pd.to_numeric(df.get("volume"), errors="coerce")
    df["close"] = pd.to_numeric(df.get("close"), errors="coerce")
    if turnover_rate_field in df.columns:
        df[turnover_rate_field] = pd.to_numeric(df.get(turnover_rate_field), errors="coerce")
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    df["avg_turnover_20d"] = df.groupby("symbol")["amount"].transform(lambda series: series.rolling(20, min_periods=20).mean())
    df["ma20_close"] = df.groupby("symbol")["close"].transform(lambda series: series.rolling(20, min_periods=20).mean())
    if turnover_rate_field in df.columns:
        df["avg_turnover_rate_20d"] = df.groupby("symbol")[turnover_rate_field].transform(
            lambda series: series.rolling(20, min_periods=20).mean()
        )
    else:
        df["avg_turnover_rate_20d"] = pd.NA

    sm_frame = security_master.copy() if security_master is not None else pd.DataFrame()
    sm_frame["symbol"] = sm_frame.get("symbol", pd.Series(dtype=str)).astype(str).str.lower()
    sm_frame["list_date"] = pd.to_datetime(sm_frame.get("list_date"), errors="coerce").dt.normalize()
    sm_frame["delist_date"] = pd.to_datetime(sm_frame.get("delist_date"), errors="coerce").dt.normalize()
    sm_map = {
        str(row.symbol): {
            "list_date": row.list_date,
            "delist_date": row.delist_date,
            "name": str(getattr(row, "name", "") or "").strip(),
        }
        for row in sm_frame.itertuples(index=False)
    }
    st_periods: dict[str, list[tuple[pd.Timestamp, pd.Timestamp | None]]] = {}
    if st_history is not None and not st_history.empty:
        temp = st_history.copy()
        temp["symbol"] = temp.get("ts_code", temp.get("symbol", pd.Series(dtype=str))).astype(str)
        temp["symbol"] = temp["symbol"].str.lower().map(
            lambda text: f"{text.split('.', 1)[1]}{text.split('.', 1)[0]}".lower() if "." in text else text
        )
        temp["start_date"] = pd.to_datetime(temp.get("start_date"), errors="coerce").dt.normalize()
        temp["end_date"] = pd.to_datetime(temp.get("end_date"), errors="coerce").dt.normalize()
        for row in temp.itertuples(index=False):
            if not isinstance(row.start_date, pd.Timestamp) or pd.isna(row.start_date):
                continue
            st_periods.setdefault(str(row.symbol), []).append((pd.Timestamp(row.start_date), row.end_date))

    observation_index = {pd.Timestamp(item).normalize() for item in observation_dates}
    snap = df[df["date"].isin(observation_index)].copy()
    rows: list[dict[str, Any]] = []
    for row in snap.itertuples(index=False):
        symbol = str(row.symbol)
        trade_dt = pd.Timestamp(row.date).normalize()
        sm = sm_map.get(symbol, {})
        list_date = sm.get("list_date")
        delist_date = sm.get("delist_date")
        list_days = 0
        if isinstance(list_date, pd.Timestamp) and not pd.isna(list_date):
            list_days = max(0, int((trade_dt - list_date).days) + 1)
        rows.append(
            {
                "date": trade_dt,
                "symbol": symbol,
                "in_hs300": True,
                "in_csi500": True,
                "is_st": any(
                    start_dt <= trade_dt <= end_dt if isinstance(end_dt, pd.Timestamp) and not pd.isna(end_dt) else start_dt <= trade_dt
                    for start_dt, end_dt in st_periods.get(symbol, [])
                ),
                "is_delisted": bool(isinstance(delist_date, pd.Timestamp) and not pd.isna(delist_date) and delist_date <= trade_dt),
                "is_star_market": bool(is_star_market_symbol(symbol)),
                "is_chinext": bool(is_chinext_symbol(symbol)),
                "security_name": str(sm.get("name") or ""),
                "is_suspended": bool(pd.notna(row.volume) and float(row.volume) <= 0.0),
                "list_days": int(list_days),
                "avg_turnover_20d": None if pd.isna(row.avg_turnover_20d) else float(row.avg_turnover_20d),
                "avg_turnover_rate_20d": None if pd.isna(row.avg_turnover_rate_20d) else float(row.avg_turnover_rate_20d),
                "last_close": None if pd.isna(row.close) else float(row.close),
                "ma20_close": None if pd.isna(row.ma20_close) else float(row.ma20_close),
                "circ_mv": None if pd.isna(getattr(row, "circ_mv", pd.NA)) else float(getattr(row, "circ_mv")),
                "limit_lock": False,
            }
        )
    return pd.DataFrame(rows)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _results_root() -> Path:
    raw = os.environ.get("RESULTS_ROOT", "outputs").strip() or "outputs"
    path = Path(raw)
    if not path.is_absolute():
        path = (_repo_root() / path).resolve()
    return path


def _create_provider_from_payload(request_payload: dict[str, Any]) -> tuple[DataProvider, dict[str, Any], str]:
    config_json = request_payload.get("config_json")
    if isinstance(config_json, dict):
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
            handle.write(json.dumps(sanitize_json(config_json), ensure_ascii=False, indent=2))
            temp_path = handle.name
        try:
            cfg_obj, config_hash = load_config(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)
    else:
        config_path = str(request_payload.get("config_path") or "").strip()
        if not config_path:
            raise ValueError("custom study runner requires request_payload.config_path")
        cfg_obj, config_hash = load_config(config_path)
    provider = build_runtime_provider_from_config(
        cfg_obj,
        (_repo_root() / "config" / "rules.csv").resolve(),
    )
    return provider, cfg_obj.to_dict(), config_hash


def _month_end_observation_dates(calendar: pd.DatetimeIndex, start: date, end: date) -> list[date]:
    if calendar.empty:
        return []
    frame = pd.DataFrame({"date": pd.to_datetime(calendar).normalize()})
    frame = frame[(frame["date"] >= pd.Timestamp(start)) & (frame["date"] <= pd.Timestamp(end))].copy()
    if frame.empty:
        return []
    frame["month"] = frame["date"].dt.to_period("M")
    month_end = frame.groupby("month", sort=True)["date"].max().tolist()
    return [pd.Timestamp(item).date() for item in month_end]


def _observation_chunk_start(observation_date: date) -> date:
    obs_ts = pd.Timestamp(observation_date).normalize()
    month_start = obs_ts.to_period("M").to_timestamp()
    return min((month_start - pd.Timedelta(days=60)).date(), (obs_ts - pd.Timedelta(days=60)).date())


def _build_observation_month_slice(
    *,
    provider: DataProvider,
    symbols: list[str],
    observation_date: date,
    moneyflow_table: str,
    denominator_mode: str,
    security_master: pd.DataFrame | None,
    st_history: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    obs_ts = pd.Timestamp(observation_date).normalize()
    chunk_start = _observation_chunk_start(observation_date)
    price_chunk = provider.load_ohlcv_daily(symbols, chunk_start, observation_date, source="moneyflow_divergence")
    moneyflow_chunk = provider.load_stock_moneyflow(symbols, chunk_start, observation_date, table=moneyflow_table)
    daily_divergence = build_daily_divergence_frame(
        price_chunk,
        moneyflow_chunk,
        denominator_mode=denominator_mode,
    )
    monthly_panel = build_monthly_divergence_panel(daily_divergence)
    month_rows = monthly_panel[
        (monthly_panel["month"] == obs_ts.to_period("M").to_timestamp())
        & (monthly_panel["monthly_factor_valid"].fillna(False).astype(bool))
    ].copy()
    candidate_rows = build_month_end_candidate_snapshot(
        price_chunk,
        [observation_date],
        security_master=security_master,
        st_history=st_history,
    )
    return month_rows, candidate_rows


def _write_csv(frame: pd.DataFrame, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def _write_json(payload: dict[str, Any], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def build_monthly_rebalance_schedule(
    trading_days: list[date] | pd.DatetimeIndex,
    observation_dates: list[date],
    coverage_ledger: pd.DataFrame,
    *,
    end_date: date | None = None,
) -> pd.DataFrame:
    calendar = [pd.Timestamp(item).normalize() for item in list(trading_days) if trading_days is not None]
    next_day_map = {
        calendar[idx].date(): calendar[idx + 1]
        for idx in range(len(calendar) - 1)
    }
    gate_map = {
        pd.Timestamp(row.trade_date).date(): row._asdict()
        for row in coverage_ledger.itertuples(index=False)
    } if coverage_ledger is not None and not coverage_ledger.empty else {}
    end_ts = pd.Timestamp(end_date).normalize() if end_date is not None else None

    rows: list[dict[str, Any]] = []
    for observation_date in observation_dates:
        obs_ts = pd.Timestamp(observation_date).normalize()
        raw_gate = gate_map.get(observation_date, {})
        execution_ts = next_day_map.get(observation_date)
        planned_rebalance = execution_ts is not None
        if end_ts is not None and execution_ts is not None and execution_ts > end_ts:
            planned_rebalance = False
            execution_ts = None
        gate_status = str(raw_gate.get("gate_status") or "")
        gate_reason = str(raw_gate.get("gate_reason") or "")
        schedule_status = gate_status
        schedule_reason = gate_reason
        if not planned_rebalance and gate_status == "tradable":
            schedule_status = "blocked_missing_execution_day"
            schedule_reason = "MISSING_NEXT_TRADING_DAY"
        rows.append(
            {
                "observation_date": obs_ts,
                "month": obs_ts.to_period("M").to_timestamp(),
                "execution_date": execution_ts,
                "gate_status": gate_status,
                "gate_reason": gate_reason,
                "schedule_status": schedule_status,
                "schedule_reason": schedule_reason,
                "planned_rebalance": bool(planned_rebalance),
                "can_rebalance": bool(planned_rebalance and gate_status == "tradable"),
            }
        )
    return pd.DataFrame(rows)


def _extract_runtime_costs(cfg_snapshot: dict[str, Any]) -> tuple[float, int, dict[str, float]]:
    execution = dict(cfg_snapshot.get("execution") or {})
    costs_cfg = dict(cfg_snapshot.get("costs") or {})
    return (
        float(cfg_snapshot.get("initial_capital", 100000.0) or 100000.0),
        max(int(execution.get("lot_size", 100) or 100), 1),
        {
            "commission_rate": float(costs_cfg.get("commission_rate", 0.0003) or 0.0003),
            "commission_min": float(costs_cfg.get("commission_min", 5.0) or 5.0),
            "stamp_tax_rate": float(costs_cfg.get("stamp_tax_rate", 0.001) or 0.001),
            "slippage_bps": float(costs_cfg.get("slippage_bps", 2.0) or 2.0),
        },
    )


def _normalize_price_history(price_history: pd.DataFrame) -> pd.DataFrame:
    if price_history is None or price_history.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "open",
                "close",
                "volume",
                "amount",
                "is_suspended",
                "limit_up",
                "limit_down",
            ]
        )
    frame = price_history.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.lower()
    for column in ("open", "close", "volume", "amount", "limit_up", "limit_down"):
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce")
    if "is_suspended" in frame.columns:
        numeric = pd.to_numeric(frame["is_suspended"], errors="coerce")
        if numeric.notna().any():
            frame["is_suspended"] = numeric.fillna(0.0).ne(0.0)
        else:
            text = frame["is_suspended"].astype(str).str.strip().str.lower()
            frame["is_suspended"] = text.isin({"1", "true", "t", "yes", "y", "on"})
    else:
        frame["is_suspended"] = False
    return frame.dropna(subset=["date", "symbol"]).sort_values(["date", "symbol"]).reset_index(drop=True)


def _round_down_to_lot(qty: int, lot_size: int) -> int:
    if int(qty or 0) <= 0:
        return 0
    lot = max(int(lot_size or 0), 1)
    return int(qty // lot) * lot


def _max_affordable_buy_qty(
    *,
    cash_available: float,
    fill_px: float,
    lot_size: int,
    commission_rate: float,
    commission_min: float,
) -> int:
    if float(cash_available or 0.0) <= 0.0 or float(fill_px or 0.0) <= 0.0:
        return 0
    lot = max(int(lot_size or 0), 1)
    qty = _round_down_to_lot(int(float(cash_available) / float(fill_px)), lot)
    while qty > 0:
        gross = float(qty) * float(fill_px)
        comm = max(float(commission_min or 0.0), gross * float(commission_rate or 0.0)) if gross > 0.0 else 0.0
        if gross + comm <= float(cash_available) + 1e-8:
            return int(qty)
        qty -= lot
    return 0


def _bar_is_tradable(
    day: pd.Timestamp,
    symbol: str,
    *,
    side: str,
    open_idx: dict[tuple[pd.Timestamp, str], float | None],
    volume_idx: dict[tuple[pd.Timestamp, str], float | None],
    amount_idx: dict[tuple[pd.Timestamp, str], float | None],
    suspended_idx: dict[tuple[pd.Timestamp, str], bool],
    limit_up_idx: dict[tuple[pd.Timestamp, str], float | None],
    limit_down_idx: dict[tuple[pd.Timestamp, str], float | None],
) -> bool:
    key = (pd.Timestamp(day).normalize(), str(symbol).lower())
    open_px = open_idx.get(key)
    if open_px is None or float(open_px) <= 0.0:
        return False
    if bool(suspended_idx.get(key, False)):
        return False
    volume = volume_idx.get(key)
    if volume is not None and float(volume) <= 0.0:
        return False
    amount = amount_idx.get(key)
    if amount is not None and float(amount) <= 0.0:
        return False
    if str(side).upper() == "BUY":
        limit_up = limit_up_idx.get(key)
        if limit_up is not None and float(open_px) >= float(limit_up) - (abs(float(limit_up)) * 1e-4 + 1e-6):
            return False
    if str(side).upper() == "SELL":
        limit_down = limit_down_idx.get(key)
        if limit_down is not None and float(open_px) <= float(limit_down) + (abs(float(limit_down)) * 1e-4 + 1e-6):
            return False
    return True


def _mark_price_for_nav(
    day: pd.Timestamp,
    symbol: str,
    *,
    close_idx: dict[tuple[pd.Timestamp, str], float | None],
    open_idx: dict[tuple[pd.Timestamp, str], float | None],
    last_close_map: dict[str, float],
    avg_cost: dict[str, float],
) -> float:
    key = (pd.Timestamp(day).normalize(), str(symbol).lower())
    close_px = close_idx.get(key)
    if close_px is not None and float(close_px) > 0.0:
        return float(close_px)
    open_px = open_idx.get(key)
    if open_px is not None and float(open_px) > 0.0:
        return float(open_px)
    if symbol in last_close_map:
        return float(last_close_map[symbol])
    return float(avg_cost.get(symbol, 0.0) or 0.0)


def _build_perf_daily_frame(daily_df: pd.DataFrame, effective_execution_start_date: str | None) -> pd.DataFrame:
    if daily_df is None or daily_df.empty or not effective_execution_start_date:
        return pd.DataFrame()
    frame = daily_df.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date")
    frame = frame[frame["date"] >= pd.Timestamp(effective_execution_start_date).normalize()].copy()
    if frame.empty:
        return frame
    nav = pd.to_numeric(frame["nav"], errors="coerce")
    frame = frame.loc[nav.notna()].copy()
    if frame.empty:
        return frame
    nav = pd.to_numeric(frame["nav"], errors="coerce").astype(float)
    frame["daily_return"] = nav.pct_change().replace([math.inf, -math.inf], pd.NA).fillna(0.0)
    frame["drawdown"] = (nav / nav.cummax()) - 1.0
    frame["positions_count"] = pd.to_numeric(frame.get("positions_count"), errors="coerce").fillna(0.0).astype(int)
    frame["turnover_pct"] = pd.to_numeric(frame.get("turnover_pct"), errors="coerce").fillna(0.0)
    return frame.reset_index(drop=True)


def _build_nav_frame(daily_df: pd.DataFrame, effective_execution_start_date: str | None) -> pd.DataFrame:
    if daily_df is None or daily_df.empty:
        return pd.DataFrame(columns=["date", "nav"])
    frame = daily_df.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["nav"] = pd.to_numeric(frame["nav"], errors="coerce")
    frame = frame.dropna(subset=["date", "nav"]).sort_values("date")
    if effective_execution_start_date:
        frame = frame[frame["date"] >= pd.Timestamp(effective_execution_start_date).normalize()].copy()
    if frame.empty:
        return pd.DataFrame(columns=["date", "nav"])
    nav0 = float(frame["nav"].iloc[0])
    if nav0 > 0.0:
        frame["nav"] = frame["nav"].astype(float) / nav0
    frame["date"] = frame["date"].dt.date.astype(str)
    return frame[["date", "nav"]].reset_index(drop=True)


def _empty_perf_payload() -> dict[str, Any]:
    return {
        "total_return": 0.0,
        "cagr": 0.0,
        "max_drawdown": 0.0,
        "sharpe": 0.0,
        "calmar": 0.0,
        "trades": 0,
        "orders": 0,
        "closed_trades": 0,
        "raw_signal": 0,
        "blocked": 0,
        "skipped": 0,
        "turnover": 0.0,
        "effective_execution_start_date": "",
    }


def _resolve_target_weights(selection_frame: pd.DataFrame, weight_mode: str = "equal_weight") -> dict[str, float]:
    if selection_frame is None or selection_frame.empty:
        return {}
    mode = str(weight_mode or "equal_weight").strip().lower() or "equal_weight"
    frame = selection_frame.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.lower()
    frame["rank"] = pd.to_numeric(frame["rank"], errors="coerce")
    frame = frame.dropna(subset=["rank"]).sort_values(["rank", "symbol"]).reset_index(drop=True)
    if frame.empty:
        return {}
    if mode == "equal_weight":
        weight = 1.0 / float(len(frame))
        return {str(row.symbol): float(weight) for row in frame.itertuples(index=False)}
    if mode == "rank_decay_linear":
        max_rank = int(frame["rank"].max())
        frame["raw_weight"] = frame["rank"].map(lambda rank: max(float(max_rank + 1 - int(rank)), 0.0))
        total = float(frame["raw_weight"].sum())
        if total <= 0.0:
            raise ValueError("rank_decay_linear produced non-positive total raw weight")
        return {
            str(row.symbol): float(row.raw_weight) / total
            for row in frame.itertuples(index=False)
        }
    raise ValueError(f"unsupported weight_mode: {weight_mode}")


def run_monthly_rebalance_backtest(
    price_history: pd.DataFrame,
    trading_days: list[date] | pd.DatetimeIndex,
    schedule: pd.DataFrame,
    selection_frame: pd.DataFrame,
    *,
    initial_capital: float = 100000.0,
    lot_size: int = 100,
    commission_rate: float = 0.0003,
    commission_min: float = 5.0,
    stamp_tax_rate: float = 0.001,
    slippage_bps: float = 2.0,
    weight_mode: str = "equal_weight",
) -> dict[str, Any]:
    normalized = _normalize_price_history(price_history)
    calendar = [pd.Timestamp(item).normalize() for item in list(trading_days) if trading_days is not None]
    if not calendar:
        return {
            "portfolio_daily": pd.DataFrame(),
            "portfolio_trades": pd.DataFrame(),
            "orders": pd.DataFrame(),
            "nav": pd.DataFrame(columns=["date", "nav"]),
            "perf": _empty_perf_payload(),
            "summary": {
                "executed_rebalance_days": 0,
                "raw_signal_count": 0,
                "skipped_buy_orders": 0,
                "untradable_sell_blocks": 0,
                "untradable_buy_blocks": 0,
            },
            "effective_execution_start_date": None,
        }

    open_idx = {
        (pd.Timestamp(row.date).normalize(), str(row.symbol)): None if pd.isna(row.open) else float(row.open)
        for row in normalized.itertuples(index=False)
    }
    close_idx = {
        (pd.Timestamp(row.date).normalize(), str(row.symbol)): None if pd.isna(row.close) else float(row.close)
        for row in normalized.itertuples(index=False)
    }
    volume_idx = {
        (pd.Timestamp(row.date).normalize(), str(row.symbol)): None if pd.isna(row.volume) else float(row.volume)
        for row in normalized.itertuples(index=False)
    }
    amount_idx = {
        (pd.Timestamp(row.date).normalize(), str(row.symbol)): None if pd.isna(row.amount) else float(row.amount)
        for row in normalized.itertuples(index=False)
    }
    suspended_idx = {
        (pd.Timestamp(row.date).normalize(), str(row.symbol)): bool(row.is_suspended)
        for row in normalized.itertuples(index=False)
    }
    limit_up_idx = {
        (pd.Timestamp(row.date).normalize(), str(row.symbol)): None if pd.isna(row.limit_up) else float(row.limit_up)
        for row in normalized.itertuples(index=False)
    }
    limit_down_idx = {
        (pd.Timestamp(row.date).normalize(), str(row.symbol)): None if pd.isna(row.limit_down) else float(row.limit_down)
        for row in normalized.itertuples(index=False)
    }

    schedule_frame = schedule.copy() if schedule is not None else pd.DataFrame()
    if not schedule_frame.empty:
        schedule_frame["execution_date"] = pd.to_datetime(schedule_frame["execution_date"], errors="coerce").dt.normalize()
        schedule_frame["observation_date"] = pd.to_datetime(schedule_frame["observation_date"], errors="coerce").dt.normalize()
        schedule_frame["planned_rebalance"] = schedule_frame["planned_rebalance"].fillna(False).astype(bool)
        schedule_frame["can_rebalance"] = schedule_frame["can_rebalance"].fillna(False).astype(bool)
    schedule_map = {
        pd.Timestamp(row.execution_date).normalize(): row._asdict()
        for row in schedule_frame.itertuples(index=False)
        if isinstance(row.execution_date, pd.Timestamp) and not pd.isna(row.execution_date)
    }

    selection = selection_frame.copy() if selection_frame is not None else pd.DataFrame()
    if not selection.empty:
        selection["execution_date"] = pd.to_datetime(selection["execution_date"], errors="coerce").dt.normalize()
        selection["observation_date"] = pd.to_datetime(selection["observation_date"], errors="coerce").dt.normalize()
        selection["symbol"] = selection["symbol"].astype(str).str.lower()
        selection["rank"] = pd.to_numeric(selection["rank"], errors="coerce")
    selection_map = {
        key: frame.sort_values(["rank", "symbol"]).reset_index(drop=True)
        for key, frame in selection.groupby("execution_date", dropna=True)
    } if not selection.empty else {}

    slip_bps = float(slippage_bps or 0.0) / 10000.0
    lot = max(int(lot_size or 0), 1)
    cash = float(initial_capital or 0.0)
    positions: dict[str, int] = {}
    avg_cost: dict[str, float] = {}
    holding_source: dict[str, dict[str, Any]] = {}
    last_close_map: dict[str, float] = {}
    trade_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    peak_nav = float(initial_capital or 0.0)
    prev_nav = float(initial_capital or 0.0)
    effective_execution_start_date: str | None = None
    executed_rebalance_days = 0
    raw_signal_count = 0
    skipped_buy_orders = 0
    untradable_sell_blocks = 0
    untradable_buy_blocks = 0

    for day in calendar:
        traded_value = 0.0
        schedule_row = schedule_map.get(day)
        day_selection = selection_map.get(day)
        selected_count = int(len(day_selection)) if day_selection is not None else 0
        candidates_count = selected_count
        buy_slots = selected_count

        if schedule_row is not None and bool(schedule_row.get("can_rebalance")) and day_selection is not None and not day_selection.empty:
            raw_signal_count += int(len(day_selection))
            desired_symbols = [str(item).lower() for item in day_selection["symbol"].tolist()]
            desired_ranks = {
                str(row.symbol): int(row.rank)
                for row in day_selection.itertuples(index=False)
                if pd.notna(row.rank)
            }
            target_weight_map = _resolve_target_weights(day_selection, weight_mode=weight_mode)
            portfolio_open_value = float(cash)
            for symbol, qty in positions.items():
                portfolio_open_value += float(qty) * _mark_price_for_nav(
                    day,
                    symbol,
                    close_idx=close_idx,
                    open_idx=open_idx,
                    last_close_map=last_close_map,
                    avg_cost=avg_cost,
                )
            target_qty_map: dict[str, int] = {}
            for symbol in desired_symbols:
                current_qty = int(positions.get(symbol, 0))
                if _bar_is_tradable(
                    day,
                    symbol,
                    side="BUY",
                    open_idx=open_idx,
                    volume_idx=volume_idx,
                    amount_idx=amount_idx,
                    suspended_idx=suspended_idx,
                    limit_up_idx=limit_up_idx,
                    limit_down_idx=limit_down_idx,
                ):
                    open_px = float(open_idx.get((day, symbol)) or 0.0)
                    fill_px = open_px * (1.0 + slip_bps)
                    target_value = float(portfolio_open_value) * float(target_weight_map.get(symbol, 0.0))
                    raw_qty = int(target_value / fill_px) if fill_px > 0.0 else 0
                    target_qty_map[symbol] = _round_down_to_lot(raw_qty, lot)
                else:
                    target_qty_map[symbol] = current_qty
                    if current_qty <= 0:
                        untradable_buy_blocks += 1

            sell_orders: list[dict[str, Any]] = []
            buy_orders: list[dict[str, Any]] = []
            for symbol, current_qty in sorted(positions.items()):
                target_qty = int(target_qty_map.get(symbol, 0))
                diff_qty = int(current_qty) - int(target_qty)
                if diff_qty <= 0:
                    continue
                sell_orders.append(
                    {
                        "symbol": symbol,
                        "qty": _round_down_to_lot(diff_qty, lot),
                        "reason_code": "MONTHLY_REBALANCE_EXIT" if symbol not in target_qty_map else "MONTHLY_REBALANCE_TRIM",
                        "rank": int(desired_ranks.get(symbol, 10**9)),
                    }
                )
            for symbol in desired_symbols:
                current_qty = int(positions.get(symbol, 0))
                target_qty = int(target_qty_map.get(symbol, current_qty))
                diff_qty = int(target_qty) - int(current_qty)
                if diff_qty <= 0:
                    continue
                buy_orders.append(
                    {
                        "symbol": symbol,
                        "qty": _round_down_to_lot(diff_qty, lot),
                        "reason_code": "MONTHLY_REBALANCE_ENTRY" if current_qty <= 0 else "MONTHLY_REBALANCE_ADD",
                        "rank": int(desired_ranks.get(symbol, 10**9)),
                    }
                )

            executed_any_trade = False
            for order in sell_orders:
                symbol = str(order["symbol"]).lower()
                qty = int(order["qty"])
                if qty <= 0:
                    continue
                if not _bar_is_tradable(
                    day,
                    symbol,
                    side="SELL",
                    open_idx=open_idx,
                    volume_idx=volume_idx,
                    amount_idx=amount_idx,
                    suspended_idx=suspended_idx,
                    limit_up_idx=limit_up_idx,
                    limit_down_idx=limit_down_idx,
                ):
                    untradable_sell_blocks += 1
                    continue
                held = int(positions.get(symbol, 0))
                qty = min(held, qty)
                if qty <= 0:
                    continue
                open_px = float(open_idx.get((day, symbol)) or 0.0)
                fill_px = open_px * (1.0 - slip_bps)
                gross = float(qty) * fill_px
                comm = max(float(commission_min or 0.0), gross * float(commission_rate or 0.0)) if gross > 0.0 else 0.0
                stax = gross * float(stamp_tax_rate or 0.0)
                net = gross - comm - stax
                cash += net
                traded_value += gross
                positions[symbol] = held - qty
                source = dict(holding_source.get(symbol, {}) or {})
                if positions[symbol] <= 0:
                    positions.pop(symbol, None)
                    avg_cost.pop(symbol, None)
                    holding_source.pop(symbol, None)
                trade_rows.append(
                    {
                        "date": day.date().isoformat(),
                        "symbol": symbol,
                        "side": "SELL",
                        "price": round(open_px, 4),
                        "fill_price": round(fill_px, 4),
                        "qty": int(qty),
                        "value": round(gross, 2),
                        "commission": round(comm, 2),
                        "stamp_tax": round(stax, 2),
                        "slippage": round(abs(fill_px - open_px) * qty, 2),
                        "net_amount": round(net, 2),
                        "reason_code": str(order["reason_code"]),
                        "triggered_rule": "moneyflow_divergence_monthly_min10",
                        "break_streak": 0,
                        "exit_owner": "monthly_rebalance",
                        "entry_alpha_id": "",
                        "entry_sleeve_id": "",
                        "entry_reason_code": str(source.get("entry_reason_code") or ""),
                        "entry_date": source.get("entry_date"),
                        "meta_json": json.dumps(
                            {
                                "observation_date": pd.Timestamp(schedule_row["observation_date"]).date().isoformat(),
                                "rank": int(order.get("rank", 10**9)),
                                "target_weight": float(target_weight_map.get(symbol, 0.0)),
                                "weight_mode": str(weight_mode or "equal_weight"),
                            },
                            ensure_ascii=False,
                        ),
                    }
                )
                executed_any_trade = True

            for order in sorted(buy_orders, key=lambda item: (int(item.get("rank", 10**9)), str(item.get("symbol")))):
                symbol = str(order["symbol"]).lower()
                qty = int(order["qty"])
                if qty <= 0:
                    continue
                if not _bar_is_tradable(
                    day,
                    symbol,
                    side="BUY",
                    open_idx=open_idx,
                    volume_idx=volume_idx,
                    amount_idx=amount_idx,
                    suspended_idx=suspended_idx,
                    limit_up_idx=limit_up_idx,
                    limit_down_idx=limit_down_idx,
                ):
                    untradable_buy_blocks += 1
                    continue
                open_px = float(open_idx.get((day, symbol)) or 0.0)
                fill_px = open_px * (1.0 + slip_bps)
                affordable_qty = _max_affordable_buy_qty(
                    cash_available=float(cash),
                    fill_px=float(fill_px),
                    lot_size=lot,
                    commission_rate=float(commission_rate or 0.0),
                    commission_min=float(commission_min or 0.0),
                )
                qty = _round_down_to_lot(min(qty, affordable_qty), lot)
                if qty <= 0:
                    skipped_buy_orders += 1
                    continue
                gross = float(qty) * fill_px
                comm = max(float(commission_min or 0.0), gross * float(commission_rate or 0.0)) if gross > 0.0 else 0.0
                net = gross + comm
                if net > cash:
                    skipped_buy_orders += 1
                    continue
                cash -= net
                traded_value += gross
                prev_qty = int(positions.get(symbol, 0))
                prev_avg = float(avg_cost.get(symbol, 0.0))
                new_qty = prev_qty + qty
                new_avg = ((prev_qty * prev_avg) + (qty * fill_px)) / float(new_qty) if new_qty > 0 else 0.0
                positions[symbol] = new_qty
                avg_cost[symbol] = float(new_avg)
                if prev_qty <= 0:
                    holding_source[symbol] = {
                        "entry_reason_code": str(order["reason_code"]),
                        "entry_date": day.date().isoformat(),
                    }
                trade_rows.append(
                    {
                        "date": day.date().isoformat(),
                        "symbol": symbol,
                        "side": "BUY",
                        "price": round(open_px, 4),
                        "fill_price": round(fill_px, 4),
                        "qty": int(qty),
                        "value": round(gross, 2),
                        "commission": round(comm, 2),
                        "stamp_tax": 0.0,
                        "slippage": round(abs(fill_px - open_px) * qty, 2),
                        "net_amount": round(net, 2),
                        "reason_code": str(order["reason_code"]),
                        "triggered_rule": "moneyflow_divergence_monthly_min10",
                        "break_streak": 0,
                        "exit_owner": "",
                        "entry_alpha_id": "",
                        "entry_sleeve_id": "",
                        "entry_reason_code": str(holding_source[symbol].get("entry_reason_code") or ""),
                        "entry_date": holding_source[symbol].get("entry_date"),
                        "meta_json": json.dumps(
                            {
                                "observation_date": pd.Timestamp(schedule_row["observation_date"]).date().isoformat(),
                                "rank": int(order.get("rank", 10**9)),
                                "target_weight": float(target_weight_map.get(symbol, 0.0)),
                                "weight_mode": str(weight_mode or "equal_weight"),
                            },
                            ensure_ascii=False,
                        ),
                    }
                )
                executed_any_trade = True

            if executed_any_trade:
                executed_rebalance_days += 1
                if effective_execution_start_date is None:
                    effective_execution_start_date = day.date().isoformat()

        market_value = 0.0
        top_positions: list[tuple[str, float]] = []
        for symbol, qty in sorted(positions.items()):
            mark_px = _mark_price_for_nav(
                day,
                symbol,
                close_idx=close_idx,
                open_idx=open_idx,
                last_close_map=last_close_map,
                avg_cost=avg_cost,
            )
            holding_value = float(qty) * float(mark_px)
            market_value += holding_value
            top_positions.append((symbol, holding_value))
        nav = float(cash) + float(market_value)
        peak_nav = max(float(peak_nav), float(nav))
        daily_return = (float(nav) / float(prev_nav) - 1.0) if float(prev_nav) > 0.0 else 0.0
        drawdown = (float(nav) / float(peak_nav) - 1.0) if float(peak_nav) > 0.0 else 0.0
        gross_exposure = float(market_value / nav) if float(nav) > 0.0 else 0.0
        turnover_pct = float(traded_value / prev_nav) if float(prev_nav) > 0.0 else 0.0
        trade_rows_today = [row for row in trade_rows if row["date"] == day.date().isoformat()]
        daily_rows.append(
            {
                "date": day.date().isoformat(),
                "nav": round(nav, 6),
                "cash": round(float(cash), 6),
                "positions_count": int(len(positions)),
                "positions_count_end_of_day": int(len(positions)),
                "daily_return": float(daily_return),
                "drawdown": float(drawdown),
                "gross_exposure": float(gross_exposure),
                "turnover_pct": float(turnover_pct),
                "top5_positions_json": json.dumps(
                    [{"symbol": symbol, "value": round(value, 2)} for symbol, value in sorted(top_positions, key=lambda item: item[1], reverse=True)[:5]],
                    ensure_ascii=False,
                ),
                "candidates_count": int(candidates_count),
                "selected_count": int(selected_count),
                "top5_selected_strength_json": "[]",
                "top5_rejected_strength_json": "[]",
                "buy_slots_before_buy": int(buy_slots),
                "buy_slots_after_sell": int(buy_slots),
                "raw_buy_signal_count": int(selected_count),
                "raw_alpha_signal_count": int(selected_count),
                "composed_buy_signal_count": int(selected_count),
                "composed_sell_signal_count": 0,
                "buy_candidate_count": int(candidates_count),
                "after_held_filter_count": int(candidates_count),
                "after_slot_filter_count": int(selected_count),
                "after_cash_lot_count": int(selected_count),
                "diagnostics_input_json": "{}",
                "positions_before_sell": "",
                "sells_executed_count": int(sum(1 for row in trade_rows_today if row["side"] == "SELL")),
                "positions_after_sell": int(len(positions)),
                "buy_slots_calculated": int(buy_slots),
                "candidates_after_held_filter_count": int(candidates_count),
                "sorting_triggered": 1 if selected_count > 0 else 0,
                "mean_order_value_scale": 1.0 if selected_count > 0 else 0.0,
                "weak_trend_buy_rate": 0.0,
                "strong_trend_buy_rate": 0.0,
                "mf_rank_triggered": 0,
                "mf_rank_applied": 0,
                "mf_candidates_when_triggered": 0,
                "mf_topk_reject_count": 0,
                "mf_concentrated_selected_count": 0,
                "mf_gate_on": 0,
                "strong_risk_on": 0,
                "mf_rank_suppressed_by_strong_gate": 0,
                "same_symbol_conflict_count": 0,
                "sleeve_budget_reject_count": 0,
                "source_only_exit_count": 0,
                "global_risk_override_count": 0,
                "trend_slope_block_count": 0,
                "trend_continuity_block_count": 0,
                "base_trend_on_rate": 0.0,
                "quality_trend_on_rate": 0.0,
                "effective_max_positions": int(max(selected_count, len(positions))),
                "dd_state": "",
                "market_state": "",
                "trade_mode": "MONTHLY_REBALANCE",
                "benchmark_regime_on": False,
            }
        )
        prev_nav = float(nav)
        todays_close = normalized[normalized["date"] == day][["symbol", "close"]]
        for row in todays_close.itertuples(index=False):
            if pd.notna(row.close) and float(row.close) > 0.0:
                last_close_map[str(row.symbol)] = float(row.close)

    portfolio_daily = pd.DataFrame(daily_rows)
    portfolio_trades = pd.DataFrame(trade_rows)
    perf_daily = _build_perf_daily_frame(portfolio_daily, effective_execution_start_date)
    nav_frame = _build_nav_frame(portfolio_daily, effective_execution_start_date)
    perf = _empty_perf_payload()
    if not perf_daily.empty:
        trades_for_perf = portfolio_trades.copy()
        if not trades_for_perf.empty and effective_execution_start_date:
            trades_for_perf = trades_for_perf[trades_for_perf["date"] >= effective_execution_start_date].copy()
        perf = compute_backtest_metrics(perf_daily, trades_for_perf, max_positions=max(int(selection["rank"].max()) if not selection.empty and pd.notna(selection["rank"].max()) else 10, 1))
        perf["effective_execution_start_date"] = str(effective_execution_start_date or "")
        perf["orders"] = int(len(portfolio_trades))
        perf["closed_trades"] = int((portfolio_trades["side"].astype(str).str.upper() == "SELL").sum()) if not portfolio_trades.empty else 0
        perf["raw_signal"] = int(raw_signal_count)
        perf["blocked"] = 0
        perf["skipped"] = int(skipped_buy_orders)
        perf["turnover"] = float(perf.get("turnover_avg", 0.0) or 0.0)

    return {
        "portfolio_daily": portfolio_daily,
        "portfolio_trades": portfolio_trades,
        "orders": portfolio_trades.copy(),
        "nav": nav_frame,
        "perf": perf,
        "summary": {
            "executed_rebalance_days": int(executed_rebalance_days),
            "raw_signal_count": int(raw_signal_count),
            "skipped_buy_orders": int(skipped_buy_orders),
            "untradable_sell_blocks": int(untradable_sell_blocks),
            "untradable_buy_blocks": int(untradable_buy_blocks),
        },
        "effective_execution_start_date": effective_execution_start_date,
    }


def _run_diagnostics_only_plan_item(
    *,
    study_id: str,
    title: str,
    baseline_id: str,
    window_key: str,
    variant_name: str,
    request_payload: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    start_date = date.fromisoformat(str(request_payload["start_date"]))
    end_date = date.fromisoformat(str(request_payload["end_date"]))
    run_params = dict(request_payload.get("run_params") or {})
    top_n = int(run_params.get("top_n", 10) or 10)
    moneyflow_table = str(run_params.get("moneyflow_table") or "pit_stock_moneyflow_v2").strip()
    denominator_mode = str(run_params.get("denominator_mode") or "avg20_circ_mv").strip().lower() or "avg20_circ_mv"
    weight_mode = str(run_params.get("weight_mode") or "equal_weight").strip().lower() or "equal_weight"
    exclude_star_market = bool(run_params.get("exclude_star_market", False))
    exclude_chinext = bool(run_params.get("exclude_chinext", False))
    allowed_industry_l1 = _resolve_allowed_industry_l1(run_params.get("allowed_industry_l1"))
    liquidity_bottom_quantile = float(run_params.get("liquidity_bottom_quantile", 0.0) or 0.0)
    price_repair_min_ma20_ratio = float(run_params.get("price_repair_min_ma20_ratio", 0.0) or 0.0)
    whitelist_raw = run_params.get("moneyflow_whitelist_table")
    whitelist_table = (
        "pit_stock_moneyflow_v2_whitelist_daily"
        if whitelist_raw is None
        else str(whitelist_raw).strip()
    )
    allow_whitelist_fallback = bool(run_params.get("allow_whitelist_fallback", False))
    output_namespace = str(run_params.get("output_namespace") or "studies/a_share_moneyflow_divergence").strip().strip("/")
    provider, cfg_snapshot, config_hash = _create_provider_from_payload(request_payload)

    observation_thresholds = dict(metadata.get("coverage_gate") or {})
    required_row_ratio = float(observation_thresholds.get("required_row_coverage_ratio", 0.95) or 0.95)
    required_net_ratio = float(observation_thresholds.get("required_net_coverage_ratio", 0.90) or 0.90)
    min_tradable_month_ratio = float(metadata.get("min_tradable_month_ratio", 0.85) or 0.85)
    initial_capital, lot_size, costs = _extract_runtime_costs(cfg_snapshot)

    warmup_start = start_date - timedelta(days=60)
    universe_mode = str(run_params.get("universe_mode") or "ALL_A").strip().upper() or "ALL_A"
    symbols, universe_meta = resolve_universe_by_mode(
        mode=universe_mode,
        as_of=end_date,
        db=provider._inner._db if hasattr(provider, "_inner") else provider._db,  # type: ignore[attr-defined]
        runtime=provider._inner._runtime if hasattr(provider, "_inner") else provider._runtime,  # type: ignore[attr-defined]
        asset_scope=str(request_payload.get("asset_scope") or "cn_a_equity"),
    )
    whitelist = provider.load_moneyflow_whitelist(start_date, end_date, table=whitelist_table) if whitelist_table else pd.DataFrame()
    security_master = provider.load_security_master(symbols)
    st_history = provider.load_st_history(symbols, warmup_start, end_date)
    trading_days = provider.load_trading_calendar_cn(start_date, end_date)
    observation_dates = _month_end_observation_dates(trading_days, start_date, end_date)

    if _has_whitelist_coverage(whitelist, observation_dates):
        coverage_ledger = assess_moneyflow_gate(
            observation_dates,
            whitelist,
            required_row_coverage_ratio=required_row_ratio,
            required_net_coverage_ratio=required_net_ratio,
        )
    elif allow_whitelist_fallback:
        coverage_ledger = synthesize_moneyflow_gate_from_daily_coverage(
            provider,
            symbols,
            observation_dates,
            moneyflow_table=moneyflow_table,
            required_row_coverage_ratio=required_row_ratio,
            required_net_coverage_ratio=required_net_ratio,
        )
    else:
        coverage_ledger = assess_moneyflow_gate(
            observation_dates,
            whitelist,
            required_row_coverage_ratio=required_row_ratio,
            required_net_coverage_ratio=required_net_ratio,
        )
    schedule = build_monthly_rebalance_schedule(trading_days, observation_dates, coverage_ledger, end_date=end_date)

    filter_cfg = UniverseFilterConfig(
        exclude_st=True,
        exclude_delisted=True,
        exclude_suspended=True,
        exclude_star_market=exclude_star_market,
        exclude_chinext=exclude_chinext,
        min_list_days=1,
        min_avg_turnover_20d=0.0,
        min_avg_turnover_rate_20d=0.0,
        min_price=0.0,
    )

    factor_rows: list[pd.DataFrame] = []
    selection_rows: list[dict[str, Any]] = []
    stats_rows: list[dict[str, Any]] = []
    schedule_map = {
        pd.Timestamp(row.observation_date).normalize(): row._asdict()
        for row in schedule.itertuples(index=False)
    } if not schedule.empty else {}
    for observation_date in observation_dates:
        obs_ts = pd.Timestamp(observation_date)
        month = obs_ts.to_period("M").to_timestamp()
        schedule_row = schedule_map.get(obs_ts, {})
        monthly_rows, candidate_rows = _build_observation_month_slice(
            provider=provider,
            symbols=symbols,
            observation_date=observation_date,
            moneyflow_table=moneyflow_table,
            denominator_mode=denominator_mode,
            security_master=security_master,
            st_history=st_history,
        )
        if allowed_industry_l1:
            industry_history = provider.load_industry_history(
                candidate_rows["symbol"].astype(str).str.lower().dropna().unique().tolist(),
                observation_date,
                observation_date,
            )
            industry_map = _build_active_industry_l1_map(industry_history, observation_date)
            if "industry_l1" not in candidate_rows.columns:
                candidate_rows["industry_l1"] = ""
            candidate_rows["industry_l1"] = candidate_rows["symbol"].map(industry_map).fillna("")
            monthly_rows["industry_l1"] = monthly_rows["symbol"].map(industry_map).fillna("")
        filtered_rows, _, excluded_counts = apply_universe_filters(candidate_rows, filter_cfg)
        if allowed_industry_l1:
            filtered_rows, industry_excluded = _apply_allowed_industry_filter(filtered_rows, allowed_industry_l1)
            if industry_excluded:
                merged_counts = dict(excluded_counts or {})
                for key, value in industry_excluded.items():
                    merged_counts[key] = int(merged_counts.get(key, 0)) + int(value)
                excluded_counts = merged_counts
        for column in ["industry_l1", "avg_turnover_20d", "avg_turnover_rate_20d", "last_close", "ma20_close", "circ_mv"]:
            if column not in filtered_rows.columns:
                filtered_rows[column] = pd.NA
        filtered_rows, screen_excluded, screen_meta = _apply_repair_screen_filters(
            filtered_rows,
            liquidity_bottom_quantile=liquidity_bottom_quantile,
            price_repair_min_ma20_ratio=price_repair_min_ma20_ratio,
        )
        if screen_excluded:
            merged_counts = dict(excluded_counts or {})
            for key, value in screen_excluded.items():
                merged_counts[key] = int(merged_counts.get(key, 0)) + int(value)
            excluded_counts = merged_counts
        joined = monthly_rows.merge(
            filtered_rows[
                [
                    "symbol",
                    "industry_l1",
                    "avg_turnover_20d",
                    "avg_turnover_rate_20d",
                    "last_close",
                    "ma20_close",
                    "circ_mv",
                ]
            ],
            on="symbol",
            how="inner",
        )
        joined["observation_date"] = obs_ts
        joined["execution_date"] = schedule_row.get("execution_date")
        joined["gate_status"] = str(schedule_row.get("schedule_status") or "")
        joined["gate_reason"] = str(schedule_row.get("schedule_reason") or "")
        factor_rows.append(joined)

        if bool(schedule_row.get("can_rebalance")):
            selected = joined.sort_values(["monthly_divergence_rate", "symbol"]).head(top_n).reset_index(drop=True)
            for idx, row in enumerate(selected.itertuples(index=False), start=1):
                selection_rows.append(
                    {
                        "observation_date": obs_ts,
                        "month": month,
                        "execution_date": schedule_row.get("execution_date"),
                        "rank": idx,
                        "symbol": row.symbol,
                        "monthly_divergence_rate": row.monthly_divergence_rate,
                        "valid_days": row.valid_days,
                        "month_trading_days": row.month_trading_days,
                        "industry_l1": getattr(row, "industry_l1", ""),
                        "avg_turnover_20d": getattr(row, "avg_turnover_20d", pd.NA),
                        "avg_turnover_rate_20d": getattr(row, "avg_turnover_rate_20d", pd.NA),
                        "last_close": getattr(row, "last_close", pd.NA),
                        "ma20_close": getattr(row, "ma20_close", pd.NA),
                        "ma20_ratio": (
                            None
                            if pd.isna(getattr(row, "last_close", pd.NA))
                            or pd.isna(getattr(row, "ma20_close", pd.NA))
                            or float(getattr(row, "ma20_close", 0.0) or 0.0) <= 0.0
                            else float(getattr(row, "last_close")) / float(getattr(row, "ma20_close"))
                        ),
                        "circ_mv": getattr(row, "circ_mv", pd.NA),
                        "gate_status": str(schedule_row.get("schedule_status") or ""),
                    }
                )
            selected_count = int(len(selected))
        else:
            selected_count = 0

        stats_rows.append(
            {
                "observation_date": obs_ts,
                "month": month,
                "execution_date": schedule_row.get("execution_date"),
                "planned_rebalance": bool(schedule_row.get("planned_rebalance")),
                "can_rebalance": bool(schedule_row.get("can_rebalance")),
                "gate_status": str(schedule_row.get("schedule_status") or ""),
                "gate_reason": str(schedule_row.get("schedule_reason") or ""),
                "candidate_symbols": int(len(candidate_rows)),
                "tradable_symbols": int(len(filtered_rows)),
                "valid_factor_symbols": int(len(monthly_rows)),
                "ranked_symbols": int(len(joined)),
                "selected_symbols": int(selected_count),
                "liquidity_bottom_quantile": liquidity_bottom_quantile,
                "liquidity_threshold_avg_turnover_20d": screen_meta.get("liquidity_threshold_avg_turnover_20d"),
                "price_repair_min_ma20_ratio": screen_meta.get("price_repair_min_ma20_ratio"),
                "excluded_counts_json": json.dumps(excluded_counts, ensure_ascii=False, sort_keys=True),
            }
        )

    factor_panel = pd.concat(factor_rows, ignore_index=True) if factor_rows else pd.DataFrame()
    selection_frame = pd.DataFrame(selection_rows)
    universe_stats = pd.DataFrame(stats_rows)
    planned_rebalance_months = int(schedule["planned_rebalance"].sum()) if not schedule.empty else 0
    tradable_months = int(schedule["can_rebalance"].sum()) if not schedule.empty else 0
    skipped_months = int(max(planned_rebalance_months - tradable_months, 0))
    partial_coverage = skipped_months > 0
    tradable_ratio = float(tradable_months / planned_rebalance_months) if planned_rebalance_months else 0.0
    data_unreliable = bool(planned_rebalance_months > 0 and tradable_ratio < min_tradable_month_ratio)

    selected_symbols = sorted({str(symbol).lower() for symbol in selection_frame.get("symbol", pd.Series(dtype=str)).dropna().tolist()})
    replay_price_history = (
        provider.load_ohlcv_daily(selected_symbols, start_date, end_date, source="moneyflow_divergence")
        if selected_symbols
        else pd.DataFrame()
    )
    replay = run_monthly_rebalance_backtest(
        replay_price_history,
        trading_days,
        schedule,
        selection_frame,
        initial_capital=initial_capital,
        lot_size=lot_size,
        commission_rate=float(costs["commission_rate"]),
        commission_min=float(costs["commission_min"]),
        stamp_tax_rate=float(costs["stamp_tax_rate"]),
        slippage_bps=float(costs["slippage_bps"]),
        weight_mode=weight_mode,
    )
    perf_payload = dict(_empty_perf_payload())
    perf_payload.update(dict(replay["perf"] or {}))
    perf_payload["effective_execution_start_date"] = str(replay.get("effective_execution_start_date") or "")
    perf_payload["data_unreliable"] = bool(data_unreliable)
    perf_payload["planned_rebalance_months"] = int(planned_rebalance_months)
    perf_payload["tradable_months"] = int(tradable_months)
    perf_payload["skipped_months"] = int(skipped_months)
    perf_payload.update(dict(replay["summary"] or {}))

    run_root = (
        _results_root()
        / output_namespace
        / study_id.replace("/", "_")
        / window_key
        / variant_name
    )
    run_root.mkdir(parents=True, exist_ok=True)

    coverage_path = _write_csv(coverage_ledger, run_root / "monthly_coverage_ledger.csv")
    schedule_path = _write_csv(schedule, run_root / "monthly_rebalance_schedule.csv")
    factor_panel_path = _write_csv(factor_panel, run_root / "monthly_factor_panel.csv")
    selection_path = _write_csv(selection_frame, run_root / "monthly_selection.csv")
    universe_stats_path = _write_csv(universe_stats, run_root / "monthly_universe_stats.csv")
    daily_path = _write_csv(replay["portfolio_daily"], run_root / "portfolio_daily.csv")
    trades_path = _write_csv(replay["portfolio_trades"], run_root / "portfolio_trades.csv")
    orders_path = _write_csv(replay["orders"], run_root / "orders.csv")
    nav_path = _write_csv(replay["nav"], run_root / "nav.csv")
    perf_path = _write_json(perf_payload, run_root / "perf.json")

    run_meta = {
        "study_id": study_id,
        "title": title,
        "baseline_id": baseline_id,
        "window_key": window_key,
        "variant_name": variant_name,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "config_path": str(request_payload.get("config_path") or ""),
        "config_hash": config_hash,
        "config_snapshot": cfg_snapshot,
        "request_payload": request_payload,
        "denominator_mode": denominator_mode,
        "weight_mode": weight_mode,
        "exclude_star_market": exclude_star_market,
        "exclude_chinext": exclude_chinext,
        "allowed_industry_l1": allowed_industry_l1,
        "liquidity_bottom_quantile": liquidity_bottom_quantile,
        "price_repair_min_ma20_ratio": price_repair_min_ma20_ratio,
        "universe_meta": universe_meta,
        "planned_rebalance_months": planned_rebalance_months,
        "tradable_months": tradable_months,
        "skipped_months": skipped_months,
        "partial_coverage": partial_coverage,
        "data_unreliable": data_unreliable,
        "tradable_month_ratio": tradable_ratio,
        "effective_execution_start_date": replay.get("effective_execution_start_date"),
        "simulation_summary": dict(replay["summary"] or {}),
        "status": "completed",
        "baseline_append_allowed": False,
        "baseline_append_skipped_reason": "CUSTOM_STUDY_RUNNER_BASELINE_APPEND_DISABLED",
    }
    run_meta_path = _write_json(run_meta, run_root / "run_meta.json")
    machine_bundle = {
        "study_id": study_id,
        "title": title,
        "window_key": window_key,
        "variant_name": variant_name,
        "status": "completed",
        "summary": {
            "planned_rebalance_months": planned_rebalance_months,
            "tradable_months": tradable_months,
            "skipped_months": skipped_months,
            "partial_coverage": partial_coverage,
            "data_unreliable": data_unreliable,
            "tradable_month_ratio": tradable_ratio,
            "denominator_mode": denominator_mode,
            "weight_mode": weight_mode,
            "exclude_star_market": exclude_star_market,
            "exclude_chinext": exclude_chinext,
            "allowed_industry_l1": allowed_industry_l1,
            "liquidity_bottom_quantile": liquidity_bottom_quantile,
            "price_repair_min_ma20_ratio": price_repair_min_ma20_ratio,
            "executed_rebalance_days": int((replay["summary"] or {}).get("executed_rebalance_days", 0) or 0),
        },
        "perf": perf_payload,
        "artifacts": {
            "monthly_coverage_ledger": coverage_path,
            "monthly_rebalance_schedule": schedule_path,
            "monthly_factor_panel": factor_panel_path,
            "monthly_selection": selection_path,
            "monthly_universe_stats": universe_stats_path,
            "portfolio_daily": daily_path,
            "portfolio_trades": trades_path,
            "orders": orders_path,
            "nav": nav_path,
            "perf": perf_path,
            "run_meta": run_meta_path,
        },
    }
    machine_bundle_path = _write_json(machine_bundle, run_root / "machine_bundle.json")
    human_lines = [
        f"# {title}",
        "",
        f"- study_id: `{study_id}`",
        f"- window: `{window_key}`",
        f"- variant: `{variant_name}`",
        f"- status: `completed`",
        f"- denominator_mode: `{denominator_mode}`",
        f"- weight_mode: `{weight_mode}`",
        f"- exclude_star_market: `{str(exclude_star_market).lower()}`",
        f"- exclude_chinext: `{str(exclude_chinext).lower()}`",
        f"- allowed_industry_l1: `{','.join(allowed_industry_l1) if allowed_industry_l1 else '-'}`",
        f"- liquidity_bottom_quantile: `{liquidity_bottom_quantile}`",
        f"- price_repair_min_ma20_ratio: `{price_repair_min_ma20_ratio}`",
        f"- planned_rebalance_months: `{planned_rebalance_months}`",
        f"- tradable_months: `{tradable_months}`",
        f"- skipped_months: `{skipped_months}`",
        f"- partial_coverage: `{str(partial_coverage).lower()}`",
        f"- data_unreliable: `{str(data_unreliable).lower()}`",
        f"- effective_execution_start_date: `{str(replay.get('effective_execution_start_date') or '')}`",
        f"- total_return: `{perf_payload.get('total_return')}`",
        f"- cagr: `{perf_payload.get('cagr')}`",
        f"- max_drawdown: `{perf_payload.get('max_drawdown')}`",
        f"- sharpe: `{perf_payload.get('sharpe')}`",
        f"- trades: `{perf_payload.get('trades')}`",
        "",
        "当前只输出覆盖率 ledger、月度因子 panel、每月选股结果和样本统计。",
        "月频调仓执行、净值曲线、交易流水和正式回测绩效尚未接通。",
    ]
    human_bundle_path = (run_root / "human_bundle.md")
    human_bundle_path.write_text("\n".join(human_lines), encoding="utf-8")

    return {
        "window_key": window_key,
        "variant_name": variant_name,
        "status": "completed",
        "results_dir": str(run_root),
        "artifacts": {
            "monthly_coverage_ledger": coverage_path,
            "monthly_rebalance_schedule": schedule_path,
            "monthly_factor_panel": factor_panel_path,
            "monthly_selection": selection_path,
            "monthly_universe_stats": universe_stats_path,
            "portfolio_daily": daily_path,
            "portfolio_trades": trades_path,
            "orders": orders_path,
            "nav": nav_path,
            "perf": perf_path,
            "run_meta": run_meta_path,
            "machine_bundle": str(machine_bundle_path),
            "human_bundle": str(human_bundle_path),
        },
        "summary": {
            "planned_rebalance_months": planned_rebalance_months,
            "tradable_months": tradable_months,
            "skipped_months": skipped_months,
            "partial_coverage": partial_coverage,
            "data_unreliable": data_unreliable,
            "tradable_month_ratio": tradable_ratio,
            "effective_execution_start_date": replay.get("effective_execution_start_date"),
            "executed_rebalance_days": int((replay["summary"] or {}).get("executed_rebalance_days", 0) or 0),
        },
        "perf": perf_payload,
    }


def run_a_share_moneyflow_divergence_study(
    *,
    study: Any,
    plan: list[dict[str, Any]],
    write_dual_output: bool,
    append_to_baseline: bool,
) -> dict[str, Any]:
    _ = write_dual_output
    _ = append_to_baseline
    runs: list[dict[str, Any]] = []
    for item in plan:
        try:
            runs.append(
                _run_diagnostics_only_plan_item(
                    study_id=str(study.study_id),
                    title=str(study.title),
                    baseline_id=str(study.baseline_id),
                    window_key=str(item.get("window_key") or ""),
                    variant_name=str(item.get("variant_name") or ""),
                    request_payload=dict(item.get("request_payload") or {}),
                    metadata=dict(study.metadata or {}),
                )
            )
        except Exception as exc:
            runs.append(
                {
                    "window_key": str(item.get("window_key") or ""),
                    "variant_name": str(item.get("variant_name") or ""),
                    "status": "blocked",
                    "blocking_reason": f"{type(exc).__name__}: {exc}",
                }
            )
    overall_status = "completed"
    if runs and all(str(run.get("status") or "") == "blocked" for run in runs):
        overall_status = "blocked"
    elif any(str(run.get("status") or "") == "blocked" for run in runs):
        overall_status = "partial"
    return {
        "study_id": str(study.study_id),
        "title": str(study.title),
        "status": overall_status,
        "runs": runs,
    }
