from __future__ import annotations

import argparse
from typing import Any

from backend.core.services import experiment_compare_service


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "experiment_compare",
        help="Compare experiments or compare a single experiment to a baseline.",
    )
    parser.add_argument("exp_ids", nargs="+", help="One or more experiment ids.")
    parser.add_argument("--baseline-id", dest="baseline_id", help="If provided with a single exp_id, compare to this baseline.")
    parser.set_defaults(handler=_handle)


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    exp_ids = [str(item or "").strip() for item in list(args.exp_ids or []) if str(item or "").strip()]
    if args.baseline_id:
        if len(exp_ids) != 1:
            raise SystemExit("--baseline-id requires exactly one exp_id")
        return experiment_compare_service.compare_experiment_to_baseline(
            exp_id=exp_ids[0],
            baseline_id=str(args.baseline_id or "").strip(),
        )
    return experiment_compare_service.compare_experiments({"exp_ids": exp_ids})
