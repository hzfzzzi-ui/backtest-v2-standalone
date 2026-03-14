from __future__ import annotations

from pathlib import Path

from backend.core.services.market_snapshot_service import MarketSnapshotArtifacts
from backend.scripts import build_market_snapshot as script


def test_build_market_snapshot_script_returns_summary(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "market_snapshots" / "2026-03-10"
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_dir / "market_snapshot.json"
    brief_path = output_dir / "market_brief.md"
    snapshot_path.write_text("{}", encoding="utf-8")
    brief_path.write_text("# brief", encoding="utf-8")

    def _fake_build_market_snapshot_artifacts(**kwargs):
        assert kwargs["trade_date"] == "2026-03-10"
        return MarketSnapshotArtifacts(
            snapshot={"trade_date": "2026-03-10", "build_status": "partial", "warnings": [{"code": "STALE"}]},
            brief_markdown="# brief",
            output_dir=output_dir,
            snapshot_path=snapshot_path,
            brief_path=brief_path,
        )

    monkeypatch.setattr(script, "build_market_snapshot_artifacts", _fake_build_market_snapshot_artifacts)
    summary = script.main(["--trade-date", "2026-03-10", "--output-dir", str(output_dir)])

    assert summary["trade_date"] == "2026-03-10"
    assert summary["build_status"] == "partial"
    assert summary["warning_count"] == 1
    assert summary["snapshot_path"] == str(snapshot_path)
