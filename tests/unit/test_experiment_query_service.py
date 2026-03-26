from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.core.config.models import BenchmarkRegimeConfig, CostConfig, MarketFilterConfig, RiskBudgetConfig, SizingConfig
from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.services import experiment_query_service
from backend.core.stage_pipeline.adapters.bridge_adapter import StagePipelineBridgeRequest, run_stage_pipeline_bridge_backtest
from backend.core.strategies.base import Strategy
from backend.core.strategies.composite_strategy import CompositeStrategy
from backend.core.tools import locked_candidate_presets
from backend.core.tools.data_bundle_builder import DataBundle


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class _ScriptedStrategy(Strategy):
    def __init__(self, scripted_signals: dict[object, list[Signal]]) -> None:
        super().__init__()
        self._scripted_signals = scripted_signals

    def generate_signals(self, day, history, positions):
        return list(self._scripted_signals.get(day, []))


def _generic_bundle() -> DataBundle:
    days = [ts.date() for ts in pd.bdate_range("2024-01-02", periods=5)]
    raw_rows = [
        {
            "date": pd.Timestamp(day),
            "symbol": "sh600000",
            "open": 10.0 + idx,
            "close": 10.2 + idx,
            "high": 10.4 + idx,
            "low": 9.8 + idx,
            "volume": 100000.0,
            "amount": 1000000.0,
            "is_suspended": False,
            "limit_up": 20.0 + idx,
            "limit_down": 1.0,
        }
        for idx, day in enumerate(days)
    ]
    benchmark_rows = [
        {"date": pd.Timestamp(day), "symbol": "000300.SH", "open": 100.0 + idx, "close": 100.5 + idx}
        for idx, day in enumerate(days)
    ]
    raw_history = pd.DataFrame(raw_rows)
    return DataBundle(
        provider=None,  # type: ignore[arg-type]
        universe_mode="CUSTOM",
        symbols=["sh600000"],
        universe_meta={"universe_mode": "CUSTOM"},
        universe_filters_raw={},
        resolve_asof=days[0],
        dynamic_all_a_entry=False,
        raw_history=raw_history,
        signal_history=raw_history.copy(deep=True),
        benchmark=pd.DataFrame(benchmark_rows),
        trading_days=days,
        st_history=pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type"]),
        sector_data={},
        industry_map={"sh600000": "Bank"},
        price_adj_mode="hfq",
        adj_factor_stats={"min": 1.0, "max": 1.0, "null_count": 0},
        summary={"symbols_count": 1},
    )


def test_get_experiment_surface_and_sections(tmp_path: Path, monkeypatch) -> None:
    exp_dir = tmp_path / "exp_surface"
    exp_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        exp_dir / "manifest.json",
        {
            "exp_id": "exp_surface",
            "experiment_id": "exp_surface",
            "status": "OK",
            "created_at": "2026-03-15T09:00:00",
            "schema_version": "backtest_v2_experiment_manifest@2",
            "artifacts": {
                "perf": "perf.json",
                "audit": "audit.json",
                "nav": "nav.csv",
                "run_meta": "run_meta.json",
                "symbol_performance": "symbol_performance.csv",
                "config": "config.json",
                "trades": "portfolio_trades.csv",
                "daily": "portfolio_daily.csv",
                "reason_codes": "reason_codes.csv",
                "cash_blocked_buys_recent": "cash_blocked_buys_recent.csv",
                "stock_names": "stock_names.json",
            },
            "stage_pipeline": {
                "route_id": "provider_breakout_runtime",
                "execution_shell": "stage_pipeline_shell_bridge",
            },
        },
    )
    _write_json(
        exp_dir / "perf.json",
        {
            "cagr": 0.12,
            "sharpe": 1.1,
            "max_drawdown": -0.2,
            "total_return": 0.35,
            "trades": 12,
            "effective_execution_start_date": "2024-01-03",
        },
    )
    _write_json(exp_dir / "audit.json", {"status": "pass", "warnings": []})
    _write_json(
        exp_dir / "run_meta.json",
        {
            "counters": {
                "buy_stage_funnel": [
                    {"stage_key": "s4", "available": True, "output_count": 10},
                    {"stage_key": "s8", "available": False, "input_count": None, "output_count": None},
                ]
            }
        },
    )
    _write_json(
        exp_dir / "config.json",
        {
            "universe_mode": "HS300_ZZ500",
            "overrides": {
                "original_workbench_config": {
                    "strategy_pack": "BREAKOUT_TREND",
                    "position_risk": {"max_positions": 10},
                }
            },
        },
    )
    _write_json(exp_dir / "stock_names.json", {"sh600519": "贵州茅台"})
    (exp_dir / "nav.csv").write_text("date,nav\n2024-01-03,1.0\n2024-01-04,1.1\n", encoding="utf-8")
    (exp_dir / "symbol_performance.csv").write_text(
        "symbol,return_pct,max_drawdown,trades,net_pnl\nsh600519,0.2,-0.1,3,10000\n",
        encoding="utf-8",
    )
    (exp_dir / "portfolio_trades.csv").write_text(
        "trade_date,symbol,side,qty\n2024-01-03,sh600519,buy,100\n2024-01-04,sh600519,sell,100\n",
        encoding="utf-8",
    )
    (exp_dir / "portfolio_daily.csv").write_text(
        "date,nav,market_state,raw_buy_signal_count,buy_candidate_count\n2024-01-03,1.0,bull,8,3\n2024-01-04,1.1,bull,5,2\n",
        encoding="utf-8",
    )
    (exp_dir / "reason_codes.csv").write_text(
        "reason_code,count\nENTRY_BREAKOUT,2\nEXIT_TRAIL,1\n",
        encoding="utf-8",
    )
    (exp_dir / "cash_blocked_buys_recent.csv").write_text(
        "date,symbol,reject_reason,cash_available,estimated_qty,estimated_amount,estimated_price\n"
        "2024-01-04,sh600519,SKIP_NO_CASH,8800.0,100,9300.0,93.0\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(experiment_query_service, "resolve_experiment_dir_by_id", lambda exp_id: exp_dir)

    surface = experiment_query_service.get_experiment_surface("exp_surface")
    assert surface["summary"]["exp_id"] == "exp_surface"
    assert surface["summary"]["runtime_route"] == "provider_breakout_runtime"
    assert surface["perf"]["cagr"] == 0.12
    assert surface["audit"]["status"] == "pass"
    assert surface["lazy_sections"]["nav"]["available"] is True
    assert surface["lazy_sections"]["stage_funnel"]["available"] is True
    assert surface["lazy_sections"]["run_meta"]["available"] is True
    assert surface["lazy_sections"]["config"]["available"] is True
    assert surface["lazy_sections"]["trades"]["available"] is True
    assert surface["lazy_sections"]["daily"]["available"] is True
    assert surface["lazy_sections"]["reason_codes"]["available"] is True
    assert surface["lazy_sections"]["cash_blocked_buys_recent"]["available"] is True
    assert surface["lazy_sections"]["stock_names"]["available"] is True

    nav_section = experiment_query_service.get_experiment_surface_section("exp_surface", "nav")
    assert nav_section["section"] == "nav"
    assert nav_section["data"][1]["nav"] == 1.1

    dd_section = experiment_query_service.get_experiment_surface_section("exp_surface", "drawdown")
    assert dd_section["data"][0]["drawdown"] == 0.0
    assert dd_section["data"][1]["drawdown"] == 0.0

    funnel_section = experiment_query_service.get_experiment_surface_section("exp_surface", "stage_funnel")
    assert funnel_section["data"][0]["stage_key"] == "s4"
    assert funnel_section["data"][1]["available"] is False
    assert funnel_section["data"][1]["output_count"] is None

    run_meta_section = experiment_query_service.get_experiment_surface_section("exp_surface", "run_meta")
    assert run_meta_section["data"]["counters"]["buy_stage_funnel"][1]["output_count"] is None

    config_section = experiment_query_service.get_experiment_surface_section("exp_surface", "config")
    assert config_section["data"]["overrides"]["original_workbench_config"]["strategy_pack"] == "BREAKOUT_TREND"

    trades_section = experiment_query_service.get_experiment_surface_section("exp_surface", "trades")
    assert trades_section["data"][0]["symbol"] == "sh600519"

    daily_section = experiment_query_service.get_experiment_surface_section("exp_surface", "daily")
    assert daily_section["data"][0]["market_state"] == "bull"

    reason_codes_section = experiment_query_service.get_experiment_surface_section("exp_surface", "reason_codes")
    assert reason_codes_section["data"][0]["reason_code"] == "ENTRY_BREAKOUT"
    cash_blocked_section = experiment_query_service.get_experiment_surface_section("exp_surface", "cash_blocked_buys_recent")
    assert cash_blocked_section["data"][0]["symbol"] == "sh600519"
    assert cash_blocked_section["data"][0]["reject_reason"] == "SKIP_NO_CASH"

    stock_names_section = experiment_query_service.get_experiment_surface_section("exp_surface", "stock_names")
    assert stock_names_section["data"]["sh600519"] == "贵州茅台"


def test_get_experiment_surface_exposes_backend_combo_truth(tmp_path: Path, monkeypatch) -> None:
    stock_dir = tmp_path / "exp_stock_component"
    etf_dir = tmp_path / "exp_etf_component"
    combo_dir = tmp_path / "exp_combo_anchor"
    for path in (stock_dir, etf_dir, combo_dir):
        path.mkdir(parents=True, exist_ok=True)

    def _write_component_bundle(
        exp_dir: Path,
        *,
        exp_id: str,
        asset_scope: str,
        benchmark: str,
        base_state: str,
        effective_state: str,
        risk_budget: float,
        budget_reason: str,
    ) -> None:
        _write_json(
            exp_dir / "manifest.json",
            {
                "exp_id": exp_id,
                "experiment_id": exp_id,
                "status": "OK",
                "created_at": "2026-03-26T09:00:00",
                "schema_version": "backtest_v2_experiment_manifest@2",
                "artifacts": {
                    "perf": "perf.json",
                    "run_meta": "run_meta.json",
                    "config": "config.json",
                    "nav": "nav.csv",
                },
                "stage_pipeline": {
                    "route_id": "provider_breakout_runtime",
                    "execution_shell": "stage_pipeline_shell_bridge",
                },
                "asset_scope": asset_scope,
                "asset_context": {"asset_scope": asset_scope},
            },
        )
        _write_json(exp_dir / "perf.json", {"cagr": 0.1, "total_return": 0.2, "max_drawdown": -0.1})
        _write_json(
            exp_dir / "run_meta.json",
            {
                "data": {
                    "asset_scope": asset_scope,
                    "benchmark": benchmark,
                },
                "regime": {
                    "latest_state": {
                        "base_state": base_state,
                        "effective_state": effective_state,
                        "effective_coarse_state": "RISK_ON",
                    }
                },
                "governed_snapshot": {
                    "budget_consumer_sleeve_id": (
                        "cn_stock_trend_alpha_core" if asset_scope == "cn_a_equity" else "cn_etf_beta"
                    ),
                    "budget_consumer_system_role": (
                        "stock_alpha_sleeve" if asset_scope == "cn_a_equity" else "market_beta_sleeve"
                    ),
                    "total_risk_budget": risk_budget,
                    "budget_reason_codes": [budget_reason],
                },
            },
        )
        _write_json(exp_dir / "config.json", {"mode": "experiment", "asset_scope": asset_scope})
        (exp_dir / "nav.csv").write_text("date,nav\n2026-03-24,1.0\n2026-03-25,1.1\n", encoding="utf-8")

    _write_component_bundle(
        stock_dir,
        exp_id="exp_stock_component",
        asset_scope="cn_a_equity",
        benchmark="000300.SH",
        base_state="TRANS_UP",
        effective_state="BULL",
        risk_budget=0.8,
        budget_reason="STOCK_OK",
    )
    _write_component_bundle(
        etf_dir,
        exp_id="exp_etf_component",
        asset_scope="cn_etf",
        benchmark="510300.SH",
        base_state="LIGHT",
        effective_state="LIGHT",
        risk_budget=0.2,
        budget_reason="ETF_OK",
    )
    _write_json(
        combo_dir / "manifest.json",
        {
            "exp_id": "exp_combo_anchor",
            "experiment_id": "exp_combo_anchor",
            "status": "OK",
            "created_at": "2026-03-26T09:00:00",
            "schema_version": "backtest_v2_experiment_manifest@2",
            "artifacts": {
                "perf": "perf.json",
                "run_meta": "run_meta.json",
                "config": "config.json",
                "nav": "nav.csv",
            },
            "stage_pipeline": {
                "route_id": "cn_stock_etf_research_combo",
                "execution_shell": "read_only_combo",
            },
            "asset_scope": "cn_a_equity",
            "asset_context": {"asset_scope": "cn_a_equity"},
        },
    )
    _write_json(combo_dir / "perf.json", {"cagr": 0.09, "total_return": 0.3, "max_drawdown": -0.12})
    _write_json(
        combo_dir / "run_meta.json",
        {
            "data": {
                "asset_scope": "cn_a_equity",
                "asset_role": "research_combo",
            },
            "research_combo": {"mode": "daily_rebalanced_equal_weight_50_50"},
            "combo_components": {
                "stock_component": {"exp_id": "exp_stock_component"},
                "etf_component": {"exp_id": "exp_etf_component"},
            },
        },
    )
    _write_json(combo_dir / "config.json", {"mode": "experiment", "asset_scope": "cn_a_equity"})
    (combo_dir / "nav.csv").write_text("date,nav\n2026-03-24,1.0\n2026-03-25,1.02\n", encoding="utf-8")

    exp_dirs = {
        "exp_stock_component": stock_dir,
        "exp_etf_component": etf_dir,
        "exp_combo_anchor": combo_dir,
    }
    monkeypatch.setattr(
        experiment_query_service,
        "resolve_experiment_dir_by_id",
        lambda exp_id: exp_dirs.get(exp_id),
    )

    surface = experiment_query_service.get_experiment_surface("exp_combo_anchor")
    assert surface["lazy_sections"]["combo_truth"]["available"] is True

    combo_truth = experiment_query_service.get_experiment_surface_section("exp_combo_anchor", "combo_truth")
    assert combo_truth["section"] == "combo_truth"
    assert combo_truth["data"]["contract_version"] == "research_combo_truth@1"
    assert combo_truth["data"]["display"]["governor"]["budget_consumer_text"] == "cn_stock_trend_alpha_core + cn_etf_beta"
    assert combo_truth["data"]["components"]["stock"]["exp_id"] == "exp_stock_component"
    assert combo_truth["data"]["components"]["etf"]["exp_id"] == "exp_etf_component"
    assert combo_truth["data"]["components"]["stock"]["snapshot"]["artifacts"]["run_meta"]["data"]["benchmark"] == "000300.SH"
    assert combo_truth["data"]["components"]["etf"]["snapshot"]["artifacts"]["run_meta"]["data"]["benchmark"] == "510300.SH"
    assert combo_truth["data"]["components"]["stock"]["snapshot"]["artifacts"]["nav"][1]["nav"] == 1.1
    assert combo_truth["data"]["display"]["regime"]["available"] is True


def test_get_experiment_surface_exposes_unified_combo_truth(tmp_path: Path, monkeypatch) -> None:
    stock_dir = tmp_path / "exp_stock_component"
    etf_dir = tmp_path / "exp_etf_component"
    combo_dir = tmp_path / "exp_combo_unified"
    for path in (stock_dir, etf_dir, combo_dir):
        path.mkdir(parents=True, exist_ok=True)

    def _write_component(exp_dir: Path, *, exp_id: str, asset_scope: str, benchmark: str, risk_budget: float) -> None:
        _write_json(
            exp_dir / "manifest.json",
            {
                "exp_id": exp_id,
                "experiment_id": exp_id,
                "status": "OK",
                "created_at": "2026-03-26T09:00:00",
                "schema_version": "backtest_v2_experiment_manifest@2",
                "artifacts": {
                    "perf": "perf.json",
                    "run_meta": "run_meta.json",
                    "config": "config.json",
                    "nav": "nav.csv",
                },
                "stage_pipeline": {
                    "route_id": "provider_breakout_runtime",
                    "execution_shell": "stage_pipeline_shell_bridge",
                },
                "asset_scope": asset_scope,
                "asset_context": {"asset_scope": asset_scope},
            },
        )
        _write_json(exp_dir / "perf.json", {"cagr": 0.1, "total_return": 0.2, "max_drawdown": -0.1})
        _write_json(
            exp_dir / "run_meta.json",
            {
                "data": {"asset_scope": asset_scope, "benchmark": benchmark},
                "regime": {
                    "latest_state": {
                        "base_state": "BULL",
                        "effective_state": "BULL" if asset_scope == "cn_a_equity" else "LIGHT",
                        "effective_coarse_state": "RISK_ON",
                    }
                },
                "governed_snapshot": {
                    "budget_consumer_sleeve_id": "cn_stock_trend_alpha_core" if asset_scope == "cn_a_equity" else "cn_etf_beta",
                    "budget_consumer_system_role": "stock_alpha_sleeve" if asset_scope == "cn_a_equity" else "market_beta_sleeve",
                    "total_risk_budget": risk_budget,
                    "budget_reason_codes": ["OK"],
                },
            },
        )
        _write_json(exp_dir / "config.json", {"mode": "experiment", "asset_scope": asset_scope})
        (exp_dir / "nav.csv").write_text("date,nav\n2026-03-24,1.0\n2026-03-25,1.1\n", encoding="utf-8")

    _write_component(stock_dir, exp_id="exp_stock_component", asset_scope="cn_a_equity", benchmark="000300.SH", risk_budget=0.8)
    _write_component(etf_dir, exp_id="exp_etf_component", asset_scope="cn_etf", benchmark="510300.SH", risk_budget=0.2)
    _write_json(
        combo_dir / "manifest.json",
        {
            "exp_id": "exp_combo_unified",
            "experiment_id": "exp_combo_unified",
            "status": "OK",
            "created_at": "2026-03-26T09:00:00",
            "schema_version": "backtest_v2_experiment_manifest@2",
            "artifacts": {
                "perf": "perf.json",
                "run_meta": "run_meta.json",
                "config": "config.json",
                "nav": "nav.csv",
            },
            "stage_pipeline": {
                "route_id": "cn_stock_etf_unified_runtime_entry",
                "execution_shell": "unified_combo_phase1",
            },
            "asset_scope": "cn_a_equity",
            "asset_context": {"asset_scope": "cn_a_equity"},
        },
    )
    _write_json(combo_dir / "perf.json", {"cagr": 0.08, "total_return": 0.18, "max_drawdown": -0.12})
    _write_json(
        combo_dir / "run_meta.json",
        {
            "data": {
                "asset_scope": "cn_a_equity",
                "asset_role": "unified_multi_sleeve_combo",
                "system_asset_scope": "cn_a_multi_sleeve",
            },
            "combo_components": {
                "stock_component": {"exp_id": "exp_stock_component"},
                "etf_component": {"exp_id": "exp_etf_component"},
            },
            "combo_runtime": {"mode": "daily_rebalanced_equal_weight_50_50"},
        },
    )
    _write_json(combo_dir / "config.json", {"mode": "experiment", "asset_scope": "cn_a_equity"})
    (combo_dir / "nav.csv").write_text("date,nav\n2026-03-24,1.0\n2026-03-25,1.05\n", encoding="utf-8")

    exp_dirs = {
        "exp_stock_component": stock_dir,
        "exp_etf_component": etf_dir,
        "exp_combo_unified": combo_dir,
    }
    monkeypatch.setattr(
        experiment_query_service,
        "resolve_experiment_dir_by_id",
        lambda exp_id: exp_dirs.get(exp_id),
    )

    combo_truth = experiment_query_service.get_experiment_surface_section("exp_combo_unified", "combo_truth")
    assert combo_truth["section"] == "combo_truth"
    assert combo_truth["data"]["components"]["stock"]["exp_id"] == "exp_stock_component"
    assert combo_truth["data"]["components"]["etf"]["exp_id"] == "exp_etf_component"
    assert combo_truth["data"]["display"]["governor"]["budget_consumer_text"] == "cn_stock_trend_alpha_core + cn_etf_beta"


def test_list_experiments_wraps_manifest_and_perf_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        experiment_query_service.experiment_history_service,
        "list_experiments",
        lambda: [
            {
                "exp_id": "exp_a",
                "label": "A",
                "created_at": "2026-03-15T09:00:00",
                "has_manifest": True,
                "has_core_artifacts": True,
                "cagr": 0.2,
                "max_drawdown": -0.1,
                "sharpe": 1.3,
                "total_return": 0.4,
                "trades": 20,
            }
        ],
    )

    items = experiment_query_service.list_experiments()
    assert items[0]["exp_id"] == "exp_a"
    assert items[0]["perf"] == {
        "cagr": 0.2,
        "max_drawdown": -0.1,
        "sharpe": 1.3,
        "total_return": 0.4,
        "trades": 20,
    }


def test_get_execution_regression_contract_counts_rows_and_date_bounds(tmp_path: Path, monkeypatch) -> None:
    exp_dir = tmp_path / "exp_regression"
    exp_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        exp_dir / "manifest.json",
        {
            "exp_id": "exp_regression",
            "experiment_id": "exp_regression",
            "status": "OK",
            "created_at": "2026-03-15T09:00:00",
            "schema_version": "backtest_v2_experiment_manifest@2",
            "baseline_compare_status": "NOT_RUN",
            "artifacts": {
                "perf": "perf.json",
                "nav": "nav.csv",
                "run_meta": "run_meta.json",
                "orders": "orders.csv",
                "trades": "portfolio_trades.csv",
                "audit": "audit.json",
                "execution_lineage_ledger": "execution_lineage_ledger.csv",
            },
            "stage_pipeline": {
                "route_id": "provider_breakout_runtime",
                "execution_shell": "stage_pipeline_shell_bridge",
            },
        },
    )
    _write_json(
        exp_dir / "perf.json",
        {
            "total_return": 0.4,
            "max_drawdown": -0.15,
            "cagr": 0.18,
            "sharpe": 1.2,
            "calmar": 1.1,
            "trades": 4,
            "turnover": 0.03,
            "effective_execution_start_date": "2024-01-03",
        },
    )
    _write_json(
        exp_dir / "run_meta.json",
        {
            "counters": {
                "orders": 4,
                "closed_trades": 2,
                "buy_orders_count": 2,
                "sell_orders_count": 2,
            }
        },
    )
    _write_json(
        exp_dir / "audit.json",
        {
            "execution_lineage": {
                "summary": {
                    "generated_count": 2,
                    "scheduled_count": 2,
                    "filled_count": 2,
                    "same_day_fill_count": 0,
                }
            }
        },
    )
    (exp_dir / "orders.csv").write_text(
        "date,symbol,side\n2024-01-03,sh600000,buy\n2024-01-08,sh600000,sell\n",
        encoding="utf-8",
    )
    (exp_dir / "portfolio_trades.csv").write_text(
        "trade_date,symbol,side\n2024-01-03,sh600000,buy\n2024-01-08,sh600000,sell\n",
        encoding="utf-8",
    )
    (exp_dir / "nav.csv").write_text(
        "as_of_date,nav\n2024-01-03,1.0\n2024-01-04,1.02\n2024-01-08,1.01\n",
        encoding="utf-8",
    )
    (exp_dir / "execution_lineage_ledger.csv").write_text(
        "signal_id,signal_date,order_id,scheduled_date,last_scheduled_date,schedule_attempts,fill_id,fill_date,symbol,side,qty,reason_code,terminal_status,terminal_reason,deferred_count\n"
        "sig_1,2024-01-02,ord_1,2024-01-03,2024-01-03,1,fil_1,2024-01-03,sh600000,BUY,100,ENTRY,filled,,0\n"
        "sig_2,2024-01-05,ord_2,2024-01-08,2024-01-08,1,fil_2,2024-01-08,sh600000,SELL,100,EXIT,filled,,0\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(experiment_query_service, "resolve_experiment_dir_by_id", lambda exp_id: exp_dir)

    contract = experiment_query_service.get_execution_regression_contract("exp_regression")

    assert contract["exp_id"] == "exp_regression"
    assert contract["manifest"] == {
        "schema_version": "backtest_v2_experiment_manifest@2",
        "status": "OK",
        "baseline_compare_status": "NOT_RUN",
        "route_id": "provider_breakout_runtime",
        "execution_shell": "stage_pipeline_shell_bridge",
    }
    assert contract["perf"] == {
        "total_return": 0.4,
        "max_drawdown": -0.15,
        "cagr": 0.18,
        "sharpe": 1.2,
        "calmar": 1.1,
        "trades": 4,
        "turnover": 0.03,
        "effective_execution_start_date": "2024-01-03",
    }
    assert contract["counters"] == {
        "orders": 4,
        "closed_trades": 2,
        "buy_orders_count": 2,
        "sell_orders_count": 2,
    }
    assert contract["artifacts"] == {
        "orders": {"rows": 2, "first_date": "2024-01-03", "last_date": "2024-01-08"},
        "trades": {"rows": 2, "first_date": "2024-01-03", "last_date": "2024-01-08"},
        "nav": {"rows": 3, "first_date": "2024-01-03", "last_date": "2024-01-08"},
        "execution_lineage_ledger": {"rows": 2, "first_date": "2024-01-02", "last_date": "2024-01-05"},
    }
    assert contract["lineage"]["summary"]["filled_count"] == 2


def test_get_execution_regression_contract_supports_generic_inline_runtime_golden(tmp_path: Path, monkeypatch) -> None:
    exp_dir = tmp_path / "exp_generic_golden"
    exp_dir.mkdir(parents=True, exist_ok=True)
    bundle = _generic_bundle()
    trading_days = bundle.trading_days
    scripted = {
        trading_days[0]: [
            Signal(
                signal_date=trading_days[0],
                symbol="SH600000",
                side=Side.BUY,
                qty=100,
                reason="ENTRY",
                reason_code="ENTRY",
            )
        ],
        trading_days[2]: [
            Signal(
                signal_date=trading_days[2],
                symbol="SH600000",
                side=Side.SELL,
                qty=100000,
                reason="EXIT",
                reason_code="EXIT",
            )
        ],
    }
    strategy = CompositeStrategy(strategies=[_ScriptedStrategy(scripted)], combine_mode="OR")
    result = run_stage_pipeline_bridge_backtest(
        StagePipelineBridgeRequest(
            data_bundle=bundle,
            strategy=strategy,
            initial_cash=100000.0,
            max_positions=5,
            lot_size=100,
            enable_strength_rank=False,
            strength_ma=55,
            enable_multifactor_rank=False,
            mf_rank_gate_mode="ALWAYS_ON",
            cost_cfg=CostConfig(slippage_bps=0.0, commission_rate=0.0, commission_min=0.0, stamp_tax_rate=0.0),
            sizing_cfg=SizingConfig(weight_mode="equal", min_positions=1, order_value=0),
            base_order_value=10000.0,
            risk_budget_cfg=RiskBudgetConfig(enabled=False),
            market_filter_cfg=MarketFilterConfig(enabled=False),
            benchmark_regime_cfg=BenchmarkRegimeConfig(enabled=False),
        )
    )
    portfolio_result = result.portfolio_result
    nav_rows = portfolio_result.daily[["date", "nav"]].copy()
    trade_rows = portfolio_result.trades[["date", "symbol", "side", "price", "fill_price", "qty"]].copy()
    perf = {
        "total_return": portfolio_result.metrics["total_return"],
        "max_drawdown": portfolio_result.metrics["max_drawdown"],
        "cagr": portfolio_result.metrics["cagr"],
        "sharpe": portfolio_result.metrics["sharpe"],
        "calmar": portfolio_result.metrics["calmar"],
        "trades": int(len(trade_rows.index)),
        "effective_execution_start_date": str(trade_rows["date"].iloc[0])[:10],
    }
    _write_json(
        exp_dir / "manifest.json",
        {
            "exp_id": "exp_generic_golden",
            "experiment_id": "exp_generic_golden",
            "status": "OK",
            "created_at": "2026-03-15T09:00:00",
            "schema_version": "backtest_v2_experiment_manifest@2",
            "baseline_compare_status": "NOT_RUN",
            "artifacts": {
                "perf": "perf.json",
                "nav": "nav.csv",
                "run_meta": "run_meta.json",
                "orders": "orders.csv",
                "trades": "portfolio_trades.csv",
                "audit": "audit.json",
                "execution_lineage_ledger": "execution_lineage_ledger.csv",
            },
            "stage_pipeline": {
                "route_id": result.route_id,
                "execution_shell": "stage_pipeline_shell_bridge",
            },
        },
    )
    _write_json(
        exp_dir / "perf.json",
        perf,
    )
    _write_json(
        exp_dir / "run_meta.json",
        {
            "counters": {
                "orders": 2,
                "closed_trades": 1,
                "buy_orders_count": 1,
                "sell_orders_count": 1,
            }
        },
    )
    _write_json(
        exp_dir / "audit.json",
        {
            "execution_lineage": {
                "summary": {
                    "generated_count": 2,
                    "scheduled_count": 2,
                    "filled_count": 2,
                    "same_day_fill_count": 0,
                }
            }
        },
    )
    nav_rows.to_csv(exp_dir / "nav.csv", index=False)
    trade_rows.to_csv(exp_dir / "orders.csv", index=False)
    trade_rows.to_csv(exp_dir / "portfolio_trades.csv", index=False)
    pd.DataFrame(
        [
            {
                "signal_id": "sig_1",
                "signal_date": "2024-01-02",
                "order_id": "ord_1",
                "scheduled_date": "2024-01-03",
                "last_scheduled_date": "2024-01-03",
                "schedule_attempts": 1,
                "fill_id": "fil_1",
                "fill_date": "2024-01-03",
                "symbol": "sh600000",
                "side": "BUY",
                "qty": 100,
                "reason_code": "ENTRY",
                "terminal_status": "filled",
                "terminal_reason": "",
                "deferred_count": 0,
            },
            {
                "signal_id": "sig_2",
                "signal_date": "2024-01-04",
                "order_id": "ord_2",
                "scheduled_date": "2024-01-05",
                "last_scheduled_date": "2024-01-05",
                "schedule_attempts": 1,
                "fill_id": "fil_2",
                "fill_date": "2024-01-05",
                "symbol": "sh600000",
                "side": "SELL",
                "qty": 100,
                "reason_code": "EXIT",
                "terminal_status": "filled",
                "terminal_reason": "",
                "deferred_count": 0,
            },
        ]
    ).to_csv(exp_dir / "execution_lineage_ledger.csv", index=False)

    monkeypatch.setattr(experiment_query_service, "resolve_experiment_dir_by_id", lambda exp_id: exp_dir)

    contract = experiment_query_service.get_execution_regression_contract("exp_generic_golden")

    assert contract["manifest"] == {
        "schema_version": "backtest_v2_experiment_manifest@2",
        "status": "OK",
        "baseline_compare_status": "NOT_RUN",
        "route_id": "generic_inline_runtime",
        "execution_shell": "stage_pipeline_shell_bridge",
    }
    assert contract["perf"] == {
        "total_return": 0.03600000000000003,
        "max_drawdown": 0.0,
        "cagr": 4.94472367840318,
        "sharpe": 15.132872978653346,
        "calmar": 0.0,
        "trades": 2,
        "turnover": None,
        "effective_execution_start_date": "2024-01-03",
    }
    assert contract["counters"] == {
        "orders": 2,
        "closed_trades": 1,
        "buy_orders_count": 1,
        "sell_orders_count": 1,
    }
    assert contract["artifacts"] == {
        "orders": {"rows": 2, "first_date": "2024-01-03", "last_date": "2024-01-05"},
        "trades": {"rows": 2, "first_date": "2024-01-03", "last_date": "2024-01-05"},
        "nav": {"rows": 5, "first_date": "2024-01-02", "last_date": "2024-01-08"},
        "execution_lineage_ledger": {"rows": 2, "first_date": "2024-01-02", "last_date": "2024-01-04"},
    }
    assert contract["lineage"]["summary"]["scheduled_count"] == 2


def test_get_execution_regression_contract_supports_locked_candidate_preset_golden(tmp_path: Path, monkeypatch) -> None:
    candidate_name = locked_candidate_presets.BREAKOUT_ATR_STOP_K10_CANDIDATE
    baseline_dir = tmp_path / "locked_candidate_seed"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    baseline_cfg = {
        "strategy": {
            "name": "breakout_trend",
            "params": {
                "atr_stop_k": 2.0,
                "breakout_window": 45,
            },
        }
    }
    baseline_meta = {
        "data": {"universe_mode": "HS300_ZZ500"},
        "code": {"fast_mode": True},
        "price_adj_mode": "hfq",
    }
    _write_json(baseline_dir / "run_config.json", baseline_cfg)
    _write_json(baseline_dir / "run_meta.json", baseline_meta)
    _write_json(baseline_dir / "perf.json", {"cagr": 0.12})
    evidence_dir = tmp_path / "locked_candidate_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        evidence_dir / "summary.json",
        {
            "generated_at": "2026-03-15T12:00:00+08:00",
            "baseline_exp_id": "exp_locked_seed",
        },
    )
    patched_defs = {
        **locked_candidate_presets._CANDIDATE_DEFS,
        candidate_name: {
            **locked_candidate_presets._CANDIDATE_DEFS[candidate_name],
            "locked_baseline_exp_id": "exp_locked_seed",
            "locked_baseline_cfg_path": baseline_dir / "run_config.json",
            "locked_baseline_perf_path": baseline_dir / "perf.json",
            "locked_baseline_meta_path": baseline_dir / "run_meta.json",
            "evidence_bundle": (("full_sample", evidence_dir / "summary.json"),),
        },
    }
    monkeypatch.setattr(locked_candidate_presets, "_CANDIDATE_DEFS", patched_defs)

    candidate_cfg, candidate_meta = locked_candidate_presets.build_locked_candidate_cfg(candidate_name)
    assert candidate_cfg["strategy"]["params"]["atr_stop_k"] == 1.0
    assert candidate_meta["source_baseline_exp_id"] == "exp_locked_seed"

    exp_dir = tmp_path / "exp_locked_candidate_golden"
    exp_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        exp_dir / "manifest.json",
        {
            "exp_id": "exp_locked_candidate_golden",
            "experiment_id": "exp_locked_candidate_golden",
            "status": "OK",
            "created_at": "2026-03-15T09:00:00",
            "schema_version": "backtest_v2_experiment_manifest@2",
            "baseline_compare_status": "NOT_RUN",
            "artifacts": {
                "perf": "perf.json",
                "nav": "nav.csv",
                "run_meta": "run_meta.json",
                "orders": "orders.csv",
                "trades": "portfolio_trades.csv",
                "audit": "audit.json",
                "execution_lineage_ledger": "execution_lineage_ledger.csv",
            },
            "stage_pipeline": {
                "route_id": "provider_breakout_runtime",
                "execution_shell": "stage_pipeline_shell_bridge",
            },
        },
    )
    _write_json(exp_dir / "run_config.json", candidate_cfg)
    _write_json(
        exp_dir / "perf.json",
        {
            "total_return": 0.27,
            "max_drawdown": -0.09,
            "cagr": 0.14,
            "sharpe": 1.08,
            "calmar": 1.55,
            "trades": 6,
            "turnover": 0.041,
            "effective_execution_start_date": "2024-02-05",
        },
    )
    _write_json(
        exp_dir / "run_meta.json",
        {
            "counters": {
                "orders": 6,
                "closed_trades": 3,
                "buy_orders_count": 3,
                "sell_orders_count": 3,
            }
        },
    )
    _write_json(
        exp_dir / "audit.json",
        {
            "summary": {"t1_check_fail": 0},
            "execution_lineage": {
                "summary": {
                    "generated_count": 3,
                    "scheduled_count": 3,
                    "filled_count": 3,
                    "same_day_fill_count": 0,
                }
            },
        },
    )
    (exp_dir / "orders.csv").write_text(
        "date,symbol,side\n2024-02-05,sh600000,buy\n2024-02-08,sh600000,sell\n2024-02-09,sh600001,buy\n",
        encoding="utf-8",
    )
    (exp_dir / "portfolio_trades.csv").write_text(
        "trade_date,symbol,side\n2024-02-05,sh600000,buy\n2024-02-08,sh600000,sell\n2024-02-09,sh600001,buy\n",
        encoding="utf-8",
    )
    (exp_dir / "nav.csv").write_text(
        "as_of_date,nav\n2024-02-05,1.0\n2024-02-06,1.03\n2024-02-08,1.05\n2024-02-09,1.04\n",
        encoding="utf-8",
    )
    (exp_dir / "execution_lineage_ledger.csv").write_text(
        "signal_id,signal_date,order_id,scheduled_date,last_scheduled_date,schedule_attempts,fill_id,fill_date,symbol,side,qty,reason_code,terminal_status,terminal_reason,deferred_count\n"
        "sig_1,2024-02-02,ord_1,2024-02-05,2024-02-05,1,fil_1,2024-02-05,sh600000,BUY,100,ENTRY,filled,,0\n"
        "sig_2,2024-02-07,ord_2,2024-02-08,2024-02-08,1,fil_2,2024-02-08,sh600000,SELL,100,EXIT,filled,,0\n"
        "sig_3,2024-02-08,ord_3,2024-02-09,2024-02-09,1,fil_3,2024-02-09,sh600001,BUY,100,ENTRY,filled,,0\n",
        encoding="utf-8",
    )

    assessment = locked_candidate_presets.assess_locked_candidate_results(candidate_name, exp_dir)
    assert assessment["status"] == "ready"
    assert assessment["blockers"] == []

    monkeypatch.setattr(experiment_query_service, "resolve_experiment_dir_by_id", lambda exp_id: exp_dir)

    contract = experiment_query_service.get_execution_regression_contract("exp_locked_candidate_golden")

    assert contract["manifest"] == {
        "schema_version": "backtest_v2_experiment_manifest@2",
        "status": "OK",
        "baseline_compare_status": "NOT_RUN",
        "route_id": "provider_breakout_runtime",
        "execution_shell": "stage_pipeline_shell_bridge",
    }
    assert contract["perf"] == {
        "total_return": 0.27,
        "max_drawdown": -0.09,
        "cagr": 0.14,
        "sharpe": 1.08,
        "calmar": 1.55,
        "trades": 6,
        "turnover": 0.041,
        "effective_execution_start_date": "2024-02-05",
    }
    assert contract["counters"] == {
        "orders": 6,
        "closed_trades": 3,
        "buy_orders_count": 3,
        "sell_orders_count": 3,
    }
    assert contract["artifacts"] == {
        "orders": {"rows": 3, "first_date": "2024-02-05", "last_date": "2024-02-09"},
        "trades": {"rows": 3, "first_date": "2024-02-05", "last_date": "2024-02-09"},
        "nav": {"rows": 4, "first_date": "2024-02-05", "last_date": "2024-02-09"},
        "execution_lineage_ledger": {"rows": 3, "first_date": "2024-02-02", "last_date": "2024-02-08"},
    }
    assert contract["lineage"]["summary"]["generated_count"] == 3
