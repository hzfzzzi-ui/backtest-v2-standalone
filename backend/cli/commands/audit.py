from __future__ import annotations

import argparse
import importlib
import sys
from contextlib import contextmanager
from typing import Any

_TARGETS = {
    "baseline_regression": "backend.cli.managed.baseline_regression_check",
    "report_consistency": "backend.cli.managed.report_consistency_check",
}


@contextmanager
def _patched_argv(argv: list[str]):
    original = list(sys.argv)
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = original


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "audit",
        help="Managed wrapper around recurring audit scripts.",
    )
    parser.add_argument("--target", choices=sorted(_TARGETS), help="Named audit target.")
    parser.add_argument("--list-targets", action="store_true", help="List managed audit targets.")
    parser.add_argument("script_args", nargs=argparse.REMAINDER, help="Arguments forwarded to the underlying managed script.")
    parser.set_defaults(handler=_handle)


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    if args.list_targets or not args.target:
        return {"targets": sorted(_TARGETS)}
    module_name = _TARGETS[str(args.target)]
    module = importlib.import_module(module_name)
    entry = getattr(module, "main", None)
    if entry is None:
        raise SystemExit(f"managed audit target missing main(): {module_name}")
    forwarded = list(args.script_args or [])
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]
    with _patched_argv([module_name, *forwarded]):
        entry()
    return {"status": "ok", "target": str(args.target), "forwarded_args": forwarded}
