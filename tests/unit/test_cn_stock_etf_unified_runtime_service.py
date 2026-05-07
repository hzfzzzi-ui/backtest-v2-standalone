from __future__ import annotations

import pandas as pd

from backend.core.services import cn_stock_etf_unified_runtime_service as service


def test_resolve_unified_runtime_component_inputs_accepts_execution_contract_only() -> None:
    unified_runtime = {
        "execution_contract": {
            "contract_version": "backtest_execution_contract@1",
            "contract_type": "unified_combo",
            "asset_scope": "cn_a_multi_sleeve",
            "components": {
                "stock_component": {
                    "asset_scope": "cn_a_equity",
                    "weight": 0.6,
                    "runtime_config": {
                        "asset_scope": "cn_a_equity",
                        "universe": {"price_adj": "hfq"},
                    },
                    "execution_overrides": {
                        "enable_multifactor_rank": True,
                        "mf_topk": 10,
                    },
                },
                "etf_component": {
                    "asset_scope": "cn_etf",
                    "weight": 0.4,
                    "runtime_config": {
                        "asset_scope": "cn_etf",
                        "universe": {"price_adj": "none"},
                    },
                    "execution_overrides": {
                        "max_positions": 2,
                    },
                },
            },
        }
    }

    resolved = service._resolve_unified_runtime_component_inputs(
        unified_runtime=unified_runtime,
        combo_context={},
    )

    assert resolved["component_source_contract"] == {}
    assert resolved["stock_semantic_cfg"] is None
    assert resolved["etf_semantic_cfg"] is None
    assert resolved["stock_runtime_cfg"]["universe"]["price_adj"] == "hfq"
    assert resolved["etf_runtime_cfg"]["universe"]["price_adj"] == "none"
    assert resolved["stock_execution_overrides"]["enable_multifactor_rank"] is True
    assert resolved["stock_execution_overrides"]["mf_topk"] == 10
    assert resolved["etf_execution_overrides"]["max_positions"] == 2
    assert resolved["stock_asset_scope"] == "cn_a_equity"
    assert resolved["etf_asset_scope"] == "cn_etf"
    assert resolved["stock_weight_from_execution"] == 0.6
    assert resolved["etf_weight_from_execution"] == 0.4


def test_resolve_unified_runtime_component_inputs_accepts_legacy_compile_input_only() -> None:
    combo_context = {
        "component_source_contract": {
            "contract_version": "unified_combo_component_source_contract@1",
            "components": {
                "stock_component": {
                    "asset_scope": "cn_a_equity",
                    "compile_input": {
                        "semantic_config": {"asset_scope": "cn_a_equity"},
                        "runtime_config": {
                            "asset_scope": "cn_a_equity",
                            "universe": {"price_adj": "hfq"},
                        },
                    },
                },
                "etf_component": {
                    "asset_scope": "cn_etf",
                    "compile_input": {
                        "semantic_config": {"asset_scope": "cn_etf"},
                        "runtime_config": {
                            "asset_scope": "cn_etf",
                            "universe": {"price_adj": "none"},
                        },
                    },
                },
            },
        }
    }

    resolved = service._resolve_unified_runtime_component_inputs(
        unified_runtime={},
        combo_context=combo_context,
    )

    assert resolved["stock_semantic_cfg"]["asset_scope"] == "cn_a_equity"
    assert resolved["etf_semantic_cfg"]["asset_scope"] == "cn_etf"
    assert resolved["stock_runtime_cfg"]["universe"]["price_adj"] == "hfq"
    assert resolved["etf_runtime_cfg"]["universe"]["price_adj"] == "none"
    assert resolved["stock_execution_overrides"] == {}
    assert resolved["etf_execution_overrides"] == {}
    assert resolved["stock_asset_scope"] == "cn_a_equity"
    assert resolved["etf_asset_scope"] == "cn_etf"
    assert resolved["stock_weight_from_execution"] is None
    assert resolved["etf_weight_from_execution"] is None


def test_component_execution_overrides_fallback_derives_multifactor_rank_from_runtime_config() -> None:
    overrides = service._component_execution_overrides_for_request(
        explicit_overrides={},
        runtime_cfg={
            "asset_scope": "cn_a_equity",
            "strategy": {
                "params": {
                    "ranking_mode": "residual_only",
                    "enable_residual_ranking": True,
                }
            },
        },
    )

    assert overrides["enable_multifactor_rank"] is True


def test_build_combo_governed_snapshot_reads_latest_component_actual_role_exposures(tmp_path) -> None:
    stock_dir = tmp_path / "stock_component"
    stock_dir.mkdir(parents=True, exist_ok=True)
    etf_dir = tmp_path / "etf_component"
    etf_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"date": "2026-03-20", "gross_exposure": 0.35},
        ]
    ).to_csv(stock_dir / service.ARTIFACT_FILENAMES["daily"], index=False)
    pd.DataFrame(
        [
            {
                "date": "2026-03-20",
                "gross_exposure": 0.12,
                "etf_actual_exposure": 0.12,
                "etf_actual_risk_exposure": 0.12,
                "etf_actual_fallback_exposure": 0.0,
                "etf_actual_other_exposure": 0.0,
                "etf_actual_core_exposure": 0.04,
                "etf_actual_defense_exposure": 0.08,
            },
        ]
    ).to_csv(etf_dir / service.ARTIFACT_FILENAMES["daily"], index=False)

    snapshot = service._build_combo_governed_snapshot(
        stock_run_meta={
            "governed_snapshot": {
                "total_exposure_cap": 0.6,
                "sleeve_budgets": {"cn_stock_trend_alpha_core": {"selected_count": 1}},
            }
        },
        etf_run_meta={
            "governed_snapshot": {
                "total_exposure_cap": 0.2,
                "sleeve_budgets": {"cn_etf_beta": {"selected_count": 2}},
            }
        },
        weights={"cn_stock_trend_alpha_core": 0.0, "cn_etf_beta": 1.0},
        combo_regime={
            "base_state": "RISK_OFF",
            "effective_state": "RISK_OFF",
            "coarse_state": "RISK_OFF",
            "effective_coarse_state": "RISK_OFF",
            "reason_codes": [],
            "manual_override": {},
        },
        account_budget_control={"enabled": True, "resolved_source": "account_state_budget_map"},
        stock_results_dir=stock_dir,
        etf_results_dir=etf_dir,
    )

    etf_payload = snapshot["sleeve_budgets"]["cn_etf_beta"]
    assert etf_payload["actual_exposure"] == 0.12
    assert etf_payload["actual_risk_exposure"] == 0.12
    assert etf_payload["actual_core_exposure"] == 0.04
    assert etf_payload["actual_defense_exposure"] == 0.08
