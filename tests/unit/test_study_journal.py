from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.research import study_journal


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")


def test_study_journal_creates_round_and_deterministic_summary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STUDY_JOURNAL_ROOT", str(tmp_path / "journal"))
    monkeypatch.setenv("RESULTS_ROOT", str(tmp_path / "outputs"))
    _write_jsonl(
        tmp_path / "outputs" / "studies" / "conclusions" / "demo" / "registry.jsonl",
        [
            {
                "recorded_at": "2026-05-10T10:00:00",
                "study_id": "demo/study",
                "compared_baseline_id": "BASE",
                "verdict": "confirmed",
                "gate_status": "PASS",
                "summary_short": "confirmed | window=1626 | variant=B1",
                "exp_id": "exp_demo_001",
                "window_key": "1626",
                "variant_name": "B1",
                "key_metrics": {
                    "cagr": {"candidate": 0.12, "baseline": 0.10, "delta": 0.02},
                    "sharpe": {"candidate": 0.8, "baseline": 0.7, "delta": 0.1},
                },
            }
        ],
    )

    item = study_journal.save_round(
        {
            "round_id": "sr_demo_001",
            "title": "ETF pool demo",
            "study_id": "demo/study",
            "baseline_id": "BASE",
            "primary_variable": "ETF universe",
            "windows": ["1626"],
            "variants": ["B1"],
            "evidence": [{"kind": "experiment", "exp_id": "exp_demo_001", "window_key": "1626", "variant_name": "B1"}],
            "audit": {"same_window_compare": True, "config_truth_checked": True, "nav_lineage_checked": True},
        }
    )

    assert item["round_id"] == "sr_demo_001"
    assert item["auto_summary"]["evidence_counts"]["linked"] == 1
    assert item["auto_summary"]["evidence_counts"]["matched_conclusions"] == 1
    assert item["auto_summary"]["verdict_counts"] == {"CONFIRMED": 1}
    assert item["auto_summary"]["gate_status_counts"] == {"PASS": 1}
    assert item["auto_summary"]["metric_highlights"][0]["cagr"]["delta"] == 0.02
    assert (tmp_path / "journal" / "rounds" / "sr_demo_001.json").exists()


def test_study_journal_rejects_unsafe_round_id(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STUDY_JOURNAL_ROOT", str(tmp_path / "journal"))

    with pytest.raises(ValueError):
        study_journal.round_path("../escape")


def test_study_journal_append_note_and_link_experiment_refresh_summary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STUDY_JOURNAL_ROOT", str(tmp_path / "journal"))
    monkeypatch.setenv("RESULTS_ROOT", str(tmp_path / "outputs"))
    _write_jsonl(
        tmp_path / "outputs" / "studies" / "conclusions" / "demo" / "registry.jsonl",
        [
            {
                "recorded_at": "2026-05-10T10:00:00",
                "study_id": "demo/study",
                "verdict": "PASS",
                "exp_id": "exp_demo_002",
                "window_key": "1217",
                "variant_name": "B2",
                "key_metrics": {},
            }
        ],
    )
    study_journal.save_round({"round_id": "sr_demo_002", "title": "Demo", "study_id": "demo/study"})

    with_note = study_journal.append_note("sr_demo_002", {"body": "needs hard gate"})
    assert with_note["notes"][0]["body"] == "needs hard gate"

    linked = study_journal.link_experiment(
        "sr_demo_002",
        {"exp_id": "exp_demo_002", "window_key": "1217", "variant_name": "B2"},
    )
    assert len(linked["evidence"]) == 1
    assert linked["auto_summary"]["evidence_counts"]["matched_conclusions"] == 1
    assert linked["auto_summary"]["verdict_counts"] == {"LEGACY_PASS": 1}
    assert linked["auto_summary"]["gate_status_counts"] == {"PASS": 1}
    assert linked["reliability"] in {"partial", "reviewable", "low"}


def test_study_journal_three_window_ready_round_is_reviewable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STUDY_JOURNAL_ROOT", str(tmp_path / "journal"))
    monkeypatch.setenv("RESULTS_ROOT", str(tmp_path / "outputs"))
    windows = ["2016_2026", "2012_2017", "2012_2026"]
    _write_jsonl(
        tmp_path / "outputs" / "studies" / "conclusions" / "demo" / "registry.jsonl",
        [
            {
                "recorded_at": f"2026-05-10T10:0{idx}:00",
                "study_id": "demo/three_window",
                "compared_baseline_id": "BASE",
                "verdict": "confirmed",
                "gate_status": "PASS",
                "summary_short": f"confirmed | window={window} | variant=B1",
                "exp_id": f"exp_demo_{idx}",
                "window_key": window,
                "variant_name": "B1",
                "key_metrics": {"cagr": {"candidate": 0.12, "baseline": 0.10, "delta": 0.02}},
            }
            for idx, window in enumerate(windows, start=1)
        ],
    )

    item = study_journal.save_round(
        {
            "round_id": "sr_demo_three_window",
            "title": "Three Window Demo",
            "study_id": "demo/three_window",
            "baseline_id": "BASE",
            "windows": windows,
            "variants": ["B1"],
            "evidence": [
                {"kind": "experiment", "exp_id": f"exp_demo_{idx}", "window_key": window, "variant_name": "B1"}
                for idx, window in enumerate(windows, start=1)
            ],
            "audit": {"same_window_compare": True, "config_truth_checked": True, "nav_lineage_checked": True},
        }
    )

    assert item["reliability"] == "reviewable"
    assert item["auto_summary"]["window_coverage"] == ["2012-2017", "2012-2026", "2016-2026"]
    assert item["auto_summary"]["gate_status_counts"] == {"PASS": 3}
    assert "三窗口证据尚不完整，不能作为 baseline 升级依据。" not in item["auto_summary"]["risks"]
