from __future__ import annotations

import argparse

from backend.core.tools.bundles import run_bundle


def main() -> None:
    p = argparse.ArgumentParser(description="run bundle workflows")
    p.add_argument("--bundle", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--symbols", default="")
    p.add_argument("--start_date", default="")
    p.add_argument("--end_date", default="")
    args = p.parse_args()

    overrides = {}
    if args.symbols:
        overrides["symbols"] = [x.strip() for x in str(args.symbols).split(",") if x.strip()]
    if args.start_date:
        overrides["start_date"] = args.start_date
    if args.end_date:
        overrides["end_date"] = args.end_date

    out = run_bundle(args.bundle, args.config, overrides)
    print(f"bundle_dir={out['bundle_dir']}")


if __name__ == "__main__":
    main()

