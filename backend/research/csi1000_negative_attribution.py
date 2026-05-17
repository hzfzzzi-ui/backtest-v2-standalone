from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from psycopg.rows import dict_row

from backend.api.shared.json_utils import sanitize_json
from backend.core.data import pg_env

STUDY_ID = "v10/hs300_zz500_csi1000_pit_pool_expansion_v1"
INDEX_CSI800 = "000906.SH"
INDEX_CSI1000 = "000852.SH"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _outputs_root() -> Path:
    return (_repo_root() / "outputs").resolve()


def _experiment_dir(exp_id: str, *, outputs_root: Path | None = None) -> Path:
    root = outputs_root or _outputs_root()
    path = (root / "experiments" / str(exp_id)).resolve()
    if not path.exists():
        raise FileNotFoundError(f"experiment not found: {path}")
    return path


def _study_output_dir(output_dir: str | Path | None = None) -> Path:
    if output_dir:
        return Path(output_dir).resolve()
    return (_outputs_root() / "studies" / "v10" / "hs300_zz500_csi1000_pit_pool_expansion_v1" / "negative_attribution").resolve()


def normalize_symbol(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace(".", "").replace("_", "").lower()
    if len(text) == 8 and text[:2] in {"sh", "sz", "bj"}:
        return text
    if len(text) == 8 and text[-2:] in {"sh", "sz", "bj"}:
        return text[-2:] + text[:6]
    if len(text) == 6 and text[0] in {"0", "2", "3"}:
        return "sz" + text
    if len(text) == 6 and text[0] in {"6", "5", "9"}:
        return "sh" + text
    return text


def to_ts_code(symbol: Any) -> str:
    value = normalize_symbol(symbol)
    if len(value) == 8 and value[:2] in {"sh", "sz", "bj"}:
        suffix = {"sh": "SH", "sz": "SZ", "bj": "BJ"}[value[:2]]
        return f"{value[2:]}.{suffix}"
    return str(symbol or "").strip()


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return payload if isinstance(payload, dict) else {}


def _parse_bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def _parse_meta(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        payload = json.loads(value)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _query_frame(conn: Any, sql: str, params: tuple[Any, ...]) -> pd.DataFrame:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return pd.DataFrame(rows)


def _load_membership_intervals(conn: Any, symbols: list[str]) -> pd.DataFrame:
    ts_symbols = sorted({to_ts_code(symbol) for symbol in symbols if to_ts_code(symbol)})
    if not ts_symbols:
        return pd.DataFrame(columns=["symbol", "index_code", "start_date", "end_date"])
    frame = _query_frame(
        conn,
        """
        SELECT index_code, symbol, start_date, COALESCE(end_date, DATE '9999-12-31') AS end_date
        FROM public.pit_index_constituents
        WHERE index_code IN (%s, %s)
          AND symbol = ANY(%s)
        """,
        (INDEX_CSI800, INDEX_CSI1000, ts_symbols),
    )
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "index_code", "start_date", "end_date"])
    frame["symbol"] = frame["symbol"].map(normalize_symbol)
    frame["start_date"] = pd.to_datetime(frame["start_date"])
    frame["end_date"] = pd.to_datetime(frame["end_date"])
    return frame


def _load_industry_intervals(conn: Any, symbols: list[str]) -> pd.DataFrame:
    query_symbols = sorted({normalize_symbol(symbol) for symbol in symbols if normalize_symbol(symbol)})
    query_symbols.extend(to_ts_code(symbol) for symbol in symbols if to_ts_code(symbol))
    query_symbols = sorted({item for item in query_symbols if item})
    if not query_symbols:
        return pd.DataFrame(columns=["symbol", "industry_l1", "start_date", "end_date"])
    frame = _query_frame(
        conn,
        """
        SELECT ts_code, industry_l1, start_date, COALESCE(end_date, DATE '9999-12-31') AS end_date
        FROM public.pit_industry_history
        WHERE ts_code = ANY(%s)
        """,
        (query_symbols,),
    )
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "industry_l1", "start_date", "end_date"])
    frame["symbol"] = frame["ts_code"].map(normalize_symbol)
    frame["industry_l1"] = frame["industry_l1"].fillna("").astype(str)
    frame["start_date"] = pd.to_datetime(frame["start_date"])
    frame["end_date"] = pd.to_datetime(frame["end_date"])
    return frame.loc[:, ["symbol", "industry_l1", "start_date", "end_date"]]


def _load_daily_features(conn: Any, symbols: list[str], *, start: str, end: str) -> pd.DataFrame:
    query_symbols = sorted({normalize_symbol(symbol) for symbol in symbols if normalize_symbol(symbol)})
    if not query_symbols:
        return pd.DataFrame(columns=["symbol", "date", "avg_turnover_20d", "avg_turnover_rate_20d", "circ_mv"])
    preload_start = (pd.to_datetime(start) - pd.Timedelta(days=90)).date().isoformat()
    frame = _query_frame(
        conn,
        """
        SELECT symbol, trade_date, turnover, turnover_rate_f, circ_mv
        FROM public.pams_ohlcv_daily_v2
        WHERE symbol = ANY(%s)
          AND trade_date BETWEEN %s AND %s
        ORDER BY symbol, trade_date
        """,
        (query_symbols, preload_start, end),
    )
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "date", "avg_turnover_20d", "avg_turnover_rate_20d", "circ_mv"])
    frame["symbol"] = frame["symbol"].map(normalize_symbol)
    frame["date"] = pd.to_datetime(frame["trade_date"])
    for column in ("turnover", "turnover_rate_f", "circ_mv"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.sort_values(["symbol", "date"]).reset_index(drop=True)
    frame["avg_turnover_20d"] = frame.groupby("symbol")["turnover"].transform(lambda s: s.rolling(20, min_periods=1).mean())
    frame["avg_turnover_rate_20d"] = frame.groupby("symbol")["turnover_rate_f"].transform(lambda s: s.rolling(20, min_periods=1).mean())
    frame = frame.loc[frame["date"].between(pd.to_datetime(start), pd.to_datetime(end))]
    return frame.loc[:, ["symbol", "date", "turnover", "turnover_rate_f", "avg_turnover_20d", "avg_turnover_rate_20d", "circ_mv"]]


def _interval_lookup(frame: pd.DataFrame, *, value_col: str, default: str = "") -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]]:
    out: dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]] = defaultdict(list)
    if frame.empty:
        return out
    for row in frame.itertuples(index=False):
        out[str(row.symbol)].append((pd.Timestamp(row.start_date), pd.Timestamp(row.end_date), str(getattr(row, value_col) or "")))
    return out


def _membership_lookup(frame: pd.DataFrame) -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]]:
    return _interval_lookup(frame, value_col="index_code")


def classify_membership(symbol: Any, as_of: Any, intervals: dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]]) -> str:
    key = normalize_symbol(symbol)
    date_value = pd.to_datetime(as_of, errors="coerce")
    if not key or pd.isna(date_value):
        return "unclassified"
    active = {
        index_code
        for start, end, index_code in intervals.get(key, [])
        if start <= date_value <= end
    }
    csi800 = INDEX_CSI800 in active
    csi1000 = INDEX_CSI1000 in active
    if csi1000 and not csi800:
        return "csi1000_new"
    if csi1000 and csi800:
        return "overlap"
    if csi800:
        return "csi800_only"
    return "unclassified"


def _lookup_interval_value(symbol: Any, as_of: Any, intervals: dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]], default: str = "") -> str:
    key = normalize_symbol(symbol)
    date_value = pd.to_datetime(as_of, errors="coerce")
    if not key or pd.isna(date_value):
        return default
    for start, end, value in intervals.get(key, []):
        if start <= date_value <= end:
            return value or default
    return default


def _liquidity_bucket(value: Any) -> str:
    amount = _to_float(value, np.nan)
    if pd.isna(amount):
        return "unknown"
    if amount < 100_000_000:
        return "<100m"
    if amount < 200_000_000:
        return "100-200m"
    if amount < 500_000_000:
        return "200-500m"
    return ">=500m"


def _market_cap_bucket(value: Any) -> str:
    circ_mv = _to_float(value, np.nan)
    if pd.isna(circ_mv):
        return "unknown"
    yi_cny = circ_mv / 10000.0
    if yi_cny < 50:
        return "<50yi"
    if yi_cny < 100:
        return "50-100yi"
    if yi_cny < 200:
        return "100-200yi"
    return ">=200yi"


def _rank_bucket(value: Any) -> str:
    pct = _to_float(value, np.nan)
    if pd.isna(pct):
        return "unknown"
    if pct <= 0.1:
        return "top_10pct"
    if pct <= 0.2:
        return "top_10_20pct"
    if pct <= 0.5:
        return "top_20_50pct"
    return "bottom_50pct"


def _load_trade_frame(exp_dir: Path) -> pd.DataFrame:
    trades = _read_csv(exp_dir / "portfolio_trades.csv")
    if trades.empty:
        return trades
    trades["symbol"] = trades["symbol"].map(normalize_symbol)
    trades["date"] = pd.to_datetime(trades["date"])
    trades["side"] = trades["side"].astype(str).str.upper()
    trades["qty"] = pd.to_numeric(trades["qty"], errors="coerce").fillna(0.0)
    for column in ("value", "commission", "stamp_tax", "slippage", "net_amount", "price", "fill_price"):
        trades[column] = pd.to_numeric(trades.get(column), errors="coerce").fillna(0.0)
    trades["_meta"] = trades.get("meta_json", pd.Series(dtype=str)).map(_parse_meta)
    trades["signal_date"] = trades["_meta"].map(lambda item: item.get("signal_date") or "")
    trades["entry_date_resolved"] = trades.apply(
        lambda row: row["date"] if row["side"] == "BUY" else pd.to_datetime(row.get("entry_date") or row["date"], errors="coerce"),
        axis=1,
    )
    return trades


def _load_symbol_performance(exp_dir: Path) -> pd.DataFrame:
    perf = _read_csv(exp_dir / "symbol_performance.csv")
    if perf.empty:
        return perf
    perf["symbol"] = perf["symbol"].map(normalize_symbol)
    for column in ("return_pct", "max_drawdown", "net_pnl", "realized_pnl", "unrealized_approx_pnl", "trades", "buy_notional"):
        perf[column] = pd.to_numeric(perf.get(column), errors="coerce").fillna(0.0)
    return perf


def _load_candidate_frame(exp_dir: Path) -> pd.DataFrame:
    path = exp_dir / "candidate_signals.csv"
    candidates = _read_csv(path)
    if candidates.empty:
        candidates = _read_csv(exp_dir / "score_diagnostics.csv")
    if candidates.empty:
        return candidates
    candidates["symbol"] = candidates["symbol"].map(normalize_symbol)
    candidates["date"] = pd.to_datetime(candidates["date"])
    if "selected_flag" in candidates.columns:
        candidates["selected_flag"] = _parse_bool_series(candidates["selected_flag"])
    else:
        candidates["selected_flag"] = False
    if "cash_blocked_flag" in candidates.columns:
        candidates["cash_blocked_flag"] = _parse_bool_series(candidates["cash_blocked_flag"])
    else:
        candidates["cash_blocked_flag"] = False
    if "final_score_rank" in candidates.columns:
        candidates["rank"] = pd.to_numeric(candidates["final_score_rank"], errors="coerce")
    elif "candidate_rank" in candidates.columns:
        candidates["rank"] = pd.to_numeric(candidates["candidate_rank"], errors="coerce")
    else:
        candidates["rank"] = np.nan
    candidates["candidate_count"] = candidates.groupby("date")["symbol"].transform("nunique")
    candidates["rank_pct"] = candidates["rank"] / candidates["candidate_count"].replace(0, np.nan)
    candidates["rank_pct_bucket"] = candidates["rank_pct"].map(_rank_bucket)
    return candidates


def _build_first_buy_features(trades: pd.DataFrame, candidates: pd.DataFrame, feature_frame: pd.DataFrame, membership_intervals: dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]], industry_intervals: dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]]) -> pd.DataFrame:
    buys = trades.loc[trades["side"] == "BUY"].copy()
    if buys.empty:
        return pd.DataFrame()
    buys["signal_date_dt"] = pd.to_datetime(buys["signal_date"], errors="coerce")
    buys["feature_date"] = buys["signal_date_dt"].fillna(buys["date"])
    buys["final_score_rank_meta"] = buys["_meta"].map(lambda item: _to_float(item.get("final_score_rank"), np.nan))
    buys["final_score_value_meta"] = buys["_meta"].map(lambda item: _to_float(item.get("final_score_value") or item.get("final_score"), np.nan))
    count_by_date = candidates.groupby("date")["symbol"].nunique().rename("candidate_count").reset_index() if not candidates.empty else pd.DataFrame(columns=["date", "candidate_count"])
    buys = buys.merge(count_by_date, left_on="signal_date_dt", right_on="date", how="left", suffixes=("", "_candidate"))
    buys["rank_pct"] = buys["final_score_rank_meta"] / buys["candidate_count"].replace(0, np.nan)
    buys["rank_pct_bucket"] = buys["rank_pct"].map(_rank_bucket)
    feature_merge = feature_frame.copy()
    if not feature_merge.empty:
        buys = buys.merge(
            feature_merge,
            left_on=["symbol", "feature_date"],
            right_on=["symbol", "date"],
            how="left",
            suffixes=("", "_feature"),
        )
    buys["membership_bucket"] = buys.apply(lambda row: classify_membership(row["symbol"], row["feature_date"], membership_intervals), axis=1)
    buys["industry_l1"] = buys.apply(lambda row: _lookup_interval_value(row["symbol"], row["feature_date"], industry_intervals, "unknown"), axis=1)
    buys["liquidity_bucket"] = buys["avg_turnover_20d"].map(_liquidity_bucket) if "avg_turnover_20d" in buys.columns else "unknown"
    buys["market_cap_bucket"] = buys["circ_mv"].map(_market_cap_bucket) if "circ_mv" in buys.columns else "unknown"
    buys = buys.sort_values(["symbol", "date"]).drop_duplicates("symbol", keep="first")
    return buys.loc[
        :,
        [
            "symbol",
            "date",
            "feature_date",
            "membership_bucket",
            "industry_l1",
            "liquidity_bucket",
            "market_cap_bucket",
            "rank_pct_bucket",
            "rank_pct",
            "final_score_rank_meta",
            "final_score_value_meta",
            "avg_turnover_20d",
            "avg_turnover_rate_20d",
            "circ_mv",
        ],
    ]


def _aggregate_symbols(symbol_perf: pd.DataFrame, first_buy_features: pd.DataFrame, by: str) -> pd.DataFrame:
    if symbol_perf.empty:
        return pd.DataFrame()
    merged = symbol_perf.merge(first_buy_features, on="symbol", how="left")
    if by not in merged.columns:
        merged[by] = "unknown"
    merged[by] = merged[by].fillna("unknown").astype(str).replace("", "unknown")
    grouped = merged.groupby(by, dropna=False).agg(
        symbol_count=("symbol", "nunique"),
        trades=("trades", "sum"),
        buy_notional=("buy_notional", "sum"),
        net_pnl=("net_pnl", "sum"),
        realized_pnl=("realized_pnl", "sum"),
        unrealized_approx_pnl=("unrealized_approx_pnl", "sum"),
        mean_return_pct=("return_pct", "mean"),
        median_return_pct=("return_pct", "median"),
        mean_symbol_max_drawdown=("max_drawdown", "mean"),
    ).reset_index()
    grouped["net_pnl_per_buy_notional"] = grouped["net_pnl"] / grouped["buy_notional"].replace(0, np.nan)
    return grouped.sort_values("net_pnl", ascending=True).reset_index(drop=True)


def _build_exit_events(trades: pd.DataFrame, first_buy_features: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    lots: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    events: list[dict[str, Any]] = []
    feature_by_symbol = first_buy_features.set_index("symbol").to_dict("index") if not first_buy_features.empty else {}
    ordered = trades.sort_values(["date"]).reset_index(drop=True)
    for row in ordered.itertuples(index=False):
        symbol = str(row.symbol)
        qty = _to_float(row.qty)
        if qty <= 0:
            continue
        if row.side == "BUY":
            lots[symbol].append({"qty": qty, "cost": _to_float(row.net_amount), "entry_date": row.date})
            continue
        remaining = qty
        realized = 0.0
        matched_cost = 0.0
        while remaining > 0 and lots[symbol]:
            lot = lots[symbol][0]
            matched_qty = min(remaining, lot["qty"])
            unit_cost = lot["cost"] / lot["qty"] if lot["qty"] else 0.0
            matched_cost += matched_qty * unit_cost
            lot["qty"] -= matched_qty
            lot["cost"] -= matched_qty * unit_cost
            remaining -= matched_qty
            if lot["qty"] <= 1e-9:
                lots[symbol].popleft()
        realized = _to_float(row.net_amount) - matched_cost
        features = feature_by_symbol.get(symbol, {})
        events.append(
            {
                "date": row.date,
                "symbol": symbol,
                "exit_reason": str(getattr(row, "reason_code", "") or getattr(row, "triggered_rule", "") or "unknown"),
                "qty": qty,
                "sell_net_amount": _to_float(row.net_amount),
                "matched_cost": matched_cost,
                "realized_pnl": realized,
                "realized_return_pct": realized / matched_cost if matched_cost > 0 else np.nan,
                "commission": _to_float(row.commission),
                "stamp_tax": _to_float(row.stamp_tax),
                "slippage": _to_float(row.slippage),
                **{key: features.get(key, "unknown") for key in ("membership_bucket", "industry_l1", "liquidity_bucket", "market_cap_bucket", "rank_pct_bucket")},
            }
        )
    return pd.DataFrame(events)


def _aggregate_exits(exit_events: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    if exit_events.empty:
        return pd.DataFrame()
    grouped = exit_events.groupby(by, dropna=False).agg(
        exit_count=("symbol", "count"),
        symbol_count=("symbol", "nunique"),
        sell_net_amount=("sell_net_amount", "sum"),
        matched_cost=("matched_cost", "sum"),
        realized_pnl=("realized_pnl", "sum"),
        mean_realized_return_pct=("realized_return_pct", "mean"),
        commission=("commission", "sum"),
        stamp_tax=("stamp_tax", "sum"),
        slippage=("slippage", "sum"),
    ).reset_index()
    grouped["cost_drag"] = grouped["commission"] + grouped["stamp_tax"] + grouped["slippage"]
    return grouped.sort_values("realized_pnl", ascending=True).reset_index(drop=True)


def _enrich_candidates(candidates: pd.DataFrame, feature_frame: pd.DataFrame, membership_intervals: dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]], industry_intervals: dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]]) -> pd.DataFrame:
    if candidates.empty:
        return candidates
    enriched = candidates.copy()
    if not feature_frame.empty:
        enriched = enriched.merge(feature_frame, on=["symbol", "date"], how="left")
    enriched["membership_bucket"] = enriched.apply(lambda row: classify_membership(row["symbol"], row["date"], membership_intervals), axis=1)
    enriched["industry_l1"] = enriched.apply(lambda row: _lookup_interval_value(row["symbol"], row["date"], industry_intervals, "unknown"), axis=1)
    enriched["liquidity_bucket"] = enriched["avg_turnover_20d"].map(_liquidity_bucket) if "avg_turnover_20d" in enriched.columns else "unknown"
    enriched["market_cap_bucket"] = enriched["circ_mv"].map(_market_cap_bucket) if "circ_mv" in enriched.columns else "unknown"
    return enriched


def _candidate_funnel(candidates: pd.DataFrame, by: str, selected_features: pd.DataFrame | None = None) -> pd.DataFrame:
    if candidates.empty and (selected_features is None or selected_features.empty):
        return pd.DataFrame()
    frame = candidates.copy() if not candidates.empty else pd.DataFrame(columns=[by, "symbol", "selected_flag", "cash_blocked_flag", "rank_pct"])
    if by not in frame.columns:
        frame[by] = "unknown"
    grouped = frame.groupby(by, dropna=False).agg(
        candidate_rows=("symbol", "count"),
        unique_symbols=("symbol", "nunique"),
        selected_rows=("selected_flag", "sum"),
        cash_blocked_rows=("cash_blocked_flag", "sum"),
        mean_rank_pct=("rank_pct", "mean"),
        median_rank_pct=("rank_pct", "median"),
    ).reset_index()
    if selected_features is not None and not selected_features.empty:
        selected = selected_features.copy()
        if by not in selected.columns:
            selected[by] = "unknown"
        selected_grouped = selected.groupby(by, dropna=False).agg(
            buy_rows=("symbol", "count"),
            buy_symbols=("symbol", "nunique"),
        ).reset_index()
        grouped = grouped.merge(selected_grouped, on=by, how="outer")
    for column in ("candidate_rows", "unique_symbols", "selected_rows", "cash_blocked_rows", "buy_rows", "buy_symbols"):
        if column in grouped.columns:
            grouped[column] = pd.to_numeric(grouped[column], errors="coerce").fillna(0)
    if "buy_rows" not in grouped.columns:
        grouped["buy_rows"] = 0
    if "buy_symbols" not in grouped.columns:
        grouped["buy_symbols"] = 0
    grouped["selected_rows_with_buys"] = grouped["selected_rows"] + grouped["buy_rows"]
    grouped["selected_rate"] = grouped["selected_rows_with_buys"] / (grouped["candidate_rows"] + grouped["buy_rows"]).replace(0, np.nan)
    grouped["cash_blocked_rate"] = grouped["cash_blocked_rows"] / grouped["candidate_rows"].replace(0, np.nan)
    return grouped.sort_values(["selected_rows_with_buys", "candidate_rows"], ascending=[False, False]).reset_index(drop=True)


def _load_perf(exp_dir: Path) -> dict[str, Any]:
    return _read_json(exp_dir / "perf.json")


def _top_records(frame: pd.DataFrame, limit: int = 8) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return sanitize_json(frame.head(limit).replace({np.nan: None}).to_dict(orient="records"))


def _write_frame(path: Path, frame: pd.DataFrame) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.replace({np.nan: None}).to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_json(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _write_report(path: Path, summary: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    direct = summary.get("direct_contribution", {})
    lines = [
        "# CSI1000 PIT stock-pool expansion negative attribution",
        "",
        f"- baseline_exp_id: `{summary.get('baseline_exp_id')}`",
        f"- candidate_exp_id: `{summary.get('candidate_exp_id')}`",
        f"- generated_at: `{summary.get('generated_at')}`",
        "",
        "## Core Read",
        "",
        str(summary.get("core_read") or ""),
        "",
        "## Direct Contribution",
        "",
        f"- A1 total net_pnl: `{direct.get('candidate_total_net_pnl')}`",
        f"- B0 total net_pnl: `{direct.get('baseline_total_net_pnl')}`",
        f"- A1 csi1000_new net_pnl: `{direct.get('candidate_csi1000_new_net_pnl')}`",
        f"- A1 csi1000_new buy_notional: `{direct.get('candidate_csi1000_new_buy_notional')}`",
        "",
        "## Top Negative Groups",
        "",
    ]
    for key in ("membership", "industry", "liquidity", "market_cap", "rank_pct", "exit_reason"):
        rows = summary.get("top_negative", {}).get(key, [])
        lines.append(f"### {key}")
        if not rows:
            lines.append("- no rows")
        for row in rows[:5]:
            label = row.get(key) or row.get("membership_bucket") or row.get("industry_l1") or row.get("exit_reason") or row.get("rank_pct_bucket") or row.get("liquidity_bucket") or row.get("market_cap_bucket")
            value = row.get("net_pnl", row.get("realized_pnl"))
            lines.append(f"- {label}: pnl `{value}`, symbols `{row.get('symbol_count')}`")
        lines.append("")
    lines.extend(
        [
            "## Limits",
            "",
            "- This is a 2016-2026 main-window attribution only.",
            "- It uses existing experiment artifacts and PIT metadata; it does not rerun or mutate the backtest.",
            "- It identifies likely drag sources, not a baseline promotion path.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def run_negative_attribution(
    *,
    baseline_exp_id: str,
    candidate_exp_id: str,
    output_dir: str | Path | None = None,
    config_path: str | Path | None = "backend/configs/pams_cn_pg.json",
) -> dict[str, Any]:
    output_root = _study_output_dir(output_dir)
    baseline_dir = _experiment_dir(baseline_exp_id)
    candidate_dir = _experiment_dir(candidate_exp_id)

    candidate_trades = _load_trade_frame(candidate_dir)
    baseline_symbol_perf = _load_symbol_performance(baseline_dir)
    candidate_symbol_perf = _load_symbol_performance(candidate_dir)
    candidate_candidates = _load_candidate_frame(candidate_dir)
    baseline_candidates = _load_candidate_frame(baseline_dir)
    all_symbols = sorted(
        {
            *candidate_trades.get("symbol", pd.Series(dtype=str)).dropna().astype(str).tolist(),
            *candidate_symbol_perf.get("symbol", pd.Series(dtype=str)).dropna().astype(str).tolist(),
            *baseline_symbol_perf.get("symbol", pd.Series(dtype=str)).dropna().astype(str).tolist(),
            *candidate_candidates.get("symbol", pd.Series(dtype=str)).dropna().astype(str).tolist(),
            *baseline_candidates.get("symbol", pd.Series(dtype=str)).dropna().astype(str).tolist(),
        }
    )

    start = "2016-01-04"
    end = "2026-03-01"
    with pg_env.connect(config_path=config_path, root=_repo_root(), autocommit=True, row_factory=dict_row, connect_timeout=10) as conn:
        membership_frame = _load_membership_intervals(conn, all_symbols)
        industry_frame = _load_industry_intervals(conn, all_symbols)
        feature_frame = _load_daily_features(conn, all_symbols, start=start, end=end)

    membership_intervals = _membership_lookup(membership_frame)
    industry_intervals = _interval_lookup(industry_frame, value_col="industry_l1", default="unknown")
    candidate_features = _build_first_buy_features(candidate_trades, candidate_candidates, feature_frame, membership_intervals, industry_intervals)
    enriched_candidates = _enrich_candidates(candidate_candidates, feature_frame, membership_intervals, industry_intervals)
    exit_events = _build_exit_events(candidate_trades, candidate_features)

    grouped = {
        "membership": _aggregate_symbols(candidate_symbol_perf, candidate_features, "membership_bucket"),
        "industry": _aggregate_symbols(candidate_symbol_perf, candidate_features, "industry_l1"),
        "liquidity": _aggregate_symbols(candidate_symbol_perf, candidate_features, "liquidity_bucket"),
        "market_cap": _aggregate_symbols(candidate_symbol_perf, candidate_features, "market_cap_bucket"),
        "rank_pct": _aggregate_symbols(candidate_symbol_perf, candidate_features, "rank_pct_bucket"),
        "exit_reason": _aggregate_exits(exit_events, ["exit_reason"]),
        "exit_by_membership": _aggregate_exits(exit_events, ["membership_bucket", "exit_reason"]),
        "candidate_funnel_membership": _candidate_funnel(enriched_candidates, "membership_bucket", candidate_features),
        "candidate_funnel_rank": _candidate_funnel(enriched_candidates, "rank_pct_bucket", candidate_features),
    }
    output_paths: dict[str, str] = {}
    for name, frame in grouped.items():
        output_paths[name] = _write_frame(output_root / f"{name}.csv", frame)
    output_paths["symbol_features"] = _write_frame(output_root / "candidate_symbol_features.csv", candidate_features)
    output_paths["exit_events"] = _write_frame(output_root / "exit_events.csv", exit_events)

    baseline_total = float(baseline_symbol_perf["net_pnl"].sum()) if not baseline_symbol_perf.empty else 0.0
    candidate_total = float(candidate_symbol_perf["net_pnl"].sum()) if not candidate_symbol_perf.empty else 0.0
    membership_group = grouped["membership"]
    csi1000_row = membership_group.loc[membership_group["membership_bucket"].eq("csi1000_new")] if not membership_group.empty else pd.DataFrame()
    csi1000_net = float(csi1000_row["net_pnl"].sum()) if not csi1000_row.empty else 0.0
    csi1000_notional = float(csi1000_row["buy_notional"].sum()) if not csi1000_row.empty else 0.0
    csi1000_symbols = int(csi1000_row["symbol_count"].sum()) if not csi1000_row.empty else 0
    core_read = (
        "A1 underperformance should be attributed primarily to directly traded CSI1000-new symbols "
        if csi1000_net < 0 and abs(csi1000_net) > abs(candidate_total - baseline_total) * 0.25
        else "A1 underperformance is not explained by direct CSI1000-new symbol PnL alone; displacement and exit-stage evidence matter. "
    )
    if not grouped["exit_reason"].empty:
        worst_exit = grouped["exit_reason"].iloc[0]
        core_read += f"Worst exit reason is {worst_exit.get('exit_reason')} with realized_pnl={worst_exit.get('realized_pnl')}."

    summary = sanitize_json(
        {
            "study_id": STUDY_ID,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "baseline_exp_id": baseline_exp_id,
            "candidate_exp_id": candidate_exp_id,
            "baseline_perf": _load_perf(baseline_dir),
            "candidate_perf": _load_perf(candidate_dir),
            "data_contract": {
                "membership_source": "public.pit_index_constituents",
                "industry_source": "public.pit_industry_history",
                "feature_source": "public.pams_ohlcv_daily_v2",
                "liquidity_metric": "avg_turnover_20d",
                "market_cap_metric": "circ_mv as 10k CNY, bucketed as CNY yi",
                "rank_metric": "final_score_rank / same-day candidate_count",
            },
            "direct_contribution": {
                "baseline_total_net_pnl": baseline_total,
                "candidate_total_net_pnl": candidate_total,
                "candidate_minus_baseline_net_pnl": candidate_total - baseline_total,
                "candidate_csi1000_new_net_pnl": csi1000_net,
                "candidate_csi1000_new_buy_notional": csi1000_notional,
                "candidate_csi1000_new_symbol_count": csi1000_symbols,
            },
            "top_negative": {
                "membership": _top_records(grouped["membership"]),
                "industry": _top_records(grouped["industry"]),
                "liquidity": _top_records(grouped["liquidity"]),
                "market_cap": _top_records(grouped["market_cap"]),
                "rank_pct": _top_records(grouped["rank_pct"]),
                "exit_reason": _top_records(grouped["exit_reason"]),
            },
            "candidate_funnel": {
                "membership": _top_records(grouped["candidate_funnel_membership"]),
                "rank_pct": _top_records(grouped["candidate_funnel_rank"]),
            },
            "core_read": core_read,
            "outputs": output_paths,
        }
    )
    output_paths["summary"] = _write_json(output_root / "summary.json", summary)
    output_paths["report"] = _write_report(output_root / "negative_attribution_report.md", summary)
    summary["outputs"] = output_paths
    _write_json(output_root / "summary.json", summary)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CSI1000 stock-pool negative attribution")
    parser.add_argument("--baseline-exp-id", required=True)
    parser.add_argument("--candidate-exp-id", required=True)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--config-path", default="backend/configs/pams_cn_pg.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    summary = run_negative_attribution(
        baseline_exp_id=args.baseline_exp_id,
        candidate_exp_id=args.candidate_exp_id,
        output_dir=args.output_dir or None,
        config_path=args.config_path,
    )
    print(json.dumps({"ok": True, "summary": summary.get("outputs", {}).get("summary")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
