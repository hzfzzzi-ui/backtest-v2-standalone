from __future__ import annotations

from backend.research import study_loader, study_runner


def test_etf_research_mainline_r1_builds_expected_execution_plan() -> None:
    study = study_loader.load_study_definition(
        "research/archive/research_only_studies/2026-04-26/etf/cn_broad_based_research_mainline_r1.study.yaml"
    )
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


def test_etf_research_shadow_pool_v1_builds_expected_execution_plan() -> None:
    study = study_loader.load_study_definition("etf/cn_etf_research_shadow_pool_v1")
    plan = study_runner.build_execution_plan(study)

    assert len(plan) == 3
    payload = dict(plan[0]["request_payload"])
    config = dict(payload["config_json"])
    etf_beta = dict(config["governed_a_share"]["etf_beta"])

    assert payload["asset_scope"] == "cn_etf"
    assert payload["benchmark"] == "510880.SH"
    assert payload["start_date"] == "2016-01-04"
    assert payload["end_date"] == "2026-05-08"
    assert config["universe"]["benchmark"] == "510880.SH"
    assert config["universe"]["symbols"] == ["cn_etf_research_shadow_pool_v1"]
    assert config["universe_filter"]["min_price"] == 0.0
    assert config["data_source"]["stocks_table"] == "pams_cn_etf_daily"
    assert etf_beta["strategy_role"] == "governed_broad_based_standalone_mainline"
    assert etf_beta["source_entry_type"] == "cn_etf_broad_based_standalone_mainline_entry"
    assert etf_beta["template_asset_pool_version"] == "cn_etf_research_shadow_pool_v1"
    assert etf_beta["core_beta_symbols"] == ["510880.SH", "512890.SH", "159915.SZ", "588000.SH", "159845.SZ"]
    assert etf_beta["limited_defense_candidates"] == ["518880.SH"]
    assert study.metadata["research_only"] is True
    assert study.metadata["pool_version"] == "cn_etf_research_shadow_pool_v1"


def test_etf_formal_pool_rotation_control_v1_builds_expected_execution_plan() -> None:
    study = study_loader.load_study_definition("etf/cn_etf_formal_pool_rotation_control_v1")
    plan = study_runner.build_execution_plan(study)

    assert len(plan) == 3
    payload = dict(plan[0]["request_payload"])
    config = dict(payload["config_json"])
    etf_beta = dict(config["governed_a_share"]["etf_beta"])

    assert payload["asset_scope"] == "cn_etf"
    assert payload["benchmark"] == "510300.SH"
    assert payload["start_date"] == "2016-01-04"
    assert payload["end_date"] == "2026-05-08"
    assert config["universe"]["benchmark"] == "510300.SH"
    assert config["universe"]["symbols"] == ["cn_etf_first_wave_core"]
    assert config["universe_filter"]["min_price"] == 0.0
    assert etf_beta["strategy_role"] == "governed_broad_based_standalone_mainline"
    assert etf_beta["source_entry_type"] == "cn_etf_broad_based_standalone_mainline_entry"
    assert etf_beta["template_asset_pool_version"] == "formal_etf_pool_v1"
    assert etf_beta["core_beta_symbols"] == ["510300.SH", "510500.SH", "510050.SH", "512100.SH"]
    assert etf_beta["limited_defense_candidates"] == ["511010.SH"]
    assert etf_beta["fallback_symbol"] == "511010.SH"
    assert study.metadata["research_only"] is True
    assert study.metadata["control_for"] == "cn_etf_research_shadow_pool_v1"


def test_etf_research_realworld_pool_v1_builds_expected_execution_plan() -> None:
    study = study_loader.load_study_definition("etf/cn_etf_research_realworld_pool_v1")
    plan = study_runner.build_execution_plan(study)

    assert len(plan) == 3
    payload = dict(plan[0]["request_payload"])
    config = dict(payload["config_json"])
    etf_beta = dict(config["governed_a_share"]["etf_beta"])

    assert payload["asset_scope"] == "cn_etf"
    assert payload["benchmark"] == "510300.SH"
    assert payload["start_date"] == "2016-01-04"
    assert payload["end_date"] == "2026-05-08"
    assert config["universe"]["benchmark"] == "510300.SH"
    assert config["universe"]["symbols"] == ["cn_etf_research_realworld_pool_v1"]
    assert etf_beta["template_asset_pool_version"] == "cn_etf_research_realworld_pool_v1"
    assert "512480.SH" in etf_beta["growth_slot_symbols"]
    assert "513100.SH" in etf_beta["growth_slot_symbols"]
    assert etf_beta["fallback_symbol"] == "511880.SH"
    assert etf_beta["limited_defense_candidates"] == ["518880.SH", "511010.SH", "511260.SH", "511880.SH"]
    assert len(etf_beta["core_beta_symbols"]) == 29
    assert study.metadata["research_only"] is True
    assert study.metadata["pool_version"] == "cn_etf_research_realworld_pool_v1"


def test_etf_research_industry_theme_pool_v2_builds_expected_execution_plan() -> None:
    study = study_loader.load_study_definition("etf/cn_etf_research_industry_theme_pool_v2")
    plan = study_runner.build_execution_plan(study)

    assert len(plan) == 3
    payload = dict(plan[0]["request_payload"])
    config = dict(payload["config_json"])
    etf_beta = dict(config["governed_a_share"]["etf_beta"])

    assert payload["asset_scope"] == "cn_etf"
    assert payload["benchmark"] == "510300.SH"
    assert payload["start_date"] == "2016-01-04"
    assert payload["end_date"] == "2026-05-08"
    assert config["universe"]["symbols"] == ["cn_etf_research_industry_theme_pool_v2"]
    assert etf_beta["template_asset_pool_version"] == "cn_etf_research_industry_theme_pool_v2"
    assert "159819.SZ" in etf_beta["growth_slot_symbols"]
    assert "562500.SH" in etf_beta["growth_slot_symbols"]
    assert "159755.SZ" in etf_beta["growth_slot_symbols"]
    assert etf_beta["fallback_symbol"] == "511880.SH"
    assert len(etf_beta["core_beta_symbols"]) == 52
    assert study.metadata["sequential_round"] == "industry_theme_v2_after_realworld_v1"


def test_etf_research_style_smart_beta_pool_v2_builds_expected_execution_plan() -> None:
    study = study_loader.load_study_definition("etf/cn_etf_research_style_smart_beta_pool_v2")
    plan = study_runner.build_execution_plan(study)

    assert len(plan) == 3
    payload = dict(plan[0]["request_payload"])
    config = dict(payload["config_json"])
    etf_beta = dict(config["governed_a_share"]["etf_beta"])

    assert payload["asset_scope"] == "cn_etf"
    assert payload["benchmark"] == "510300.SH"
    assert payload["start_date"] == "2016-01-04"
    assert payload["end_date"] == "2026-05-08"
    assert config["universe"]["symbols"] == ["cn_etf_research_style_smart_beta_pool_v2"]
    assert etf_beta["template_asset_pool_version"] == "cn_etf_research_style_smart_beta_pool_v2"
    assert "159201.SZ" in etf_beta["core_slot_symbols"]
    assert "512050.SH" in etf_beta["core_slot_symbols"]
    assert "159819.SZ" in etf_beta["growth_slot_symbols"]
    assert etf_beta["fallback_symbol"] == "511880.SH"
    assert len(etf_beta["core_slot_symbols"]) == 52
    assert len(etf_beta["growth_slot_symbols"]) == 43
    assert len(etf_beta["core_beta_symbols"]) == 95
    assert study.metadata["sequential_round"] == "style_smart_beta_v2_after_industry_theme_v2"
