from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.cli.main import main


if __name__ == "__main__":
    raise SystemExit(main(["study_run", "snapshots/stock_alpha_snapshot_backed_demo", *(__import__('sys').argv[1:])]))
