from __future__ import annotations

from fastapi import APIRouter, Query, Request

from backend.api.mobile import impl

router = APIRouter(tags=["mobile_dashboard"])

MobileApprovalRevokeRequest = impl.MobileApprovalRevokeRequest


@router.get("/api/mobile/approval-tickets")
def get_mobile_approval_tickets(request: Request, status: str = Query("approved_pending")):
    return impl.get_mobile_approval_tickets(request, status=status)


@router.post("/api/mobile/approval-tickets/{ticket_id}/revoke")
def revoke_mobile_approval_ticket(ticket_id: str, body: MobileApprovalRevokeRequest, request: Request):
    return impl.revoke_mobile_approval_ticket(ticket_id, body, request)
