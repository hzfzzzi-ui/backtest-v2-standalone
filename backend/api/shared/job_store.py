from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime
from typing import Any

from backend.api.shared.json_utils import sanitize_for_json
from backend.api.shared.paths import job_file

JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def persist_job(job: dict[str, Any]) -> None:
    try:
        job_file(str(job.get("job_id"))).write_text(
            json.dumps(sanitize_for_json(job), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def load_job_from_disk(job_id: str) -> dict[str, Any] | None:
    path = job_file(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def create_job(job_type: str, eta_seconds: int = 300) -> str:
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    now = time.time()
    with JOBS_LOCK:
        JOBS[job_id] = {
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
        persist_job(JOBS[job_id])
    return job_id


def update_job(job_id: str, **kwargs: Any) -> None:
    now = time.time()
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job.update(kwargs)
        job["updated_at_ts"] = now
        if kwargs.get("status") == "running" and job.get("started_at_ts") is None:
            job["started_at_ts"] = now
        if kwargs.get("status") in {"success", "failed"}:
            job["finished_at_ts"] = now
        persist_job(job)


def is_cancel_requested(job_id: str) -> bool:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is not None:
            return bool(job.get("cancel_requested"))
    disk_job = load_job_from_disk(job_id)
    return bool(disk_job and disk_job.get("cancel_requested"))


def mark_job_canceled(job_id: str, message: str = "任务已取消") -> dict[str, Any] | None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            job = load_job_from_disk(job_id)
            if job is None:
                return None
            JOBS[job_id] = job
        status = str(job.get("status") or "")
        if status in {"success", "failed", "canceled"}:
            return job
        now = time.time()
        job["cancel_requested"] = True
        job["status"] = "canceled"
        job["message"] = message
        job["finished_at_ts"] = now
        job["updated_at_ts"] = now
        persist_job(job)
        return job


def job_payload(job: dict[str, Any]) -> dict[str, Any]:
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
