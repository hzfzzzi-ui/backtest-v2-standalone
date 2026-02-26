from __future__ import annotations

import json
from pathlib import Path

from backend.api.endpoints.backtest_v2 import BacktestV2RunRequest, _write_data_validation_section


def test_run_report_includes_data_validation(tmp_path: Path) -> None:
    bt_root = tmp_path / "backtest_V2"
    run_dir = bt_root / "results" / "run_x"
    run_dir.mkdir(parents=True, exist_ok=True)
    report_path = run_dir / "report.json"
    report_path.write_text(json.dumps({"summary": {"trades": 1}}, ensure_ascii=False), encoding="utf-8")

    req = BacktestV2RunRequest(
        start_date="2025-10-01",
        end_date="2026-02-01",
        symbols=["600000.SH"],
        benchmark="000300.SH",
        validation_request_id="val_abc",
        validation_passed=True,
        validation_warnings=["LIMIT_FIELD_INCONSISTENCY: high>limit_up count=1"],
    )

    _write_data_validation_section(run_dir, req, bt_root)
    out = json.loads(report_path.read_text(encoding="utf-8"))
    assert "data_validation" in out
    assert out["data_validation"]["request_id"] == "val_abc"
    assert out["data_validation"]["passed"] is True
    assert out["data_validation"]["warnings"] == ["LIMIT_FIELD_INCONSISTENCY: high>limit_up count=1"]
