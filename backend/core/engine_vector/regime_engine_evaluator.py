from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from backend.core.config.models import RegimeEngineConfig
from backend.core.engine_vector.regime_engine_inputs import FormalRegimeFeatureBundle
from backend.core.engine_vector.regime_engine_inputs import resolve_required_regime_blocks


def _empty_float_array() -> np.ndarray:
    return np.array([], dtype=float)


def _empty_int_array() -> np.ndarray:
    return np.array([], dtype=np.int32)


def _empty_bool_array() -> np.ndarray:
    return np.array([], dtype=bool)


def _empty_object_array() -> np.ndarray:
    return np.array([], dtype=object)


def _clip01(values: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(values, dtype=float), 0.0, 1.0)


def _safe_nanmean(*arrays: np.ndarray) -> np.ndarray:
    stacked = np.vstack([np.asarray(arr, dtype=float) for arr in arrays])
    valid_counts = np.sum(~np.isnan(stacked), axis=0)
    summed = np.nansum(stacked, axis=0)
    out = np.full(stacked.shape[1], np.nan, dtype=float)
    valid = valid_counts > 0
    out[valid] = summed[valid] / valid_counts[valid]
    return out


def _tanh01(values: np.ndarray, *, scale: float) -> np.ndarray:
    safe_scale = max(float(scale), 1e-6)
    return 0.5 * (np.tanh(np.asarray(values, dtype=float) / safe_scale) + 1.0)


@dataclass(slots=True)
class FormalRegimeEvaluationResult:
    market_state: np.ndarray = field(default_factory=_empty_int_array)
    trade_mode: np.ndarray = field(default_factory=_empty_int_array)
    regime_confidence: np.ndarray = field(default_factory=_empty_float_array)
    regime_duration_bars: np.ndarray = field(default_factory=_empty_int_array)
    regime_transition_reason: np.ndarray = field(default_factory=_empty_object_array)
    feature_availability: np.ndarray = field(default_factory=_empty_object_array)
    fallback_active: np.ndarray = field(default_factory=_empty_bool_array)


STATE_NAMES = ("BULL", "TRANS_DOWN", "TRANS_UP", "BEAR")
TRADE_MODE_NAMES = ("TREND_MAIN", "TREND_LIGHT", "NO_TRADE")


def _build_feature_availability_rows(
    bundle: FormalRegimeFeatureBundle,
    *,
    required_blocks_ready: np.ndarray,
    fallback_active: np.ndarray,
) -> np.ndarray:
    day_count = len(bundle.dates)
    rows = np.empty(day_count, dtype=object)
    for idx in range(day_count):
        rows[idx] = {
            "trend_block": bool(bundle.feature_availability.trend_block[idx]),
            "risk_block": bool(bundle.feature_availability.risk_block[idx]),
            "breadth_block": bool(bundle.feature_availability.breadth_block[idx]),
            "participation_block": bool(bundle.feature_availability.participation_block[idx]),
            "required_blocks_ready": bool(required_blocks_ready[idx]),
            "fallback_active": bool(fallback_active[idx]),
        }
    return rows


def _compute_trend_scores(bundle: FormalRegimeFeatureBundle) -> tuple[np.ndarray, np.ndarray]:
    price_gap = bundle.benchmark_close / bundle.trend_long_ma - 1.0
    bull = _safe_nanmean(
        _clip01(price_gap / 0.08),
        _clip01(bundle.trend_long_ma_slope / 0.06),
        _clip01((bundle.trend_breakout_ratio - 1.0) / 0.03),
    )
    bear = _safe_nanmean(
        _clip01((-price_gap) / 0.08),
        _clip01((-bundle.trend_long_ma_slope) / 0.06),
        _clip01((1.0 - bundle.trend_breakout_ratio) / 0.03),
    )
    return bull, bear


def _compute_risk_scores(bundle: FormalRegimeFeatureBundle) -> tuple[np.ndarray, np.ndarray]:
    risk_pressure = _safe_nanmean(
        _clip01(bundle.risk_realized_vol / 0.04),
        _clip01(bundle.risk_atr_ratio / 0.04),
        _clip01(np.abs(np.minimum(bundle.risk_drawdown, 0.0)) / 0.15),
    )
    bull = 1.0 - risk_pressure
    bear = risk_pressure
    return bull, bear


def _compute_breadth_scores(bundle: FormalRegimeFeatureBundle) -> tuple[np.ndarray, np.ndarray]:
    breadth_spread = _clip01(0.5 + 0.5 * (bundle.breadth_new_high_ratio - bundle.breadth_new_low_ratio))
    breadth_down_spread = _clip01(0.5 + 0.5 * (bundle.breadth_new_low_ratio - bundle.breadth_new_high_ratio))
    bull = _safe_nanmean(
        bundle.breadth_above_ma_short_ratio,
        bundle.breadth_above_ma_long_ratio,
        breadth_spread,
    )
    bear = _safe_nanmean(
        1.0 - bundle.breadth_above_ma_short_ratio,
        1.0 - bundle.breadth_above_ma_long_ratio,
        breadth_down_spread,
    )
    return bull, bear


def _compute_participation_scores(bundle: FormalRegimeFeatureBundle) -> tuple[np.ndarray, np.ndarray]:
    turnover_norm = _clip01(bundle.participation_turnover_mean / 0.03)
    amount_z = _tanh01(bundle.participation_amount_zscore, scale=2.0)
    bull = _safe_nanmean(turnover_norm, amount_z)
    bear = _safe_nanmean(1.0 - turnover_norm, 1.0 - amount_z)
    return bull, bear


def _weighted_score(values: dict[str, np.ndarray], availability: dict[str, np.ndarray]) -> np.ndarray:
    weights = {
        "trend_block": 0.40,
        "risk_block": 0.25,
        "breadth_block": 0.20,
        "participation_block": 0.15,
    }
    day_count = len(next(iter(values.values()))) if values else 0
    total = np.zeros(day_count, dtype=float)
    denom = np.zeros(day_count, dtype=float)
    for name, arr in values.items():
        weight = float(weights.get(name, 0.0))
        mask = np.asarray(availability[name], dtype=bool)
        safe_values = np.where(mask, np.asarray(arr, dtype=float), 0.0)
        total += safe_values * weight
        denom += mask.astype(float) * weight
    out = np.full(day_count, np.nan, dtype=float)
    valid = denom > 0
    out[valid] = total[valid] / denom[valid]
    return out


def _candidate_state_and_confidence(
    bundle: FormalRegimeFeatureBundle,
    *,
    availability: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    trend_bull, trend_bear = _compute_trend_scores(bundle)
    risk_bull, risk_bear = _compute_risk_scores(bundle)
    breadth_bull, breadth_bear = _compute_breadth_scores(bundle)
    participation_bull, participation_bear = _compute_participation_scores(bundle)
    bull_score = _weighted_score(
        {
            "trend_block": trend_bull,
            "risk_block": risk_bull,
            "breadth_block": breadth_bull,
            "participation_block": participation_bull,
        },
        availability,
    )
    bear_score = _weighted_score(
        {
            "trend_block": trend_bear,
            "risk_block": risk_bear,
            "breadth_block": breadth_bear,
            "participation_block": participation_bear,
        },
        availability,
    )
    diff = bull_score - bear_score
    state = np.full(len(diff), 3, dtype=np.int8)
    state[(bull_score >= 0.62) & (diff >= 0.08)] = 0
    state[(bear_score < 0.62) & (diff >= 0.0)] = 2
    state[(bull_score < 0.62) & (diff < 0.0)] = 1
    confidence = np.full(len(diff), 0.0, dtype=float)
    bull_mask = state == 0
    bear_mask = state == 3
    trans_mask = ~(bull_mask | bear_mask)
    confidence[bull_mask] = bull_score[bull_mask]
    confidence[bear_mask] = bear_score[bear_mask]
    confidence[trans_mask] = 0.45 + 0.55 * np.abs(diff[trans_mask])
    confidence = _clip01(confidence)
    return state, confidence


def _transition_reason(prev_state: int, new_state: int) -> str:
    if prev_state == new_state:
        return "UNCHANGED"
    if new_state == 0:
        return "TREND_RISK_BREADTH_CONFIRMED"
    if new_state == 3:
        return "TREND_RISK_BREAKDOWN_CONFIRMED"
    if new_state == 2:
        return "RECOVERY_UNCONFIRMED"
    return "BREAKDOWN_UNCONFIRMED"


def _build_trade_mode_array(
    *,
    market_state: np.ndarray,
    regime_confidence: np.ndarray,
    regime_duration_bars: np.ndarray,
    transition_reason: np.ndarray,
    fallback_active: np.ndarray,
    legacy_trade_mode: np.ndarray | None,
    regime_engine_cfg: RegimeEngineConfig,
    bundle: FormalRegimeFeatureBundle,
) -> np.ndarray:
    day_count = len(market_state)
    trade_mode = np.full(day_count, 2, dtype=np.int8)
    confidence_floor = float(regime_engine_cfg.persistence.confidence_floor)
    entry_confirm_bars = max(1, int(regime_engine_cfg.persistence.entry_confirm_bars))
    exit_confirm_bars = max(1, int(regime_engine_cfg.persistence.exit_confirm_bars))
    amount_z = np.asarray(bundle.participation_amount_zscore, dtype=float)
    for idx in range(day_count):
        if bool(fallback_active[idx]) and legacy_trade_mode is not None and idx < len(legacy_trade_mode):
            trade_mode[idx] = int(legacy_trade_mode[idx])
            continue
        state = int(market_state[idx])
        confidence = float(regime_confidence[idx])
        duration = int(regime_duration_bars[idx])
        participation_ok = bool(not np.isnan(amount_z[idx]) and amount_z[idx] >= -0.5)
        if state == 0:
            trade_mode[idx] = 0 if confidence >= confidence_floor and duration >= entry_confirm_bars else 1
            continue
        if state == 2:
            if confidence >= confidence_floor and duration >= entry_confirm_bars and participation_ok:
                trade_mode[idx] = 1
            else:
                trade_mode[idx] = 2
            continue
        if state == 1:
            trade_mode[idx] = 1 if confidence >= confidence_floor and duration >= exit_confirm_bars else 2
            continue
        trade_mode[idx] = 2
    return trade_mode


def evaluate_formal_regime_engine(
    *,
    bundle: FormalRegimeFeatureBundle,
    regime_engine_cfg: RegimeEngineConfig,
    legacy_market_state: np.ndarray | None = None,
    legacy_trade_mode: np.ndarray | None = None,
) -> FormalRegimeEvaluationResult:
    day_count = len(bundle.dates)
    legacy_market_state_arr = (
        np.asarray(legacy_market_state, dtype=np.int32)
        if legacy_market_state is not None
        else np.array([], dtype=np.int32)
    )
    legacy_trade_mode_arr = (
        np.asarray(legacy_trade_mode, dtype=np.int32)
        if legacy_trade_mode is not None
        else np.array([], dtype=np.int32)
    )
    availability = {
        "trend_block": np.asarray(bundle.feature_availability.trend_block, dtype=bool),
        "risk_block": np.asarray(bundle.feature_availability.risk_block, dtype=bool),
        "breadth_block": np.asarray(bundle.feature_availability.breadth_block, dtype=bool),
        "participation_block": np.asarray(bundle.feature_availability.participation_block, dtype=bool),
    }
    required_ready = resolve_required_regime_blocks(
        bundle.feature_availability,
        regime_engine_cfg.fallback.required_blocks,
    )
    if required_ready.size == 0:
        required_ready = np.ones(day_count, dtype=bool)
    fallback_active = ~required_ready
    feature_rows = _build_feature_availability_rows(
        bundle,
        required_blocks_ready=required_ready,
        fallback_active=fallback_active,
    )
    candidate_state, candidate_confidence = _candidate_state_and_confidence(
        bundle,
        availability=availability,
    )
    market_state = np.full(day_count, 0, dtype=np.int8)
    regime_confidence = np.full(day_count, 0.0, dtype=float)
    regime_duration = np.zeros(day_count, dtype=np.int32)
    transition_reason = np.empty(day_count, dtype=object)

    current_state = int(legacy_market_state_arr[0]) if len(legacy_market_state_arr) > 0 and day_count > 0 else 0
    current_confidence = 0.0
    current_duration = 0
    pending_state: int | None = None
    pending_count = 0
    cooldown_remaining = 0
    entry_confirm = max(1, int(regime_engine_cfg.persistence.entry_confirm_bars))
    exit_confirm = max(1, int(regime_engine_cfg.persistence.exit_confirm_bars))
    min_state_duration = max(1, int(regime_engine_cfg.persistence.min_state_duration))
    confidence_floor = float(regime_engine_cfg.persistence.confidence_floor)
    cooldown_bars = max(0, int(regime_engine_cfg.persistence.transition_cooldown))

    for idx in range(day_count):
        if bool(fallback_active[idx]):
            state = int(legacy_market_state_arr[idx]) if idx < len(legacy_market_state_arr) else current_state
            if idx == 0 or state != current_state:
                current_duration = 1
            else:
                current_duration += 1
            current_state = state
            current_confidence = 0.0
            market_state[idx] = current_state
            regime_confidence[idx] = current_confidence
            regime_duration[idx] = current_duration
            transition_reason[idx] = "FALLBACK_FEATURE_UNAVAILABLE"
            pending_state = None
            pending_count = 0
            cooldown_remaining = max(cooldown_remaining - 1, 0)
            continue

        cand_state = int(candidate_state[idx])
        cand_conf = float(candidate_confidence[idx])
        if idx == 0 and current_duration == 0:
            current_state = cand_state
            current_confidence = cand_conf
            current_duration = 1
            market_state[idx] = current_state
            regime_confidence[idx] = current_confidence
            regime_duration[idx] = current_duration
            transition_reason[idx] = "INITIAL_STATE"
            continue

        if cand_state == current_state:
            current_duration += 1
            current_confidence = cand_conf
            pending_state = None
            pending_count = 0
            cooldown_remaining = max(cooldown_remaining - 1, 0)
            market_state[idx] = current_state
            regime_confidence[idx] = current_confidence
            regime_duration[idx] = current_duration
            transition_reason[idx] = "UNCHANGED"
            continue

        if cand_conf < confidence_floor:
            current_duration += 1
            cooldown_remaining = max(cooldown_remaining - 1, 0)
            market_state[idx] = current_state
            regime_confidence[idx] = current_confidence
            regime_duration[idx] = current_duration
            transition_reason[idx] = "CONFIDENCE_FLOOR_HOLD"
            pending_state = None
            pending_count = 0
            continue

        if current_duration < min_state_duration:
            current_duration += 1
            cooldown_remaining = max(cooldown_remaining - 1, 0)
            market_state[idx] = current_state
            regime_confidence[idx] = current_confidence
            regime_duration[idx] = current_duration
            transition_reason[idx] = "MIN_DURATION_HOLD"
            pending_state = None
            pending_count = 0
            continue

        if cooldown_remaining > 0:
            current_duration += 1
            cooldown_remaining = max(cooldown_remaining - 1, 0)
            market_state[idx] = current_state
            regime_confidence[idx] = current_confidence
            regime_duration[idx] = current_duration
            transition_reason[idx] = "COOLDOWN_HOLD"
            pending_state = None
            pending_count = 0
            continue

        confirm_needed = entry_confirm if cand_state in (0, 2) else exit_confirm
        if pending_state == cand_state:
            pending_count += 1
        else:
            pending_state = cand_state
            pending_count = 1

        if pending_count >= confirm_needed:
            previous_state = current_state
            current_state = cand_state
            current_confidence = cand_conf
            current_duration = 1
            cooldown_remaining = cooldown_bars
            pending_state = None
            pending_count = 0
            market_state[idx] = current_state
            regime_confidence[idx] = current_confidence
            regime_duration[idx] = current_duration
            transition_reason[idx] = _transition_reason(previous_state, current_state)
            continue

        current_duration += 1
        market_state[idx] = current_state
        regime_confidence[idx] = current_confidence
        regime_duration[idx] = current_duration
        transition_reason[idx] = f"PERSISTENCE_CONFIRMING_{STATE_NAMES[cand_state]}"

    trade_mode = _build_trade_mode_array(
        market_state=market_state,
        regime_confidence=regime_confidence,
        regime_duration_bars=regime_duration,
        transition_reason=transition_reason,
        fallback_active=fallback_active,
        legacy_trade_mode=legacy_trade_mode_arr if len(legacy_trade_mode_arr) > 0 else None,
        regime_engine_cfg=regime_engine_cfg,
        bundle=bundle,
    )
    return FormalRegimeEvaluationResult(
        market_state=market_state.astype(np.int32),
        trade_mode=trade_mode.astype(np.int32),
        regime_confidence=regime_confidence.astype(float),
        regime_duration_bars=regime_duration.astype(np.int32),
        regime_transition_reason=transition_reason,
        feature_availability=feature_rows,
        fallback_active=fallback_active.astype(bool),
    )
