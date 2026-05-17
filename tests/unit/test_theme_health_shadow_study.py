from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.research import study_loader, study_runner
from backend.research import theme_health_shadow_study as ths
from backend.research.study_definition import validate_study_payload


def _alignment_rows() -> list[dict[str, object]]:
    return [
        {
            "date": "2025-01-02",
            "theme": "compute",
            "stock_theme_exposure_pct": 0.25,
            "stock_theme_position_count": 2,
            "held_examples": "AAA",
            "proxy_available": True,
            "theme_proxy": "compute_proxy",
            "proxy_max_ret20": -0.05,
            "proxy_max_ret60": -0.02,
            "proxy_max_ret5": -0.01,
            "candidate_rows": 0,
            "selected_rows": 0,
            "cash_blocked_rows": 0,
            "candidate_examples": "",
            "stock_overweight_proxy_weak": True,
        },
        {
            "date": "2025-01-02",
            "theme": "power",
            "stock_theme_exposure_pct": 0.10,
            "stock_theme_position_count": 1,
            "held_examples": "BBB",
            "proxy_available": True,
            "theme_proxy": "power_proxy",
            "proxy_max_ret20": 0.12,
            "proxy_max_ret60": 0.18,
            "proxy_max_ret5": 0.04,
            "candidate_rows": 1,
            "selected_rows": 1,
            "cash_blocked_rows": 0,
            "candidate_examples": "CCC",
            "stock_overweight_proxy_weak": False,
        },
    ]


def _write_source_bundle(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "baseline_id": "CN_STOCK_ETF_COMBO_BASELINE_V3",
                "stock_component_exp_id": "exp_stock",
                "etf_component_exp_id": "exp_etf",
                "scope": "test",
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(_alignment_rows()).to_csv(
        root / "long_daily_theme_alignment.csv",
        index=False,
        encoding="utf-8-sig",
    )


def test_compute_theme_health_daily_labels_confirmed_weak() -> None:
    daily = ths.compute_theme_health_daily(
        pd.DataFrame(_alignment_rows()),
        dict(ths.DEFAULT_THRESHOLDS),
    )

    compute = daily.loc[daily["theme"].eq("compute")].iloc[0]
    power = daily.loc[daily["theme"].eq("power")].iloc[0]

    assert compute["theme_health_label"] == "confirmed_weak"
    assert int(compute["weak_flag_count"]) >= 3
    assert power["theme_health_label"] == "healthy"


def test_theme_health_study_dry_run_matrix() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_theme_health_shadow_v1")
    plan = study_runner.build_execution_plan(study)

    assert len(plan) == 6
    assert [variant.name for variant in study.variants] == ["C1_THEME_HEALTH_SHADOW"]
    assert [window.key for window in study.windows][:3] == ["1626", "2020_2026", "2024_2026"]
    assert study.metadata["runner_mode"] == "cn_stock_etf_theme_health_shadow"


def test_theme_health_runner_writes_research_only_outputs(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    _write_source_bundle(source)
    monkeypatch.setattr(ths, "outputs_root", lambda: tmp_path / "outputs" / "studies")
    study = validate_study_payload(
        {
            "study_id": "cn_stock_etf/demo_theme_health",
            "title": "Demo",
            "asset_scope": "cn_stock_etf",
            "baseline_id": "CN_STOCK_ETF_COMBO_BASELINE_V3",
            "hypothesis": "demo",
            "change_scope": {"modules_modified": ["demo"]},
            "variants": [{"name": "C1_THEME_HEALTH_SHADOW"}],
            "windows": [{"key": "2025", "role": "diagnostic", "start": "2025-01-01", "end": "2025-01-31"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "study_conclusion"],
        }
    )
    result = ths.run_theme_health_shadow_study(
        study=study,
        plan=[
            {
                "window_key": "2025",
                "window_role": "diagnostic",
                "variant_name": "C1_THEME_HEALTH_SHADOW",
                "request_payload": {
                    "start_date": "2025-01-01",
                    "end_date": "2025-01-31",
                    "runner_params": {"input_artifact_dir": str(source)},
                },
            }
        ],
    )

    run = result["runs"][0]
    assert run["research_only"] is True
    assert run["not_nav_backtest"] is True
    assert run["exp_id"] == ""
    assert run["summary"]["held_theme_days"] == 2
    assert run["summary"]["confirmed_weak_days"] == 1
    assert run["verdict"]["status"] == "confirmed"
    assert Path(run["machine_outputs"]["summary"]).exists()
    assert Path(run["machine_outputs"]["daily"]).exists()
    assert Path(run["human_outputs"]["summary"]).exists()


def test_theme_health_runner_missing_source_is_inconclusive(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "missing"
    source.mkdir()
    monkeypatch.setattr(ths, "outputs_root", lambda: tmp_path / "outputs" / "studies")
    study = validate_study_payload(
        {
            "study_id": "cn_stock_etf/demo_theme_health_missing",
            "title": "Demo",
            "asset_scope": "cn_stock_etf",
            "baseline_id": "CN_STOCK_ETF_COMBO_BASELINE_V3",
            "hypothesis": "demo",
            "change_scope": {"modules_modified": ["demo"]},
            "variants": [{"name": "C1_THEME_HEALTH_SHADOW"}],
            "windows": [{"key": "2025", "role": "diagnostic", "start": "2025-01-01", "end": "2025-01-31"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "study_conclusion"],
        }
    )
    result = ths.run_theme_health_shadow_study(
        study=study,
        plan=[
            {
                "window_key": "2025",
                "window_role": "diagnostic",
                "variant_name": "C1_THEME_HEALTH_SHADOW",
                "request_payload": {
                    "start_date": "2025-01-01",
                    "end_date": "2025-01-31",
                    "runner_params": {"input_artifact_dir": str(source)},
                },
            }
        ],
    )

    run = result["runs"][0]
    assert run["verdict"]["status"] == "inconclusive"
    assert "long_daily_theme_alignment.csv" in run["source_audit"]["missing_files"]


def test_study_runner_delegates_to_theme_health_runner(monkeypatch) -> None:
    study = validate_study_payload(
        {
            "study_id": "cn_stock_etf/demo_delegate_theme_health",
            "title": "Demo",
            "asset_scope": "cn_stock_etf",
            "baseline_id": "CN_STOCK_ETF_COMBO_BASELINE_V3",
            "hypothesis": "demo",
            "change_scope": {"modules_modified": ["demo"]},
            "variants": [{"name": "C1_THEME_HEALTH_SHADOW"}],
            "windows": [{"key": "2025", "role": "diagnostic", "start": "2025-01-01", "end": "2025-01-31"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle"],
            "metadata": {"runner_mode": "cn_stock_etf_theme_health_shadow"},
        }
    )
    captured: dict[str, object] = {}

    def _fake_runner(**kwargs):
        captured.update(kwargs)
        return {"status": "theme_health_runner_only"}

    monkeypatch.setattr(study_runner, "run_theme_health_shadow_study", _fake_runner)
    result = study_runner.run_study(study, only_window_keys=["2025"], only_variant_names=["C1_THEME_HEALTH_SHADOW"])

    assert result["status"] == "theme_health_runner_only"
    assert captured["study"] == study
    assert isinstance(captured["plan"], list) and len(captured["plan"]) == 1
