from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from backend.core.portfolio.types import PortfolioBacktestResult
from backend.core.tools import experiment_runner as mod


def test_run_experiment_routes_through_foundation_shell(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "initial_capital": 1000000,
                "universe": {},
                "execution": {},
                "sizing": {},
                "strategy": {"name": "breakout_trend", "params": {}},
            }
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    monkeypatch.setattr(mod, "_results_root", lambda: tmp_path)
    monkeypatch.setattr(
        mod,
        "load_config",
        lambda _path: (
            SimpleNamespace(
                initial_capital=1000000.0,
                execution=SimpleNamespace(lot_size=100),
                sizing=SimpleNamespace(order_value=10000.0),
                costs=SimpleNamespace(),
                exit=SimpleNamespace(),
                risk_budget=SimpleNamespace(),
                market_filter=SimpleNamespace(),
                benchmark_regime=SimpleNamespace(),
                breadth=SimpleNamespace(),
                strategy=SimpleNamespace(),
                universe=SimpleNamespace(benchmark="000300.SH"),
            ),
            None,
        ),
    )
    monkeypatch.setattr(
        mod,
        "build_data_bundle",
        lambda **_kwargs: SimpleNamespace(
            universe_filters_raw={},
            dynamic_all_a_entry=False,
            membership_history=None,
            trading_days=[pd.Timestamp("2026-03-02").date()],
            symbols=["sh600000"],
            st_history=pd.DataFrame(),
            sector_data={},
            industry_map={},
            price_adj_mode="hfq",
            adj_factor_stats={},
            summary={"symbols_count": 1},
            benchmark=pd.DataFrame(),
            signal_history=pd.DataFrame(),
            raw_history=pd.DataFrame(),
            universe_meta={},
        ),
    )
    monkeypatch.setattr(
        mod,
        "build_strategy",
        lambda _strategy_cfg: SimpleNamespace(
            state={},
            set_context=lambda _ctx: None,
        ),
    )

    def _fake_run_foundation_execution_shell(request):
        captured["request"] = request
        return PortfolioBacktestResult(
            daily=pd.DataFrame(
                [
                    {
                        "date": "2026-03-02",
                        "nav": 1.0,
                        "cash": 1.0,
                        "positions_count": 0,
                        "positions_count_end_of_day": 0,
                        "daily_return": 0.0,
                        "drawdown": 0.0,
                    }
                ]
            ),
            trades=pd.DataFrame(columns=["date", "symbol", "side"]),
            candidates=pd.DataFrame(columns=["date", "symbol"]),
            metrics={
                "total_return": 0.0,
                "max_drawdown": 0.0,
                "cagr": 0.0,
                "sharpe": 0.0,
                "calmar": 0.0,
                "trades": 0,
                "turnover": 0.0,
                "orders": 0,
                "closed_trades": 0,
            },
        )

    monkeypatch.setattr(mod, "run_foundation_execution_shell", _fake_run_foundation_execution_shell)

    result = mod.run_experiment(str(config_path), "single", overrides={})

    assert "request" in captured
    request = captured["request"]
    assert request.compiled_plan.execution_assumptions["execution_clock"] == "NEXT_OPEN"
    assert request.compiled_plan.execution_assumptions["signal_clock"] == "POST_CLOSE"
    assert result["status"] == "OK"
