from __future__ import annotations

from pathlib import Path

from backend.research import study_loader, study_runner


def test_d7_post_entry_action_stock_ab_patches_only_d7_action_params() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_d7_post_entry_action_stock_ab_v1")
    plan = study_runner.build_execution_plan(study, only_window_keys=["1626"])

    assert len(plan) == 6
    assert {item["variant_name"] for item in plan} == {
        "B0_CURRENT_D7_HALF_EXIT",
        "D7_IMMEDIATE_50_CONTROL",
        "D7_IMMEDIATE_75",
        "D7_IMMEDIATE_100",
        "D7_DELAYED_5D_HALF_EXIT",
        "D7_WATCH_DAY10_HALF_EXIT",
    }

    b0 = next(item for item in plan if item["variant_name"] == "B0_CURRENT_D7_HALF_EXIT")
    base_payload = b0["request_payload"]
    assert base_payload["asset_scope"] == "cn_a_equity"
    assert Path(base_payload["runtime_config_path"]).as_posix().endswith(
        "outputs/baselines/baseline_V10_1/run_config.json"
    )
    assert base_payload["universe_mode"] == "HS300_ZZ500"

    expected = {
        "D7_IMMEDIATE_50_CONTROL": {
            "mfe_mae_confirmation_action": "exit",
            "mfe_mae_confirmation_lookahead_bars": 3,
            "mfe_mae_confirmation_exit_pct": 0.5,
        },
        "D7_IMMEDIATE_75": {
            "mfe_mae_confirmation_action": "exit",
            "mfe_mae_confirmation_lookahead_bars": 3,
            "mfe_mae_confirmation_exit_pct": 0.75,
        },
        "D7_IMMEDIATE_100": {
            "mfe_mae_confirmation_action": "exit",
            "mfe_mae_confirmation_lookahead_bars": 3,
            "mfe_mae_confirmation_exit_pct": 1.0,
        },
        "D7_DELAYED_5D_HALF_EXIT": {
            "mfe_mae_confirmation_action": "exit",
            "mfe_mae_confirmation_lookahead_bars": 5,
            "mfe_mae_confirmation_exit_pct": 0.5,
        },
        "D7_WATCH_DAY10_HALF_EXIT": {
            "mfe_mae_confirmation_action": "watch_day10",
            "mfe_mae_confirmation_lookahead_bars": 3,
            "mfe_mae_confirmation_exit_pct": 0.5,
            "mfe_mae_watch_review_bars": 10,
            "mfe_mae_watch_review_min_mfe_pct": 0.05,
            "mfe_mae_watch_review_max_current_return_pct": 0.05,
            "mfe_mae_watch_review_max_mae_pct": -0.08,
            "mfe_mae_watch_deep_mae_immediate_pct": -1.0,
        },
    }
    fixed_d7 = {
        "enable_mfe_mae_confirmation_exit": True,
        "mfe_mae_confirmation_scope": "high_chase",
        "mfe_mae_confirmation_min_mfe_pct": 0.02,
        "mfe_mae_confirmation_max_mae_pct": -0.08,
    }

    for variant, patch in expected.items():
        item = next(row for row in plan if row["variant_name"] == variant)
        payload = item["request_payload"]
        assert payload["asset_scope"] == base_payload["asset_scope"]
        assert payload["runtime_config_path"] == base_payload["runtime_config_path"]
        assert payload["universe_mode"] == base_payload["universe_mode"]
        assert "runner_params" not in payload

        params = dict(payload["runtime_config_json"]["strategy"]["params"])
        assert {key: params[key] for key in fixed_d7} == fixed_d7
        assert {key: params[key] for key in patch} == patch
