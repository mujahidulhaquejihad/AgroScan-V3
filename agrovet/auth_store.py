"""Lightweight SQLite user store + session tokens."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "users.db"
SESSION_DAYS = 30


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with _connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                name TEXT NOT NULL,
                password_hash TEXT,
                provider TEXT NOT NULL DEFAULT 'local',
                picture TEXT,
                google_sub TEXT UNIQUE,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"{salt}${digest.hex()}"


def _check_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return secrets.compare_digest(check.hex(), digest)


def _user_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "provider": row["provider"],
        "picture": row["picture"],
    }


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()


def create_local_user(name: str, email: str, password: str) -> dict:
    init_db()
    email = email.strip().lower()
    with _connect() as con:
        if con.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise ValueError("Email already registered")
        cur = con.execute(
            "INSERT INTO users (email,name,password_hash,provider,created_at) VALUES (?,?,?,?,?)",
            (email, name.strip(), _hash_password(password), "local", datetime.now(timezone.utc).isoformat()),
        )
        user_id = cur.lastrowid
        con.commit()
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return _user_dict(row)


def login_local(email: str, password: str) -> dict:
    init_db()
    email = email.strip().lower()
    with _connect() as con:
        row = con.execute("SELECT * FROM users WHERE email=? AND provider='local'", (email,)).fetchone()
        if not row or not row["password_hash"] or not _check_password(password, row["password_hash"]):
            raise ValueError("Invalid email or password")
    return _user_dict(row)


def upsert_google_user(name: str, email: str, picture: str, google_sub: str) -> dict:
    init_db()
    email = (email or f"{google_sub}@google.local").strip().lower()
    with _connect() as con:
        row = con.execute("SELECT * FROM users WHERE google_sub=?", (google_sub,)).fetchone()
        if row:
            con.execute(
                "UPDATE users SET name=?, email=?, picture=? WHERE id=?",
                (name, email, picture, row["id"]),
            )
            user_id = row["id"]
        else:
            cur = con.execute(
                "INSERT INTO users (email,name,provider,picture,google_sub,created_at) VALUES (?,?,?,?,?,?)",
                (email, name, "google", picture, google_sub, datetime.now(timezone.utc).isoformat()),
            )
            user_id = cur.lastrowid
        con.commit()
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return _user_dict(row)


def create_session(user_id: int) -> str:
    token = _new_token()
    with _connect() as con:
        con.execute(
            "INSERT INTO sessions (token,user_id,expires_at) VALUES (?,?,?)",
            (token, user_id, _expires_at()),
        )
        con.commit()
    return token


def get_user_by_token(token: str) -> Optional[dict]:
    if not token:
        return None
    init_db()
    with _connect() as con:
        row = con.execute(
            """
            SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
            WHERE s.token=? AND s.expires_at > ?
            """,
            (token, datetime.now(timezone.utc).isoformat()),
        ).fetchone()
    return _user_dict(row) if row else None


def delete_session(token: str):
    if not token:
        return
    with _connect() as con:
        con.execute("DELETE FROM sessions WHERE token=?", (token,))
        con.commit()
