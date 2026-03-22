from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.cli.managed.refresh_csi800_pit import (
    build_fetch_command,
    build_import_command,
    build_materialize_command,
    run_refresh,
)


def test_build_fetch_command_targets_csi800_fetcher(tmp_path: Path) -> None:
    cmd = build_fetch_command(out_dir=tmp_path / "data_cache", summary_out=tmp_path / "fetch_summary.json")

    joined = " ".join(cmd)
    assert "fetch_csi800_pit_history.py" in joined
    assert "--summary-out" in joined


def test_build_import_command_targets_csi800_importer(tmp_path: Path) -> None:
    cmd = build_import_command(
        changes_csv=tmp_path / "csi800_pit_history_changes.csv",
        summary_out=tmp_path / "import_summary.json",
    )

    joined = " ".join(cmd)
    assert "import_csi800_pit.py" in joined
    assert str(tmp_path / "csi800_pit_history_changes.csv") in joined
    assert "--replace-existing" in joined


def test_build_materialize_command_targets_formal_history_builder(tmp_path: Path) -> None:
    cmd = build_materialize_command(
        seed_csv=tmp_path / "seed.csv",
        patch_csv=tmp_path / "patch.csv",
        out_dir=tmp_path / "data_cache",
        summary_out=tmp_path / "materialize_summary.json",
        required_start="2007-01-01",
        required_end="2026-03-17",
    )

    joined = " ".join(cmd)
    assert "build_csi800_formal_history.py" in joined
    assert "--seed-csv" in joined
    assert "--patch-csv" in joined


def test_run_refresh_executes_fetch_then_import(monkeypatch, tmp_path: Path) -> None:
    seen: list[list[str]] = []

    def _fake_run(cmd: list[str]) -> None:
        seen.append(cmd)
        joined = " ".join(cmd)
        if "fetch_csi800_pit_history.py" in joined:
            (tmp_path / "ops" / "csi800_pit_fetch_summary.json").write_text(
                json.dumps({"first_usable_trade_date": "2007-01-01"}, ensure_ascii=False),
                encoding="utf-8",
            )

    monkeypatch.setattr("backend.cli.managed.refresh_csi800_pit._run_command", _fake_run)

    summary = run_refresh(
        out_dir=tmp_path / "data_cache",
        ops_dir=tmp_path / "ops",
        skip_import=False,
    )

    assert len(seen) == 2
    assert "fetch_csi800_pit_history.py" in " ".join(seen[0])
    assert "import_csi800_pit.py" in " ".join(seen[1])
    assert "--replace-existing" in " ".join(seen[1])
    assert summary["status"] == "ok"
    assert summary["outputs"]["refresh_summary"].endswith("csi800_pit_refresh_summary.json")
    assert summary["outputs"]["changes_csv"].endswith("csi800_pit_history_changes.csv")


def test_run_refresh_can_skip_import(monkeypatch, tmp_path: Path) -> None:
    seen: list[list[str]] = []

    def _fake_run(cmd: list[str]) -> None:
        seen.append(cmd)
        joined = " ".join(cmd)
        if "fetch_csi800_pit_history.py" in joined:
            (tmp_path / "ops" / "csi800_pit_fetch_summary.json").write_text(
                json.dumps({"first_usable_trade_date": "2007-01-01"}, ensure_ascii=False),
                encoding="utf-8",
            )

    monkeypatch.setattr("backend.cli.managed.refresh_csi800_pit._run_command", _fake_run)

    summary = run_refresh(
        out_dir=tmp_path / "data_cache",
        ops_dir=tmp_path / "ops",
        skip_import=True,
    )

    assert len(seen) == 1
    assert "fetch_csi800_pit_history.py" in " ".join(seen[0])
    assert summary["commands"]["import"] is None
    assert summary["outputs"]["import_summary"] is None


def test_run_refresh_blocks_short_history_without_seed(monkeypatch, tmp_path: Path) -> None:
    seen: list[list[str]] = []

    def _fake_run(cmd: list[str]) -> None:
        seen.append(cmd)
        joined = " ".join(cmd)
        if "fetch_csi800_pit_history.py" in joined:
            (tmp_path / "ops" / "csi800_pit_fetch_summary.json").write_text(
                json.dumps({"first_usable_trade_date": "2025-08-29"}, ensure_ascii=False),
                encoding="utf-8",
            )

    monkeypatch.setattr("backend.cli.managed.refresh_csi800_pit._run_command", _fake_run)
    monkeypatch.setattr(
        "backend.cli.managed.refresh_csi800_pit._bootstrap_seed_csv_from_existing_db",
        lambda **_: (None, {"status": "unavailable"}),
    )

    with pytest.raises(RuntimeError, match="provide --seed-csv"):
        run_refresh(
            out_dir=tmp_path / "data_cache",
            ops_dir=tmp_path / "ops",
            skip_import=False,
        )

    refresh_summary = json.loads((tmp_path / "ops" / "csi800_pit_refresh_summary.json").read_text(encoding="utf-8"))
    assert refresh_summary["status"] == "blocked"
    assert refresh_summary["reason"] == "fetch_missing_required_start"
    assert len(seen) == 1


def test_run_refresh_materializes_when_seed_is_provided(monkeypatch, tmp_path: Path) -> None:
    seen: list[list[str]] = []
    seed_csv = tmp_path / "seed.csv"
    seed_csv.write_text(
        "\n".join(
            [
                "index_code,symbol,in_date,out_date,source",
                "000906.SH,000001.SZ,2007-01-01,,jqdatasdk_pit_snapshot",
            ]
        ),
        encoding="utf-8",
    )

    def _fake_run(cmd: list[str]) -> None:
        seen.append(cmd)
        joined = " ".join(cmd)
        if "fetch_csi800_pit_history.py" in joined:
            (tmp_path / "ops" / "csi800_pit_fetch_summary.json").write_text(
                json.dumps({"first_usable_trade_date": "2025-08-29"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (tmp_path / "data_cache" / "csi800_pit_history_changes.csv").write_text(
                "\n".join(
                    [
                        "index_code,symbol,in_date,out_date,source",
                        "000906.SH,000001.SZ,2025-08-29,,tushare_csi800_history",
                    ]
                ),
                encoding="utf-8",
            )
        elif "build_csi800_formal_history.py" in joined:
            (tmp_path / "ops" / "csi800_pit_materialize_summary.json").write_text(
                json.dumps({"covers_required_start": True}, ensure_ascii=False),
                encoding="utf-8",
            )
            (tmp_path / "data_cache" / "csi800_formal_history_changes.csv").write_text(
                "\n".join(
                    [
                        "index_code,symbol,in_date,out_date,source",
                        "000906.SH,000001.SZ,2007-01-01,,csi800_formal_history",
                    ]
                ),
                encoding="utf-8",
            )

    monkeypatch.setattr("backend.cli.managed.refresh_csi800_pit._run_command", _fake_run)

    summary = run_refresh(
        out_dir=tmp_path / "data_cache",
        ops_dir=tmp_path / "ops",
        skip_import=False,
        seed_csv=seed_csv,
    )

    assert len(seen) == 3
    assert "build_csi800_formal_history.py" in " ".join(seen[1])
    assert summary["outputs"]["changes_csv"].endswith("csi800_formal_history_changes.csv")
    assert summary["outputs"]["materialize_summary"].endswith("csi800_pit_materialize_summary.json")


def test_run_refresh_auto_bootstraps_seed_from_existing_db(monkeypatch, tmp_path: Path) -> None:
    seen: list[list[str]] = []
    auto_seed = tmp_path / "data_cache" / "csi800_formal_history_seed_auto.csv"

    def _fake_run(cmd: list[str]) -> None:
        seen.append(cmd)
        joined = " ".join(cmd)
        if "fetch_csi800_pit_history.py" in joined:
            (tmp_path / "ops" / "csi800_pit_fetch_summary.json").write_text(
                json.dumps({"first_usable_trade_date": "2025-08-29"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (tmp_path / "data_cache" / "csi800_pit_history_changes.csv").write_text(
                "\n".join(
                    [
                        "index_code,symbol,in_date,out_date,source",
                        "000906.SH,000001.SZ,2025-08-29,,tushare_csi800_history",
                    ]
                ),
                encoding="utf-8",
            )
        elif "build_csi800_formal_history.py" in joined:
            (tmp_path / "ops" / "csi800_pit_materialize_summary.json").write_text(
                json.dumps({"covers_required_start": True}, ensure_ascii=False),
                encoding="utf-8",
            )
            (tmp_path / "data_cache" / "csi800_formal_history_changes.csv").write_text(
                "\n".join(
                    [
                        "index_code,symbol,in_date,out_date,source",
                        "000906.SH,000001.SZ,2007-01-01,,csi800_formal_history",
                    ]
                ),
                encoding="utf-8",
            )

    monkeypatch.setattr("backend.cli.managed.refresh_csi800_pit._run_command", _fake_run)
    monkeypatch.setattr(
        "backend.cli.managed.refresh_csi800_pit._bootstrap_seed_csv_from_existing_db",
        lambda **_: (
            auto_seed,
            {"status": "ok", "seed_csv": str(auto_seed), "covers_required_start": True},
        ),
    )

    summary = run_refresh(
        out_dir=tmp_path / "data_cache",
        ops_dir=tmp_path / "ops",
        skip_import=False,
    )

    assert len(seen) == 3
    assert summary["seed_mode"] == "auto_db_export"
    assert summary["seed_csv"].endswith("csi800_formal_history_seed_auto.csv")
    assert summary["outputs"]["changes_csv"].endswith("csi800_formal_history_changes.csv")
