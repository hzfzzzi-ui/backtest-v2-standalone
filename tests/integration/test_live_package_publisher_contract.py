from __future__ import annotations

from backend.core.contracts.daily_position_adjustment_package import validate_daily_position_adjustment_package
from backend.core.services.live_package_publisher_service import (
    build_daily_position_adjustment_package_from_reconcile,
    package_to_payload,
)
from backend.core.services.live_strategy_registry_service import LiveStrategyRecord


def test_live_package_publisher_output_passes_daily_package_contract() -> None:
    strategy = LiveStrategyRecord(
        strategy_id="integration_live_strategy",
        status="live_approved",
        baseline_id="CN_STOCK_ETF_COMBO_BASELINE_V3",
        config_path="backend/configs/pams_cn_pg.json",
        config_hash="cfg_hash_integration",
        execution_contract_hash="exec_hash_integration",
        asset_scope="cn_a_equity",
        account_scopes=["default_personal_account"],
        publish_schedule="cn_a_after_close",
        approval_record={"approved_by": "manual", "approved_at": "2026-05-29"},
    )
    reconcile_payload = {
        "reconcile_id": "rc_integration_20260529",
        "account_id": "default_personal_account",
        "snapshot_id": "holdings_default_20260529",
        "snapshot_trade_date": "2026-05-29",
        "as_of_date": "2026-05-29",
        "strategy_source": {
            "exp_id": "run_integration_20260529",
            "config_hash": "cfg_hash_integration",
            "asset_scope": "cn_a_equity",
        },
        "execution_assumptions": {
            "signal_clock": "POST_CLOSE",
            "execution_clock": "NEXT_OPEN",
            "reference_price_basis": "latest_close",
        },
        "action_sheet": [
            {
                "symbol": "sh600519",
                "action_type": "buy",
                "current_qty": 0,
                "suggested_qty": 100,
                "target_qty": 100,
                "delta_qty": 100,
                "reference_price": 1500.0,
                "reference_price_basis": "latest_close",
                "reason_code": "BUY_BREAKOUT",
                "reason_tags": ["breakout"],
                "blocked": False,
                "blocked_reason": "",
                "target_weight": 0.2,
            }
        ],
    }

    package = build_daily_position_adjustment_package_from_reconcile(
        reconcile_payload,
        strategy=strategy,
        baseline_id="CN_STOCK_ETF_COMBO_BASELINE_V3",
        execution_contract_hash="exec_hash_integration",
        execution_date="2026-06-01",
        generated_at="2026-05-29T15:30:00+08:00",
    )
    payload = package_to_payload(package)
    validated = validate_daily_position_adjustment_package(payload)

    assert validated.package_status == "ready"
    assert validated.source.strategy_id == "integration_live_strategy"
    assert validated.action_sheet[0].idempotency_key
