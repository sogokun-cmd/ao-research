"""
SQLite データベース管理
テーブル: users, anon_usage
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "ao_product.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            email           TEXT    UNIQUE NOT NULL,
            password_hash   TEXT,
            google_id       TEXT    UNIQUE,
            picture         TEXT,
            plan            TEXT    NOT NULL DEFAULT 'free',
            usage_count     INTEGER NOT NULL DEFAULT 0,
            usage_reset_at  TEXT,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS anon_usage (
            ip              TEXT    PRIMARY KEY,
            usage_count     INTEGER NOT NULL DEFAULT 0,
            reset_at        TEXT
        );
    """)
    conn.commit()
    # マイグレーション: picture 列が未存在の場合は追加
    cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "picture" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN picture TEXT")
        conn.commit()
    conn.close()
