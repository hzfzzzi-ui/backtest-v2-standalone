from __future__ import annotations

from backend.cli.main import main


if __name__ == "__main__":
    raise SystemExit(main(["study_run", "v10/onset_ingress_minimal_s2", *(__import__("sys").argv[1:])]))
