from __future__ import annotations

import json
import os
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover
    psycopg = None
    dict_row = None

try:
    from backend.core.universe.ingest_universe import SW_L1_INDEX_MAP
except Exception:  # pragma: no cover
    SW_L1_INDEX_MAP = {
        "农林牧渔": "801010.SI",
        "基础化工": "801030.SI",
        "钢铁": "801040.SI",
        "有色金属": "801050.SI",
        "电子": "801080.SI",
        "汽车": "801880.SI",
        "家用电器": "801110.SI",
        "食品饮料": "801120.SI",
        "纺织服饰": "801130.SI",
        "轻工制造": "801140.SI",
        "医药生物": "801150.SI",
        "公用事业": "801160.SI",
        "交通运输": "801170.SI",
        "房地产": "801180.SI",
        "商贸零售": "801200.SI",
        "社会服务": "801210.SI",
        "银行": "801780.SI",
        "非银金融": "801790.SI",
        "综合": "801230.SI",
        "建筑材料": "801710.SI",
        "建筑装饰": "801720.SI",
        "电力设备": "801730.SI",
        "机械设备": "801890.SI",
        "国防军工": "801740.SI",
        "计算机": "801750.SI",
        "传媒": "801760.SI",
        "通信": "801770.SI",
        "煤炭": "801950.SI",
        "石油石化": "801960.SI",
        "环保": "801970.SI",
        "美容护理": "801980.SI",
    }


BASELINE_ID = "CN_STOCK_ETF_COMBO_BASELINE_V3"
STUDY_ID = "cn_stock_etf/v3_loss_top30_exit_reason_audit_v1"
STOCK_SLEEVE_ID = "stock_alpha_core"
BASELINE_DIR = Path("outputs/baselines") / BASELINE_ID
ATTR_DIR = Path("outputs/studies/cn_stock_etf/sr_20260510_v3_industry_theme_etf_index_attribution")
OUT_DIR = Path("outputs/studies/cn_stock_etf/sr_20260511_v3_loss_top30_exit_reason_audit")

BENCHMARKS = {
    "000001.SH": "上证指数",
    "000300.SH": "沪深300",
    "000905.SH": "中证500",
    "399006.SZ": "创业板指",
}

STOP_REASON_CODES = {"ATR_STOP_LOSS", "PRE_PROFIT_BREAKOUT_FAILURE_EXIT"}
RISK_REASON_CODES = {"RISK_OFF_EXIT"}


@dataclass
class Lot:
    symbol: str
    entry_date: pd.Timestamp
    qty_left: float
    qty_original: float
    net_cost: float
    fill_price: float
    reason_code: str
    meta: dict[str, Any]

    @property
    def cost_per_share(self) -> float:
        return self.net_cost / self.qty_original if self.qty_original else 0.0


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _abs(path: Path) -> Path:
    return (_repo_root() / path).resolve()


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(_abs(path), encoding="utf-8-sig", low_memory=False)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(_abs(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_env_file() -> dict[str, str]:
    env_path = _repo_root() / ".env"
    out: dict[str, str] = {}
    try:
        lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except FileNotFoundError:
        return out
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _db_settings() -> dict[str, Any]:
    file_env = _read_env_file()
    return {
        "host": os.environ.get("PAMS_PG_HOST") or file_env.get("PAMS_PG_HOST") or "127.0.0.1",
        "port": int(os.environ.get("PAMS_PG_PORT") or file_env.get("PAMS_PG_PORT") or "15432"),
        "dbname": os.environ.get("PAMS_PG_DB") or file_env.get("PAMS_PG_DB") or "pams",
        "user": os.environ.get("PAMS_PG_USER") or file_env.get("PAMS_PG_USER") or "pams",
        "password": (
            os.environ.get("PAMS_PG_PASSWORD")
            or file_env.get("PAMS_PG_PASSWORD")
            or os.environ.get("POSTGRES_PASSWORD")
            or file_env.get("POSTGRES_PASSWORD")
            or ""
        ),
    }


def _parse_meta(raw: Any) -> dict[str, Any]:
    if pd.isna(raw):
        return {}
    try:
        payload = json.loads(str(raw))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _to_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _fmt_pct(value: Any) -> str:
    num = _to_float(value)
    if num is None:
        return "-"
    return f"{num * 100:.2f}%"


def _fmt_money(value: Any) -> str:
    num = _to_float(value)
    if num is None:
        return "-"
    return f"{num:,.0f}"


def _load_stock_trades() -> pd.DataFrame:
    trades = _read_csv(BASELINE_DIR / "portfolio_trades.csv")
    if trades.empty:
        raise RuntimeError("missing V3 portfolio_trades.csv")
    trades = trades.loc[trades["sleeve_id"].astype(str).eq(STOCK_SLEEVE_ID)].copy()
    trades["date"] = pd.to_datetime(trades["date"], errors="coerce")
    for col in ["qty", "net_amount", "fill_price", "price", "value"]:
        trades[col] = pd.to_numeric(trades[col], errors="coerce")
    trades["_row_id"] = range(len(trades))
    trades.sort_values(["date", "_row_id"], inplace=True)
    return trades


def _reconstruct_closed_trades(trades: pd.DataFrame) -> pd.DataFrame:
    lots: dict[str, deque[Lot]] = defaultdict(deque)
    rows: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    for row in trades.itertuples(index=False):
        symbol = str(row.symbol)
        side = str(row.side)
        qty = float(row.qty or 0.0)
        net_amount = float(row.net_amount or 0.0)
        if side == "BUY":
            lots[symbol].append(
                Lot(
                    symbol=symbol,
                    entry_date=pd.Timestamp(row.date),
                    qty_left=qty,
                    qty_original=qty,
                    net_cost=net_amount,
                    fill_price=float(row.fill_price or row.price or 0.0),
                    reason_code=str(row.reason_code or ""),
                    meta=_parse_meta(row.meta_json),
                )
            )
            continue

        if side != "SELL":
            continue
        remaining = qty
        sell_proceeds_per_share = net_amount / qty if qty else 0.0
        sell_fill_price = float(row.fill_price or row.price or 0.0)
        while remaining > 1e-9 and lots[symbol]:
            lot = lots[symbol][0]
            matched_qty = min(remaining, lot.qty_left)
            buy_cost = lot.cost_per_share * matched_qty
            sell_proceeds = sell_proceeds_per_share * matched_qty
            pnl = sell_proceeds - buy_cost
            entry_meta = lot.meta
            rows.append(
                {
                    "symbol": symbol,
                    "entry_date": lot.entry_date,
                    "exit_date": pd.Timestamp(row.date),
                    "qty": matched_qty,
                    "buy_net_cost": buy_cost,
                    "sell_net_proceeds": sell_proceeds,
                    "realized_pnl": pnl,
                    "realized_return": (sell_proceeds / buy_cost - 1.0) if buy_cost else None,
                    "buy_fill_price": lot.fill_price,
                    "sell_fill_price": sell_fill_price,
                    "entry_reason_code": lot.reason_code,
                    "exit_reason_code": str(row.reason_code or ""),
                    "triggered_rule": str(row.triggered_rule or ""),
                    "break_streak": getattr(row, "break_streak", None),
                    "exit_owner": str(row.exit_owner or ""),
                    "entry_alpha_id": str(row.entry_alpha_id or ""),
                    "component_exp_id": str(row.component_exp_id or ""),
                    "entry_signal_date": entry_meta.get("signal_date"),
                    "breakout_margin_raw": entry_meta.get("breakout_margin_raw"),
                    "breakout_open_gap_raw": entry_meta.get("breakout_open_gap_raw"),
                    "breakout_fade_raw": entry_meta.get("breakout_fade_raw"),
                    "breakout_quality_score": entry_meta.get("breakout_quality_score"),
                    "residual_strength_score": entry_meta.get("residual_strength_score"),
                    "sector_strength_score": entry_meta.get("sector_strength_score"),
                    "volume_price_quality_score": entry_meta.get("volume_price_quality_score"),
                    "final_score": entry_meta.get("final_score"),
                    "final_score_rank": entry_meta.get("final_score_rank"),
                    "strong_risk_on_at_entry": entry_meta.get("strong_risk_on"),
                    "entry_meta": entry_meta,
                }
            )
            lot.qty_left -= matched_qty
            remaining -= matched_qty
            if lot.qty_left <= 1e-9:
                lots[symbol].popleft()
        if remaining > 1e-9:
            unmatched.append({"symbol": symbol, "date": row.date, "unmatched_qty": remaining})

    closed = pd.DataFrame(rows)
    if closed.empty:
        raise RuntimeError("no closed stock trades reconstructed")
    closed["hold_calendar_days"] = (closed["exit_date"] - closed["entry_date"]).dt.days
    closed["unmatched_sell_lots"] = len(unmatched)
    closed.attrs["unmatched_sell_lots_detail"] = unmatched
    return closed


def _load_meta() -> pd.DataFrame:
    for rel in [
        ATTR_DIR / "long_stock_meta_theme_map.csv",
        ATTR_DIR / "stock_meta_theme_map.csv",
    ]:
        path = _abs(rel)
        if path.exists():
            frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
            return frame.drop_duplicates("symbol")
    return pd.DataFrame(columns=["symbol", "ts_code", "name", "industry", "theme_tags"])


def _load_portfolio_daily() -> pd.DataFrame:
    frame = _read_csv(BASELINE_DIR / "portfolio_daily.csv")
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    cols = [
        "date",
        "nav",
        "stock_nav",
        "account_budget_effective_state_5",
        "account_transition_kind",
        "stock_gross_exposure",
        "stock_positions_count",
    ]
    return frame.loc[:, [col for col in cols if col in frame.columns]].copy()


def _fetch_db_frame(query: str, params: tuple[Any, ...]) -> pd.DataFrame:
    if psycopg is None or dict_row is None:
        raise RuntimeError("psycopg is required")
    with psycopg.connect(**_db_settings(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    return pd.DataFrame(rows)


def _load_prices(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=["symbol", "date", "close", "adj_close"])
    frame = _fetch_db_frame(
        """
        SELECT symbol, trade_date AS date, close, adj_factor, row_status
        FROM public.pams_ohlcv_daily_v2
        WHERE symbol = ANY(%s)
          AND trade_date >= %s
          AND trade_date <= %s
        ORDER BY symbol, trade_date
        """,
        (symbols, start, end),
    )
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "date", "close", "adj_close"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["adj_factor"] = pd.to_numeric(frame["adj_factor"], errors="coerce").fillna(1.0)
    frame["adj_close"] = frame["close"] * frame["adj_factor"]
    return frame.dropna(subset=["symbol", "date", "adj_close"]).sort_values(["symbol", "date"]).reset_index(drop=True)


def _load_index_prices(index_codes: list[str], start: str, end: str) -> pd.DataFrame:
    if not index_codes:
        return pd.DataFrame(columns=["index_code", "date", "close"])
    frame = _fetch_db_frame(
        """
        SELECT index_code, trade_date AS date, close
        FROM public.pit_index_daily
        WHERE index_code = ANY(%s)
          AND trade_date >= %s
          AND trade_date <= %s
        ORDER BY index_code, trade_date
        """,
        (index_codes, start, end),
    )
    if frame.empty:
        return pd.DataFrame(columns=["index_code", "date", "close"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    return frame.dropna(subset=["index_code", "date", "close"]).sort_values(["index_code", "date"]).reset_index(drop=True)


def _load_industry_history(symbols: list[str]) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=["symbol", "start_date", "end_date", "standard", "industry_l1"])
    frame = _fetch_db_frame(
        """
        SELECT ts_code AS symbol, start_date, COALESCE(end_date, DATE '9999-12-31') AS end_date,
               standard, industry_l1
        FROM public.pit_industry_history
        WHERE ts_code = ANY(%s)
        ORDER BY ts_code, start_date
        """,
        (symbols,),
    )
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "start_date", "end_date", "standard", "industry_l1"])
    frame["symbol"] = frame["symbol"].astype(str).str.lower()
    frame["start_date"] = pd.to_datetime(frame["start_date"], errors="coerce")
    frame["end_date"] = pd.to_datetime(frame["end_date"], errors="coerce")
    return frame


def _asof_industry(industry_history: pd.DataFrame, symbol: str, at_date: pd.Timestamp) -> str:
    part = industry_history.loc[industry_history["symbol"].eq(str(symbol).lower())]
    if part.empty or pd.isna(at_date):
        return ""
    mask = (part["start_date"] <= at_date) & (part["end_date"] > at_date)
    hit = part.loc[mask]
    if hit.empty:
        hit = part.loc[part["start_date"] <= at_date].tail(1)
    if hit.empty:
        return ""
    return str(hit.iloc[-1].get("industry_l1") or "")


def _build_series_map(frame: pd.DataFrame, key_col: str, value_col: str) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for key, grp in frame.groupby(key_col):
        out[str(key)] = grp.sort_values("date").reset_index(drop=True).loc[:, ["date", value_col]].rename(columns={value_col: "value"})
    return out


def _row_at_or_before(series: pd.DataFrame, date_value: pd.Timestamp) -> pd.Series | None:
    part = series.loc[series["date"] <= date_value]
    if part.empty:
        return None
    return part.iloc[-1]


def _row_at_or_after(series: pd.DataFrame, date_value: pd.Timestamp) -> pd.Series | None:
    part = series.loc[series["date"] >= date_value]
    if part.empty:
        return None
    return part.iloc[0]


def _ret_between_dates(series: pd.DataFrame | None, start: Any, end: Any) -> float | None:
    if series is None or series.empty:
        return None
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    start_row = _row_at_or_after(series, start_ts)
    end_row = _row_at_or_before(series, end_ts)
    if start_row is None or end_row is None:
        return None
    start_value = _to_float(start_row["value"])
    end_value = _to_float(end_row["value"])
    if not start_value or end_value is None:
        return None
    return end_value / start_value - 1.0


def _ret_offset(series: pd.DataFrame | None, anchor: Any, start_offset: int, end_offset: int) -> float | None:
    if series is None or series.empty:
        return None
    anchor_ts = pd.Timestamp(anchor)
    first_idx = series.index[series["date"] >= anchor_ts]
    if len(first_idx) == 0:
        return None
    anchor_idx = int(first_idx[0])
    start_idx = anchor_idx + start_offset
    end_idx = anchor_idx + end_offset
    if start_idx < 0 or end_idx < 0 or start_idx >= len(series) or end_idx >= len(series):
        return None
    start_value = _to_float(series.iloc[start_idx]["value"])
    end_value = _to_float(series.iloc[end_idx]["value"])
    if not start_value or end_value is None:
        return None
    return end_value / start_value - 1.0


def _future_ret(series: pd.DataFrame | None, anchor: Any, horizon: int) -> float | None:
    if series is None or series.empty:
        return None
    anchor_ts = pd.Timestamp(anchor)
    base_idx = series.index[series["date"] <= anchor_ts]
    if len(base_idx) == 0:
        return None
    idx0 = int(base_idx[-1])
    idx1 = idx0 + horizon
    if idx1 >= len(series):
        return None
    base = _to_float(series.iloc[idx0]["value"])
    future = _to_float(series.iloc[idx1]["value"])
    if not base or future is None:
        return None
    return future / base - 1.0


def _future_date(series: pd.DataFrame | None, anchor: Any, horizon: int) -> str:
    if series is None or series.empty:
        return ""
    anchor_ts = pd.Timestamp(anchor)
    base_idx = series.index[series["date"] <= anchor_ts]
    if len(base_idx) == 0:
        return ""
    idx = int(base_idx[-1]) + horizon
    if idx >= len(series):
        return ""
    return pd.Timestamp(series.iloc[idx]["date"]).strftime("%Y-%m-%d")


def _cause_bucket(reason_code: str) -> str:
    if reason_code in RISK_REASON_CODES:
        return "大盘风向变化强制平仓"
    if reason_code in STOP_REASON_CODES:
        return "突破失败后止损/失败退出"
    if reason_code == "ATR_TRAIL_EXIT":
        return "移动止盈/趋势回落退出"
    return "其他"


def _entry_chase_level(row: pd.Series) -> str:
    margin = _to_float(row.get("breakout_margin_raw")) or 0.0
    gap = _to_float(row.get("breakout_open_gap_raw")) or 0.0
    pre20 = _to_float(row.get("stock_pre_entry_20d_return")) or 0.0
    flags = int(margin >= 0.04) + int(gap >= 0.02) + int(pre20 >= 0.12)
    if flags >= 2:
        return "明显追高"
    if flags == 1:
        return "轻度追高"
    return "常规突破"


def _sell_judgment(row: pd.Series) -> str:
    post20 = _to_float(row.get("stock_post_sell_20d_return"))
    post60 = _to_float(row.get("stock_post_sell_60d_return"))
    reason = str(row.get("exit_reason_code") or "")
    if post20 is None and post60 is None:
        return "证据不足"
    if (post20 is not None and post20 <= -0.02) or (post60 is not None and post60 <= -0.05):
        return "卖出合理：卖后继续走弱"
    if (post20 is not None and post20 >= 0.05) or (post60 is not None and post60 >= 0.10):
        return "卖出偏早：卖后明显反弹"
    if reason in RISK_REASON_CODES and ((post20 or 0.0) > 0 or (post60 or 0.0) > 0):
        return "偏保守：风险退出后有修复"
    return "基本合理/影响有限"


def _risk_context(row: pd.Series) -> str:
    sse = _to_float(row.get("sse_return_holding"))
    zz500 = _to_float(row.get("zz500_return_holding"))
    industry = _to_float(row.get("industry_index_return_holding"))
    exit_state = str(row.get("exit_account_state") or "")
    pieces: list[str] = []
    if exit_state and exit_state not in {"BULL", "TRANS_UP"}:
        pieces.append(f"账户状态={exit_state}")
    if sse is not None:
        pieces.append(f"上证同期{_fmt_pct(sse)}")
    if zz500 is not None:
        pieces.append(f"中证500同期{_fmt_pct(zz500)}")
    if industry is not None:
        pieces.append(f"行业同期{_fmt_pct(industry)}")
    return "；".join(pieces)


def _enrich_closed_trades(closed: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    meta = _load_meta()
    daily = _load_portfolio_daily()
    symbols = sorted(closed["symbol"].astype(str).str.lower().unique().tolist())
    min_date = (closed["entry_date"].min() - pd.Timedelta(days=420)).strftime("%Y-%m-%d")
    max_date = (closed["exit_date"].max() + pd.Timedelta(days=140)).strftime("%Y-%m-%d")

    prices = _load_prices(symbols, min_date, max_date)
    price_map = _build_series_map(prices.rename(columns={"adj_close": "value"}), "symbol", "value")
    industry_history = _load_industry_history(symbols)

    work = closed.copy()
    if not meta.empty:
        work = work.merge(meta[["symbol", "ts_code", "name", "industry", "theme_tags"]], how="left", on="symbol")
    else:
        work["name"] = ""
        work["industry"] = ""
        work["theme_tags"] = ""
    if not daily.empty:
        exit_daily = daily.add_prefix("exit_").rename(columns={"exit_date": "exit_date"})
        work = work.merge(exit_daily, how="left", on="exit_date")

    work["sw_l1_industry"] = work.apply(lambda r: _asof_industry(industry_history, r["symbol"], r["exit_date"]), axis=1)
    work["sw_l1_index_code"] = work["sw_l1_industry"].map(SW_L1_INDEX_MAP).fillna("")
    index_codes = sorted(set(BENCHMARKS) | {x for x in work["sw_l1_index_code"].dropna().astype(str) if x})
    index_prices = _load_index_prices(index_codes, min_date, max_date)
    index_map = _build_series_map(index_prices.rename(columns={"close": "value"}), "index_code", "value")

    for horizon in (5, 20, 60):
        work[f"stock_post_sell_{horizon}d_return"] = work.apply(
            lambda r: _future_ret(price_map.get(str(r["symbol"]).lower()), r["exit_date"], horizon), axis=1
        )
        work[f"stock_post_sell_{horizon}d_date"] = work.apply(
            lambda r: _future_date(price_map.get(str(r["symbol"]).lower()), r["exit_date"], horizon), axis=1
        )
        work[f"sse_post_sell_{horizon}d_return"] = work.apply(
            lambda r: _future_ret(index_map.get("000001.SH"), r["exit_date"], horizon), axis=1
        )
        work[f"industry_post_sell_{horizon}d_return"] = work.apply(
            lambda r: _future_ret(index_map.get(str(r["sw_l1_index_code"])), r["exit_date"], horizon), axis=1
        )

    work["stock_price_return_holding"] = work.apply(
        lambda r: _ret_between_dates(price_map.get(str(r["symbol"]).lower()), r["entry_date"], r["exit_date"]), axis=1
    )
    work["stock_pre_entry_20d_return"] = work.apply(
        lambda r: _ret_offset(price_map.get(str(r["symbol"]).lower()), r["entry_date"], -20, 0), axis=1
    )
    work["sse_return_holding"] = work.apply(
        lambda r: _ret_between_dates(index_map.get("000001.SH"), r["entry_date"], r["exit_date"]), axis=1
    )
    work["hs300_return_holding"] = work.apply(
        lambda r: _ret_between_dates(index_map.get("000300.SH"), r["entry_date"], r["exit_date"]), axis=1
    )
    work["zz500_return_holding"] = work.apply(
        lambda r: _ret_between_dates(index_map.get("000905.SH"), r["entry_date"], r["exit_date"]), axis=1
    )
    work["chinext_return_holding"] = work.apply(
        lambda r: _ret_between_dates(index_map.get("399006.SZ"), r["entry_date"], r["exit_date"]), axis=1
    )
    work["industry_index_return_holding"] = work.apply(
        lambda r: _ret_between_dates(index_map.get(str(r["sw_l1_index_code"])), r["entry_date"], r["exit_date"]), axis=1
    )
    work["industry_index_name"] = work["sw_l1_industry"]
    work["cause_bucket"] = work["exit_reason_code"].map(_cause_bucket)
    work["entry_chase_level"] = work.apply(_entry_chase_level, axis=1)
    work["sell_judgment"] = work.apply(_sell_judgment, axis=1)
    work["risk_context"] = work.apply(_risk_context, axis=1)
    work["relative_vs_sse_holding"] = work["stock_price_return_holding"] - work["sse_return_holding"]
    work["relative_vs_industry_holding"] = work["stock_price_return_holding"] - work["industry_index_return_holding"]

    audit = {
        "price_symbols_requested": len(symbols),
        "price_symbols_loaded": int(prices["symbol"].nunique()) if not prices.empty else 0,
        "index_codes_requested": len(index_codes),
        "index_codes_loaded": int(index_prices["index_code"].nunique()) if not index_prices.empty else 0,
        "industry_history_symbols_loaded": int(industry_history["symbol"].nunique()) if not industry_history.empty else 0,
        "min_query_date": min_date,
        "max_query_date": max_date,
    }
    return work, audit


def _summarize(top30: pd.DataFrame, enriched: pd.DataFrame, audit: dict[str, Any]) -> dict[str, Any]:
    def _group(df: pd.DataFrame, by: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key, grp in df.groupby(by, dropna=False):
            rows.append(
                {
                    by: str(key),
                    "count": int(len(grp)),
                    "loss_sum": float(grp["realized_pnl"].sum()),
                    "loss_abs_sum": float((-grp["realized_pnl"]).sum()),
                    "avg_realized_return": float(grp["realized_return"].mean()),
                    "avg_sse_return_holding": float(pd.to_numeric(grp["sse_return_holding"], errors="coerce").mean()),
                    "avg_industry_return_holding": float(pd.to_numeric(grp["industry_index_return_holding"], errors="coerce").mean()),
                    "sell_reasonable_count": int(grp["sell_judgment"].astype(str).str.contains("合理|继续走弱", regex=True).sum()),
                    "sell_rebound_count": int(grp["sell_judgment"].astype(str).str.contains("反弹|偏早", regex=True).sum()),
                }
            )
        return sorted(rows, key=lambda x: x["loss_abs_sum"], reverse=True)

    all_losses = enriched.loc[enriched["realized_pnl"] < 0].copy()
    return {
        "study_id": STUDY_ID,
        "baseline_id": BASELINE_ID,
        "source_files": {
            "portfolio_trades": str(BASELINE_DIR / "portfolio_trades.csv"),
            "portfolio_daily": str(BASELINE_DIR / "portfolio_daily.csv"),
            "stock_meta_theme_map": str(ATTR_DIR / "long_stock_meta_theme_map.csv"),
            "db_stock_prices": "public.pams_ohlcv_daily_v2 close*adj_factor",
            "db_index_prices": "public.pit_index_daily",
            "db_industry_history": "public.pit_industry_history",
        },
        "scope": "stock_alpha_core closed trades only; ETF sleeve excluded",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "audit": audit,
        "all_stock_closed_trades": int(len(enriched)),
        "all_stock_losing_trades": int(len(all_losses)),
        "all_stock_losing_pnl": float(all_losses["realized_pnl"].sum()),
        "top30_loss_sum": float(top30["realized_pnl"].sum()),
        "top30_loss_abs_sum": float((-top30["realized_pnl"]).sum()),
        "top30_avg_realized_return": float(top30["realized_return"].mean()),
        "top30_avg_holding_days": float(top30["hold_calendar_days"].mean()),
        "cause_bucket_summary": _group(top30, "cause_bucket"),
        "exit_reason_summary": _group(top30, "exit_reason_code"),
        "sell_judgment_summary": _group(top30, "sell_judgment"),
        "industry_summary": _group(top30, "sw_l1_industry"),
        "theme_summary": _group(top30, "theme_tags"),
    }


def _write_report(top30: pd.DataFrame, summary: dict[str, Any], out_dir: Path) -> None:
    lines: list[str] = []
    lines.append("# V3 亏损 TOP30 卖出原因审计")
    lines.append("")
    lines.append("## 结论")
    cause = {row["cause_bucket"]: row for row in summary["cause_bucket_summary"]}
    risk = cause.get("大盘风向变化强制平仓", {})
    stop = cause.get("突破失败后止损/失败退出", {})
    risk_count = int(risk.get("count", 0) or 0)
    stop_count = int(stop.get("count", 0) or 0)
    risk_loss = float(risk.get("loss_abs_sum", 0.0) or 0.0)
    stop_loss = float(stop.get("loss_abs_sum", 0.0) or 0.0)
    total_loss = float(summary["top30_loss_abs_sum"] or 0.0)
    lines.append(
        f"- 亏损 TOP30 的主因是大盘风向变化触发的 `RISK_OFF_EXIT`：{risk_count}/30 笔，亏损 {_fmt_money(risk_loss)}，占 TOP30 亏损 {risk_loss / total_loss:.1%}。"
    )
    lines.append(
        f"- 突破失败/止损类退出合计 {stop_count}/30 笔，亏损 {_fmt_money(stop_loss)}，占 TOP30 亏损 {stop_loss / total_loss:.1%}。它是重要次因，但不是这一组最大来源。"
    )
    lines.append(
        f"- TOP30 平均单笔收益率 {_fmt_pct(summary['top30_avg_realized_return'])}，平均持仓 {summary['top30_avg_holding_days']:.1f} 个自然日。"
    )
    rebound = sum(1 for x in top30["sell_judgment"].astype(str) if "反弹" in x or "偏早" in x)
    reasonable = sum(1 for x in top30["sell_judgment"].astype(str) if "合理" in x or "继续走弱" in x)
    lines.append(
        f"- 卖出后表现看，{reasonable}/30 笔卖后继续走弱或影响有限，{rebound}/30 笔卖后明显反弹/偏早；风险退出保护了部分继续下跌，但也有明显 whipsaw。"
    )
    lines.append("")
    lines.append("## 归因口径")
    lines.append("- 只分析 V3 股票腿 `stock_alpha_core` 已平仓交易；ETF 调仓不纳入 TOP30。")
    lines.append("- 单笔盈亏按 FIFO 匹配买卖，买入/卖出净额含佣金、印花税、滑点。")
    lines.append("- 个股卖出后表现使用 `pams_ohlcv_daily_v2` 的 `close * adj_factor`，卖出后 5/20/60 个交易日。")
    lines.append("- 大盘指数使用 `pit_index_daily`：上证指数、沪深300、中证500、创业板指；行业使用卖出日 PIT 申万 L1 行业及对应 801xxx.SI 指数。")
    unmatched_count = int(summary.get("audit", {}).get("unmatched_sell_lots", 0) or 0)
    if unmatched_count:
        lines.append(f"- FIFO 重建发现 {unmatched_count} 笔部分卖出余量无法匹配买入，已单独输出 `machine/unmatched_sell_lots.csv`，TOP30 仅使用可审计匹配部分。")
    lines.append("")

    lines.append("## 原因汇总")
    lines.append("|原因|笔数|亏损额|平均单笔收益|同期上证均值|同期行业均值|卖出合理|卖后反弹|")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in summary["cause_bucket_summary"]:
        lines.append(
            "|{cause_bucket}|{count}|{loss}|{avg_ret}|{sse}|{industry}|{reasonable}|{rebound}|".format(
                cause_bucket=row["cause_bucket"],
                count=row["count"],
                loss=_fmt_money(row["loss_abs_sum"]),
                avg_ret=_fmt_pct(row["avg_realized_return"]),
                sse=_fmt_pct(row["avg_sse_return_holding"]),
                industry=_fmt_pct(row["avg_industry_return_holding"]),
                reasonable=row["sell_reasonable_count"],
                rebound=row["sell_rebound_count"],
            )
        )
    lines.append("")

    lines.append("## 行业集中")
    lines.append("|申万L1行业|笔数|亏损额|同期行业均值|卖后反弹|")
    lines.append("|---|---:|---:|---:|---:|")
    for row in summary["industry_summary"][:12]:
        lines.append(
            f"|{row['sw_l1_industry'] or '-'}|{row['count']}|{_fmt_money(row['loss_abs_sum'])}|{_fmt_pct(row['avg_industry_return_holding'])}|{row['sell_rebound_count']}|"
        )
    lines.append("")

    lines.append("## TOP30 明细")
    lines.append(
        "|rank|股票|买入|卖出|亏损|收益率|卖出原因|行业指数同期|上证同期|卖后20日|卖后60日|判断|"
    )
    lines.append("|---:|---|---|---|---:|---:|---|---:|---:|---:|---:|---|")
    for row in top30.itertuples(index=False):
        stock = f"{getattr(row, 'symbol')} {getattr(row, 'name', '')}".strip()
        lines.append(
            f"|{getattr(row, 'loss_rank')}|{stock}|{pd.Timestamp(row.entry_date).strftime('%Y-%m-%d')}|"
            f"{pd.Timestamp(row.exit_date).strftime('%Y-%m-%d')}|{_fmt_money(row.realized_pnl)}|{_fmt_pct(row.realized_return)}|"
            f"{row.exit_reason_code}|{row.sw_l1_industry} {row.sw_l1_index_code} {_fmt_pct(row.industry_index_return_holding)}|"
            f"{_fmt_pct(row.sse_return_holding)}|{_fmt_pct(row.stock_post_sell_20d_return)}|"
            f"{_fmt_pct(row.stock_post_sell_60d_return)}|{row.sell_judgment}|"
        )
    lines.append("")

    lines.append("## 解释")
    lines.append(
        "这组亏损不是单纯的“突破追高止损”。所有买入都来自突破体系，但 TOP30 里最大亏损更多发生在市场状态切换后的 `RISK_OFF_EXIT`。"
        "这说明 V3 的个股腿在市场风向变化时会集中平仓，损失来自持仓在风险退出日之前已经回撤，而不是等到单票 ATR 止损全部触发。"
    )
    lines.append(
        "止损类亏损的特征更像短持仓突破失败：买入后没有走出利润垫，随后触发 ATR_STOP_LOSS 或 PRE_PROFIT_BREAKOUT_FAILURE_EXIT。"
        "这类问题应从突破质量、主题强度、买入后确认和失败退出速度继续研究。"
    )
    lines.append(
        "风险退出类亏损的改进方向不是简单放宽卖出，而是判断市场风险切换是否与持仓主题同步转弱。若指数转弱但持仓主题仍强，V3 容易过早卖出；若主题和大盘同步转弱，强平是合理保护。"
    )
    lines.append("")

    out_path = out_dir / "human" / "v3_loss_top30_exit_reason_audit.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def run() -> dict[str, Any]:
    out_dir = _abs(OUT_DIR)
    machine_dir = out_dir / "machine"
    machine_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "human").mkdir(parents=True, exist_ok=True)

    source_audit = {
        "baseline_id": BASELINE_ID,
        "baseline_dir": str(BASELINE_DIR),
        "portfolio_trades_exists": _abs(BASELINE_DIR / "portfolio_trades.csv").exists(),
        "portfolio_daily_exists": _abs(BASELINE_DIR / "portfolio_daily.csv").exists(),
        "baseline_manifest": _read_json(BASELINE_DIR / "manifest.json"),
    }
    trades = _load_stock_trades()
    closed = _reconstruct_closed_trades(trades)
    unmatched_detail = pd.DataFrame(closed.attrs.get("unmatched_sell_lots_detail", []))
    enriched, db_audit = _enrich_closed_trades(closed)
    enriched.sort_values(["realized_pnl", "exit_date", "symbol"], inplace=True)
    enriched["loss_rank"] = range(1, len(enriched) + 1)
    losses = enriched.loc[enriched["realized_pnl"] < 0].copy()
    top30 = losses.head(30).copy()
    top30["loss_rank"] = range(1, len(top30) + 1)

    ordered_cols = [
        "loss_rank",
        "symbol",
        "ts_code",
        "name",
        "industry",
        "theme_tags",
        "sw_l1_industry",
        "sw_l1_index_code",
        "entry_date",
        "exit_date",
        "hold_calendar_days",
        "qty",
        "buy_net_cost",
        "sell_net_proceeds",
        "realized_pnl",
        "realized_return",
        "entry_reason_code",
        "exit_reason_code",
        "cause_bucket",
        "entry_chase_level",
        "sell_judgment",
        "risk_context",
        "stock_pre_entry_20d_return",
        "breakout_margin_raw",
        "breakout_open_gap_raw",
        "breakout_fade_raw",
        "breakout_quality_score",
        "residual_strength_score",
        "sector_strength_score",
        "stock_price_return_holding",
        "industry_index_return_holding",
        "sse_return_holding",
        "hs300_return_holding",
        "zz500_return_holding",
        "chinext_return_holding",
        "relative_vs_sse_holding",
        "relative_vs_industry_holding",
        "exit_account_budget_effective_state_5",
        "exit_account_transition_kind",
        "stock_post_sell_5d_return",
        "stock_post_sell_5d_date",
        "stock_post_sell_20d_return",
        "stock_post_sell_20d_date",
        "stock_post_sell_60d_return",
        "stock_post_sell_60d_date",
        "sse_post_sell_20d_return",
        "industry_post_sell_20d_return",
    ]
    for column in ordered_cols:
        if column not in top30.columns:
            top30[column] = pd.NA
    top30_out = top30.loc[:, ordered_cols]
    all_loss_cols = [col for col in ordered_cols if col in enriched.columns]

    audit = {**source_audit, **db_audit, "unmatched_sell_lots": int(enriched["unmatched_sell_lots"].max())}
    summary = _summarize(top30, enriched, audit)

    top30_out.to_csv(machine_dir / "top30_loss_trades.csv", index=False, encoding="utf-8-sig")
    if not unmatched_detail.empty:
        unmatched_detail.to_csv(machine_dir / "unmatched_sell_lots.csv", index=False, encoding="utf-8-sig")
    losses.loc[:, all_loss_cols].to_csv(machine_dir / "all_losing_stock_trades.csv", index=False, encoding="utf-8-sig")
    enriched.to_csv(machine_dir / "all_closed_stock_trades_enriched.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(summary["cause_bucket_summary"]).to_csv(machine_dir / "cause_bucket_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(summary["industry_summary"]).to_csv(machine_dir / "industry_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(summary["sell_judgment_summary"]).to_csv(machine_dir / "sell_judgment_summary.csv", index=False, encoding="utf-8-sig")
    (machine_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(top30, summary, out_dir)
    return summary


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
