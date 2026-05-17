from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from psycopg.rows import dict_row

from backend.api.shared.json_utils import sanitize_json
from backend.core.data import pg_env
from backend.research.csi1000_negative_attribution import (
    INDEX_CSI1000,
    INDEX_CSI800,
    classify_membership,
    normalize_symbol,
)
from backend.research.simple_entry_quality_attribution import (
    accel_bucket,
    entry_risk_labels,
    entry_risk_tier,
    ma_distance_bucket,
    ret120_bucket,
    ret20_bucket,
    risk_tier_multiplier,
    vol20_bucket,
)


STUDY_ID = "cn_stock/simple_csi1000_trend_rebuild_v1"
MARKET_FILTER_INDICES = ("000300.SH", "000905.SH", "000852.SH")
WINDOWS: dict[str, tuple[str, str]] = {
    "1626": ("2016-01-01", "2026-05-15"),
    "1217": ("2012-01-04", "2017-12-29"),
    "1226": ("2012-01-04", "2026-05-15"),
}


@dataclass(frozen=True)
class SimpleTrendConfig:
    start: str
    end: str
    max_positions: int = 20
    keep_rank: int = 40
    min_bars: int = 120
    ma_window: int = 120
    ret_short_window: int = 60
    ret_rank_window: int = 120
    turnover_window: int = 20
    min_avg_turnover: float = 100_000_000.0
    cost_rate: float = 0.0015
    variant: str = "plain"
    market_filter_indices: tuple[str, ...] = MARKET_FILTER_INDICES
    market_filter_ma_window: int = 120
    market_filter_min_on: int = 2


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_output_root() -> Path:
    return _repo_root() / "outputs" / "studies" / "cn_stock" / "simple_csi1000_trend_rebuild_v1"


def _query_frame(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return pd.DataFrame(rows)


def _load_membership(conn: Any, start: str, end: str) -> pd.DataFrame:
    frame = _query_frame(
        conn,
        """
        SELECT index_code, symbol, start_date, COALESCE(end_date, DATE '2262-04-11') AS end_date
        FROM public.pit_index_constituents
        WHERE index_code IN (%s, %s)
          AND start_date <= %s
          AND COALESCE(end_date, DATE '2262-04-11') >= %s
        """,
        (INDEX_CSI800, INDEX_CSI1000, end, start),
    )
    if frame.empty:
        return pd.DataFrame(columns=["index_code", "symbol", "start_date", "end_date"])
    frame["symbol"] = frame["symbol"].map(normalize_symbol)
    frame["start_date"] = pd.to_datetime(frame["start_date"])
    frame["end_date"] = pd.to_datetime(frame["end_date"])
    return frame


def build_membership_intervals(frame: pd.DataFrame) -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]]:
    intervals: dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]] = {}
    if frame.empty:
        return intervals
    for row in frame.itertuples(index=False):
        symbol = normalize_symbol(getattr(row, "symbol", ""))
        if not symbol:
            continue
        intervals.setdefault(symbol, []).append(
            (pd.Timestamp(row.start_date), pd.Timestamp(row.end_date), str(row.index_code))
        )
    return intervals


def _active_symbols_by_date(
    dates: pd.DatetimeIndex,
    membership: pd.DataFrame,
) -> dict[pd.Timestamp, set[str]]:
    out: dict[pd.Timestamp, set[str]] = {}
    if membership.empty:
        return {pd.Timestamp(date): set() for date in dates}
    slim = membership.loc[:, ["symbol", "start_date", "end_date"]].copy()
    slim["symbol"] = slim["symbol"].map(normalize_symbol)
    for date in dates:
        ts = pd.Timestamp(date)
        active = slim.loc[(slim["start_date"] <= ts) & (slim["end_date"] >= ts), "symbol"]
        out[ts] = set(active.dropna().astype(str).tolist())
    return out


def _load_prices(conn: Any, symbols: list[str], start: str, end: str, preload_days: int = 220) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=["symbol", "date", "adj_close", "turnover", "is_suspended"])
    preload_start = (pd.to_datetime(start) - pd.Timedelta(days=preload_days)).date().isoformat()
    frame = _query_frame(
        conn,
        """
        SELECT symbol, trade_date, close, adj_factor, turnover, is_suspended
        FROM public.pams_ohlcv_daily_v2
        WHERE symbol = ANY(%s)
          AND trade_date BETWEEN %s AND %s
          AND row_status = 'traded'
        ORDER BY symbol, trade_date
        """,
        (symbols, preload_start, end),
    )
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "date", "adj_close", "turnover", "is_suspended"])
    frame["symbol"] = frame["symbol"].map(normalize_symbol)
    frame["date"] = pd.to_datetime(frame["trade_date"])
    for column in ("close", "adj_factor", "turnover"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["adj_close"] = frame["close"] * frame["adj_factor"].replace(0, np.nan)
    frame["is_suspended"] = frame["is_suspended"].fillna(False).astype(bool)
    frame = frame.dropna(subset=["symbol", "date", "adj_close"]).sort_values(["symbol", "date"])
    return frame.loc[:, ["symbol", "date", "adj_close", "turnover", "is_suspended"]]


def _load_index_prices(conn: Any, index_codes: tuple[str, ...], start: str, end: str, preload_days: int = 220) -> pd.DataFrame:
    if not index_codes:
        return pd.DataFrame(columns=["index_code", "date", "close"])
    preload_start = (pd.to_datetime(start) - pd.Timedelta(days=preload_days)).date().isoformat()
    frame = _query_frame(
        conn,
        """
        SELECT index_code, trade_date, close
        FROM public.pit_index_daily
        WHERE index_code = ANY(%s)
          AND trade_date BETWEEN %s AND %s
        ORDER BY index_code, trade_date
        """,
        (list(index_codes), preload_start, end),
    )
    if frame.empty:
        return pd.DataFrame(columns=["index_code", "date", "close"])
    frame["date"] = pd.to_datetime(frame["trade_date"])
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    return frame.dropna(subset=["index_code", "date", "close"]).loc[:, ["index_code", "date", "close"]]


def build_market_gate(index_prices: pd.DataFrame, cfg: SimpleTrendConfig) -> pd.DataFrame:
    if cfg.variant in {"plain", "entry_risk_scaled"}:
        return pd.DataFrame(columns=["date", "market_gate_on", "market_positive_count"])
    if cfg.variant != "market_2of3_ma120":
        raise ValueError(f"unknown variant: {cfg.variant}")
    if index_prices.empty:
        return pd.DataFrame(columns=["date", "market_gate_on", "market_positive_count"])
    frame = index_prices.copy().sort_values(["index_code", "date"]).reset_index(drop=True)
    frame["ma"] = frame.groupby("index_code")["close"].transform(
        lambda s: s.rolling(cfg.market_filter_ma_window, min_periods=cfg.market_filter_ma_window).mean()
    )
    frame["index_on"] = frame["close"] > frame["ma"]
    daily = (
        frame.groupby("date")
        .agg(
            market_positive_count=("index_on", "sum"),
            loaded_index_count=("index_code", "nunique"),
        )
        .reset_index()
    )
    daily["market_gate_on"] = daily["market_positive_count"] >= cfg.market_filter_min_on
    daily = daily.loc[daily["date"].between(pd.to_datetime(cfg.start), pd.to_datetime(cfg.end))]
    return daily.loc[:, ["date", "market_gate_on", "market_positive_count", "loaded_index_count"]]


def add_simple_trend_features(prices: pd.DataFrame, cfg: SimpleTrendConfig) -> pd.DataFrame:
    if prices.empty:
        return pd.DataFrame()
    frame = prices.copy().sort_values(["symbol", "date"]).reset_index(drop=True)
    grouped = frame.groupby("symbol", sort=False)
    frame["bars"] = grouped.cumcount() + 1
    frame["daily_return"] = grouped["adj_close"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    frame["ma120"] = grouped["adj_close"].transform(lambda s: s.rolling(cfg.ma_window, min_periods=cfg.ma_window).mean())
    frame["ret20"] = grouped["adj_close"].pct_change(20)
    frame["ret60"] = grouped["adj_close"].pct_change(cfg.ret_short_window)
    frame["ret120"] = grouped["adj_close"].pct_change(cfg.ret_rank_window)
    frame["avg_turnover20"] = grouped["turnover"].transform(
        lambda s: s.rolling(cfg.turnover_window, min_periods=cfg.turnover_window).mean()
    )
    frame["vol20"] = grouped["daily_return"].transform(lambda s: s.rolling(20, min_periods=20).std(ddof=0))
    frame["ma120_distance"] = frame["adj_close"] / frame["ma120"] - 1.0
    frame["eligible_base"] = (
        (frame["bars"] >= cfg.min_bars)
        & (frame["adj_close"] > frame["ma120"])
        & (frame["ret60"] > 0)
        & (frame["avg_turnover20"] >= cfg.min_avg_turnover)
        & (~frame["is_suspended"])
    )
    return frame


def select_rebalance_target(
    features_on_date: pd.DataFrame,
    active_symbols: set[str],
    cfg: SimpleTrendConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if features_on_date.empty or not active_symbols:
        empty = pd.DataFrame(columns=list(features_on_date.columns) + ["rank"])
        return empty, empty
    candidates = features_on_date.loc[
        features_on_date["symbol"].isin(active_symbols) & features_on_date["eligible_base"]
    ].copy()
    if candidates.empty:
        candidates["rank"] = pd.Series(dtype=int)
        return candidates, candidates
    candidates = candidates.sort_values(
        ["ret120", "ret60", "avg_turnover20", "symbol"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    candidates["rank"] = np.arange(1, len(candidates) + 1)
    target = candidates.head(cfg.max_positions).copy()
    return target, candidates


def _candidate_entry_risk_tier(row: pd.Series, membership_bucket: str) -> str:
    buckets = {
        "membership_bucket": membership_bucket,
        "ret120_bucket": ret120_bucket(row.get("ret120")),
        "ret20_bucket": ret20_bucket(row.get("ret20")),
        "ma_distance_bucket": ma_distance_bucket(row.get("ma120_distance")),
        "vol20_bucket": vol20_bucket(row.get("vol20")),
        "accel_bucket": accel_bucket(row.get("ret20"), row.get("ret120")),
    }
    return entry_risk_tier(len(entry_risk_labels(buckets)))


def _rebalance_dates(dates: pd.Series, start: str, end: str) -> list[pd.Timestamp]:
    calendar = pd.Series(pd.to_datetime(dates).drop_duplicates()).sort_values()
    calendar = calendar.loc[calendar.between(pd.to_datetime(start), pd.to_datetime(end))]
    if calendar.empty:
        return []
    weeks = calendar.dt.strftime("%G-%V")
    return calendar.groupby(weeks).first().map(pd.Timestamp).tolist()


def _metrics(nav: pd.DataFrame) -> dict[str, Any]:
    if nav.empty:
        return {}
    returns = pd.to_numeric(nav["daily_return"], errors="coerce").fillna(0.0)
    nav_series = pd.to_numeric(nav["nav"], errors="coerce").dropna()
    if nav_series.empty:
        return {}
    days = max((pd.to_datetime(nav["date"]).max() - pd.to_datetime(nav["date"]).min()).days, 1)
    years = days / 365.25
    total_return = float(nav_series.iloc[-1] / nav_series.iloc[0] - 1.0)
    cagr = (float(nav_series.iloc[-1] / nav_series.iloc[0]) ** (1.0 / years) - 1.0) if years > 0 else 0.0
    std = float(returns.std(ddof=0))
    sharpe = float((returns.mean() / std) * math.sqrt(252)) if std > 0 else 0.0
    running_max = nav_series.cummax()
    dd = nav_series / running_max - 1.0
    max_drawdown = float(dd.min())
    calmar = float(cagr / abs(max_drawdown)) if max_drawdown < 0 else 0.0
    return {
        "start": str(pd.to_datetime(nav["date"]).min().date()),
        "end": str(pd.to_datetime(nav["date"]).max().date()),
        "trading_days": int(len(nav)),
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "calmar": calmar,
        "avg_positions": float(pd.to_numeric(nav["positions"], errors="coerce").mean()),
        "avg_exposure": float(pd.to_numeric(nav["exposure"], errors="coerce").mean()) if "exposure" in nav else 0.0,
        "avg_turnover_per_rebalance": float(pd.to_numeric(nav["turnover"], errors="coerce").replace(0, np.nan).mean() or 0.0),
        "total_turnover": float(pd.to_numeric(nav["turnover"], errors="coerce").sum()),
    }


def run_backtest_from_frames(
    prices: pd.DataFrame,
    membership: pd.DataFrame,
    cfg: SimpleTrendConfig,
    index_prices: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame | dict[str, Any]]:
    features = add_simple_trend_features(prices, cfg)
    if features.empty:
        return {"nav": pd.DataFrame(), "trades": pd.DataFrame(), "holdings": pd.DataFrame(), "candidates": pd.DataFrame(), "perf": {}}

    dates = pd.Series(features["date"].drop_duplicates()).sort_values()
    trading_dates = [pd.Timestamp(item) for item in dates if pd.Timestamp(cfg.start) <= pd.Timestamp(item) <= pd.Timestamp(cfg.end)]
    rebalance_set = set(_rebalance_dates(pd.Series(trading_dates), cfg.start, cfg.end))
    active_by_date = _active_symbols_by_date(pd.DatetimeIndex(trading_dates), membership)
    market_gate = build_market_gate(index_prices if index_prices is not None else pd.DataFrame(), cfg)
    if market_gate.empty:
        market_by_date = {date: (True, None, None) for date in trading_dates}
    else:
        market_by_date = {
            pd.Timestamp(row.date): (
                bool(row.market_gate_on),
                int(row.market_positive_count),
                int(getattr(row, "loaded_index_count", 0)),
            )
            for row in market_gate.itertuples(index=False)
        }
    membership_intervals = build_membership_intervals(membership)
    feature_by_date = {pd.Timestamp(k): v.copy() for k, v in features.groupby("date", sort=False)}
    returns_by_date = {
        pd.Timestamp(row.date): {} for row in features.loc[features["date"].isin(trading_dates), ["date"]].drop_duplicates().itertuples(index=False)
    }
    for row in features.loc[features["date"].isin(trading_dates), ["date", "symbol", "daily_return"]].itertuples(index=False):
        returns_by_date.setdefault(pd.Timestamp(row.date), {})[str(row.symbol)] = float(row.daily_return)

    positions: dict[str, float] = {}
    position_tiers: dict[str, str] = {}
    nav_value = 1.0
    nav_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    holding_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    for date in trading_dates:
        date_returns = returns_by_date.get(date, {})
        gross_return = sum(weight * date_returns.get(symbol, 0.0) for symbol, weight in positions.items())
        nav_value *= 1.0 + gross_return
        turnover = 0.0
        cost = 0.0

        if date in rebalance_set:
            market_gate_on, market_positive_count, loaded_index_count = market_by_date.get(date, (True, None, None))
            target_frame, candidate_frame = select_rebalance_target(
                feature_by_date.get(date, pd.DataFrame()),
                active_by_date.get(date, set()),
                cfg,
            )
            for row in candidate_frame.head(max(cfg.keep_rank, cfg.max_positions)).itertuples(index=False):
                candidate_rows.append(
                    {
                        "date": date.date().isoformat(),
                        "symbol": str(row.symbol),
                        "rank": int(row.rank),
                        "bucket": classify_membership(row.symbol, date, membership_intervals),
                        "ret20": float(row.ret20) if pd.notna(row.ret20) else None,
                        "ret60": float(row.ret60) if pd.notna(row.ret60) else None,
                        "ret120": float(row.ret120) if pd.notna(row.ret120) else None,
                        "ma120_distance": float(row.ma120_distance) if pd.notna(row.ma120_distance) else None,
                        "vol20": float(row.vol20) if pd.notna(row.vol20) else None,
                        "avg_turnover20": float(row.avg_turnover20) if pd.notna(row.avg_turnover20) else None,
                    }
                )

            if not market_gate_on:
                target_symbols = []
            else:
                candidate_ranks = {str(row.symbol): int(row.rank) for row in candidate_frame.itertuples(index=False)}
                candidate_symbols = [str(symbol) for symbol in candidate_frame["symbol"].tolist()]
                keep_symbols = [
                    symbol
                    for symbol in positions
                    if candidate_ranks.get(symbol, cfg.keep_rank + 1) <= cfg.keep_rank
                ]
                target_symbols = list(keep_symbols)
                for symbol in candidate_symbols:
                    if len(target_symbols) >= cfg.max_positions:
                        break
                    if symbol not in target_symbols:
                        target_symbols.append(symbol)
            target_weight = 1.0 / len(target_symbols) if target_symbols else 0.0
            new_position_tiers: dict[str, str] = {}
            new_positions: dict[str, float] = {}
            feature_rows = feature_by_date.get(date, pd.DataFrame())
            feature_by_symbol = (
                {str(row.symbol): pd.Series(row._asdict()) for row in feature_rows.itertuples(index=False)}
                if not feature_rows.empty
                else {}
            )
            for symbol in target_symbols:
                if symbol in positions and symbol in position_tiers:
                    tier = position_tiers[symbol]
                else:
                    membership_bucket = classify_membership(symbol, date, membership_intervals)
                    tier = _candidate_entry_risk_tier(feature_by_symbol.get(symbol, pd.Series(dtype=object)), membership_bucket)
                multiplier = risk_tier_multiplier(tier) if cfg.variant == "entry_risk_scaled" else 1.0
                new_position_tiers[symbol] = tier
                new_positions[symbol] = target_weight * multiplier
            touched = sorted(set(positions) | set(new_positions))
            turnover = sum(abs(new_positions.get(symbol, 0.0) - positions.get(symbol, 0.0)) for symbol in touched)
            cost = turnover * cfg.cost_rate
            nav_value *= 1.0 - cost
            for symbol in touched:
                before = positions.get(symbol, 0.0)
                after = new_positions.get(symbol, 0.0)
                if abs(after - before) < 1e-12:
                    continue
                side = "BUY" if after > before else "SELL"
                reason = "rebalance_buy" if side == "BUY" and before == 0 else "rank_or_trend_rebalance"
                if side == "SELL" and after == 0:
                    if not market_gate_on:
                        reason = "market_filter_off"
                    else:
                        on_date = feature_by_date.get(date, pd.DataFrame())
                        matched = on_date.loc[on_date["symbol"] == symbol]
                        if not matched.empty and not bool(matched.iloc[0]["eligible_base"]):
                            reason = "trend_fail"
                        else:
                            reason = "rank_exit"
                trade_rows.append(
                    {
                        "date": date.date().isoformat(),
                        "symbol": symbol,
                        "side": side,
                        "weight_before": before,
                        "weight_after": after,
                        "weight_delta": after - before,
                        "bucket": classify_membership(symbol, date, membership_intervals),
                        "entry_risk_tier": new_position_tiers.get(symbol, position_tiers.get(symbol, "")),
                        "risk_multiplier": risk_tier_multiplier(new_position_tiers.get(symbol, position_tiers.get(symbol, "0_low")))
                        if cfg.variant == "entry_risk_scaled"
                        else 1.0,
                        "reason": reason,
                    }
                )
            positions = new_positions
            position_tiers = new_position_tiers
            for symbol, weight in sorted(positions.items()):
                holding_rows.append(
                    {
                        "date": date.date().isoformat(),
                        "symbol": symbol,
                        "weight": weight,
                        "bucket": classify_membership(symbol, date, membership_intervals),
                        "entry_risk_tier": position_tiers.get(symbol, ""),
                        "risk_multiplier": risk_tier_multiplier(position_tiers.get(symbol, "0_low"))
                        if cfg.variant == "entry_risk_scaled"
                        else 1.0,
                    }
                )

        bucket_return: dict[str, float] = {}
        for symbol, weight in positions.items():
            bucket = classify_membership(symbol, date, membership_intervals)
            bucket_return[bucket] = bucket_return.get(bucket, 0.0) + weight * date_returns.get(symbol, 0.0)
        nav_rows.append(
            {
                "date": date.date().isoformat(),
                "nav": nav_value,
                "daily_return": gross_return - cost,
                "gross_return": gross_return,
                "cost": cost,
                "turnover": turnover,
                "positions": len(positions),
                "exposure": sum(positions.values()),
                "market_gate_on": bool(market_by_date.get(date, (True, None, None))[0]),
                "market_positive_count": market_by_date.get(date, (True, None, None))[1],
                "loaded_market_index_count": market_by_date.get(date, (True, None, None))[2],
                "csi800_only_return": bucket_return.get("csi800_only", 0.0),
                "csi1000_new_return": bucket_return.get("csi1000_new", 0.0),
                "overlap_return": bucket_return.get("overlap", 0.0),
                "unclassified_return": bucket_return.get("unclassified", 0.0),
            }
        )

    nav = pd.DataFrame(nav_rows)
    trades = pd.DataFrame(trade_rows)
    holdings = pd.DataFrame(holding_rows)
    candidates = pd.DataFrame(candidate_rows)
    perf = _metrics(nav)
    perf["trade_rows"] = int(len(trades))
    perf["rebalance_count"] = int(len(rebalance_set))
    if not nav.empty and "market_gate_on" in nav:
        perf["market_gate_on_ratio"] = float(nav["market_gate_on"].astype(bool).mean())
    if not holdings.empty:
        perf["avg_csi1000_weight_at_rebalance"] = float(
            holdings.assign(is_csi1000=holdings["bucket"].eq("csi1000_new")).groupby("date")["is_csi1000"].mean().mean()
        )
    return {
        "nav": nav,
        "trades": trades,
        "holdings": holdings,
        "candidates": candidates,
        "perf": perf,
    }


def _bucket_summary(nav: pd.DataFrame, holdings: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    buckets = ["csi800_only", "csi1000_new", "overlap", "unclassified"]
    rows: list[dict[str, Any]] = []
    for bucket in buckets:
        return_col = f"{bucket}_return"
        avg_holdings = 0.0
        if not holdings.empty:
            by_date = holdings.assign(hit=holdings["bucket"].eq(bucket)).groupby("date")["hit"].mean()
            avg_holdings = float(by_date.mean()) if not by_date.empty else 0.0
        trade_count = int((trades["bucket"].eq(bucket)).sum()) if not trades.empty and "bucket" in trades else 0
        rows.append(
            {
                "bucket": bucket,
                "return_contribution_sum": float(pd.to_numeric(nav.get(return_col, pd.Series(dtype=float)), errors="coerce").sum()),
                "avg_rebalance_position_share": avg_holdings,
                "trade_rows": trade_count,
            }
        )
    return pd.DataFrame(rows)


def _write_outputs(result: dict[str, Any], out_dir: Path, cfg: SimpleTrendConfig, window: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for key in ("nav", "trades", "holdings", "candidates"):
        frame = result.get(key)
        if isinstance(frame, pd.DataFrame):
            frame.to_csv(out_dir / f"{key}.csv", index=False, encoding="utf-8-sig")
    bucket_summary = _bucket_summary(result["nav"], result["holdings"], result["trades"])
    bucket_summary.to_csv(out_dir / "bucket_summary.csv", index=False, encoding="utf-8-sig")
    summary = {
        "study_id": STUDY_ID,
        "window": window,
        "config": asdict(cfg),
        "data_sources": {
            "prices": "public.pams_ohlcv_daily_v2 adjusted close = close * adj_factor",
            "membership": "public.pit_index_constituents 000906.SH + 000852.SH",
        },
        "perf": result["perf"],
        "bucket_summary": bucket_summary.to_dict(orient="records"),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        f"# {STUDY_ID} {window}",
        "",
        "## Rule",
        "",
        "- PIT universe: CSI800 + CSI1000.",
        "- Weekly equal-weight rebalance.",
        "- Candidate: bars>=120, close>MA120, ret60>0, avg turnover20>=100m.",
        "- Rank: ret120 desc, ret60 desc.",
        "- No market state, industry state, theme proxy, residual rank, or post-entry failure layer.",
        "",
        "## Metrics",
        "",
    ]
    for key, value in result["perf"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Bucket Summary", "", bucket_summary.to_markdown(index=False)])
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def run_window(window: str, *, variant: str = "plain", output_root: Path | None = None) -> dict[str, Any]:
    if window not in WINDOWS:
        raise ValueError(f"unknown window: {window}")
    start, end = WINDOWS[window]
    cfg = SimpleTrendConfig(start=start, end=end, variant=variant)
    with pg_env.connect(config_path="backend/configs/pams_cn_pg.json", autocommit=True, connect_timeout=10) as conn:
        membership = _load_membership(conn, start, end)
        symbols = sorted(membership["symbol"].dropna().map(normalize_symbol).unique().tolist())
        prices = _load_prices(conn, symbols, start, end)
        index_prices = _load_index_prices(conn, cfg.market_filter_indices, start, end)
    result = run_backtest_from_frames(prices, membership, cfg, index_prices=index_prices)
    out_dir = (output_root or _default_output_root()) / variant / window
    _write_outputs(result, out_dir, cfg, window)
    return {"output_dir": str(out_dir), **result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Research-only simple CSI1000 trend rebuild backtest")
    parser.add_argument("--window", choices=sorted(WINDOWS), default="1626")
    parser.add_argument("--variant", choices=["plain", "market_2of3_ma120", "entry_risk_scaled"], default="plain")
    parser.add_argument("--output-root", default="")
    args = parser.parse_args(argv)
    result = run_window(args.window, variant=args.variant, output_root=Path(args.output_root).resolve() if args.output_root else None)
    print(json.dumps(sanitize_json({"output_dir": result["output_dir"], "perf": result["perf"]}), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
