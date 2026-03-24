from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from typing import Any
from typing import Mapping

import numpy as np

from backend.core.config.cn_a_governed_mainline import canonical_state_5
from backend.core.config.cn_a_governed_mainline import coarse_state_from_state_5
from backend.core.config.models import RegimeEngineConfig
from backend.core.engine_vector.regime_engine_evaluator import FormalRegimeEvaluationResult
from backend.core.engine_vector.regime_engine_evaluator import _compute_breadth_scores
from backend.core.engine_vector.regime_engine_evaluator import _compute_participation_scores
from backend.core.engine_vector.regime_engine_evaluator import _compute_risk_scores
from backend.core.engine_vector.regime_engine_evaluator import _compute_trend_scores
from backend.core.engine_vector.regime_engine_evaluator import evaluate_formal_regime_engine
from backend.core.engine_vector.regime_engine_inputs import FormalRegimeFeatureBundle


def _empty_float_array() -> np.ndarray:
    return np.array([], dtype=float)


def _empty_object_array() -> np.ndarray:
    return np.array([], dtype=object)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        out = float(value)
    except Exception:
        return None
    if out != out:
        return None
    return float(out)


@dataclass(slots=True)
class FormalMarketRegimeResult:
    market_state: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int32))
    trade_mode: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int32))
    regime_confidence: np.ndarray = field(default_factory=_empty_float_array)
    regime_duration_bars: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int32))
    regime_transition_reason: np.ndarray = field(default_factory=_empty_object_array)
    feature_availability: np.ndarray = field(default_factory=_empty_object_array)
    fallback_active: np.ndarray = field(default_factory=lambda: np.array([], dtype=bool))
    base_state_5: np.ndarray = field(default_factory=_empty_object_array)
    effective_state_5: np.ndarray = field(default_factory=_empty_object_array)
    coarse_state: np.ndarray = field(default_factory=_empty_object_array)
    effective_coarse_state: np.ndarray = field(default_factory=_empty_object_array)
    reason_codes: np.ndarray = field(default_factory=_empty_object_array)
    block_scores: np.ndarray = field(default_factory=_empty_object_array)
    subscores: np.ndarray = field(default_factory=_empty_object_array)
    manual_override: np.ndarray = field(default_factory=_empty_object_array)
    state_stability_metrics: np.ndarray = field(default_factory=_empty_object_array)
    risk_budget_multiplier: np.ndarray = field(default_factory=_empty_float_array)
    defense_bias: np.ndarray = field(default_factory=_empty_float_array)


_STATE_NAMES = ("BULL", "TRANS_DOWN", "TRANS_UP", "BEAR")
_DEFAULT_BUDGET_BY_STATE = {
    "BULL": 1.0,
    "TRANS_UP": 0.8,
    "LIGHT": 0.5,
    "TRANS_DOWN": 0.25,
    "RISK_OFF": 0.0,
}
_DEFAULT_DEFENSE_BIAS_BY_STATE = {
    "BULL": 0.0,
    "TRANS_UP": 0.15,
    "LIGHT": 0.35,
    "TRANS_DOWN": 0.7,
    "RISK_OFF": 1.0,
}


def _canonical_state_for_day(*, state_code: int, trade_mode_code: int) -> str:
    state_name = _STATE_NAMES[int(state_code)] if 0 <= int(state_code) < len(_STATE_NAMES) else ""
    trade_mode_name = "TREND_MAIN" if int(trade_mode_code) == 0 else "TREND_LIGHT" if int(trade_mode_code) == 1 else "NO_TRADE"
    state_5 = canonical_state_5(state_name)
    if state_5 == "RISK_OFF":
        return "RISK_OFF"
    if trade_mode_name == "NO_TRADE":
        return "RISK_OFF"
    if trade_mode_name == "TREND_LIGHT" and state_5 not in {"TRANS_UP", "TRANS_DOWN"}:
        return "LIGHT"
    return state_5


def _normalize_effective_window(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, Mapping):
        start = _normalize_text(raw.get("start")) or None
        end = _normalize_text(raw.get("end")) or None
        label = _normalize_text(raw.get("label")) or None
        if start or end or label:
            return {"start": start, "end": end, "label": label}
        return None
    text = _normalize_text(raw)
    return {"label": text} if text else None


def _manual_override_spec(governed_contract: Mapping[str, Any] | None) -> dict[str, Any]:
    governed = dict(governed_contract or {})
    regime = dict(governed.get("regime") or {})
    override = dict(regime.get("manual_override") or {})
    target_state = _normalize_text(override.get("target_state_5")) or None
    return {
        "active": bool(override.get("active", False)),
        "reason": _normalize_text(override.get("reason")) or None,
        "scope": _normalize_text(override.get("scope")) or None,
        "actor": _normalize_text(override.get("actor")) or None,
        "effective_window": _normalize_effective_window(override.get("effective_window")),
        "target_state_5": canonical_state_5(target_state) if target_state else None,
        "risk_budget_multiplier": _safe_float(override.get("risk_budget_multiplier")),
        "defense_bias": _safe_float(override.get("defense_bias")),
    }


def _override_active_for_day(override: Mapping[str, Any], current_date: date) -> bool:
    if not bool(override.get("active", False)):
        return False
    window = dict(override.get("effective_window") or {})
    start_text = _normalize_text(window.get("start"))
    end_text = _normalize_text(window.get("end"))
    try:
        start_date = date.fromisoformat(start_text) if start_text else None
    except Exception:
        start_date = None
    try:
        end_date = date.fromisoformat(end_text) if end_text else None
    except Exception:
        end_date = None
    if start_date is not None and current_date < start_date:
        return False
    if end_date is not None and current_date > end_date:
        return False
    return True


def _build_block_scores(bundle: FormalRegimeFeatureBundle) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    trend_bull, trend_bear = _compute_trend_scores(bundle)
    risk_bull, risk_bear = _compute_risk_scores(bundle)
    breadth_bull, breadth_bear = _compute_breadth_scores(bundle)
    participation_bull, participation_bear = _compute_participation_scores(bundle)
    return {
        "trend_block": (np.asarray(trend_bull, dtype=float), np.asarray(trend_bear, dtype=float)),
        "risk_block": (np.asarray(risk_bull, dtype=float), np.asarray(risk_bear, dtype=float)),
        "breadth_block": (np.asarray(breadth_bull, dtype=float), np.asarray(breadth_bear, dtype=float)),
        "participation_block": (np.asarray(participation_bull, dtype=float), np.asarray(participation_bear, dtype=float)),
    }


def _safe_nanmean(values: list[float]) -> float | None:
    finite_values = [float(value) for value in values if np.isfinite(value)]
    if not finite_values:
        return None
    return _safe_float(float(np.mean(finite_values)))


def _score_payload_rows(block_scores: dict[str, tuple[np.ndarray, np.ndarray]], *, day_count: int) -> tuple[np.ndarray, np.ndarray]:
    block_rows = np.empty(day_count, dtype=object)
    subscore_rows = np.empty(day_count, dtype=object)
    for idx in range(day_count):
        trend_bull, trend_bear = block_scores["trend_block"][0][idx], block_scores["trend_block"][1][idx]
        risk_bull, risk_bear = block_scores["risk_block"][0][idx], block_scores["risk_block"][1][idx]
        breadth_bull, breadth_bear = block_scores["breadth_block"][0][idx], block_scores["breadth_block"][1][idx]
        participation_bull, participation_bear = block_scores["participation_block"][0][idx], block_scores["participation_block"][1][idx]
        block_rows[idx] = {
            "trend_block": {"support": _safe_float(trend_bull), "stress": _safe_float(trend_bear), "net": _safe_float(trend_bull - trend_bear)},
            "risk_block": {"support": _safe_float(risk_bull), "stress": _safe_float(risk_bear), "net": _safe_float(risk_bull - risk_bear)},
            "breadth_block": {"support": _safe_float(breadth_bull), "stress": _safe_float(breadth_bear), "net": _safe_float(breadth_bull - breadth_bear)},
            "participation_block": {
                "support": _safe_float(participation_bull),
                "stress": _safe_float(participation_bear),
                "net": _safe_float(participation_bull - participation_bear),
            },
        }
        subscore_rows[idx] = {
            "technical": _safe_nanmean([trend_bull, risk_bull, breadth_bull]),
            "sentiment": _safe_float(participation_bull),
            "macro_global": None,
        }
    return block_rows, subscore_rows


def _reason_codes_for_day(
    *,
    transition_reason: str,
    fallback_active: bool,
    feature_availability: Mapping[str, Any],
    base_state_5: str,
    effective_state_5: str,
    manual_override_active: bool,
) -> list[str]:
    codes: list[str] = []
    reason = _normalize_text(transition_reason)
    if reason:
        codes.append(reason)
    if fallback_active:
        codes.append("FEATURE_FALLBACK_ACTIVE")
    if not bool(feature_availability.get("required_blocks_ready", True)):
        codes.append("REQUIRED_BLOCKS_UNAVAILABLE")
    if manual_override_active:
        codes.append("MANUAL_OVERRIDE_ACTIVE")
    if base_state_5 and effective_state_5 and base_state_5 != effective_state_5:
        codes.append("EFFECTIVE_STATE_OVERRIDDEN")
    if base_state_5:
        codes.append(f"BASE_STATE::{base_state_5}")
    return sorted({code for code in codes if _normalize_text(code)})


def _stability_payload_for_day(
    *,
    transition_reason: str,
    fallback_active: bool,
) -> dict[str, Any]:
    reason = _normalize_text(transition_reason).upper()
    return {
        "pending_transition": reason.startswith("PERSISTENCE_CONFIRMING_"),
        "cooldown_active": reason == "COOLDOWN_HOLD",
        "suppressed_by_confidence_floor": reason == "CONFIDENCE_FLOOR_HOLD",
        "suppressed_by_min_duration": reason == "MIN_DURATION_HOLD",
        "fallback_active": bool(fallback_active),
    }


def build_formal_market_regime_result(
    *,
    bundle: FormalRegimeFeatureBundle,
    regime_engine_cfg: RegimeEngineConfig,
    legacy_market_state: np.ndarray | None = None,
    legacy_trade_mode: np.ndarray | None = None,
    governed_contract: Mapping[str, Any] | None = None,
) -> FormalMarketRegimeResult:
    formal_eval: FormalRegimeEvaluationResult = evaluate_formal_regime_engine(
        bundle=bundle,
        regime_engine_cfg=regime_engine_cfg,
        legacy_market_state=legacy_market_state,
        legacy_trade_mode=legacy_trade_mode,
    )
    day_count = len(formal_eval.market_state)
    override_spec = _manual_override_spec(governed_contract)
    block_score_map = _build_block_scores(bundle)
    block_rows, subscore_rows = _score_payload_rows(block_score_map, day_count=day_count)

    base_state_5 = np.empty(day_count, dtype=object)
    effective_state_5 = np.empty(day_count, dtype=object)
    coarse_state = np.empty(day_count, dtype=object)
    effective_coarse_state = np.empty(day_count, dtype=object)
    reason_codes = np.empty(day_count, dtype=object)
    manual_override_rows = np.empty(day_count, dtype=object)
    stability_rows = np.empty(day_count, dtype=object)
    risk_budget_multiplier = np.full(day_count, np.nan, dtype=float)
    defense_bias = np.full(day_count, np.nan, dtype=float)

    for idx in range(day_count):
        current_date = bundle.dates[idx]
        base_state = _canonical_state_for_day(
            state_code=int(formal_eval.market_state[idx]),
            trade_mode_code=int(formal_eval.trade_mode[idx]),
        )
        override_active = _override_active_for_day(override_spec, current_date)
        effective_state = base_state
        if override_active and _normalize_text(override_spec.get("target_state_5")):
            effective_state = canonical_state_5(override_spec.get("target_state_5"))
        effective_risk_budget = _DEFAULT_BUDGET_BY_STATE.get(effective_state, 0.0)
        effective_defense_bias = _DEFAULT_DEFENSE_BIAS_BY_STATE.get(effective_state, 0.0)
        if override_active and override_spec.get("risk_budget_multiplier") is not None:
            effective_risk_budget = float(override_spec["risk_budget_multiplier"])
        if override_active and override_spec.get("defense_bias") is not None:
            effective_defense_bias = float(override_spec["defense_bias"])
        availability = dict(formal_eval.feature_availability[idx] or {}) if isinstance(formal_eval.feature_availability[idx], dict) else {}
        manual_override_rows[idx] = {
            "active": bool(override_active),
            "reason": override_spec.get("reason"),
            "scope": override_spec.get("scope"),
            "actor": override_spec.get("actor"),
            "effective_window": override_spec.get("effective_window"),
            "target_state_5": override_spec.get("target_state_5"),
            "risk_budget_multiplier": override_spec.get("risk_budget_multiplier"),
            "defense_bias": override_spec.get("defense_bias"),
        }
        base_state_5[idx] = base_state
        effective_state_5[idx] = effective_state
        coarse_state[idx] = coarse_state_from_state_5(base_state)
        effective_coarse_state[idx] = coarse_state_from_state_5(effective_state)
        risk_budget_multiplier[idx] = float(effective_risk_budget)
        defense_bias[idx] = float(effective_defense_bias)
        reason_codes[idx] = _reason_codes_for_day(
            transition_reason=str(formal_eval.regime_transition_reason[idx] or ""),
            fallback_active=bool(formal_eval.fallback_active[idx]),
            feature_availability=availability,
            base_state_5=base_state,
            effective_state_5=effective_state,
            manual_override_active=override_active,
        )
        stability_rows[idx] = _stability_payload_for_day(
            transition_reason=str(formal_eval.regime_transition_reason[idx] or ""),
            fallback_active=bool(formal_eval.fallback_active[idx]),
        )

    return FormalMarketRegimeResult(
        market_state=np.array(formal_eval.market_state, dtype=np.int32),
        trade_mode=np.array(formal_eval.trade_mode, dtype=np.int32),
        regime_confidence=np.array(formal_eval.regime_confidence, dtype=float),
        regime_duration_bars=np.array(formal_eval.regime_duration_bars, dtype=np.int32),
        regime_transition_reason=np.array(formal_eval.regime_transition_reason, dtype=object),
        feature_availability=np.array(formal_eval.feature_availability, dtype=object),
        fallback_active=np.array(formal_eval.fallback_active, dtype=bool),
        base_state_5=base_state_5,
        effective_state_5=effective_state_5,
        coarse_state=coarse_state,
        effective_coarse_state=effective_coarse_state,
        reason_codes=reason_codes,
        block_scores=block_rows,
        subscores=subscore_rows,
        manual_override=manual_override_rows,
        state_stability_metrics=stability_rows,
        risk_budget_multiplier=risk_budget_multiplier,
        defense_bias=defense_bias,
    )


__all__ = [
    "FormalMarketRegimeResult",
    "build_formal_market_regime_result",
]
