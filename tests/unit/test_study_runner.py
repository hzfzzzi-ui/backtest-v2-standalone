from __future__ import annotations

from pathlib import Path
import json

from backend.research.study_definition import validate_study_payload
from backend.research import study_loader, study_runner


def _study():
    return validate_study_payload(
        {
            "study_id": "v10/demo",
            "title": "Demo Study",
            "asset_scope": "cn_a_equity",
            "baseline_id": "baseline_V10_1",
            "hypothesis": "residual split should improve ranking stability",
            "change_scope": {"modules_modified": ["ranking"]},
            "variants": [
                {
                    "name": "B0",
                    "config_patches": [
                        {"path": "signal_generation.ranking.residual_window", "value": 40},
                    ],
                }
            ],
            "windows": [
                {
                    "key": "main",
                    "role": "main",
                    "start": "2024-01-01",
                    "end": "2024-02-01",
                }
            ],
            "hard_gates": {"min_cagr": 0.1, "min_trades": 1},
            "required_outputs": ["machine_bundle", "human_bundle", "baseline_append"],
            "request_template": {"fast_mode": True, "config_json": {"universe": {"benchmark": "000300.SH"}}},
        }
    )


def test_build_execution_plan_applies_window_and_variant_patch() -> None:
    plan = study_runner.build_execution_plan(_study())
    payload = plan[0]["request_payload"]
    assert payload["start_date"] == "2024-01-01"
    assert payload["end_date"] == "2024-02-01"
    assert payload["asset_scope"] == "cn_a_equity"
    assert payload["config_json"]["signal_generation"]["ranking"]["residual_window"] == 40
    assert payload["config_json"]["universe"]["start"] == "2024-01-01"


def test_hs300_zz500_csi1000_pool_expansion_study_builds_stock_only_ab_plan() -> None:
    study = study_loader.load_study_definition("v10/hs300_zz500_csi1000_pit_pool_expansion_v1")
    plan = study_runner.build_execution_plan(study)

    assert len(plan) == 9
    assert {item["variant_name"] for item in plan} == {
        "B0_HS300_ZZ500",
        "A1_HS300_ZZ500_CSI1000",
        "A2_HS300_ZZ500_CSI1000_MCAP100",
    }
    candidate = next(
        item
        for item in plan
        if item["window_key"] == "1626" and item["variant_name"] == "A1_HS300_ZZ500_CSI1000"
    )
    payload = candidate["request_payload"]
    assert payload["asset_scope"] == "cn_a_equity"
    assert payload["universe_mode"] == "HS300_ZZ500_CSI1000"
    assert payload["runtime_config_json"]["universe_mode"] == "HS300_ZZ500_CSI1000"
    assert payload["runtime_config_json"]["universe"]["membership_mode"] == "PIT_DYNAMIC"
    assert payload["runtime_config_json"]["universe"]["start"] == "2016-01-04"
    assert payload["study_meta"]["study_id"] == "v10/hs300_zz500_csi1000_pit_pool_expansion_v1"

    a2 = next(
        item
        for item in plan
        if item["window_key"] == "1626" and item["variant_name"] == "A2_HS300_ZZ500_CSI1000_MCAP100"
    )
    a2_payload = a2["request_payload"]
    assert a2_payload["universe_mode"] == "HS300_ZZ500_CSI1000"
    assert a2_payload["runtime_config_json"]["universe_mode"] == "HS300_ZZ500_CSI1000"
    assert a2_payload["runtime_config_json"]["universe"]["membership_mode"] == "PIT_DYNAMIC"
    assert a2_payload["runtime_config_json"]["universe"]["filters"]["csi1000_new_min_circ_mv_yi"] == 100


def test_b1_runtime_replacement_ab_uses_runtime_config_and_single_variable_patch() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_b1_runtime_replacement_ab_v1")
    plan = study_runner.build_execution_plan(study, only_window_keys=["1626"])

    assert len(plan) == 2
    assert {item["variant_name"] for item in plan} == {
        "B0_V3_STOCK_REPLAY",
        "B1_RUNTIME_REPLACE_CONTROL",
    }

    b0 = next(item for item in plan if item["variant_name"] == "B0_V3_STOCK_REPLAY")
    b1 = next(item for item in plan if item["variant_name"] == "B1_RUNTIME_REPLACE_CONTROL")
    b0_payload = b0["request_payload"]
    b1_payload = b1["request_payload"]

    assert b0_payload["config_path"].endswith("backend\\configs\\pams_cn_pg.json") or b0_payload["config_path"].endswith("backend/configs/pams_cn_pg.json")
    assert b0_payload["runtime_config_path"] == b1_payload["runtime_config_path"]
    assert "config_json" not in b0_payload
    assert "config_json" not in b1_payload
    assert b0_payload["runtime_config_json"]["universe"]["start"] == "2016-01-01"
    assert b1_payload["runtime_config_json"]["universe"]["end"] == "2026-05-08"
    assert b0_payload["runtime_config_json"].get("sizing", {}) == {}

    b1_sizing = b1_payload["runtime_config_json"]["sizing"]
    assert b1_sizing == {
        "rotation_replace_enabled": True,
        "rotation_replace_only_strong_risk_on": True,
        "rotation_replace_max_swaps_per_day": 1,
        "rotation_replace_candidate_top_n": 3,
        "rotation_replace_min_score_gap": 0.15,
    }
    assert b0_payload["enable_multifactor_rank"] is True
    assert b1_payload["enable_multifactor_rank"] is True


def test_v4_relative_replacement_stock_ab_uses_promoted_stock_runtime_config() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_v4_relative_replacement_stock_ab_v1")
    plan = study_runner.build_execution_plan(study, only_window_keys=["1626"])

    assert len(plan) == 2
    assert {item["variant_name"] for item in plan} == {
        "B0_V4_STOCK_REPLAY",
        "REL_REPLACE_GAP005_TOP5",
    }

    b0 = next(item for item in plan if item["variant_name"] == "B0_V4_STOCK_REPLAY")
    rel = next(item for item in plan if item["variant_name"] == "REL_REPLACE_GAP005_TOP5")
    b0_payload = b0["request_payload"]
    rel_payload = rel["request_payload"]

    assert b0_payload["runtime_config_path"] == rel_payload["runtime_config_path"]
    assert b0_payload["runtime_config_path"].replace("\\", "/").endswith("outputs/baselines/baseline_V10_1/run_config.json")
    assert "config_json" not in b0_payload
    assert "config_json" not in rel_payload
    assert b0_payload["runtime_config_json"]["universe"]["start"] == "2016-01-01"
    assert rel_payload["runtime_config_json"]["universe"]["end"] == "2026-05-11"
    assert b0_payload["runtime_config_json"].get("sizing", {}) == {}

    assert rel_payload["runtime_config_json"]["sizing"] == {
        "rotation_replace_enabled": True,
        "rotation_replace_only_strong_risk_on": False,
        "rotation_replace_max_swaps_per_day": 1,
        "rotation_replace_candidate_top_n": 5,
        "rotation_replace_min_score_gap": 0.05,
    }
    assert b0_payload["universe_mode"] == "HS300_ZZ500"
    assert rel_payload["universe_mode"] == "HS300_ZZ500"


def test_d5_mfe_mae_3d_runtime_ab_uses_runtime_config_and_single_variable_patch() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_d5_mfe_mae_3d_runtime_ab_v1")
    plan = study_runner.build_execution_plan(study, only_window_keys=["1626"])

    assert len(plan) == 2
    assert {item["variant_name"] for item in plan} == {
        "B0_V3_STOCK_REPLAY",
        "D5_3D_MFE_MAE_RUNTIME_HALF_EXIT",
    }

    b0 = next(item for item in plan if item["variant_name"] == "B0_V3_STOCK_REPLAY")
    d5 = next(item for item in plan if item["variant_name"] == "D5_3D_MFE_MAE_RUNTIME_HALF_EXIT")
    b0_payload = b0["request_payload"]
    d5_payload = d5["request_payload"]

    assert b0_payload["runtime_config_path"] == d5_payload["runtime_config_path"]
    assert "config_json" not in b0_payload
    assert "config_json" not in d5_payload
    assert b0_payload["runtime_config_json"]["universe"]["start"] == "2016-01-01"
    assert d5_payload["runtime_config_json"]["universe"]["end"] == "2026-05-08"
    patch = {
        "enable_mfe_mae_confirmation_exit": True,
        "mfe_mae_confirmation_lookahead_bars": 3,
        "mfe_mae_confirmation_min_mfe_pct": 0.02,
        "mfe_mae_confirmation_max_mae_pct": -0.05,
        "mfe_mae_confirmation_exit_pct": 0.5,
    }
    b0_params = dict(b0_payload["runtime_config_json"]["strategy"]["params"])
    d5_params = dict(d5_payload["runtime_config_json"]["strategy"]["params"])
    assert {key: d5_params[key] for key in patch} == patch
    for key in patch:
        b0_params.pop(key, None)
        d5_params.pop(key, None)
    assert d5_params == b0_params
    assert b0_payload["enable_multifactor_rank"] is True
    assert d5_payload["enable_multifactor_rank"] is True


def test_high_chase_d5_action_ab_uses_runtime_config_and_scoped_d5_patches() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_high_chase_d5_action_ab_v1")
    plan = study_runner.build_execution_plan(study, only_window_keys=["1626"])

    assert len(plan) == 5
    assert {item["variant_name"] for item in plan} == {
        "B0_V3_STOCK_REPLAY",
        "D5_ALL_3D_IMMEDIATE_HALF_EXIT",
        "HC_D5_IMMEDIATE_HALF_EXIT",
        "HC_D5_WATCH_DAY10_HALF_EXIT",
        "HC_D5_DELAYED_5D_HALF_EXIT",
    }

    b0 = next(item for item in plan if item["variant_name"] == "B0_V3_STOCK_REPLAY")
    immediate = next(item for item in plan if item["variant_name"] == "HC_D5_IMMEDIATE_HALF_EXIT")
    watch = next(item for item in plan if item["variant_name"] == "HC_D5_WATCH_DAY10_HALF_EXIT")
    delayed = next(item for item in plan if item["variant_name"] == "HC_D5_DELAYED_5D_HALF_EXIT")

    for item in (immediate, watch, delayed):
        assert item["request_payload"]["runtime_config_path"] == b0["request_payload"]["runtime_config_path"]
        assert "config_json" not in item["request_payload"]
        assert item["request_payload"]["enable_multifactor_rank"] is True

    immediate_params = dict(immediate["request_payload"]["runtime_config_json"]["strategy"]["params"])
    assert immediate_params["enable_mfe_mae_confirmation_exit"] is True
    assert immediate_params["mfe_mae_confirmation_scope"] == "high_chase"
    assert immediate_params["mfe_mae_confirmation_action"] == "exit"
    assert immediate_params["mfe_mae_confirmation_lookahead_bars"] == 3

    watch_params = dict(watch["request_payload"]["runtime_config_json"]["strategy"]["params"])
    assert watch_params["mfe_mae_confirmation_scope"] == "high_chase"
    assert watch_params["mfe_mae_confirmation_action"] == "watch_day10"
    assert watch_params["mfe_mae_watch_review_bars"] == 10
    assert watch_params["mfe_mae_watch_deep_mae_immediate_pct"] == -0.08

    delayed_params = dict(delayed["request_payload"]["runtime_config_json"]["strategy"]["params"])
    assert delayed_params["mfe_mae_confirmation_scope"] == "high_chase"
    assert delayed_params["mfe_mae_confirmation_action"] == "exit"
    assert delayed_params["mfe_mae_confirmation_lookahead_bars"] == 5


def test_high_chase_d5_deep_mae_stock_ab_uses_runtime_config_and_stock_only_patches() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_high_chase_d5_deep_mae_stock_ab_v1")
    plan = study_runner.build_execution_plan(study, only_window_keys=["1626"])

    assert len(plan) == 5
    assert {item["variant_name"] for item in plan} == {
        "B0_V3_STOCK_REPLAY",
        "HC_D5_IMMEDIATE_HALF_EXIT",
        "D7_DEEP_ONLY_IMMEDIATE_HALF_EXIT",
        "D7_MILD_WATCH_DEEP_IMMEDIATE_DAY10",
        "D7_ALL_WATCH_DEEP_REVIEW_DAY10",
    }

    b0 = next(item for item in plan if item["variant_name"] == "B0_V3_STOCK_REPLAY")
    incumbent = next(item for item in plan if item["variant_name"] == "HC_D5_IMMEDIATE_HALF_EXIT")
    deep_only = next(item for item in plan if item["variant_name"] == "D7_DEEP_ONLY_IMMEDIATE_HALF_EXIT")
    mild_watch = next(item for item in plan if item["variant_name"] == "D7_MILD_WATCH_DEEP_IMMEDIATE_DAY10")
    all_watch = next(item for item in plan if item["variant_name"] == "D7_ALL_WATCH_DEEP_REVIEW_DAY10")

    for item in (incumbent, deep_only, mild_watch, all_watch):
        payload = item["request_payload"]
        assert payload["asset_scope"] == "cn_a_equity"
        assert payload["runtime_config_path"] == b0["request_payload"]["runtime_config_path"]
        assert "config_json" not in payload
        assert payload["enable_multifactor_rank"] is True
        assert "runner_params" not in payload

    b0_payload = b0["request_payload"]
    assert b0_payload["runtime_config_json"]["universe"]["start"] == "2016-01-01"
    assert b0_payload["runtime_config_json"]["universe"]["end"] == "2026-05-11"

    incumbent_params = dict(incumbent["request_payload"]["runtime_config_json"]["strategy"]["params"])
    assert incumbent_params["mfe_mae_confirmation_scope"] == "high_chase"
    assert incumbent_params["mfe_mae_confirmation_action"] == "exit"
    assert incumbent_params["mfe_mae_confirmation_max_mae_pct"] == -0.05

    deep_params = dict(deep_only["request_payload"]["runtime_config_json"]["strategy"]["params"])
    assert deep_params["mfe_mae_confirmation_action"] == "exit"
    assert deep_params["mfe_mae_confirmation_max_mae_pct"] == -0.08

    mild_watch_params = dict(mild_watch["request_payload"]["runtime_config_json"]["strategy"]["params"])
    assert mild_watch_params["mfe_mae_confirmation_action"] == "watch_day10"
    assert mild_watch_params["mfe_mae_confirmation_max_mae_pct"] == -0.05
    assert mild_watch_params["mfe_mae_watch_review_min_mfe_pct"] == 0.05
    assert mild_watch_params["mfe_mae_watch_review_max_current_return_pct"] == 0.05
    assert mild_watch_params["mfe_mae_watch_review_max_mae_pct"] == -0.08
    assert mild_watch_params["mfe_mae_watch_deep_mae_immediate_pct"] == -0.08

    all_watch_params = dict(all_watch["request_payload"]["runtime_config_json"]["strategy"]["params"])
    assert all_watch_params["mfe_mae_confirmation_action"] == "watch_day10"
    assert all_watch_params["mfe_mae_watch_review_min_mfe_pct"] == 0.05
    assert all_watch_params["mfe_mae_watch_review_max_mae_pct"] == -0.08
    assert all_watch_params["mfe_mae_watch_deep_mae_immediate_pct"] == -1.0


def test_trend_quality_soft_score_stock_ab_patches_only_soft_score_params() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_trend_quality_soft_score_ab_v1")
    plan = study_runner.build_execution_plan(study, only_window_keys=["1626"])

    assert len(plan) == 2
    assert {item["variant_name"] for item in plan} == {
        "B0_V4_STOCK_REPLAY",
        "TQ_SOFT_SCORE_W030",
    }

    b0 = next(item for item in plan if item["variant_name"] == "B0_V4_STOCK_REPLAY")
    candidate = next(item for item in plan if item["variant_name"] == "TQ_SOFT_SCORE_W030")
    b0_payload = b0["request_payload"]
    candidate_payload = candidate["request_payload"]

    assert candidate_payload["asset_scope"] == "cn_a_equity"
    assert candidate_payload["runtime_config_path"] == b0_payload["runtime_config_path"]
    assert "config_json" not in candidate_payload
    assert candidate_payload["enable_multifactor_rank"] is True
    assert candidate_payload["runtime_config_json"]["universe_mode"] == "HS300_ZZ500"
    assert candidate_payload["runtime_config_json"]["universe"]["membership_mode"] == "PIT_DYNAMIC"
    assert candidate_payload["runtime_config_json"]["universe"]["start"] == "2016-01-01"
    assert candidate_payload["runtime_config_json"]["universe"]["end"] == "2026-05-12"

    b0_params = dict(b0_payload["runtime_config_json"]["strategy"]["params"])
    candidate_params = dict(candidate_payload["runtime_config_json"]["strategy"]["params"])
    patch = {
        "trend_quality_soft_score_enabled": True,
        "trend_quality_soft_score_weight": 0.30,
        "trend_quality_r2_60_weight": 0.45,
        "trend_quality_slope60_weight": 0.25,
        "trend_quality_ret60_vol_adj_weight": 0.15,
        "trend_quality_ret60_dd_adj_weight": 0.15,
    }
    assert {key: candidate_params[key] for key in patch} == patch
    for key in patch:
        b0_params.pop(key, None)
        candidate_params.pop(key, None)
    assert candidate_params == b0_params


def test_profit_giveback_ma20_protection_stock_ab_patches_only_giveback_params() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_profit_giveback_ma20_protection_ab_v1")
    plan = study_runner.build_execution_plan(study, only_window_keys=["1626"])

    assert len(plan) == 4
    assert {item["variant_name"] for item in plan} == {
        "B0_V4_STOCK_REPLAY",
        "GIVEBACK20_MA20_HALF",
        "GIVEBACK25_MA20_HALF",
        "GIVEBACK30_MA20_HALF",
    }

    b0 = next(item for item in plan if item["variant_name"] == "B0_V4_STOCK_REPLAY")
    giveback25 = next(item for item in plan if item["variant_name"] == "GIVEBACK25_MA20_HALF")
    b0_payload = b0["request_payload"]
    candidate_payload = giveback25["request_payload"]

    assert candidate_payload["asset_scope"] == "cn_a_equity"
    assert candidate_payload["runtime_config_path"] == b0_payload["runtime_config_path"]
    assert "config_json" not in candidate_payload
    assert candidate_payload["enable_multifactor_rank"] is True
    assert candidate_payload["runtime_config_json"]["universe_mode"] == "HS300_ZZ500"
    assert candidate_payload["runtime_config_json"]["universe"]["membership_mode"] == "PIT_DYNAMIC"
    assert candidate_payload["runtime_config_json"]["universe"]["start"] == "2016-01-01"
    assert candidate_payload["runtime_config_json"]["universe"]["end"] == "2026-05-12"

    b0_params = dict(b0_payload["runtime_config_json"]["strategy"]["params"])
    candidate_params = dict(candidate_payload["runtime_config_json"]["strategy"]["params"])
    patch = {
        "enable_peak_giveback_ma20_exit": True,
        "peak_giveback_ma20_min_peak_profit_pct": 0.20,
        "peak_giveback_ma20_min_giveback_pct": 0.25,
        "peak_giveback_ma20_min_hold_bars": 10,
        "peak_giveback_ma20_exit_pct": 0.5,
    }
    assert {key: candidate_params[key] for key in patch} == patch
    for key in patch:
        b0_params.pop(key, None)
        candidate_params.pop(key, None)
    assert candidate_params == b0_params


def test_risk_archetype_soft_deprioritize_stock_ab_patches_only_soft_score_params() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_risk_archetype_soft_deprioritize_ab_v1")
    plan = study_runner.build_execution_plan(study, only_window_keys=["1626"])

    assert len(plan) == 2
    assert {item["variant_name"] for item in plan} == {
        "B0_V4_STOCK_REPLAY",
        "RISK_ARCHETYPE_SOFT_Q80_H20_V15",
    }

    b0 = next(item for item in plan if item["variant_name"] == "B0_V4_STOCK_REPLAY")
    candidate = next(item for item in plan if item["variant_name"] == "RISK_ARCHETYPE_SOFT_Q80_H20_V15")
    b0_payload = b0["request_payload"]
    candidate_payload = candidate["request_payload"]

    assert candidate_payload["asset_scope"] == "cn_a_equity"
    assert candidate_payload["runtime_config_path"] == b0_payload["runtime_config_path"]
    assert "config_json" not in candidate_payload
    assert candidate_payload["enable_multifactor_rank"] is True
    assert candidate_payload["runtime_config_json"]["universe_mode"] == "HS300_ZZ500"
    assert candidate_payload["runtime_config_json"]["universe"]["membership_mode"] == "PIT_DYNAMIC"
    assert candidate_payload["runtime_config_json"]["universe"]["start"] == "2016-01-01"
    assert candidate_payload["runtime_config_json"]["universe"]["end"] == "2026-05-12"

    b0_params = dict(b0_payload["runtime_config_json"]["strategy"]["params"])
    candidate_params = dict(candidate_payload["runtime_config_json"]["strategy"]["params"])
    patch = {
        "risk_archetype_soft_deprioritize_enabled": True,
        "risk_archetype_soft_deprioritize_quantile": 0.80,
        "risk_archetype_hot_crowded_penalty": 0.20,
        "risk_archetype_high_volatility_penalty": 0.15,
    }
    assert {key: candidate_params[key] for key in patch} == patch
    for key in patch:
        b0_params.pop(key, None)
        candidate_params.pop(key, None)
    assert candidate_params == b0_params


def test_build_execution_plan_can_patch_config_loaded_from_config_path(tmp_path: Path) -> None:
    cfg_path = tmp_path / "baseline.json"
    cfg_path.write_text(
        json.dumps({"signal_generation": {"ranking": {"residual_window": 20}}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    study = validate_study_payload(
        {
            "study_id": "v10/demo_path",
            "title": "Demo From Path",
            "asset_scope": "cn_a_equity",
            "baseline_id": "baseline_V10_1",
            "hypothesis": "path-backed patching",
            "change_scope": {"modules_modified": ["ranking"]},
            "variants": [
                {
                    "name": "B0",
                    "config_patches": [
                        {"path": "signal_generation.ranking.residual_window", "value": 40},
                    ],
                }
            ],
            "windows": [{"key": "main", "role": "main", "start": "2024-01-01", "end": "2024-02-01"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "baseline_append"],
            "request_template": {"config_path": str(cfg_path)},
        }
    )

    payload = study_runner.build_execution_plan(study)[0]["request_payload"]
    assert payload["asset_scope"] == "cn_a_equity"
    assert payload["config_path"] == str(study_runner._default_runtime_config_path())
    assert payload["config_json"]["signal_generation"]["ranking"]["residual_window"] == 40


def test_build_execution_plan_resolves_relative_config_path_from_repo_root(monkeypatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "configs" / "baseline.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps({"universe": {"benchmark": "000300.SH"}}, ensure_ascii=False, indent=2), encoding="utf-8")
    runtime_cfg_path = tmp_path / "backend" / "configs" / "pams_cn_pg.json"
    runtime_cfg_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_cfg_path.write_text(json.dumps({"db": {}, "schema_mapping": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(study_runner, "_repo_root", lambda: tmp_path)
    study = validate_study_payload(
        {
            "study_id": "v10/demo_relative_path",
            "title": "Demo Relative Path",
            "asset_scope": "cn_a_equity",
            "baseline_id": "baseline_V10_1",
            "hypothesis": "relative path should stay executable",
            "change_scope": {"modules_modified": ["universe"]},
            "variants": [{"name": "B0"}],
            "windows": [{"key": "main", "role": "main", "start": "2024-01-01", "end": "2024-02-01"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "baseline_append"],
            "request_template": {"config_path": "configs/baseline.json"},
            "metadata": {"materialize_config_json": True},
        }
    )

    payload = study_runner.build_execution_plan(study)[0]["request_payload"]
    assert payload["config_path"] == str(runtime_cfg_path.resolve())
    assert payload["config_json"]["universe"]["benchmark"] == "000300.SH"


def test_build_execution_plan_loads_workbench_config_path_and_applies_window_bounds(tmp_path: Path) -> None:
    runtime_cfg_path = tmp_path / "runtime.json"
    runtime_cfg_path.write_text(
        json.dumps(
            {
                "db": {},
                "schema_mapping": {},
                "universe": {"benchmark": "000300.SH", "start": "2016-01-01", "end": "2026-01-01"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    study = validate_study_payload(
        {
            "study_id": "v10/demo_workbench_path",
            "title": "Demo Workbench Path",
            "asset_scope": "cn_a_equity",
            "baseline_id": "baseline_V10_1",
            "hypothesis": "path-backed runtime config should stay executable",
            "change_scope": {"modules_modified": ["runtime"]},
            "variants": [
                {
                    "name": "B0",
                    "request_overrides": {
                        "workbench_config": {
                            "asset_context": {
                                "moneyflow_overlay": {"enabled": True, "mode": "shadow"},
                            }
                        }
                    },
                }
            ],
            "windows": [{"key": "main", "role": "main", "start": "2023-07-03", "end": "2026-03-16"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "baseline_append"],
            "request_template": {
                "config_path": "backend/configs/pams_cn_pg.json",
                "workbench_config_path": str(runtime_cfg_path),
                "enable_multifactor_rank": True,
                "max_positions": 10,
            },
        }
    )

    payload = study_runner.build_execution_plan(study)[0]["request_payload"]
    assert payload["workbench_config"]["universe"]["start"] == "2023-07-03"
    assert payload["workbench_config"]["universe"]["end"] == "2026-03-16"
    assert payload["workbench_config"]["asset_context"]["moneyflow_overlay"]["mode"] == "shadow"


def test_build_execution_plan_can_merge_window_runtime_config_with_variant_overlay_mode(tmp_path: Path, monkeypatch) -> None:
    runtime_base_cfg = tmp_path / "research" / "studies" / "v10" / "configs" / "moneyflow_monthly_shadow_s1" / "1226_base.json"
    runtime_base_cfg.parent.mkdir(parents=True, exist_ok=True)
    runtime_base_cfg.write_text(
        json.dumps(
            {
                "db": {},
                "schema_mapping": {},
                "universe": {"benchmark": "000300.SH"},
                "asset_context": {
                    "moneyflow_overlay": {
                        "factor_snapshot_path": "outputs/studies/factors/moneyflow_factor_real_mainline_s2/1226/A_H20_CONTROL/machine/factor_snapshot.csv",
                        "score_source": "moneyflow_factor_real_mainline_s2:A_H20_CONTROL:1226",
                        "source_kind": "daily_factor_snapshot",
                        "factor_id": "monthly_divergence_rate",
                        "score_field": "rank_value",
                        "available_column": "availability_flag",
                        "lower_is_better": False,
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    default_runtime_cfg = tmp_path / "backend" / "configs" / "pams_cn_pg.json"
    default_runtime_cfg.parent.mkdir(parents=True, exist_ok=True)
    default_runtime_cfg.write_text(json.dumps({"db": {}, "schema_mapping": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(study_runner, "_repo_root", lambda: tmp_path)
    study = validate_study_payload(
        {
            "study_id": "v10/demo_moneyflow_shadow",
            "title": "Demo Moneyflow Shadow",
            "asset_scope": "cn_a_equity",
            "baseline_id": "baseline_V10_1",
            "hypothesis": "window-level source path plus variant-level overlay mode should compose cleanly",
            "change_scope": {"modules_modified": ["asset_context.moneyflow_overlay"]},
            "variants": [
                {
                    "name": "BULL_ONLY_TIEBREAK",
                    "request_overrides": {
                        "runtime_config_json": {
                            "asset_context": {
                                "moneyflow_overlay": {
                                    "enabled": True,
                                    "mode": "bull_only_tiebreak",
                                    "factor_role": "rank",
                                    "apply_layer": "candidate",
                                }
                            }
                        }
                    },
                }
            ],
            "windows": [
                {
                    "key": "1226",
                    "role": "audit",
                    "start": "2012-01-04",
                    "end": "2026-03-01",
                    "request_overrides": {"runtime_config_path": "research/studies/v10/configs/moneyflow_monthly_shadow_s1/1226_base.json"},
                }
            ],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "study_conclusion"],
            "request_template": {"config_path": "backend/configs/pams_cn_pg.json"},
        }
    )

    payload = study_runner.build_execution_plan(study)[0]["request_payload"]
    overlay_cfg = payload["runtime_config_json"]["asset_context"]["moneyflow_overlay"]
    assert payload["config_path"] == str(default_runtime_cfg.resolve())
    assert payload["runtime_config_path"] == str(runtime_base_cfg.resolve())
    assert overlay_cfg["factor_snapshot_path"] == "outputs/studies/factors/moneyflow_factor_real_mainline_s2/1226/A_H20_CONTROL/machine/factor_snapshot.csv"
    assert overlay_cfg["score_source"] == "moneyflow_factor_real_mainline_s2:A_H20_CONTROL:1226"
    assert overlay_cfg["mode"] == "bull_only_tiebreak"
    assert overlay_cfg["source_kind"] == "daily_factor_snapshot"
    assert overlay_cfg["factor_id"] == "monthly_divergence_rate"
    assert overlay_cfg["enabled"] is True


def test_build_execution_plan_resolves_variant_override_config_path(tmp_path: Path, monkeypatch) -> None:
    runtime_cfg_path = tmp_path / "backend" / "configs" / "pams_cn_pg.json"
    runtime_cfg_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_cfg_path.write_text(json.dumps({"db": {}, "schema_mapping": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
    variant_cfg_path = tmp_path / "research" / "studies" / "v10" / "configs" / "demo.json"
    variant_cfg_path.parent.mkdir(parents=True, exist_ok=True)
    variant_cfg_path.write_text(json.dumps({"mode": "experiment"}, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(study_runner, "_repo_root", lambda: tmp_path)
    study = validate_study_payload(
        {
            "study_id": "v10/demo_variant_path",
            "title": "Demo Variant Path",
            "asset_scope": "cn_a_equity",
            "baseline_id": "baseline_V10_1",
            "hypothesis": "variant config_path should resolve from repo root",
            "change_scope": {"modules_modified": ["request_overrides.config_path"]},
            "variants": [
                {
                    "name": "B0",
                    "request_overrides": {"config_path": "research/studies/v10/configs/demo.json"},
                }
            ],
            "windows": [{"key": "main", "role": "main", "start": "2024-01-01", "end": "2024-02-01"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "study_conclusion"],
            "request_template": {"config_path": "backend/configs/pams_cn_pg.json"},
        }
    )

    payload = study_runner.build_execution_plan(study)[0]["request_payload"]
    assert payload["config_path"] == str(variant_cfg_path.resolve())


def test_run_study_delegates_to_runtime_and_output_services(monkeypatch, tmp_path: Path) -> None:
    exp_dir = tmp_path / "outputs" / "experiments" / "exp_demo"
    exp_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        study_runner.experiment_runtime_access,
        "run_experiment_sync",
        lambda payload: {"exp_id": "exp_demo", "results_dir": str(exp_dir)},
    )
    monkeypatch.setattr(
        study_runner.experiment_runtime_access,
        "resolve_results_dir",
        lambda **kwargs: exp_dir,
    )
    monkeypatch.setattr(
        study_runner,
        "_load_run_meta",
        lambda exp_id, results_dir: {"status": "OK", "counters": {"orders": 3}},
    )
    monkeypatch.setattr(
        study_runner,
        "_load_config_snapshot",
        lambda exp_id, results_dir: {"universe": {"start": "2024-01-01", "end": "2024-02-01"}},
    )
    monkeypatch.setattr(
        study_runner.experiment_query_service,
        "get_experiment_surface",
        lambda exp_id: {
            "summary": {"exp_id": exp_id, "label": exp_id},
            "perf": {"cagr": 0.15, "max_drawdown": -0.08, "sharpe": 1.1, "trades": 5},
            "audit": {"status": "pass"},
        },
    )
    monkeypatch.setattr(
        study_runner.experiment_compare_service,
        "compare_experiment_to_baseline",
        lambda **kwargs: {"metrics": {"cagr": {"delta": 0.02}, "max_drawdown": {"delta": 0.01}}},
    )
    monkeypatch.setattr(
        study_runner.experiment_summary_service,
        "write_dual_output_bundle",
        lambda **kwargs: {"machine": {"nac": "machine/nac.json"}, "human": {"conclusion": "human/conclusion.md"}},
    )
    monkeypatch.setattr(
        study_runner.baseline_report_service,
        "append_experiment_to_baseline",
        lambda **kwargs: {"ledger": "machine/experiment_ledger.jsonl", "champion_updated": False},
    )
    captured_conclusion: dict[str, object] = {}

    def _append_conclusion(**kwargs):
        captured_conclusion.update(kwargs)
        return {"registry": "studies/conclusions/v10/demo/registry.jsonl"}

    monkeypatch.setattr(study_runner.study_conclusion_registry, "append_study_conclusion", _append_conclusion)

    result = study_runner.run_study(_study())
    run = result["runs"][0]
    assert run["exp_id"] == "exp_demo"
    assert run["verdict"]["status"] == "PASS"
    assert run["study_verdict"]["status"] == "confirmed"
    assert captured_conclusion["verdict"]["status"] == "confirmed"
    assert captured_conclusion["verdict"]["gate_status"] == "PASS"
    assert run["machine_outputs"]["nac"] == "machine/nac.json"
    assert run["baseline_outputs"] == {}
    assert run["conclusion_outputs"]["registry"] == "studies/conclusions/v10/demo/registry.jsonl"


def test_run_study_maps_weak_gate_pass_with_bad_compare_to_falsified(monkeypatch, tmp_path: Path) -> None:
    exp_dir = tmp_path / "outputs" / "experiments" / "exp_bad"
    exp_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        study_runner.experiment_runtime_access,
        "run_experiment_sync",
        lambda payload: {"exp_id": "exp_bad", "results_dir": str(exp_dir)},
    )
    monkeypatch.setattr(
        study_runner.experiment_runtime_access,
        "resolve_results_dir",
        lambda **kwargs: exp_dir,
    )
    monkeypatch.setattr(study_runner, "_load_run_meta", lambda exp_id, results_dir: {})
    monkeypatch.setattr(study_runner, "_load_config_snapshot", lambda exp_id, results_dir: {})
    monkeypatch.setattr(
        study_runner.experiment_query_service,
        "get_experiment_surface",
        lambda exp_id: {
            "perf": {"cagr": 0.15, "max_drawdown": -0.55, "sharpe": 0.05, "trades": 5},
            "audit": {},
        },
    )
    monkeypatch.setattr(
        study_runner.experiment_compare_service,
        "compare_experiment_to_baseline",
        lambda **kwargs: {
            "metrics": {
                "cagr": {"delta": -0.16},
                "sharpe": {"delta": -0.63},
                "max_drawdown": {"delta": -0.20},
            }
        },
    )
    monkeypatch.setattr(
        study_runner.experiment_summary_service,
        "write_dual_output_bundle",
        lambda **kwargs: {"machine": {}, "human": {}},
    )
    captured_conclusion: dict[str, object] = {}

    def _append_conclusion(**kwargs):
        captured_conclusion.update(kwargs)
        return {"registry": "studies/conclusions/v10/demo/registry.jsonl"}

    monkeypatch.setattr(study_runner.study_conclusion_registry, "append_study_conclusion", _append_conclusion)

    result = study_runner.run_study(_study())
    run = result["runs"][0]
    assert run["verdict"]["status"] == "PASS"
    assert run["study_verdict"]["status"] == "falsified"
    assert run["study_verdict"]["gate_status"] == "PASS"
    assert captured_conclusion["verdict"]["status"] == "falsified"
    assert captured_conclusion["verdict"]["gate_status"] == "PASS"


def test_run_study_can_opt_in_to_baseline_append(monkeypatch, tmp_path: Path) -> None:
    exp_dir = tmp_path / "outputs" / "experiments" / "exp_demo"
    exp_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        study_runner.experiment_runtime_access,
        "run_experiment_sync",
        lambda payload: {"exp_id": "exp_demo", "results_dir": str(exp_dir)},
    )
    monkeypatch.setattr(
        study_runner.experiment_runtime_access,
        "resolve_results_dir",
        lambda **kwargs: exp_dir,
    )
    monkeypatch.setattr(study_runner, "_load_run_meta", lambda exp_id, results_dir: {})
    monkeypatch.setattr(study_runner, "_load_config_snapshot", lambda exp_id, results_dir: {})
    monkeypatch.setattr(
        study_runner.experiment_query_service,
        "get_experiment_surface",
        lambda exp_id: {"perf": {"cagr": 0.15, "max_drawdown": -0.08, "sharpe": 1.1, "trades": 5}, "audit": {}},
    )
    monkeypatch.setattr(
        study_runner.experiment_compare_service,
        "compare_experiment_to_baseline",
        lambda **kwargs: {"metrics": {}, "baseline_source_of_truth": {"kind": "linked_experiment"}},
    )
    monkeypatch.setattr(
        study_runner.experiment_summary_service,
        "write_dual_output_bundle",
        lambda **kwargs: {"machine": {}, "human": {}},
    )
    monkeypatch.setattr(
        study_runner.study_conclusion_registry,
        "append_study_conclusion",
        lambda **kwargs: {"registry": "studies/conclusions/v10/demo/registry.jsonl"},
    )
    monkeypatch.setattr(
        study_runner.baseline_report_service,
        "append_experiment_to_baseline",
        lambda **kwargs: {"ledger": "machine/experiment_ledger.jsonl", "champion_updated": False},
    )

    result = study_runner.run_study(_study(), append_to_baseline=True)
    assert result["runs"][0]["baseline_outputs"]["ledger"] == "machine/experiment_ledger.jsonl"


def test_custom_runner_study_delegates_to_stock_lifecycle_fragility_surface(monkeypatch) -> None:
    study = validate_study_payload(
        {
            "study_id": "factors/stock_lifecycle_fragility_demo",
            "title": "Lifecycle Demo",
            "asset_scope": "cn_a_equity",
            "baseline_id": "baseline_V10_1",
            "hypothesis": "lifecycle fragility should explain exit risk",
            "change_scope": {"modules_modified": ["backend.research.stock_lifecycle_fragility_study"]},
            "variants": [{"name": "B0_EQUAL"}],
            "windows": [{"key": "1226", "role": "audit", "start": "2012-01-04", "end": "2026-03-20"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "baseline_append"],
            "request_template": {
                "runtime_config_path": "outputs/experiments/exp_20260409_052948616_a4c5/run_config.json",
                "config_path": "backend/configs/pams_cn_pg.json",
            },
            "metadata": {"runner_mode": "stock_lifecycle_fragility_surface"},
        }
    )
    captured: dict[str, object] = {}

    def _fake_runner(**kwargs):
        captured.update(kwargs)
        return {"status": "stock_lifecycle_fragility_only"}

    monkeypatch.setattr(study_runner, "run_stock_lifecycle_fragility_study", _fake_runner)
    result = study_runner.run_study(
        study,
        only_window_keys=["1226"],
        only_variant_names=["B0_EQUAL"],
        write_dual_output=False,
        append_to_baseline=False,
    )
    assert result["status"] == "stock_lifecycle_fragility_only"
    assert captured["study"] == study
    assert isinstance(captured["plan"], list) and len(captured["plan"]) == 1
