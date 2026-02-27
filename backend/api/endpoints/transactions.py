from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import psycopg
from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row

router = APIRouter(tags=["transactions"])


def _db_settings() -> dict[str, Any]:
    host = os.getenv("PAMS_PG_HOST") or os.getenv("PGHOST") or "127.0.0.1"
    port = int(os.getenv("PAMS_PG_PORT") or os.getenv("PGPORT") or "5432")
    dbname = os.getenv("PAMS_PG_DBNAME") or os.getenv("PGDATABASE") or "pams"
    user = os.getenv("PAMS_PG_USER") or os.getenv("PGUSER") or "pams"
    password = os.getenv("PAMS_PG_PASSWORD") or os.getenv("PGPASSWORD")
    if not password:
        raise HTTPException(status_code=500, detail="database password is not configured")
    return {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password,
    }


def _sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = str(v)
        else:
            out[k] = v
    return out


@router.post("/api/transactions/undo-latest")
def undo_latest_transaction():
    settings = _db_settings()
    try:
        with psycopg.connect(**settings, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        date,
                        amount,
                        currency,
                        category,
                        subcategory,
                        account_code,
                        description,
                        location,
                        auto_classified,
                        source,
                        created_at
                    FROM pams_transactions
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    FOR UPDATE
                    """
                )
                latest = cur.fetchone()
                if not latest:
                    raise HTTPException(status_code=404, detail="no transaction to undo")

                tx_id = int(latest["id"])
                cur.execute("DELETE FROM pams_transaction_sync_log WHERE transaction_id = %s", (tx_id,))
                cur.execute("DELETE FROM pams_transactions WHERE id = %s", (tx_id,))
            conn.commit()
            return {"ok": True, "deleted": _sanitize_row(latest)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"undo latest transaction failed: {exc}") from exc
