from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.research.watch_lagging_deconcentration_shadow import (
    apply_exclusion,
    build_case_summary,
    run_watch_lagging_deconcentration,
)


def _watch_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2015-01-02",
                "year": "2015",
                "symbol": "sh600001",
                "industry_name": "房地产",
                "forward_ret5": -0.05,
                "forward_ret20": -0.20,
                "mfe20": 0.02,
                "mae20": -0.30,
            },
            {
                "date": "2016-01-02",
                "year": "2016",
                "symbol": "sh600002",
                "industry_name": "计算机",
                "forward_ret5": -0.01,
                "forward_ret20": -0.04,
                "mfe20": 0.04,
                "mae20": -0.10,
            },
            {
                "date": "2017-01-02",
                "year": "2017",
                "symbol": "sh600003",
                "industry_name": "电子",
                "forward_ret5": 0.02,
                "forward_ret20": 0.06,
                "mfe20": 0.10,
                "mae20": -0.03,
            },
        ]
    )


def test_apply_exclusion_removes_years_and_industries() -> None:
    filtered = apply_exclusion(_watch_rows(), years={"2015"}, industries={"计算机"})

    assert len(filtered) == 1
    assert filtered.iloc[0]["industry_name"] == "电子"


def test_case_summary_and_runner_write_outputs(tmp_path: Path) -> None:
    summary = build_case_summary(_watch_rows(), window_key="demo")
    assert "EX_YEAR_2015" in set(summary["case"])
    assert int(summary.loc[summary["case"].eq("EX_YEAR_2015"), "rows"].iloc[0]) == 2

    input_root = tmp_path / "inputs"
    window_dir = input_root / "demo"
    window_dir.mkdir(parents=True)
    _watch_rows().to_csv(window_dir / "watch_lagging_detail.csv", index=False, encoding="utf-8-sig")

    result = run_watch_lagging_deconcentration(input_root=input_root, output_root=tmp_path / "outputs", windows=("demo",))
    assert result["research_only"] is True
    assert result["target_state"] == "watch_lagging"
    assert (tmp_path / "outputs" / "demo" / "case_summary.csv").exists()
    assert (tmp_path / "outputs" / "matrix.csv").exists()
    assert (tmp_path / "outputs" / "summary.md").exists()
