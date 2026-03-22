from __future__ import annotations

from backend.api.backtest_v2 import runner_impl
from backend.core.services import experiment_runtime_service as service
from backend.core.tools import experiment_runner as runner


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


def test_config_json_position_risk_max_positions_becomes_execution_override(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_experiment(base_cfg_path, preset="single", overrides=None, progress_hook=None):
        captured["base_cfg_path"] = base_cfg_path
        captured["preset"] = preset
        captured["overrides"] = dict(overrides or {})
        return {
            "exp_id": "exp_test",
            "results_dir": "",
            "status": "OK",
        }

    monkeypatch.setattr(runner, "run_experiment", _fake_run_experiment)
    monkeypatch.setattr(runner_impl, "_attach_run_profile_summary", lambda result: None)
    monkeypatch.setattr(runner_impl, "_write_config_snapshots", lambda **kwargs: None)
    monkeypatch.setattr(service, "stabilize_experiment_output", lambda **kwargs: dict(kwargs["result"]))

    body = runner_impl.BacktestV2ExperimentRequest(
        config_json=_breakout_config(),
        fast_mode=True,
    )
    result = service.run_experiment_request_body(body)

    overrides = dict(captured["overrides"] or {})
    assert overrides["max_positions"] == 12
    assert overrides["fast_mode"] is True
    assert result["exp_id"] == "exp_test"
    assert result["experiment_id"] == "exp_test"


def test_config_json_ranking_fields_become_execution_overrides(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_experiment(base_cfg_path, preset="single", overrides=None, progress_hook=None):
        captured["base_cfg_path"] = base_cfg_path
        captured["preset"] = preset
        captured["overrides"] = dict(overrides or {})
        return {
            "exp_id": "exp_test_rank",
            "results_dir": "",
            "status": "OK",
        }

    monkeypatch.setattr(runner, "run_experiment", _fake_run_experiment)
    monkeypatch.setattr(runner_impl, "_attach_run_profile_summary", lambda result: None)
    monkeypatch.setattr(runner_impl, "_write_config_snapshots", lambda **kwargs: None)
    monkeypatch.setattr(service, "stabilize_experiment_output", lambda **kwargs: dict(kwargs["result"]))

    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "momentum_top_pct": 0.1,
        "enable_strength_rank": True,
        "strength_ma": 120,
        "strength_top_k_mode": "FILL_TO_MAX",
        "enable_multifactor_rank": True,
        "mf_topk": 10,
        "mf_concentrate_scale": 1.25,
        "mf_rank_gate_mode": "TRANS_UP_OR_BULL",
    }
    body = runner_impl.BacktestV2ExperimentRequest(
        config_json=payload,
        fast_mode=True,
    )
    result = service.run_experiment_request_body(body)

    overrides = dict(captured["overrides"] or {})
    assert overrides["enable_strength_rank"] is True
    assert overrides["strength_ma"] == 120
    assert overrides["strength_top_k_mode"] == "FILL_TO_MAX"
    assert overrides["enable_multifactor_rank"] is True
    assert overrides["mf_topk"] == 10
    assert overrides["mf_concentrate_scale"] == 1.25
    assert overrides["mf_rank_gate_mode"] == "TRANS_UP_OR_BULL"
    assert overrides["momentum_top_pct"] == 0.1
    assert overrides["fast_mode"] is True
    assert result["exp_id"] == "exp_test_rank"
    assert result["experiment_id"] == "exp_test_rank"


def test_config_json_provider_final_score_source_mode_enables_multifactor_rank(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_experiment(base_cfg_path, preset="single", overrides=None, progress_hook=None):
        captured["base_cfg_path"] = base_cfg_path
        captured["preset"] = preset
        captured["overrides"] = dict(overrides or {})
        return {
            "exp_id": "exp_test_rank_mode",
            "results_dir": "",
            "status": "OK",
        }

    monkeypatch.setattr(runner, "run_experiment", _fake_run_experiment)
    monkeypatch.setattr(runner_impl, "_attach_run_profile_summary", lambda result: None)
    monkeypatch.setattr(runner_impl, "_write_config_snapshots", lambda **kwargs: None)
    monkeypatch.setattr(service, "stabilize_experiment_output", lambda **kwargs: dict(kwargs["result"]))

    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "provider_final",
        "momentum_top_pct": 0.1,
    }
    body = runner_impl.BacktestV2ExperimentRequest(
        config_json=payload,
        fast_mode=True,
    )
    result = service.run_experiment_request_body(body)

    overrides = dict(captured["overrides"] or {})
    assert overrides["enable_multifactor_rank"] is True
    assert overrides["momentum_top_pct"] == 0.1
    assert "enable_strength_rank" not in overrides
    assert overrides["fast_mode"] is True
    assert result["exp_id"] == "exp_test_rank_mode"
    assert result["experiment_id"] == "exp_test_rank_mode"


def test_config_json_residual_quality_score_source_mode_carries_weight_overrides(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_experiment(base_cfg_path, preset="single", overrides=None, progress_hook=None):
        captured["base_cfg_path"] = base_cfg_path
        captured["preset"] = preset
        captured["overrides"] = dict(overrides or {})
        return {
            "exp_id": "exp_test_residual_quality",
            "results_dir": "",
            "status": "OK",
        }

    monkeypatch.setattr(runner, "run_experiment", _fake_run_experiment)
    monkeypatch.setattr(runner_impl, "_attach_run_profile_summary", lambda result: None)
    monkeypatch.setattr(runner_impl, "_write_config_snapshots", lambda **kwargs: None)
    monkeypatch.setattr(service, "stabilize_experiment_output", lambda **kwargs: dict(kwargs["result"]))

    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_quality",
        "residual_weight": 0.7,
        "sector_weight": 0.0,
        "quality_weight": 0.3,
        "momentum_top_pct": 0.1,
    }
    body = runner_impl.BacktestV2ExperimentRequest(
        config_json=payload,
        fast_mode=True,
    )
    result = service.run_experiment_request_body(body)

    overrides = dict(captured["overrides"] or {})
    assert overrides["enable_multifactor_rank"] is True
    assert overrides["residual_weight"] == 0.7
    assert overrides["sector_weight"] == 0.0
    assert overrides["quality_weight"] == 0.3
    assert overrides["momentum_top_pct"] == 0.1
    assert overrides["fast_mode"] is True
    assert result["exp_id"] == "exp_test_residual_quality"
    assert result["experiment_id"] == "exp_test_residual_quality"


def test_config_json_residual_split_weights_become_execution_overrides(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_experiment(base_cfg_path, preset="single", overrides=None, progress_hook=None):
        captured["base_cfg_path"] = base_cfg_path
        captured["preset"] = preset
        captured["overrides"] = dict(overrides or {})
        return {
            "exp_id": "exp_test_residual_split",
            "results_dir": "",
            "status": "OK",
        }

    monkeypatch.setattr(runner, "run_experiment", _fake_run_experiment)
    monkeypatch.setattr(runner_impl, "_attach_run_profile_summary", lambda result: None)
    monkeypatch.setattr(runner_impl, "_write_config_snapshots", lambda **kwargs: None)
    monkeypatch.setattr(service, "stabilize_experiment_output", lambda **kwargs: dict(kwargs["result"]))

    payload = _breakout_config()
    payload["signal_generation"]["ranking"] = {
        "score_source_mode": "residual_only",
        "residual_window": 40,
        "residual_benchmark_weight": 0.3,
        "residual_industry_weight": 0.7,
    }
    body = runner_impl.BacktestV2ExperimentRequest(
        config_json=payload,
        fast_mode=True,
    )
    result = service.run_experiment_request_body(body)

    overrides = dict(captured["overrides"] or {})
    assert overrides["enable_multifactor_rank"] is True
    assert overrides["residual_window"] == 40
    assert overrides["residual_benchmark_weight"] == 0.3
    assert overrides["residual_industry_weight"] == 0.7
    assert result["exp_id"] == "exp_test_residual_split"
    assert result["experiment_id"] == "exp_test_residual_split"


def test_config_json_mf_rank_tilt_sizing_fields_become_execution_overrides(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_experiment(base_cfg_path, preset="single", overrides=None, progress_hook=None):
        captured["base_cfg_path"] = base_cfg_path
        captured["preset"] = preset
        captured["overrides"] = dict(overrides or {})
        return {
            "exp_id": "exp_test_mf_rank_tilt",
            "results_dir": "",
            "status": "OK",
        }

    monkeypatch.setattr(runner, "run_experiment", _fake_run_experiment)
    monkeypatch.setattr(runner_impl, "_attach_run_profile_summary", lambda result: None)
    monkeypatch.setattr(runner_impl, "_write_config_snapshots", lambda **kwargs: None)
    monkeypatch.setattr(service, "stabilize_experiment_output", lambda **kwargs: dict(kwargs["result"]))

    payload = _breakout_config()
    payload["sizing"] = {
        "weight_mode": "mf_rank_tilt",
        "min_positions": 10,
        "tilt_strength": 0.15,
        "tilt_top_n": 3,
        "tilt_bottom_n": 2,
    }
    body = runner_impl.BacktestV2ExperimentRequest(
        config_json=payload,
        fast_mode=True,
    )
    result = service.run_experiment_request_body(body)

    overrides = dict(captured["overrides"] or {})
    assert overrides["weight_mode"] == "mf_rank_tilt"
    assert overrides["min_positions"] == 10
    assert overrides["tilt_strength"] == 0.15
    assert overrides["tilt_top_n"] == 3
    assert overrides["tilt_bottom_n"] == 2
    assert overrides["fast_mode"] is True
    assert result["exp_id"] == "exp_test_mf_rank_tilt"
    assert result["experiment_id"] == "exp_test_mf_rank_tilt"


def test_runtime_config_asset_context_preserves_custom_overlay_fields(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_experiment(base_cfg_path, preset="single", overrides=None, progress_hook=None):
        captured["base_cfg_path"] = base_cfg_path
        captured["preset"] = preset
        captured["overrides"] = dict(overrides or {})
        return {
            "exp_id": "exp_test_asset_context_overlay",
            "results_dir": "",
            "status": "OK",
        }

    monkeypatch.setattr(runner, "run_experiment", _fake_run_experiment)
    monkeypatch.setattr(runner_impl, "_attach_run_profile_summary", lambda result: None)
    monkeypatch.setattr(runner_impl, "_write_config_snapshots", lambda **kwargs: None)
    monkeypatch.setattr(service, "stabilize_experiment_output", lambda **kwargs: dict(kwargs["result"]))

    runtime_cfg = _breakout_config()
    runtime_cfg["db"] = {"host": "pams-postgres"}
    runtime_cfg["schema_mapping"] = {}
    runtime_cfg["asset_context"] = {
        "asset_scope": "cn_a_equity",
        "moneyflow_overlay": {
            "enabled": True,
            "mode": "shadow",
            "factor_panel_path": "outputs/factors/monthly_factor_panel.csv",
            "coverage_ledger_path": "outputs/factors/monthly_coverage_ledger.csv",
        },
    }
    body = runner_impl.BacktestV2ExperimentRequest(
        runtime_config_json=runtime_cfg,
        fast_mode=True,
    )
    result = service.run_experiment_request_body(body)

    overrides = dict(captured["overrides"] or {})
    assert overrides["asset_context"]["asset_scope"] == "cn_a_equity"
    assert overrides["asset_context"]["moneyflow_overlay"]["enabled"] is True
    assert overrides["asset_context"]["moneyflow_overlay"]["mode"] == "shadow"
    assert result["exp_id"] == "exp_test_asset_context_overlay"
    assert result["experiment_id"] == "exp_test_asset_context_overlay"


def test_runtime_config_can_carry_explicit_data_role(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_experiment(base_cfg_path, preset="single", overrides=None, progress_hook=None):
        captured["overrides"] = dict(overrides or {})
        return {
            "exp_id": "exp_test_v2_runtime",
            "results_dir": "",
            "status": "OK",
        }

    monkeypatch.setattr(runner, "run_experiment", _fake_run_experiment)
    monkeypatch.setattr(runner_impl, "_attach_run_profile_summary", lambda result: None)
    monkeypatch.setattr(runner_impl, "_write_config_snapshots", lambda **kwargs: None)
    monkeypatch.setattr(service, "stabilize_experiment_output", lambda **kwargs: dict(kwargs["result"]))
    monkeypatch.setattr(
        service,
        "resolve_runtime_config_source",
        lambda **kwargs: {
            "effective_config_json": {
                "db": {"host": "pams-postgres"},
                "schema_mapping": {"pams_ohlcv_daily_v2": {"date": "trade_date", "symbol": "symbol"}},
                "data_source": {
                    "data_role": "v2_runtime",
                    "stocks_table": "pams_ohlcv_daily",
                    "v2_runtime_stocks_table": "pams_ohlcv_daily_v2_runtime",
                    "v2_schema_mapping_table": "pams_ohlcv_daily_v2",
                },
            },
            "config_source": "runtime_config_json",
            "resolved_config_mode": "draft_run",
            "resolved_config_id": "",
            "resolved_config_hash": "cfghash",
            "resolved_config_meta": {"source_type": "runtime_json", "owner": "manual"},
            "config_conflict_policy": "none",
        },
    )

    body = runner_impl.BacktestV2ExperimentRequest(runtime_config_json={"data_source": {"data_role": "v2_runtime"}})
    result = service.run_experiment_request_body(body)

    overrides = dict(captured["overrides"] or {})
    assert overrides["data_role"] == "v2_runtime"
    assert result["data_role"] == "v2_runtime"


def test_workbench_config_can_carry_explicit_data_role(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_experiment(base_cfg_path, preset="single", overrides=None, progress_hook=None):
        captured["overrides"] = dict(overrides or {})
        return {
            "exp_id": "exp_test_v2_canonical",
            "results_dir": "",
            "status": "OK",
        }

    monkeypatch.setattr(runner, "run_experiment", _fake_run_experiment)
    monkeypatch.setattr(runner_impl, "_attach_run_profile_summary", lambda result: None)
    monkeypatch.setattr(runner_impl, "_write_config_snapshots", lambda **kwargs: None)
    monkeypatch.setattr(service, "stabilize_experiment_output", lambda **kwargs: dict(kwargs["result"]))

    body = runner_impl.BacktestV2ExperimentRequest(
        workbench_config={
            "mode": "experiment",
            "initial_capital": 1000000,
            "strategy_pack": "BREAKOUT_TREND",
            "universe_mode": "HS300_ZZ500",
            "universe": {
                "start": "2012-01-04",
                "end": "2016-12-30",
                "benchmark": "000300.SH",
                "membership_mode": "PIT_DYNAMIC",
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
                "breakout": {"breakout_window": 45, "enable_dual_breakout": False},
            },
            "exit_rules": {
                "enabled": True,
                "atr_stop": {"enabled": True, "k": 1.2},
                "trailing": {"enabled": True, "k": 3.0},
            },
            "position_risk": {"enabled": True, "max_positions": 10},
            "data_source": {"data_role": "v2_canonical"},
        }
    )

    result = service.run_experiment_request_body(body)

    overrides = dict(captured["overrides"] or {})
    assert overrides["data_role"] == "v2_canonical"
    assert result["data_role"] == "v2_canonical"

