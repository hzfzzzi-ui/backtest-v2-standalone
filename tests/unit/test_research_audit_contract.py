from __future__ import annotations

import json

import pandas as pd

from backend.core.audit.research_audit import (
    aggregate_overall_status,
    build_research_audit,
    evaluate_accounting_integrity,
    evaluate_execution_realism,
    evaluate_result_sanity,
    evaluate_timing_alignment,
    evaluate_universe_lineage,
)


def test_aggregate_overall_status_uses_fail_warn_unknown_pass_order() -> None:
    assert aggregate_overall_status({"a": {"status": "PASS"}, "b": {"status": "UNKNOWN"}}) == "UNKNOWN"
    assert aggregate_overall_status({"a": {"status": "WARN"}, "b": {"status": "PASS"}}) == "WARN"
    assert aggregate_overall_status({"a": {"status": "FAIL"}, "b": {"status": "PASS"}}) == "FAIL"
    assert aggregate_overall_status({"a": {"status": "PASS"}, "b": {"status": "PASS"}}) == "PASS"


def test_evaluate_universe_lineage_maps_current_snapshot_and_unknown() -> None:
    all_a_gate = evaluate_universe_lineage(
        run_meta={
            "data": {"universe_mode": "ALL_A"},
            "universe": {
                "universe_mode": "ALL_A",
                "symbols_source": "pit_security_master+pams_ohlcv_daily",
                "resolve_asof": "2026-03-01",
                "dynamic_all_a_entry": True,
            },
        }
    )
    assert all_a_gate["lineage_mode"] == "CURRENT_SNAPSHOT"
    assert all_a_gate["status"] == "FAIL"

    custom_gate = evaluate_universe_lineage(
        run_meta={
            "data": {"universe_mode": "CUSTOM"},
            "universe": {"universe_mode": "CUSTOM"},
        }
    )
    assert custom_gate["lineage_mode"] == "UNKNOWN"
    assert custom_gate["status"] == "UNKNOWN"


def test_evaluate_universe_lineage_uses_membership_audit_for_pit_dynamic() -> None:
    gate = evaluate_universe_lineage(
        run_meta={
            "data": {"universe_mode": "CSI1000"},
            "universe": {
                "universe_mode": "CSI1000",
                "membership_mode": "PIT_DYNAMIC",
                "membership_history_mode": "PIT_DYNAMIC",
                "historical_membership_dynamic": True,
                "symbols_source": "pit_index_constituents",
                "membership_source": "akshare_csi1000_static_fallback",
                "membership_data_quality": "static_fallback",
                "audit_status": "blocked",
                "audit_reason": "source_static",
                "distinct_start_dates": 1,
                "open_rows": 1000,
                "provider_floor_date": "2015-07-31",
                "refresh_event_count": 54,
                "zero_diff_refresh_event_count": 17,
                "rebalance_calendar_version": "seed-v1",
                "rebalance_calendar_source": "csindex_seed_schedule",
                "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
            },
        }
    )

    assert gate["lineage_mode"] == "PIT_DYNAMIC"
    assert gate["status"] == "FAIL"
    assert gate["evidence"]["audit_reason"] == "source_static"
    assert gate["evidence"]["provider_floor_date"] == "2015-07-31"
    assert gate["evidence"]["rebalance_calendar_version"] == "seed-v1"
    assert gate["metrics"]["distinct_start_dates"] == 1
    assert gate["metrics"]["refresh_event_count"] == 54


def test_evaluate_universe_lineage_passes_cn_etf_direct_symbols_whitelist() -> None:
    gate = evaluate_universe_lineage(
        run_meta={
            "data": {"asset_scope": "cn_etf", "universe_mode": "CUSTOM"},
            "universe": {
                "asset_scope": "cn_etf",
                "universe_mode": "CUSTOM",
                "membership_source": "cn_etf_catalog_whitelist",
                "membership_data_quality": "whitelist_verified",
                "audit_status": "PASS",
                "etf_batch": "cn_etf_first_wave_core",
                "etf_symbols": ["510300.SH", "512100.SH"],
                "coverage_start": "2016-11-04",
                "coverage_end": "2026-03-20",
                "price_series_semantics": "executable_price_only_not_total_return",
            },
        }
    )

    assert gate["lineage_mode"] == "DIRECT_SYMBOLS"
    assert gate["status"] == "PASS"
    assert gate["evidence"]["membership_source"] == "cn_etf_catalog_whitelist"
    assert gate["evidence"]["etf_batch"] == "cn_etf_first_wave_core"
    assert gate["evidence"]["coverage_end"] == "2026-03-20"


def test_evaluate_execution_realism_flags_hard_fail_on_suspended_trade() -> None:
    trades = pd.DataFrame(
        [
            {"date": "2024-01-02", "symbol": "sh600000", "side": "BUY", "price": 10.0, "fill_price": 10.0},
        ]
    )
    bars = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "sh600000",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000,
                "amount": 10000,
                "limit_up": 11.0,
                "limit_down": 9.0,
                "is_suspended": True,
            }
        ]
    )

    gate = evaluate_execution_realism(trades_df=trades, bars_df=bars)

    assert gate["status"] == "FAIL"
    assert gate["metrics"]["suspended_trade_count"] == 1


def test_evaluate_execution_realism_warns_for_small_limit_lock_ratio() -> None:
    trades = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": f"sh600{i:03d}",
                "side": "BUY",
                "price": 10.0 if i else 11.0,
                "fill_price": 10.0 if i else 11.0,
            }
            for i in range(100)
        ]
    )
    bars = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": f"sh600{i:03d}",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000,
                "amount": 10000,
                "limit_up": 11.0,
                "limit_down": 9.0,
                "is_suspended": False,
            }
            for i in range(100)
        ]
    )

    gate = evaluate_execution_realism(trades_df=trades, bars_df=bars)

    assert gate["status"] == "WARN"
    assert gate["metrics"]["limit_up_buy_count"] == 1
    assert gate["metrics"]["limit_locked_trade_ratio"] == 0.01


def test_evaluate_execution_realism_normalizes_four_decimal_limit_prices_to_tick_size() -> None:
    trades = pd.DataFrame(
        [
            {
                "date": "2024-10-22",
                "symbol": "sz002261",
                "side": "BUY",
                "price": 26.98,
                "fill_price": 26.9854,
            },
            {
                "date": "2020-02-04",
                "symbol": "sz002797",
                "side": "SELL",
                "price": 6.24,
                "fill_price": 6.2388,
            },
        ]
    )
    bars = pd.DataFrame(
        [
            {
                "date": "2024-10-22",
                "symbol": "sz002261",
                "open": 26.98,
                "high": 26.98,
                "low": 24.53,
                "close": 25.27,
                "volume": 1000,
                "amount": 10000,
                "limit_up": 26.983,
                "limit_down": 22.077,
                "is_suspended": False,
            },
            {
                "date": "2020-02-04",
                "symbol": "sz002797",
                "open": 6.24,
                "high": 6.82,
                "low": 6.24,
                "close": 6.71,
                "volume": 1000,
                "amount": 10000,
                "limit_up": 7.623,
                "limit_down": 6.237,
                "is_suspended": False,
            },
        ]
    )

    gate = evaluate_execution_realism(trades_df=trades, bars_df=bars)

    assert gate["status"] == "FAIL"
    assert gate["metrics"]["limit_up_buy_count"] == 1
    assert gate["metrics"]["limit_down_sell_count"] == 1
    assert gate["evidence"]["samples"]["limit_up_buy"][0]["limit_up"] == 26.98
    assert gate["evidence"]["samples"]["limit_down_sell"][0]["limit_down"] == 6.24


def test_evaluate_accounting_integrity_fails_on_execution_audit_violations() -> None:
    gate = evaluate_accounting_integrity(
        result={
            "metrics": {
                "audit": {
                    "accounting_integrity": {
                        "contract_version": "accounting_integrity_audit@1",
                        "status": "FAIL",
                        "reason": "Detected invariant violations.",
                        "summary": {
                            "trading_days": 2,
                            "days_with_evidence": 2,
                            "missing_evidence_days": 0,
                            "cash_check_fail": 1,
                            "position_check_fail": 0,
                            "nav_check_fail": 0,
                            "invalid_nav_days": 0,
                            "negative_cash_days": 0,
                            "max_positions_breach_days": 0,
                        },
                        "samples": {"cash_check_fail": [{"day": "2026-03-02"}]},
                    }
                }
            }
        }
    )

    assert gate["status"] == "FAIL"
    assert gate["metrics"]["cash_check_fail"] == 1
    assert gate["evidence"]["source"] == "result"


def test_evaluate_accounting_integrity_returns_unknown_when_evidence_missing() -> None:
    gate = evaluate_accounting_integrity(result={})

    assert gate["status"] == "UNKNOWN"
    assert gate["metrics"]["trading_days"] == 0


def test_evaluate_timing_alignment_derives_pass_from_price_only_next_day_artifacts(tmp_path) -> None:
    results_dir = tmp_path / "exp_timing_pass"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "compiled_plan.json").write_text(
        json.dumps(
            {
                "runtime_config": {
                    "execution": {"t_plus_one": True},
                    "strategy": {"name": "breakout_trend", "params": {"enable_sector_gate": False}},
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_dir / "input_config.json").write_text(
        json.dumps(
            {
                "strategy_pack": "BREAKOUT_TREND",
                "sector_gate": {"enabled": False},
                "position_risk": {"cost_model": {"matching": "next_open"}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gate = evaluate_timing_alignment(
        stage_summary={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        stage_pipeline={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        results_dir=results_dir,
    )

    assert gate["status"] == "PASS"
    assert gate["metrics"]["contract_proved"] is True
    assert gate["metrics"]["pit_safe"] is True


def test_evaluate_timing_alignment_keeps_unknown_when_membership_signal_is_enabled(tmp_path) -> None:
    results_dir = tmp_path / "exp_timing_unknown"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "compiled_plan.json").write_text(
        json.dumps(
            {
                "runtime_config": {
                    "execution": {"t_plus_one": True},
                    "strategy": {"name": "breakout_trend", "params": {"enable_sector_gate": True}},
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_dir / "input_config.json").write_text(
        json.dumps(
            {
                "strategy_pack": "BREAKOUT_TREND",
                "sector_gate": {"enabled": True},
                "position_risk": {"cost_model": {"matching": "next_open"}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gate = evaluate_timing_alignment(
        stage_summary={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        stage_pipeline={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        results_dir=results_dir,
    )

    assert gate["status"] == "UNKNOWN"
    assert gate["metrics"]["contract_proved"] is True
    assert gate["metrics"]["pit_safe"] is False


def test_evaluate_timing_alignment_fails_on_same_day_fill_from_lineage_ledger(tmp_path) -> None:
    results_dir = tmp_path / "exp_timing_same_day_fill"
    results_dir.mkdir(parents=True, exist_ok=True)
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
                "fill_date": "2024-01-02",
                "symbol": "sh600000",
                "side": "BUY",
                "qty": 100,
                "reason_code": "ENTRY",
                "terminal_status": "filled",
                "terminal_reason": "",
                "deferred_count": 0,
            }
        ]
    ).to_csv(results_dir / "execution_lineage_ledger.csv", index=False)
    (results_dir / "audit.json").write_text("{}", encoding="utf-8")

    gate = evaluate_timing_alignment(
        stage_summary={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        stage_pipeline={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        results_dir=results_dir,
    )

    assert gate["status"] == "FAIL"
    assert gate["metrics"]["lineage_same_day_fill_count"] == 1


def test_evaluate_timing_alignment_prefers_lineage_evidence_when_available(tmp_path) -> None:
    results_dir = tmp_path / "exp_timing_lineage_pass"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "compiled_plan.json").write_text(
        json.dumps(
            {
                "runtime_config": {
                    "execution": {"t_plus_one": True},
                    "strategy": {"name": "breakout_trend", "params": {"enable_sector_gate": False}},
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_dir / "input_config.json").write_text(
        json.dumps(
            {
                "strategy_pack": "BREAKOUT_TREND",
                "sector_gate": {"enabled": False},
                "position_risk": {"cost_model": {"matching": "next_open"}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
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
            }
        ]
    ).to_csv(results_dir / "execution_lineage_ledger.csv", index=False)
    (results_dir / "audit.json").write_text("{}", encoding="utf-8")

    gate = evaluate_timing_alignment(
        stage_summary={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        stage_pipeline={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        results_dir=results_dir,
    )

    assert gate["status"] == "PASS"
    assert gate["metrics"]["lineage_rows"] == 1
    assert gate["metrics"]["lineage_same_day_fill_count"] == 0

def test_evaluate_result_sanity_returns_unknown_when_sample_too_small() -> None:
    gate = evaluate_result_sanity(
        perf={"total_return": 0.2, "sharpe": 8.0, "cagr": 2.0, "trades": 5},
        run_meta={"counters": {"closed_trades": 5}, "stage_pipeline": {"trading_days": 100}},
        symbol_performance_df=pd.DataFrame(
            [{"symbol": "sh600000", "net_pnl": 1000.0}, {"symbol": "sz000001", "net_pnl": 500.0}]
        ),
    )

    assert gate["status"] == "UNKNOWN"


def test_build_research_audit_reuses_evidence_refs_instead_of_embedding_payload(tmp_path) -> None:
    results_dir = tmp_path / "exp_ra"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "data": {"universe_mode": "HS300_ZZ500"},
                "universe": {
                    "universe_mode": "HS300_ZZ500",
                    "symbols_source": "pit_index_constituents",
                    "load_table": "pit_index_constituents",
                    "resolve_asof": "2016-03-01",
                    "dynamic_all_a_entry": False,
                },
                "counters": {"closed_trades": 30},
                "stage_pipeline": {
                    "schema_version": "stage_pipeline_summary@1",
                    "execution_shell": "stage_pipeline_shell_bridge",
                    "daily_loop_mode": "single_day_loop",
                    "route_id": "provider_breakout_runtime",
                    "trading_days": 300,
                },
                "report_consistency": {"resolved_config_hash": "abc123"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_dir / "manifest.json").write_text(
        json.dumps(
            {
                "config_snapshots": {
                    "input_config": "input_config.json",
                    "resolved_config": "resolved_config.json",
                    "compiled_plan": "compiled_plan.json",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_dir / "perf.json").write_text(
        json.dumps(
            {"total_return": 0.2, "sharpe": 1.2, "cagr": 0.1, "trades": 30},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_dir / "audit.json").write_text("{}", encoding="utf-8")
    (results_dir / "stage_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "stage_pipeline_summary@1",
                "execution_shell": "stage_pipeline_shell_bridge",
                "daily_loop_mode": "single_day_loop",
                "route_id": "provider_breakout_runtime",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    audit = build_research_audit(results_dir=results_dir)

    assert audit["contract_version"] == "research_audit@1"
    assert audit["gates"]["accounting_integrity"]["status"] == "UNKNOWN"
    assert audit["evidence_refs"]["audit"] == "audit.json"
    assert audit["evidence_refs"]["execution_lineage_ledger"] is None
    assert audit["evidence_refs"]["run_meta"] == "run_meta.json"
    assert audit["evidence_refs"]["manifest"] == "manifest.json"
    assert audit["evidence_refs"]["stage_summary"] == "stage_summary.json"
    assert "run_meta" not in audit
    assert "manifest" not in audit
    assert "stage_summary" not in audit
