from __future__ import annotations

import argparse
import json

from backend.core.data.cached_provider import clear_ohlcv_cache_files, get_ohlcv_cache_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Clear local OHLCV parquet cache files.")
    parser.add_argument("--quiet", action="store_true", help="print compact JSON only")
    args = parser.parse_args()

    removed = clear_ohlcv_cache_files()
    payload = {
        "removed": removed,
        "paths": get_ohlcv_cache_paths(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.quiet else 2))


if __name__ == "__main__":
    main()
