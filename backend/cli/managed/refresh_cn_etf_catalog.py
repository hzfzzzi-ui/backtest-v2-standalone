from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.core.data.cn_etf_catalog import list_seeded_entries
from . import cn_side_table_common as common


CATALOG_TABLE = "pit_cn_etf_master"
DEFAULT_SOURCE = "cn_etf_first_wave_seeded_catalog"


def _normalize_optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.lower() in {"nan", "nat", "none", "null"}:
        return None
    return text


def _ensure_table(cur) -> None:
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS public.{CATALOG_TABLE} (
            ts_code VARCHAR(16) PRIMARY KEY,
            symbol VARCHAR(16) NOT NULL UNIQUE,
            name TEXT NOT NULL,
            exchange VARCHAR(8) NOT NULL,
            batch_id TEXT NOT NULL,
            exposure_bucket TEXT NOT NULL,
            list_date DATE,
            delist_date DATE,
            source TEXT NOT NULL,
            latest_refresh_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def _load_tushare_catalog_rows(token: str) -> dict[str, dict[str, Any]]:
    if not token:
        return {}
    pro = common.load_tushare_client(token)
    raw = pro.fund_basic(market="E")
    if raw is None or raw.empty:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in raw.to_dict(orient="records"):
        ts_code = str(row.get("ts_code") or "").strip().upper()
        if not ts_code:
            continue
        out[ts_code] = row
    return out


def run_refresh(*, token: str = "", source: str = DEFAULT_SOURCE, summary_out: Path | None = None) -> dict[str, Any]:
    tushare_rows = _load_tushare_catalog_rows(token)
    refresh_at = datetime.now().isoformat()
    upserted = 0
    rows_written: list[dict[str, Any]] = []
    with common.connect() as conn:
        with conn.cursor() as cur:
            _ensure_table(cur)
            for entry in list_seeded_entries():
                ts_row = tushare_rows.get(entry.ts_code, {})
                name = str(ts_row.get("name") or entry.name).strip() or entry.name
                list_date = _normalize_optional_text(ts_row.get("list_date"))
                if list_date is None:
                    list_date = _normalize_optional_text(entry.list_date)
                delist_date = _normalize_optional_text(ts_row.get("delist_date"))
                if delist_date is None:
                    delist_date = _normalize_optional_text(entry.delist_date)
                cur.execute(
                    f"""
                    INSERT INTO public.{CATALOG_TABLE}
                        (
                            ts_code,
                            symbol,
                            name,
                            exchange,
                            batch_id,
                            exposure_bucket,
                            list_date,
                            delist_date,
                            source,
                            latest_refresh_at,
                            updated_at
                        )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (ts_code) DO UPDATE SET
                        symbol = EXCLUDED.symbol,
                        name = EXCLUDED.name,
                        exchange = EXCLUDED.exchange,
                        batch_id = EXCLUDED.batch_id,
                        exposure_bucket = EXCLUDED.exposure_bucket,
                        list_date = EXCLUDED.list_date,
                        delist_date = EXCLUDED.delist_date,
                        source = EXCLUDED.source,
                        latest_refresh_at = NOW(),
                        updated_at = NOW()
                    """,
                    (
                        entry.ts_code,
                        entry.symbol,
                        name,
                        entry.exchange,
                        entry.batch_id,
                        entry.exposure_bucket,
                        list_date,
                        delist_date,
                        source if not ts_row else "tushare_fund_basic",
                    ),
                )
                upserted += 1
                rows_written.append(
                    {
                        "ts_code": entry.ts_code,
                        "symbol": entry.symbol,
                        "name": name,
                        "exchange": entry.exchange,
                        "batch_id": entry.batch_id,
                        "exposure_bucket": entry.exposure_bucket,
                        "list_date": list_date,
                        "delist_date": delist_date,
                    }
                )
        conn.commit()

    payload = {
        "table": CATALOG_TABLE,
        "source": "tushare_fund_basic" if tushare_rows else source,
        "refresh_at": refresh_at,
        "token_available": bool(token),
        "upserted_rows": upserted,
        "catalog_size": len(rows_written),
        "ts_codes": [row["ts_code"] for row in rows_written],
    }
    if summary_out is not None:
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        summary_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh seeded cn_etf catalog into pit_cn_etf_master")
    parser.add_argument("--token", default="", help="optional Tushare token for fund_basic enrichment")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="fallback source label when Tushare is unavailable")
    parser.add_argument("--summary-out", default="", help="optional summary json output path")
    args = parser.parse_args()
    token = common.resolve_tushare_token(args.token)
    summary_path = Path(args.summary_out).resolve() if str(args.summary_out or "").strip() else None
    payload = run_refresh(token=token, source=str(args.source or DEFAULT_SOURCE), summary_out=summary_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
