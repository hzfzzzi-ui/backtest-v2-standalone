from __future__ import annotations

import json
import pandas as pd
import pytest

from backend.api.backtest_v2 import runner_impl
from backend.api.shared.paths import bt_root
from backend.core.tools import baseline_access
from backend.core.tools.experiment_runner import _project_trade_csv_schema


def _multi_alpha_config() -> dict:
    return {
        "mode": "experiment",
        "initial_capital": 1000000,
        "universe_mode": "HS300_ZZ500",
        "industries": [],
        "universe": {
            "start": "2016-03-01",
            "end": "2026-03-01",
            "benchmark": "000300.SH",
            "symbols": [],
            "limit": 0,
            "price_adj": "hfq",
            "filters": {
                "exclude_st": True,
                "exclude_suspended": True,
                "min_list_days": 120,
                "min_avg_turnover_20d": 100000000,
                "price_min": 5,
                "price_max": 99999,
                "atr_pct_range": "0,100",
                "limit_rule": "ignore",
            },
        },
        "signal_generation": {
            "enabled": True,
            "modules": [
                {"name": "breakout_55", "alpha_id": "breakout_55", "family": "trend"},
                {"name": "rsi_reversal", "alpha_id": "rsi_rev_6_20_80", "family": "mean_revert"},
                {
                    "name": "moneyflow_monthly",
                    "alpha_id": "moneyflow_monthly",
                    "family": "mean_revert",
                    "params": {"selection_path": "outputs/demo/monthly_selection.csv"},
                },
            ],
        },
        "signal_composition": {
            "enabled": True,
            "compose_mode": "REGIME_ROUTE",
            "same_symbol_policy": "PREFER_HIGHER_SCORE",
            "holding_ownership": "SOURCE_ONLY",
            "modules": [
                {"name": "breakout_55", "role": "trend", "priority": 100},
                {"name": "rsi_reversal", "role": "mean_revert", "priority": 80},
                {"name": "moneyflow_monthly", "role": "repair", "priority": 70},
            ],
            "regime_matrix": {
                "TREND_UP": ["breakout_55", "moneyflow_monthly"],
                "RANGE": ["breakout_55", "rsi_reversal", "moneyflow_monthly"],
            },
        },
        "position_risk": {
            "portfolio_mode": "hard_sleeve_budget",
        },
    }


def _breakout_config() -> dict:
    return {
        "mode": "experiment",
        "initial_capital": 1000000,
        "strategy_pack": "BREAKOUT_TREND",
        "universe_mode": "HS300_ZZ500",
        "industries": [],
        "universe": {
            "start": "2016-03-01",
            "end": "2026-03-01",
            "benchmark": "000300.SH",
            "symbols": [],
            "limit": 0,
            "price_adj": "hfq",
            "filters": {
                "exclude_st": True,
                "exclude_suspended": True,
                "min_list_days": 120,
                "min_avg_turnover_20d": 100000000,
                "price_min": 5,
                "price_max": 99999,
                "atr_pct_range": "0,100",
                "limit_rule": "ignore",
            },
        },
        "signal_generation": {
            "enabled": True,
            "strategy": "BREAKOUT_TREND",
            "breakout": {
                "breakout_window": 45,
                "enable_dual_breakout": False,
                "breakout_entry_buffer_pct": 0.0,
                "entry_confirm_mode": "none",
                "entry_delay_mode": "none",
            },
            "entry_filter": {
                "enable_entry_above_slow_ma": True,
                "enable_entry_slow_ma_slope": True,
                "entry_slope_lookback": 7,
            },
        },
        "exit_rules": {
            "enabled": True,
            "atr_stop": {"enabled": True, "k": 1.2},
            "trailing": {"enabled": True, "k": 3.0},
        },
        "position_risk": {
            "enabled": True,
            "max_positions": 12,
            "portfolio_mode": "profit_release",
        },
    }


def _stock_etf_unified_config() -> dict:
    payload = _breakout_config()
    payload["flow_script"] = {
        "script_id": "cn_stock_etf_v1",
        "description": "unified runtime template",
        "recommended_preset": "A股个股+ETFV1",
    }
    payload["governed_a_share"] = {
        "enabled": True,
        "stock_alpha_core": {
            "enabled": True,
            "sleeve_id": "cn_stock_trend_alpha_core",
        },
        "etf_beta": {
            "enabled": True,
            "sleeve_id": "cn_etf_beta",
            "phase1_scope_mode": "research_combo_only",
            "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
        },
    }
    return payload


def _assert_pure_unified_combo_component_runtime(runtime_cfg: dict, *, active_key: str, inactive_key: str) -> None:
    governed = dict(runtime_cfg.get("governed_a_share") or {})
    assert active_key in governed
    assert inactive_key not in governed


def test_compile_semantic_bundle_preserves_multi_alpha_runtime_payload() -> None:
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=_multi_alpha_config(),
        config_source="config_json",
        use_body_universe_fields=False,
    )
    runtime_cfg = compiled["runtime_config"]
    multi_alpha = runtime_cfg["strategy"]["params"]["multi_alpha"]
    assert runtime_cfg["strategy"]["name"] == "composite"
    assert runtime_cfg["strategy"]["params"]["portfolio_mode"] == "hard_sleeve_budget"
    assert [item["name"] for item in multi_alpha["signal_generation"]["modules"]] == [
        "breakout_55",
        "rsi_reversal",
        "moneyflow_monthly",
    ]
    assert multi_alpha["signal_composition"]["compose_mode"] == "REGIME_ROUTE"
    assert multi_alpha["signal_composition"]["same_symbol_policy"] == "PREFER_HIGHER_SCORE"


def test_compile_semantic_bundle_preserves_market_state_weight_overrides() -> None:
    payload = _multi_alpha_config()
    payload["signal_composition"]["market_state_weight_overrides"] = {
        "bull": {"breakout_55": 0.7, "moneyflow_monthly": 0.3},
        "bear": {"breakout_55": 0.3, "moneyflow_monthly": 0.7},
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    multi_alpha = compiled["runtime_config"]["strategy"]["params"]["multi_alpha"]
    overrides = multi_alpha["signal_composition"]["market_state_weight_overrides"]
    assert overrides == {
        "BULL": {"breakout_55": 0.7, "moneyflow_monthly": 0.3},
        "BEAR": {"breakout_55": 0.3, "moneyflow_monthly": 0.7},
    }


def test_compile_semantic_bundle_injects_breakout_entry_filters() -> None:
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=_breakout_config(),
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert compiled["runtime_config"]["strategy"]["name"] == "breakout_trend"
    assert params["enable_entry_above_slow_ma"] is True
    assert params["enable_entry_slow_ma_slope"] is True
    assert params["entry_slope_lookback"] == 7
    assert params["portfolio_mode"] == "profit_release"


def test_compile_semantic_bundle_preserves_data_role_in_runtime_config() -> None:
    payload = _breakout_config()
    payload["data_source"] = {"data_role": "v2_canonical"}

    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    runtime_cfg = compiled["runtime_config"]
    assert runtime_cfg["market_data_contract"] == "canonical_market"
    assert runtime_cfg["data_source"]["data_role"] == "v2_canonical"
    assert "pams_ohlcv_daily_v2" in runtime_cfg["schema_mapping"]
    assert runtime_cfg["schema_mapping"]["pams_ohlcv_daily_v2"]["date"] == "trade_date"


def test_compile_semantic_bundle_defaults_baseline_v10_1_to_canonical_market_contract() -> None:
    record = baseline_access.load_baseline_record("baseline_V10_1")
    if not isinstance(record, dict):
        pytest.skip("baseline_V10_1 fixture missing")
    semantic_cfg = dict(record.get("config_json") or {})

    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=semantic_cfg,
        config_source="baseline_fixture",
        use_body_universe_fields=False,
    )

    runtime_cfg = compiled["runtime_config"]
    assert runtime_cfg["market_data_contract"] == "canonical_market"
    assert runtime_cfg["data_source"]["stocks_table"] == "pams_ohlcv_daily_v2"
    assert runtime_cfg["universe"]["start"] == semantic_cfg["universe"]["start"]
    assert runtime_cfg["universe"]["end"] == semantic_cfg["universe"]["end"]
    assert "data_role" not in runtime_cfg["data_source"]




def test_compile_semantic_bundle_preserves_regime_engine_in_runtime_config() -> None:
    payload = _breakout_config()
    payload["regime_engine"] = {
        "engine": "market_regime_framework",
        "benchmark": "000300.SH",
        "trend_block": {"enabled": True, "long_ma_window": 200},
        "risk_block": {"enabled": True, "realized_vol_window": 20},
        "persistence": {"entry_confirm_bars": 3, "min_state_duration": 5},
        "fallback": {
            "on_feature_unavailable": "ma200_legacy",
            "required_blocks": ["trend_block", "risk_block"],
            "emit_feature_availability": True,
        },
    }

    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    runtime_cfg = compiled["runtime_config"]
    regime_engine = runtime_cfg["regime_engine"]
    assert regime_engine["engine"] == "market_regime_framework"
    assert regime_engine["benchmark"] == "000300.SH"
    assert regime_engine["fallback"]["on_feature_unavailable"] == "ma200_legacy"
    assert regime_engine["fallback"]["required_blocks"] == ["trend_block", "risk_block"]


def test_compile_semantic_bundle_preserves_blank_etf_benchmark_truth() -> None:
    payload = {
        "asset_scope": "cn_etf",
        "universe_mode": "CUSTOM",
        "universe": {
            "start": "2016-11-04",
            "end": "2026-03-20",
            "benchmark": "",
            "symbols": ["cn_etf_first_wave_core"],
            "price_adj": "none",
        },
        "data_source": {"stocks_table": "pams_cn_etf_daily", "data_role": "v1"},
        "regime_engine": {"engine": "market_regime_framework"},
    }

    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    runtime_cfg = compiled["runtime_config"]
    assert runtime_cfg["asset_context"]["asset_scope"] == "cn_etf"
    assert runtime_cfg["universe"]["benchmark"] == ""
    assert runtime_cfg["regime_engine"]["benchmark"] == ""


def test_compile_semantic_bundle_applies_top_level_combo_window_to_sleeve_runtime_configs() -> None:
    semantic_cfg = _stock_etf_unified_config()
    semantic_cfg["universe"] = dict(semantic_cfg.get("universe") or {})
    semantic_cfg["universe"]["start"] = "2012-01-04"
    semantic_cfg["universe"]["end"] = "2016-12-30"

    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=semantic_cfg,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    execution_contract = compiled["compiled_plan"]["unified_runtime"]["execution_contract"]
    stock_runtime = execution_contract["components"]["stock_component"]["runtime_config"]
    etf_runtime = execution_contract["components"]["etf_component"]["runtime_config"]

    assert stock_runtime["universe"]["start"] == "2012-01-04"
    assert stock_runtime["universe"]["end"] == "2016-12-30"
    assert stock_runtime["universe_mode"] == "HS300_ZZ500"
    assert stock_runtime["universe"]["membership_mode"] == "PIT_DYNAMIC"
    assert etf_runtime["universe"]["start"] == "2012-01-04"
    assert etf_runtime["universe"]["end"] == "2016-12-30"
    assert etf_runtime["universe_mode"] == "CUSTOM"
    _assert_pure_unified_combo_component_runtime(stock_runtime, active_key="stock_alpha_core", inactive_key="etf_beta")
    _assert_pure_unified_combo_component_runtime(etf_runtime, active_key="etf_beta", inactive_key="stock_alpha_core")


def test_compile_semantic_bundle_emits_execution_contract_for_unified_combo() -> None:
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=_stock_etf_unified_config(),
        config_source="config_json",
        use_body_universe_fields=False,
    )

    unified_runtime = dict(compiled.get("unified_runtime") or {})
    execution_contract = dict(unified_runtime.get("execution_contract") or {})
    assert execution_contract["contract_version"] == "backtest_execution_contract@1"
    assert execution_contract["contract_type"] == "unified_combo"
    assert execution_contract["asset_scope"] == "cn_a_multi_sleeve"
    assert execution_contract["combo_policy"]["benchmark"] == "CN_STOCK_ETF_50_50"
    assert execution_contract["components"]["stock_component"]["asset_scope"] == "cn_a_equity"
    assert execution_contract["components"]["etf_component"]["asset_scope"] == "cn_etf"
    _assert_pure_unified_combo_component_runtime(
        execution_contract["components"]["stock_component"]["runtime_config"],
        active_key="stock_alpha_core",
        inactive_key="etf_beta",
    )
    _assert_pure_unified_combo_component_runtime(
        execution_contract["components"]["etf_component"]["runtime_config"],
        active_key="etf_beta",
        inactive_key="stock_alpha_core",
    )
    source_contract = dict(unified_runtime.get("component_source_contract") or {})
    source_stock_compile_input = dict(
        (((source_contract.get("components") or {}).get("stock_component") or {}).get("compile_input") or {})
    )
    source_etf_compile_input = dict(
        (((source_contract.get("components") or {}).get("etf_component") or {}).get("compile_input") or {})
    )
    assert "runtime_config" not in source_stock_compile_input
    assert "runtime_config" not in source_etf_compile_input
    assert isinstance(source_stock_compile_input.get("semantic_config"), dict)
    assert isinstance(source_etf_compile_input.get("semantic_config"), dict)
    serialized = json.dumps(execution_contract, ensure_ascii=False)
    assert "source_kind" not in serialized
    assert "baseline_id" not in serialized
    assert "linked_exp_id" not in serialized
    assert "study_id" not in serialized


def test_compile_semantic_bundle_emits_etf_source_truth_from_component_semantic_identity() -> None:
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=_stock_etf_unified_config(),
        config_source="config_json",
        use_body_universe_fields=False,
    )

    source_contract = dict((compiled.get("unified_runtime") or {}).get("component_source_contract") or {})
    etf_component = dict(((source_contract.get("components") or {}).get("etf_component") or {}))
    etf_semantic_cfg = dict((((etf_component.get("compile_input") or {}).get("semantic_config")) or {}))
    etf_governed = dict((etf_semantic_cfg.get("governed_a_share") or {}).get("etf_beta") or {})

    assert etf_component["formal_alignment_status"] in {"formal_mainline", "research_only", "do_not_promote"}
    assert etf_component["source_entry_type"] == etf_governed["source_entry_type"]
    assert etf_component["strategy_role"] == etf_governed["strategy_role"]
    assert etf_component["local_policy_mode"] == etf_governed["local_policy_mode"]
    assert etf_component["governor_boundary_mode"] == etf_governed["governor_boundary_mode"]


def test_compile_semantic_bundle_can_force_formal_etf_promotion_for_unified_combo() -> None:
    semantic_cfg = _stock_etf_unified_config()
    semantic_cfg["unified_runtime"] = {
        "enabled": True,
        "etf_component_promotion_mode": "formal_phase1",
        "execution_contract": {
            "contract_version": "backtest_execution_contract@1",
            "contract_type": "unified_combo",
            "asset_scope": "cn_a_multi_sleeve",
            "components": {
                "etf_component": {
                    "asset_scope": "cn_etf",
                    "runtime_config": {
                        "asset_scope": "cn_etf",
                        "universe": {
                            "symbols": ["510050.SH", "512890.SH", "588000.SH", "518880.SH", "511010.SH"],
                            "price_adj": "hfq",
                        },
                        "governed_a_share": {
                            "enabled": True,
                            "etf_beta": {
                                "enabled": True,
                                "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                                "strategy_role": "governed_broad_based_standalone_mainline",
                                "local_policy_mode": "broad_based_rotation_mainline",
                                "governor_boundary_mode": "consume_governor_state_and_budget",
                                "core_beta_symbols": ["510050.SH", "510300.SH", "510500.SH", "512100.SH", "588000.SH"],
                                "limited_defense_candidates": ["511010.SH", "518880.SH"],
                            },
                        },
                    },
                },
            },
        },
    }

    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=semantic_cfg,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    source_contract = dict((compiled.get("unified_runtime") or {}).get("component_source_contract") or {})
    execution_contract = dict((compiled.get("compiled_plan") or {}).get("unified_runtime", {}).get("execution_contract") or {})
    etf_component = dict(((source_contract.get("components") or {}).get("etf_component") or {}))
    etf_semantic_cfg = dict((((etf_component.get("compile_input") or {}).get("semantic_config")) or {}))
    etf_governed = dict((etf_semantic_cfg.get("governed_a_share") or {}).get("etf_beta") or {})
    etf_symbols = set(etf_semantic_cfg.get("universe", {}).get("symbols") or [])
    etf_runtime_component = dict((execution_contract.get("components") or {}).get("etf_component") or {})
    etf_runtime_cfg = dict(etf_runtime_component.get("runtime_config") or {})
    etf_runtime_governed = dict((etf_runtime_cfg.get("governed_a_share") or {}).get("etf_beta") or {})
    etf_runtime_symbols = set((etf_runtime_cfg.get("universe") or {}).get("symbols") or [])

    assert etf_component["formal_alignment_status"] == "formal_mainline"
    assert etf_component["formal_etf_pool_version"] == "formal_etf_pool_v1"
    assert etf_component["source_entry_type"] == "cn_etf_phase1_allocation_entry"
    assert etf_component["strategy_role"] == "strategic_beta_stabilizer"
    assert etf_component["local_policy_mode"] == "phase1_bucket_allocation"
    assert etf_component["governor_boundary_mode"] == "consume_governor_sleeve_budget"
    assert etf_semantic_cfg["universe"]["price_adj"] == "none"
    assert etf_symbols == {"510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"}
    assert "518880.SH" not in etf_symbols
    assert "588000.SH" not in etf_symbols
    assert "512890.SH" not in etf_symbols
    assert etf_governed["source_entry_type"] == "cn_etf_phase1_allocation_entry"
    assert etf_governed["local_policy_mode"] == "phase1_bucket_allocation"
    assert etf_runtime_cfg["universe"]["price_adj"] == "none"
    assert etf_runtime_symbols == {"510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"}
    assert etf_runtime_governed["source_entry_type"] == "cn_etf_phase1_allocation_entry"
    assert etf_runtime_governed["strategy_role"] == "strategic_beta_stabilizer"
    assert etf_runtime_governed["local_policy_mode"] == "phase1_bucket_allocation"
    assert etf_runtime_governed["governor_boundary_mode"] == "consume_governor_sleeve_budget"


def test_compile_semantic_bundle_prefers_execution_contract_seed_for_unified_combo() -> None:
    semantic_cfg = _stock_etf_unified_config()
    semantic_cfg["unified_runtime"] = {
        "etf_component_promotion_mode": "replay_only",
        "component_source_contract": {
            "contract_version": "unified_combo_component_source_contract@1",
            "components": {
                "etf_component": {
                    "asset_scope": "cn_etf",
                    "compile_input": {
                        "semantic_config": {
                            "asset_scope": "cn_etf",
                            "universe": {
                                "symbols": ["510050.SH", "510300.SH", "510500.SH", "512100.SH", "512890.SH", "588000.SH", "518880.SH", "511010.SH"],
                                "price_adj": "hfq",
                            },
                            "governed_a_share": {
                                "enabled": True,
                                "etf_beta": {
                                    "enabled": True,
                                    "sleeve_id": "cn_etf_beta",
                                    "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                                    "strategy_role": "governed_broad_based_standalone_mainline",
                                    "local_policy_mode": "broad_based_rotation_mainline",
                                    "governor_boundary_mode": "consume_governor_state_and_budget",
                                    "exposure_policy_family": "broad_based_standalone_mainline_v1",
                                    "core_beta_symbols": ["510050.SH", "510300.SH", "510500.SH", "512100.SH", "512890.SH", "588000.SH"],
                                    "limited_defense_candidates": ["511010.SH", "518880.SH"],
                                },
                            },
                        },
                    },
                },
            },
        },
        "execution_contract": {
            "contract_version": "backtest_execution_contract@1",
            "contract_type": "unified_combo",
            "asset_scope": "cn_a_multi_sleeve",
            "combo_policy": {
                "mode": "account_budget_controlled_dynamic_mix",
                "benchmark": "CN_STOCK_ETF_EXECUTION",
            },
            "components": {
                "stock_component": {
                    "asset_scope": "cn_a_equity",
                    "weight": 0.7,
                    "runtime_config": {
                        "asset_scope": "cn_a_equity",
                        "universe": {"start": "2013-01-04", "end": "2015-12-31"},
                        "governed_a_share": {
                            "enabled": True,
                            "stock_alpha_core": {"enabled": True, "legacy_anchor": "baseline_V10.1"},
                            "etf_beta": {"enabled": True, "sleeve_id": "cn_etf_beta"},
                        },
                    },
                },
                    "etf_component": {
                        "asset_scope": "cn_etf",
                        "weight": 0.3,
                        "runtime_config": {
                            "asset_scope": "cn_etf",
                            "universe": {
                                "start": "2013-01-04",
                                "end": "2015-12-31",
                                "symbols": ["510050.SH", "510300.SH", "510500.SH", "512100.SH", "512890.SH", "588000.SH", "518880.SH", "511010.SH"],
                                "price_adj": "hfq",
                            },
                            "governed_a_share": {
                                "enabled": True,
                                "stock_alpha_core": {"enabled": True, "legacy_anchor": "baseline_V10.1"},
                                "etf_beta": {
                                    "enabled": True,
                                    "sleeve_id": "cn_etf_beta",
                                    "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                                    "strategy_role": "governed_broad_based_standalone_mainline",
                                    "local_policy_mode": "broad_based_rotation_mainline",
                                    "governor_boundary_mode": "consume_governor_state_and_budget",
                                    "exposure_policy_family": "broad_based_standalone_mainline_v1",
                                    "core_beta_symbols": ["510050.SH", "510300.SH", "510500.SH", "512100.SH", "512890.SH", "588000.SH"],
                                    "limited_defense_candidates": ["511010.SH", "518880.SH"],
                                },
                            },
                        },
                    },
                },
        }
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=semantic_cfg,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    execution_contract = dict(compiled["compiled_plan"]["unified_runtime"]["execution_contract"] or {})
    stock_component = dict(execution_contract["components"]["stock_component"] or {})
    etf_component = dict(execution_contract["components"]["etf_component"] or {})

    assert execution_contract["combo_policy"]["mode"] == "account_budget_controlled_dynamic_mix"
    assert execution_contract["combo_policy"]["benchmark"] == "CN_STOCK_ETF_EXECUTION"
    assert stock_component["weight"] == 0.7
    assert etf_component["weight"] == 0.3
    assert stock_component["runtime_config"]["universe"]["start"] == "2013-01-04"
    assert etf_component["runtime_config"]["universe"]["end"] == "2015-12-31"
    _assert_pure_unified_combo_component_runtime(
        stock_component["runtime_config"],
        active_key="stock_alpha_core",
        inactive_key="etf_beta",
    )
    _assert_pure_unified_combo_component_runtime(
        etf_component["runtime_config"],
        active_key="etf_beta",
        inactive_key="stock_alpha_core",
    )


def test_compile_semantic_bundle_accepts_stabilizer_symbol_contract_fields() -> None:
    payload = {
        "asset_scope": "cn_etf",
        "universe_mode": "CUSTOM",
        "universe": {
            "start": "2016-11-04",
            "end": "2026-03-20",
            "benchmark": "",
            "symbols": ["cn_etf_first_wave_core"],
            "price_adj": "none",
        },
        "data_source": {"stocks_table": "pams_cn_etf_daily", "data_role": "v1"},
        "governed_a_share": {
            "enabled": True,
            "etf_beta": {
                "enabled": True,
                "strategy_role": "strategic_beta_stabilizer",
                "local_policy_mode": "phase1_bucket_allocation",
                "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "core_accumulator_symbols": ["510300.SH", "510050.SH"],
                "tactical_satellite_symbols": ["510500.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "symbol_role_map": {
                    "510300.SH": "core_accumulator",
                    "510050.SH": "core_accumulator",
                    "510500.SH": "tactical_satellite",
                    "512100.SH": "tactical_satellite",
                    "511010.SH": "limited_defense",
                },
            },
        },
    }

    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    etf_beta = compiled["runtime_config"]["governed_a_share"]["etf_beta"]
    assert etf_beta["strategy_role"] == "strategic_beta_stabilizer"
    assert etf_beta["core_accumulator_symbols"] == ["510300.SH", "510050.SH"]
    assert etf_beta["tactical_satellite_symbols"] == ["510500.SH", "512100.SH"]
    assert etf_beta["symbol_role_map"]["511010.SH"] == "limited_defense"


def test_compile_semantic_bundle_preserves_turnover_rate_filter_fields() -> None:
    payload = _breakout_config()
    payload["universe"]["filters"]["min_avg_turnover_rate_20d"] = 1.1
    payload["universe"]["filters"]["turnover_rate_field"] = "turnover_rate_f"
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    runtime_filters = compiled["runtime_config"]["universe"]["filters"]
    assert runtime_filters["min_avg_turnover_rate_20d"] == 1.1
    assert runtime_filters["turnover_rate_field"] == "turnover_rate_f"


def test_compile_semantic_bundle_preserves_star_market_filter_field() -> None:
    payload = _breakout_config()
    payload["universe"]["filters"]["exclude_star_market"] = True
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    runtime_filters = compiled["runtime_config"]["universe"]["filters"]
    assert runtime_filters["exclude_star_market"] is True


def test_compile_semantic_bundle_emits_ranking_execution_overrides() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "momentum_top_pct": 0.1,
        "enable_strength_rank": True,
        "strength_ma": 120,
        "strength_top_k_mode": "FILL_TO_MAX",
        "enable_multifactor_rank": True,
        "mf_topk": 10,
        "mf_concentrate_scale": 1.25,
        "mf_rank_gate_mode": "BULL_ONLY",
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert params["momentum_top_pct"] == 0.1
    assert execution_overrides["enable_strength_rank"] is True
    assert execution_overrides["strength_ma"] == 120
    assert execution_overrides["strength_top_k_mode"] == "FILL_TO_MAX"
    assert execution_overrides["enable_multifactor_rank"] is True
    assert execution_overrides["mf_topk"] == 10
    assert execution_overrides["mf_concentrate_scale"] == 1.25
    assert execution_overrides["mf_rank_gate_mode"] == "BULL_ONLY"
    assert execution_overrides["momentum_top_pct"] == 0.1


def test_compile_semantic_bundle_maps_provider_final_score_source_mode() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "provider_final",
        "momentum_top_pct": 0.1,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert params["momentum_top_pct"] == 0.1
    assert params["enable_residual_ranking"] is True
    assert params["enable_sector_quality_ranking"] is True
    assert params["source_aware_residual_mode"] == "off"
    assert params["residual_weight"] == 0.5
    assert params["sector_weight"] == 0.3
    assert params["quality_weight"] == 0.2
    assert execution_overrides["enable_multifactor_rank"] is True
    assert "enable_strength_rank" not in execution_overrides


def test_compile_semantic_bundle_injects_conditional_tiebreak_refine_mode() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "residual_refine_mode": "conditional_tiebreak",
        "residual_refine_weight": 0.2,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_residual_ranking"] is True
    assert params["residual_refine_mode"] == "conditional_tiebreak"
    assert params["residual_refine_weight"] == 0.2


def test_compile_semantic_bundle_injects_industry_second_stage_refine_mode() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "residual_refine_mode": "industry_second_stage",
        "residual_refine_weight": 0.15,
        "industry_second_stage_min_industry_score": 0.85,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_residual_ranking"] is True
    assert params["residual_refine_mode"] == "industry_second_stage"
    assert params["residual_refine_weight"] == 0.15
    assert params["industry_second_stage_min_industry_score"] == 0.85


def test_compile_semantic_bundle_injects_leadership_then_residual_mode() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "leadership_then_residual",
        "residual_window": 40,
        "leadership_route_bucket_count": 3,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert params["ranking_mode"] == "leadership_then_residual"
    assert params["enable_residual_ranking"] is True
    assert params["leadership_route_bucket_count"] == 3
    assert execution_overrides["leadership_route_bucket_count"] == 3


def test_compile_semantic_bundle_injects_source_aware_residual_mode() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "source_aware_residual_mode": "pullback_only",
    }
    payload["signal_generation"]["breakout"]["enable_pullback_candidates"] = True
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_residual_ranking"] is True
    assert params["enable_pullback_candidates"] is True
    assert params["source_aware_residual_mode"] == "pullback_only"


def test_compile_semantic_bundle_injects_residual_split_weights() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "residual_window": 40,
        "residual_benchmark_weight": 0.7,
        "residual_industry_weight": 0.3,
        "industry_relative_mode": "industry_rank_pct",
        "industry_relative_regime_mode": "strong_risk_on",
        "residual_weight_regime_mode": "STRONG_RISK_ON",
        "residual_benchmark_weight_fallback": 0.5,
        "residual_industry_weight_fallback": 0.5,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert params["enable_residual_ranking"] is True
    assert params["residual_window"] == 40
    assert params["residual_benchmark_weight"] == 0.7
    assert params["residual_industry_weight"] == 0.3
    assert params["industry_relative_mode"] == "industry_rank_pct"
    assert params["industry_relative_regime_mode"] == "strong_risk_on"
    assert params["residual_weight_regime_mode"] == "STRONG_RISK_ON"
    assert params["residual_benchmark_weight_fallback"] == 0.5
    assert params["residual_industry_weight_fallback"] == 0.5
    assert execution_overrides["residual_benchmark_weight"] == 0.7
    assert execution_overrides["residual_industry_weight"] == 0.3
    assert execution_overrides["industry_relative_mode"] == "industry_rank_pct"
    assert execution_overrides["industry_relative_regime_mode"] == "strong_risk_on"
    assert execution_overrides["residual_weight_regime_mode"] == "STRONG_RISK_ON"
    assert execution_overrides["residual_benchmark_weight_fallback"] == 0.5
    assert execution_overrides["residual_industry_weight_fallback"] == 0.5


def test_compile_semantic_bundle_maps_residual_quality_score_source_mode() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_quality",
        "residual_weight": 0.8,
        "sector_weight": 0.0,
        "quality_weight": 0.2,
        "momentum_top_pct": 0.1,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert params["momentum_top_pct"] == 0.1
    assert params["enable_residual_ranking"] is True
    assert params["enable_sector_quality_ranking"] is True
    assert params["source_aware_residual_mode"] == "off"
    assert params["residual_weight"] == 0.8
    assert params["sector_weight"] == 0.0
    assert params["quality_weight"] == 0.2
    assert execution_overrides["enable_multifactor_rank"] is True
    assert execution_overrides["residual_weight"] == 0.8
    assert execution_overrides["sector_weight"] == 0.0
    assert execution_overrides["quality_weight"] == 0.2
    assert "enable_strength_rank" not in execution_overrides


def test_compile_semantic_bundle_injects_gated_dual_breakout_fields() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["breakout"].update(
        {
            "enable_dual_breakout": True,
            "breakout_window_short": 10,
            "breakout_window_long": 55,
            "dual_breakout_mode": "slow_gate_fast_trigger",
            "dual_breakout_gate_ma_window": 120,
            "dual_breakout_gate_slope_lookback": 10,
        }
    )
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_dual_breakout"] is True
    assert params["breakout_window_short"] == 10
    assert params["breakout_window_long"] == 55
    assert params["dual_breakout_mode"] == "slow_gate_fast_trigger"
    assert params["dual_breakout_gate_ma_window"] == 120
    assert params["dual_breakout_gate_slope_lookback"] == 10


def test_compile_semantic_bundle_injects_pullback_candidate_fields() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["breakout"].update(
        {
            "enable_pullback_candidates": True,
            "pullback_variant_mode": "pb_reclaim_ma20",
            "pullback_touch_lookback": 15,
            "pullback_reclaim_window": 4,
            "pullback_ma20_touch_band_pct": 0.02,
            "pullback_low_lookback": 11,
            "pullback_low_band_pct": 0.03,
            "pullback_box_window": 6,
            "pullback_box_range_pct_max": 0.07,
        }
    )
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_pullback_candidates"] is True
    assert params["pullback_variant_mode"] == "pb_reclaim_ma20"
    assert params["pullback_touch_lookback"] == 15
    assert params["pullback_reclaim_window"] == 4
    assert params["pullback_ma20_touch_band_pct"] == 0.02
    assert params["pullback_low_lookback"] == 11
    assert params["pullback_low_band_pct"] == 0.03
    assert params["pullback_box_window"] == 6
    assert params["pullback_box_range_pct_max"] == 0.07


def test_compile_semantic_bundle_injects_segmented_market_filter_fields() -> None:
    payload = _breakout_config()
    payload["position_risk"]["market_filter"] = {
        "enabled": True,
        "bull_multiplier": 1.5,
        "light_multiplier": 0.6,
        "trans_down_multiplier": 0.3,
        "trans_up_multiplier": 0.8,
        "bear_multiplier": 0.0,
        "ema_light_fast": 5,
        "ema_light_slow": 20,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    market_filter = compiled["runtime_config"]["market_filter"]
    assert market_filter["trans_down_multiplier"] == 0.3
    assert market_filter["trans_up_multiplier"] == 0.8
    assert market_filter["bear_multiplier"] == 0.0


def test_compile_semantic_bundle_injects_breadth_fields() -> None:
    payload = _breakout_config()
    payload["position_risk"]["breadth"] = {
        "enabled": True,
        "mode": "dynamic_maxpos",
        "score_type": "combo",
        "mapping_mode": "smooth",
        "min_positions": 6,
        "max_positions": 10,
        "gate_threshold": 0.45,
        "gate_quantile_window": 252,
        "gate_quantile_pct": 0.2,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    breadth = compiled["runtime_config"]["breadth"]
    assert breadth["enabled"] is True
    assert breadth["mode"] == "dynamic_maxpos"
    assert breadth["score_type"] == "combo"
    assert breadth["mapping_mode"] == "smooth"
    assert breadth["min_positions"] == 6
    assert breadth["max_positions"] == 10
    assert breadth["gate_threshold"] == 0.45
    assert breadth["gate_quantile_window"] == 252
    assert breadth["gate_quantile_pct"] == 0.2


def test_compile_semantic_bundle_injects_mf_rank_tilt_sizing_fields() -> None:
    payload = _breakout_config()
    payload["sizing"] = {
        "weight_mode": "mf_rank_tilt",
        "min_positions": 10,
        "tilt_strength": 0.15,
        "tilt_top_n": 3,
        "tilt_bottom_n": 2,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    sizing = compiled["runtime_config"]["sizing"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert sizing["weight_mode"] == "mf_rank_tilt"
    assert sizing["min_positions"] == 10
    assert sizing["tilt_strength"] == 0.15
    assert sizing["tilt_top_n"] == 3
    assert sizing["tilt_bottom_n"] == 2
    assert execution_overrides["weight_mode"] == "mf_rank_tilt"
    assert execution_overrides["tilt_strength"] == 0.15
    assert execution_overrides["tilt_top_n"] == 3
    assert execution_overrides["tilt_bottom_n"] == 2


def test_compile_semantic_bundle_injects_score_weighted_sizing_fields() -> None:
    payload = _breakout_config()
    payload["sizing"] = {
        "weight_mode": "score_weighted",
        "min_positions": 10,
        "score_weight_min_scale": 0.75,
        "score_weight_max_scale": 1.25,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    sizing = compiled["runtime_config"]["sizing"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert sizing["weight_mode"] == "score_weighted"
    assert sizing["min_positions"] == 10
    assert sizing["score_weight_min_scale"] == 0.75
    assert sizing["score_weight_max_scale"] == 1.25
    assert execution_overrides["weight_mode"] == "score_weighted"
    assert execution_overrides["score_weight_min_scale"] == 0.75
    assert execution_overrides["score_weight_max_scale"] == 1.25


def test_compile_semantic_bundle_injects_cash_aware_candidate_planner_fields() -> None:
    payload = _breakout_config()
    payload["sizing"] = {
        "candidate_plan_mode": "cash_aware",
        "cash_aware_search_top_n": 12,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    sizing = compiled["runtime_config"]["sizing"]
    execution_overrides = compiled["compiled_plan"]["execution_overrides"]
    assert sizing["candidate_plan_mode"] == "cash_aware"
    assert sizing["cash_aware_search_top_n"] == 12
    assert execution_overrides["candidate_plan_mode"] == "cash_aware"
    assert execution_overrides["cash_aware_search_top_n"] == 12


def test_compile_semantic_bundle_injects_risk_off_exit_flag() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "bear_only",
        "partial_pct": 0.5,
        "partial_mode": "first_trans_down_then_full",
        "partial_only_if_profitable": True,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_risk_off_exit"] is True
    assert params["risk_off_exit_mode"] == "bear_only"
    assert params["risk_off_exit_partial_pct"] == 0.5
    assert params["risk_off_exit_partial_mode"] == "first_trans_down_then_full"
    assert params["risk_off_exit_partial_only_if_profitable"] is True


def test_compile_semantic_bundle_injects_chandelier_segmented_trailing_fields() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.15,
        "segmented_trend_exit_mode": "chandelier",
        "segmented_mid_profit_pct": 0.15,
        "segmented_high_profit_pct": 0.25,
        "segmented_high_trail_k": 2.0,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    exit_cfg = compiled["runtime_config"]["exit"]
    assert params["segmented_trend_exit_mode"] == "chandelier"
    assert params["segmented_mid_profit_pct"] == 0.15
    assert params["segmented_high_profit_pct"] == 0.25
    assert params["segmented_high_trail_k"] == 2.0
    assert exit_cfg["segmented_trend_exit_mode"] == "chandelier"
    assert exit_cfg["segmented_mid_profit_pct"] == 0.15
    assert exit_cfg["segmented_high_profit_pct"] == 0.25
    assert exit_cfg["segmented_high_trail_k"] == 2.0


def test_compile_semantic_bundle_injects_trans_down_freeze_bear_exit_mode() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "trans_down_freeze_bear_exit",
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_risk_off_exit"] is True
    assert params["risk_off_exit_mode"] == "trans_down_freeze_bear_exit"


def test_compile_semantic_bundle_injects_trans_down_topk_bear_exit_mode() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "trans_down_topk_bear_exit",
        "trans_down_max_positions": 4,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_risk_off_exit"] is True
    assert params["risk_off_exit_mode"] == "trans_down_topk_bear_exit"
    assert params["risk_off_exit_trans_down_max_positions"] == 4


def test_compile_semantic_bundle_injects_trans_down_residual_floor_bear_exit_mode() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "trans_down_residual_floor_bear_exit",
        "trans_down_min_residual_score": 0.85,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_risk_off_exit"] is True
    assert params["risk_off_exit_mode"] == "trans_down_residual_floor_bear_exit"
    assert params["risk_off_exit_trans_down_min_residual_score"] == 0.85


def test_compile_semantic_bundle_injects_trans_down_residual_profit_floor_bear_exit_mode() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "trans_down_residual_profit_floor_bear_exit",
        "trans_down_min_residual_score": 0.85,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_risk_off_exit"] is True
    assert params["risk_off_exit_mode"] == "trans_down_residual_profit_floor_bear_exit"
    assert params["risk_off_exit_trans_down_min_residual_score"] == 0.85


def test_compile_semantic_bundle_injects_trans_down_residual_ma20_floor_bear_exit_mode() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["risk_off_exit"] = {
        "enabled": True,
        "mode": "trans_down_residual_ma20_floor_bear_exit",
        "trans_down_min_residual_score": 0.85,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_risk_off_exit"] is True
    assert params["risk_off_exit_mode"] == "trans_down_residual_ma20_floor_bear_exit"
    assert params["risk_off_exit_trans_down_min_residual_score"] == 0.85


def test_compile_semantic_bundle_injects_trailing_activate_profit_pct() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.08,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_atr_trail"] is True
    assert params["atr_trail_k"] == 3.0
    assert params["trailing_activate_profit_pct"] == 0.08
    assert compiled["runtime_config"]["exit"]["trailing_activate_profit_pct"] == 0.08


def test_compile_semantic_bundle_injects_pre_profit_breakout_failure_fields() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.15,
        "pre_profit_breakout_failure_enabled": True,
        "pre_profit_breakout_failure_max_bars": 10,
        "pre_profit_breakout_failure_atr_buffer_k": 0.5,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    exit_cfg = compiled["runtime_config"]["exit"]
    assert params["enable_pre_profit_breakout_failure_exit"] is True
    assert params["pre_profit_breakout_failure_max_bars"] == 10
    assert params["pre_profit_breakout_failure_atr_buffer_k"] == 0.5
    assert exit_cfg["enable_pre_profit_breakout_failure_exit"] is True
    assert exit_cfg["pre_profit_breakout_failure_max_bars"] == 10
    assert exit_cfg["pre_profit_breakout_failure_atr_buffer_k"] == 0.5


def test_compile_semantic_bundle_injects_profit_decay_exit_fields() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.15,
        "profit_decay_exit_enabled": True,
        "profit_decay_exit_profit_pct": 0.12,
        "profit_decay_exit_min_hold_bars": 8,
        "profit_decay_exit_residual_score_threshold": 0.35,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    exit_cfg = compiled["runtime_config"]["exit"]
    assert params["enable_profit_decay_exit"] is True
    assert params["profit_decay_exit_profit_pct"] == 0.12
    assert params["profit_decay_exit_min_hold_bars"] == 8
    assert params["profit_decay_exit_residual_score_threshold"] == 0.35
    assert exit_cfg["enable_profit_decay_exit"] is True
    assert exit_cfg["profit_decay_exit_profit_pct"] == 0.12
    assert exit_cfg["profit_decay_exit_min_hold_bars"] == 8
    assert exit_cfg["profit_decay_exit_residual_score_threshold"] == 0.35


def test_compile_semantic_bundle_injects_entry_gap_guard_fields() -> None:
    payload = _breakout_config()
    payload["signal_generation"]["breakout"]["entry_gap_guard_enabled"] = True
    payload["signal_generation"]["breakout"]["entry_gap_guard_pct"] = 0.04
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    assert params["enable_entry_gap_guard"] is True
    assert params["entry_gap_guard_pct"] == 0.04


def test_compile_semantic_bundle_injects_segmented_trend_exit_fields() -> None:
    payload = _breakout_config()
    payload["exit_rules"]["trailing"] = {
        "enabled": True,
        "k": 3.0,
        "activate_profit_pct": 0.15,
        "segmented_trend_exit_mode": "low10",
        "segmented_mid_profit_pct": 0.08,
        "segmented_high_profit_pct": 0.15,
        "segmented_high_trail_k": 2.5,
    }
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=payload,
        config_source="config_json",
        use_body_universe_fields=False,
    )

    params = compiled["runtime_config"]["strategy"]["params"]
    exit_cfg = compiled["runtime_config"]["exit"]
    assert params["segmented_trend_exit_mode"] == "low10"
    assert params["segmented_mid_profit_pct"] == 0.08
    assert params["segmented_high_profit_pct"] == 0.15
    assert params["segmented_high_trail_k"] == 2.5
    assert exit_cfg["segmented_trend_exit_mode"] == "low10"
    assert exit_cfg["segmented_mid_profit_pct"] == 0.08
    assert exit_cfg["segmented_high_profit_pct"] == 0.15
    assert exit_cfg["segmented_high_trail_k"] == 2.5


def test_compile_semantic_bundle_merges_request_level_blocks() -> None:
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=runner_impl.BacktestV2ExperimentRequest(
            signal_generation={"modules": [{"name": "breakout_55", "alpha_id": "breakout_55"}]},
            signal_composition={"compose_mode": "REGIME_ROUTE"},
        ),
        semantic_cfg={
            "mode": "experiment",
            "initial_capital": 1000000,
            "universe_mode": "HS300_ZZ500",
            "industries": [],
            "universe": {
                "start": "2016-03-01",
                "end": "2026-03-01",
                "benchmark": "000300.SH",
                "symbols": [],
                "limit": 0,
                "price_adj": "hfq",
            },
        },
        config_source="saved_config",
        use_body_universe_fields=False,
    )
    multi_alpha = compiled["runtime_config"]["strategy"]["params"]["multi_alpha"]
    assert [item["name"] for item in multi_alpha["signal_generation"]["modules"]] == ["breakout_55"]
    assert multi_alpha["signal_composition"]["compose_mode"] == "REGIME_ROUTE"


def test_compile_semantic_bundle_accepts_missing_body() -> None:
    compiled = runner_impl._compile_semantic_config_bundle(
        base_cfg=runner_impl._load_base_config(bt_root()),
        body=None,
        semantic_cfg=_breakout_config(),
        config_source="config_json",
        use_body_universe_fields=False,
    )

    runtime_cfg = compiled["runtime_config"]
    assert runtime_cfg["universe"]["start"] == "2016-03-01"
    assert runtime_cfg["universe"]["end"] == "2026-03-01"
    assert runtime_cfg["strategy"]["name"] == "breakout_trend"


def test_build_runtime_cfg_from_workbench_prefers_body_universe_fields_when_enabled() -> None:
    runtime_cfg = runner_impl._build_runtime_cfg_from_workbench(
        runner_impl._load_base_config(bt_root()),
        runner_impl.BacktestV2ExperimentRequest(
            start_date="2020-01-01",
            end_date="2020-12-31",
            benchmark="000905.SH",
            symbols=["sh600000", "sz000001"],
        ),
        _breakout_config(),
        use_body_universe_fields=True,
    )

    assert runtime_cfg["universe"]["start"] == "2020-01-01"
    assert runtime_cfg["universe"]["end"] == "2020-12-31"
    assert runtime_cfg["universe"]["benchmark"] == "000905.SH"
    assert runtime_cfg["universe"]["symbols"] == ["sh600000", "sz000001"]


def test_build_runtime_cfg_from_workbench_infers_governed_a_share_contract_for_breakout() -> None:
    runtime_cfg = runner_impl._build_runtime_cfg_from_workbench(
        runner_impl._load_base_config(bt_root()),
        runner_impl.BacktestV2ExperimentRequest(),
        _breakout_config(),
        use_body_universe_fields=False,
    )

    governed = dict(runtime_cfg.get("governed_a_share") or {})
    assert governed["system_id"] == "cn_a_governed_multi_sleeve_phase1"
    assert governed["stock_alpha_core"]["sleeve_id"] == "cn_stock_trend_alpha_core"
    assert governed["stock_alpha_core"]["legacy_anchor"] == "baseline_V10.1"
    assert governed["stock_alpha_core"]["budget_semantics"] == "consume_governor_sleeve_budget"
    assert governed["stock_alpha_core"]["total_budget_owner"] == "global_portfolio_governor"
    assert governed["etf_beta"]["core_beta_symbols"] == ["510300.SH", "510500.SH", "510050.SH", "512100.SH"]
    assert governed["etf_beta"]["limited_defense_candidates"] == ["511010.SH"]


def test_project_trade_csv_schema_keeps_source_and_exit_fields() -> None:
    projected = _project_trade_csv_schema(
        pd.DataFrame(
            [
                {
                    "date": "2026-03-02",
                    "symbol": "sh600000",
                    "side": "SELL",
                    "price": 10.0,
                    "qty": 100,
                    "reason_code": "EXIT",
                    "exit_owner": "global_risk_override",
                    "entry_alpha_id": "breakout_55",
                    "entry_sleeve_id": "trend",
                    "entry_reason_code": "BREAKOUT_HIGH",
                    "entry_date": "2026-02-20",
                }
            ]
        )
    )

    assert "exit_owner" in projected.columns
    assert "entry_alpha_id" in projected.columns
    assert "entry_sleeve_id" in projected.columns
    assert projected.loc[0, "exit_owner"] == "global_risk_override"
    assert projected.loc[0, "entry_alpha_id"] == "breakout_55"




