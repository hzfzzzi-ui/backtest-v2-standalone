from __future__ import annotations

from backend.research import study_loader, study_runner


def test_etf_research_mainline_r1_builds_expected_execution_plan() -> None:
    study = study_loader.load_study_definition("etf/cn_broad_based_research_mainline_r1")
    plan = study_runner.build_execution_plan(study)

    assert len(plan) == 1
    payload = dict(plan[0]["request_payload"])
    config = dict(payload["config_json"])
    etf_beta = dict(config["governed_a_share"]["etf_beta"])

    assert payload["asset_scope"] == "cn_etf"
    assert payload["start_date"] == "2012-01-01"
    assert payload["end_date"] == "2026-03-24"
    assert config["universe"]["symbols"] == [
        "510050.SH",
        "510300.SH",
        "510500.SH",
        "512100.SH",
        "512890.SH",
        "588000.SH",
        "518880.SH",
        "511010.SH",
    ]
    assert etf_beta["strategy_role"] == "governed_broad_based_standalone_mainline"
    assert etf_beta["rebalance_frequency"] == "biweekly"
    assert etf_beta["selection_chain_profile"] == "core_growth_slot"
    assert etf_beta["growth_seat_symbol"] == "588000.SH"
    assert etf_beta["limited_defense_candidates"] == ["511010.SH", "518880.SH"]
    assert etf_beta["defense_asset_weights"] == {"511010.SH": 0.65, "518880.SH": 0.35}
    assert etf_beta["target_selected_count_by_state_5"]["RISK_OFF"] == 1
    assert etf_beta["target_exposure_by_state_5"]["RISK_OFF"] == 0.15
    assert etf_beta["fallback_symbol"] == "511010.SH"
