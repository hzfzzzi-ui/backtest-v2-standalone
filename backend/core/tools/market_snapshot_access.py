from __future__ import annotations

import os
from datetime import date
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _results_root() -> Path:
    raw = os.environ.get("RESULTS_ROOT", "outputs").strip() or "outputs"
    path = Path(raw)
    if not path.is_absolute():
        path = (_repo_root() / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def market_snapshots_root() -> Path:
    root = _results_root() / "market_snapshots"
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_market_snapshot_dir(trade_date: date | str, *, create: bool = True) -> Path:
    if isinstance(trade_date, str):
        trade_dt = date.fromisoformat(trade_date)
    else:
        trade_dt = trade_date
    target = market_snapshots_root() / trade_dt.isoformat()
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target
