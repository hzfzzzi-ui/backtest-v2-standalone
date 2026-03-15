from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

SESSION_COOKIE = "btv2_mobile_session"
CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")


@dataclass(frozen=True, slots=True)
class MobileSession:
    issued_at: str
    expires_at: str


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def mobile_private_access_enabled() -> bool:
    return env_bool("MOBILE_PRIVATE_ACCESS_ENABLED", True)


def mobile_password() -> str:
    return str(os.getenv("MOBILE_DASHBOARD_PASSWORD") or "").strip()


def mobile_secret() -> str:
    return str(os.getenv("MOBILE_AUTH_SECRET") or "").strip()


def mobile_auth_configured() -> bool:
    return bool(mobile_password()) and bool(mobile_secret())


def require_mobile_auth_configured() -> None:
    if mobile_auth_configured():
        return
    raise HTTPException(status_code=503, detail="mobile dashboard auth is not configured")


def mobile_session_ttl_seconds() -> int:
    raw = str(os.getenv("MOBILE_SESSION_TTL_SECONDS") or "43200").strip()
    try:
        return max(300, int(raw))
    except Exception:
        return 43200


def is_mobile_protected_path(path: str | None) -> bool:
    normalized = str(path or "").strip() or "/"
    if normalized in {"/mobile", "/mobile/", "/mobile.html"}:
        return True
    return normalized.startswith("/api/mobile/")


def allowed_mobile_hosts() -> set[str]:
    raw = str(os.getenv("MOBILE_ALLOWED_HOSTS") or "").strip()
    if not raw:
        return set()
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def normalize_host(raw_host: str | None) -> str:
    host = str(raw_host or "").strip().lower()
    if not host:
        return ""
    if host.startswith("["):
        end = host.find("]")
        if end > 0:
            return host[1:end]
    if host.count(":") == 1:
        maybe_host, maybe_port = host.rsplit(":", 1)
        if maybe_port.isdigit():
            return maybe_host
    return host


def is_allowed_mobile_host(raw_host: str | None) -> bool:
    host = normalize_host(raw_host)
    if not host:
        return False
    if host in allowed_mobile_hosts():
        return True
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    if host.endswith(".local"):
        return True
    if "." not in host and ":" not in host:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if ip.is_loopback or ip.is_private or ip.is_link_local:
        return True
    if isinstance(ip, ipaddress.IPv4Address) and ip in CGNAT_NETWORK:
        return True
    return False


def verify_mobile_password(password: str) -> bool:
    require_mobile_auth_configured()
    return hmac.compare_digest(str(password or ""), mobile_password())


def urlsafe_b64encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def urlsafe_b64decode(payload: str) -> bytes:
    padded = payload + "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def create_mobile_session_token(now_ts: int | None = None) -> tuple[str, MobileSession]:
    require_mobile_auth_configured()
    issued_ts = int(now_ts if now_ts is not None else time.time())
    exp_ts = issued_ts + mobile_session_ttl_seconds()
    payload = {
        "iat": issued_ts,
        "exp": exp_ts,
        "nonce": secrets.token_hex(8),
    }
    payload_b64 = urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(mobile_secret().encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    session = MobileSession(
        issued_at=datetime.fromtimestamp(issued_ts, tz=UTC).isoformat(),
        expires_at=datetime.fromtimestamp(exp_ts, tz=UTC).isoformat(),
    )
    return f"{payload_b64}.{signature}", session


def parse_mobile_session_token(token: str | None) -> MobileSession | None:
    raw = str(token or "").strip()
    if not raw or "." not in raw:
        return None
    payload_b64, signature = raw.split(".", 1)
    expected = hmac.new(mobile_secret().encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(urlsafe_b64decode(payload_b64).decode("utf-8"))
    except Exception:
        return None
    issued_ts = int(payload.get("iat") or 0)
    exp_ts = int(payload.get("exp") or 0)
    now_ts = int(time.time())
    if issued_ts <= 0 or exp_ts <= issued_ts or exp_ts <= now_ts:
        return None
    return MobileSession(
        issued_at=datetime.fromtimestamp(issued_ts, tz=UTC).isoformat(),
        expires_at=datetime.fromtimestamp(exp_ts, tz=UTC).isoformat(),
    )


def get_mobile_session(request: Request) -> MobileSession | None:
    if not mobile_auth_configured():
        return None
    return parse_mobile_session_token(request.cookies.get(SESSION_COOKIE))


def require_mobile_session(request: Request) -> MobileSession:
    session = get_mobile_session(request)
    if session is not None:
        return session
    raise HTTPException(status_code=401, detail="mobile session is required")


def set_mobile_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=mobile_session_ttl_seconds(),
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def clear_mobile_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, path="/")
