from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Mapping

LINEAGE_LEDGER_CONTRACT_VERSION = "execution_lineage_ledger@1"
LINEAGE_AUDIT_CONTRACT_VERSION = "execution_lineage_audit@1"
LINEAGE_LEDGER_COLUMNS: tuple[str, ...] = (
    "signal_id",
    "signal_date",
    "order_id",
    "scheduled_date",
    "last_scheduled_date",
    "schedule_attempts",
    "fill_id",
    "fill_date",
    "symbol",
    "side",
    "qty",
    "reason_code",
    "signal_alpha_id",
    "signal_sleeve_id",
    "entry_alpha_id",
    "entry_sleeve_id",
    "terminal_status",
    "terminal_reason",
    "deferred_count",
)
_MAX_LINEAGE_SAMPLES = 5


def _normalized_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any, *, fallback: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return int(fallback)


def _iso_date(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value or "").strip()[:10]


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(payload or {}), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _signal_identity_payload(signal: Any) -> dict[str, Any]:
    meta = dict(getattr(signal, "meta", {}) or {})
    return {
        "signal_date": _iso_date(getattr(signal, "signal_date", None)),
        "symbol": _normalized_text(getattr(signal, "symbol", "")),
        "side": _text(getattr(signal, "side", "")).upper(),
        "qty": _safe_int(getattr(signal, "qty", 0)),
        "reason_code": _text(getattr(signal, "reason_code", "") or getattr(signal, "reason", "")),
        "alpha_id": _text(meta.get("alpha_id") or meta.get("entry_alpha_id")),
        "sleeve_id": _text(meta.get("sleeve_id") or meta.get("entry_sleeve_id")),
        "exit_owner": _text(meta.get("exit_owner")),
        "triggered_rule": _text(meta.get("triggered_rule")),
    }


def attach_signal_lineage(day_signals: Any) -> None:
    signals = list(getattr(day_signals, "sell_signals", []) or ()) + list(getattr(day_signals, "buy_signals", []) or ())
    seen_counts: dict[str, int] = {}
    indexed: list[tuple[str, int, Any, dict[str, Any]]] = []
    for original_index, signal in enumerate(signals):
        payload = _signal_identity_payload(signal)
        key = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        indexed.append((key, original_index, signal, payload))
    for key, original_index, signal, payload in sorted(indexed, key=lambda item: (item[0], item[1])):
        occurrence = int(seen_counts.get(key, 0))
        seen_counts[key] = occurrence + 1
        meta = dict(getattr(signal, "meta", {}) or {})
        meta["signal_id"] = _stable_id("sig", {**payload, "occurrence": occurrence})
        meta.setdefault("signal_date", payload["signal_date"])
        signal.meta = meta


def record_scheduled_orders(
    runtime: Any,
    *,
    decision_date: date,
    scheduled_date: date | None,
    orders: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records = getattr(runtime, "execution_lineage_records", None)
    if not isinstance(records, dict):
        records = {}
        setattr(runtime, "execution_lineage_records", records)

    out: list[dict[str, Any]] = []
    indexed: list[tuple[str, int, dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for original_index, raw_order in enumerate(list(orders or ())):
        order = dict(raw_order or {})
        meta = dict(order.get("meta") or {})
        signal_id = _text(meta.get("signal_id"))
        signal_date = _text(meta.get("signal_date")) or decision_date.isoformat()
        payload = {
            "signal_id": signal_id,
            "signal_date": signal_date,
            "scheduled_date": _iso_date(scheduled_date),
            "symbol": _normalized_text(order.get("symbol")),
            "side": _text(order.get("side")).upper(),
            "qty": _safe_int(order.get("qty")),
            "reason_code": _text(order.get("reason_code")),
        }
        key = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        indexed.append((key, original_index, order, meta, payload))

    occurrence_by_index: dict[int, int] = {}
    seen_counts: dict[str, int] = {}
    for key, original_index, order, meta, payload in sorted(indexed, key=lambda item: (item[0], item[1])):
        occurrence = int(seen_counts.get(key, 0))
        seen_counts[key] = occurrence + 1
        occurrence_by_index[original_index] = occurrence

    for _, original_index, order, meta, payload in indexed:
        occurrence = int(occurrence_by_index.get(original_index, 0))
        if not _text(meta.get("signal_id")):
            meta["signal_id"] = _stable_id(
                "sig",
                {
                    "signal_date": payload["signal_date"],
                    "symbol": payload["symbol"],
                    "side": payload["side"],
                    "qty": payload["qty"],
                    "reason_code": payload["reason_code"],
                    "occurrence": occurrence,
                },
            )
        order_id = _text(meta.get("order_id")) or _stable_id("ord", {**payload, "signal_id": meta["signal_id"], "occurrence": occurrence})
        meta["order_id"] = order_id
        meta["signal_date"] = payload["signal_date"]
        meta["scheduled_date"] = payload["scheduled_date"]
        order["meta"] = meta
        out.append(order)

        record = dict(records.get(order_id) or {})
        if not record:
            record = {
                "signal_id": _text(meta.get("signal_id")),
                "signal_date": payload["signal_date"],
                "order_id": order_id,
                "scheduled_date": payload["scheduled_date"],
                "last_scheduled_date": payload["scheduled_date"],
                "schedule_attempts": 1,
                "fill_id": "",
                "fill_date": "",
                "symbol": payload["symbol"],
                "side": payload["side"],
                "qty": int(payload["qty"]),
                "reason_code": payload["reason_code"],
                "signal_alpha_id": _text(meta.get("alpha_id") or meta.get("entry_alpha_id")),
                "signal_sleeve_id": _text(meta.get("sleeve_id") or meta.get("entry_sleeve_id")),
                "entry_alpha_id": _text(meta.get("entry_alpha_id") or meta.get("alpha_id")),
                "entry_sleeve_id": _text(meta.get("entry_sleeve_id") or meta.get("sleeve_id")),
                "terminal_status": "",
                "terminal_reason": "",
                "deferred_count": 0,
            }
        else:
            record["last_scheduled_date"] = payload["scheduled_date"]
            record["schedule_attempts"] = int(record.get("schedule_attempts", 0) or 0) + 1
            if not _text(record.get("scheduled_date")):
                record["scheduled_date"] = payload["scheduled_date"]
        records[order_id] = record
    return out


def record_fill_outcome(
    runtime: Any,
    *,
    day: date,
    order: Mapping[str, Any],
    status: str,
    reason: str = "",
) -> str | None:
    records = getattr(runtime, "execution_lineage_records", None)
    if not isinstance(records, dict):
        return None
    meta = dict((order or {}).get("meta") or {})
    order_id = _text(meta.get("order_id"))
    if not order_id:
        return None
    record = dict(records.get(order_id) or {})
    if not record:
        return None
    status_norm = _normalized_text(status)
    if status_norm == "deferred":
        record["deferred_count"] = int(record.get("deferred_count", 0) or 0) + 1
        records[order_id] = record
        return None
    if status_norm == "filled":
        fill_payload = {
            "order_id": order_id,
            "fill_date": day.isoformat(),
            "symbol": _normalized_text(order.get("symbol")),
            "side": _text(order.get("side")).upper(),
            "qty": _safe_int(order.get("qty")),
        }
        fill_id = _stable_id("fil", fill_payload)
        record["fill_id"] = fill_id
        record["fill_date"] = day.isoformat()
        record["terminal_status"] = "filled"
        record["terminal_reason"] = ""
        records[order_id] = record
        return fill_id
    record["terminal_status"] = status_norm or "expired"
    record["terminal_reason"] = _text(reason)
    records[order_id] = record
    return None


def finalize_execution_lineage(runtime: Any) -> list[dict[str, Any]]:
    records = getattr(runtime, "execution_lineage_records", None)
    if not isinstance(records, dict):
        return []
    rows: list[dict[str, Any]] = []
    for order_id, raw_record in records.items():
        record = dict(raw_record or {})
        if not _text(record.get("terminal_status")):
            record["terminal_status"] = "missing_fill"
            record["terminal_reason"] = "UNFILLED_END_OF_RANGE"
            records[order_id] = record
        rows.append({column: record.get(column) for column in LINEAGE_LEDGER_COLUMNS})
    rows.sort(
        key=lambda row: (
            _text(row.get("signal_date")),
            _text(row.get("scheduled_date")),
            _text(row.get("symbol")),
            _text(row.get("order_id")),
        )
    )
    return rows


def _parse_date(value: Any) -> date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except Exception:
        return None


def _append_sample(target: list[dict[str, Any]], sample: dict[str, Any]) -> None:
    if len(target) < _MAX_LINEAGE_SAMPLES:
        target.append(sample)


def build_execution_lineage_audit(
    rows: list[dict[str, Any]] | None,
    *,
    ledger_ref: str | None = None,
    planning_reject_reason_counts: Mapping[str, Any] | None = None,
    fill_reject_reason_counts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    ledger_rows = list(rows or ())
    planning_reason_counts = {str(key): int(value or 0) for key, value in dict(planning_reject_reason_counts or {}).items()}
    fill_reason_counts = {str(key): int(value or 0) for key, value in dict(fill_reject_reason_counts or {}).items()}
    summary = {
        "generated_count": int(len(ledger_rows)),
        "scheduled_count": int(len(ledger_rows)),
        "filled_count": 0,
        "expired_count": 0,
        "rejected_count": 0,
        "canceled_count": 0,
        "missing_fill_count": 0,
        "same_day_fill_count": 0,
        "open_count": 0,
        "terminal_reason_counts": {},
        "planning_reject_reason_counts": planning_reason_counts,
        "fill_reject_reason_counts": fill_reason_counts,
        "planning_cash_skip_count": int(
            int(planning_reason_counts.get("SKIP_NO_CASH", 0) or 0)
            + int(planning_reason_counts.get("SKIP_CASH_INSUFFICIENT", 0) or 0)
        ),
        "fill_insufficient_cash_count": int(fill_reason_counts.get("INSUFFICIENT_CASH", 0) or 0),
    }
    samples = {
        "same_day_fill": [],
        "dropped_order": [],
        "missing_fill": [],
    }
    if not ledger_rows:
        return {
            "contract_version": LINEAGE_AUDIT_CONTRACT_VERSION,
            "status": "UNKNOWN",
            "reason": "Missing execution lineage ledger evidence.",
            "summary": summary,
            "samples": samples,
            "ledger_ref": ledger_ref,
        }

    for row in ledger_rows:
        terminal_status = _normalized_text(row.get("terminal_status"))
        terminal_reason = _text(row.get("terminal_reason"))
        signal_dt = _parse_date(row.get("signal_date"))
        fill_dt = _parse_date(row.get("fill_date"))
        if terminal_status == "filled":
            summary["filled_count"] += 1
            if signal_dt is not None and fill_dt is not None and fill_dt <= signal_dt:
                summary["same_day_fill_count"] += 1
                _append_sample(
                    samples["same_day_fill"],
                    {
                        "signal_id": row.get("signal_id"),
                        "order_id": row.get("order_id"),
                        "fill_id": row.get("fill_id"),
                        "signal_date": row.get("signal_date"),
                        "fill_date": row.get("fill_date"),
                        "symbol": row.get("symbol"),
                        "side": row.get("side"),
                    },
                )
        elif terminal_status == "expired":
            summary["expired_count"] += 1
            if terminal_reason:
                summary["terminal_reason_counts"][terminal_reason] = int(summary["terminal_reason_counts"].get(terminal_reason, 0)) + 1
            _append_sample(
                samples["dropped_order"],
                {
                    "signal_id": row.get("signal_id"),
                    "order_id": row.get("order_id"),
                    "signal_date": row.get("signal_date"),
                    "scheduled_date": row.get("last_scheduled_date") or row.get("scheduled_date"),
                    "symbol": row.get("symbol"),
                    "side": row.get("side"),
                    "terminal_reason": row.get("terminal_reason"),
                },
            )
        elif terminal_status == "rejected":
            summary["rejected_count"] += 1
            if terminal_reason:
                summary["terminal_reason_counts"][terminal_reason] = int(summary["terminal_reason_counts"].get(terminal_reason, 0)) + 1
            _append_sample(
                samples["dropped_order"],
                {
                    "signal_id": row.get("signal_id"),
                    "order_id": row.get("order_id"),
                    "signal_date": row.get("signal_date"),
                    "scheduled_date": row.get("last_scheduled_date") or row.get("scheduled_date"),
                    "symbol": row.get("symbol"),
                    "side": row.get("side"),
                    "terminal_reason": row.get("terminal_reason"),
                },
            )
        elif terminal_status == "canceled":
            summary["canceled_count"] += 1
            if terminal_reason:
                summary["terminal_reason_counts"][terminal_reason] = int(summary["terminal_reason_counts"].get(terminal_reason, 0)) + 1
            _append_sample(
                samples["dropped_order"],
                {
                    "signal_id": row.get("signal_id"),
                    "order_id": row.get("order_id"),
                    "signal_date": row.get("signal_date"),
                    "scheduled_date": row.get("last_scheduled_date") or row.get("scheduled_date"),
                    "symbol": row.get("symbol"),
                    "side": row.get("side"),
                    "terminal_reason": row.get("terminal_reason"),
                },
            )
        elif terminal_status == "missing_fill":
            summary["missing_fill_count"] += 1
            if terminal_reason:
                summary["terminal_reason_counts"][terminal_reason] = int(summary["terminal_reason_counts"].get(terminal_reason, 0)) + 1
            _append_sample(
                samples["missing_fill"],
                {
                    "signal_id": row.get("signal_id"),
                    "order_id": row.get("order_id"),
                    "signal_date": row.get("signal_date"),
                    "scheduled_date": row.get("last_scheduled_date") or row.get("scheduled_date"),
                    "symbol": row.get("symbol"),
                    "side": row.get("side"),
                    "terminal_reason": row.get("terminal_reason"),
                },
            )
        else:
            summary["open_count"] += 1

    if int(summary["same_day_fill_count"]) > 0 or int(summary["missing_fill_count"]) > 0:
        status = "FAIL"
        reason = "Detected same-day fills or missing-fill lineage breaks."
    elif int(summary["expired_count"]) > 0 or int(summary["rejected_count"]) > 0 or int(summary["canceled_count"]) > 0:
        status = "WARN"
        reason = "Detected dropped execution lineage records."
    else:
        status = "PASS"
        reason = "Execution lineage ledger is internally consistent."

    return {
        "contract_version": LINEAGE_AUDIT_CONTRACT_VERSION,
        "status": status,
        "reason": reason,
        "summary": summary,
        "samples": samples,
        "ledger_ref": ledger_ref,
    }
