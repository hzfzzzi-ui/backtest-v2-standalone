from __future__ import annotations

from pathlib import Path

from backend.research import study_loader, study_runner
from backend.research import cn_stock_etf_expanded_pool_shadow_study as combo_shadow
from backend.research.study_definition import validate_study_payload


def test_expanded_pool_combo_study_dry_run_matrix_has_expected_controls() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_expanded_pool_shadow_v1")
    plan = study_runner.build_execution_plan(study)

    assert len(plan) == 15
    assert [variant.name for variant in study.variants] == [
        "CURRENT_FORMAL_COMBO_REPLAY",
        "FORMAL_POOL_ROTATION_CONTROL",
        "REALWORLD_POOL_V1",
        "INDUSTRY_THEME_POOL_V2",
        "STYLE_SMART_BETA_POOL_V2",
    ]
    assert [window.key for window in study.windows] == ["1626", "1217", "1226"]


def test_combo_shadow_payload_replaces_only_etf_component_and_patches_nested_windows() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_expanded_pool_shadow_v1")
    plan = study_runner.build_execution_plan(
        study,
        only_variant_names=["STYLE_SMART_BETA_POOL_V2"],
        only_window_keys=["1217"],
    )
    payload = combo_shadow.build_combo_shadow_request_payload(study, plan[0])
    config_json = payload["config_json"]
    unified_runtime = config_json["unified_runtime"]
    source_contract = unified_runtime["component_source_contract"]
    combo_context_source_contract = unified_runtime["combo_context"]["component_source_contract"]
    stock_component = source_contract["components"]["stock_component"]
    etf_component = source_contract["components"]["etf_component"]
    stock_semantic = stock_component["compile_input"]["semantic_config"]
    etf_semantic = etf_component["compile_input"]["semantic_config"]

    template_payload = combo_shadow._read_json(
        Path("outputs/baselines/CN_STOCK_ETF_FORMAL_V1/config.json").resolve()
    )
    template_source = combo_shadow._source_contract_from_config(template_payload["workbench_config"])

    assert payload["asset_scope"] == "cn_a_equity"
    assert "execution_contract" not in unified_runtime
    assert "execution_contract" not in unified_runtime["combo_context"]
    assert source_contract == combo_context_source_contract
    assert stock_component["source"] == template_source["components"]["stock_component"]["source"]
    assert unified_runtime["weights"] == {"cn_stock_trend_alpha_core": 0.5, "cn_etf_beta": 0.5}
    assert config_json["universe"]["start"] == "2012-01-04"
    assert config_json["universe"]["end"] == "2017-12-29"
    assert stock_semantic["universe"]["start"] == "2012-01-04"
    assert stock_semantic["universe"]["end"] == "2017-12-29"
    assert etf_semantic["universe"]["start"] == "2012-01-04"
    assert etf_semantic["universe"]["end"] == "2017-12-29"
    assert etf_semantic["universe"]["symbols"] == ["cn_etf_research_style_smart_beta_pool_v2"]
    assert etf_component["source"]["source_kind"] == "study_shadow"
    assert etf_component["source"]["study_id"] == "etf/cn_etf_research_style_smart_beta_pool_v2"
    assert etf_component["source"]["pool_version"] == "cn_etf_research_style_smart_beta_pool_v2"
    assert "runtime_config" not in etf_component["compile_input"]


def test_combo_shadow_runner_result_records_component_exp_ids(monkeypatch, tmp_path: Path) -> None:
    study = validate_study_payload(
        {
            "study_id": "cn_stock_etf/demo",
            "title": "Demo Combo",
            "asset_scope": "cn_a_equity",
            "baseline_id": "CN_STOCK_ETF_FORMAL_V1",
            "hypothesis": "demo",
            "change_scope": {"modules_modified": ["demo"]},
            "variants": [{"name": "STYLE_SMART_BETA_POOL_V2"}],
            "windows": [{"key": "1226", "role": "audit", "start": "2012-01-04", "end": "2026-05-08"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "study_conclusion"],
        }
    )
    exp_dir = tmp_path / "outputs" / "experiments" / "exp_combo"
    exp_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        combo_shadow,
        "build_combo_shadow_request_payload",
        lambda study, item: {"study_meta": {"etf_source": {"pool_version": "demo_pool"}}},
    )
    monkeypatch.setattr(
        combo_shadow.experiment_runtime_access,
        "run_experiment_sync",
        lambda payload: {"exp_id": "exp_combo", "results_dir": str(exp_dir)},
    )
    monkeypatch.setattr(
        combo_shadow.experiment_runtime_access,
        "resolve_results_dir",
        lambda **kwargs: exp_dir,
    )
    monkeypatch.setattr(
        combo_shadow.experiment_query_service,
        "get_experiment_surface",
        lambda exp_id: {"perf": {"cagr": 0.12, "max_drawdown": -0.2, "sharpe": 0.8, "trades": 10}, "audit": {}},
    )
    monkeypatch.setattr(
        combo_shadow.experiment_compare_service,
        "compare_experiment_to_baseline",
        lambda **kwargs: {"metrics": {"cagr": {"delta": 0.01}}},
    )
    monkeypatch.setattr(
        combo_shadow,
        "_load_run_meta",
        lambda exp_id, results_dir: {
            "dependencies": {
                "component_runs": {
                    "stock_alpha_core": {"exp_id": "exp_stock"},
                    "etf_beta": {"exp_id": "exp_etf"},
                }
            }
        },
    )
    monkeypatch.setattr(combo_shadow, "_load_config_snapshot", lambda exp_id, results_dir: {})
    monkeypatch.setattr(
        combo_shadow.experiment_summary_service,
        "write_dual_output_bundle",
        lambda **kwargs: {"machine": {"perf": "machine/perf.json"}, "human": {"summary": "human/summary.md"}},
    )
    monkeypatch.setattr(combo_shadow, "_study_root", lambda study: tmp_path / "outputs" / "studies" / "cn_stock_etf" / "demo")

    result = combo_shadow.run_cn_stock_etf_expanded_pool_shadow_study(
        study=study,
        plan=[
            {
                "window_key": "1226",
                "window_role": "audit",
                "variant_name": "STYLE_SMART_BETA_POOL_V2",
                "request_payload": {},
            }
        ],
    )

    run = result["runs"][0]
    assert run["research_only"] is True
    assert run["exp_id"] == "exp_combo"
    assert run["component_exp_ids"] == {"stock_exp_id": "exp_stock", "etf_exp_id": "exp_etf"}
    assert run["baseline_outputs"] == {}
    assert run["machine_outputs"]["perf"] == "machine/perf.json"


def test_study_runner_delegates_to_combo_shadow_runner(monkeypatch) -> None:
    study = validate_study_payload(
        {
            "study_id": "cn_stock_etf/demo",
            "title": "Demo Combo",
            "asset_scope": "cn_a_equity",
            "baseline_id": "CN_STOCK_ETF_FORMAL_V1",
            "hypothesis": "demo",
            "change_scope": {"modules_modified": ["demo"]},
            "variants": [{"name": "B0"}],
            "windows": [{"key": "1226", "role": "audit", "start": "2012-01-04", "end": "2026-05-08"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "study_conclusion"],
            "metadata": {"runner_mode": "cn_stock_etf_expanded_pool_shadow"},
        }
    )
    captured: dict[str, object] = {}

    def _fake_runner(**kwargs):
        captured.update(kwargs)
        return {"status": "combo_shadow_only"}

    monkeypatch.setattr(study_runner, "run_cn_stock_etf_expanded_pool_shadow_study", _fake_runner)
    result = study_runner.run_study(study, only_window_keys=["1226"], only_variant_names=["B0"])

    assert result["status"] == "combo_shadow_only"
    assert captured["study"] == study
    assert isinstance(captured["plan"], list) and len(captured["plan"]) == 1
