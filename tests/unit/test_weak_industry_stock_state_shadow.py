from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.research.weak_industry_stock_state_shadow import (
    build_flag_summary,
    build_position_state_detail,
    run_weak_industry_stock_state_shadow,
)


def _held_industry() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-01-30",
                "industry_index_code": "801010.SI",
                "industry_name": "测试行业",
                "industry_health_label": "weak",
                "held_symbols": "sh600001;sh600002",
                "ret20": -0.05,
                "ret60": -0.08,
            }
        ]
    )


def _industry_daily() -> pd.DataFrame:
    rows = []
    for idx, day in enumerate(pd.date_range("2026-01-26", "2026-01-30", freq="D"), start=1):
        rows.append(
            {
                "date": day.strftime("%Y-%m-%d"),
                "industry_index_code": "801010.SI",
                "industry_name": "测试行业",
                "industry_health_label": "weak",
                "ret20": -0.05,
                "ret60": -0.08,
                "drawdown60": -0.12,
                "trend_score": 0.2,
            }
        )
    return pd.DataFrame(rows)


def _ohlcv() -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2025-12-20", "2026-02-28", freq="D")
    for i, day in enumerate(dates):
        strong_close = 10.0 + i * 0.05
        weak_close = 20.0 - i * 0.08
        rows.append({"date": day, "symbol": "sh600001", "open": strong_close, "high": strong_close * 1.01, "low": strong_close * 0.99, "close": strong_close})
        rows.append({"date": day, "symbol": "sh600002", "open": weak_close, "high": weak_close * 1.01, "low": weak_close * 0.99, "close": weak_close})
    return pd.DataFrame(rows)


def test_position_state_detail_classifies_stock_strength() -> None:
    detail = build_position_state_detail(held_industry=_held_industry(), industry_daily=_industry_daily(), ohlcv=_ohlcv())

    assert set(detail["symbol"]) == {"sh600001", "sh600002"}
    by_symbol = detail.set_index("symbol")
    assert by_symbol.loc["sh600001", "stage_label"] == "G1_INDUSTRY_WEAK_STOCK_STRONG"
    assert by_symbol.loc["sh600002", "stage_label"] == "G2_INDUSTRY_WEAK_STOCK_WEAK"
    assert int(by_symbol.loc["sh600001", "industry_weak_duration"]) == 5
    assert "mfe20" in detail.columns
    assert "mae20" in detail.columns


def test_run_shadow_writes_outputs(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    machine = input_root / "demo" / "M1_STYLE_STATE" / "machine"
    machine.mkdir(parents=True)
    _held_industry().to_csv(machine / "rotation_pressure_held_industry_daily.csv", index=False, encoding="utf-8-sig")
    _industry_daily().to_csv(machine / "industry_health_by_industry_daily.csv", index=False, encoding="utf-8-sig")
    ohlcv_path = tmp_path / "ohlcv.csv"
    _ohlcv().to_csv(ohlcv_path, index=False, encoding="utf-8-sig")

    result = run_weak_industry_stock_state_shadow(
        input_root=input_root,
        output_root=tmp_path / "outputs",
        windows=("demo",),
        ohlcv_csv=ohlcv_path,
    )

    assert result["research_only"] is True
    assert result["baseline_mutation"] is False
    assert result["nav_recompute"] is False
    assert (tmp_path / "outputs" / "demo" / "position_state_detail.csv").exists()
    assert (tmp_path / "outputs" / "summary.md").exists()

    detail = pd.read_csv(tmp_path / "outputs" / "demo" / "position_state_detail.csv")
    flag_summary = build_flag_summary(detail)
    assert int(flag_summary.loc[flag_summary["flag"].eq("stock_strong_flag"), "rows"].iloc[0]) == 1
