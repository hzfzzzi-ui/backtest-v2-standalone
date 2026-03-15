from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.mobile import impl

router = APIRouter(tags=["mobile_dashboard"])

MobileLoginRequest = impl.MobileLoginRequest


@router.get("/api/mobile/session")
def get_mobile_session_status(request: Request):
    return impl.get_mobile_session_status(request)


@router.post("/api/mobile/login")
def login_mobile(request: MobileLoginRequest):
    return impl.login_mobile(request)


@router.post("/api/mobile/logout")
def logout_mobile():
    return impl.logout_mobile()
