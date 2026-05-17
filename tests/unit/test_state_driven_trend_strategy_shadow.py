from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.research.state_driven_trend_strategy_shadow import (
    build_trade_state_audit,
    derive_stock_eligibility,
    industry_permission_from_health,
    market_permission_from_style,
    prepare_industry_states,
    prepare_market_states,
    run_state_driven_trend_strategy_shadow,
    summarize_trade_audit,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def test_permission_label_mapping_is_live_safe_and_layered() -> None:
    assert market_permission_from_style("broad_bull") == "risk_on"
    assert market_permission_from_style("risk_off") == "risk_off"
    assert industry_permission_from_health("weak") == "block"
    assert derive_stock_eligibility("risk_off", "allow") == ("blocked", "block_market")
    assert derive_stock_eligibility("risk_on", "block") == ("blocked", "block_industry")
    assert derive_stock_eligibility("neutral", "allow") == ("reduced", "reduce_state")
    assert derive_stock_eligibility("risk_on", "allow") == ("eligible", "allow")


def test_build_trade_state_audit_counts_false_positive_and_false_negative() -> None:
    style = prepare_market_states(
        pd.DataFrame(
            [
                {"date": "2024-01-01", "style_state_label": "broad_bull"},
                {"date": "2024-01-10", "style_state_label": "risk_off"},
                {"date": "2024-01-20", "style_state_label": "broad_bull"},
            ]
        )
    )
    industry = prepare_industry_states(
        pd.DataFrame(
            [
                {"date": "2024-01-01", "industry_name": "计算机", "industry_health_label": "healthy"},
                {"date": "2024-01-20", "industry_name": "计算机", "industry_health_label": "weak"},
            ]
        )
    )
    trades = pd.DataFrame(
        [
            {
                "symbol": "sz000001",
                "name": "loss allowed",
                "entry_date": "2024-01-03",
                "entry_signal_date": "2024-01-02",
                "exit_date": "2024-02-01",
                "sw_l1_industry": "计算机",
                "realized_pnl": -10,
                "realized_return": -0.10,
            },
            {
                "symbol": "sz000002",
                "name": "loss filtered",
                "entry_date": "2024-01-12",
                "entry_signal_date": "2024-01-11",
                "exit_date": "2024-02-01",
                "sw_l1_industry": "计算机",
                "realized_pnl": -20,
                "realized_return": -0.20,
            },
            {
                "symbol": "sz000003",
                "name": "winner filtered",
                "entry_date": "2024-01-22",
                "entry_signal_date": "2024-01-21",
                "exit_date": "2024-02-01",
                "sw_l1_industry": "计算机",
                "realized_pnl": 30,
                "realized_return": 0.30,
            },
        ]
    )

    audit = build_trade_state_audit(trades=trades, market_states=style, industry_states=industry)
    summary = summarize_trade_audit(audit)

    assert audit.loc[audit["symbol"].eq("sz000001"), "shadow_action"].item() == "allow"
    assert audit.loc[audit["symbol"].eq("sz000002"), "shadow_action"].item() == "block_market"
    assert audit.loc[audit["symbol"].eq("sz000003"), "shadow_action"].item() == "block_industry"
    assert summary["loser_filtered_or_reduced_rows"] == 1
    assert summary["winner_filtered_or_reduced_rows"] == 1
    assert summary["loser_allowed_rows"] == 1


def test_run_state_driven_trend_strategy_shadow_writes_window_outputs(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    trade_path = tmp_path / "trades.csv"
    output_root = tmp_path / "out"
    _write_csv(
        state_root / "1626" / "M1_STYLE_STATE" / "machine" / "style_state_daily.csv",
        [
            {"date": "2024-01-01", "style_state_label": "broad_bull"},
            {"date": "2024-01-10", "style_state_label": "risk_off"},
        ],
    )
    _write_csv(
        state_root / "1626" / "M1_STYLE_STATE" / "machine" / "industry_health_by_industry_daily.csv",
        [
            {"date": "2024-01-01", "industry_name": "电子", "industry_health_label": "healthy"},
            {"date": "2024-01-10", "industry_name": "电子", "industry_health_label": "watch"},
        ],
    )
    _write_csv(
        trade_path,
        [
            {
                "symbol": "sz000001",
                "name": "sample",
                "entry_date": "2024-01-12",
                "entry_signal_date": "2024-01-10",
                "exit_date": "2024-02-01",
                "sw_l1_industry": "电子",
                "realized_pnl": -10,
                "realized_return": -0.10,
            }
        ],
    )

    summary = run_state_driven_trend_strategy_shadow(
        state_root=state_root,
        trade_detail_path=trade_path,
        output_root=output_root,
        windows=("1626",),
    )

    assert summary["runs"][0]["summary"]["trade_rows"] == 1
    assert summary["runs"][0]["summary"]["loser_filtered_or_reduced_rows"] == 1
    assert (output_root / "1626" / "machine" / "trade_state_audit.csv").exists()
    assert (output_root / "1626" / "machine" / "summary.json").exists()
    assert (output_root / "matrix_summary.json").exists()
