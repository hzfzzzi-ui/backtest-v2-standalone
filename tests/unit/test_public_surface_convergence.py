from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.api.endpoints import _experiment_history, _experiment_runner_api, _public_contracts, backtest_v2


def _minimal_manifest(*, exp_id: str, include_nav: bool = True) -> dict[str, object]:
    artifacts = {
        "perf": "perf.json",
        "run_meta": "run_meta.json",
        "config": "config.json",
    }
    if include_nav:
        artifacts["nav"] = "nav.csv"
    return {
        "exp_id": exp_id,
        "experiment_id": exp_id,
        "artifacts": artifacts,
        "core_artifacts": dict(artifacts),
    }


def _write_minimal_experiment(
    root: Path,
    exp_id: str,
    *,
    include_manifest: bool = True,
    include_nav: bool = True,
) -> Path:
    exp_dir = root / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    (exp_dir / "perf.json").write_text(
        json.dumps(
            {
                "cagr": 0.1,
                "sharpe": 1.2,
                "max_drawdown": -0.2,
                "total_return": 0.3,
                "trades": 5,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (exp_dir / "nav.csv").write_text("date,nav\n2024-01-01,1.0\n2024-01-02,1.1\n", encoding="utf-8")
    (exp_dir / "run_meta.json").write_text("{}", encoding="utf-8")
    (exp_dir / "config.json").write_text("{}", encoding="utf-8")
    if include_manifest:
        manifest = _minimal_manifest(exp_id=exp_id, include_nav=include_nav)
        (exp_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return exp_dir


def test_public_run_requires_config_json_unless_locked_candidate() -> None:
    with pytest.raises(HTTPException) as exc:
        _experiment_runner_api._validate_public_run_request(_experiment_runner_api.BacktestV2ExperimentRequest())
    assert exc.value.status_code == 400
    assert exc.value.detail["reason"] == "config_json_required"

    _experiment_runner_api._validate_public_run_request(
        _experiment_runner_api.BacktestV2ExperimentRequest(
            preset="v2-breakout-atr-stop-k10-candidate",
        )
    )


def test_public_run_rejects_legacy_config_fields() -> None:
    with pytest.raises(HTTPException) as exc:
        _experiment_runner_api._validate_public_run_request(
            _experiment_runner_api.BacktestV2ExperimentRequest(
                config_json={"schema_version": "frontend_semantic_config@1"},
                config_id="cfg_legacy",
                runtime_config_json={"runtime": True},
                signal_generation={"modules": [{"name": "breakout_55"}]},
                signal_composition={"compose_mode": "REGIME_ROUTE"},
            )
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["reason"] == "legacy_config_fields_not_allowed"
    assert set(exc.value.detail["rejected_fields"]) >= {
        "config_id",
        "runtime_config_json",
        "signal_generation",
        "signal_composition",
    }


def test_internal_request_accepts_multi_alpha_blocks() -> None:
    req = _experiment_runner_api.BacktestV2ExperimentRequest(
        signal_generation={
            "modules": [
                {"name": "breakout_55", "alpha_id": "breakout_55"},
                {"name": "rsi_reversal", "alpha_id": "rsi_rev_6_20_80"},
            ]
        },
        signal_composition={
            "compose_mode": "REGIME_ROUTE",
            "same_symbol_policy": "PREFER_HIGHER_SCORE",
            "holding_ownership": "SOURCE_ONLY",
        },
    )
    assert req.signal_generation["modules"][0]["name"] == "breakout_55"
    assert req.signal_composition["compose_mode"] == "REGIME_ROUTE"


def test_public_run_response_is_experiment_id_first(monkeypatch) -> None:
    monkeypatch.setattr(
        _experiment_runner_api,
        "_run_backtest_v2_experiment_sync",
        lambda body: {
            "exp_id": "exp_sync",
            "status": "OK",
            "manifest": {"baseline_compare_status": "PASS"},
        },
    )
    payload = _experiment_runner_api.run_backtest_v2_experiment(
        _experiment_runner_api.BacktestV2ExperimentRequest(config_json={"schema_version": "frontend_semantic_config@1"})
    )
    assert payload == {
        "experiment_id": "exp_sync",
        "exp_id": "exp_sync",
        "status": "OK",
        "baseline_compare_status": "PASS",
        "endpoints": {
            "manifest": "/api/backtest_v2/experiments/exp_sync/manifest",
        },
    }


def test_execution_preview_contract_forbids_legacy_fields() -> None:
    with pytest.raises(ValidationError):
        backtest_v2.BacktestV2ExecutionPreviewRequest(
            config_json={"schema_version": "frontend_semantic_config@1"},
            exp_id="exp_preview",
            results_dir="outputs/experiments/exp_preview",
        )


def test_public_run_contract_forbids_legacy_surface_fields() -> None:
    with pytest.raises(ValidationError):
        _public_contracts.PublicBacktestV2ExperimentRequest(
            config_json={"schema_version": "frontend_semantic_config@1"},
            workbench_mode="draft",
        )


def test_artifact_read_contract_requires_exp_id_only() -> None:
    with pytest.raises(ValidationError):
        backtest_v2.BacktestV2ArtifactReadRequest(
            exp_id="exp_artifact",
            results_dir="outputs/experiments/exp_artifact",
            rel_path="perf.json",
        )


def test_legacy_public_result_route_is_retired() -> None:
    paths = {route.path for route in backtest_v2.router.routes}
    assert "/api/backtest_v2/results/{run_id}" not in paths


def test_public_report_route_is_retired() -> None:
    paths = {route.path for route in backtest_v2.router.routes}
    assert "/api/backtest_v2/experiments/{exp_id}/report" not in paths


def test_wave1_legacy_helpers_are_removed() -> None:
    for name in (
        "_read_result",
        "_resolve_experiment_dir",
        "_preview_rejected_fields",
        "_load_runtime_cfg_obj",
    ):
        assert not hasattr(backtest_v2, name)


def test_artifact_read_requires_manifest_declared_path(tmp_path: Path, monkeypatch) -> None:
    exp_dir = _write_minimal_experiment(tmp_path, "exp_artifact")
    manifest = json.loads((exp_dir / "manifest.json").read_text(encoding="utf-8"))
    (exp_dir / "secret.txt").write_text("hidden", encoding="utf-8")

    monkeypatch.setattr(backtest_v2, "_load_manifest_or_404", lambda exp_id: (exp_dir, manifest))

    ok_payload = backtest_v2.read_backtest_v2_artifact(
        backtest_v2.BacktestV2ArtifactReadRequest(exp_id="exp_artifact", rel_path="perf.json")
    )
    assert ok_payload["kind"] == "json"
    assert ok_payload["data"]["cagr"] == 0.1

    with pytest.raises(HTTPException) as exc:
        backtest_v2.read_backtest_v2_artifact(
            backtest_v2.BacktestV2ArtifactReadRequest(exp_id="exp_artifact", rel_path="secret.txt")
        )
    assert exc.value.status_code == 400
    assert "not declared by manifest" in str(exc.value.detail)


def test_history_list_prunes_entries_without_manifest(tmp_path: Path, monkeypatch) -> None:
    exp_root = tmp_path / "experiments"
    exp_root.mkdir(parents=True, exist_ok=True)
    _write_minimal_experiment(exp_root, "exp_ok")
    (exp_root / "exp_no_manifest").mkdir(parents=True, exist_ok=True)
    (exp_root / "index.json").write_text(
        json.dumps(
            [
                {"exp_id": "exp_ok", "created_at": "2026-03-08T01:00:00"},
                {"exp_id": "exp_no_manifest", "created_at": "2026-03-08T01:01:00"},
                {"exp_id": "exp_missing_dir", "created_at": "2026-03-08T01:02:00"},
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(_experiment_history, "_experiments_root", lambda: exp_root)

    items = _experiment_history.list_experiments()
    assert [item["exp_id"] for item in items] == ["exp_ok"]
    assert items[0]["has_manifest"] is True

    persisted = json.loads((exp_root / "index.json").read_text(encoding="utf-8"))
    assert [item["exp_id"] for item in persisted] == ["exp_ok"]


def test_compare_experiments_uses_manifest_and_skips_incomplete(tmp_path: Path, monkeypatch) -> None:
    exp_root = tmp_path / "experiments"
    exp_root.mkdir(parents=True, exist_ok=True)
    _write_minimal_experiment(exp_root, "exp_a")
    _write_minimal_experiment(exp_root, "exp_b")
    _write_minimal_experiment(exp_root, "exp_c", include_nav=False)
    (exp_root / "index.json").write_text(
        json.dumps(
            [
                {"exp_id": "exp_a", "label": "A", "created_at": "2026-03-08T01:00:00"},
                {"exp_id": "exp_b", "label": "B", "created_at": "2026-03-08T01:01:00"},
                {"exp_id": "exp_c", "label": "C", "created_at": "2026-03-08T01:02:00"},
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(_experiment_history, "_experiments_root", lambda: exp_root)

    payload = _experiment_history.compare_experiments({"exp_ids": ["exp_a", "exp_b", "exp_c"]})
    assert [item["exp_id"] for item in payload["items"]] == ["exp_a", "exp_b"]
    assert payload["skipped"] == [{"exp_id": "exp_c", "reason": "missing_manifest_core_artifacts"}]
