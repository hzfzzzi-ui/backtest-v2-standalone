from __future__ import annotations

import os
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _bt_root() -> Path:
    env_root = os.environ.get("BACKTEST_V2_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve()
    return (_repo_root() / "backend" / "core").resolve()


def _results_root() -> Path:
    raw = os.environ.get("RESULTS_ROOT", "outputs").strip() or "outputs"
    p = Path(raw)
    if not p.is_absolute():
        p = (_repo_root() / p).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _configs_root() -> Path:
    root = _results_root() / "configs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _execution_root() -> Path:
    root = _results_root() / "execution"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _mobile_ops_root() -> Path:
    root = _results_root() / "mobile_ops"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _jobs_root() -> Path:
    root = _results_root() / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _job_file(job_id: str) -> Path:
    return _jobs_root() / f"{job_id}.json"


def _experiments_root() -> Path:
    return _results_root() / "experiments"
