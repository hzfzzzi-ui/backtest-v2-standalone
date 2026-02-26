"""
Run Context Manager - Orchestrates complete backtest reproducibility.

Manages:
- run_meta.json generation
- Structured logging setup
- Random seed initialization
- Results checksumming
- Output directory structure
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .logger import StructuredLogger
from .reproducibility import (
    RunMetadata,
    ensure_deterministic_run,
    hash_dict,
    hash_list,
    set_random_seeds,
)


class BacktestRunContext:
    """
    Context manager for reproducible backtest runs.

    Handles:
    - Directory creation
    - run_meta.json generation
    - Structured logging setup
    - Deterministic random seeds
    - Results checksumming
    """

    def __init__(
        self,
        config: Any,
        output_dir: str | Path,
        random_seed: int = 42,
        run_id: str | None = None,
    ):
        """Initialize run context.

        Args:
            config: Backtest configuration (must be serializable)
            output_dir: Output directory for results
            random_seed: Random seed for reproducibility
            run_id: Optional run ID (auto-generated if not provided)
        """
        self.config = config
        self.output_dir = Path(output_dir)
        self.random_seed = random_seed
        self.run_id = run_id or f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # Create output directory
        self.run_dir = self.output_dir / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Initialize run metadata
        self.run_meta = ensure_deterministic_run(config, random_seed)
        self.run_meta.run_id = self.run_id

        # Create structured logger
        self.logger = StructuredLogger(
            run_id=self.run_id,
            log_path=self.run_dir / "audit_log.jsonl",
        )

        # Results tracking
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None
        self.results: dict[str, Any] = {}

    def __enter__(self) -> BacktestRunContext:
        """Enter context (start run)."""
        self.start_time = datetime.now(timezone.utc)
        print(f"📊 Starting backtest run: {self.run_id}")
        print(f"📁 Output directory: {self.run_dir}")
        print(f"🎲 Random seed: {self.random_seed}")

        # Set random seeds
        set_random_seeds(self.random_seed)

        # Save initial run_meta (will be updated on exit)
        self._save_run_meta()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context (finalize run)."""
        self.end_time = datetime.now(timezone.utc)

        # Close logger
        self.logger.close()

        # Finalize run_meta
        if self.results:
            self._finalize_run_meta()

        # Save final run_meta
        self._save_run_meta()

        duration = (self.end_time - self.start_time).total_seconds() if self.start_time else 0
        print(f"✅ Backtest complete in {duration:.1f}s")
        print(f"📄 Results saved to: {self.run_dir}")

    def save_results(
        self,
        equity_curve: pd.DataFrame,
        trades: pd.DataFrame,
        signals: list[dict],
        summary: dict,
        **extra_data,
    ) -> None:
        """Save backtest results and compute checksums.

        Args:
            equity_curve: Daily equity curve DataFrame
            trades: Trade log DataFrame
            signals: List of signal dicts
            summary: Summary statistics dict
            **extra_data: Additional data to save (e.g., orders, positions)
        """
        # Save equity curve
        equity_path = self.run_dir / "equity_curve.parquet"
        equity_curve.to_parquet(equity_path, index=False)

        # Save trades
        trades_path = self.run_dir / "trades.parquet"
        trades.to_parquet(trades_path, index=False)

        # Save signals
        signals_path = self.run_dir / "signals.json"
        signals_path.write_text(json.dumps(signals, ensure_ascii=False, indent=2), encoding="utf-8")

        # Save summary
        summary_path = self.run_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        # Save extra data
        for name, data in extra_data.items():
            if isinstance(data, pd.DataFrame):
                path = self.run_dir / f"{name}.parquet"
                data.to_parquet(path, index=False)
            else:
                path = self.run_dir / f"{name}.json"
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Store for checksumming
        self.results = {
            "equity_curve": equity_curve,
            "trades": trades,
            "signals": signals,
            "summary": summary,
            **extra_data,
        }

        print(f"💾 Saved {len(trades)} trades, {len(signals)} signals, {len(equity_curve)} daily snapshots")

    def _finalize_run_meta(self) -> None:
        """Finalize run metadata with result checksums."""
        # Checksum equity curve
        if "equity_curve" in self.results:
            equity_values = self.results["equity_curve"]["equity"].round(6).tolist()
            self.run_meta.equity_curve_checksum = hash_list(equity_values)

        # Checksum trades
        if "trades" in self.results:
            trades_df = self.results["trades"]
            # Use trade_id + net_amount for deterministic check
            if "trade_id" in trades_df.columns and "net_amount" in trades_df.columns:
                trade_data = trades_df[["trade_id", "net_amount"]].round(6).to_dict("records")
                self.run_meta.trades_checksum = hash_list(trade_data)

        # Add execution time to metadata
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
            self.run_meta.config_snapshot["_execution_time_seconds"] = round(duration, 2)

    def _save_run_meta(self) -> None:
        """Save run_meta.json."""
        meta_path = self.run_dir / "run_meta.json"
        self.run_meta.save(meta_path)

    def verify_reproducibility(self, reference_meta_path: str | Path) -> dict[str, Any]:
        """Verify this run matches a reference run.

        Args:
            reference_meta_path: Path to reference run_meta.json

        Returns:
            Verification results with pass/fail for each check
        """
        reference = RunMetadata.load(reference_meta_path)
        results = {}

        # Check config hash
        results["config_match"] = (
            self.run_meta.config_hash == reference.config_hash
        )

        # Check git commit
        results["git_commit_match"] = (
            self.run_meta.git_commit == reference.git_commit
        )

        # Check random seed
        results["random_seed_match"] = (
            self.run_meta.random_seed == reference.random_seed
        )

        # Check equity curve
        results["equity_curve_match"] = (
            self.run_meta.equity_curve_checksum == reference.equity_curve_checksum
        )

        # Check trades
        results["trades_match"] = (
            self.run_meta.trades_checksum == reference.trades_checksum
        )

        # Overall pass
        results["all_checks_pass"] = all([
            results["config_match"],
            results["random_seed_match"],
            results["equity_curve_match"],
            results["trades_match"],
        ])

        # Warnings
        results["warnings"] = []
        if not results["git_commit_match"]:
            results["warnings"].append(
                f"Git commit mismatch: {self.run_meta.git_commit[:8]} vs {reference.git_commit[:8]}"
            )

        return results

    def get_output_paths(self) -> dict[str, Path]:
        """Get paths to all output files.

        Returns:
            Dictionary of {name: path}
        """
        return {
            "run_meta": self.run_dir / "run_meta.json",
            "audit_log": self.run_dir / "audit_log.jsonl",
            "equity_curve": self.run_dir / "equity_curve.parquet",
            "trades": self.run_dir / "trades.parquet",
            "signals": self.run_dir / "signals.json",
            "summary": self.run_dir / "summary.json",
        }


# Convenience function
def create_run_context(
    config: Any,
    output_dir: str | Path = "results",
    random_seed: int = 42,
    run_id: str | None = None,
) -> BacktestRunContext:
    """Create a backtest run context.

    Args:
        config: Backtest configuration
        output_dir: Base output directory
        random_seed: Random seed for reproducibility
        run_id: Optional custom run ID

    Returns:
        BacktestRunContext instance

    Example:
        >>> with create_run_context(config, output_dir="results") as ctx:
        ...     # Run backtest
        ...     result = run_backtest(...)
        ...
        ...     # Save results
        ...     ctx.save_results(
        ...         equity_curve=result.equity_curve,
        ...         trades=result.trades,
        ...         signals=result.signals,
        ...         summary=result.summary,
        ...     )
    """
    return BacktestRunContext(
        config=config,
        output_dir=output_dir,
        random_seed=random_seed,
        run_id=run_id,
    )


__all__ = [
    "BacktestRunContext",
    "create_run_context",
]
