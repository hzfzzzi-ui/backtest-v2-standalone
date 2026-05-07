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

from backend.core.data.mapping import normalize_stock_symbol
from backend.core.services import ops_domain_pg
from backend.core.services import sim_account_domain_service as sim_account_domain
from backend.core.services.mobile_ops_service import list_approval_tickets

_ACCOUNT_ID_RE = re.compile(r"[^a-z0-9_-]+")
_SNAPSHOT_SCHEMA_VERSION = "sim_account_holdings_snapshot@1"
_STATUS_SCHEMA_VERSION = "sim_account_holdings_status@1"


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = str(os.getenv(name) or "").strip()
    try:
        return max(minimum, int(raw))
    except Exception:
        return int(default)


def default_sim_account_id() -> str:
    return _normalize_account_id(str(os.getenv("SIM_ACCOUNT_DEFAULT_ID") or "").strip() or "paper_a_share_main")


def sim_account_stale_seconds() -> int:
    return _env_int("SIM_ACCOUNT_SYNC_STALE_SECONDS", 86400, minimum=60)


def _now_ts(now_ts: int | None = None) -> int:
    return int(now_ts if now_ts is not None else time.time())


def _now_iso(now_ts: int | None = None) -> str:
    return datetime.fromtimestamp(_now_ts(now_ts), tz=UTC).replace(microsecond=0).isoformat()


def _parse_iso_ts(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False, dir=str(path.parent)) as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
        tmp_path = Path(fh.name)
    os.replace(str(tmp_path), str(path))


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        fh.write("\n")


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


def _ops_root(results_root: Path) -> Path:
    root = results_root / "ops"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sim_account_root(results_root: Path, account_id: str) -> Path:
    root = _ops_root(results_root) / "sim_account" / _normalize_account_id(account_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _holdings_root(results_root: Path, account_id: str) -> Path:
    root = _sim_account_root(results_root, account_id) / "holdings"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _holdings_history_root(results_root: Path, account_id: str) -> Path:
    root = _holdings_root(results_root, account_id) / "history"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _latest_snapshot_path(results_root: Path, account_id: str) -> Path:
    return _holdings_root(results_root, account_id) / "latest.json"


def _audit_log_path(results_root: Path, account_id: str) -> Path:
    return _sim_account_root(results_root, account_id) / "audit_log.jsonl"


def _pick_value(payload: Mapping[str, Any], keys: tuple[str, ...], *, default: Any = None) -> Any:
    for key in keys:
        if key in payload and payload.get(key) not in (None, ""):
            return payload.get(key)
    return default


def _coerce_float(value: Any, *, field_name: str) -> float:
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    try:
        return float(value)
    except Exception as exc:
        raise ValueError(f"{field_name} is invalid") from exc


def _coerce_int(value: Any, *, field_name: str) -> int:
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    try:
        number = int(float(value))
    except Exception as exc:
        raise ValueError(f"{field_name} is invalid") from exc
    return int(number)


def _normalize_trade_date(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except Exception as exc:
        raise ValueError(f"{field_name} is invalid") from exc


def _normalize_synced_at(value: Any, *, now_ts: int | None = None) -> str:
    text = str(value or "").strip()
    if not text:
        return _now_iso(now_ts)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC).replace(microsecond=0).isoformat()
    except Exception as exc:
        raise ValueError("synced_at is invalid") from exc


def _normalize_position_row(row: Mapping[str, Any], *, row_index: int) -> dict[str, Any]:
    symbol_raw = _pick_value(row, ("symbol", "ts_code", "code", "stock_code", "证券代码", "股票代码"))
    if symbol_raw in (None, ""):
        raise ValueError(f"positions[{row_index}].symbol is required")
    symbol = normalize_stock_symbol(str(symbol_raw).strip())

    qty = _coerce_int(
        _pick_value(row, ("qty", "total_qty", "position_qty", "持仓数量", "当前持仓", "证券数量")),
        field_name=f"positions[{row_index}].qty",
    )
    if qty <= 0:
        raise ValueError(f"positions[{row_index}].qty must be > 0")

    sellable_raw = _pick_value(row, ("sellable_qty", "available_qty", "可用数量", "可卖数量"), default=qty)
    sellable_qty = _coerce_int(sellable_raw, field_name=f"positions[{row_index}].sellable_qty")
    if sellable_qty < 0 or sellable_qty > qty:
        raise ValueError(f"positions[{row_index}].sellable_qty must be between 0 and qty")

    avg_cost_raw = _pick_value(row, ("avg_cost", "cost_price", "成本价", "买入成本"), default=0.0)
    avg_cost = float(avg_cost_raw or 0.0)
    if avg_cost < 0:
        raise ValueError(f"positions[{row_index}].avg_cost must be >= 0")

    return {
        "symbol": symbol,
        "qty": qty,
        "sellable_qty": sellable_qty,
        "avg_cost": round(float(avg_cost), 6),
        "name": str(_pick_value(row, ("name", "证券名称", "股票名称"), default="") or "").strip(),
    }


def _normalize_positions(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("positions must be a list")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, row in enumerate(payload):
        if not isinstance(row, Mapping):
            raise ValueError(f"positions[{idx}] must be an object")
        normalized = _normalize_position_row(row, row_index=idx)
        symbol = str(normalized["symbol"])
        if symbol in seen:
            raise ValueError(f"duplicate symbol in positions: {symbol}")
        seen.add(symbol)
        out.append(normalized)
    out.sort(key=lambda item: str(item.get("symbol") or ""))
    return out


def _snapshot_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    positions = list(snapshot.get("positions") or [])
    return {
        "position_count": len(positions),
        "total_qty": int(sum(int(item.get("qty") or 0) for item in positions)),
        "total_sellable_qty": int(sum(int(item.get("sellable_qty") or 0) for item in positions)),
        "symbols": [str(item.get("symbol") or "") for item in positions],
    }


def _snapshot_digest(payload: dict[str, Any]) -> str:
    stable_obj = {
        "account_id": payload.get("account_id"),
        "trade_date": payload.get("trade_date"),
        "synced_at": payload.get("synced_at"),
        "cash": payload.get("cash"),
        "source_type": payload.get("source_type"),
        "positions": payload.get("positions"),
    }
    return hashlib.sha1(
        json.dumps(stable_obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]


def _pending_ticket_summary(results_root: Path) -> dict[str, Any]:
    pending = list_approval_tickets(results_root, status="approved_pending")
    return {
        "count": len(pending),
        "ticket_ids": [str(item.get("ticket_id") or "") for item in pending if str(item.get("ticket_id") or "").strip()],
    }


def _build_drift_summary(
    previous_snapshot: dict[str, Any] | None,
    current_snapshot: dict[str, Any],
    *,
    pending_summary: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(previous_snapshot, dict) or not previous_snapshot:
        return {
            "has_previous_snapshot": False,
            "has_drift": False,
            "previous_snapshot_id": "",
            "added_symbols": [],
            "removed_symbols": [],
            "qty_changed": [],
            "pending_ticket_count": int(pending_summary.get("count") or 0),
            "pending_ticket_ids": list(pending_summary.get("ticket_ids") or []),
            "pending_ticket_drift": False,
        }

    prev_map = {
        str(item.get("symbol") or ""): item
        for item in list(previous_snapshot.get("positions") or [])
        if isinstance(item, Mapping) and str(item.get("symbol") or "").strip()
    }
    curr_map = {
        str(item.get("symbol") or ""): item
        for item in list(current_snapshot.get("positions") or [])
        if isinstance(item, Mapping) and str(item.get("symbol") or "").strip()
    }
    added = sorted(symbol for symbol in curr_map if symbol not in prev_map)
    removed = sorted(symbol for symbol in prev_map if symbol not in curr_map)
    qty_changed = []
    for symbol in sorted(set(prev_map) & set(curr_map)):
        prev_qty = int(prev_map[symbol].get("qty") or 0)
        curr_qty = int(curr_map[symbol].get("qty") or 0)
        if prev_qty == curr_qty:
            continue
        qty_changed.append(
            {
                "symbol": symbol,
                "previous_qty": prev_qty,
                "current_qty": curr_qty,
            }
        )
    has_drift = bool(added or removed or qty_changed)
    pending_count = int(pending_summary.get("count") or 0)
    return {
        "has_previous_snapshot": True,
        "has_drift": has_drift,
        "previous_snapshot_id": str(previous_snapshot.get("snapshot_id") or ""),
        "added_symbols": added,
        "removed_symbols": removed,
        "qty_changed": qty_changed,
        "pending_ticket_count": pending_count,
        "pending_ticket_ids": list(pending_summary.get("ticket_ids") or []),
        "pending_ticket_drift": bool(has_drift and pending_count > 0),
    }


def normalize_holdings_snapshot(
    payload: Mapping[str, Any],
    *,
    default_account_id_value: str | None = None,
    now_ts: int | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be an object")
    account_id = _normalize_account_id(
        str(
            _pick_value(payload, ("account_id", "account", "账户", "账户ID"), default=default_account_id_value or default_sim_account_id())
            or ""
        )
    )
    trade_date = _normalize_trade_date(
        _pick_value(payload, ("trade_date", "date", "交易日期", "持仓日期")),
        field_name="trade_date",
    )
    synced_at = _normalize_synced_at(
        _pick_value(payload, ("synced_at", "sync_time", "同步时间"), default=""),
        now_ts=now_ts,
    )
    cash_raw = _pick_value(payload, ("cash", "available_cash", "可用资金", "资金余额"), default=0.0)
    cash = float(cash_raw or 0.0)
    if cash < 0:
        raise ValueError("cash must be >= 0")
    positions = _normalize_positions(payload.get("positions"))
    snapshot = {
        "schema_version": _SNAPSHOT_SCHEMA_VERSION,
        "object_type": "holdings_snapshot",
        "object_scope": "account_ops",
        "account_id": account_id,
        "trade_date": trade_date,
        "synced_at": synced_at,
        "source_type": str(_pick_value(payload, ("source_type", "source", "来源"), default="manual_import") or "").strip()
        or "manual_import",
        "cash": round(cash, 6),
        "positions": positions,
    }
    snapshot["snapshot_id"] = f"hs_{_snapshot_digest(snapshot)}"
    snapshot["summary"] = _snapshot_summary(snapshot)
    return snapshot


def load_latest_holdings_snapshot(results_root: Path, account_id: str | None = None) -> dict[str, Any] | None:
    normalized_account_id = _normalize_account_id(str(account_id or default_sim_account_id()))
    try:
        payload = ops_domain_pg.get_latest_holdings_snapshot(results_root, normalized_account_id)
    except ops_domain_pg.OpsDomainDbUnavailable:
        payload = None
    if payload:
        _atomic_write_json(_latest_snapshot_path(results_root, normalized_account_id), payload)
        return payload
    payload = _read_json(_latest_snapshot_path(results_root, normalized_account_id))
    if payload:
        try:
            ops_domain_pg.upsert_holdings_snapshot(results_root, payload)
        except ops_domain_pg.OpsDomainDbUnavailable:
            pass
    return payload or None


def store_holdings_snapshot(
    results_root: Path,
    payload: Mapping[str, Any],
    *,
    default_account_id_value: str | None = None,
    now_ts: int | None = None,
) -> dict[str, Any]:
    fallback_account_id = default_account_id_value or default_sim_account_id()
    account_candidate = str(
        _pick_value(payload, ("account_id", "account", "账户", "账户ID"), default=fallback_account_id) or fallback_account_id
    )
    try:
        snapshot = normalize_holdings_snapshot(
            payload,
            default_account_id_value=fallback_account_id,
            now_ts=now_ts,
        )
    except ValueError as exc:
        try:
            normalized_account_id = _normalize_account_id(account_candidate)
        except ValueError:
            normalized_account_id = fallback_account_id
        sim_account_domain.ensure_account_profile(results_root, normalized_account_id, now_ts=now_ts)
        sim_account_domain.write_sync_log_entry(
            results_root,
            account_id=normalized_account_id,
            entry={
                "event_type": "snapshot_sync_failed",
                "status": "failed",
                "source_type": str(_pick_value(payload, ("source_type", "source", "鏉ユ簮"), default="manual_import") or "manual_import"),
                "message": str(exc),
                "created_at": _now_iso(now_ts),
            },
            now_ts=now_ts,
        )
        _append_jsonl(
            _audit_log_path(results_root, normalized_account_id),
            {
                "event_type": "snapshot_sync_failed",
                "account_id": normalized_account_id,
                "reason": str(exc),
                "at": _now_iso(now_ts),
            },
        )
        raise

    account_id = str(snapshot["account_id"])
    sim_account_domain.ensure_account_profile(results_root, account_id, now_ts=now_ts)
    previous_snapshot = load_latest_holdings_snapshot(results_root, account_id)
    pending_summary = _pending_ticket_summary(results_root)
    snapshot["drift_summary"] = _build_drift_summary(previous_snapshot, snapshot, pending_summary=pending_summary)

    history_path = _holdings_history_root(results_root, account_id) / f"{snapshot['snapshot_id']}.json"
    latest_path = _latest_snapshot_path(results_root, account_id)
    try:
        ops_domain_pg.upsert_holdings_snapshot(results_root, snapshot)
    except ops_domain_pg.OpsDomainDbUnavailable:
        pass
    _atomic_write_json(history_path, snapshot)
    _atomic_write_json(latest_path, snapshot)
    _append_jsonl(
        _audit_log_path(results_root, account_id),
        {
            "event_type": "snapshot_synced",
            "account_id": account_id,
            "snapshot_id": snapshot["snapshot_id"],
            "trade_date": snapshot["trade_date"],
            "source_type": snapshot["source_type"],
            "position_count": snapshot["summary"]["position_count"],
            "has_drift": snapshot["drift_summary"]["has_drift"],
            "pending_ticket_count": snapshot["drift_summary"]["pending_ticket_count"],
            "at": snapshot["synced_at"],
        },
    )
    sim_account_domain.write_sync_log_entry(
        results_root,
        account_id=account_id,
        entry={
            "event_type": "snapshot_synced",
            "status": "success",
            "snapshot_id": snapshot["snapshot_id"],
            "trade_date": snapshot["trade_date"],
            "source_type": snapshot["source_type"],
            "message": "holdings snapshot synchronized",
            "created_at": snapshot["synced_at"],
        },
        now_ts=now_ts,
    )
    return snapshot


def get_holdings_sync_status(
    results_root: Path,
    account_id: str | None = None,
    *,
    now_ts: int | None = None,
) -> dict[str, Any]:
    normalized_account_id = _normalize_account_id(str(account_id or default_sim_account_id()))
    snapshot = load_latest_holdings_snapshot(results_root, normalized_account_id)
    if not snapshot:
        return {
            "schema_version": _STATUS_SCHEMA_VERSION,
            "account_id": normalized_account_id,
            "status": "unsynced",
            "latest_snapshot_id": "",
            "trade_date": "",
            "synced_at": "",
            "age_seconds": None,
            "warnings": ["当前账户尚未同步真实持仓"],
            "drift_summary": {
                "has_previous_snapshot": False,
                "has_drift": False,
                "previous_snapshot_id": "",
                "added_symbols": [],
                "removed_symbols": [],
                "qty_changed": [],
                "pending_ticket_count": 0,
                "pending_ticket_ids": [],
                "pending_ticket_drift": False,
            },
        }

    synced_ts = _parse_iso_ts(snapshot.get("synced_at"))
    age_seconds = None if synced_ts is None else max(_now_ts(now_ts) - synced_ts, 0)
    stale = age_seconds is not None and age_seconds > sim_account_stale_seconds()
    warnings: list[str] = []
    if stale:
        warnings.append("真实持仓同步已过期，请先刷新模拟盘持仓")
    drift_summary = snapshot.get("drift_summary") if isinstance(snapshot.get("drift_summary"), dict) else {}
    if bool(drift_summary.get("pending_ticket_drift")):
        warnings.append("待执行 ticket 期间持仓发生变化，旧动作单可能失效")
    return {
        "schema_version": _STATUS_SCHEMA_VERSION,
        "account_id": normalized_account_id,
        "status": "stale" if stale else "fresh",
        "latest_snapshot_id": str(snapshot.get("snapshot_id") or ""),
        "trade_date": str(snapshot.get("trade_date") or ""),
        "synced_at": str(snapshot.get("synced_at") or ""),
        "age_seconds": age_seconds,
        "warnings": warnings,
        "drift_summary": drift_summary,
    }


__all__ = [
    "default_sim_account_id",
    "get_holdings_sync_status",
    "load_latest_holdings_snapshot",
    "normalize_holdings_snapshot",
    "sim_account_stale_seconds",
    "store_holdings_snapshot",
]
