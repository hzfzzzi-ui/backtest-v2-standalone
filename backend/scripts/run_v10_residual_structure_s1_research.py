from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.cli.main import main


if __name__ == "__main__":
    raise SystemExit(main(["study_run", "v10/residual_structure_s1", *sys.argv[1:]]))
