"""
認証依存関係 — JWT Cookie からユーザー情報を取得するヘルパー
"""
import os

from fastapi import Request
from jose import JWTError, jwt

COOKIE_KEY = "ao_session"
JWT_SECRET  = os.environ.get("JWT_SECRET_KEY", "dev-secret-please-change-in-production")
ALGORITHM   = "HS256"
FREE_LIMIT  = 3


def get_current_user(request: Request) -> dict | None:
    """Cookie の JWT を検証してユーザー情報を返す。未認証なら None。"""
    token = request.cookies.get(COOKIE_KEY)
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return {
            "user_id": int(payload["sub"]),
            "email":   payload.get("email", ""),
            "plan":    payload.get("plan", "free"),
            "name":    payload.get("name", ""),
        }
    except Exception:
        return None


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
