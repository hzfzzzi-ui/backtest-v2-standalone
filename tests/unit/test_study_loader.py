from __future__ import annotations

from pathlib import Path

import pytest

from backend.research import study_loader
from backend.research.study_definition import StudyValidationError


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_study_definition_from_explicit_path(tmp_path: Path) -> None:
    study_path = tmp_path / "demo.study.yaml"
    _write_text(
        study_path,
        "\n".join(
                [
                    "study_id: v10/demo",
                    "title: Demo",
                    "asset_scope: cn_a_equity",
                    "baseline_id: baseline_V10_1",
                    "hypothesis: hypothesis",
                    "change_scope: {}",
                "variants:",
                "  - name: B0",
                "    config_patches:",
                "      - path: signal_generation.ranking.residual_window",
                "        value: 40",
                "windows:",
                "  - key: main",
                "    role: main",
                "    start: '2024-01-01'",
                "    end: '2024-02-01'",
                "hard_gates:",
                "  min_cagr: 0.1",
                "required_outputs:",
                "  - machine_bundle",
                "  - human_bundle",
                "  - baseline_append",
                "request_template:",
                "  fast_mode: true",
            ]
        ),
    )

    study = study_loader.load_study_definition(study_path)
    assert study.study_id == "v10/demo"
    assert study.variants[0].config_patches[0].path == "signal_generation.ranking.residual_window"


def test_load_study_definition_rejects_missing_required_fields(tmp_path: Path) -> None:
    study_path = tmp_path / "broken.study.yaml"
    _write_text(
        study_path,
        "\n".join(
            [
                "study_id: broken",
                "title: Broken",
                "baseline_id: baseline_V10_1",
                "change_scope: {}",
                "variants:",
                "  - name: B0",
                "windows:",
                "  - key: main",
                "    role: main",
                "    start: '2024-01-01'",
                "    end: '2024-02-01'",
                "hard_gates: {}",
                "required_outputs:",
                "  - machine_bundle",
            ]
        ),
    )

    with pytest.raises(StudyValidationError):
        study_loader.load_study_definition(study_path)


def test_load_repo_study_by_id() -> None:
    study = study_loader.load_study_definition("v10/industry_second_stage_s7")
    assert study.study_id == "v10/industry_second_stage_s7"
    assert len(study.variants) >= 3
