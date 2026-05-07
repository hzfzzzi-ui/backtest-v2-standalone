from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from math import sqrt
from typing import Any

import pandas as pd

from backend.core.data import MarketDataAccess


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def to_iso_date(value: Any) -> str | None:
    if value is None:
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.date().isoformat()


def to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def to_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def make_warning(code: str, layer: str, message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": str(code),
        "layer": str(layer),
        "message": str(message),
    }
    for key, value in extra.items():
        if value is None:
            continue
        if isinstance(value, (date, datetime, pd.Timestamp)):
            payload[key] = to_iso_date(value) or str(value)
        else:
            payload[key] = value
    return payload


def source_entry(*, name: str, source_type: str, effective_as_of: date | str | None, fields: list[str]) -> dict[str, Any]:
    return {
        "name": str(name),
        "source_type": str(source_type),
        "effective_as_of": to_iso_date(effective_as_of),
        "fields": list(fields),
    }


def history_start_from_calendar(
    market_data_access: MarketDataAccess,
    effective_trade_date: date,
    lookback_days: int,
) -> date:
    start_guess = effective_trade_date - timedelta(days=max(int(lookback_days) * 3, 30))
    calendar = market_data_access.load_trading_calendar_index(
        start=start_guess,
        end=effective_trade_date,
        asset_scope="cn_a_equity",
        market="CN_A",
    )
    if len(calendar) == 0:
        return effective_trade_date
    idx = max(0, len(calendar) - int(lookback_days))
    return pd.Timestamp(calendar[idx]).date()


def normalize_market_history(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["symbol"] = out["symbol"].astype(str).str.lower()
    for col in (
        "close",
        "amount",
        "limit_up",
        "limit_down",
        "turnover_rate",
        "turnover_rate_f",
        "volume_ratio",
        "circ_mv",
        "volume",
    ):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "is_suspended" in out.columns:
        out["is_suspended"] = out["is_suspended"].fillna(False).astype(bool)
    return out.sort_values(["symbol", "date"]).reset_index(drop=True)


def normalize_index_history(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    for col in ("close", "amount", "volume"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.sort_values("date").reset_index(drop=True)


def prepare_market_daily(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    history = normalize_market_history(frame)
    if history.empty:
        return history, pd.DataFrame()

    grouped = history.groupby("symbol", group_keys=False)
    history["prev_close"] = grouped["close"].shift(1)
    history["ret_1d"] = history["close"].div(history["prev_close"]) - 1.0
    history["ma20"] = grouped["close"].transform(lambda s: s.rolling(20, min_periods=20).mean())
    history["ma60"] = grouped["close"].transform(lambda s: s.rolling(60, min_periods=60).mean())
    history["prior_high_20d"] = grouped["close"].transform(lambda s: s.shift(1).rolling(20, min_periods=20).max())
    history["prior_low_20d"] = grouped["close"].transform(lambda s: s.shift(1).rolling(20, min_periods=20).min())
    history["is_new_high_20d"] = history["prior_high_20d"].notna() & history["close"].gt(history["prior_high_20d"])
    history["is_new_low_20d"] = history["prior_low_20d"].notna() & history["close"].lt(history["prior_low_20d"])
    history["above_ma20"] = history["ma20"].notna() & history["close"].gt(history["ma20"])
    history["above_ma60"] = history["ma60"].notna() & history["close"].gt(history["ma60"])
    if "turnover_rate_f" in history.columns and history["turnover_rate_f"].notna().any():
        history["turnover_rate_pref"] = history["turnover_rate_f"]
        history["turnover_rate_field"] = "turnover_rate_f"
    elif "turnover_rate" in history.columns and history["turnover_rate"].notna().any():
        history["turnover_rate_pref"] = history["turnover_rate"]
        history["turnover_rate_field"] = "turnover_rate"
    else:
        history["turnover_rate_pref"] = pd.NA
        history["turnover_rate_field"] = "unavailable"
    history["is_limit_up_close"] = history["limit_up"].notna() & history["close"].notna() & history["close"].ge(history["limit_up"] - 1e-9)
    history["is_limit_down_close"] = history["limit_down"].notna() & history["close"].notna() & history["close"].le(history["limit_down"] + 1e-9)

    by_date = history.groupby("date")
    daily = pd.DataFrame(index=sorted(history["date"].dropna().unique()))
    daily.index.name = "date"
    daily["symbol_count"] = by_date["symbol"].nunique()
    daily["advancers_count"] = by_date["ret_1d"].apply(lambda s: int((s > 0).sum()))
    daily["decliners_count"] = by_date["ret_1d"].apply(lambda s: int((s < 0).sum()))
    daily["limit_up_count"] = by_date["is_limit_up_close"].sum().astype(int)
    daily["limit_down_count"] = by_date["is_limit_down_close"].sum().astype(int)
    daily["new_high_20d_count"] = by_date["is_new_high_20d"].sum().astype(int)
    daily["new_low_20d_count"] = by_date["is_new_low_20d"].sum().astype(int)
    daily["above_ma20_ratio"] = by_date["above_ma20"].mean()
    daily["above_ma60_ratio"] = by_date["above_ma60"].mean()
    daily["market_amount_total"] = by_date["amount"].sum(min_count=1)
    daily["volume_ratio_market"] = by_date["volume_ratio"].mean()
    daily["turnover_rate_market"] = by_date["turnover_rate_pref"].mean()
    daily["turnover_rate_non_null"] = by_date["turnover_rate_pref"].apply(lambda s: int(s.notna().sum()))
    daily["volume_ratio_non_null"] = by_date["volume_ratio"].apply(lambda s: int(s.notna().sum()))
    daily["circ_mv_total"] = by_date["circ_mv"].sum(min_count=1)
    daily["equal_weight_ret_1d"] = by_date["ret_1d"].mean()
    daily["market_amount_ma20_prev"] = daily["market_amount_total"].shift(1).rolling(20, min_periods=5).mean()
    daily["market_amount_heat"] = daily["market_amount_total"].div(daily["market_amount_ma20_prev"])
    daily["breadth_balance"] = (
        (daily["advancers_count"] - daily["decliners_count"])
        .div((daily["advancers_count"] + daily["decliners_count"]).replace(0, pd.NA))
        .fillna(0.0)
    )
    daily["limit_balance"] = (
        (daily["limit_up_count"] - daily["limit_down_count"])
        .div((daily["limit_up_count"] + daily["limit_down_count"]).replace(0, pd.NA))
        .fillna(0.0)
    )
    daily["market_proxy_nav"] = (1.0 + daily["equal_weight_ret_1d"].fillna(0.0)).cumprod()
    return history, daily


def return_over(series: pd.Series, current_date: pd.Timestamp, periods: int) -> float | None:
    ordered = pd.to_numeric(series.sort_index(), errors="coerce")
    if current_date not in ordered.index:
        return None
    loc = ordered.index.get_loc(current_date)
    if isinstance(loc, slice):
        loc = loc.stop - 1
    prev_loc = loc - int(periods)
    if prev_loc < 0:
        return None
    current_value = to_float(ordered.iloc[loc])
    prev_value = to_float(ordered.iloc[prev_loc])
    if current_value is None or prev_value in (None, 0.0):
        return None
    return current_value / prev_value - 1.0


def ma_gap(series: pd.Series, current_date: pd.Timestamp, window: int) -> float | None:
    ordered = pd.to_numeric(series.sort_index(), errors="coerce")
    if current_date not in ordered.index:
        return None
    loc = ordered.index.get_loc(current_date)
    if isinstance(loc, slice):
        loc = loc.stop - 1
    if loc + 1 < int(window):
        return None
    current_value = to_float(ordered.iloc[loc])
    average_value = to_float(ordered.iloc[loc + 1 - int(window): loc + 1].mean())
    if current_value is None or average_value in (None, 0.0):
        return None
    return current_value / average_value - 1.0


def prev_window_zscore(series: pd.Series, current_date: pd.Timestamp, *, window: int, min_obs: int) -> float | None:
    ordered = pd.to_numeric(series.sort_index(), errors="coerce")
    if current_date not in ordered.index:
        return None
    history = ordered.loc[ordered.index < current_date].dropna().tail(int(window))
    current_value = to_float(ordered.loc[current_date])
    if current_value is None or len(history) < int(min_obs):
        return None
    sigma = float(history.std(ddof=0))
    if sigma == 0.0:
        return 0.0
    return float((current_value - float(history.mean())) / sigma)


def prev_window_quantile(series: pd.Series, current_date: pd.Timestamp, *, window: int, min_obs: int) -> float | None:
    ordered = pd.to_numeric(series.sort_index(), errors="coerce")
    if current_date not in ordered.index:
        return None
    history = ordered.loc[ordered.index < current_date].dropna().tail(int(window))
    current_value = to_float(ordered.loc[current_date])
    if current_value is None or len(history) < int(min_obs):
        return None
    return float((history <= current_value).mean())


def annualized_vol(series: pd.Series, window: int) -> float | None:
    sample = pd.to_numeric(series.tail(int(window)), errors="coerce").dropna()
    if len(sample) < max(5, int(window) // 2):
        return None
    return float(sample.std(ddof=0) * sqrt(252.0))


def latest_sentiment_row(frame: pd.DataFrame, requested_trade_date: date) -> pd.Series | None:
    if frame.empty:
        return None
    filtered = frame[frame["as_of"] <= pd.Timestamp(requested_trade_date)].copy()
    if filtered.empty:
        return None
    usable = filtered[(filtered["advancers"].fillna(0) + filtered["decliners"].fillna(0)) > 0]
    target = usable if not usable.empty else filtered
    if target.empty:
        return None
    return target.sort_values("as_of").iloc[-1]


def dedupe_warnings(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        marker = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(item)
    return deduped


def fmt_float(value: Any, digits: int = 2) -> str:
    parsed = to_float(value)
    if parsed is None:
        return "-"
    return f"{parsed:.{int(digits)}f}"


def fmt_pct(value: Any, digits: int = 2) -> str:
    parsed = to_float(value)
    if parsed is None:
        return "-"
    return f"{parsed * 100:.{int(digits)}f}%"
