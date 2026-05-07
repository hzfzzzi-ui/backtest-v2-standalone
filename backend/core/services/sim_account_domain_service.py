from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from backend.core.services import ops_domain_pg

_ACCOUNT_ID_RE = re.compile(r"[^a-z0-9_-]+")
_ACCOUNT_SCHEMA_VERSION = "sim_account_account@1"
_CASH_LEDGER_SCHEMA_VERSION = "sim_account_cash_ledger_entry@1"
_SYNC_LOG_SCHEMA_VERSION = "sim_account_sync_log_entry@1"
_RECONCILE_SUMMARY_SCHEMA_VERSION = "sim_account_reconcile_summary@1"
_COMPAT_MANIFEST_SCHEMA_VERSION = "sim_account_compat_manifest@1"
_ACCOUNT_OBJECT_SCOPE = "account_ops"
_ACCOUNT_OBJECT_TYPE = "account"
_HOLDINGS_OBJECT_TYPE = "holdings_snapshot"
_CASH_LEDGER_OBJECT_TYPE = "cash_ledger"
_SYNC_LOG_OBJECT_TYPE = "sync_log"
_RECONCILE_SUMMARY_OBJECT_TYPE = "reconcile_summary"


def _now_iso(now_ts: int | None = None) -> str:
    if now_ts is None:
        now_ts = int(time.time())
    return datetime.fromtimestamp(int(now_ts), tz=UTC).replace(microsecond=0).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False, dir=str(path.parent)) as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
        tmp_path = Path(fh.name)
    os.replace(str(tmp_path), str(path))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_account_id(value: str) -> str:
    normalized = _ACCOUNT_ID_RE.sub("_", str(value or "").strip().lower()).strip("_")
    if not normalized:
        raise ValueError("account_id is required")
    return normalized


def account_root(results_root: Path, account_id: str) -> Path:
    root = results_root / "ops" / "sim_account" / _normalize_account_id(account_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def account_profile_path(results_root: Path, account_id: str) -> Path:
    return account_root(results_root, account_id) / "account.json"


def compat_manifest_path(results_root: Path, account_id: str) -> Path:
    return account_root(results_root, account_id) / "compat_manifest.json"


def holdings_root(results_root: Path, account_id: str) -> Path:
    root = account_root(results_root, account_id) / "holdings"
    root.mkdir(parents=True, exist_ok=True)
    return root


def holdings_history_root(results_root: Path, account_id: str) -> Path:
    root = holdings_root(results_root, account_id) / "history"
    root.mkdir(parents=True, exist_ok=True)
    return root


def latest_holdings_path(results_root: Path, account_id: str) -> Path:
    return holdings_root(results_root, account_id) / "latest.json"


def cash_ledger_root(results_root: Path, account_id: str) -> Path:
    root = account_root(results_root, account_id) / "cash_ledger"
    root.mkdir(parents=True, exist_ok=True)
    return root


def cash_ledger_history_root(results_root: Path, account_id: str) -> Path:
    root = cash_ledger_root(results_root, account_id) / "history"
    root.mkdir(parents=True, exist_ok=True)
    return root


def latest_cash_ledger_path(results_root: Path, account_id: str) -> Path:
    return cash_ledger_root(results_root, account_id) / "latest.json"


def sync_logs_root(results_root: Path, account_id: str) -> Path:
    root = account_root(results_root, account_id) / "sync_logs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def sync_logs_history_root(results_root: Path, account_id: str) -> Path:
    root = sync_logs_root(results_root, account_id) / "history"
    root.mkdir(parents=True, exist_ok=True)
    return root


def latest_sync_log_path(results_root: Path, account_id: str) -> Path:
    return sync_logs_root(results_root, account_id) / "latest.json"


def reconcile_root(results_root: Path, account_id: str) -> Path:
    root = account_root(results_root, account_id) / "reconcile"
    root.mkdir(parents=True, exist_ok=True)
    return root


def reconcile_summary_root(results_root: Path, account_id: str) -> Path:
    root = reconcile_root(results_root, account_id) / "summary"
    root.mkdir(parents=True, exist_ok=True)
    return root


def reconcile_summary_history_root(results_root: Path, account_id: str) -> Path:
    root = reconcile_summary_root(results_root, account_id) / "history"
    root.mkdir(parents=True, exist_ok=True)
    return root


def latest_reconcile_summary_path(results_root: Path, account_id: str) -> Path:
    return reconcile_summary_root(results_root, account_id) / "latest.json"


def account_object_catalog(results_root: Path, account_id: str) -> dict[str, Any]:
    normalized = _normalize_account_id(account_id)
    return {
        "account": {
            "object_type": _ACCOUNT_OBJECT_TYPE,
            "object_scope": _ACCOUNT_OBJECT_SCOPE,
            "path": str(account_profile_path(results_root, normalized).relative_to(results_root).as_posix()),
        },
        "holdings_snapshots": {
            "object_type": _HOLDINGS_OBJECT_TYPE,
            "object_scope": _ACCOUNT_OBJECT_SCOPE,
            "latest_path": str(latest_holdings_path(results_root, normalized).relative_to(results_root).as_posix()),
            "history_path": str(holdings_history_root(results_root, normalized).relative_to(results_root).as_posix()),
        },
        "cash_ledger": {
            "object_type": _CASH_LEDGER_OBJECT_TYPE,
            "object_scope": _ACCOUNT_OBJECT_SCOPE,
            "latest_path": str(latest_cash_ledger_path(results_root, normalized).relative_to(results_root).as_posix()),
            "history_path": str(cash_ledger_history_root(results_root, normalized).relative_to(results_root).as_posix()),
        },
        "sync_logs": {
            "object_type": _SYNC_LOG_OBJECT_TYPE,
            "object_scope": _ACCOUNT_OBJECT_SCOPE,
            "latest_path": str(latest_sync_log_path(results_root, normalized).relative_to(results_root).as_posix()),
            "history_path": str(sync_logs_history_root(results_root, normalized).relative_to(results_root).as_posix()),
        },
        "reconcile_summary": {
            "object_type": _RECONCILE_SUMMARY_OBJECT_TYPE,
            "object_scope": _ACCOUNT_OBJECT_SCOPE,
            "latest_path": str(latest_reconcile_summary_path(results_root, normalized).relative_to(results_root).as_posix()),
            "history_path": str(reconcile_summary_history_root(results_root, normalized).relative_to(results_root).as_posix()),
        },
    }


def _compat_manifest_payload(results_root: Path, account_id: str, *, now_ts: int | None = None) -> dict[str, Any]:
    normalized = _normalize_account_id(account_id)
    root = account_root(results_root, normalized)
    def _rel(path: Path) -> str:
        return path.relative_to(results_root).as_posix()
    return {
        "schema_version": _COMPAT_MANIFEST_SCHEMA_VERSION,
        "account_id": normalized,
        "status": "active_transition",
        "authority": "account_ops_domain",
        "role": "compat_file_mirror_only",
        "compat_root": _rel(root),
        "formal_truth_objects": [
            "accounts",
            "holdings_snapshots",
            "cash_ledger",
            "sync_logs",
            "reconcile_summary",
        ],
        "formal_object_catalog": account_object_catalog(results_root, normalized),
        "compat_paths": {
            "holdings_latest": _rel(latest_holdings_path(results_root, normalized)),
            "holdings_history": _rel(holdings_history_root(results_root, normalized)),
            "cash_ledger_latest": _rel(latest_cash_ledger_path(results_root, normalized)),
            "cash_ledger_history": _rel(cash_ledger_history_root(results_root, normalized)),
            "sync_logs_latest": _rel(latest_sync_log_path(results_root, normalized)),
            "sync_logs_history": _rel(sync_logs_history_root(results_root, normalized)),
            "reconcile_latest": _rel(account_root(results_root, normalized) / "reconcile" / "latest.json"),
            "reconcile_history": _rel(account_root(results_root, normalized) / "reconcile" / "history"),
            "reconcile_summary_latest": _rel(latest_reconcile_summary_path(results_root, normalized)),
            "reconcile_summary_history": _rel(reconcile_summary_history_root(results_root, normalized)),
            "account_profile": _rel(account_profile_path(results_root, normalized)),
        },
        "exit_conditions": [
            "sim_account services stop reading outputs/ops/sim_account/* as formal truth",
            "mobile and desktop consumers switch to account ops domain objects or summaries",
            "reconcile detailed payload remains derived-only and no longer acts as sync truth",
            "rollback path is validated before compat mirror deletion",
        ],
        "rollback_order": [
            "keep database/domain writes enabled",
            "fall back to database mirror + file main-read only if domain reads regress",
            "disable auto sync before replaying historical compat snapshots",
        ],
        "updated_at": _now_iso(now_ts),
    }


def write_compat_manifest(results_root: Path, account_id: str, *, now_ts: int | None = None) -> dict[str, Any]:
    payload = _compat_manifest_payload(results_root, account_id, now_ts=now_ts)
    _atomic_write_json(compat_manifest_path(results_root, account_id), payload)
    return payload


def ensure_account_profile(
    results_root: Path,
    account_id: str,
    *,
    source_type: str = "sim_account_service",
    now_ts: int | None = None,
) -> dict[str, Any]:
    normalized = _normalize_account_id(account_id)
    write_compat_manifest(results_root, normalized, now_ts=now_ts)
    try:
        existing_db = ops_domain_pg.get_account_profile(results_root, normalized)
    except ops_domain_pg.OpsDomainDbUnavailable:
        existing_db = None
    if existing_db:
        _atomic_write_json(account_profile_path(results_root, normalized), existing_db)
        return existing_db
    path = account_profile_path(results_root, normalized)
    existing = _read_json(path)
    if existing:
        try:
            ops_domain_pg.upsert_account_profile(results_root, existing)
        except ops_domain_pg.OpsDomainDbUnavailable:
            pass
        return existing
    payload = {
        "schema_version": _ACCOUNT_SCHEMA_VERSION,
        "object_type": _ACCOUNT_OBJECT_TYPE,
        "object_scope": _ACCOUNT_OBJECT_SCOPE,
        "account_id": normalized,
        "status": "active",
        "source_type": source_type,
        "created_at": _now_iso(now_ts),
        "updated_at": _now_iso(now_ts),
    }
    try:
        ops_domain_pg.upsert_account_profile(results_root, payload)
    except ops_domain_pg.OpsDomainDbUnavailable:
        pass
    _atomic_write_json(path, payload)
    return payload


def _record_id(prefix: str, payload: Mapping[str, Any], *, extra: str = "") -> str:
    digest_input = json.dumps(
        {
            "prefix": prefix,
            "payload": dict(payload),
            "extra": extra,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha1(digest_input).hexdigest()[:16]}"


def write_cash_ledger_entry(
    results_root: Path,
    *,
    account_id: str,
    entry: Mapping[str, Any],
    now_ts: int | None = None,
) -> dict[str, Any]:
    normalized = _normalize_account_id(account_id)
    payload = {
        "schema_version": _CASH_LEDGER_SCHEMA_VERSION,
        "object_type": _CASH_LEDGER_OBJECT_TYPE,
        "object_scope": _ACCOUNT_OBJECT_SCOPE,
        "account_id": normalized,
        "entry_id": str(entry.get("entry_id") or "").strip(),
        "entry_type": str(entry.get("entry_type") or "cash_change").strip() or "cash_change",
        "amount": round(float(entry.get("amount") or 0.0), 6),
        "balance_before": round(float(entry.get("balance_before") or 0.0), 6),
        "balance_after": round(float(entry.get("balance_after") or 0.0), 6),
        "reference_id": str(entry.get("reference_id") or ""),
        "source_type": str(entry.get("source_type") or ""),
        "message": str(entry.get("message") or ""),
        "created_at": str(entry.get("created_at") or _now_iso(now_ts)),
    }
    if not payload["entry_id"]:
        payload["entry_id"] = _record_id("cl", payload, extra=payload["created_at"])
    try:
        ops_domain_pg.upsert_cash_ledger_entry(results_root, payload)
    except ops_domain_pg.OpsDomainDbUnavailable:
        pass
    latest_path = latest_cash_ledger_path(results_root, normalized)
    history_path = cash_ledger_history_root(results_root, normalized) / f"{payload['entry_id']}.json"
    _atomic_write_json(history_path, payload)
    _atomic_write_json(latest_path, payload)
    return payload


def write_sync_log_entry(
    results_root: Path,
    *,
    account_id: str,
    entry: Mapping[str, Any],
    now_ts: int | None = None,
) -> dict[str, Any]:
    normalized = _normalize_account_id(account_id)
    payload = {
        "schema_version": _SYNC_LOG_SCHEMA_VERSION,
        "object_type": _SYNC_LOG_OBJECT_TYPE,
        "object_scope": _ACCOUNT_OBJECT_SCOPE,
        "account_id": normalized,
        "event_id": str(entry.get("event_id") or "").strip(),
        "event_type": str(entry.get("event_type") or "sync").strip() or "sync",
        "status": str(entry.get("status") or ""),
        "snapshot_id": str(entry.get("snapshot_id") or ""),
        "reconcile_id": str(entry.get("reconcile_id") or ""),
        "trade_date": str(entry.get("trade_date") or ""),
        "source_type": str(entry.get("source_type") or ""),
        "message": str(entry.get("message") or ""),
        "error": str(entry.get("error") or ""),
        "created_at": str(entry.get("created_at") or _now_iso(now_ts)),
    }
    if not payload["event_id"]:
        payload["event_id"] = _record_id("sl", payload, extra=payload["created_at"])
    try:
        ops_domain_pg.upsert_sync_log_entry(results_root, payload)
    except ops_domain_pg.OpsDomainDbUnavailable:
        pass
    latest_path = latest_sync_log_path(results_root, normalized)
    history_path = sync_logs_history_root(results_root, normalized) / f"{payload['event_id']}.json"
    _atomic_write_json(history_path, payload)
    _atomic_write_json(latest_path, payload)
    return payload


def reconcile_summary_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    actions = payload.get("actions") if isinstance(payload.get("actions"), Mapping) else {}
    return {
        "schema_version": _RECONCILE_SUMMARY_SCHEMA_VERSION,
        "object_type": _RECONCILE_SUMMARY_OBJECT_TYPE,
        "object_scope": _ACCOUNT_OBJECT_SCOPE,
        "source_kind": "derived_summary",
        "reconcile_id": str(payload.get("reconcile_id") or ""),
        "account_id": str(payload.get("account_id") or ""),
        "snapshot_id": str(payload.get("snapshot_id") or ""),
        "exp_id": str((payload.get("strategy_source") or {}).get("exp_id") or ""),
        "config_hash": str((payload.get("strategy_source") or {}).get("config_hash") or ""),
        "generated_at": str(payload.get("generated_at") or ""),
        "as_of_date": str(payload.get("as_of_date") or ""),
        "source_mode": str(payload.get("source_mode") or ""),
        "summary": {
            "action_count": int(summary.get("action_count") or 0),
            "buy_count": int(summary.get("buy_count") or len(list(actions.get("buy") or []))),
            "sell_count": int(summary.get("sell_count") or len(list(actions.get("sell") or []))),
            "hold_count": int(summary.get("hold_count") or len(list(actions.get("hold") or []))),
            "blocked_count": int(summary.get("blocked_count") or 0),
        },
        "created_at": str(payload.get("generated_at") or ""),
    }


def write_reconcile_summary(
    results_root: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    account_id = _normalize_account_id(str(payload.get("account_id") or ""))
    summary = reconcile_summary_from_payload(payload)
    if not summary["reconcile_id"]:
        summary["reconcile_id"] = _record_id("rs", summary)
    try:
        ops_domain_pg.upsert_reconcile_summary(results_root, summary)
    except ops_domain_pg.OpsDomainDbUnavailable:
        pass
    latest_path = latest_reconcile_summary_path(results_root, account_id)
    history_path = reconcile_summary_history_root(results_root, account_id) / f"{summary['reconcile_id']}.json"
    _atomic_write_json(history_path, summary)
    _atomic_write_json(latest_path, summary)
    return summary


def load_latest_reconcile_summary(results_root: Path, account_id: str | None = None) -> dict[str, Any] | None:
    normalized = _normalize_account_id(str(account_id or os.getenv("SIM_ACCOUNT_DEFAULT_ID") or "paper_a_share_main"))
    try:
        payload = ops_domain_pg.get_latest_reconcile_summary(results_root, normalized)
    except ops_domain_pg.OpsDomainDbUnavailable:
        payload = None
    if payload:
        _atomic_write_json(latest_reconcile_summary_path(results_root, normalized), payload)
        return payload
    payload = _read_json(latest_reconcile_summary_path(results_root, normalized))
    if payload:
        try:
            ops_domain_pg.upsert_reconcile_summary(results_root, payload)
        except ops_domain_pg.OpsDomainDbUnavailable:
            pass
    return payload or None


def load_account_profile(results_root: Path, account_id: str) -> dict[str, Any] | None:
    normalized = _normalize_account_id(account_id)
    try:
        payload = ops_domain_pg.get_account_profile(results_root, normalized)
    except ops_domain_pg.OpsDomainDbUnavailable:
        payload = None
    if payload:
        _atomic_write_json(account_profile_path(results_root, normalized), payload)
        return payload
    payload = _read_json(account_profile_path(results_root, normalized)) or None
    if payload:
        try:
            ops_domain_pg.upsert_account_profile(results_root, payload)
        except ops_domain_pg.OpsDomainDbUnavailable:
            pass
    return payload


def load_latest_cash_ledger_entry(results_root: Path, account_id: str) -> dict[str, Any] | None:
    normalized = _normalize_account_id(account_id)
    try:
        payload = ops_domain_pg.get_latest_cash_ledger_entry(results_root, normalized)
    except ops_domain_pg.OpsDomainDbUnavailable:
        payload = None
    if payload:
        _atomic_write_json(latest_cash_ledger_path(results_root, normalized), payload)
        return payload
    payload = _read_json(latest_cash_ledger_path(results_root, normalized)) or None
    if payload:
        try:
            ops_domain_pg.upsert_cash_ledger_entry(results_root, payload)
        except ops_domain_pg.OpsDomainDbUnavailable:
            pass
    return payload


def load_latest_sync_log_entry(results_root: Path, account_id: str) -> dict[str, Any] | None:
    normalized = _normalize_account_id(account_id)
    try:
        payload = ops_domain_pg.get_latest_sync_log_entry(results_root, normalized)
    except ops_domain_pg.OpsDomainDbUnavailable:
        payload = None
    if payload:
        _atomic_write_json(latest_sync_log_path(results_root, normalized), payload)
        return payload
    payload = _read_json(latest_sync_log_path(results_root, normalized)) or None
    if payload:
        try:
            ops_domain_pg.upsert_sync_log_entry(results_root, payload)
        except ops_domain_pg.OpsDomainDbUnavailable:
            pass
    return payload


def list_cash_ledger_entries(results_root: Path, account_id: str) -> list[dict[str, Any]]:
    normalized = _normalize_account_id(account_id)
    try:
        entries = ops_domain_pg.list_cash_ledger_entries(results_root, normalized)
    except ops_domain_pg.OpsDomainDbUnavailable:
        entries = []
    if entries:
        return entries
    root = cash_ledger_history_root(results_root, normalized)
    file_entries: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        payload = _read_json(path)
        if payload:
            try:
                ops_domain_pg.upsert_cash_ledger_entry(results_root, payload)
            except ops_domain_pg.OpsDomainDbUnavailable:
                pass
            file_entries.append(payload)
    return file_entries


def list_sync_log_entries(results_root: Path, account_id: str) -> list[dict[str, Any]]:
    normalized = _normalize_account_id(account_id)
    try:
        entries = ops_domain_pg.list_sync_log_entries(results_root, normalized)
    except ops_domain_pg.OpsDomainDbUnavailable:
        entries = []
    if entries:
        return entries
    root = sync_logs_history_root(results_root, normalized)
    file_entries: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        payload = _read_json(path)
        if payload:
            try:
                ops_domain_pg.upsert_sync_log_entry(results_root, payload)
            except ops_domain_pg.OpsDomainDbUnavailable:
                pass
            file_entries.append(payload)
    return file_entries


__all__ = [
    "account_object_catalog",
    "account_profile_path",
    "account_root",
    "cash_ledger_history_root",
    "compat_manifest_path",
    "cash_ledger_root",
    "ensure_account_profile",
    "holdings_history_root",
    "holdings_root",
    "latest_cash_ledger_path",
    "latest_holdings_path",
    "latest_reconcile_summary_path",
    "latest_sync_log_path",
    "load_account_profile",
    "load_latest_cash_ledger_entry",
    "load_latest_reconcile_summary",
    "load_latest_sync_log_entry",
    "list_cash_ledger_entries",
    "list_sync_log_entries",
    "reconcile_root",
    "reconcile_summary_from_payload",
    "reconcile_summary_history_root",
    "reconcile_summary_root",
    "sync_logs_history_root",
    "sync_logs_root",
    "write_compat_manifest",
    "write_cash_ledger_entry",
    "write_reconcile_summary",
    "write_sync_log_entry",
]
