from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.core.config.cn_a_governed_mainline import (
    canonical_state_5,
    coarse_state_from_state_5,
)
from backend.core.config.etf_beta_contract import (
    CN_ETF_BETA_ABSOLUTE_FILTER_MODE,
    CN_ETF_BETA_CORE_SYMBOLS,
    CN_ETF_BETA_FALLBACK_MODE,
    CN_ETF_BETA_REBALANCE_FREQUENCY,
    CN_ETF_BETA_RS_FAST_WEIGHT,
    CN_ETF_BETA_RS_FAST_WINDOW,
    CN_ETF_BETA_RS_MID_WEIGHT,
    CN_ETF_BETA_RS_MID_WINDOW,
    CN_ETF_BETA_RS_SLOW_WEIGHT,
    CN_ETF_BETA_RS_SLOW_WINDOW,
    CN_ETF_BETA_RULE_FAMILY,
    CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET,
    CN_ETF_BETA_VOL_TARGET_MAX_SCALE,
    CN_ETF_BETA_VOL_TARGET_MIN_SCALE,
    CN_ETF_BETA_VOL_TARGET_WINDOW,
    resolve_etf_beta_exposure_semantics as resolve_cn_etf_beta_exposure_semantics,
)
from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.breakout_signal_provider import (
    BreakoutTrendProvider,
    _build_legacy_market_filter_multipliers,
    _build_legacy_market_filter_state,
    _coerce_market_filter_cfg,
    _legacy_market_state_names,
    _legacy_trade_mode_names,
)
from backend.core.engine_vector.signal_provider import DayContext, DaySignals, ExitCounts

def _normalize_etf_symbol_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "." in text:
        code, venue = text.split(".", 1)
        code = code.strip()
        venue = venue.strip().lower()
        if code and venue in {"sh", "sse"}:
            return f"sh{code}"
        if code and venue in {"sz", "szse"}:
            return f"sz{code}"
    if len(text) > 2 and text[:2] in {"sh", "sz"}:
        return text
    return text


def _display_etf_symbol(value: Any) -> str:
    normalized = _normalize_etf_symbol_key(value)
    if len(normalized) > 2 and normalized[:2] in {"sh", "sz"} and normalized[2:].isdigit():
        return f"{normalized[2:]}.{normalized[:2].upper()}"
    text = str(value or "").strip().upper()
    return text


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_choice(value: Any, *, default: str, allowed: set[str]) -> str:
    text = _normalize_text(value).lower()
    if text in allowed:
        return text
    return default


def _normalize_symbol_map(value: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(value, dict):
        return out
    for key, raw in value.items():
        symbol = _display_etf_symbol(key).upper()
        text = _normalize_text(raw)
        if not symbol or not text:
            continue
        out[symbol] = text
    return out


def _normalize_symbol_pairs(value: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(value, dict):
        return out
    for key, raw in value.items():
        symbol = _display_etf_symbol(key).upper()
        replacement = _display_etf_symbol(raw).upper()
        if not symbol or not replacement:
            continue
        out[symbol] = replacement
    return out


def _absolute_filter_reason_codes(mode: str) -> list[str]:
    if mode == "positive_12m":
        return ["ABSOLUTE_RET12_PASS"]
    if mode == "ma200_and_positive_12m":
        return ["ABSOLUTE_MA200_PASS", "ABSOLUTE_RET12_PASS"]
    return ["ABSOLUTE_MA120_PASS"]


def _rebalance_selection_reason_code(frequency: str, *, rebalance_day: bool) -> str:
    mapping = {
        "weekly": ("WEEKLY_REBALANCE", "HOLD_UNTIL_REBALANCE"),
        "biweekly": ("BIWEEKLY_REBALANCE", "HOLD_UNTIL_REBALANCE"),
        "monthly": ("MONTHLY_REBALANCE", "HOLD_UNTIL_REBALANCE"),
    }
    on_rebalance, off_rebalance = mapping.get(str(frequency or "").strip().lower(), mapping["weekly"])
    return on_rebalance if rebalance_day else off_rebalance


def _selection_active_reason_code(frequency: str) -> str:
    mapping = {
        "weekly": "ETF_BETA_WEEKLY_SELECTION_ACTIVE",
        "biweekly": "ETF_BETA_BIWEEKLY_SELECTION_ACTIVE",
        "monthly": "ETF_BETA_MONTHLY_SELECTION_ACTIVE",
    }
    return mapping.get(str(frequency or "").strip().lower(), "ETF_BETA_WEEKLY_SELECTION_ACTIVE")


def _await_rebalance_reason_code(frequency: str) -> str:
    mapping = {
        "weekly": "ETF_BETA_AWAIT_WEEKLY_REBALANCE",
        "biweekly": "ETF_BETA_AWAIT_BIWEEKLY_REBALANCE",
        "monthly": "ETF_BETA_AWAIT_MONTHLY_REBALANCE",
    }
    return mapping.get(str(frequency or "").strip().lower(), "ETF_BETA_AWAIT_WEEKLY_REBALANCE")


def _entry_reason_code(frequency: str) -> str:
    mapping = {
        "weekly": "ETF_BETA_WEEKLY_RS",
        "biweekly": "ETF_BETA_BIWEEKLY_RS",
        "monthly": "ETF_BETA_MONTHLY_RS",
    }
    return mapping.get(str(frequency or "").strip().lower(), "ETF_BETA_WEEKLY_RS")


_FORMAL_CORE_SCOPE = tuple(_normalize_etf_symbol_key(symbol) for symbol in CN_ETF_BETA_CORE_SYMBOLS)
_STATE_SLOT_CAPS = {
    "BULL": 2,
    "TRANS_UP": 2,
    "LIGHT": 1,
    "TRANS_DOWN": 0,
    "RISK_OFF": 0,
}

def _sequence_payload(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _safe_return(close_now: float, close_prev: float) -> float | None:
    if close_now != close_now or close_prev != close_prev:
        return None
    if close_prev <= 0.0:
        return None
    return float(close_now / close_prev - 1.0)


def _realized_vol_annualized(daily_returns: np.ndarray, row_idx: int, window: int) -> float | None:
    if row_idx <= 0 or window <= 1:
        return None
    start_idx = max(0, row_idx - int(window) + 1)
    sample = np.asarray(daily_returns[start_idx : row_idx + 1], dtype=float)
    sample = sample[np.isfinite(sample)]
    if sample.size < max(3, int(window) // 2):
        return None
    vol = float(np.std(sample, ddof=1)) * float(np.sqrt(252.0))
    if not np.isfinite(vol) or vol <= 0.0:
        return None
    return vol


def _coerce_day(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, np.datetime64):
        return date.fromisoformat(np.datetime_as_string(value, unit="D"))
    return date.fromisoformat(str(value)[:10])


def _rebalance_flags(trading_days: list[Any], *, frequency: str) -> np.ndarray:
    flags = np.zeros(len(trading_days), dtype=bool)
    if not trading_days:
        return flags
    frequency_text = str(frequency or "").strip().lower()
    if frequency_text == "monthly":
        for idx, day in enumerate(trading_days):
            current_day = _coerce_day(day)
            if idx == len(trading_days) - 1:
                flags[idx] = True
                continue
            next_day = _coerce_day(trading_days[idx + 1])
            flags[idx] = (current_day.year, current_day.month) != (next_day.year, next_day.month)
        return flags
    bucket_divisor = 2 if frequency_text == "biweekly" else 1
    for idx, day in enumerate(trading_days):
        current_day = _coerce_day(day)
        if idx == len(trading_days) - 1:
            flags[idx] = True
            continue
        next_day = _coerce_day(trading_days[idx + 1])
        current_iso = current_day.isocalendar()
        next_iso = next_day.isocalendar()
        current_bucket = (current_iso[0], max(current_iso[1] - 1, 0) // bucket_divisor)
        next_bucket = (next_iso[0], max(next_iso[1] - 1, 0) // bucket_divisor)
        flags[idx] = current_bucket != next_bucket
    return flags


def _rank_score(values: dict[int, float]) -> dict[int, float]:
    if not values:
        return {}
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    total = max(len(ordered), 1)
    return {col: float(rank) / float(total) for rank, (col, _value) in enumerate(ordered, start=1)}


def _array_item(arr: Any, idx: int) -> Any:
    if isinstance(arr, np.ndarray) and idx < len(arr):
        return arr[idx]
    return None


def _has_text_payload(arr: Any) -> bool:
    if not isinstance(arr, np.ndarray) or len(arr) == 0:
        return False
    for value in arr.tolist():
        if str(value or "").strip():
            return True
    return False


class CNETFBetaSignalProvider(BreakoutTrendProvider):
    def __init__(self) -> None:
        super().__init__()
        self._etf_beta_slot_cap_arr: np.ndarray = np.array([], dtype=np.int32)
        self._etf_beta_rebalance_flag_arr: np.ndarray = np.array([], dtype=bool)
        self._etf_beta_formal_scope_symbols: list[str] = []
        self._etf_beta_eligible_symbols_arr: np.ndarray = np.array([], dtype=object)
        self._etf_beta_selected_symbols_arr: np.ndarray = np.array([], dtype=object)
        self._etf_beta_selection_reason_codes_arr: np.ndarray = np.array([], dtype=object)
        self._etf_beta_runtime_reason_codes_arr: np.ndarray = np.array([], dtype=object)
        self._market_state_name_map: dict[date, str] = {}
        self._trade_mode_name_map: dict[date, str] = {}
        self._etf_beta_rule_family = CN_ETF_BETA_RULE_FAMILY
        self._etf_beta_template_id = ""
        self._etf_beta_template_asset_pool_version = ""
        self._etf_beta_template_role_map: dict[str, str] = {}
        self._etf_beta_template_proxy_map: dict[str, str] = {}
        self._etf_beta_template_target_formal_symbols: list[str] = []
        self._etf_beta_proxy_replacement_mode = "none"
        self._etf_beta_formal_replacement_pairs: dict[str, str] = {}
        self._etf_beta_core_slot_symbols: list[str] = []
        self._etf_beta_growth_slot_symbols: list[str] = []
        self._etf_beta_growth_seat_symbol = ""
        self._etf_beta_rebalance_frequency = CN_ETF_BETA_REBALANCE_FREQUENCY
        self._etf_beta_absolute_filter_mode = CN_ETF_BETA_ABSOLUTE_FILTER_MODE
        self._etf_beta_fallback_mode = CN_ETF_BETA_FALLBACK_MODE
        self._etf_beta_fallback_symbol = ""
        self._etf_beta_rs_fast_window = CN_ETF_BETA_RS_FAST_WINDOW
        self._etf_beta_rs_mid_window: int | None = None
        self._etf_beta_rs_slow_window = CN_ETF_BETA_RS_SLOW_WINDOW
        self._etf_beta_rs_fast_weight = CN_ETF_BETA_RS_FAST_WEIGHT
        self._etf_beta_rs_mid_weight = CN_ETF_BETA_RS_MID_WEIGHT
        self._etf_beta_rs_slow_weight = CN_ETF_BETA_RS_SLOW_WEIGHT
        self._etf_beta_max_selected_symbols: int | None = None
        self._etf_beta_vol_target_window = CN_ETF_BETA_VOL_TARGET_WINDOW
        self._etf_beta_vol_target_annualized_target = CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET
        self._etf_beta_vol_target_min_scale = CN_ETF_BETA_VOL_TARGET_MIN_SCALE
        self._etf_beta_vol_target_max_scale = CN_ETF_BETA_VOL_TARGET_MAX_SCALE
        self._etf_beta_vol_target_info_arr: np.ndarray = np.array([], dtype=object)
        self._etf_beta_target_exposure_arr: np.ndarray = np.array([], dtype=float)
        self._etf_beta_target_exposure_source_arr: np.ndarray = np.array([], dtype=object)
        self._etf_beta_min_deployable_exposure_arr: np.ndarray = np.array([], dtype=float)
        self._etf_beta_min_deployable_exposure_source_arr: np.ndarray = np.array([], dtype=object)
        self._etf_beta_target_selected_count_arr: np.ndarray = np.array([], dtype=np.int32)
        self._etf_beta_target_exposure_per_symbol_arr: np.ndarray = np.array([], dtype=float)
        self._etf_beta_target_actual_exposure_arr: np.ndarray = np.array([], dtype=float)
        self._etf_beta_target_deployability_gap_arr: np.ndarray = np.array([], dtype=float)
        self._etf_beta_fallback_allowed_arr: np.ndarray = np.array([], dtype=bool)
        self._etf_beta_core_slot_selected_symbol_arr: np.ndarray = np.array([], dtype=object)
        self._etf_beta_growth_slot_selected_symbol_arr: np.ndarray = np.array([], dtype=object)
        self._etf_beta_slot_selection_reason_codes_arr: np.ndarray = np.array([], dtype=object)
        self._etf_beta_slot_under_deploy_reason_codes_arr: np.ndarray = np.array([], dtype=object)
        self._etf_beta_core_slot_target_exposure_arr: np.ndarray = np.array([], dtype=float)
        self._etf_beta_growth_slot_target_exposure_arr: np.ndarray = np.array([], dtype=float)
        self._etf_beta_core_slot_target_actual_exposure_arr: np.ndarray = np.array([], dtype=float)
        self._etf_beta_growth_slot_target_actual_exposure_arr: np.ndarray = np.array([], dtype=float)

    def precompute(
        self,
        *,
        history: Any,
        benchmark: Any,
        raw_history: Any,
        trading_days: list[date],
        strategy: Any,
        **kwargs: Any,
    ) -> None:
        super().precompute(
            history=history,
            benchmark=benchmark,
            raw_history=raw_history,
            trading_days=trading_days,
            strategy=strategy,
            **kwargs,
        )
        mx = self._mx
        feats = self._feats
        dates = list(mx.dates)
        symbols = [_normalize_etf_symbol_key(symbol) for symbol in list(mx.symbols)]
        display_symbols = [_display_etf_symbol(symbol) for symbol in list(mx.symbols)]
        governed_a_share = dict(kwargs.get("governed_a_share") or {}) if isinstance(kwargs.get("governed_a_share"), dict) else {}
        etf_beta_cfg = dict(governed_a_share.get("etf_beta") or {})
        self._etf_beta_template_id = _normalize_text(etf_beta_cfg.get("template_id"))
        self._etf_beta_template_asset_pool_version = _normalize_text(etf_beta_cfg.get("template_asset_pool_version"))
        self._etf_beta_template_role_map = _normalize_symbol_map(etf_beta_cfg.get("template_role_map"))
        self._etf_beta_template_proxy_map = _normalize_symbol_map(etf_beta_cfg.get("template_proxy_map"))
        self._etf_beta_template_target_formal_symbols = [
            _display_etf_symbol(item).upper()
            for item in list(etf_beta_cfg.get("template_target_formal_symbols") or [])
            if _normalize_text(item)
        ]
        self._etf_beta_proxy_replacement_mode = _normalize_choice(
            etf_beta_cfg.get("proxy_replacement_mode"),
            default="none",
            allowed={"none", "csi1000_proxy_only", "dividend_proxy_only", "full_standard_swap"},
        )
        self._etf_beta_formal_replacement_pairs = _normalize_symbol_pairs(etf_beta_cfg.get("formal_replacement_pairs"))
        self._etf_beta_core_slot_symbols = [
            _display_etf_symbol(item).upper()
            for item in list(etf_beta_cfg.get("core_slot_symbols") or [])
            if _normalize_text(item)
        ]
        self._etf_beta_growth_slot_symbols = [
            _display_etf_symbol(item).upper()
            for item in list(etf_beta_cfg.get("growth_slot_symbols") or [])
            if _normalize_text(item)
        ]
        self._etf_beta_growth_seat_symbol = (
            _display_etf_symbol(etf_beta_cfg.get("growth_seat_symbol")).upper()
            if _normalize_text(etf_beta_cfg.get("growth_seat_symbol"))
            else ""
        )
        self._etf_beta_rule_family = _normalize_choice(
            etf_beta_cfg.get("research_rule_family"),
            default=CN_ETF_BETA_RULE_FAMILY,
            allowed={
                "etf_beta_v1_control",
                "dual_momentum_basic",
                "dual_momentum_vol_target",
                "broad_based_rotation_template_a",
                "broad_based_rotation_template_a0_core_satellite_v2",
            },
        )
        self._etf_beta_rebalance_frequency = _normalize_choice(
            etf_beta_cfg.get("rebalance_frequency"),
            default=CN_ETF_BETA_REBALANCE_FREQUENCY,
            allowed={"weekly", "biweekly", "monthly"},
        )
        self._etf_beta_absolute_filter_mode = _normalize_choice(
            etf_beta_cfg.get("absolute_filter_mode"),
            default=CN_ETF_BETA_ABSOLUTE_FILTER_MODE,
            allowed={"ma120", "positive_12m", "ma200_and_positive_12m"},
        )
        self._etf_beta_fallback_mode = _normalize_choice(
            etf_beta_cfg.get("fallback_mode"),
            default=CN_ETF_BETA_FALLBACK_MODE,
            allowed={"none", "cash", "single_symbol"},
        )
        self._etf_beta_fallback_symbol = _normalize_etf_symbol_key(etf_beta_cfg.get("fallback_symbol"))
        self._etf_beta_rs_fast_window = max(2, int(etf_beta_cfg.get("relative_strength_fast_window") or CN_ETF_BETA_RS_FAST_WINDOW))
        mid_window = int(etf_beta_cfg.get("relative_strength_mid_window") or CN_ETF_BETA_RS_MID_WINDOW or 0)
        self._etf_beta_rs_mid_window = max(2, mid_window) if mid_window >= 2 else None
        self._etf_beta_rs_slow_window = max(2, int(etf_beta_cfg.get("relative_strength_slow_window") or CN_ETF_BETA_RS_SLOW_WINDOW))
        fast_weight = float(etf_beta_cfg.get("relative_strength_fast_weight") or CN_ETF_BETA_RS_FAST_WEIGHT)
        mid_weight = float(etf_beta_cfg.get("relative_strength_mid_weight") or CN_ETF_BETA_RS_MID_WEIGHT)
        slow_weight = float(etf_beta_cfg.get("relative_strength_slow_weight") or CN_ETF_BETA_RS_SLOW_WEIGHT)
        if fast_weight < 0.0:
            fast_weight = 0.0
        if mid_weight < 0.0:
            mid_weight = 0.0
        if slow_weight < 0.0:
            slow_weight = 0.0
        if self._etf_beta_rs_mid_window is None:
            mid_weight = 0.0
        if fast_weight + mid_weight + slow_weight <= 1e-12:
            fast_weight = CN_ETF_BETA_RS_FAST_WEIGHT
            mid_weight = CN_ETF_BETA_RS_MID_WEIGHT
            slow_weight = CN_ETF_BETA_RS_SLOW_WEIGHT
        self._etf_beta_rs_fast_weight = fast_weight
        self._etf_beta_rs_mid_weight = mid_weight
        self._etf_beta_rs_slow_weight = slow_weight
        max_selected_symbols = int(etf_beta_cfg.get("max_selected_symbols") or 0)
        self._etf_beta_max_selected_symbols = max_selected_symbols if max_selected_symbols > 0 else None
        self._etf_beta_vol_target_window = max(
            5,
            int(etf_beta_cfg.get("vol_target_window") or CN_ETF_BETA_VOL_TARGET_WINDOW),
        )
        target_vol = float(etf_beta_cfg.get("vol_target_annualized_target") or CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET)
        if target_vol <= 0.0:
            target_vol = CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET
        self._etf_beta_vol_target_annualized_target = float(target_vol)
        min_scale = float(etf_beta_cfg.get("vol_target_min_scale") or CN_ETF_BETA_VOL_TARGET_MIN_SCALE)
        max_scale = float(etf_beta_cfg.get("vol_target_max_scale") or CN_ETF_BETA_VOL_TARGET_MAX_SCALE)
        min_scale = max(0.0, min(min_scale, 1.0))
        max_scale = max(0.0, min(max_scale, 1.0))
        if min_scale > max_scale:
            min_scale, max_scale = max_scale, min_scale
        self._etf_beta_vol_target_min_scale = float(min_scale)
        self._etf_beta_vol_target_max_scale = float(max_scale)
        configured_core_scope_source = (
            list(self._etf_beta_core_slot_symbols) + list(self._etf_beta_growth_slot_symbols)
            if (self._etf_beta_core_slot_symbols or self._etf_beta_growth_slot_symbols)
            else list(etf_beta_cfg.get("core_beta_symbols") or CN_ETF_BETA_CORE_SYMBOLS)
        )
        configured_core_scope = [
            _normalize_etf_symbol_key(symbol)
            for symbol in configured_core_scope_source
            if _normalize_etf_symbol_key(symbol)
        ]
        scope_set = set(configured_core_scope or _FORMAL_CORE_SCOPE)
        scope_cols = [idx for idx, symbol in enumerate(symbols) if symbol in scope_set]
        self._etf_beta_formal_scope_symbols = [display_symbols[idx] for idx in scope_cols]
        day_count = len(dates)

        source_state_name_arr = getattr(self, "_market_state_name_arr", None)
        source_trade_mode_name_arr = getattr(self, "_trade_mode_name_arr", None)
        source_raw_state_name_arr = getattr(self, "_market_state_raw_name_arr", None)
        source_smoothed_state_name_arr = getattr(self, "_market_state_smoothed_name_arr", None)
        source_base_state_arr = getattr(self, "_base_state_5_arr", None)
        source_effective_state_arr = getattr(self, "_effective_state_5_arr", None)
        source_risk_budget_arr = getattr(self, "_regime_risk_budget_multiplier_arr", None)
        market_filter_cfg = _coerce_market_filter_cfg(kwargs.get("market_filter_cfg"))

        if not _has_text_payload(source_effective_state_arr):
            legacy_state_arr, legacy_trade_mode_arr = _build_legacy_market_filter_state(
                benchmark=benchmark,
                dates=np.array(mx.dates),
                market_filter_cfg=market_filter_cfg,
            )
            legacy_state_names = _legacy_market_state_names(np.asarray(legacy_state_arr, dtype=np.int8))
            legacy_trade_mode_names = _legacy_trade_mode_names(np.asarray(legacy_trade_mode_arr, dtype=np.int8))
            legacy_budget_arr = _build_legacy_market_filter_multipliers(
                market_state=np.asarray(legacy_state_arr, dtype=np.int8),
                trade_mode=np.asarray(legacy_trade_mode_arr, dtype=np.int8),
                market_filter_cfg=market_filter_cfg,
            )

            self._market_state = np.asarray(legacy_state_arr, dtype=np.int8)
            self._trade_mode = np.asarray(legacy_trade_mode_arr, dtype=np.int8)
            self._market_state_name_arr = np.asarray(legacy_state_names, dtype=object)
            self._trade_mode_name_arr = np.asarray(legacy_trade_mode_names, dtype=object)
            self._market_state_raw_name_arr = np.asarray(legacy_state_names, dtype=object)
            self._market_state_smoothed_name_arr = np.asarray(legacy_state_names, dtype=object)
            self._market_state_score_arr = np.full(day_count, np.nan, dtype=float)
            self._risk_budget_multiplier_arr = np.asarray(legacy_budget_arr, dtype=float)
            self._regime_risk_budget_multiplier_arr = np.asarray(legacy_budget_arr, dtype=float)
            self._weekly_observation_flag_arr = np.zeros(day_count, dtype=bool)
            source_state_name_arr = self._market_state_name_arr
            source_trade_mode_name_arr = self._trade_mode_name_arr
            source_raw_state_name_arr = self._market_state_raw_name_arr
            source_smoothed_state_name_arr = self._market_state_smoothed_name_arr
            source_base_state_arr = self._base_state_5_arr
            source_effective_state_arr = self._effective_state_5_arr
            source_risk_budget_arr = self._regime_risk_budget_multiplier_arr

        base_state_5_arr = np.empty(day_count, dtype=object)
        effective_state_5_arr = np.empty(day_count, dtype=object)
        coarse_state_arr = np.empty(day_count, dtype=object)
        effective_coarse_state_arr = np.empty(day_count, dtype=object)
        for idx in range(day_count):
            source_trade_mode = _array_item(source_trade_mode_name_arr, idx)
            raw_base = (
                _array_item(source_base_state_arr, idx)
                or _array_item(source_raw_state_name_arr, idx)
                or _array_item(source_state_name_arr, idx)
            )
            raw_effective = (
                _array_item(source_effective_state_arr, idx)
                or _array_item(source_smoothed_state_name_arr, idx)
                or _array_item(source_state_name_arr, idx)
            )
            base_state_text = canonical_state_5(raw_base, trade_mode=source_trade_mode)
            effective_state_text = canonical_state_5(raw_effective, trade_mode=source_trade_mode) or base_state_text
            base_state_5_arr[idx] = base_state_text
            effective_state_5_arr[idx] = effective_state_text
            coarse_state_arr[idx] = coarse_state_from_state_5(base_state_text)
            effective_coarse_state_arr[idx] = coarse_state_from_state_5(effective_state_text)

        self._base_state_5_arr = base_state_5_arr
        self._effective_state_5_arr = effective_state_5_arr
        self._coarse_state_arr = coarse_state_arr
        self._effective_coarse_state_arr = effective_coarse_state_arr
        if not isinstance(source_risk_budget_arr, np.ndarray) or len(source_risk_budget_arr) != day_count:
            source_risk_budget_arr = np.array(getattr(self, "_risk_budget_multiplier_arr", np.array([], dtype=float)), dtype=float)
        if not isinstance(source_risk_budget_arr, np.ndarray) or len(source_risk_budget_arr) != day_count:
            source_risk_budget_arr = np.ones(day_count, dtype=float)
        self._regime_risk_budget_multiplier_arr = np.array(source_risk_budget_arr, dtype=float)
        if not isinstance(getattr(self, "_reason_codes_arr", None), np.ndarray) or len(
            getattr(self, "_reason_codes_arr", np.array([], dtype=object))
        ) != day_count:
            reason_codes_arr = np.empty(day_count, dtype=object)
            for idx in range(day_count):
                reason_codes_arr[idx] = []
            self._reason_codes_arr = reason_codes_arr
        if not isinstance(getattr(self, "_block_scores_arr", None), np.ndarray) or len(
            getattr(self, "_block_scores_arr", np.array([], dtype=object))
        ) != day_count:
            block_scores_arr = np.empty(day_count, dtype=object)
            for idx in range(day_count):
                block_scores_arr[idx] = {}
            self._block_scores_arr = block_scores_arr
        if not isinstance(getattr(self, "_subscores_arr", None), np.ndarray) or len(
            getattr(self, "_subscores_arr", np.array([], dtype=object))
        ) != day_count:
            subscores_arr = np.empty(day_count, dtype=object)
            for idx in range(day_count):
                subscores_arr[idx] = {}
            self._subscores_arr = subscores_arr
        if not isinstance(getattr(self, "_manual_override_arr", None), np.ndarray) or len(
            getattr(self, "_manual_override_arr", np.array([], dtype=object))
        ) != day_count:
            manual_override_arr = np.empty(day_count, dtype=object)
            for idx in range(day_count):
                manual_override_arr[idx] = {"active": False, "reason": None, "scope": None, "actor": None}
            self._manual_override_arr = manual_override_arr
        if not isinstance(getattr(self, "_state_stability_metrics_arr", None), np.ndarray) or len(
            getattr(self, "_state_stability_metrics_arr", np.array([], dtype=object))
        ) != day_count:
            stability_arr = np.empty(day_count, dtype=object)
            for idx in range(day_count):
                stability_arr[idx] = {}
            self._state_stability_metrics_arr = stability_arr

        state_5_arr = np.array(
            [
                str(self._effective_state_5_arr[idx] or "")
                for idx in range(day_count)
            ],
            dtype=object,
        )
        self._market_state_name_arr = state_5_arr.copy()
        self._market_state_smoothed_name_arr = state_5_arr.copy()
        trade_mode_arr = np.array(
            [
                "TREND_MAIN"
                if _STATE_SLOT_CAPS.get(str(state).strip().upper(), 0) >= 2
                else "TREND_LIGHT"
                if _STATE_SLOT_CAPS.get(str(state).strip().upper(), 0) == 1
                else "NO_TRADE"
                for state in state_5_arr
            ],
            dtype=object,
        )
        self._trade_mode_name_arr = trade_mode_arr
        self._market_state_name_map = {day: str(state_5_arr[idx] or "") for idx, day in enumerate(dates)}
        self._trade_mode_name_map = {day: str(trade_mode_arr[idx] or "") for idx, day in enumerate(dates)}
        self._etf_beta_rebalance_flag_arr = _rebalance_flags(dates, frequency=self._etf_beta_rebalance_frequency)
        self._etf_beta_slot_cap_arr = np.array(
            [_STATE_SLOT_CAPS.get(str(state).strip().upper(), 0) for state in state_5_arr],
            dtype=np.int32,
        )

        close = np.asarray(mx.close, dtype=float)
        ma120 = np.asarray(feats.trend_fast_ma, dtype=float)
        ma200 = np.full_like(close, np.nan, dtype=float)
        for col_idx in scope_cols:
            ma200[:, col_idx] = pd.Series(close[:, col_idx]).rolling(200, min_periods=200).mean().to_numpy(dtype=float)
        score_windows: list[tuple[int, float]] = [
            (int(self._etf_beta_rs_slow_window), float(self._etf_beta_rs_slow_weight)),
        ]
        if self._etf_beta_rs_mid_window is not None and float(self._etf_beta_rs_mid_weight) > 1e-12:
            score_windows.append((int(self._etf_beta_rs_mid_window), float(self._etf_beta_rs_mid_weight)))
        score_windows.append((int(self._etf_beta_rs_fast_window), float(self._etf_beta_rs_fast_weight)))
        windows_needed = {window for window, _weight in score_windows}
        if self._etf_beta_absolute_filter_mode in {"positive_12m", "ma200_and_positive_12m"}:
            windows_needed.add(252)
        returns_by_window = {
            window: np.full_like(close, np.nan, dtype=float)
            for window in sorted(windows_needed)
        }
        for row_idx in range(day_count):
            for col_idx in scope_cols:
                close_now = float(close[row_idx, col_idx])
                for window, arr in returns_by_window.items():
                    if row_idx >= window:
                        arr[row_idx, col_idx] = _safe_return(close_now, float(close[row_idx - window, col_idx]))
        daily_returns = np.full_like(close, np.nan, dtype=float)
        for row_idx in range(1, day_count):
            for col_idx in scope_cols:
                daily_returns[row_idx, col_idx] = _safe_return(float(close[row_idx, col_idx]), float(close[row_idx - 1, col_idx]))

        eligible_rows: list[list[str]] = []
        selected_rows: list[list[str]] = []
        selection_reason_rows: list[dict[str, list[str]]] = []
        runtime_reason_rows: list[list[str]] = []
        vol_target_rows: list[dict[str, Any]] = []
        target_exposure_rows = np.full(day_count, np.nan, dtype=float)
        target_exposure_source_rows = np.full(day_count, "", dtype=object)
        min_deployable_exposure_rows = np.full(day_count, np.nan, dtype=float)
        min_deployable_exposure_source_rows = np.full(day_count, "", dtype=object)
        target_selected_count_rows = np.zeros(day_count, dtype=np.int32)
        target_exposure_per_symbol_rows = np.full(day_count, np.nan, dtype=float)
        target_actual_exposure_rows = np.full(day_count, np.nan, dtype=float)
        target_deployability_gap_rows = np.full(day_count, np.nan, dtype=float)
        fallback_allowed_rows = np.zeros(day_count, dtype=bool)
        core_slot_selected_rows: list[str | None] = [None] * day_count
        growth_slot_selected_rows: list[str | None] = [None] * day_count
        slot_selection_reason_rows: list[dict[str, list[str]]] = [{} for _ in range(day_count)]
        slot_under_deploy_reason_rows: list[dict[str, list[str]]] = [{} for _ in range(day_count)]
        core_slot_target_exposure_rows = np.full(day_count, np.nan, dtype=float)
        growth_slot_target_exposure_rows = np.full(day_count, np.nan, dtype=float)
        core_slot_target_actual_exposure_rows = np.full(day_count, np.nan, dtype=float)
        growth_slot_target_actual_exposure_rows = np.full(day_count, np.nan, dtype=float)
        for row_idx in range(day_count):
            slot_cap = int(self._etf_beta_slot_cap_arr[row_idx]) if row_idx < len(self._etf_beta_slot_cap_arr) else 0
            rebalance_day = bool(self._etf_beta_rebalance_flag_arr[row_idx]) if row_idx < len(self._etf_beta_rebalance_flag_arr) else False
            eligible_scores_by_window: dict[int, dict[int, float]] = {window: {} for window, _weight in score_windows}
            for col_idx in scope_cols:
                close_now = float(close[row_idx, col_idx])
                ma120_now = float(ma120[row_idx, col_idx])
                ma200_now = float(ma200[row_idx, col_idx])
                if close_now != close_now or ma120_now != ma120_now:
                    continue
                window_returns: dict[int, float] = {}
                has_all_returns = True
                for window, _weight in score_windows:
                    value = float(returns_by_window[window][row_idx, col_idx])
                    if value != value:
                        has_all_returns = False
                        break
                    window_returns[int(window)] = float(value)
                if not has_all_returns:
                    continue
                absolute_pass = False
                if self._etf_beta_absolute_filter_mode == "positive_12m":
                    ret12 = float(returns_by_window[252][row_idx, col_idx])
                    absolute_pass = ret12 == ret12 and ret12 > 0.0
                elif self._etf_beta_absolute_filter_mode == "ma200_and_positive_12m":
                    ret12 = float(returns_by_window[252][row_idx, col_idx])
                    absolute_pass = ma200_now == ma200_now and close_now > ma200_now and ret12 == ret12 and ret12 > 0.0
                else:
                    absolute_pass = close_now > ma120_now
                if not absolute_pass:
                    continue
                for window, _weight in score_windows:
                    eligible_scores_by_window[int(window)][col_idx] = float(window_returns[int(window)])

            primary_window = int(score_windows[0][0])
            eligible_cols = sorted(eligible_scores_by_window[primary_window].keys(), key=lambda col: symbols[col])
            ranks_by_window = {
                int(window): _rank_score(eligible_scores_by_window[int(window)])
                for window, _weight in score_windows
            }
            combined_scores = {
                col_idx: sum(
                    float(weight) * float(ranks_by_window[int(window)].get(col_idx, 0.0))
                    for window, weight in score_windows
                )
                for col_idx in eligible_cols
            }
            ranked_cols = sorted(
                eligible_cols,
                key=lambda col_idx: (
                    -float(combined_scores.get(col_idx, 0.0)),
                    *[
                        -float(eligible_scores_by_window[int(window)].get(col_idx, float("-inf")))
                        for window, _weight in score_windows
                    ],
                    symbols[col_idx],
                ),
            )
            selected_cap = int(slot_cap)
            if self._etf_beta_max_selected_symbols is not None:
                selected_cap = min(selected_cap, int(self._etf_beta_max_selected_symbols))
            exposure_semantics = resolve_cn_etf_beta_exposure_semantics(
                etf_beta_contract=etf_beta_cfg,
                effective_state_5=state_5_arr[row_idx],
                slot_cap=selected_cap,
                target_selected_count=selected_cap,
            )
            target_exposure = (
                float(exposure_semantics.get("target_exposure"))
                if exposure_semantics.get("target_exposure") is not None
                else None
            )
            target_exposure_source = str(exposure_semantics.get("target_exposure_source") or "").strip()
            min_deployable_exposure = (
                float(exposure_semantics.get("min_deployable_exposure"))
                if exposure_semantics.get("min_deployable_exposure") is not None
                else None
            )
            min_deployable_exposure_source = str(exposure_semantics.get("min_deployable_exposure_source") or "").strip()
            target_selected_count = int(exposure_semantics.get("target_selected_count") or max(selected_cap, 1))
            if target_selected_count <= 0:
                target_selected_count = max(selected_cap, 1)
            target_exposure_per_symbol = (
                float(target_exposure) / float(max(target_selected_count, 1))
                if target_exposure is not None
                else None
            )
            fallback_allowed = bool(exposure_semantics.get("fallback_allowed", False))
            is_a0_core_satellite_v2 = self._etf_beta_rule_family == "broad_based_rotation_template_a0_core_satellite_v2"
            core_slot_display_symbols = (
                list(self._etf_beta_core_slot_symbols)
                if self._etf_beta_core_slot_symbols
                else [
                    symbol.upper()
                    for symbol in display_symbols
                    if symbol.upper() not in set(self._etf_beta_growth_slot_symbols)
                    and symbol.upper() != self._etf_beta_growth_seat_symbol
                ]
            )
            growth_slot_display_symbols = (
                list(self._etf_beta_growth_slot_symbols)
                if self._etf_beta_growth_slot_symbols
                else [self._etf_beta_growth_seat_symbol] if self._etf_beta_growth_seat_symbol else []
            )
            core_slot_set = {symbol.upper() for symbol in core_slot_display_symbols if symbol}
            growth_slot_set = {symbol.upper() for symbol in growth_slot_display_symbols if symbol}
            core_slot_selected_col: int | None = None
            growth_slot_selected_col: int | None = None
            slot_selection_reason_codes: dict[str, list[str]] = {}
            slot_under_deploy_reason_codes: dict[str, list[str]] = {}
            if is_a0_core_satellite_v2:
                core_ranked_cols = [col_idx for col_idx in ranked_cols if display_symbols[col_idx].upper() in core_slot_set]
                growth_ranked_cols = [col_idx for col_idx in ranked_cols if display_symbols[col_idx].upper() in growth_slot_set]
                slot_under_deploy_reason_codes["core_slot"] = []
                slot_under_deploy_reason_codes["growth_slot"] = []
                if selected_cap <= 0:
                    slot_under_deploy_reason_codes["core_slot"].append("ETF_BETA_CORE_SLOT_SUPPRESSED_BY_SLOT_CAP")
                    slot_under_deploy_reason_codes["growth_slot"].append("ETF_BETA_GROWTH_SLOT_SUPPRESSED_BY_SLOT_CAP")
                else:
                    if core_ranked_cols:
                        core_slot_selected_col = core_ranked_cols[0]
                    else:
                        slot_under_deploy_reason_codes["core_slot"].append("ETF_BETA_CORE_SLOT_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER")
                    if selected_cap >= 2:
                        for col_idx in growth_ranked_cols:
                            if core_slot_selected_col is not None and col_idx == core_slot_selected_col:
                                continue
                            growth_slot_selected_col = col_idx
                            break
                        if growth_slot_selected_col is None:
                            slot_under_deploy_reason_codes["growth_slot"].append("ETF_BETA_GROWTH_SLOT_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER")
                    else:
                        slot_under_deploy_reason_codes["growth_slot"].append("ETF_BETA_GROWTH_SLOT_SUPPRESSED_BY_SLOT_CAP")
                selected_cols = []
                if core_slot_selected_col is not None:
                    selected_cols.append(core_slot_selected_col)
                if growth_slot_selected_col is not None and growth_slot_selected_col not in selected_cols:
                    selected_cols.append(growth_slot_selected_col)
                if core_slot_selected_col is not None:
                    core_symbol = display_symbols[core_slot_selected_col].upper()
                    slot_selection_reason_codes["core_slot"] = [
                        "SLOT::CORE_SLOT",
                        f"SELECTED::{core_symbol}",
                        f"STATE::{str(state_5_arr[row_idx]).upper()}",
                        f"REBALANCE::{self._etf_beta_rebalance_frequency.upper()}",
                    ]
                if growth_slot_selected_col is not None:
                    growth_symbol = display_symbols[growth_slot_selected_col].upper()
                    slot_selection_reason_codes["growth_slot"] = [
                        "SLOT::GROWTH_SLOT",
                        f"SELECTED::{growth_symbol}",
                        f"STATE::{str(state_5_arr[row_idx]).upper()}",
                        f"REBALANCE::{self._etf_beta_rebalance_frequency.upper()}",
                    ]
            else:
                selected_cols = ranked_cols[:selected_cap] if selected_cap > 0 else []

            core_slot_target_exposure = (
                float(target_exposure_per_symbol)
                if is_a0_core_satellite_v2 and selected_cap >= 1 and target_exposure_per_symbol is not None
                else None
            )
            growth_slot_target_exposure = (
                float(target_exposure_per_symbol)
                if is_a0_core_satellite_v2 and selected_cap >= 2 and target_exposure_per_symbol is not None
                else None
            )
            selection_reason_codes = {
                display_symbols[col_idx]: [
                    "ETF_BETA_CORE_SCOPE",
                    *list(_absolute_filter_reason_codes(self._etf_beta_absolute_filter_mode)),
                    *[f"RS{int(window)}_RANK_PASS" for window, _weight in score_windows],
                    f"STATE::{str(state_5_arr[row_idx]).upper()}",
                    f"RULE_FAMILY::{self._etf_beta_rule_family.upper()}",
                    f"REBALANCE::{self._etf_beta_rebalance_frequency.upper()}",
                    _rebalance_selection_reason_code(self._etf_beta_rebalance_frequency, rebalance_day=rebalance_day),
                ]
                for col_idx in selected_cols
            }
            for symbol_text, codes in selection_reason_codes.items():
                role_text = self._etf_beta_template_role_map.get(symbol_text.upper())
                proxy_text = self._etf_beta_template_proxy_map.get(symbol_text.upper())
                if self._etf_beta_template_id:
                    codes.append(f"TEMPLATE::{self._etf_beta_template_id.upper()}")
                if self._etf_beta_template_asset_pool_version:
                    codes.append(f"POOL::{self._etf_beta_template_asset_pool_version.upper()}")
                if role_text:
                    codes.append(f"ROLE::{str(role_text).upper()}")
                if proxy_text:
                    codes.append(f"PROXY::{str(proxy_text).upper()}")
                if is_a0_core_satellite_v2:
                    if core_slot_selected_col is not None and symbol_text.upper() == display_symbols[core_slot_selected_col].upper():
                        codes.append("SLOT::CORE_SLOT")
                    if growth_slot_selected_col is not None and symbol_text.upper() == display_symbols[growth_slot_selected_col].upper():
                        codes.append("SLOT::GROWTH_SLOT")
                    if self._etf_beta_proxy_replacement_mode:
                        codes.append(f"PROXY_REPLACEMENT_MODE::{self._etf_beta_proxy_replacement_mode.upper()}")
            runtime_reason_codes: list[str] = []
            selected_display_symbols = [display_symbols[col_idx] for col_idx in selected_cols]
            fallback_active = False
            vol_target_payload: dict[str, Any] = {
                "active": False,
                "window": self._etf_beta_vol_target_window,
                "annualized_target": self._etf_beta_vol_target_annualized_target,
                "min_scale": self._etf_beta_vol_target_min_scale,
                "max_scale": self._etf_beta_vol_target_max_scale,
                "scale_by_symbol": {},
                "realized_vol_by_symbol": {},
            }
            if self._etf_beta_rule_family == "dual_momentum_vol_target" and selected_cols:
                scale_by_symbol: dict[str, float] = {}
                realized_vol_by_symbol: dict[str, float] = {}
                scale_changed = False
                for col_idx in selected_cols:
                    symbol_text = display_symbols[col_idx]
                    realized_vol = _realized_vol_annualized(daily_returns[:, col_idx], row_idx, self._etf_beta_vol_target_window)
                    if realized_vol is None:
                        scale = self._etf_beta_vol_target_max_scale
                    else:
                        raw_scale = self._etf_beta_vol_target_annualized_target / float(realized_vol)
                        scale = min(self._etf_beta_vol_target_max_scale, max(self._etf_beta_vol_target_min_scale, float(raw_scale)))
                        realized_vol_by_symbol[symbol_text] = float(realized_vol)
                    scale_by_symbol[symbol_text] = float(scale)
                    selection_reason_codes.setdefault(symbol_text, []).extend(
                        [
                            f"VOL_TARGET_WINDOW::{int(self._etf_beta_vol_target_window)}",
                            f"VOL_TARGET_SCALE::{float(scale):.4f}",
                        ]
                    )
                    if float(scale) < float(self._etf_beta_vol_target_max_scale) - 1e-9:
                        scale_changed = True
                vol_target_payload = {
                    "active": True,
                    "window": self._etf_beta_vol_target_window,
                    "annualized_target": self._etf_beta_vol_target_annualized_target,
                    "min_scale": self._etf_beta_vol_target_min_scale,
                    "max_scale": self._etf_beta_vol_target_max_scale,
                    "scale_by_symbol": scale_by_symbol,
                    "realized_vol_by_symbol": realized_vol_by_symbol,
                }
                runtime_reason_codes.append("ETF_BETA_VOL_TARGET_ACTIVE")
                if scale_changed:
                    runtime_reason_codes.append("ETF_BETA_VOL_TARGET_SCALED_DOWN")
            if slot_cap <= 0:
                runtime_reason_codes.append("ETF_BETA_SLOT_CAP_ZERO")
            elif not rebalance_day:
                runtime_reason_codes.append(_await_rebalance_reason_code(self._etf_beta_rebalance_frequency))
            if slot_cap > 0 and not eligible_cols:
                runtime_reason_codes.append("ETF_BETA_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER")
            if slot_cap > 0 and rebalance_day and selected_cols:
                runtime_reason_codes.append(_selection_active_reason_code(self._etf_beta_rebalance_frequency))
            if is_a0_core_satellite_v2:
                for codes in slot_under_deploy_reason_codes.values():
                    for code in codes:
                        runtime_reason_codes.append(str(code))
            if (
                slot_cap > 0
                and rebalance_day
                and self._etf_beta_fallback_mode == "single_symbol"
                and self._etf_beta_fallback_symbol
                and self._etf_beta_fallback_symbol in self._sym_to_col
                and len(selected_display_symbols) < selected_cap
            ):
                fallback_display_symbol = _display_etf_symbol(self._etf_beta_fallback_symbol)
                fallback_symbol_key = fallback_display_symbol.upper()
                if fallback_display_symbol not in selected_display_symbols:
                    selected_display_symbols.append(fallback_display_symbol)
                    selection_reason_codes[fallback_symbol_key] = [
                        "ETF_BETA_FALLBACK_SINGLE_SYMBOL",
                        f"FALLBACK_SYMBOL::{fallback_display_symbol}",
                        f"STATE::{str(state_5_arr[row_idx]).upper()}",
                        f"RULE_FAMILY::{self._etf_beta_rule_family.upper()}",
                        "UNDERFILLED_DEPLOYMENT_FILL",
                    ]
                    fallback_active = True
                    runtime_reason_codes.append("ETF_BETA_FALLBACK_ACTIVE")
                    if ranked_cols:
                        runtime_reason_codes.append("ETF_BETA_FALLBACK_PARTIAL_FILL_ACTIVE")
                    else:
                        runtime_reason_codes.append("ETF_BETA_FALLBACK_FULL_REPLACEMENT_ACTIVE")
            if (
                slot_cap > 0
                and rebalance_day
                and len(selected_display_symbols) < selected_cap
            ):
                runtime_reason_codes.append("ETF_BETA_UNDERFILLED_DEPLOYMENT")
            actual_target_exposure = (
                float(target_exposure_per_symbol) * float(len(selected_display_symbols))
                if target_exposure_per_symbol is not None
                else None
            )
            core_slot_target_actual_exposure = (
                float(target_exposure_per_symbol)
                if core_slot_selected_col is not None and target_exposure_per_symbol is not None
                else None
            )
            growth_slot_target_actual_exposure = (
                float(target_exposure_per_symbol)
                if growth_slot_selected_col is not None and target_exposure_per_symbol is not None
                else None
            )
            deployability_gap = (
                max(0.0, float(target_exposure) - float(actual_target_exposure))
                if target_exposure is not None and actual_target_exposure is not None
                else None
            )
            if (
                min_deployable_exposure is not None
                and actual_target_exposure is not None
                and float(actual_target_exposure) + 1e-12 < float(min_deployable_exposure)
            ):
                runtime_reason_codes.append("ETF_BETA_MIN_DEPLOYABLE_EXPOSURE_UNMET")
            if target_exposure is not None:
                target_exposure_rows[row_idx] = float(target_exposure)
            target_exposure_source_rows[row_idx] = target_exposure_source
            if min_deployable_exposure is not None:
                min_deployable_exposure_rows[row_idx] = float(min_deployable_exposure)
            min_deployable_exposure_source_rows[row_idx] = min_deployable_exposure_source
            target_selected_count_rows[row_idx] = int(target_selected_count)
            if target_exposure_per_symbol is not None:
                target_exposure_per_symbol_rows[row_idx] = float(target_exposure_per_symbol)
            if actual_target_exposure is not None:
                target_actual_exposure_rows[row_idx] = float(actual_target_exposure)
            if deployability_gap is not None:
                target_deployability_gap_rows[row_idx] = float(deployability_gap)
            fallback_allowed_rows[row_idx] = bool(fallback_allowed)
            core_slot_selected_rows[row_idx] = (
                display_symbols[core_slot_selected_col]
                if core_slot_selected_col is not None
                else None
            )
            growth_slot_selected_rows[row_idx] = (
                display_symbols[growth_slot_selected_col]
                if growth_slot_selected_col is not None
                else None
            )
            slot_selection_reason_rows[row_idx] = dict(slot_selection_reason_codes)
            slot_under_deploy_reason_rows[row_idx] = {
                slot: list(codes)
                for slot, codes in slot_under_deploy_reason_codes.items()
                if list(codes)
            }
            if core_slot_target_exposure is not None:
                core_slot_target_exposure_rows[row_idx] = float(core_slot_target_exposure)
            if growth_slot_target_exposure is not None:
                growth_slot_target_exposure_rows[row_idx] = float(growth_slot_target_exposure)
            if core_slot_target_actual_exposure is not None:
                core_slot_target_actual_exposure_rows[row_idx] = float(core_slot_target_actual_exposure)
            if growth_slot_target_actual_exposure is not None:
                growth_slot_target_actual_exposure_rows[row_idx] = float(growth_slot_target_actual_exposure)

            eligible_rows.append([display_symbols[col_idx] for col_idx in ranked_cols])
            selected_rows.append(list(selected_display_symbols))
            selection_reason_rows.append(selection_reason_codes)
            runtime_reason_rows.append(runtime_reason_codes)
            vol_target_rows.append(vol_target_payload)

        self._etf_beta_eligible_symbols_arr = np.empty(day_count, dtype=object)
        self._etf_beta_selected_symbols_arr = np.empty(day_count, dtype=object)
        self._etf_beta_selection_reason_codes_arr = np.empty(day_count, dtype=object)
        self._etf_beta_runtime_reason_codes_arr = np.empty(day_count, dtype=object)
        self._etf_beta_vol_target_info_arr = np.empty(day_count, dtype=object)
        self._etf_beta_target_exposure_arr = target_exposure_rows
        self._etf_beta_target_exposure_source_arr = target_exposure_source_rows
        self._etf_beta_min_deployable_exposure_arr = min_deployable_exposure_rows
        self._etf_beta_min_deployable_exposure_source_arr = min_deployable_exposure_source_rows
        self._etf_beta_target_selected_count_arr = target_selected_count_rows
        self._etf_beta_target_exposure_per_symbol_arr = target_exposure_per_symbol_rows
        self._etf_beta_target_actual_exposure_arr = target_actual_exposure_rows
        self._etf_beta_target_deployability_gap_arr = target_deployability_gap_rows
        self._etf_beta_fallback_allowed_arr = fallback_allowed_rows
        self._etf_beta_core_slot_selected_symbol_arr = np.empty(day_count, dtype=object)
        self._etf_beta_growth_slot_selected_symbol_arr = np.empty(day_count, dtype=object)
        self._etf_beta_slot_selection_reason_codes_arr = np.empty(day_count, dtype=object)
        self._etf_beta_slot_under_deploy_reason_codes_arr = np.empty(day_count, dtype=object)
        self._etf_beta_core_slot_target_exposure_arr = core_slot_target_exposure_rows
        self._etf_beta_growth_slot_target_exposure_arr = growth_slot_target_exposure_rows
        self._etf_beta_core_slot_target_actual_exposure_arr = core_slot_target_actual_exposure_rows
        self._etf_beta_growth_slot_target_actual_exposure_arr = growth_slot_target_actual_exposure_rows
        for row_idx in range(day_count):
            self._etf_beta_eligible_symbols_arr[row_idx] = list(eligible_rows[row_idx])
            self._etf_beta_selected_symbols_arr[row_idx] = list(selected_rows[row_idx])
            self._etf_beta_selection_reason_codes_arr[row_idx] = dict(selection_reason_rows[row_idx])
            self._etf_beta_runtime_reason_codes_arr[row_idx] = list(runtime_reason_rows[row_idx])
            self._etf_beta_vol_target_info_arr[row_idx] = dict(vol_target_rows[row_idx])
            self._etf_beta_core_slot_selected_symbol_arr[row_idx] = core_slot_selected_rows[row_idx]
            self._etf_beta_growth_slot_selected_symbol_arr[row_idx] = growth_slot_selected_rows[row_idx]
            self._etf_beta_slot_selection_reason_codes_arr[row_idx] = dict(slot_selection_reason_rows[row_idx])
            self._etf_beta_slot_under_deploy_reason_codes_arr[row_idx] = dict(slot_under_deploy_reason_rows[row_idx])

    def day_signals(self, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
        held_symbols = {
            str(symbol).strip().lower()
            for symbol, qty in dict(ctx.positions or {}).items()
            if int(qty) > 0
        }
        state_5 = str(
            self._effective_state_5_arr[day_idx]
            if day_idx < len(self._effective_state_5_arr)
            else self._market_state_name_map.get(day, "")
        ).strip().upper()
        trade_mode = str(
            self._trade_mode_name_arr[day_idx]
            if day_idx < len(self._trade_mode_name_arr)
            else self._trade_mode_name_map.get(day, "")
        ).strip().upper()
        slot_cap = int(self._etf_beta_slot_cap_arr[day_idx]) if day_idx < len(self._etf_beta_slot_cap_arr) else 0
        rebalance_day = bool(self._etf_beta_rebalance_flag_arr[day_idx]) if day_idx < len(self._etf_beta_rebalance_flag_arr) else False
        eligible_symbols = (
            [str(symbol).strip().upper() for symbol in _sequence_payload(self._etf_beta_eligible_symbols_arr[day_idx])]
            if day_idx < len(self._etf_beta_eligible_symbols_arr)
            else []
        )
        selected_symbols = (
            [str(symbol).strip().upper() for symbol in _sequence_payload(self._etf_beta_selected_symbols_arr[day_idx])]
            if day_idx < len(self._etf_beta_selected_symbols_arr)
            else []
        )
        selection_reason_codes = (
            dict(self._etf_beta_selection_reason_codes_arr[day_idx] or {})
            if day_idx < len(self._etf_beta_selection_reason_codes_arr)
            else {}
        )
        runtime_reason_codes = (
            [str(code).strip() for code in _sequence_payload(self._etf_beta_runtime_reason_codes_arr[day_idx])]
            if day_idx < len(self._etf_beta_runtime_reason_codes_arr)
            else []
        )
        vol_target_info = (
            dict(self._etf_beta_vol_target_info_arr[day_idx] or {})
            if day_idx < len(self._etf_beta_vol_target_info_arr)
            else {}
        )
        vol_target_scale_by_symbol = {
            str(symbol).strip().upper(): float(scale)
            for symbol, scale in dict(vol_target_info.get("scale_by_symbol") or {}).items()
            if str(symbol).strip()
        }
        vol_target_realized_vol_by_symbol = {
            str(symbol).strip().upper(): float(vol)
            for symbol, vol in dict(vol_target_info.get("realized_vol_by_symbol") or {}).items()
            if str(symbol).strip()
        }
        target_exposure = (
            float(self._etf_beta_target_exposure_arr[day_idx])
            if day_idx < len(self._etf_beta_target_exposure_arr)
            and np.isfinite(self._etf_beta_target_exposure_arr[day_idx])
            else None
        )
        target_exposure_source = (
            str(self._etf_beta_target_exposure_source_arr[day_idx] or "").strip()
            if day_idx < len(self._etf_beta_target_exposure_source_arr)
            else ""
        )
        min_deployable_exposure = (
            float(self._etf_beta_min_deployable_exposure_arr[day_idx])
            if day_idx < len(self._etf_beta_min_deployable_exposure_arr)
            and np.isfinite(self._etf_beta_min_deployable_exposure_arr[day_idx])
            else None
        )
        min_deployable_exposure_source = (
            str(self._etf_beta_min_deployable_exposure_source_arr[day_idx] or "").strip()
            if day_idx < len(self._etf_beta_min_deployable_exposure_source_arr)
            else ""
        )
        target_selected_count = (
            int(self._etf_beta_target_selected_count_arr[day_idx])
            if day_idx < len(self._etf_beta_target_selected_count_arr)
            else 0
        )
        target_exposure_per_symbol = (
            float(self._etf_beta_target_exposure_per_symbol_arr[day_idx])
            if day_idx < len(self._etf_beta_target_exposure_per_symbol_arr)
            and np.isfinite(self._etf_beta_target_exposure_per_symbol_arr[day_idx])
            else None
        )
        target_actual_exposure = (
            float(self._etf_beta_target_actual_exposure_arr[day_idx])
            if day_idx < len(self._etf_beta_target_actual_exposure_arr)
            and np.isfinite(self._etf_beta_target_actual_exposure_arr[day_idx])
            else None
        )
        target_deployability_gap = (
            float(self._etf_beta_target_deployability_gap_arr[day_idx])
            if day_idx < len(self._etf_beta_target_deployability_gap_arr)
            and np.isfinite(self._etf_beta_target_deployability_gap_arr[day_idx])
            else None
        )
        fallback_allowed = (
            bool(self._etf_beta_fallback_allowed_arr[day_idx])
            if day_idx < len(self._etf_beta_fallback_allowed_arr)
            else False
        )
        core_slot_selected_symbol = (
            str(self._etf_beta_core_slot_selected_symbol_arr[day_idx] or "").strip().upper()
            if day_idx < len(self._etf_beta_core_slot_selected_symbol_arr)
            else ""
        )
        growth_slot_selected_symbol = (
            str(self._etf_beta_growth_slot_selected_symbol_arr[day_idx] or "").strip().upper()
            if day_idx < len(self._etf_beta_growth_slot_selected_symbol_arr)
            else ""
        )
        slot_selection_reason_codes = (
            dict(self._etf_beta_slot_selection_reason_codes_arr[day_idx] or {})
            if day_idx < len(self._etf_beta_slot_selection_reason_codes_arr)
            else {}
        )
        slot_under_deploy_reason_codes = (
            dict(self._etf_beta_slot_under_deploy_reason_codes_arr[day_idx] or {})
            if day_idx < len(self._etf_beta_slot_under_deploy_reason_codes_arr)
            else {}
        )
        core_slot_target_exposure = (
            float(self._etf_beta_core_slot_target_exposure_arr[day_idx])
            if day_idx < len(self._etf_beta_core_slot_target_exposure_arr)
            and np.isfinite(self._etf_beta_core_slot_target_exposure_arr[day_idx])
            else None
        )
        growth_slot_target_exposure = (
            float(self._etf_beta_growth_slot_target_exposure_arr[day_idx])
            if day_idx < len(self._etf_beta_growth_slot_target_exposure_arr)
            and np.isfinite(self._etf_beta_growth_slot_target_exposure_arr[day_idx])
            else None
        )
        core_slot_target_actual_exposure = (
            float(self._etf_beta_core_slot_target_actual_exposure_arr[day_idx])
            if day_idx < len(self._etf_beta_core_slot_target_actual_exposure_arr)
            and np.isfinite(self._etf_beta_core_slot_target_actual_exposure_arr[day_idx])
            else None
        )
        growth_slot_target_actual_exposure = (
            float(self._etf_beta_growth_slot_target_actual_exposure_arr[day_idx])
            if day_idx < len(self._etf_beta_growth_slot_target_actual_exposure_arr)
            and np.isfinite(self._etf_beta_growth_slot_target_actual_exposure_arr[day_idx])
            else None
        )
        configured_max_selected = (
            int(self._etf_beta_max_selected_symbols)
            if self._etf_beta_max_selected_symbols is not None and int(self._etf_beta_max_selected_symbols) > 0
            else None
        )
        selected_cap = int(slot_cap)
        if configured_max_selected is not None:
            selected_cap = min(int(slot_cap), int(configured_max_selected))
        fallback_active = any(
            "ETF_BETA_FALLBACK_SINGLE_SYMBOL" in [str(code).strip() for code in list(codes or [])]
            for codes in selection_reason_codes.values()
        )
        entry_reason_code = _entry_reason_code(self._etf_beta_rebalance_frequency)

        selected_lower = {_normalize_etf_symbol_key(symbol) for symbol in selected_symbols}
        strength_map: dict[str, float] = {}
        mf_score_map: dict[str, float] = {}
        for symbol in set(selected_lower) | held_symbols:
            col_idx = self._sym_to_col.get(symbol)
            if col_idx is None:
                continue
            close_now = float(self._mx.close[day_idx, col_idx])
            ma120_now = float(self._feats.trend_fast_ma[day_idx, col_idx])
            if close_now != close_now or ma120_now != ma120_now:
                continue
            score = 0.0
            if symbol.upper() in selected_symbols:
                rank_map = selection_reason_codes.get(symbol.upper()) or []
                if rank_map:
                    score = 1.0
            strength_map[symbol] = float(score)
            mf_score_map[symbol] = float(score)

        sell_signals: list[Signal] = []
        buy_signals: list[Signal] = []
        exit_counts = ExitCounts()

        if slot_cap <= 0:
            for symbol in sorted(held_symbols):
                sell_signals.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol,
                        side=Side.SELL,
                        qty=0,
                        reason="ETF_BETA_STATE_EXIT",
                        reason_code="ETF_BETA_STATE_EXIT",
                        meta={
                            "alpha_id": "cn_etf_beta",
                            "alpha_source": "cn_etf_beta_selector",
                            "sleeve_id": "cn_etf_beta",
                            "state_5": state_5,
                            "selection_reason_codes": [],
                            "runtime_reason_codes": list(runtime_reason_codes),
                        },
                    )
                )
                self.diag_reason_counts["ETF_BETA_STATE_EXIT"] = int(self.diag_reason_counts.get("ETF_BETA_STATE_EXIT", 0)) + 1
        elif rebalance_day:
            for symbol in sorted(held_symbols - selected_lower):
                sell_signals.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol,
                        side=Side.SELL,
                        qty=0,
                        reason="ETF_BETA_REBALANCE_EXIT",
                        reason_code="ETF_BETA_REBALANCE_EXIT",
                        meta={
                            "alpha_id": "cn_etf_beta",
                            "alpha_source": "cn_etf_beta_selector",
                            "sleeve_id": "cn_etf_beta",
                            "state_5": state_5,
                            "selection_reason_codes": [],
                            "runtime_reason_codes": list(runtime_reason_codes),
                        },
                    )
                )
                self.diag_reason_counts["ETF_BETA_REBALANCE_EXIT"] = int(self.diag_reason_counts.get("ETF_BETA_REBALANCE_EXIT", 0)) + 1
            for symbol in selected_symbols:
                normalized = _normalize_etf_symbol_key(symbol)
                if normalized in held_symbols:
                    continue
                col_idx = self._sym_to_col.get(normalized)
                if col_idx is None:
                    continue
                close_now = float(self._mx.close[day_idx, col_idx])
                ma120_now = float(self._feats.trend_fast_ma[day_idx, col_idx])
                if close_now != close_now or ma120_now != ma120_now:
                    continue
                raw_score = float(len(selected_symbols) - selected_symbols.index(symbol))
                order_value_scale = float(vol_target_scale_by_symbol.get(symbol.upper(), 1.0))
                signal_meta = {
                    "alpha_id": "cn_etf_beta",
                    "alpha_source": "cn_etf_beta_selector",
                    "sleeve_id": "cn_etf_beta",
                    "raw_score": raw_score,
                    "compose_score": raw_score,
                    "close": close_now,
                    "ma120": ma120_now,
                    "research_rule_family": self._etf_beta_rule_family,
                    "proxy_replacement_mode": self._etf_beta_proxy_replacement_mode,
                    "formal_replacement_pairs": dict(self._etf_beta_formal_replacement_pairs),
                    "core_slot_symbols": list(self._etf_beta_core_slot_symbols),
                    "growth_slot_symbols": list(self._etf_beta_growth_slot_symbols),
                    "core_slot_selected_symbol": core_slot_selected_symbol or None,
                    "growth_slot_selected_symbol": growth_slot_selected_symbol or None,
                    "absolute_filter_mode": self._etf_beta_absolute_filter_mode,
                    "fallback_mode": self._etf_beta_fallback_mode,
                    "fallback_symbol": _display_etf_symbol(self._etf_beta_fallback_symbol) if self._etf_beta_fallback_symbol else None,
                    "target_exposure": target_exposure,
                    "target_exposure_source": target_exposure_source or None,
                    "min_deployable_exposure": min_deployable_exposure,
                    "min_deployable_exposure_source": min_deployable_exposure_source or None,
                    "target_selected_count": int(target_selected_count),
                    "target_exposure_per_symbol": target_exposure_per_symbol,
                    "target_actual_exposure": target_actual_exposure,
                    "deployability_gap": target_deployability_gap,
                    "fallback_allowed": bool(fallback_allowed),
                    "order_value_scale": order_value_scale,
                    "vol_target_active": bool(vol_target_info.get("active", False)),
                    "vol_target_window": vol_target_info.get("window"),
                    "vol_target_annualized_target": vol_target_info.get("annualized_target"),
                    "vol_target_min_scale": vol_target_info.get("min_scale"),
                    "vol_target_max_scale": vol_target_info.get("max_scale"),
                    "vol_target_realized_vol": vol_target_realized_vol_by_symbol.get(symbol.upper()),
                    "selection_reason_codes": list(selection_reason_codes.get(symbol) or []),
                    "runtime_reason_codes": list(runtime_reason_codes),
                    "rebalance_day": rebalance_day,
                    "state_5": state_5,
                }
                is_fallback_buy = "ETF_BETA_FALLBACK_SINGLE_SYMBOL" in signal_meta["selection_reason_codes"]
                buy_signals.append(
                    Signal(
                        signal_date=day,
                        symbol=normalized,
                        side=Side.BUY,
                        qty=1,
                        reason="ETF_BETA_FALLBACK_BUY" if is_fallback_buy else entry_reason_code,
                        reason_code="ETF_BETA_FALLBACK_BUY" if is_fallback_buy else entry_reason_code,
                        meta=signal_meta,
                    )
                )
                strength_map[normalized] = raw_score
                mf_score_map[normalized] = raw_score
                reason_counter_key = "ETF_BETA_FALLBACK_BUY" if is_fallback_buy else entry_reason_code
                self.diag_reason_counts[reason_counter_key] = int(self.diag_reason_counts.get(reason_counter_key, 0)) + 1

        diagnostics = {
            "composition_enabled": False,
            "market_state": state_5,
            "trade_mode": trade_mode,
            "raw_alpha_signal_count": int(len(buy_signals)),
            "buy_candidate_count": int(len(eligible_symbols)),
            "after_held_filter_count": int(len([symbol for symbol in selected_symbols if symbol.lower() not in held_symbols])),
            "etf_beta_rebalance_day": bool(rebalance_day),
            "etf_beta_deployable_slot_cap": int(slot_cap),
            "etf_beta_formal_scope_symbols": list(self._etf_beta_formal_scope_symbols),
            "etf_beta_eligible_symbols": list(eligible_symbols),
            "etf_beta_selected_symbols": list(selected_symbols),
            "etf_beta_selection_reason_codes": selection_reason_codes,
            "etf_beta_runtime_reason_codes": list(runtime_reason_codes),
            "etf_beta_rule_family": self._etf_beta_rule_family,
            "etf_beta_template_id": self._etf_beta_template_id or None,
            "etf_beta_template_asset_pool_version": self._etf_beta_template_asset_pool_version or None,
            "etf_beta_template_role_map": dict(self._etf_beta_template_role_map),
            "etf_beta_template_proxy_map": dict(self._etf_beta_template_proxy_map),
            "etf_beta_template_target_formal_symbols": list(self._etf_beta_template_target_formal_symbols),
            "etf_beta_proxy_replacement_mode": self._etf_beta_proxy_replacement_mode,
            "etf_beta_formal_replacement_pairs": dict(self._etf_beta_formal_replacement_pairs),
            "etf_beta_core_slot_symbols": list(self._etf_beta_core_slot_symbols),
            "etf_beta_growth_slot_symbols": list(self._etf_beta_growth_slot_symbols),
            "etf_beta_growth_seat_symbol": self._etf_beta_growth_seat_symbol or None,
            "etf_beta_core_slot_selected_symbol": core_slot_selected_symbol or None,
            "etf_beta_growth_slot_selected_symbol": growth_slot_selected_symbol or None,
            "etf_beta_slot_selection_reason_codes": slot_selection_reason_codes,
            "etf_beta_slot_under_deploy_reason_codes": slot_under_deploy_reason_codes,
            "etf_beta_core_slot_target_exposure": core_slot_target_exposure,
            "etf_beta_growth_slot_target_exposure": growth_slot_target_exposure,
            "etf_beta_core_slot_target_actual_exposure": core_slot_target_actual_exposure,
            "etf_beta_growth_slot_target_actual_exposure": growth_slot_target_actual_exposure,
            "etf_beta_absolute_filter_mode": self._etf_beta_absolute_filter_mode,
            "etf_beta_rebalance_frequency": self._etf_beta_rebalance_frequency,
            "etf_beta_relative_strength_fast_window": self._etf_beta_rs_fast_window,
            "etf_beta_relative_strength_mid_window": self._etf_beta_rs_mid_window,
            "etf_beta_relative_strength_slow_window": self._etf_beta_rs_slow_window,
            "etf_beta_relative_strength_fast_weight": self._etf_beta_rs_fast_weight,
            "etf_beta_relative_strength_mid_weight": self._etf_beta_rs_mid_weight,
            "etf_beta_relative_strength_slow_weight": self._etf_beta_rs_slow_weight,
            "etf_beta_max_selected_symbols": self._etf_beta_max_selected_symbols,
            "etf_beta_selected_cap": int(selected_cap),
            "etf_beta_target_exposure": target_exposure,
            "etf_beta_target_exposure_source": target_exposure_source or None,
            "etf_beta_min_deployable_exposure": min_deployable_exposure,
            "etf_beta_min_deployable_exposure_source": min_deployable_exposure_source or None,
            "etf_beta_target_selected_count": int(target_selected_count),
            "etf_beta_target_exposure_per_symbol": target_exposure_per_symbol,
            "etf_beta_target_actual_exposure": target_actual_exposure,
            "etf_beta_target_deployability_gap": target_deployability_gap,
            "etf_beta_fallback_mode": self._etf_beta_fallback_mode,
            "etf_beta_fallback_symbol": _display_etf_symbol(self._etf_beta_fallback_symbol) if self._etf_beta_fallback_symbol else None,
            "etf_beta_fallback_allowed": bool(fallback_allowed),
            "etf_beta_fallback_active": bool(fallback_active),
            "etf_beta_under_deploy_reason_codes": [
                code
                for code in list(runtime_reason_codes)
                if str(code).strip()
                in {
                    "ETF_BETA_SLOT_CAP_ZERO",
                    "ETF_BETA_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER",
                    "ETF_BETA_UNDERFILLED_DEPLOYMENT",
                    "ETF_BETA_MIN_DEPLOYABLE_EXPOSURE_UNMET",
                    "ETF_BETA_FALLBACK_PARTIAL_FILL_ACTIVE",
                    "ETF_BETA_FALLBACK_FULL_REPLACEMENT_ACTIVE",
                    "ETF_BETA_CORE_SLOT_SUPPRESSED_BY_SLOT_CAP",
                    "ETF_BETA_GROWTH_SLOT_SUPPRESSED_BY_SLOT_CAP",
                    "ETF_BETA_CORE_SLOT_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER",
                    "ETF_BETA_GROWTH_SLOT_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER",
                }
            ],
            "etf_beta_vol_target_active": bool(vol_target_info.get("active", False)),
            "etf_beta_vol_target_window": vol_target_info.get("window"),
            "etf_beta_vol_target_annualized_target": vol_target_info.get("annualized_target"),
            "etf_beta_vol_target_min_scale": vol_target_info.get("min_scale"),
            "etf_beta_vol_target_max_scale": vol_target_info.get("max_scale"),
            "etf_beta_vol_target_scale_by_symbol": vol_target_scale_by_symbol,
            "etf_beta_vol_target_realized_vol_by_symbol": vol_target_realized_vol_by_symbol,
        }
        return DaySignals(
            sell_signals=sell_signals,
            buy_signals=buy_signals,
            raw_alpha_signals=list(buy_signals),
            composed_sell_signals=[],
            composed_buy_signals=[],
            exit_syms={str(signal.symbol).lower() for signal in sell_signals},
            strength_map=strength_map,
            mf_score_map=mf_score_map,
            mf_gate_on_today=False,
            strong_risk_on=state_5 in {"BULL", "TRANS_UP"},
            exit_counts=exit_counts,
            diagnostics=diagnostics,
        )
