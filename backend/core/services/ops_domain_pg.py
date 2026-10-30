from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover
    psycopg = None
    dict_row = None

from backend.core.data.pg_env import env_or_file


class OpsDomainDbUnavailable(RuntimeError):
    pass


class OpsDomainSchemaMissing(RuntimeError):
    """The transaction lifecycle schema must be provisioned separately."""


_CONNECT_FAILURE_CACHE_UNTIL = 0.0
_CONNECT_FAILURE_MESSAGE = ""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_env_file() -> dict[str, str]:
    path = _repo_root() / ".env"
    if not path.exists():
        return {}
    payload: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        payload[key.strip()] = value.strip()
    return payload


def _env_or_file(name: str, default: str = "") -> str:
    return env_or_file(name, file_env=_read_env_file(), default=default)


def load_db_settings() -> dict[str, Any]:
    if psycopg is None:  # pragma: no cover
        raise OpsDomainDbUnavailable("psycopg is not installed")
    host = _env_or_file("PAMS_PG_HOST") or _env_or_file("PGHOST") or "pams-postgres"
    port = int(_env_or_file("PAMS_PG_PORT") or _env_or_file("PGPORT") or "5432")
    dbname = _env_or_file("PAMS_PG_DBNAME") or _env_or_file("PGDATABASE") or "pams"
    user = _env_or_file("PAMS_PG_USER") or _env_or_file("PGUSER") or "pams"
    password = _env_or_file("PAMS_PG_PASSWORD") or _env_or_file("PGPASSWORD")
    if not password:
        raise OpsDomainDbUnavailable("postgres password is not configured")
    return {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password,
        "connect_timeout": 2,
    }


def _scope_key(results_root: Path) -> tuple[str, str]:
    resolved = str(Path(results_root).resolve())
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:16]
    return digest, resolved


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _jsonb_dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def connect():
    global _CONNECT_FAILURE_CACHE_UNTIL, _CONNECT_FAILURE_MESSAGE
    if psycopg is None:  # pragma: no cover
        raise OpsDomainDbUnavailable("psycopg is not installed")
    now_ts = time.time()
    if _CONNECT_FAILURE_CACHE_UNTIL > now_ts:
        raise OpsDomainDbUnavailable(_CONNECT_FAILURE_MESSAGE or "postgres unavailable")
    settings = load_db_settings()
    try:
        conn = psycopg.connect(**settings, row_factory=dict_row)
        _CONNECT_FAILURE_CACHE_UNTIL = 0.0
        _CONNECT_FAILURE_MESSAGE = ""
        return conn
    except Exception as exc:  # pragma: no cover
        _CONNECT_FAILURE_MESSAGE = f"postgres unavailable: {exc}"
        _CONNECT_FAILURE_CACHE_UNTIL = now_ts + 10.0
        raise OpsDomainDbUnavailable(_CONNECT_FAILURE_MESSAGE) from exc


def ensure_tables(conn) -> None:
    """Verify required schema without creating or modifying database objects."""
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) AS relation", ("public.pams_transaction_lifecycle",))
        row = cur.fetchone()
    if not row or row.get("relation") is None:
        raise OpsDomainSchemaMissing(
            "Required database table public.pams_transaction_lifecycle is missing; "
            "schema must be provisioned separately"
        )


def upsert_transaction_record(results_root: Path, record: dict[str, Any]) -> dict[str, Any]:
    scope_key, resolved_root = _scope_key(results_root)
    summary = record.get("summary") if isinstance(record.get("summary"), dict) else {}
    created_at_ts = _parse_ts(summary.get("created_at"))
    updated_at_ts = _parse_ts(summary.get("updated_at") or summary.get("last_event_at") or summary.get("created_at"))
    with connect() as conn:
        ensure_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.pams_transaction_lifecycle (
                    scope_key, results_root, transaction_id, account_id, symbol, side,
                    lifecycle_status, status_group, approval_source, source_intent_id,
                    failure_reason_codes, summary_json, record_json, compat_source,
                    created_at_ts, updated_at_ts
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s,
                    %s, %s
                )
                ON CONFLICT (scope_key, transaction_id) DO UPDATE SET
                    results_root = EXCLUDED.results_root,
                    account_id = EXCLUDED.account_id,
                    symbol = EXCLUDED.symbol,
                    side = EXCLUDED.side,
                    lifecycle_status = EXCLUDED.lifecycle_status,
                    status_group = EXCLUDED.status_group,
                    approval_source = EXCLUDED.approval_source,
                    source_intent_id = EXCLUDED.source_intent_id,
                    failure_reason_codes = EXCLUDED.failure_reason_codes,
                    summary_json = EXCLUDED.summary_json,
                    record_json = EXCLUDED.record_json,
                    compat_source = EXCLUDED.compat_source,
                    created_at_ts = EXCLUDED.created_at_ts,
                    updated_at_ts = EXCLUDED.updated_at_ts
                """,
                (
                    scope_key,
                    resolved_root,
                    str(record.get("transaction_id") or "").strip(),
                    str(record.get("account_id") or "").strip(),
                    str(record.get("symbol") or "").strip(),
                    str(record.get("side") or "").strip(),
                    str(record.get("lifecycle_status") or "").strip(),
                    str(record.get("status_group") or "").strip(),
                    str(record.get("approval_source") or "").strip(),
                    str(record.get("source_intent_id") or "").strip(),
                    _jsonb_dump(list(record.get("failure_reason_codes") or [])),
                    _jsonb_dump(summary),
                    _jsonb_dump(record),
                    str(record.get("compat_source") or "").strip(),
                    created_at_ts,
                    updated_at_ts,
                ),
            )
        conn.commit()
    return record


def get_transaction_record(results_root: Path, transaction_id: str) -> dict[str, Any] | None:
    scope_key, _ = _scope_key(results_root)
    with connect() as conn:
        ensure_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT record_json
                FROM public.pams_transaction_lifecycle
                WHERE scope_key = %s AND transaction_id = %s
                """,
                (scope_key, str(transaction_id or "").strip()),
            )
            row = cur.fetchone()
    if not row:
        return None
    payload = row.get("record_json")
    return payload if isinstance(payload, dict) else None


def list_transaction_records(results_root: Path) -> list[dict[str, Any]]:
    scope_key, _ = _scope_key(results_root)
    with connect() as conn:
        ensure_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT record_json
                FROM public.pams_transaction_lifecycle
                WHERE scope_key = %s
                ORDER BY updated_at_ts DESC NULLS LAST, transaction_id DESC
                """,
                (scope_key,),
            )
            rows = cur.fetchall() or []
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = row.get("record_json")
        if isinstance(payload, dict):
            out.append(payload)
    return out
