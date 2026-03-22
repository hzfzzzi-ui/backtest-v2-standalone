from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.core.services import experiment_history_service


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


def test_history_service_list_prunes_orphans_and_updates_index(tmp_path: Path) -> None:
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

    items = experiment_history_service.list_experiments(experiments_root=exp_root)

    assert [item["exp_id"] for item in items] == ["exp_ok"]
    assert items[0]["has_manifest"] is True
    persisted = json.loads((exp_root / "index.json").read_text(encoding="utf-8"))
    assert [item["exp_id"] for item in persisted] == ["exp_ok"]


def test_history_service_compare_keeps_public_response_semantics(tmp_path: Path) -> None:
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

    payload = experiment_history_service.compare_experiments(
        {"exp_ids": ["exp_a", "exp_b", "exp_c"]},
        experiments_root=exp_root,
    )

    assert [item["exp_id"] for item in payload["items"]] == ["exp_a", "exp_b"]
    assert payload["items"][0]["perf"]["cagr"] == 0.1
    assert payload["skipped"] == [{"exp_id": "exp_c", "reason": "missing_manifest_core_artifacts"}]


def test_history_service_compare_rejects_underfilled_requests(tmp_path: Path) -> None:
    exp_root = tmp_path / "experiments"
    exp_root.mkdir(parents=True, exist_ok=True)

    with pytest.raises(HTTPException) as exc:
        experiment_history_service.compare_experiments({"exp_ids": ["exp_only"]}, experiments_root=exp_root)

    assert exc.value.status_code == 400
