from __future__ import annotations

from fastapi import HTTPException

from backend.api.endpoints._semantic_config_compiler import (
    SEMANTIC_CONFIG_SCHEMA_VERSION,
    compile_semantic_config_json,
    validate_semantic_config_json,
)


def _valid_config() -> dict:
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
                "breakout_window": 55,
                "enable_dual_breakout": False,
            },
        },
        "exit_rules": {
            "enabled": True,
            "atr_stop": {"enabled": True, "k": 1.2},
            "trailing": {"enabled": True, "k": 3.0},
            "time_exit": {"enabled": False, "n_days": 20},
        },
        "position_risk": {
            "enabled": True,
            "max_positions": 10,
            "single_stock_cap": 0.1,
            "industry_cap": 0.3,
            "lot": 100,
            "cash_shortage_policy": "skip",
        },
    }


def test_validate_semantic_config_json_accepts_known_fields() -> None:
    out = validate_semantic_config_json(_valid_config())
    assert out["strategy_pack"] == "BREAKOUT_TREND"
    assert out["universe"]["filters"]["price_min"] == 5.0


def test_validate_semantic_config_json_rejects_unknown_top_level_field() -> None:
    payload = _valid_config()
    payload["unexpected_flag"] = True
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "unexpected_flag" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for unknown top-level field")


def test_validate_semantic_config_json_rejects_unknown_nested_field() -> None:
    payload = _valid_config()
    payload["universe"]["filters"]["mystery_field"] = 123
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "mystery_field" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for unknown nested field")


def test_validate_semantic_config_json_rejects_missing_strategy_block() -> None:
    payload = _valid_config()
    payload["signal_generation"].pop("breakout", None)
    try:
        validate_semantic_config_json(payload)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "signal_generation.breakout" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException for missing breakout block")


def test_compile_semantic_config_json_emits_provenance_and_compiled_plan() -> None:
    compiled = compile_semantic_config_json(
        _valid_config(),
        compiled_plan_payload={"runtime_config": {"strategy": {"name": "breakout_trend"}}},
        config_source="config_json",
    )
    assert compiled["schema_version"] == SEMANTIC_CONFIG_SCHEMA_VERSION
    assert compiled["resolved_config"]["schema_version"] == SEMANTIC_CONFIG_SCHEMA_VERSION
    assert compiled["resolved_config"]["config_source"] == "config_json"
    assert compiled["compiled_plan"]["runtime_config"]["strategy"]["name"] == "breakout_trend"
