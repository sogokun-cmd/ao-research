"""
メール + パスワード認証
- bcrypt によるパスワードハッシュ化
- JWT トークン生成 / 検証
"""
import os
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from jose import jwt

from auth.deps import COOKIE_KEY, JWT_SECRET, ALGORITHM

TOKEN_EXPIRE_DAYS = 30


# ── Password (bcrypt 直接使用 — passlib 互換性問題を回避) ──────

def hash_password(pw: str) -> str:
    return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── JWT ───────────────────────────────────────────────────────

def create_token(user_id: int, email: str, plan: str, name: str = "") -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "email": email, "plan": plan, "name": name, "exp": expire},
        JWT_SECRET,
        algorithm=ALGORITHM,
    )


# ── Register / Login ──────────────────────────────────────────

def register_user(name: str, email: str, password: str) -> dict:
    from database import get_db
    if len(password) < 8:
        raise ValueError("パスワードは8文字以上で設定してください")
    db = get_db()
    try:
        if db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            raise ValueError("このメールアドレスは既に登録されています")
        cur = db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, hash_password(password)),
        )
        db.commit()
        return {"id": cur.lastrowid, "name": name, "email": email, "plan": "free", "usage_count": 0}
    finally:
        db.close()


def login_user(email: str, password: str) -> dict:
    from database import get_db
    db = get_db()
    try:
        row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or not row["password_hash"]:
            raise ValueError("メールアドレスまたはパスワードが正しくありません")
        if not verify_password(password, row["password_hash"]):
            raise ValueError("メールアドレスまたはパスワードが正しくありません")
        return dict(row)
    finally:
        db.close()
