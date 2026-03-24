from __future__ import annotations

import json

import pandas as pd

from backend.core.audit.attribution_audit import build_attribution_audit


def test_build_attribution_audit_collects_state_budget_sleeve_and_reason_logs() -> None:
    daily_df = pd.DataFrame(
        [
            {
                "date": "2026-03-19",
                "market_state_5": "LIGHT",
                "trade_mode": "LIGHT",
                "regime_transition_reason": "breadth_weak",
                "reason_codes_json": json.dumps(["BREADTH_WEAK"], ensure_ascii=False),
                "regime_confidence": 0.55,
                "risk_budget_multiplier": 0.6,
                "manual_override_json": json.dumps({"active": False}, ensure_ascii=False),
                "governor_budget_json": json.dumps(
                    {
                        "budget_owner": "global_portfolio_governor",
                        "budget_consumer_sleeve_id": "cn_stock_trend_alpha_core",
                        "budget_consumer_system_role": "stock_alpha_sleeve",
                        "total_risk_budget": 0.6,
                        "total_exposure_cap": 0.6,
                        "drawdown_state": "NORMAL",
                        "recovery_state": "INACTIVE",
                        "cooldown_state": "INACTIVE",
                        "defense_floor_state": "INACTIVE",
                        "budget_reason_codes": ["TOTAL_RISK_BUDGET_REDUCED"],
                    },
                    ensure_ascii=False,
                ),
            },
            {
                "date": "2026-03-20",
                "market_state_5": "TRANS_DOWN",
                "trade_mode": "RISK_OFF",
                "regime_transition_reason": "trend_break",
                "reason_codes_json": json.dumps(["TREND_BREAK"], ensure_ascii=False),
                "regime_confidence": 0.8,
                "risk_budget_multiplier": 0.3,
                "manual_override_json": json.dumps(
                    {"active": True, "reason": "manual_risk_cut", "scope": "runtime", "actor": "user"},
                    ensure_ascii=False,
                ),
                "governor_budget_json": json.dumps(
                    {
                        "budget_owner": "global_portfolio_governor",
                        "budget_consumer_sleeve_id": "cn_etf_beta",
                        "budget_consumer_system_role": "market_beta_sleeve",
                        "total_risk_budget": 0.3,
                        "total_exposure_cap": 0.3,
                        "drawdown_state": "REDUCED",
                        "recovery_state": "DRAWDOWN_RECOVERY_PENDING",
                        "cooldown_state": "INACTIVE",
                        "defense_floor_state": "ACTIVE",
                        "defense_floor": 0.2,
                        "budget_reason_codes": ["DRAWDOWN_REDUCED", "MANUAL_OVERRIDE_ACTIVE"],
                    },
                    ensure_ascii=False,
                ),
            },
        ]
    )
    run_meta = {
        "governed_snapshot": {
            "sleeve_budgets": {
                "cn_etf_beta": {
                    "system_role": "market_beta_sleeve",
                    "budget_source": "global_portfolio_governor",
                    "slot_cap": 2,
                    "available_slots": 1,
                    "candidate_count": 4,
                    "selected_count": 1,
                    "raw_sleeve_ids": ["cn_etf_beta"],
                }
            },
            "sleeve_selection_summary": {
                "cn_etf_beta": {
                    "eligible_etfs": ["510300.SH", "512100.SH"],
                    "selected_etfs": ["510300.SH"],
                    "out_of_scope_etfs": ["511010.SH"],
                    "selection_reason_codes": {"510300.SH": ["FORMAL_CORE_BETA"]},
                }
            },
        },
        "etf_beta": {
            "source_entry_type": "cn_etf_research_entry",
            "formal_core_beta_symbols": ["510300.SH", "512100.SH"],
            "limited_defense_candidates": ["512890.SH"],
            "out_of_scope_reason_codes": {"511010.SH": ["OUT_OF_PHASE1_FORMAL_SCOPE"]},
        },
    }

    payload = build_attribution_audit(daily_df=daily_df, run_meta=run_meta)

    assert payload["summary"]["state_log_count"] == 2
    assert payload["summary"]["budget_log_count"] == 2
    assert payload["summary"]["sleeve_log_count"] == 1
    assert payload["summary"]["manual_override_log_count"] == 1
    assert payload["reason_code_summary"]["state_reason_codes"]["TREND_BREAK"] == 1
    assert payload["reason_code_summary"]["budget_reason_codes"]["DRAWDOWN_REDUCED"] == 1
    assert payload["reason_code_summary"]["sleeve_reason_codes"]["FORMAL_CORE_BETA"] == 1
    assert payload["reason_code_summary"]["manual_override_reasons"]["manual_risk_cut"] == 1
