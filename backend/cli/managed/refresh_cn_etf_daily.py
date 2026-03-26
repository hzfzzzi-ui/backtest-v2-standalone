from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from backend.core.data.cn_etf_catalog import list_seeded_entries, normalize_cn_etf_ts_code
from . import cn_side_table_common as common


DAILY_TABLE = "pams_cn_etf_daily"
COVERAGE_TABLE = "cn_etf_data_coverage_daily"
PRICE_SERIES_SEMANTICS = "executable_price_only_not_total_return"


def _ensure_tables(cur) -> None:
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.{DAILY_TABLE} (
            trade_date DATE NOT NULL,
            symbol VARCHAR(16) NOT NULL,
            ts_code VARCHAR(16) NOT NULL,
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION,
            volume DOUBLE PRECISION,
            turnover DOUBLE PRECISION,
            amount DOUBLE PRECISION,
            price_adjust_mode TEXT NOT NULL DEFAULT 'none',
            price_series_semantics TEXT NOT NULL DEFAULT '{PRICE_SERIES_SEMANTICS}',
            source TEXT NOT NULL,
            build_run_id TEXT NOT NULL,
            latest_refresh_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (trade_date, symbol)
        )
        """
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.{COVERAGE_TABLE} (
            ts_code VARCHAR(16) PRIMARY KEY,
            symbol VARCHAR(16) NOT NULL UNIQUE,
            batch_id TEXT NOT NULL,
            exposure_bucket TEXT NOT NULL,
            coverage_start DATE,
            coverage_end DATE,
            row_count BIGINT NOT NULL DEFAULT 0,
            latest_refresh_at TIMESTAMPTZ,
            daily_table TEXT NOT NULL DEFAULT '{DAILY_TABLE}',
            price_series_semantics TEXT NOT NULL DEFAULT '{PRICE_SERIES_SEMANTICS}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def _resolve_target_end(pro, explicit_end: str) -> date:
    if str(explicit_end or "").strip():
        return date.fromisoformat(str(explicit_end).strip())
    latest_trade_date = common.resolve_latest_trade_date(pro)
    if latest_trade_date is None:
        raise RuntimeError("failed to resolve latest trade date for cn_etf daily refresh")
    return latest_trade_date


def _read_catalog_symbols(symbols_csv: str) -> list[str]:
    requested = {normalize_cn_etf_ts_code(item) for item in str(symbols_csv or "").split(",") if str(item).strip()}
    supported = {entry.ts_code for entry in list_seeded_entries()}
    if not requested:
        return sorted(supported)
    unsupported = sorted(requested - supported)
    if unsupported:
        raise RuntimeError(f"unsupported cn_etf symbols: {', '.join(unsupported)}")
    return sorted(requested)


def _load_tushare_daily(pro, ts_code: str, start_date: date, end_date: date) -> pd.DataFrame:
    raw = pro.fund_daily(
        ts_code=ts_code,
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["trade_date", "ts_code", "open", "high", "low", "close", "vol", "amount"])
    return raw.copy()


def run_refresh(
    *,
    token: str,
    start: str = "",
    end: str = "",
    symbols_csv: str = "",
    summary_out: Path | None = None,
) -> dict[str, object]:
    pro = common.load_tushare_client(token)
    selected_symbols = _read_catalog_symbols(symbols_csv)
    target_end = _resolve_target_end(pro, end)
    requested_start = date.fromisoformat(str(start).strip()) if str(start or "").strip() else date(2013, 1, 1)
    build_run_id = f"cn_etf_daily_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    rows_inserted = 0
    per_symbol_summary: list[dict[str, object]] = []

    with common.connect() as conn:
        with conn.cursor() as cur:
            _ensure_tables(cur)
            catalog_rows = {entry.ts_code: entry for entry in list_seeded_entries() if entry.ts_code in selected_symbols}
            for ts_code in selected_symbols:
                entry = catalog_rows[ts_code]
                raw = _load_tushare_daily(pro, ts_code, requested_start, target_end)
                if raw.empty:
                    per_symbol_summary.append({"ts_code": ts_code, "symbol": entry.symbol, "rows": 0})
                    continue
                raw["trade_date"] = pd.to_datetime(raw["trade_date"], format="%Y%m%d", errors="coerce").dt.date
                raw = raw.dropna(subset=["trade_date"]).sort_values("trade_date")
                for row in raw.itertuples(index=False):
                    cur.execute(
                        f"""
                        INSERT INTO public.{DAILY_TABLE}
                            (
                                trade_date,
                                symbol,
                                ts_code,
                                open,
                                high,
                                low,
                                close,
                                volume,
                                turnover,
                                amount,
                                price_adjust_mode,
                                price_series_semantics,
                                source,
                                build_run_id,
                                latest_refresh_at,
                                updated_at
                            )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                        ON CONFLICT (trade_date, symbol) DO UPDATE SET
                            ts_code = EXCLUDED.ts_code,
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            turnover = EXCLUDED.turnover,
                            amount = EXCLUDED.amount,
                            price_adjust_mode = EXCLUDED.price_adjust_mode,
                            price_series_semantics = EXCLUDED.price_series_semantics,
                            source = EXCLUDED.source,
                            build_run_id = EXCLUDED.build_run_id,
                            latest_refresh_at = NOW(),
                            updated_at = NOW()
                        """,
                        (
                            row.trade_date,
                            entry.symbol,
                            ts_code,
                            float(getattr(row, "open", 0.0) or 0.0),
                            float(getattr(row, "high", 0.0) or 0.0),
                            float(getattr(row, "low", 0.0) or 0.0),
                            float(getattr(row, "close", 0.0) or 0.0),
                            float(getattr(row, "vol", 0.0) or 0.0),
                            float(getattr(row, "amount", 0.0) or 0.0),
                            float(getattr(row, "amount", 0.0) or 0.0),
                            "none",
                            PRICE_SERIES_SEMANTICS,
                            "tushare_fund_daily",
                            build_run_id,
                        ),
                    )
                rows_inserted += int(len(raw))
                cur.execute(
                    f"""
                    INSERT INTO public.{COVERAGE_TABLE}
                        (
                            ts_code,
                            symbol,
                            batch_id,
                            exposure_bucket,
                            coverage_start,
                            coverage_end,
                            row_count,
                            latest_refresh_at,
                            daily_table,
                            price_series_semantics,
                            updated_at
                        )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        (SELECT MIN(trade_date) FROM public.{DAILY_TABLE} WHERE symbol = %s),
                        (SELECT MAX(trade_date) FROM public.{DAILY_TABLE} WHERE symbol = %s),
                        (SELECT COUNT(*) FROM public.{DAILY_TABLE} WHERE symbol = %s),
                        NOW(),
                        %s,
                        %s,
                        NOW()
                    )
                    ON CONFLICT (ts_code) DO UPDATE SET
                        symbol = EXCLUDED.symbol,
                        batch_id = EXCLUDED.batch_id,
                        exposure_bucket = EXCLUDED.exposure_bucket,
                        coverage_start = EXCLUDED.coverage_start,
                        coverage_end = EXCLUDED.coverage_end,
                        row_count = EXCLUDED.row_count,
                        latest_refresh_at = NOW(),
                        daily_table = EXCLUDED.daily_table,
                        price_series_semantics = EXCLUDED.price_series_semantics,
                        updated_at = NOW()
                    """,
                    (
                        ts_code,
                        entry.symbol,
                        entry.batch_id,
                        entry.exposure_bucket,
                        entry.symbol,
                        entry.symbol,
                        entry.symbol,
                        DAILY_TABLE,
                        PRICE_SERIES_SEMANTICS,
                    ),
                )
                per_symbol_summary.append(
                    {
                        "ts_code": ts_code,
                        "symbol": entry.symbol,
                        "rows": int(len(raw)),
                        "coverage_start": raw["trade_date"].min().isoformat(),
                        "coverage_end": raw["trade_date"].max().isoformat(),
                    }
                )
        conn.commit()

    payload = {
        "daily_table": DAILY_TABLE,
        "coverage_table": COVERAGE_TABLE,
        "build_run_id": build_run_id,
        "start_date": requested_start.isoformat(),
        "end_date": target_end.isoformat(),
        "symbols": selected_symbols,
        "rows_inserted": rows_inserted,
        "price_series_semantics": PRICE_SERIES_SEMANTICS,
        "per_symbol": per_symbol_summary,
    }
    if summary_out is not None:
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        summary_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh seeded cn_etf daily bars into pams_cn_etf_daily")
    parser.add_argument("--token", default="", help="Tushare token")
    parser.add_argument("--start", default="", help="optional inclusive start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="", help="optional inclusive end date (YYYY-MM-DD)")
    parser.add_argument("--symbols-csv", default="", help="optional whitelist subset")
    parser.add_argument("--summary-out", default="", help="optional summary json output path")
    args = parser.parse_args()
    token = common.resolve_tushare_token(args.token)
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is required for cn_etf daily refresh")
    summary_path = Path(args.summary_out).resolve() if str(args.summary_out or "").strip() else None
    payload = run_refresh(
        token=token,
        start=str(args.start or ""),
        end=str(args.end or ""),
        symbols_csv=str(args.symbols_csv or ""),
        summary_out=summary_path,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
