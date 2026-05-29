from __future__ import annotations

import json

from backend.cli import main as cli_main


def test_cli_audit_lists_baseline_regression_target(capsys) -> None:
    exit_code = cli_main.main(["audit", "--list-targets"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert "baseline_regression" in payload["targets"]
