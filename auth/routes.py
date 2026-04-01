"""
認証ルーター: /auth/*
  POST /auth/register  — メール+パスワード登録
  POST /auth/login     — メール+パスワードログイン
  GET  /auth/google    — Google OAuth2 開始
  GET  /auth/callback  — Google OAuth2 コールバック
  POST /auth/logout    — ログアウト
"""
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from auth.deps import COOKIE_KEY
from auth.email_auth import create_token, login_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])

_MAX_AGE = 30 * 24 * 3600  # 30日


# ── Register ────────────────────────────────────────────────────────────────

@router.post("/register")
async def do_register(
    name:     str = Form(...),
    email:    str = Form(...),
    password: str = Form(...),
):
    try:
        user  = register_user(name.strip(), email.strip().lower(), password)
        token = create_token(user["id"], user["email"], user["plan"], user["name"])
        resp  = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(COOKIE_KEY, token, max_age=_MAX_AGE, httponly=True, samesite="lax")
        return resp
    except ValueError as e:
        return RedirectResponse(url=f"/register?error={quote(str(e))}", status_code=303)


# ── Login ───────────────────────────────────────────────────────────────────

@router.post("/login")
async def do_login(
    email:    str = Form(...),
    password: str = Form(...),
):
    try:
        user  = login_user(email.strip().lower(), password)
        token = create_token(user["id"], user["email"], user["plan"], user["name"])
        resp  = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(COOKIE_KEY, token, max_age=_MAX_AGE, httponly=True, samesite="lax")
        return resp
    except ValueError as e:
        return RedirectResponse(url=f"/login?error={quote(str(e))}", status_code=303)


# ── Google OAuth2 ────────────────────────────────────────────────────────────

@router.get("/google")
async def google_login():
    from auth.google import get_google_auth_url
    state = secrets.token_urlsafe(16)
    url   = get_google_auth_url(state)
    resp  = RedirectResponse(url=url)
    resp.set_cookie("oauth_state", state, max_age=600, httponly=True, samesite="lax")
    return resp


@router.get("/callback")
async def google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse(
            url=f"/login?error={quote('Googleログインがキャンセルされました')}",
            status_code=303,
        )

    # State 検証 (CSRF対策)
    stored = request.cookies.get("oauth_state", "")
    if stored and state and stored != state:
        raise HTTPException(400, "Invalid OAuth state — もう一度お試しください")

    from auth.google import exchange_code, get_google_user_info, get_or_create_google_user
    try:
        tokens    = await exchange_code(code)
        user_info = await get_google_user_info(tokens["access_token"])
        user      = get_or_create_google_user(
            google_id = user_info["id"],
            email     = user_info["email"],
            name      = user_info.get("name", user_info["email"]),
            picture   = user_info.get("picture", ""),
        )
    except Exception as exc:
        return RedirectResponse(
            url=f"/login?error={quote('Googleログインに失敗しました: ' + str(exc)[:40])}",
            status_code=303,
        )

    token = create_token(user["id"], user["email"], user.get("plan", "free"), user.get("name", ""))
    resp  = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(COOKIE_KEY, token, max_age=_MAX_AGE, httponly=True, samesite="lax")
    resp.delete_cookie("oauth_state")
    return resp


# ── Logout ──────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(COOKIE_KEY)
    return resp
