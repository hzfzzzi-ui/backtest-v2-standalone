from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


_ROLE_SET = frozenset({"rank", "veto", "context", "lifecycle", "state"})
_LAYER_SET = frozenset({"candidate", "ranking", "holding", "exit", "holding_exit", "state"})
_MONEYFLOW_VETO_PATTERN = re.compile(r"^veto_bottom\d+$")


@dataclass(frozen=True, slots=True)
class FactorInsertionContractSnapshot:
    valid: bool = True
    factor_role: str = ""
    apply_layer: str = ""
    action: str = ""
    status: str = ""
    reason: str = ""
    error_field: str = ""


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_role(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in _ROLE_SET else ""


def _normalize_layer(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in _LAYER_SET else ""


def _normalize_moneyflow_mode(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"", "off"}:
        return "off"
    if text in {
        "shadow",
        "tiebreak",
        "bull_only_tiebreak",
        "soft_weight",
        "band_rerank",
        "bull_only_band_rerank",
        "bull_trans_up_band_rerank",
    }:
        return text
    if _MONEYFLOW_VETO_PATTERN.match(text):
        return text
    return ""


def _normalize_positive_int(value: Any) -> int:
    try:
        parsed = int(value)
    except Exception:
        return 0
    return parsed if parsed > 0 else 0


def _normalize_fragility_action(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"watch", "fragility_watch"}:
        return "watch"
    if text in {"trim_candidate", "fragility_trim_candidate"}:
        return "trim_candidate"
    if text in {"exit_candidate", "fragility_exit_candidate"}:
        return "exit_candidate"
    return ""


def _invalid(
    *,
    factor_role: str,
    apply_layer: str,
    action: str,
    status: str,
    reason: str,
    error_field: str,
) -> FactorInsertionContractSnapshot:
    return FactorInsertionContractSnapshot(
        valid=False,
        factor_role=factor_role,
        apply_layer=apply_layer,
        action=action,
        status=status,
        reason=reason,
        error_field=error_field,
    )


def resolve_moneyflow_overlay_contract(raw_cfg: Mapping[str, Any] | None) -> FactorInsertionContractSnapshot:
    cfg = dict(raw_cfg or {})
    enabled = _as_bool(cfg.get("enabled"), default=False)
    mode_raw = str(cfg.get("mode") or "off").strip().lower()
    mode = _normalize_moneyflow_mode(mode_raw)
    if not enabled or mode == "off":
        return FactorInsertionContractSnapshot(
            valid=True,
            factor_role="",
            apply_layer=_normalize_layer(cfg.get("apply_layer")) or "candidate",
            action="off",
            status="disabled",
        )
    if not mode:
        return _invalid(
            factor_role=_normalize_role(cfg.get("factor_role")),
            apply_layer=_normalize_layer(cfg.get("apply_layer")) or "candidate",
            action=mode_raw,
            status="invalid_action",
            reason=f"unsupported_moneyflow_overlay_mode:{mode_raw or 'empty'}",
            error_field="mode",
        )
    inferred_role = "context"
    if mode in {
        "tiebreak",
        "bull_only_tiebreak",
        "band_rerank",
        "bull_only_band_rerank",
        "bull_trans_up_band_rerank",
    }:
        inferred_role = "rank"
    elif _MONEYFLOW_VETO_PATTERN.match(mode):
        inferred_role = "veto"
    explicit_role = str(cfg.get("factor_role") or "").strip()
    factor_role = _normalize_role(explicit_role) or inferred_role
    if explicit_role and not _normalize_role(explicit_role):
        return _invalid(
            factor_role=str(explicit_role).strip().lower(),
            apply_layer=_normalize_layer(cfg.get("apply_layer")) or "candidate",
            action=mode,
            status="invalid_role",
            reason=f"unsupported_factor_role:{explicit_role}",
            error_field="factor_role",
        )
    if factor_role not in {"rank", "veto", "context"}:
        return _invalid(
            factor_role=factor_role,
            apply_layer=_normalize_layer(cfg.get("apply_layer")) or "candidate",
            action=mode,
            status="invalid_role",
            reason=f"moneyflow_overlay_disallows_role:{factor_role}",
            error_field="factor_role",
        )
    explicit_layer = str(cfg.get("apply_layer") or "").strip()
    apply_layer = _normalize_layer(explicit_layer) or "candidate"
    if explicit_layer and not _normalize_layer(explicit_layer):
        return _invalid(
            factor_role=factor_role,
            apply_layer=str(explicit_layer).strip().lower(),
            action=mode,
            status="invalid_layer",
            reason=f"unsupported_apply_layer:{explicit_layer}",
            error_field="apply_layer",
        )
    if apply_layer not in {"candidate", "ranking"}:
        return _invalid(
            factor_role=factor_role,
            apply_layer=apply_layer,
            action=mode,
            status="invalid_layer",
            reason=f"moneyflow_overlay_disallows_layer:{apply_layer}",
            error_field="apply_layer",
        )
    role_actions = {
        "context": {"shadow", "soft_weight"},
        "rank": {
            "tiebreak",
            "bull_only_tiebreak",
            "band_rerank",
            "bull_only_band_rerank",
            "bull_trans_up_band_rerank",
        },
        "veto": {"veto"},
    }
    action_family = "veto" if _MONEYFLOW_VETO_PATTERN.match(mode) else mode
    if action_family not in role_actions.get(factor_role, set()):
        return _invalid(
            factor_role=factor_role,
            apply_layer=apply_layer,
            action=mode,
            status="invalid_action",
            reason=f"moneyflow_overlay_role_action_mismatch:{factor_role}->{mode}",
            error_field="mode",
        )
    if mode in {"band_rerank", "bull_only_band_rerank", "bull_trans_up_band_rerank"} and _normalize_positive_int(cfg.get("band_limit")) < 2:
        return _invalid(
            factor_role=factor_role,
            apply_layer=apply_layer,
            action=mode,
            status="invalid_band_limit",
            reason="moneyflow_overlay_band_limit_required_for_band_rerank",
            error_field="band_limit",
        )
    return FactorInsertionContractSnapshot(
        valid=True,
        factor_role=factor_role,
        apply_layer=apply_layer,
        action=mode,
        status="ready",
    )


def resolve_holding_exit_fragility_contract(raw_cfg: Mapping[str, Any] | None) -> FactorInsertionContractSnapshot:
    cfg = dict(raw_cfg or {})
    enabled = _as_bool(cfg.get("enabled"), default=False)
    explicit_layer = str(cfg.get("apply_layer") or "").strip()
    apply_layer = _normalize_layer(explicit_layer) or "holding_exit"
    explicit_role = str(cfg.get("factor_role") or "").strip()
    factor_role = _normalize_role(explicit_role) or "lifecycle"
    action_raw = str(cfg.get("action") or "").strip().lower()
    action = _normalize_fragility_action(action_raw)
    if not enabled:
        return FactorInsertionContractSnapshot(
            valid=True,
            factor_role=factor_role,
            apply_layer=apply_layer,
            action=action or "",
            status="disabled",
        )
    if explicit_role and not _normalize_role(explicit_role):
        return _invalid(
            factor_role=str(explicit_role).strip().lower(),
            apply_layer=apply_layer,
            action=action,
            status="invalid_role",
            reason=f"unsupported_factor_role:{explicit_role}",
            error_field="factor_role",
        )
    if factor_role != "lifecycle":
        return _invalid(
            factor_role=factor_role,
            apply_layer=apply_layer,
            action=action,
            status="invalid_role",
            reason=f"holding_exit_fragility_disallows_role:{factor_role}",
            error_field="factor_role",
        )
    if explicit_layer and not _normalize_layer(explicit_layer):
        return _invalid(
            factor_role=factor_role,
            apply_layer=str(explicit_layer).strip().lower(),
            action=action,
            status="invalid_layer",
            reason=f"unsupported_apply_layer:{explicit_layer}",
            error_field="apply_layer",
        )
    if apply_layer not in {"holding_exit", "holding", "exit"}:
        return _invalid(
            factor_role=factor_role,
            apply_layer=apply_layer,
            action=action,
            status="invalid_layer",
            reason=f"holding_exit_fragility_disallows_layer:{apply_layer}",
            error_field="apply_layer",
        )
    if not action:
        return _invalid(
            factor_role=factor_role,
            apply_layer=apply_layer,
            action=action_raw,
            status="invalid_action",
            reason=f"unsupported_action:{action_raw or 'empty'}",
            error_field="action",
        )
    return FactorInsertionContractSnapshot(
        valid=True,
        factor_role=factor_role,
        apply_layer=apply_layer,
        action=action,
        status="ready",
    )


def validate_asset_context_factor_insertion_contracts(asset_context: Mapping[str, Any] | None) -> list[dict[str, str]]:
    context = dict(asset_context or {})
    errors: list[dict[str, str]] = []
    if isinstance(context.get("moneyflow_overlay"), Mapping):
        snapshot = resolve_moneyflow_overlay_contract(context.get("moneyflow_overlay"))
        if not snapshot.valid:
            errors.append(
                {
                    "path": f"asset_context.moneyflow_overlay.{snapshot.error_field or 'mode'}",
                    "message": snapshot.reason or snapshot.status or "invalid moneyflow overlay contract",
                }
            )
    if isinstance(context.get("holding_exit_fragility"), Mapping):
        snapshot = resolve_holding_exit_fragility_contract(context.get("holding_exit_fragility"))
        if not snapshot.valid:
            errors.append(
                {
                    "path": f"asset_context.holding_exit_fragility.{snapshot.error_field or 'action'}",
                    "message": snapshot.reason or snapshot.status or "invalid holding_exit_fragility contract",
                }
            )
    return errors
