from __future__ import annotations

import time
from datetime import date
from types import SimpleNamespace

from pytest import MonkeyPatch

from backend.core.core.types import Side
from backend.core.stage_pipeline.adapters.daily_accounting import prepare_daily_snapshot
from backend.core.stage_pipeline.adapters.fill_accounting import apply_open_fills
from backend.core.stage_pipeline.adapters.result_bridge import build_portfolio_backtest_result


def test_apply_open_fills_sell_clears_position_and_updates_provider_state() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600000"): 10.0},
        close_idx={(trading_day, "sh600000"): 10.1},
        _slip_bps=0.001,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=1000.0,
        _traded_value_today=0.0,
        positions={"sh600000": 100},
        position_avg_cost={"sh600000": 9.5},
        provider=SimpleNamespace(
            last_sell_day={},
            extra_clear_dicts=[{"sh600000": {"cached": True}}],
            entry_day={"sh600000": trading_day},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.SELL,
        symbol="SH600000",
        qty=100,
        reason_code="EXIT",
        meta={"triggered_rule": "RULE_X", "break_streak": 2},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.positions == {}
    assert runtime.position_avg_cost == {}
    assert round(runtime.cash, 3) == 1997.001
    assert round(runtime._traded_value_today, 3) == 999.0
    assert runtime.provider.last_sell_day["sh600000"] == trading_day
    assert runtime.provider.extra_clear_dicts[0] == {}
    assert runtime.provider.entry_day == {}
    assert runtime.trade_rows[0]["side"] == "SELL"
    assert runtime.trade_rows[0]["reason_code"] == "EXIT"
    assert runtime.trade_rows[0]["triggered_rule"] == "RULE_X"


def test_apply_open_fills_buy_updates_avg_cost_and_buy_side_effects() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600001"): 10.0},
        close_idx={(trading_day, "sh600001"): 10.2},
        _slip_bps=0.001,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=2000.0,
        _traded_value_today=0.0,
        positions={},
        position_avg_cost={},
        provider=SimpleNamespace(
            entry_day={},
            entry_day_overwrite=False,
            peak_state_on_buy={},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.BUY,
        symbol="SH600001",
        qty=100,
        reason_code="ENTRY",
        meta={"triggered_rule": "RULE_Y", "break_streak": 1},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.positions == {"sh600001": 100}
    assert round(runtime.position_avg_cost["sh600001"], 2) == 10.01
    assert round(runtime.cash, 2) == 998.0
    assert round(runtime._traded_value_today, 2) == 1001.0
    assert runtime.provider.entry_day["sh600001"] == trading_day
    assert runtime.provider.peak_state_on_buy["sh600001"] == 10.2
    assert runtime.trade_rows[0]["side"] == "BUY"
    assert runtime.trade_rows[0]["reason_code"] == "ENTRY"
    assert runtime.trade_rows[0]["triggered_rule"] == "RULE_Y"


def test_prepare_daily_snapshot_updates_nav_trackers_and_daily_row() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        cash=1000.0,
        positions={"sh600000": 100},
        close_idx={(trading_day, "sh600000"): 10.0},
        peak_nav=900.0,
        prev_nav=950.0,
        _traded_value_today=95.0,
        daily_rows=[],
        route_id="strict_inline_runtime",
        _compute_day_controls=lambda *_args: {
            "effective_max_positions": 5,
            "dd_state": "NORMAL",
            "market_state": "",
            "trade_mode": "",
            "benchmark_regime_on": True,
            "risk_on_today": True,
        },
    )

    snapshot = prepare_daily_snapshot(runtime, day_index=0, day=trading_day)

    assert snapshot.nav == 2000.0
    assert snapshot.market_value == 1000.0
    assert snapshot.controls["effective_max_positions"] == 5
    assert runtime.prev_nav == 2000.0
    assert runtime.peak_nav == 2000.0
    assert runtime.daily_rows[0]["date"] == "2026-03-02"
    assert runtime.daily_rows[0]["positions_count"] == 1
    assert round(runtime.daily_rows[0]["turnover_pct"], 2) == 0.10


def test_build_portfolio_backtest_result_preserves_metrics_shape() -> None:
    captured: dict[str, object] = {}

    def _fake_compute_metrics(*args, **kwargs):
        captured["daily_df"] = args[0]
        captured["trades_df"] = args[1]
        captured["kwargs"] = kwargs
        return {"audit": {}, "baseline": "ok"}

    monkeypatch = MonkeyPatch()
    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.result_bridge._compute_metrics",
        _fake_compute_metrics,
    )
    try:
        runtime = SimpleNamespace(
            daily_rows=[{"date": "2026-03-02", "nav": 1.0, "drawdown": 0.0}],
            trade_rows=[{"date": "2026-03-02", "symbol": "sh600000", "side": "BUY"}],
            candidate_rows=[{"date": "2026-03-02", "symbol": "sh600000"}],
            request=SimpleNamespace(max_positions=5, enable_strength_rank=False, strength_ma=120),
            provider=SimpleNamespace(
                precompute_seconds=1.25,
                blocked_by_trend_count=3,
                total_buy_signals=7,
                diag_reason_counts={"ATR_STOP_LOSS": 2, "TREND_EXIT_MA20": 1},
            ),
            route_id="provider_breakout_runtime",
            _simulation_t0=time.perf_counter() - 2.0,
            market_filter_bull_days=11,
            market_filter_bear_days=2,
            market_state_trans_down_days=3,
            market_state_trans_up_days=4,
            trade_mode_main_days=5,
            trade_mode_light_days=6,
            trade_mode_notrade_days=7,
        )

        result = build_portfolio_backtest_result(runtime)
    finally:
        monkeypatch.undo()

    assert list(captured["daily_df"]["date"]) == ["2026-03-02"]
    assert list(captured["trades_df"]["symbol"]) == ["sh600000"]
    assert result.metrics["baseline"] == "ok"
    assert result.metrics["notes"] == "stage_pipeline_legacy_adapter=true"
    assert result.metrics["precompute_seconds"] == 1.25
    assert result.metrics["blocked_by_trend_count"] == 3
    assert result.metrics["exit_atr_stop_count"] == 2
    assert result.metrics["exit_ma20_count"] == 1
    assert result.metrics["trade_mode_notrade_days"] == 7
