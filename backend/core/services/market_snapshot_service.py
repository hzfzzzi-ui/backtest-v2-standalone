from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.services.market_snapshot_utils import (
    annualized_vol as _annualized_vol,
    dedupe_warnings as _dedupe_warnings,
    fmt_float as _fmt_float,
    fmt_pct as _fmt_pct,
    history_start_from_calendar as _history_start_from_calendar,
    latest_sentiment_row as _latest_sentiment_row,
    ma_gap as _ma_gap,
    make_warning as _make_warning,
    normalize_index_history as _normalize_index_history,
    now_iso as _now_iso,
    prepare_market_daily as _prepare_market_daily,
    prev_window_quantile as _prev_window_quantile,
    prev_window_zscore as _prev_window_zscore,
    return_over as _return_over,
    source_entry as _source_entry,
    to_float as _to_float,
    to_int as _to_int,
    to_iso_date as _to_iso_date,
)
from backend.core.tools.market_snapshot_access import resolve_market_snapshot_dir
from backend.core.tools.runtime_data_access import RuntimeDataAccess, load_runtime_data_access
from backend.core.universe.universe_resolver import resolve_universe_by_mode

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None


INDEX_SPECS: tuple[dict[str, str], ...] = (
    {"key": "sse_composite", "label": "上证综指", "symbol": "000001.SH"},
    {"key": "szse_component", "label": "深证成指", "symbol": "399001.SZ"},
    {"key": "chinext", "label": "创业板指", "symbol": "399006.SZ"},
    {"key": "csi300", "label": "沪深300", "symbol": "000300.SH"},
    {"key": "csi500", "label": "中证500", "symbol": "000905.SH"},
    {"key": "csi1000", "label": "中证1000", "symbol": "000852.SH"},
)

MARKET_LOOKBACK_DAYS = 260
INDEX_LOOKBACK_DAYS = 90
MIN_SHORT_OBS = 20
MIN_LONG_OBS = 40


class MarketSnapshotError(RuntimeError):
    pass


@dataclass(slots=True)
class MarketSnapshotArtifacts:
    snapshot: dict[str, Any]
    brief_markdown: str
    output_dir: Path
    snapshot_path: Path
    brief_path: Path


class MarketSnapshotRepository:
    def __init__(self, access: RuntimeDataAccess) -> None:
        self.access = access

    def _connect(self):
        if psycopg is None:  # pragma: no cover
            raise MarketSnapshotError("psycopg is required for market snapshot service")
        db = self.access.cfg_obj.db
        return psycopg.connect(
            host=db.host,
            port=db.port,
            dbname=db.dbname,
            user=db.user,
            password=db.password,
            autocommit=False,
        )

    def max_trade_date(self, *, table: str, date_col: str, where_sql: str = "", params: tuple[Any, ...] = ()) -> date | None:
        query = f"SELECT MAX({date_col}) AS max_date FROM public.{table}"
        if where_sql:
            query += f" WHERE {where_sql}"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    f"SET LOCAL statement_timeout = '{int(self.access.cfg_obj.db_runtime.statement_timeout_ms)}ms'"
                )
                cur.execute(query, params)
                row = cur.fetchone()
        if not row or row[0] is None:
            return None
        return pd.Timestamp(row[0]).date()

    def latest_market_trade_date(self, requested_trade_date: date) -> date | None:
        return self.max_trade_date(
            table="pams_ohlcv_daily",
            date_col="trade_date",
            where_sql="market = 'CN_A' AND trade_date <= %s",
            params=(requested_trade_date,),
        )

    def latest_sentiment_date(self, requested_trade_date: date) -> date | None:
        return self.max_trade_date(
            table="pams_sentiment_state",
            date_col="as_of",
            where_sql="as_of <= %s",
            params=(requested_trade_date,),
        )

    def latest_index_trade_date(self, requested_trade_date: date, symbols: list[str]) -> date | None:
        return self.max_trade_date(
            table="pit_index_daily",
            date_col="trade_date",
            where_sql="trade_date <= %s AND index_code = ANY(%s)",
            params=(requested_trade_date, symbols),
        )

    def load_sentiment_history(self, requested_trade_date: date, limit_rows: int = 400) -> pd.DataFrame:
        query = """
            SELECT
                as_of,
                sent_state,
                sent_score,
                advancers,
                decliners,
                limit_up,
                limit_down,
                created_at
            FROM public.pams_sentiment_state
            WHERE as_of <= %s
            ORDER BY as_of DESC
            LIMIT %s
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    f"SET LOCAL statement_timeout = '{int(self.access.cfg_obj.db_runtime.statement_timeout_ms)}ms'"
                )
                cur.execute(query, (requested_trade_date, int(limit_rows)))
                rows = cur.fetchall()
                cols = [d.name for d in cur.description]
        frame = pd.DataFrame(rows, columns=cols)
        if frame.empty:
            return frame
        frame["as_of"] = pd.to_datetime(frame["as_of"], errors="coerce").dt.normalize()
        for col in ("sent_score", "advancers", "decliners", "limit_up", "limit_down"):
            if col in frame.columns:
                frame[col] = pd.to_numeric(frame[col], errors="coerce")
        return frame.sort_values("as_of").reset_index(drop=True)


def build_market_snapshot_from_frames(
    *,
    requested_trade_date: date,
    market_history: pd.DataFrame,
    index_histories: dict[str, pd.DataFrame],
    sentiment_history: pd.DataFrame,
    provider_query_audit: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    provider_query_audit = list(provider_query_audit or [])
    all_warnings: list[dict[str, Any]] = []
    market_history_prepared, market_daily = _prepare_market_daily(market_history)
    if market_history_prepared.empty or market_daily.empty:
        raise MarketSnapshotError("market history is empty; cannot build market snapshot")

    market_effective_ts = market_daily.index.max()
    market_effective_date = pd.Timestamp(market_effective_ts).date()
    if market_effective_date < requested_trade_date:
        all_warnings.append(
            _make_warning(
                "STALE_MARKET_PRICE_DATA",
                "liquidity_layer",
                f"价量主数据最新仅到 {market_effective_date.isoformat()}，落后于请求日期 {requested_trade_date.isoformat()}",
                requested_trade_date=requested_trade_date,
                effective_as_of=market_effective_date,
                lag_days=(requested_trade_date - market_effective_date).days,
            )
        )

    daily_row = market_daily.loc[market_effective_ts]
    sentiment_row = _latest_sentiment_row(sentiment_history, requested_trade_date)

    index_layer_warnings: list[dict[str, Any]] = []
    style_layer_warnings: list[dict[str, Any]] = []
    index_entries: dict[str, dict[str, Any]] = {}
    index_effective_dates: dict[str, str | None] = {}
    style_returns_1d: dict[str, float] = {}
    style_returns_20d: dict[str, float] = {}

    for spec in INDEX_SPECS:
        key = spec["key"]
        symbol = spec["symbol"]
        label = spec["label"]
        raw_index_frame = index_histories.get(symbol)
        frame = _normalize_index_history(raw_index_frame if raw_index_frame is not None else pd.DataFrame())
        if frame.empty:
            index_entries[key] = {
                "symbol": symbol,
                "label": label,
                "effective_as_of": None,
                "close": None,
                "ret_1d": None,
                "ret_20d": None,
                "ret_60d": None,
                "ma20_gap": None,
                "ma60_gap": None,
            }
            warning = _make_warning("INDEX_HISTORY_MISSING", "index_layer", f"{symbol} 缺少指数历史数据", symbol=symbol)
            index_layer_warnings.append(warning)
            if key in {"csi300", "csi500", "csi1000", "chinext"}:
                style_layer_warnings.append(warning)
            continue

        series = frame.set_index("date")["close"].sort_index()
        effective_ts = series.index.max()
        effective_date = pd.Timestamp(effective_ts).date()
        index_effective_dates[key] = effective_date.isoformat()
        if effective_date < requested_trade_date:
            index_layer_warnings.append(
                _make_warning(
                    "STALE_INDEX_DATA",
                    "index_layer",
                    f"{symbol} 指数数据最新仅到 {effective_date.isoformat()}",
                    symbol=symbol,
                    requested_trade_date=requested_trade_date,
                    effective_as_of=effective_date,
                    lag_days=(requested_trade_date - effective_date).days,
                )
            )
            if key in {"csi300", "csi500", "csi1000", "chinext"}:
                style_layer_warnings.append(
                    _make_warning(
                        "STALE_STYLE_INPUT",
                        "style_layer",
                        f"{symbol} 风格基准数据最新仅到 {effective_date.isoformat()}",
                        symbol=symbol,
                        requested_trade_date=requested_trade_date,
                        effective_as_of=effective_date,
                        lag_days=(requested_trade_date - effective_date).days,
                    )
                )
        entry = {
            "symbol": symbol,
            "label": label,
            "effective_as_of": effective_date.isoformat(),
            "close": _to_float(series.loc[effective_ts]),
            "ret_1d": _return_over(series, effective_ts, 1),
            "ret_20d": _return_over(series, effective_ts, 20),
            "ret_60d": _return_over(series, effective_ts, 60),
            "ma20_gap": _ma_gap(series, effective_ts, 20),
            "ma60_gap": _ma_gap(series, effective_ts, 60),
        }
        index_entries[key] = entry
        if key in {"csi300", "csi500", "csi1000", "chinext"}:
            if entry["ret_1d"] is not None:
                style_returns_1d[key] = float(entry["ret_1d"])
            if entry["ret_20d"] is not None:
                style_returns_20d[key] = float(entry["ret_20d"])

    csi300_entry = index_entries.get("csi300") or {}
    style_reference_date = csi300_entry.get("effective_as_of") or market_effective_date.isoformat()

    def _style_diff(lhs: str, rhs: str, field: str) -> float | None:
        left = index_entries.get(lhs) or {}
        right = index_entries.get(rhs) or {}
        if left.get("effective_as_of") != right.get("effective_as_of"):
            style_layer_warnings.append(
                _make_warning(
                    "STYLE_DATE_MISMATCH",
                    "style_layer",
                    f"{lhs} 与 {rhs} 的风格比较日期不一致，已跳过该相对强弱字段",
                    lhs=lhs,
                    rhs=rhs,
                    lhs_as_of=left.get("effective_as_of"),
                    rhs_as_of=right.get("effective_as_of"),
                )
            )
            return None
        left_value = left.get(field)
        right_value = right.get(field)
        if left_value is None or right_value is None:
            return None
        return float(left_value) - float(right_value)

    ranked_1d = {
        key: value
        for key, value in style_returns_1d.items()
        if index_entries.get(key, {}).get("effective_as_of") == style_reference_date
    }
    ranked_20d = {
        key: value
        for key, value in style_returns_20d.items()
        if index_entries.get(key, {}).get("effective_as_of") == style_reference_date
    }
    small_mid_large_rank = " > ".join(sorted(ranked_20d, key=ranked_20d.get, reverse=True)) if ranked_20d else None

    breadth_layer_warnings: list[dict[str, Any]] = []
    breadth_field_as_of: dict[str, str | None] = {}
    if sentiment_row is not None and (
        _to_int(sentiment_row.get("advancers")) is not None or _to_int(sentiment_row.get("decliners")) is not None
    ):
        breadth_counts_as_of = pd.Timestamp(sentiment_row["as_of"]).date()
        advancers_count = _to_int(sentiment_row.get("advancers"))
        decliners_count = _to_int(sentiment_row.get("decliners"))
        limit_up_count = _to_int(sentiment_row.get("limit_up"))
        limit_down_count = _to_int(sentiment_row.get("limit_down"))
        breadth_field_as_of.update(
            {
                "advancers_count": breadth_counts_as_of.isoformat(),
                "decliners_count": breadth_counts_as_of.isoformat(),
                "limit_up_count": breadth_counts_as_of.isoformat(),
                "limit_down_count": breadth_counts_as_of.isoformat(),
            }
        )
        if breadth_counts_as_of < requested_trade_date:
            breadth_layer_warnings.append(
                _make_warning(
                    "STALE_BREADTH_COUNTS",
                    "breadth_layer",
                    f"广度计数表最新仅到 {breadth_counts_as_of.isoformat()}",
                    requested_trade_date=requested_trade_date,
                    effective_as_of=breadth_counts_as_of,
                    lag_days=(requested_trade_date - breadth_counts_as_of).days,
                )
            )
    else:
        breadth_counts_as_of = market_effective_date
        advancers_count = _to_int(daily_row["advancers_count"])
        decliners_count = _to_int(daily_row["decliners_count"])
        limit_up_count = _to_int(daily_row["limit_up_count"])
        limit_down_count = _to_int(daily_row["limit_down_count"])
        breadth_field_as_of.update(
            {
                "advancers_count": market_effective_date.isoformat(),
                "decliners_count": market_effective_date.isoformat(),
                "limit_up_count": market_effective_date.isoformat(),
                "limit_down_count": market_effective_date.isoformat(),
            }
        )

    breadth_denominator = (advancers_count or 0) + (decliners_count or 0)
    breadth_up_down_ratio = None
    breadth_balance = None
    if breadth_denominator > 0:
        breadth_up_down_ratio = (advancers_count or 0) / max(decliners_count or 0, 1)
        breadth_balance = ((advancers_count or 0) - (decliners_count or 0)) / breadth_denominator

    technical_breadth_as_of = market_effective_date.isoformat()
    breadth_field_as_of.update(
        {
            "new_high_20d_count": technical_breadth_as_of,
            "new_low_20d_count": technical_breadth_as_of,
            "above_ma20_ratio": technical_breadth_as_of,
            "above_ma60_ratio": technical_breadth_as_of,
            "up_down_ratio": breadth_field_as_of.get("advancers_count"),
            "breadth_balance": breadth_field_as_of.get("advancers_count"),
        }
    )
    if breadth_counts_as_of != market_effective_date:
        breadth_layer_warnings.append(
            _make_warning(
                "BREADTH_MIXED_DATES",
                "breadth_layer",
                "广度计数与技术广度字段来自不同日期，已在 field_as_of 中显式记录",
                counts_as_of=breadth_counts_as_of,
                technical_as_of=market_effective_date,
            )
        )

    liquidity_layer_warnings: list[dict[str, Any]] = []
    turnover_rate_z252 = _prev_window_zscore(
        market_daily["turnover_rate_market"],
        market_effective_ts,
        window=252,
        min_obs=MIN_LONG_OBS,
    )
    amount_heat = _to_float(daily_row.get("market_amount_heat"))
    if amount_heat is None:
        liquidity_layer_warnings.append(
            _make_warning(
                "AMOUNT_HEAT_HISTORY_SHORT",
                "liquidity_layer",
                "成交额热度历史窗口不足，market_amount_heat 已置空",
                effective_as_of=market_effective_date,
            )
        )
    if turnover_rate_z252 is None:
        liquidity_layer_warnings.append(
            _make_warning(
                "TURNOVER_RATE_HISTORY_SHORT",
                "liquidity_layer",
                "换手率热度历史窗口不足，turnover_rate_market_z252 已置空",
                effective_as_of=market_effective_date,
            )
        )
    if _to_int(daily_row.get("turnover_rate_non_null")) in (None, 0):
        liquidity_layer_warnings.append(
            _make_warning(
                "TURNOVER_RATE_UNAVAILABLE",
                "liquidity_layer",
                "主市场价量表缺少可用换手率字段，turnover_rate_market 相关统计可能为空",
                effective_as_of=market_effective_date,
            )
        )

    sentiment_layer_warnings: list[dict[str, Any]] = []
    derived_turnover_z = _prev_window_zscore(
        market_daily["market_amount_heat"],
        market_effective_ts,
        window=252,
        min_obs=MIN_LONG_OBS,
    )
    derived_breadth_z = _prev_window_zscore(
        market_daily["breadth_balance"],
        market_effective_ts,
        window=252,
        min_obs=MIN_LONG_OBS,
    )
    derived_limit_z = _prev_window_zscore(
        market_daily["limit_balance"],
        market_effective_ts,
        window=252,
        min_obs=MIN_LONG_OBS,
    )
    derived_sentiment_score = None
    if None not in (derived_turnover_z, derived_breadth_z, derived_limit_z):
        derived_sentiment_score = float(0.4 * derived_turnover_z + 0.35 * derived_breadth_z + 0.25 * derived_limit_z)
    else:
        sentiment_layer_warnings.append(
            _make_warning(
                "SENTIMENT_HISTORY_SHORT",
                "sentiment_layer",
                "行为型情绪分数历史窗口不足，derived_sentiment_score 已置空",
                effective_as_of=market_effective_date,
            )
        )

    blended_history = pd.Series(
        (
            0.4 * pd.to_numeric(market_daily["market_amount_heat"], errors="coerce")
            + 0.35 * pd.to_numeric(market_daily["breadth_balance"], errors="coerce")
            + 0.25 * pd.to_numeric(market_daily["limit_balance"], errors="coerce")
        ),
        index=market_daily.index,
    )
    sentiment_quantile = _prev_window_quantile(
        blended_history,
        market_effective_ts,
        window=252,
        min_obs=MIN_LONG_OBS,
    )
    derived_regime = None
    if sentiment_quantile is not None:
        if sentiment_quantile <= 0.2:
            derived_regime = "cold"
        elif sentiment_quantile >= 0.8:
            derived_regime = "hot"
        else:
            derived_regime = "neutral"

    official_sentiment_score = None
    official_sentiment_regime = None
    official_sentiment_as_of = None
    if sentiment_row is not None:
        official_sentiment_score = _to_float(sentiment_row.get("sent_score"))
        official_sentiment_regime = str(sentiment_row.get("sent_state") or "").strip().lower() or None
        official_sentiment_as_of = _to_iso_date(sentiment_row.get("as_of"))
        if official_sentiment_as_of and official_sentiment_as_of != market_effective_date.isoformat():
            sentiment_layer_warnings.append(
                _make_warning(
                    "SENTIMENT_OFFICIAL_DATE_DIFFERS",
                    "sentiment_layer",
                    "官方情绪表与行为型价量情绪日期不同，已同时保留 official 与 derived 字段",
                    official_as_of=official_sentiment_as_of,
                    derived_as_of=market_effective_date,
                )
            )

    final_sentiment_score = official_sentiment_score if official_sentiment_score is not None else derived_sentiment_score
    final_sentiment_regime = official_sentiment_regime or derived_regime

    risk_layer_warnings: list[dict[str, Any]] = []
    recent_20 = market_history_prepared.loc[
        market_history_prepared["date"] <= market_effective_ts,
        ["date", "symbol", "ret_1d"],
    ].dropna(subset=["ret_1d"])
    recent_20 = recent_20.pivot(index="date", columns="symbol", values="ret_1d").sort_index().tail(20)
    cross_section_corr_20d = None
    if len(recent_20.index) >= 10 and len(recent_20.columns) >= 5:
        market_proxy = recent_20.mean(axis=1, skipna=True)
        correlations = recent_20.apply(lambda col: col.corr(market_proxy), axis=0)
        valid_corr = correlations.dropna()
        if not valid_corr.empty:
            cross_section_corr_20d = float(valid_corr.mean())
    if cross_section_corr_20d is None:
        risk_layer_warnings.append(
            _make_warning(
                "CROSS_SECTION_CORR_SHORT",
                "risk_layer",
                "横截面相关性样本不足，cross_section_corr_20d 已置空",
                effective_as_of=market_effective_date,
            )
        )

    fragility_components: list[float] = []
    if _to_float(daily_row.get("above_ma20_ratio")) is not None:
        fragility_components.append(1.0 - float(daily_row["above_ma20_ratio"]))
    high_low_total = (_to_int(daily_row.get("new_high_20d_count")) or 0) + (_to_int(daily_row.get("new_low_20d_count")) or 0)
    if high_low_total > 0:
        fragility_components.append((_to_int(daily_row.get("new_low_20d_count")) or 0) / high_low_total)
    limit_total = (limit_up_count or 0) + (limit_down_count or 0)
    if limit_total > 0:
        fragility_components.append((limit_down_count or 0) / limit_total)
    breadth_fragility_score = float(sum(fragility_components) / len(fragility_components)) if fragility_components else None

    nav_series = pd.to_numeric(market_daily["market_proxy_nav"], errors="coerce").dropna()
    drawdown_from_60d_high = None
    if market_effective_ts in nav_series.index:
        recent_nav = nav_series.loc[nav_series.index <= market_effective_ts].tail(60)
        if len(recent_nav) >= 20:
            current_nav = float(recent_nav.iloc[-1])
            rolling_high = float(recent_nav.max())
            if rolling_high > 0:
                drawdown_from_60d_high = current_nav / rolling_high - 1.0

    index_layer = {
        "reference_as_of": style_reference_date,
        "indices": index_entries,
        "summary": {
            "leader_1d": max(ranked_1d, key=ranked_1d.get) if ranked_1d else None,
            "leader_20d": max(ranked_20d, key=ranked_20d.get) if ranked_20d else None,
        },
        "sources": [
            _source_entry(
                name="pit_index_daily",
                source_type="postgres_index_daily",
                effective_as_of=style_reference_date,
                fields=["close", "ret_1d", "ret_20d", "ret_60d", "ma20_gap", "ma60_gap"],
            )
        ],
        "coverage": {
            "requested_trade_date": requested_trade_date.isoformat(),
            "available_indices": sum(1 for item in index_entries.values() if item.get("effective_as_of")),
            "total_indices": len(INDEX_SPECS),
            "field_as_of": index_effective_dates,
        },
        "warnings": index_layer_warnings,
    }

    style_layer = {
        "reference_as_of": style_reference_date,
        "style_rel_500_vs_300": _style_diff("csi500", "csi300", "ret_20d"),
        "style_rel_1000_vs_300": _style_diff("csi1000", "csi300", "ret_20d"),
        "style_rel_chinext_vs_300": _style_diff("chinext", "csi300", "ret_20d"),
        "style_leader_1d": max(ranked_1d, key=ranked_1d.get) if ranked_1d else None,
        "style_leader_20d": max(ranked_20d, key=ranked_20d.get) if ranked_20d else None,
        "small_mid_large_rank": small_mid_large_rank,
        "sources": [
            _source_entry(
                name="pit_index_daily",
                source_type="postgres_index_daily",
                effective_as_of=style_reference_date,
                fields=["style_rel_500_vs_300", "style_rel_1000_vs_300", "style_rel_chinext_vs_300"],
            )
        ],
        "coverage": {
            "requested_trade_date": requested_trade_date.isoformat(),
            "reference_as_of": style_reference_date,
        },
        "warnings": style_layer_warnings,
    }

    breadth_layer = {
        "effective_as_of": max(filter(None, [_to_iso_date(breadth_counts_as_of), technical_breadth_as_of]), default=None),
        "advancers_count": advancers_count,
        "decliners_count": decliners_count,
        "up_down_ratio": breadth_up_down_ratio,
        "limit_up_count": limit_up_count,
        "limit_down_count": limit_down_count,
        "new_high_20d_count": _to_int(daily_row.get("new_high_20d_count")),
        "new_low_20d_count": _to_int(daily_row.get("new_low_20d_count")),
        "above_ma20_ratio": _to_float(daily_row.get("above_ma20_ratio")),
        "above_ma60_ratio": _to_float(daily_row.get("above_ma60_ratio")),
        "breadth_balance": breadth_balance,
        "sources": [
            _source_entry(
                name="pams_sentiment_state" if sentiment_row is not None else "pams_ohlcv_daily",
                source_type="sentiment_table" if sentiment_row is not None else "derived_from_market_daily",
                effective_as_of=breadth_counts_as_of,
                fields=["advancers_count", "decliners_count", "limit_up_count", "limit_down_count", "up_down_ratio", "breadth_balance"],
            ),
            _source_entry(
                name="pams_ohlcv_daily",
                source_type="derived_from_market_daily",
                effective_as_of=market_effective_date,
                fields=["new_high_20d_count", "new_low_20d_count", "above_ma20_ratio", "above_ma60_ratio"],
            ),
        ],
        "coverage": {
            "requested_trade_date": requested_trade_date.isoformat(),
            "symbol_count_market_price": _to_int(daily_row.get("symbol_count")),
            "field_as_of": breadth_field_as_of,
        },
        "warnings": breadth_layer_warnings,
    }

    liquidity_layer = {
        "effective_as_of": market_effective_date.isoformat(),
        "market_amount_total": _to_float(daily_row.get("market_amount_total")),
        "market_amount_ma20_prev": _to_float(daily_row.get("market_amount_ma20_prev")),
        "market_amount_heat": amount_heat,
        "turnover_rate_market": _to_float(daily_row.get("turnover_rate_market")),
        "turnover_rate_market_z252": turnover_rate_z252,
        "volume_ratio_market": _to_float(daily_row.get("volume_ratio_market")),
        "circulating_market_cap_total": _to_float(daily_row.get("circ_mv_total")),
        "sources": [
            _source_entry(
                name="pams_ohlcv_daily",
                source_type="postgres_market_daily",
                effective_as_of=market_effective_date,
                fields=[
                    "market_amount_total",
                    "market_amount_ma20_prev",
                    "market_amount_heat",
                    "turnover_rate_market",
                    "turnover_rate_market_z252",
                    "volume_ratio_market",
                    "circulating_market_cap_total",
                ],
            )
        ],
        "coverage": {
            "requested_trade_date": requested_trade_date.isoformat(),
            "effective_as_of": market_effective_date.isoformat(),
            "symbol_count": _to_int(daily_row.get("symbol_count")),
            "turnover_rate_non_null": _to_int(daily_row.get("turnover_rate_non_null")),
            "volume_ratio_non_null": _to_int(daily_row.get("volume_ratio_non_null")),
            "turnover_rate_field": str(market_history_prepared["turnover_rate_field"].iloc[0]),
        },
        "warnings": liquidity_layer_warnings,
    }

    sentiment_field_as_of = {
        "sentiment_score": official_sentiment_as_of or market_effective_date.isoformat(),
        "sentiment_regime": official_sentiment_as_of or market_effective_date.isoformat(),
        "derived_sentiment_score": market_effective_date.isoformat(),
        "derived_sentiment_regime": market_effective_date.isoformat(),
    }
    sentiment_layer = {
        "effective_as_of": official_sentiment_as_of or market_effective_date.isoformat(),
        "breadth_balance": breadth_balance,
        "limit_balance": (((limit_up_count or 0) - (limit_down_count or 0)) / limit_total) if limit_total > 0 else None,
        "turnover_heat": amount_heat,
        "sentiment_score": final_sentiment_score,
        "sentiment_regime": final_sentiment_regime,
        "derived_sentiment_score": derived_sentiment_score,
        "derived_sentiment_regime": derived_regime,
        "official_sentiment_score": official_sentiment_score,
        "official_sentiment_regime": official_sentiment_regime,
        "sources": [
            _source_entry(
                name="pams_ohlcv_daily",
                source_type="derived_from_market_daily",
                effective_as_of=market_effective_date,
                fields=["breadth_balance", "limit_balance", "turnover_heat", "derived_sentiment_score", "derived_sentiment_regime"],
            ),
            _source_entry(
                name="pams_sentiment_state",
                source_type="sentiment_table",
                effective_as_of=official_sentiment_as_of,
                fields=["official_sentiment_score", "official_sentiment_regime", "sentiment_score", "sentiment_regime"],
            ),
        ],
        "coverage": {
            "requested_trade_date": requested_trade_date.isoformat(),
            "field_as_of": sentiment_field_as_of,
        },
        "warnings": sentiment_layer_warnings,
    }

    risk_layer = {
        "effective_as_of": market_effective_date.isoformat(),
        "market_realized_vol_20d": _annualized_vol(market_daily["equal_weight_ret_1d"], 20),
        "market_realized_vol_60d": _annualized_vol(market_daily["equal_weight_ret_1d"], 60),
        "cross_section_corr_20d": cross_section_corr_20d,
        "breadth_fragility_score": breadth_fragility_score,
        "drawdown_from_60d_high": drawdown_from_60d_high,
        "sources": [
            _source_entry(
                name="pams_ohlcv_daily",
                source_type="derived_from_market_daily",
                effective_as_of=market_effective_date,
                fields=[
                    "market_realized_vol_20d",
                    "market_realized_vol_60d",
                    "cross_section_corr_20d",
                    "breadth_fragility_score",
                    "drawdown_from_60d_high",
                ],
            )
        ],
        "coverage": {
            "requested_trade_date": requested_trade_date.isoformat(),
            "effective_as_of": market_effective_date.isoformat(),
            "cross_section_symbol_count": int(len(recent_20.columns)) if not recent_20.empty else 0,
            "cross_section_day_count": int(len(recent_20.index)) if not recent_20.empty else 0,
        },
        "warnings": risk_layer_warnings,
    }

    all_warnings.extend(index_layer["warnings"])
    all_warnings.extend(style_layer["warnings"])
    all_warnings.extend(breadth_layer["warnings"])
    all_warnings.extend(liquidity_layer["warnings"])
    all_warnings.extend(sentiment_layer["warnings"])
    all_warnings.extend(risk_layer["warnings"])
    all_warnings = _dedupe_warnings(all_warnings)

    return {
        "schema_version": "market_snapshot_v1",
        "trade_date": requested_trade_date.isoformat(),
        "generated_at": _now_iso(),
        "build_status": "partial" if all_warnings else "ok",
        "build_meta": {
            "pit_safe": True,
            "provider_query_audit": provider_query_audit,
            "market_price_effective_as_of": market_effective_date.isoformat(),
            "sentiment_effective_as_of": official_sentiment_as_of,
        },
        "index_layer": index_layer,
        "style_layer": style_layer,
        "breadth_layer": breadth_layer,
        "liquidity_layer": liquidity_layer,
        "sentiment_layer": sentiment_layer,
        "risk_layer": risk_layer,
        "sources": {
            "index_layer": index_layer["sources"],
            "style_layer": style_layer["sources"],
            "breadth_layer": breadth_layer["sources"],
            "liquidity_layer": liquidity_layer["sources"],
            "sentiment_layer": sentiment_layer["sources"],
            "risk_layer": risk_layer["sources"],
        },
        "coverage": {
            "index_layer": index_layer["coverage"],
            "style_layer": style_layer["coverage"],
            "breadth_layer": breadth_layer["coverage"],
            "liquidity_layer": liquidity_layer["coverage"],
            "sentiment_layer": sentiment_layer["coverage"],
            "risk_layer": risk_layer["coverage"],
        },
        "warnings": all_warnings,
    }

def render_market_brief(snapshot: dict[str, Any]) -> str:
    trade_date = str(snapshot.get("trade_date") or "")
    build_status = str(snapshot.get("build_status") or "ok")
    warnings = list(snapshot.get("warnings") or [])

    index_layer = dict(snapshot.get("index_layer") or {})
    style_layer = dict(snapshot.get("style_layer") or {})
    breadth_layer = dict(snapshot.get("breadth_layer") or {})
    liquidity_layer = dict(snapshot.get("liquidity_layer") or {})
    sentiment_layer = dict(snapshot.get("sentiment_layer") or {})
    risk_layer = dict(snapshot.get("risk_layer") or {})
    indices = dict(index_layer.get("indices") or {})
    stale_warning = next((item for item in warnings if str(item.get("code") or "").startswith("STALE_")), None)

    lines = [
        f"# A股市场快照（{trade_date}）",
        "",
        "## 今日结论",
        f"- 快照状态：`{build_status}`。",
        f"- 指数层短线领涨：`{((index_layer.get('summary') or {}).get('leader_1d')) or '-'}`；风格层占优：`{style_layer.get('style_leader_20d') or style_layer.get('style_leader_1d') or '-'}`。",
        f"- 广度平衡：`{_fmt_pct(breadth_layer.get('breadth_balance'))}`；成交热度：`{_fmt_float(liquidity_layer.get('market_amount_heat'))}` 倍。",
        f"- 情绪状态：`{sentiment_layer.get('sentiment_regime') or '-'}`，情绪分数：`{_fmt_float(sentiment_layer.get('sentiment_score'))}`。",
    ]
    if stale_warning is not None:
        lines.append(f"- 数据告警：{stale_warning.get('message')}")

    lines.extend(
        [
            "",
            "## 指数与风格",
            (
                f"- 上证综指：`{_fmt_float(((indices.get('sse_composite') or {}).get('close')))}`，"
                f" 1日 `{_fmt_pct(((indices.get('sse_composite') or {}).get('ret_1d')))}`，"
                f" MA20 偏离 `{_fmt_pct(((indices.get('sse_composite') or {}).get('ma20_gap')))}`。"
            ),
            (
                f"- 沪深300：`{_fmt_float(((indices.get('csi300') or {}).get('close')))}`，"
                f" 20日 `{_fmt_pct(((indices.get('csi300') or {}).get('ret_20d')))}`；"
                f" 中证500 相对强弱 `{_fmt_pct(style_layer.get('style_rel_500_vs_300'))}`；"
                f" 创业板相对强弱 `{_fmt_pct(style_layer.get('style_rel_chinext_vs_300'))}`。"
            ),
            f"- 20日风格排序：`{style_layer.get('small_mid_large_rank') or '-'}`。",
        ]
    )

    lines.extend(
        [
            "",
            "## 广度与成交",
            (
                f"- 上涨 / 下跌家数：`{breadth_layer.get('advancers_count') or '-'}` / "
                f"`{breadth_layer.get('decliners_count') or '-'}`，涨跌比 `{_fmt_float(breadth_layer.get('up_down_ratio'))}`。"
            ),
            (
                f"- 20日新高 / 新低：`{breadth_layer.get('new_high_20d_count') or '-'}` / "
                f"`{breadth_layer.get('new_low_20d_count') or '-'}`，站上 MA20 比例 `{_fmt_pct(breadth_layer.get('above_ma20_ratio'))}`。"
            ),
            (
                f"- 全市场成交额：`{_fmt_float(liquidity_layer.get('market_amount_total'))}`，"
                f" 换手率均值 `{_fmt_float(liquidity_layer.get('turnover_rate_market'))}`，"
                f" 换手率 z252 `{_fmt_float(liquidity_layer.get('turnover_rate_market_z252'))}`。"
            ),
        ]
    )

    lines.extend(
        [
            "",
            "## 情绪状态",
            f"- 情绪分数：`{_fmt_float(sentiment_layer.get('sentiment_score'))}`，情绪分区：`{sentiment_layer.get('sentiment_regime') or '-'}`。",
            (
                f"- 行为型代理：breadth_balance `{_fmt_pct(sentiment_layer.get('breadth_balance'))}`，"
                f" limit_balance `{_fmt_pct(sentiment_layer.get('limit_balance'))}`，"
                f" turnover_heat `{_fmt_float(sentiment_layer.get('turnover_heat'))}`。"
            ),
            (
                f"- 官方情绪表：score `{_fmt_float(sentiment_layer.get('official_sentiment_score'))}`，"
                f" regime `{sentiment_layer.get('official_sentiment_regime') or '-'}`。"
            ),
        ]
    )

    lines.extend(
        [
            "",
            "## 风险提示",
            f"- 20日 / 60日市场实现波动：`{_fmt_pct(risk_layer.get('market_realized_vol_20d'))}` / `{_fmt_pct(risk_layer.get('market_realized_vol_60d'))}`。",
            f"- 横截面相关性代理：`{_fmt_float(risk_layer.get('cross_section_corr_20d'))}`；广度脆弱度：`{_fmt_float(risk_layer.get('breadth_fragility_score'))}`。",
            f"- 距 60 日高点回撤：`{_fmt_pct(risk_layer.get('drawdown_from_60d_high'))}`。",
        ]
    )
    if warnings:
        lines.append("- 数据/口径告警：")
        for warning in warnings[:5]:
            lines.append(f"  - {warning.get('code')}: {warning.get('message')}")
    lines.append("")
    return "\n".join(lines)


def _write_snapshot_files(snapshot: dict[str, Any], brief_markdown: str, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_dir / "market_snapshot.json"
    brief_path = output_dir / "market_brief.md"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    brief_path.write_text(brief_markdown, encoding="utf-8")
    return snapshot_path, brief_path


def build_market_snapshot(
    *,
    trade_date: date | str,
    access: RuntimeDataAccess | None = None,
    bt_root: str | Path | None = None,
) -> dict[str, Any]:
    requested_trade_date = date.fromisoformat(trade_date) if isinstance(trade_date, str) else trade_date
    runtime_access = access or load_runtime_data_access(bt_root)
    repository = MarketSnapshotRepository(runtime_access)

    market_effective_date = repository.latest_market_trade_date(requested_trade_date)
    if market_effective_date is None:
        raise MarketSnapshotError(f"no CN_A market data available on or before {requested_trade_date.isoformat()}")

    symbols, universe_meta = resolve_universe_by_mode(
        mode="ALL_A",
        as_of=market_effective_date,
        db=runtime_access.cfg_obj.db,
        runtime=runtime_access.cfg_obj.db_runtime,
    )
    history_start = _history_start_from_calendar(runtime_access, market_effective_date, MARKET_LOOKBACK_DAYS)
    market_history = runtime_access.provider.load_ohlcv_daily(symbols, history_start, market_effective_date, source="market_snapshot")

    index_history_start = _history_start_from_calendar(runtime_access, market_effective_date, INDEX_LOOKBACK_DAYS)
    index_histories: dict[str, pd.DataFrame] = {}
    for spec in INDEX_SPECS:
        symbol = spec["symbol"]
        try:
            frame = runtime_access.provider.load_benchmark_daily(symbol, index_history_start, requested_trade_date)
        except Exception:
            frame = pd.DataFrame(columns=["date", "symbol", "close", "volume", "amount"])
        index_histories[symbol] = frame

    sentiment_history = repository.load_sentiment_history(requested_trade_date)
    snapshot = build_market_snapshot_from_frames(
        requested_trade_date=requested_trade_date,
        market_history=market_history,
        index_histories=index_histories,
        sentiment_history=sentiment_history,
        provider_query_audit=runtime_access.provider.query_audit,
    )
    snapshot["build_meta"]["universe_meta"] = universe_meta
    snapshot["build_meta"]["resolved_symbol_count"] = int(len(symbols))
    snapshot["build_meta"]["market_history_start"] = history_start.isoformat()
    snapshot["build_meta"]["index_history_start"] = index_history_start.isoformat()
    return snapshot


def build_market_snapshot_artifacts(
    *,
    trade_date: date | str,
    access: RuntimeDataAccess | None = None,
    bt_root: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> MarketSnapshotArtifacts:
    requested_trade_date = date.fromisoformat(trade_date) if isinstance(trade_date, str) else trade_date
    snapshot = build_market_snapshot(trade_date=requested_trade_date, access=access, bt_root=bt_root)
    brief_markdown = render_market_brief(snapshot)
    target_dir = Path(output_dir).resolve() if output_dir else resolve_market_snapshot_dir(requested_trade_date, create=True)
    snapshot_path, brief_path = _write_snapshot_files(snapshot, brief_markdown, target_dir)
    return MarketSnapshotArtifacts(
        snapshot=snapshot,
        brief_markdown=brief_markdown,
        output_dir=target_dir,
        snapshot_path=snapshot_path,
        brief_path=brief_path,
    )
