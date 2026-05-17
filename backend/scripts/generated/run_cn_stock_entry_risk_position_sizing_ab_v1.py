from __future__ import annotations

from backend.cli.main import main


if __name__ == "__main__":
    raise SystemExit(
        main(
            [
                "study_run",
                "cn_stock_etf/cn_stock_entry_risk_position_sizing_ab_v1",
                *(__import__("sys").argv[1:]),
            ]
        )
    )
