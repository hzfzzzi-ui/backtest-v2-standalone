from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.mobile import impl

router = APIRouter(tags=["mobile_dashboard"])


@router.get("/api/mobile/dashboard")
def get_mobile_dashboard(request: Request):
    return impl.get_mobile_dashboard(request)
