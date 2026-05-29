from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from backend.core.contracts.daily_position_adjustment_package import (
    PACKAGE_SCHEMA_VERSION,
    DailyPositionAdjustmentPackage,
    PackageAction,
    PackageClock,
    PackageHeader,
    PackageInputs,
    PackageScope,
    PackageSource,
    PackageValidation,
    RiskFlag,
    TargetPosition,
)
from backend.core.services.live_strategy_registry_service import LiveStrategyRecord


PublishMode = Literal["live", "dry_run", "audit_copy"]


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def _stable_id(prefix: str, payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return None


def _reason_tags_from_row(row: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for item in row.get("reason_tags") or []:
        text = _text(item)
        if text and text not in tags:
            tags.append(text)
    return tags


def _reason_codes_from_row(row: dict[str, Any]) -> list[str]:
    codes: list[str] = []
    for value in [row.get("reason_code"), row.get("blocked_reason")]:
        text = _text(value)
        if text and text not in codes:
            codes.append(text)
    for text in _reason_tags_from_row(row):
        if text and text not in codes:
            codes.append(text)
    return codes


def _gate_failure_reason_codes(
    *,
    strategy: LiveStrategyRecord,
    reconcile_payload: dict[str, Any],
    baseline_id: str,
    execution_contract_hash: str,
    account_scope: str,
    enforce_live_status: bool,
    stale: bool,
    drifted: bool,
    extra_failure_reason_codes: list[str] | None = None,
) -> list[str]:
    strategy_source = reconcile_payload.get("strategy_source") if isinstance(reconcile_payload.get("strategy_source"), dict) else {}
    failure_reason_codes: list[str] = []
    if enforce_live_status and strategy.status != "live_approved":
        failure_reason_codes.append("strategy_not_live_approved")
    if _text(baseline_id) != strategy.baseline_id:
        failure_reason_codes.append("baseline_id_mismatch")
    if _text(strategy_source.get("config_hash")) != strategy.config_hash:
        failure_reason_codes.append("config_hash_mismatch")
    if _text(execution_contract_hash) != strategy.execution_contract_hash:
        failure_reason_codes.append("execution_contract_hash_mismatch")
    if _text(account_scope) not in set(strategy.account_scopes):
        failure_reason_codes.append("account_scope_not_allowed")
    if stale:
        failure_reason_codes.append("stale_reconcile")
    if drifted:
        failure_reason_codes.append("drifted_reconcile")
    for code in extra_failure_reason_codes or []:
        text = _text(code)
        if text and text not in failure_reason_codes:
            failure_reason_codes.append(text)
    return failure_reason_codes


def _target_positions_from_rows(rows: list[dict[str, Any]]) -> list[TargetPosition]:
    out: list[TargetPosition] = []
    seen: set[str] = set()
    for row in rows:
        symbol = _text(row.get("symbol"))
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        target_weight = _float_or_none(row.get("target_weight"))
        out.append(
            TargetPosition(
                symbol=symbol,
                target_weight=float(target_weight if target_weight is not None else 0.0),
                target_qty=_int_or_none(row.get("target_qty")),
                current_qty=_int_or_none(row.get("current_qty")),
                reference_price=_float_or_none(row.get("reference_price")),
            )
        )
    return out


def _default_expires_at(execution_date: str) -> str:
    return f"{execution_date}T15:00:00+08:00"


def _actions_from_rows(
    package_id: str,
    rows: list[dict[str, Any]],
    *,
    market: str,
    asset_class: str,
    reference_price_basis: str,
    expires_at: str,
) -> list[PackageAction]:
    actions: list[PackageAction] = []
    for idx, row in enumerate(rows, start=1):
        action_type = _text(row.get("action_type")).lower()
        if action_type == "hold":
            continue
        if action_type not in {"buy", "sell", "increase", "reduce", "rebalance"}:
            continue
        symbol = _text(row.get("symbol"))
        if not symbol:
            continue
        action_id = _stable_id("act", {"package_id": package_id, "idx": idx, "symbol": symbol, "action_type": action_type})
        blocked = bool(row.get("blocked"))
        current_qty = _int_or_none(row.get("current_qty"))
        target_qty = _int_or_none(row.get("target_qty"))
        delta_qty = _int_or_none(row.get("delta_qty"))
        suggested_qty = _int_or_none(row.get("suggested_qty"))
        reference_price = _float_or_none(row.get("reference_price"))
        if current_qty is None:
            current_qty = 0
        if target_qty is None:
            target_qty = current_qty
        if delta_qty is None:
            delta_qty = target_qty - current_qty
        if suggested_qty is None:
            suggested_qty = abs(delta_qty)
        estimated_amount = None
        if suggested_qty is not None and reference_price is not None:
            estimated_amount = abs(float(suggested_qty) * float(reference_price))
        reason_code = _text(row.get("reason_code"), _text(row.get("blocked_reason"), action_type.upper()))
        actions.append(
            PackageAction(
                action_id=action_id,
                idempotency_key=f"{package_id}:{action_id}",
                symbol=symbol,
                market=market,
                asset_class=asset_class,
                action_type=action_type,  # type: ignore[arg-type]
                action_status="blocked" if blocked else "proposed",
                current_qty=current_qty,
                target_qty=target_qty,
                delta_qty=delta_qty,
                suggested_qty=suggested_qty,
                target_weight=_float_or_none(row.get("target_weight")),
                reference_price=float(reference_price if reference_price is not None else 0.0),
                reference_price_basis=_text(row.get("reference_price_basis"), reference_price_basis),
                estimated_amount=estimated_amount,
                reason_code=reason_code,
                reason_tags=_reason_tags_from_row(row),
                reason_codes=_reason_codes_from_row(row),
                blocked=blocked,
                blocked_reason=_text(row.get("blocked_reason")),
                expires_at=_text(row.get("expires_at"), expires_at),
            )
        )
    return actions


def _risk_flags(
    *,
    failure_reason_codes: list[str],
    stale: bool,
    drifted: bool,
    blocked_rows: list[dict[str, Any]],
) -> list[RiskFlag]:
    flags: list[RiskFlag] = []
    for code in failure_reason_codes:
        flags.append(RiskFlag(code=code, severity="blocker", message=f"Publish gate blocked: {code}"))
    if stale and "stale_reconcile" not in failure_reason_codes:
        flags.append(RiskFlag(code="stale_reconcile", severity="blocker", message="Reconcile payload is stale."))
    if drifted and "drifted_reconcile" not in failure_reason_codes:
        flags.append(RiskFlag(code="drifted_reconcile", severity="blocker", message="Reconcile payload drift was detected."))
    for row in blocked_rows:
        code = _text(row.get("blocked_reason"), "action_blocked")
        flags.append(RiskFlag(code=code, severity="blocker", message=f"Action blocked for {_text(row.get('symbol'), 'unknown')}: {code}"))
    return flags


def build_daily_position_adjustment_package_from_reconcile(
    reconcile_payload: dict[str, Any],
    *,
    strategy: LiveStrategyRecord,
    baseline_id: str,
    execution_contract_hash: str,
    signal_date: str | None = None,
    execution_date: str | None = None,
    market: str = "CN_A",
    asset_class: str = "equity",
    currency: str = "CNY",
    symbol_namespace: str = "tushare_ts_code",
    market_snapshot_id: str | None = None,
    cash_snapshot_id: str | None = None,
    publish_mode: PublishMode = "live",
    stale: bool = False,
    drifted: bool = False,
    failure_reason_codes: list[str] | None = None,
    generated_at: str | None = None,
) -> DailyPositionAdjustmentPackage:
    strategy_source = reconcile_payload.get("strategy_source") if isinstance(reconcile_payload.get("strategy_source"), dict) else {}
    execution_assumptions = (
        reconcile_payload.get("execution_assumptions") if isinstance(reconcile_payload.get("execution_assumptions"), dict) else {}
    )
    account_scope = _text(reconcile_payload.get("account_id"), strategy.account_scopes[0] if strategy.account_scopes else "")
    resolved_signal_date = _text(signal_date, _text(reconcile_payload.get("as_of_date"), _text(reconcile_payload.get("snapshot_trade_date"))))
    resolved_execution_date = _text(execution_date, resolved_signal_date)
    reconcile_id = _text(reconcile_payload.get("reconcile_id"), _stable_id("reconcile", reconcile_payload))
    strategy_run_id = _text(strategy_source.get("exp_id"), reconcile_id)
    package_seed = {
        "strategy_id": strategy.strategy_id,
        "strategy_run_id": strategy_run_id,
        "signal_date": resolved_signal_date,
        "execution_date": resolved_execution_date,
        "account_scope": account_scope,
        "publish_mode": publish_mode,
        "reconcile_id": reconcile_id,
    }
    package_id = _stable_id("pkg", package_seed)

    rows = [dict(item) for item in (reconcile_payload.get("action_sheet") or []) if isinstance(item, dict)]
    blocked_rows = [row for row in rows if bool(row.get("blocked"))]
    enforce_live_status = publish_mode == "live"
    gate_failure_codes = _gate_failure_reason_codes(
        strategy=strategy,
        reconcile_payload=reconcile_payload,
        baseline_id=baseline_id,
        execution_contract_hash=execution_contract_hash,
        account_scope=account_scope,
        enforce_live_status=enforce_live_status,
        stale=stale,
        drifted=drifted,
        extra_failure_reason_codes=failure_reason_codes,
    )
    for row in blocked_rows:
        code = _text(row.get("blocked_reason"), "action_blocked")
        if code not in gate_failure_codes:
            gate_failure_codes.append(code)

    target_positions = _target_positions_from_rows(rows)
    resolved_reference_price_basis = _text(execution_assumptions.get("reference_price_basis"), "latest_close")
    default_expires_at = _text(reconcile_payload.get("expires_at"), _default_expires_at(resolved_execution_date))
    actions = _actions_from_rows(
        package_id,
        rows,
        market=market,
        asset_class=asset_class,
        reference_price_basis=resolved_reference_price_basis,
        expires_at=default_expires_at,
    )
    has_actionable = any(action.action_status == "proposed" for action in actions)
    if gate_failure_codes:
        package_status = "blocked"
        validation_status = "blocked"
    elif has_actionable:
        package_status = "ready"
        validation_status = "passed"
    else:
        package_status = "no_op"
        validation_status = "passed"

    package = DailyPositionAdjustmentPackage(
        header=PackageHeader(
            schema_version=PACKAGE_SCHEMA_VERSION,
            package_id=package_id,
            idempotency_key=f"{strategy.strategy_id}:{account_scope}:{resolved_signal_date}:{publish_mode}",
            generated_at=_text(generated_at, _now_iso()),
        ),
        source=PackageSource(
            strategy_id=strategy.strategy_id,
            strategy_run_id=strategy_run_id,
            baseline_id=baseline_id,
            config_hash=_text(strategy_source.get("config_hash"), "missing_config_hash"),
            execution_contract_hash=execution_contract_hash,
            publish_mode=publish_mode,
        ),
        clock=PackageClock(
            signal_date=resolved_signal_date,
            execution_date=resolved_execution_date,
            signal_clock=_text(execution_assumptions.get("signal_clock"), "POST_CLOSE"),
            execution_clock=_text(execution_assumptions.get("execution_clock"), "NEXT_OPEN"),
            reference_price_basis=resolved_reference_price_basis,
        ),
        scope=PackageScope(
            market=market,
            asset_scope=_text(strategy_source.get("asset_scope"), strategy.asset_scope),
            asset_class=asset_class,
            account_scope=account_scope,
            currency=currency,
            symbol_namespace=symbol_namespace,
        ),
        inputs=PackageInputs(
            market_snapshot_id=_text(market_snapshot_id, f"{market}:{resolved_signal_date}"),
            holdings_snapshot_id=_text(reconcile_payload.get("snapshot_id")),
            cash_snapshot_id=_text(cash_snapshot_id, f"cash:{_text(reconcile_payload.get('snapshot_id'))}"),
            reconcile_id=reconcile_id,
        ),
        package_status=package_status,  # type: ignore[arg-type]
        target_positions=target_positions,
        action_sheet=actions if package_status != "no_op" else [],
        risk_flags=(
            _risk_flags(
                failure_reason_codes=gate_failure_codes,
                stale=stale,
                drifted=drifted,
                blocked_rows=blocked_rows,
            )
            or (
                [RiskFlag(code="no_action_required", severity="info", message="No position adjustment action is required.")]
                if package_status == "no_op"
                else []
            )
        ),
        validation=PackageValidation(
            status=validation_status,  # type: ignore[arg-type]
            failure_reason_codes=gate_failure_codes,
            stale=bool(stale),
            drifted=bool(drifted),
        ),
    )
    return package


def package_to_payload(package: DailyPositionAdjustmentPackage) -> dict[str, Any]:
    return package.model_dump(mode="json", exclude_none=True)


__all__ = [
    "build_daily_position_adjustment_package_from_reconcile",
    "package_to_payload",
]
