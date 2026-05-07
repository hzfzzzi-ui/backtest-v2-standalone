from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.core.config.models import (
    BacktestConfig,
    BenchmarkRegimeConfig,
    BreadthConfig,
    CostConfig,
    DataScopeConfig,
    DataSourceConfig,
    DBConfig,
    DBRuntimeConfig,
    ExecutionConfig,
    ExitConfig,
    MarketFilterConfig,
    RiskBudgetConfig,
    RiskConfig,
    SizingConfig,
    StrategyConfig,
    UniverseConfig,
)
from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.signal_provider import DaySignals
from backend.core.services.sim_account_reconcile_service import (
    load_latest_reconcile_run,
    load_latest_reconcile_summary,
    run_position_aware_reconcile,
)
from backend.core.services.sim_account_service import store_holdings_snapshot
from backend.core.tools.data_bundle_builder import DataBundle


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _bundle(*, price_map: dict[str, float]) -> DataBundle:
    trading_day = date.fromisoformat("2026-03-16")
    raw_rows = [
        {
            "date": pd.Timestamp(trading_day),
            "symbol": symbol,
            "open": float(price),
            "close": float(price),
            "volume": 100000.0,
            "amount": float(price) * 100000.0,
            "is_suspended": False,
            "limit_up": float(price) * 1.1,
            "limit_down": float(price) * 0.9,
        }
        for symbol, price in price_map.items()
    ]
    benchmark_rows = [
        {
            "date": pd.Timestamp(trading_day),
            "symbol": "000300.SH",
            "open": 100.0,
            "close": 101.0,
        }
    ]
    raw_history = pd.DataFrame(raw_rows)
    return DataBundle(
        provider=None,  # type: ignore[arg-type]
        universe_mode="CUSTOM",
        symbols=sorted(price_map),
        universe_meta={"universe_mode": "CUSTOM"},
        universe_filters_raw={},
        resolve_asof=trading_day,
        dynamic_all_a_entry=False,
        raw_history=raw_history,
        signal_history=raw_history.copy(deep=True),
        benchmark=pd.DataFrame(benchmark_rows),
        trading_days=[trading_day],
        st_history=pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type"]),
        sector_data={},
        industry_map={},
        industry_history=pd.DataFrame(columns=["ts_code", "start_date", "end_date"]),
        price_adj_mode="hfq",
        adj_factor_stats={"min": 1.0, "max": 1.0, "null_count": 0},
        summary={"symbols_count": len(price_map)},
    )


def _cfg_obj() -> BacktestConfig:
    return BacktestConfig(
        db=DBConfig(host="localhost", port=5432, dbname="pams", user="pams", password=""),
        db_runtime=DBRuntimeConfig(),
        universe=UniverseConfig(
            symbols=[],
            benchmark="000300.SH",
            start=date.fromisoformat("2025-01-01"),
            end=date.fromisoformat("2026-03-16"),
        ),
        data_source=DataSourceConfig(),
        schema_mapping={},
        data_scope=DataScopeConfig(),
        execution=ExecutionConfig(lot_size=100),
        sizing=SizingConfig(order_value=0.0, lot_size=100, min_positions=1),
        costs=CostConfig(),
        exit=ExitConfig(),
        risk=RiskConfig(),
        risk_budget=RiskBudgetConfig(enabled=False),
        market_filter=MarketFilterConfig(enabled=False),
        benchmark_regime=BenchmarkRegimeConfig(enabled=False),
        breadth=BreadthConfig(enabled=False),
        strategy=StrategyConfig(name="sma_cross"),
        initial_capital=100000.0,
    )


def _setup_latest_experiment(tmp_path, *, order_value: float = 0.0, max_positions: int = 3) -> tuple:
    results_root = tmp_path / "outputs"
    exp_id = "exp_reconcile_001"
    exp_dir = results_root / "experiments" / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        results_root / "experiments" / "index.json",
        [
            {
                "exp_id": exp_id,
                "label": "reconcile-test",
                "created_at": "2026-03-16T15:10:00+08:00",
                "status": "OK",
            }
        ],
    )
    _write_json(
        exp_dir / "manifest.json",
        {
            "artifacts": {
                "stock_names": "stock_names.json",
            }
        },
    )
    _write_json(
        exp_dir / "resolved_config.json",
        {
            "config_json": {
                "asset_scope": "cn_a_equity",
                "universe_mode": "CUSTOM",
                "position_risk": {"max_positions": max_positions},
                "universe": {"price_adj": "hfq"},
            }
        },
    )
    _write_json(
        exp_dir / "compiled_plan.json",
        {
            "runtime_config": {
                "initial_capital": 100000.0,
                "execution": {"lot_size": 100},
                "sizing": {"order_value": order_value},
                "asset_context": {},
                "universe": {"end": "2026-03-16"},
            },
            "execution_overrides": {
                "max_positions": max_positions,
            },
        },
    )
    _write_json(
        exp_dir / "stock_names.json",
        {
            "sh600000": "浦发银行",
            "sh600036": "招商银行",
            "sh600519": "贵州茅台",
        },
    )
    return results_root, exp_dir


def _patch_runtime(monkeypatch, *, provider, bundle: DataBundle) -> None:
    monkeypatch.setattr(
        "backend.core.services.sim_account_reconcile_service.load_config",
        lambda _path: (_cfg_obj(), "runtime_hash_test"),
    )
    monkeypatch.setattr(
        "backend.core.services.sim_account_reconcile_service.build_data_bundle",
        lambda **kwargs: bundle,
    )
    monkeypatch.setattr(
        "backend.core.services.sim_account_reconcile_service.build_strategy",
        lambda _cfg: SimpleNamespace(state={}, portfolio_mode="equal_10"),
    )
    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.bridge_adapter.build_signal_provider",
        lambda strategy, asset_context=None: ("strict_inline_runtime", provider),
    )
    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.bridge_adapter.precompute_signal_provider",
        lambda *args, **kwargs: None,
    )


def test_run_position_aware_reconcile_builds_buy_sell_hold_and_caps_sellable_qty(tmp_path, monkeypatch) -> None:
    results_root, _exp_dir = _setup_latest_experiment(tmp_path, order_value=0.0, max_positions=3)
    store_holdings_snapshot(
        results_root,
        {
            "account_id": "paper_a_share_main",
            "trade_date": "2026-03-16",
            "synced_at": "2026-03-16T15:20:00+08:00",
            "cash": 2500,
            "positions": [
                {"symbol": "600000.SH", "qty": 200, "sellable_qty": 100, "avg_cost": 10.0, "name": "浦发银行"},
                {"symbol": "600036.SH", "qty": 100, "sellable_qty": 100, "avg_cost": 40.0, "name": "招商银行"},
            ],
        },
    )

    class _Provider:
        extra_clear_dicts = []
        last_sell_day = None
        entry_day = {}
        entry_day_overwrite = False
        peak_state_on_buy = None

        def day_signals(self, day, day_idx, ctx):
            return DaySignals(
                sell_signals=[
                        Signal(
                            signal_date=day,
                            symbol="sh600000",
                            side=Side.SELL,
                            qty=200,
                            reason="EXIT_ALL",
                            reason_code="EXIT_ALL",
                            meta={},
                        )
                    ],
                    buy_signals=[
                        Signal(
                            signal_date=day,
                            symbol="sh600519",
                            side=Side.BUY,
                            qty=0,
                            reason="BREAKOUT_HIGH",
                            reason_code="BREAKOUT_HIGH",
                            meta={},
                        )
                    ],
                )

    _patch_runtime(
        monkeypatch,
        provider=_Provider(),
        bundle=_bundle(price_map={"sh600000": 10.0, "sh600036": 40.0, "sh600519": 20.0}),
    )

    payload = run_position_aware_reconcile(results_root, "paper_a_share_main")

    assert payload["summary"] == {
        "action_count": 3,
        "buy_count": 1,
        "sell_count": 1,
        "hold_count": 1,
        "blocked_count": 0,
    }
    buy_row = payload["actions"]["buy"][0]
    sell_row = payload["actions"]["sell"][0]
    hold_row = payload["actions"]["hold"][0]

    assert buy_row["symbol"] == "sh600519"
    assert buy_row["reference_price_basis"] == "latest_close"
    assert buy_row["suggested_qty"] == 100

    assert sell_row["symbol"] == "sh600000"
    assert sell_row["current_qty"] == 200
    assert sell_row["sellable_qty"] == 100
    assert sell_row["suggested_qty"] == 100
    assert sell_row["target_qty"] == 100
    assert sell_row["delta_qty"] == -100

    assert hold_row["symbol"] == "sh600036"
    assert hold_row["action_type"] == "hold"
    assert hold_row["target_qty"] == 100

    latest = load_latest_reconcile_run(results_root, "paper_a_share_main")
    assert latest is not None
    assert latest["reconcile_id"] == payload["reconcile_id"]
    summary = load_latest_reconcile_summary(results_root, "paper_a_share_main")
    assert summary is not None
    assert summary["reconcile_id"] == payload["reconcile_id"]
    assert summary["object_type"] == "reconcile_summary"
    assert summary["object_scope"] == "account_ops"
    assert summary["source_kind"] == "derived_summary"
    assert summary["summary"]["buy_count"] == 1
    assert (results_root / "ops" / "sim_account" / "paper_a_share_main" / "reconcile" / "summary" / "latest.json").exists()


@pytest.mark.parametrize(
    ("max_positions", "cash", "positions", "price_map", "expected_reason"),
    [
        (1, 1500.0, [], {"sh600519": 20.0}, "SKIP_QTY_ZERO"),
        (
            2,
            500.0,
            [
                {
                    "symbol": "600000.SH",
                    "qty": 100,
                    "sellable_qty": 100,
                    "avg_cost": 100.0,
                    "name": "浦发银行",
                }
            ],
            {"sh600000": 100.0, "sh600519": 20.0},
            "SKIP_NO_CASH",
        ),
    ],
)
def test_run_position_aware_reconcile_surfaces_lot_and_cash_reject_reasons(
    tmp_path,
    monkeypatch,
    *,
    max_positions: int,
    cash: float,
    positions,
    price_map,
    expected_reason: str,
) -> None:
    results_root, _exp_dir = _setup_latest_experiment(tmp_path, order_value=0.0, max_positions=max_positions)
    store_holdings_snapshot(
        results_root,
        {
            "account_id": "paper_a_share_main",
            "trade_date": "2026-03-16",
            "synced_at": "2026-03-16T15:20:00+08:00",
            "cash": cash,
            "positions": positions,
        },
    )

    class _Provider:
        extra_clear_dicts = []
        last_sell_day = None
        entry_day = {}
        entry_day_overwrite = False
        peak_state_on_buy = None

        def day_signals(self, day, day_idx, ctx):
            return DaySignals(
                sell_signals=[],
                buy_signals=[
                        Signal(
                            signal_date=day,
                            symbol="sh600519",
                            side=Side.BUY,
                            qty=0,
                            reason="BREAKOUT_HIGH",
                            reason_code="BREAKOUT_HIGH",
                            meta={},
                        )
                    ],
                )

    _patch_runtime(
        monkeypatch,
        provider=_Provider(),
        bundle=_bundle(price_map=price_map),
    )

    payload = run_position_aware_reconcile(results_root, "paper_a_share_main")

    assert payload["summary"]["buy_count"] == 0
    assert payload["summary"]["sell_count"] == 0
    reject_counts = {
        **dict(payload["diagnostics"].get("order_reject_reason_counts") or {}),
        **dict(payload["diagnostics"].get("reason_counts") or {}),
    }
    assert reject_counts[expected_reason] == 1
