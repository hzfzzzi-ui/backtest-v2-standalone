from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from psycopg.rows import dict_row

from backend.api.shared.json_utils import sanitize_json
from backend.core.data import pg_env
from backend.research.csi1000_negative_attribution import normalize_symbol


DEFAULT_EXP_ID = "exp_20260516_224942916_8830"
DEFAULT_OUTPUT_DIR = Path("outputs/analysis/v4_liquidity_turnover_crowding_shadow_20260517")
DEFAULT_QUALITY_PATH = Path(
    "outputs/studies/cn_stock/v4_fundamental_quality_ranking_ab_v1/snapshots/fundamental_quality_daily_snapshot.csv"
)
STUDY_ID = "cn_stock/v4_liquidity_turnover_crowding_shadow_v1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(path: str | Path) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        return raw
    return (_repo_root() / raw).resolve()


def _safe_float(value: Any) -> float:
    try:
        out = float(value)
    except Exception:
        return np.nan
    return out if np.isfinite(out) else np.nan


def _pct_rank(series: pd.Series, *, higher_is_hot: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() <= 1:
        return pd.Series(np.nan, index=series.index)
    ranked = numeric.rank(method="average", pct=True)
    return ranked if higher_is_hot else 1.0 - ranked


def _bucket_pct(value: Any) -> str:
    value = _safe_float(value)
    if not np.isfinite(value):
        return "missing"
    if value <= 0.2:
        return "q1_low"
    if value <= 0.4:
        return "q2"
    if value <= 0.6:
        return "q3"
    if value <= 0.8:
        return "q4"
    return "q5_high"


def _fmt_pct(value: Any) -> str:
    value = _safe_float(value)
    if not np.isfinite(value):
        return ""
    return f"{value * 100:.2f}%"


def _fmt_num(value: Any, digits: int = 3) -> str:
    value = _safe_float(value)
    if not np.isfinite(value):
        return ""
    return f"{value:.{digits}f}"


def _load_orders(exp_dir: Path) -> pd.DataFrame:
    orders = pd.read_csv(exp_dir / "orders.csv", low_memory=False)
    if orders.empty:
        return pd.DataFrame()
    orders["symbol"] = orders["symbol"].map(normalize_symbol)
    orders["date"] = pd.to_datetime(orders["date"], errors="coerce")
    rows: list[dict[str, Any]] = []
    for row in orders.itertuples(index=False):
        side = str(getattr(row, "side", "")).upper()
        try:
            meta = json.loads(getattr(row, "meta_json", "") or "{}")
        except Exception:
            meta = {}
        signal_date = pd.to_datetime(meta.get("signal_date") or getattr(row, "date"), errors="coerce")
        rows.append(
            {
                "date": getattr(row, "date"),
                "symbol": str(getattr(row, "symbol")),
                "side": side,
                "fill_price": _safe_float(getattr(row, "fill_price", np.nan)),
                "qty": _safe_float(getattr(row, "qty", np.nan)),
                "net_amount": _safe_float(getattr(row, "net_amount", np.nan)),
                "reason_code": str(getattr(row, "reason_code", "") or ""),
                "signal_date": signal_date,
                "final_score_rank": _safe_float(meta.get("final_score_rank")),
                "final_score": _safe_float(meta.get("final_score_value", meta.get("final_score"))),
                "residual_strength_score": _safe_float(meta.get("residual_strength_score")),
                "breakout_margin_raw": _safe_float(meta.get("breakout_margin_raw")),
            }
        )
    return pd.DataFrame(rows)


def _build_buy_entries(orders: pd.DataFrame) -> pd.DataFrame:
    buys = orders.loc[orders["side"].eq("BUY")].copy().sort_values(["symbol", "date"]).reset_index(drop=True)
    sells = orders.loc[orders["side"].eq("SELL")].copy().sort_values(["symbol", "date"]).reset_index(drop=True)
    exit_rows: list[dict[str, Any]] = []
    for idx, buy in buys.iterrows():
        later = sells.loc[(sells["symbol"].eq(buy["symbol"])) & (sells["date"] > buy["date"])].sort_values("date")
        if later.empty:
            exit_rows.append({"entry_row_id": idx, "exit_date": pd.NaT, "exit_reason": "", "realized_return": np.nan})
            continue
        sell = later.iloc[0]
        entry_price = _safe_float(buy["fill_price"])
        exit_price = _safe_float(sell["fill_price"])
        realized_return = exit_price / entry_price - 1.0 if np.isfinite(entry_price) and entry_price > 0 else np.nan
        exit_rows.append(
            {
                "entry_row_id": idx,
                "exit_date": sell["date"],
                "exit_reason": str(sell.get("reason_code", "") or ""),
                "realized_return": realized_return,
            }
        )
    buys = buys.reset_index(names="entry_row_id")
    return buys.merge(pd.DataFrame(exit_rows), on="entry_row_id", how="left")


def _load_candidate_pool(exp_dir: Path, buys: pd.DataFrame) -> pd.DataFrame:
    path = exp_dir / "candidate_signals.csv"
    columns = ["date", "symbol", "source"]
    frames: list[pd.DataFrame] = []
    if path.exists():
        candidates = pd.read_csv(path, low_memory=False)
        if not candidates.empty:
            candidates["date"] = pd.to_datetime(candidates["date"], errors="coerce")
            candidates["symbol"] = candidates["symbol"].map(normalize_symbol)
            candidates["source"] = "candidate_signals"
            frames.append(candidates.loc[:, columns].copy())
    buy_pool = buys.loc[:, ["signal_date", "symbol"]].rename(columns={"signal_date": "date"}).copy()
    buy_pool["source"] = "selected_buy"
    frames.append(buy_pool.loc[:, columns].copy())
    pool = pd.concat(frames, ignore_index=True).dropna(subset=["date", "symbol"])
    pool["date"] = pd.to_datetime(pool["date"], errors="coerce")
    pool["symbol"] = pool["symbol"].map(normalize_symbol)
    pool = pool.drop_duplicates(["date", "symbol"]).sort_values(["date", "symbol"]).reset_index(drop=True)
    return pool


def _query_prices(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    with pg_env.connect(config_path="backend/configs/pams_cn_pg.json", autocommit=True, connect_timeout=10) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT symbol, trade_date, close, adj_factor, turnover, turnover_rate_f, volume_ratio, circ_mv
                FROM public.pams_ohlcv_daily_v2
                WHERE symbol = ANY(%s)
                  AND trade_date BETWEEN %s AND %s
                  AND row_status = 'traded'
                ORDER BY symbol, trade_date
                """,
                (symbols, start, end),
            )
            frame = pd.DataFrame(cur.fetchall())
    if frame.empty:
        return frame
    frame["symbol"] = frame["symbol"].map(normalize_symbol)
    frame["date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    for col in ["close", "adj_factor", "turnover", "turnover_rate_f", "volume_ratio", "circ_mv"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["adj_close"] = frame["close"] * frame["adj_factor"].replace(0, np.nan)
    return frame.dropna(subset=["symbol", "date", "adj_close"]).sort_values(["symbol", "date"]).reset_index(drop=True)


def _load_quality_for_pairs(path: Path, pairs: set[tuple[str, str]]) -> pd.DataFrame:
    if not path.exists() or not pairs:
        return pd.DataFrame(columns=["date", "symbol", "quality_score", "roe", "roa", "gross_margin", "net_margin", "leverage"])
    usecols = [
        "date",
        "symbol",
        "quality_score",
        "available",
        "roe",
        "roa",
        "gross_margin",
        "net_margin",
        "leverage",
    ]
    chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(path, usecols=usecols, chunksize=500_000, low_memory=False):
        chunk["date"] = chunk["date"].astype(str)
        chunk["symbol"] = chunk["symbol"].map(normalize_symbol)
        mask = [pair in pairs for pair in zip(chunk["date"], chunk["symbol"], strict=False)]
        if any(mask):
            chunks.append(chunk.loc[mask].copy())
    if not chunks:
        return pd.DataFrame(columns=["date", "symbol", "quality_score", "roe", "roa", "gross_margin", "net_margin", "leverage"])
    quality = pd.concat(chunks, ignore_index=True)
    quality["date"] = pd.to_datetime(quality["date"], errors="coerce")
    quality["symbol"] = quality["symbol"].map(normalize_symbol)
    for col in ["quality_score", "roe", "roa", "gross_margin", "net_margin", "leverage"]:
        quality[col] = pd.to_numeric(quality[col], errors="coerce")
    quality["quality_available"] = quality["available"].astype(str).str.lower().isin({"true", "1", "yes"})
    return quality.drop(columns=["available"], errors="ignore")


def _entry_features(pool: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    price_map = {symbol: group.sort_values("date").reset_index(drop=True) for symbol, group in prices.groupby("symbol")}
    for item in pool.itertuples(index=False):
        symbol = str(item.symbol)
        date_value = pd.Timestamp(item.date)
        series = price_map.get(symbol)
        if series is None or series.empty:
            continue
        idxs = series.index[series["date"].le(date_value)].tolist()
        if not idxs:
            continue
        idx = int(idxs[-1])
        close = pd.to_numeric(series["adj_close"], errors="coerce")
        returns = close.pct_change()
        amount = pd.to_numeric(series["turnover"], errors="coerce")
        turnover_rate = pd.to_numeric(series["turnover_rate_f"], errors="coerce")

        def mean_n(values: pd.Series, n: int) -> float:
            part = values.iloc[max(0, idx - n + 1) : idx + 1]
            return float(part.mean()) if part.notna().any() else np.nan

        def ret_n(n: int) -> float:
            if idx < n:
                return np.nan
            base = _safe_float(close.iloc[idx - n])
            now = _safe_float(close.iloc[idx])
            return now / base - 1.0 if np.isfinite(base) and base > 0 and np.isfinite(now) else np.nan

        entry_close = _safe_float(close.iloc[idx])
        amount20 = mean_n(amount, 20)
        amount60 = mean_n(amount, 60)
        turnover20 = mean_n(turnover_rate, 20)
        turnover60 = mean_n(turnover_rate, 60)
        ma20 = mean_n(close, 20)
        rows.append(
            {
                "date": date_value,
                "symbol": symbol,
                "price_obs_date": series.loc[idx, "date"],
                "amount20": amount20,
                "amount60": amount60,
                "turnover_rate20": turnover20,
                "turnover_rate60": turnover60,
                "amount_accel_20_60": amount20 / amount60 if np.isfinite(amount20) and np.isfinite(amount60) and amount60 else np.nan,
                "turnover_accel_20_60": turnover20 / turnover60 if np.isfinite(turnover20) and np.isfinite(turnover60) and turnover60 else np.nan,
                "pre_ret_20": ret_n(20),
                "pre_ret_60": ret_n(60),
                "dist_ma20": entry_close / ma20 - 1.0 if np.isfinite(entry_close) and np.isfinite(ma20) and ma20 else np.nan,
                "vol20": float(returns.iloc[max(0, idx - 19) : idx + 1].std(ddof=0)) if idx >= 20 else np.nan,
                "circ_mv": _safe_float(series.loc[idx, "circ_mv"]),
            }
        )
    features = pd.DataFrame(rows)
    if features.empty:
        return features
    for col in [
        "amount20",
        "amount60",
        "turnover_rate20",
        "turnover_rate60",
        "amount_accel_20_60",
        "turnover_accel_20_60",
        "pre_ret_20",
        "dist_ma20",
        "vol20",
    ]:
        features[f"{col}_pct"] = features.groupby("date")[col].transform(_pct_rank)
    return features


def _assign_labels(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["amount_pct_bucket"] = out["amount20_pct"].map(_bucket_pct)
    out["turnover_pct_bucket"] = out["turnover_rate20_pct"].map(_bucket_pct)
    out["amount_accel_bucket"] = out["amount_accel_20_60_pct"].map(_bucket_pct)
    out["turnover_accel_bucket"] = out["turnover_accel_20_60_pct"].map(_bucket_pct)
    out["position_bucket"] = out[["pre_ret_20_pct", "dist_ma20_pct"]].max(axis=1).map(_bucket_pct)
    out["low_amount"] = out["amount20_pct"] <= 0.2
    out["hot_turnover"] = out["turnover_rate20_pct"] >= 0.8
    out["amount_surge"] = out["amount_accel_20_60_pct"] >= 0.8
    out["turnover_surge"] = out["turnover_accel_20_60_pct"] >= 0.8
    out["high_position"] = out[["pre_ret_20_pct", "dist_ma20_pct"]].max(axis=1) >= 0.8
    out["high_amount"] = out["amount20_pct"] >= 0.8
    out["low_quality"] = out["quality_score_pct"] <= 0.4
    out["high_volatility"] = out["vol20_pct"] >= 0.8
    out["crowding_risk"] = out["hot_turnover"] & out["turnover_surge"]
    out["hot_liquidity_chase"] = out["hot_turnover"] & out["high_position"]
    out["hot_amount_turnover"] = out["high_amount"] & out["hot_turnover"]
    out["hot_position_turnover"] = out["high_position"] & out["hot_turnover"]
    out["hot_position_turnover_with_qv"] = out["hot_position_turnover"] & (out["low_quality"] | out["high_volatility"])
    components = ["high_amount", "hot_turnover", "high_position", "low_quality", "high_volatility"]
    out["composite_risk_count_5"] = out[components].sum(axis=1)
    out["composite_risk_3of5"] = out["composite_risk_count_5"] >= 3
    out["composite_risk_4of5"] = out["composite_risk_count_5"] >= 4
    out["healthy_liquidity"] = (~out["low_amount"]) & (~out["hot_turnover"]) & (~out["turnover_surge"])
    tags: list[str] = []
    for row in out.itertuples(index=False):
        current: list[str] = []
        if bool(getattr(row, "low_amount")):
            current.append("LOW_AMOUNT")
        if bool(getattr(row, "hot_turnover")):
            current.append("HOT_TURNOVER")
        if bool(getattr(row, "amount_surge")):
            current.append("AMOUNT_SURGE")
        if bool(getattr(row, "turnover_surge")):
            current.append("TURNOVER_SURGE")
        if bool(getattr(row, "high_position")):
            current.append("HIGH_POSITION")
        if bool(getattr(row, "high_amount")):
            current.append("HIGH_AMOUNT")
        if bool(getattr(row, "low_quality")):
            current.append("LOW_QUALITY")
        if bool(getattr(row, "high_volatility")):
            current.append("HIGH_VOLATILITY")
        if bool(getattr(row, "crowding_risk")):
            current.append("CROWDING_RISK")
        if bool(getattr(row, "hot_liquidity_chase")):
            current.append("HOT_LIQUIDITY_CHASE")
        if bool(getattr(row, "hot_amount_turnover")):
            current.append("HOT_AMOUNT_TURNOVER")
        if bool(getattr(row, "hot_position_turnover_with_qv")):
            current.append("HOT_POSITION_TURNOVER_WITH_QV")
        if bool(getattr(row, "composite_risk_3of5")):
            current.append("COMPOSITE_RISK_3OF5")
        if bool(getattr(row, "composite_risk_4of5")):
            current.append("COMPOSITE_RISK_4OF5")
        if bool(getattr(row, "healthy_liquidity")):
            current.append("HEALTHY_LIQUIDITY")
        tags.append(";".join(current) if current else "none")
    out["liquidity_turnover_tags"] = tags
    return out


def _summarize_bucket(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(group_cols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        payload = {col: value for col, value in zip(group_cols, key, strict=False)}
        realized = pd.to_numeric(group["realized_return"], errors="coerce")
        fwd20 = pd.to_numeric(group["fwd_ret_20"], errors="coerce")
        fwd60 = pd.to_numeric(group["fwd_ret_60"], errors="coerce")
        payload.update(
            {
                "entries": int(len(group)),
                "symbols": int(group["symbol"].nunique()),
                "win_rate_realized": float((realized > 0).mean()) if realized.notna().any() else np.nan,
                "realized_median": float(realized.median()) if realized.notna().any() else np.nan,
                "fwd20_median": float(fwd20.median()) if fwd20.notna().any() else np.nan,
                "fwd60_median": float(fwd60.median()) if fwd60.notna().any() else np.nan,
                "profit_top50_rate": float(group["is_profit_top50"].mean()),
                "loss_top50_rate": float(group["is_loss_top50"].mean()),
            }
        )
        rows.append(payload)
    return pd.DataFrame(rows).sort_values(["entries"], ascending=False).reset_index(drop=True)


def _forward_returns(panel: pd.DataFrame, prices: pd.DataFrame, horizons: tuple[int, ...] = (20, 60)) -> pd.DataFrame:
    price_map = {symbol: group.sort_values("date").reset_index(drop=True) for symbol, group in prices.groupby("symbol")}
    out = panel.copy()
    for horizon in horizons:
        values: list[float] = []
        for row in out.itertuples(index=False):
            series = price_map.get(str(row.symbol))
            if series is None or series.empty:
                values.append(np.nan)
                continue
            idxs = series.index[series["date"].ge(pd.Timestamp(row.date))].tolist()
            if not idxs:
                values.append(np.nan)
                continue
            idx = int(idxs[0])
            end_idx = idx + horizon
            if end_idx >= len(series):
                values.append(np.nan)
                continue
            start = _safe_float(series.loc[idx, "adj_close"])
            end = _safe_float(series.loc[end_idx, "adj_close"])
            values.append(end / start - 1.0 if np.isfinite(start) and start > 0 and np.isfinite(end) else np.nan)
        out[f"fwd_ret_{horizon}"] = values
    return out


def run_shadow(exp_id: str = DEFAULT_EXP_ID, output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    exp_dir = _resolve(Path("outputs/experiments") / exp_id)
    out_dir = _resolve(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    orders = _load_orders(exp_dir)
    buys = _build_buy_entries(orders)
    pool = _load_candidate_pool(exp_dir, buys)
    start = (pool["date"].min() - pd.Timedelta(days=260)).date().isoformat()
    end = (pool["date"].max() + pd.Timedelta(days=90)).date().isoformat()
    symbols = sorted(pool["symbol"].dropna().unique().tolist())
    prices = _query_prices(symbols, start, end)
    features = _entry_features(pool, prices)
    quality_path = _resolve(DEFAULT_QUALITY_PATH)
    quality_pairs = set(zip(features["date"].dt.strftime("%Y-%m-%d"), features["symbol"], strict=False)) if not features.empty else set()
    quality = _load_quality_for_pairs(quality_path, quality_pairs)
    if not quality.empty:
        features = features.merge(quality, on=["date", "symbol"], how="left")
    else:
        features["quality_score"] = np.nan
        features["quality_available"] = False
    features["quality_score_pct"] = features.groupby("date")["quality_score"].transform(_pct_rank)
    features = _assign_labels(features)

    entry_base = buys.copy()
    entry_base["trade_date"] = entry_base["date"]
    entry_base["date"] = entry_base["signal_date"]
    entry_panel = entry_base.merge(features, on=["date", "symbol"], how="left")
    entry_panel = _forward_returns(entry_panel, prices)

    performance = pd.read_csv(exp_dir / "symbol_performance.csv")
    performance["symbol"] = performance["symbol"].map(normalize_symbol)
    performance["net_pnl"] = pd.to_numeric(performance["net_pnl"], errors="coerce")
    profit_top = set(performance.sort_values("net_pnl", ascending=False).head(50)["symbol"])
    loss_top = set(performance.sort_values("net_pnl", ascending=True).head(50)["symbol"])
    names_path = exp_dir / "stock_names.json"
    names = json.loads(names_path.read_text(encoding="utf-8")) if names_path.exists() else {}
    entry_panel["name"] = entry_panel["symbol"].map(names).fillna("")
    entry_panel["is_profit_top50"] = entry_panel["symbol"].isin(profit_top)
    entry_panel["is_loss_top50"] = entry_panel["symbol"].isin(loss_top)

    bucket_parts = []
    for col in [
        "amount_pct_bucket",
        "turnover_pct_bucket",
        "amount_accel_bucket",
        "turnover_accel_bucket",
        "position_bucket",
        "quality_score_pct_bucket",
    ]:
        if col == "quality_score_pct_bucket":
            entry_panel[col] = entry_panel["quality_score_pct"].map(_bucket_pct)
        part = _summarize_bucket(entry_panel, [col])
        part.insert(0, "factor", col)
        part = part.rename(columns={col: "bucket"})
        bucket_parts.append(part)
    bucket_summary = pd.concat(bucket_parts, ignore_index=True)
    cross_bucket = _summarize_bucket(entry_panel, ["amount_pct_bucket", "turnover_pct_bucket"])
    position_turnover = _summarize_bucket(entry_panel, ["position_bucket", "turnover_pct_bucket"])

    tag_cols = [
        "low_amount",
        "hot_turnover",
        "high_amount",
        "low_quality",
        "high_volatility",
        "amount_surge",
        "turnover_surge",
        "crowding_risk",
        "hot_liquidity_chase",
        "hot_amount_turnover",
        "hot_position_turnover",
        "hot_position_turnover_with_qv",
        "composite_risk_3of5",
        "composite_risk_4of5",
        "healthy_liquidity",
    ]
    coverage_rows: list[dict[str, Any]] = []
    for tag in tag_cols:
        for group_name, mask in {
            "all_buys": pd.Series(True, index=entry_panel.index),
            "profit_top50_entries": entry_panel["is_profit_top50"],
            "loss_top50_entries": entry_panel["is_loss_top50"],
        }.items():
            group = entry_panel.loc[mask]
            coverage_rows.append(
                {
                    "tag": tag,
                    "group": group_name,
                    "entries": int(len(group)),
                    "covered": int(pd.to_numeric(group[tag], errors="coerce").fillna(False).sum()) if not group.empty else 0,
                    "coverage_rate": float(group[tag].mean()) if not group.empty else np.nan,
                }
            )
    top50_coverage = pd.DataFrame(coverage_rows)
    complete_composite = _summarize_bucket(
        entry_panel,
        ["composite_risk_count_5"],
    )
    composite_tag_summary = []
    for tag in [
        "high_amount",
        "hot_turnover",
        "high_position",
        "low_quality",
        "high_volatility",
        "hot_amount_turnover",
        "hot_position_turnover",
        "hot_position_turnover_with_qv",
        "composite_risk_3of5",
        "composite_risk_4of5",
    ]:
        tagged = entry_panel.loc[entry_panel[tag].fillna(False)].copy()
        if tagged.empty:
            continue
        row = _summarize_bucket(tagged.assign(tag=tag), ["tag"]).iloc[0].to_dict()
        row["coverage_all_buys"] = float(entry_panel[tag].mean())
        composite_tag_summary.append(row)
    composite_tag_summary_frame = pd.DataFrame(composite_tag_summary)

    entry_panel.to_csv(out_dir / "entry_panel.csv", index=False, encoding="utf-8-sig")
    features.to_csv(out_dir / "signal_pool_feature_panel.csv", index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(out_dir / "bucket_summary.csv", index=False, encoding="utf-8-sig")
    cross_bucket.to_csv(out_dir / "cross_bucket_summary.csv", index=False, encoding="utf-8-sig")
    position_turnover.to_csv(out_dir / "position_turnover_summary.csv", index=False, encoding="utf-8-sig")
    top50_coverage.to_csv(out_dir / "top50_coverage.csv", index=False, encoding="utf-8-sig")
    complete_composite.to_csv(out_dir / "complete_composite_bucket_summary.csv", index=False, encoding="utf-8-sig")
    composite_tag_summary_frame.to_csv(out_dir / "complete_composite_tag_summary.csv", index=False, encoding="utf-8-sig")

    wide = top50_coverage.pivot(index="tag", columns="group", values="coverage_rate").reset_index()
    for col in ["loss_top50_entries", "profit_top50_entries"]:
        if col not in wide:
            wide[col] = np.nan
    wide["loss_minus_profit_coverage"] = wide["loss_top50_entries"] - wide["profit_top50_entries"]
    wide = wide.sort_values("loss_minus_profit_coverage", ascending=False)

    top_hot = bucket_summary.loc[bucket_summary["factor"].eq("turnover_pct_bucket")].copy()
    top_amount = bucket_summary.loc[bucket_summary["factor"].eq("amount_pct_bucket")].copy()

    lines = [
        "# V4 Liquidity / Turnover Crowding Shadow",
        "",
        "## Conclusion",
        "",
        "This is a shadow audit only. It does not change trading logic or baselines.",
        "",
        "The percentile scope is the logged signal pool for each signal date: selected BUY rows plus `candidate_signals.csv` rows. It is not a full-market percentile.",
        "",
        "## Coverage",
        "",
        f"- source_exp_id: `{exp_id}`",
        f"- buy_entries: {len(entry_panel)}",
        f"- signal_pool_rows: {len(features)}",
        f"- symbols: {entry_panel['symbol'].nunique()}",
        f"- feature_matched_entries: {int(entry_panel['amount20'].notna().sum())}",
        f"- quality_matched_entries: {int(entry_panel['quality_score'].notna().sum())}",
        "",
        "## TOP50 Coverage By Tags",
        "",
        wide.to_markdown(index=False),
        "",
        "## Turnover Buckets",
        "",
        top_hot.to_markdown(index=False),
        "",
        "## Amount Buckets",
        "",
        top_amount.to_markdown(index=False),
        "",
        "## Amount x Turnover",
        "",
        cross_bucket.sort_values(["loss_top50_rate", "entries"], ascending=[False, False]).head(20).to_markdown(index=False),
        "",
        "## Position x Turnover",
        "",
        position_turnover.sort_values(["loss_top50_rate", "entries"], ascending=[False, False]).head(20).to_markdown(index=False),
        "",
        "## Complete Composite Tags",
        "",
        composite_tag_summary_frame.sort_values(["loss_top50_rate", "entries"], ascending=[False, False]).to_markdown(index=False),
        "",
        "## Composite Risk Count",
        "",
        complete_composite.to_markdown(index=False),
        "",
        "## Plain Interpretation",
        "",
        "- Low amount is capacity risk, but it is not assumed to be the main loss driver.",
        "- Hot turnover and turnover surge represent crowding/heat risk.",
        "- Hot turnover combined with high position is the cleanest liquidity-only candidate before any AB.",
        "- The complete shadow adds quality and volatility to check whether losses are concentrated in a broader risk image.",
    ]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "study_id": STUDY_ID,
        "source_exp_id": exp_id,
        "output_dir": str(out_dir),
        "buy_entries": int(len(entry_panel)),
        "signal_pool_rows": int(len(features)),
        "feature_matched_entries": int(entry_panel["amount20"].notna().sum()),
        "quality_matched_entries": int(entry_panel["quality_score"].notna().sum()),
        "top50_coverage": wide.to_dict(orient="records"),
        "complete_composite_tag_summary": composite_tag_summary_frame.to_dict(orient="records"),
        "files": {
            "report": str(out_dir / "report.md"),
            "entry_panel": str(out_dir / "entry_panel.csv"),
            "bucket_summary": str(out_dir / "bucket_summary.csv"),
            "cross_bucket_summary": str(out_dir / "cross_bucket_summary.csv"),
            "top50_coverage": str(out_dir / "top50_coverage.csv"),
            "complete_composite_bucket_summary": str(out_dir / "complete_composite_bucket_summary.csv"),
            "complete_composite_tag_summary": str(out_dir / "complete_composite_tag_summary.csv"),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V4 liquidity/turnover crowding shadow audit")
    parser.add_argument("--exp-id", default=DEFAULT_EXP_ID)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    print(json.dumps(sanitize_json(run_shadow(args.exp_id, args.output_dir)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
