from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from backend.core.data.pg_provider import PostgresDataProvider
from backend.research import study_loader, study_runner
from backend.research import a_share_moneyflow_divergence as moneyflow_divergence
from backend.research.a_share_moneyflow_divergence import (
    _apply_repair_screen_filters,
    _apply_allowed_industry_filter,
    _resolve_allowed_industry_l1,
    _resolve_target_weights,
    _create_provider_from_payload,
    assess_moneyflow_gate,
    build_daily_divergence_frame,
    build_monthly_divergence_panel,
    build_monthly_rebalance_schedule,
    required_valid_days,
    run_monthly_rebalance_backtest,
    synthesize_moneyflow_gate_from_daily_coverage,
)


def test_repo_study_definition_loads_for_moneyflow_divergence() -> None:
    study = study_loader.load_study_definition("factors/a_share_moneyflow_divergence_min10")
    assert study.study_id == "factors/a_share_moneyflow_divergence_min10"
    assert study.windows[0].key == "1626"
    assert study.metadata["runner_mode"] == "a_share_moneyflow_divergence"


def test_custom_runner_study_delegates_to_custom_runner(monkeypatch) -> None:
    study = study_loader.load_study_definition("factors/a_share_moneyflow_divergence_min10")
    captured: dict[str, object] = {}

    def _fake_runner(**kwargs):
        captured.update(kwargs)
        return {"status": "diagnostics_only"}

    monkeypatch.setattr(study_runner, "run_a_share_moneyflow_divergence_study", _fake_runner)
    result = study_runner.run_study(
        study,
        only_window_keys=["1626"],
        only_variant_names=["B0_MIN10"],
        write_dual_output=False,
        append_to_baseline=False,
    )
    assert result["status"] == "diagnostics_only"
    assert captured["study"] == study
    assert captured["write_dual_output"] is False
    assert captured["append_to_baseline"] is False
    plan = captured["plan"]
    assert isinstance(plan, list) and len(plan) == 1


def test_assess_moneyflow_gate_marks_missing_and_low_coverage() -> None:
    whitelist = pd.DataFrame(
        [
            {
                "trade_date": "2026-01-30",
                "row_coverage_ratio": 0.96,
                "net_amount_coverage_ratio": 0.91,
                "allow_in_research": True,
            },
            {
                "trade_date": "2026-02-27",
                "row_coverage_ratio": 0.94,
                "net_amount_coverage_ratio": 0.91,
                "allow_in_research": True,
            },
        ]
    )
    result = assess_moneyflow_gate(
        [date(2026, 1, 30), date(2026, 2, 27), date(2026, 3, 31)],
        whitelist,
    )
    status_map = dict(zip(result["trade_date"].dt.date, result["gate_status"]))
    assert status_map[date(2026, 1, 30)] == "tradable"
    assert status_map[date(2026, 2, 27)] == "skipped_low_coverage"
    assert status_map[date(2026, 3, 31)] == "blocked_missing_gate"


def test_synthesize_moneyflow_gate_from_daily_coverage_uses_daily_table_snapshot() -> None:
    class _Provider:
        def load_stock_moneyflow(self, symbols, start, end, table="pit_stock_moneyflow"):
            assert table == "pit_stock_moneyflow"
            rows = [
                {"trade_date": "2026-01-30", "symbol": "sh600000", "net_mf_amount": 1.0},
                {"trade_date": "2026-01-30", "symbol": "sz000001", "net_mf_amount": 2.0},
                {"trade_date": "2026-01-30", "symbol": "sz000002", "net_mf_amount": None},
                {"trade_date": "2026-02-27", "symbol": "sh600000", "net_mf_amount": 1.0},
            ]
            frame = pd.DataFrame(rows)
            frame["trade_date"] = pd.to_datetime(frame["trade_date"])
            mask = frame["trade_date"].dt.date.eq(start)
            return frame.loc[mask].reset_index(drop=True)

    result = synthesize_moneyflow_gate_from_daily_coverage(
        _Provider(),
        ["sh600000", "sz000001", "sz000002"],
        [date(2026, 1, 30), date(2026, 2, 27)],
        moneyflow_table="pit_stock_moneyflow",
        required_row_coverage_ratio=0.95,
        required_net_coverage_ratio=0.90,
    )
    status_map = dict(zip(result["trade_date"].dt.date, result["gate_status"]))
    row_ratio_map = dict(zip(result["trade_date"].dt.date, result["row_coverage_ratio"]))
    net_ratio_map = dict(zip(result["trade_date"].dt.date, result["net_amount_coverage_ratio"]))
    assert status_map[date(2026, 1, 30)] == "skipped_low_coverage"
    assert row_ratio_map[date(2026, 1, 30)] == 1.0
    assert net_ratio_map[date(2026, 1, 30)] == 2.0 / 3.0
    assert status_map[date(2026, 2, 27)] == "skipped_low_coverage"


def test_postgres_provider_load_stock_moneyflow_uses_case_insensitive_symbol_filter() -> None:
    provider = PostgresDataProvider.__new__(PostgresDataProvider)
    provider._audit = []
    provider._table_columns_cache = {}
    provider._runtime = SimpleNamespace(statement_timeout_ms=60000)
    provider._get_table_columns = lambda table: {"symbol", "trade_date", "net_mf_amount"}  # type: ignore[attr-defined]
    captured: dict[str, object] = {}

    def _fake_exec_df(query, params, audit_meta):
        captured["query"] = query
        captured["params"] = params
        return pd.DataFrame(
            [
                {"symbol": "600000.SH", "trade_date": "2025-03-31", "net_mf_amount": 1.0},
            ]
        )

    provider._exec_df = _fake_exec_df  # type: ignore[attr-defined]

    result = provider.load_stock_moneyflow(
        ["600000.SH"],
        date(2025, 3, 31),
        date(2025, 3, 31),
        table="pit_stock_moneyflow",
    )

    assert "LOWER(symbol) = ANY(%s)" in str(captured["query"])
    assert captured["params"] == (date(2025, 3, 31), date(2025, 3, 31), ["sh600000"])
    assert result["symbol"].tolist() == ["600000.sh"]


def test_create_provider_from_payload_prefers_materialized_config_json(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Cfg:
        db = SimpleNamespace()
        db_runtime = SimpleNamespace()
        data_source = SimpleNamespace()
        schema_mapping = {}

        def to_dict(self):
            return {"data_source": {"stocks_table": "pams_ohlcv_daily_v2"}}

    def _fake_load_config(path):
        captured["path"] = path
        captured["payload"] = json.loads(Path(path).read_text(encoding="utf-8"))
        return _Cfg(), "hash"

    def _fake_build_runtime_provider(cfg_obj, rules_path, *, use_cache=False):
        captured["provider_cfg_obj"] = cfg_obj
        captured["provider_rules_path"] = rules_path
        captured["provider_use_cache"] = use_cache
        return "provider"

    monkeypatch.setattr(moneyflow_divergence, "load_config", _fake_load_config)
    monkeypatch.setattr(moneyflow_divergence, "build_runtime_provider_from_config", _fake_build_runtime_provider)

    provider, snapshot, config_hash = _create_provider_from_payload(
        {
            "config_path": "/does/not/matter.json",
            "config_json": {
                "db": {},
                "db_runtime": {},
                "data_source": {"stocks_table": "pams_ohlcv_daily_v2"},
                "schema_mapping": {},
            },
        }
    )

    assert provider == "provider"
    assert snapshot["data_source"]["stocks_table"] == "pams_ohlcv_daily_v2"
    assert config_hash == "hash"
    assert captured["payload"]["data_source"]["stocks_table"] == "pams_ohlcv_daily_v2"
    assert str(captured["provider_rules_path"]).endswith("config\\rules.csv")
    assert captured["provider_use_cache"] is False


def test_build_daily_divergence_frame_requires_full_20d_window_and_non_null_moneyflow() -> None:
    dates = pd.bdate_range("2026-01-01", periods=22)
    price_history = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["sh600000"] * len(dates),
            "circ_mv": [100.0] * len(dates),
            "amount": [200.0] * len(dates),
        }
    )
    moneyflow = pd.DataFrame(
        {
            "trade_date": dates,
            "symbol": ["sh600000"] * len(dates),
            "net_mf_amount": [1.0] * 21 + [None],
        }
    )
    result = build_daily_divergence_frame(price_history, moneyflow)
    assert result["factor_valid"].sum() == 2
    valid_rows = result[result["factor_valid"]]
    assert valid_rows["date"].dt.date.tolist() == [dates[19].date(), dates[20].date()]
    assert valid_rows["daily_divergence_rate"].tolist() == [0.01, 0.01]


def test_build_daily_divergence_frame_supports_avg20_amount_denominator() -> None:
    dates = pd.bdate_range("2026-01-01", periods=22)
    price_history = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["sh600000"] * len(dates),
            "circ_mv": [pd.NA] * len(dates),
            "amount": [200.0] * len(dates),
        }
    )
    moneyflow = pd.DataFrame(
        {
            "trade_date": dates,
            "symbol": ["sh600000"] * len(dates),
            "net_mf_amount": [1.0] * len(dates),
        }
    )
    result = build_daily_divergence_frame(price_history, moneyflow, denominator_mode="avg20_amount")
    valid_rows = result[result["factor_valid"]]
    assert valid_rows["date"].dt.date.tolist() == [dates[19].date(), dates[20].date(), dates[21].date()]
    assert valid_rows["daily_divergence_rate"].tolist() == [0.005, 0.005, 0.005]


def test_build_monthly_divergence_panel_enforces_valid_day_threshold_and_month_end_valid() -> None:
    daily = pd.DataFrame(
        {
            "date": pd.bdate_range("2026-01-01", periods=20).tolist() + pd.bdate_range("2026-02-02", periods=20).tolist(),
            "symbol": ["sh600000"] * 40,
            "daily_divergence_rate": [0.01] * 16 + [pd.NA] * 4 + [0.02] * 15 + [pd.NA] * 4 + [0.02],
            "factor_valid": [True] * 16 + [False] * 4 + [True] * 15 + [False] * 4 + [True],
        }
    )
    panel = build_monthly_divergence_panel(daily)
    january = panel.loc[panel["month"] == pd.Timestamp("2026-01-01")].iloc[0]
    february = panel.loc[panel["month"] == pd.Timestamp("2026-02-01")].iloc[0]
    assert required_valid_days(20) == 16
    assert bool(january["monthly_factor_valid"]) is False
    assert bool(february["monthly_factor_valid"]) is True


def test_build_monthly_rebalance_schedule_requires_next_trading_day() -> None:
    coverage = pd.DataFrame(
        [
            {"trade_date": "2026-01-30", "gate_status": "tradable", "gate_reason": ""},
            {"trade_date": "2026-02-27", "gate_status": "tradable", "gate_reason": ""},
        ]
    )
    schedule = build_monthly_rebalance_schedule(
        pd.to_datetime(["2026-01-30", "2026-02-02", "2026-02-27"]),
        [date(2026, 1, 30), date(2026, 2, 27)],
        coverage,
        end_date=date(2026, 2, 27),
    )
    january = schedule.iloc[0]
    february = schedule.iloc[1]
    assert str(january["execution_date"].date()) == "2026-02-02"
    assert bool(january["planned_rebalance"]) is True
    assert bool(january["can_rebalance"]) is True
    assert pd.isna(february["execution_date"])
    assert bool(february["planned_rebalance"]) is False
    assert bool(february["can_rebalance"]) is False
    assert february["schedule_status"] == "blocked_missing_execution_day"


def test_resolve_target_weights_supports_equal_and_rank_decay() -> None:
    selection = pd.DataFrame(
        [
            {"rank": 1, "symbol": "sh600000"},
            {"rank": 2, "symbol": "sz000001"},
            {"rank": 3, "symbol": "sh600519"},
        ]
    )
    equal_weights = _resolve_target_weights(selection, weight_mode="equal_weight")
    decay_weights = _resolve_target_weights(selection, weight_mode="rank_decay_linear")

    assert equal_weights == {
        "sh600000": 1.0 / 3.0,
        "sz000001": 1.0 / 3.0,
        "sh600519": 1.0 / 3.0,
    }
    assert round(sum(decay_weights.values()), 10) == 1.0
    assert decay_weights["sh600000"] > decay_weights["sz000001"] > decay_weights["sh600519"]
    assert decay_weights["sh600000"] == 3.0 / 6.0
    assert decay_weights["sz000001"] == 2.0 / 6.0
    assert decay_weights["sh600519"] == 1.0 / 6.0


def test_resolve_allowed_industry_l1_normalizes_and_deduplicates() -> None:
    result = _resolve_allowed_industry_l1(["电子", "计算机", "电子", " 通信 "])
    assert result == ["电子", "计算机", "通信"]
    assert _resolve_allowed_industry_l1("电子,计算机，通信") == ["电子", "计算机", "通信"]


def test_apply_allowed_industry_filter_keeps_only_whitelisted_industries() -> None:
    candidates = pd.DataFrame(
        [
            {"symbol": "sz300502", "industry_l1": "通信"},
            {"symbol": "sz300476", "industry_l1": "电子"},
            {"symbol": "sh600062", "industry_l1": "医药生物"},
            {"symbol": "sh601019", "industry_l1": ""},
        ]
    )
    filtered, excluded_counts = _apply_allowed_industry_filter(candidates, ["电子", "通信"])
    assert filtered["symbol"].tolist() == ["sz300502", "sz300476"]
    assert excluded_counts == {"EXCLUDE_INDUSTRY_NOT_ALLOWED": 2}


def test_apply_repair_screen_filters_excludes_bottom_liquidity_tail() -> None:
    candidates = pd.DataFrame(
        [
            {"symbol": "a", "avg_turnover_20d": 100.0, "last_close": 10.0, "ma20_close": 9.9},
            {"symbol": "b", "avg_turnover_20d": 200.0, "last_close": 10.0, "ma20_close": 10.0},
            {"symbol": "c", "avg_turnover_20d": 300.0, "last_close": 10.0, "ma20_close": 10.1},
            {"symbol": "d", "avg_turnover_20d": 400.0, "last_close": 10.0, "ma20_close": 10.0},
            {"symbol": "e", "avg_turnover_20d": 500.0, "last_close": 10.0, "ma20_close": 10.0},
        ]
    )
    filtered, excluded, audit_meta = _apply_repair_screen_filters(
        candidates,
        liquidity_bottom_quantile=0.2,
    )
    assert filtered["symbol"].tolist() == ["b", "c", "d", "e"]
    assert excluded == {"EXCLUDE_LIQUIDITY_BOTTOM_QUANTILE": 1}
    assert audit_meta["liquidity_threshold_avg_turnover_20d"] == 180.0


def test_apply_repair_screen_filters_applies_light_price_repair_gate() -> None:
    candidates = pd.DataFrame(
        [
            {"symbol": "a", "avg_turnover_20d": 100.0, "last_close": 9.8, "ma20_close": 10.0},
            {"symbol": "b", "avg_turnover_20d": 100.0, "last_close": 9.6, "ma20_close": 10.0},
            {"symbol": "c", "avg_turnover_20d": 100.0, "last_close": 10.1, "ma20_close": 10.0},
        ]
    )
    filtered, excluded, audit_meta = _apply_repair_screen_filters(
        candidates,
        price_repair_min_ma20_ratio=0.97,
    )
    assert filtered["symbol"].tolist() == ["a", "c"]
    assert excluded == {"EXCLUDE_PRICE_REPAIR_BELOW_MA20": 1}
    assert audit_meta["price_repair_min_ma20_ratio"] == 0.97


def test_monthly_rebalance_backtest_replaces_and_retains_positions() -> None:
    trading_days = pd.to_datetime(["2026-02-02", "2026-02-03", "2026-03-02", "2026-03-03"])
    schedule = pd.DataFrame(
        [
            {
                "observation_date": "2026-01-30",
                "execution_date": "2026-02-02",
                "planned_rebalance": True,
                "can_rebalance": True,
            },
            {
                "observation_date": "2026-02-27",
                "execution_date": "2026-03-02",
                "planned_rebalance": True,
                "can_rebalance": True,
            },
        ]
    )
    selection = pd.DataFrame(
        [
            {"observation_date": "2026-01-30", "execution_date": "2026-02-02", "rank": 1, "symbol": "sh600000"},
            {"observation_date": "2026-01-30", "execution_date": "2026-02-02", "rank": 2, "symbol": "sz000001"},
            {"observation_date": "2026-02-27", "execution_date": "2026-03-02", "rank": 1, "symbol": "sz000001"},
            {"observation_date": "2026-02-27", "execution_date": "2026-03-02", "rank": 2, "symbol": "sh600519"},
        ]
    )
    price_history = pd.DataFrame(
        [
            {"date": "2026-02-02", "symbol": "sh600000", "open": 10.0, "close": 10.0, "volume": 1000, "amount": 10000},
            {"date": "2026-02-02", "symbol": "sz000001", "open": 10.0, "close": 10.0, "volume": 1000, "amount": 10000},
            {"date": "2026-02-03", "symbol": "sh600000", "open": 10.0, "close": 10.0, "volume": 1000, "amount": 10000},
            {"date": "2026-02-03", "symbol": "sz000001", "open": 10.0, "close": 10.0, "volume": 1000, "amount": 10000},
            {"date": "2026-03-02", "symbol": "sh600000", "open": 10.0, "close": 10.0, "volume": 1000, "amount": 10000},
            {"date": "2026-03-02", "symbol": "sz000001", "open": 12.0, "close": 12.0, "volume": 1000, "amount": 12000},
            {"date": "2026-03-02", "symbol": "sh600519", "open": 8.0, "close": 8.0, "volume": 1000, "amount": 8000},
            {"date": "2026-03-03", "symbol": "sh600000", "open": 10.0, "close": 10.0, "volume": 1000, "amount": 10000},
            {"date": "2026-03-03", "symbol": "sz000001", "open": 12.0, "close": 12.0, "volume": 1000, "amount": 12000},
            {"date": "2026-03-03", "symbol": "sh600519", "open": 8.0, "close": 8.0, "volume": 1000, "amount": 8000},
        ]
    )
    result = run_monthly_rebalance_backtest(
        price_history,
        trading_days,
        schedule,
        selection,
        initial_capital=100000.0,
        lot_size=100,
        commission_rate=0.0,
        commission_min=0.0,
        stamp_tax_rate=0.0,
        slippage_bps=0.0,
    )
    trades = result["portfolio_trades"]
    assert result["effective_execution_start_date"] == "2026-02-02"
    assert trades["side"].tolist() == ["BUY", "BUY", "SELL", "SELL", "BUY"]
    assert trades["symbol"].tolist() == ["sh600000", "sz000001", "sh600000", "sz000001", "sh600519"]
    assert trades["qty"].tolist() == [5000, 5000, 5000, 500, 6800]
    last_daily = result["portfolio_daily"].iloc[-1]
    assert int(last_daily["positions_count_end_of_day"]) == 2
    assert float(last_daily["nav"]) == 110000.0


def test_monthly_rebalance_backtest_rank_decay_overweights_front_rank() -> None:
    trading_days = pd.to_datetime(["2026-02-02", "2026-02-03"])
    schedule = pd.DataFrame(
        [
            {
                "observation_date": "2026-01-30",
                "execution_date": "2026-02-02",
                "planned_rebalance": True,
                "can_rebalance": True,
            },
        ]
    )
    selection = pd.DataFrame(
        [
            {"observation_date": "2026-01-30", "execution_date": "2026-02-02", "rank": 1, "symbol": "sh600000"},
            {"observation_date": "2026-01-30", "execution_date": "2026-02-02", "rank": 2, "symbol": "sz000001"},
        ]
    )
    price_history = pd.DataFrame(
        [
            {"date": "2026-02-02", "symbol": "sh600000", "open": 10.0, "close": 10.0, "volume": 1000, "amount": 10000},
            {"date": "2026-02-02", "symbol": "sz000001", "open": 10.0, "close": 10.0, "volume": 1000, "amount": 10000},
            {"date": "2026-02-03", "symbol": "sh600000", "open": 10.0, "close": 10.0, "volume": 1000, "amount": 10000},
            {"date": "2026-02-03", "symbol": "sz000001", "open": 10.0, "close": 10.0, "volume": 1000, "amount": 10000},
        ]
    )
    result = run_monthly_rebalance_backtest(
        price_history,
        trading_days,
        schedule,
        selection,
        initial_capital=100000.0,
        lot_size=100,
        commission_rate=0.0,
        commission_min=0.0,
        stamp_tax_rate=0.0,
        slippage_bps=0.0,
        weight_mode="rank_decay_linear",
    )
    buys = result["portfolio_trades"]
    assert buys["side"].tolist() == ["BUY", "BUY"]
    assert buys["symbol"].tolist() == ["sh600000", "sz000001"]
    assert buys["qty"].tolist() == [6600, 3300]
    meta = buys["meta_json"].map(json.loads).tolist()
    assert meta[0]["target_weight"] > meta[1]["target_weight"]
    assert meta[0]["weight_mode"] == "rank_decay_linear"
