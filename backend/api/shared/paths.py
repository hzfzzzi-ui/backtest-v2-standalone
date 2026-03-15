from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def bt_root() -> Path:
    env_root = os.environ.get("BACKTEST_V2_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve()
    return (repo_root() / "backend" / "core").resolve()


def results_root() -> Path:
    raw = os.environ.get("RESULTS_ROOT", "outputs").strip() or "outputs"
    path = Path(raw)
    if not path.is_absolute():
        path = (repo_root() / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def configs_root() -> Path:
    root = results_root() / "configs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def execution_root() -> Path:
    root = results_root() / "execution"
    root.mkdir(parents=True, exist_ok=True)
    return root


def mobile_ops_root() -> Path:
    root = results_root() / "mobile_ops"
    root.mkdir(parents=True, exist_ok=True)
    return root


def jobs_root() -> Path:
    root = results_root() / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def job_file(job_id: str) -> Path:
    return jobs_root() / f"{job_id}.json"


def experiments_root() -> Path:
    return results_root() / "experiments"
