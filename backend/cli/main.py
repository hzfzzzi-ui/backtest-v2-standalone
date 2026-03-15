from __future__ import annotations

import argparse
import json
from typing import Sequence

from backend.cli.commands import audit, data_refresh, experiment_compare, study_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.cli",
        description="Unified command surface for research studies, comparisons, refresh, and audit workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for module in (study_run, experiment_compare, data_refresh, audit):
        module.register(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1
    result = handler(args)
    if result is None:
        return 0
    if isinstance(result, (dict, list)):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result is not True:
        print(result)
    return 0
