from __future__ import annotations

import json
from pathlib import Path

from backend.cli import main as cli_main
from backend.core.cli import main as legacy_cli_main


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_cli_lists_data_refresh_targets(capsys) -> None:
    exit_code = cli_main.main(["data_refresh", "--list-targets"])
    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert exit_code == 0
    assert payload["targets"] == [
        "csi1000_pit",
        "csi800_pit",
        "pams_ohlcv_daily",
        "pams_ohlcv_daily_v2",
        "pams_ohlcv_daily_v2_audit",
        "pams_ohlcv_daily_v2_formal_audits",
        "pams_ohlcv_daily_v2_full_backfill",
        "pams_ohlcv_daily_v2_raw",
        "pit_index_daily",
        "pit_stock_daily_basic",
        "pit_stock_feature_coverage",
        "pit_stock_moneyflow",
        "pit_stock_moneyflow_v2",
        "security_master",
    ]


def test_cli_study_run_dry_run_loads_yaml(tmp_path: Path, capsys) -> None:
    study_path = tmp_path / "demo.study.yaml"
    _write_text(
        study_path,
        "\n".join(
            [
                "study_id: demo/test",
                "title: Demo Test",
                "asset_scope: cn_a_equity",
                "baseline_id: baseline_V10",
                "hypothesis: test hypothesis",
                "change_scope:",
                "  modules_modified:",
                "    - ranking",
                "variants:",
                "  - name: B0",
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

    exit_code = cli_main.main(["study_run", "--study-path", str(study_path), "--dry-run"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["study"]["study_id"] == "demo/test"
    assert payload["plan"][0]["request_payload"]["start_date"] == "2024-01-01"


def test_cli_experiment_compare_supports_baseline_mode(monkeypatch, capsys) -> None:
    captured: dict[str, str] = {}

    def _fake_compare(*, exp_id: str, baseline_id: str) -> dict[str, str]:
        captured["exp_id"] = exp_id
        captured["baseline_id"] = baseline_id
        return {"status": "ok", "exp_id": exp_id, "baseline_id": baseline_id}

    monkeypatch.setattr("backend.core.services.experiment_compare_service.compare_experiment_to_baseline", _fake_compare)

    exit_code = cli_main.main(["experiment_compare", "exp_demo", "--baseline-id", "baseline_V10"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured == {"exp_id": "exp_demo", "baseline_id": "baseline_V10"}
    assert payload["status"] == "ok"


def test_cli_study_run_can_emit_thin_script(tmp_path: Path, capsys, monkeypatch) -> None:
    study_path = tmp_path / "emit.study.yaml"
    _write_text(
        study_path,
        "\n".join(
            [
                "study_id: v10/demo_emit",
                "title: Emit Demo",
                "asset_scope: cn_a_equity",
                "baseline_id: baseline_V10",
                "hypothesis: test hypothesis",
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
                "  - human_bundle",
                "  - baseline_append",
            ]
        ),
    )

    monkeypatch.setattr("backend.research.thin_script.generated_scripts_root", lambda: tmp_path / "generated")

    exit_code = cli_main.main(["study_run", "--study-path", str(study_path), "--emit-thin-script"])
    payload = json.loads(capsys.readouterr().out)
    generated = Path(payload["generated_script"])
    assert exit_code == 0
    assert generated.exists()
    assert 'main(["study_run", "v10/demo_emit"' in generated.read_text(encoding="utf-8")


def test_legacy_core_cli_delegates_to_unified_cli(capsys) -> None:
    exit_code = legacy_cli_main.main(["data_refresh", "--list-targets"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert "csi1000_pit" in payload["targets"]


def test_cli_surface_readme_declares_official_and_compat_roles() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    readme_path = repo_root / "backend" / "cli" / "README.md"
    text = readme_path.read_text(encoding="utf-8")
    assert "python -m backend.cli" in text
    assert "backend/cli/managed/" in text
    assert "backend/scripts/generated/" in text
    assert "backend/core/cli/" in text
    assert "compatibility-only" in text
