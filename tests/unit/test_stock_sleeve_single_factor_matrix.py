from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from backend.research import stock_sleeve_single_factor_matrix as matrix


# Explicit expectations: changing the active studies is a reviewable contract change.
SOURCES = (
    ("stock_alpha", "factors/stock_alpha_factor_real_mainline_s1", "B0_EQUAL", "rank_long"),
    ("moneyflow", "factors/moneyflow_factor_real_mainline_s2", "A_H20_CONTROL", "rank_long"),
    ("positive_quality", "factors/positive_quality_factor_real_mainline_s1", "B0_EQUAL", "rank_long"),
    ("industry_second_stage", "factors/industry_second_stage_factor_real_mainline_s1", "B0_EQUAL", "rank_long"),
    ("negative_conditional_context", "factors/negative_conditional_context_real_mainline_s1", "B0_EQUAL", "veto_high"),
    ("risk_gate", "factors/risk_gate_factor_real_mainline_s1", "B0_EQUAL", "veto_high"),
    ("execution_pressure", "factors/execution_pressure_factor_real_mainline_s1", "B0_EQUAL", "veto_high"),
    ("exit_fragility", "factors/exit_fragility_factor_real_mainline_s1", "B0_EQUAL", "veto_high"),
    ("stock_lifecycle_fragility", "factors/stock_lifecycle_fragility_real_mainline_s1", "B0_EQUAL", "veto_high"),
    ("final_score_composition", "factors/final_score_composition_real_mainline_s1", "B0_EQUAL", "rank_long"),
)
WINDOWS = ("1217", "1222", "1226")


def _analysis_path(root: Path, study: str, variant: str, window: str) -> Path:
    return root / "outputs" / "studies" / study / window / variant / "machine" / "analysis.json"


def _require_complete_evidence(root: Path) -> None:
    missing = [f"{study}/{window}/{variant}" for _, study, variant, _ in SOURCES for window in WINDOWS
               if not _analysis_path(root, study, variant, window).is_file()]
    if missing:
        raise AssertionError(f"真实研究综合验收失败：缺少 {len(missing)} 份 analysis.json")


@pytest.fixture
def synthetic_studies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Only temporary test fixtures, never real experiments or baseline evidence."""
    monkeypatch.setattr(matrix, "_repo_root", lambda: tmp_path)
    for family, study, variant, mode in SOURCES:
        for index, window in enumerate(WINDOWS):
            factor = "synthetic_shared" if family in {"stock_alpha", "moneyflow"} else f"synthetic_{family}"
            if mode == "veto_high":
                metrics = {"horizon_20d": {"veto_top20_improvement": (index + 1) / 100,
                                           "high20_mean_return": -(index + 1) / 200}, "coverage_ratio": 0.8}
            else:
                horizon = "1d" if family == "stock_alpha" else "20d"
                metrics = {f"mean_observation_ic_{horizon}": (index + 1) / 100,
                           f"mean_top_bottom_spread_{horizon}": (index + 1) / 200,
                           "coverage_ratio": 0.8}
            analysis = {"single_factor": {factor: metrics}}
            payload = {"analysis": analysis} if window != "1222" else analysis
            path = _analysis_path(tmp_path, study, variant, window)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


def _assert_current_source_contract(result: dict) -> None:
    meta, window, stability = result["meta"], result["window_matrix"], result["stability_matrix"]
    assert meta["family_count"] == 10
    assert meta["window_keys"] == list(WINDOWS)
    assert [(s["family"], s["study_id"], s["variant_name"], s["use_mode"]) for s in meta["source_studies"]] == list(SOURCES)
    assert meta["family_factor_count"] == len(stability)
    assert meta["factor_window_row_count"] == len(window)
    moneyflow = window.loc[window["family"] == "moneyflow"]
    assert not moneyflow.empty
    assert set(moneyflow["study_id"]) == {"factors/moneyflow_factor_real_mainline_s2"}
    assert set(moneyflow["variant_name"]) == {"A_H20_CONTROL"}
    assert set(moneyflow["primary_metric_name"]) == {"mean_observation_ic_20d"}
    projection = stability.loc[stability["family"] == "final_score_composition"]
    assert not projection.empty and projection["is_projection_family"].all()


def test_synthetic_matrix_checks_all_sources_windows_and_metric_semantics(synthetic_studies: Path) -> None:
    result = matrix.build_stock_sleeve_single_factor_matrix(write_outputs=False)
    _assert_current_source_contract(result)
    window, stability = result["window_matrix"], result["stability_matrix"]
    assert len(window) == 30 and len(stability) == 10
    assert result["meta"]["unique_factor_id_count"] == 9
    assert set(window["window_key"]) == set(WINDOWS)
    assert set(window.loc[window["factor_id"] == "synthetic_shared", "factor_id_family_count"]) == {2}
    moneyflow = stability.loc[stability["family"] == "moneyflow"].iloc[0]
    assert moneyflow["current_primary_metric_name"] == "mean_observation_ic_20d"
    assert moneyflow["current_primary_metric_value"] == pytest.approx(0.03)
    assert moneyflow["mean_primary_metric"] == pytest.approx(0.02)
    assert moneyflow["positive_window_count"] == 3 and moneyflow["direction"] == "positive"
    risk = window.loc[(window["family"] == "risk_gate") & (window["window_key"] == "1226")].iloc[0]
    assert risk["analysis_style"] == "veto_surface"
    assert risk["primary_metric_name"] == "veto_top20_improvement_20d"
    assert risk["primary_metric_value"] == pytest.approx(0.03)
    assert result["output_refs"] == {}
    assert not (synthetic_studies / "outputs/studies/factors/stock_sleeve_single_factor_matrix").exists()


def test_missing_or_corrupt_study_is_not_reported_as_success(synthetic_studies: Path) -> None:
    _, study, variant, _ = SOURCES[1]
    path = _analysis_path(synthetic_studies, study, variant, "1226")
    path.unlink()
    with pytest.raises(AssertionError, match="缺少 1 份"):
        _require_complete_evidence(synthetic_studies)
    with pytest.raises(FileNotFoundError):
        matrix.build_stock_sleeve_single_factor_matrix(write_outputs=False)
    path.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        matrix.build_stock_sleeve_single_factor_matrix(write_outputs=False)


def test_real_study_matrix_requires_explicit_complete_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    evidence = os.environ.get("BACKTEST_MATRIX_REAL_EVIDENCE_ROOT", "").strip()
    if not evidence:
        pytest.skip("真实研究综合验收未执行：未显式提供独立证据目录及 30 份 analysis.json")
    root = Path(evidence).expanduser()
    if not root.is_absolute():
        pytest.fail("真实证据目录必须使用绝对路径")
    root = root.resolve()
    repository = Path(__file__).resolve().parents[2]
    if root == repository or root.is_relative_to(repository):
        pytest.fail("真实证据应放在与源码工作区独立的只读目录")
    _require_complete_evidence(root)
    monkeypatch.setattr(matrix, "_repo_root", lambda: root)
    _assert_current_source_contract(matrix.build_stock_sleeve_single_factor_matrix(write_outputs=False))
