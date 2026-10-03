from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


PBKDF2_ITERATIONS = 600_000
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128
_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_DUMMY_SALT = b"TRADEXBOT_LOGIN_CHECK"


def _database_path() -> Path:
    configured_path = os.environ.get("TRADEXBOT_AUTH_DB")
    if configured_path:
        path = Path(configured_path).expanduser()
    elif os.name == "nt":
        data_root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        path = data_root / "TRADEXBOT" / "accounts.sqlite3"
    else:
        data_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        path = data_root / "tradexbot" / "accounts.sqlite3"

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(_database_path(), timeout=15)
    try:
        connection.execute("PRAGMA busy_timeout = 15000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                salt BLOB NOT NULL,
                password_hash BLOB NOT NULL,
                iterations INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("Enter a valid email address.")
    return normalized


def _validate_password(password: str) -> None:
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError("Password must be between 10 and 128 characters.")


def _password_hash(password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def create_account(email: str, password: str) -> str:
    normalized_email = _normalize_email(email)
    _validate_password(password)
    salt = secrets.token_bytes(16)
    password_hash = _password_hash(password, salt)

    try:
        with _connection() as connection:
            connection.execute(
                "INSERT INTO users (email, salt, password_hash, iterations) VALUES (?, ?, ?, ?)",
                (normalized_email, salt, password_hash, PBKDF2_ITERATIONS),
            )
    except sqlite3.IntegrityError as error:
        raise ValueError("An account with this email already exists.") from error

    return normalized_email


def authenticate(email: str, password: str) -> str | None:
    try:
        normalized_email = _normalize_email(email)
    except ValueError:
        return None

    with _connection() as connection:
        row = connection.execute(
            "SELECT salt, password_hash, iterations FROM users WHERE email = ?",
            (normalized_email,),
        ).fetchone()

    if row is None:
        _password_hash(password, _DUMMY_SALT)
        return None

    salt, stored_hash, iterations = row
    candidate_hash = _password_hash(password, salt, iterations)
    if not hmac.compare_digest(candidate_hash, stored_hash):
        return None
    return normalized_email
