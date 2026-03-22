from __future__ import annotations

from collections.abc import Sequence

from backend.cli.main import main as unified_main


def main(argv: Sequence[str] | None = None) -> int:
    """Compatibility-only wrapper for the unified backend CLI."""
    return unified_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
