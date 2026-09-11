"""
FastAPI dependencies for JWT-protected routes.
Usage:
    @router.get("/api/protected")
    async def route(wm=Depends(require_wm)):
        ...
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from auth.jwt_handler import decode_token

_bearer = HTTPBearer(auto_error=False)


def _get_payload(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return payload


def require_wm(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """Requires a Wealth Manager JWT."""
    payload = _get_payload(credentials)
    if payload.get("role") != "wm":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wealth Manager access required")
    return payload


def require_client(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """Requires a Client JWT."""
    payload = _get_payload(credentials)
    if payload.get("role") != "client":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client access required")
    return payload


def require_any(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """Accepts any valid JWT (WM or Client)."""
    return _get_payload(credentials)
