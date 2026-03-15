from __future__ import annotations

from backend.cli.main import main


if __name__ == "__main__":
    raise SystemExit(main(["study_run", "v10/residual_structure_s1", *(__import__("sys").argv[1:])]))
