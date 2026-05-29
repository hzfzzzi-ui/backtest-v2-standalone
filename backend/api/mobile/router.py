from __future__ import annotations

from fastapi import APIRouter

from backend.api.shared.safe_json_response import SafeJSONResponse

from .routes import approvals_router, auth_router, cash_pool_router, dashboard_router, tickets_router

router = APIRouter(tags=["mobile_dashboard"], default_response_class=SafeJSONResponse)
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(cash_pool_router)
router.include_router(approvals_router)
router.include_router(tickets_router)
