from __future__ import annotations

import os
from pathlib import Path


def write_report_to_local(filename: str, content: str) -> Path:
    out_dir_env = str(os.getenv("PAMS_REPORTS_DIR", "")).strip()
    if out_dir_env:
        out_dir = Path(out_dir_env).resolve()
    else:
        repo_root = Path(__file__).resolve().parents[3]
        out_dir = repo_root / "outputs" / "report"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path
