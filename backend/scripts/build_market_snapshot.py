from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.core.services.market_snapshot_service import build_market_snapshot_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a daily A-share market snapshot artifact")
    parser.add_argument("--trade-date", required=True, help="anchor trade date in YYYY-MM-DD")
    parser.add_argument("--bt-root", default="", help="optional repo/backend root override")
    parser.add_argument("--output-dir", default="", help="optional explicit output directory")
    return parser


def main(argv: Sequence[str] | None = None) -> dict[str, object]:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    artifacts = build_market_snapshot_artifacts(
        trade_date=str(args.trade_date),
        bt_root=Path(args.bt_root).resolve() if str(args.bt_root).strip() else None,
        output_dir=Path(args.output_dir).resolve() if str(args.output_dir).strip() else None,
    )
    summary = {
        "trade_date": artifacts.snapshot.get("trade_date"),
        "build_status": artifacts.snapshot.get("build_status"),
        "output_dir": str(artifacts.output_dir),
        "snapshot_path": str(artifacts.snapshot_path),
        "brief_path": str(artifacts.brief_path),
        "warning_count": len(list(artifacts.snapshot.get("warnings") or [])),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    main()
