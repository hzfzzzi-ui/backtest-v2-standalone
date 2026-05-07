from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from backend.core.config.loader import load_config
from backend.core.data.provider_factory import build_runtime_provider_from_config
from backend.core.data.price_adjust import apply_price_adjustment
from backend.core.engine_vector.breakout_signal_provider import _build_industry_assignment_matrices


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "ops" / "v10_1_pnl_source_analysis_20260314"
WINDOWS = {
    "12-17": {
        "exp_id": "exp_20260314_144431437_56c4",
        "subphases": {
            "2012-2013": ("2012-01-04", "2013-12-31"),
            "2014-2015": ("2014-01-02", "2015-06-12"),
            "2015-2017": ("2015-06-15", "2017-01-13"),
        },
    },
    "16-26": {
        "exp_id": "exp_20260314_144548534_7db9",
        "subphases": {},
    },
}


def _safe_float(value: object, default: float = np.nan) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _provider():
    cfg, _ = load_config(str(ROOT / "backend" / "configs" / "pams_cn_pg.json"))
    return build_runtime_provider_from_config(
        cfg,
        ROOT / "backend" / "core" / "data" / "rules.csv",
        use_cache=False,
    )


def _calendar_maps(calendar: pd.DatetimeIndex) -> tuple[dict[pd.Timestamp, pd.Timestamp], dict[pd.Timestamp, pd.Timestamp]]:
    dates = [pd.Timestamp(x).normalize() for x in calendar]
    prev_map: dict[pd.Timestamp, pd.Timestamp] = {}
    next_map: dict[pd.Timestamp, pd.Timestamp] = {}
    for i, dt in enumerate(dates):
        if i > 0:
            prev_map[dt] = dates[i - 1]
        if i < len(dates) - 1:
            next_map[dt] = dates[i + 1]
    return prev_map, next_map


def _load_roundtrips(exp_id: str, window_label: str) -> pd.DataFrame:
    exp_dir = ROOT / "outputs" / "experiments" / exp_id
    trades = pd.read_csv(exp_dir / "portfolio_trades.csv", parse_dates=["date"])
    trades["symbol"] = trades["symbol"].astype(str).str.lower()
    buys = trades[trades["side"].astype(str).str.upper() == "BUY"].copy().sort_values(["date", "symbol"])
    sells = trades[trades["side"].astype(str).str.upper() == "SELL"].copy().sort_values(["date", "symbol"])
    buy_rows = []
    for row in buys.itertuples(index=False):
        meta = {}
        try:
            meta = json.loads(str(getattr(row, "meta_json", "{}")))
        except Exception:
            meta = {}
        buy_rows.append((row, meta))
    fifo: dict[str, deque] = defaultdict(deque)
    for row, meta in buy_rows:
        fifo[str(row.symbol)].append((row, meta))
    roundtrips: list[dict[str, object]] = []
    for sell in sells.itertuples(index=False):
        sym = str(sell.symbol)
        if not fifo.get(sym):
            continue
        buy, meta = fifo[sym].popleft()
        buy_fill = _safe_float(getattr(buy, "fill_price", np.nan))
        sell_fill = _safe_float(getattr(sell, "fill_price", np.nan))
        qty = int(getattr(sell, "qty", 0) or 0)
        if not np.isfinite(buy_fill) or not np.isfinite(sell_fill) or qty <= 0:
            continue
        sell_meta = {}
        try:
            sell_meta = json.loads(str(getattr(sell, "meta_json", "{}")))
        except Exception:
            sell_meta = {}
        roundtrips.append(
            {
                "window_label": window_label,
                "symbol": sym,
                "buy_date": pd.Timestamp(buy.date).normalize(),
                "sell_date": pd.Timestamp(sell.date).normalize(),
                "trade_return_pct": sell_fill / buy_fill - 1.0,
                "buy_fill_price": buy_fill,
                "sell_fill_price": sell_fill,
                "qty": qty,
                "pnl": (sell_fill - buy_fill) * qty,
                "holding_days": int((pd.Timestamp(sell.date).normalize() - pd.Timestamp(buy.date).normalize()).days),
                "exit_reason": str(getattr(sell, "reason_code", "")),
                "industry_relative_score": _safe_float(meta.get("residual_strength_score")),
                "residual_score": _safe_float(meta.get("residual_strength_score")),
                "benchmark_relative_component": _safe_float(meta.get("residual_vs_bench_raw")),
                "sector_relative_component": _safe_float(meta.get("residual_vs_sector_raw")),
                "industry_median_excess_raw": _safe_float(meta.get("industry_median_excess_raw")),
                "sector_beta_tailwind_raw": _safe_float(meta.get("sector_beta_tailwind_raw")),
                "final_rank": _safe_float(meta.get("mf_rank")),
                "selected_flag": True,
                "final_score": _safe_float(meta.get("final_score")),
                "breakout_distance_pct": _safe_float(meta.get("breakout_margin_raw")),
                "buy_date_regime": "STRONG_RISK_ON" if bool(meta.get("strong_risk_on", False)) else ("RISK_ON" if bool(meta.get("regime_on", False)) else "RISK_OFF"),
                "sell_date_regime": "STRONG_RISK_ON" if bool(sell_meta.get("strong_risk_on", False)) else ("RISK_ON" if bool(sell_meta.get("regime_on", False)) else "RISK_OFF"),
            }
        )
    return pd.DataFrame(roundtrips)


def _prepare_feature_frame(raw: pd.DataFrame) -> pd.DataFrame:
    out = raw.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out["symbol"] = out["symbol"].astype(str).str.lower()
    for col in [
        "open",
        "high",
        "low",
        "close",
        "limit_up",
        "adj_factor",
    ]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    grp = out.groupby("symbol", group_keys=False)
    out["prev_close_raw"] = grp["close"].shift(1)
    out["gap_pct"] = out["open"] / out["prev_close_raw"] - 1.0
    day_range = (out["high"] - out["low"]).replace(0, np.nan)
    out["intraday_reversal_pct"] = (out["high"] - out["close"]) / day_range
    out["limit_hit_up"] = out["limit_up"].notna() & (((out["high"] / out["limit_up"]) >= 0.999) | ((out["close"] / out["limit_up"]) >= 0.999))
    out["recent_limit_move_count_signal"] = grp["limit_hit_up"].apply(lambda s: s.rolling(5, min_periods=1).sum()).shift(1)

    adj = apply_price_adjustment(out[["date", "symbol", "open", "high", "low", "close", "adj_factor"]].copy(), "hfq")
    adj = adj.sort_values(["symbol", "date"]).reset_index(drop=True)
    agrp = adj.groupby("symbol", group_keys=False)
    adj["prev_close"] = agrp["close"].shift(1)
    adj["ret_10"] = adj["close"] / agrp["close"].shift(10) - 1.0
    adj["ret_20"] = adj["close"] / agrp["close"].shift(20) - 1.0
    adj["ret_40"] = adj["close"] / agrp["close"].shift(40) - 1.0
    adj["ma20"] = agrp["close"].apply(lambda s: s.rolling(20, min_periods=15).mean())
    adj["ma60"] = agrp["close"].apply(lambda s: s.rolling(60, min_periods=40).mean())
    tr = pd.concat(
        [
            (adj["high"] - adj["low"]).abs(),
            (adj["high"] - adj["prev_close"]).abs(),
            (adj["low"] - adj["prev_close"]).abs(),
        ],
        axis=1,
    ).max(axis=1)
    adj["atr20"] = tr.groupby(adj["symbol"]).apply(lambda s: s.rolling(20, min_periods=15).mean()).reset_index(level=0, drop=True)
    adj["atr60"] = tr.groupby(adj["symbol"]).apply(lambda s: s.rolling(60, min_periods=40).mean()).reset_index(level=0, drop=True)
    adj["distance_to_ma20_pct"] = adj["close"] / adj["ma20"] - 1.0
    adj["distance_to_ma60_pct"] = adj["close"] / adj["ma60"] - 1.0
    adj["atr20_pct"] = adj["atr20"] / adj["close"]
    adj["atr_expansion_pct"] = adj["atr20"] / adj["atr60"] - 1.0
    return out.merge(
        adj[
            [
                "date",
                "symbol",
                "ret_10",
                "ret_20",
                "ret_40",
                "distance_to_ma20_pct",
                "distance_to_ma60_pct",
                "atr20_pct",
                "atr_expansion_pct",
            ]
        ],
        on=["date", "symbol"],
        how="left",
    )


def _membership_mask(membership_history: pd.DataFrame, symbols: list[str], dates: pd.DatetimeIndex) -> np.ndarray:
    mask = np.zeros((len(dates), len(symbols)), dtype=bool)
    symbol_to_col = {str(sym).lower(): idx for idx, sym in enumerate(symbols)}
    hist = membership_history.copy()
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    hist["start_date"] = pd.to_datetime(hist["start_date"], errors="coerce").dt.normalize()
    hist["end_date"] = pd.to_datetime(hist["end_date"], errors="coerce").dt.normalize()
    hist = hist.dropna(subset=["symbol", "start_date"]).reset_index(drop=True)
    for row in hist.itertuples(index=False):
        col = symbol_to_col.get(str(row.symbol).lower())
        if col is None:
            continue
        start_idx = int(dates.searchsorted(pd.Timestamp(row.start_date).normalize(), side="left"))
        end_idx = int(dates.searchsorted(pd.Timestamp(row.end_date).normalize(), side="left")) if not pd.isna(row.end_date) else len(dates)
        if start_idx < len(dates) and start_idx < end_idx:
            mask[start_idx:end_idx, col] = True
    return mask


def _classify_regime(close: float, ma20: float, ma120: float, slope5: float) -> str:
    if not np.isfinite(close) or not np.isfinite(ma20) or not np.isfinite(ma120):
        return "UNKNOWN"
    if close >= ma120 and ma20 >= ma120 and slope5 > 0:
        return "BULL"
    if close >= ma120:
        return "TRANS_UP"
    if close < ma120 and ma20 < ma120:
        return "BEAR"
    return "TRANS_DOWN"


def _build_daily_cross(
    feature_frame: pd.DataFrame,
    benchmark: pd.DataFrame,
    membership_history: pd.DataFrame,
    industry_map: dict[str, str],
    industry_history: pd.DataFrame,
    sector_data: dict[str, pd.DataFrame],
    dates: pd.DatetimeIndex,
    symbols: list[str],
) -> pd.DataFrame:
    frame = feature_frame.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.lower()
    by_date = {dt: grp.copy() for dt, grp in frame.groupby("date", sort=True)}
    active_mask = _membership_mask(membership_history, symbols, dates)
    name_matrix, code_matrix = _build_industry_assignment_matrices(
        industry_map=industry_map,
        industry_history=industry_history,
        sector_data=sector_data,
        symbols=symbols,
        dates=dates.to_numpy(),
    )
    if name_matrix is None or code_matrix is None:
        raise RuntimeError("industry assignment unavailable")
    names = np.asarray(name_matrix, dtype=object)
    codes = np.asarray(code_matrix, dtype=object)
    sym_to_col = {sym: i for i, sym in enumerate(symbols)}

    bm = benchmark.copy()
    bm["date"] = pd.to_datetime(bm["date"]).dt.normalize()
    bm["close"] = pd.to_numeric(bm["close"], errors="coerce")
    bm = bm.sort_values("date").reset_index(drop=True)
    bm["ret40"] = bm["close"] / bm["close"].shift(40) - 1.0
    bm["ma20"] = bm["close"].rolling(20, min_periods=15).mean()
    bm["ma120"] = bm["close"].rolling(120, min_periods=80).mean()
    bm["slope5"] = bm["ma20"] / bm["ma20"].shift(5) - 1.0
    bm_map = bm.set_index("date")[["ret40", "close", "ma20", "ma120", "slope5"]].to_dict(orient="index")

    sector_ret60: dict[str, dict[pd.Timestamp, float]] = {}
    for code, df in sector_data.items():
        tmp = df.copy()
        date_col = "trade_date" if "trade_date" in tmp.columns else "date"
        tmp["date"] = pd.to_datetime(tmp[date_col]).dt.normalize()
        tmp["close"] = pd.to_numeric(tmp["close"], errors="coerce")
        tmp = tmp.sort_values("date").reset_index(drop=True)
        tmp["ret60"] = tmp["close"] / tmp["close"].shift(60) - 1.0
        sector_ret60[str(code).upper()] = tmp.set_index("date")["ret60"].to_dict()

    rows: list[dict[str, object]] = []
    for idx, dt in enumerate(dates):
        grp = by_date.get(pd.Timestamp(dt).normalize())
        if grp is None or grp.empty:
            continue
        active = {symbols[i] for i in np.flatnonzero(active_mask[idx])}
        if not active:
            continue
        day = grp[grp["symbol"].isin(active)].copy()
        if day.empty:
            continue
        day["industry_l1"] = [names[idx, sym_to_col[s]] for s in day["symbol"]]
        day["industry_index_code"] = [codes[idx, sym_to_col[s]] for s in day["symbol"]]
        day = day.dropna(subset=["industry_l1", "ret_40"]).copy()
        if day.empty:
            continue
        bm_row = bm_map.get(pd.Timestamp(dt).normalize(), {})
        bench_ret40 = _safe_float(bm_row.get("ret40"))
        day["residual_vs_bench_raw"] = day["ret_40"] - bench_ret40
        day["sector_ret60"] = [sector_ret60.get(str(c).upper(), {}).get(pd.Timestamp(dt).normalize(), np.nan) if c is not None else np.nan for c in day["industry_index_code"]]
        day["residual_vs_sector_raw"] = day["ret_40"] - day["sector_ret60"]
        day["residual_score_daily"] = day["residual_vs_sector_raw"].rank(method="average", pct=True)
        day["industry_rank_pct"] = day.groupby("industry_l1")["ret_40"].rank(method="average", pct=True)
        stats = day.groupby("industry_l1").agg(
            industry_breadth_level=("ret_20", lambda s: float(np.nanmean(np.asarray(s) > 0.0))),
            industry_top_strength_dispersion=("ret_40", lambda s: float(np.nanpercentile(np.asarray(s.dropna()), 80) - np.nanmedian(np.asarray(s.dropna()))) if s.dropna().size >= 3 else np.nan),
        ).reset_index()
        day = day.merge(stats, on="industry_l1", how="left")
        regime = _classify_regime(_safe_float(bm_row.get("close")), _safe_float(bm_row.get("ma20")), _safe_float(bm_row.get("ma120")), _safe_float(bm_row.get("slope5")))
        day["regime_bucket"] = regime
        rows.extend(day[["date", "symbol", "industry_l1", "ret_40", "industry_rank_pct", "residual_score_daily", "industry_breadth_level", "industry_top_strength_dispersion", "regime_bucket"]].to_dict(orient="records"))

    daily = pd.DataFrame(rows).sort_values(["symbol", "date"]).reset_index(drop=True)
    daily["industry_top_flag"] = (pd.to_numeric(daily["industry_rank_pct"], errors="coerce") >= 0.7).astype(float)
    grp = daily.groupby("symbol", group_keys=False)
    daily["industry_rank_persistence_5d"] = grp["industry_top_flag"].apply(lambda s: s.rolling(5, min_periods=3).mean())
    daily["industry_rank_persistence_10d"] = grp["industry_top_flag"].apply(lambda s: s.rolling(10, min_periods=5).mean())
    daily["residual_rank_change_5d"] = grp["residual_score_daily"].diff(5)
    daily["residual_rank_change_10d"] = grp["residual_score_daily"].diff(10)
    breadth = daily[["date", "industry_l1", "industry_breadth_level"]].drop_duplicates().sort_values(["industry_l1", "date"])
    breadth["industry_breadth_change_5d"] = breadth.groupby("industry_l1")["industry_breadth_level"].diff(5)
    breadth["industry_breadth_change_10d"] = breadth.groupby("industry_l1")["industry_breadth_level"].diff(10)
    return daily.merge(
        breadth[["date", "industry_l1", "industry_breadth_change_5d", "industry_breadth_change_10d"]],
        on=["date", "industry_l1"],
        how="left",
    )


def _attach_trade_features(
    rt: pd.DataFrame,
    feature_frame: pd.DataFrame,
    daily_cross: pd.DataFrame,
    prev_map: dict[pd.Timestamp, pd.Timestamp],
) -> pd.DataFrame:
    out = rt.copy()
    out["signal_date"] = out["buy_date"].map(prev_map)
    ff = feature_frame.copy()
    ff["date"] = pd.to_datetime(ff["date"]).dt.normalize()
    ff["symbol"] = ff["symbol"].astype(str).str.lower()
    out = out.merge(
        ff[
            [
                "date",
                "symbol",
                "distance_to_ma20_pct",
                "distance_to_ma60_pct",
                "ret_10",
                "ret_20",
                "atr20_pct",
                "atr_expansion_pct",
                "recent_limit_move_count_signal",
            ]
        ].rename(
            columns={
                "date": "signal_date",
                "ret_10": "trailing_10d_return",
                "ret_20": "trailing_20d_return",
                "recent_limit_move_count_signal": "recent_limit_move_count",
            }
        ),
        on=["signal_date", "symbol"],
        how="left",
    )
    out = out.merge(
        ff[["date", "symbol", "gap_pct", "intraday_reversal_pct", "high", "low"]].rename(columns={"date": "buy_date"}),
        on=["buy_date", "symbol"],
        how="left",
    )
    out = out.merge(
        daily_cross[
            [
                "date",
                "symbol",
                "industry_l1",
                "industry_breadth_level",
                "industry_breadth_change_5d",
                "industry_breadth_change_10d",
                "industry_top_strength_dispersion",
                "industry_rank_persistence_5d",
                "industry_rank_persistence_10d",
                "residual_rank_change_5d",
                "residual_rank_change_10d",
                "regime_bucket",
            ]
        ].rename(columns={"date": "signal_date", "regime_bucket": "signal_date_regime"}),
        on=["signal_date", "symbol"],
        how="left",
    )
    price_lookup = ff[["date", "symbol", "high", "low"]].copy()
    price_lookup["date"] = pd.to_datetime(price_lookup["date"]).dt.normalize()
    price_groups = {sym: grp.reset_index(drop=True) for sym, grp in price_lookup.groupby("symbol", sort=False)}
    mfe = []
    mae = []
    for row in out.itertuples(index=False):
        grp = price_groups.get(str(row.symbol))
        if grp is None or grp.empty or not np.isfinite(float(row.buy_fill_price)):
            mfe.append(np.nan)
            mae.append(np.nan)
            continue
        span = grp[(grp["date"] >= pd.Timestamp(row.buy_date).normalize()) & (grp["date"] <= pd.Timestamp(row.sell_date).normalize())]
        if span.empty:
            mfe.append(np.nan)
            mae.append(np.nan)
            continue
        buy_fill = float(row.buy_fill_price)
        mfe.append(float(span["high"].max() / buy_fill - 1.0))
        mae.append(float(span["low"].min() / buy_fill - 1.0))
    out["max_favorable_excursion_pct"] = mfe
    out["max_adverse_excursion_pct"] = mae
    return out


def _phase_1217(buy_date: pd.Timestamp) -> str:
    dt = pd.Timestamp(buy_date).normalize()
    for phase, (start, end) in WINDOWS["12-17"]["subphases"].items():
        if pd.Timestamp(start) <= dt <= pd.Timestamp(end):
            return phase
    return "OTHER"


def _group_compare(df: pd.DataFrame, fields: list[str], q: float) -> pd.DataFrame:
    ret = pd.to_numeric(df["trade_return_pct"], errors="coerce")
    hi = float(ret.quantile(1.0 - q))
    lo = float(ret.quantile(q))
    winners = df[ret >= hi]
    losers = df[ret <= lo]
    rows = []
    for field in fields:
        w = pd.to_numeric(winners[field], errors="coerce")
        l = pd.to_numeric(losers[field], errors="coerce")
        rows.append(
            {
                "field": field,
                "winner_mean": float(w.mean()) if not w.empty else np.nan,
                "winner_median": float(w.median()) if not w.empty else np.nan,
                "loser_mean": float(l.mean()) if not l.empty else np.nan,
                "loser_median": float(l.median()) if not l.empty else np.nan,
                "diff_mean": float(w.mean() - l.mean()) if not w.empty and not l.empty else np.nan,
                "winner_n": int(w.notna().sum()),
                "loser_n": int(l.notna().sum()),
            }
        )
    return pd.DataFrame(rows)


def _bucket_curve(df: pd.DataFrame, field: str) -> pd.DataFrame:
    vals = pd.to_numeric(df[field], errors="coerce")
    work = df.loc[vals.notna(), ["trade_return_pct", field]].copy()
    if len(work) < 20:
        return pd.DataFrame()
    bucket_codes = pd.qcut(pd.to_numeric(work[field], errors="coerce"), 5, labels=False, duplicates="drop")
    if bucket_codes.isna().all():
        return pd.DataFrame()
    work["bucket"] = bucket_codes.map(lambda x: f"Q{int(x) + 1}" if pd.notna(x) else np.nan)
    return work.groupby("bucket", dropna=False).agg(
        trades=("trade_return_pct", "size"),
        avg_return=("trade_return_pct", "mean"),
        median_return=("trade_return_pct", "median"),
        field_mean=(field, "mean"),
    ).reset_index()


def _cross_table(df: pd.DataFrame, x_field: str, y_field: str) -> pd.DataFrame:
    x = pd.to_numeric(df[x_field], errors="coerce")
    y = pd.to_numeric(df[y_field], errors="coerce")
    valid = x.notna() & y.notna()
    if valid.sum() < 20:
        return pd.DataFrame()
    sub = df.loc[valid, ["trade_return_pct"]].copy()
    sub["x_bucket"] = np.where(x[valid] >= float(x[valid].median()), "HIGH", "LOW")
    sub["y_bucket"] = np.where(y[valid] >= float(y[valid].median()), "HIGH", "LOW")
    return sub.groupby(["x_bucket", "y_bucket"], dropna=False).agg(
        trades=("trade_return_pct", "size"),
        avg_return=("trade_return_pct", "mean"),
        median_return=("trade_return_pct", "median"),
    ).reset_index()


def _matched_pairs(df: pd.DataFrame, q: float) -> pd.DataFrame:
    ret = pd.to_numeric(df["trade_return_pct"], errors="coerce")
    hi = float(ret.quantile(1.0 - q))
    lo = float(ret.quantile(q))
    winners = df[ret >= hi].copy().sort_values("buy_date")
    losers = df[ret <= lo].copy()
    used: set[int] = set()
    rows = []
    for _, win in winners.iterrows():
        cand = losers[
            (losers["industry_l1"] == win["industry_l1"])
            & (~losers.index.isin(used))
            & (abs((pd.to_datetime(losers["buy_date"]) - pd.Timestamp(win["buy_date"])).dt.days) <= 90)
            & (abs(pd.to_numeric(losers["holding_days"], errors="coerce") - float(win["holding_days"])) <= 5)
        ].copy()
        if cand.empty:
            continue
        cand["distance"] = abs((pd.to_datetime(cand["buy_date"]) - pd.Timestamp(win["buy_date"])).dt.days) + abs(pd.to_numeric(cand["holding_days"], errors="coerce") - float(win["holding_days"]))
        loser_idx = int(cand.sort_values(["distance", "buy_date"]).index[0])
        used.add(loser_idx)
        lose = losers.loc[loser_idx]
        rows.append(
            {
                "industry_l1": str(win.get("industry_l1", "")),
                "winner_return": float(win["trade_return_pct"]),
                "loser_return": float(lose["trade_return_pct"]),
                "delta_industry_relative_score": _safe_float(win["industry_relative_score"]) - _safe_float(lose["industry_relative_score"]),
                "delta_breakout_distance_pct": _safe_float(win["breakout_distance_pct"]) - _safe_float(lose["breakout_distance_pct"]),
                "delta_atr_expansion_pct": _safe_float(win["atr_expansion_pct"]) - _safe_float(lose["atr_expansion_pct"]),
                "delta_industry_rank_persistence_10d": _safe_float(win["industry_rank_persistence_10d"]) - _safe_float(lose["industry_rank_persistence_10d"]),
            }
        )
    return pd.DataFrame(rows)


def _loss_modes(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for window_label, grp in df.groupby("window_label", sort=False):
        ret = pd.to_numeric(grp["trade_return_pct"], errors="coerce")
        losers = grp[ret <= float(ret.quantile(0.2))].copy()
        if losers.empty:
            continue
        strength_cut = float(pd.to_numeric(grp["industry_relative_score"], errors="coerce").median())
        late_cut = float(pd.to_numeric(grp["breakout_distance_pct"], errors="coerce").quantile(0.75))
        vol_cut = float(pd.to_numeric(grp["atr_expansion_pct"], errors="coerce").quantile(0.75))
        breadth_cut = float(pd.to_numeric(grp["industry_breadth_change_10d"], errors="coerce").quantile(0.75))
        t10_cut = float(pd.to_numeric(grp["trailing_10d_return"], errors="coerce").quantile(0.75))
        gap_cut = float(pd.to_numeric(grp["gap_pct"], errors="coerce").quantile(0.75))
        rev_cut = float(pd.to_numeric(grp["intraday_reversal_pct"], errors="coerce").quantile(0.75))
        for row in losers.itertuples(index=False):
            strength = _safe_float(getattr(row, "industry_relative_score", np.nan))
            late = _safe_float(getattr(row, "breakout_distance_pct", np.nan)) >= late_cut or _safe_float(getattr(row, "trailing_10d_return", np.nan)) >= t10_cut
            crowded = _safe_float(getattr(row, "atr_expansion_pct", np.nan)) >= vol_cut or _safe_float(getattr(row, "gap_pct", np.nan)) >= gap_cut or _safe_float(getattr(row, "intraday_reversal_pct", np.nan)) >= rev_cut
            breadth_tail = _safe_float(getattr(row, "industry_breadth_change_10d", np.nan)) >= breadth_cut
            if np.isfinite(strength) and strength < strength_cut:
                mode = "D"
            elif late:
                mode = "A"
            elif crowded:
                mode = "B"
            elif breadth_tail:
                mode = "C"
            else:
                mode = "E"
            rows.append({"window_label": window_label, "mode": mode})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.groupby(["window_label", "mode"], as_index=False).size().rename(columns={"size": "trades"}).assign(
        share=lambda x: x["trades"] / x.groupby("window_label")["trades"].transform("sum")
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(OUT))
    args = parser.parse_args()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    provider = _provider()
    frames = []
    min_buy = None
    max_sell = None
    for window_label, meta in WINDOWS.items():
        rt = _load_roundtrips(meta["exp_id"], window_label)
        frames.append(rt)
        if not rt.empty:
            min_buy = pd.Timestamp(rt["buy_date"].min()).normalize() if min_buy is None else min(min_buy, pd.Timestamp(rt["buy_date"].min()).normalize())
            max_sell = pd.Timestamp(rt["sell_date"].max()).normalize() if max_sell is None else max(max_sell, pd.Timestamp(rt["sell_date"].max()).normalize())
    roundtrips = pd.concat(frames, ignore_index=True)
    if roundtrips.empty or min_buy is None or max_sell is None:
        raise RuntimeError("no roundtrips found")

    start_date = (min_buy - pd.Timedelta(days=160)).date()
    end_date = max_sell.date()
    calendar = provider.load_trading_calendar_cn(start_date, end_date)
    prev_map, _ = _calendar_maps(calendar)
    index_hist = provider.load_index_constituent_history("000906.SH", start_date, end_date)
    universe_symbols = sorted(index_hist["symbol"].astype(str).str.lower().unique().tolist())
    raw_history = provider.load_ohlcv_daily(universe_symbols, start_date, end_date, source="v10_1_pnl_analysis")
    feature_frame = _prepare_feature_frame(raw_history)
    benchmark = provider.load_benchmark_daily("000300.SH", start_date, end_date)
    industry_map = provider.load_industry_mapping(universe_symbols)
    industry_history = provider.load_industry_history(universe_symbols, start_date, end_date)
    sec_df = provider.load_sector_indices(start_date, end_date)
    sector_data = {str(code).upper(): grp.reset_index(drop=True) for code, grp in sec_df.groupby("index_code")} if not sec_df.empty else {}
    daily_cross = _build_daily_cross(feature_frame, benchmark, index_hist, industry_map, industry_history, sector_data, calendar.normalize(), universe_symbols)
    tagged = _attach_trade_features(roundtrips, feature_frame, daily_cross, prev_map)
    tagged["phase_1217"] = tagged["buy_date"].map(_phase_1217)
    fields = [
        "industry_relative_score", "residual_score", "benchmark_relative_component", "sector_relative_component",
        "breakout_distance_pct", "distance_to_ma20_pct", "distance_to_ma60_pct", "trailing_10d_return", "trailing_20d_return",
        "atr20_pct", "atr_expansion_pct", "gap_pct", "intraday_reversal_pct", "recent_limit_move_count",
        "industry_breadth_level", "industry_breadth_change_5d", "industry_breadth_change_10d", "industry_top_strength_dispersion",
        "industry_rank_persistence_5d", "industry_rank_persistence_10d", "residual_rank_change_5d", "residual_rank_change_10d",
    ]

    compare_rows = []
    for label, grp in tagged.groupby("window_label", sort=False):
        c20 = _group_compare(grp, fields, 0.2); c20["window_label"] = label; c20["group_label"] = "top20_bottom20"; compare_rows.append(c20)
        c10 = _group_compare(grp, fields, 0.1); c10["window_label"] = label; c10["group_label"] = "top10_bottom10"; compare_rows.append(c10)
    for phase in ["2012-2013", "2014-2015", "2015-2017"]:
        grp = tagged[(tagged["window_label"] == "12-17") & (tagged["phase_1217"] == phase)]
        if len(grp) >= 10:
            c20 = _group_compare(grp, fields, 0.2); c20["window_label"] = f"12-17/{phase}"; c20["group_label"] = "top20_bottom20"; compare_rows.append(c20)
    comparisons = pd.concat(compare_rows, ignore_index=True) if compare_rows else pd.DataFrame()

    bucket_rows = []
    for window_label, grp in tagged.groupby("window_label", sort=False):
        for field in ["breakout_distance_pct", "atr_expansion_pct", "industry_breadth_level", "industry_breadth_change_10d", "industry_rank_persistence_10d"]:
            cur = _bucket_curve(grp, field)
            if not cur.empty:
                cur["window_label"] = window_label
                cur["field"] = field
                bucket_rows.append(cur)
    buckets = pd.concat(bucket_rows, ignore_index=True) if bucket_rows else pd.DataFrame()

    cross_rows = []
    for window_label, grp in tagged.groupby("window_label", sort=False):
        for x_field, y_field in [
            ("industry_relative_score", "breakout_distance_pct"),
            ("industry_relative_score", "atr_expansion_pct"),
            ("industry_relative_score", "industry_breadth_change_10d"),
            ("industry_relative_score", "industry_rank_persistence_10d"),
        ]:
            cur = _cross_table(grp, x_field, y_field)
            if not cur.empty:
                cur["window_label"] = window_label
                cur["x_field"] = x_field
                cur["y_field"] = y_field
                cross_rows.append(cur)
    crosses = pd.concat(cross_rows, ignore_index=True) if cross_rows else pd.DataFrame()

    matched20_rows = []
    matched10_rows = []
    for label, grp in tagged.groupby("window_label", sort=False):
        cur20 = _matched_pairs(grp, 0.2)
        if not cur20.empty:
            cur20["window_label"] = label
            matched20_rows.append(cur20)
        cur10 = _matched_pairs(grp, 0.1)
        if not cur10.empty:
            cur10["window_label"] = label
            matched10_rows.append(cur10)
    matched20 = pd.concat(matched20_rows, ignore_index=True) if matched20_rows else pd.DataFrame()
    matched10 = pd.concat(matched10_rows, ignore_index=True) if matched10_rows else pd.DataFrame()
    loss_modes = _loss_modes(tagged)

    tagged.to_csv(out_dir / "tagged_roundtrips.csv", index=False, encoding="utf-8-sig")
    comparisons.to_csv(out_dir / "winner_loser_comparison.csv", index=False, encoding="utf-8-sig")
    buckets.to_csv(out_dir / "bucket_curves.csv", index=False, encoding="utf-8-sig")
    crosses.to_csv(out_dir / "cross_tables.csv", index=False, encoding="utf-8-sig")
    matched20.to_csv(out_dir / "matched_top20.csv", index=False, encoding="utf-8-sig")
    matched10.to_csv(out_dir / "matched_top10.csv", index=False, encoding="utf-8-sig")
    loss_modes.to_csv(out_dir / "loss_modes.csv", index=False, encoding="utf-8-sig")
    summary = {
        "artifacts": {
            "tagged_roundtrips_csv": str(out_dir / "tagged_roundtrips.csv"),
            "winner_loser_comparison_csv": str(out_dir / "winner_loser_comparison.csv"),
            "bucket_curves_csv": str(out_dir / "bucket_curves.csv"),
            "cross_tables_csv": str(out_dir / "cross_tables.csv"),
            "matched_top20_csv": str(out_dir / "matched_top20.csv"),
            "matched_top10_csv": str(out_dir / "matched_top10.csv"),
            "loss_modes_csv": str(out_dir / "loss_modes.csv"),
        },
        "facts": {
            "roundtrips_total": int(len(tagged)),
            "roundtrips_1217": int((tagged["window_label"] == "12-17").sum()),
            "roundtrips_1626": int((tagged["window_label"] == "16-26").sum()),
            "matched_pairs_top20_1217": int((matched20["window_label"] == "12-17").sum()) if not matched20.empty else 0,
            "matched_pairs_top20_1626": int((matched20["window_label"] == "16-26").sum()) if not matched20.empty else 0,
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
