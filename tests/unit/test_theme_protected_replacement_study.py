from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.research import study_loader, study_runner
from backend.research import theme_protected_replacement_study as tprs
from backend.research.study_definition import validate_study_payload


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
    pd.DataFrame(
        [
            {"date": "2016-01-05", "buy_symbol": "sz000001", "buy_name": "A", "sell_symbol": "sh600000", "sell_name": "B"},
            {"date": "2024-01-05", "buy_symbol": "sz000002", "buy_name": "C", "sell_symbol": "sh600001", "sell_name": "D"},
        ]
    ).to_csv(root / "b0_shadow_daily_plan.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {
                "date": "2016-01-05",
                "theme": "storage",
                "proxy_max_ret20": 0.2,
                "buy_symbol": "sz000001",
                "buy_name": "A",
                "sell_symbol": "sh600000",
                "sell_name": "B",
                "sell_theme_tags": "consumer",
                "potential_replace_amount_capped": 100.0,
            },
            {
                "date": "2024-01-05",
                "theme": "power",
                "proxy_max_ret20": 0.3,
                "buy_symbol": "sz000002",
                "buy_name": "C",
                "sell_symbol": "sh600001",
                "sell_name": "D",
                "sell_theme_tags": "cyclical",
                "potential_replace_amount_capped": 200.0,
            },
        ]
    ).to_csv(root / "b01_shadow_daily_plan.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {"date": "2016-01-05", "shadow_status": "PAIR_FOUND"},
            {"date": "2024-01-05", "shadow_status": "PAIR_FOUND"},
        ]
    ).to_csv(root / "b01_shadow_raw_triggers.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {"date": "2016-01-06", "filter_no_eligible_sell": 2},
            {"date": "2024-01-06", "filter_risk_state": 1},
        ]
    ).to_csv(root / "b01_shadow_filtered.csv", index=False, encoding="utf-8-sig")


def test_theme_protected_replacement_study_dry_run_matrix() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_theme_protected_replacement_v1")
    plan = study_runner.build_execution_plan(study)

    assert len(plan) == 6
    assert [variant.name for variant in study.variants] == ["B01_PROTECTED_SHADOW"]
    assert [window.key for window in study.windows][:3] == ["1626", "1217", "1226"]
    assert study.metadata["runner_mode"] == "cn_stock_etf_theme_protected_replacement"


def test_theme_protected_runner_writes_formal_shadow_outputs(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    _write_source_bundle(source)
    out_root = tmp_path / "outputs" / "studies"
    monkeypatch.setattr(tprs, "outputs_root", lambda: out_root)

    study = validate_study_payload(
        {
            "study_id": "cn_stock_etf/demo_theme_replacement",
            "title": "Demo",
            "asset_scope": "cn_stock_etf",
            "baseline_id": "CN_STOCK_ETF_COMBO_BASELINE_V3",
            "hypothesis": "demo",
            "change_scope": {"modules_modified": ["demo"]},
            "variants": [{"name": "B01_PROTECTED_SHADOW"}],
            "windows": [{"key": "1626", "role": "main", "start": "2016-01-01", "end": "2026-05-08"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "study_conclusion"],
        }
    )
    result = tprs.run_theme_protected_replacement_study(
        study=study,
        plan=[
            {
                "window_key": "1626",
                "window_role": "main",
                "variant_name": "B01_PROTECTED_SHADOW",
                "request_payload": {
                    "start_date": "2016-01-01",
                    "end_date": "2026-05-08",
                    "runner_params": {
                        "input_artifact_dir": str(source),
                        "source_coverage_start": "2016-01-01",
                        "source_coverage_end": "2026-05-08",
                        "min_b01_plan_rows": {"1626": 1},
                    },
                },
            }
        ],
    )

    run = result["runs"][0]
    assert run["research_only"] is True
    assert run["not_nav_backtest"] is True
    assert run["exp_id"] == ""
    assert run["summary"]["b01_daily_plan_rows"] == 2
    assert run["summary"]["core_tech_sell_rows"] == 0
    assert run["verdict"]["status"] == "confirmed"
    assert Path(run["machine_outputs"]["summary"]).exists()
    assert Path(run["human_outputs"]["summary"]).exists()


def test_theme_protected_runner_marks_partial_coverage_inconclusive(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    _write_source_bundle(source)
    monkeypatch.setattr(tprs, "outputs_root", lambda: tmp_path / "outputs" / "studies")

    study = validate_study_payload(
        {
            "study_id": "cn_stock_etf/demo_partial",
            "title": "Demo",
            "asset_scope": "cn_stock_etf",
            "baseline_id": "CN_STOCK_ETF_COMBO_BASELINE_V3",
            "hypothesis": "demo",
            "change_scope": {"modules_modified": ["demo"]},
            "variants": [{"name": "B01_PROTECTED_SHADOW"}],
            "windows": [{"key": "1217", "role": "hard_gate", "start": "2012-01-04", "end": "2017-12-29"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "study_conclusion"],
        }
    )
    result = tprs.run_theme_protected_replacement_study(
        study=study,
        plan=[
            {
                "window_key": "1217",
                "window_role": "hard_gate",
                "variant_name": "B01_PROTECTED_SHADOW",
                "request_payload": {
                    "start_date": "2012-01-04",
                    "end_date": "2017-12-29",
                    "runner_params": {
                        "input_artifact_dir": str(source),
                        "source_coverage_start": "2016-01-01",
                        "source_coverage_end": "2026-05-08",
                    },
                },
            }
        ],
    )

    run = result["runs"][0]
    assert run["summary"]["coverage_complete"] is False
    assert run["verdict"]["status"] == "inconclusive"


def test_study_runner_delegates_to_theme_protected_runner(monkeypatch) -> None:
    study = validate_study_payload(
        {
            "study_id": "cn_stock_etf/demo_delegate",
            "title": "Demo",
            "asset_scope": "cn_stock_etf",
            "baseline_id": "CN_STOCK_ETF_COMBO_BASELINE_V3",
            "hypothesis": "demo",
            "change_scope": {"modules_modified": ["demo"]},
            "variants": [{"name": "B01_PROTECTED_SHADOW"}],
            "windows": [{"key": "1626", "role": "main", "start": "2016-01-01", "end": "2026-05-08"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "study_conclusion"],
            "metadata": {"runner_mode": "cn_stock_etf_theme_protected_replacement"},
        }
    )
    captured: dict[str, object] = {}

    def _fake_runner(**kwargs):
        captured.update(kwargs)
        return {"status": "theme_runner_only"}

    monkeypatch.setattr(study_runner, "run_theme_protected_replacement_study", _fake_runner)
    result = study_runner.run_study(study, only_window_keys=["1626"], only_variant_names=["B01_PROTECTED_SHADOW"])

    assert result["status"] == "theme_runner_only"
    assert captured["study"] == study
    assert isinstance(captured["plan"], list) and len(captured["plan"]) == 1
