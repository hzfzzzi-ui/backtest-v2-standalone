from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.core.config.models import WeeklyFiveStateRegimeConfig
from backend.core.engine_vector.features import adx_matrix

STATE_NAME_BY_RANK = (
    "DEFENSIVE",
    "TURN_WEAK",
    "LIGHT_TREND",
    "TURN_STRONG",
    "BULL_MAIN",
)
STATE_CODE_BY_NAME = {name: idx for idx, name in enumerate(STATE_NAME_BY_RANK)}
TRADE_MODE_CODE_BY_NAME = {
    "TREND_MAIN": 0,
    "TREND_LIGHT": 1,
    "NO_TRADE": 2,
}


@dataclass(slots=True)
class WeeklyFiveStateEvaluation:
    market_state_codes: np.ndarray
    market_state_names: np.ndarray
    market_state_raw_names: np.ndarray
    market_state_smoothed_names: np.ndarray
    trade_mode_codes: np.ndarray
    trade_mode_names: np.ndarray
    risk_budget_multipliers: np.ndarray
    state_scores: np.ndarray
    weekly_observation_flags: np.ndarray
    regime_confidence: np.ndarray
    regime_duration_bars: np.ndarray
    regime_transition_reason: np.ndarray
    feature_availability: np.ndarray
    fallback_active: np.ndarray


def _score_to_rank(score: float) -> int:
    if score >= 5.0:
        return STATE_CODE_BY_NAME["BULL_MAIN"]
    if score >= 4.0:
        return STATE_CODE_BY_NAME["TURN_STRONG"]
    if score >= 3.0:
        return STATE_CODE_BY_NAME["LIGHT_TREND"]
    if score >= 1.0:
        return STATE_CODE_BY_NAME["TURN_WEAK"]
    return STATE_CODE_BY_NAME["DEFENSIVE"]


def _budget_for_rank(rank: int, *, turn_weak_budget: float) -> float:
    if rank >= STATE_CODE_BY_NAME["BULL_MAIN"]:
        return 1.0
    if rank == STATE_CODE_BY_NAME["TURN_STRONG"]:
        return 0.70
    if rank == STATE_CODE_BY_NAME["LIGHT_TREND"]:
        return 0.40
    if rank == STATE_CODE_BY_NAME["TURN_WEAK"]:
        return float(turn_weak_budget)
    return 0.0


def _normalize_budget_mode(mode: str | None) -> str:
    value = str(mode or "five_state").strip().lower()
    if value == "asymmetric_budget":
        return "asymmetric_budget"
    return "three_state" if value == "three_state" else "five_state"


def _trade_mode_for_rank(rank: int, *, risk_budget_mode: str) -> tuple[int, str]:
    if risk_budget_mode in {"three_state", "asymmetric_budget"}:
        if rank in (STATE_CODE_BY_NAME["TURN_WEAK"], STATE_CODE_BY_NAME["DEFENSIVE"]):
            return TRADE_MODE_CODE_BY_NAME["NO_TRADE"], "NO_TRADE"
        return TRADE_MODE_CODE_BY_NAME["TREND_MAIN"], "TREND_MAIN"
    if rank == STATE_CODE_BY_NAME["DEFENSIVE"]:
        return TRADE_MODE_CODE_BY_NAME["NO_TRADE"], "NO_TRADE"
    return TRADE_MODE_CODE_BY_NAME["TREND_MAIN"], "TREND_MAIN"


def _risk_budget_for_rank(
    rank: int,
    *,
    turn_weak_budget: float,
    risk_budget_mode: str,
) -> float:
    if risk_budget_mode == "three_state":
        if rank >= STATE_CODE_BY_NAME["TURN_STRONG"]:
            return 1.0
        if rank == STATE_CODE_BY_NAME["LIGHT_TREND"]:
            return 0.40
        return 0.0
    if risk_budget_mode == "asymmetric_budget":
        if rank >= STATE_CODE_BY_NAME["BULL_MAIN"]:
            return 1.0
        if rank == STATE_CODE_BY_NAME["TURN_STRONG"]:
            return 0.70
        if rank == STATE_CODE_BY_NAME["LIGHT_TREND"]:
            return 0.40
        return 0.0
    return _budget_for_rank(rank, turn_weak_budget=turn_weak_budget)


def _fallback_rank_from_legacy_state(state_code: int) -> int:
    if state_code == 0:
        return STATE_CODE_BY_NAME["BULL_MAIN"]
    if state_code == 2:
        return STATE_CODE_BY_NAME["TURN_STRONG"]
    if state_code == 1:
        return STATE_CODE_BY_NAME["TURN_WEAK"]
    return STATE_CODE_BY_NAME["DEFENSIVE"]


def _resample_last_trading_day_indices(day_index: pd.DatetimeIndex, rule: str) -> np.ndarray:
    if len(day_index) == 0:
        return np.array([], dtype=np.int32)
    anchor = pd.Series(np.arange(len(day_index), dtype=np.int32), index=day_index)
    sampled = anchor.resample(rule).last().dropna()
    if sampled.empty:
        return np.array([], dtype=np.int32)
    return sampled.to_numpy(dtype=np.int32)


def evaluate_weekly_five_state_regime(
    *,
    benchmark: pd.DataFrame,
    dates: np.ndarray,
    cfg: WeeklyFiveStateRegimeConfig,
    legacy_market_state: np.ndarray,
) -> WeeklyFiveStateEvaluation:
    day_index = pd.DatetimeIndex(pd.to_datetime(dates)).normalize()
    day_count = len(day_index)

    market_state_codes = np.full(day_count, STATE_CODE_BY_NAME["DEFENSIVE"], dtype=np.int8)
    market_state_names = np.full(day_count, "DEFENSIVE", dtype=object)
    market_state_raw_names = np.full(day_count, "", dtype=object)
    market_state_smoothed_names = np.full(day_count, "", dtype=object)
    trade_mode_codes = np.full(day_count, TRADE_MODE_CODE_BY_NAME["NO_TRADE"], dtype=np.int8)
    trade_mode_names = np.full(day_count, "NO_TRADE", dtype=object)
    risk_budget_multipliers = np.zeros(day_count, dtype=float)
    state_scores = np.full(day_count, np.nan, dtype=float)
    weekly_observation_flags = np.zeros(day_count, dtype=bool)
    regime_confidence = np.zeros(day_count, dtype=float)
    regime_duration_bars = np.zeros(day_count, dtype=np.int32)
    regime_transition_reason = np.full(day_count, "", dtype=object)
    feature_availability = np.empty(day_count, dtype=object)
    fallback_active = np.zeros(day_count, dtype=bool)

    bench = benchmark.copy()
    bench["date"] = pd.to_datetime(bench["date"], errors="coerce").dt.normalize()
    bench = bench.dropna(subset=["date"]).sort_values("date")
    close = pd.Series(
        pd.to_numeric(bench.get("close"), errors="coerce").to_numpy(dtype=float),
        index=bench["date"],
        dtype=float,
    ).reindex(day_index)
    high = pd.Series(
        pd.to_numeric(bench.get("high", bench.get("close")), errors="coerce").to_numpy(dtype=float),
        index=bench["date"],
        dtype=float,
    ).reindex(day_index)
    low = pd.Series(
        pd.to_numeric(bench.get("low", bench.get("close")), errors="coerce").to_numpy(dtype=float),
        index=bench["date"],
        dtype=float,
    ).reindex(day_index)

    ma_window = max(2, int(cfg.ma_window))
    ma_slope_lookback = max(1, int(cfg.ma_slope_lookback))
    ret_short_window = max(1, int(cfg.ret_short_window))
    ret_long_window = max(ret_short_window, int(cfg.ret_long_window))
    adx_window = max(2, int(cfg.adx_window))
    weekly_rule = str(cfg.weekly_rule or "W-FRI").strip() or "W-FRI"
    upgrade_confirm_weeks = max(1, int(cfg.upgrade_confirm_weeks))
    downgrade_confirm_weeks = max(1, int(cfg.downgrade_confirm_weeks))
    turn_weak_budget = float(cfg.turn_weak_budget)
    risk_budget_mode = _normalize_budget_mode(getattr(cfg, "risk_budget_mode", "five_state"))

    ma120 = close.rolling(ma_window, min_periods=ma_window).mean()
    ma_slope_up = ma120 > ma120.shift(ma_slope_lookback)
    ret60 = close / close.shift(ret_short_window) - 1.0
    ret120 = close / close.shift(ret_long_window) - 1.0
    adx20 = pd.Series(
        adx_matrix(
            high.to_numpy(dtype=float),
            low.to_numpy(dtype=float),
            close.to_numpy(dtype=float),
            period=adx_window,
        ),
        index=day_index,
        dtype=float,
    )

    close_above_ma = close > ma120
    ret60_pos = ret60 > 0.0
    ret120_pos = ret120 > 0.0
    adx_score = pd.Series(np.where(adx20 >= 25.0, 1.0, np.where(adx20 >= 20.0, 0.0, -1.0)), index=day_index, dtype=float)

    all_ready = (
        close.notna()
        & ma120.notna()
        & ma120.shift(ma_slope_lookback).notna()
        & ret60.notna()
        & ret120.notna()
        & adx20.notna()
    )

    for idx in range(day_count):
        feature_availability[idx] = {
            "close_ma120": bool(close.notna().iloc[idx] and ma120.notna().iloc[idx]),
            "ma120_slope": bool(ma120.notna().iloc[idx] and ma120.shift(ma_slope_lookback).notna().iloc[idx]),
            "ret60": bool(ret60.notna().iloc[idx]),
            "ret120": bool(ret120.notna().iloc[idx]),
            "adx20": bool(adx20.notna().iloc[idx]),
            "all_ready": bool(all_ready.iloc[idx]),
        }

    valid_indices = np.flatnonzero(all_ready.to_numpy(dtype=bool))
    if len(valid_indices) > 0:
        raw_scores = (
            close_above_ma.astype(float)
            + ma_slope_up.astype(float)
            + ret60_pos.astype(float)
            + ret120_pos.astype(float)
            + adx_score
        )
        state_scores[valid_indices] = raw_scores.to_numpy(dtype=float)[valid_indices]
        for idx in valid_indices:
            rank = _score_to_rank(float(state_scores[idx]))
            name = STATE_NAME_BY_RANK[rank]
            market_state_raw_names[idx] = name

    observation_indices = _resample_last_trading_day_indices(day_index, weekly_rule)
    weekly_observation_flags[observation_indices] = True

    current_rank: int | None = None
    pending_rank: int | None = None
    pending_count = 0
    obs_smoothed_rank: dict[int, int] = {}
    obs_reason: dict[int, str] = {}
    obs_confidence: dict[int, float] = {}

    downgrade_pending_rank: int | None = None
    downgrade_pending_count = 0

    for obs_idx in observation_indices:
        if not bool(all_ready.iloc[obs_idx]):
            continue
        raw_rank = _score_to_rank(float(state_scores[obs_idx]))
        raw_name = STATE_NAME_BY_RANK[raw_rank]
        base_conf = float(np.clip((float(state_scores[obs_idx]) + 1.0) / 6.0, 0.0, 1.0))
        if current_rank is None:
            current_rank = raw_rank
            obs_smoothed_rank[obs_idx] = current_rank
            obs_reason[obs_idx] = "INIT"
            obs_confidence[obs_idx] = base_conf
            continue

        if raw_rank < current_rank:
            if downgrade_confirm_weeks <= 1:
                current_rank = raw_rank
                downgrade_pending_rank = None
                downgrade_pending_count = 0
                pending_rank = None
                pending_count = 0
                obs_reason[obs_idx] = "DOWNGRADE_IMMEDIATE"
            else:
                if downgrade_pending_rank == raw_rank:
                    downgrade_pending_count += 1
                else:
                    downgrade_pending_rank = raw_rank
                    downgrade_pending_count = 1
                if downgrade_pending_count >= downgrade_confirm_weeks:
                    current_rank = raw_rank
                    obs_reason[obs_idx] = "DOWNGRADE_CONFIRMED"
                    downgrade_pending_rank = None
                    downgrade_pending_count = 0
                    pending_rank = None
                    pending_count = 0
                else:
                    obs_reason[obs_idx] = "DOWNGRADE_PENDING"
        elif raw_rank == current_rank:
            pending_rank = None
            pending_count = 0
            downgrade_pending_rank = None
            downgrade_pending_count = 0
            obs_reason[obs_idx] = "UNCHANGED"
        else:
            downgrade_pending_rank = None
            downgrade_pending_count = 0
            if pending_rank == raw_rank:
                pending_count += 1
            else:
                pending_rank = raw_rank
                pending_count = 1
            if pending_count >= upgrade_confirm_weeks:
                current_rank = raw_rank
                pending_rank = None
                pending_count = 0
                obs_reason[obs_idx] = "UPGRADE_CONFIRMED"
            else:
                obs_reason[obs_idx] = "UPGRADE_PENDING"

        obs_smoothed_rank[obs_idx] = current_rank
        obs_confidence[obs_idx] = base_conf
        if obs_reason[obs_idx] == "UPGRADE_PENDING":
            obs_confidence[obs_idx] = float(max(base_conf - 0.10, 0.0))
        elif obs_reason[obs_idx].startswith("DOWNGRADE"):
            obs_confidence[obs_idx] = float(max(base_conf - 0.05, 0.0))

    last_rank: int | None = None
    last_conf = 0.0
    last_obs_idx: int | None = None
    for idx in range(day_count):
        if idx in obs_smoothed_rank:
            last_rank = int(obs_smoothed_rank[idx])
            last_conf = float(obs_confidence.get(idx, 0.0))
            last_obs_idx = idx
            regime_transition_reason[idx] = str(obs_reason.get(idx, "UNCHANGED"))
        elif last_rank is not None:
            regime_transition_reason[idx] = "CARRY_FORWARD"

        if last_rank is not None:
            market_state_codes[idx] = np.int8(last_rank)
            state_name = STATE_NAME_BY_RANK[last_rank]
            market_state_names[idx] = state_name
            market_state_smoothed_names[idx] = state_name
            trade_mode_codes[idx], trade_mode_names[idx] = _trade_mode_for_rank(
                last_rank,
                risk_budget_mode=risk_budget_mode,
            )
            risk_budget_multipliers[idx] = _risk_budget_for_rank(
                last_rank,
                turn_weak_budget=turn_weak_budget,
                risk_budget_mode=risk_budget_mode,
            )
            regime_confidence[idx] = last_conf
        else:
            market_state_smoothed_names[idx] = ""

        if weekly_observation_flags[idx] and not regime_transition_reason[idx]:
            regime_transition_reason[idx] = "OBSERVATION_UNAVAILABLE"

    if len(legacy_market_state) == day_count:
        for idx in range(day_count):
            if bool(all_ready.iloc[idx]) and market_state_smoothed_names[idx]:
                continue
            fallback_active[idx] = True
            fallback_rank = _fallback_rank_from_legacy_state(int(legacy_market_state[idx]))
            fallback_name = STATE_NAME_BY_RANK[fallback_rank]
            market_state_codes[idx] = np.int8(fallback_rank)
            market_state_names[idx] = fallback_name
            if not str(market_state_raw_names[idx] or "").strip():
                market_state_raw_names[idx] = fallback_name
            if not str(market_state_smoothed_names[idx] or "").strip():
                market_state_smoothed_names[idx] = fallback_name
            trade_mode_codes[idx], trade_mode_names[idx] = _trade_mode_for_rank(
                fallback_rank,
                risk_budget_mode=risk_budget_mode,
            )
            risk_budget_multipliers[idx] = _risk_budget_for_rank(
                fallback_rank,
                turn_weak_budget=turn_weak_budget,
                risk_budget_mode=risk_budget_mode,
            )
            regime_confidence[idx] = float(np.clip(regime_confidence[idx], 0.0, 1.0))
            if not str(regime_transition_reason[idx] or "").strip():
                regime_transition_reason[idx] = "FALLBACK_MA200_LEGACY"

    current_duration = 0
    prev_name = ""
    for idx in range(day_count):
        name = str(market_state_names[idx] or "")
        if name and name == prev_name:
            current_duration += 1
        elif name:
            current_duration = 1
        else:
            current_duration = 0
        regime_duration_bars[idx] = np.int32(current_duration)
        prev_name = name

    return WeeklyFiveStateEvaluation(
        market_state_codes=market_state_codes,
        market_state_names=market_state_names,
        market_state_raw_names=market_state_raw_names,
        market_state_smoothed_names=market_state_smoothed_names,
        trade_mode_codes=trade_mode_codes,
        trade_mode_names=trade_mode_names,
        risk_budget_multipliers=risk_budget_multipliers,
        state_scores=state_scores,
        weekly_observation_flags=weekly_observation_flags,
        regime_confidence=regime_confidence,
        regime_duration_bars=regime_duration_bars,
        regime_transition_reason=regime_transition_reason,
        feature_availability=feature_availability,
        fallback_active=fallback_active,
    )
