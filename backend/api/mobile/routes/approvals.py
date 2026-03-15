from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.mobile import impl

router = APIRouter(tags=["mobile_dashboard"])

MobileApprovalPrepareRequest = impl.MobileApprovalPrepareRequest
MobileApprovalCommitRequest = impl.MobileApprovalCommitRequest


@router.post("/api/mobile/approvals/prepare")
def prepare_mobile_approval(body: MobileApprovalPrepareRequest, request: Request):
    return impl.prepare_mobile_approval(body, request)


@router.post("/api/mobile/approvals/commit")
def commit_mobile_approval(body: MobileApprovalCommitRequest, request: Request):
    return impl.commit_mobile_approval(body, request)
