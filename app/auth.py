import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional

from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from .config import settings


SESSION_COOKIE = "wise_agent_session"


def _sign(payload: str) -> str:
    return hmac.new(settings.auth_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_session_token(user_id: str, role: str = "admin") -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.session_ttl_seconds,
    }
    payload_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_text.encode("utf-8")).decode("utf-8").rstrip("=")
    return f"{payload_b64}.{_sign(payload_b64)}"


def parse_session_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(payload_b64)):
        return None
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload


def authenticate(username: str, password: str) -> Optional[Dict[str, str]]:
    username_ok = hmac.compare_digest(username, settings.admin_username)
    password_ok = hmac.compare_digest(password, settings.admin_password)
    if username_ok and password_ok:
        return {"userId": username, "role": "admin"}
    return None


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.environment.lower() == "production",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE)


def current_user(request: Request, session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)) -> Dict[str, Any]:
    if not settings.auth_enabled:
        return {"userId": "local-dev", "role": "admin"}

    token = session
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = parse_session_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return {"userId": payload["sub"], "role": payload.get("role", "user")}


def require_admin(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permission required")
    return user


def require_page_session(request: Request) -> Optional[RedirectResponse]:
    if not settings.auth_enabled:
        return None
    token = request.cookies.get(SESSION_COOKIE)
    if token and parse_session_token(token):
        return None
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
