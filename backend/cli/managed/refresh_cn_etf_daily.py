from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from backend.core.data.cn_etf_catalog import list_seeded_entries, normalize_cn_etf_ts_code
from . import cn_side_table_common as common


DAILY_TABLE = "pams_cn_etf_daily"
COVERAGE_TABLE = "cn_etf_data_coverage_daily"
DIVIDEND_TABLE = "pit_cn_etf_dividend_events"
PRICE_SERIES_SEMANTICS = "executable_price_only_not_total_return"


_REQUIRED_COLUMNS = {
    DAILY_TABLE: frozenset({
        "trade_date", "symbol", "ts_code", "open", "high", "low", "close", "volume", "turnover", "amount",
        "adj_factor", "price_adjust_mode", "price_series_semantics", "source", "build_run_id",
        "latest_refresh_at", "created_at", "updated_at",
    }),
    COVERAGE_TABLE: frozenset({
        "ts_code", "symbol", "batch_id", "exposure_bucket", "coverage_start", "coverage_end", "row_count",
        "latest_refresh_at", "daily_table", "price_series_semantics", "created_at", "updated_at",
    }),
    DIVIDEND_TABLE: frozenset({
        "event_id", "ts_code", "symbol", "ann_date", "imp_ann_date", "base_date", "record_date", "ex_date",
        "pay_date", "earpay_date", "net_ex_date", "div_proc", "div_cash", "base_unit", "ear_distr", "source",
        "build_run_id", "latest_refresh_at", "created_at", "updated_at",
    }),
}


def _ensure_tables(cur) -> None:
    """Require pre-provisioned ETF schema without executing DDL."""
    for table, required in _REQUIRED_COLUMNS.items():
        cur.execute(
            "SELECT attname FROM pg_attribute WHERE attrelid = to_regclass(%s) "
            "AND attnum > 0 AND NOT attisdropped",
            (f"public.{table}",),
        )
        columns = {row[0] for row in cur.fetchall()}
        missing = required - columns
        if missing:
            raise RuntimeError(
                f"required ETF schema public.{table} is missing or incomplete: {', '.join(sorted(missing))}; "
                "provision it separately"
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


def _load_tushare_adj_factor(pro, ts_code: str, start_date: date, end_date: date) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    window_start = start_date
    window_days = 1200
    while window_start <= end_date:
        window_end = min(window_start + timedelta(days=window_days - 1), end_date)
        raw = pro.query(
            "fund_adj",
            ts_code=ts_code,
            start_date=window_start.strftime("%Y%m%d"),
            end_date=window_end.strftime("%Y%m%d"),
        )
        if raw is not None and not raw.empty:
            frames.append(raw.copy())
        window_start = window_end + timedelta(days=1)
    if not frames:
        return pd.DataFrame(columns=["trade_date", "ts_code", "adj_factor"])
    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset=["trade_date"], keep="last")
    return merged


def _load_tushare_dividend_events(pro, ts_code: str) -> pd.DataFrame:
    loader = getattr(pro, "fund_div", None)
    if callable(loader):
        raw = loader(ts_code=ts_code)
    else:
        raw = pro.query("fund_div", ts_code=ts_code)
    if raw is None or raw.empty:
        return pd.DataFrame(
            columns=[
                "ts_code",
                "ann_date",
                "imp_ann_date",
                "base_date",
                "div_proc",
                "record_date",
                "ex_date",
                "pay_date",
                "earpay_date",
                "net_ex_date",
                "div_cash",
                "base_unit",
                "ear_distr",
            ]
        )
    return raw.copy()


def _normalize_event_id(ts_code: str, row: pd.Series) -> str:
    ex_date = str(row.get("ex_date") or "")
    pay_date = str(row.get("pay_date") or row.get("earpay_date") or "")
    record_date = str(row.get("record_date") or "")
    div_cash = float(pd.to_numeric(row.get("div_cash"), errors="coerce") or 0.0)
    return f"{normalize_cn_etf_ts_code(ts_code)}|{ex_date}|{pay_date}|{record_date}|{div_cash:.8f}"


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
    dividend_rows_inserted = 0
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
                raw_adj = _load_tushare_adj_factor(pro, ts_code, requested_start, target_end)
                raw["trade_date"] = pd.to_datetime(raw["trade_date"], format="%Y%m%d", errors="coerce").dt.date
                raw = raw.dropna(subset=["trade_date"]).sort_values("trade_date")
                if not raw_adj.empty:
                    raw_adj["trade_date"] = pd.to_datetime(raw_adj["trade_date"], format="%Y%m%d", errors="coerce").dt.date
                    raw_adj["adj_factor"] = pd.to_numeric(raw_adj["adj_factor"], errors="coerce")
                    raw_adj = raw_adj.dropna(subset=["trade_date"]).sort_values("trade_date")
                    raw = raw.merge(
                        raw_adj.loc[:, ["trade_date", "adj_factor"]],
                        on="trade_date",
                        how="left",
                    )
                raw["adj_factor"] = pd.to_numeric(raw.get("adj_factor"), errors="coerce").fillna(1.0)
                raw_div = _load_tushare_dividend_events(pro, ts_code)
                if not raw_div.empty:
                    for col in ("ann_date", "imp_anndate", "base_date", "record_date", "ex_date", "pay_date", "earpay_date", "net_ex_date"):
                        if col in raw_div.columns:
                            raw_div[col] = pd.to_datetime(raw_div[col], format="%Y%m%d", errors="coerce").dt.date
                    raw_div = raw_div.rename(columns={"imp_anndate": "imp_ann_date"})
                    raw_div["div_cash"] = pd.to_numeric(raw_div.get("div_cash"), errors="coerce")
                    raw_div = raw_div.dropna(subset=["ex_date", "div_cash"]).sort_values(["ex_date", "pay_date", "record_date"])
                    raw_div["event_id"] = raw_div.apply(lambda row: _normalize_event_id(ts_code, row), axis=1)
                    raw_div = raw_div.drop_duplicates(subset=["event_id"], keep="last")
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
                                adj_factor,
                                price_adjust_mode,
                                price_series_semantics,
                                source,
                                build_run_id,
                                latest_refresh_at,
                                updated_at
                            )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                        ON CONFLICT (trade_date, symbol) DO UPDATE SET
                            ts_code = EXCLUDED.ts_code,
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            turnover = EXCLUDED.turnover,
                            amount = EXCLUDED.amount,
                            adj_factor = EXCLUDED.adj_factor,
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
                            float(getattr(row, "adj_factor", 1.0) or 1.0),
                            "none",
                            PRICE_SERIES_SEMANTICS,
                            "tushare_fund_daily",
                            build_run_id,
                        ),
                    )
                rows_inserted += int(len(raw))
                if not raw_div.empty:
                    for row in raw_div.itertuples(index=False):
                        cur.execute(
                            f"""
                            INSERT INTO public.{DIVIDEND_TABLE}
                                (
                                    event_id,
                                    ts_code,
                                    symbol,
                                    ann_date,
                                    imp_ann_date,
                                    base_date,
                                    record_date,
                                    ex_date,
                                    pay_date,
                                    earpay_date,
                                    net_ex_date,
                                    div_proc,
                                    div_cash,
                                    base_unit,
                                    ear_distr,
                                    source,
                                    build_run_id,
                                    latest_refresh_at,
                                    updated_at
                                )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                            ON CONFLICT (event_id) DO UPDATE SET
                                ts_code = EXCLUDED.ts_code,
                                symbol = EXCLUDED.symbol,
                                ann_date = EXCLUDED.ann_date,
                                imp_ann_date = EXCLUDED.imp_ann_date,
                                base_date = EXCLUDED.base_date,
                                record_date = EXCLUDED.record_date,
                                ex_date = EXCLUDED.ex_date,
                                pay_date = EXCLUDED.pay_date,
                                earpay_date = EXCLUDED.earpay_date,
                                net_ex_date = EXCLUDED.net_ex_date,
                                div_proc = EXCLUDED.div_proc,
                                div_cash = EXCLUDED.div_cash,
                                base_unit = EXCLUDED.base_unit,
                                ear_distr = EXCLUDED.ear_distr,
                                source = EXCLUDED.source,
                                build_run_id = EXCLUDED.build_run_id,
                                latest_refresh_at = NOW(),
                                updated_at = NOW()
                            """,
                            (
                                str(getattr(row, "event_id")),
                                ts_code,
                                entry.symbol,
                                getattr(row, "ann_date", None),
                                getattr(row, "imp_ann_date", None),
                                getattr(row, "base_date", None),
                                getattr(row, "record_date", None),
                                getattr(row, "ex_date", None),
                                getattr(row, "pay_date", None),
                                getattr(row, "earpay_date", None),
                                getattr(row, "net_ex_date", None),
                                str(getattr(row, "div_proc", "") or ""),
                                float(getattr(row, "div_cash", 0.0) or 0.0),
                                float(getattr(row, "base_unit", 0.0) or 0.0),
                                float(getattr(row, "ear_distr", 0.0) or 0.0),
                                "tushare_fund_div",
                                build_run_id,
                            ),
                        )
                    dividend_rows_inserted += int(len(raw_div))
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
                        "dividend_events": int(len(raw_div)),
                    }
                )
        conn.commit()

    payload = {
        "daily_table": DAILY_TABLE,
        "coverage_table": COVERAGE_TABLE,
        "dividend_table": DIVIDEND_TABLE,
        "build_run_id": build_run_id,
        "start_date": requested_start.isoformat(),
        "end_date": target_end.isoformat(),
        "symbols": selected_symbols,
        "rows_inserted": rows_inserted,
        "dividend_rows_inserted": dividend_rows_inserted,
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
