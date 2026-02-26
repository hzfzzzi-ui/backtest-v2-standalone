from __future__ import annotations

from datetime import date

import pandas as pd

from .mapping import normalize_index_symbol, normalize_stock_symbol, to_canonical
from .provider import DataProvider
from .rules_loader import load_rules_csv


class InMemoryDataProvider(DataProvider):
    def __init__(
        self,
        stocks_df: pd.DataFrame,
        index_df: pd.DataFrame | None = None,
        rules_df: pd.DataFrame | None = None,
        rules_path: str | None = None,
        schema_mapping: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self._stocks = stocks_df.copy()
        self._index = pd.DataFrame() if index_df is None else index_df.copy()
        self._rules = rules_df.copy() if rules_df is not None else None
        self._rules_path = rules_path
        self._schema = schema_mapping or {
            "stocks": {"date": "date", "symbol": "symbol", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume", "amount": "amount"},
            "index": {"date": "date", "symbol": "symbol", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume", "amount": "amount"},
        }
        self._audit: list[dict] = []

    @property
    def query_audit(self) -> list[dict]:
        return list(self._audit)

    def load_ohlcv_daily(self, symbols: list[str], start: date, end: date, source: str) -> pd.DataFrame:
        syms = {normalize_stock_symbol(s) for s in symbols}
        raw = self._stocks.copy()
        mapping = self._schema["stocks"]
        can, warnings = to_canonical(raw, mapping)
        can["symbol"] = can["symbol"].str.lower()
        out = can[(can["symbol"].isin(syms)) & (can["date"] >= pd.Timestamp(start)) & (can["date"] <= pd.Timestamp(end))].copy()
        self._audit.append({
            "provider": "memory",
            "source": source,
            "table": "stocks",
            "symbols": sorted(syms),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "row_count": int(len(out)),
            "warnings": warnings,
            "query_template": "memory:stocks",
        })
        return out.reset_index(drop=True)

    def load_benchmark_daily(self, benchmark_symbol: str, start: date, end: date) -> pd.DataFrame:
        target_ts = normalize_index_symbol(benchmark_symbol)
        target_internal = normalize_stock_symbol(target_ts)
        mapping = self._schema["index"]
        can, warnings = to_canonical(self._index.copy(), mapping)
        can["symbol"] = can["symbol"].astype(str)
        out = can[(can["symbol"].isin({target_ts, target_internal, benchmark_symbol})) & (can["date"] >= pd.Timestamp(start)) & (can["date"] <= pd.Timestamp(end))].copy()
        self._audit.append({
            "provider": "memory",
            "source": "benchmark",
            "table": "index",
            "symbols": [benchmark_symbol],
            "start": start.isoformat(),
            "end": end.isoformat(),
            "row_count": int(len(out)),
            "warnings": warnings,
            "query_template": "memory:index",
        })
        out["symbol"] = benchmark_symbol
        return out.reset_index(drop=True)

    def load_trading_calendar_cn(self, start: date, end: date) -> pd.DatetimeIndex:
        s = self._stocks[self._stocks["date"].between(pd.Timestamp(start), pd.Timestamp(end), inclusive="both")]["date"]
        dates = pd.to_datetime(sorted(set(pd.to_datetime(s).dt.normalize())))
        return pd.DatetimeIndex(dates)

    def get_previous_trading_day_cn(self, start: date) -> date | None:
        dates = pd.to_datetime(self._stocks["date"]).dt.normalize()
        prior = dates[dates < pd.Timestamp(start)]
        if prior.empty:
            return None
        return pd.Timestamp(prior.max()).date()

    def load_instrument_rules(self, symbols: list[str]) -> pd.DataFrame:
        if self._rules is not None:
            out = self._rules.copy()
        elif self._rules_path:
            out = load_rules_csv(self._rules_path, symbols)
        else:
            out = pd.DataFrame(
                {
                    "symbol": [s.upper() for s in symbols],
                    "board": "MAIN",
                    "type": "STOCK",
                    "lot_size": 100,
                    "tick_size": 0.01,
                    "limit_pct": 0.1,
                    "stamp_tax_sell": True,
                }
            )
        return out.sort_values("symbol").reset_index(drop=True)
