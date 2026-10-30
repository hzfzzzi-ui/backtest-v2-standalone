from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Project root (parent of backend/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.backtest_v2.router import router as backtest_v2_router  # noqa: E402
from backend.api.mobile import router as mobile_dashboard_router  # noqa: E402
from backend.api.research_journal import router as research_journal_router  # noqa: E402
from backend.api.transactions import router as transactions_router  # noqa: E402
from backend.api.shared.mobile_access import (  # noqa: E402
    is_allowed_mobile_host,
    is_mobile_protected_path,
    mobile_private_access_enabled,
)
from backend.core.services.ops_domain_pg import OpsDomainSchemaMissing  # noqa: E402
from backend.core.services.market_data_sync_service import (  # noqa: E402
    start_market_data_sync_scheduler,
    stop_market_data_sync_scheduler,
)


class NoCacheMiddleware(BaseHTTPMiddleware):
    """Force no-cache on every response so Ctrl+Shift+R always gets fresh files."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


class PrivateMobileAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if mobile_private_access_enabled() and is_mobile_protected_path(request.url.path):
            if not is_allowed_mobile_host(request.headers.get("host")):
                return JSONResponse(
                    {"detail": "mobile dashboard is only available on private hosts"},
                    status_code=403,
                )
        return await call_next(request)


@asynccontextmanager
async def app_lifespan(_: FastAPI) -> AsyncIterator[None]:
    start_market_data_sync_scheduler()
    try:
        yield
    finally:
        stop_market_data_sync_scheduler()


app = FastAPI(title="backtest-v2-standalone", version="1.0.0", lifespan=app_lifespan)


@app.exception_handler(OpsDomainSchemaMissing)
async def lifecycle_schema_missing_handler(request: Request, exc: OpsDomainSchemaMissing) -> JSONResponse:
    return JSONResponse(
        {"detail": "transaction lifecycle storage is not initialized", "code": "transaction_lifecycle_schema_missing"},
        status_code=503,
    )
app.add_middleware(NoCacheMiddleware)
app.add_middleware(PrivateMobileAccessMiddleware)
app.include_router(backtest_v2_router)
app.include_router(mobile_dashboard_router)
app.include_router(research_journal_router)
app.include_router(transactions_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = PROJECT_ROOT / "frontend"
app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "service": "backtest-v2-standalone"}


_NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "index.html"), headers=_NO_CACHE)


@app.get("/index.html")
def page() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "index.html"), headers=_NO_CACHE)


@app.get("/study-journal")
def study_journal_index() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "study-journal.html"), headers=_NO_CACHE)


@app.get("/study-journal.html")
def study_journal_page() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "study-journal.html"), headers=_NO_CACHE)


@app.get("/mobile")
def mobile_index() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "mobile.html"), headers=_NO_CACHE)


@app.get("/mobile.html")
def mobile_page() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "mobile.html"), headers=_NO_CACHE)


@app.get("/mobile-service-worker.js")
def mobile_service_worker() -> FileResponse:
    return FileResponse(
        str(FRONTEND_DIR / "mobile-service-worker.js"),
        headers={**_NO_CACHE, "Service-Worker-Allowed": "/"},
        media_type="application/javascript",
    )
