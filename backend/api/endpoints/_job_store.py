from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime
from typing import Any

from ._paths import _job_file
from ._utils import _sanitize_for_json

_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


def _persist_job(job: dict[str, Any]) -> None:
    try:
        _job_file(str(job.get("job_id"))).write_text(
            json.dumps(_sanitize_for_json(job), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _load_job_from_disk(job_id: str) -> dict[str, Any] | None:
    p = _job_file(job_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _create_job(job_type: str, eta_seconds: int = 300) -> str:
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    now = time.time()
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "queued",
            "message": "等待执行",
            "progress_pct": 0,
            "created_at_ts": now,
            "updated_at_ts": now,
            "started_at_ts": None,
            "finished_at_ts": None,
            "eta_seconds": int(max(30, eta_seconds)),
            "result": None,
            "error": None,
        }
        _persist_job(_JOBS[job_id])
    return job_id


def _update_job(job_id: str, **kwargs: Any) -> None:
    now = time.time()
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.update(kwargs)
        job["updated_at_ts"] = now
        if kwargs.get("status") == "running" and job.get("started_at_ts") is None:
            job["started_at_ts"] = now
        if kwargs.get("status") in {"success", "failed"}:
            job["finished_at_ts"] = now
        _persist_job(job)


def _is_cancel_requested(job_id: str) -> bool:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is not None:
            return bool(job.get("cancel_requested"))
    disk_job = _load_job_from_disk(job_id)
    return bool(disk_job and disk_job.get("cancel_requested"))


def _mark_job_canceled(job_id: str, message: str = "任务已取消") -> dict[str, Any] | None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            job = _load_job_from_disk(job_id)
            if job is None:
                return None
            _JOBS[job_id] = job
        status = str(job.get("status") or "")
        if status in {"success", "failed", "canceled"}:
            return job
        now = time.time()
        job["cancel_requested"] = True
        job["status"] = "canceled"
        job["message"] = message
        job["finished_at_ts"] = now
        job["updated_at_ts"] = now
        _persist_job(job)
        return job


def _job_payload(job: dict[str, Any]) -> dict[str, Any]:
    status = str(job.get("status") or "queued")
    progress = int(job.get("progress_pct") or 0)
    if status == "success":
        progress = 100
    if status == "canceled":
        progress = min(progress, 99)
    return {
        "job_id": job.get("job_id"),
        "job_type": job.get("job_type"),
        "status": status,
        "message": job.get("message"),
        "progress_pct": progress,
        "created_at": datetime.fromtimestamp(float(job.get("created_at_ts") or time.time())).isoformat(),
        "updated_at": datetime.fromtimestamp(float(job.get("updated_at_ts") or time.time())).isoformat(),
        "result": job.get("result"),
        "error": job.get("error"),
    }
