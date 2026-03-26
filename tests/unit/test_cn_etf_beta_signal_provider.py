from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd

from backend.core.engine_vector.breakout_signal_provider import BreakoutTrendProvider
from backend.core.engine_vector.cn_etf_beta_signal_provider import CNETFBetaSignalProvider
from backend.core.engine_vector.signal_provider import DayContext


def test_cn_etf_beta_day_signals_rebalance_into_runtime_selection() -> None:
    trading_day = date(2026, 3, 20)
    provider = CNETFBetaSignalProvider()
    provider._mx = SimpleNamespace(
        symbols=["sh510300", "sh510500"],
        close=np.array([[4.0, 6.0]], dtype=float),
        dates=[trading_day],
    )
    provider._feats = SimpleNamespace(
        trend_fast_ma=np.array([[3.5, 5.5]], dtype=float),
    )
    provider._sym_to_col = {"sh510300": 0, "sh510500": 1}
    provider._effective_state_5_arr = np.array(["BULL"], dtype=object)
    provider._trade_mode_name_arr = np.array(["TREND_MAIN"], dtype=object)
    provider._etf_beta_slot_cap_arr = np.array([1], dtype=np.int32)
    provider._etf_beta_rebalance_flag_arr = np.array([True], dtype=bool)
    provider._etf_beta_formal_scope_symbols = ["510300.SH", "510500.SH"]
    provider._etf_beta_eligible_symbols_arr = np.array([["510300.SH", "510500.SH"]], dtype=object)
    provider._etf_beta_selected_symbols_arr = np.array([["510300.SH"]], dtype=object)
    provider._etf_beta_selection_reason_codes_arr = np.array(
        [{"510300.SH": ["ETF_BETA_CORE_SCOPE", "ABSOLUTE_TREND_PASS"]}],
        dtype=object,
    )
    provider._etf_beta_runtime_reason_codes_arr = np.array([["ETF_BETA_WEEKLY_SELECTION_ACTIVE"]], dtype=object)
    provider._etf_beta_target_exposure_arr = np.array([0.2], dtype=float)
    provider._etf_beta_target_exposure_source_arr = np.array(["fixed"], dtype=object)
    provider._etf_beta_min_deployable_exposure_arr = np.array([0.1], dtype=float)
    provider._etf_beta_min_deployable_exposure_source_arr = np.array(["fixed"], dtype=object)
    provider._etf_beta_target_selected_count_arr = np.array([1], dtype=np.int32)
    provider._etf_beta_target_exposure_per_symbol_arr = np.array([0.2], dtype=float)
    provider._etf_beta_target_actual_exposure_arr = np.array([0.2], dtype=float)
    provider._etf_beta_target_deployability_gap_arr = np.array([0.0], dtype=float)
    provider._etf_beta_fallback_allowed_arr = np.array([False], dtype=bool)

    ctx = DayContext(
        positions={"sh510500": 100},
        position_avg_cost={"sh510500": 5.0},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=1,
        close_idx={(trading_day, "sh510500"): 6.0},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )

    day_signals = provider.day_signals(trading_day, 0, ctx)

    assert [signal.symbol for signal in day_signals.sell_signals] == ["sh510500"]
    assert [signal.reason_code for signal in day_signals.sell_signals] == ["ETF_BETA_REBALANCE_EXIT"]
    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh510300"]
    assert [signal.reason_code for signal in day_signals.buy_signals] == ["ETF_BETA_WEEKLY_RS"]
    assert day_signals.diagnostics["etf_beta_selected_symbols"] == ["510300.SH"]
    assert day_signals.diagnostics["etf_beta_eligible_symbols"] == ["510300.SH", "510500.SH"]
    assert day_signals.diagnostics["etf_beta_runtime_reason_codes"] == ["ETF_BETA_WEEKLY_SELECTION_ACTIVE"]
    assert day_signals.diagnostics["etf_beta_target_exposure"] == 0.2
    assert day_signals.diagnostics["etf_beta_min_deployable_exposure"] == 0.1
    assert day_signals.diagnostics["etf_beta_target_selected_count"] == 1
    assert day_signals.diagnostics["etf_beta_target_exposure_per_symbol"] == 0.2
    assert day_signals.diagnostics["etf_beta_target_actual_exposure"] == 0.2
    assert day_signals.diagnostics["etf_beta_target_deployability_gap"] == 0.0
    assert day_signals.buy_signals[0].meta["sleeve_id"] == "cn_etf_beta"
    assert day_signals.buy_signals[0].meta["target_exposure"] == 0.2
    assert day_signals.buy_signals[0].meta["min_deployable_exposure"] == 0.1
    assert day_signals.buy_signals[0].meta["target_exposure_per_symbol"] == 0.2
    assert day_signals.buy_signals[0].meta["deployability_gap"] == 0.0


def test_cn_etf_beta_precompute_derives_legacy_regime_when_super_arrays_blank(monkeypatch) -> None:
    trading_days = [date(2026, 1, 5 + idx) for idx in range(10)]
    benchmark = pd.DataFrame(
        {
            "date": pd.to_datetime(trading_days),
            "close": [100.0 + float(idx) for idx in range(10)],
        }
    )

    def _fake_super_precompute(self, **_kwargs) -> None:
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh"],
            close=np.full((10, 1), 5.0, dtype=float),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.full((10, 1), 4.0, dtype=float),
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array([], dtype=object)
        self._effective_state_5_arr = np.array([], dtype=object)
        self._regime_risk_budget_multiplier_arr = np.array([], dtype=float)
        self._risk_budget_multiplier_arr = np.array([], dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=benchmark,
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        market_filter_cfg={
            "enabled": True,
            "long_ma_window": 5,
            "slope_window": 1,
            "slope_ma_period": 3,
            "bull_multiplier": 1.0,
            "light_multiplier": 0.5,
            "trans_down_multiplier": 0.25,
            "trans_up_multiplier": 0.75,
            "bear_multiplier": 0.0,
        },
    )

    assert len(provider._effective_state_5_arr) == 10
    assert provider._effective_state_5_arr[-1] == "BULL"
    assert provider._trade_mode_name_arr[-1] == "TREND_MAIN"
    assert provider._regime_risk_budget_multiplier_arr[-1] == 1.0
    assert provider._etf_beta_slot_cap_arr[-1] == 2


def test_cn_etf_beta_precompute_respects_dual_momentum_basic_config(monkeypatch) -> None:
    trading_days = [date(2025, 1, 1) + pd.Timedelta(days=idx) for idx in range(270)]
    trading_days = [pd.Timestamp(day).date() for day in trading_days]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 8.0, 270, dtype=float)
        close_510050 = np.linspace(8.0, 4.0, 270, dtype=float)
        close_511010 = np.linspace(3.0, 3.2, 270, dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510050.sh", "511010.sh"],
            close=np.column_stack([close_510300, close_510050, close_511010]),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.2,
                    close_510050 - 0.2,
                    close_511010 - 0.05,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array([], dtype=object)
        self._effective_state_5_arr = np.array([], dtype=object)
        self._regime_risk_budget_multiplier_arr = np.array([], dtype=float)
        self._risk_budget_multiplier_arr = np.array([], dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 130.0, 270, dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        market_filter_cfg={
            "enabled": True,
            "long_ma_window": 5,
            "slope_window": 1,
            "slope_ma_period": 3,
            "bull_multiplier": 1.0,
            "light_multiplier": 0.5,
            "trans_down_multiplier": 0.25,
            "trans_up_multiplier": 0.75,
            "bear_multiplier": 0.0,
        },
        governed_a_share={
            "etf_beta": {
                "research_rule_family": "dual_momentum_basic",
                "core_beta_symbols": ["510300.SH", "510050.SH"],
                "absolute_filter_mode": "positive_12m",
                "fallback_mode": "single_symbol",
                "fallback_symbol": "511010.SH",
                "relative_strength_fast_window": 60,
                "relative_strength_slow_window": 120,
                "relative_strength_fast_weight": 0.4,
                "relative_strength_slow_weight": 0.6,
                "max_selected_symbols": 1,
            }
        },
    )

    assert provider._etf_beta_rule_family == "dual_momentum_basic"
    assert provider._etf_beta_formal_scope_symbols == ["510300.SH", "510050.SH"]
    assert provider._etf_beta_selected_symbols_arr[-1] == ["510300.SH"]
    assert "ETF_BETA_WEEKLY_SELECTION_ACTIVE" in provider._etf_beta_runtime_reason_codes_arr[-1]


def test_cn_etf_beta_precompute_biweekly_rebalance_has_fewer_switch_dates(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2025-01-02", periods=40)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 5.0, len(trading_days), dtype=float)
        close_510050 = np.linspace(3.0, 4.0, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510050.sh"],
            close=np.column_stack([close_510300, close_510050]),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack([close_510300 - 0.2, close_510050 - 0.2]),
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array([], dtype=object)
        self._effective_state_5_arr = np.array([], dtype=object)
        self._regime_risk_budget_multiplier_arr = np.array([], dtype=float)
        self._risk_budget_multiplier_arr = np.array([], dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    common_kwargs = {
        "history": pd.DataFrame(),
        "benchmark": pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 105.0, len(trading_days), dtype=float)}),
        "raw_history": pd.DataFrame(),
        "trading_days": trading_days,
        "strategy": SimpleNamespace(),
        "market_filter_cfg": {
            "enabled": True,
            "long_ma_window": 5,
            "slope_window": 1,
            "slope_ma_period": 3,
            "bull_multiplier": 1.0,
            "light_multiplier": 0.5,
            "trans_down_multiplier": 0.25,
            "trans_up_multiplier": 0.75,
            "bear_multiplier": 0.0,
        },
    }

    weekly = CNETFBetaSignalProvider()
    weekly.precompute(
        **common_kwargs,
        governed_a_share={"etf_beta": {"core_beta_symbols": ["510300.SH", "510050.SH"], "rebalance_frequency": "weekly"}},
    )
    biweekly = CNETFBetaSignalProvider()
    biweekly.precompute(
        **common_kwargs,
        governed_a_share={"etf_beta": {"core_beta_symbols": ["510300.SH", "510050.SH"], "rebalance_frequency": "biweekly"}},
    )

    assert weekly._etf_beta_rebalance_frequency == "weekly"
    assert biweekly._etf_beta_rebalance_frequency == "biweekly"
    assert int(weekly._etf_beta_rebalance_flag_arr.sum()) > int(biweekly._etf_beta_rebalance_flag_arr.sum())
    assert bool(weekly._etf_beta_rebalance_flag_arr[-1]) is True


def test_cn_etf_beta_precompute_supports_broad_based_rotation_template_a(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2024-01-02", periods=320)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 6.2, len(trading_days), dtype=float)
        close_510500 = np.linspace(3.0, 5.6, len(trading_days), dtype=float)
        close_512100 = np.linspace(2.0, 4.4, len(trading_days), dtype=float)
        close_512890 = np.linspace(2.5, 3.8, len(trading_days), dtype=float)
        close_159915 = np.linspace(3.2, 5.8, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510500.sh", "512100.sh", "512890.sh", "159915.sz"],
            close=np.column_stack([close_510300, close_510500, close_512100, close_512890, close_159915]),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.1,
                    close_510500 - 0.1,
                    close_512100 - 0.1,
                    close_512890 - 0.05,
                    close_159915 - 0.12,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array([], dtype=object)
        self._effective_state_5_arr = np.array([], dtype=object)
        self._regime_risk_budget_multiplier_arr = np.array([], dtype=float)
        self._risk_budget_multiplier_arr = np.array([], dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 120.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        market_filter_cfg={
            "enabled": True,
            "long_ma_window": 5,
            "slope_window": 1,
            "slope_ma_period": 3,
            "bull_multiplier": 1.0,
            "light_multiplier": 0.5,
            "trans_down_multiplier": 0.25,
            "trans_up_multiplier": 0.75,
            "bear_multiplier": 0.0,
        },
        governed_a_share={
            "etf_beta": {
                "research_rule_family": "broad_based_rotation_template_a",
                "template_id": "broad_based_rotation_template_a",
                "template_asset_pool_version": "A0",
                "template_role_map": {
                    "510300.SH": "hs300",
                    "510500.SH": "csi500",
                    "512100.SH": "csi1000_proxy",
                    "512890.SH": "dividend_proxy",
                    "159915.SZ": "growth_seat",
                },
                "template_proxy_map": {
                    "512100.SH": "CSI1000_STANDARD",
                    "512890.SH": "DIVIDEND_STANDARD",
                },
                "template_target_formal_symbols": [
                    "510300.SH",
                    "510500.SH",
                    "CSI1000_STANDARD",
                    "DIVIDEND_STANDARD",
                ],
                "growth_seat_symbol": "159915.SZ",
                "core_beta_symbols": ["510300.SH", "510500.SH", "512100.SH", "512890.SH", "159915.SZ"],
                "limited_defense_candidates": [],
                "rebalance_frequency": "monthly",
                "absolute_filter_mode": "ma200_and_positive_12m",
                "fallback_mode": "cash",
                "relative_strength_fast_window": 63,
                "relative_strength_mid_window": 126,
                "relative_strength_slow_window": 252,
                "relative_strength_fast_weight": 0.2,
                "relative_strength_mid_weight": 0.3,
                "relative_strength_slow_weight": 0.5,
                "max_selected_symbols": 2,
            }
        },
    )

    assert provider._etf_beta_rule_family == "broad_based_rotation_template_a"
    assert provider._etf_beta_rebalance_frequency == "monthly"
    assert provider._etf_beta_absolute_filter_mode == "ma200_and_positive_12m"
    assert provider._etf_beta_rs_mid_window == 126
    assert provider._etf_beta_rs_mid_weight == 0.3
    assert provider._etf_beta_template_asset_pool_version == "A0"
    assert provider._etf_beta_template_proxy_map["512100.SH"] == "CSI1000_STANDARD"
    assert provider._etf_beta_growth_seat_symbol == "159915.SZ"
    assert int(provider._etf_beta_rebalance_flag_arr.sum()) < len(trading_days) // 4
    latest_selected = provider._etf_beta_selected_symbols_arr[-1]
    assert len(latest_selected) == 2
    assert "510500.SH" in latest_selected
    assert set(latest_selected).issubset(
        {"510300.SH", "510500.SH", "512100.SH", "512890.SH", "159915.SZ"}
    )
    latest_reason_codes = provider._etf_beta_selection_reason_codes_arr[-1]
    growth_or_proxy_symbol = next(
        symbol for symbol in latest_selected if symbol != "510500.SH"
    )
    assert "ABSOLUTE_MA200_PASS" in latest_reason_codes[growth_or_proxy_symbol]
    assert "ABSOLUTE_RET12_PASS" in latest_reason_codes[growth_or_proxy_symbol]
    assert "RS252_RANK_PASS" in latest_reason_codes[growth_or_proxy_symbol]
    assert "RS126_RANK_PASS" in latest_reason_codes[growth_or_proxy_symbol]
    assert "RS63_RANK_PASS" in latest_reason_codes[growth_or_proxy_symbol]
    assert "POOL::A0" in latest_reason_codes[growth_or_proxy_symbol]
    assert any(
        code.startswith("ROLE::") for code in latest_reason_codes[growth_or_proxy_symbol]
    )


def test_cn_etf_beta_precompute_supports_a0_core_satellite_v2(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2024-01-02", periods=320)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 5.9, len(trading_days), dtype=float)
        close_510500 = np.linspace(3.0, 6.1, len(trading_days), dtype=float)
        close_512100 = np.linspace(2.0, 4.6, len(trading_days), dtype=float)
        close_512890 = np.linspace(2.5, 3.7, len(trading_days), dtype=float)
        close_159915 = np.linspace(3.2, 6.4, len(trading_days), dtype=float)
        close_511010 = np.linspace(3.0, 3.3, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510500.sh", "512100.sh", "512890.sh", "159915.sz", "511010.sh"],
            close=np.column_stack([close_510300, close_510500, close_512100, close_512890, close_159915, close_511010]),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.1,
                    close_510500 - 0.1,
                    close_512100 - 0.1,
                    close_512890 - 0.05,
                    close_159915 - 0.12,
                    close_511010 - 0.03,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array(["BULL"] * len(trading_days), dtype=object)
        self._effective_state_5_arr = np.array(["BULL"] * len(trading_days), dtype=object)
        self._regime_risk_budget_multiplier_arr = np.ones(len(trading_days), dtype=float)
        self._risk_budget_multiplier_arr = np.ones(len(trading_days), dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 120.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        governed_a_share={
            "etf_beta": {
                "research_rule_family": "broad_based_rotation_template_a0_core_satellite_v2",
                "template_id": "broad_based_rotation_template_a0_core_satellite_v2",
                "template_asset_pool_version": "A0_V2",
                "template_role_map": {
                    "510300.SH": "hs300",
                    "510500.SH": "csi500",
                    "512100.SH": "csi1000_proxy",
                    "512890.SH": "dividend_proxy",
                    "159915.SZ": "growth_seat",
                },
                "template_proxy_map": {
                    "512100.SH": "CSI1000_STANDARD",
                    "512890.SH": "DIVIDEND_STANDARD",
                },
                "template_target_formal_symbols": [
                    "510300.SH",
                    "510500.SH",
                    "159845.SZ",
                    "510880.SH",
                    "159915.SZ",
                ],
                "proxy_replacement_mode": "none",
                "formal_replacement_pairs": {
                    "512100.SH": "159845.SZ",
                    "512890.SH": "510880.SH",
                },
                "core_slot_symbols": ["510300.SH", "510500.SH", "512100.SH", "512890.SH"],
                "growth_slot_symbols": ["159915.SZ"],
                "growth_seat_symbol": "159915.SZ",
                "core_beta_symbols": ["510300.SH", "510500.SH", "512100.SH", "512890.SH", "159915.SZ"],
                "limited_defense_candidates": [],
                "rebalance_frequency": "monthly",
                "absolute_filter_mode": "ma200_and_positive_12m",
                "fallback_mode": "single_symbol",
                "fallback_symbol": "511010.SH",
                "relative_strength_fast_window": 63,
                "relative_strength_mid_window": 126,
                "relative_strength_slow_window": 252,
                "relative_strength_fast_weight": 0.2,
                "relative_strength_mid_weight": 0.3,
                "relative_strength_slow_weight": 0.5,
                "max_selected_symbols": 2,
            }
        },
    )

    assert provider._etf_beta_rule_family == "broad_based_rotation_template_a0_core_satellite_v2"
    assert provider._etf_beta_proxy_replacement_mode == "none"
    assert provider._etf_beta_formal_replacement_pairs["512100.SH"] == "159845.SZ"
    latest_selected = provider._etf_beta_selected_symbols_arr[-1]
    assert latest_selected == ["512100.SH", "159915.SZ"]
    assert provider._etf_beta_core_slot_selected_symbol_arr[-1] == "512100.SH"
    assert provider._etf_beta_growth_slot_selected_symbol_arr[-1] == "159915.SZ"
    latest_reason_codes = provider._etf_beta_selection_reason_codes_arr[-1]
    assert "SLOT::CORE_SLOT" in latest_reason_codes["512100.SH"]
    assert "SLOT::GROWTH_SLOT" in latest_reason_codes["159915.SZ"]
    slot_selection_reason_codes = provider._etf_beta_slot_selection_reason_codes_arr[-1]
    assert "SELECTED::512100.SH" in slot_selection_reason_codes["core_slot"]
    assert "SELECTED::159915.SZ" in slot_selection_reason_codes["growth_slot"]


def test_cn_etf_beta_a0_core_satellite_v2_light_state_only_keeps_core_slot(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2024-01-02", periods=320)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        close_510300 = np.linspace(4.0, 5.9, len(trading_days), dtype=float)
        close_510500 = np.linspace(3.0, 6.1, len(trading_days), dtype=float)
        close_512100 = np.linspace(2.0, 4.6, len(trading_days), dtype=float)
        close_512890 = np.linspace(2.5, 3.7, len(trading_days), dtype=float)
        close_159915 = np.linspace(3.2, 6.4, len(trading_days), dtype=float)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510500.sh", "512100.sh", "512890.sh", "159915.sz"],
            close=np.column_stack([close_510300, close_510500, close_512100, close_512890, close_159915]),
        )
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack(
                [
                    close_510300 - 0.1,
                    close_510500 - 0.1,
                    close_512100 - 0.1,
                    close_512890 - 0.05,
                    close_159915 - 0.12,
                ]
            )
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array(["LIGHT"] * len(trading_days), dtype=object)
        self._effective_state_5_arr = np.array(["LIGHT"] * len(trading_days), dtype=object)
        self._regime_risk_budget_multiplier_arr = np.full(len(trading_days), 0.5, dtype=float)
        self._risk_budget_multiplier_arr = np.full(len(trading_days), 0.5, dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 110.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        governed_a_share={
            "etf_beta": {
                "research_rule_family": "broad_based_rotation_template_a0_core_satellite_v2",
                "core_slot_symbols": ["510300.SH", "510500.SH", "512100.SH", "512890.SH"],
                "growth_slot_symbols": ["159915.SZ"],
                "growth_seat_symbol": "159915.SZ",
                "core_beta_symbols": ["510300.SH", "510500.SH", "512100.SH", "512890.SH", "159915.SZ"],
                "rebalance_frequency": "monthly",
                "absolute_filter_mode": "ma200_and_positive_12m",
                "fallback_mode": "cash",
                "relative_strength_fast_window": 63,
                "relative_strength_mid_window": 126,
                "relative_strength_slow_window": 252,
                "relative_strength_fast_weight": 0.2,
                "relative_strength_mid_weight": 0.3,
                "relative_strength_slow_weight": 0.5,
                "max_selected_symbols": 2,
            }
        },
    )

    latest_selected = provider._etf_beta_selected_symbols_arr[-1]
    assert latest_selected == ["512100.SH"]
    assert provider._etf_beta_core_slot_selected_symbol_arr[-1] == "512100.SH"
    assert provider._etf_beta_growth_slot_selected_symbol_arr[-1] is None
    slot_under_deploy = provider._etf_beta_slot_under_deploy_reason_codes_arr[-1]
    assert "ETF_BETA_GROWTH_SLOT_SUPPRESSED_BY_SLOT_CAP" in slot_under_deploy["growth_slot"]


def test_cn_etf_beta_day_signals_exposes_vol_target_scale(monkeypatch) -> None:
    trading_days = [pd.Timestamp(day).date() for day in pd.bdate_range("2025-01-02", periods=260)]

    def _fake_super_precompute(self, **_kwargs) -> None:
        vol_returns = np.array([0.03 if idx % 2 == 0 else -0.015 for idx in range(len(trading_days))], dtype=float)
        base_returns = np.array([0.001 for _ in range(len(trading_days))], dtype=float)
        close_510300 = 4.0 * np.cumprod(1.0 + vol_returns)
        close_510050 = 4.0 * np.cumprod(1.0 + base_returns)
        self._mx = SimpleNamespace(
            dates=trading_days,
            symbols=["510300.sh", "510050.sh"],
            close=np.column_stack([close_510300, close_510050]),
        )
        self._sym_to_col = {"sh510300": 0, "sh510050": 1}
        self._feats = SimpleNamespace(
            trend_fast_ma=np.column_stack([close_510300 - 0.1, close_510050 - 0.1]),
        )
        self._market_state = np.array([], dtype=np.int8)
        self._trade_mode = np.array([], dtype=np.int8)
        self._market_state_name_arr = np.array([], dtype=object)
        self._trade_mode_name_arr = np.array([], dtype=object)
        self._market_state_raw_name_arr = np.array([], dtype=object)
        self._market_state_smoothed_name_arr = np.array([], dtype=object)
        self._base_state_5_arr = np.array([], dtype=object)
        self._effective_state_5_arr = np.array([], dtype=object)
        self._regime_risk_budget_multiplier_arr = np.array([], dtype=float)
        self._risk_budget_multiplier_arr = np.array([], dtype=float)

    monkeypatch.setattr(BreakoutTrendProvider, "precompute", _fake_super_precompute)

    provider = CNETFBetaSignalProvider()
    provider.precompute(
        history=pd.DataFrame(),
        benchmark=pd.DataFrame({"date": pd.to_datetime(trading_days), "close": np.linspace(100.0, 130.0, len(trading_days), dtype=float)}),
        raw_history=pd.DataFrame(),
        trading_days=trading_days,
        strategy=SimpleNamespace(),
        market_filter_cfg={
            "enabled": True,
            "long_ma_window": 5,
            "slope_window": 1,
            "slope_ma_period": 3,
            "bull_multiplier": 1.0,
            "light_multiplier": 0.5,
            "trans_down_multiplier": 0.25,
            "trans_up_multiplier": 0.75,
            "bear_multiplier": 0.0,
        },
        governed_a_share={
            "etf_beta": {
                "research_rule_family": "dual_momentum_vol_target",
                "core_beta_symbols": ["510300.SH", "510050.SH"],
                "absolute_filter_mode": "ma120",
                "fallback_mode": "cash",
                "relative_strength_fast_window": 60,
                "relative_strength_slow_window": 120,
                "relative_strength_fast_weight": 0.4,
                "relative_strength_slow_weight": 0.6,
                "max_selected_symbols": 1,
                "vol_target_window": 20,
                "vol_target_annualized_target": 0.18,
                "vol_target_min_scale": 0.35,
                "vol_target_max_scale": 1.0,
            }
        },
    )

    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=1,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )
    day_idx = len(trading_days) - 1
    day_signals = provider.day_signals(trading_days[day_idx], day_idx, ctx)

    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh510300"]
    buy_meta = day_signals.buy_signals[0].meta
    assert float(buy_meta["order_value_scale"]) < 1.0
    assert buy_meta["vol_target_active"] is True
    assert int(buy_meta["vol_target_window"]) == 20
    assert "ETF_BETA_VOL_TARGET_ACTIVE" in day_signals.diagnostics["etf_beta_runtime_reason_codes"]
    assert float(day_signals.diagnostics["etf_beta_vol_target_scale_by_symbol"]["510300.SH"]) < 1.0


def test_cn_etf_beta_day_signals_buy_fallback_symbol_when_selected() -> None:
    trading_day = date(2026, 3, 20)
    provider = CNETFBetaSignalProvider()
    provider._mx = SimpleNamespace(
        symbols=["sh510300", "sh511010"],
        close=np.array([[4.0, 3.1]], dtype=float),
        dates=[trading_day],
    )
    provider._feats = SimpleNamespace(
        trend_fast_ma=np.array([[3.5, 3.0]], dtype=float),
    )
    provider._sym_to_col = {"sh510300": 0, "sh511010": 1}
    provider._effective_state_5_arr = np.array(["BULL"], dtype=object)
    provider._trade_mode_name_arr = np.array(["TREND_MAIN"], dtype=object)
    provider._etf_beta_slot_cap_arr = np.array([1], dtype=np.int32)
    provider._etf_beta_rebalance_flag_arr = np.array([True], dtype=bool)
    provider._etf_beta_formal_scope_symbols = ["510300.SH"]
    provider._etf_beta_eligible_symbols_arr = np.array([[]], dtype=object)
    provider._etf_beta_selected_symbols_arr = np.array([["511010.SH"]], dtype=object)
    provider._etf_beta_selection_reason_codes_arr = np.array(
        [{"511010.SH": ["ETF_BETA_FALLBACK_SINGLE_SYMBOL", "FALLBACK_SYMBOL::511010.SH"]}],
        dtype=object,
    )
    provider._etf_beta_runtime_reason_codes_arr = np.array(
        [["ETF_BETA_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER", "ETF_BETA_FALLBACK_ACTIVE"]],
        dtype=object,
    )
    provider._etf_beta_rule_family = "dual_momentum_basic"
    provider._etf_beta_absolute_filter_mode = "positive_12m"
    provider._etf_beta_fallback_mode = "single_symbol"
    provider._etf_beta_fallback_symbol = "sh511010"

    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=1,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )

    day_signals = provider.day_signals(trading_day, 0, ctx)

    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh511010"]
    assert [signal.reason_code for signal in day_signals.buy_signals] == ["ETF_BETA_FALLBACK_BUY"]
    assert "ETF_BETA_FALLBACK_ACTIVE" in day_signals.diagnostics["etf_beta_runtime_reason_codes"]


def test_cn_etf_beta_day_signals_partial_fallback_fill_when_second_slot_missing() -> None:
    trading_day = date(2026, 3, 20)
    provider = CNETFBetaSignalProvider()
    provider._mx = SimpleNamespace(
        symbols=["sh510300", "sh510050", "sh511010"],
        close=np.array([[4.0, 2.8, 3.1]], dtype=float),
        dates=[trading_day],
    )
    provider._feats = SimpleNamespace(
        trend_fast_ma=np.array([[3.5, 2.7, 3.0]], dtype=float),
    )
    provider._sym_to_col = {"sh510300": 0, "sh510050": 1, "sh511010": 2}
    provider._effective_state_5_arr = np.array(["BULL"], dtype=object)
    provider._trade_mode_name_arr = np.array(["TREND_MAIN"], dtype=object)
    provider._etf_beta_slot_cap_arr = np.array([2], dtype=np.int32)
    provider._etf_beta_rebalance_flag_arr = np.array([True], dtype=bool)
    provider._etf_beta_formal_scope_symbols = ["510300.SH", "510050.SH"]
    provider._etf_beta_eligible_symbols_arr = np.array([["510300.SH"]], dtype=object)
    provider._etf_beta_selected_symbols_arr = np.array([["510300.SH", "511010.SH"]], dtype=object)
    provider._etf_beta_selection_reason_codes_arr = np.array(
        [
            {
                "510300.SH": ["ETF_BETA_CORE_SCOPE", "ABSOLUTE_MA120_PASS"],
                "511010.SH": [
                    "ETF_BETA_FALLBACK_SINGLE_SYMBOL",
                    "FALLBACK_SYMBOL::511010.SH",
                    "UNDERFILLED_DEPLOYMENT_FILL",
                ],
            }
        ],
        dtype=object,
    )
    provider._etf_beta_runtime_reason_codes_arr = np.array(
        [["ETF_BETA_WEEKLY_SELECTION_ACTIVE", "ETF_BETA_FALLBACK_ACTIVE", "ETF_BETA_FALLBACK_PARTIAL_FILL_ACTIVE"]],
        dtype=object,
    )
    provider._etf_beta_rule_family = "dual_momentum_basic"
    provider._etf_beta_absolute_filter_mode = "ma120"
    provider._etf_beta_fallback_mode = "single_symbol"
    provider._etf_beta_fallback_symbol = "sh511010"
    provider._etf_beta_max_selected_symbols = 2

    ctx = DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=2,
        close_idx={},
        open_idx={},
        next_day=None,
        holding_sources={},
        asset_context={"asset_scope": "cn_etf"},
        risk_on=True,
        market_state="BULL",
    )

    day_signals = provider.day_signals(trading_day, 0, ctx)

    assert [signal.symbol for signal in day_signals.buy_signals] == ["sh510300", "sh511010"]
    assert [signal.reason_code for signal in day_signals.buy_signals] == ["ETF_BETA_WEEKLY_RS", "ETF_BETA_FALLBACK_BUY"]
    assert day_signals.diagnostics["etf_beta_selected_cap"] == 2
    assert day_signals.diagnostics["etf_beta_fallback_active"] is True
    assert "ETF_BETA_FALLBACK_PARTIAL_FILL_ACTIVE" in day_signals.diagnostics["etf_beta_under_deploy_reason_codes"]
