from __future__ import annotations

import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import pandas as pd

from backend.api.backtest_v2.artifacts_finalize import _append_to_experiment_index
from backend.api.backtest_v2.artifacts_manifest import write_manifest
from backend.api.backtest_v2.protocol import ARTIFACT_FILENAMES
from backend.api.backtest_v2.runner_output_helpers import (
    build_execution_contract_ref,
    build_unified_combo_execution_contract,
    write_execution_contract_snapshot,
)
from backend.api.shared.paths import experiments_root as _experiments_root
from backend.api.shared.json_utils import sanitize_json
from backend.core.config.asset_profiles import build_asset_context
from backend.core.config.cn_a_governed_mainline import canonical_state_5, coarse_state_from_state_5
from backend.core.audit.research_audit import build_research_audit
from backend.core.services.account_budget_runtime import (
    build_account_allocator_runtime,
    build_account_budget_runtime_reference,
    build_shared_transition_execution_policy_config,
    build_account_state_transition_runtime,
    resolve_account_state_from_evidence,
    resolve_stock_etf_budget_for_state,
)


def _emit_progress(progress_hook: Callable[[int, str], None] | None, pct: int, message: str) -> None:
    if progress_hook is None:
        return
    try:
        progress_hook(int(max(0, min(100, pct))), str(message))
    except Exception:
        pass


def _child_progress(
    progress_hook: Callable[[int, str], None] | None,
    *,
    start: int,
    end: int,
    prefix: str,
) -> Callable[[int, str], None]:
    span = max(0, int(end) - int(start))

    def _hook(pct: int, message: str) -> None:
        mapped = int(start + (max(0, min(100, int(pct))) / 100.0) * span)
        _emit_progress(progress_hook, mapped, f"{prefix}: {message}")

    return _hook


def _allocate_combo_results_dir(bt_root: Path) -> tuple[str, Path]:
    exp_root = _experiments_root().resolve()
    exp_root.mkdir(parents=True, exist_ok=True)
    for _ in range(20):
        now = datetime.now()
        exp_id = f"exp_{now.strftime('%Y%m%d_%H%M%S')}{int(now.microsecond / 1000):03d}_{uuid4().hex[:4]}"
        results_dir = (exp_root / exp_id).resolve()
        try:
            results_dir.mkdir(parents=False, exist_ok=False)
            return exp_id, results_dir
        except FileExistsError:
            continue
    raise RuntimeError("failed to allocate unified combo exp_id after retries")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_nav_frame(results_dir: Path) -> pd.DataFrame:
    path = results_dir / "nav.csv"
    if not path.exists():
        return pd.DataFrame(columns=["date", "nav"])
    frame = pd.read_csv(path)
    if frame.empty or "date" not in frame.columns or "nav" not in frame.columns:
        return pd.DataFrame(columns=["date", "nav"])
    frame = frame[["date", "nav"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["nav"] = pd.to_numeric(frame["nav"], errors="coerce")
    frame = frame.dropna(subset=["date", "nav"]).sort_values("date").reset_index(drop=True)
    return frame


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _build_combo_nav(
    stock_results_dir: Path,
    etf_results_dir: Path,
    *,
    daily_budget_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    stock_nav = _read_nav_frame(stock_results_dir).rename(columns={"nav": "stock_nav"})
    etf_nav = _read_nav_frame(etf_results_dir).rename(columns={"nav": "etf_nav"})
    merged = stock_nav.merge(etf_nav, on="date", how="inner")
    if merged.empty:
        raise RuntimeError("unified combo requires overlapping stock/ETF nav windows")
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if isinstance(daily_budget_frame, pd.DataFrame) and not daily_budget_frame.empty:
        budget = daily_budget_frame.copy()
        budget["date"] = pd.to_datetime(budget["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        merged = merged.merge(budget, on="date", how="left")
    if "stock_weight" not in merged.columns:
        merged["stock_weight"] = 0.5
    if "etf_weight" not in merged.columns:
        merged["etf_weight"] = 0.5
    if "account_budget_effective_state_5" not in merged.columns:
        merged["account_budget_effective_state_5"] = None
    if "account_budget_source" not in merged.columns:
        merged["account_budget_source"] = "account_allocator_runtime_reference_50_50"
    if "account_budget_fallback_applied" not in merged.columns:
        merged["account_budget_fallback_applied"] = True
    if "account_state_source" not in merged.columns:
        merged["account_state_source"] = "account_layer_state_machine"
    if "account_transition_kind" not in merged.columns:
        merged["account_transition_kind"] = None
    merged["stock_weight"] = pd.to_numeric(merged["stock_weight"], errors="coerce").fillna(0.5).astype(float)
    merged["etf_weight"] = pd.to_numeric(merged["etf_weight"], errors="coerce").fillna(0.5).astype(float)
    merged["stock_ret"] = merged["stock_nav"].pct_change().fillna(0.0)
    merged["etf_ret"] = merged["etf_nav"].pct_change().fillna(0.0)
    merged["combo_ret"] = merged["stock_weight"] * merged["stock_ret"] + merged["etf_weight"] * merged["etf_ret"]
    merged["nav"] = (1.0 + merged["combo_ret"]).cumprod()
    return merged[
        [
            "date",
            "nav",
            "stock_nav",
            "etf_nav",
            "stock_ret",
            "etf_ret",
            "combo_ret",
            "stock_weight",
            "etf_weight",
            "account_budget_effective_state_5",
            "account_budget_source",
            "account_budget_fallback_applied",
            "account_state_source",
            "account_transition_kind",
        ]
    ].copy()


def _normalize_account_budget_control(
    raw_control: dict[str, Any] | None,
    *,
    unified_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    control = dict(raw_control or {})
    if control:
        control["enabled"] = bool(control.get("enabled", True))
        fallback_weights = dict(control.get("fallback_weights") or {})
        if "cn_stock_trend_alpha_core" not in fallback_weights:
            fallback_weights["cn_stock_trend_alpha_core"] = float(
                (dict(unified_runtime or {}).get("weights") or {}).get("cn_stock_trend_alpha_core", 0.5)
            )
        if "cn_etf_beta" not in fallback_weights:
            fallback_weights["cn_etf_beta"] = float(
                (dict(unified_runtime or {}).get("weights") or {}).get("cn_etf_beta", 0.5)
            )
        control["fallback_weights"] = sanitize_json(fallback_weights)
        return sanitize_json(control)
    fallback_weights = dict((dict(unified_runtime or {}).get("weights") or {}))
    return sanitize_json(
        {
            "enabled": True,
            "fallback_weights": {
                "cn_stock_trend_alpha_core": float(fallback_weights.get("cn_stock_trend_alpha_core", 0.5)),
                "cn_etf_beta": float(fallback_weights.get("cn_etf_beta", 0.5)),
            },
        }
    )


def _build_account_budget_daily_frame(
    stock_results_dir: Path,
    etf_results_dir: Path,
    *,
    account_budget_control: dict[str, Any] | None,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    payload = dict(account_budget_control or {})
    fallback_weights = dict(payload.get("fallback_weights") or {})
    if not bool(payload.get("enabled")):
        return pd.DataFrame(), {}, {}
    stock_daily = _read_csv(stock_results_dir / ARTIFACT_FILENAMES["daily"])
    etf_daily = _read_csv(etf_results_dir / ARTIFACT_FILENAMES["daily"])
    if stock_daily.empty or etf_daily.empty or "date" not in stock_daily.columns or "date" not in etf_daily.columns:
        return pd.DataFrame(), {}, {}
    stock_states = stock_daily[["date", "effective_state_5"]].rename(columns={"effective_state_5": "stock_state_5"}).copy()
    etf_states = etf_daily[["date", "effective_state_5"]].rename(columns={"effective_state_5": "etf_state_5"}).copy()
    merged = stock_states.merge(etf_states, on="date", how="inner")
    if merged.empty:
        return pd.DataFrame(), {}, {}
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    merged = merged.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    if merged.empty:
        return pd.DataFrame(), {}, {}

    def _resolve_weight(weights: dict[str, Any], key: str, fallback_weights: dict[str, Any]) -> float:
        value = weights.get(key)
        if value is None:
            value = fallback_weights.get(key)
        if value is None:
            value = 0.5
        return float(value)

    rows: list[dict[str, Any]] = []
    latest_state_resolution: dict[str, Any] = {}
    latest_transition_runtime: dict[str, Any] = {}
    previous_account_state: str | None = None
    for row in merged.to_dict("records"):
        state_resolution = resolve_account_state_from_evidence(
            stock_state_5=row.get("stock_state_5"),
            etf_state_5=row.get("etf_state_5"),
            previous_account_state_5=previous_account_state,
        )
        effective_state = state_resolution.get("effective_state_5")
        transition_runtime = build_account_state_transition_runtime(
            previous_state_5=previous_account_state,
            effective_state_5=effective_state,
        )
        resolved = resolve_stock_etf_budget_for_state(effective_state, fallback_weights=fallback_weights)
        weights = dict(resolved.get("weights") or {})
        rows.append(
            {
                "date": pd.to_datetime(row.get("date"), errors="coerce").strftime("%Y-%m-%d"),
                "account_budget_effective_state_5": resolved.get("effective_state_5"),
                "stock_weight": _resolve_weight(weights, "cn_stock_trend_alpha_core", fallback_weights),
                "etf_weight": _resolve_weight(weights, "cn_etf_beta", fallback_weights),
                "account_budget_source": str(resolved.get("source") or "account_allocator_runtime_reference_50_50"),
                "account_budget_fallback_applied": bool(resolved.get("fallback_applied")),
                "account_state_source": str(state_resolution.get("state_source") or "account_layer_state_machine"),
                "account_transition_kind": str(transition_runtime.get("transition_kind") or ""),
            }
        )
        latest_state_resolution = dict(state_resolution or {})
        latest_transition_runtime = dict(transition_runtime or {})
        previous_account_state = str(effective_state or "").strip() or previous_account_state
    return pd.DataFrame(rows), latest_state_resolution, latest_transition_runtime


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    return out if math.isfinite(out) else None


def _safe_int(value: Any) -> int | None:
    try:
        out = int(float(value))
    except Exception:
        return None
    return out


def _inject_etf_shared_transition_execution_policy(
    cfg: dict[str, Any] | None,
    *,
    account_budget_control: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(cfg, dict):
        return None
    payload = dict(cfg)
    governed_a_share = (
        dict(payload.get("governed_a_share") or {})
        if isinstance(payload.get("governed_a_share"), dict)
        else {}
    )
    etf_beta = (
        dict(governed_a_share.get("etf_beta") or {})
        if isinstance(governed_a_share.get("etf_beta"), dict)
        else {}
    )
    etf_beta["shared_transition_execution"] = build_shared_transition_execution_policy_config(
        account_budget_control=account_budget_control,
    )
    governed_a_share["etf_beta"] = etf_beta
    payload["governed_a_share"] = governed_a_share
    return sanitize_json(payload)


def _coerce_state(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    state = canonical_state_5(text)
    return state or None


def _most_defensive_state(*states: Any) -> str | None:
    order = {
        "RISK_OFF": 0,
        "TRANS_DOWN": 1,
        "TRANS_UP": 2,
        "BULL": 3,
    }
    normalized = [state for state in (_coerce_state(item) for item in states) if state]
    if not normalized:
        return None
    return min(normalized, key=lambda item: order.get(item, 999))


def _coalesce_numeric(values: list[Any], *, reducer: str = "sum") -> float | None:
    nums = [_safe_float(value) for value in values]
    present = [value for value in nums if value is not None]
    if not present:
        return None
    if reducer == "min":
        return min(present)
    if reducer == "max":
        return max(present)
    return float(sum(present))


def _coalesce_int(values: list[Any], *, reducer: str = "sum") -> int | None:
    nums = [_safe_int(value) for value in values]
    present = [value for value in nums if value is not None]
    if not present:
        return None
    if reducer == "min":
        return min(present)
    if reducer == "max":
        return max(present)
    return int(sum(present))


def _normalize_reason_codes(values: Any) -> list[str]:
    return [str(item).strip() for item in list(values or ()) if str(item).strip()]


def _prefixed_reason_codes(prefix: str, values: Any) -> list[str]:
    return [f"{prefix}::{code}" for code in _normalize_reason_codes(values)]


def _component_sleeve_payload(component_run_meta: dict[str, Any], sleeve_id: str) -> dict[str, Any]:
    governed = dict(component_run_meta.get("governed_snapshot") or {})
    sleeve_budgets = dict(governed.get("sleeve_budgets") or {})
    payload = sleeve_budgets.get(sleeve_id)
    return dict(payload or {})


def _latest_component_daily_actuals(
    component_dir: Path | None,
    *,
    asset_scope: str,
) -> dict[str, float | None]:
    if component_dir is None:
        return {}
    daily = _read_csv(component_dir / ARTIFACT_FILENAMES["daily"])
    if daily.empty:
        return {}
    if "date" in daily.columns:
        ordered = daily.copy()
        ordered["date"] = pd.to_datetime(ordered["date"], errors="coerce")
        ordered = ordered.sort_values("date")
        latest = ordered.iloc[-1]
    else:
        latest = daily.iloc[-1]
    if str(asset_scope or "").strip().lower() == "cn_etf":
        return {
            "actual_exposure": _safe_float(latest.get("etf_actual_exposure")),
            "actual_risk_exposure": _safe_float(latest.get("etf_actual_risk_exposure")),
            "actual_fallback_exposure": _safe_float(latest.get("etf_actual_fallback_exposure")),
            "actual_other_exposure": _safe_float(latest.get("etf_actual_other_exposure")),
            "actual_core_exposure": _safe_float(latest.get("etf_actual_core_exposure")),
            "actual_defense_exposure": _safe_float(latest.get("etf_actual_defense_exposure")),
        }
    gross_exposure = _safe_float(latest.get("gross_exposure"))
    return {
        "actual_exposure": gross_exposure,
        "actual_risk_exposure": gross_exposure,
        "actual_fallback_exposure": 0.0,
        "actual_other_exposure": 0.0,
    }


def _component_weighted_exposure(weight: float, value: Any, fallback: Any = None) -> float | None:
    num = _safe_float(value)
    if num is None:
        num = _safe_float(fallback)
    if num is None:
        return None
    return float(weight) * float(num)


def _build_riskoff_budget_execution_materialization(
    *,
    account_budget_runtime_reference: dict[str, Any],
    etf_run_meta: dict[str, Any],
) -> dict[str, Any]:
    shadow_budget = dict(account_budget_runtime_reference.get("riskoff_left_side_accumulation_budget") or {})
    etf_payload = dict(etf_run_meta.get("etf_beta") or {})
    formal_view = dict(etf_payload.get("formal_view") or {})
    materialization = dict(formal_view.get("riskoff_account_budget_materialization") or {})
    active = bool(materialization.get("active"))
    reject_reason = str(materialization.get("reject_reason") or "").strip()
    return sanitize_json(
        {
            "contract_version": "riskoff_account_budget_execution_materialization@1",
            "active": bool(shadow_budget.get("active")),
            "budget_established": bool(shadow_budget.get("active")),
            "execution_activated": active,
            "execution_rejected": bool(reject_reason) and not active,
            "execution_path": "riskoff_account_budget_materialization" if active else None,
            "materialization_mode": "bounded_partial_de_risk_release",
            "materialization_order": ["defense", "core_beta"],
            "release_destination": materialization.get("release_destination"),
            "release_target_cash": materialization.get("release_target_cash"),
            "release_cash": materialization.get("release_cash"),
            "bounded_partial_release_ratio_cap": materialization.get(
                "bounded_partial_release_ratio_cap"
            ),
            "reason_code": materialization.get("reason_code"),
            "reject_reason": reject_reason or None,
            "target_symbols": list(materialization.get("target_symbols") or []),
            "release_symbols": list(materialization.get("symbols") or []),
        }
    )


def _build_combo_regime(
    stock_run_meta: dict[str, Any],
    etf_run_meta: dict[str, Any],
) -> dict[str, Any]:
    stock_latest = dict(((stock_run_meta.get("regime") or {}).get("latest_state")) or {})
    etf_latest = dict(((etf_run_meta.get("regime") or {}).get("latest_state")) or {})
    stock_base = _coerce_state(stock_latest.get("base_state"))
    etf_base = _coerce_state(etf_latest.get("base_state"))
    stock_effective = _coerce_state(stock_latest.get("effective_state"))
    etf_effective = _coerce_state(etf_latest.get("effective_state"))
    base_state = _most_defensive_state(stock_base, etf_base)
    effective_state = _most_defensive_state(stock_effective, etf_effective, base_state)
    coarse_state = coarse_state_from_state_5(base_state) if base_state else None
    effective_coarse_state = coarse_state_from_state_5(effective_state) if effective_state else coarse_state
    confidence = _coalesce_numeric(
        [stock_latest.get("confidence"), etf_latest.get("confidence")],
        reducer="min",
    )
    duration_bars = _coalesce_int(
        [stock_latest.get("regime_duration_bars"), etf_latest.get("regime_duration_bars")],
        reducer="min",
    )
    reason_codes = [
        *(_prefixed_reason_codes("STOCK", stock_latest.get("reason_codes")) or (["STOCK::NO_REASON_CODES"] if stock_effective else [])),
        *(_prefixed_reason_codes("ETF", etf_latest.get("reason_codes")) or (["ETF::NO_REASON_CODES"] if etf_effective else [])),
    ]
    manual_override_reasons = []
    for prefix, payload in (("STOCK", stock_latest.get("manual_override")), ("ETF", etf_latest.get("manual_override"))):
        override = dict(payload or {}) if isinstance(payload, dict) else {}
        if override.get("active"):
            reason = str(override.get("reason") or "ACTIVE").strip()
            manual_override_reasons.append(f"{prefix}::{reason}")
    manual_override = {
        "active": bool(manual_override_reasons),
        "scope": "component_override" if manual_override_reasons else None,
        "reason": " | ".join(manual_override_reasons) if manual_override_reasons else None,
        "actor": "unified_runtime_combo_aggregator" if manual_override_reasons else None,
        "target_state_5": effective_state,
    }
    return sanitize_json(
        {
            "contract_version": "cn_stock_etf_unified_combo_regime@1",
            "base_state": base_state,
            "effective_state": effective_state,
            "coarse_state": coarse_state,
            "effective_coarse_state": effective_coarse_state,
            "confidence": confidence,
            "risk_budget_multiplier": None,
            "defense_bias": None,
            "regime_duration_bars": duration_bars,
            "reason_codes": reason_codes,
            "manual_override": manual_override,
            "component_states": {
                "stock_alpha_core": stock_latest,
                "etf_beta": etf_latest,
            },
        }
    )


def _build_combo_governed_snapshot(
    *,
    stock_run_meta: dict[str, Any],
    etf_run_meta: dict[str, Any],
    weights: dict[str, float],
    combo_regime: dict[str, Any],
    account_budget_control: dict[str, Any] | None = None,
    stock_results_dir: Path | None = None,
    etf_results_dir: Path | None = None,
) -> dict[str, Any]:
    stock_governed = dict(stock_run_meta.get("governed_snapshot") or {})
    etf_governed = dict(etf_run_meta.get("governed_snapshot") or {})
    stock_weight = float(weights.get("cn_stock_trend_alpha_core", 0.5) or 0.0)
    etf_weight = float(weights.get("cn_etf_beta", 0.5) or 0.0)
    budget_control = dict(account_budget_control or {})
    budget_control_active = bool(budget_control.get("enabled"))
    budget_source = str(
        budget_control.get("resolved_source")
        or ("account_state_budget_map" if budget_control_active else "fixed_weight_50_50_fallback")
    )
    budget_fallback_applied = bool(budget_control.get("resolved_fallback_applied")) if budget_control_active else True
    budget_effective_state = budget_control.get("resolved_effective_state_5") if budget_control_active else None

    stock_sleeve = _component_sleeve_payload(stock_run_meta, "cn_stock_trend_alpha_core")
    etf_sleeve = _component_sleeve_payload(etf_run_meta, "cn_etf_beta")
    stock_daily_actuals = _latest_component_daily_actuals(stock_results_dir, asset_scope="cn_a_equity")
    etf_daily_actuals = _latest_component_daily_actuals(etf_results_dir, asset_scope="cn_etf")
    stock_target = _component_weighted_exposure(stock_weight, stock_governed.get("total_exposure_cap"), stock_weight)
    etf_target = _component_weighted_exposure(etf_weight, etf_governed.get("total_exposure_cap"), etf_weight)
    stock_actual = _component_weighted_exposure(
        stock_weight,
        stock_daily_actuals.get("actual_exposure") if stock_daily_actuals else stock_governed.get("actual_exposure"),
    )
    etf_actual = _component_weighted_exposure(
        etf_weight,
        etf_daily_actuals.get("actual_exposure") if etf_daily_actuals else etf_governed.get("actual_exposure"),
    )
    stock_actual_risk = _component_weighted_exposure(
        stock_weight,
        stock_daily_actuals.get("actual_risk_exposure") if stock_daily_actuals else stock_governed.get("actual_risk_exposure"),
    )
    etf_actual_risk = _component_weighted_exposure(
        etf_weight,
        etf_daily_actuals.get("actual_risk_exposure") if etf_daily_actuals else etf_governed.get("actual_risk_exposure"),
    )
    stock_actual_fallback = _component_weighted_exposure(
        stock_weight,
        stock_daily_actuals.get("actual_fallback_exposure") if stock_daily_actuals else stock_governed.get("actual_fallback_exposure"),
        0.0,
    )
    etf_actual_fallback = _component_weighted_exposure(
        etf_weight,
        etf_daily_actuals.get("actual_fallback_exposure") if etf_daily_actuals else etf_governed.get("actual_fallback_exposure"),
        0.0,
    )
    stock_actual_other = _component_weighted_exposure(
        stock_weight,
        stock_daily_actuals.get("actual_other_exposure") if stock_daily_actuals else stock_governed.get("actual_other_exposure"),
        0.0,
    )
    etf_actual_other = _component_weighted_exposure(
        etf_weight,
        etf_daily_actuals.get("actual_other_exposure") if etf_daily_actuals else etf_governed.get("actual_other_exposure"),
        0.0,
    )
    etf_actual_core = _component_weighted_exposure(etf_weight, etf_daily_actuals.get("actual_core_exposure"), 0.0)
    etf_actual_defense = _component_weighted_exposure(etf_weight, etf_daily_actuals.get("actual_defense_exposure"), 0.0)
    total_risk_budget = _coalesce_numeric(
        [
            _component_weighted_exposure(stock_weight, stock_governed.get("total_risk_budget"), stock_weight),
            _component_weighted_exposure(etf_weight, etf_governed.get("total_risk_budget"), etf_weight),
        ]
    )
    total_exposure_cap = _coalesce_numeric([stock_target, etf_target])
    target_exposure = total_exposure_cap
    actual_exposure = _coalesce_numeric([stock_actual, etf_actual])
    actual_risk_exposure = _coalesce_numeric([stock_actual_risk, etf_actual_risk])
    actual_fallback_exposure = _coalesce_numeric([stock_actual_fallback, etf_actual_fallback])
    actual_other_exposure = _coalesce_numeric([stock_actual_other, etf_actual_other])
    deployability_gap = (
        float(target_exposure) - float(actual_exposure)
        if target_exposure is not None and actual_exposure is not None
        else None
    )
    budget_reason_codes = [
        *_prefixed_reason_codes("STOCK", stock_governed.get("budget_reason_codes")),
        *_prefixed_reason_codes("ETF", etf_governed.get("budget_reason_codes")),
    ]
    sleeve_budgets = {
        "cn_stock_trend_alpha_core": {
            **stock_sleeve,
            "system_role": str(stock_sleeve.get("system_role") or "stock_alpha_sleeve"),
            "budget_source": budget_source,
            "budget_share": stock_weight,
            "target_exposure": stock_target,
            "actual_exposure": stock_actual,
            "actual_risk_exposure": stock_actual_risk,
            "actual_fallback_exposure": stock_actual_fallback,
            "actual_other_exposure": stock_actual_other,
            "phase1_boundary_excludes": list(stock_sleeve.get("phase1_boundary_excludes") or []),
            "local_budget_controls": list(stock_sleeve.get("local_budget_controls") or []),
        },
        "cn_etf_beta": {
            **etf_sleeve,
            "system_role": str(etf_sleeve.get("system_role") or "market_beta_sleeve"),
            "budget_source": budget_source,
            "budget_share": etf_weight,
            "target_exposure": etf_target,
            "actual_exposure": etf_actual,
            "actual_risk_exposure": etf_actual_risk,
            "actual_fallback_exposure": etf_actual_fallback,
            "actual_other_exposure": etf_actual_other,
            "actual_core_exposure": etf_actual_core,
            "actual_defense_exposure": etf_actual_defense,
            "phase1_boundary_excludes": list(etf_sleeve.get("phase1_boundary_excludes") or []),
            "local_budget_controls": list(etf_sleeve.get("local_budget_controls") or []),
        },
    }
    target_selected_count = _coalesce_int(
        [stock_sleeve.get("selected_count"), etf_sleeve.get("selected_count")],
    )
    return sanitize_json(
        {
            "contract_version": "cn_a_governor_budget@1",
            "asset_scope": "cn_a_multi_sleeve",
            "budget_owner": "account_allocator" if budget_control_active else "research_combo_runtime",
            "budget_consumer_sleeve_id": "cn_stock_trend_alpha_core + cn_etf_beta",
            "budget_consumer_system_role": "unified_multi_sleeve_combo",
            "budget_semantics": "account_layer_stock_etf_budget_control" if budget_control_active else "research_combo_only_fixed_weight_mix",
            "research_combo_only": not budget_control_active,
            "regime_source_state": combo_regime.get("base_state"),
            "regime_effective_state": combo_regime.get("effective_state"),
            "budget_effective_state_5": budget_effective_state,
            "budget_source": budget_source,
            "budget_fallback_applied": budget_fallback_applied,
            "coarse_state": combo_regime.get("coarse_state"),
            "effective_coarse_state": combo_regime.get("effective_coarse_state"),
            "regime_reason_codes": list(combo_regime.get("reason_codes") or []),
            "total_risk_budget": total_risk_budget,
            "total_exposure_cap": total_exposure_cap,
            "target_exposure": target_exposure,
            "min_deployable_exposure": None,
            "target_exposure_source": "account_budget_controlled_component_weighted_caps" if budget_control_active else "unified_runtime_component_weighted_caps",
            "min_deployable_exposure_source": None,
            "fallback_allowed": bool(etf_governed.get("fallback_allowed")),
            "under_deploy_reason_codes": _prefixed_reason_codes("ETF", etf_governed.get("under_deploy_reason_codes")),
            "actual_exposure": actual_exposure,
            "actual_risk_exposure": actual_risk_exposure,
            "actual_fallback_exposure": actual_fallback_exposure,
            "actual_other_exposure": actual_other_exposure,
            "deployability_gap": deployability_gap,
            "hard_max_positions": _coalesce_int([stock_governed.get("hard_max_positions"), etf_governed.get("hard_max_positions")]),
            "effective_max_positions": _coalesce_int([stock_governed.get("effective_max_positions"), etf_governed.get("effective_max_positions")]),
            "drawdown": None,
            "drawdown_state": "NORMAL",
            "recovery_state": "INACTIVE",
            "cooldown_state": "INACTIVE",
            "defense_floor": 0.0,
            "defense_floor_state": "INACTIVE",
            "defense_bias": None,
            "manual_override": dict(combo_regime.get("manual_override") or {}),
            "phase1_boundary_excludes": [],
            "local_budget_controls": [],
            "sleeve_budget_mode": "account_budget_controlled_component_weighted" if budget_control_active else "unified_runtime_component_weighted",
            "sleeve_budget_reject_count": 0,
            "budget_reason_codes": budget_reason_codes,
            "sleeve_budgets": sleeve_budgets,
            "raw_sleeve_budget": {
                "slot_caps": {
                    "cn_stock_trend_alpha_core": _safe_int(stock_sleeve.get("slot_cap")) or 0,
                    "cn_etf_beta": _safe_int(etf_sleeve.get("slot_cap")) or 0,
                },
                "available_slots": {
                    "cn_stock_trend_alpha_core": _safe_int(stock_sleeve.get("available_slots")) or 0,
                    "cn_etf_beta": _safe_int(etf_sleeve.get("available_slots")) or 0,
                },
                "positions_after_sell": {
                    "cn_stock_trend_alpha_core": _safe_int(stock_sleeve.get("positions_after_sell")) or 0,
                    "cn_etf_beta": _safe_int(etf_sleeve.get("positions_after_sell")) or 0,
                },
                "candidate_counts": {
                    "cn_stock_trend_alpha_core": _safe_int(stock_sleeve.get("candidate_count")) or 0,
                    "cn_etf_beta": _safe_int(etf_sleeve.get("candidate_count")) or 0,
                },
                "selected_counts": {
                    "cn_stock_trend_alpha_core": _safe_int(stock_sleeve.get("selected_count")) or 0,
                    "cn_etf_beta": _safe_int(etf_sleeve.get("selected_count")) or 0,
                },
            },
            "target_selected_count": target_selected_count,
        }
    )


def _combine_component_csv(
    stock_dir: Path,
    etf_dir: Path,
    *,
    filename: str,
    stock_label: str = "stock_alpha_core",
    etf_label: str = "etf_beta",
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for sleeve_id, component_dir in ((stock_label, stock_dir), (etf_label, etf_dir)):
        frame = _read_csv(component_dir / filename)
        if frame.empty:
            continue
        frame = frame.copy()
        frame["sleeve_id"] = sleeve_id
        frame["component_exp_id"] = component_dir.name
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def _build_combo_daily(
    combo_nav: pd.DataFrame,
    *,
    stock_dir: Path,
    etf_dir: Path,
    combo_governor_snapshot: dict[str, Any],
) -> pd.DataFrame:
    daily_columns = ["date", "nav", "stock_nav", "etf_nav"]
    for col in (
        "stock_weight",
        "etf_weight",
        "account_budget_effective_state_5",
        "account_budget_source",
        "account_budget_fallback_applied",
        "account_state_source",
        "account_transition_kind",
    ):
        if col in combo_nav.columns:
            daily_columns.append(col)
    daily = combo_nav[daily_columns].copy()
    stock_daily = _read_csv(stock_dir / ARTIFACT_FILENAMES["daily"])
    etf_daily = _read_csv(etf_dir / ARTIFACT_FILENAMES["daily"])
    if not stock_daily.empty and "date" in stock_daily.columns:
        stock_daily = stock_daily.copy()
        stock_daily["date"] = stock_daily["date"].astype(str)
        for source_col, target_col in (
            ("gross_exposure", "stock_gross_exposure"),
            ("cash", "stock_cash"),
            ("positions_count", "stock_positions_count"),
        ):
            if source_col in stock_daily.columns:
                daily = daily.merge(stock_daily[["date", source_col]].rename(columns={source_col: target_col}), on="date", how="left")
    if not etf_daily.empty and "date" in etf_daily.columns:
        etf_daily = etf_daily.copy()
        etf_daily["date"] = etf_daily["date"].astype(str)
        for source_col, target_col in (
            ("gross_exposure", "etf_gross_exposure"),
            ("cash", "etf_cash"),
            ("positions_count", "etf_positions_count"),
        ):
            if source_col in etf_daily.columns:
                daily = daily.merge(etf_daily[["date", source_col]].rename(columns={source_col: target_col}), on="date", how="left")
    daily["governor_budget_json"] = json.dumps(combo_governor_snapshot, ensure_ascii=False)
    daily["combo_mode"] = "account_budget_controlled_dynamic_mix" if "account_budget_source" in daily.columns else "daily_rebalanced_equal_weight_50_50"
    daily["research_combo_only"] = bool(combo_governor_snapshot.get("research_combo_only", False))
    return daily


def _build_combo_attribution_audit(
    combo_regime: dict[str, Any],
    combo_governor_snapshot: dict[str, Any],
) -> dict[str, Any]:
    state_reason_counts: dict[str, int] = {}
    for code in list(combo_regime.get("reason_codes") or []):
        text = str(code).strip()
        if text:
            state_reason_counts[text] = state_reason_counts.get(text, 0) + 1
    budget_reason_counts: dict[str, int] = {}
    for code in list(combo_governor_snapshot.get("budget_reason_codes") or []):
        text = str(code).strip()
        if text:
            budget_reason_counts[text] = budget_reason_counts.get(text, 0) + 1
    sleeve_reason_counts: dict[str, int] = {}
    for sleeve_id, payload in dict(combo_governor_snapshot.get("sleeve_budgets") or {}).items():
        for code in list((payload or {}).get("under_deploy_reason_codes") or []):
            text = str(code).strip()
            if text:
                sleeve_reason_counts[f"{sleeve_id}::{text}"] = sleeve_reason_counts.get(f"{sleeve_id}::{text}", 0) + 1
    manual_override_reasons: dict[str, int] = {}
    manual_override = dict(combo_regime.get("manual_override") or {})
    if manual_override.get("active"):
        reason = str(manual_override.get("reason") or "ACTIVE").strip()
        if reason:
            manual_override_reasons[reason] = 1
    etf_budget_roles = dict(combo_governor_snapshot.get("etf_budget_roles") or {})
    etf_budget_roles_target = dict(etf_budget_roles.get("target") or {})
    etf_budget_roles_actual = dict(etf_budget_roles.get("actual") or {})
    etf_budget_roles_deviation = dict(etf_budget_roles.get("deviation") or {})
    return sanitize_json(
        {
            "contract_version": "attribution_audit@1",
            "summary": {
                "state_log_count": 1,
                "budget_log_count": 1,
                "sleeve_log_count": len(dict(combo_governor_snapshot.get("sleeve_budgets") or {})),
                "manual_override_log_count": 1 if manual_override.get("active") else 0,
                "state_transition_count": 0,
                "budget_change_count": 0,
                "reason_code_family_count": int(bool(state_reason_counts)) + int(bool(budget_reason_counts)) + int(bool(sleeve_reason_counts)),
                "latest_state_date": None,
                "latest_budget_date": None,
                "latest_manual_override_date": None,
                "sleeves": list(dict(combo_governor_snapshot.get("sleeve_budgets") or {}).keys()),
            },
            "etf_budget_roles": {
                "contract_version": str(etf_budget_roles.get("contract_version") or "").strip() or None,
                "effective_state_5": str(etf_budget_roles.get("effective_state_5") or "").strip() or None,
                "target": etf_budget_roles_target,
                "actual": etf_budget_roles_actual,
                "deviation": etf_budget_roles_deviation,
            },
            "reason_code_summary": {
                "state_reason_codes": state_reason_counts,
                "budget_reason_codes": budget_reason_counts,
                "sleeve_reason_codes": sleeve_reason_counts,
                "manual_override_reasons": manual_override_reasons,
            },
            "refs": {},
        }
    )


def _compute_combo_perf(nav_frame: pd.DataFrame) -> dict[str, Any]:
    if nav_frame.empty:
        raise RuntimeError("unified combo nav frame is empty")
    nav = pd.to_numeric(nav_frame["nav"], errors="coerce").astype(float)
    ret = pd.to_numeric(nav_frame["combo_ret"], errors="coerce").fillna(0.0).astype(float)
    total_return = float(nav.iloc[-1] - 1.0)
    start = pd.to_datetime(nav_frame["date"].iloc[0], errors="coerce")
    end = pd.to_datetime(nav_frame["date"].iloc[-1], errors="coerce")
    years = None
    if pd.notna(start) and pd.notna(end):
        years = max((end - start).days / 365.25, 1.0 / 365.25)
    cagr = ((float(nav.iloc[-1]) / float(nav.iloc[0])) ** (1.0 / years) - 1.0) if years and float(nav.iloc[0]) > 0 else None
    running_max = nav.cummax()
    drawdown = (nav / running_max) - 1.0
    max_drawdown = float(drawdown.min()) if not drawdown.empty else None
    ret_std = float(ret.std(ddof=0))
    sharpe = None
    if ret_std > 1e-12:
        sharpe = float(ret.mean() / ret_std * math.sqrt(252.0))
    calmar = None
    if cagr is not None and max_drawdown is not None and max_drawdown < 0:
        calmar = float(cagr / abs(max_drawdown))
    return sanitize_json(
        {
            "total_return": total_return,
            "cagr": cagr,
            "max_drawdown": max_drawdown,
            "sharpe": sharpe,
            "calmar": calmar,
            "effective_execution_start_date": str(nav_frame["date"].iloc[0]),
            "effective_signal_start_date": str(nav_frame["date"].iloc[0]),
            "analysis_mode": "cn_stock_etf_unified_runtime_phase1",
        }
    )


def _read_component_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    results_dir = Path(str(result.get("results_dir") or "")).resolve()
    return {
        "exp_id": str(result.get("exp_id") or ""),
        "results_dir": str(results_dir),
        "perf": _read_json(results_dir / "perf.json"),
        "run_meta": _read_json(results_dir / "run_meta.json"),
        "run_profile": _read_json(results_dir / "run_profile.json"),
        "audit": _read_json(results_dir / "audit.json"),
    }


def _summarize_runtime_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(profile, dict):
        return {}
    stage_seconds = profile.get("stage_seconds") if isinstance(profile.get("stage_seconds"), dict) else {}
    perf = profile.get("perf") if isinstance(profile.get("perf"), dict) else {}
    return sanitize_json(
        {
            "total_wall_seconds": profile.get("total_wall_seconds"),
            "stage_seconds": {str(k): float(v or 0.0) for k, v in stage_seconds.items()},
            "bottleneck_stage": profile.get("bottleneck_stage"),
            "bottleneck_label": profile.get("bottleneck_label"),
            "symbols_count": profile.get("symbols_count"),
            "trading_days": profile.get("trading_days"),
            "perf": perf,
        }
    )


def _build_sleeve_summary(component: dict[str, Any], *, sleeve_id: str, asset_scope: str) -> dict[str, Any]:
    run_meta = component.get("run_meta") if isinstance(component.get("run_meta"), dict) else {}
    perf = component.get("perf") if isinstance(component.get("perf"), dict) else {}
    regime = run_meta.get("regime") if isinstance(run_meta.get("regime"), dict) else {}
    latest_state = regime.get("latest_state") if isinstance(regime.get("latest_state"), dict) else {}
    return sanitize_json(
        {
            "exp_id": component.get("exp_id"),
            "results_dir": component.get("results_dir"),
            "asset_scope": asset_scope,
            "sleeve_id": sleeve_id,
            "perf": {
                "total_return": perf.get("total_return"),
                "cagr": perf.get("cagr"),
                "max_drawdown": perf.get("max_drawdown"),
                "sharpe": perf.get("sharpe"),
                "trades": perf.get("trades"),
                "turnover": perf.get("turnover"),
            },
            "regime": {
                "latest_state": latest_state,
            },
            "governed_snapshot": dict(run_meta.get("governed_snapshot") or {}),
            "counters": dict(run_meta.get("counters") or {}),
        }
    )


def _build_combo_dependencies(
    *,
    stock_component: dict[str, Any],
    etf_component: dict[str, Any],
) -> dict[str, Any]:
    return sanitize_json(
        {
            "component_runs": {
                "stock_alpha_core": {
                    "exp_id": stock_component.get("exp_id"),
                    "results_dir": stock_component.get("results_dir"),
                    "asset_scope": "cn_a_equity",
                    "sleeve_id": "cn_stock_trend_alpha_core",
                },
                "etf_beta": {
                    "exp_id": etf_component.get("exp_id"),
                    "results_dir": etf_component.get("results_dir"),
                    "asset_scope": "cn_etf",
                    "sleeve_id": "cn_etf_beta",
                },
            }
        }
    )


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(sanitize_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_unified_runtime_component_inputs(
    *,
    unified_runtime: dict[str, Any],
    combo_context: dict[str, Any],
) -> dict[str, Any]:
    component_source_contract = (
        dict(combo_context.get("component_source_contract") or {})
        if isinstance(combo_context.get("component_source_contract"), dict)
        else {}
    )
    contract_components = (
        dict(component_source_contract.get("components") or {})
        if isinstance(component_source_contract.get("components"), dict)
        else {}
    )
    execution_contract = (
        dict(combo_context.get("execution_contract") or {})
        if isinstance(combo_context.get("execution_contract"), dict)
        else (
            dict(unified_runtime.get("execution_contract") or {})
            if isinstance(unified_runtime.get("execution_contract"), dict)
            else {}
        )
    )
    execution_components = (
        dict(execution_contract.get("components") or {})
        if isinstance(execution_contract.get("components"), dict)
        else {}
    )

    def _resolve_component_compile_input(component_key: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        contract_entry = (
            contract_components.get(component_key)
            if isinstance(contract_components.get(component_key), dict)
            else {}
        )
        compile_input = (
            contract_entry.get("compile_input")
            if isinstance(contract_entry.get("compile_input"), dict)
            else {}
        )
        semantic_cfg = (
            compile_input.get("semantic_config")
            if isinstance(compile_input.get("semantic_config"), dict)
            else None
        )
        runtime_cfg = (
            compile_input.get("runtime_config")
            if isinstance(compile_input.get("runtime_config"), dict)
            else None
        )
        return (
            dict(semantic_cfg) if isinstance(semantic_cfg, dict) else None,
            dict(runtime_cfg) if isinstance(runtime_cfg, dict) else None,
        )

    def _resolve_component_execution_entry(
        component_key: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Any], str | None, float | None]:
        component_entry = (
            execution_components.get(component_key)
            if isinstance(execution_components.get(component_key), dict)
            else {}
        )
        runtime_cfg = (
            component_entry.get("runtime_config")
            if isinstance(component_entry.get("runtime_config"), dict)
            else None
        )
        execution_overrides = (
            component_entry.get("execution_overrides")
            if isinstance(component_entry.get("execution_overrides"), dict)
            else {}
        )
        asset_scope = str(component_entry.get("asset_scope") or "").strip() or None
        try:
            weight = float(component_entry.get("weight"))
        except (TypeError, ValueError):
            weight = None
        return (
            dict(runtime_cfg) if isinstance(runtime_cfg, dict) else None,
            dict(execution_overrides) if isinstance(execution_overrides, dict) else {},
            asset_scope,
            weight,
        )

    stock_semantic_cfg, stock_runtime_cfg_fallback = _resolve_component_compile_input("stock_component")
    etf_semantic_cfg, etf_runtime_cfg_fallback = _resolve_component_compile_input("etf_component")
    (
        stock_runtime_cfg,
        stock_execution_overrides,
        stock_asset_scope_from_execution,
        stock_weight_from_execution,
    ) = _resolve_component_execution_entry("stock_component")
    (
        etf_runtime_cfg,
        etf_execution_overrides,
        etf_asset_scope_from_execution,
        etf_weight_from_execution,
    ) = _resolve_component_execution_entry("etf_component")

    if not isinstance(stock_runtime_cfg, dict):
        stock_runtime_cfg = stock_runtime_cfg_fallback
    if not isinstance(etf_runtime_cfg, dict):
        etf_runtime_cfg = etf_runtime_cfg_fallback
    if not isinstance(stock_runtime_cfg, dict) and not isinstance(stock_semantic_cfg, dict):
        raise RuntimeError("unified runtime payload missing stock sleeve execution inputs")
    if not isinstance(etf_runtime_cfg, dict) and not isinstance(etf_semantic_cfg, dict):
        raise RuntimeError("unified runtime payload missing ETF sleeve execution inputs")

    stock_asset_scope = str(
        stock_asset_scope_from_execution
        or ((contract_components.get("stock_component") or {}).get("asset_scope") if isinstance(contract_components.get("stock_component"), dict) else "")
        or "cn_a_equity"
    ).strip() or "cn_a_equity"
    etf_asset_scope = str(
        etf_asset_scope_from_execution
        or ((contract_components.get("etf_component") or {}).get("asset_scope") if isinstance(contract_components.get("etf_component"), dict) else "")
        or "cn_etf"
    ).strip() or "cn_etf"
    return {
        "component_source_contract": component_source_contract,
        "contract_components": contract_components,
        "execution_contract": execution_contract,
        "stock_semantic_cfg": dict(stock_semantic_cfg) if isinstance(stock_semantic_cfg, dict) else None,
        "etf_semantic_cfg": dict(etf_semantic_cfg) if isinstance(etf_semantic_cfg, dict) else None,
        "stock_runtime_cfg": dict(stock_runtime_cfg) if isinstance(stock_runtime_cfg, dict) else None,
        "etf_runtime_cfg": dict(etf_runtime_cfg) if isinstance(etf_runtime_cfg, dict) else None,
        "stock_execution_overrides": dict(stock_execution_overrides) if isinstance(stock_execution_overrides, dict) else {},
        "etf_execution_overrides": dict(etf_execution_overrides) if isinstance(etf_execution_overrides, dict) else {},
        "stock_asset_scope": stock_asset_scope,
        "etf_asset_scope": etf_asset_scope,
        "stock_weight_from_execution": stock_weight_from_execution,
        "etf_weight_from_execution": etf_weight_from_execution,
    }


def _derive_component_execution_overrides_from_runtime(runtime_cfg: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(runtime_cfg, dict):
        return {}
    strategy = runtime_cfg.get("strategy") if isinstance(runtime_cfg.get("strategy"), dict) else {}
    params = strategy.get("params") if isinstance(strategy.get("params"), dict) else {}
    overrides: dict[str, Any] = {}
    ranking_mode = str(params.get("ranking_mode") or "").strip().lower()
    if ranking_mode and ranking_mode not in {"none", "off", "disabled"}:
        overrides["enable_multifactor_rank"] = True
    elif bool(params.get("enable_residual_ranking")):
        overrides["enable_multifactor_rank"] = True
    if params.get("momentum_top_pct") is not None:
        try:
            overrides["momentum_top_pct"] = float(params.get("momentum_top_pct"))
        except Exception:
            pass
    for key in ("enable_strength_rank", "strength_ma", "strength_top_k_mode", "mf_topk"):
        if runtime_cfg.get(key) is not None:
            overrides[key] = runtime_cfg.get(key)
    return sanitize_json(overrides)


def _component_execution_overrides_for_request(
    *,
    explicit_overrides: dict[str, Any] | None,
    runtime_cfg: dict[str, Any] | None,
    allow_rank_derivation: bool = True,
) -> dict[str, Any]:
    if isinstance(explicit_overrides, dict) and explicit_overrides:
        return sanitize_json(dict(explicit_overrides))
    if not allow_rank_derivation:
        return {}
    return _derive_component_execution_overrides_from_runtime(runtime_cfg)


def _component_benchmark_from_inputs(
    *,
    runtime_cfg: dict[str, Any] | None,
    semantic_cfg: dict[str, Any] | None,
) -> str:
    for cfg in (runtime_cfg, semantic_cfg):
        universe = cfg.get("universe") if isinstance(cfg, dict) and isinstance(cfg.get("universe"), dict) else {}
        benchmark = str(universe.get("benchmark") or "").strip()
        if benchmark:
            return benchmark
    return ""


def _runtime_config_with_component_benchmark(runtime_cfg: dict[str, Any], benchmark: str) -> dict[str, Any]:
    payload = sanitize_json(dict(runtime_cfg or {}))
    if not isinstance(payload, dict):
        return {}
    benchmark_text = str(benchmark or "").strip()
    if not benchmark_text:
        return payload
    universe = payload.get("universe") if isinstance(payload.get("universe"), dict) else {}
    payload["universe"] = {**dict(universe), "benchmark": benchmark_text}
    return payload


def _apply_execution_overrides_to_child_payload(
    payload: dict[str, Any],
    execution_overrides: dict[str, Any] | None,
) -> None:
    if not isinstance(execution_overrides, dict):
        return
    supported = {
        "max_positions",
        "enable_strength_rank",
        "strength_ma",
        "strength_top_k_mode",
        "enable_multifactor_rank",
        "mf_topk",
        "mf_concentrate_topn",
        "mf_concentrate_scale",
        "mf_rank_gate_mode",
        "momentum_top_pct",
    }
    for key in supported:
        if key in execution_overrides and execution_overrides.get(key) is not None:
            payload[key] = execution_overrides.get(key)


def _ensure_unified_contract_component_overrides(
    execution_contract: dict[str, Any],
    *,
    stock_execution_overrides: dict[str, Any],
    etf_execution_overrides: dict[str, Any],
) -> dict[str, Any]:
    payload = sanitize_json(dict(execution_contract or {}))
    components = payload.get("components") if isinstance(payload.get("components"), dict) else {}
    if not components:
        return payload
    payload["components"] = dict(components)
    for component_key, overrides in (
        ("stock_component", stock_execution_overrides),
        ("etf_component", etf_execution_overrides),
    ):
        component = payload["components"].get(component_key)
        if not isinstance(component, dict):
            continue
        if isinstance(component.get("execution_overrides"), dict) and component.get("execution_overrides"):
            continue
        payload["components"][component_key] = {
            **dict(component),
            "execution_overrides": sanitize_json(dict(overrides or {})),
        }
    return sanitize_json(payload)


def run_cn_stock_etf_unified_runtime(
    *,
    bt_root: Path,
    body: Any,
    base_cfg: dict[str, Any],
    semantic_compile: dict[str, Any],
    requested_preset: str,
    resolved_config_id: str,
    resolved_config_hash: str,
    resolved_config_meta: dict[str, Any] | None,
    conflict_policy: str,
    run_request_body: Callable[[Any, Callable[[int, str], None] | None], dict[str, Any]],
    request_model: type,
    progress_hook: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    runtime_t0 = time.perf_counter()
    runtime_stage_t0 = runtime_t0
    runtime_stage_seconds: dict[str, float] = {}

    def _finish_runtime_stage(name: str) -> None:
        nonlocal runtime_stage_t0
        now = time.perf_counter()
        runtime_stage_seconds[str(name)] = float(runtime_stage_seconds.get(str(name), 0.0)) + float(now - runtime_stage_t0)
        runtime_stage_t0 = now

    unified_runtime = semantic_compile.get("unified_runtime") if isinstance(semantic_compile.get("unified_runtime"), dict) else {}
    combo_context = dict(unified_runtime.get("combo_context") or {})
    account_budget_control = _normalize_account_budget_control(
        dict(unified_runtime.get("account_budget_control") or {})
        if isinstance(unified_runtime.get("account_budget_control"), dict)
        else {},
        unified_runtime=unified_runtime,
    )
    resolved_components = _resolve_unified_runtime_component_inputs(
        unified_runtime=unified_runtime,
        combo_context=combo_context,
    )
    component_source_contract = dict(resolved_components.get("component_source_contract") or {})
    execution_contract = dict(resolved_components.get("execution_contract") or {})
    stock_semantic_cfg = resolved_components.get("stock_semantic_cfg")
    etf_semantic_cfg = resolved_components.get("etf_semantic_cfg")
    stock_runtime_cfg = resolved_components.get("stock_runtime_cfg")
    etf_runtime_cfg = resolved_components.get("etf_runtime_cfg")
    stock_execution_overrides = _component_execution_overrides_for_request(
        explicit_overrides=resolved_components.get("stock_execution_overrides")
        if isinstance(resolved_components.get("stock_execution_overrides"), dict)
        else {},
        runtime_cfg=stock_runtime_cfg if isinstance(stock_runtime_cfg, dict) else None,
        allow_rank_derivation=True,
    )
    etf_execution_overrides = _component_execution_overrides_for_request(
        explicit_overrides=resolved_components.get("etf_execution_overrides")
        if isinstance(resolved_components.get("etf_execution_overrides"), dict)
        else {},
        runtime_cfg=etf_runtime_cfg if isinstance(etf_runtime_cfg, dict) else None,
        allow_rank_derivation=False,
    )
    stock_asset_scope = str(resolved_components.get("stock_asset_scope") or "cn_a_equity").strip() or "cn_a_equity"
    etf_asset_scope = str(resolved_components.get("etf_asset_scope") or "cn_etf").strip() or "cn_etf"
    stock_weight_from_execution = resolved_components.get("stock_weight_from_execution")
    etf_weight_from_execution = resolved_components.get("etf_weight_from_execution")
    if isinstance(etf_semantic_cfg, dict):
        etf_semantic_cfg = _inject_etf_shared_transition_execution_policy(
            etf_semantic_cfg,
            account_budget_control=account_budget_control,
        )
    if isinstance(etf_runtime_cfg, dict):
        etf_runtime_cfg = _inject_etf_shared_transition_execution_policy(
            etf_runtime_cfg,
            account_budget_control=account_budget_control,
        )
    stock_price_adj = str(
        (
            ((stock_runtime_cfg or {}).get("universe") if isinstance((stock_runtime_cfg or {}).get("universe"), dict) else {})
            or ((stock_semantic_cfg or {}).get("universe") if isinstance((stock_semantic_cfg or {}).get("universe"), dict) else {})
        ).get("price_adj")
        or ""
    ).strip()
    etf_price_adj = str(
        (
            ((etf_runtime_cfg or {}).get("universe") if isinstance((etf_runtime_cfg or {}).get("universe"), dict) else {})
            or ((etf_semantic_cfg or {}).get("universe") if isinstance((etf_semantic_cfg or {}).get("universe"), dict) else {})
        ).get("price_adj")
        or ""
    ).strip()

    _emit_progress(progress_hook, 5, "开始运行个股 alpha sleeve")
    stock_body_payload = {
        "preset": requested_preset or "single",
        "asset_scope": stock_asset_scope,
        "workbench_mode": getattr(body, "workbench_mode", None),
        "fast_mode": getattr(body, "fast_mode", None),
    }
    if stock_price_adj:
        stock_body_payload["price_adj"] = stock_price_adj
    stock_benchmark = _component_benchmark_from_inputs(
        runtime_cfg=stock_runtime_cfg if isinstance(stock_runtime_cfg, dict) else None,
        semantic_cfg=stock_semantic_cfg if isinstance(stock_semantic_cfg, dict) else None,
    )
    if stock_benchmark:
        stock_body_payload["benchmark"] = stock_benchmark
    if isinstance(stock_runtime_cfg, dict) and stock_runtime_cfg:
        stock_body_payload["runtime_config_json"] = _runtime_config_with_component_benchmark(
            stock_runtime_cfg,
            stock_benchmark,
        )
    else:
        stock_body_payload["config_json"] = stock_semantic_cfg
    _apply_execution_overrides_to_child_payload(stock_body_payload, stock_execution_overrides)
    stock_body = request_model(**stock_body_payload)
    stock_result = run_request_body(
        stock_body,
        _child_progress(progress_hook, start=5, end=45, prefix="个股 sleeve"),
    )

    _finish_runtime_stage("stock_component_run")
    _emit_progress(progress_hook, 46, "开始运行 ETF beta sleeve")
    etf_body_payload = {
        "preset": requested_preset or "single",
        "asset_scope": etf_asset_scope,
        "workbench_mode": getattr(body, "workbench_mode", None),
        "fast_mode": getattr(body, "fast_mode", None),
    }
    if etf_price_adj:
        etf_body_payload["price_adj"] = etf_price_adj
    etf_benchmark = _component_benchmark_from_inputs(
        runtime_cfg=etf_runtime_cfg if isinstance(etf_runtime_cfg, dict) else None,
        semantic_cfg=etf_semantic_cfg if isinstance(etf_semantic_cfg, dict) else None,
    )
    if etf_benchmark:
        etf_body_payload["benchmark"] = etf_benchmark
    if isinstance(etf_runtime_cfg, dict) and etf_runtime_cfg:
        etf_body_payload["runtime_config_json"] = _runtime_config_with_component_benchmark(
            etf_runtime_cfg,
            etf_benchmark,
        )
    else:
        etf_body_payload["config_json"] = etf_semantic_cfg
    _apply_execution_overrides_to_child_payload(etf_body_payload, etf_execution_overrides)
    etf_body = request_model(**etf_body_payload)
    etf_result = run_request_body(
        etf_body,
        _child_progress(progress_hook, start=46, end=86, prefix="ETF sleeve"),
    )

    _finish_runtime_stage("etf_component_run")
    stock_component = _read_component_snapshot(stock_result)
    etf_component = _read_component_snapshot(etf_result)
    stock_dir = Path(str(stock_component.get("results_dir") or "")).resolve()
    etf_dir = Path(str(etf_component.get("results_dir") or "")).resolve()
    daily_budget_frame, latest_account_state_resolution, latest_state_transition_runtime = _build_account_budget_daily_frame(
        stock_dir,
        etf_dir,
        account_budget_control=account_budget_control,
    )
    combo_nav = _build_combo_nav(stock_dir, etf_dir, daily_budget_frame=daily_budget_frame)
    combo_perf = _compute_combo_perf(combo_nav)
    exp_id, results_dir = _allocate_combo_results_dir(bt_root)
    combo_weights = {
        "cn_stock_trend_alpha_core": 0.5 if stock_weight_from_execution is None else float(stock_weight_from_execution),
        "cn_etf_beta": 0.5 if etf_weight_from_execution is None else float(etf_weight_from_execution),
    }
    combo_budget_source = "account_allocator_runtime_reference_50_50"
    combo_budget_fallback_applied = True
    combo_budget_effective_state = None
    combo_budget_state_source = "account_layer_state_machine"
    combo_transition_kind = None
    if not daily_budget_frame.empty:
        latest_budget = daily_budget_frame.iloc[-1].to_dict()
        stock_weight = latest_budget.get("stock_weight")
        etf_weight = latest_budget.get("etf_weight")
        combo_weights = {
            "cn_stock_trend_alpha_core": float(0.5 if stock_weight is None else stock_weight),
            "cn_etf_beta": float(0.5 if etf_weight is None else etf_weight),
        }
        combo_budget_source = str(latest_budget.get("account_budget_source") or combo_budget_source)
        combo_budget_fallback_applied = bool(latest_budget.get("account_budget_fallback_applied"))
        combo_budget_effective_state = latest_budget.get("account_budget_effective_state_5")
        combo_budget_state_source = str(latest_budget.get("account_state_source") or combo_budget_state_source)
        combo_transition_kind = str(latest_budget.get("account_transition_kind") or "") or None
    else:
        combo_weights = dict((account_budget_control.get("fallback_weights") or unified_runtime.get("weights") or combo_weights))
    if not execution_contract:
        execution_contract = build_unified_combo_execution_contract(
            combo_mode="account_budget_controlled_dynamic_mix",
            benchmark="CN_STOCK_ETF_50_50",
            weights=combo_weights,
            stock_runtime_config=stock_runtime_cfg,
            etf_runtime_config=etf_runtime_cfg,
            stock_execution_overrides=stock_execution_overrides,
            etf_execution_overrides=etf_execution_overrides,
            account_budget_control=account_budget_control,
        )
    execution_contract = _ensure_unified_contract_component_overrides(
        dict(execution_contract or {}),
        stock_execution_overrides=stock_execution_overrides,
        etf_execution_overrides=etf_execution_overrides,
    )
    unified_runtime["execution_contract"] = execution_contract
    account_budget_control = sanitize_json(
        {
            **account_budget_control,
            "resolved_weights": combo_weights,
            "resolved_source": combo_budget_source,
            "resolved_fallback_applied": combo_budget_fallback_applied,
            "resolved_effective_state_5": combo_budget_effective_state,
            "resolved_state_source": combo_budget_state_source,
            "resolved_transition_kind": combo_transition_kind,
        }
    )
    combo_regime = _build_combo_regime(
        stock_component.get("run_meta") if isinstance(stock_component.get("run_meta"), dict) else {},
        etf_component.get("run_meta") if isinstance(etf_component.get("run_meta"), dict) else {},
    )
    etf_run_meta = etf_component.get("run_meta") if isinstance(etf_component.get("run_meta"), dict) else {}
    combo_governed_snapshot = _build_combo_governed_snapshot(
        stock_run_meta=stock_component.get("run_meta") if isinstance(stock_component.get("run_meta"), dict) else {},
        etf_run_meta=etf_run_meta,
        weights=combo_weights,
        combo_regime=combo_regime,
        account_budget_control=account_budget_control,
        stock_results_dir=stock_dir,
        etf_results_dir=etf_dir,
    )
    account_budget_runtime_reference = build_account_budget_runtime_reference(
        combo_regime=combo_regime,
        combo_governed_snapshot=combo_governed_snapshot,
        account_state_resolution=latest_account_state_resolution,
        state_transition_runtime=latest_state_transition_runtime,
    )
    account_allocator_runtime = build_account_allocator_runtime(
        account_budget_control=account_budget_control,
        account_budget_runtime_reference=account_budget_runtime_reference,
        riskoff_budget_execution_materialization=_build_riskoff_budget_execution_materialization(
            account_budget_runtime_reference=account_budget_runtime_reference,
            etf_run_meta=etf_run_meta,
        ),
        combo_reference={
            "benchmark": "CN_STOCK_ETF_50_50",
            "combo_mode": "account_budget_controlled_dynamic_mix",
            "weights": combo_weights,
        },
    )
    etf_formal_view = (
        dict(((etf_run_meta.get("etf_beta") or {}).get("formal_view") or {}))
        if isinstance((etf_run_meta.get("etf_beta") or {}), dict)
        else {}
    )
    transition_execution_reference = sanitize_json(
        {
            "source": "etf_formal_view_diagnostics",
            "account_transition_execution": dict(etf_formal_view.get("account_transition_execution") or {}),
            "account_transition_handoff_consumption": dict(
                etf_formal_view.get("account_transition_handoff_consumption") or {}
            ),
        }
    )
    account_allocator_runtime = sanitize_json(
        {
            **account_allocator_runtime,
            "transition_execution_reference": transition_execution_reference,
        }
    )
    etf_budget_roles = dict(account_budget_runtime_reference.get("etf_budget_roles") or {})
    combo_governed_snapshot = sanitize_json(
        {
            **combo_governed_snapshot,
            "etf_budget_roles": etf_budget_roles,
        }
    )
    combo_attribution = _build_combo_attribution_audit(combo_regime, combo_governed_snapshot)
    combo_daily = _build_combo_daily(
        combo_nav,
        stock_dir=stock_dir,
        etf_dir=etf_dir,
        combo_governor_snapshot=combo_governed_snapshot,
    )
    combo_trades = _combine_component_csv(stock_dir, etf_dir, filename=ARTIFACT_FILENAMES["trades"])
    combo_orders = _combine_component_csv(stock_dir, etf_dir, filename=ARTIFACT_FILENAMES["orders"])
    combo_reason_codes = _combine_component_csv(stock_dir, etf_dir, filename=ARTIFACT_FILENAMES["reason_codes"])
    combo_symbol_performance = _combine_component_csv(stock_dir, etf_dir, filename=ARTIFACT_FILENAMES["symbol_performance"])
    combined_counters = sanitize_json(
        {
            "orders": _coalesce_int(
                [
                    ((stock_component.get("run_meta") or {}).get("counters") or {}).get("orders"),
                    ((etf_component.get("run_meta") or {}).get("counters") or {}).get("orders"),
                ]
            )
            or 0,
            "closed_trades": _coalesce_int(
                [
                    ((stock_component.get("run_meta") or {}).get("counters") or {}).get("closed_trades"),
                    ((etf_component.get("run_meta") or {}).get("counters") or {}).get("closed_trades"),
                ]
            )
            or 0,
            "buy_orders_count": int((combo_orders["side"].astype(str).str.upper() == "BUY").sum()) if not combo_orders.empty and "side" in combo_orders.columns else 0,
            "sell_orders_count": int((combo_orders["side"].astype(str).str.upper() == "SELL").sum()) if not combo_orders.empty and "side" in combo_orders.columns else 0,
        }
    )
    combo_dependencies = _build_combo_dependencies(
        stock_component=stock_component,
        etf_component=etf_component,
    )
    combo_stage_pipeline = sanitize_json(
        {
            "schema_version": "stage_pipeline_summary@1",
            "route_id": "cn_stock_etf_unified_runtime_entry",
            "execution_shell": "unified_combo_phase1",
            "daily_loop_mode": "unified_combo_phase1",
            "trading_days": int(len(combo_nav.index)),
            "enabled_stages": ["stock_alpha_core", "etf_beta", "combo_assembly"],
        }
    )
    combo_stage_summary = sanitize_json(
        {
            "schema_version": "stage_pipeline_summary@1",
            "route_id": "cn_stock_etf_unified_runtime_entry",
            "execution_shell": "unified_combo_phase1",
            "daily_loop_mode": "unified_combo_phase1",
            "trading_days": int(len(combo_nav.index)),
        }
    )
    combo_regime_audit_summary = sanitize_json(
        {
            "contract_version": "regime_audit_summary@1",
            "summary": {
                "base_state_5": combo_regime.get("base_state"),
                "effective_state_5": combo_regime.get("effective_state"),
                "coarse_state": combo_regime.get("coarse_state"),
                "effective_coarse_state": combo_regime.get("effective_coarse_state"),
                "confidence": combo_regime.get("confidence"),
                "reason_codes": list(combo_regime.get("reason_codes") or []),
                "manual_override_active": bool((combo_regime.get("manual_override") or {}).get("active")),
            },
        }
    )

    _finish_runtime_stage("combo_assembly")
    _emit_progress(progress_hook, 90, "写入统一组合产物")
    combo_nav.to_csv(results_dir / ARTIFACT_FILENAMES["nav"], index=False)
    combo_daily.to_csv(results_dir / ARTIFACT_FILENAMES["daily"], index=False)
    _write_json(results_dir / ARTIFACT_FILENAMES["perf"], combo_perf)
    _write_json(results_dir / ARTIFACT_FILENAMES["regime_audit_summary"], combo_regime_audit_summary)
    _write_json(results_dir / ARTIFACT_FILENAMES["attribution_audit"], combo_attribution)
    _write_json(results_dir / ARTIFACT_FILENAMES["stage_summary"], combo_stage_summary)
    if not combo_trades.empty:
        combo_trades.to_csv(results_dir / ARTIFACT_FILENAMES["trades"], index=False)
    if not combo_orders.empty:
        combo_orders.to_csv(results_dir / ARTIFACT_FILENAMES["orders"], index=False)
    if not combo_reason_codes.empty:
        combo_reason_codes.to_csv(results_dir / ARTIFACT_FILENAMES["reason_codes"], index=False)
    if not combo_symbol_performance.empty:
        combo_symbol_performance.to_csv(results_dir / ARTIFACT_FILENAMES["symbol_performance"], index=False)
    execution_contract_path = write_execution_contract_snapshot(
        results_dir=results_dir,
        execution_contract=execution_contract,
        filename=ARTIFACT_FILENAMES["execution_contract"],
    )
    execution_contract_rel = (
        str(execution_contract_path.name)
        if isinstance(execution_contract_path, Path) and execution_contract_path.exists()
        else None
    )
    execution_contract_ref = build_execution_contract_ref(
        execution_contract=execution_contract,
        artifact_rel=execution_contract_rel,
    )
    _finish_runtime_stage("combo_artifact_write")
    bottleneck_stage = ""
    bottleneck_seconds = 0.0
    if runtime_stage_seconds:
        bottleneck_stage, bottleneck_seconds = max(
            runtime_stage_seconds.items(),
            key=lambda item: float(item[1] or 0.0),
        )
    total_wall_seconds = float(time.perf_counter() - runtime_t0)
    row_count = int(len(combo_daily.index) + len(combo_trades.index) + len(combo_orders.index))
    combo_runtime_profile = sanitize_json(
        {
            "preset": requested_preset or "single",
            "created_at_utc": datetime.utcnow().isoformat() + "Z",
            "results_dir": str(results_dir),
            "stage_seconds": {str(k): float(v or 0.0) for k, v in runtime_stage_seconds.items()},
            "total_wall_seconds": total_wall_seconds,
            "symbols_count": int(len(combo_weights)),
            "trading_days": int(len(combo_nav.index)),
            "row_count": row_count,
            "rows_per_second": float(row_count / max(total_wall_seconds, 1e-9)),
            "bottleneck_stage": bottleneck_stage,
            "bottleneck_stage_seconds": float(bottleneck_seconds),
            "bottleneck_label": (
                "BOTTLENECK_COMPONENT_RUN"
                if str(bottleneck_stage).endswith("_component_run")
                else "BOTTLENECK_COMBO_ASSEMBLY"
            ),
            "component_profiles": {
                "stock_alpha_core": _summarize_runtime_profile(
                    stock_component.get("run_profile") if isinstance(stock_component.get("run_profile"), dict) else None
                ),
                "etf_beta": _summarize_runtime_profile(
                    etf_component.get("run_profile") if isinstance(etf_component.get("run_profile"), dict) else None
                ),
            },
        }
    )
    _write_json(results_dir / "run_profile.json", combo_runtime_profile)

    combo_run_meta = sanitize_json(
        {
            "exp_id": exp_id,
            "status": "OK",
            "data": {
                "asset_scope": "cn_a_equity",
                "system_asset_scope": "cn_a_multi_sleeve",
                "asset_role": "unified_multi_sleeve_combo",
                "benchmark": "CN_STOCK_ETF_50_50",
                "coverage_start": str(combo_nav["date"].iloc[0]),
                "coverage_end": str(combo_nav["date"].iloc[-1]),
            },
            "asset_context": build_asset_context("cn_a_equity"),
            "execution_contract_ref": execution_contract_ref,
            "provenance": {
                "config_source": "config_json",
                "resolved_config_mode": "semantic_config_run",
                "resolved_config_id": resolved_config_id or None,
                "resolved_config_hash": resolved_config_hash or None,
                "resolved_config_meta": resolved_config_meta,
                "component_source_contract": component_source_contract,
            },
            "dependencies": combo_dependencies,
            "runtime_truth_source": "account_allocator",
            "run_profile": _summarize_runtime_profile(combo_runtime_profile),
            "stage_pipeline": combo_stage_pipeline,
            "account_allocator_runtime": account_allocator_runtime,
            "combo_runtime": {
                "contract_version": "cn_stock_etf_unified_runtime_reference@1",
                "mode": "account_budget_controlled_dynamic_mix",
                "weights": combo_weights,
                "runtime_truth_source": "account_allocator",
                "account_budget_control": account_budget_control,
                "etf_budget_roles": etf_budget_roles,
                "benchmark": "CN_STOCK_ETF_50_50",
            },
            "execution_contract": execution_contract,
            "account_budget_runtime_reference": account_budget_runtime_reference,
            "account_budget_control": account_budget_control,
            "etf_budget_roles": etf_budget_roles,
            "combo_metrics": {
                "start": str(combo_nav["date"].iloc[0]),
                "end": str(combo_nav["date"].iloc[-1]),
                "days": int(len(combo_nav.index)),
                "total_return": combo_perf.get("total_return"),
                "cagr": combo_perf.get("cagr"),
                "max_drawdown": combo_perf.get("max_drawdown"),
                "sharpe": combo_perf.get("sharpe"),
                "calmar": combo_perf.get("calmar"),
            },
            "governed_a_share": (
                ((semantic_compile.get("resolved_config") or {}).get("config_json") or {}).get("governed_a_share")
                if isinstance((semantic_compile.get("resolved_config") or {}).get("config_json"), dict)
                else {}
            ),
            "regime": {
                "latest_state": combo_regime,
            },
            "governed_snapshot": combo_governed_snapshot,
            "attribution": combo_attribution,
            "counters": combined_counters,
            "sleeves": {
                "stock_alpha_core": _build_sleeve_summary(stock_component, sleeve_id="cn_stock_trend_alpha_core", asset_scope="cn_a_equity"),
                "etf_beta": _build_sleeve_summary(etf_component, sleeve_id="cn_etf_beta", asset_scope="cn_etf"),
            },
        }
    )
    _write_json(results_dir / ARTIFACT_FILENAMES["run_meta"], combo_run_meta)
    _write_json(
        results_dir / "audit.json",
        {
            "status": "PASS",
            "unified_runtime": {
                "status": "PASS",
                "message": "Unified runtime phase1 executed stock alpha and ETF beta as component experiments and assembled an official combo artifact.",
            },
            "research_combo": {
                "status": "PASS",
                "message": "Unified combo artifact derived from stock and ETF component experiments.",
                "research_combo_only": False,
            },
            "components": {
                "stock_alpha_core": {"exp_id": stock_component.get("exp_id"), "status": "PASS"},
                "etf_beta": {"exp_id": etf_component.get("exp_id"), "status": "PASS"},
            },
        },
    )

    combo_run_config = sanitize_json(
        {
            "asset_scope": "cn_a_equity",
            "asset_context": build_asset_context("cn_a_equity"),
            "unified_runtime": unified_runtime,
        }
    )
    _write_json(results_dir / "run_config.json", combo_run_config)
    _write_json(
        results_dir / "config.json",
        {
            "workbench_config": semantic_compile.get("input_config"),
            "resolved_config": semantic_compile.get("resolved_config"),
            "compiled_plan": semantic_compile.get("compiled_plan"),
            "overrides": {
                "config_source": "config_json",
                "resolved_config_mode": "semantic_config_run",
                "resolved_config_id": resolved_config_id or None,
                "resolved_config_hash": resolved_config_hash or None,
                "resolved_config_meta": resolved_config_meta,
                "config_conflict_policy": conflict_policy,
                "original_workbench_config": semantic_compile.get("input_config"),
                "workbench_config": combo_run_config,
            },
            "component_experiments": {
                "stock_alpha_core": stock_component,
                "etf_beta": etf_component,
            },
        },
    )
    _write_json(results_dir / "input_config.json", semantic_compile.get("input_config") or {})
    _write_json(results_dir / "resolved_config.json", semantic_compile.get("resolved_config") or {})
    _write_json(results_dir / "compiled_plan.json", semantic_compile.get("compiled_plan") or {})

    result = sanitize_json(
        {
            "exp_id": exp_id,
            "results_dir": str(results_dir),
            "status": "OK",
            "total_return": combo_perf.get("total_return"),
            "cagr": combo_perf.get("cagr"),
            "max_drawdown": combo_perf.get("max_drawdown"),
            "sharpe": combo_perf.get("sharpe"),
            "calmar": combo_perf.get("calmar"),
            "trades": sum(
                int(((component.get("perf") or {}).get("trades")) or 0)
                for component in (stock_component, etf_component)
            ),
            "turnover": None,
            "effective_execution_start_date": combo_perf.get("effective_execution_start_date"),
            "effective_signal_start_date": combo_perf.get("effective_signal_start_date"),
            "asset_context": build_asset_context("cn_a_equity"),
            "run_profile": combo_runtime_profile,
            "runtime_profile": _summarize_runtime_profile(combo_runtime_profile),
            "run_profile_summary": _summarize_runtime_profile(combo_runtime_profile),
            "artifacts": {
                "perf": ARTIFACT_FILENAMES["perf"],
                "nav": ARTIFACT_FILENAMES["nav"],
                "daily": ARTIFACT_FILENAMES["daily"],
                "trades": ARTIFACT_FILENAMES["trades"],
                "orders": ARTIFACT_FILENAMES["orders"],
                "reason_codes": ARTIFACT_FILENAMES["reason_codes"],
                "symbol_performance": ARTIFACT_FILENAMES["symbol_performance"],
                "stage_summary": ARTIFACT_FILENAMES["stage_summary"],
                "regime_audit_summary": ARTIFACT_FILENAMES["regime_audit_summary"],
                "attribution_audit": ARTIFACT_FILENAMES["attribution_audit"],
                "run_meta": ARTIFACT_FILENAMES["run_meta"],
                "execution_contract": ARTIFACT_FILENAMES["execution_contract"],
                "config": "config.json",
                "audit": "audit.json",
                "input_config": "input_config.json",
                "resolved_config": "resolved_config.json",
                "compiled_plan": "compiled_plan.json",
            },
            "stage_pipeline": combo_stage_pipeline,
        }
    )
    _, manifest = write_manifest(results_dir, result)
    result["manifest"] = manifest
    research_audit = build_research_audit(
        results_dir=results_dir,
        result=result,
        run_meta=combo_run_meta,
        perf=combo_perf,
        stage_summary=combo_stage_summary,
        stage_pipeline=combo_stage_pipeline,
    )
    _write_json(results_dir / "audit.json", research_audit)
    _append_to_experiment_index(
        results_dir,
        result,
        base_cfg,
        {
            "workbench_config": semantic_compile.get("input_config"),
            "original_workbench_config": semantic_compile.get("input_config"),
        },
    )
    _emit_progress(progress_hook, 100, "统一组合实验完成")
    return sanitize_json(result)
