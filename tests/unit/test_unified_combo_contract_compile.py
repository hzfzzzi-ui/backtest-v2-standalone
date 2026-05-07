from __future__ import annotations

from backend.api.backtest_v2 import runner_config_bundle as bundle


def test_etf_phase1_promotion_skips_explicit_r1_standalone_semantics() -> None:
    semantic_cfg = {
        "asset_scope": "cn_etf",
        "universe": {
            "symbols": ["510050.SH", "588000.SH", "518880.SH", "511010.SH"],
            "price_adj": "none",
        },
        "governed_a_share": {
            "etf_beta": {
                "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                "local_policy_mode": "broad_based_rotation_mainline",
                "exposure_policy_family": "broad_based_standalone_mainline_v1",
            }
        },
    }

    assert bundle._etf_component_requires_phase1_promotion(semantic_cfg) is False


def test_etf_phase1_promotion_accepts_explicit_phase1_semantics() -> None:
    semantic_cfg = {
        "asset_scope": "cn_etf",
        "governed_a_share": {
            "etf_beta": {
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "local_policy_mode": "phase1_bucket_allocation",
            }
        },
    }

    assert bundle._etf_component_requires_phase1_promotion(semantic_cfg) is True


def test_unified_etf_phase1_promotion_can_be_forced_for_explicit_r1_semantics() -> None:
    semantic_cfg = {
        "asset_scope": "cn_etf",
        "governed_a_share": {
            "etf_beta": {
                "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                "local_policy_mode": "broad_based_rotation_mainline",
                "exposure_policy_family": "broad_based_standalone_mainline_v1",
            }
        },
    }

    assert bundle._should_promote_etf_component_to_formal_v1(
        unified_runtime_seed={"etf_component_promotion_mode": "formal_phase1"},
        semantic_cfg=semantic_cfg,
    ) is True


def test_unified_etf_source_truth_marks_explicit_r1_semantics_do_not_promote() -> None:
    semantic_cfg = {
        "asset_scope": "cn_etf",
        "governed_a_share": {
            "etf_beta": {
                "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                "strategy_role": "governed_broad_based_standalone_mainline",
                "local_policy_mode": "broad_based_rotation_mainline",
                "governor_boundary_mode": "consume_governor_state_and_budget",
            }
        },
    }

    source_truth = bundle._resolve_unified_etf_component_source_truth(
        semantic_cfg=semantic_cfg,
        promoted=False,
    )

    assert source_truth["formal_alignment_status"] == "do_not_promote"
    assert source_truth["source_entry_type"] == "cn_etf_broad_based_standalone_mainline_entry"
    assert source_truth["local_policy_mode"] == "broad_based_rotation_mainline"


def test_component_execution_overrides_derive_ranking_from_semantic_config() -> None:
    overrides = bundle._component_execution_overrides(
        semantic_cfg={
            "signal_generation": {
                "ranking": {
                    "score_source_mode": "residual_only",
                    "mf_topk": 10,
                }
            }
        },
        runtime_cfg=None,
        existing_overrides=None,
    )

    assert overrides["enable_multifactor_rank"] is True
    assert overrides["mf_topk"] == 10


def test_component_execution_overrides_can_disable_rank_derivation_for_etf() -> None:
    overrides = bundle._component_execution_overrides(
        semantic_cfg={
            "signal_generation": {
                "ranking": {
                    "score_source_mode": "residual_only",
                    "mf_topk": 10,
                }
            }
        },
        runtime_cfg={
            "strategy": {
                "params": {
                    "ranking_mode": "residual_only",
                    "enable_residual_ranking": True,
                }
            }
        },
        existing_overrides=None,
        allow_rank_derivation=False,
    )

    assert overrides == {}
