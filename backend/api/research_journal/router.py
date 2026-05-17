from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.research import study_journal

router = APIRouter(tags=["research_journal"])


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, FileExistsError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/api/research/study-rounds")
def list_study_rounds() -> dict[str, Any]:
    try:
        return {"ok": True, "items": study_journal.list_rounds()}
    except Exception as exc:  # pragma: no cover - defensive API boundary
        raise _handle_error(exc) from exc


@router.post("/api/research/study-rounds")
def create_study_round(body: dict[str, Any]) -> dict[str, Any]:
    try:
        return {"ok": True, "item": study_journal.save_round(body)}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/api/research/study-rounds/{round_id}")
def get_study_round(round_id: str) -> dict[str, Any]:
    try:
        return {"ok": True, "item": study_journal.get_round(round_id)}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.patch("/api/research/study-rounds/{round_id}")
def update_study_round(round_id: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        return {"ok": True, "item": study_journal.update_round(round_id, body)}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/api/research/study-rounds/{round_id}/notes")
def append_study_round_note(round_id: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        return {"ok": True, "item": study_journal.append_note(round_id, body)}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/api/research/study-rounds/{round_id}/links/experiment")
def link_study_round_experiment(round_id: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        return {"ok": True, "item": study_journal.link_experiment(round_id, body)}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/api/research/study-rounds/{round_id}/summary/refresh")
def refresh_study_round_summary(round_id: str) -> dict[str, Any]:
    try:
        return {"ok": True, "item": study_journal.refresh_auto_summary(round_id)}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/api/research/study-conclusions")
def list_study_conclusions(
    study_id: str | None = None,
    exp_id: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
) -> dict[str, Any]:
    try:
        return {
            "ok": True,
            "items": study_journal.list_conclusion_records(
                study_id=study_id,
                exp_id=exp_id,
                limit=limit,
            ),
        }
    except Exception as exc:
        raise _handle_error(exc) from exc
