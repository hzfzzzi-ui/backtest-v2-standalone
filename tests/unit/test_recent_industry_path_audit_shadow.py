from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.research.recent_industry_path_audit_shadow import (
    build_snapshot_segments,
    label_target_trades,
    run_recent_industry_path_audit,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _snapshot(date: str, symbol: str = "sz000001", **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "date": date,
        "symbol": symbol,
        "industry_name": "计算机",
        "ret5": 0.05,
        "ret10": 0.12,
        "ret20": 0.24,
        "close_vs_ma20": 0.18,
        "drawdown20": -0.12,
        "forward_ret20": -0.16,
        "mfe20": 0.03,
        "mae20": -0.22,
        "industry_ret20": -0.08,
        "industry_ret60": -0.12,
        "industry_breadth_weak": 0.7,
        "industry_breadth_healthy": 0.1,
        "high_chase_like_flag": True,
        "trend_exhaustion_after_flag": True,
        "industry_breakdown_flag": True,
        "market_breadth_weak_flag": False,
        "rotation_pressure_flag": False,
        "delayed_exit_like_flag": False,
        "healthy_state_misread_flag": False,
        "style_adverse_flag": False,
        "failure_outcome_flag": True,
        "position_risk_state": "watch_pullback",
        "style_state_label": "split_rotation",
        "industry_market_health_label": "industry_rotation",
    }
    row.update(overrides)
    return row


def _trade(symbol: str = "sz000001", **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "symbol": symbol,
        "name": "样本",
        "entry_date": "2025-02-14",
        "exit_date": "2025-04-07",
        "sw_l1_industry": "计算机",
        "realized_pnl": -100.0,
        "realized_return": -0.15,
        "stock_pre_entry_20d_return": 0.9,
        "pre_entry_ret5": 0.4,
        "pre_entry_ret10": 0.7,
        "entry_close_vs_prev_ma20": 0.6,
        "close_mfe": 0.1,
        "close_mae": -0.25,
        "giveback_from_close_peak": 0.4,
        "peak_to_exit_drawdown": -0.3,
        "industry_index_return_holding": -0.2,
        "relative_vs_industry_holding": -0.1,
        "days_below_ma20_warning_before_exit": 20,
        "days_dd10_warning_before_exit": 25,
        "days_since_last_candidate_before_exit": 9,
        "hold_calendar_days": 50,
        "exit_reason_code": "RISK_OFF_EXIT",
    }
    row.update(overrides)
    return row


def test_build_snapshot_segments_labels_path() -> None:
    frame = pd.DataFrame([_snapshot("2025-02-03"), _snapshot("2025-02-04")])

    segments = build_snapshot_segments(frame)

    assert len(segments) == 1
    assert segments.loc[0, "path_label"] == "industry_breakdown"
    assert segments.loc[0, "failure_outcome_rate"] == 1.0


def test_label_target_trades_adds_reason_flags() -> None:
    trades = pd.DataFrame([_trade(), _trade("sz000002", realized_return=0.02, sw_l1_industry="基础化工")])

    labeled = label_target_trades(trades)

    assert "trade_path_reasons" in labeled.columns
    assert bool(labeled.loc[0, "trade_industry_drag_flag"])
    assert bool(labeled.loc[0, "trade_risk_off_exit_flag"])


def test_run_recent_industry_path_audit_writes_outputs(tmp_path: Path) -> None:
    mechanism_root = tmp_path / "mechanism"
    trade_path = tmp_path / "trades.csv"
    output_root = tmp_path / "out"
    _write_csv(mechanism_root / "1226" / "mechanism_detail.csv", [_snapshot("2025-02-03")])
    _write_csv(trade_path, [_trade()])

    summary = run_recent_industry_path_audit(
        mechanism_root=mechanism_root,
        trade_detail_path=trade_path,
        output_root=output_root,
    )

    assert summary["target_trade_rows"] == 1
    assert summary["target_segment_rows"] == 1
    assert (output_root / "target_trade_detail.csv").exists()
    assert (output_root / "target_snapshot_segments.csv").exists()
