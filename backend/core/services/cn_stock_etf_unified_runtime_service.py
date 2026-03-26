from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import pandas as pd

from backend.api.backtest_v2.artifacts_finalize import _append_to_experiment_index
from backend.api.backtest_v2.artifacts_manifest import write_manifest
from backend.api.backtest_v2.protocol import ARTIFACT_FILENAMES
from backend.api.shared.paths import experiments_root as _experiments_root
from backend.api.shared.json_utils import sanitize_json
from backend.core.config.asset_profiles import build_asset_context
from backend.core.config.cn_a_governed_mainline import canonical_state_5, coarse_state_from_state_5
from backend.core.audit.research_audit import build_research_audit


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


def _build_combo_nav(stock_results_dir: Path, etf_results_dir: Path) -> pd.DataFrame:
    stock_nav = _read_nav_frame(stock_results_dir).rename(columns={"nav": "stock_nav"})
    etf_nav = _read_nav_frame(etf_results_dir).rename(columns={"nav": "etf_nav"})
    merged = stock_nav.merge(etf_nav, on="date", how="inner")
    if merged.empty:
        raise RuntimeError("unified combo requires overlapping stock/ETF nav windows")
    merged["stock_ret"] = merged["stock_nav"].pct_change().fillna(0.0)
    merged["etf_ret"] = merged["etf_nav"].pct_change().fillna(0.0)
    merged["combo_ret"] = 0.5 * merged["stock_ret"] + 0.5 * merged["etf_ret"]
    merged["nav"] = (1.0 + merged["combo_ret"]).cumprod()
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return merged[["date", "nav", "stock_nav", "etf_nav", "stock_ret", "etf_ret", "combo_ret"]].copy()


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
        "LIGHT": 2,
        "TRANS_UP": 3,
        "BULL": 4,
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


def _component_weighted_exposure(weight: float, value: Any, fallback: Any = None) -> float | None:
    num = _safe_float(value)
    if num is None:
        num = _safe_float(fallback)
    if num is None:
        return None
    return float(weight) * float(num)


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
) -> dict[str, Any]:
    stock_governed = dict(stock_run_meta.get("governed_snapshot") or {})
    etf_governed = dict(etf_run_meta.get("governed_snapshot") or {})
    stock_weight = float(weights.get("cn_stock_trend_alpha_core", 0.5) or 0.0)
    etf_weight = float(weights.get("cn_etf_beta", 0.5) or 0.0)

    stock_sleeve = _component_sleeve_payload(stock_run_meta, "cn_stock_trend_alpha_core")
    etf_sleeve = _component_sleeve_payload(etf_run_meta, "cn_etf_beta")
    stock_target = _component_weighted_exposure(stock_weight, stock_governed.get("total_exposure_cap"), stock_weight)
    etf_target = _component_weighted_exposure(etf_weight, etf_governed.get("total_exposure_cap"), etf_weight)
    stock_actual = _component_weighted_exposure(stock_weight, stock_governed.get("actual_exposure"), stock_governed.get("total_exposure_cap"))
    etf_actual = _component_weighted_exposure(etf_weight, etf_governed.get("actual_exposure"), etf_governed.get("total_exposure_cap"))
    stock_actual_risk = _component_weighted_exposure(stock_weight, stock_governed.get("actual_risk_exposure"), stock_governed.get("total_exposure_cap"))
    etf_actual_risk = _component_weighted_exposure(etf_weight, etf_governed.get("actual_risk_exposure"), etf_governed.get("total_exposure_cap"))
    stock_actual_fallback = _component_weighted_exposure(stock_weight, stock_governed.get("actual_fallback_exposure"), 0.0)
    etf_actual_fallback = _component_weighted_exposure(etf_weight, etf_governed.get("actual_fallback_exposure"), 0.0)
    stock_actual_other = _component_weighted_exposure(stock_weight, stock_governed.get("actual_other_exposure"), 0.0)
    etf_actual_other = _component_weighted_exposure(etf_weight, etf_governed.get("actual_other_exposure"), 0.0)
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
            "budget_source": "global_portfolio_governor",
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
            "budget_source": "global_portfolio_governor",
            "budget_share": etf_weight,
            "target_exposure": etf_target,
            "actual_exposure": etf_actual,
            "actual_risk_exposure": etf_actual_risk,
            "actual_fallback_exposure": etf_actual_fallback,
            "actual_other_exposure": etf_actual_other,
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
            "budget_owner": "global_portfolio_governor",
            "budget_consumer_sleeve_id": "cn_stock_trend_alpha_core + cn_etf_beta",
            "budget_consumer_system_role": "unified_multi_sleeve_combo",
            "budget_semantics": "weighted_combo_governor_budget",
            "regime_source_state": combo_regime.get("base_state"),
            "regime_effective_state": combo_regime.get("effective_state"),
            "coarse_state": combo_regime.get("coarse_state"),
            "effective_coarse_state": combo_regime.get("effective_coarse_state"),
            "regime_reason_codes": list(combo_regime.get("reason_codes") or []),
            "total_risk_budget": total_risk_budget,
            "total_exposure_cap": total_exposure_cap,
            "target_exposure": target_exposure,
            "min_deployable_exposure": None,
            "target_exposure_source": "unified_runtime_component_weighted_caps",
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
            "sleeve_budget_mode": "unified_runtime_component_weighted",
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
    daily = combo_nav[["date", "nav", "stock_nav", "etf_nav"]].copy()
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
    daily["combo_mode"] = "daily_rebalanced_equal_weight_50_50"
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
        "audit": _read_json(results_dir / "audit.json"),
    }


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


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(sanitize_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")


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
    unified_runtime = semantic_compile.get("unified_runtime") if isinstance(semantic_compile.get("unified_runtime"), dict) else {}
    sleeves = unified_runtime.get("sleeves") if isinstance(unified_runtime.get("sleeves"), dict) else {}
    stock_semantic_cfg = ((sleeves.get("stock_alpha_core") or {}).get("semantic_config")) if isinstance((sleeves.get("stock_alpha_core") or {}), dict) else None
    etf_semantic_cfg = ((sleeves.get("etf_beta") or {}).get("semantic_config")) if isinstance((sleeves.get("etf_beta") or {}), dict) else None
    if not isinstance(stock_semantic_cfg, dict) or not isinstance(etf_semantic_cfg, dict):
        raise RuntimeError("unified runtime payload missing stock/ETF sleeve semantic configs")

    _emit_progress(progress_hook, 5, "开始运行个股 alpha sleeve")
    stock_body = request_model(
        preset=requested_preset or "single",
        config_json=stock_semantic_cfg,
        workbench_mode=getattr(body, "workbench_mode", None),
        fast_mode=getattr(body, "fast_mode", None),
    )
    stock_result = run_request_body(
        stock_body,
        _child_progress(progress_hook, start=5, end=45, prefix="个股 sleeve"),
    )

    _emit_progress(progress_hook, 46, "开始运行 ETF beta sleeve")
    etf_body = request_model(
        preset=requested_preset or "single",
        config_json=etf_semantic_cfg,
        workbench_mode=getattr(body, "workbench_mode", None),
        fast_mode=getattr(body, "fast_mode", None),
    )
    etf_result = run_request_body(
        etf_body,
        _child_progress(progress_hook, start=46, end=86, prefix="ETF sleeve"),
    )

    stock_component = _read_component_snapshot(stock_result)
    etf_component = _read_component_snapshot(etf_result)
    stock_dir = Path(str(stock_component.get("results_dir") or "")).resolve()
    etf_dir = Path(str(etf_component.get("results_dir") or "")).resolve()
    combo_nav = _build_combo_nav(stock_dir, etf_dir)
    combo_perf = _compute_combo_perf(combo_nav)
    exp_id, results_dir = _allocate_combo_results_dir(bt_root)
    combo_weights = dict(unified_runtime.get("weights") or {})
    if not combo_weights:
        combo_weights = {
            "cn_stock_trend_alpha_core": 0.5,
            "cn_etf_beta": 0.5,
        }
    combo_regime = _build_combo_regime(
        stock_component.get("run_meta") if isinstance(stock_component.get("run_meta"), dict) else {},
        etf_component.get("run_meta") if isinstance(etf_component.get("run_meta"), dict) else {},
    )
    combo_governed_snapshot = _build_combo_governed_snapshot(
        stock_run_meta=stock_component.get("run_meta") if isinstance(stock_component.get("run_meta"), dict) else {},
        etf_run_meta=etf_component.get("run_meta") if isinstance(etf_component.get("run_meta"), dict) else {},
        weights=combo_weights,
        combo_regime=combo_regime,
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
            "stage_pipeline": combo_stage_pipeline,
            "combo_runtime": {
                "contract_version": "cn_stock_etf_unified_runtime@1",
                "mode": "daily_rebalanced_equal_weight_50_50",
                "weights": combo_weights,
            },
            "combo_components": {
                "stock_component": {
                    "exp_id": stock_component.get("exp_id"),
                    "results_dir": stock_component.get("results_dir"),
                    "weight": combo_weights.get("cn_stock_trend_alpha_core"),
                },
                "etf_component": {
                    "exp_id": etf_component.get("exp_id"),
                    "results_dir": etf_component.get("results_dir"),
                    "weight": combo_weights.get("cn_etf_beta"),
                },
            },
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
            "research_combo": {
                "assumption": "cn_stock_etf_unified_runtime_phase1_daily_rebalanced_equal_weight_50_50",
                "mode": "daily_rebalanced_equal_weight_50_50",
                "stock_nav_column": "stock_nav",
                "etf_nav_column": "etf_nav",
                "combo_nav_column": "nav",
            },
            "combo_result": {
                "type": "unified_runtime_combo",
                "display_mode": "official_combo_result",
                "assumption": "cn_stock_etf_unified_runtime_phase1_daily_rebalanced_equal_weight_50_50",
                "mode": "daily_rebalanced_equal_weight_50_50",
                "stock_nav_column": "stock_nav",
                "etf_nav_column": "etf_nav",
                "combo_nav_column": "nav",
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
                "config": "config.json",
                "audit": "audit.json",
                "input_config": "input_config.json",
                "resolved_config": "resolved_config.json",
                "compiled_plan": "compiled_plan.json",
            },
            "stage_pipeline": combo_stage_pipeline,
        }
    )
    research_audit = build_research_audit(
        results_dir=results_dir,
        result=result,
        run_meta=combo_run_meta,
        perf=combo_perf,
        stage_summary=combo_stage_summary,
        stage_pipeline=combo_stage_pipeline,
    )
    _write_json(results_dir / "audit.json", research_audit)
    _, manifest = write_manifest(results_dir, result)
    result["manifest"] = manifest
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
