from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from backend.core.services.product_launch_report_service import write_launch_readiness_report


DEFAULT_CHECKLIST_PATH = Path("docs/product_launch/RELEASE_CHECKLIST.md")
DEFAULT_OUTPUT_PATH = Path("outputs/product_launch/launch_readiness_report.md")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the product launch readiness report from the release checklist.")
    parser.add_argument("--checklist", default=str(DEFAULT_CHECKLIST_PATH), help="release checklist markdown path")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="markdown report output path")
    parser.add_argument("--generated-at", default="", help="optional fixed generation timestamp for reproducible tests")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    report_path = write_launch_readiness_report(
        args.checklist,
        args.output,
        generated_at=str(args.generated_at or "").strip() or None,
    )
    print(f"launch_report={report_path}")


if __name__ == "__main__":
    main()
