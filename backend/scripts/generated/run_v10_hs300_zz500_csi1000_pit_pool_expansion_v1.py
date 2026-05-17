from __future__ import annotations

from backend.cli.main import main


if __name__ == "__main__":
    raise SystemExit(
        main(
            [
                "study_run",
                "v10/hs300_zz500_csi1000_pit_pool_expansion_v1",
                *(__import__("sys").argv[1:]),
            ]
        )
    )
