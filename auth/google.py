"""
Google OAuth2 認証フロー
環境変数: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
"""
import os
from urllib.parse import urlencode

import httpx

GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")

_AUTH_URL     = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL    = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def get_google_auth_url(state: str = "") -> str:
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "offline",
        "prompt":        "select_account",
        "state":         state,
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post(_TOKEN_URL, data={
            "code":          code,
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri":  GOOGLE_REDIRECT_URI,
            "grant_type":    "authorization_code",
        }, timeout=15)
        r.raise_for_status()
        return r.json()


async def get_google_user_info(access_token: str) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.get(_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        r.raise_for_status()
        return r.json()


def get_or_create_google_user(google_id: str, email: str, name: str, picture: str = "") -> tuple[dict, bool]:
    """返り値: (user_dict, is_new)"""
    from database import get_db
    db = get_db()
    try:
        # 既存の Google アカウント
        row = db.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
        if row:
            if picture and row["picture"] != picture:
                db.execute("UPDATE users SET picture = ? WHERE id = ?", (picture, row["id"]))
                db.commit()
            return dict(db.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()), False

        # 同メールアドレスのアカウントに google_id を紐付け
        row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            db.execute("UPDATE users SET google_id = ?, picture = ? WHERE id = ?", (google_id, picture, row["id"]))
            db.commit()
            return dict(db.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()), False

        # 新規ユーザー作成
        cur = db.execute(
            "INSERT INTO users (name, email, google_id, picture) VALUES (?, ?, ?, ?)",
            (name, email, google_id, picture),
        )
        db.commit()
        return {"id": cur.lastrowid, "name": name, "email": email, "plan": "free", "usage_count": 0, "picture": picture}, True
    finally:
        db.close()
