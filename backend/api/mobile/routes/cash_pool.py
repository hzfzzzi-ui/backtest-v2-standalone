from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.mobile import impl

router = APIRouter(tags=["mobile_dashboard"])

MobileCashPoolDepositRequest = impl.MobileCashPoolDepositRequest


@router.post("/api/mobile/cash-pool/deposit")
def deposit_mobile_cash_pool(body: MobileCashPoolDepositRequest, request: Request):
    return impl.deposit_mobile_cash_pool(body, request)


@router.get("/api/mobile/cash-pool/status")
def get_mobile_cash_pool_status(request: Request):
    return impl.get_mobile_cash_pool_status(request)
