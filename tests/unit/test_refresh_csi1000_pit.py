from __future__ import annotations

from pathlib import Path

from backend.cli.managed.refresh_csi1000_pit import (
    build_fetch_command,
    build_import_command,
    build_manual_command,
    run_refresh,
)


def test_build_fetch_command_respects_guard_flags(tmp_path: Path) -> None:
    cmd = build_fetch_command(
        calendar=tmp_path / "calendar.csv",
        provider="tushare",
        out_dir=tmp_path / "data_cache",
        summary_out=tmp_path / "fetch_summary.json",
        expected_count=1000,
        lookahead_days=10,
        allow_count_mismatch=True,
        allow_static_fallback=False,
    )

    joined = " ".join(cmd)
    assert "fetch_csi1000_pit_by_calendar.py" in joined
    assert "--provider tushare" in joined
    assert "--allow-count-mismatch" in joined
    assert "--allow-static-fallback" not in joined


def test_build_import_command_can_override_source_label(tmp_path: Path) -> None:
    cmd = build_import_command(
        changes_csv=tmp_path / "changes.csv",
        snapshots_csv=tmp_path / "snapshots.csv",
        summary_out=tmp_path / "import_summary.json",
        source_label="manual_override",
    )

    joined = " ".join(cmd)
    assert "import_csi1000_pit.py" in joined
    assert "--snapshots-csv" in joined
    assert "--source-label manual_override" in joined


def test_build_manual_command_targets_manual_snapshot_builder(tmp_path: Path) -> None:
    cmd = build_manual_command(
        manifest=tmp_path / "manifest.csv",
        out_dir=tmp_path / "data_cache",
        summary_out=tmp_path / "manual_summary.json",
        expected_count=1000,
        allow_count_mismatch=False,
    )

    joined = " ".join(cmd)
    assert "build_csi1000_pit_from_manual_snapshots.py" in joined
    assert "--manifest" in joined
    assert "--summary-out" in joined


def test_run_refresh_executes_fetch_then_import(monkeypatch, tmp_path: Path) -> None:
    seen: list[list[str]] = []

    def _fake_run(cmd: list[str]) -> None:
        seen.append(cmd)

    monkeypatch.setattr(
        "backend.cli.managed.refresh_csi1000_pit._run_command_with_env",
        lambda cmd, extra_env=None: seen.append(cmd),
    )
    monkeypatch.setattr("backend.cli.managed.refresh_csi1000_pit._run_command", _fake_run)
    monkeypatch.setattr("backend.cli.managed.refresh_csi1000_pit._resolve_tushare_token", lambda explicit=None: "secret-token")

    summary = run_refresh(
        calendar=tmp_path / "calendar.csv",
        provider="auto",
        out_dir=tmp_path / "data_cache",
        ops_dir=tmp_path / "ops",
        expected_count=1000,
        lookahead_days=10,
        allow_count_mismatch=False,
        allow_static_fallback=False,
        skip_import=False,
    )

    assert len(seen) == 2
    assert "fetch_csi1000_pit_by_calendar.py" in " ".join(seen[0])
    assert "--provider tushare" in " ".join(seen[0])
    assert "import_csi1000_pit.py" in " ".join(seen[1])
    assert summary["skip_import"] is False
    assert summary["token_available"] is True
    assert summary["outputs"]["snapshots_csv"].endswith("csi1000_pit_calendar_snapshots.csv")
    assert summary["outputs"]["refresh_summary"].endswith("csi1000_pit_refresh_summary.json")


def test_run_refresh_can_skip_import(monkeypatch, tmp_path: Path) -> None:
    seen: list[list[str]] = []

    def _fake_run(cmd: list[str]) -> None:
        seen.append(cmd)

    monkeypatch.setattr(
        "backend.cli.managed.refresh_csi1000_pit._run_command_with_env",
        lambda cmd, extra_env=None: seen.append(cmd),
    )
    monkeypatch.setattr("backend.cli.managed.refresh_csi1000_pit._run_command", _fake_run)
    monkeypatch.setattr("backend.cli.managed.refresh_csi1000_pit._resolve_tushare_token", lambda explicit=None: "")

    summary = run_refresh(
        calendar=tmp_path / "calendar.csv",
        provider="auto",
        out_dir=tmp_path / "data_cache",
        ops_dir=tmp_path / "ops",
        expected_count=1000,
        lookahead_days=10,
        allow_count_mismatch=False,
        allow_static_fallback=True,
        skip_import=True,
    )

    assert len(seen) == 1
    assert "fetch_csi1000_pit_by_calendar.py" in " ".join(seen[0])
    assert summary["commands"]["import"] is None
    assert summary["outputs"]["import_summary"] is None
    assert summary["outputs"]["snapshots_csv"].endswith("csi1000_pit_calendar_snapshots.csv")


def test_run_refresh_manual_manifest_executes_build_then_import(monkeypatch, tmp_path: Path) -> None:
    seen: list[list[str]] = []

    def _fake_run(cmd: list[str]) -> None:
        seen.append(cmd)

    monkeypatch.setattr(
        "backend.cli.managed.refresh_csi1000_pit._run_command_with_env",
        lambda cmd, extra_env=None: seen.append(cmd),
    )
    monkeypatch.setattr("backend.cli.managed.refresh_csi1000_pit._run_command", _fake_run)
    monkeypatch.setattr("backend.cli.managed.refresh_csi1000_pit._resolve_tushare_token", lambda explicit=None: "")

    summary = run_refresh(
        calendar=tmp_path / "calendar.csv",
        provider="manual_manifest",
        out_dir=tmp_path / "data_cache",
        ops_dir=tmp_path / "ops",
        expected_count=1000,
        lookahead_days=10,
        allow_count_mismatch=False,
        allow_static_fallback=False,
        manual_manifest=tmp_path / "manifest.csv",
        skip_import=False,
    )

    assert len(seen) == 2
    assert "build_csi1000_pit_from_manual_snapshots.py" in " ".join(seen[0])
    assert "import_csi1000_pit.py" in " ".join(seen[1])
    assert summary["provider"] == "manual_manifest"
    assert summary["outputs"]["manual_build_summary"] is not None
    assert summary["outputs"]["snapshots_csv"].endswith("csi1000_pit_manual_snapshots.csv")
