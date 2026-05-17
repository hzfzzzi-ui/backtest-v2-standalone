from __future__ import annotations

import json
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")


def test_study_journal_api_create_link_note_and_list(test_client, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STUDY_JOURNAL_ROOT", str(tmp_path / "journal"))
    monkeypatch.setenv("RESULTS_ROOT", str(tmp_path / "outputs"))
    _write_jsonl(
        tmp_path / "outputs" / "studies" / "conclusions" / "demo" / "registry.jsonl",
        [
            {
                "recorded_at": "2026-05-10T10:00:00",
                "study_id": "demo/study",
                "verdict": "confirmed",
                "gate_status": "PASS",
                "summary_short": "confirmed | window=1626 | variant=B1",
                "exp_id": "exp_api_001",
                "window_key": "1626",
                "variant_name": "B1",
                "key_metrics": {"cagr": {"candidate": 0.12, "baseline": 0.10, "delta": 0.02}},
            }
        ],
    )

    created = test_client.post(
        "/api/research/study-rounds",
        json={
            "round_id": "sr_api_001",
            "title": "API journal",
            "study_id": "demo/study",
            "baseline_id": "BASE",
            "primary_variable": "ETF universe",
        },
    )
    assert created.status_code == 200
    assert created.json()["item"]["round_id"] == "sr_api_001"

    linked = test_client.post(
        "/api/research/study-rounds/sr_api_001/links/experiment",
        json={"exp_id": "exp_api_001", "window_key": "1626", "variant_name": "B1"},
    )
    assert linked.status_code == 200
    assert linked.json()["item"]["auto_summary"]["evidence_counts"]["matched_conclusions"] == 1

    noted = test_client.post("/api/research/study-rounds/sr_api_001/notes", json={"body": "audit later"})
    assert noted.status_code == 200
    assert noted.json()["item"]["notes"][0]["body"] == "audit later"

    listed = test_client.get("/api/research/study-rounds")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["round_id"] == "sr_api_001"

    conclusions = test_client.get("/api/research/study-conclusions?study_id=demo/study")
    assert conclusions.status_code == 200
    assert conclusions.json()["items"][0]["exp_id"] == "exp_api_001"


def test_study_journal_page_route(test_client) -> None:
    response = test_client.get("/study-journal")
    assert response.status_code == 200
    assert "study-journal.js" in response.text
