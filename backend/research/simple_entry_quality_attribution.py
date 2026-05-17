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


STUDY_ID = "cn_stock/simple_entry_quality_attribution_v1"
SOURCE_STUDY_ROOT = Path("outputs/studies/cn_stock/simple_csi1000_trend_rebuild_v1")
OUT_ROOT = Path("outputs/studies/cn_stock/simple_entry_quality_attribution_v1")
RISK_TIER_MULTIPLIERS = {
    "0_low": 1.0,
    "1_watch": 0.8,
    "2_high": 0.5,
    "3_plus_extreme": 1.0 / 3.0,
}


def _source_dir(variant: str, window: str) -> Path:
    root = SOURCE_STUDY_ROOT
    if variant == "plain":
        candidate = root / window
        if candidate.exists():
            return candidate
    return root / variant / window


def _query_frame(conn: Any, sql: str, params: tuple[Any, ...]) -> pd.DataFrame:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return pd.DataFrame(rows)


def _load_prices(conn: Any, symbols: list[str], start: str, end: str) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=["symbol", "date", "adj_close", "turnover"])
    preload_start = (pd.to_datetime(start) - pd.Timedelta(days=260)).date().isoformat()
    forward_end = (pd.to_datetime(end) + pd.Timedelta(days=120)).date().isoformat()
    frame = _query_frame(
        conn,
        """
        SELECT symbol, trade_date, close, adj_factor, turnover
        FROM public.pams_ohlcv_daily_v2
        WHERE symbol = ANY(%s)
          AND trade_date BETWEEN %s AND %s
          AND row_status = 'traded'
        ORDER BY symbol, trade_date
        """,
        (symbols, preload_start, forward_end),
    )
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "date", "adj_close", "turnover"])
    frame["symbol"] = frame["symbol"].map(normalize_symbol)
    frame["date"] = pd.to_datetime(frame["trade_date"])
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["adj_factor"] = pd.to_numeric(frame["adj_factor"], errors="coerce")
    frame["turnover"] = pd.to_numeric(frame["turnover"], errors="coerce")
    frame["adj_close"] = frame["close"] * frame["adj_factor"].replace(0, np.nan)
    return frame.dropna(subset=["symbol", "date", "adj_close"]).loc[:, ["symbol", "date", "adj_close", "turnover"]]


def _bucket_numeric(value: Any, cuts: list[float], labels: list[str], missing: str = "missing") -> str:
    try:
        number = float(value)
    except Exception:
        return missing
    if not np.isfinite(number):
        return missing
    for cut, label in zip(cuts, labels, strict=False):
        if number < cut:
            return label
    return labels[-1]


def ret120_bucket(value: Any) -> str:
    return _bucket_numeric(value, [0.20, 0.40, 0.80], ["<20%", "20-40%", "40-80%", ">=80%"])


def ret20_bucket(value: Any) -> str:
    return _bucket_numeric(value, [0.00, 0.10, 0.20], ["<0%", "0-10%", "10-20%", ">=20%"])


def ma_distance_bucket(value: Any) -> str:
    return _bucket_numeric(value, [0.10, 0.25, 0.50], ["<10%", "10-25%", "25-50%", ">=50%"])


def vol20_bucket(value: Any) -> str:
    return _bucket_numeric(value, [0.025, 0.04, 0.06], ["<2.5%", "2.5-4%", "4-6%", ">=6%"])


def drawdown60_bucket(value: Any) -> str:
    return _bucket_numeric(value, [-0.20, -0.10, -0.03], ["deep<-20%", "-20--10%", "-10--3%", "near_high"])


def turnover_bucket(value: Any) -> str:
    return _bucket_numeric(value, [100_000_000, 300_000_000, 800_000_000], ["<100m", "100-300m", "300-800m", ">=800m"])


def accel_bucket(ret20: Any, ret120: Any) -> str:
    try:
        r20 = float(ret20)
        r120 = float(ret120)
    except Exception:
        return "missing"
    if not np.isfinite(r20) or not np.isfinite(r120) or r120 <= 0:
        return "missing"
    share = r20 / r120
    return _bucket_numeric(share, [0.25, 0.50, 0.80], ["slow", "balanced", "recent_fast", "very_recent"])


def entry_risk_labels(row: dict[str, Any] | pd.Series) -> list[str]:
    value = dict(row)
    labels: list[str] = []
    if str(value.get("ma_distance_bucket") or "") == ">=50%":
        labels.append("high_extension")
    if str(value.get("vol20_bucket") or "") == ">=6%":
        labels.append("high_volatility")
    if str(value.get("ret120_bucket") or "") == ">=80%" and str(value.get("accel_bucket") or "") in {
        "recent_fast",
        "very_recent",
    }:
        labels.append("late_acceleration")
    if str(value.get("membership_bucket") or "") == "csi1000_new" and str(value.get("ma_distance_bucket") or "") == ">=50%":
        labels.append("csi1000_high_extension")
    return labels


def entry_risk_tier(count: int) -> str:
    if count <= 0:
        return "0_low"
    if count == 1:
        return "1_watch"
    if count == 2:
        return "2_high"
    return "3_plus_extreme"


def risk_tier_multiplier(tier: str) -> float:
    return float(RISK_TIER_MULTIPLIERS.get(str(tier), 1.0))


def _path_metrics(closes: pd.Series, entry_pos: int, horizons: tuple[int, ...] = (20, 60)) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    if entry_pos >= len(closes):
        return out
    entry_close = float(closes.iloc[entry_pos])
    if not np.isfinite(entry_close) or entry_close <= 0:
        return out
    for horizon in horizons:
        end_pos = entry_pos + horizon
        if end_pos >= len(closes):
            out[f"fwd_ret_{horizon}"] = None
            out[f"mfe_{horizon}"] = None
            out[f"mae_{horizon}"] = None
            continue
        future = closes.iloc[entry_pos + 1 : end_pos + 1].astype(float)
        out[f"fwd_ret_{horizon}"] = float(closes.iloc[end_pos] / entry_close - 1.0)
        out[f"mfe_{horizon}"] = float(future.max() / entry_close - 1.0)
        out[f"mae_{horizon}"] = float(future.min() / entry_close - 1.0)
    return out


def _entry_features(group: pd.DataFrame, entry_date: pd.Timestamp) -> dict[str, Any]:
    group = group.sort_values("date").reset_index(drop=True)
    matches = group.index[group["date"].eq(entry_date)].tolist()
    if not matches:
        return {}
    idx = int(matches[0])
    closes = pd.to_numeric(group["adj_close"], errors="coerce")
    turnovers = pd.to_numeric(group["turnover"], errors="coerce")
    entry_close = float(closes.iloc[idx])
    ret = closes.pct_change()
    row: dict[str, Any] = {
        "entry_close": entry_close,
        "ret20": float(closes.iloc[idx] / closes.iloc[idx - 20] - 1.0) if idx >= 20 else None,
        "ret60": float(closes.iloc[idx] / closes.iloc[idx - 60] - 1.0) if idx >= 60 else None,
        "ret120": float(closes.iloc[idx] / closes.iloc[idx - 120] - 1.0) if idx >= 120 else None,
        "vol20": float(ret.iloc[max(0, idx - 19) : idx + 1].std(ddof=0)) if idx >= 20 else None,
        "avg_turnover20": float(turnovers.iloc[max(0, idx - 19) : idx + 1].mean()) if idx >= 20 else None,
    }
    if idx >= 119:
        ma120 = float(closes.iloc[idx - 119 : idx + 1].mean())
        row["ma120_distance"] = entry_close / ma120 - 1.0 if ma120 > 0 else None
    else:
        row["ma120_distance"] = None
    if idx >= 59:
        high60 = float(closes.iloc[idx - 59 : idx + 1].max())
        row["high60_distance"] = entry_close / high60 - 1.0 if high60 > 0 else None
        row["drawdown60"] = row["high60_distance"]
    else:
        row["high60_distance"] = None
        row["drawdown60"] = None
    row.update(_path_metrics(closes, idx))
    return row


def _load_source_entries(source: Path) -> pd.DataFrame:
    trades_path = source / "trades.csv"
    if not trades_path.exists():
        raise FileNotFoundError(f"missing trades: {trades_path}")
    trades = pd.read_csv(trades_path)
    if trades.empty:
        return pd.DataFrame()
    trades["date"] = pd.to_datetime(trades["date"])
    trades["symbol"] = trades["symbol"].map(normalize_symbol)
    trades["weight_before"] = pd.to_numeric(trades["weight_before"], errors="coerce").fillna(0.0)
    trades["weight_after"] = pd.to_numeric(trades["weight_after"], errors="coerce").fillna(0.0)
    entries = trades.loc[
        trades["side"].astype(str).str.upper().eq("BUY")
        & (trades["weight_before"].abs() < 1e-12)
        & (trades["weight_after"] > 0)
    ].copy()
    entries = entries.sort_values(["date", "symbol"]).reset_index(drop=True)
    entries["entry_id"] = np.arange(1, len(entries) + 1)
    exits = trades.loc[
        trades["side"].astype(str).str.upper().eq("SELL")
        & (trades["weight_after"].abs() < 1e-12)
    ].copy()
    realized_rows: list[dict[str, Any]] = []
    for entry in entries.itertuples(index=False):
        later = exits.loc[(exits["symbol"] == entry.symbol) & (exits["date"] > entry.date)].sort_values("date")
        if later.empty:
            realized_rows.append({"entry_id": entry.entry_id, "exit_date": None, "exit_reason": None})
        else:
            sell = later.iloc[0]
            realized_rows.append(
                {
                    "entry_id": entry.entry_id,
                    "exit_date": sell["date"],
                    "exit_reason": sell.get("reason", ""),
                }
            )
    return entries.merge(pd.DataFrame(realized_rows), on="entry_id", how="left")


def build_entry_attribution(source: Path, prices: pd.DataFrame) -> pd.DataFrame:
    entries = _load_source_entries(source)
    if entries.empty:
        return entries
    price_map = {symbol: group.copy() for symbol, group in prices.groupby("symbol")}
    rows: list[dict[str, Any]] = []
    for entry in entries.itertuples(index=False):
        group = price_map.get(str(entry.symbol))
        if group is None or group.empty:
            continue
        features = _entry_features(group, pd.Timestamp(entry.date))
        if not features:
            continue
        realized_return = None
        if pd.notna(getattr(entry, "exit_date", None)):
            g = group.sort_values("date").reset_index(drop=True)
            entry_match = g.loc[g["date"].eq(pd.Timestamp(entry.date)), "adj_close"]
            exit_match = g.loc[g["date"].eq(pd.Timestamp(entry.exit_date)), "adj_close"]
            if not entry_match.empty and not exit_match.empty and float(entry_match.iloc[0]) > 0:
                realized_return = float(exit_match.iloc[0] / entry_match.iloc[0] - 1.0)
        row = {
            "entry_id": int(entry.entry_id),
            "entry_date": pd.Timestamp(entry.date).date().isoformat(),
            "symbol": str(entry.symbol),
            "membership_bucket": str(getattr(entry, "bucket", "") or ""),
            "entry_reason": str(getattr(entry, "reason", "") or ""),
            "exit_date": pd.Timestamp(entry.exit_date).date().isoformat() if pd.notna(getattr(entry, "exit_date", None)) else "",
            "exit_reason": str(getattr(entry, "exit_reason", "") or ""),
            "realized_return": realized_return,
            **features,
        }
        row["ret120_bucket"] = ret120_bucket(row.get("ret120"))
        row["ret20_bucket"] = ret20_bucket(row.get("ret20"))
        row["ma_distance_bucket"] = ma_distance_bucket(row.get("ma120_distance"))
        row["vol20_bucket"] = vol20_bucket(row.get("vol20"))
        row["drawdown60_bucket"] = drawdown60_bucket(row.get("drawdown60"))
        row["turnover_bucket"] = turnover_bucket(row.get("avg_turnover20"))
        row["accel_bucket"] = accel_bucket(row.get("ret20"), row.get("ret120"))
        labels = entry_risk_labels(row)
        row["entry_risk_labels"] = ";".join(labels) if labels else "none"
        row["entry_risk_count"] = len(labels)
        row["entry_risk_tier"] = entry_risk_tier(len(labels))
        rows.append(row)
    return pd.DataFrame(rows)


def _summarize(entries: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if entries.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    grouped = entries.groupby(group_cols, dropna=False)
    for key, group in grouped:
        if not isinstance(key, tuple):
            key = (key,)
        row = {col: value for col, value in zip(group_cols, key, strict=False)}
        row.update(
            {
                "n": int(len(group)),
                "fwd20_mean": float(pd.to_numeric(group["fwd_ret_20"], errors="coerce").mean()),
                "fwd20_median": float(pd.to_numeric(group["fwd_ret_20"], errors="coerce").median()),
                "fwd60_mean": float(pd.to_numeric(group["fwd_ret_60"], errors="coerce").mean()),
                "fwd60_median": float(pd.to_numeric(group["fwd_ret_60"], errors="coerce").median()),
                "mfe20_median": float(pd.to_numeric(group["mfe_20"], errors="coerce").median()),
                "mae20_median": float(pd.to_numeric(group["mae_20"], errors="coerce").median()),
                "mfe60_median": float(pd.to_numeric(group["mfe_60"], errors="coerce").median()),
                "mae60_median": float(pd.to_numeric(group["mae_60"], errors="coerce").median()),
                "realized_median": float(pd.to_numeric(group["realized_return"], errors="coerce").median()),
                "tail_loss60_p25": float(pd.to_numeric(group["fwd_ret_60"], errors="coerce").quantile(0.25)),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["n", "fwd60_median"], ascending=[False, True]).reset_index(drop=True)


def _nav_metrics(nav: pd.DataFrame) -> dict[str, Any]:
    if nav.empty:
        return {}
    frame = nav.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    returns = pd.to_numeric(frame["daily_return"], errors="coerce").fillna(0.0)
    values = pd.to_numeric(frame["nav"], errors="coerce").dropna()
    if values.empty:
        return {}
    days = max((frame["date"].max() - frame["date"].min()).days, 1)
    years = days / 365.25
    total_return = float(values.iloc[-1] / values.iloc[0] - 1.0)
    cagr = float(values.iloc[-1] / values.iloc[0]) ** (1.0 / years) - 1.0
    std = float(returns.std(ddof=0))
    sharpe = float((returns.mean() / std) * np.sqrt(252)) if std > 0 else 0.0
    drawdown = values / values.cummax() - 1.0
    max_drawdown = float(drawdown.min())
    return {
        "start": str(frame["date"].min().date()),
        "end": str(frame["date"].max().date()),
        "trading_days": int(len(frame)),
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "calmar": float(cagr / abs(max_drawdown)) if max_drawdown < 0 else 0.0,
        "avg_exposure": float(pd.to_numeric(frame["exposure"], errors="coerce").mean()),
        "total_turnover_proxy": float(pd.to_numeric(frame["turnover"], errors="coerce").sum()),
    }


def _tier_for_holding(entries: pd.DataFrame, symbol: str, date_value: pd.Timestamp) -> str:
    if entries.empty:
        return "0_low"
    work = entries.loc[entries["symbol"].eq(symbol)].copy()
    if work.empty:
        return "0_low"
    work["entry_date_ts"] = pd.to_datetime(work["entry_date"])
    work["exit_date_ts"] = pd.to_datetime(work["exit_date"], errors="coerce")
    active = work.loc[
        (work["entry_date_ts"] <= date_value)
        & (work["exit_date_ts"].isna() | (work["exit_date_ts"] > date_value))
    ].sort_values("entry_date_ts")
    if active.empty:
        return "0_low"
    return str(active.iloc[-1]["entry_risk_tier"])


def run_position_mapping_shadow(
    source: Path,
    entries: pd.DataFrame,
    prices: pd.DataFrame,
    out_dir: Path,
) -> dict[str, Any]:
    nav_path = source / "nav.csv"
    holdings_path = source / "holdings.csv"
    summary_path = source / "summary.json"
    if not nav_path.exists() or not holdings_path.exists():
        return {"status": "missing_source_nav_or_holdings"}
    source_nav = pd.read_csv(nav_path, parse_dates=["date"])
    holdings = pd.read_csv(holdings_path, parse_dates=["date"])
    if source_nav.empty or holdings.empty:
        return {"status": "empty_source"}
    cost_rate = 0.0015
    if summary_path.exists():
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            cost_rate = float(payload.get("config", {}).get("cost_rate", cost_rate))
        except Exception:
            cost_rate = 0.0015
    prices_work = prices.copy().sort_values(["symbol", "date"])
    prices_work["daily_return"] = prices_work.groupby("symbol")["adj_close"].pct_change().fillna(0.0)
    returns_by_date: dict[pd.Timestamp, dict[str, float]] = {}
    for row in prices_work.itertuples(index=False):
        date_value = pd.Timestamp(row.date)
        returns_by_date.setdefault(date_value, {})[str(row.symbol)] = float(row.daily_return)
    holdings["symbol"] = holdings["symbol"].map(normalize_symbol)
    holdings["weight"] = pd.to_numeric(holdings["weight"], errors="coerce").fillna(0.0)
    holdings_by_date = {pd.Timestamp(date): group.copy() for date, group in holdings.groupby("date")}
    entries_work = entries.copy()
    entries_work["symbol"] = entries_work["symbol"].map(normalize_symbol)
    current_weights: dict[str, float] = {}
    nav_value = 1.0
    nav_rows: list[dict[str, Any]] = []
    weight_rows: list[dict[str, Any]] = []
    missing_tier_count = 0
    for source_row in source_nav.itertuples(index=False):
        date_value = pd.Timestamp(source_row.date)
        gross_return = sum(
            weight * returns_by_date.get(date_value, {}).get(symbol, 0.0)
            for symbol, weight in current_weights.items()
        )
        nav_value *= 1.0 + gross_return
        turnover = 0.0
        cost = 0.0
        if date_value in holdings_by_date:
            next_weights: dict[str, float] = {}
            for holding in holdings_by_date[date_value].itertuples(index=False):
                symbol = str(holding.symbol)
                tier = _tier_for_holding(entries_work, symbol, date_value)
                if not tier:
                    missing_tier_count += 1
                    tier = "0_low"
                multiplier = risk_tier_multiplier(tier)
                shadow_weight = float(holding.weight) * multiplier
                if shadow_weight > 0:
                    next_weights[symbol] = shadow_weight
                weight_rows.append(
                    {
                        "date": date_value.date().isoformat(),
                        "symbol": symbol,
                        "source_weight": float(holding.weight),
                        "shadow_weight": shadow_weight,
                        "entry_risk_tier": tier,
                        "multiplier": multiplier,
                    }
                )
            touched = sorted(set(current_weights) | set(next_weights))
            turnover = sum(abs(next_weights.get(symbol, 0.0) - current_weights.get(symbol, 0.0)) for symbol in touched)
            cost = turnover * cost_rate
            nav_value *= 1.0 - cost
            current_weights = next_weights
        nav_rows.append(
            {
                "date": date_value.date().isoformat(),
                "nav": nav_value,
                "daily_return": gross_return - cost,
                "gross_return": gross_return,
                "cost": cost,
                "turnover": turnover,
                "exposure": sum(current_weights.values()),
                "positions": len(current_weights),
            }
        )
    shadow_nav = pd.DataFrame(nav_rows)
    shadow_weights = pd.DataFrame(weight_rows)
    shadow_nav.to_csv(out_dir / "position_mapping_shadow_nav.csv", index=False, encoding="utf-8-sig")
    shadow_weights.to_csv(out_dir / "position_mapping_shadow_weights.csv", index=False, encoding="utf-8-sig")
    source_perf = {}
    if summary_path.exists():
        try:
            source_perf = json.loads(summary_path.read_text(encoding="utf-8")).get("perf", {})
        except Exception:
            source_perf = {}
    shadow_perf = _nav_metrics(shadow_nav)
    compare = {
        "mapping": RISK_TIER_MULTIPLIERS,
        "source_perf": source_perf,
        "shadow_perf": shadow_perf,
        "deltas": {
            "cagr": shadow_perf.get("cagr", 0.0) - float(source_perf.get("cagr", 0.0) or 0.0),
            "max_drawdown": shadow_perf.get("max_drawdown", 0.0) - float(source_perf.get("max_drawdown", 0.0) or 0.0),
            "total_return": shadow_perf.get("total_return", 0.0) - float(source_perf.get("total_return", 0.0) or 0.0),
        },
        "missing_tier_count": missing_tier_count,
    }
    (out_dir / "position_mapping_shadow_summary.json").write_text(
        json.dumps(sanitize_json(compare), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Position Mapping Shadow",
        "",
        "## Mapping",
        "",
        *(f"- {key}: {value}" for key, value in RISK_TIER_MULTIPLIERS.items()),
        "",
        "## Source Perf",
        "",
        *(f"- {key}: {value}" for key, value in source_perf.items() if key in {"total_return", "cagr", "sharpe", "max_drawdown", "calmar", "total_turnover"}),
        "",
        "## Shadow Perf",
        "",
        *(f"- {key}: {value}" for key, value in shadow_perf.items()),
    ]
    (out_dir / "position_mapping_shadow_summary.md").write_text("\n".join(lines), encoding="utf-8")
    return compare


def run_attribution(window: str, variant: str, *, output_root: Path = OUT_ROOT) -> dict[str, Any]:
    source = _source_dir(variant, window)
    source_entries = _load_source_entries(source)
    symbols = sorted(source_entries["symbol"].dropna().map(normalize_symbol).unique().tolist())
    if source_entries.empty:
        raise ValueError(f"no source entries found: {source}")
    start = pd.to_datetime(source_entries["date"]).min().date().isoformat()
    end = pd.to_datetime(source_entries["date"]).max().date().isoformat()
    with pg_env.connect(config_path="backend/configs/pams_cn_pg.json", autocommit=True, connect_timeout=10) as conn:
        prices = _load_prices(conn, symbols, start, end)
    entries = build_entry_attribution(source, prices)
    single_cols = [
        "membership_bucket",
        "ret120_bucket",
        "ret20_bucket",
        "accel_bucket",
        "ma_distance_bucket",
        "vol20_bucket",
        "drawdown60_bucket",
        "turnover_bucket",
    ]
    single = pd.concat(
        [_summarize(entries, [column]).assign(factor=column).rename(columns={column: "bucket"}) for column in single_cols],
        ignore_index=True,
    )
    pair_defs = [
        ["membership_bucket", "ret120_bucket"],
        ["membership_bucket", "ma_distance_bucket"],
        ["ret120_bucket", "accel_bucket"],
        ["ma_distance_bucket", "vol20_bucket"],
        ["drawdown60_bucket", "ret20_bucket"],
    ]
    pair = pd.concat(
        [_summarize(entries, cols).assign(pair=" x ".join(cols)) for cols in pair_defs],
        ignore_index=True,
    )
    risk_tier = _summarize(entries, ["entry_risk_tier"])
    risk_pattern = _summarize(entries, ["entry_risk_labels"])
    out_dir = output_root / variant / window
    out_dir.mkdir(parents=True, exist_ok=True)
    entries.to_csv(out_dir / "entries.csv", index=False, encoding="utf-8-sig")
    single.to_csv(out_dir / "single_factor_summary.csv", index=False, encoding="utf-8-sig")
    pair.to_csv(out_dir / "pair_factor_summary.csv", index=False, encoding="utf-8-sig")
    risk_tier.to_csv(out_dir / "risk_tier_summary.csv", index=False, encoding="utf-8-sig")
    risk_pattern.to_csv(out_dir / "risk_pattern_summary.csv", index=False, encoding="utf-8-sig")
    position_shadow = run_position_mapping_shadow(source, entries, prices, out_dir)
    summary = {
        "study_id": STUDY_ID,
        "source_study": str(source),
        "variant": variant,
        "window": window,
        "entry_count": int(len(entries)),
        "symbol_count": int(entries["symbol"].nunique()) if not entries.empty else 0,
        "rules": {
            "buckets_use_future_data": False,
            "outcomes_are_labels_only": True,
            "no_industry_theme_or_market_state_inputs": True,
        },
        "top_single_bad_fwd60": single.loc[single["n"] >= 30].sort_values("fwd60_median").head(10).to_dict(orient="records"),
        "top_pair_bad_fwd60": pair.loc[pair["n"] >= 20].sort_values("fwd60_median").head(10).to_dict(orient="records"),
        "risk_tier_summary": risk_tier.to_dict(orient="records"),
        "top_risk_patterns": risk_pattern.loc[risk_pattern["n"] >= 20]
        .sort_values("fwd60_median")
        .head(10)
        .to_dict(orient="records"),
        "position_mapping_shadow": position_shadow,
    }
    (out_dir / "summary.json").write_text(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# {STUDY_ID} {variant} {window}",
        "",
        "## Contract",
        "",
        "- Buckets use entry-time price/liquidity/PIT membership only.",
        "- Future returns, MFE, MAE, and realized result are outcome labels only.",
        "- No industry, theme, or production market-state input.",
        "",
        f"- entries: {len(entries)}",
        f"- symbols: {entries['symbol'].nunique() if not entries.empty else 0}",
        "",
        "## Worst Single Buckets By 60D Median Forward Return",
        "",
        single.loc[single["n"] >= 30].sort_values("fwd60_median").head(12).to_markdown(index=False),
        "",
        "## Worst Pair Buckets By 60D Median Forward Return",
        "",
        pair.loc[pair["n"] >= 20].sort_values("fwd60_median").head(12).to_markdown(index=False),
        "",
        "## Composite Risk Tier",
        "",
        risk_tier.to_markdown(index=False),
        "",
        "## Worst Composite Risk Patterns",
        "",
        risk_pattern.loc[risk_pattern["n"] >= 20].sort_values("fwd60_median").head(12).to_markdown(index=False),
    ]
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    return {"output_dir": str(out_dir), "summary": summary}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Entry quality attribution for simple CSI1000 trend rebuild")
    parser.add_argument("--window", default="1626", choices=["1626", "1217", "1226"])
    parser.add_argument("--variant", default="plain", choices=["plain", "market_2of3_ma120"])
    args = parser.parse_args(argv)
    result = run_attribution(args.window, args.variant)
    print(json.dumps(sanitize_json(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
