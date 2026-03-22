from __future__ import annotations

import argparse
import importlib
import sys
from contextlib import contextmanager
from typing import Any

_TARGETS = {
    "pams_ohlcv_daily": "backend.cli.managed.update_pams_ohlcv_daily",
    "pams_ohlcv_daily_v2_full_backfill": "backend.cli.managed.run_pams_ohlcv_daily_v2_full_backfill",
    "pams_ohlcv_daily_v2_formal_audits": "backend.cli.managed.run_pams_ohlcv_daily_v2_formal_audits",
    "pams_ohlcv_daily_v2_raw": "backend.cli.managed.update_pams_ohlcv_daily_v2_raw",
    "pams_ohlcv_daily_v2": "backend.cli.managed.update_pams_ohlcv_daily_v2",
    "pams_ohlcv_daily_v2_audit": "backend.cli.managed.audit_pams_ohlcv_daily_v2",
    "pit_index_daily": "backend.cli.managed.update_pit_index_daily",
    "pit_stock_daily_basic": "backend.cli.managed.update_pit_stock_daily_basic",
    "pit_stock_moneyflow": "backend.cli.managed.update_pit_stock_moneyflow",
    "pit_stock_moneyflow_v2": "backend.cli.managed.update_pit_stock_moneyflow_v2",
    "pit_stock_feature_coverage": "backend.cli.managed.audit_pit_stock_feature_coverage",
    "security_master": "backend.cli.managed.refresh_security_master",
    "csi1000_pit": "backend.cli.managed.refresh_csi1000_pit",
    "csi800_pit": "backend.cli.managed.refresh_csi800_pit",
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
        "data_refresh",
        help="Managed wrapper around recurring data refresh scripts.",
    )
    parser.add_argument("--target", choices=sorted(_TARGETS), help="Named refresh target.")
    parser.add_argument("--list-targets", action="store_true", help="List managed refresh targets.")
    parser.add_argument("script_args", nargs=argparse.REMAINDER, help="Arguments forwarded to the underlying managed script.")
    parser.set_defaults(handler=_handle)


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    if args.list_targets or not args.target:
        return {"targets": sorted(_TARGETS)}
    module_name = _TARGETS[str(args.target)]
    module = importlib.import_module(module_name)
    entry = getattr(module, "main", None)
    if entry is None:
        raise SystemExit(f"managed refresh target missing main(): {module_name}")
    forwarded = list(args.script_args or [])
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]
    with _patched_argv([module_name, *forwarded]):
        entry()
    return {"status": "ok", "target": str(args.target), "forwarded_args": forwarded}
