"""
Authentication and session management for PBPX.
Provides secure username/password handling with PBKDF2-HMAC-SHA256 and cryptographic session tokens.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from fastapi import Request, HTTPException, Security, status, Depends

from app.core.config import settings
from app.core.database import get_db_connection


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Generate PBKDF2-HMAC-SHA256 hash and salt for a password."""
    if not salt:
        salt = secrets.token_hex(16)
    salt_bytes = bytes.fromhex(salt)
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        200_000
    ).hex()
    return pw_hash, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verify password against stored hash using constant-time comparison."""
    computed_hash, _ = hash_password(password, salt=salt)
    return secrets.compare_digest(computed_hash, password_hash)


def count_users(db_path: str = None) -> int:
    """Return the total number of registered users."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    conn.close()
    return count


def create_user(
    username: str,
    password: str,
    is_admin: Optional[bool] = None,
    is_private: bool = False,
    db_path: str = None
) -> Dict[str, Any]:
    """Register a new user with hashed credentials."""
    username = username.strip()
    if not username or len(username) < 2:
        raise ValueError("Username must be at least 2 characters long.")
    if not password or len(password) < 4:
        raise ValueError("Password must be at least 4 characters long.")

    if is_admin is None:
        is_admin = (count_users(db_path) == 0)

    pw_hash, salt = hash_password(password)

    conn = get_db_connection(db_path)
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO users (username, password_hash, salt, is_admin, is_private, created_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (username, pw_hash, salt, 1 if is_admin else 0, 1 if is_private else 0))
        user_id = cur.lastrowid
        conn.commit()
    except Exception as e:
        conn.close()
        raise ValueError(f"Username '{username}' already exists.") from e

    conn.close()
    return {
        "id": user_id,
        "username": username,
        "is_admin": bool(is_admin),
        "is_private": bool(is_private)
    }


def authenticate_user(username: str, password: str, db_path: str = None) -> Optional[Dict[str, Any]]:
    """Validate username and password, returning user dict if valid."""
    username = username.strip()
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, username, password_hash, salt, is_admin, is_private, bio, avatar, favorite_console FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    if verify_password(password, row["password_hash"], row["salt"]):
        return {
            "id": row["id"],
            "username": row["username"],
            "is_admin": bool(row["is_admin"]),
            "is_private": bool(row["is_private"]),
            "bio": row["bio"] or "",
            "avatar": row["avatar"] or "memory_card",
            "favorite_console": row["favorite_console"] or "ALL"
        }
    return None


def create_session(user_id: int, days: int = 30, db_path: str = None) -> str:
    """Generate and record a secure session token."""
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    expires_str = expires_at.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO user_sessions (token, user_id, created_at, expires_at)
    VALUES (?, ?, CURRENT_TIMESTAMP, ?)
    """, (token, user_id, expires_str))
    conn.commit()
    conn.close()
    return token


def get_user_by_session(token: str, db_path: str = None) -> Optional[Dict[str, Any]]:
    """Look up active session token and return user details."""
    if not token or not isinstance(token, str):
        return None

    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    SELECT u.id, u.username, u.is_admin, u.is_private, u.bio, u.avatar, u.favorite_console, s.expires_at
    FROM user_sessions s
    JOIN users u ON s.user_id = u.id
    WHERE s.token = ?
    """, (token.strip(),))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    # Check expiration
    expires_str = row["expires_at"]
    try:
        # Parse ISO or SQLite timestamp
        expires_dt = datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_dt:
            destroy_session(token, db_path=db_path)
            return None
    except Exception:
        pass

    return {
        "id": row["id"],
        "username": row["username"],
        "is_admin": bool(row["is_admin"]),
        "is_private": bool(row["is_private"]),
        "bio": row["bio"] or "",
        "avatar": row["avatar"] or "memory_card",
        "favorite_console": row["favorite_console"] or "ALL"
    }


def destroy_session(token: str, db_path: str = None) -> None:
    """Invalidate and remove a session token."""
    if not token:
        return
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM user_sessions WHERE token = ?", (token.strip(),))
    conn.commit()
    conn.close()


def extract_session_token(request: Request) -> Optional[str]:
    """Extract session token from Authorization header, X-Session-Token, or cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    token_header = request.headers.get("X-Session-Token")
    if token_header:
        return token_header.strip()

    cookie_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if cookie_token:
        return cookie_token.strip()

    return request.cookies.get("demoscene_session")


async def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """Retrieve user if valid session exists; otherwise None."""
    token = extract_session_token(request)
    if not token:
        return None
    return get_user_by_session(token)


async def get_current_user(request: Request) -> Dict[str, Any]:
    """Require an authenticated user session; raises 401 otherwise."""
    user = await get_current_user_optional(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require an authenticated admin user; raises 403 otherwise."""
    if not user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required."
        )
    return user
