from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from backend.core.tools.experiment_runner import run_experiment


def run_bundle(
    bundle: str,
    config_path: str,
    overrides: dict[str, Any] | None = None,
    progress_hook: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    key = str(bundle or "").strip().upper()
    if key != "ATR_VALIDATE_BUNDLE_V1":
        raise ValueError(f"unsupported bundle: {bundle}")
    overrides = overrides or {}

    if progress_hook:
        progress_hook(8, "Bundle Step1/3：ATR_PARAM_VALIDATE_v1")
    step1 = run_experiment(config_path, "ATR_PARAM_VALIDATE_v1", dict(overrides), progress_hook=progress_hook)
    if progress_hook:
        progress_hook(38, "Bundle Step2/3：ATR_PARAM_VALIDATE_WF3")
    step2 = run_experiment(config_path, "ATR_PARAM_VALIDATE_WF3", dict(overrides), progress_hook=progress_hook)
    if progress_hook:
        progress_hook(68, "Bundle Step3/3：ATR_PARAM_VALIDATE_UNIVOTE")
    step3 = run_experiment(config_path, "ATR_PARAM_VALIDATE_UNIVOTE", dict(overrides), progress_hook=progress_hook)

    bundle_dir = Path(step1["results_dir"]).parent / f"bundle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "bundle": key,
        "step1": step1,
        "step2": step2,
        "step3": step3,
    }
    (bundle_dir / "bundle_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (bundle_dir / "bundle_summary.md").write_text(
        "\n".join(
            [
                "# ATR Validate Bundle v1",
                "",
                f"- step1: `{step1['results_dir']}`",
                f"- step2: `{step2['results_dir']}`",
                f"- step3: `{step3['results_dir']}`",
                "",
                "## Final Recommendation",
                "- check step2 walkforward_report.md first, then confirm with step3 universe_vote_report.md",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"bundle": key, "bundle_dir": str(bundle_dir), "step1": step1, "step2": step2, "step3": step3}
