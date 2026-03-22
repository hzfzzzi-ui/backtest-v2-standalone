from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scripts import update_pit_index_daily as script_mod

DEFAULT_OUTPUT_ROOT = script_mod.DEFAULT_OUTPUT_ROOT
DEFAULT_SOURCE_TABLE = script_mod.DEFAULT_SOURCE_TABLE
DEFAULT_TARGET_TABLE = script_mod.DEFAULT_TARGET_TABLE


def build_update_args(
    *,
    end: str,
    start: str = "",
    source_table: str = DEFAULT_SOURCE_TABLE,
    target_table: str = DEFAULT_TARGET_TABLE,
    batch_size: int = 5000,
    output_dir: str = "",
    apply: bool = True,
) -> argparse.Namespace:
    return argparse.Namespace(
        end=str(end or "").strip(),
        start=str(start or "").strip(),
        source_table=str(source_table or DEFAULT_SOURCE_TABLE),
        target_table=str(target_table or DEFAULT_TARGET_TABLE),
        batch_size=int(batch_size),
        output_dir=str(output_dir or ""),
        apply=bool(apply),
    )


def run_update_to_target(
    *,
    end: str,
    start: str = "",
    source_table: str = DEFAULT_SOURCE_TABLE,
    target_table: str = DEFAULT_TARGET_TABLE,
    batch_size: int = 5000,
    output_dir: str = "",
    apply: bool = True,
) -> dict[str, Any]:
    return script_mod.run_update(
        build_update_args(
            end=end,
            start=start,
            source_table=source_table,
            target_table=target_table,
            batch_size=batch_size,
            output_dir=output_dir,
            apply=apply,
        )
    )


def main() -> None:
    script_mod.main()


__all__ = [
    "DEFAULT_OUTPUT_ROOT",
    "DEFAULT_SOURCE_TABLE",
    "DEFAULT_TARGET_TABLE",
    "build_update_args",
    "main",
    "run_update_to_target",
]
