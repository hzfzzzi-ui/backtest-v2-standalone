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
        reason="drawdown improvement unclear",
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
    assert append["human_summary"]["reason"] == "drawdown improvement unclear"

