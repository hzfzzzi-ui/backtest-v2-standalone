from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
import os

import pandas as pd

from backend.core.data.price_limits import (
    compute_limit_prices as shared_compute_limit_prices,
    limit_pct_for_symbol as shared_limit_pct_for_symbol,
)

from . import cn_side_table_common as common

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = common.DEFAULT_OUTPUT_ROOT
DEFAULT_BACKFILL_START = common.DEFAULT_BACKFILL_START
BUILD_VERSION = "pams_ohlcv_daily_v2_db_completion_20260317"
OFFICIAL_END_DATE = date(2026, 3, 16)
BJ_ESTABLISHED_DATE = date(2021, 11, 15)

RAW_STOCK_BASIC_TABLE = "raw_tushare_stock_basic"
RAW_TRADE_CAL_TABLE = "raw_tushare_trade_cal"
RAW_DAILY_TABLE = "raw_tushare_daily"
RAW_ADJ_FACTOR_TABLE = "raw_tushare_adj_factor"
RAW_DAILY_BASIC_TABLE = "raw_tushare_daily_basic"
RAW_SUSPEND_TABLE = "raw_tushare_suspend_d"
RAW_STK_LIMIT_TABLE = "raw_tushare_stk_limit"
RAW_MONEYFLOW_TABLE = "raw_tushare_moneyflow"
SYMBOL_LINEAGE_TABLE = "pit_security_symbol_lineage"

V2_MAIN_TABLE = "pams_ohlcv_daily_v2"
V2_MONEYFLOW_TABLE = "pit_stock_moneyflow_v2"
V2_AUDIT_DAILY_TABLE = "pams_ohlcv_daily_v2_audit_daily"
V2_EXCEPTIONS_TABLE = "pams_ohlcv_daily_v2_exceptions"
V2_MONEYFLOW_WHITELIST_TABLE = "pit_stock_moneyflow_v2_whitelist_daily"

MONEYFLOW_ROW_COVERAGE_THRESHOLD = 0.95
MONEYFLOW_NET_COVERAGE_THRESHOLD = 0.90

HARD_FIELDS = [
    "symbol",
    "ts_code",
    "market",
    "market_phase",
    "trade_date",
    "row_status",
    "is_suspended",
    "pre_close",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "turnover",
    "adj_factor",
    "limit_up",
    "limit_down",
    "turnover_rate",
    "pre_close_source",
    "pre_close_confidence",
    "adj_factor_source",
    "adj_factor_confidence",
    "turnover_rate_source",
    "turnover_rate_confidence",
]

SOFT_FIELDS = [
    "turnover_rate_f",
    "volume_ratio",
    "float_share",
    "free_share",
    "circ_mv",
]

CRITICAL_BUILD_ISSUE_TYPES = {
    "eligible_no_source",
    "pre_close_imputed_zero",
    "turnover_rate_imputed_zero",
    "source_unresolved",
}

DAILY_BASIC_FIELDS = [
    "close",
    "turnover_rate",
    "turnover_rate_f",
    "volume_ratio",
    "float_share",
    "free_share",
    "circ_mv",
]

MONEYFLOW_VOLUME_FIELDS = [
    "buy_sm_vol",
    "sell_sm_vol",
    "buy_md_vol",
    "sell_md_vol",
    "buy_lg_vol",
    "sell_lg_vol",
    "buy_elg_vol",
    "sell_elg_vol",
    "net_mf_vol",
]

MONEYFLOW_AMOUNT_FIELDS = [
    "buy_sm_amount",
    "sell_sm_amount",
    "buy_md_amount",
    "sell_md_amount",
    "buy_lg_amount",
    "sell_lg_amount",
    "buy_elg_amount",
    "sell_elg_amount",
    "net_mf_amount",
]


@dataclass(slots=True)
class PrevState:
    close: float | None = None
    adj_factor: float | None = None
    float_share: float | None = None
    free_share: float | None = None


@dataclass(slots=True)
class LineageCandidate:
    symbol: str
    source: str
    confidence: int


class SymbolLineageResolver:
    def __init__(self, entries: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._entries = entries or {}

    @classmethod
    def load_from_db(cls, conn) -> "SymbolLineageResolver":
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (f"public.{SYMBOL_LINEAGE_TABLE}",))
            exists = cur.fetchone()[0] is not None
            if not exists:
                return cls()
        frame = df_from_query(
            conn,
            f"""
            SELECT current_symbol, historical_symbol, phase_start, phase_end, mapping_source, mapping_confidence, is_active
            FROM public.{common.safe_ident(SYMBOL_LINEAGE_TABLE)}
            WHERE is_active = TRUE
            ORDER BY current_symbol, historical_symbol, phase_start NULLS FIRST
            """,
        )
        if frame.empty:
            return cls()
        entries: dict[str, list[dict[str, Any]]] = {}
        for row in frame.itertuples(index=False):
            symbol = normalize_stock_symbol(str(row.current_symbol))
            entries.setdefault(symbol, []).append(
                {
                    "historical_symbol": normalize_stock_symbol(str(row.historical_symbol)),
                    "phase_start": to_date_or_none(row.phase_start),
                    "phase_end": to_date_or_none(row.phase_end),
                    "mapping_source": str(row.mapping_source or "").strip() or "lineage_table",
                    "mapping_confidence": int(to_int_or_none(row.mapping_confidence) or 1),
                }
            )
        return cls(entries)

    def candidates_for_trade_date(self, symbol: str, trade_date: date, market_phase: str) -> list[LineageCandidate]:
        normalized = normalize_stock_symbol(symbol)
        candidates: list[LineageCandidate] = [LineageCandidate(symbol=normalized, source="current_symbol", confidence=3)]
        if market_phase != "bj_pre_20211115":
            return candidates
        for item in self._entries.get(normalized, []):
            phase_start = item.get("phase_start")
            phase_end = item.get("phase_end")
            if phase_start is not None and trade_date < phase_start:
                continue
            if phase_end is not None and trade_date > phase_end:
                continue
            hist_symbol = normalize_stock_symbol(str(item.get("historical_symbol") or ""))
            if hist_symbol and hist_symbol != normalized:
                candidates.append(
                    LineageCandidate(
                        symbol=hist_symbol,
                        source=str(item.get("mapping_source") or "lineage_table"),
                        confidence=int(item.get("mapping_confidence") or 1),
                    )
                )
        seen: set[str] = set()
        unique: list[LineageCandidate] = []
        for item in candidates:
            if item.symbol in seen:
                continue
            seen.add(item.symbol)
            unique.append(item)
        return unique


def build_run_id(prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}"


def normalize_stock_symbol(symbol: str) -> str:
    return common.normalize_stock_symbol(symbol).lower()


def symbol_to_tushare_code(symbol: str) -> str:
    text = normalize_stock_symbol(symbol)
    if text.startswith("sh"):
        return f"{text[2:].upper()}.SH"
    if text.startswith("sz"):
        return f"{text[2:].upper()}.SZ"
    if text.startswith("bj"):
        return f"{text[2:].upper()}.BJ"
    raise ValueError(f"unsupported symbol: {symbol}")


def symbol_to_akshare_args(symbol: str) -> tuple[str, str]:
    text = normalize_stock_symbol(symbol)
    if text.startswith("sh"):
        return text[2:], "sh"
    if text.startswith("sz"):
        return text[2:], "sz"
    if text.startswith("bj"):
        return text[2:], "bj"
    raise ValueError(f"unsupported symbol: {symbol}")


def historical_bj_symbol_heuristic(symbol: str) -> str | None:
    text = normalize_stock_symbol(symbol)
    if not text.startswith("bj"):
        return None
    digits = text[2:]
    if len(digits) == 6 and digits.startswith("92"):
        return f"bj43{digits[2:]}"
    return None


def market_phase_for_symbol(symbol: str, trade_date: date) -> str:
    text = normalize_stock_symbol(symbol)
    if text.startswith("sh"):
        return "sh"
    if text.startswith("sz"):
        return "sz"
    if text.startswith("bj"):
        return "bj_pre_20211115" if trade_date < BJ_ESTABLISHED_DATE else "bj_post_20211115"
    raise ValueError(f"unsupported symbol: {symbol}")


def to_date_or_none(value: Any) -> date | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def to_float_or_none(value: Any) -> float | None:
    series = pd.to_numeric(pd.Series([value]), errors="coerce")
    number = series.iloc[0]
    if pd.isna(number):
        return None
    return float(number)


def to_int_or_none(value: Any) -> int | None:
    series = pd.to_numeric(pd.Series([value]), errors="coerce")
    number = series.iloc[0]
    if pd.isna(number):
        return None
    return int(round(float(number)))


def limit_pct_for_symbol(symbol: str, *, is_st: bool) -> float:
    return shared_limit_pct_for_symbol(normalize_stock_symbol(symbol), is_st=is_st)


def compute_limit_prices(prev_close: Any, symbol: str, *, is_st: bool) -> tuple[float | None, float | None]:
    return shared_compute_limit_prices(prev_close, normalize_stock_symbol(symbol), is_st=is_st)


def derive_turnover_rate(volume: Any, float_share: Any) -> float | None:
    volume_number = to_float_or_none(volume)
    float_share_number = to_float_or_none(float_share)
    if volume_number is None or float_share_number is None or float_share_number <= 0:
        return None
    return float(volume_number / (float_share_number * 100.0))


def derive_share_from_turnover_rate(volume: Any, turnover_rate: Any) -> float | None:
    volume_number = to_float_or_none(volume)
    turnover_rate_number = to_float_or_none(turnover_rate)
    if volume_number is None or turnover_rate_number is None or turnover_rate_number <= 0:
        return None
    return float(volume_number / (turnover_rate_number * 100.0))


def derive_circ_mv(close: Any, float_share: Any) -> float | None:
    close_number = to_float_or_none(close)
    float_share_number = to_float_or_none(float_share)
    if close_number is None or float_share_number is None:
        return None
    return float(close_number * float_share_number)


def df_from_query(conn, query: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d.name for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=cols)


def load_st_periods(start: date, end: date) -> dict[str, list[tuple[date, date | None]]]:
    out: dict[str, list[tuple[date, date | None]]] = {}
    with common.connect() as conn:
        frame = df_from_query(
            conn,
            """
            SELECT ts_code, start_date, end_date
            FROM public.pit_st_history
            WHERE start_date <= %s
              AND (end_date IS NULL OR end_date >= %s)
            """,
            (end, start),
        )
    if frame.empty:
        return out
    for row in frame.itertuples(index=False):
        symbol = normalize_stock_symbol(str(row.ts_code))
        start_date = to_date_or_none(row.start_date)
        end_date = to_date_or_none(row.end_date)
        if not symbol or start_date is None:
            continue
        out.setdefault(symbol, []).append((start_date, end_date))
    return out


def _pick_akshare_hist_columns(frame: pd.DataFrame) -> tuple[str | None, str | None]:
    date_column: str | None = None
    turnover_column: str | None = None
    for column in frame.columns:
        text = str(column).strip()
        compact = text.replace(" ", "")
        if date_column is None and ("日期" in compact or compact.lower() == "date" or "鏃" in compact):
            date_column = str(column)
        if turnover_column is None and ("换手" in compact or "turnover" in compact.lower() or "鎹" in compact):
            turnover_column = str(column)
    return date_column, turnover_column


class AkShareTurnoverCache:
    def __init__(self, lineage_resolver: SymbolLineageResolver | None = None) -> None:
        self._ak = None
        self._cache: dict[str, dict[date, float | None]] = {}
        self._lineage_resolver = lineage_resolver or SymbolLineageResolver()

    def _load_symbol(self, symbol: str) -> dict[date, float | None]:
        digits, _market = symbol_to_akshare_args(symbol)
        if self._ak is None:
            import akshare as ak

            self._ak = ak
        try:
            raw = self._ak.stock_zh_a_hist(
                symbol=digits,
                period="daily",
                start_date="20070101",
                end_date=OFFICIAL_END_DATE.strftime("%Y%m%d"),
                adjust="",
            )
        except Exception:
            return {}
        if raw is None or raw.empty:
            return {}
        date_col, turnover_col = _pick_akshare_hist_columns(raw)
        if date_col not in raw.columns or turnover_col not in raw.columns:
            return {}
        frame = raw[[date_col, turnover_col]].copy()
        frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce").dt.date
        frame[turnover_col] = pd.to_numeric(frame[turnover_col], errors="coerce")
        frame = frame.dropna(subset=[date_col]).drop_duplicates(subset=[date_col], keep="last")
        return {
            row[date_col]: (None if pd.isna(row[turnover_col]) else float(row[turnover_col]))
            for _, row in frame.iterrows()
        }

    def get(self, symbol: str, trade_date: date, market_phase: str) -> tuple[float | None, str | None]:
        for candidate in self._lineage_resolver.candidates_for_trade_date(symbol, trade_date, market_phase):
            key = normalize_stock_symbol(candidate.symbol)
            if key not in self._cache:
                self._cache[key] = self._load_symbol(key)
            value = self._cache.get(key, {}).get(trade_date)
            if value is None:
                continue
            source = "akshare_stock_zh_a_hist"
            if candidate.source != "current_symbol":
                source = "akshare_stock_zh_a_hist_lineage"
                if candidate.source == "heuristic_92_to_43":
                    source = "akshare_stock_zh_a_hist_lineage_heuristic"
            return value, source
        return None, None


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    common.write_json(temp_path, payload)
    temp_path.replace(path)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    temp_path.write_text(str(content), encoding="utf-8")
    temp_path.replace(path)


def touch_heartbeat(
    heartbeat_path: str | Path | None,
    *,
    step: str,
    trade_date: date | str | None = None,
    status: str = "running",
    extra: dict[str, Any] | None = None,
) -> None:
    if not heartbeat_path:
        return
    heartbeat = Path(heartbeat_path)
    payload: dict[str, Any] = {
        "step": str(step),
        "status": str(status),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if trade_date is not None:
        payload["trade_date"] = trade_date.isoformat() if isinstance(trade_date, date) else str(trade_date)
    if extra:
        payload.update(extra)
    write_json_atomic(heartbeat, payload)
