from __future__ import annotations

from backend.core.services import baseline_report_service, experiment_query_service, experiment_summary_service


def test_summary_and_baseline_services_expose_apply_ready_contracts() -> None:
    surface = {
        "summary": {"exp_id": "exp_contract", "label": "exp_contract"},
        "perf": {"cagr": 0.11, "max_drawdown": -0.22, "sharpe": 0.9, "trades": 18},
        "audit": {"status": "pass"},
    }

    machine = experiment_summary_service.build_machine_summary_bundle(
        exp_id="exp_contract",
        hypothesis="regime filter should reduce false breakouts",
        surface=surface,
    )
    human = experiment_summary_service.build_human_summary_bundle(
        exp_id="exp_contract",
        title="exp_contract",
        verdict="FAIL",
        reason="回撤改善不明显",
        perf=surface["perf"],
    )
    ledger = baseline_report_service.build_baseline_ledger_entry(
        baseline_id="baseline_V10_1",
        exp_id="exp_contract",
        verdict="FAIL",
        summary=machine,
    )
    append = baseline_report_service.build_baseline_report_append(
        baseline_id="baseline_V10_1",
        exp_id="exp_contract",
        human_summary=human,
    )

    assert machine["schema_version"] == "experiment_nac@1"
    assert human["verdict"] == "FAIL"
    assert ledger["baseline_id"] == "baseline_V10_1"
    assert append["human_summary"]["reason"] == "回撤改善不明显"


def test_v10_1_regression_snapshot_is_pinned_to_current_baseline() -> None:
    snapshot = experiment_query_service.get_v10_1_regression_snapshot()

    assert snapshot["baseline_id"] == "baseline_V10_1"
    assert snapshot["linked_exp_id"] == "exp_20260314_144548534_7db9"
    assert snapshot["manifest"] == {
        "schema_version": "backtest_v2_experiment_manifest@2",
        "status": "OK",
        "baseline_compare_status": "NOT_RUN",
        "route_id": "provider_breakout_runtime",
        "execution_shell": "stage_pipeline_shell_bridge",
    }
    assert snapshot["perf"] == {
        "total_return": 4.425630011081876,
        "max_drawdown": -0.29025259513173496,
        "cagr": 0.2032763161631579,
        "sharpe": 0.8891097010317657,
        "calmar": 0.7003428033809594,
        "trades": 467,
        "turnover": 0.02077596030035478,
        "effective_execution_start_date": "2016-08-29",
    }
    assert snapshot["counters"] == {
        "orders": 467,
        "closed_trades": 230,
        "buy_orders_count": 237,
        "sell_orders_count": 230,
    }
    assert snapshot["artifacts"] == {
        "orders": {"rows": 467, "first_date": "2016-08-29", "last_date": "2025-12-23"},
        "trades": {"rows": 467, "first_date": "2016-08-29", "last_date": "2025-12-23"},
        "nav": {"rows": 2303, "first_date": "2016-08-29", "last_date": "2026-02-27"},
    }


def test_baseline_v10_regression_snapshot_is_available_for_breakout_golden() -> None:
    snapshot = experiment_query_service.get_baseline_regression_snapshot("baseline_V10")

    assert snapshot["baseline_id"] == "baseline_V10"
    assert snapshot["linked_exp_id"] == "exp_20260312_034933994_f811"
    assert snapshot["manifest"] == {
        "schema_version": "backtest_v2_experiment_manifest@2",
        "status": "OK",
        "baseline_compare_status": "NOT_RUN",
        "route_id": "provider_breakout_runtime",
        "execution_shell": "stage_pipeline_shell_bridge",
    }
    assert snapshot["perf"] == {
        "total_return": 4.096692064775184,
        "max_drawdown": -0.2898315564107581,
        "cagr": 0.1950697650911588,
        "sharpe": 0.8584897711959014,
        "calmar": 0.6730452939868977,
        "trades": 467,
        "turnover": 0.020618773515121508,
        "effective_execution_start_date": "2016-08-29",
    }
    assert snapshot["counters"] == {
        "orders": 467,
        "closed_trades": 230,
        "buy_orders_count": 237,
        "sell_orders_count": 230,
    }
    assert snapshot["artifacts"] == {
        "orders": {"rows": 467, "first_date": "2016-08-29", "last_date": "2025-12-23"},
        "trades": {"rows": 467, "first_date": "2016-08-29", "last_date": "2025-12-23"},
        "nav": {"rows": 2303, "first_date": "2016-08-29", "last_date": "2026-02-27"},
    }
