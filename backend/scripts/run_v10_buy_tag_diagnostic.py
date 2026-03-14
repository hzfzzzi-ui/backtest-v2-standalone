"""V10 现有买点四标签纯诊断。

不改交易逻辑，只对既有 BUY 交易补 4 组标签：
1. CTO / overnight pressure
2. near-limit / recent-limit-hit
3. industry leader bucket / factor leader bucket
4. institutionalization proxy bucket

输出：
- summary_by_bucket.csv
- tagged_roundtrips.csv
- diagnosis_summary.json
"""
from __future__ import annotations

import io
import json
import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import numpy as np
import pandas as pd

from backend.core.config.loader import load_config
from backend.core.data.pg_provider import PostgresDataProvider
from backend.core.data.price_adjust import apply_price_adjustment
from backend.core.universe.ingest_universe import SW_L1_INDEX_MAP

try:
    from backend.core.data.cached_provider import CachedDataProvider
except Exception:
    CachedDataProvider = None


EXPERIMENTS: dict[str, dict[str, str]] = {
    "0717": {
        "window_label": "07-17",
        "exp_id": "exp_20260313_035110024_32ed",
    },
    "1626": {
        "window_label": "16-26",
        "exp_id": "exp_20260312_034933994_f811",
    },
}

OUTPUT_DIR = _root / "outputs" / "ops" / "v10_buy_tag_diagnostic_20260313"
LOOKBACK_DAYS = 40


@dataclass(frozen=True)
class TagSummary:
    trades: int
    win_rate: float
    avg_return: float
    median_return: float
    avg_pnl: float
    total_pnl: float


def _build_provider():
    base_path = _root / "backend" / "configs" / "pams_cn_pg.json"
    cfg_obj, _ = load_config(str(base_path))
    pg = PostgresDataProvider(
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
        data_source=cfg_obj.data_source,
        schema_mapping=cfg_obj.schema_mapping,
        rules_path=base_path.parent / "instrument_rules_cn.csv",
    )
    if CachedDataProvider is not None:
        return CachedDataProvider(pg)
    return pg


def _load_buy_and_roundtrip_rows(exp_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    trades = pd.read_csv(exp_path / "portfolio_trades.csv", parse_dates=["date", "entry_date"])
    trades["symbol"] = trades["symbol"].astype(str).str.lower()
    buys = trades[trades["side"] == "BUY"].copy().sort_values(["date", "symbol"]).reset_index(drop=True)
    sells = trades[trades["side"] == "SELL"].copy().sort_values(["date", "symbol"]).reset_index(drop=True)

    buy_meta: list[dict[str, object]] = []
    for row in buys.itertuples(index=False):
        meta = {}
        try:
            meta = json.loads(str(getattr(row, "meta_json", "{}")))
        except Exception:
            meta = {}
        buy_meta.append(meta)
    meta_df = pd.DataFrame(buy_meta)
    if not meta_df.empty:
        buys = pd.concat([buys.reset_index(drop=True), meta_df.reset_index(drop=True)], axis=1)

    fifo: dict[str, deque] = defaultdict(deque)
    for row in buys.itertuples(index=False):
        fifo[str(row.symbol)].append(row)

    roundtrips: list[dict[str, object]] = []
    for sell in sells.itertuples(index=False):
        sym = str(sell.symbol)
        if not fifo.get(sym):
            continue
        buy = fifo[sym].popleft()
        buy_fill = float(getattr(buy, "fill_price", np.nan) or np.nan)
        sell_fill = float(getattr(sell, "fill_price", np.nan) or np.nan)
        qty = int(getattr(sell, "qty", 0) or 0)
        if not np.isfinite(buy_fill) or not np.isfinite(sell_fill) or qty <= 0:
            continue
        pnl = (sell_fill - buy_fill) * qty
        pnl_pct = sell_fill / buy_fill - 1.0 if buy_fill > 0 else np.nan
        hold_days = int((sell.date - buy.date).days)
        roundtrips.append(
            {
                "symbol": sym,
                "buy_date": pd.Timestamp(buy.date).normalize(),
                "sell_date": pd.Timestamp(sell.date).normalize(),
                "buy_fill_price": buy_fill,
                "sell_fill_price": sell_fill,
                "qty": qty,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "hold_days": hold_days,
                "sell_reason": str(getattr(sell, "reason_code", "")),
            }
        )

    buys["buy_date"] = pd.to_datetime(buys["date"]).dt.normalize()
    return buys, pd.DataFrame(roundtrips)


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out["symbol"] = out["symbol"].astype(str).str.lower()
    numeric_cols = [
        "open",
        "high",
        "low",
        "close",
        "amount",
        "circ_mv",
        "turnover_rate",
        "turnover_rate_f",
        "limit_up",
        "limit_down",
    ]
    for col in numeric_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.sort_values(["symbol", "date"]).reset_index(drop=True)


def _tag_cto_bucket(series: pd.Series) -> pd.Series:
    vals = pd.to_numeric(series, errors="coerce")
    return pd.Series(
        np.select(
            [
                vals < -0.01,
                vals <= 0.01,
                vals <= 0.03,
                vals > 0.03,
            ],
            [
                "GAP_DOWN",
                "FLAT",
                "MILD_GAP_UP",
                "HEAVY_GAP_UP",
            ],
            default="UNKNOWN",
        ),
        index=series.index,
    )


def _tag_limit_bucket(signal_near_limit: pd.Series, recent_limit_hit: pd.Series) -> pd.Series:
    near = signal_near_limit.fillna(False).astype(bool)
    recent = recent_limit_hit.fillna(False).astype(bool)
    return pd.Series(
        np.select(
            [
                near & recent,
                near & ~recent,
                ~near & recent,
                ~near & ~recent,
            ],
            [
                "BOTH",
                "SIGNAL_NEAR_LIMIT_ONLY",
                "RECENT_LIMIT_HIT_ONLY",
                "NONE",
            ],
            default="UNKNOWN",
        ),
        index=signal_near_limit.index,
    )


def _bucket_three_way_from_rank(rank_pct: pd.Series) -> pd.Series:
    vals = pd.to_numeric(rank_pct, errors="coerce")
    return pd.Series(
        np.select(
            [
                vals < (1.0 / 3.0),
                vals < (2.0 / 3.0),
                vals <= 1.0,
            ],
            [
                "LAGGARD",
                "MID",
                "LEADER",
            ],
            default="UNKNOWN",
        ),
        index=rank_pct.index,
    )


def _safe_rank_pct(series: pd.Series, ascending: bool = True) -> pd.Series:
    vals = pd.to_numeric(series, errors="coerce")
    return vals.rank(method="average", pct=True, ascending=ascending)


def _build_calendar_maps(calendar_idx: pd.DatetimeIndex) -> tuple[dict[pd.Timestamp, pd.Timestamp], dict[pd.Timestamp, pd.Timestamp]]:
    dates = [pd.Timestamp(d).normalize() for d in calendar_idx]
    prev_map: dict[pd.Timestamp, pd.Timestamp] = {}
    next_map: dict[pd.Timestamp, pd.Timestamp] = {}
    for i, dt in enumerate(dates):
        if i > 0:
            prev_map[dt] = dates[i - 1]
        if i < len(dates) - 1:
            next_map[dt] = dates[i + 1]
    return prev_map, next_map


def _active_symbols_by_date(history: pd.DataFrame, signal_dates: list[pd.Timestamp]) -> dict[pd.Timestamp, set[str]]:
    hist = history.copy()
    hist["start_date"] = pd.to_datetime(hist["start_date"]).dt.normalize()
    hist["end_date"] = pd.to_datetime(hist["end_date"], errors="coerce").dt.normalize()
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    result: dict[pd.Timestamp, set[str]] = {}
    for dt in signal_dates:
        mask = (hist["start_date"] <= dt) & (hist["end_date"].isna() | (hist["end_date"] > dt))
        result[dt] = set(hist.loc[mask, "symbol"].astype(str).tolist())
    return result


def _industry_map_by_date(industry_history: pd.DataFrame, signal_dates: list[pd.Timestamp]) -> dict[pd.Timestamp, dict[str, str]]:
    hist = industry_history.copy()
    hist["start_date"] = pd.to_datetime(hist["start_date"]).dt.normalize()
    hist["end_date"] = pd.to_datetime(hist["end_date"], errors="coerce").dt.normalize()
    hist["ts_code"] = hist["ts_code"].astype(str).str.lower()
    result: dict[pd.Timestamp, dict[str, str]] = {}
    for dt in signal_dates:
        mask = (hist["start_date"] <= dt) & (hist["end_date"].isna() | (hist["end_date"] >= dt))
        subset = hist.loc[mask, ["ts_code", "start_date", "industry_l1"]].sort_values(["ts_code", "start_date"])
        result[dt] = (
            subset.drop_duplicates(subset=["ts_code"], keep="last")
            .set_index("ts_code")["industry_l1"]
            .astype(str)
            .to_dict()
        )
    return result


def _prepare_feature_frame(raw: pd.DataFrame) -> pd.DataFrame:
    raw = _normalize_ohlcv(raw)
    by_symbol = raw.groupby("symbol", group_keys=False)

    raw["amount20"] = by_symbol["amount"].apply(lambda s: s.rolling(20, min_periods=15).mean())
    turnover_proxy = raw["turnover_rate_f"]
    if "turnover_rate" in raw.columns:
        turnover_proxy = turnover_proxy.fillna(raw["turnover_rate"])
    raw["turnover_rate_proxy"] = pd.to_numeric(turnover_proxy, errors="coerce")
    raw["inst_mcap_proxy"] = np.where(
        raw["circ_mv"].notna(),
        raw["circ_mv"],
        np.where(raw["turnover_rate_proxy"] > 1e-8, raw["amount"] * 100.0 / raw["turnover_rate_proxy"], np.nan),
    )
    raw["near_limit_up"] = (
        raw["limit_up"].notna()
        & (
            ((raw["high"] / raw["limit_up"]) >= 0.995)
            | ((raw["close"] / raw["limit_up"]) >= 0.985)
        )
    )
    raw["limit_hit_up"] = raw["limit_up"].notna() & (
        ((raw["high"] / raw["limit_up"]) >= 0.999)
        | ((raw["close"] / raw["limit_up"]) >= 0.999)
    )
    raw["signal_near_limit_up"] = by_symbol["near_limit_up"].shift(1)
    raw["recent_limit_hit_3d_exec"] = (
        by_symbol["limit_hit_up"].apply(lambda s: s.shift(1).rolling(3, min_periods=1).max()).fillna(0.0) > 0.0
    )
    raw["cto_raw"] = raw["open"] / by_symbol["close"].shift(1) - 1.0
    raw["circ_mv_signal"] = by_symbol["inst_mcap_proxy"].shift(1)
    raw["amount20_signal"] = by_symbol["amount20"].shift(1)

    adj = apply_price_adjustment(raw[["date", "symbol", "open", "high", "low", "close", "adj_factor"]].copy(), "hfq")
    adj = adj.sort_values(["symbol", "date"]).reset_index(drop=True)
    adj_group = adj.groupby("symbol", group_keys=False)
    adj["adj_ret_40"] = adj_group["close"].shift(0) / adj_group["close"].shift(LOOKBACK_DAYS) - 1.0
    adj["adj_daily_ret"] = adj_group["close"].pct_change()
    adj["vol20"] = adj_group["adj_daily_ret"].apply(lambda s: s.rolling(20, min_periods=15).std())
    adj["adj_ret_40_signal"] = adj_group["adj_ret_40"].shift(1)
    adj["vol20_signal"] = adj_group["vol20"].shift(1)

    merged = raw.merge(
        adj[["date", "symbol", "adj_ret_40_signal", "vol20_signal"]],
        on=["date", "symbol"],
        how="left",
    )
    return merged


def _assign_cross_section_buckets(
    *,
    feature_frame: pd.DataFrame,
    sector_indices: pd.DataFrame,
    active_by_date: dict[pd.Timestamp, set[str]],
    industry_map_by_date: dict[pd.Timestamp, dict[str, str]],
    signal_dates: list[pd.Timestamp],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ff = feature_frame.copy()
    ff["date"] = pd.to_datetime(ff["date"]).dt.normalize()
    ff["symbol"] = ff["symbol"].astype(str).str.lower()
    ff = ff.set_index(["date", "symbol"]).sort_index()

    sector = sector_indices.copy()
    sector["trade_date"] = pd.to_datetime(sector["trade_date"]).dt.normalize()
    sector["index_code"] = sector["index_code"].astype(str)
    for col in ("open", "high", "low", "close"):
        if col in sector.columns:
            sector[col] = pd.to_numeric(sector[col], errors="coerce")
    sector = sector.sort_values(["index_code", "trade_date"]).reset_index(drop=True)
    sector["sector_ret_40"] = sector.groupby("index_code")["close"].transform(
        lambda s: s / s.shift(LOOKBACK_DAYS) - 1.0
    )
    sector_ret_lookup = sector.set_index(["trade_date", "index_code"])["sector_ret_40"]

    tag_rows: list[dict[str, object]] = []
    style_rows: list[dict[str, object]] = []
    name_to_code = dict(SW_L1_INDEX_MAP)

    for dt in signal_dates:
        active = active_by_date.get(dt, set())
        if not active:
            continue
        try:
            day_rows = ff.loc[dt]
        except KeyError:
            continue
        if isinstance(day_rows, pd.Series):
            day_rows = day_rows.to_frame().T
        day_rows = day_rows.loc[day_rows.index.intersection(active)].copy()
        if day_rows.empty:
            continue

        day_rows["symbol"] = day_rows.index.astype(str)
        industry_map = industry_map_by_date.get(dt, {})
        day_rows["industry_l1"] = day_rows["symbol"].map(industry_map)
        day_rows["sector_code"] = day_rows["industry_l1"].map(name_to_code)

        sector_codes = sorted({str(v) for v in day_rows["sector_code"].dropna().astype(str).tolist()})
        sector_bucket_map: dict[str, str] = {}
        if sector_codes:
            sector_rows = []
            for code in sector_codes:
                try:
                    val = float(sector_ret_lookup.loc[(dt, code)])
                except Exception:
                    continue
                if np.isfinite(val):
                    sector_rows.append({"sector_code": code, "sector_ret_40": val})
            sector_df = pd.DataFrame(sector_rows)
            if not sector_df.empty:
                sector_df["rank_pct"] = _safe_rank_pct(sector_df["sector_ret_40"], ascending=True)
                sector_df["industry_leader_bucket"] = _bucket_three_way_from_rank(sector_df["rank_pct"])
                sector_bucket_map = sector_df.set_index("sector_code")["industry_leader_bucket"].astype(str).to_dict()

        valid_style = day_rows.dropna(subset=["circ_mv_signal", "amount20_signal", "vol20_signal", "adj_ret_40_signal"]).copy()
        style_bucket_map: dict[str, str] = {}
        if not valid_style.empty:
            size_cut = float(valid_style["circ_mv_signal"].median())
            liq_cut = float(valid_style["amount20_signal"].median())
            vol_cut = float(valid_style["vol20_signal"].median())
            valid_style["size_side"] = np.where(valid_style["circ_mv_signal"] >= size_cut, "BIG", "SMALL")
            valid_style["liq_side"] = np.where(valid_style["amount20_signal"] >= liq_cut, "LIQ", "ILLQ")
            valid_style["vol_side"] = np.where(valid_style["vol20_signal"] <= vol_cut, "LOWVOL", "HIGHVOL")
            valid_style["style_bucket"] = (
                valid_style["size_side"] + "_" + valid_style["liq_side"] + "_" + valid_style["vol_side"]
            )
            style_perf = (
                valid_style.groupby("style_bucket", dropna=False)["adj_ret_40_signal"]
                .mean()
                .reset_index(name="style_ret_40")
            )
            if not style_perf.empty:
                style_perf["rank_pct"] = _safe_rank_pct(style_perf["style_ret_40"], ascending=True)
                style_perf["factor_leader_bucket"] = _bucket_three_way_from_rank(style_perf["rank_pct"])
                style_bucket_map = (
                    style_perf.set_index("style_bucket")["factor_leader_bucket"].astype(str).to_dict()
                )
                style_rows.extend(
                    [
                        {
                            "signal_date": dt,
                            "style_bucket": r["style_bucket"],
                            "style_ret_40": float(r["style_ret_40"]),
                            "factor_leader_bucket": str(r["factor_leader_bucket"]),
                        }
                        for r in style_perf.to_dict(orient="records")
                    ]
                )

            valid_style["inst_rank_size"] = _safe_rank_pct(valid_style["circ_mv_signal"], ascending=True)
            valid_style["inst_rank_liq"] = _safe_rank_pct(valid_style["amount20_signal"], ascending=True)
            valid_style["inst_proxy_score"] = 0.5 * valid_style["inst_rank_size"] + 0.5 * valid_style["inst_rank_liq"]
            valid_style["institutionalization_proxy_bucket"] = _bucket_three_way_from_rank(valid_style["inst_proxy_score"])
            inst_map = (
                valid_style.set_index("symbol")["institutionalization_proxy_bucket"].astype(str).to_dict()
            )
            style_name_map = valid_style.set_index("symbol")["style_bucket"].astype(str).to_dict()
        else:
            inst_map = {}
            style_name_map = {}

        for row in day_rows.itertuples():
            sym = str(row.symbol)
            tag_rows.append(
                {
                    "signal_date": dt,
                    "symbol": sym,
                    "industry_l1": industry_map.get(sym),
                    "sector_code": getattr(row, "sector_code", None),
                    "industry_leader_bucket": sector_bucket_map.get(getattr(row, "sector_code", None), "UNKNOWN"),
                    "style_bucket": style_name_map.get(sym, "UNKNOWN"),
                    "factor_leader_bucket": style_bucket_map.get(style_name_map.get(sym, ""), "UNKNOWN"),
                    "institutionalization_proxy_bucket": inst_map.get(sym, "UNKNOWN"),
                }
            )

    return pd.DataFrame(tag_rows), pd.DataFrame(style_rows)


def _summarize_by_bucket(df: pd.DataFrame, label_col: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (window_label, bucket), grp in df.groupby(["window_label", label_col], dropna=False):
        g = grp.copy()
        n = int(len(g))
        win_rate = float((g["pnl_pct"] > 0).mean()) if n > 0 else np.nan
        rows.append(
            {
                "window_label": window_label,
                "label_group": label_col,
                "bucket": str(bucket),
                "trades": n,
                "win_rate": win_rate,
                "avg_return": float(g["pnl_pct"].mean()) if n > 0 else np.nan,
                "median_return": float(g["pnl_pct"].median()) if n > 0 else np.nan,
                "avg_pnl": float(g["pnl"].mean()) if n > 0 else np.nan,
                "total_pnl": float(g["pnl"].sum()) if n > 0 else np.nan,
                "buy_share": float(n / max(len(df[df["window_label"] == window_label]), 1)),
            }
        )
    return pd.DataFrame(rows).sort_values(["label_group", "window_label", "trades"], ascending=[True, True, False])


def _top_bucket_deltas(summary: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    for label_group, grp in summary.groupby("label_group"):
        pivot = grp.pivot_table(index="bucket", columns="window_label", values="avg_return", aggfunc="first")
        if not {"07-17", "16-26"}.issubset(set(pivot.columns)):
            continue
        pivot = pivot.dropna(subset=["07-17", "16-26"]).copy()
        if pivot.empty:
            continue
        pivot["delta_1626_minus_0717"] = pivot["16-26"] - pivot["07-17"]
        top = pivot.sort_values("delta_1626_minus_0717", ascending=False).head(3).reset_index()
        result[str(label_group)] = [
            {
                "bucket": str(r["bucket"]),
                "avg_return_0717": float(r["07-17"]),
                "avg_return_1626": float(r["16-26"]),
                "delta_1626_minus_0717": float(r["delta_1626_minus_0717"]),
            }
            for r in top.to_dict(orient="records")
        ]
    return result


def main() -> None:
    t0 = time.perf_counter()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    provider = _build_provider()

    exp_rows: list[pd.DataFrame] = []
    roundtrip_rows: list[pd.DataFrame] = []
    min_date: pd.Timestamp | None = None
    max_date: pd.Timestamp | None = None
    for key, meta in EXPERIMENTS.items():
        exp_path = _root / "outputs" / "experiments" / meta["exp_id"]
        buys, roundtrips = _load_buy_and_roundtrip_rows(exp_path)
        if buys.empty:
            continue
        buys["window_key"] = key
        buys["window_label"] = meta["window_label"]
        roundtrips["window_key"] = key
        roundtrips["window_label"] = meta["window_label"]
        exp_rows.append(buys)
        roundtrip_rows.append(roundtrips)
        dt_min = buys["buy_date"].min()
        dt_max = buys["buy_date"].max()
        min_date = dt_min if min_date is None else min(min_date, dt_min)
        max_date = dt_max if max_date is None else max(max_date, dt_max)

    if not exp_rows:
        raise RuntimeError("No BUY rows found in target experiments")

    buys_all = pd.concat(exp_rows, ignore_index=True)
    roundtrips_all = pd.concat(roundtrip_rows, ignore_index=True)

    if min_date is None or max_date is None:
        raise RuntimeError("Unable to determine experiment date range")

    start_date = (min_date - pd.Timedelta(days=120)).date()
    end_date = max_date.date()

    calendar = provider.load_trading_calendar_cn(start_date, end_date)
    prev_map, _ = _build_calendar_maps(calendar)
    buys_all["signal_date"] = buys_all["buy_date"].map(prev_map)
    buys_all = buys_all.dropna(subset=["signal_date"]).copy()
    buys_all["signal_date"] = pd.to_datetime(buys_all["signal_date"]).dt.normalize()

    index_hist = provider.load_index_constituent_history("000906.SH", start_date, end_date)
    universe_symbols = sorted(index_hist["symbol"].astype(str).str.lower().unique().tolist())
    raw_history = provider.load_ohlcv_daily(universe_symbols, start_date, end_date, source="buy_tag_diagnostic")
    feature_frame = _prepare_feature_frame(raw_history)

    industry_history = provider.load_industry_history(universe_symbols, start_date, end_date)
    sector_indices = provider.load_sector_indices(start_date, end_date)
    signal_dates = sorted(pd.to_datetime(buys_all["signal_date"]).dt.normalize().unique().tolist())
    active_by_date = _active_symbols_by_date(index_hist, signal_dates)
    industry_map_by_date = _industry_map_by_date(industry_history, signal_dates)
    cross_section_tags, style_performance = _assign_cross_section_buckets(
        feature_frame=feature_frame,
        sector_indices=sector_indices,
        active_by_date=active_by_date,
        industry_map_by_date=industry_map_by_date,
        signal_dates=signal_dates,
    )

    exec_features = feature_frame[
        [
            "date",
            "symbol",
            "cto_raw",
            "signal_near_limit_up",
            "recent_limit_hit_3d_exec",
            "circ_mv_signal",
            "amount20_signal",
            "adj_ret_40_signal",
            "vol20_signal",
        ]
    ].rename(columns={"date": "buy_date"})

    tagged = buys_all.merge(exec_features, on=["buy_date", "symbol"], how="left")
    tagged = tagged.merge(cross_section_tags, on=["signal_date", "symbol"], how="left")
    tagged["cto_bucket"] = _tag_cto_bucket(tagged["cto_raw"])
    tagged["near_limit_bucket"] = _tag_limit_bucket(
        tagged["signal_near_limit_up"],
        tagged["recent_limit_hit_3d_exec"],
    )
    tagged["industry_leader_bucket"] = tagged["industry_leader_bucket"].fillna("UNKNOWN")
    tagged["factor_leader_bucket"] = tagged["factor_leader_bucket"].fillna("UNKNOWN")
    tagged["institutionalization_proxy_bucket"] = tagged["institutionalization_proxy_bucket"].fillna("UNKNOWN")

    tagged_roundtrips = roundtrips_all.merge(
        tagged[
            [
                "window_label",
                "window_key",
                "symbol",
                "buy_date",
                "signal_date",
                "cto_raw",
                "cto_bucket",
                "near_limit_bucket",
                "industry_l1",
                "industry_leader_bucket",
                "style_bucket",
                "factor_leader_bucket",
                "institutionalization_proxy_bucket",
                "circ_mv_signal",
                "amount20_signal",
                "adj_ret_40_signal",
                "vol20_signal",
            ]
        ],
        on=["window_label", "window_key", "symbol", "buy_date"],
        how="left",
    )

    summary_frames = []
    for col in [
        "cto_bucket",
        "near_limit_bucket",
        "industry_leader_bucket",
        "factor_leader_bucket",
        "institutionalization_proxy_bucket",
    ]:
        summary_frames.append(_summarize_by_bucket(tagged_roundtrips, col))
    summary_all = pd.concat(summary_frames, ignore_index=True)

    diagnosis_summary = {
        "artifacts": {
            "summary_by_bucket_csv": str(OUTPUT_DIR / "summary_by_bucket.csv"),
            "tagged_roundtrips_csv": str(OUTPUT_DIR / "tagged_roundtrips.csv"),
            "style_performance_csv": str(OUTPUT_DIR / "style_performance_by_signal_date.csv"),
        },
        "facts": {
            "buy_count_0717": int((tagged["window_label"] == "07-17").sum()),
            "buy_count_1626": int((tagged["window_label"] == "16-26").sum()),
            "roundtrip_count_0717": int((tagged_roundtrips["window_label"] == "07-17").sum()),
            "roundtrip_count_1626": int((tagged_roundtrips["window_label"] == "16-26").sum()),
            "top_bucket_deltas": _top_bucket_deltas(summary_all),
        },
        "run_meta": {
            "elapsed_seconds": round(time.perf_counter() - t0, 3),
            "output_dir": str(OUTPUT_DIR),
        },
    }

    summary_all.to_csv(OUTPUT_DIR / "summary_by_bucket.csv", index=False, encoding="utf-8-sig")
    tagged_roundtrips.to_csv(OUTPUT_DIR / "tagged_roundtrips.csv", index=False, encoding="utf-8-sig")
    style_performance.to_csv(OUTPUT_DIR / "style_performance_by_signal_date.csv", index=False, encoding="utf-8-sig")
    (OUTPUT_DIR / "diagnosis_summary.json").write_text(
        json.dumps(diagnosis_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(diagnosis_summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
