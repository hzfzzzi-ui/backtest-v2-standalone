from __future__ import annotations

from fastapi import APIRouter

from .routes import approvals_router, auth_router, dashboard_router, tickets_router

router = APIRouter(tags=["mobile_dashboard"])
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(approvals_router)
router.include_router(tickets_router)
