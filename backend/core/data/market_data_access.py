from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import date
from typing import TYPE_CHECKING, Any, Iterable

import pandas as pd

from backend.core.config.models import DataSourceConfig
from backend.core.data.mapping import normalize_stock_symbol, safe_ident
from backend.core.data.pg_provider import PostgresDataProvider

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

if TYPE_CHECKING:  # pragma: no cover
    from backend.core.tools.runtime_data_access import RuntimeDataAccess


QUERY_VERSION = "market-data-access@1"
DIRECT_CANONICAL_CACHE_VERSION = "direct_canonical"
CALENDAR_VERSION = "canonical_trade_calendar@1"


@dataclass(slots=True)
class MarketDataRequest:
    asset_scope: str
    market: str
    data_level: str = "L1"
    as_of_date: date | None = None
    window_start: date | None = None
    window_end: date | None = None
    symbols: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MarketDataAudit:
    capability: str
    canonical_objects: list[str]
    market: str
    data_level: str
    as_of_date: str | None
    window_start: str | None
    window_end: str | None
    degraded: bool
    missing_data: bool
    query_version: str = QUERY_VERSION
    cache_hit: bool = False
    cache_version: str = DIRECT_CANONICAL_CACHE_VERSION
    provider_query_audit: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MarketDataFrameResult:
    frame: pd.DataFrame
    audit: MarketDataAudit

    def audit_dict(self) -> dict[str, Any]:
        return self.audit.to_dict()


def _iso_or_none(value: date | None) -> str | None:
    return value.isoformat() if isinstance(value, date) else None


def _unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _default_market_for_asset_scope(asset_scope: str) -> str:
    scope = str(asset_scope or "").strip().lower()
    if scope in {"cn_a_equity", "cn_etf", "cn_a_multi_sleeve"}:
        return "CN_A"
    return "UNKNOWN"


class MarketDataAccess:
    def __init__(self, runtime_access: RuntimeDataAccess) -> None:
        if psycopg is None:  # pragma: no cover
            raise RuntimeError("psycopg is required for market data access")
        self._runtime_access = runtime_access
        self._canonical_data_source = self._build_canonical_data_source(runtime_access.cfg_obj.data_source)
        self._provider = PostgresDataProvider(
            db=runtime_access.cfg_obj.db,
            runtime=runtime_access.cfg_obj.db_runtime,
            data_source=self._canonical_data_source,
            schema_mapping=runtime_access.cfg_obj.schema_mapping,
            rules_path=runtime_access.cfg_path.parent / "instrument_rules_cn.csv",
        )

    @staticmethod
    def _build_canonical_data_source(base: DataSourceConfig) -> DataSourceConfig:
        canonical_table = str(base.v2_canonical_stocks_table or base.stocks_table)
        mapping_table = str(base.v2_schema_mapping_table or canonical_table)
        return replace(
            base,
            data_role="v2_canonical",
            stocks_table=canonical_table,
            v2_canonical_stocks_table=canonical_table,
            v2_schema_mapping_table=mapping_table,
        )

    @property
    def provider(self) -> PostgresDataProvider:
        return self._provider

    @property
    def canonical_stocks_table(self) -> str:
        return str(self._canonical_data_source.resolved_stocks_table())

    def _conn(self):
        db = self._runtime_access.cfg_obj.db
        return psycopg.connect(
            host=db.host,
            port=db.port,
            dbname=db.dbname,
            user=db.user,
            password=db.password,
            autocommit=False,
        )

    def _provider_call(self, func: Any, *args: Any, **kwargs: Any) -> tuple[Any, list[dict[str, Any]]]:
        start = len(self._provider.query_audit)
        result = func(*args, **kwargs)
        return result, list(self._provider.query_audit[start:])

    def _build_audit(
        self,
        *,
        capability: str,
        request: MarketDataRequest,
        canonical_objects: Iterable[str],
        frame: pd.DataFrame,
        provider_query_audit: list[dict[str, Any]] | None = None,
        degraded: bool = False,
    ) -> MarketDataAudit:
        return MarketDataAudit(
            capability=capability,
            canonical_objects=_unique_preserve_order(canonical_objects),
            market=request.market,
            data_level=request.data_level,
            as_of_date=_iso_or_none(request.as_of_date),
            window_start=_iso_or_none(request.window_start),
            window_end=_iso_or_none(request.window_end),
            degraded=bool(degraded),
            missing_data=bool(frame.empty),
            provider_query_audit=list(provider_query_audit or []),
        )

    def load_price_history(
        self,
        *,
        symbols: list[str],
        start: date,
        end: date,
        asset_scope: str = "cn_a_equity",
        market: str | None = None,
    ) -> MarketDataFrameResult:
        request = MarketDataRequest(
            asset_scope=asset_scope,
            market=market or _default_market_for_asset_scope(asset_scope),
            window_start=start,
            window_end=end,
            symbols=list(symbols),
        )
        frame, query_audit = self._provider_call(
            self._provider.load_ohlcv_daily,
            list(symbols),
            start,
            end,
            "market_data_access_price_history",
        )
        audit = self._build_audit(
            capability="price_history",
            request=request,
            canonical_objects=[entry.get("table") for entry in query_audit],
            frame=frame,
            provider_query_audit=query_audit,
        )
        return MarketDataFrameResult(frame=frame, audit=audit)

    def load_benchmark_history(
        self,
        *,
        symbol: str,
        start: date,
        end: date,
        asset_scope: str = "cn_a_equity",
        market: str | None = None,
    ) -> MarketDataFrameResult:
        request = MarketDataRequest(
            asset_scope=asset_scope,
            market=market or _default_market_for_asset_scope(asset_scope),
            window_start=start,
            window_end=end,
            symbols=[symbol],
        )
        frame, query_audit = self._provider_call(
            self._provider.load_benchmark_daily,
            symbol,
            start,
            end,
        )
        audit = self._build_audit(
            capability="benchmark_history",
            request=request,
            canonical_objects=[entry.get("table") for entry in query_audit],
            frame=frame,
            provider_query_audit=query_audit,
        )
        return MarketDataFrameResult(frame=frame, audit=audit)

    def load_trading_calendar(
        self,
        *,
        start: date,
        end: date,
        asset_scope: str = "cn_a_equity",
        market: str | None = None,
    ) -> MarketDataFrameResult:
        request = MarketDataRequest(
            asset_scope=asset_scope,
            market=market or _default_market_for_asset_scope(asset_scope),
            window_start=start,
            window_end=end,
        )
        calendar, query_audit = self._provider_call(
            self._provider.load_trading_calendar_cn,
            start,
            end,
        )
        frame = pd.DataFrame(
            {
                "trade_date": pd.DatetimeIndex(calendar).normalize(),
                "is_trading_day": True,
                "calendar_version": CALENDAR_VERSION,
            }
        )
        audit = self._build_audit(
            capability="trading_calendar",
            request=request,
            canonical_objects=[entry.get("table") for entry in query_audit],
            frame=frame,
            provider_query_audit=query_audit,
        )
        return MarketDataFrameResult(frame=frame, audit=audit)

    def load_trading_calendar_index(
        self,
        *,
        start: date,
        end: date,
        asset_scope: str = "cn_a_equity",
        market: str | None = None,
    ) -> pd.DatetimeIndex:
        result = self.load_trading_calendar(
            start=start,
            end=end,
            asset_scope=asset_scope,
            market=market,
        )
        if result.frame.empty or "trade_date" not in result.frame.columns:
            return pd.DatetimeIndex([])
        trade_dates = pd.to_datetime(result.frame["trade_date"], errors="coerce").dropna()
        if trade_dates.empty:
            return pd.DatetimeIndex([])
        return pd.DatetimeIndex(trade_dates).normalize()

    def load_pit_constituents_snapshot(
        self,
        *,
        index_code: str,
        as_of_date: date,
        asset_scope: str = "cn_a_equity",
        market: str | None = None,
    ) -> MarketDataFrameResult:
        request = MarketDataRequest(
            asset_scope=asset_scope,
            market=market or _default_market_for_asset_scope(asset_scope),
            as_of_date=as_of_date,
            symbols=[index_code],
        )
        frame, query_audit = self._provider_call(
            self._provider.load_index_constituent_history,
            index_code,
            as_of_date,
            as_of_date,
        )
        if not frame.empty and "as_of_date" not in frame.columns:
            frame = frame.copy()
            frame["as_of_date"] = pd.Timestamp(as_of_date)
        audit = self._build_audit(
            capability="pit_constituents_snapshot",
            request=request,
            canonical_objects=[entry.get("table") for entry in query_audit] or ["pit_index_constituents"],
            frame=frame,
            provider_query_audit=query_audit,
        )
        return MarketDataFrameResult(frame=frame, audit=audit)

    def load_pit_constituents_window(
        self,
        *,
        index_code: str,
        start: date,
        end: date,
        asset_scope: str = "cn_a_equity",
        market: str | None = None,
    ) -> MarketDataFrameResult:
        request = MarketDataRequest(
            asset_scope=asset_scope,
            market=market or _default_market_for_asset_scope(asset_scope),
            window_start=start,
            window_end=end,
            symbols=[index_code],
        )
        frame, query_audit = self._provider_call(
            self._provider.load_index_constituent_history,
            index_code,
            start,
            end,
        )
        if "as_of_date" not in frame.columns:
            frame = frame.copy()
            frame["as_of_date"] = pd.NaT
        audit = self._build_audit(
            capability="pit_constituents_window",
            request=request,
            canonical_objects=[entry.get("table") for entry in query_audit] or ["pit_index_constituents"],
            frame=frame,
            provider_query_audit=query_audit,
        )
        return MarketDataFrameResult(frame=frame, audit=audit)

    def load_pit_industry_snapshot(
        self,
        *,
        as_of_date: date,
        symbols: list[str] | None = None,
        industries: list[str] | None = None,
        asset_scope: str = "cn_a_equity",
        market: str | None = None,
    ) -> MarketDataFrameResult:
        request = MarketDataRequest(
            asset_scope=asset_scope,
            market=market or _default_market_for_asset_scope(asset_scope),
            as_of_date=as_of_date,
            symbols=list(symbols or industries or []),
        )
        frame = self._load_pit_industry_frame(
            as_of_date=as_of_date,
            start=as_of_date,
            end=as_of_date,
            symbols=symbols,
            industries=industries,
        )
        if "as_of_date" not in frame.columns:
            frame["as_of_date"] = pd.Timestamp(as_of_date)
        audit = self._build_audit(
            capability="pit_industry_snapshot",
            request=request,
            canonical_objects=["pit_industry_history"],
            frame=frame,
        )
        return MarketDataFrameResult(frame=frame, audit=audit)

    def load_pit_industry_window(
        self,
        *,
        start: date,
        end: date,
        symbols: list[str] | None = None,
        industries: list[str] | None = None,
        asset_scope: str = "cn_a_equity",
        market: str | None = None,
    ) -> MarketDataFrameResult:
        request = MarketDataRequest(
            asset_scope=asset_scope,
            market=market or _default_market_for_asset_scope(asset_scope),
            window_start=start,
            window_end=end,
            symbols=list(symbols or industries or []),
        )
        frame = self._load_pit_industry_frame(
            as_of_date=None,
            start=start,
            end=end,
            symbols=symbols,
            industries=industries,
        )
        if "as_of_date" not in frame.columns:
            frame["as_of_date"] = pd.NaT
        audit = self._build_audit(
            capability="pit_industry_window",
            request=request,
            canonical_objects=["pit_industry_history"],
            frame=frame,
        )
        return MarketDataFrameResult(frame=frame, audit=audit)

    def load_security_master_snapshot(
        self,
        *,
        as_of_date: date,
        symbols: list[str],
        asset_scope: str = "cn_a_equity",
        market: str | None = None,
    ) -> MarketDataFrameResult:
        request = MarketDataRequest(
            asset_scope=asset_scope,
            market=market or _default_market_for_asset_scope(asset_scope),
            as_of_date=as_of_date,
            symbols=list(symbols),
        )
        frame, query_audit = self._provider_call(
            self._provider.load_security_master,
            list(symbols),
        )
        frame = self._normalize_security_master_frame(
            frame=frame,
            as_of_date=as_of_date,
            asset_scope=asset_scope,
            market=request.market,
        )
        audit = self._build_audit(
            capability="security_master_snapshot",
            request=request,
            canonical_objects=[entry.get("table") for entry in query_audit] or ["pit_security_master"],
            frame=frame,
            provider_query_audit=query_audit,
        )
        return MarketDataFrameResult(frame=frame, audit=audit)

    def load_active_cn_a_symbols(
        self,
        *,
        as_of_date: date,
        universe_limit: int | None = None,
    ) -> tuple[list[str], dict[str, Any]]:
        date_col = safe_ident(self._provider._resolved_stocks_mapping()["date"])
        table = safe_ident(self.canonical_stocks_table)
        sql = f"""
            WITH available AS (
              SELECT DISTINCT symbol
              FROM public.{table}
              WHERE {date_col} <= %s
            )
            SELECT DISTINCT sm.symbol AS symbol
            FROM public.pit_security_master sm
            JOIN available a ON a.symbol = sm.symbol
            WHERE sm.market_type = 'CN_A'
              AND sm.exchange IN ('SH', 'SZ')
              AND (sm.list_date IS NULL OR sm.list_date <= %s)
              AND (sm.delist_date IS NULL OR sm.delist_date > %s)
            ORDER BY sm.symbol
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    f"SET LOCAL statement_timeout = '{int(self._runtime_access.cfg_obj.db_runtime.statement_timeout_ms)}ms'"
                )
                cur.execute(sql, (as_of_date, as_of_date, as_of_date))
                rows = cur.fetchall()
        symbols = sorted(
            {
                normalize_stock_symbol(str(row[0]))
                for row in rows
                if row and row[0]
            }
        )
        raw_count = int(len(symbols))
        if universe_limit is not None:
            symbols = symbols[: int(universe_limit)]
        meta = {
            "symbols_source": "market_data_access:pit_security_master+canonical_market",
            "constituents_load_status": "OK" if raw_count > 0 else "EMPTY",
            "universe_limit": universe_limit,
            "raw_count": raw_count,
            "load_table": f"pit_security_master+{self.canonical_stocks_table}",
            "load_detail": "active_cn_a_with_canonical_ohlcv",
            "canonical_objects": ["pit_security_master", self.canonical_stocks_table],
            "query_version": QUERY_VERSION,
        }
        return symbols, meta

    def _load_pit_industry_frame(
        self,
        *,
        as_of_date: date | None,
        start: date,
        end: date,
        symbols: list[str] | None,
        industries: list[str] | None,
    ) -> pd.DataFrame:
        if symbols:
            frame, _ = self._provider_call(
                self._provider.load_industry_history,
                list(symbols),
                start,
                end,
            )
            frame = frame.copy()
            if "symbol" not in frame.columns and "ts_code" in frame.columns:
                frame["symbol"] = frame["ts_code"].astype(str).map(normalize_stock_symbol)
            return frame.loc[:, [col for col in ("symbol", "industry_l1", "industry_l2", "standard", "start_date", "end_date") if col in frame.columns]]
        if not industries:
            return pd.DataFrame(columns=["symbol", "industry_l1", "industry_l2", "standard", "start_date", "end_date"])
        placeholders = ", ".join(["%s"] * len(industries))
        sql = f"""
            SELECT ts_code, industry_l1, industry_l2, standard, start_date, end_date
            FROM public.pit_industry_history
            WHERE industry_l1 IN ({placeholders})
              AND start_date <= %s
              AND (end_date IS NULL OR end_date >= %s)
            ORDER BY ts_code, start_date
        """
        params = tuple(industries) + (end, start)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    f"SET LOCAL statement_timeout = '{int(self._runtime_access.cfg_obj.db_runtime.statement_timeout_ms)}ms'"
                )
                cur.execute(sql, params)
                rows = cur.fetchall()
                cols = [desc.name for desc in cur.description] if cur.description else []
        frame = pd.DataFrame(rows, columns=cols)
        if frame.empty:
            return pd.DataFrame(columns=["symbol", "industry_l1", "industry_l2", "standard", "start_date", "end_date"])
        frame["symbol"] = frame["ts_code"].astype(str).map(normalize_stock_symbol)
        return frame.loc[:, ["symbol", "industry_l1", "industry_l2", "standard", "start_date", "end_date"]]

    @staticmethod
    def _normalize_security_master_frame(
        *,
        frame: pd.DataFrame,
        as_of_date: date,
        asset_scope: str,
        market: str,
    ) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "ts_code",
                    "name",
                    "market",
                    "exchange",
                    "security_type",
                    "asset_scope",
                    "list_date",
                    "delist_date",
                    "is_active_at_asof",
                ]
            )
        out = frame.copy()
        if "symbol" in out.columns:
            out["symbol"] = out["symbol"].astype(str).map(normalize_stock_symbol)
        else:
            out["symbol"] = ""
        if "ts_code" not in out.columns:
            out["ts_code"] = out["symbol"].astype(str).map(_internal_symbol_to_ts_code)
        if "exchange" not in out.columns:
            out["exchange"] = out["symbol"].astype(str).map(_infer_exchange)
        if "market" not in out.columns:
            out["market"] = market
        if "security_type" not in out.columns:
            out["security_type"] = _default_security_type(asset_scope)
        if "asset_scope" not in out.columns:
            out["asset_scope"] = asset_scope
        if "name" not in out.columns:
            out["name"] = ""
        for col in ("list_date", "delist_date"):
            if col not in out.columns:
                out[col] = pd.NaT
            out[col] = pd.to_datetime(out[col], errors="coerce").dt.date.astype("object")
        out["is_active_at_asof"] = (
            (out["list_date"].isna() | (out["list_date"] <= as_of_date))
            & (out["delist_date"].isna() | (out["delist_date"] > as_of_date))
        )
        return out.loc[
            :,
            [
                "symbol",
                "ts_code",
                "name",
                "market",
                "exchange",
                "security_type",
                "asset_scope",
                "list_date",
                "delist_date",
                "is_active_at_asof",
            ],
        ]


def _infer_exchange(symbol: str) -> str:
    text = str(symbol or "").strip().lower()
    if text.startswith("sh"):
        return "SH"
    if text.startswith("sz"):
        return "SZ"
    if text.startswith("bj"):
        return "BJ"
    return ""


def _internal_symbol_to_ts_code(symbol: str) -> str:
    text = str(symbol or "").strip().lower()
    if len(text) == 8 and text[:2] in {"sh", "sz", "bj"}:
        return f"{text[2:]}.{text[:2].upper()}"
    return str(symbol or "").upper()


def _default_security_type(asset_scope: str) -> str:
    scope = str(asset_scope or "").strip().lower()
    if scope == "cn_etf":
        return "etf"
    if scope == "cn_a_equity":
        return "stock"
    return "security"


def build_market_data_access(runtime_access: RuntimeDataAccess) -> MarketDataAccess:
    return MarketDataAccess(runtime_access)


def load_market_data_access(
    bt_root: str | None = None,
    *,
    asset_scope: str | None = None,
) -> MarketDataAccess:
    from backend.core.tools.runtime_data_access import load_runtime_data_access

    return MarketDataAccess(load_runtime_data_access(bt_root, asset_scope=asset_scope))


__all__ = [
    "CALENDAR_VERSION",
    "DIRECT_CANONICAL_CACHE_VERSION",
    "QUERY_VERSION",
    "MarketDataAccess",
    "MarketDataAudit",
    "MarketDataFrameResult",
    "MarketDataRequest",
    "build_market_data_access",
    "load_market_data_access",
]
