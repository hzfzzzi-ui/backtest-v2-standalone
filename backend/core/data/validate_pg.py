from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.data.mapping import normalize_index_symbol, normalize_stock_symbol, ts_to_cn_index_symbol

try:
    import psycopg
except Exception as exc:  # pragma: no cover
    psycopg = None
    _PSYCOPG_IMPORT_ERROR = exc
else:
    _PSYCOPG_IMPORT_ERROR = None


def _default_results_root() -> Path:
    raw = os.environ.get("RESULTS_ROOT", "outputs").strip() or "outputs"
    p = Path(raw)
    if not p.is_absolute():
        p = (Path(__file__).resolve().parents[3] / p).resolve()
    return p


@dataclass(slots=True)
class PGConnConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str
    statement_timeout_ms: int = 60000


def _json_safe(value: Any) -> Any:
    if isinstance(value, (pd.Series, pd.Index)):
        return [_json_safe(v) for v in value.tolist()]
    if hasattr(value, "item") and callable(getattr(value, "item")):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, float):
        if pd.isna(value):
            return None
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, bool, str)) or value is None:
        return value
    if isinstance(value, (pd.Timestamp, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _pick_samples_for_symbol(df: pd.DataFrame, symbol: str, targets: list[date]) -> list[dict[str, Any]]:
    sub = df[df["symbol"] == symbol].copy()
    if sub.empty:
        return []
    out: list[dict[str, Any]] = []
    sub["trade_date"] = pd.to_datetime(sub["trade_date"]).dt.date
    for td in targets:
        exact = sub[sub["trade_date"] == td]
        row = None
        if not exact.empty:
            row = exact.iloc[0]
        else:
            # nearest row by absolute day distance
            tmp = sub.copy()
            tmp["dist"] = tmp["trade_date"].map(lambda d: abs((d - td).days))
            row = tmp.sort_values(["dist", "trade_date"]).iloc[0]
        out.append(
            {
                "symbol": symbol,
                "target_date": td.isoformat(),
                "trade_date": row["trade_date"].isoformat(),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
                "turnover": row.get("turnover"),
                "limit_up": row.get("limit_up"),
                "limit_down": row.get("limit_down"),
                "is_suspended": row.get("is_suspended"),
            }
        )
    return out


def _evaluate_frames(
    stocks_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    symbols: list[str],
    benchmark: str,
    strict_suspended: bool,
    allow_cn_index_fallback: bool,
    schema_ok: bool,
    schema_missing: dict[str, list[str]],
    start: date,
    end: date,
) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    warnings: list[dict[str, Any]] = []
    pass_flag = bool(schema_ok)

    if stocks_df.empty:
        checks["coverage"] = {"pass": False, "rows": 0, "symbols": len(symbols), "detail": "no stock rows in range"}
        pass_flag = False
    stocks = stocks_df.copy()
    if not stocks.empty:
        stocks["trade_date"] = pd.to_datetime(stocks["trade_date"]).dt.date
        for c in ["open", "high", "low", "close", "turnover", "limit_up", "limit_down"]:
            if c in stocks.columns:
                stocks[c] = pd.to_numeric(stocks[c], errors="coerce")
        if "volume" in stocks.columns:
            stocks["volume"] = pd.to_numeric(stocks["volume"], errors="coerce")

    checks["schema"] = {
        "pass": schema_ok,
        "missing_columns": schema_missing,
    }

    dup_count = 0
    if not stocks.empty:
        dup_count = int(stocks.duplicated(subset=["symbol", "trade_date"], keep=False).sum())
    checks["duplicates"] = {"pass": dup_count == 0, "duplicate_rows": dup_count}
    if dup_count > 0:
        pass_flag = False

    null_count = 0
    invalid_close = 0
    invalid_ohlc = 0
    neg_volume = 0
    neg_turnover = 0
    if not stocks.empty:
        null_count = int(stocks[["open", "high", "low", "close"]].isna().sum().sum())
        invalid_close = int((stocks["close"] <= 0).fillna(False).sum())
        invalid_ohlc = int(
            (
                (stocks["high"] < stocks[["open", "close", "low"]].max(axis=1))
                | (stocks["low"] > stocks[["open", "close", "high"]].min(axis=1))
            ).fillna(False).sum()
        )
        neg_volume = int((stocks["volume"] < 0).fillna(False).sum()) if "volume" in stocks.columns else 0
        neg_turnover = int((stocks["turnover"] < 0).fillna(False).sum()) if "turnover" in stocks.columns else 0

    sanity_pass = (null_count == 0 and invalid_close == 0 and invalid_ohlc == 0 and neg_volume == 0 and neg_turnover == 0)
    checks["nulls_sanity"] = {
        "pass": sanity_pass,
        "null_ohlc": null_count,
        "close_le_zero": invalid_close,
        "ohlc_relation_violations": invalid_ohlc,
        "negative_volume": neg_volume,
        "negative_turnover": neg_turnover,
    }
    if not sanity_pass:
        pass_flag = False

    limit_missing = 0
    limit_invalid = 0
    high_over_up = 0
    low_under_down = 0
    high_over_up_ratio = 0.0
    low_under_down_ratio = 0.0
    high_over_sample: list[dict[str, Any]] = []
    low_under_sample: list[dict[str, Any]] = []
    if not stocks.empty:
        limit_missing = int((stocks["limit_up"].isna() | stocks["limit_down"].isna()).sum())
        limit_invalid = int((stocks["limit_up"] <= stocks["limit_down"]).fillna(False).sum())
        high_over_up = int((stocks["high"] > stocks["limit_up"]).fillna(False).sum())
        low_under_down = int((stocks["low"] < stocks["limit_down"]).fillna(False).sum())
        total_rows = int(len(stocks))
        if total_rows > 0:
            high_over_up_ratio = high_over_up / total_rows
            low_under_down_ratio = low_under_down / total_rows
        if high_over_up > 0:
            bad_up = stocks[(stocks["high"] > stocks["limit_up"]).fillna(False)].copy()
            bad_up["diff_up"] = bad_up["high"].astype(float) - bad_up["limit_up"].astype(float)
            bad_up = bad_up.sort_values(["diff_up", "trade_date"], ascending=[False, True]).head(20)
            high_over_sample = [
                {
                    "symbol": r["symbol"],
                    "trade_date": r["trade_date"].isoformat(),
                    "open": r["open"],
                    "high": r["high"],
                    "low": r["low"],
                    "close": r["close"],
                    "limit_up": r["limit_up"],
                    "limit_down": r["limit_down"],
                    "volume": r["volume"],
                    "turnover": r["turnover"],
                    "is_suspended": r["is_suspended"],
                    "diff_up": r["diff_up"],
                    "diff_down": 0.0,
                }
                for _, r in bad_up.iterrows()
            ]
        if low_under_down > 0:
            bad_down = stocks[(stocks["low"] < stocks["limit_down"]).fillna(False)].copy()
            bad_down["diff_down"] = bad_down["limit_down"].astype(float) - bad_down["low"].astype(float)
            bad_down = bad_down.sort_values(["diff_down", "trade_date"], ascending=[False, True]).head(20)
            low_under_sample = [
                {
                    "symbol": r["symbol"],
                    "trade_date": r["trade_date"].isoformat(),
                    "open": r["open"],
                    "high": r["high"],
                    "low": r["low"],
                    "close": r["close"],
                    "limit_up": r["limit_up"],
                    "limit_down": r["limit_down"],
                    "volume": r["volume"],
                    "turnover": r["turnover"],
                    "is_suspended": r["is_suspended"],
                    "diff_up": 0.0,
                    "diff_down": r["diff_down"],
                }
                for _, r in bad_down.iterrows()
            ]
    limit_pass = (limit_missing == 0 and limit_invalid == 0)
    checks["limits"] = {
        "pass": limit_pass,
        "limit_missing": limit_missing,
        "limit_up_le_limit_down": limit_invalid,
        "high_gt_limit_up": high_over_up,
        "low_lt_limit_down": low_under_down,
        "high_gt_limit_up_ratio": round(high_over_up_ratio, 6),
        "low_lt_limit_down_ratio": round(low_under_down_ratio, 6),
        "limits_violations_sample": {
            "high_gt_limit_up": high_over_sample,
            "low_lt_limit_down": low_under_sample,
        },
    }
    if not limit_pass:
        pass_flag = False
    if high_over_up > 0 or low_under_down > 0:
        warnings.append(
            {
                "code": "LIMIT_FIELD_INCONSISTENCY",
                "message": f"LIMIT_FIELD_INCONSISTENCY: high>limit_up count={high_over_up}, low<limit_down count={low_under_down}, sample_included=true",
                "high_gt_limit_up": high_over_up,
                "low_lt_limit_down": low_under_down,
            }
        )

    suspended_null = 0
    inconsistent_suspend = 0
    if not stocks.empty:
        suspended_null = int(stocks["is_suspended"].isna().sum())
        inconsistent_suspend = int(
            (((stocks["is_suspended"] == True) & (stocks["volume"] > 0)) | ((stocks["is_suspended"] == False) & (stocks["volume"] == 0)))
            .fillna(False)
            .sum()
        )
    suspended_pass = (suspended_null == 0 and inconsistent_suspend == 0) if strict_suspended else True
    checks["suspended"] = {
        "pass": suspended_pass,
        "strict_suspended": strict_suspended,
        "is_suspended_null": suspended_null,
        "inconsistent_suspend_vs_volume": inconsistent_suspend,
    }
    if (suspended_null > 0 or inconsistent_suspend > 0) and not strict_suspended:
        warnings.append(
            {
                "code": "SUSPENDED_WARNING",
                "message": "suspended flags and volume have inconsistencies",
                "is_suspended_null": suspended_null,
                "inconsistent_suspend_vs_volume": inconsistent_suspend,
            }
        )
    if strict_suspended and not suspended_pass:
        pass_flag = False

    coverage_rows: list[dict[str, Any]] = []
    if not stocks.empty:
        grp = stocks.groupby("symbol", as_index=False)["trade_date"].nunique().rename(columns={"trade_date": "days"})
        for _, r in grp.iterrows():
            coverage_rows.append({"symbol": r["symbol"], "days": int(r["days"])})
        total_days = max((end - start).days + 1, 1)
        low_cov = [r for r in coverage_rows if r["days"] < max(5, int(total_days * 0.1))]
        if low_cov:
            warnings.append(
                {
                    "code": "LOW_COVERAGE_WARNING",
                    "message": "some symbols have low day coverage in range",
                    "symbols": low_cov,
                }
            )
    checks["coverage"] = {"pass": True, "by_symbol": coverage_rows}

    benchmark_rows = int(len(benchmark_df))
    benchmark_pass = benchmark_rows > 0
    if not benchmark_pass:
        pass_flag = False
    checks["benchmark"] = {
        "pass": benchmark_pass,
        "rows": benchmark_rows,
        "benchmark": benchmark,
        "allow_cn_index_fallback": allow_cn_index_fallback,
    }

    sample_targets = [start - timedelta(days=1), start, end]
    samples = {
        "stocks_rows": sum([_pick_samples_for_symbol(stocks, s, sample_targets) for s in sorted(set(stocks["symbol"].tolist()))], []),
        "benchmark_rows": _pick_samples_for_symbol(
            benchmark_df.rename(columns={"index_code": "symbol"}), benchmark, sample_targets
        )
        if not benchmark_df.empty
        else [],
    }

    return {
        "pass": bool(pass_flag),
        "checks": checks,
        "warnings": warnings,
        "samples": samples,
    }


def validate_data(
    pg: PGConnConfig,
    symbols: list[str],
    start: date,
    end: date,
    benchmark: str,
    audit_dump: bool = True,
    strict_suspended: bool = False,
    allow_cn_index_fallback: bool = False,
    results_root: Path | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    if psycopg is None:  # pragma: no cover
        raise RuntimeError(f"psycopg is required: {_PSYCOPG_IMPORT_ERROR}")

    started = time.time()
    rid = request_id or f"val_{uuid.uuid4().hex[:12]}"
    norm_symbols = [normalize_stock_symbol(s) for s in symbols]
    bench_ts = normalize_index_symbol(benchmark)
    schema_missing: dict[str, list[str]] = {"pams_ohlcv_daily": [], "pit_index_daily": []}

    with psycopg.connect(
        host=pg.host,
        port=pg.port,
        dbname=pg.dbname,
        user=pg.user,
        password=pg.password,
        autocommit=False,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(f"SET LOCAL statement_timeout = '{int(pg.statement_timeout_ms)}ms'")

            cur.execute(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name IN ('pams_ohlcv_daily','pit_index_daily')
                """
            )
            col_rows = cur.fetchall()
            cols: dict[str, set[str]] = {"pams_ohlcv_daily": set(), "pit_index_daily": set()}
            for t, c in col_rows:
                cols[str(t)].add(str(c))
            need_stocks = {"symbol", "market", "trade_date", "open", "high", "low", "close", "volume", "turnover", "limit_up", "limit_down", "is_suspended"}
            need_index = {"index_code", "trade_date", "open", "high", "low", "close", "volume", "turnover"}
            schema_missing["pams_ohlcv_daily"] = sorted(list(need_stocks - cols.get("pams_ohlcv_daily", set())))
            schema_missing["pit_index_daily"] = sorted(list(need_index - cols.get("pit_index_daily", set())))
            schema_ok = not schema_missing["pams_ohlcv_daily"] and not schema_missing["pit_index_daily"]

            cur.execute(
                """
                SELECT symbol, market, trade_date, open, high, low, close, volume, turnover, limit_up, limit_down, is_suspended
                FROM pams_ohlcv_daily
                WHERE market='CN_A'
                  AND symbol = ANY(%s)
                  AND trade_date >= %s
                  AND trade_date <= %s
                ORDER BY symbol, trade_date
                """,
                (norm_symbols, start, end),
            )
            stocks = pd.DataFrame(
                cur.fetchall(),
                columns=[
                    "symbol",
                    "market",
                    "trade_date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "turnover",
                    "limit_up",
                    "limit_down",
                    "is_suspended",
                ],
            )

            cur.execute(
                """
                SELECT index_code, trade_date, open, high, low, close, volume, turnover
                FROM pit_index_daily
                WHERE index_code = %s
                  AND trade_date >= %s
                  AND trade_date <= %s
                ORDER BY trade_date
                """,
                (bench_ts, start, end),
            )
            benchmark_df = pd.DataFrame(
                cur.fetchall(),
                columns=["index_code", "trade_date", "open", "high", "low", "close", "volume", "turnover"],
            )

            if benchmark_df.empty and allow_cn_index_fallback:
                internal_benchmark = ts_to_cn_index_symbol(benchmark)
                cur.execute(
                    """
                    SELECT symbol AS index_code, trade_date, open, high, low, close, volume, turnover
                    FROM pams_ohlcv_daily
                    WHERE market='CN_INDEX'
                      AND symbol = %s
                      AND trade_date >= %s
                      AND trade_date <= %s
                    ORDER BY trade_date
                    """,
                    (internal_benchmark, start, end),
                )
                benchmark_df = pd.DataFrame(
                    cur.fetchall(),
                    columns=["index_code", "trade_date", "open", "high", "low", "close", "volume", "turnover"],
                )

    evaluated = _evaluate_frames(
        stocks_df=stocks,
        benchmark_df=benchmark_df,
        symbols=norm_symbols,
        benchmark=bench_ts,
        strict_suspended=strict_suspended,
        allow_cn_index_fallback=allow_cn_index_fallback,
        schema_ok=schema_ok,
        schema_missing=schema_missing,
        start=start,
        end=end,
    )
    elapsed_ms = int((time.time() - started) * 1000)
    out: dict[str, Any] = {
        "pass": bool(evaluated["pass"]),
        "request_id": rid,
        "meta": {
            "elapsed_ms": elapsed_ms,
            "symbols_count": len(norm_symbols),
            "symbols": norm_symbols,
            "date_range": {"start": start.isoformat(), "end": end.isoformat()},
            "benchmark": bench_ts,
            "strict_suspended": bool(strict_suspended),
            "allow_cn_index_fallback": bool(allow_cn_index_fallback),
        },
        "checks": evaluated["checks"],
        "warnings": evaluated["warnings"],
        "samples": evaluated["samples"],
    }
    out = _json_safe(out)

    if audit_dump:
        root = (results_root or _default_results_root()) / rid / "audit"
        root.mkdir(parents=True, exist_ok=True)
        (root / "validate_data.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return out
