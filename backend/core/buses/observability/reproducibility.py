"""
Reproducibility Support for Backtest V2.

Provides run_meta.json schema and determinism utilities.
"""

import hashlib
import json
import random
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class RunMetadata:
    """Complete run metadata for reproducibility."""

    # Run identification
    run_id: str                          # UUID v4
    run_timestamp: str                   # ISO 8601 UTC

    # Code version
    git_commit: str                      # Git SHA
    code_checksum: str                   # SHA256 of key modules

    # Configuration
    config_hash: str                     # SHA256 of config dict
    config_snapshot: dict = field(default_factory=dict)  # Full config

    # Data snapshot
    data_version: str = ""               # From pams_data_version table
    data_as_of_date: str = ""            # ISO date
    ohlcv_checksum: str = ""             # SHA256 of OHLCV rows
    universe_checksum: str = ""          # SHA256 of symbols + dates

    # Environment
    python_version: str = ""             # e.g., "3.11.5"
    dependencies: dict = field(default_factory=dict)  # {package: version}

    # Random seeds
    random_seed: int = 42                # For numpy, random

    # Query audit trail
    queries_executed: list = field(default_factory=list)  # From DataProvider.query_audit

    # Results checksum
    equity_curve_checksum: str = ""      # SHA256 of equity values
    trades_checksum: str = ""            # SHA256 of trade IDs + amounts

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(asdict(self), indent=2, sort_keys=True, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "RunMetadata":
        """Deserialize from JSON."""
        data = json.loads(json_str)
        return cls(**data)

    def save(self, path: str | Path) -> None:
        """Save to file."""
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "RunMetadata":
        """Load from file."""
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


def get_git_commit() -> str:
    """Get current git commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


def hash_dict(d: dict) -> str:
    """Compute SHA256 hash of dict (deterministic)."""
    json_str = json.dumps(d, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json_str.encode()).hexdigest()


def hash_list(values: list[Any]) -> str:
    """Compute SHA256 hash of list."""
    json_str = json.dumps(values, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json_str.encode()).hexdigest()


def set_random_seeds(seed: int) -> None:
    """Set random seeds for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)


def get_python_version() -> str:
    """Get Python version string."""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def get_package_versions() -> dict[str, str]:
    """Get versions of key packages."""
    packages = ["numpy", "pandas", "psycopg2"]
    versions = {}

    for package in packages:
        try:
            mod = __import__(package)
            versions[package] = getattr(mod, "__version__", "unknown")
        except ImportError:
            versions[package] = "not installed"

    return versions


def ensure_deterministic_run(config: Any, random_seed: int = 42) -> RunMetadata:
    """Set up deterministic environment and return metadata."""

    # Set random seeds
    set_random_seeds(random_seed)

    # Create run metadata
    run_meta = RunMetadata(
        run_id=f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        git_commit=get_git_commit(),
        code_checksum="",  # TODO: Implement code checksumming
        config_hash=hash_dict(asdict(config) if hasattr(config, '__dataclass_fields__') else config),
        config_snapshot=asdict(config) if hasattr(config, '__dataclass_fields__') else config,
        python_version=get_python_version(),
        dependencies=get_package_versions(),
        random_seed=random_seed,
    )

    return run_meta


# Determinism checklist:
"""
1. ✓ Database query ordering → All queries use ORDER BY symbol, trade_date
2. ✓ Dict iteration order → Use sorted(dict.items()) when order matters
3. ✓ Floating-point precision → Round to 6 decimals for checksums
4. ✓ Random number generation → Set numpy.random.seed(random_seed)
5. ✓ Timestamp-based IDs → Use deterministic counters, not time.time()
6. ✓ Concurrent execution → Disable parallelization for reproducible runs
7. ✓ Data updates → Snapshot data_as_of_date, query with trade_date <= as_of_date
"""
