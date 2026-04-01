"""
総合型選抜リサーチ Web アプリ — FastAPI エントリーポイント

起動:
    cd /mnt/g/マイドライブ/.claude/scripts/ao-product
    /home/ryuu7/.venv/bin/uvicorn main:app --reload --port 8000
"""

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.research import router as research_router
from auth.routes import router as auth_router
from database import init_db

app = FastAPI(
    title="総合型選抜リサーチ API",
    description="大学・学部を指定して総合型選抜の情報を収集・分析するAPI",
    version="1.0.0",
)

# DB 初期化（起動時）
@app.on_event("startup")
async def startup():
    init_db()

# API ルーター
app.include_router(research_router)
app.include_router(auth_router)

# 静的ファイル（フロントエンド）
_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(str(_STATIC_DIR / "index.html"))


@app.get("/login", include_in_schema=False)
async def login_page():
    return FileResponse(str(_STATIC_DIR / "login.html"))


@app.get("/register", include_in_schema=False)
async def register_page():
    return FileResponse(str(_STATIC_DIR / "register.html"))
